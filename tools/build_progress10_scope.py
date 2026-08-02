#!/usr/bin/env python3
"""Validate the accepted Progress 10 scope or print a current-ledger candidate."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LEDGER = ROOT / "requirements/requirements-ledger.json"
OUTPUT = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_10.json"
IDS = tuple(
    [f"ARCRES-{i:03d}" for i in range(1, 6)]
    + [f"DATRET-{i:03d}" for i in range(1, 7)]
    + [f"PLTIO-{i:03d}" for i in range(1, 13)]
    + [f"LIFPRESV-{i:03d}" for i in range(1, 7)]
    + [f"OPSDR-{i:03d}" for i in range(1, 7)]
    + [f"SIPMIG-{i:03d}" for i in range(1, 11)]
)
VERIFIED_LOCALLY = {
    "DATRET-001",
    "DATRET-002",
    "DATRET-003",
    "DATRET-004",
    "DATRET-005",
    "DATRET-006",
    "OPSDR-004",
    "OPSDR-005",
    "PLTIO-003",
    "PLTIO-006",
    "PLTIO-012",
}
EXTERNAL_ONLY = {"ARCRES-002", "ARCRES-005", "OPSDR-002", "OPSDR-003"}
IMPLEMENTATION_FILES = {
    "ARCRES": [
        "src/sip/recovery.py",
        "src/sip/operations.py",
        "src/sip/deployment.py",
        "src/sip/observability.py",
        "migrations/versions/0020_progress10_recovery_retention.py",
        "docs/operator/PROGRESS_10_RECOVERY_RUNBOOK.md",
    ],
    "DATRET": [
        "src/sip/recovery.py",
        "src/sip/lifecycle.py",
        "src/sip/assets.py",
        "src/sip/database.py",
        "migrations/versions/0020_progress10_recovery_retention.py",
        "docs/operator/PROGRESS_10_RETENTION_DELETION_RUNBOOK.md",
    ],
    "PLTIO": [
        "src/sip/exporting.py",
        "src/sip/recovery.py",
        "src/sip/hybrid.py",
        "src/sip/contracts.py",
        "docs/developer/PROGRESS_10_RECOVERY_API.md",
    ],
    "LIFPRESV": [
        "src/sip/exporting.py",
        "src/sip/recovery.py",
        "src/sip/liveforever.py",
        "docs/operator/PROGRESS_10_RECOVERY_RUNBOOK.md",
    ],
    "OPSDR": [
        "src/sip/recovery.py",
        "src/sip/security_ops.py",
        "src/sip/database.py",
        "src/sip/api.py",
        "migrations/versions/0020_progress10_recovery_retention.py",
        "docs/runbooks/PROGRESS_10_RECOVERY_INCIDENTS.md",
    ],
    "SIPMIG": [
        "src/sip/recovery.py",
        "src/sip/exporting.py",
        "src/sip/spatial_data.py",
        "src/sip/scene.py",
        "migrations/versions/0020_progress10_recovery_retention.py",
        "docs/operator/PROGRESS_10_MIGRATION_RUNBOOK.md",
    ],
}


def _tests() -> dict[str, list[dict[str, str]]]:
    result = {identifier: [] for identifier in IDS}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            doc = ast.get_docstring(node) or ""
            for identifier in IDS:
                if identifier in doc:
                    result[identifier].append({"test_id": f"{path.relative_to(ROOT).as_posix()}::{node.name}"})
    return result


def build() -> dict[str, Any]:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))["requirements"]
    by_id = {item["requirement_id"]: item for item in ledger}
    tests = _tests()
    included = []
    for identifier in IDS:
        item = by_id[identifier]
        prefix = identifier.split("-", 1)[0]
        if identifier in VERIFIED_LOCALLY:
            status = "VERIFIED"
        elif identifier in EXTERNAL_ONLY:
            status = "EXTERNAL_VALIDATION_REQUIRED"
        else:
            status = "IMPLEMENTED_UNVERIFIED"
        included.append(
            {
                "requirement_id": identifier,
                "priority": item["priority"],
                "requirement": item["text"],
                "source_document": item["source_document"],
                "source_line": item.get("source_line"),
                "verification_method": item.get("verification_method"),
                "status_at_scope_freeze": item.get("implementation_status"),
                "implementation_status": status,
                "implementation_files": IMPLEMENTATION_FILES[prefix],
                "direct_tests": tests[identifier],
                "evidence_paths": [
                    "build/reports/test-matrix.json",
                    "build/reports/tests/integration.xml",
                    "build/reports/tests/security.xml",
                    "build/evidence/demo-progress10-recovery.json",
                    "build/reports/checkpoint-acceptance-gates.json",
                ],
            }
        )
    return {
        "schema": "sip.milestone-scope/v1",
        "checkpoint_id": "sip-v1.1.0-progress-10",
        "branch": "progress-10-recovery",
        "accepted_base_commit": "f293d6425182ef04f5893275724e2a4bd28cf00e",
        "authorized_epics": ["OPS-004"],
        "scope_statement": (
            "Progress 10 is limited to OPS-004 backup, restore, disaster recovery, retention, deletion, "
            "portability contingency, preservation, and conservative v1.0 migration safeguards. QA-002, "
            "pilots, Progress 11, production credentials, production traffic, and production promotion "
            "remain unauthorized."
        ),
        "dependency_rationale": (
            "Progress 09 closed OPS-003 and True North authorized only OPS-004 as its bounded successor."
        ),
        "included_requirement_count": len(included),
        "deferred_requirement_count": 0,
        "included_requirements": included,
        "deferred_requirements": [],
        "acceptance_criteria": [
            "corrupted, incomplete, stale, cross-scope, and unauthorized-region recovery attempts fail closed",
            "restore replays are idempotent and reconcile manifests, database references, object hashes, "
            "audit chronology, and queues before writes reopen",
            "legal holds block purge and backup expiry",
            "deletion graphs retain impact, approvals, cross-store propagation, exceptions, and "
            "cryptographic-erasure evidence",
            "ordinary restore cannot resurrect data after completed deletion",
            "tenant offboarding produces verified open exports plus retention and deletion reports",
            "fixity, format migration, offline viewing, succession, shutdown, and portability controls "
            "retain originals and open formats",
            "v1.0 migration is additive, provenance-based, conservative, rollback-backed, and signed",
            "synthetic game days retain measured RPO/RTO and a verified portability export without "
            "claiming cloud or production certification",
            "complete exact-commit acceptance and both dedicated package verifiers return zero findings",
        ],
        "external_gaps": [
            "Database PITR and object-version recovery require credentialed managed database and "
            "object-store execution.",
            "Multi-region service-loss and cross-region recovery require executed cloud evidence and residency review.",
            "Physical edge recovery, key-custodian ceremonies, and external witnessing remain unexecuted.",
            "Production RPO/RTO certification, customer data recovery, and legal/evidentiary review remain external.",
        ],
        "explicitly_out_of_scope": [
            "QA-002 final release gates",
            "customer or human-subject pilots",
            "production credentials, data, or traffic",
            "Progress 11",
            "production promotion",
        ],
        "progress_10_authorized": True,
        "progress_11_authorized": False,
        "production_authorized": False,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate the immutable accepted Progress 10 snapshot")
    parser.add_argument(
        "--regenerate-current",
        action="store_true",
        help="print a current-ledger candidate to stdout; never rewrite the accepted historical scope",
    )
    args = parser.parse_args()
    if args.regenerate_current:
        print(json.dumps(build(), indent=2, sort_keys=True))
        return 0

    from tools.audit_progress10_traceability import validate_accepted_snapshot

    value = validate_accepted_snapshot()
    print(
        json.dumps(
            {
                "status": value["status"],
                "included": value["included"],
                "deferred": value["deferred"],
                "historical_snapshot": value["historical_snapshot"],
            },
            sort_keys=True,
        )
    )
    return 0 if value["status"] == "passed_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
