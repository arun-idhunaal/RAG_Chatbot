"""Corpus-isolated vector retrieval with similarity floor and keyword boost (FR-3)."""

from __future__ import annotations

import re
from typing import Any, Literal

from src.config.fact_types import FACT_TYPE_PATTERNS
from src.config.schemes import all_scheme_ids
from src.config.settings import Settings, get_settings
from src.ingestion.embed import embed_texts
from src.ingestion.store import VectorStore
from src.pipeline.models import RetrievedChunk

# Field-label keywords for optional re-ranking boost.
_FIELD_LABEL_BOOSTS: dict[str, tuple[str, ...]] = {
    "expense_ratio": ("expense ratio", "total expense ratio", "ter"),
    "exit_load": ("exit load", "redemption load"),
    "min_sip": ("minimum sip", "min sip", "minimum investment"),
    "lock_in": ("lock-in", "lock in", "lockin"),
    "riskometer": ("riskometer", "risk-o-meter", "risk level"),
    "benchmark": ("benchmark", "benchmark index"),
    "statement_download": ("download statement", "account statement", "capital gain"),
}


class Retriever:
    """Dual-corpus retriever — never blends scheme and general in one call."""

    def __init__(
        self,
        store: VectorStore | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.store = store or VectorStore(self.settings)

    def retrieve_scheme(
        self,
        query: str,
        scheme_id: str,
        *,
        fact_type: str | None = None,
    ) -> list[RetrievedChunk]:
        """EC-RET-01: corpus=scheme AND scheme_id filter only."""
        fact_type = fact_type or infer_fact_type(query)
        hits = self._query(
            corpus="scheme",
            query=query,
            scheme_id=scheme_id,
            fact_type=fact_type,
        )
        return self._to_chunks(hits, expected_corpus="scheme", expected_scheme_id=scheme_id)

    def retrieve_general(self, query: str) -> list[RetrievedChunk]:
        """EC-RET-02: corpus=general only."""
        hits = self._query(corpus="general", query=query)
        return self._to_chunks(hits, expected_corpus="general", expected_scheme_id=None)

    def retrieve_cross_scheme(
        self,
        query: str,
        *,
        fact_type: str | None = None,
    ) -> list[RetrievedChunk]:
        """Per-scheme isolated retrieval for all 5 schemes (FR-4 prep)."""
        fact_type = fact_type or infer_fact_type(query)
        all_chunks: list[RetrievedChunk] = []
        for scheme_id in all_scheme_ids():
            chunks = self.retrieve_scheme(query, scheme_id, fact_type=fact_type)
            all_chunks.extend(chunks)
        return all_chunks

    def _query(
        self,
        *,
        corpus: Literal["scheme", "general"],
        query: str,
        scheme_id: str | None = None,
        fact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        embedding = embed_texts([query], settings=self.settings)[0]
        col = self.store.collection_for(corpus)
        where: dict[str, Any] | None = None
        if corpus == "scheme" and scheme_id:
            where = {"scheme_id": scheme_id}

        n_results = self.settings.retrieval_top_k
        result = col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]

        for i, chunk_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            if meta.get("out_of_scope"):
                continue
            distance = dists[i] if i < len(dists) else None
            similarity = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
            if similarity < self.settings.retrieval_min_similarity:
                continue
            doc = docs[i] if i < len(docs) else ""
            boost = _keyword_boost(query, doc, meta, fact_type)
            hits.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": distance,
                    "similarity": similarity + boost,
                }
            )

        hits.sort(key=lambda h: h.get("similarity", 0.0), reverse=True)
        return hits[:n_results]

    def _to_chunks(
        self,
        hits: list[dict[str, Any]],
        *,
        expected_corpus: str,
        expected_scheme_id: str | None,
    ) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        for hit in hits:
            chunk = RetrievedChunk.from_store_hit(hit)
            if chunk.corpus != expected_corpus:
                continue
            if expected_scheme_id and chunk.scheme_id != expected_scheme_id:
                continue
            chunks.append(chunk)
        return chunks


def infer_fact_type(query: str) -> str | None:
    """Map query text to an in-scope fact_type tag when possible."""
    lower = query.lower()
    for fact_type, patterns in FACT_TYPE_PATTERNS.items():
        if any(p in lower for p in patterns):
            return fact_type
    for fact_type, labels in _FIELD_LABEL_BOOSTS.items():
        if any(label in lower for label in labels):
            return fact_type
    return None


def _keyword_boost(
    query: str,
    document: str,
    metadata: dict[str, Any],
    fact_type: str | None,
) -> float:
    """Small re-rank boost when field labels align with query / chunk metadata."""
    boost = 0.0
    lower_q = query.lower()
    lower_doc = (document or "").lower()
    fact_types_raw = str(metadata.get("fact_types") or "")
    chunk_facts = {f.strip() for f in fact_types_raw.split(",") if f.strip()}

    targets: set[str] = set()
    if fact_type:
        targets.add(fact_type)
    for ft, labels in _FIELD_LABEL_BOOSTS.items():
        if any(label in lower_q for label in labels):
            targets.add(ft)

    for ft in targets:
        labels = _FIELD_LABEL_BOOSTS.get(ft, FACT_TYPE_PATTERNS.get(ft, ()))
        if ft in chunk_facts:
            boost += 0.08
        if any(label in lower_doc for label in labels):
            boost += 0.05
    return min(boost, 0.15)
