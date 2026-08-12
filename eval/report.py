"""Eval pass/fail report mapped to EDGECASES.md IDs with S0/S1 release gate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

from eval.catalog import MINIMUM_SUITE, Severity, edge_case_by_id

IST = ZoneInfo("Asia/Kolkata")


class CaseStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    MISSING = "missing"  # no matching pytest coverage observed


@dataclass
class CaseResult:
    ec_id: str
    suite: str
    severity: str
    status: CaseStatus
    summary: str
    detail: str = ""
    nodeids: list[str] = field(default_factory=list)


@dataclass
class ReleaseGate:
    """EDGECASES.md §12 pass rule."""

    release_blocked: bool
    acceptance_blocked: bool
    s0_failures: list[str] = field(default_factory=list)
    s1_failures: list[str] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.release_blocked and not self.acceptance_blocked


@dataclass
class EvalReport:
    started_at: str
    finished_at: str
    cases: list[CaseResult]
    gate: ReleaseGate
    pytest_passed: int = 0
    pytest_failed: int = 0
    pytest_skipped: int = 0
    sample_qa_passed: int = 0
    sample_qa_failed: int = 0

    def summary(self) -> str:
        passed = sum(1 for c in self.cases if c.status == CaseStatus.PASS)
        failed = sum(1 for c in self.cases if c.status == CaseStatus.FAIL)
        missing = sum(1 for c in self.cases if c.status == CaseStatus.MISSING)
        lines = [
            "=== Phase 6 Eval Report (EDGECASES.md §12) ===",
            f"Started:  {self.started_at}",
            f"Finished: {self.finished_at}",
            f"Edge cases: pass={passed} fail={failed} missing={missing} total={len(self.cases)}",
            f"Pytest: pass={self.pytest_passed} fail={self.pytest_failed} skip={self.pytest_skipped}",
            f"Sample Q&A routing: pass={self.sample_qa_passed} fail={self.sample_qa_failed}",
            "",
            "Release gate:",
            f"  S0 failures (block release): {self.gate.s0_failures or 'none'}",
            f"  S1 failures (block PRD acceptance): {self.gate.s1_failures or 'none'}",
            f"  Missing coverage IDs: {self.gate.missing_ids or 'none'}",
            f"  Gate OK: {self.gate.ok}",
        ]
        if failed or missing:
            lines.append("")
            lines.append("Failed / missing detail:")
            for c in self.cases:
                if c.status in (CaseStatus.FAIL, CaseStatus.MISSING):
                    lines.append(f"  [{c.severity}] {c.ec_id} ({c.status}): {c.detail or c.summary}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "pytest_passed": self.pytest_passed,
            "pytest_failed": self.pytest_failed,
            "pytest_skipped": self.pytest_skipped,
            "sample_qa_passed": self.sample_qa_passed,
            "sample_qa_failed": self.sample_qa_failed,
            "gate": asdict(self.gate),
            "cases": [
                {
                    **{k: v for k, v in asdict(c).items() if k != "status"},
                    "status": c.status.value,
                }
                for c in self.cases
            ],
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        md_path = path.with_suffix(".md")
        md_path.write_text(self.summary() + "\n", encoding="utf-8")
        return path


def build_gate(cases: list[CaseResult]) -> ReleaseGate:
    """Any S0 fail → block release; any S1 fail → block PRD acceptance.

    Missing coverage of a required §12 ID is treated as a failure at that ID's severity.
    """
    s0: list[str] = []
    s1: list[str] = []
    missing: list[str] = []
    for c in cases:
        bad = c.status in (CaseStatus.FAIL, CaseStatus.MISSING)
        if c.status == CaseStatus.MISSING:
            missing.append(c.ec_id)
        if not bad:
            continue
        if c.severity == Severity.S0.value:
            s0.append(c.ec_id)
        elif c.severity == Severity.S1.value:
            s1.append(c.ec_id)
        # S2/S3 failures do not block release/acceptance gates
    return ReleaseGate(
        release_blocked=bool(s0),
        acceptance_blocked=bool(s0 or s1),
        s0_failures=s0,
        s1_failures=s1,
        missing_ids=missing,
    )


def map_pytest_to_cases(
    *,
    passed_nodeids: list[str],
    failed_nodeids: list[str],
    skipped_nodeids: list[str] | None = None,
) -> list[CaseResult]:
    """Map pytest nodeids onto EDGECASES §12 IDs via catalog test_patterns."""
    skipped_nodeids = skipped_nodeids or []
    all_seen = passed_nodeids + failed_nodeids + skipped_nodeids
    results: list[CaseResult] = []

    for spec in MINIMUM_SUITE:
        matched_pass = [n for n in passed_nodeids if _matches(n, spec.test_patterns)]
        matched_fail = [n for n in failed_nodeids if _matches(n, spec.test_patterns)]
        matched_skip = [n for n in skipped_nodeids if _matches(n, spec.test_patterns)]
        matched_any = [n for n in all_seen if _matches(n, spec.test_patterns)]

        if matched_fail:
            status = CaseStatus.FAIL
            detail = f"Failed tests: {', '.join(matched_fail[:5])}"
            nodeids = matched_fail
        elif matched_pass:
            status = CaseStatus.PASS
            detail = f"Covered by {len(matched_pass)} passing test(s)"
            nodeids = matched_pass
        elif matched_skip and not matched_any:
            status = CaseStatus.SKIP
            detail = "Only skipped tests matched"
            nodeids = matched_skip
        elif matched_skip:
            status = CaseStatus.SKIP
            detail = "Skipped"
            nodeids = matched_skip
        else:
            status = CaseStatus.MISSING
            detail = f"No pytest coverage matched patterns {spec.test_patterns}"
            nodeids = []

        results.append(
            CaseResult(
                ec_id=spec.ec_id,
                suite=spec.suite,
                severity=spec.severity.value,
                status=status,
                summary=spec.summary,
                detail=detail,
                nodeids=nodeids,
            )
        )
    return results


def _matches(nodeid: str, patterns: tuple[str, ...]) -> bool:
    low = nodeid.lower().replace("\\", "/")
    for p in patterns:
        if p.lower() in low:
            return True
    return False


def now_ist_iso() -> str:
    return datetime.now(tz=IST).isoformat()


def assert_known_ec(ec_id: str) -> None:
    if edge_case_by_id(ec_id) is None:
        raise KeyError(f"Unknown edge case ID: {ec_id}")
