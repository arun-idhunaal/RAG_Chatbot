"""Canonical scheme IDs, names, and aliases (Architecture §3.2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemeConfig:
    scheme_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    source_url: str


SCHEMES: tuple[SchemeConfig, ...] = (
    SchemeConfig(
        scheme_id="icici_nasdaq100_dg",
        canonical_name="ICICI Prudential Nasdaq 100 Index Fund (Direct Growth)",
        aliases=(
            "nasdaq 100",
            "icici nasdaq",
            "icici nasdaq 100",
            "nasdaq100",
            "icici prudential nasdaq 100 index fund",
        ),
        source_url=(
            "https://www.indmoney.com/mutual-funds/"
            "icici-prudential-nasdaq-100-index-fund-direct-growth"
        ),
    ),
    SchemeConfig(
        scheme_id="icici_midcap_dg",
        canonical_name="ICICI Prudential Midcap Fund (Direct Plan Growth)",
        aliases=(
            "icici midcap",
            "midcap fund",
            "icici mid cap",
            "icici prudential midcap",
            "midcap",
        ),
        source_url=(
            "https://www.indmoney.com/mutual-funds/"
            "icici-prudential-midcap-fund-direct-plan-growth"
        ),
    ),
    SchemeConfig(
        scheme_id="icici_flexicap_dg",
        canonical_name="ICICI Prudential Flexicap Fund (Direct Growth)",
        aliases=(
            "icici flexicap",
            "flexi cap",
            "flexicap",
            "icici flexi cap",
            "icici prudential flexicap",
        ),
        source_url=(
            "https://www.indmoney.com/mutual-funds/"
            "icici-prudential-flexicap-fund-direct-growth"
        ),
    ),
    SchemeConfig(
        scheme_id="icici_largecap_dg",
        canonical_name="ICICI Prudential Large Cap Fund (Direct Plan Growth)",
        aliases=(
            "icici large cap",
            "largecap",
            "icici largecap",
            "large cap fund",
            "icici prudential large cap",
        ),
        source_url=(
            "https://www.indmoney.com/mutual-funds/"
            "icici-prudential-large-cap-fund-direct-plan-growth"
        ),
    ),
    SchemeConfig(
        scheme_id="icici_elss_dg",
        canonical_name="ICICI Prudential ELSS Tax Saver Fund (Direct Plan Growth)",
        aliases=(
            "icici elss",
            "tax saver",
            "elss tax saver",
            "icici tax saver",
            "icici prudential elss",
        ),
        source_url=(
            "https://www.indmoney.com/mutual-funds/"
            "icici-prudential-elss-tax-saver-fund-direct-plan-growth"
        ),
    ),
)

_BY_ID = {s.scheme_id: s for s in SCHEMES}
_BY_URL = {s.source_url.rstrip("/"): s for s in SCHEMES}


def get_scheme_by_id(scheme_id: str) -> SchemeConfig | None:
    return _BY_ID.get(scheme_id)


def get_scheme_by_url(url: str) -> SchemeConfig | None:
    return _BY_URL.get(url.rstrip("/"))


def list_canonical_names() -> list[str]:
    return [s.canonical_name for s in SCHEMES]


def all_scheme_ids() -> list[str]:
    return [s.scheme_id for s in SCHEMES]
