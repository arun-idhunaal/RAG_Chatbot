"""Shared pytest fixtures for Phase 2 tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.config.settings import Settings
from src.ingestion.models import ChunkRecord
from src.ingestion.store import VectorStore
from src.pipeline.models import RetrievedChunk
from src.retrieval.retriever import Retriever

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def no_llm_settings() -> Settings:
    """Rules-only classifier — deterministic tests without Groq."""
    return Settings(use_llm_classifier=False, groq_api_key="")


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        raw_html_dir=tmp_path / "raw",
        audit_log_dir=tmp_path / "audit",
        embedding_model="BAAI/bge-m3",
        use_llm_classifier=False,
        groq_api_key="",
        retrieval_top_k=5,
        retrieval_min_similarity=0.0,  # allow all hits in unit tests
    )


def make_chunk(
    *,
    chunk_id: str,
    corpus: str,
    scheme_id: str | None,
    source_url: str,
    text: str,
    fact_types: list[str] | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        corpus=corpus,  # type: ignore[arg-type]
        scheme_id=scheme_id,
        fact_types=fact_types or ["expense_ratio"],
        source_url=source_url,
        source_title="Test",
        page_ref="Expense Ratio",
        scraped_at=datetime.now(tz=IST).isoformat(),
        content_hash=f"hash-{chunk_id}",
        text=text,
    )


@pytest.fixture
def populated_store(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> VectorStore:
    """In-memory Chroma with scheme + general chunks for retrieval tests."""
    import numpy as np

    def _fake_embed(texts, settings=None):
        del settings
        return [np.random.rand(16).tolist() for _ in texts]

    monkeypatch.setattr("src.retrieval.retriever.embed_texts", _fake_embed)
    monkeypatch.setattr("src.ingestion.store.embed_texts", _fake_embed)

    store = VectorStore(tmp_settings)
    chunks = [
        make_chunk(
            chunk_id="flex-er-1",
            corpus="scheme",
            scheme_id="icici_flexicap_dg",
            source_url="https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
            text="Expense Ratio for ICICI Flexicap Direct Growth is 0.65%.",
            fact_types=["expense_ratio"],
        ),
        make_chunk(
            chunk_id="mid-er-1",
            corpus="scheme",
            scheme_id="icici_midcap_dg",
            source_url="https://www.indmoney.com/mutual-funds/icici-prudential-midcap-fund-direct-plan-growth",
            text="Expense Ratio for ICICI Midcap Direct Growth is 0.72%.",
            fact_types=["expense_ratio"],
        ),
        make_chunk(
            chunk_id="gen-exit-1",
            corpus="general",
            scheme_id=None,
            source_url="https://investor.sebi.gov.in/exit_load.html",
            text="Exit load is a fee charged when investors redeem units before a specified period.",
            fact_types=["exit_load"],
        ),
    ]
    fake_vectors = [np.random.rand(16).tolist() for _ in chunks]
    store.upsert_chunks(chunks, embeddings=fake_vectors)
    return store


@pytest.fixture
def mock_retriever() -> MagicMock:
    retriever = MagicMock(spec=Retriever)

    def _scheme_chunks(query, scheme_id, fact_type=None):
        del query, fact_type
        return [
            RetrievedChunk(
                chunk_id=f"mock-{scheme_id}",
                text="Expense ratio is 0.5%. Exit load is Nil. Minimum SIP is 100.",
                corpus="scheme",
                scheme_id=scheme_id,
                source_url=f"https://example.com/{scheme_id}",
                source_title=scheme_id,
                page_ref=None,
                scraped_at="2026-08-12T10:00:00+05:30",
                fact_types=["expense_ratio", "exit_load", "min_sip"],
                similarity=0.9,
            )
        ]

    retriever.retrieve_scheme.side_effect = _scheme_chunks
    retriever.retrieve_general.return_value = [
        RetrievedChunk(
            chunk_id="mock-g1",
            text="Exit load is a fee on early redemption.",
            corpus="general",
            scheme_id=None,
            source_url="https://investor.sebi.gov.in/exit_load.html",
            source_title="SEBI Exit Load",
            page_ref=None,
            scraped_at="2026-08-12T10:00:00+05:30",
            fact_types=["exit_load"],
            similarity=0.85,
        )
    ]
    retriever.retrieve_cross_scheme.return_value = []
    return retriever
