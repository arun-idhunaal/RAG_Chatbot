"""CLI: run a query through the pipeline (Phase 3: grounded answers for factual intents)."""

from __future__ import annotations

import argparse
import json
import sys

from src.pipeline.orchestrator import process_query


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Route a query through PII → intent → retrieval → answer"
    )
    parser.add_argument("message", nargs="?", help="User message")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        return 1

    result = process_query(args.message)

    if args.json:
        payload = {
            "intent": result.intent.value,
            "short_circuit": result.short_circuit,
            "short_circuit_reason": result.short_circuit_reason,
            "scheme_id": result.scheme_id,
            "scheme_ids": result.scheme_ids,
            "retrieval_empty": result.retrieval_empty,
            "chunk_count": len(result.chunks),
            "answer_text": result.answer_text,
            "refusal_appended": result.refusal_appended,
            "citations": [
                {"title": c.title, "url": c.url, "page_ref": c.page_ref}
                for c in result.citations
            ],
            "last_updated_from_sources": result.last_updated_from_sources,
            "insufficient_context": result.insufficient_context,
            "comparison_field": result.comparison_field,
            "chunks": [
                {
                    "scheme_id": c.scheme_id,
                    "corpus": c.corpus,
                    "source_url": c.source_url,
                    "similarity": round(c.similarity, 3),
                }
                for c in result.chunks
            ],
            "supported_schemes": result.supported_schemes or None,
            "refusal_message": result.refusal_message,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Intent: {result.intent.value}")
    if result.short_circuit:
        print(f"Short-circuit: {result.short_circuit_reason}")
        if result.answer_text:
            print(f"Answer:\n{result.answer_text}")
        elif result.refusal_message:
            print(f"Refusal: {result.refusal_message}")
        if result.supported_schemes:
            print("Supported schemes:")
            for name in result.supported_schemes:
                print(f"  - {name}")
        return 0

    if result.scheme_id:
        print(f"Scheme: {result.scheme_id}")
    if result.comparison_field:
        print(f"Comparison field: {result.comparison_field}")
    print(f"Chunks retrieved: {len(result.chunks)}")
    for i, c in enumerate(result.chunks[:5], 1):
        print(f"  [{i}] {c.corpus} | {c.scheme_id or '-'} | sim={c.similarity:.3f} | {c.source_url}")
    if result.answer_text:
        print(f"\nAnswer:\n{result.answer_text}")
        if result.refusal_appended:
            print("(refusal appended)")
        if result.citations:
            print("Citations:")
            for c in result.citations:
                print(f"  - {c.url}")
    elif result.retrieval_empty:
        print("Note: retrieval empty — fail closed (EC-RET-04)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
