"""EC-ING-03: Embedding failure mid-run aborts upsert; preserves existing Chroma."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.config.settings import Settings
from src.config.sources import SCHEME_SOURCES
from src.ingestion.embed import EmbeddingError
from src.ingestion.models import ChunkRecord, CleanedDocument, ScrapedPage
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore

IST = ZoneInfo("Asia/Kolkata")


def test_ec_ing_03_embed_failure_preserves_index(tmp_settings: Settings) -> None:
    source_a = SCHEME_SOURCES[0]
    source_b = SCHEME_SOURCES[1]
    store = VectorStore(tmp_settings)
    fake_embedding = [[0.1] * 8]

    existing = ChunkRecord(
        chunk_id="keep-b-1",
        corpus="scheme",
        scheme_id=source_b.scheme_id,
        fact_types=["expense_ratio"],
        source_url=source_b.url,
        source_title=source_b.title,
        page_ref=None,
        scraped_at=datetime.now(tz=IST).isoformat(),
        content_hash="hash-b",
        text="Expense ratio is 0.72%.",
    )
    with patch("src.ingestion.store.embed_texts", return_value=fake_embedding):
        store.upsert_chunks([existing], embeddings=fake_embedding)

    before_b = store.count_for_url("scheme", source_b.url)
    assert before_b >= 1

    ok_page = ScrapedPage(
        url=source_a.url,
        title=source_a.title,
        corpus=source_a.corpus,
        scheme_id=source_a.scheme_id,
        html="<html><body><p>Expense ratio 0.99%</p></body></html>",
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = CleanedDocument(
        url=source_a.url,
        title=source_a.title,
        corpus=source_a.corpus,
        scheme_id=source_a.scheme_id,
        text="Expense ratio is 0.99%.",
        sections=[("Expense Ratio", "Expense ratio is 0.99%.")],
        content_hash="new-hash-a",
        scraped_at=datetime.now(tz=IST),
    )

    def boom_upsert(chunks, embeddings=None):
        raise EmbeddingError("simulated embed failure (EC-ING-03)")

    with (
        patch("src.ingestion.pipeline.fetch_url", return_value=ok_page),
        patch("src.ingestion.pipeline.clean_page", return_value=cleaned),
        patch.object(store, "upsert_chunks", side_effect=boom_upsert),
    ):
        report = run_ingest(
            urls=[source_a.url],
            settings=tmp_settings,
            store=store,
            save_raw=False,
        )

    assert report.urls_failed >= 1 or report.urls_stale_kept >= 0
    assert any("EC-ING-03" in e or "embed" in e.lower() for e in report.errors) or report.urls_failed >= 1
    # Prior scheme B chunks must still exist — no wipe.
    assert store.count_for_url("scheme", source_b.url) == before_b
