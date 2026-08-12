"""SOURCE_LIST URLs for scheme and general corpora."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.config.schemes import SCHEMES


Corpus = Literal["scheme", "general"]
SourceType = Literal["indmoney_scheme", "amc_faq", "sebi", "amfi"]


@dataclass(frozen=True)
class SourceConfig:
    url: str
    corpus: Corpus
    source_type: SourceType
    title: str
    scheme_id: str | None = None


SCHEME_SOURCES: tuple[SourceConfig, ...] = tuple(
    SourceConfig(
        url=s.source_url,
        corpus="scheme",
        source_type="indmoney_scheme",
        title=s.canonical_name,
        scheme_id=s.scheme_id,
    )
    for s in SCHEMES
)

GENERAL_SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://www.icicipruamc.com/help-center/faqs",
        corpus="general",
        source_type="amc_faq",
        title="ICICI Prudential AMC Help Center FAQs",
    ),
    # SEBI
    SourceConfig(
        url="https://investor.sebi.gov.in/riskometer.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Riskometer",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/understanding_mf.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Understanding Mutual Funds",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/securities-mf-investments.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Securities MF Investments",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/exchange_traded_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Exchange Traded Funds",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/regular_and_direct_mutual_funds.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Regular and Direct Mutual Funds",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/thematic_sectoral_mutual_funds.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Thematic / Sectoral Mutual Funds",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/fund_of_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Fund of Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/elss.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — ELSS",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/arbitrage_mutual_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Arbitrage Mutual Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/open_ended_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Open Ended Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/new_fund_offer.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — New Fund Offer",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/understanding_Tracking_error.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Understanding Tracking Error",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/interval_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Interval Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/index_mutual_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Index Mutual Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/closed_ended_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Closed Ended Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/balanced_fund.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Balanced Fund",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/exit_load.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Exit Load",
    ),
    SourceConfig(
        url="https://investor.sebi.gov.in/Brokers.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — Brokers",
    ),
    # AMFI
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TypesOfMutualFundSchemes",
        corpus="general",
        source_type="amfi",
        title="AMFI — Types of Mutual Fund Schemes",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio",
        corpus="general",
        source_type="amfi",
        title="AMFI — Expense Ratio",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds",
        corpus="general",
        source_type="amfi",
        title="AMFI — Risk in Mutual Funds",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=AdvantagesOfInvestingInMutualFunds",
        corpus="general",
        source_type="amfi",
        title="AMFI — Advantages of Investing in Mutual Funds",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes",
        corpus="general",
        source_type="amfi",
        title="AMFI — Categorization of Mutual Fund Schemes",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=HistoryOfMutualFundsInIndia",
        corpus="general",
        source_type="amfi",
        title="AMFI — History of Mutual Funds in India",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=DirectPlan",
        corpus="general",
        source_type="amfi",
        title="AMFI — Direct Plan",
    ),
    SourceConfig(
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CutOffTimingsAndNewRuleOnApplicableNAV",
        corpus="general",
        source_type="amfi",
        title="AMFI — Cut-off Timings and Applicable NAV",
    ),
)


def all_sources() -> tuple[SourceConfig, ...]:
    return SCHEME_SOURCES + GENERAL_SOURCES


def get_source_by_url(url: str) -> SourceConfig | None:
    normalized = url.rstrip("/")
    for src in all_sources():
        if src.url.rstrip("/") == normalized:
            return src
    return None
