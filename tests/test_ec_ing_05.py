"""EC-ING-05: Performance-only content tagged/excluded as out_of_scope."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.ingestion.chunk import chunk_document
from src.ingestion.clean import _is_performance_only, clean_page, tag_fact_types
from src.ingestion.models import CleanedDocument, ScrapedPage

IST = ZoneInfo("Asia/Kolkata")


def test_performance_only_detected() -> None:
    text = "1Y return was 22%. 3Y CAGR is 15%. Past performance vs benchmark."
    assert _is_performance_only(text) is True
    assert tag_fact_types(text) == ["out_of_scope"]


def test_in_scope_expense_ratio_not_out_of_scope() -> None:
    text = "Expense Ratio (Direct): 0.82%. Exit load: Nil."
    assert _is_performance_only(text) is False
    tags = tag_fact_types(text)
    assert "expense_ratio" in tags
    assert "exit_load" in tags
    assert "out_of_scope" not in tags


def test_chunking_drops_pure_performance_sections() -> None:
    doc = CleanedDocument(
        url="https://example.com/fund",
        title="Test Fund",
        corpus="scheme",
        scheme_id="icici_flexicap_dg",
        text="placeholder",
        sections=[
            ("Returns", "1Y return 18%. 3Y CAGR 14%. Fund performance chart."),
            ("Expense Ratio", "Expense ratio is 0.75% for Direct Growth plan."),
        ],
        content_hash="hash",
        scraped_at=datetime.now(tz=IST),
        out_of_scope_sections=[],
    )
    # Simulate clean_page filtering: mark performance section as would be dropped upstream,
    # but also ensure chunk_document filters if it slips through via tag_fact_types.
    chunks = chunk_document(doc)
    texts = " ".join(c.text for c in chunks).lower()
    assert "expense ratio" in texts
    # Pure returns section should not produce an answerable chunk
    assert not any(
        "cagr" in c.text.lower() and "expense" not in c.text.lower() for c in chunks
    )


def test_clean_page_quarantines_performance_html() -> None:
    html = """
    <html><body>
      <main>
        <h2>Expense Ratio</h2>
        <p>Expense ratio is 0.55%.</p>
        <h2>Fund Performance</h2>
        <p>1Y return 21%. 3 year return 16%. Past performance vs benchmark.</p>
      </main>
    </body></html>
    """
    page = ScrapedPage(
        url="https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
        title="Flexicap",
        corpus="scheme",
        scheme_id="icici_flexicap_dg",
        html=html,
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = clean_page(page)
    assert cleaned is not None
    assert "expense ratio" in cleaned.text.lower()
    assert "1y return" not in cleaned.text.lower()
    assert "past performance" not in cleaned.text.lower()
