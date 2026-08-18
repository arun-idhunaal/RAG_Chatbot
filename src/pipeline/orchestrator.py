"""Query orchestrator: PII → intent → scheme match → retrieve → answer/template (Phase 4)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from src.config.fact_types import FACT_TYPES
from src.config.schemes import all_scheme_ids, get_scheme_by_id, list_canonical_names
from src.config.settings import Settings, get_settings
from src.pipeline.answer_generator import GeneratedAnswer, generate_grounded_answer
from src.pipeline.comparison_templater import (
    UNSUPPORTED_FIELD_MESSAGE,
    render_comparison,
)
from src.pipeline.field_extractor import (
    COMPARISON_ALLOWED_FIELDS,
    LlmExtractFn,
    extract_field_for_scheme,
    is_allowed_comparison_field,
)
from src.pipeline.intent_classifier import classify_intent
from src.pipeline.models import Intent, PipelineResult, RetrievedChunk, SchemeMatchResult
from src.pipeline.pii_guard import check_pii
from src.pipeline.refusal_templates import (
    advisory_refusal,
    empty_query_refusal,
    out_of_corpus_refusal,
    unsupported_scheme_refusal,
)
from src.pipeline.scheme_resolver import mentions_unsupported_amc, resolve_scheme
from src.retrieval.retriever import Retriever, infer_fact_type

LlmGenerateFn = Callable[[str, list[RetrievedChunk]], dict[str, Any]]

_COMPARISON_CUES = re.compile(
    r"\b(?:compare|comparison|which of these|lowest|highest|among these|among the)\b"
    r"|\b(?:these|the)\s+(?:5|five)\b",
    re.IGNORECASE,
)
_ADVISORY_CUES = re.compile(
    r"\b(?:should i|recommend|best for me|good fund|suitable|is it good|which should i)\b",
    re.IGNORECASE,
)
_PERFORMANCE_CUES = re.compile(
    r"\b(?:return|returns|performance|cagr|outperform|nav)\b",
    re.IGNORECASE,
)


def process_query(
    message: str,
    *,
    settings: Settings | None = None,
    retriever: Retriever | None = None,
    llm_generate: LlmGenerateFn | None = None,
    llm_extract: LlmExtractFn | None = None,
    prior_scheme_id: str | None = None,
) -> PipelineResult:
    """Run full control plane covering all 8 taxonomy paths (Phase 4)."""
    settings = settings or get_settings()
    retriever = retriever or Retriever(settings=settings)
    text = (message or "").strip()
    supported = list_canonical_names()

    # Stage 1 — PII gate (FR-11). Never classify/retrieve on PII (EC-X-01).
    pii = check_pii(text)
    if pii.detected:
        return PipelineResult(
            intent=Intent.PII,
            original_message="",  # never persist/echo raw PII-bearing message
            short_circuit=True,
            short_circuit_reason="pii",
            refusal_message=pii.refusal_message,
            answer_text=pii.refusal_message,
        )

    if not text:
        msg = empty_query_refusal()
        return PipelineResult(
            intent=Intent.ADVISORY,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="empty_query",
            refusal_message=msg,
            answer_text=msg,
        )

    # Stage 2 — Intent classification (FR-1)
    classification = classify_intent(text, settings=settings)
    intent = classification.intent

    # Stage 3 — Early-exit intents
    if intent == Intent.ADVISORY:
        refusal = advisory_refusal()
        return PipelineResult(
            intent=intent,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="advisory",
            refusal_message=refusal,
            answer_text=refusal,
        )

    if intent == Intent.UNSUPPORTED_SCHEME:
        refusal = unsupported_scheme_refusal(scheme_names=supported)
        return PipelineResult(
            intent=intent,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="unsupported_scheme",
            supported_schemes=supported,
            refusal_message=refusal,
            answer_text=refusal,
        )

    if intent == Intent.OUT_OF_CORPUS_FACT_TYPE:
        return _handle_out_of_corpus(text, settings=settings)

    # Stage 4 — Retrieval + composition
    carried = _carried_scheme_id(
        text, intent, prior_scheme_id, settings=settings
    )
    if carried:
        return _handle_scheme_specific(
            text,
            scheme_id=carried,
            settings=settings,
            retriever=retriever,
            llm_generate=llm_generate,
        )

    if intent == Intent.GENERAL_FACTUAL:
        chunks = retriever.retrieve_general(text)
        return _with_grounded_answer(
            intent=intent,
            message=text,
            chunks=chunks,
            settings=settings,
            llm_generate=llm_generate,
        )

    if intent == Intent.CROSS_SCHEME_COMPARISON:
        return _handle_comparison(
            text,
            settings=settings,
            retriever=retriever,
            llm_extract=llm_extract,
            append_advisory=_ADVISORY_CUES.search(text) is not None,
        )

    if intent == Intent.MIXED:
        return _handle_mixed(
            text,
            settings=settings,
            retriever=retriever,
            llm_generate=llm_generate,
            llm_extract=llm_extract,
            supported=supported,
        )

    if intent == Intent.SCHEME_SPECIFIC_FACTUAL:
        return _handle_scheme_specific(
            text,
            scheme_id=None,
            settings=settings,
            retriever=retriever,
            llm_generate=llm_generate,
        )

    # Safe fallback
    refusal = advisory_refusal()
    return PipelineResult(
        intent=Intent.ADVISORY,
        original_message=text,
        short_circuit=True,
        short_circuit_reason="advisory",
        refusal_message=refusal,
        answer_text=refusal,
    )


_STANDALONE_DEFINITION = re.compile(
    r"\b(?:what(?:'s| is)\s+an?\b|define\b|explain\b)",
    re.IGNORECASE,
)
_CARRY_BLOCKED_INTENTS = frozenset(
    {
        Intent.ADVISORY,
        Intent.PII,
        Intent.CROSS_SCHEME_COMPARISON,
        Intent.OUT_OF_CORPUS_FACT_TYPE,
        Intent.MIXED,
        Intent.UNSUPPORTED_SCHEME,
    }
)


def _carried_scheme_id(
    text: str,
    intent: Intent,
    prior_scheme_id: str | None,
    *,
    settings: Settings,
) -> str | None:
    """Reuse last scheme for an in-scope field ask with no new scheme named."""
    if not prior_scheme_id or intent in _CARRY_BLOCKED_INTENTS:
        return None
    prior = get_scheme_by_id(prior_scheme_id)
    if prior is None:
        return None
    if mentions_unsupported_amc(text) or _COMPARISON_CUES.search(text):
        return None
    if infer_fact_type(text) not in FACT_TYPES:
        return None
    if _STANDALONE_DEFINITION.search(text):
        return None
    match = resolve_scheme(text, settings=settings)
    if match.matched and match.scheme_id != prior_scheme_id:
        return None
    return prior_scheme_id


def _handle_scheme_specific(
    text: str,
    *,
    scheme_id: str | None,
    settings: Settings,
    retriever: Retriever,
    llm_generate: LlmGenerateFn | None,
) -> PipelineResult:
    supported = list_canonical_names()
    if scheme_id:
        scheme = get_scheme_by_id(scheme_id)
        if scheme is None:
            scheme_id = None
        else:
            match = SchemeMatchResult(
                scheme_id=scheme.scheme_id,
                scheme_name=scheme.canonical_name,
                confidence=1.0,
                matched=True,
            )
    if not scheme_id:
        match = resolve_scheme(text, settings=settings)
        if not match.matched:
            refusal = unsupported_scheme_refusal(scheme_names=supported)
            return PipelineResult(
                intent=Intent.UNSUPPORTED_SCHEME,
                original_message=text,
                short_circuit=True,
                short_circuit_reason="scheme_unresolved",
                scheme_match=match,
                supported_schemes=supported,
                refusal_message=refusal,
                answer_text=refusal,
            )
        scheme_id = match.scheme_id

    chunks = retriever.retrieve_scheme(
        text,
        scheme_id,  # type: ignore[arg-type]
        fact_type=infer_fact_type(text),
    )
    return _with_grounded_answer(
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        message=text,
        chunks=chunks,
        scheme_id=scheme_id,
        scheme_match=match,
        settings=settings,
        llm_generate=llm_generate,
    )


def _handle_out_of_corpus(text: str, *, settings: Settings) -> PipelineResult:
    """FR-10 — distinct from FR-9; optional FR-7 append when advisory cues present."""
    match = resolve_scheme(text, settings=settings)
    # EC-OOC-04: unsupported scheme + returns → prefer FR-9
    if mentions_unsupported_amc(text) or (
        not match.matched and _looks_like_named_scheme(text)
    ):
        supported = list_canonical_names()
        refusal = unsupported_scheme_refusal(scheme_names=supported)
        return PipelineResult(
            intent=Intent.UNSUPPORTED_SCHEME,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="unsupported_scheme",
            scheme_match=match if not match.matched else None,
            supported_schemes=supported,
            refusal_message=refusal,
            answer_text=refusal,
        )

    ooc = out_of_corpus_refusal(
        scheme_id=match.scheme_id if match.matched else None,
        scheme_name=match.scheme_name if match.matched else None,
    )
    answer = ooc
    refusal_appended = False
    refusal_message = None
    if _ADVISORY_CUES.search(text):
        # EC-MIX-03: FR-10 style + separate refusal
        refusal_message = advisory_refusal(include_sebi_link=False)
        answer = f"{ooc}\n\n{refusal_message}"
        refusal_appended = True

    return PipelineResult(
        intent=Intent.OUT_OF_CORPUS_FACT_TYPE,
        original_message=text,
        short_circuit=True,
        short_circuit_reason="out_of_corpus_fact_type",
        scheme_id=match.scheme_id if match.matched else None,
        scheme_match=match if match.matched else None,
        answer_text=answer,
        refusal_message=refusal_message or ooc,
        refusal_appended=refusal_appended,
    )


def _handle_mixed(
    text: str,
    *,
    settings: Settings,
    retriever: Retriever,
    llm_generate: LlmGenerateFn | None,
    llm_extract: LlmExtractFn | None,
    supported: list[str],
) -> PipelineResult:
    """FR-8 — factual block then distinct refusal (EC-MIX-01…04, EC-X-02…03)."""
    # EC-MIX-04: unsupported scheme named → FR-9, do not invent ER
    if mentions_unsupported_amc(text):
        refusal = unsupported_scheme_refusal(scheme_names=supported)
        return PipelineResult(
            intent=Intent.UNSUPPORTED_SCHEME,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="unsupported_scheme",
            supported_schemes=supported,
            refusal_message=refusal,
            answer_text=refusal,
        )

    # EC-MIX-03: out-of-corpus factual part
    if _PERFORMANCE_CUES.search(text):
        return _handle_out_of_corpus(text, settings=settings)

    # EC-X-02: comparison + advisory → FR-4 values then FR-7
    if _COMPARISON_CUES.search(text):
        return _handle_comparison(
            text,
            settings=settings,
            retriever=retriever,
            llm_extract=llm_extract,
            append_advisory=True,
            force_intent=Intent.MIXED,
        )

    match = resolve_scheme(text, settings=settings)
    if not match.matched:
        refusal = unsupported_scheme_refusal(scheme_names=supported)
        return PipelineResult(
            intent=Intent.UNSUPPORTED_SCHEME,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="scheme_unresolved",
            scheme_match=match,
            supported_schemes=supported,
            refusal_message=refusal,
            answer_text=refusal,
        )

    chunks = retriever.retrieve_scheme(
        text,
        match.scheme_id,  # type: ignore[arg-type]
        fact_type=infer_fact_type(text),
    )
    result = _with_grounded_answer(
        intent=Intent.MIXED,
        message=text,
        chunks=chunks,
        scheme_id=match.scheme_id,
        scheme_match=match,
        settings=settings,
        llm_generate=llm_generate,
    )
    return _append_advisory_refusal(result)


def _handle_comparison(
    text: str,
    *,
    settings: Settings,
    retriever: Retriever,
    llm_extract: LlmExtractFn | None,
    append_advisory: bool = False,
    force_intent: Intent | None = None,
) -> PipelineResult:
    """FR-4 extract → template; optionally FR-8 append (EC-CMP-*, EC-X-02)."""
    fact_type = infer_fact_type(text)
    intent = force_intent or Intent.CROSS_SCHEME_COMPARISON

    if fact_type and fact_type not in COMPARISON_ALLOWED_FIELDS:
        # e.g. statement_download — not an allowed comparison field (EC-CMP-08)
        return PipelineResult(
            intent=Intent.OUT_OF_CORPUS_FACT_TYPE,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="out_of_corpus_fact_type",
            answer_text=UNSUPPORTED_FIELD_MESSAGE,
            refusal_message=UNSUPPORTED_FIELD_MESSAGE,
        )

    if not is_allowed_comparison_field(fact_type):
        # Bare "which of these 5" without field — still refuse invented ranking
        msg = (
            "I can compare expense ratio, exit load, minimum SIP, lock-in, "
            "riskometer, or benchmark across the five supported schemes. "
            "Please name which of those fields to compare."
        )
        return PipelineResult(
            intent=intent,
            original_message=text,
            short_circuit=True,
            short_circuit_reason="out_of_corpus_fact_type",
            answer_text=msg,
            refusal_message=msg,
        )

    assert fact_type is not None
    scheme_ids = all_scheme_ids()
    all_chunks: list[RetrievedChunk] = []
    rows = []
    for scheme_id in scheme_ids:
        chunks = retriever.retrieve_scheme_field(scheme_id, fact_type)
        all_chunks.extend(chunks)
        rows.append(
            extract_field_for_scheme(
                scheme_id,
                fact_type,
                chunks,
                settings=settings,
                llm_extract=llm_extract,
            )
        )

    comparison = render_comparison(rows, field=fact_type)
    result = PipelineResult(
        intent=intent,
        original_message=text,
        short_circuit=False,
        scheme_ids=scheme_ids,
        chunks=all_chunks,
        retrieval_empty=len(all_chunks) == 0,
        answer_text=comparison.answer_text,
        citations=list(comparison.citations),
        last_updated_from_sources=comparison.last_updated_from_sources,
        insufficient_context=comparison.insufficient_context,
        comparison_field=fact_type,
        comparison_rows=list(comparison.rows),
    )
    if append_advisory:
        result = _append_advisory_refusal(result)
    return result


def _append_advisory_refusal(result: PipelineResult) -> PipelineResult:
    """FR-8 — keep fact and refusal structurally distinct (EC-MIX-01, EC-MIX-02)."""
    refusal = advisory_refusal(include_sebi_link=False)
    fact = (result.answer_text or "").rstrip()
    if fact:
        result.answer_text = f"{fact}\n\n{refusal}"
    else:
        result.answer_text = refusal
    result.refusal_message = refusal
    result.refusal_appended = True
    return result


def _with_grounded_answer(
    *,
    intent: Intent,
    message: str,
    chunks: list[RetrievedChunk],
    settings: Settings,
    scheme_id: str | None = None,
    scheme_match=None,
    llm_generate: LlmGenerateFn | None = None,
) -> PipelineResult:
    generated = generate_grounded_answer(
        message,
        chunks,
        intent=intent,
        scheme_id=scheme_id,
        settings=settings,
        llm_generate=llm_generate,
    )
    return _attach_answer(
        _result_with_chunks(
            intent=intent,
            message=message,
            chunks=chunks,
            scheme_id=scheme_id,
            scheme_match=scheme_match,
        ),
        generated,
    )


def _attach_answer(result: PipelineResult, generated: GeneratedAnswer) -> PipelineResult:
    result.answer_text = generated.answer_text
    result.citations = list(generated.citations)
    result.last_updated_from_sources = generated.last_updated_from_sources
    result.insufficient_context = generated.insufficient_context
    return result


def _result_with_chunks(
    *,
    intent: Intent,
    message: str,
    chunks: list,
    scheme_id: str | None = None,
    scheme_ids: list[str] | None = None,
    scheme_match=None,
) -> PipelineResult:
    return PipelineResult(
        intent=intent,
        original_message=message,
        short_circuit=False,
        scheme_id=scheme_id,
        scheme_ids=scheme_ids or [],
        scheme_match=scheme_match,
        chunks=chunks,
        retrieval_empty=len(chunks) == 0,
    )


def _looks_like_named_scheme(text: str) -> bool:
    """True when an unsupported AMC/scheme brand is named (not generic 'fund')."""
    return mentions_unsupported_amc(text)
