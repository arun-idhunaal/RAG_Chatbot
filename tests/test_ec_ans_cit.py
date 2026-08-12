"""EC-ANS / EC-CIT / EC-RET-04 — grounded answers and citation fail-closed (Phase 3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.config.settings import Settings
from src.pipeline.answer_generator import (
    NOT_FOUND_MESSAGE,
    UNABLE_TO_VERIFY_MESSAGE,
    generate_grounded_answer,
)
from src.pipeline.citation_validator import is_exact_page_url, validate_citations
from src.pipeline.models import Intent, RetrievedChunk
from src.pipeline.orchestrator import process_query
from src.retrieval.retriever import Retriever

FLEX_URL = "https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth"
MID_URL = "https://www.indmoney.com/mutual-funds/icici-prudential-midcap-fund-direct-plan-growth"
SEBI_URL = "https://investor.sebi.gov.in/exit_load.html"


def _chunk(
    *,
    chunk_id: str = "c1",
    corpus: str = "scheme",
    scheme_id: str | None = "icici_flexicap_dg",
    source_url: str = FLEX_URL,
    text: str = "Expense Ratio is 0.65%.",
    scraped_at: str = "2026-08-12T10:00:00+05:30",
    title: str = "Flexicap",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        corpus=corpus,  # type: ignore[arg-type]
        scheme_id=scheme_id,
        source_url=source_url,
        source_title=title,
        page_ref="Expense Ratio",
        scraped_at=scraped_at,
        fact_types=["expense_ratio"],
        similarity=0.9,
    )


# --- Citation validator unit tests ---


def test_ec_cit_01_domain_only_rejected():
    assert is_exact_page_url("https://www.indmoney.com") is False
    assert is_exact_page_url("https://indmoney.com/") is False
    assert is_exact_page_url(FLEX_URL) is True

    chunks = [_chunk()]
    result = validate_citations(["https://www.indmoney.com"], chunks, scheme_id="icici_flexicap_dg")
    assert result.ok is False
    assert result.reason == "domain_only"


def test_ec_cit_02_wrong_scheme_url_rejected():
    """Even if URL sneaks in, wrong scheme_id on chunk → reject."""
    flex = _chunk(scheme_id="icici_flexicap_dg", source_url=FLEX_URL)
    # Simulate polluted retrieved set (should not happen in prod filters)
    mid = _chunk(
        chunk_id="mid",
        scheme_id="icici_midcap_dg",
        source_url=MID_URL,
        text="Expense Ratio is 0.72%.",
        title="Midcap",
    )
    result = validate_citations([MID_URL], [flex, mid], scheme_id="icici_flexicap_dg")
    assert result.ok is False
    assert result.reason == "wrong_scheme_citation"


def test_ec_cit_03_url_not_in_retrieved_rejected():
    chunks = [_chunk()]
    result = validate_citations([MID_URL], chunks, scheme_id="icici_flexicap_dg")
    assert result.ok is False
    assert result.reason == "url_not_in_retrieved"


def test_ec_cit_04_date_from_cited_chunk_scraped_at():
    chunks = [
        _chunk(scraped_at="2026-08-10T10:00:00+05:30"),
        _chunk(
            chunk_id="c2",
            source_url=FLEX_URL + "#overview",
            scraped_at="2026-08-12T10:00:00+05:30",
        ),
    ]
    # Same normalized URL — first wins in by_url map; use distinct paths via page only
    # Use single chunk for clear stamp
    single = [_chunk(scraped_at="2026-08-11T15:30:00+05:30")]
    result = validate_citations([FLEX_URL], single, scheme_id="icici_flexicap_dg")
    assert result.ok is True
    assert result.last_updated_from_sources == "2026-08-11"


# --- Answer generator ---


def test_ec_ans_01_normal_factual_shape():
    chunks = [_chunk()]

    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "The expense ratio of ICICI Prudential Flexicap Fund (Direct Growth) is 0.65%.",
            "citation_urls": [FLEX_URL],
            "insufficient_context": False,
        }

    out = generate_grounded_answer(
        "expense ratio of flexicap",
        chunks,
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        scheme_id="icici_flexicap_dg",
        llm_generate=fake_llm,
    )
    assert out.insufficient_context is False
    assert out.citations
    assert out.citations[0].url == FLEX_URL
    assert out.last_updated_from_sources == "2026-08-12"
    assert "Last updated from sources: 2026-08-12" in out.answer_text
    # ≤3 sentences in the factual body (before stamp)
    body = out.answer_text.split("Last updated")[0].strip()
    sentences = [s for s in body.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    assert len(sentences) <= 3


def test_ec_ans_03_advisory_phrasing_stripped():
    chunks = [_chunk()]

    def leaky_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": (
                "The expense ratio is 0.65%. "
                "You should invest in this fund because it is a good fund."
            ),
            "citation_urls": [FLEX_URL],
            "insufficient_context": False,
        }

    out = generate_grounded_answer(
        "expense ratio of flexicap",
        chunks,
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        scheme_id="icici_flexicap_dg",
        llm_generate=leaky_llm,
    )
    assert "should" not in out.answer_text.lower()
    assert "good fund" not in out.answer_text.lower()
    assert "0.65%" in out.answer_text


def test_ec_ans_04_insufficient_context_no_hallucination():
    chunks = [_chunk(text="Unrelated marketing blurb with no expense figure.")]

    def empty_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "",
            "citation_urls": [],
            "insufficient_context": True,
        }

    out = generate_grounded_answer(
        "expense ratio of flexicap",
        chunks,
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        scheme_id="icici_flexicap_dg",
        llm_generate=empty_llm,
    )
    assert out.insufficient_context is True
    assert out.answer_text == NOT_FOUND_MESSAGE
    assert out.citations == []


def test_ec_ret_04_empty_retrieval_fail_closed(no_llm_settings):
    mock = MagicMock(spec=Retriever)
    mock.retrieve_scheme.return_value = []

    def boom_llm(query, ctx):
        raise AssertionError("LLM must not be called on empty retrieval")

    result = process_query(
        "expense ratio of icici flexicap",
        settings=no_llm_settings,
        retriever=mock,
        llm_generate=boom_llm,
    )
    assert result.intent == Intent.SCHEME_SPECIFIC_FACTUAL
    assert result.retrieval_empty is True
    assert result.insufficient_context is True
    assert result.answer_text == NOT_FOUND_MESSAGE
    assert result.citations == []


def test_ec_cit_03_invalid_citation_retries_then_fallback():
    chunks = [_chunk()]
    calls = {"n": 0}

    def bad_then_still_bad(query, ctx):
        del query, ctx
        calls["n"] += 1
        return {
            "answer_text": "The expense ratio is 0.65%.",
            "citation_urls": ["https://www.indmoney.com"],  # domain-only
            "insufficient_context": False,
        }

    out = generate_grounded_answer(
        "expense ratio",
        chunks,
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        scheme_id="icici_flexicap_dg",
        llm_generate=bad_then_still_bad,
    )
    assert calls["n"] == 2  # initial + one retry
    assert out.citation_validation_failed is True
    assert out.answer_text == UNABLE_TO_VERIFY_MESSAGE


def test_orchestrator_scheme_path_attaches_answer(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        # URL must match mock retriever's per-scheme URL
        return {
            "answer_text": "The expense ratio is 0.5%.",
            "citation_urls": ["https://example.com/icici_flexicap_dg"],
            "insufficient_context": False,
        }

    result = process_query(
        "expense ratio of icici flexicap",
        settings=no_llm_settings,
        retriever=mock_retriever,
        llm_generate=fake_llm,
    )
    assert result.answer_text is not None
    assert "0.5%" in result.answer_text
    assert result.citations
    assert result.last_updated_from_sources == "2026-08-12"


def test_orchestrator_general_path_attaches_answer(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "Exit load is a fee on early redemption.",
            "citation_urls": [SEBI_URL],
            "insufficient_context": False,
        }

    result = process_query(
        "What is an exit load?",
        settings=no_llm_settings,
        retriever=mock_retriever,
        llm_generate=fake_llm,
    )
    assert result.intent == Intent.GENERAL_FACTUAL
    assert result.answer_text is not None
    assert result.citations[0].url == SEBI_URL


def test_example_com_is_exact_page():
    """example.com/flexicap has a path — not domain-only."""
    assert is_exact_page_url("https://example.com/flexicap") is True
