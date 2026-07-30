#!/usr/bin/env python3
"""Audit the bounded Progress 07 milestone against exact tests and conservative ledger state."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_07.json"
AUDIT = ROOT / "requirements/progress-07-traceability-audit.json"
REQ = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
EXPECTED_BASE = "600e3d81ffb47a88cc0a3041b7fdc7a5901a9fe8"
EXPECTED_INCLUDED = 61
EXPECTED_DEFERRED = 3


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

    if scope.get("accepted_base_commit") != EXPECTED_BASE:
        findings.append({"code": "ACCEPTED_BASE_MISMATCH", "expected": EXPECTED_BASE, "actual": scope.get("accepted_base_commit")})
    if scope.get("included_requirement_count") != EXPECTED_INCLUDED or len(scope.get("included_requirements", [])) != EXPECTED_INCLUDED:
        findings.append({"code": "INCLUDED_SCOPE_COUNT_MISMATCH"})
    if scope.get("deferred_requirement_count") != EXPECTED_DEFERRED or len(scope.get("deferred_requirements", [])) != EXPECTED_DEFERRED:
        findings.append({"code": "DEFERRED_SCOPE_COUNT_MISMATCH"})
    if scope.get("progress_07_authorized") is not True or scope.get("production_authorized") is not False or scope.get("progress_08_authorized") is not False:
        findings.append({"code": "AUTHORIZATION_POSTURE_INVALID"})

    included_ids = {item["requirement_id"] for item in scope.get("included_requirements", [])}
    deferred_ids = {item["requirement_id"] for item in scope.get("deferred_requirements", [])}
    if included_ids & deferred_ids:
        findings.append({"code": "SCOPE_PARTITION_OVERLAP", "requirements": sorted(included_ids & deferred_ids)})
    if deferred_ids != {"OPSSEC-005", "OPSPRIV-005", "OPSAUDIT-006"}:
        findings.append({"code": "DEFERRED_SCOPE_IDENTITY_MISMATCH", "actual": sorted(deferred_ids)})

    for disposition, entries in (
        ("included", scope.get("included_requirements", [])),
        ("deferred", scope.get("deferred_requirements", [])),
    ):
        for entry in sorted(entries, key=lambda value: value["requirement_id"]):
            rid = entry["requirement_id"]
            ledger_item = ledger.get(rid)
            overlay = mapping.get(rid)
            if ledger_item is None:
                findings.append({"code": "REQUIREMENT_MISSING_FROM_LEDGER", "requirement_id": rid})
                continue
            if disposition == "included" and overlay is None:
                findings.append({"code": "INCLUDED_REQUIREMENT_MISSING_FROM_IMPLEMENTATION_MAP", "requirement_id": rid})
            direct: list[dict[str, Any]] = []
            for raw in entry.get("direct_tests", []):
                test_id = raw.get("test_id") if isinstance(raw, dict) else str(raw)
                declared = catalog.get(test_id)
                exists = declared is not None
                declares = exists and rid in declared
                mapped = overlay is not None and test_id in overlay.get("test_ids", [])
                direct.append(
                    {
                        "test_id": test_id,
                        "exists": exists,
                        "declares_requirement_id": bool(declares),
                        "present_in_implementation_map": bool(mapped),
                        "declared_requirement_ids": sorted(declared or []),
                    }
                )
                if not exists:
                    findings.append({"code": "DIRECT_TEST_MISSING", "requirement_id": rid, "test_id": test_id})
                elif not declares:
                    findings.append({"code": "DIRECT_TEST_DECLARATION_MISSING", "requirement_id": rid, "test_id": test_id})
                if disposition == "included" and not mapped:
                    findings.append({"code": "DIRECT_TEST_MAPPING_MISSING", "requirement_id": rid, "test_id": test_id})
            if disposition == "included" and not direct:
                findings.append({"code": "INCLUDED_REQUIREMENT_WITHOUT_DIRECT_TEST", "requirement_id": rid})
            if entry.get("implementation_status") != ledger_item.get("implementation_status"):
                findings.append(
                    {
                        "code": "SCOPE_LEDGER_STATUS_MISMATCH",
                        "requirement_id": rid,
                        "scope": entry.get("implementation_status"),
                        "ledger": ledger_item.get("implementation_status"),
                    }
                )
            for path in entry.get("implementation_files", []):
                if not (ROOT / path).exists():
                    findings.append({"code": "IMPLEMENTATION_PATH_MISSING", "requirement_id": rid, "path": path})
            records.append(
                {
                    "requirement_id": rid,
                    "disposition": disposition,
                    "priority": ledger_item.get("priority"),
                    "implementation_status": ledger_item.get("implementation_status"),
                    "verification_method": ledger_item.get("verification_method"),
                    "direct_tests": direct,
                    "implementation_files": entry.get("implementation_files", []),
                    "evidence_paths": entry.get("evidence_paths", []),
                    "defer_reason": entry.get("defer_reason"),
                }
            )

    if ledger.get("PLTVIEW-007", {}).get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        findings.append({"code": "PLTVIEW_007_STATUS_INVALID"})

    return {
        "schema": "sip.progress07-traceability-audit/v1",
        "milestone": "Progress 07 bounded security, privacy, audit, key, provider, and supply-chain readiness",
        "accepted_base_commit": EXPECTED_BASE,
        "status": "passed_complete" if not findings else "failed",
        "requirement_count": len(records),
        "included_requirement_count": len(included_ids),
        "deferred_requirement_count": len(deferred_ids),
        "requirements_audited": records,
        "finding_count": len(findings),
        "findings": findings,
        "progress_07_authorized": True,
        "progress_08_authorized": False,
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
            raise SystemExit("Progress 07 traceability audit drift detected; run tools/audit_progress07_traceability.py")
    else:
        AUDIT.write_text(text, encoding="utf-8")
    print(json.dumps({"status": value["status"], "requirements": value["requirement_count"], "findings": value["finding_count"]}, sort_keys=True))
    raise SystemExit(0 if value["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
