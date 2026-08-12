"""Shared types for the query pipeline (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Intent(StrEnum):
    """FR-1 taxonomy — exactly one label per query."""

    SCHEME_SPECIFIC_FACTUAL = "scheme_specific_factual"
    CROSS_SCHEME_COMPARISON = "cross_scheme_comparison"
    GENERAL_FACTUAL = "general_factual"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    OUT_OF_CORPUS_FACT_TYPE = "out_of_corpus_fact_type"
    ADVISORY = "advisory"
    MIXED = "mixed"
    PII = "pii"


ShortCircuitReason = Literal[
    "pii",
    "advisory",
    "unsupported_scheme",
    "out_of_corpus_fact_type",
    "empty_query",
    "scheme_unresolved",
]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    corpus: Literal["scheme", "general"]
    scheme_id: str | None
    source_url: str
    source_title: str
    page_ref: str | None
    scraped_at: str
    fact_types: list[str]
    similarity: float
    distance: float | None = None

    @classmethod
    def from_store_hit(cls, hit: dict[str, Any]) -> RetrievedChunk:
        meta = hit.get("metadata") or {}
        distance = hit.get("distance")
        similarity = hit.get("similarity")
        if similarity is None and distance is not None:
            similarity = max(0.0, 1.0 - float(distance))
        fact_raw = meta.get("fact_types") or ""
        fact_types = [f for f in str(fact_raw).split(",") if f]
        return cls(
            chunk_id=str(hit.get("id") or ""),
            text=str(hit.get("document") or ""),
            corpus=meta.get("corpus", "general"),
            scheme_id=meta.get("scheme_id"),
            source_url=str(meta.get("source_url") or ""),
            source_title=str(meta.get("source_title") or ""),
            page_ref=meta.get("page_ref"),
            scraped_at=str(meta.get("scraped_at") or ""),
            fact_types=fact_types,
            similarity=float(similarity or 0.0),
            distance=float(distance) if distance is not None else None,
        )


@dataclass
class SchemeMatchResult:
    scheme_id: str | None
    scheme_name: str | None
    confidence: float
    matched: bool
    ambiguous: bool = False
    candidates: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class PIICheckResult:
    detected: bool
    refusal_message: str | None = None


@dataclass
class ClassificationResult:
    intent: Intent
    rules_hint: Intent | None = None
    rationale: str = ""


@dataclass(frozen=True)
class Citation:
    """Exact-page citation for a factual answer (FR-6)."""

    title: str
    url: str
    page_ref: str | None = None


@dataclass
class PipelineResult:
    """Orchestrator output — full Phase 4 response for all 8 taxonomy paths."""

    intent: Intent
    original_message: str
    short_circuit: bool = False
    short_circuit_reason: ShortCircuitReason | None = None
    scheme_id: str | None = None
    scheme_ids: list[str] = field(default_factory=list)
    scheme_match: SchemeMatchResult | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieval_empty: bool = False
    refusal_message: str | None = None
    supported_schemes: list[str] = field(default_factory=list)
    # Phase 3/4 — grounded / comparison answer
    answer_text: str | None = None
    citations: list[Citation] = field(default_factory=list)
    last_updated_from_sources: str | None = None
    insufficient_context: bool = False
    # Phase 4 — FR-8 distinct refusal line; FR-4 comparison rows
    refusal_appended: bool = False
    comparison_field: str | None = None
    comparison_rows: list[Any] = field(default_factory=list)
