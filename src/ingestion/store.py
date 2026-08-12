"""Chroma persistence with dual collections and upsert-by-content_hash."""

from __future__ import annotations

from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from src.config.settings import Settings, get_settings
from src.ingestion.embed import EmbeddingError, embed_texts
from src.ingestion.models import ChunkRecord


class VectorStore:
    """Two isolated Chroma collections: scheme vs general."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.settings.chroma_persist_dir)
        )
        self.scheme = self._client.get_or_create_collection(
            name=self.settings.scheme_collection,
            metadata={"hnsw:space": "cosine", "embedding_model": "BAAI/bge-m3"},
        )
        self.general = self._client.get_or_create_collection(
            name=self.settings.general_collection,
            metadata={"hnsw:space": "cosine", "embedding_model": "BAAI/bge-m3"},
        )

    def collection_for(self, corpus: str) -> Collection:
        if corpus == "scheme":
            return self.scheme
        if corpus == "general":
            return self.general
        raise ValueError(f"Unknown corpus: {corpus}")

    def existing_content_hash(self, corpus: str, source_url: str) -> str | None:
        col = self.collection_for(corpus)
        try:
            result = col.get(
                where={"source_url": source_url},
                include=["metadatas"],
                limit=1,
            )
        except Exception:  # noqa: BLE001 — empty / missing
            return None
        metadatas = result.get("metadatas") or []
        if not metadatas:
            return None
        return metadatas[0].get("content_hash")

    def count_for_url(self, corpus: str, source_url: str) -> int:
        col = self.collection_for(corpus)
        try:
            result = col.get(where={"source_url": source_url}, include=[])
            return len(result.get("ids") or [])
        except Exception:  # noqa: BLE001
            return 0

    def delete_url(self, corpus: str, source_url: str) -> int:
        """Delete chunks for a URL. Used only when replacing with a valid new extract."""
        col = self.collection_for(corpus)
        result = col.get(where={"source_url": source_url}, include=[])
        ids = result.get("ids") or []
        if ids:
            col.delete(ids=ids)
        return len(ids)

    def upsert_chunks(
        self,
        chunks: list[ChunkRecord],
        *,
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Replace prior chunks for the URL(s) then upsert. Caller ensures valid extract."""
        if not chunks:
            return 0
        if embeddings is None:
            embeddings = embed_texts([c.text for c in chunks], settings=self.settings)
        if len(embeddings) != len(chunks):
            raise EmbeddingError("Embedding count mismatch; aborting upsert (EC-ING-03).")

        # Group by (corpus, url) so we delete once per URL.
        by_key: dict[tuple[str, str], list[int]] = {}
        for i, chunk in enumerate(chunks):
            by_key.setdefault((chunk.corpus, chunk.source_url), []).append(i)

        for (corpus, url), indices in by_key.items():
            self.delete_url(corpus, url)
            subset = [chunks[i] for i in indices]
            vectors = [embeddings[i] for i in indices]
            col = self.collection_for(corpus)
            col.upsert(
                ids=[c.chunk_id for c in subset],
                embeddings=vectors,
                documents=[c.text for c in subset],
                metadatas=[_to_metadata(c) for c in subset],
            )
        return len(chunks)

    def counts(self) -> dict[str, int]:
        return {
            "scheme": self.scheme.count(),
            "general": self.general.count(),
        }

    def counts_by_scheme(self) -> dict[str, int]:
        result = self.scheme.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in result.get("metadatas") or []:
            sid = meta.get("scheme_id") or "unknown"
            counts[sid] = counts.get(sid, 0) + 1
        return counts

    def sample_query(
        self,
        *,
        corpus: str,
        query_embedding: list[float],
        scheme_id: str | None = None,
        n_results: int = 3,
    ) -> list[dict[str, Any]]:
        """Metadata-filtered query for readiness checks (EC-RET-01)."""
        col = self.collection_for(corpus)
        where: dict[str, Any] | None = None
        if corpus == "scheme" and scheme_id:
            where = {"scheme_id": scheme_id}
        result = col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, chunk_id in enumerate(ids):
            out.append(
                {
                    "id": chunk_id,
                    "document": docs[i] if i < len(docs) else None,
                    "metadata": metas[i] if i < len(metas) else None,
                    "distance": dists[i] if i < len(dists) else None,
                }
            )
        return out


def _to_metadata(chunk: ChunkRecord) -> dict[str, Any]:
    # Chroma metadata values must be str|int|float|bool
    meta: dict[str, Any] = {
        "corpus": chunk.corpus,
        "source_url": chunk.source_url,
        "source_title": chunk.source_title,
        "scraped_at": chunk.scraped_at,
        "content_hash": chunk.content_hash,
        "fact_types": ",".join(chunk.fact_types),
        "out_of_scope": chunk.out_of_scope,
    }
    if chunk.scheme_id:
        meta["scheme_id"] = chunk.scheme_id
    if chunk.page_ref:
        meta["page_ref"] = chunk.page_ref
    return meta
