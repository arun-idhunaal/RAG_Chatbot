"""Structured field extraction for cross-scheme comparisons (FR-4)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.config.schemes import get_scheme_by_id
from src.config.settings import Settings, get_settings
from src.pipeline.llm import LLMError, chat_json
from src.pipeline.models import RetrievedChunk
from src.prompts.field_extractor import FIELD_EXTRACTOR_SYSTEM_PROMPT

# FR-4 allowed comparison fields only (EC-CMP-01, EC-CMP-08).
COMPARISON_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "expense_ratio",
        "exit_load",
        "min_sip",
        "lock_in",
        "riskometer",
        "benchmark",
    }
)

FIELD_DISPLAY_NAMES: dict[str, str] = {
    "expense_ratio": "expense ratio",
    "exit_load": "exit load",
    "min_sip": "minimum SIP",
    "lock_in": "lock-in",
    "riskometer": "riskometer",
    "benchmark": "benchmark",
}

def field_retrieval_query(field: str) -> str:
    """Embedding query for FR-4 retrieve — field labels, not ranking language."""
    label = FIELD_DISPLAY_NAMES.get(field, field.replace("_", " "))
    extras = {
        "expense_ratio": "total expense ratio TER Direct Plan Growth",
        "exit_load": "exit load redemption load",
        "min_sip": "minimum SIP amount",
        "lock_in": "lock-in period ELSS",
        "riskometer": "riskometer risk level",
        "benchmark": "benchmark index",
    }
    extra = extras.get(field, "")
    return f"{label} {extra}".strip()


# Regex fallbacks when LLM is unavailable or fails.
_PERCENT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[%％]|percent\b|per\s*cent\b)",
    re.IGNORECASE,
)
_BARE_NUMBER = re.compile(r"(\d+\.\d+)")
_MONTH = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)
_LABEL_RE = re.compile(
    r"(?:total\s*)?expense\s*ratio|expenseratio|\bter\b",
    re.IGNORECASE,
)
_REGEX_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "expense_ratio": (
        # Kept for simple "Expense ratio is 0.65%" lines; dated INDmoney
        # cards are handled by _extract_expense_ratio (skips "as on 31 Jul").
        re.compile(
            r"(?:expense\s*ratio|total\s*expense\s*ratio|\bter\b)"
            r"[^\d%]{0,60}(\d+(?:\.\d+)?\s*%)",
            re.IGNORECASE,
        ),
        re.compile(r"(\d+(?:\.\d+)?\s*%)[^\n]{0,40}expense\s*ratio", re.IGNORECASE),
    ),
    "exit_load": (
        re.compile(
            r"(?:exit\s*load|redemption\s*load)[:\s]+([^\n.]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(r"(nil|none|0%|zero)[^\n.]{0,40}exit\s*load", re.IGNORECASE),
    ),
    "min_sip": (
        re.compile(
            r"(?:minimum\s*sip|min\.?\s*sip|min\s*sip|sip\s*amount)"
            r"[^\d₹Rs]{0,40}(?:₹|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    "lock_in": (
        re.compile(
            r"(?:lock[\s-]?in)[:\s]+([^\n.]{3,80})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:lock[\s-]?in(?:\s*period)?)[^\d]{0,30}(\d+\s*(?:years?|yrs?|months?))",
            re.IGNORECASE,
        ),
        re.compile(r"\b(no\s+lock[\s-]?in|nil\s+lock[\s-]?in)\b", re.IGNORECASE),
    ),
    "riskometer": (
        re.compile(
            r"(?:riskometer|risk[\s-]?o[\s-]?meter|risk\s*level|risk\s*category)"
            r"[:\s]+([A-Za-z][A-Za-z\s-]{2,40})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b((?:very\s+)?(?:high|moderate|low|moderately\s+high)\s+risk)\b",
            re.IGNORECASE,
        ),
    ),
    "benchmark": (
        re.compile(
            r"(?:benchmark|benchmark\s*index|tracks\s+the)[:\s]+([^\n.]{3,100})",
            re.IGNORECASE,
        ),
    ),
}

LlmExtractFn = Callable[[str, str, list[RetrievedChunk]], dict[str, Any]]


@dataclass(frozen=True)
class ExtractedField:
    """Structured per-scheme field record for FR-4 templating."""

    scheme_id: str
    scheme_name: str
    field: str
    value: str | None
    source_url: str
    scraped_at: str
    available: bool


def is_allowed_comparison_field(field: str | None) -> bool:
    return bool(field) and field in COMPARISON_ALLOWED_FIELDS


def extract_field_for_scheme(
    scheme_id: str,
    field: str,
    chunks: list[RetrievedChunk],
    *,
    settings: Settings | None = None,
    llm_extract: LlmExtractFn | None = None,
) -> ExtractedField:
    """
    Extract one field value for one scheme from scheme-filtered chunks.

    Fail closed on missing extract (EC-CMP-05) — available=False, no guess.
    """
    settings = settings or get_settings()
    scheme = get_scheme_by_id(scheme_id)
    scheme_name = scheme.canonical_name if scheme else scheme_id
    fallback_url = scheme.source_url if scheme else ""
    fallback_scraped = chunks[0].scraped_at if chunks else ""

    if field not in COMPARISON_ALLOWED_FIELDS:
        return ExtractedField(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            field=field,
            value=None,
            source_url=fallback_url,
            scraped_at=fallback_scraped,
            available=False,
        )

    scheme_chunks = [c for c in chunks if c.scheme_id == scheme_id]
    if not scheme_chunks:
        return ExtractedField(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            field=field,
            value=None,
            source_url=fallback_url,
            scraped_at=fallback_scraped,
            available=False,
        )

    # Prefer deterministic regex first (citation-safe, testable).
    regex_hit = _regex_extract(field, scheme_chunks)
    if regex_hit is not None:
        return ExtractedField(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            field=field,
            value=regex_hit["value"],
            source_url=regex_hit["source_url"],
            scraped_at=regex_hit["scraped_at"],
            available=True,
        )

    if llm_extract is None and settings.groq_api_key:
        llm_extract = _default_llm_extract_factory(settings)

    if llm_extract is not None:
        try:
            draft = llm_extract(scheme_id, field, scheme_chunks)
            finalized = _finalize_llm_extract(
                draft,
                scheme_id=scheme_id,
                scheme_name=scheme_name,
                field=field,
                chunks=scheme_chunks,
                fallback_url=fallback_url,
            )
            if finalized is not None:
                return finalized
            # One retry
            draft = llm_extract(scheme_id, field, scheme_chunks)
            finalized = _finalize_llm_extract(
                draft,
                scheme_id=scheme_id,
                scheme_name=scheme_name,
                field=field,
                chunks=scheme_chunks,
                fallback_url=fallback_url,
            )
            if finalized is not None:
                return finalized
        except Exception:  # noqa: BLE001 — fail closed
            pass

    return ExtractedField(
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        field=field,
        value=None,
        source_url=scheme_chunks[0].source_url or fallback_url,
        scraped_at=scheme_chunks[0].scraped_at or fallback_scraped,
        available=False,
    )


def extract_field_for_all_schemes(
    field: str,
    chunks_by_scheme: dict[str, list[RetrievedChunk]],
    *,
    scheme_ids: list[str],
    settings: Settings | None = None,
    llm_extract: LlmExtractFn | None = None,
) -> list[ExtractedField]:
    """Extract the same field for each scheme (FR-4)."""
    rows: list[ExtractedField] = []
    for scheme_id in scheme_ids:
        rows.append(
            extract_field_for_scheme(
                scheme_id,
                field,
                chunks_by_scheme.get(scheme_id, []),
                settings=settings,
                llm_extract=llm_extract,
            )
        )
    return rows


def _regex_extract(field: str, chunks: list[RetrievedChunk]) -> dict[str, str] | None:
    tagged = [c for c in chunks if field in (c.fact_types or [])]
    ordered = tagged + [c for c in chunks if c not in tagged]
    patterns = _REGEX_PATTERNS.get(field, ())
    for chunk in ordered:
        text = chunk.text or ""
        value: str | None = None
        if field == "expense_ratio":
            value = _extract_expense_ratio(text)
        if value is None:
            for pattern in patterns:
                match = pattern.search(text)
                if not match:
                    continue
                raw = match.group(1).strip() if match.lastindex else match.group(0).strip()
                value = re.sub(r"\s+", " ", raw).strip(" :,-")
                if value:
                    break
        if not value:
            continue
        return {
            "value": value,
            "source_url": chunk.source_url,
            "scraped_at": chunk.scraped_at,
        }
    return None


def _extract_expense_ratio(text: str) -> str | None:
    """Parse Direct-plan TER, skipping dates; allow values without a % sign."""
    lower = text.lower()
    match = _LABEL_RE.search(lower)
    if not match:
        return None
    label_idx = match.start()
    window = text[label_idx : label_idx + 500]
    window_l = window.lower()

    plausible: list[re.Match[str]] = []
    for found in _PERCENT.finditer(window):
        amount = _safe_float(found.group(1))
        if amount is not None and 0.01 <= amount <= 6.0:
            plausible.append(found)

    if not plausible:
        for found in _BARE_NUMBER.finditer(window):
            if _looks_like_date_number(window, found):
                continue
            amount = _safe_float(found.group(1))
            if amount is not None and 0.01 <= amount <= 6.0:
                plausible.append(found)

    if not plausible:
        return None

    direct_span = re.search(
        r"\bdirect\b.{0,40}?(\d+\.\d+)",
        window_l,
        re.IGNORECASE | re.DOTALL,
    )
    if direct_span:
        amount = _safe_float(direct_span.group(1))
        if amount is not None and 0.01 <= amount <= 6.0:
            return f"{direct_span.group(1)}%"
    return f"{plausible[0].group(1)}%"


def _safe_float(raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        return None


def _looks_like_date_number(window: str, match: re.Match[str]) -> bool:
    around = window[max(0, match.start() - 24) : match.end() + 24]
    if _MONTH.search(around):
        return True
    if re.fullmatch(r"20\d{2}", match.group(1)):
        return True
    return False


def _finalize_llm_extract(
    draft: dict[str, Any],
    *,
    scheme_id: str,
    scheme_name: str,
    field: str,
    chunks: list[RetrievedChunk],
    fallback_url: str,
) -> ExtractedField | None:
    if not draft.get("available", False):
        return None

    value = draft.get("value")
    if value is None or str(value).strip() == "" or str(value).lower() == "null":
        return None

    source_url = str(draft.get("source_url") or "").strip()
    allowed_urls = {c.source_url for c in chunks if c.source_url}
    if source_url not in allowed_urls:
        # Fall back to first chunk URL if model omitted/mangled URL but value looks present
        if chunks:
            source_url = chunks[0].source_url
        else:
            return None

    scraped_at = str(draft.get("scraped_at") or "")
    if not scraped_at:
        for c in chunks:
            if c.source_url == source_url:
                scraped_at = c.scraped_at
                break
        if not scraped_at and chunks:
            scraped_at = chunks[0].scraped_at

    return ExtractedField(
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        field=field,
        value=str(value).strip(),
        source_url=source_url or fallback_url,
        scraped_at=scraped_at,
        available=True,
    )


def _default_llm_extract_factory(settings: Settings) -> LlmExtractFn:
    def _extract(scheme_id: str, field: str, chunks: list[RetrievedChunk]) -> dict[str, Any]:
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not configured.")
        parts = [
            f"scheme_id={scheme_id}",
            f"field={field}",
            "",
            "Context chunks:",
        ]
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[{i}] source_url={chunk.source_url}\n"
                f"    scraped_at={chunk.scraped_at}\n"
                f"    text={chunk.text}"
            )
        data = chat_json(
            system_prompt=FIELD_EXTRACTOR_SYSTEM_PROMPT,
            user_content="\n".join(parts),
            settings=settings,
        )
        return data

    return _extract
