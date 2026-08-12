"""Sample Q&A happy-path intent routing (Phase 6)."""

from __future__ import annotations

import pytest

from eval.sample_qa import SAMPLE_QA_CASES
from src.config.settings import Settings
from src.pipeline.intent_classifier import classify_intent


@pytest.fixture
def rules_settings() -> Settings:
    return Settings(use_llm_classifier=False, groq_api_key="")


@pytest.mark.parametrize(
    "case",
    SAMPLE_QA_CASES,
    ids=[c.case_id for c in SAMPLE_QA_CASES],
)
def test_sample_qa_intent_routing(case, rules_settings: Settings):
    got = classify_intent(case.question, settings=rules_settings).intent
    assert got == case.expected_intent
