"""EC-ADV / EC-MIX — advisory refusals and mixed fact-then-refusal (Phase 4)."""

from __future__ import annotations

from src.config.schemes import list_canonical_names
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query
from src.pipeline.refusal_templates import ADVISORY_REFUSAL, SEBI_INVESTOR_EDU_URL


def test_ec_adv_01_pure_advisory_refusal(no_llm_settings, mock_retriever):
    result = process_query(
        "Should I invest in Midcap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.ADVISORY
    assert result.short_circuit is True
    assert ADVISORY_REFUSAL in (result.answer_text or "")
    assert SEBI_INVESTOR_EDU_URL in (result.answer_text or "")
    # No scheme fact dump as hedge
    assert "expense ratio" not in (result.answer_text or "").lower()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_adv_02_no_echo_of_advisory_framing(no_llm_settings, mock_retriever):
    result = process_query(
        "Is Midcap a good fund?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.ADVISORY
    lower = (result.answer_text or "").lower()
    assert "you asked" not in lower
    assert "good fund" not in lower


def test_ec_adv_03_soft_suitability_refusal(no_llm_settings, mock_retriever):
    result = process_query(
        "Is Midcap suitable for a 25-year-old?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.ADVISORY
    assert "investment advice" in (result.answer_text or "").lower()


def test_ec_mix_01_fact_then_refusal(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "The expense ratio of ICICI Prudential Flexicap Fund is 0.5%.",
            "citation_urls": ["https://example.com/icici_flexicap_dg"],
            "insufficient_context": False,
        }

    result = process_query(
        "Expense ratio of Flexicap, and is it good?",
        settings=no_llm_settings,
        retriever=mock_retriever,
        llm_generate=fake_llm,
    )
    assert result.intent == Intent.MIXED
    assert result.refusal_appended is True
    assert result.citations
    assert "Last updated from sources:" in (result.answer_text or "")
    parts = (result.answer_text or "").split("\n\n")
    assert len(parts) >= 2
    assert "0.5%" in parts[0]
    assert "investment advice" in parts[-1].lower()


def test_ec_mix_02_fact_and_refusal_not_blended(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "The expense ratio is 0.5%.",
            "citation_urls": ["https://example.com/icici_flexicap_dg"],
            "insufficient_context": False,
        }

    result = process_query(
        "What is the expense ratio of Flexicap, and is it a good fund to invest in?",
        settings=no_llm_settings,
        retriever=mock_retriever,
        llm_generate=fake_llm,
    )
    # Must not be a single ambiguous sentence blending fact+advice
    assert "\n\n" in (result.answer_text or "")
    assert result.refusal_appended is True


def test_ec_mix_03_ooc_fact_plus_advice(no_llm_settings, mock_retriever):
    result = process_query(
        "What is the return of ICICI Midcap, should I buy?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    # FR-10 style + refusal; never invent return
    text = (result.answer_text or "").lower()
    assert "return" in text or "performance" in text
    assert "investment advice" in text
    assert "%" not in text or "compute" in text or "don't provide" in text or "do not" in text
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_mix_04_unsupported_scheme_mixed(no_llm_settings, mock_retriever):
    result = process_query(
        "HDFC Flexicap expense ratio, is it good?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.supported_schemes == list_canonical_names()
    # Do not answer ER from knowledge
    assert "expense ratio of hdfc" not in (result.answer_text or "").lower()
    mock_retriever.retrieve_scheme.assert_not_called()
