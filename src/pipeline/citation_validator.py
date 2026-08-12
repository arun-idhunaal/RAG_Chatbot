"""Post-generation / post-template citation checks (FR-6) — fail closed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

from src.config.schemes import get_scheme_by_id, get_scheme_by_url
from src.pipeline.models import Citation, RetrievedChunk

if TYPE_CHECKING:
    from src.pipeline.field_extractor import ExtractedField


@dataclass(frozen=True)
class CitationValidationResult:
    ok: bool
    citations: list[Citation]
    last_updated_from_sources: str | None = None
    reason: str | None = None


def normalize_url(url: str) -> str:
    """Normalize for comparison: strip fragment, trailing slash, lowercase host."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    path = (parsed.path or "").rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def is_exact_page_url(url: str) -> bool:
    """EC-CIT-01: reject domain-only citations (must have a real page path)."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    path = (parsed.path or "").rstrip("/")
    # Bare domain or "/" only → not an exact page
    return bool(path) and path != ""


def validate_citations(
    cited_urls: list[str],
    chunks: list[RetrievedChunk],
    *,
    scheme_id: str | None = None,
) -> CitationValidationResult:
    """
    Validate cited URLs against this turn's retrieved set.

    - EC-CIT-01: exact page URL (not domain-only)
    - EC-CIT-02: scheme answers must not cite another scheme's URL
    - EC-CIT-03: URL must be in the retrieved set
    - EC-CIT-04: date stamp from cited chunk scraped_at
    """
    if not cited_urls:
        return CitationValidationResult(ok=False, citations=[], reason="no_citations")

    by_url: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        key = normalize_url(chunk.source_url)
        if key and key not in by_url:
            by_url[key] = chunk

    retrieved_urls = set(by_url.keys())
    citations: list[Citation] = []
    cited_chunks: list[RetrievedChunk] = []

    for raw_url in cited_urls:
        url = (raw_url or "").strip()
        if not url:
            return CitationValidationResult(ok=False, citations=[], reason="empty_url")

        if not is_exact_page_url(url):
            return CitationValidationResult(ok=False, citations=[], reason="domain_only")

        key = normalize_url(url)
        if key not in retrieved_urls:
            return CitationValidationResult(ok=False, citations=[], reason="url_not_in_retrieved")

        chunk = by_url[key]

        # EC-CIT-02: wrong-scheme citation
        if scheme_id:
            if chunk.scheme_id and chunk.scheme_id != scheme_id:
                return CitationValidationResult(
                    ok=False, citations=[], reason="wrong_scheme_citation"
                )
            scheme = get_scheme_by_id(scheme_id)
            url_scheme = get_scheme_by_url(chunk.source_url)
            if url_scheme and url_scheme.scheme_id != scheme_id:
                return CitationValidationResult(
                    ok=False, citations=[], reason="wrong_scheme_citation"
                )
            if scheme and normalize_url(chunk.source_url) != normalize_url(scheme.source_url):
                # Allow other pages for same scheme if tagged correctly; only reject cross-scheme.
                # Already covered by chunk.scheme_id check above.
                pass

        citations.append(
            Citation(
                title=chunk.source_title or "Source",
                url=chunk.source_url,
                page_ref=chunk.page_ref,
            )
        )
        cited_chunks.append(chunk)

    stamp = _date_stamp_from_chunks(cited_chunks)
    return CitationValidationResult(
        ok=True,
        citations=citations,
        last_updated_from_sources=stamp,
    )


def validate_comparison_rows(rows: list[ExtractedField]) -> CitationValidationResult:
    """
    Harden comparison citations (EC-CIT-05, EC-CMP-01).

    Every available row must carry its own exact page URL for that scheme.
    Unavailable rows may omit a value but must not invent a cross-scheme URL.
    """
    if not rows:
        return CitationValidationResult(ok=False, citations=[], reason="no_rows")

    citations: list[Citation] = []
    dates: list[str] = []
    available_count = 0

    for row in rows:
        if not row.available:
            # EC-CMP-05: unavailable is OK; if a URL is present it must be exact page
            if row.source_url and not is_exact_page_url(row.source_url):
                return CitationValidationResult(
                    ok=False, citations=[], reason="domain_only"
                )
            if row.source_url:
                scheme = get_scheme_by_id(row.scheme_id)
                url_scheme = get_scheme_by_url(row.source_url)
                if url_scheme and url_scheme.scheme_id != row.scheme_id:
                    return CitationValidationResult(
                        ok=False, citations=[], reason="wrong_scheme_citation"
                    )
                if scheme and normalize_url(row.source_url) != normalize_url(
                    scheme.source_url
                ):
                    # Allow only that scheme's official URL for unavailable rows
                    if url_scheme is None or url_scheme.scheme_id != row.scheme_id:
                        return CitationValidationResult(
                            ok=False, citations=[], reason="wrong_scheme_citation"
                        )
            continue

        available_count += 1
        url = (row.source_url or "").strip()
        if not url:
            return CitationValidationResult(
                ok=False, citations=[], reason="missing_scheme_citation"
            )
        if not is_exact_page_url(url):
            return CitationValidationResult(ok=False, citations=[], reason="domain_only")

        url_scheme = get_scheme_by_url(url)
        if url_scheme and url_scheme.scheme_id != row.scheme_id:
            return CitationValidationResult(
                ok=False, citations=[], reason="wrong_scheme_citation"
            )
        # Prefer matching canonical scheme URL when known
        scheme = get_scheme_by_id(row.scheme_id)
        if scheme and url_scheme is None:
            # URL not in known scheme map — still reject if another scheme's URL
            other = get_scheme_by_url(url)
            if other and other.scheme_id != row.scheme_id:
                return CitationValidationResult(
                    ok=False, citations=[], reason="wrong_scheme_citation"
                )

        citations.append(
            Citation(title=row.scheme_name or "Source", url=url, page_ref=None)
        )
        day = to_yyyy_mm_dd(row.scraped_at)
        if day:
            dates.append(day)

    if available_count == 0:
        # All unavailable — still a valid fail-closed comparison (no invented values)
        return CitationValidationResult(
            ok=True,
            citations=citations,
            last_updated_from_sources=min(dates) if dates else None,
            reason="all_unavailable",
        )

    # EC-CIT-05: need one citation per available scheme row
    if len(citations) < available_count:
        return CitationValidationResult(
            ok=False, citations=[], reason="shared_or_missing_citation"
        )

    return CitationValidationResult(
        ok=True,
        citations=citations,
        last_updated_from_sources=min(dates) if dates else None,
    )


def _date_stamp_from_chunks(chunks: list[RetrievedChunk]) -> str | None:
    """EC-CIT-04 / FR-5: per-answer date from cited chunk scraped_at (not global ingest)."""
    dates: list[str] = []
    for chunk in chunks:
        day = to_yyyy_mm_dd(chunk.scraped_at)
        if day:
            dates.append(day)
    if not dates:
        return None
    # Prefer the earliest cited date when multiple (conservative freshness signal)
    return min(dates)


def to_yyyy_mm_dd(scraped_at: str) -> str | None:
    """Normalize scraped_at to YYYY-MM-DD for per-answer / per-citation stamps."""
    raw = (scraped_at or "").strip()
    if not raw:
        return None
    # Already a date
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        try:
            datetime.strptime(raw[:10], "%Y-%m-%d")
            return raw[:10]
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        return None


# Back-compat alias for internal callers
_to_yyyy_mm_dd = to_yyyy_mm_dd
