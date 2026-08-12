"""Pure rendering helpers for Streamlit chat answers (testable without Streamlit)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from src.config.schemes import list_canonical_names
from src.pipeline.models import Citation, Intent, PipelineResult
from src.pipeline.refusal_templates import ADVISORY_REFUSAL

_URL_RE = re.compile(r"(https?://[^\s<>\]\)]+)")
_DATE_STAMP_RE = re.compile(
    r"Last updated from sources:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


@dataclass
class AssistantView:
    """Structured payload the UI stores and re-renders (no server-side history beyond session)."""

    intent: str
    fact_text: str
    refusal_text: str | None = None
    citations: list[dict[str, str | None]] = field(default_factory=list)
    last_updated_from_sources: str | None = None
    supported_schemes: list[str] = field(default_factory=list)
    is_mixed: bool = False
    is_pii: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "fact_text": self.fact_text,
            "refusal_text": self.refusal_text,
            "citations": self.citations,
            "last_updated_from_sources": self.last_updated_from_sources,
            "supported_schemes": self.supported_schemes,
            "is_mixed": self.is_mixed,
            "is_pii": self.is_pii,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssistantView:
        return cls(
            intent=str(data.get("intent") or ""),
            fact_text=str(data.get("fact_text") or ""),
            refusal_text=data.get("refusal_text"),
            citations=list(data.get("citations") or []),
            last_updated_from_sources=data.get("last_updated_from_sources"),
            supported_schemes=list(data.get("supported_schemes") or []),
            is_mixed=bool(data.get("is_mixed")),
            is_pii=bool(data.get("is_pii")),
        )


def build_assistant_view(result: PipelineResult) -> AssistantView:
    """Map orchestrator output → UI blocks (EC-UI-03…05)."""
    answer = (result.answer_text or result.refusal_message or "").strip()
    stamp = result.last_updated_from_sources or _extract_date_stamp(answer)
    citations = _citations_as_dicts(result.citations)
    schemes = list(result.supported_schemes or [])
    if result.intent == Intent.UNSUPPORTED_SCHEME and not schemes:
        schemes = list_canonical_names()

    is_mixed = bool(result.refusal_appended) or result.intent == Intent.MIXED
    if is_mixed:
        fact_text, refusal_text = split_mixed_answer(
            answer,
            refusal_message=result.refusal_message,
        )
    else:
        fact_text, refusal_text = answer, None

    # Ensure date stamp is present inline on factual / mixed fact blocks (EC-UI-03).
    if stamp and citations and not _DATE_STAMP_RE.search(fact_text):
        fact_text = f"{fact_text.rstrip()}\n\nLast updated from sources: {stamp}"

    return AssistantView(
        intent=result.intent.value,
        fact_text=fact_text,
        refusal_text=refusal_text,
        citations=citations,
        last_updated_from_sources=stamp,
        supported_schemes=schemes,
        is_mixed=is_mixed,
        is_pii=result.intent == Intent.PII,
    )


def split_mixed_answer(
    answer_text: str,
    *,
    refusal_message: str | None = None,
) -> tuple[str, str]:
    """
    Split FR-8 fact-then-refusal into two blocks (EC-UI-04 / EC-MIX-02).

    Prefer the known refusal message when provided; otherwise split on advisory copy.
    """
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

    # Fallback: last double-newline paragraph is refusal.
    parts = re.split(r"\n\s*\n", text)
    if len(parts) >= 2 and "investment advice" in parts[-1].lower():
        return "\n\n".join(parts[:-1]).strip(), parts[-1].strip()

    return text, refusal or ADVISORY_REFUSAL


def linkify_urls(text: str) -> str:
    """Turn bare http(s) URLs into markdown links (EC-UI-03 clickable citations)."""

    def _replace(match: re.Match[str]) -> str:
        url = match.group(1).rstrip(".,;)")
        return f"[{_link_label(url)}]({url})"

    return _URL_RE.sub(_replace, text or "")


def citations_markdown(citations: list[dict[str, str | None]]) -> str:
    """Inline citation list with clickable links."""
    if not citations:
        return ""
    lines = ["**Sources:**"]
    for i, c in enumerate(citations, 1):
        url = (c.get("url") or "").strip()
        title = (c.get("title") or "").strip() or _link_label(url)
        if not url:
            continue
        lines.append(f"{i}. [{title}]({url})")
    return "\n".join(lines) if len(lines) > 1 else ""


def date_stamp_markdown(date: str | None) -> str:
    if not date:
        return ""
    return f"Last updated from sources: {date}"


def has_all_supported_schemes(text: str, scheme_names: list[str] | None = None) -> bool:
    """EC-UI-05 — FR-9 answers list all 5 canonical names."""
    names = scheme_names or list_canonical_names()
    lower = (text or "").lower()
    return all(n.lower() in lower for n in names)


def _citations_as_dicts(citations: list[Citation]) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for c in citations:
        url = (c.url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": c.title or _link_label(url), "url": url, "page_ref": c.page_ref})
    return out


def _extract_date_stamp(text: str) -> str | None:
    match = _DATE_STAMP_RE.search(text or "")
    return match.group(1) if match else None


def _link_label(url: str) -> str:
    try:
        host = urlparse(url).netloc or url
        path = urlparse(url).path.rstrip("/")
        if path:
            slug = path.rsplit("/", 1)[-1]
            if slug:
                return slug.replace("-", " ")[:60]
        return host
    except Exception:
        return url[:60]
