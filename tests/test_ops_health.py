"""EC-X-04 + ops health — empty Chroma fail closed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.config.settings import Settings
from src.ingestion.models import ChunkRecord
from src.ingestion.store import VectorStore
from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE, check_index_health
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def test_ec_x_04_empty_chroma_health_fails(tmp_path: Path) -> None:
    settings = Settings(
        chroma_persist_dir=tmp_path / "chroma",
        raw_html_dir=tmp_path / "raw",
        audit_log_dir=tmp_path / "audit",
        metrics_log_dir=tmp_path / "metrics",
        use_llm_classifier=False,
        groq_api_key="",
    )
    status = check_index_health(settings=settings, run_sample_query=False)
    assert status.ok is False
    assert status.reason == "empty_collections"
    assert "unavailable" in CORPUS_UNAVAILABLE_MESSAGE.lower()


def test_health_ok_when_populated(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.ingestion.store.embed_texts",
        lambda texts, settings=None: [np.random.rand(16).tolist() for _ in texts],
    )
    store = VectorStore(tmp_settings)
    urls = {
        "icici_flexicap_dg": "https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
        "icici_midcap_dg": "https://www.indmoney.com/mutual-funds/icici-prudential-midcap-fund-direct-plan-growth",
        "icici_largecap_dg": "https://www.indmoney.com/mutual-funds/icici-prudential-large-cap-fund-direct-plan-growth",
        "icici_elss_dg": "https://www.indmoney.com/mutual-funds/icici-prudential-elss-tax-saver-fund-direct-plan-growth",
        "icici_nasdaq100_dg": "https://www.indmoney.com/mutual-funds/icici-prudential-nasdaq-100-index-fund-direct-growth",
    }
    chunks = []
    for sid, url in urls.items():
        chunks.append(
            ChunkRecord(
                chunk_id=f"{sid}-1",
                corpus="scheme",
                scheme_id=sid,
                fact_types=["expense_ratio"],
                source_url=url,
                source_title=sid,
                page_ref=None,
                scraped_at=datetime.now(tz=IST).isoformat(),
                content_hash=f"h-{sid}",
                text=f"Expense ratio for {sid} is 0.5%.",
            )
        )
    chunks.append(
        ChunkRecord(
            chunk_id="gen-1",
            corpus="general",
            scheme_id=None,
            fact_types=["exit_load"],
            source_url="https://investor.sebi.gov.in/exit_load.html",
            source_title="SEBI",
            page_ref=None,
            scraped_at=datetime.now(tz=IST).isoformat(),
            content_hash="h-gen",
            text="Exit load is a fee on early redemption.",
        )
    )
    store.upsert_chunks(
        chunks,
        embeddings=[np.random.rand(16).tolist() for _ in chunks],
    )
    status = check_index_health(settings=tmp_settings, store=store, run_sample_query=True)
    assert status.ok is True
    assert status.sample_query_ok is True
