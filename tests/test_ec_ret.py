"""EC-RET-* — corpus-isolated retrieval filters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.config.settings import Settings
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query
from src.retrieval.retriever import Retriever


def test_ec_ret_01_scheme_filter_only(populated_store, tmp_settings: Settings):
    retriever = Retriever(store=populated_store, settings=tmp_settings)
    chunks = retriever.retrieve_scheme(
        "expense ratio flexicap",
        "icici_flexicap_dg",
    )
    assert len(chunks) >= 1
    for c in chunks:
        assert c.corpus == "scheme"
        assert c.scheme_id == "icici_flexicap_dg"


def test_ec_ret_02_general_corpus_only(populated_store, tmp_settings: Settings):
    retriever = Retriever(store=populated_store, settings=tmp_settings)
    chunks = retriever.retrieve_general("what is exit load")
    assert len(chunks) >= 1
    for c in chunks:
        assert c.corpus == "general"
        assert c.scheme_id is None


def test_ec_ret_01_no_cross_scheme_bleed(populated_store, tmp_settings: Settings):
    """Scheme A query must not return Scheme B chunks."""
    retriever = Retriever(store=populated_store, settings=tmp_settings)
    chunks = retriever.retrieve_scheme(
        "expense ratio",
        "icici_flexicap_dg",
    )
    for c in chunks:
        assert c.scheme_id != "icici_midcap_dg"


def test_ec_ret_04_empty_retrieval_flagged(no_llm_settings):
    """Similarity floor drops all hits → retrieval_empty + not-found answer (Phase 3)."""
    strict = Settings(
        use_llm_classifier=False,
        groq_api_key="",
        retrieval_min_similarity=0.99,
    )
    mock = MagicMock(spec=Retriever)
    mock.retrieve_scheme.return_value = []
    result = process_query(
        "expense ratio of icici flexicap",
        settings=strict,
        retriever=mock,
        llm_generate=lambda q, c: (_ for _ in ()).throw(AssertionError("no llm")),
    )
    assert result.intent == Intent.SCHEME_SPECIFIC_FACTUAL
    assert result.retrieval_empty is True
    assert result.chunks == []
    assert result.insufficient_context is True
    assert result.answer_text is not None
    assert "not find" in result.answer_text.lower() or "sources" in result.answer_text.lower()
