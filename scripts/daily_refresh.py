"""
Daily freshness entrypoint — 10:00 AM IST cron / GitHub Action (Phase 6).

python -m scripts.daily_refresh

Flow: full ingest → metrics → health check. Keeps last-good chunks on
single-URL failure (EC-ING-01). Cold-start empty index fails health (EC-X-04).
"""

from __future__ import annotations

import argparse
import sys

from src.config.settings import get_settings
from src.ingestion.pipeline import run_ingest
from src.ingestion.store import VectorStore
from src.ops.health import check_index_health
from src.ops.metrics import record_scrape_from_ingest_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Daily SOURCE_LIST scrape → re-embed changed → Chroma upsert + health."
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Scrape/clean/chunk only (debug).",
    )
    parser.add_argument(
        "--no-save-raw",
        action="store_true",
        help="Do not cache HTML under data/raw/.",
    )
    parser.add_argument(
        "--allow-partial-schemes",
        action="store_true",
        help="Health check does not require all 5 schemes.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    store = VectorStore(settings)

    print("=== Daily refresh: ingest ===")
    report = run_ingest(
        settings=settings,
        store=store,
        skip_embed=args.skip_embed,
        save_raw=not args.no_save_raw,
    )
    print(report.summary())
    record_scrape_from_ingest_report(report, settings=settings)

    print("\n=== Daily refresh: health check ===")
    health = check_index_health(
        settings=settings,
        store=store,
        require_all_schemes=not args.allow_partial_schemes,
        run_sample_query=True,
    )
    print(health.summary())

    # EC-ING-07: entire job failure still leaves prior index if it was healthy before;
    # we only exit non-zero when post-run health fails (EC-X-04 cold start / wipe).
    if not health.ok:
        print("ERROR: Post-ingest health check failed.", file=sys.stderr)
        return 1

    # Soft warn if many URLs failed but last-good kept the index healthy.
    if report.urls_failed and report.urls_ok == 0 and report.urls_unchanged == 0:
        print(
            "WARNING: No URLs succeeded this run; serving last-good index (EC-ING-01/07).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
