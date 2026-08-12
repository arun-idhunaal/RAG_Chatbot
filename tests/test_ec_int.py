"""EC-INT-* — hybrid intent classifier routing (rules-only for determinism)."""

from __future__ import annotations

import pytest

from src.config.settings import Settings
from src.pipeline.intent_classifier import classify_intent
from src.pipeline.models import Intent


@pytest.fixture
def rules_settings() -> Settings:
    return Settings(use_llm_classifier=False, groq_api_key="")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Expense ratio of Flexicap, and is it good?", Intent.MIXED),
        ("Should I invest in Midcap?", Intent.ADVISORY),
        ("1Y return of ICICI Midcap?", Intent.OUT_OF_CORPUS_FACT_TYPE),
        ("Expense ratio of HDFC Flexicap?", Intent.UNSUPPORTED_SCHEME),
        ("Which of these 5 has lowest expense ratio?", Intent.CROSS_SCHEME_COMPARISON),
        ("Which of these is best for me?", Intent.ADVISORY),
        ("What is an exit load?", Intent.GENERAL_FACTUAL),
        ("expense ratio of icici midcap", Intent.SCHEME_SPECIFIC_FACTUAL),
        ("Compare performance of these 5 funds", Intent.OUT_OF_CORPUS_FACT_TYPE),
    ],
    ids=[
        "EC-INT-01-mixed",
        "EC-INT-02-advisory",
        "EC-INT-03-performance",
        "EC-INT-04-unsupported",
        "EC-INT-05-comparison",
        "EC-INT-06-advice-comparison",
        "EC-INT-07-general",
        "EC-INT-08-scheme-fact",
        "EC-INT-12-perf-compare",
    ],
)
def test_intent_classification_edge_cases(message: str, expected: Intent, rules_settings: Settings):
    result = classify_intent(message, settings=rules_settings)
    assert result.intent == expected


def test_all_eight_intent_labels_reachable(rules_settings: Settings):
    """Smoke: each taxonomy label is classifiable (routing coverage)."""
    samples = {
        Intent.SCHEME_SPECIFIC_FACTUAL: "expense ratio of icici flexicap",
        Intent.CROSS_SCHEME_COMPARISON: "lowest expense ratio among these 5 schemes",
        Intent.GENERAL_FACTUAL: "what is an exit load",
        Intent.UNSUPPORTED_SCHEME: "expense ratio of HDFC flexicap",
        Intent.OUT_OF_CORPUS_FACT_TYPE: "1 year return of icici midcap",
        Intent.ADVISORY: "should I invest in elss",
        Intent.MIXED: "exit load of flexicap, is it good?",
    }
    for intent, msg in samples.items():
        assert classify_intent(msg, settings=rules_settings).intent == intent
