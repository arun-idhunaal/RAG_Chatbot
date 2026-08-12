"""Happy-path cases derived from SAMPLE_Q&A_RAGMFCHATBOT.md (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass

from src.pipeline.models import Intent


@dataclass(frozen=True)
class SampleQACase:
    case_id: str
    question: str
    expected_intent: Intent
    section: str


# Concrete questions for the five supported schemes (placeholders filled).
SAMPLE_QA_CASES: tuple[SampleQACase, ...] = (
    SampleQACase(
        "SQA-01",
        "What is the expense ratio of ICICI Prudential Flexicap Fund?",
        Intent.SCHEME_SPECIFIC_FACTUAL,
        "scheme_specific",
    ),
    SampleQACase(
        "SQA-02",
        "What is the exit load for ICICI Prudential Midcap Fund?",
        Intent.SCHEME_SPECIFIC_FACTUAL,
        "scheme_specific",
    ),
    SampleQACase(
        "SQA-03",
        "What is the minimum SIP amount for ICICI Prudential Large Cap Fund?",
        Intent.SCHEME_SPECIFIC_FACTUAL,
        "scheme_specific",
    ),
    SampleQACase(
        "SQA-04",
        "Does ICICI Prudential ELSS Tax Saver Fund have a lock-in period?",
        Intent.SCHEME_SPECIFIC_FACTUAL,
        "scheme_specific",
    ),
    SampleQACase(
        "SQA-05",
        "What benchmark does ICICI Prudential Nasdaq 100 Index Fund use?",
        Intent.SCHEME_SPECIFIC_FACTUAL,
        "scheme_specific",
    ),
    SampleQACase(
        "SQA-06",
        "What is an expense ratio in a mutual fund?",
        Intent.GENERAL_FACTUAL,
        "general",
    ),
    SampleQACase(
        "SQA-07",
        "What is an exit load?",
        Intent.GENERAL_FACTUAL,
        "general",
    ),
    SampleQACase(
        "SQA-08",
        "What is a mutual fund riskometer?",
        Intent.GENERAL_FACTUAL,
        "general",
    ),
    SampleQACase(
        "SQA-09",
        "How can I download my mutual fund statement?",
        Intent.GENERAL_FACTUAL,
        "general",
    ),
    SampleQACase(
        "SQA-10",
        "What is the difference between SIP and lump-sum investment?",
        Intent.GENERAL_FACTUAL,
        "general",
    ),
    SampleQACase(
        "SQA-11",
        "Which mutual fund is best for me?",
        Intent.ADVISORY,
        "advisory",
    ),
    SampleQACase(
        "SQA-12",
        "Should I invest in a small-cap fund now?",
        Intent.ADVISORY,
        "advisory",
    ),
    SampleQACase(
        "SQA-13",
        "Which of these funds should I choose for my portfolio?",
        Intent.ADVISORY,
        "advisory",
    ),
    SampleQACase(
        "SQA-14",
        "Do you think ICICI Prudential Flexicap Fund will outperform its benchmark?",
        Intent.ADVISORY,
        "advisory",
    ),
    SampleQACase(
        "SQA-15",
        "Is this a good time to start an SIP in an equity mutual fund?",
        Intent.ADVISORY,
        "advisory",
    ),
    SampleQACase(
        "SQA-16",
        "What is the expense ratio of ICICI Prudential Flexicap Fund, and is it a good fund to invest in?",
        Intent.MIXED,
        "mixed",
    ),
    SampleQACase(
        "SQA-17",
        "What is the exit load of ICICI Prudential Midcap Fund, and should I avoid this fund because of it?",
        Intent.MIXED,
        "mixed",
    ),
)
