"""Hybrid intent classifier: rules pre-filter + optional LLM structured output (FR-1)."""

from __future__ import annotations

import re
from typing import Callable

from src.config.fact_types import PERFORMANCE_KEYWORDS
from src.config.settings import Settings, get_settings
from src.pipeline.llm import chat_json, llm_available
from src.pipeline.models import ClassificationResult, Intent
from src.pipeline.scheme_resolver import mentions_unsupported_amc, resolve_scheme
from src.prompts.intent_classifier import CLASSIFIER_SYSTEM_PROMPT

# --- Rule patterns ---

_ADVISORY_PATTERNS = (
    r"\bshould i\b",
    r"\bought? to invest\b",
    r"\brecommend\b",
    r"\bbest fund\b",
    r"\bbest for me\b",
    r"\bgood fund\b",
    r"\bgood time\b",
    r"\bis this a good\b",
    r"\bsuitable\b",
    r"\bwhich should i pick\b",
    r"\bwhich one should i\b",
    r"\bwhich is better\b",
    r"\bwhich(?:\s+\w+){0,4}\s+better\b",
    r"\bis it good\b",
    r"\bis it worth\b",
    r"\bworth investing\b",
    r"\bbetter choice\b",
    r"\bwhich is best\b",
    r"\bfor me\b",
    r"\bdo you think\b",
    r"\benough\b",
    r"\bshould i (?:buy|avoid|choose|pick)\b",
)

_FACTUAL_CUES = (
    "expense ratio",
    "exit load",
    "minimum sip",
    "min sip",
    "lock-in",
    "lock in",
    "riskometer",
    "benchmark",
    "statement",
    "download",
    "what is",
    "how to",
    "define",
    "definition",
)

_COMPARISON_PATTERNS = (
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bwhich of these\b",
    r"\bwhich of the\b",
    r"\blowest\b",
    r"\bhighest\b",
    r"\bamong these\b",
    r"\bamong the\b",
    r"\b5 (?:funds?|schemes?)\b",
    r"\bfive (?:funds?|schemes?)\b",
)

_ALLOWED_COMPARISON_FIELDS = (
    "expense ratio",
    "exit load",
    "minimum sip",
    "min sip",
    "lock-in",
    "lock in",
    "riskometer",
    "benchmark",
)


def classify_intent(
    message: str,
    *,
    settings: Settings | None = None,
    llm_classify: Callable[[str, Intent | None], Intent] | None = None,
) -> ClassificationResult:
    """Classify query into exactly one of 8 taxonomy labels."""
    settings = settings or get_settings()
    text = (message or "").strip()
    if not text:
        return ClassificationResult(intent=Intent.ADVISORY, rationale="empty query")

    rules_hint = _rules_classify(text)

    if llm_available(settings) and llm_classify is None:
        llm_classify = _default_llm_classify_factory(settings)

    if llm_classify is not None:
        try:
            llm_intent = llm_classify(text, rules_hint)
            return ClassificationResult(
                intent=llm_intent,
                rules_hint=rules_hint,
                rationale="llm",
            )
        except Exception:  # noqa: BLE001 — fall back to rules
            pass

    intent = rules_hint or Intent.ADVISORY
    return ClassificationResult(intent=intent, rules_hint=rules_hint, rationale="rules")


