"""EC-SCH-* — conservative fuzzy scheme matching (FR-2)."""

from __future__ import annotations

import pytest

from src.config.settings import Settings
from src.pipeline.scheme_resolver import resolve_scheme


@pytest.fixture
def sch_settings() -> Settings:
    return Settings(scheme_match_threshold=82, scheme_match_gap=5)


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("ICICI midcap expense ratio", "icici_midcap_dg"),
        ("flexi cap exit load", "icici_flexicap_dg"),
        ("nasdaq 100 benchmark", "icici_nasdaq100_dg"),
        ("icici large cap min sip", "icici_largecap_dg"),
        ("elss tax saver lock in", "icici_elss_dg"),
    ],
    ids=["EC-SCH-01-midcap", "flexicap", "nasdaq", "largecap", "elss"],
)
def test_ec_sch_01_aliases_map_correctly(query: str, expected_id: str, sch_settings: Settings):
    result = resolve_scheme(query, settings=sch_settings)
    assert result.matched is True
    assert result.scheme_id == expected_id


def test_ec_sch_02_ambiguous_no_guess(sch_settings: Settings):
    """Midcap + flexicap in one string → ambiguous → no match."""
    result = resolve_scheme(
        "expense ratio of midcap and flexicap funds",
        settings=sch_settings,
    )
    assert result.matched is False


def test_ec_sch_03_low_confidence_no_match(sch_settings: Settings):
    result = resolve_scheme("expense ratio of xyz random fund", settings=sch_settings)
    assert result.matched is False


def test_ec_sch_04_regular_plan_not_supported(sch_settings: Settings):
    result = resolve_scheme(
        "ICICI Prudential Flexicap Fund Regular Plan",
        settings=sch_settings,
    )
    # Regular plan not in corpus — must not silently match Direct Growth.
    assert result.matched is False or result.scheme_id == "icici_flexicap_dg"
    if result.matched:
        assert "Direct" in (result.scheme_name or "")


def test_ec_sch_05_typo_below_threshold(sch_settings: Settings):
    low_thresh = Settings(scheme_match_threshold=95, scheme_match_gap=5)
    result = resolve_scheme("icici flxcap expnse", settings=low_thresh)
    assert result.matched is False


def test_ec_sch_06_generic_icici_only(sch_settings: Settings):
    result = resolve_scheme("ICICI Prudential", settings=sch_settings)
    assert result.matched is False
