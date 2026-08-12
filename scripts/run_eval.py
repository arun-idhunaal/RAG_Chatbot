"""CLI: python -m scripts.run_eval — Phase 6 edge-case + Sample Q&A harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval.runner import run_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run EDGECASES.md §12 eval harness with S0/S1 release gate."
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory for JSON/MD reports (default: data/eval).",
    )
    parser.add_argument(
        "--skip-sample-qa",
        action="store_true",
        help="Skip SAMPLE_Q&A routing checks.",
    )
    parser.add_argument(
        "--use-llm-sample",
        action="store_true",
        help="Use LLM classifier for Sample Q&A (requires GROQ_API_KEY).",
    )
    args = parser.parse_args(argv)

    report = run_eval(
        include_sample_qa=not args.skip_sample_qa,
        use_llm_sample=args.use_llm_sample,
        report_dir=args.report_dir,
    )
    print(report.summary())

    if report.gate.release_blocked:
        print("\nRELEASE BLOCKED: S0 edge-case failure(s).", file=sys.stderr)
        return 2
    if report.gate.acceptance_blocked:
        print("\nPRD ACCEPTANCE BLOCKED: S1 failure(s) or Sample Q&A regressions.", file=sys.stderr)
        return 1
    print("\nGate OK — no open S0/S1 failures in §12 suite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
