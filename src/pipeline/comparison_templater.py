"""Deterministic comparison answer templating (FR-4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.pipeline.citation_validator import to_yyyy_mm_dd, validate_comparison_rows
from src.pipeline.field_extractor import (
    FIELD_DISPLAY_NAMES,
    ExtractedField,
)
from src.pipeline.models import Citation

_BETTER_CHOICE_PATTERNS = (
    r"\bbetter choice\b",
    r"\bbest (?:choice|fund|option)\b",
    r"\brecommend\b",
    r"\bshould (?:pick|choose|buy|invest)\b",
    r"\bpick\b.+\bscheme\b",
)

UNAVAILABLE_LABEL = "unavailable from sources"
UNABLE_TO_VERIFY_COMPARISON = (
    "I was unable to verify a comparison from the approved sources for this question."
)
UNSUPPORTED_FIELD_MESSAGE = (
    "I can only compare these fields across the supported schemes: "
    "expense ratio, exit load, minimum SIP, lock-in, riskometer, and benchmark. "
    "I don't build comparison tables for other attributes."
)


@dataclass
class ComparisonAnswer:
    answer_text: str
    citations: list[Citation] = field(default_factory=list)
    last_updated_from_sources: str | None = None
    rows: list[ExtractedField] = field(default_factory=list)
    insufficient_context: bool = False
    citation_validation_failed: bool = False


def render_comparison(
    rows: list[ExtractedField],
    *,
    field: str,
    include_lowest_note: bool = True,
) -> ComparisonAnswer:
    """
    Render FR-4 comparison: each scheme value + own citation (EC-CMP-01, EC-CIT-05).

    - Missing extract → unavailable row, no guess (EC-CMP-05)
    - Bare ranking still shows all values (EC-CMP-02)
    - No \"better choice\" language (EC-CMP-06)
    - Optional factual \"lower than\" / lowest only when numeric values support it
    """
    if not rows:
        return ComparisonAnswer(
            answer_text=UNABLE_TO_VERIFY_COMPARISON,
            insufficient_context=True,
        )

    validation = validate_comparison_rows(rows)
    if not validation.ok:
        return ComparisonAnswer(
            answer_text=UNABLE_TO_VERIFY_COMPARISON,
            rows=list(rows),
            insufficient_context=True,
            citation_validation_failed=True,
        )

    field_label = FIELD_DISPLAY_NAMES.get(field, field.replace("_", " "))
    lines: list[str] = [f"Comparison of {field_label} across the supported schemes:"]
    citations: list[Citation] = []
    dates: list[str] = []

    for row in rows:
        day = to_yyyy_mm_dd(row.scraped_at) if row.scraped_at else None
        if row.available and row.value:
            stamp = f" (as of {day})" if day else ""
            lines.append(
                f"- {row.scheme_name}: {row.value}{stamp} — Source: {row.source_url}"
            )
            citations.append(
                Citation(title=row.scheme_name, url=row.source_url, page_ref=None)
            )
            if day:
                dates.append(day)
        else:
            # Still point at the scheme page when we attempted extract (EC-CMP-05)
            url_note = f" — See: {row.source_url}" if row.source_url else ""
            lines.append(
                f"- {row.scheme_name}: {UNAVAILABLE_LABEL}{url_note}"
            )
            if row.source_url:
                citations.append(
                    Citation(title=row.scheme_name, url=row.source_url, page_ref=None)
                )

    if include_lowest_note:
        note = _factual_lowest_note(rows, field=field)
        if note:
            lines.append(note)

    answer = "\n".join(lines)
    # EC-CMP-06: strip any advisory leakage if somehow present
    if _has_better_choice_language(answer):
        answer = _strip_better_choice_lines(answer)

    stamp = min(dates) if dates else validation.last_updated_from_sources
    if stamp:
        answer = f"{answer}\n\nLast updated from sources: {stamp}"

    return ComparisonAnswer(
        answer_text=answer,
        citations=citations,
        last_updated_from_sources=stamp,
        rows=list(rows),
        insufficient_context=not any(r.available for r in rows),
    )


def _factual_lowest_note(rows: list[ExtractedField], *, field: str) -> str | None:
    """Optional factual comparative phrasing when values support it (FR-4)."""
    if field != "expense_ratio":
        return None

    parsed: list[tuple[ExtractedField, float]] = []
    for row in rows:
        if not row.available or not row.value:
            continue
        num = _parse_percent(row.value)
        if num is not None:
            parsed.append((row, num))

    if len(parsed) < 2:
        return None

    parsed.sort(key=lambda x: x[1])
    lowest_row, lowest_val = parsed[0]
    # Tie: mention all tied schemes factually
    tied = [r for r, v in parsed if abs(v - lowest_val) < 1e-9]
    if len(tied) > 1:
        names = ", ".join(r.scheme_name for r in tied)
        return (
            f"Among schemes with available values, these share the lowest "
            f"expense ratio ({tied[0].value}): {names}."
        )
    return (
        f"Among schemes with available values, {lowest_row.scheme_name} has the "
        f"lowest expense ratio ({lowest_row.value})."
    )


def _parse_percent(value: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _has_better_choice_language(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in _BETTER_CHOICE_PATTERNS)


def _strip_better_choice_lines(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if _has_better_choice_language(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()
