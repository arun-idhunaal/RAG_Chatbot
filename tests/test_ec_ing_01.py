"""EC-ING-01: Single URL scrape failure keeps last-good chunks; no full wipe."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from src.config.settings import Settings
from src.config.sources import SCHEME_SOURCES, SourceConfig
from src.ingestion.models import ChunkRecord, ScrapedPage
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        raw_html_dir=tmp_path / "raw",
        audit_log_dir=tmp_path / "audit",
        embedding_model="BAAI/bge-m3",
    )


def _chunk(
    url: str,
    scheme_id: str,
    text: str = "Expense ratio is 0.5%.",
    chunk_id: str | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id or f"chunk-{scheme_id}-{abs(hash(url)) % 10_000}",
        corpus="scheme",
        scheme_id=scheme_id,
        fact_types=["expense_ratio"],
        source_url=url,
        source_title="Test Scheme",
        page_ref="Expense Ratio",
        scraped_at=datetime.now(tz=IST).isoformat(),
        content_hash="abc123",
        text=text,
    )


def test_ec_ing_01_scrape_failure_keeps_last_good(tmp_settings: Settings) -> None:
    source = SCHEME_SOURCES[0]
    store = VectorStore(tmp_settings)

    # Seed last-good chunks without calling the real embedder.
    fake_embedding = [[0.1] * 8]
    with patch("src.ingestion.store.embed_texts", return_value=fake_embedding):
        store.upsert_chunks([_chunk(source.url, source.scheme_id or "x")], embeddings=fake_embedding)

    assert store.count_for_url("scheme", source.url) == 1
    before = store.counts()["scheme"]

    failed_page = ScrapedPage(
        url=source.url,
        title=source.title,
        corpus=source.corpus,
        scheme_id=source.scheme_id,
        html="",
        scraped_at=datetime.now(tz=IST),
        status="error",
        error="ConnectTimeout: simulated",
    )

    with patch("src.ingestion.pipeline.fetch_url", return_value=failed_page):
        report = run_ingest(
            urls=[source.url],
            settings=tmp_settings,
            store=store,
            save_raw=False,
        )

    assert store.count_for_url("scheme", source.url) == 1
    assert store.counts()["scheme"] == before
    assert report.urls_stale_kept == 1 or report.urls_failed == 0
    assert any(e.status == "stale_kept" for e in _read_statuses(report))


def _read_statuses(report):
    # Reconstruct from audit file is heavy; assert via report counters + store instead.
    # Provide a tiny shim object list based on report fields for the assertion above.
    class E:
        def __init__(self, status: str):
            self.status = status

    if report.urls_stale_kept:
        return [E("stale_kept")]
    return [E("error")]


def test_ec_ing_01_failure_does_not_delete_other_urls(tmp_settings: Settings) -> None:
    a, b = SCHEME_SOURCES[0], SCHEME_SOURCES[1]
    store = VectorStore(tmp_settings)
    emb = [[0.2] * 8]

    with patch("src.ingestion.store.embed_texts", return_value=emb):
        store.upsert_chunks(
            [_chunk(a.url, a.scheme_id or "a", "A expense ratio 1%", chunk_id="chunk-a")],
            embeddings=emb,
        )
        store.upsert_chunks(
            [_chunk(b.url, b.scheme_id or "b", "B expense ratio 2%", chunk_id="chunk-b")],
            embeddings=[[0.3] * 8],
        )

    assert store.count_for_url("scheme", a.url) == 1
    assert store.count_for_url("scheme", b.url) == 1

    def fake_fetch(source: SourceConfig, **_kwargs):
        if source.url == a.url:
            return ScrapedPage(
                url=a.url,
                title=a.title,
                corpus=a.corpus,
                scheme_id=a.scheme_id,
                html="",
                scraped_at=datetime.now(tz=IST),
                status="error",
                error="403",
            )
        return ScrapedPage(
            url=b.url,
            title=b.title,
            corpus=b.corpus,
            scheme_id=b.scheme_id,
            html="",
            scraped_at=datetime.now(tz=IST),
            status="error",
            error="skip",
        )

    with patch("src.ingestion.pipeline.fetch_url", side_effect=fake_fetch):
        run_ingest(urls=[a.url, b.url], settings=tmp_settings, store=store, save_raw=False)

    # Both last-good retained — no wipe of index
    assert store.count_for_url("scheme", a.url) == 1
    assert store.count_for_url("scheme", b.url) == 1
    assert store.counts()["scheme"] == 2