def _rules_classify(text: str) -> Intent | None:
    lower = text.lower()

    has_advisory = _matches_any(lower, _ADVISORY_PATTERNS)
    has_performance = _has_performance_ask(lower)
    # Scheme name alone is not a factual ask (EC-INT-02 vs EC-INT-01).
    has_factual = _has_factual_cue(lower)
    has_comparison = _matches_any(lower, _COMPARISON_PATTERNS)
    has_allowed_comparison_field = any(f in lower for f in _ALLOWED_COMPARISON_FIELDS)
    unsupported_amc = mentions_unsupported_amc(lower)

    # Sample Q&A Q14 / forecast-as-advice: advisory + performance without a
    # concrete in-corpus fact field → FR-7, unless the user also asks for an
    # explicit returns figure (EC-MIX-03 → mixed / FR-10 + refusal).
    _in_corpus_fact_fields = (
        "expense ratio",
        "exit load",
        "minimum sip",
        "min sip",
        "lock-in",
        "lock in",
        "riskometer",
        "statement",
        "download",
    )
    explicit_ooc_fact_ask = bool(
        re.search(
            r"\b(?:what(?:'s| is)\b.*\b(?:return|returns|performance|cagr|nav)\b)"
            r"|\b(?:return|returns|performance|cagr|nav)\s+of\b"
            r"|\b(?:1y|1\s*year|one year)\s+return\b",
            lower,
        )
    )
    if (
        has_advisory
        and has_performance
        and not any(f in lower for f in _in_corpus_fact_fields)
        and not explicit_ooc_fact_ask
    ):
        return Intent.ADVISORY

    # EC-INT-01, EC-MIX: factual + advisory → mixed
    if has_advisory and has_factual:
        return Intent.MIXED

    # EC-CMP-04 / EC-INT-06: "which is better" / comparison framed as advice
    if has_advisory and (has_comparison or _mentions_supported_scheme(lower)):
        # Pure advice about schemes (no allowed-field fact ask) → advisory
        if not has_factual:
            return Intent.ADVISORY

    # EC-INT-04: unsupported AMC + fact
    if unsupported_amc:
        return Intent.UNSUPPORTED_SCHEME

    # EC-INT-12: compare performance → out_of_corpus
    if has_performance and has_comparison:
        return Intent.OUT_OF_CORPUS_FACT_TYPE

    # EC-INT-03: performance on supported scheme
    if has_performance:
        return Intent.OUT_OF_CORPUS_FACT_TYPE

    # EC-INT-06: comparison as advice
    if has_advisory and has_comparison:
        return Intent.ADVISORY

    # EC-INT-02, EC-ADV: pure advisory
    if has_advisory:
        return Intent.ADVISORY

    # EC-INT-05: allowed field comparison across schemes
    if has_comparison and has_allowed_comparison_field and not has_performance:
        return Intent.CROSS_SCHEME_COMPARISON

    # Bare ranking without field — still comparison if "these 5" mentioned
    if has_comparison and re.search(r"\b(?:these|the)\s+(?:5|five)\b", lower):
        if has_performance:
            return Intent.OUT_OF_CORPUS_FACT_TYPE
        return Intent.CROSS_SCHEME_COMPARISON

    # EC-INT-07: general definition
    if _is_general_definition(lower):
        return Intent.GENERAL_FACTUAL

    # EC-INT-08: scheme-specific factual
    match = resolve_scheme(text)
    if match.matched:
        return Intent.SCHEME_SPECIFIC_FACTUAL

    # Scheme-like tokens but unresolved
    if _mentions_supported_scheme(lower):
        return Intent.UNSUPPORTED_SCHEME

    # Gibberish / unknown — safe refusal path (EC-INT-10)
    if len(lower) < 4 or not re.search(r"[a-z]{3,}", lower):
        return Intent.ADVISORY

    return Intent.GENERAL_FACTUAL


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _has_performance_ask(lower: str) -> bool:
    return any(kw in lower for kw in PERFORMANCE_KEYWORDS) or bool(
        re.search(r"\b(?:return|returns|performance|cagr|nav)\b", lower)
    )


def _has_factual_cue(lower: str) -> bool:
    return any(cue in lower for cue in _FACTUAL_CUES)


def _mentions_supported_scheme(lower: str) -> bool:
    cues = (
        "nasdaq",
        "midcap",
        "mid cap",
        "flexicap",
        "flexi cap",
        "large cap",
        "largecap",
        "elss",
        "tax saver",
        "icici prudential",
        "icici",
    )
    return any(c in lower for c in cues)


def _is_general_definition(lower: str) -> bool:
    if not re.search(r"\bwhat is\b|\bwhat's\b|\bdefine\b|\bexplain\b", lower):
        return False
    # "what is expense ratio of flexicap" is scheme-specific, not general
    if resolve_scheme(lower).matched:
        return False
    if _mentions_supported_scheme(lower) and any(
        f in lower for f in ("expense ratio", "exit load", "sip", "lock", "benchmark", "riskometer")
    ):
        return False
    return True


def _default_llm_classify_factory(settings: Settings) -> Callable[[str, Intent | None], Intent]:
    def _classify(message: str, rules_hint: Intent | None) -> Intent:
        user_content = message
        if rules_hint:
            user_content = f"Rules-stage hint: {rules_hint.value}\n\nUser query: {message}"

        data = chat_json(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            user_content=user_content,
            settings=settings,
        )
        label = str(data.get("intent", "advisory")).strip().lower()
        try:
            return Intent(label)
        except ValueError:
            return rules_hint or Intent.ADVISORY

    return _classify
