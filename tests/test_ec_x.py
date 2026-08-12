"""EC-X-* compound / stress scenarios (Phase 4)."""

from __future__ import annotations

from src.config.schemes import list_canonical_names
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query


def test_ec_x_01_pii_first(no_llm_settings, mock_retriever):
    msg = "HDFC Midcap 1Y return and should I buy? My PAN is ABCDE1234F"
    result = process_query(msg, settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.PII
    assert result.short_circuit_reason == "pii"
    assert "ABCDE" not in (result.answer_text or "")
    assert "ABCDE" not in (result.original_message or "")
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_x_02_comparison_plus_advice(no_llm_settings, mock_retriever):
    result = process_query(
        "Lowest expense ratio among these 5, so which should I pick?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    # Mixed or comparison+advisory: values via FR-4, then FR-7 — never "pick Scheme A"
    assert result.intent in (Intent.MIXED, Intent.CROSS_SCHEME_COMPARISON)
    text = result.answer_text or ""
    assert "expense ratio" in text.lower() or result.comparison_field == "expense_ratio"
    assert "investment advice" in text.lower()
    assert result.refusal_appended is True
    lower = text.lower()
    assert "should pick" not in lower
    assert "pick scheme" not in lower
    assert "better choice" not in lower


def test_ec_x_03_lockin_plus_suitability(no_llm_settings, mock_retriever):
    def fake_llm(query, ctx):
        del query, ctx
        return {
            "answer_text": (
                "ICICI Prudential ELSS Tax Saver Fund (Direct Plan Growth) has a "
                "lock-in period of 3 years."
            ),
            "citation_urls": ["https://example.com/icici_elss_dg"],
            "insufficient_context": False,
        }

    # Enrich mock text for lock-in when ELSS is requested
    def _scheme_chunks(query, scheme_id, fact_type=None):
        del query, fact_type
        text = (
            "Lock-in period is 3 years for ELSS."
            if scheme_id == "icici_elss_dg"
            else "Expense ratio is 0.5%."
        )
        from src.pipeline.models import RetrievedChunk

        return [
            RetrievedChunk(
                chunk_id=f"mock-{scheme_id}",
                text=text,
                corpus="scheme",
                scheme_id=scheme_id,
                source_url=f"https://example.com/{scheme_id}",
                source_title=scheme_id,
                page_ref=None,
                scraped_at="2026-08-12T10:00:00+05:30",
                fact_types=["lock_in", "expense_ratio"],
                similarity=0.9,
            )
        ]

    mock_retriever.retrieve_scheme.side_effect = _scheme_chunks

    result = process_query(
        "Lock-in of ELSS Tax Saver and is 2 years enough?",
        settings=no_llm_settings,
        retriever=mock_retriever,
        llm_generate=fake_llm,
    )
    assert result.intent == Intent.MIXED
    assert result.refusal_appended is True
    assert "lock" in (result.answer_text or "").lower()
    assert "investment advice" in (result.answer_text or "").lower()
    assert "\n\n" in (result.answer_text or "")
