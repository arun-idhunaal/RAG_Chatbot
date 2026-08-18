"""SOURCE_LIST URLs for scheme and general corpora.

Canonical list: `DOCS/SOURCE_LIST_RAGMFCHATBOT.md` — 18 URLs
(5 INDmoney scheme + 1 AMC FAQ + 9 SEBI + 3 AMFI).
"""

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
    # SEBI (9)
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
        url="https://investor.sebi.gov.in/elss.html",
        corpus="general",
        source_type="sebi",
        title="SEBI — ELSS",
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
    # AMFI (3)
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
        url="https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes",
        corpus="general",
        source_type="amfi",
        title="AMFI — Categorization of Mutual Fund Schemes",
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
