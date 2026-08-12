"""Deterministic refusal copy for FR-7 / FR-9 / FR-10 / FR-11 (Phase 4)."""

from __future__ import annotations

from src.config.schemes import get_scheme_by_id, list_canonical_names
from src.pipeline.pii_guard import PII_REFUSAL_MESSAGE

# Sample Q&A §3 / FR-7 — fixed polite refusal; do not echo advisory framing (EC-ADV-02).
ADVISORY_REFUSAL = (
    "I am designed to give only facts, not investment advice. Thanks for your understanding."
)

# Optional SEBI investor-education link (FR-7) — not a product recommendation.
SEBI_INVESTOR_EDU_URL = "https://investor.sebi.gov.in/understanding_mf.html"
SEBI_INVESTOR_EDU_LINE = (
    f"For general investor education, see: {SEBI_INVESTOR_EDU_URL}"
)


def advisory_refusal(*, include_sebi_link: bool = True) -> str:
    """FR-7 / EC-ADV-01…03 — fixed refusal; never hedge with uncited facts."""
    if include_sebi_link:
        return f"{ADVISORY_REFUSAL}\n\n{SEBI_INVESTOR_EDU_LINE}"
    return ADVISORY_REFUSAL


def unsupported_scheme_refusal(
    *,
    scheme_names: list[str] | None = None,
) -> str:
    """
    FR-9 / EC-UNS-01…04 — scheme not covered; list exactly the 5 supported names.
    Distinct from FR-10 (EC-OOC-04).
    """
    names = scheme_names or list_canonical_names()
    bullets = "\n".join(f"- {n}" for n in names)
    return (
        "I don't cover that scheme. I only have facts for these supported schemes:\n"
        f"{bullets}"
    )


def out_of_corpus_refusal(
    *,
    scheme_id: str | None = None,
    scheme_name: str | None = None,
    source_url: str | None = None,
) -> str:
    """
    FR-10 / EC-OOC-01…03 — scheme known (when matched), fact type not covered.
    Never compute/estimate returns. Distinct from FR-9 (EC-OOC-04).
    """
    scheme = get_scheme_by_id(scheme_id) if scheme_id else None
    name = scheme_name or (scheme.canonical_name if scheme else None)
    url = source_url or (scheme.source_url if scheme else None)

    if name and url:
        return (
            f"I cover {name}, but I don't provide performance or returns figures. "
            "I never compute or estimate returns. "
            f"See the official scheme page for disclosures: {url}"
        )
    if name:
        return (
            f"I cover {name}, but I don't provide performance or returns figures. "
            "I never compute or estimate returns. "
            "Please check the official scheme factsheet or INDmoney scheme page."
        )
    return (
        "I don't provide performance or returns figures for mutual fund schemes. "
        "I never compute or estimate returns. "
        "For supported schemes, see the official scheme page on INDmoney."
    )


def pii_refusal() -> str:
    """FR-11 — reuse gate copy; never echo PII."""
    return PII_REFUSAL_MESSAGE


def empty_query_refusal() -> str:
    return (
        "Please type a facts-only question about the supported ICICI Prudential schemes."
    )
