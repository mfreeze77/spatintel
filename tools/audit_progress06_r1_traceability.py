#!/usr/bin/env python3
"""Audit the narrow Progress 06-R1 stop-line remediation evidence and scope."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "requirements/progress-06-r1-traceability-audit.json"
SCOPE_PATH = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_06_R1.json"
REQ_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
ACCEPTED_BASE = "383d4bde2518edabe92337df570336a6ecc0d411"

REMEDIATION_REQUIREMENTS = {
    "ARCIAM-001",
    "LIFCONS-001", "LIFCONS-005",
    "CONQC-003", "CONQC-004", "CONQC-006",
    "CONHAND-001", "CONHAND-004", "CONHAND-006",
    "CONAC-006", "CONMEP-006", "SECEXT-005",
    "CONDOC-001", "DATBIM-001", "DATEVID-002",
    "LIFPRESV-001",
    "TSTLAY-003", "TSTSTRAT-002",
}

DIRECT_EVIDENCE: dict[str, tuple[str, ...]] = {
    "ARCIAM-001": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_consent_revocation_is_tenant_and_project_scoped",
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_deficiency_retest_is_tenant_and_project_scoped",
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_issue_verifier_is_authenticated_and_independent",
    ),
    "LIFCONS-001": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_consent_revocation_is_tenant_and_project_scoped",
    ),
    "LIFCONS-005": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_consent_revocation_is_tenant_and_project_scoped",
    ),
    "CONQC-003": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_deficiency_retest_is_tenant_and_project_scoped",
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_issue_verifier_is_authenticated_and_independent",
    ),
    "CONQC-004": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_issue_verifier_is_authenticated_and_independent",
    ),
    "CONQC-006": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_deficiency_retest_is_tenant_and_project_scoped",
    ),
    "CONHAND-001": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_restricted_annex_requires_scoped_server_approval",
    ),
    "CONHAND-004": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_restricted_annex_requires_scoped_server_approval",
    ),
    "CONHAND-006": (
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_accepts_only_complete_exact_sha256_manifest",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_unexpected_member_even_when_checksummed",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_empty_partial_and_malformed_manifests",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_tampered_required_content",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_duplicate_checksum_manifest_keys",
        "tests/integration/test_progress06_r1_integrity_and_provenance.py::test_progress06_r1_owner_handoff_replay_revalidates_current_package_bytes",
    ),
    "CONAC-006": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_restricted_annex_requires_scoped_server_approval",
    ),
    "CONMEP-006": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_restricted_annex_requires_scoped_server_approval",
    ),
    "SECEXT-005": (
        "tests/security/test_progress06_r1_stopline_security.py::test_progress06_r1_restricted_annex_requires_scoped_server_approval",
    ),
    "CONDOC-001": (
        "tests/integration/test_progress06_r1_integrity_and_provenance.py::test_progress06_r1_document_and_interchange_sources_are_scoped_immutable_assets",
    ),
    "DATBIM-001": (
        "tests/integration/test_progress06_r1_integrity_and_provenance.py::test_progress06_r1_document_and_interchange_sources_are_scoped_immutable_assets",
    ),
    "DATEVID-002": (
        "tests/integration/test_progress06_r1_integrity_and_provenance.py::test_progress06_r1_document_and_interchange_sources_are_scoped_immutable_assets",
    ),
    "LIFPRESV-001": (
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_accepts_only_complete_exact_sha256_manifest",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_unexpected_member_even_when_checksummed",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_empty_partial_and_malformed_manifests",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_tampered_required_content",
        "tests/unit/test_progress06_r1_package_integrity.py::test_progress06_r1_vertical_verifier_rejects_duplicate_checksum_manifest_keys",
        "tests/integration/test_progress06_r1_integrity_and_provenance.py::test_progress06_r1_preservation_replay_revalidates_current_package_bytes",
    ),
    "TSTLAY-003": (
        "tests/contract/test_progress06_r1_test_matrix_isolation.py::test_progress06_r1_parallel_shards_receive_unique_database_and_runtime_roots",
    ),
    "TSTSTRAT-002": (
        "tests/contract/test_progress06_r1_test_matrix_isolation.py::test_progress06_r1_parallel_shards_receive_unique_database_and_runtime_roots",
    ),
}

STOP_LINES = (
    "cross-tenant consent revocation denied",
    "cross-tenant deficiency mutation denied",
    "independent verifier identity derived from authenticated principal",
    "restricted annex requires exact immutable server-side approval",
    "owner handoff and preservation packages require complete exact checksum coverage",
    "idempotent package replay revalidates current bytes and retained identity",
    "document and interchange provenance requires immutable in-scope assets",
    "parallel test shards use isolated runtime and database roots",
)


def _tests() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                result[f"{rel}::{node.name}"] = set(REQ_PATTERN.findall(ast.get_docstring(node) or ""))
    return result


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    ledger_doc = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    ledger = {item["requirement_id"]: item for item in ledger_doc["requirements"]}
    implementation = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))["requirements"]
    tests = _tests()
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for req_id in sorted(REMEDIATION_REQUIREMENTS):
        record = ledger.get(req_id)
        if record is None:
            findings.append({"code": "REQUIREMENT_MISSING", "requirement_id": req_id})
            continue
        if record["implementation_status"] == "NOT_STARTED":
            findings.append({"code": "REMEDIATION_REQUIREMENT_NOT_STARTED", "requirement_id": req_id})
        required_tests = DIRECT_EVIDENCE.get(req_id, ())
        declarations: list[dict[str, Any]] = []
        for test_id in required_tests:
            declared = tests.get(test_id)
            exists = declared is not None
            declares = exists and req_id in declared
            mapped = test_id in implementation.get(req_id, {}).get("test_ids", [])
            declarations.append({
                "test_id": test_id,
                "exists": exists,
                "declares_requirement_id": declares,
                "present_in_implementation_map": mapped,
                "declared_requirement_ids": sorted(declared or []),
            })
            if not exists:
                findings.append({"code": "DIRECT_TEST_MISSING", "requirement_id": req_id, "test_id": test_id})
            elif not declares:
                findings.append({"code": "DIRECT_TEST_DECLARATION_MISSING", "requirement_id": req_id, "test_id": test_id})
            if not mapped:
                findings.append({"code": "DIRECT_TEST_MAPPING_MISSING", "requirement_id": req_id, "test_id": test_id})
        records.append({
            "requirement_id": req_id,
            "priority": record["priority"],
            "status": record["implementation_status"],
            "requirement": record["text"],
            "verification_method": record.get("verification_method"),
            "implementation_files": record.get("implementation_files", []),
            "direct_tests": declarations,
            "evidence_paths": record.get("test_result_evidence_paths", []),
        })
    # The mounted viewer test remains outside this remediation and must not be promoted.
    viewer = ledger.get("PLTVIEW-007")
    if viewer is None or viewer.get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        findings.append({"code": "PLTVIEW_007_STATUS_DRIFT", "actual": None if viewer is None else viewer.get("implementation_status")})
    audit = {
        "schema": "sip.progress-06-r1-traceability-audit/v1",
        "milestone": "Progress 06-R1 security, privacy, provenance, package-integrity, and test-isolation remediation",
        "accepted_base_commit": ACCEPTED_BASE,
        "requirements_audited": records,
        "requirement_count": len(records),
        "stop_lines": list(STOP_LINES),
        "findings": findings,
        "finding_count": len(findings),
        "status": "passed_complete" if not findings else "failed",
        "progress_07_authorized": False,
        "production_authorized": False,
    }
    scope = {
        "schema": "sip.milestone-scope/v1",
        "milestone": "Progress 06-R1 narrow remediation checkpoint",
        "accepted_base_commit": ACCEPTED_BASE,
        "scope_statement": (
            "Progress 06-R1 remediates only the True North stop-line findings against the accepted Progress 06 "
            "development snapshot. It adds no Progress 07 product scope and does not promote production readiness."
        ),
        "authorized_epics": ["CON-001", "CON-002", "CON-003", "CON-004", "CON-005", "LIF-001", "LIF-002", "LIF-003", "LIF-004"],
        "included_requirements": records,
        "deferred_requirements": [],
        "included_requirement_count": len(records),
        "included_by_status": dict(sorted(Counter(item["status"] for item in records).items())),
        "unchanged_progress_06_scope": {
            "path": "requirements/MILESTONE_SCOPE_PROGRESS_06.json",
            "requirement_count": 206,
            "meaning": "The accepted Progress 06 vertical scope remains intact; only the listed stop-line controls are modified by R1.",
        },
        "explicitly_out_of_scope": [
            "Progress 07 implementation",
            "production promotion",
            "mounted PLTVIEW-007 viewer integration evidence",
            "Apple-device, LiDAR, GPU/model, cloud deployment, penetration, privacy, accessibility, usability, and legal validation",
        ],
        "acceptance_criteria": [
            *STOP_LINES,
            "complete clean-detached acceptance against the committed R1 bytes",
            "independent inner and outer verification return passed_complete with zero findings",
            "PLTVIEW-007 remains IMPLEMENTED_UNVERIFIED",
            "Progress 07 remains unauthorized and production remains NO-GO",
        ],
        "external_gaps": [
            "frozen Node/pnpm production web build and mounted viewer integration",
            "Apple, ARKit, LiDAR, and physical-device acceptance",
            "approved LingBot checkpoint, commercial model rights, CUDA/GPU, and real-scene validation",
            "executable Docker, Kubernetes, Terraform, and credentialed cloud recovery",
            "independent penetration, privacy, accessibility, usability, and legal review",
        ],
        "milestone_result": "remediation_checkpoint_candidate",
        "progress_07_authorized": False,
        "production_authorized": False,
    }
    return audit, scope

EXPECTED_ACCEPTED_AUDIT_SHA256 = "09c3377cdbc1f0110d874dc43ed65b7ee986e72d160d3bd206ad5dd6c838b255"
EXPECTED_ACCEPTED_SCOPE_SHA256 = "4e35501ae19217413c1da434deda88231e5c52c2fb5fc37ad782866c74a9bbc1"

def _verify_accepted_snapshot() -> dict[str, Any]:
    actual_audit = hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest() if AUDIT_PATH.is_file() else None
    if actual_audit != EXPECTED_ACCEPTED_AUDIT_SHA256:
        raise SystemExit("accepted historical audit drift detected for audit_progress06_r1_traceability.py")
    actual_scope = hashlib.sha256(SCOPE_PATH.read_bytes()).hexdigest() if SCOPE_PATH.is_file() else None
    if actual_scope != EXPECTED_ACCEPTED_SCOPE_SHA256:
        raise SystemExit("accepted historical scope drift detected for audit_progress06_r1_traceability.py")
    value = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if value.get("status") != "passed_complete" or value.get("finding_count") != 0:
        raise SystemExit("accepted historical traceability snapshot is not passing")
    return value

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("accepted historical milestone evidence is immutable and cannot be regenerated")
    value = _verify_accepted_snapshot()
    print(json.dumps({"status": value["status"], "requirements": value.get("requirement_count"), "findings": value["finding_count"], "snapshot": "accepted_immutable"}, sort_keys=True))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
