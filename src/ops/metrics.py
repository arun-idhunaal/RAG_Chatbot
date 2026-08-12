"""Lightweight operational metrics — no PII (Architecture §12)."""

from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.config.settings import Settings, get_settings

IST = ZoneInfo("Asia/Kolkata")
_lock = threading.Lock()


@dataclass
class QueryMetricEvent:
    """Anonymized per-query counters — never includes message text."""

    ts: str
    intent: str
    empty_hit: bool = False
    citation_validation_failed: bool = False
    short_circuit: bool = False
    latency_ms: float | None = None


@dataclass
class ScrapeMetricSnapshot:
    ts: str
    urls_attempted: int
    urls_ok: int
    urls_failed: int
    urls_unchanged: int
    urls_empty: int
    urls_stale_kept: int
    scheme_chunks: int
    general_chunks: int
    success_rate: float


@dataclass
class MetricsSummary:
    intent_distribution: dict[str, int] = field(default_factory=dict)
    empty_hit_rate: float = 0.0
    citation_failure_rate: float = 0.0
    scrape_success_rate: float | None = None
    query_count: int = 0


class MetricsRecorder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.dir = Path(self.settings.metrics_log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.query_path = self.dir / "query_metrics.jsonl"
        self.scrape_path = self.dir / "scrape_metrics.jsonl"

    def record_query(self, event: QueryMetricEvent) -> None:
        _append_jsonl(self.query_path, asdict(event))

    def record_scrape(self, snap: ScrapeMetricSnapshot) -> None:
        _append_jsonl(self.scrape_path, asdict(snap))

    def summarize_queries(self, *, limit: int = 5000) -> MetricsSummary:
        events = _read_jsonl(self.query_path, limit=limit)
        if not events:
            return MetricsSummary()
        intents = Counter(e.get("intent") or "unknown" for e in events)
        n = len(events)
        empty = sum(1 for e in events if e.get("empty_hit"))
        cit_fail = sum(1 for e in events if e.get("citation_validation_failed"))
        scrapes = _read_jsonl(self.scrape_path, limit=100)
        scrape_rate = None
        if scrapes:
            scrape_rate = float(scrapes[-1].get("success_rate") or 0.0)
        return MetricsSummary(
            intent_distribution=dict(intents),
            empty_hit_rate=empty / n if n else 0.0,
            citation_failure_rate=cit_fail / n if n else 0.0,
            scrape_success_rate=scrape_rate,
            query_count=n,
        )


def record_query_metric(
    *,
    intent: str,
    empty_hit: bool = False,
    citation_validation_failed: bool = False,
    short_circuit: bool = False,
    latency_ms: float | None = None,
    settings: Settings | None = None,
) -> None:
    """Convenience wrapper — never pass user message text."""
    recorder = MetricsRecorder(settings)
    recorder.record_query(
        QueryMetricEvent(
            ts=datetime.now(tz=IST).isoformat(),
            intent=intent,
            empty_hit=empty_hit,
            citation_validation_failed=citation_validation_failed,
            short_circuit=short_circuit,
            latency_ms=latency_ms,
        )
    )


def record_scrape_from_ingest_report(report, *, settings: Settings | None = None) -> None:
    attempted = max(1, int(report.urls_attempted or 0))
    okish = int(report.urls_ok or 0) + int(report.urls_unchanged or 0)
    snap = ScrapeMetricSnapshot(
        ts=datetime.now(tz=IST).isoformat(),
        urls_attempted=report.urls_attempted,
        urls_ok=report.urls_ok,
        urls_failed=report.urls_failed,
        urls_unchanged=report.urls_unchanged,
        urls_empty=report.urls_empty,
        urls_stale_kept=report.urls_stale_kept,
        scheme_chunks=report.scheme_chunks,
        general_chunks=report.general_chunks,
        success_rate=okish / attempted,
    )
    MetricsRecorder(settings).record_scrape(snap)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, *, limit: int) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]
