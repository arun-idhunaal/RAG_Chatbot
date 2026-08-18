"""Background ingest for Render (same process as the API — shared Chroma disk)."""

from __future__ import annotations

import threading
from typing import Any

from src.config.settings import Settings, get_settings
from src.ingestion.pipeline import run_ingest
from src.ops.health import check_index_health
from src.ops.metrics import record_scrape_from_ingest_report
from src.retrieval.retriever import Retriever

_lock = threading.Lock()
_running = False
_last_error: str | None = None


def ingest_status() -> dict[str, Any]:
    with _lock:
        return {"running": _running, "last_error": _last_error}


def try_start_ingest(app: Any, *, settings: Settings | None = None) -> bool:
    """Start ingest in a daemon thread if not already running. Returns True if started."""
    global _running
    settings = settings or get_settings()
    with _lock:
        if _running:
            return False
        _running = True

    thread = threading.Thread(
        target=_run_ingest,
        args=(app, settings),
        name="mf-ingest",
        daemon=True,
    )
    thread.start()
    return True


def _run_ingest(app: Any, settings: Settings) -> None:
    global _running, _last_error
    try:
        report = run_ingest(settings=settings, save_raw=False)
        record_scrape_from_ingest_report(report, settings=settings)
        check_index_health(settings=settings, run_sample_query=True)
        if getattr(app, "state", None) is not None:
            app.state.retriever = Retriever(settings=settings)
        _last_error = None
    except Exception as exc:  # noqa: BLE001 — background job must not crash the API
        _last_error = f"{type(exc).__name__}: {exc}"
    finally:
        with _lock:
            _running = False
