"""Ingestion package: scrape → clean → chunk → embed → Chroma upsert."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ingestion.pipeline import IngestReport

__all__ = ["IngestReport", "run_ingest"]


def __getattr__(name: str):
    if name in {"IngestReport", "run_ingest"}:
        from src.ingestion import pipeline as _pipeline

        return getattr(_pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
