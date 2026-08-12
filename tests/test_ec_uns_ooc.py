"""EC-UNS / EC-OOC — FR-9 vs FR-10 distinct handling (Phase 4)."""

from __future__ import annotations

from src.config.schemes import list_canonical_names
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query
from src.pipeline.refusal_templates import out_of_corpus_refusal, unsupported_scheme_refusal


def test_ec_uns_01_other_amc_lists_exactly_five(no_llm_settings, mock_retriever):
    result = process_query(
        "Expense ratio of HDFC Flexicap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.supported_schemes == list_canonical_names()
    assert len(result.supported_schemes) == 5
    for name in list_canonical_names():
        assert name in (result.answer_text or "")
    lower = (result.answer_text or "").lower()
    assert "don't cover" in lower or "only have facts" in lower


def test_ec_uns_02_other_icici_scheme(no_llm_settings, mock_retriever):
    result = process_query(
        "Expense ratio of ICICI Prudential Bluechip Fund?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    # Bluechip is outside the 5 — FR-9 (may resolve as unsupported or unresolved)
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert len(result.supported_schemes) == 5
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_uns_03_no_uncited_knowledge(no_llm_settings, mock_retriever):
    result = process_query(
        "What is the expense ratio of SBI Small Cap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    # Refusal only — no invented TER
    assert "%" not in (result.answer_text or "")
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_uns_04_failed_match_same_as_fr9(no_llm_settings, mock_retriever):
    result = process_query(
        "ICICI Prudential",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.supported_schemes == list_canonical_names()


def test_ec_ooc_01_returns_on_supported_scheme(no_llm_settings, mock_retriever):
    result = process_query(
        "1Y return of ICICI Midcap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.OUT_OF_CORPUS_FACT_TYPE
    text = result.answer_text or ""
    assert "performance" in text.lower() or "return" in text.lower()
    assert "don't cover that scheme" not in text.lower()
    assert "Midcap" in text or "midcap" in text.lower() or "official" in text.lower()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_ooc_02_predict_outperform(no_llm_settings, mock_retriever):
    result = process_query(
        "Predict if Midcap will outperform",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent in (Intent.OUT_OF_CORPUS_FACT_TYPE, Intent.ADVISORY)
    text = (result.answer_text or "").lower()
    assert "forecast" not in text
    assert result.short_circuit is True


def test_ec_ooc_03_approximate_from_memory(no_llm_settings, mock_retriever):
    result = process_query(
        "Just approximate the 3Y return of ICICI Flexicap from memory",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.OUT_OF_CORPUS_FACT_TYPE
    text = (result.answer_text or "").lower()
    assert "never compute" in text or "don't provide" in text or "do not" in text


def test_ec_ooc_04_unsupported_plus_returns_prefers_fr9(no_llm_settings, mock_retriever):
    result = process_query(
        "What is the 1Y return of HDFC Midcap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    # Prefer FR-9 over implying we have the scheme but lack returns
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.supported_schemes == list_canonical_names()
    lower = (result.answer_text or "").lower()
    assert "don't cover that scheme" in lower or "only have facts" in lower


def test_fr9_vs_fr10_copy_distinct():
    fr9 = unsupported_scheme_refusal()
    fr10 = out_of_corpus_refusal(scheme_id="icici_midcap_dg")
    assert "don't cover that scheme" in fr9.lower() or "only have facts" in fr9.lower()
    assert "performance" in fr10.lower() or "returns" in fr10.lower()
    assert fr9 != fr10
    assert "HDFC" not in fr10
