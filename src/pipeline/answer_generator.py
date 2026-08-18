"""Grounded answer generation for scheme-specific and general factual intents (FR-5, FR-6)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import Settings, get_settings
from src.pipeline.citation_validator import validate_citations
from src.pipeline.llm import LLMError, chat_json
from src.pipeline.models import Citation, Intent, RetrievedChunk
from src.prompts.answer_generator import ANSWER_SYSTEM_PROMPT

NOT_FOUND_MESSAGE = (
    "I could not find this information in the approved sources for this question."
)
UNABLE_TO_VERIFY_MESSAGE = (
    "I was unable to verify an answer from the approved sources for this question."
)

_ADVISORY_LEAK_PATTERNS = (
    r"\bshould\b",
    r"\brecommend\b",
    r"\bbest (?:choice|fund|option)\b",
    r"\bsuitable\b",
    r"\bgood fund\b",
    r"\binvest in\b",
    r"\bbuy\b",
    r"\bsell\b",
)

LlmGenerateFn = Callable[[str, list[RetrievedChunk]], dict[str, Any]]


@dataclass
class GeneratedAnswer:
    answer_text: str
    citations: list[Citation] = field(default_factory=list)
    last_updated_from_sources: str | None = None
    insufficient_context: bool = False
    citation_validation_failed: bool = False


def generate_grounded_answer(
    query: str,
    chunks: list[RetrievedChunk],
    *,
    intent: Intent,
    scheme_id: str | None = None,
    settings: Settings | None = None,
    llm_generate: LlmGenerateFn | None = None,
) -> GeneratedAnswer:
    """
    Produce a PRD-compliant factual answer from retrieved chunks only.

    Empty / insufficient retrieval → fail closed (EC-RET-04, EC-ANS-04).
    Citations must pass validator; one retry then safe fallback (EC-CIT-*).
    """
    settings = settings or get_settings()
    del intent  # reserved for future prompt variants

    if not chunks:
        return GeneratedAnswer(
            answer_text=NOT_FOUND_MESSAGE,
            insufficient_context=True,
        )

    if llm_generate is None:
        llm_generate = _default_llm_generate_factory(settings)

    draft = _safe_generate(llm_generate, query, chunks)
    result = _finalize_draft(draft, chunks, scheme_id=scheme_id)
    if result is not None:
        return result

    # One retry (Architecture §5.5)
    draft = _safe_generate(llm_generate, query, chunks, retry_hint=True)
    result = _finalize_draft(draft, chunks, scheme_id=scheme_id)
    if result is not None:
        return result

    return GeneratedAnswer(
        answer_text=UNABLE_TO_VERIFY_MESSAGE,
        insufficient_context=True,
        citation_validation_failed=True,
    )


def _safe_generate(
    llm_generate: LlmGenerateFn,
    query: str,
    chunks: list[RetrievedChunk],
    *,
    retry_hint: bool = False,
) -> dict[str, Any]:
    try:
        if retry_hint:
            query = (
                f"{query}\n\n"
                "(Retry) Your previous citations were invalid. "
                "Copy source_url values exactly from context only."
            )
        return llm_generate(query, chunks)
    except Exception as exc:  # noqa: BLE001 — fail closed, but do not fake empty retrieval
        return {
            "llm_error": True,
            "insufficient_context": False,
            "answer_text": "",
            "citation_urls": [],
            "error": str(exc),
        }


def _finalize_draft(
    draft: dict[str, Any],
    chunks: list[RetrievedChunk],
    *,
    scheme_id: str | None,
) -> GeneratedAnswer | None:
    if draft.get("llm_error"):
        return GeneratedAnswer(
            answer_text=UNABLE_TO_VERIFY_MESSAGE,
            insufficient_context=True,
            citation_validation_failed=True,
        )

    if draft.get("insufficient_context"):
        return GeneratedAnswer(
            answer_text=NOT_FOUND_MESSAGE,
            insufficient_context=True,
        )

    answer_text = _clean_answer_text(str(draft.get("answer_text") or ""))
    citation_urls = _coerce_urls(draft.get("citation_urls"))

    if not answer_text:
        return GeneratedAnswer(
            answer_text=NOT_FOUND_MESSAGE,
            insufficient_context=True,
        )

    # EC-ANS-03: strip advisory leakage rather than ship it
    if _has_advisory_leak(answer_text):
        answer_text = _strip_advisory_sentences(answer_text)
        if not answer_text:
            return None

    # Prefer model citations; if missing, try attaching top retrieved URL for retry path
    if not citation_urls:
        citation_urls = [chunks[0].source_url]

    validation = validate_citations(citation_urls, chunks, scheme_id=scheme_id)
    if not validation.ok:
        return None

    answer_text = _enforce_max_sentences(answer_text, max_sentences=3)
    stamped = answer_text
    if validation.last_updated_from_sources:
        stamped = (
            f"{answer_text}\n\n"
            f"Last updated from sources: {validation.last_updated_from_sources}"
        )

    return GeneratedAnswer(
        answer_text=stamped,
        citations=list(validation.citations),
        last_updated_from_sources=validation.last_updated_from_sources,
        insufficient_context=False,
    )


def _default_llm_generate_factory(settings: Settings) -> LlmGenerateFn:
    def _generate(query: str, chunks: list[RetrievedChunk]) -> dict[str, Any]:
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not configured.")
        user_content = _build_user_content(query, chunks)
        data = chat_json(
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_content=user_content,
            settings=settings,
        )
        return {
            "answer_text": data.get("answer_text", ""),
            "citation_urls": data.get("citation_urls") or [],
            "insufficient_context": bool(data.get("insufficient_context")),
        }

    return _generate


def _build_user_content(query: str, chunks: list[RetrievedChunk]) -> str:
    parts = [f"User question: {query}", "", "Context chunks:"]
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[{i}] source_url={chunk.source_url}\n"
            f"    source_title={chunk.source_title}\n"
            f"    scheme_id={chunk.scheme_id or '-'}\n"
            f"    page_ref={chunk.page_ref or '-'}\n"
            f"    scraped_at={chunk.scraped_at}\n"
            f"    text={chunk.text}"
        )
    return "\n".join(parts)


def _coerce_urls(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [str(u).strip() for u in raw if str(u).strip()]
    return []


def _clean_answer_text(text: str) -> str:
    text = text.strip()
    # Drop any model-appended stamp; we add our own from cited chunks
    text = re.sub(
        r"\n*Last updated from sources:.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()
    return text


def _enforce_max_sentences(text: str, max_sentences: int = 3) -> str:
    # Simple sentence split on .!? while keeping the delimiter
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [p for p in parts if p.strip()]
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()


def _has_advisory_leak(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in _ADVISORY_LEAK_PATTERNS)


def _strip_advisory_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p for p in parts if p.strip() and not _has_advisory_leak(p)]
    return " ".join(kept).strip()
