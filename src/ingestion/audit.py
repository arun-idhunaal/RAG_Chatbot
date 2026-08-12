"""Scrape audit logging — url/status/chunk_count/scraped_at only (no PII)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.config.settings import Settings, get_settings
from src.ingestion.models import UrlAuditEntry

IST = ZoneInfo("Asia/Kolkata")


def write_audit_log(
    entries: list[UrlAuditEntry],
    *,
    settings: Settings | None = None,
    run_id: str | None = None,
) -> Path:
    settings = settings or get_settings()
    settings.audit_log_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or datetime.now(tz=IST).strftime("%Y%m%d_%H%M%S")
    path = settings.audit_log_dir / f"ingest_{run_id}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
    return path
