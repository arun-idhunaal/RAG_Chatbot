"""CLI walkthrough: Sample Q&A sections 1–4 (Phase 4 — all intent paths)."""

from __future__ import annotations

import argparse
import json
import sys

from src.pipeline.orchestrator import process_query

# Sample Q&A §1–4 (concrete schemes substituted for templates)
SECTION_1_SCHEME = [
    "What is the expense ratio of ICICI Prudential Flexicap Fund?",
    "What is the exit load for ICICI Prudential Midcap Fund?",
    "What is the minimum SIP amount for ICICI Prudential Large Cap Fund?",
    "Does ICICI Prudential ELSS Tax Saver Fund have a lock-in period?",
    "What benchmark does ICICI Prudential Nasdaq 100 Index Fund use?",
]

SECTION_2_GENERAL = [
    "What is an expense ratio in a mutual fund?",
    "What is an exit load?",
    "What is a mutual fund riskometer?",
    "How can I download my mutual fund statement?",
    "What is the difference between SIP and lump-sum investment?",
]

SECTION_3_ADVISORY = [
    "Which mutual fund is best for me?",
    "Should I invest in a small-cap fund now?",
    "Which of these funds should I choose for my portfolio?",
    "Do you think ICICI Prudential Flexicap Fund will outperform its benchmark?",
    "Is this a good time to start an SIP in an equity mutual fund?",
]

SECTION_4_MIXED = [
    "What is the expense ratio of ICICI Prudential Flexicap Fund, and is it a good fund to invest in?",
    "What is the exit load of ICICI Prudential Midcap Fund, and should I avoid this fund because of it?",
    "What benchmark does ICICI Prudential Large Cap Fund follow, and do you think it can beat the benchmark?",
    "What is the minimum SIP for ICICI Prudential Nasdaq 100 Index Fund, and would you recommend starting with that amount?",
    "Does ICICI Prudential ELSS Tax Saver Fund have a lock-in, and is it suitable for a 2-year investment?",
]

# Extra Phase 4 paths beyond Sample Q&A §1–4
SECTION_EXTRA = [
    "Which of these 5 has the lowest expense ratio?",
    "Expense ratio of HDFC Flexicap?",
    "1Y return of ICICI Midcap?",
    "Lowest expense ratio among these 5, so which should I pick?",
]


SUITES = {
    "1": ("scheme_specific", SECTION_1_SCHEME),
    "2": ("general", SECTION_2_GENERAL),
    "3": ("advisory", SECTION_3_ADVISORY),
    "4": ("mixed", SECTION_4_MIXED),
    "extra": ("comparisons_guardrails", SECTION_EXTRA),
    "all": (
        "all",
        SECTION_1_SCHEME + SECTION_2_GENERAL + SECTION_3_ADVISORY + SECTION_4_MIXED + SECTION_EXTRA,
    ),
}


def _print_result(query: str, result) -> None:
    print("=" * 72)
    print(f"Q: {query}")
    print(f"Intent: {result.intent.value}")
    if result.short_circuit:
        print(f"Short-circuit: {result.short_circuit_reason}")
    if result.scheme_id:
        print(f"Scheme: {result.scheme_id}")
    if result.comparison_field:
        print(f"Comparison field: {result.comparison_field}")
    if result.answer_text:
        print(f"A:\n{result.answer_text}")
    if result.refusal_appended:
        print("(refusal_appended=True)")
    if result.citations:
        print("Citations:")
        for c in result.citations:
            print(f"  - {c.title}: {c.url}")
    if result.last_updated_from_sources:
        print(f"Last updated from sources: {result.last_updated_from_sources}")
    if result.supported_schemes:
        print("Supported schemes listed:", len(result.supported_schemes))
    print()


def _to_json(query: str, result) -> dict:
    return {
        "query": query,
        "intent": result.intent.value,
        "short_circuit": result.short_circuit,
        "short_circuit_reason": result.short_circuit_reason,
        "scheme_id": result.scheme_id,
        "answer_text": result.answer_text,
        "refusal_appended": result.refusal_appended,
        "refusal_message": result.refusal_message,
        "citations": [
            {"title": c.title, "url": c.url, "page_ref": c.page_ref}
            for c in result.citations
        ],
        "last_updated_from_sources": result.last_updated_from_sources,
        "insufficient_context": result.insufficient_context,
        "comparison_field": result.comparison_field,
        "supported_schemes": result.supported_schemes or None,
        "chunk_count": len(result.chunks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 CLI walkthrough — Sample Q&A sections 1–4 + guardrails"
    )
    parser.add_argument("message", nargs="?", help="Single user message (optional)")
    parser.add_argument(
        "--suite",
        choices=("1", "2", "3", "4", "extra", "all"),
        default="all",
        help="Sample Q&A section (1=scheme, 2=general, 3=advisory, 4=mixed)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    if args.message:
        queries = [args.message]
    else:
        _, queries = SUITES[args.suite]

    results = []
    for q in queries:
        result = process_query(q)
        if args.json:
            results.append(_to_json(q, result))
        else:
            _print_result(q, result)

    if args.json:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
