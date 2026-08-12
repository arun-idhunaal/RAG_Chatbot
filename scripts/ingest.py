"""CLI entrypoint: python -m scripts.ingest"""

from __future__ import annotations

import argparse
import sys

from src.config.settings import get_settings
from src.config.sources import all_sources
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest SOURCE_LIST URLs into Chroma (bge-m3)."
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Ingest a single SOURCE_LIST URL (repeatable).",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Scrape/clean/chunk only; do not embed or upsert.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print current collection counts without ingesting.",
    )
    parser.add_argument(
        "--no-save-raw",
        action="store_true",
        help="Do not cache raw HTML under data/raw/.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    store = VectorStore(settings)

    if args.report_only:
        counts = store.counts()
        by_scheme = store.counts_by_scheme()
        print("=== Chroma Report ===")
        print(f"scheme collection ({settings.scheme_collection}): {counts['scheme']}")
        print(f"general collection ({settings.general_collection}): {counts['general']}")
        print("Chunks by scheme_id:")
        for sid, n in sorted(by_scheme.items()):
            print(f"  {sid}: {n}")
        print(f"Configured SOURCE_LIST URLs: {len(all_sources())}")
        return 0

    report = run_ingest(
        urls=args.urls,
        settings=settings,
        store=store,
        skip_embed=args.skip_embed,
        save_raw=not args.no_save_raw,
    )
    print(report.summary())

    # Exit non-zero only if everything failed and both collections empty
    if report.scheme_chunks == 0 and report.general_chunks == 0 and report.urls_ok == 0:
        print("ERROR: Both collections empty after ingest.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
