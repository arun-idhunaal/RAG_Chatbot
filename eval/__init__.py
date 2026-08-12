"""Phase 6 eval harness — Sample Q&A + EDGECASES.md §12 suites with S0/S1 release gate."""

from eval.catalog import MINIMUM_SUITE, Severity, edge_case_by_id
from eval.report import EvalReport, ReleaseGate

__all__ = [
    "MINIMUM_SUITE",
    "Severity",
    "edge_case_by_id",
    "EvalReport",
    "ReleaseGate",
]
