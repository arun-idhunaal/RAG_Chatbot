"""EC-CMP-* — cross-scheme comparison extract → template (Phase 4)."""

from __future__ import annotations

from src.config.schemes import SCHEMES, list_canonical_names
from src.pipeline.citation_validator import validate_comparison_rows
from src.pipeline.comparison_templater import (
    UNAVAILABLE_LABEL,
    render_comparison,
)
from src.pipeline.field_extractor import ExtractedField, extract_field_for_scheme
from src.pipeline.models import Intent, RetrievedChunk
from src.pipeline.orchestrator import process_query

FLEX_URL = "https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth"
MID_URL = "https://www.indmoney.com/mutual-funds/icici-prudential-midcap-fund-direct-plan-growth"


def _row(
    scheme_id: str,
    value: str | None,
    *,
    available: bool | None = None,
    url: str | None = None,
    scraped_at: str = "2026-08-12T10:00:00+05:30",
) -> ExtractedField:
    scheme = next(s for s in SCHEMES if s.scheme_id == scheme_id)
    avail = available if available is not None else value is not None
    return ExtractedField(
        scheme_id=scheme_id,
        scheme_name=scheme.canonical_name,
        field="expense_ratio",
        value=value,
        source_url=url or scheme.source_url,
        scraped_at=scraped_at,
        available=avail,
    )


def test_ec_cmp_01_template_lists_each_scheme_with_citation():
    rows = [
        _row("icici_flexicap_dg", "0.65%"),
        _row("icici_midcap_dg", "0.72%"),
        _row("icici_largecap_dg", "0.80%"),
        _row("icici_nasdaq100_dg", "0.40%"),
        _row("icici_elss_dg", "0.90%"),
    ]
    out = render_comparison(rows, field="expense_ratio")
    assert out.insufficient_context is False
    assert len(out.citations) == 5
    for scheme in SCHEMES:
        assert scheme.canonical_name in out.answer_text
        assert scheme.source_url in out.answer_text
    assert "Last updated from sources:" in out.answer_text


def test_ec_cmp_02_bare_ranking_still_shows_all_values():
    rows = [_row(s.scheme_id, f"0.{i}5%") for i, s in enumerate(SCHEMES)]
    out = render_comparison(rows, field="expense_ratio", include_lowest_note=True)
    # Must show underlying values, not only a winner line
    for row in rows:
        assert row.value in out.answer_text
    assert "lowest expense ratio" in out.answer_text.lower()


