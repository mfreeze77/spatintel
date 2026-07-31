#!/usr/bin/env python3
"""Audit the exact bounded Progress 08 OPS-002 milestone against executable evidence."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_08.json"
AUDIT = ROOT / "requirements/progress-08-traceability-audit.json"
REQ = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
EXPECTED_BASE = "986c198a127616f8bf1d2379e9f9df5138dabc40"
EXPECTED_INCLUDED = 40
EXPECTED_DEFERRED = 0
ALLOWED_PREFIXES = ("ARCOBS-", "ARCRES-", "RECGPU-", "OPSSRE-", "OPSCOST-", "OPSPERF-", "OPSSUP-")


def _tests() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                result[f"{relative}::{node.name}"] = set(REQ.findall(ast.get_docstring(node) or ""))
    return result


def build() -> dict[str, Any]:
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    ledger_payload = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    ledger = {item["requirement_id"]: item for item in ledger_payload["requirements"]}
    mapping = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))["requirements"]
    catalog = _tests()
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    included = scope.get("included_requirements", [])
    deferred = scope.get("deferred_requirements", [])
    if scope.get("accepted_base_commit") != EXPECTED_BASE:
        findings.append({"code": "ACCEPTED_BASE_MISMATCH", "expected": EXPECTED_BASE, "actual": scope.get("accepted_base_commit")})
    if scope.get("authorized_epics") != ["OPS-002"]:
        findings.append({"code": "AUTHORIZED_EPIC_MISMATCH", "actual": scope.get("authorized_epics")})
    if scope.get("included_requirement_count") != EXPECTED_INCLUDED or len(included) != EXPECTED_INCLUDED:
        findings.append({"code": "INCLUDED_SCOPE_COUNT_MISMATCH", "actual": len(included)})
    if scope.get("deferred_requirement_count") != EXPECTED_DEFERRED or deferred:
        findings.append({"code": "DEFERRED_SCOPE_COUNT_MISMATCH", "actual": len(deferred)})
    if scope.get("progress_08_authorized") is not True or scope.get("progress_09_authorized") is not False or scope.get("production_authorized") is not False:
        findings.append({"code": "AUTHORIZATION_POSTURE_INVALID"})

    included_ids = {item["requirement_id"] for item in included}
    if len(included_ids) != EXPECTED_INCLUDED:
        findings.append({"code": "DUPLICATE_OR_MISSING_SCOPE_IDS"})
    invalid_ids = sorted(item for item in included_ids if not item.startswith(ALLOWED_PREFIXES))
    if invalid_ids:
        findings.append({"code": "OUT_OF_SCOPE_REQUIREMENT", "requirements": invalid_ids})

    for entry in sorted(included, key=lambda value: value["requirement_id"]):
        rid = entry["requirement_id"]
        ledger_item = ledger.get(rid)
        overlay = mapping.get(rid)
        if ledger_item is None:
            findings.append({"code": "REQUIREMENT_MISSING_FROM_LEDGER", "requirement_id": rid})
            continue
        if overlay is None:
            findings.append({"code": "REQUIREMENT_MISSING_FROM_IMPLEMENTATION_MAP", "requirement_id": rid})
        direct: list[dict[str, Any]] = []
        for raw in entry.get("direct_tests", []):
            test_id = raw.get("test_id") if isinstance(raw, dict) else str(raw)
            declared = catalog.get(test_id)
            exists = declared is not None
            declares = exists and rid in declared
            mapped = overlay is not None and test_id in overlay.get("test_ids", [])
            direct.append({
                "test_id": test_id,
                "exists": exists,
                "declares_requirement_id": bool(declares),
                "present_in_implementation_map": bool(mapped),
                "declared_requirement_ids": sorted(declared or []),
            })
            if not exists:
                findings.append({"code": "DIRECT_TEST_MISSING", "requirement_id": rid, "test_id": test_id})
            elif not declares:
                findings.append({"code": "DIRECT_TEST_DECLARATION_MISSING", "requirement_id": rid, "test_id": test_id})
            if not mapped:
                findings.append({"code": "DIRECT_TEST_MAPPING_MISSING", "requirement_id": rid, "test_id": test_id})
        if not direct:
            findings.append({"code": "INCLUDED_REQUIREMENT_WITHOUT_DIRECT_TEST", "requirement_id": rid})
        if entry.get("implementation_status") != ledger_item.get("implementation_status"):
            findings.append({
                "code": "SCOPE_LEDGER_STATUS_MISMATCH",
                "requirement_id": rid,
                "scope": entry.get("implementation_status"),
                "ledger": ledger_item.get("implementation_status"),
            })
        for path in entry.get("implementation_files", []):
            if not (ROOT / path).exists():
                findings.append({"code": "IMPLEMENTATION_PATH_MISSING", "requirement_id": rid, "path": path})
        records.append({
            "requirement_id": rid,
            "priority": ledger_item.get("priority"),
            "implementation_status": ledger_item.get("implementation_status"),
            "verification_method": ledger_item.get("verification_method"),
            "direct_tests": direct,
            "implementation_files": entry.get("implementation_files", []),
            "evidence_paths": entry.get("evidence_paths", []),
        })

    if ledger.get("PLTVIEW-007", {}).get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        findings.append({"code": "PLTVIEW_007_STATUS_INVALID"})

    return {
        "schema": "sip.progress08-traceability-audit/v1",
        "milestone": "Progress 08 bounded observability, SLO, cost, quota, resilience, and support tooling",
        "accepted_base_commit": EXPECTED_BASE,
        "authorized_epics": ["OPS-002"],
        "status": "passed_complete" if not findings else "failed",
        "requirement_count": len(records),
        "included_requirement_count": len(included_ids),
        "deferred_requirement_count": len(deferred),
        "requirements_audited": records,
        "finding_count": len(findings),
        "findings": findings,
        "progress_08_authorized": True,
        "progress_09_authorized": False,
        "production_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not AUDIT.is_file() or AUDIT.read_text(encoding="utf-8") != text:
            raise SystemExit("Progress 08 traceability audit drift detected; run tools/audit_progress08_traceability.py")
    else:
        AUDIT.write_text(text, encoding="utf-8")
    print(json.dumps({"status": value["status"], "requirements": value["requirement_count"], "findings": value["finding_count"]}, sort_keys=True))
    raise SystemExit(0 if value["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
