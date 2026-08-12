"""Ops package — health checks and lightweight metrics (Architecture §12)."""

from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE, HealthStatus, check_index_health
from src.ops.metrics import MetricsRecorder, record_query_metric

__all__ = [
    "CORPUS_UNAVAILABLE_MESSAGE",
    "HealthStatus",
    "check_index_health",
    "MetricsRecorder",
    "record_query_metric",
]
