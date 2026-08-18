"""Orchestrator routing integration — all 8 intent paths."""

from __future__ import annotations

import pytest

from src.config.schemes import list_canonical_names
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query


def test_route_advisory_short_circuits(no_llm_settings, mock_retriever):
    result = process_query("Should I invest in Midcap?", settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.ADVISORY
    assert result.short_circuit is True
    assert result.chunks == []
    mock_retriever.retrieve_scheme.assert_not_called()


def test_route_unsupported_lists_schemes(no_llm_settings, mock_retriever):
    result = process_query(
        "Expense ratio of HDFC Flexicap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.short_circuit is True
    assert result.supported_schemes == list_canonical_names()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_route_out_of_corpus_short_circuits(no_llm_settings, mock_retriever):
    result = process_query(
        "1Y return of ICICI Midcap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.OUT_OF_CORPUS_FACT_TYPE
    assert result.short_circuit is True
    mock_retriever.retrieve_general.assert_not_called()


def test_route_general_retrieves_general_only(no_llm_settings, mock_retriever):
    result = process_query("What is an exit load?", settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.GENERAL_FACTUAL
    assert result.short_circuit is False
    mock_retriever.retrieve_general.assert_called_once()
    mock_retriever.retrieve_scheme.assert_not_called()
    assert all(c.corpus == "general" for c in result.chunks)


def test_route_scheme_specific_retrieves_scheme(no_llm_settings, mock_retriever):
    result = process_query(
        "expense ratio of icici flexicap",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.SCHEME_SPECIFIC_FACTUAL
    assert result.scheme_id == "icici_flexicap_dg"
    mock_retriever.retrieve_scheme.assert_called_once()
    assert all(c.corpus == "scheme" for c in result.chunks)


def test_route_mixed_still_retrieves_facts(no_llm_settings, mock_retriever):
    result = process_query(
        "Expense ratio of Flexicap, and is it good?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.MIXED
    assert result.short_circuit is False
    mock_retriever.retrieve_scheme.assert_called_once()


def test_route_unresolved_scheme_no_retrieval(no_llm_settings, mock_retriever):
    result = process_query("ICICI Prudential", settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.UNSUPPORTED_SCHEME
    assert result.short_circuit is True
    assert result.short_circuit_reason in ("scheme_unresolved", "unsupported_scheme")
    mock_retriever.retrieve_scheme.assert_not_called()


def test_route_cross_scheme_calls_per_scheme_retrieval(no_llm_settings, mock_retriever):
    result = process_query(
        "Which of these 5 has lowest expense ratio?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.CROSS_SCHEME_COMPARISON
    # Phase 4: per-scheme field scan + extract (not a single blended call)
    assert mock_retriever.retrieve_scheme_field.call_count == 5
    assert result.answer_text is not None
    assert result.comparison_field == "expense_ratio"


def test_route_advisory_has_refusal_copy(no_llm_settings, mock_retriever):
    result = process_query("Should I invest in Midcap?", settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.ADVISORY
    assert result.answer_text
    assert "investment advice" in result.answer_text.lower()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_route_mixed_appends_refusal(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": "The expense ratio is 0.5%.",
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
    assert result.answer_text
    assert "0.5%" in result.answer_text
    assert "investment advice" in result.answer_text.lower()
    # Fact and refusal are separate paragraphs
    parts = result.answer_text.split("\n\n")
    assert len(parts) >= 2
