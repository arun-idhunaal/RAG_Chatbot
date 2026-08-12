"""EC-ING-04: Idempotent upsert when content_hash unchanged."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from src.config.settings import Settings
from src.config.sources import SCHEME_SOURCES
from src.ingestion.models import ChunkRecord, CleanedDocument, ScrapedPage
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        raw_html_dir=tmp_path / "raw",
        audit_log_dir=tmp_path / "audit",
    )


def test_ec_ing_04_unchanged_hash_skips_reembed(tmp_settings: Settings) -> None:
    source = SCHEME_SOURCES[2]
    store = VectorStore(tmp_settings)
    content_hash = "same-hash-001"
    chunk = ChunkRecord(
        chunk_id="id-1",
        corpus="scheme",
        scheme_id=source.scheme_id,
        fact_types=["expense_ratio"],
        source_url=source.url,
        source_title=source.title,
        page_ref=None,
        scraped_at=datetime.now(tz=IST).isoformat(),
        content_hash=content_hash,
        text="Expense ratio is 0.9%.",
    )
    emb = [[0.05] * 8]
    with patch("src.ingestion.store.embed_texts", return_value=emb) as embed_mock:
        store.upsert_chunks([chunk], embeddings=emb)
        assert embed_mock.call_count == 0  # embeddings provided

    page = ScrapedPage(
        url=source.url,
        title=source.title,
        corpus=source.corpus,
        scheme_id=source.scheme_id,
        html="<html><body><main><p>Expense ratio is 0.9%.</p></main></body></html>",
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = CleanedDocument(
        url=source.url,
        title=source.title,
        corpus=source.corpus,
        scheme_id=source.scheme_id,
        text="Expense ratio is 0.9%.",
        sections=[(None, "Expense ratio is 0.9%.")],
        content_hash=content_hash,
        scraped_at=datetime.now(tz=IST),
    )

    with (
        patch("src.ingestion.pipeline.fetch_url", return_value=page),
        patch("src.ingestion.pipeline.clean_page", return_value=cleaned),
        patch("src.ingestion.store.embed_texts") as embed_mock,
    ):
        report = run_ingest(
            urls=[source.url],
            settings=tmp_settings,
            store=store,
            save_raw=False,
        )
        embed_mock.assert_not_called()

    assert report.urls_unchanged == 1
    assert store.count_for_url("scheme", source.url) == 1
