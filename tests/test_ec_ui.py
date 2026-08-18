"""EC-UI — FR-12 rendering contracts (framework-agnostic DTO + copy)."""

from __future__ import annotations

from src.api.dto import (
    citations_markdown,
    has_all_supported_schemes,
    linkify_urls,
    pipeline_result_to_chat_response,
    split_mixed_answer,
    ui_config,
)
from src.config.schemes import list_canonical_names
from src.pipeline.models import Citation, Intent, PipelineResult
from src.pipeline.refusal_templates import ADVISORY_REFUSAL, unsupported_scheme_refusal
from src.ui_copy import DISCLAIMER, EXAMPLE_QUESTIONS, WELCOME_MESSAGE


def test_ec_ui_01_welcome_and_three_examples():
    cfg = ui_config()
    assert "facts only" in cfg.welcome_message.lower() or "facts-only" in cfg.welcome_message.lower()
    assert "investment advice" in cfg.welcome_message.lower()
    assert len(cfg.example_questions) == 3
    joined = " ".join(cfg.example_questions).lower()
    assert "expense ratio" in joined
    assert "exit load" in joined
    assert "lowest" in joined or "which of these" in joined
    assert WELCOME_MESSAGE == cfg.welcome_message


def test_ec_ui_02_disclaimer_always_defined():
    assert DISCLAIMER == "Facts-only. No investment advice."
    assert ui_config().disclaimer == DISCLAIMER


def test_ec_ui_03_citation_links_and_inline_date():
    result = PipelineResult(
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        original_message="What is the expense ratio of Flexicap?",
        answer_text="The expense ratio is 0.5%.",
        citations=[
            Citation(
                title="ICICI Prudential Flexicap Fund (Direct Growth)",
                url="https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
            )
        ],
        last_updated_from_sources="2026-08-12",
    )
    view = pipeline_result_to_chat_response(result)
    assert "Last updated from sources: 2026-08-12" in view.answer_text
    assert view.citations
    md = citations_markdown([c.model_dump() for c in view.citations])
    assert "](https://www.indmoney.com/mutual-funds/" in md
    linked = linkify_urls("See https://example.com/page for details")
    assert "](https://example.com/page)" in linked


def test_ec_ui_04_mixed_fact_and_refusal_visually_split():
    answer = (
        "The expense ratio of ICICI Prudential Flexicap Fund is 0.5%.\n\n"
        "Last updated from sources: 2026-08-12\n\n"
        f"{ADVISORY_REFUSAL}"
    )
    fact, refusal = split_mixed_answer(answer, refusal_message=ADVISORY_REFUSAL)
    assert "0.5%" in fact
    assert "Last updated from sources:" in fact
    assert "investment advice" in refusal.lower()
    assert fact != refusal

    result = PipelineResult(
        intent=Intent.MIXED,
        original_message="ER of Flexicap, and is it good?",
        answer_text=answer,
        refusal_message=ADVISORY_REFUSAL,
        refusal_appended=True,
        citations=[
            Citation(title="Flexicap", url="https://example.com/icici_flexicap_dg")
        ],
        last_updated_from_sources="2026-08-12",
    )
    view = pipeline_result_to_chat_response(result)
    assert view.refusal_appended is True
    assert view.refusal_message
    assert "0.5%" in view.answer_text
    assert ADVISORY_REFUSAL not in view.answer_text
    assert "investment advice" in (view.refusal_message or "").lower()


def test_ec_ui_05_fr9_lists_all_five_schemes():
    names = list_canonical_names()
    refusal = unsupported_scheme_refusal(scheme_names=names)
    assert has_all_supported_schemes(refusal, names)
    assert len(names) == 5

    result = PipelineResult(
        intent=Intent.UNSUPPORTED_SCHEME,
        original_message="Expense ratio of HDFC Flexicap?",
        short_circuit=True,
        short_circuit_reason="unsupported_scheme",
        answer_text=refusal,
        refusal_message=refusal,
        supported_schemes=names,
    )
    view = pipeline_result_to_chat_response(result)
    combined = f"{view.answer_text}\n" + "\n".join(view.supported_schemes)
    assert has_all_supported_schemes(combined, names)
    assert len(view.supported_schemes) == 5


def test_ec_ui_06_examples_are_real_pipeline_queries():
    """Example chips must send real questions — not hardcoded fake answers."""
    assert len(EXAMPLE_QUESTIONS) == 3
    for q in EXAMPLE_QUESTIONS:
        assert isinstance(q, str) and len(q) > 10
        assert "?" in q
    assert EXAMPLE_QUESTIONS[0] != EXAMPLE_QUESTIONS[1]
    assert "which of these" in EXAMPLE_QUESTIONS[2].lower()
    assert ui_config().example_questions == list(EXAMPLE_QUESTIONS)
