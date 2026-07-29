#!/usr/bin/env python3
"""Audit every Progress 05 milestone requirement against its declared automated tests."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "requirements/progress-05-traceability-audit.json"
REQ_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
P05_SCOPE_IDS = {
    *(f"RECCHANG-{index:03d}" for index in range(1, 7)),
    *(f"PLTVIEW-{index:03d}" for index in range(1, 13)),
    *(f"PLTDESK-{index:03d}" for index in range(1, 7)),
    "DATGIT-003", "DATGIT-004", "DATDB-004", "DELDOD-002", "TSTSEC-001", "TSTGATE-003",
}

# This is a semantic audit, not an automatic claim that a broad requirement is complete.
# "direct" means the linked local-reference test directly exercises the implemented
# behavior. "partial" means the test is applicable but the normative requirement is
# broader. "deferred" means the ledger remains NOT_STARTED and no test is claimed.
COVERAGE: dict[str, tuple[str, str]] = {
    "RECCHANG-001": ("direct", "comparison tests assert commits, region, registration, thresholds, evidence, and algorithm identity"),
    "RECCHANG-002": ("direct", "comparison tests assert nuisance-cause suppression"),
    "RECCHANG-003": ("direct", "comparison tests prove unobserved removal is suppressed"),
    "RECCHANG-004": ("partial", "review tests bind synchronized viewer state and source evidence, but independent browser usability remains external"),
    "RECCHANG-005": ("direct", "failure injection proves semantic event application and controlled scene commit are atomic and idempotent"),
    "RECCHANG-006": ("direct", "benchmark tests retain precision, recall, localization error, and false-action rate by class"),
    "PLTVIEW-001": ("partial", "saved viewer state covers navigation and comparison controls; full browser/device navigation acceptance remains external"),
    "PLTVIEW-002": ("deferred", "bounded production streaming and device frame budgets are not implemented in this checkpoint"),
    "PLTVIEW-003": ("partial", "selection and policy-bound session state are covered; every related panel is not browser-acceptance verified"),
    "PLTVIEW-004": ("deferred", "persistent label and evidence-view requirement remains NOT_STARTED in the ledger"),
    "PLTVIEW-005": ("direct", "browser-independent runtime and source tests execute keyboard, semantic fallback, captions, reduced motion, and contrast controls"),
    "PLTVIEW-006": ("direct", "round-trip session test compares saved commit, camera, layers, filters, redaction, and accessibility state"),
    "PLTVIEW-007": ("partial", "the five-role implementation and directive model are exercised, but no mounted React/Three.js viewer integration test has run in the frozen web toolchain"),
    "PLTVIEW-008": ("deferred", "stable semantic proxy picking remains outside the included verified scope"),
    "PLTVIEW-009": ("deferred", "proxy-started measurement UI acceptance remains outside the included verified scope"),
    "PLTVIEW-010": ("deferred", "independent diagnostic tooling remains outside this checkpoint"),
    "PLTVIEW-011": ("deferred", "supported-device graceful-degradation budgets remain outside this checkpoint"),
    "PLTVIEW-012": ("deferred", "complete non-splat fallback acceptance remains outside this checkpoint"),
    "PLTDESK-001": ("direct", "local project tests exercise synchronized observations, all correspondence types, undo, and provenance"),
    "PLTDESK-002": ("direct", "tests exercise factor residuals, loop constraints, source weights, and regional uncertainty"),
    "PLTDESK-003": ("direct", "branch and merge tests preserve local author, base commit, and conflicts"),
    "PLTDESK-004": ("direct", "authorized project opens and mutates locally without cloud identity or login token"),
    "PLTDESK-005": ("partial", "atomic bundle, tamper, lock, and reopen tests cover deterministic crash safety; actual GPU-process crash validation remains external"),
    "PLTDESK-006": ("direct", "proposal export tests enforce policy, license, and non-authoritative publication gates"),
    "DATGIT-003": ("direct", "protected merge tests reject automatic merge of authoritative conflict classes"),
    "DATGIT-004": ("direct", "spatial Git tests exercise immutable tags and temporal milestone identity"),
    "DATDB-004": ("partial", "clean install and exact rollback rehearsal are local; production-sized rehearsal remains external"),
    "DELDOD-002": ("partial", "migration compatibility and local rollback are tested; every generated-client/deployment profile is broader"),
    "TSTSEC-001": ("partial", "cross-tenant and live local-HTTP discovery denials are tested; the normative attack surface is broader"),
    "TSTGATE-003": ("partial", "release admission and control-status propagation fail closed while many production gates remain open"),
}


def _tests() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                result[f"{relative}::{node.name}"] = set(REQ_PATTERN.findall(ast.get_docstring(node) or ""))
    return result


def build() -> dict[str, Any]:
    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    records = {item["requirement_id"]: item for item in ledger["requirements"]}
    implementation = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))["requirements"]
    tests = _tests()
    findings: list[dict[str, str]] = []
    audited: list[dict[str, Any]] = []
    if set(COVERAGE) != P05_SCOPE_IDS:
        raise RuntimeError("Progress 05 semantic coverage table does not exactly match milestone scope")

    for requirement_id in sorted(P05_SCOPE_IDS):
        record = records.get(requirement_id)
        if record is None:
            findings.append({"code": "REQUIREMENT_MISSING", "requirement_id": requirement_id})
            continue
        classification, rationale = COVERAGE[requirement_id]
        linked = list(implementation.get(requirement_id, {}).get("test_ids", []))
        declarations: list[dict[str, Any]] = []
        for test_id in linked:
            declared = tests.get(test_id)
            declarations.append({
                "test_id": test_id,
                "test_exists": declared is not None,
                "declares_requirement_id": declared is not None and requirement_id in declared,
                "declared_requirement_ids": sorted(declared or []),
            })
            if declared is None:
                findings.append({"code": "LINKED_TEST_MISSING", "requirement_id": requirement_id, "test_id": test_id})
            elif requirement_id not in declared:
                findings.append({"code": "TEST_DOES_NOT_DECLARE_REQUIREMENT", "requirement_id": requirement_id, "test_id": test_id})

        status = str(record.get("implementation_status"))
        if classification == "deferred" and status != "NOT_STARTED":
            findings.append({"code": "DEFERRED_STATUS_MISMATCH", "requirement_id": requirement_id, "status": status})
        if classification == "deferred" and linked:
            findings.append({"code": "DEFERRED_REQUIREMENT_HAS_CLAIMED_TEST", "requirement_id": requirement_id})
        if classification != "deferred" and status == "NOT_STARTED":
            findings.append({"code": "IMPLEMENTED_STATUS_MISMATCH", "requirement_id": requirement_id, "status": status})
        if status == "VERIFIED" and classification != "direct":
            findings.append({"code": "VERIFIED_WITHOUT_DIRECT_COVERAGE", "requirement_id": requirement_id})
        if status == "VERIFIED" and not linked:
            findings.append({"code": "VERIFIED_WITHOUT_LINKED_TEST", "requirement_id": requirement_id})

        audited.append({
            "requirement_id": requirement_id,
            "status": status,
            "coverage_classification": classification,
            "semantic_rationale": rationale,
            "linked_tests": declarations,
            "linked_test_count": len(linked),
            "all_linked_tests_declare_requirement_id": all(item["declares_requirement_id"] for item in declarations),
        })

    return {
        "schema": "sip.progress-05-traceability-audit/v1",
        "milestone": "Progress 05-R2",
        "scope_requirement_count": len(P05_SCOPE_IDS),
        "audited_requirements": audited,
        "findings": findings,
        "finding_count": len(findings),
        "status": "passed_complete" if not findings else "failed",
        "production_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Progress 05 traceability audit drift detected; run tools/audit_progress05_traceability.py")
    else:
        DESTINATION.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": payload["status"], "requirements": payload["scope_requirement_count"], "findings": payload["finding_count"]}, sort_keys=True))
    raise SystemExit(0 if payload["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
