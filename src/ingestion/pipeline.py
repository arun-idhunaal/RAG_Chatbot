"""Full ingest orchestration with partial-failure safety (EC-ING-01…04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import httpx

from src.config.settings import Settings, get_settings
from src.config.sources import SourceConfig, all_sources, get_source_by_url
from src.ingestion.audit import write_audit_log
from src.ingestion.chunk import chunk_document
from src.ingestion.clean import clean_page
from src.ingestion.embed import EmbeddingError
from src.ingestion.fetch import fetch_url
from src.ingestion.models import UrlAuditEntry
from src.ingestion.store import VectorStore

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class IngestReport:
    started_at: str
    finished_at: str
    urls_attempted: int
    urls_ok: int
    urls_unchanged: int
    urls_failed: int
    urls_empty: int
    urls_stale_kept: int
    scheme_chunks: int
    general_chunks: int
    chunks_by_scheme: dict[str, int] = field(default_factory=dict)
    audit_path: str | None = None
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Ingest Report ===",
            f"Started:  {self.started_at}",
            f"Finished: {self.finished_at}",
            f"URLs attempted: {self.urls_attempted}",
            f"  ok: {self.urls_ok} | unchanged: {self.urls_unchanged} | "
            f"empty: {self.urls_empty} | failed: {self.urls_failed} | stale_kept: {self.urls_stale_kept}",
            f"Collection counts — scheme: {self.scheme_chunks}, general: {self.general_chunks}",
            "Chunks by scheme_id:",
        ]
        for sid, count in sorted(self.chunks_by_scheme.items()):
            lines.append(f"  {sid}: {count}")
        if self.audit_path:
            lines.append(f"Audit log: {self.audit_path}")
        if self.errors:
            lines.append("Errors:")
            for err in self.errors[:20]:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def run_ingest(
    *,
    urls: Iterable[str] | None = None,
    settings: Settings | None = None,
    store: VectorStore | None = None,
    skip_embed: bool = False,
    save_raw: bool = True,
) -> IngestReport:
    """
    Ingest SOURCE_LIST (or a subset).

    Failure rules:
    - Single URL scrape fail → keep last-good chunks (EC-ING-01)
    - Empty extract → do not delete prior chunks (EC-ING-02)
    - Embedding failure → abort remaining upserts; do not wipe index (EC-ING-03)
    - Same content_hash → skip re-embed (EC-ING-04)
    """
    settings = settings or get_settings()
    store = store or VectorStore(settings)
    started = datetime.now(tz=IST)

    if urls is None:
        sources: list[SourceConfig] = list(all_sources())
    else:
        sources = []
        for u in urls:
            src = get_source_by_url(u)
            if src is None:
                raise ValueError(f"URL not in SOURCE_LIST: {u}")
            sources.append(src)

    audit: list[UrlAuditEntry] = []
    errors: list[str] = []
    ok = unchanged = failed = empty = stale_kept = 0
    embed_aborted = False

    with httpx.Client(
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    ) as client:
        for source in sources:
            if embed_aborted:
                # Still record remaining as skipped after abort? Mark error.
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="error",
                        chunk_count=store.count_for_url(source.corpus, source.url),
                        scraped_at=datetime.now(tz=IST).isoformat(),
                        error="aborted_after_embedding_failure",
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                failed += 1
                continue

            page = fetch_url(source, settings=settings, client=client, save_raw=save_raw)
            scraped_at = page.scraped_at.isoformat()

            if page.status == "error":
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="stale_kept" if kept else "error",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        error=page.error,
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                if kept:
                    stale_kept += 1
                else:
                    failed += 1
                errors.append(f"{source.url}: scrape failed — {page.error}")
                continue

            if page.status == "empty":
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="empty",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        error="empty_html",
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                empty += 1
                # EC-ING-02: do not delete prior chunks
                continue

            cleaned = clean_page(page)
            if cleaned is None or not cleaned.text.strip():
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="empty",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        error="empty_extract",
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                empty += 1
                continue

            existing_hash = store.existing_content_hash(source.corpus, source.url)
            if existing_hash and existing_hash == cleaned.content_hash:
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="unchanged",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        content_hash=cleaned.content_hash,
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                unchanged += 1
                continue

            chunks = chunk_document(cleaned, settings=settings)
            if not chunks:
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="empty",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        error="no_chunks_after_filter",
                        content_hash=cleaned.content_hash,
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                empty += 1
                continue

            if skip_embed:
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="ok",
                        chunk_count=len(chunks),
                        scraped_at=scraped_at,
                        content_hash=cleaned.content_hash,
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                ok += 1
                continue

            try:
                store.upsert_chunks(chunks)
            except EmbeddingError as exc:
                embed_aborted = True
                kept = store.count_for_url(source.corpus, source.url)
                audit.append(
                    UrlAuditEntry(
                        url=source.url,
                        status="stale_kept" if kept else "error",
                        chunk_count=kept,
                        scraped_at=scraped_at,
                        error=str(exc),
                        content_hash=cleaned.content_hash,
                        scheme_id=source.scheme_id,
                        corpus=source.corpus,
                    )
                )
                if kept:
                    stale_kept += 1
                else:
                    failed += 1
                errors.append(f"{source.url}: {exc}")
                continue

            audit.append(
                UrlAuditEntry(
                    url=source.url,
                    status="ok",
                    chunk_count=len(chunks),
                    scraped_at=scraped_at,
                    content_hash=cleaned.content_hash,
                    scheme_id=source.scheme_id,
                    corpus=source.corpus,
                )
            )
            ok += 1

    finished = datetime.now(tz=IST)
    audit_path = write_audit_log(audit, settings=settings)
    counts = store.counts()

    return IngestReport(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        urls_attempted=len(sources),
        urls_ok=ok,
        urls_unchanged=unchanged,
        urls_failed=failed,
        urls_empty=empty,
        urls_stale_kept=stale_kept,
        scheme_chunks=counts["scheme"],
        general_chunks=counts["general"],
        chunks_by_scheme=store.counts_by_scheme(),
        audit_path=str(audit_path),
        errors=errors,
    )