def test_ec_cmp_03_returns_comparison_not_fr4(no_llm_settings, mock_retriever):
    result = process_query(
        "Compare performance of these 5 funds",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.OUT_OF_CORPUS_FACT_TYPE
    assert result.short_circuit is True
    assert "return" in result.answer_text.lower() or "performance" in result.answer_text.lower()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_cmp_04_which_is_better_is_advisory(no_llm_settings, mock_retriever):
    result = process_query(
        "Which is better, Midcap or Flexicap?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.ADVISORY
    assert "investment advice" in (result.answer_text or "").lower()
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_cmp_05_missing_extract_unavailable_no_guess():
    rows = [
        _row("icici_flexicap_dg", "0.65%"),
        _row("icici_midcap_dg", None, available=False),
        _row("icici_largecap_dg", "0.80%"),
        _row("icici_nasdaq100_dg", "0.40%"),
        _row("icici_elss_dg", "0.90%"),
    ]
    out = render_comparison(rows, field="expense_ratio")
    assert UNAVAILABLE_LABEL in out.answer_text
    assert "0.65%" in out.answer_text
    assert "Midcap" in out.answer_text
    # Ensure we didn't invent a percent for the unavailable midcap row
    for line in out.answer_text.splitlines():
        if "Midcap" in line and UNAVAILABLE_LABEL in line:
            before = line.split(UNAVAILABLE_LABEL)[0]
            assert "%" not in before.split(":")[-1]


def test_ec_cmp_06_no_better_choice_language():
    rows = [_row(s.scheme_id, f"0.{i + 1}%") for i, s in enumerate(SCHEMES)]
    out = render_comparison(rows, field="expense_ratio")
    lower = out.answer_text.lower()
    assert "better choice" not in lower
    assert "best fund" not in lower
    assert "recommend" not in lower


def test_ec_cit_05_shared_citation_rejected():
    """Two schemes must not share one citation URL."""
    flex = _row("icici_flexicap_dg", "0.65%", url=FLEX_URL)
    # Wrong: midcap value cited to flexicap URL
    mid = _row("icici_midcap_dg", "0.72%", url=FLEX_URL)
    result = validate_comparison_rows([flex, mid])
    assert result.ok is False
    assert result.reason == "wrong_scheme_citation"


def test_extract_regex_expense_ratio():
    chunks = [
        RetrievedChunk(
            chunk_id="1",
            text="Expense Ratio for Direct Growth is 0.65%.",
            corpus="scheme",
            scheme_id="icici_flexicap_dg",
            source_url=FLEX_URL,
            source_title="Flexicap",
            page_ref=None,
            scraped_at="2026-08-12T10:00:00+05:30",
            fact_types=["expense_ratio"],
            similarity=0.9,
        )
    ]
    row = extract_field_for_scheme("icici_flexicap_dg", "expense_ratio", chunks)
    assert row.available is True
    assert "0.65%" in (row.value or "")
    assert row.source_url == FLEX_URL


def test_ec_cmp_09_extract_skips_as_on_date():
    """INDmoney cards put 'as on 31 Jul' between the label and the TER (EC-CMP-09)."""
    chunks = [
        RetrievedChunk(
            chunk_id="mid-er",
            text=(
                "Expense Ratio\n"
                "as on 31 Jul 2026\n"
                "Direct 0.89%\n"
                "Regular 1.53%\n"
                "Exit Load\n"
                "1%"
            ),
            corpus="scheme",
            scheme_id="icici_midcap_dg",
            source_url=MID_URL,
            source_title="Midcap",
            page_ref=None,
            scraped_at="2026-08-18T10:00:00+05:30",
            fact_types=["expense_ratio"],
            similarity=0.88,
        )
    ]
    row = extract_field_for_scheme("icici_midcap_dg", "expense_ratio", chunks)
    assert row.available is True
    assert row.value == "0.89%"
    assert "1.53" not in (row.value or "")
    assert "1%" != row.value


def test_ec_cmp_10_extract_ter_without_percent_sign():
    """INDmoney httpx extracts often omit % after the Direct TER (EC-CMP-10)."""
    chunks = [
        RetrievedChunk(
            chunk_id="nasdaq-er",
            text=(
                "ExpenseRatio\n"
                "as on 18 Aug 2026\n"
                "Direct 0.43\n"
                "Regular 0.90\n"
            ),
            corpus="scheme",
            scheme_id="icici_nasdaq100_dg",
            source_url=(
                "https://www.indmoney.com/mutual-funds/"
                "icici-prudential-nasdaq-100-index-fund-direct-growth"
            ),
            source_title="Nasdaq",
            page_ref=None,
            scraped_at="2026-08-18T10:00:00+05:30",
            fact_types=["expense_ratio"],
            similarity=0.5,
        )
    ]
    row = extract_field_for_scheme("icici_nasdaq100_dg", "expense_ratio", chunks)
    assert row.available is True
    assert row.value == "0.43%"


def test_ec_cmp_10_keyword_scan_finds_ter_chunk(populated_store, tmp_settings):
    from src.retrieval.retriever import Retriever

    retriever = Retriever(store=populated_store, settings=tmp_settings)
    chunks = retriever.retrieve_scheme_field("icici_flexicap_dg", "expense_ratio")
    assert chunks
    assert any("0.65%" in (c.text or "") for c in chunks)
    for c in chunks:
        assert c.scheme_id == "icici_flexicap_dg"


def test_ec_cmp_09_comparison_uses_field_retrieval_query(
    no_llm_settings, mock_retriever
):
    result = process_query(
        "Which of these 5 has the lowest expense ratio?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.CROSS_SCHEME_COMPARISON
    assert result.insufficient_context is False
    assert UNAVAILABLE_LABEL not in (result.answer_text or "").lower()
    assert "0.5%" in (result.answer_text or "")
    for call in mock_retriever.retrieve_scheme_field.call_args_list:
        scheme_id, field = call.args[0], call.args[1]
        assert field == "expense_ratio"
        assert scheme_id in {
            "icici_nasdaq100_dg",
            "icici_midcap_dg",
            "icici_flexicap_dg",
            "icici_largecap_dg",
            "icici_elss_dg",
        }


def test_orchestrator_comparison_end_to_end(no_llm_settings, mock_retriever):
    result = process_query(
        "Which of these 5 has the lowest expense ratio?",
        settings=no_llm_settings,
        retriever=mock_retriever,
    )
    assert result.intent == Intent.CROSS_SCHEME_COMPARISON
    assert result.comparison_field == "expense_ratio"
    assert result.answer_text
    assert len(result.citations) == 5
    for name in list_canonical_names():
        assert name in result.answer_text
    assert "better choice" not in result.answer_text.lower()
