"""EC-RET-01 readiness: metadata-filtered sample queries against Chroma."""

from __future__ import annotations

import sys

from src.ingestion.embed import embed_texts
from src.ingestion.store import VectorStore


def main() -> int:
    store = VectorStore()
    counts = store.counts()
    print("=== Collection counts ===")
    print(counts)
    print("Chunks by scheme:", store.counts_by_scheme())

    if counts["scheme"] == 0 or counts["general"] == 0:
        print("ERROR: collections must be non-empty. Run: python -m scripts.ingest", file=sys.stderr)
        return 1

    scheme_emb = embed_texts(["expense ratio of ICICI Flexicap"])[0]
    scheme_hits = store.sample_query(
        corpus="scheme",
        query_embedding=scheme_emb,
        scheme_id="icici_flexicap_dg",
        n_results=3,
    )
    print("\n=== Scheme filter (icici_flexicap_dg) ===")
    for hit in scheme_hits:
        meta = hit["metadata"] or {}
        print(meta.get("scheme_id"), meta.get("source_url"), meta.get("fact_types"))
        if meta.get("scheme_id") != "icici_flexicap_dg":
            print("EC-RET-01 FAIL: wrong scheme_id in results", file=sys.stderr)
            return 1
        if meta.get("corpus") != "scheme":
            print("EC-RET-01 FAIL: wrong corpus", file=sys.stderr)
            return 1

    general_emb = embed_texts(["what is an exit load"])[0]
    general_hits = store.sample_query(
        corpus="general",
        query_embedding=general_emb,
        n_results=3,
    )
    print("\n=== General corpus filter ===")
    for hit in general_hits:
        meta = hit["metadata"] or {}
        print(meta.get("corpus"), meta.get("source_url"))
        if meta.get("corpus") != "general":
            print("EC-RET-02 FAIL: scheme bleed into general", file=sys.stderr)
            return 1
        if meta.get("scheme_id"):
            print("EC-RET-02 FAIL: scheme_id present on general hit", file=sys.stderr)
            return 1

    print("\nEC-RET-01 / EC-RET-02 readiness OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
