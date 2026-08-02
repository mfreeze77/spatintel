#!/usr/bin/env python3
"""Validate the immutable, accepted Progress 10 historical traceability snapshot."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_10.json"
AUDIT = ROOT / "requirements/progress-10-traceability-audit.json"
PROVENANCE = ROOT / "RECONSTRUCTION_PROVENANCE_PROGRESS_11.json"
LEDGER = ROOT / "requirements/requirements-ledger.json"
CURRENT_IMPLEMENTATION_MAP = ROOT / "requirements/implementation-map.json"

REQ = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
EXPECTED_BASE = "f293d6425182ef04f5893275724e2a4bd28cf00e"
EXPECTED_CHECKPOINT = "sip-v1.1.0-progress-10"
EXPECTED_COMMIT = "ab409f6ac7ca583535f69e5806b7a3bdbfe08214"
EXPECTED_TREE = "ced38981c7f41891a9c1288b789400b597a28b44"
EXPECTED_SOURCE_ROOT = "0c93009874f99c72c3670d6cfca47af00ff04b762e4f4ddddffa20ab03ed8678"
EXPECTED_SCOPE_SHA256 = "a44973d2f03ec67a3bb37055476093a40668f90b31671802c7aef3877f9a6e9a"
EXPECTED_AUDIT_SHA256 = "3c2cb66e550a8dd3403b2a2ce243cc453808472a58290a5b940937079a959e26"
EXPECTED_INCLUDED = 45
EXPECTED_DEFERRED = 0
ALLOWED_PREFIXES = ("ARCRES-", "DATRET-", "PLTIO-", "LIFPRESV-", "OPSDR-", "SIPMIG-")

SCOPE_FIELDS = {
    "schema",
    "checkpoint_id",
    "branch",
    "accepted_base_commit",
    "authorized_epics",
    "scope_statement",
    "included_requirement_count",
    "deferred_requirement_count",
    "included_requirements",
    "deferred_requirements",
    "acceptance_criteria",
    "external_gaps",
    "explicitly_out_of_scope",
    "progress_10_authorized",
    "progress_11_authorized",
    "production_authorized",
}
SCOPE_ENTRY_FIELDS = {
    "requirement_id",
    "priority",
    "requirement",
    "source_document",
    "source_line",
    "verification_method",
    "status_at_scope_freeze",
    "implementation_status",
    "implementation_files",
    "direct_tests",
    "evidence_paths",
}
AUDIT_FIELDS = {
    "schema",
    "milestone",
    "accepted_base_commit",
    "authorized_epics",
    "status",
    "requirement_count",
    "included_requirement_count",
    "deferred_requirement_count",
    "requirements_audited",
    "finding_count",
    "findings",
    "progress_10_authorized",
    "progress_11_authorized",
    "production_authorized",
}
AUDIT_ENTRY_FIELDS = {
    "requirement_id",
    "implementation_status",
    "direct_tests",
    "implementation_files",
    "evidence_paths",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, *, label: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.is_file():
        findings.append({"code": f"{label}_MISSING", "path": path.relative_to(ROOT).as_posix()})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        findings.append({"code": f"{label}_MALFORMED", "detail": str(exc)})
        return {}
    if not isinstance(value, dict):
        findings.append({"code": f"{label}_TYPE_INVALID"})
        return {}
    return value


def _tests() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                result[f"{relative}::{node.name}"] = set(REQ.findall(ast.get_docstring(node) or ""))
    return result


def _test_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("test_id", "")) if isinstance(item, dict) else str(item)
        for item in value
    ]


def validate_accepted_snapshot() -> dict[str, Any]:
    """Validate frozen Progress 10 facts while allowing cumulative evidence to advance."""
    findings: list[dict[str, Any]] = []
    scope = _read_json(SCOPE, label="SCOPE_SNAPSHOT", findings=findings)
    audit = _read_json(AUDIT, label="AUDIT_SNAPSHOT", findings=findings)
    provenance = _read_json(PROVENANCE, label="PROVENANCE", findings=findings)
    ledger_payload = _read_json(LEDGER, label="LEDGER", findings=findings)

    scope_hash = _sha256(SCOPE) if SCOPE.is_file() else None
    audit_hash = _sha256(AUDIT) if AUDIT.is_file() else None
    if scope_hash != EXPECTED_SCOPE_SHA256:
        findings.append(
            {"code": "SCOPE_SNAPSHOT_DRIFT", "expected": EXPECTED_SCOPE_SHA256, "actual": scope_hash}
        )
    if audit_hash != EXPECTED_AUDIT_SHA256:
        findings.append(
            {"code": "AUDIT_SNAPSHOT_DRIFT", "expected": EXPECTED_AUDIT_SHA256, "actual": audit_hash}
        )

    missing_scope_fields = sorted(SCOPE_FIELDS - set(scope))
    if missing_scope_fields:
        findings.append({"code": "SCOPE_FIELDS_MISSING", "fields": missing_scope_fields})
    missing_audit_fields = sorted(AUDIT_FIELDS - set(audit))
    if missing_audit_fields:
        findings.append({"code": "AUDIT_FIELDS_MISSING", "fields": missing_audit_fields})

    accepted_base = provenance.get("accepted_base", {}) if isinstance(provenance, dict) else {}
    expected_identity = {
        "checkpoint_id": EXPECTED_CHECKPOINT,
        "commit": EXPECTED_COMMIT,
        "tree": EXPECTED_TREE,
        "source_root_sha256": EXPECTED_SOURCE_ROOT,
    }
    actual_identity = {key: accepted_base.get(key) for key in expected_identity}
    if actual_identity != expected_identity:
        findings.append(
            {"code": "ACCEPTED_CHECKPOINT_IDENTITY_DRIFT", "expected": expected_identity, "actual": actual_identity}
        )

    included = scope.get("included_requirements", [])
    deferred = scope.get("deferred_requirements", [])
    if not isinstance(included, list):
        findings.append({"code": "SCOPE_INCLUDED_TYPE_INVALID"})
        included = []
    if not isinstance(deferred, list):
        findings.append({"code": "SCOPE_DEFERRED_TYPE_INVALID"})
        deferred = []
    if scope.get("checkpoint_id") != EXPECTED_CHECKPOINT:
        findings.append({"code": "CHECKPOINT_ID_MISMATCH", "actual": scope.get("checkpoint_id")})
    if scope.get("accepted_base_commit") != EXPECTED_BASE:
        findings.append({"code": "ACCEPTED_BASE_MISMATCH", "actual": scope.get("accepted_base_commit")})
    if scope.get("authorized_epics") != ["OPS-004"]:
        findings.append({"code": "AUTHORIZED_EPIC_MISMATCH", "actual": scope.get("authorized_epics")})
    if scope.get("included_requirement_count") != EXPECTED_INCLUDED or len(included) != EXPECTED_INCLUDED:
        findings.append({"code": "INCLUDED_SCOPE_COUNT_MISMATCH", "actual": len(included)})
    if scope.get("deferred_requirement_count") != EXPECTED_DEFERRED or deferred:
        findings.append({"code": "DEFERRED_SCOPE_COUNT_MISMATCH", "actual": len(deferred)})
    if (
        scope.get("progress_10_authorized") is not True
        or scope.get("progress_11_authorized") is not False
        or scope.get("production_authorized") is not False
    ):
        findings.append({"code": "SCOPE_AUTHORIZATION_POSTURE_INVALID"})

    ledger_items = ledger_payload.get("requirements", []) if isinstance(ledger_payload, dict) else []
    ledger = {
        item.get("requirement_id"): item
        for item in ledger_items
        if isinstance(item, dict) and isinstance(item.get("requirement_id"), str)
    }
    catalog = _tests()
    scope_by_id: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(included):
        if not isinstance(entry, dict):
            findings.append({"code": "SCOPE_ENTRY_TYPE_INVALID", "index": index})
            continue
        missing = sorted(SCOPE_ENTRY_FIELDS - set(entry))
        if missing:
            findings.append(
                {"code": "SCOPE_ENTRY_FIELDS_MISSING", "requirement_id": entry.get("requirement_id"), "fields": missing}
            )
        requirement_id = entry.get("requirement_id")
        if not isinstance(requirement_id, str) or not requirement_id.startswith(ALLOWED_PREFIXES):
            findings.append({"code": "OUT_OF_SCOPE_REQUIREMENT", "requirement_id": requirement_id})
            continue
        if requirement_id in scope_by_id:
            findings.append({"code": "DUPLICATE_SCOPE_REQUIREMENT", "requirement_id": requirement_id})
            continue
        scope_by_id[requirement_id] = entry

        current = ledger.get(requirement_id)
        if current is None:
            findings.append({"code": "REQUIREMENT_MISSING_FROM_LEDGER", "requirement_id": requirement_id})
        else:
            semantics = {
                "priority": ("priority", "priority"),
                "requirement": ("requirement", "text"),
                "source_document": ("source_document", "source_document"),
                "source_line": ("source_line", "source_line"),
                "verification_method": ("verification_method", "verification_method"),
            }
            for label, (historical_key, current_key) in semantics.items():
                if entry.get(historical_key) != current.get(current_key):
                    findings.append(
                        {
                            "code": "REQUIREMENT_SEMANTICS_DRIFT",
                            "requirement_id": requirement_id,
                            "field": label,
                        }
                    )

        for path in entry.get("implementation_files", []):
            if not isinstance(path, str) or not (ROOT / path).is_file():
                findings.append(
                    {"code": "HISTORICAL_IMPLEMENTATION_PATH_MISSING", "requirement_id": requirement_id, "path": path}
                )
        evidence_paths = entry.get("evidence_paths")
        if not isinstance(evidence_paths, list) or not evidence_paths or not all(
            isinstance(path, str) and path for path in evidence_paths
        ):
            findings.append({"code": "HISTORICAL_EVIDENCE_IDENTIFIERS_INVALID", "requirement_id": requirement_id})
        linked_tests = _test_ids(entry.get("direct_tests"))
        if not linked_tests or any(not test_id for test_id in linked_tests):
            findings.append({"code": "HISTORICAL_LINKED_TESTS_INVALID", "requirement_id": requirement_id})
        for test_id in linked_tests:
            declared = catalog.get(test_id)
            if declared is None:
                findings.append(
                    {"code": "ACCEPTED_LINKED_TEST_MISSING", "requirement_id": requirement_id, "test_id": test_id}
                )
            elif requirement_id not in declared:
                findings.append(
                    {
                        "code": "ACCEPTED_LINKED_TEST_DECLARATION_DRIFT",
                        "requirement_id": requirement_id,
                        "test_id": test_id,
                        "declared": sorted(declared),
                    }
                )

    if len(scope_by_id) != EXPECTED_INCLUDED:
        findings.append({"code": "UNIQUE_SCOPE_COUNT_MISMATCH", "actual": len(scope_by_id)})

    audited = audit.get("requirements_audited", [])
    if not isinstance(audited, list):
        findings.append({"code": "AUDITED_REQUIREMENTS_TYPE_INVALID"})
        audited = []
    if (
        audit.get("status") != "passed_complete"
        or audit.get("finding_count") != 0
        or audit.get("findings") != []
    ):
        findings.append({"code": "ACCEPTED_AUDIT_STATUS_INVALID"})
    if audit.get("accepted_base_commit") != EXPECTED_BASE or audit.get("authorized_epics") != ["OPS-004"]:
        findings.append({"code": "ACCEPTED_AUDIT_METADATA_INVALID"})
    if (
        audit.get("requirement_count") != EXPECTED_INCLUDED
        or audit.get("included_requirement_count") != EXPECTED_INCLUDED
        or audit.get("deferred_requirement_count") != EXPECTED_DEFERRED
        or len(audited) != EXPECTED_INCLUDED
    ):
        findings.append({"code": "ACCEPTED_AUDIT_COUNT_INVALID", "actual": len(audited)})
    if (
        audit.get("progress_10_authorized") is not True
        or audit.get("progress_11_authorized") is not False
        or audit.get("production_authorized") is not False
    ):
        findings.append({"code": "AUDIT_AUTHORIZATION_POSTURE_INVALID"})

    audited_by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(audited):
        if not isinstance(record, dict):
            findings.append({"code": "AUDIT_ENTRY_TYPE_INVALID", "index": index})
            continue
        missing = sorted(AUDIT_ENTRY_FIELDS - set(record))
        if missing:
            findings.append(
                {
                    "code": "AUDIT_ENTRY_FIELDS_MISSING",
                    "requirement_id": record.get("requirement_id"),
                    "fields": missing,
                }
            )
        requirement_id = record.get("requirement_id")
        if not isinstance(requirement_id, str) or requirement_id in audited_by_id:
            findings.append({"code": "AUDIT_REQUIREMENT_ID_INVALID", "requirement_id": requirement_id})
            continue
        audited_by_id[requirement_id] = record
        historical = scope_by_id.get(requirement_id)
        if historical is None:
            findings.append({"code": "AUDIT_REQUIREMENT_OUTSIDE_SCOPE", "requirement_id": requirement_id})
            continue
        if record.get("implementation_status") != historical.get("implementation_status"):
            findings.append({"code": "ACCEPTED_STATUS_DRIFT", "requirement_id": requirement_id})
        if _test_ids(record.get("direct_tests")) != _test_ids(historical.get("direct_tests")):
            findings.append({"code": "ACCEPTED_LINKED_TEST_SET_DRIFT", "requirement_id": requirement_id})
        if record.get("implementation_files") != historical.get("implementation_files"):
            findings.append({"code": "ACCEPTED_IMPLEMENTATION_IDENTIFIERS_DRIFT", "requirement_id": requirement_id})
        if record.get("evidence_paths") != historical.get("evidence_paths"):
            findings.append({"code": "ACCEPTED_EVIDENCE_IDENTIFIERS_DRIFT", "requirement_id": requirement_id})

    if set(audited_by_id) != set(scope_by_id):
        findings.append(
            {
                "code": "AUDIT_SCOPE_REQUIREMENT_SET_MISMATCH",
                "missing": sorted(set(scope_by_id) - set(audited_by_id)),
                "extra": sorted(set(audited_by_id) - set(scope_by_id)),
            }
        )

    return {
        "schema": "sip.progress10-accepted-snapshot-validation/v1",
        "status": "passed_complete" if not findings else "failed",
        "checkpoint": expected_identity,
        "accepted_base_commit": EXPECTED_BASE,
        "authorized_epics": ["OPS-004"],
        "requirements": len(scope_by_id),
        "included": len(included),
        "deferred": len(deferred),
        "finding_count": len(findings),
        "findings": findings,
        "scope_sha256": scope_hash,
        "audit_sha256": audit_hash,
        "historical_snapshot": True,
        "current_cumulative_implementation_map_compared": False,
        "progress_10_authorized": True,
        "progress_11_authorized": False,
        "production_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the immutable accepted snapshot")
    parser.parse_args()
    value = validate_accepted_snapshot()
    print(json.dumps(value, sort_keys=True))
    raise SystemExit(0 if value["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
