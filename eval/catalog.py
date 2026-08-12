"""EDGECASES.md §12 minimum suite catalog with S0/S1 severity (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    S0 = "S0"  # Compliance / safety — blocks release
    S1 = "S1"  # Core PRD defect — blocks PRD acceptance
    S2 = "S2"
    S3 = "S3"


@dataclass(frozen=True)
class EdgeCaseSpec:
    ec_id: str
    suite: str
    severity: Severity
    summary: str
    # pytest nodeid substrings / file patterns that cover this ID
    test_patterns: tuple[str, ...]


# Severity sourced from EDGECASES.md tables (highest severity when multiple apply).
MINIMUM_SUITE: tuple[EdgeCaseSpec, ...] = (
    # Intent routing — EC-INT-01…08, EC-INT-12
    EdgeCaseSpec("EC-INT-01", "intent", Severity.S0, "Factual+opinion → mixed", ("EC-INT-01", "test_ec_int")),
    EdgeCaseSpec("EC-INT-02", "intent", Severity.S0, "Pure advisory → FR-7", ("EC-INT-02", "test_ec_int")),
    EdgeCaseSpec("EC-INT-03", "intent", Severity.S0, "Performance → out_of_corpus", ("EC-INT-03", "test_ec_int")),
    EdgeCaseSpec("EC-INT-04", "intent", Severity.S1, "Unsupported AMC → FR-9", ("EC-INT-04", "test_ec_int")),
    EdgeCaseSpec("EC-INT-05", "intent", Severity.S1, "Allowed field comparison → FR-4", ("EC-INT-05", "test_ec_int")),
    EdgeCaseSpec("EC-INT-06", "intent", Severity.S0, "Advice-framed comparison → FR-7", ("EC-INT-06", "test_ec_int")),
    EdgeCaseSpec("EC-INT-07", "intent", Severity.S1, "General definition → general_factual", ("EC-INT-07", "test_ec_int")),
    EdgeCaseSpec("EC-INT-08", "intent", Severity.S1, "Informal alias scheme fact", ("EC-INT-08", "test_ec_int")),
    EdgeCaseSpec("EC-INT-12", "intent", Severity.S0, "Compare performance ≠ FR-4", ("EC-INT-12", "test_ec_int")),
    # Scheme match — EC-SCH-01…06
    EdgeCaseSpec("EC-SCH-01", "scheme", Severity.S1, "Informal alias maps correctly", ("EC-SCH-01", "test_ec_sch")),
    EdgeCaseSpec("EC-SCH-02", "scheme", Severity.S1, "Ambiguous → no guess", ("EC-SCH-02", "test_ec_sch")),
    EdgeCaseSpec("EC-SCH-03", "scheme", Severity.S1, "Low-confidence → FR-9", ("EC-SCH-03", "test_ec_sch")),
    EdgeCaseSpec("EC-SCH-04", "scheme", Severity.S1, "Wrong plan variant not covered", ("EC-SCH-04", "test_ec_sch")),
    EdgeCaseSpec("EC-SCH-05", "scheme", Severity.S1, "Typo below threshold → FR-9", ("EC-SCH-05", "test_ec_sch")),
    EdgeCaseSpec("EC-SCH-06", "scheme", Severity.S1, "Generic AMC only → no default", ("EC-SCH-06", "test_ec_sch")),
    # Retrieval isolation — EC-RET-01…04
    EdgeCaseSpec("EC-RET-01", "retrieval", Severity.S1, "Scheme filter isolation", ("EC-RET-01", "test_ec_ret")),
    EdgeCaseSpec("EC-RET-02", "retrieval", Severity.S1, "General corpus only", ("EC-RET-02", "test_ec_ret")),
    EdgeCaseSpec("EC-RET-03", "retrieval", Severity.S1, "No related-fund contamination", ("EC-ING-06", "test_ec_ing_06")),
    EdgeCaseSpec("EC-RET-04", "retrieval", Severity.S1, "Empty retrieval fail-closed", ("EC-RET-04", "test_ec_ret", "test_ec_ans_cit")),
    # Citations — EC-CIT-01…05, EC-ANS-03…04
    EdgeCaseSpec("EC-CIT-01", "citations", Severity.S1, "Domain-only citation rejected", ("EC-CIT-01", "test_ec_ans_cit")),
    EdgeCaseSpec("EC-CIT-02", "citations", Severity.S0, "Wrong-scheme citation rejected", ("EC-CIT-02", "test_ec_ans_cit")),
    EdgeCaseSpec("EC-CIT-03", "citations", Severity.S1, "URL not in retrieved set", ("EC-CIT-03", "test_ec_ans_cit")),
    EdgeCaseSpec("EC-CIT-04", "citations", Severity.S1, "Date from cited scraped_at", ("EC-CIT-04", "test_ec_ans_cit")),
    EdgeCaseSpec("EC-CIT-05", "citations", Severity.S1, "Per-scheme comparison citations", ("EC-CIT-05", "test_ec_cmp")),
    EdgeCaseSpec("EC-ANS-03", "citations", Severity.S0, "No uncited extra facts", ("EC-ANS-03", "test_ec_ans_cit")),
    EdgeCaseSpec("EC-ANS-04", "citations", Severity.S1, "Insufficient context fail-closed", ("EC-ANS-04", "test_ec_ans_cit")),
    # Comparisons — EC-CMP-01…06
    EdgeCaseSpec("EC-CMP-01", "comparison", Severity.S1, "Allowed field + per-scheme cites", ("EC-CMP-01", "test_ec_cmp")),
    EdgeCaseSpec("EC-CMP-02", "comparison", Severity.S1, "Bare ranking shows all values", ("EC-CMP-02", "test_ec_cmp")),
    EdgeCaseSpec("EC-CMP-03", "comparison", Severity.S0, "Returns comparison not FR-4", ("EC-CMP-03", "test_ec_cmp")),
    EdgeCaseSpec("EC-CMP-04", "comparison", Severity.S0, "Which is better → advisory", ("EC-CMP-04", "test_ec_cmp")),
    EdgeCaseSpec("EC-CMP-05", "comparison", Severity.S1, "Missing extract → unavailable", ("EC-CMP-05", "test_ec_cmp")),
    EdgeCaseSpec("EC-CMP-06", "comparison", Severity.S0, "No better-choice language", ("EC-CMP-06", "test_ec_cmp")),
    # Advisory / mixed — EC-ADV-01…03, EC-MIX-01…03
    EdgeCaseSpec("EC-ADV-01", "advisory_mixed", Severity.S0, "Best/should/recommend refused", ("EC-ADV-01", "test_ec_adv_mix")),
    EdgeCaseSpec("EC-ADV-02", "advisory_mixed", Severity.S2, "No echo of advisory framing", ("EC-ADV-02", "test_ec_adv_mix")),
    EdgeCaseSpec("EC-ADV-03", "advisory_mixed", Severity.S0, "Soft suitability → FR-7", ("EC-ADV-03", "test_ec_adv_mix")),
    EdgeCaseSpec("EC-MIX-01", "advisory_mixed", Severity.S0, "Fact then separate refusal", ("EC-MIX-01", "test_ec_adv_mix")),
    EdgeCaseSpec("EC-MIX-02", "advisory_mixed", Severity.S1, "Fact/refusal not blended", ("EC-MIX-02", "test_ec_adv_mix")),
    EdgeCaseSpec("EC-MIX-03", "advisory_mixed", Severity.S0, "OOC fact + advice", ("EC-MIX-03", "test_ec_adv_mix")),
    # FR-9 vs FR-10 — EC-UNS-01…04, EC-OOC-01…04
    EdgeCaseSpec("EC-UNS-01", "fr9_fr10", Severity.S1, "Other AMC lists exactly 5", ("EC-UNS-01", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-UNS-02", "fr9_fr10", Severity.S1, "Other ICICI scheme → FR-9", ("EC-UNS-02", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-UNS-03", "fr9_fr10", Severity.S0, "No uncited knowledge", ("EC-UNS-03", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-UNS-04", "fr9_fr10", Severity.S1, "Failed match → FR-9 list", ("EC-UNS-04", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-OOC-01", "fr9_fr10", Severity.S0, "Returns on supported → FR-10", ("EC-OOC-01", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-OOC-02", "fr9_fr10", Severity.S0, "Predict outperform refused", ("EC-OOC-02", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-OOC-03", "fr9_fr10", Severity.S0, "Approximate returns refused", ("EC-OOC-03", "test_ec_uns_ooc")),
    EdgeCaseSpec("EC-OOC-04", "fr9_fr10", Severity.S1, "Unsupported+returns prefers FR-9", ("EC-OOC-04", "test_ec_uns_ooc")),
    # PII — EC-PII-01…04
    EdgeCaseSpec("EC-PII-01", "pii", Severity.S0, "PII alone full refuse", ("EC-PII-01", "test_ec_pii")),
    EdgeCaseSpec("EC-PII-02", "pii", Severity.S0, "PII+fact refuses entire message", ("EC-PII-02", "test_ec_pii")),
    EdgeCaseSpec("EC-PII-03", "pii", Severity.S0, "Never echo/partial echo PII", ("EC-PII-03", "test_ec_pii")),
    EdgeCaseSpec("EC-PII-04", "pii", Severity.S0, "No raw PII in pipeline logs", ("EC-PII-04", "test_ec_pii")),
    # UI (manual OK) — EC-UI-01…04
    EdgeCaseSpec("EC-UI-01", "ui", Severity.S1, "Welcome + 3 examples", ("EC-UI-01", "test_ec_ui")),
    EdgeCaseSpec("EC-UI-02", "ui", Severity.S1, "Persistent disclaimer", ("EC-UI-02", "test_ec_ui")),
    EdgeCaseSpec("EC-UI-03", "ui", Severity.S1, "Citation link + inline date", ("EC-UI-03", "test_ec_ui")),
    EdgeCaseSpec("EC-UI-04", "ui", Severity.S1, "Mixed fact/refusal distinct", ("EC-UI-04", "test_ec_ui")),
    # Ingest (ops) — EC-ING-01…06
    EdgeCaseSpec("EC-ING-01", "ingest", Severity.S3, "Single URL fail keeps last-good", ("EC-ING-01", "test_ec_ing_01")),
    EdgeCaseSpec("EC-ING-02", "ingest", Severity.S3, "Empty extract keeps prior", ("EC-ING-02", "test_ec_ing_02")),
    EdgeCaseSpec("EC-ING-03", "ingest", Severity.S3, "Embed failure preserves index", ("EC-ING-03", "test_ec_ing_03")),
    EdgeCaseSpec("EC-ING-04", "ingest", Severity.S3, "Unchanged hash idempotent", ("EC-ING-04", "test_ec_ing_04")),
    EdgeCaseSpec("EC-ING-05", "ingest", Severity.S0, "Performance tagged out_of_scope", ("EC-ING-05", "test_ec_ing_05")),
    EdgeCaseSpec("EC-ING-06", "ingest", Severity.S1, "No cross-scheme contamination", ("EC-ING-06", "test_ec_ing_06")),
    # Compound — EC-X-01…03 (+ EC-X-04 health)
    EdgeCaseSpec("EC-X-01", "compound", Severity.S0, "PII gate wins first", ("EC-X-01", "test_ec_x", "test_ec_pii")),
    EdgeCaseSpec("EC-X-02", "compound", Severity.S0, "Comparison+advice never picks", ("EC-X-02", "test_ec_x")),
    EdgeCaseSpec("EC-X-03", "compound", Severity.S0, "Lock-in fact + suitability refusal", ("EC-X-03", "test_ec_x")),
    EdgeCaseSpec("EC-X-04", "compound", Severity.S1, "Empty Chroma fail closed", ("EC-X-04", "test_ec_x", "test_ops_health")),
)


def edge_case_by_id(ec_id: str) -> EdgeCaseSpec | None:
    for spec in MINIMUM_SUITE:
        if spec.ec_id == ec_id:
            return spec
    return None


def suite_names() -> list[str]:
    return sorted({s.suite for s in MINIMUM_SUITE})


def required_ids() -> list[str]:
    return [s.ec_id for s in MINIMUM_SUITE]


# Pytest paths that collectively cover the §12 minimum suite.
EVAL_TEST_PATHS: tuple[str, ...] = (
    "tests/test_ec_int.py",
    "tests/test_ec_sch.py",
    "tests/test_ec_ret.py",
    "tests/test_ec_ans_cit.py",
    "tests/test_ec_cmp.py",
    "tests/test_ec_adv_mix.py",
    "tests/test_ec_uns_ooc.py",
    "tests/test_ec_pii.py",
    "tests/test_ec_ui.py",
    "tests/test_ec_ing_01.py",
    "tests/test_ec_ing_02.py",
    "tests/test_ec_ing_03.py",
    "tests/test_ec_ing_04.py",
    "tests/test_ec_ing_05.py",
    "tests/test_ec_ing_06.py",
    "tests/test_ec_x.py",
    "tests/test_ops_health.py",
    "tests/test_sample_qa_routing.py",
)
