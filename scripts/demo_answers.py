"""CLI demo: Phase 3 grounded answers for Sample Q&A scheme + general questions."""

from __future__ import annotations

import argparse
import json
import sys

from src.pipeline.orchestrator import process_query

# ~5 scheme + ~5 general from SAMPLE_Q&A_RAGMFCHATBOT.md
SCHEME_DEMOS = [
    "What is the expense ratio of ICICI Prudential Flexicap Fund?",
    "What is the exit load for ICICI Prudential Midcap Fund?",
    "What is the minimum SIP amount for ICICI Prudential Large Cap Fund?",
    "Does ICICI Prudential ELSS Tax Saver Fund have a lock-in period?",
    "What benchmark does ICICI Prudential Nasdaq 100 Index Fund use?",
]

GENERAL_DEMOS = [
    "What is an expense ratio in a mutual fund?",
    "What is an exit load?",
    "What is a mutual fund riskometer?",
    "How can I download my mutual fund statement?",
    "What is the difference between SIP and lump-sum investment?",
]


def _print_result(query: str, result) -> None:
    print("=" * 72)
    print(f"Q: {query}")
    print(f"Intent: {result.intent.value}")
    if result.scheme_id:
        print(f"Scheme: {result.scheme_id}")
    print(f"Chunks: {len(result.chunks)} (empty={result.retrieval_empty})")
    if result.answer_text:
        print(f"A: {result.answer_text}")
    if result.citations:
        print("Citations:")
        for c in result.citations:
            ref = f" ({c.page_ref})" if c.page_ref else ""
            print(f"  - {c.title}{ref}: {c.url}")
    if result.last_updated_from_sources:
        print(f"Last updated from sources: {result.last_updated_from_sources}")
    if result.insufficient_context:
        print("(insufficient_context=True)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 grounded-answer demo")
    parser.add_argument("message", nargs="?", help="Single user message (optional)")
    parser.add_argument(
        "--suite",
        choices=("scheme", "general", "all"),
        default="all",
        help="Run Sample Q&A demo suite when no message given",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    if args.message:
        queries = [args.message]
    elif args.suite == "scheme":
        queries = SCHEME_DEMOS
    elif args.suite == "general":
        queries = GENERAL_DEMOS
    else:
        queries = SCHEME_DEMOS + GENERAL_DEMOS

    results = []
    for q in queries:
        result = process_query(q)
        if args.json:
            results.append(
                {
                    "query": q,
                    "intent": result.intent.value,
                    "scheme_id": result.scheme_id,
                    "answer_text": result.answer_text,
                    "citations": [
                        {"title": c.title, "url": c.url, "page_ref": c.page_ref}
                        for c in result.citations
                    ],
                    "last_updated_from_sources": result.last_updated_from_sources,
                    "insufficient_context": result.insufficient_context,
                    "chunk_count": len(result.chunks),
                }
            )
        else:
            _print_result(q, result)

    if args.json:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
