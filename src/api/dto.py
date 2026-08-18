"""HTTP DTOs for POST /v1/chat — no chunk text, no PII echo (Architecture §6.1)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.config.schemes import SCHEMES, list_canonical_names
from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE
from src.pipeline.field_extractor import ExtractedField
from src.pipeline.models import Citation, Intent, PipelineResult
from src.pipeline.refusal_templates import ADVISORY_REFUSAL
from src.ui_copy import (
    DISCLAIMER,
    EXAMPLE_QUESTIONS,
    PII_USER_PLACEHOLDER,
    WELCOME_MESSAGE,
)

_URL_RE = re.compile(r"(https?://[^\s<>\]\)]+)")
_DATE_STAMP_RE = re.compile(
    r"Last updated from sources:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=8000)


class CitationOut(BaseModel):
    title: str
    url: str
    page_ref: str | None = None


class ComparisonRowOut(BaseModel):
    scheme_id: str
    scheme_name: str
    field: str
    value: str | None = None
    source_url: str = ""
    scraped_at: str = ""
    available: bool = False


class ChatResponse(BaseModel):
    intent: str
    answer_text: str
    refusal_message: str | None = None
    refusal_appended: bool = False
    citations: list[CitationOut] = Field(default_factory=list)
    last_updated_from_sources: str | None = None
    supported_schemes: list[str] = Field(default_factory=list)
    comparison_field: str | None = None
    comparison_rows: list[ComparisonRowOut] = Field(default_factory=list)
    insufficient_context: bool = False
    corpus_available: bool = True


class SchemeOut(BaseModel):
    scheme_id: str
    canonical_name: str
    source_url: str


class UiConfigResponse(BaseModel):
    disclaimer: str
    welcome_message: str
    example_questions: list[str]
    pii_user_placeholder: str
    schemes: list[SchemeOut]


class HealthResponse(BaseModel):
    ok: bool
    corpus_available: bool
    scheme_count: int = 0
    general_count: int = 0
    reason: str | None = None
    message: str | None = None


def ui_config() -> UiConfigResponse:
    return UiConfigResponse(
        disclaimer=DISCLAIMER,
        welcome_message=WELCOME_MESSAGE,
        example_questions=list(EXAMPLE_QUESTIONS),
        pii_user_placeholder=PII_USER_PLACEHOLDER,
        schemes=[
            SchemeOut(
                scheme_id=s.scheme_id,
                canonical_name=s.canonical_name,
                source_url=s.source_url,
            )
            for s in SCHEMES
        ],
    )


def corpus_unavailable_response() -> ChatResponse:
    return ChatResponse(
        intent="unavailable",
        answer_text=CORPUS_UNAVAILABLE_MESSAGE,
        corpus_available=False,
        insufficient_context=True,
    )


def pipeline_result_to_chat_response(result: PipelineResult) -> ChatResponse:
    """Map orchestrator output → public JSON (never includes original_message)."""
    answer = (result.answer_text or result.refusal_message or "").strip()
    stamp = result.last_updated_from_sources or _extract_date_stamp(answer)
    citations = _citations_out(result.citations)
    schemes = list(result.supported_schemes or [])
    if result.intent == Intent.UNSUPPORTED_SCHEME and not schemes:
        schemes = list_canonical_names()

    is_mixed = bool(result.refusal_appended) or result.intent == Intent.MIXED
    refusal_message = result.refusal_message
    if is_mixed:
        fact_text, refusal_message = split_mixed_answer(
            answer,
            refusal_message=result.refusal_message,
        )
        answer_text = fact_text
    else:
        answer_text = answer

    if stamp and citations and not _DATE_STAMP_RE.search(answer_text):
        answer_text = f"{answer_text.rstrip()}\n\nLast updated from sources: {stamp}"

    return ChatResponse(
        intent=result.intent.value,
        answer_text=answer_text,
        refusal_message=refusal_message if is_mixed else (
            result.refusal_message if result.intent in {
                Intent.ADVISORY,
                Intent.PII,
                Intent.UNSUPPORTED_SCHEME,
                Intent.OUT_OF_CORPUS_FACT_TYPE,
            }
            else None
        ),
        refusal_appended=is_mixed,
        citations=citations,
        last_updated_from_sources=stamp,
        supported_schemes=schemes,
        comparison_field=result.comparison_field,
        comparison_rows=_rows_out(result.comparison_rows),
        insufficient_context=bool(result.insufficient_context),
        corpus_available=True,
    )


def split_mixed_answer(
    answer_text: str,
    *,
    refusal_message: str | None = None,
) -> tuple[str, str]:
    """Split FR-8 fact-then-refusal into two blocks (EC-UI-04)."""
    text = (answer_text or "").strip()
    refusal = (refusal_message or "").strip()

    if refusal and refusal in text:
        idx = text.rfind(refusal)
        fact = text[:idx].strip()
        return fact, refusal

    if ADVISORY_REFUSAL in text:
        idx = text.find(ADVISORY_REFUSAL)
        fact = text[:idx].strip()
        refusal_block = text[idx:].strip()
        return fact, refusal_block

    parts = re.split(r"\n\s*\n", text)
    if len(parts) >= 2 and "investment advice" in parts[-1].lower():
        return "\n\n".join(parts[:-1]).strip(), parts[-1].strip()

    return text, refusal or ADVISORY_REFUSAL


def citations_markdown(citations: list[dict[str, str | None]] | list[CitationOut]) -> str:
    if not citations:
        return ""
    lines = ["**Sources:**"]
    for i, c in enumerate(citations, 1):
        if isinstance(c, CitationOut):
            url, title = c.url, c.title
        else:
            url = (c.get("url") or "").strip()
            title = (c.get("title") or "").strip() or _link_label(url)
        if not url:
            continue
        lines.append(f"{i}. [{title}]({url})")
    return "\n".join(lines) if len(lines) > 1 else ""


def linkify_urls(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        url = match.group(1).rstrip(".,;)")
        return f"[{_link_label(url)}]({url})"

    return _URL_RE.sub(_replace, text or "")


def has_all_supported_schemes(text: str, scheme_names: list[str] | None = None) -> bool:
    names = scheme_names or list_canonical_names()
    lower = (text or "").lower()
    return all(n.lower() in lower for n in names)


def _citations_out(citations: list[Citation]) -> list[CitationOut]:
    out: list[CitationOut] = []
    seen: set[str] = set()
    for c in citations:
        url = (c.url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            CitationOut(
                title=c.title or _link_label(url),
                url=url,
                page_ref=c.page_ref,
            )
        )
    return out


def _rows_out(rows: list[Any]) -> list[ComparisonRowOut]:
    out: list[ComparisonRowOut] = []
    for row in rows or []:
        if isinstance(row, ExtractedField):
            out.append(
                ComparisonRowOut(
                    scheme_id=row.scheme_id,
                    scheme_name=row.scheme_name,
                    field=row.field,
                    value=row.value,
                    source_url=row.source_url,
                    scraped_at=row.scraped_at,
                    available=row.available,
                )
            )
        elif isinstance(row, dict):
            out.append(ComparisonRowOut.model_validate(row))
    return out


def _extract_date_stamp(text: str) -> str | None:
    match = _DATE_STAMP_RE.search(text or "")
    return match.group(1) if match else None


def _link_label(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or url
        path = parsed.path.rstrip("/")
        if path:
            slug = path.rsplit("/", 1)[-1]
            if slug:
                return slug.replace("-", " ")[:60]
        return host
    except Exception:
        return url[:60]
