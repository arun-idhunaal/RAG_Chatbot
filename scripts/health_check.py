"""CLI: python -m scripts.health_check — post-ingest / cold-start health (EC-X-04)."""

from __future__ import annotations

import argparse
import sys

from src.ops.health import check_index_health


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Chroma index health.")
    parser.add_argument(
        "--allow-partial-schemes",
        action="store_true",
        help="Do not require all 5 scheme_ids to be present.",
    )
    parser.add_argument(
        "--skip-sample",
        action="store_true",
        help="Skip sample metadata peek.",
    )
    args = parser.parse_args(argv)

    status = check_index_health(
        require_all_schemes=not args.allow_partial_schemes,
        run_sample_query=not args.skip_sample,
    )
    print(status.summary())
    return 0 if status.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
