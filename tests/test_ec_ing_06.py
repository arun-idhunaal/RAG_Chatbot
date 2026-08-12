"""EC-ING-06: Related-fund chrome must not contaminate another scheme_id."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.config.schemes import SCHEMES
from src.ingestion.clean import clean_page
from src.ingestion.models import ScrapedPage

IST = ZoneInfo("Asia/Kolkata")


def _scheme(scheme_id: str):
    return next(s for s in SCHEMES if s.scheme_id == scheme_id)


def test_related_funds_carousel_stripped() -> None:
    flexi = _scheme("icici_flexicap_dg")
    midcap = _scheme("icici_midcap_dg")

    html = f"""
    <html><body>
      <main>
        <h1>{flexi.canonical_name}</h1>
        <h2>Expense Ratio</h2>
        <p>Expense ratio for this fund is 0.81%.</p>
        <h2>Related Funds</h2>
        <div class="related-funds">
          <a href="{midcap.source_url}">ICICI Prudential Midcap Fund</a>
          <p>Expense ratio 1.05%. Explore Midcap.</p>
        </div>
        <section class="similarFunds">
          <a href="{midcap.source_url}">View Midcap</a>
        </section>
      </main>
    </body></html>
    """
    page = ScrapedPage(
        url=flexi.source_url,
        title=flexi.canonical_name,
        corpus="scheme",
        scheme_id=flexi.scheme_id,
        html=html,
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = clean_page(page)
    assert cleaned is not None
    assert cleaned.scheme_id == "icici_flexicap_dg"
    text = cleaned.text.lower()
    assert "0.81%" in text or "expense ratio" in text
    # Midcap expense from related carousel must not remain
    assert "1.05%" not in text
    assert "related funds" not in text


def test_peer_comparison_table_dropped() -> None:
    flexi = _scheme("icici_flexicap_dg")
    html = f"""
    <html><body><main>
      <h1>{flexi.canonical_name}</h1>
      <h2>Expense Ratio</h2>
      <p>Expense ratio for Direct Growth is 0.67%.</p>
      <h2>ICICI Prudential Flexicap Fund Ranking and Peer Comparison</h2>
      <table>
        <tr><th>Fund Name</th><th>Expense Ratio</th><th>1Y Returns</th></tr>
        <tr><td>ICICI Prudential Flexicap Fund</td><td>0.67%</td><td>16.99%</td></tr>
        <tr><td>HDFC Flexi Cap Fund</td><td>0.75%</td><td>7.17%</td></tr>
      </table>
    </main></body></html>
    """
    page = ScrapedPage(
        url=flexi.source_url,
        title=flexi.canonical_name,
        corpus="scheme",
        scheme_id=flexi.scheme_id,
        html=html,
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = clean_page(page)
    assert cleaned is not None
    text = cleaned.text.lower()
    assert "0.67%" in text
    assert "hdfc" not in text
    assert "peer comparison" not in text


def test_cross_scheme_link_cards_removed() -> None:
    nasdaq = _scheme("icici_nasdaq100_dg")
    elss = _scheme("icici_elss_dg")

    html = f"""
    <html><body><article>
      <h2>Benchmark</h2>
      <p>Benchmark: Nasdaq 100 TRI.</p>
      <div class="card">
        <a href="{elss.source_url}">Invest in ELSS Tax Saver</a>
        <span>Lock-in 3 years. Similar fund.</span>
      </div>
    </article></body></html>
    """
    page = ScrapedPage(
        url=nasdaq.source_url,
        title=nasdaq.canonical_name,
        corpus="scheme",
        scheme_id=nasdaq.scheme_id,
        html=html,
        scraped_at=datetime.now(tz=IST),
        status="ok",
    )
    cleaned = clean_page(page)
    assert cleaned is not None
    text = cleaned.text.lower()
    assert "nasdaq" in text or "benchmark" in text
    assert "lock-in 3 years" not in text
    assert "elss tax saver" not in text or "invest in elss" not in text
