"""Run Phase 6 eval: pytest §12 suite + Sample Q&A routing checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eval.catalog import EVAL_TEST_PATHS
from eval.report import (
    CaseStatus,
    EvalReport,
    build_gate,
    map_pytest_to_cases,
    now_ist_iso,
)
from eval.sample_qa import SAMPLE_QA_CASES
from src.config.settings import Settings
from src.pipeline.intent_classifier import classify_intent

_REPO_ROOT = Path(__file__).resolve().parents[1]


def run_sample_qa_routing(*, use_llm: bool = False) -> tuple[int, int, list[str]]:
    """Happy-path intent routing from SAMPLE_Q&A (rules-only by default)."""
    settings = Settings(use_llm_classifier=use_llm, groq_api_key="")
    passed = failed = 0
    failures: list[str] = []
    for case in SAMPLE_QA_CASES:
        got = classify_intent(case.question, settings=settings).intent
        if got == case.expected_intent:
            passed += 1
        else:
            failed += 1
            failures.append(
                f"{case.case_id}: expected {case.expected_intent.value}, got {got.value}"
            )
    return passed, failed, failures


def run_pytest_suite(
    *,
    paths: tuple[str, ...] | None = None,
    extra_args: list[str] | None = None,
) -> tuple[list[str], list[str], list[str], int]:
    """
    Execute pytest and return (passed, failed, skipped nodeids, exit_code).
    Uses pytest --report-log style via JSON report plugin fallback to --collect + rerun.
    """
    paths = paths or EVAL_TEST_PATHS
    report_path = _REPO_ROOT / "data" / "eval" / "pytest_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "-q",
        "--tb=no",
        f"--junitxml={report_path.with_suffix('.xml')}",
    ]
    if extra_args:
        cmd.extend(extra_args)

    # Prefer pytest-json-report if available; otherwise parse junit via stdlib.
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    passed, failed, skipped = _parse_junit(report_path.with_suffix(".xml"))
    if not (passed or failed or skipped):
        # Fallback: scrape concise pytest output lines
        passed, failed, skipped = _parse_pytest_stdout(proc.stdout + "\n" + proc.stderr)
    return passed, failed, skipped, proc.returncode


def run_eval(
    *,
    include_sample_qa: bool = True,
    use_llm_sample: bool = False,
    report_dir: Path | None = None,
) -> EvalReport:
    started = now_ist_iso()
    passed_n, failed_n, skipped_n, _rc = run_pytest_suite()

    cases = map_pytest_to_cases(
        passed_nodeids=passed_n,
        failed_nodeids=failed_n,
        skipped_nodeids=skipped_n,
    )

    sq_pass = sq_fail = 0
    if include_sample_qa:
        sq_pass, sq_fail, sq_failures = run_sample_qa_routing(use_llm=use_llm_sample)
        if sq_fail:
            # Attach sample QA failures as detail on a synthetic note in report summary only;
            # they do not invent EC IDs, but block acceptance via gate helper below.
            for c in cases:
                if c.ec_id == "EC-INT-01" and sq_fail:
                    # Keep EC mapping intact; sample failures counted separately.
                    pass
            _ = sq_failures

    gate = build_gate(cases)
    # Sample Q&A routing failures block PRD acceptance (happy-path regression).
    if sq_fail:
        gate.acceptance_blocked = True

    finished = now_ist_iso()
    report = EvalReport(
        started_at=started,
        finished_at=finished,
        cases=cases,
        gate=gate,
        pytest_passed=len(passed_n),
        pytest_failed=len(failed_n),
        pytest_skipped=len(skipped_n),
        sample_qa_passed=sq_pass,
        sample_qa_failed=sq_fail,
    )

    out_dir = report_dir or (_REPO_ROOT / "data" / "eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = finished.replace(":", "").replace("+", "_")[:15]
    report.write(out_dir / f"eval_report_{stamp}.json")
    latest = out_dir / "latest_report.json"
    latest.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    (out_dir / "latest_report.md").write_text(report.summary() + "\n", encoding="utf-8")
    return report


def _parse_junit(path: Path) -> tuple[list[str], list[str], list[str]]:
    if not path.exists():
        return [], [], []
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    # junit may be <testsuites> or <testsuite>
    suites = root.findall("testsuite")
    if not suites and root.tag == "testsuite":
        suites = [root]
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    for suite in suites:
        for case in suite.findall("testcase"):
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "")
            # classname is like tests.test_ec_int — convert to path-ish nodeid
            file_part = classname.replace(".", "/") + ".py"
            nodeid = f"{file_part}::{name}"
            if case.find("failure") is not None or case.find("error") is not None:
                failed.append(nodeid)
            elif case.find("skipped") is not None:
                skipped.append(nodeid)
            else:
                passed.append(nodeid)
    return passed, failed, skipped


def _parse_pytest_stdout(text: str) -> tuple[list[str], list[str], list[str]]:
    """Best-effort fallback when junit is empty."""
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if " FAILED" in line or line.endswith("FAILED"):
            failed.append(line.split()[0])
        elif " PASSED" in line or line.endswith("PASSED"):
            passed.append(line.split()[0])
        elif " SKIPPED" in line:
            skipped.append(line.split()[0])
    return passed, failed, skipped


# Re-export for typing convenience
__all__ = ["run_eval", "run_sample_qa_routing", "run_pytest_suite", "CaseStatus"]
