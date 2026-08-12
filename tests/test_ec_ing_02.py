"""EC-ING-02: Empty HTML extract must not delete prior chunks."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.config.settings import Settings
from src.config.sources import SCHEME_SOURCES
from src.ingestion.models import ChunkRecord, ScrapedPage
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore

IST = ZoneInfo("Asia/Kolkata")


def test_ec_ing_02_empty_extract_keeps_prior(tmp_settings: Settings) -> None:
    source = SCHEME_SOURCES[0]
    store = VectorStore(tmp_settings)
    fake_embedding = [[0.1] * 8]
    chunk = ChunkRecord(
        chunk_id="flex-keep-1",
        corpus="scheme",
        scheme_id=source.scheme_id,
        fact_types=["expense_ratio"],
        source_url=source.url,
        source_title="Flexicap",
        page_ref=None,
        scraped_at=datetime.now(tz=IST).isoformat(),
        content_hash="hash-keep",
        text="Expense ratio is 0.65%.",
    )
    with patch("src.ingestion.store.embed_texts", return_value=fake_embedding):
        store.upsert_chunks([chunk], embeddings=fake_embedding)

    before = store.count_for_url("scheme", source.url)
    assert before >= 1

    empty_page = ScrapedPage(
        url=source.url,
        title=source.title,
        corpus=source.corpus,
        scheme_id=source.scheme_id,
        html="",
        scraped_at=datetime.now(tz=IST),
        status="empty",
        error="empty_html",
    )
    with patch("src.ingestion.pipeline.fetch_url", return_value=empty_page):
        report = run_ingest(
            urls=[source.url],
            settings=tmp_settings,
            store=store,
            save_raw=False,
        )

    assert report.urls_empty >= 1
    assert store.count_for_url("scheme", source.url) == before
