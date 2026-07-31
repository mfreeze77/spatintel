#!/usr/bin/env python3
"""Independently verify a SIP Progress 09 checkpoint ZIP and all retained evidence."""
from __future__ import annotations

import argparse
import json
import tempfile
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.checkpoint_common import MANIFEST_PATH, sha256_file, validate_relative_path
from tools.verify_checkpoint import (
    Verification,
    _checkpoint_facts,
    _extract_checked,
    _read_json,
    _report,
    _git,
    _validate_zip_metadata,
    _verify_evidence_wrapper,
    _verify_git_and_source,
    _verify_manifest,
)

CHECKPOINT_ID = "sip-v1.1.0-progress-09"
TOP_LEVEL = "Spatial-Intelligence-Platform-v1.1.0-progress-09"
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
EXPECTED_BASE_COMMIT = "cc3c24ca3acff704144ed7d112566a2acaa88d79"
EXPECTED_BASE_ZIP_SHA256 = "b5e479cceebf0ee5c581af0f6918ebb4b9a4d51b4a51735b6986118e03ff5014"
EXPECTED_BASE_OUTER_SHA256 = "cd3484b38973c67559569f72cb7c8f9c28ff5a0a87b90c79d73b21922854b75d"
EXPECTED_BASE_SOURCE_ROOT = "52cee93befee3f380d249d796b56dbc16cf0367a207b504ffd8d8b060920914d"
EXPECTED_MIGRATION_SHA256 = "22e3ceb60be68f02a0cfa68f832ab19ecd2c9e0c831b61f4b32bc4db5eabe8f4"
EXPECTED_MIGRATION_BYTES = 33248
EXPECTED_SCOPE_TOTAL = 17
EXPECTED_INCLUDED = 17
EXPECTED_DEFERRED = 0
MINIMUM_PYTHON_TESTS = 390
MILESTONE_WORDING = (
    "Progress 09 implements and verifies the bounded OPS-003 deployment-profile and production-shaped infrastructure layer defined by the enclosed milestone scope. "
    "Executed Compose, Kubernetes, Terraform, AWS-account, edge-device, cloud-continuity, and independent security evidence remain external; structural and synthetic checks are not production deployment evidence. "
    "Progress 10 is unauthorized and production remains NO-GO."
)
AUTHORIZED_EPICS = {"OPS-003"}
REQUIRED_EVIDENCE_CATEGORIES = {
    "source_commit", "source_root", "python_matrix", "swift_tests", "web_tests", "desktop_tests",
    "contracts", "migrations", "infrastructure", "security", "licensing", "requirements", "benchmarks",
    "demonstrations", "preservation_export", "independent_restore", "release_readiness",
}


def _verify_runtime_report(
    root: Path,
    verification: Verification,
    *,
    relative: str,
    facts: dict[str, Any],
    minimum_tests: int,
    minimum_source_checks: int = 0,
) -> None:
    report = _read_json(root / relative, verification, code="RUNTIME_REPORT_INVALID")
    if report is None:
        return
    binding = report.get("git") if isinstance(report.get("git"), dict) else {}
    if binding.get("commit") != facts.get("commit"):
        verification.fail("RUNTIME_COMMIT", "runtime report is bound to another commit", relative)
    if binding.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
        verification.fail("RUNTIME_SOURCE_ROOT", "runtime report is bound to another source root", relative)
    if binding.get("working_tree_clean_before_tests") is not True:
        verification.fail("RUNTIME_DIRTY", "runtime report did not begin from a clean worktree", relative)
    if report.get("status") not in {"passed", "passed_complete", "passed_with_external_gaps"}:
        verification.fail("RUNTIME_STATUS", f"unexpected runtime status {report.get('status')!r}", relative)
    if int(report.get("tests_passed", -1)) < minimum_tests or int(report.get("tests_failed", -1)) != 0:
        verification.fail("RUNTIME_COUNTS", "runtime result does not meet the checkpoint minimum", relative)
    if minimum_source_checks and int(report.get("source_invariant_checks", -1)) < minimum_source_checks:
        verification.fail("RUNTIME_SOURCE_CHECKS", "web source checks do not meet the checkpoint minimum", relative)


def _verify_accepted_base_ancestry(
    root: Path, verification: Verification, source_record: dict[str, Any] | None
) -> None:
    """Prove the checkpoint commit descends from the accepted Progress 08 base."""
    if not isinstance(source_record, dict):
        return
    commit = str(source_record.get("commit", ""))
    branch = str(source_record.get("branch", ""))
    bundle_record = source_record.get("git_bundle")
    bundle_relative = str(bundle_record.get("path", "")) if isinstance(bundle_record, dict) else ""
    try:
        validate_relative_path(bundle_relative)
    except ValueError as exc:
        verification.fail("BASE_ANCESTRY_BUNDLE_PATH", str(exc), "SOURCE_COMMIT.json")
        return
    bundle = root / bundle_relative
    if not bundle.is_file():
        return
    with tempfile.TemporaryDirectory(prefix="sip-progress09-ancestry-") as temporary:
        bare = Path(temporary) / "repo.git"
        initialized = _git("init", "--bare", str(bare), cwd=Path(temporary))
        if initialized.returncode != 0:
            verification.fail("BASE_ANCESTRY_GIT_INIT", initialized.stderr.decode(errors="replace"), bundle_relative)
            return
        branch_ref = f"refs/heads/{branch}"
        fetched = _git("fetch", str(bundle), f"{branch_ref}:refs/heads/checkpoint", cwd=bare)
        if fetched.returncode != 0:
            verification.fail("BASE_ANCESTRY_FETCH", fetched.stderr.decode(errors="replace"), bundle_relative)
            return
        base_exists = _git("cat-file", "-e", f"{EXPECTED_BASE_COMMIT}^{{commit}}", cwd=bare)
        if base_exists.returncode != 0:
            verification.fail("BASE_COMMIT_MISSING", "accepted Progress 08 commit is absent from the Git bundle", bundle_relative)
            return
        descendant_exists = _git("cat-file", "-e", f"{commit}^{{commit}}", cwd=bare)
        if descendant_exists.returncode != 0:
            verification.fail("CHECKPOINT_COMMIT_MISSING", "checkpoint commit is absent from the Git bundle", bundle_relative)
            return
        ancestry = _git("merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, commit, cwd=bare)
        if ancestry.returncode != 0:
            verification.fail(
                "CHECKPOINT_BASE_ANCESTRY",
                "checkpoint commit does not descend from accepted Progress 08",
                bundle_relative,
            )


def _verify_predecessor(root: Path, verification: Verification) -> None:
    relative = "PREDECESSOR_CHECKPOINT.json"
    package_record = _read_json(root / relative, verification, code="PREDECESSOR_INVALID")
    source_record = _read_json(root / "source/PREDECESSOR_CHECKPOINT.json", verification, code="SOURCE_PREDECESSOR_INVALID")
    if package_record is None or source_record is None:
        return
    if package_record != source_record:
        verification.fail("PREDECESSOR_COPY", "package and committed predecessor records differ", relative)
    accepted = package_record.get("accepted_progress_08_checkpoint")
    if not isinstance(accepted, dict):
        verification.fail("PREDECESSOR_PROGRESS08_MISSING", "accepted Progress 08 record is absent", relative)
        return
    for key, expected in (
        ("commit", EXPECTED_BASE_COMMIT),
        ("project_zip_sha256", EXPECTED_BASE_ZIP_SHA256),
        ("outer_delivery_zip_sha256", EXPECTED_BASE_OUTER_SHA256),
        ("source_tree_root_sha256", EXPECTED_BASE_SOURCE_ROOT),
    ):
        if accepted.get(key) != expected:
            verification.fail("PREDECESSOR_PROGRESS08_MISMATCH", f"{key} differs from the accepted Progress 08 base", relative)


def _scope_records(value: object) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}, {}
    included = {
        str(item.get("requirement_id")): item
        for item in value.get("included_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    deferred = {
        str(item.get("requirement_id")): item
        for item in value.get("deferred_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    return included, deferred


def _verify_scope_and_traceability(root: Path, verification: Verification, facts: dict[str, Any]) -> None:
    package_relative = "MILESTONE_SCOPE_PROGRESS_09.json"
    package_scope = _read_json(root / package_relative, verification, code="MILESTONE_SCOPE_INVALID")
    source_scope = _read_json(root / "source/requirements/MILESTONE_SCOPE_PROGRESS_09.json", verification, code="SOURCE_MILESTONE_SCOPE_INVALID")
    ledger = _read_json(root / "source/requirements/requirements-ledger.json", verification, code="LEDGER_INVALID")
    implementation = _read_json(root / "source/requirements/implementation-map.json", verification, code="IMPLEMENTATION_MAP_INVALID")
    audit = _read_json(root / "source/requirements/progress-09-traceability-audit.json", verification, code="TRACEABILITY_AUDIT_INVALID")
    if package_scope is None or source_scope is None or ledger is None or implementation is None or audit is None:
        return

    for key, expected in (
        ("checkpoint_id", CHECKPOINT_ID),
        ("source_commit", facts.get("commit")),
        ("source_tree_root_sha256", facts.get("source_tree_root_sha256")),
    ):
        if package_scope.get(key) != expected:
            verification.fail("MILESTONE_BINDING", f"{key} differs from checkpoint facts", package_relative)
    if package_scope.get("authoritative_wording") != MILESTONE_WORDING:
        verification.fail("MILESTONE_WORDING", "authoritative wording differs from the authorized Progress 09 scope", package_relative)
    if set(package_scope.get("authorized_epics", [])) != AUTHORIZED_EPICS:
        verification.fail("MILESTONE_EPICS", "authorized epic set differs", package_relative)
    if package_scope.get("accepted_base_commit") != EXPECTED_BASE_COMMIT:
        verification.fail("MILESTONE_BASE", "accepted base commit differs", package_relative)
    if package_scope.get("progress_09_authorized") is not True or package_scope.get("progress_10_authorized") is not False or package_scope.get("production_authorized") is not False:
        verification.fail("MILESTONE_POSTURE", "Progress 09, Progress 10, or production posture is incorrect", package_relative)

    included, deferred = _scope_records(package_scope)
    source_included, source_deferred = _scope_records(source_scope)
    if len(included) != EXPECTED_INCLUDED or len(deferred) != EXPECTED_DEFERRED:
        verification.fail("MILESTONE_COUNTS", f"expected {EXPECTED_INCLUDED} included and {EXPECTED_DEFERRED} deferred", package_relative)
    if set(included) & set(deferred) or len(set(included) | set(deferred)) != EXPECTED_SCOPE_TOTAL:
        verification.fail("MILESTONE_PARTITION", "Progress 09 milestone scope is not an exact 17-requirement partition", package_relative)
    if set(included) != set(source_included) or set(deferred) != set(source_deferred):
        verification.fail("MILESTONE_SOURCE_DRIFT", "packaged and committed milestone partitions differ", package_relative)

    raw_requirements = ledger.get("requirements") if isinstance(ledger.get("requirements"), list) else []
    ledger_by_id = {str(item.get("requirement_id")): item for item in raw_requirements if isinstance(item, dict)}
    if len(ledger_by_id) != 1028:
        verification.fail("LEDGER_COUNT", f"expected 1028 requirements, found {len(ledger_by_id)}", "source/requirements/requirements-ledger.json")
    for requirement_id, item in {**included, **deferred}.items():
        ledger_item = ledger_by_id.get(requirement_id)
        if ledger_item is None:
            verification.fail("MILESTONE_LEDGER_MISSING", f"{requirement_id} is absent from the ledger", package_relative)
            continue
        if item.get("status") != ledger_item.get("implementation_status"):
            verification.fail("MILESTONE_STATUS_DRIFT", f"{requirement_id} status differs from the ledger", package_relative)
        if requirement_id in deferred and item.get("status") not in {"NOT_STARTED", "EXTERNAL_VALIDATION_REQUIRED"}:
            verification.fail("MILESTONE_DEFERRED_STATUS", f"{requirement_id} has an invalid deferred status", package_relative)
        if requirement_id in included and item.get("status") == "NOT_STARTED":
            verification.fail("MILESTONE_INCLUDED_NOT_STARTED", f"{requirement_id} is included but NOT_STARTED", package_relative)
        if item.get("status") == "VERIFIED" and not item.get("evidence_paths"):
            verification.fail("MILESTONE_VERIFIED_NO_EVIDENCE", f"{requirement_id} lacks evidence", package_relative)

    implementation_records = implementation.get("requirements") if isinstance(implementation.get("requirements"), dict) else {}
    pltview = implementation_records.get("PLTVIEW-007") if isinstance(implementation_records, dict) else None
    if not isinstance(pltview, dict) or pltview.get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        verification.fail("PLTVIEW_007_OVERCLAIM", "PLTVIEW-007 must remain IMPLEMENTED_UNVERIFIED", "source/requirements/implementation-map.json")
    if audit.get("status") != "passed_complete" or int(audit.get("finding_count", -1)) != 0:
        verification.fail("TRACEABILITY_AUDIT", "Progress 09 traceability audit did not pass with zero findings", "source/requirements/progress-09-traceability-audit.json")
    if int(audit.get("requirement_count", -1)) != EXPECTED_SCOPE_TOTAL:
        verification.fail("TRACEABILITY_SCOPE", "Progress 09 traceability audit did not cover all 17 scoped requirements", "source/requirements/progress-09-traceability-audit.json")
    if audit.get("progress_10_authorized") is not False or audit.get("production_authorized") is not False:
        verification.fail("TRACEABILITY_POSTURE", "traceability audit incorrectly authorizes Progress 10 or production", "source/requirements/progress-09-traceability-audit.json")
    audited = audit.get("requirements_audited") if isinstance(audit.get("requirements_audited"), list) else []
    if len(audited) != EXPECTED_SCOPE_TOTAL:
        verification.fail("TRACEABILITY_RECORD_COUNT", "traceability audit record count differs", "source/requirements/progress-09-traceability-audit.json")
    if {str(item.get("requirement_id")) for item in audited if isinstance(item, dict)} != (set(included) | set(deferred)):
        verification.fail("TRACEABILITY_SCOPE_DRIFT", "traceability audit requirement set differs from the Progress 09 milestone scope", "source/requirements/progress-09-traceability-audit.json")
    for record in audited:
        if not isinstance(record, dict):
            verification.fail("TRACEABILITY_RECORD", "audit record must be an object", "source/requirements/progress-09-traceability-audit.json")
            continue
        direct = record.get("direct_tests") if isinstance(record.get("direct_tests"), list) else []
        requirement_id = str(record.get("requirement_id"))
        if requirement_id in included and not direct:
            verification.fail("TRACEABILITY_DIRECT_EVIDENCE", f"{record.get('requirement_id')} has no direct Progress 09 evidence", "source/requirements/progress-09-traceability-audit.json")
        for test in direct:
            if not isinstance(test, dict) or test.get("exists") is not True or test.get("declares_requirement_id") is not True or test.get("present_in_implementation_map") is not True:
                verification.fail("TRACEABILITY_DECLARATION", f"{record.get('requirement_id')} has invalid direct test evidence", "source/requirements/progress-09-traceability-audit.json")


def _verify_matrix(root: Path, verification: Verification, facts: dict[str, Any]) -> None:
    relative = "build/reports/test-matrix.json"
    matrix = _read_json(root / relative, verification, code="PYTHON_MATRIX_INVALID")
    if matrix is None:
        return
    evidence = matrix.get("evidence") if isinstance(matrix.get("evidence"), dict) else {}
    totals = matrix.get("totals") if isinstance(matrix.get("totals"), dict) else {}
    if matrix.get("status") not in {"passed", "passed_complete"}:
        verification.fail("PYTHON_MATRIX_STATUS", "Python matrix is not passing", relative)
    if evidence.get("git_commit") != facts.get("commit") or evidence.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
        verification.fail("PYTHON_MATRIX_BINDING", "Python matrix is bound to another source", relative)
    if evidence.get("git_dirty") is not False:
        verification.fail("PYTHON_MATRIX_DIRTY", "Python matrix was not executed from a clean worktree", relative)
    tests = int(totals.get("tests", -1))
    if tests < MINIMUM_PYTHON_TESTS or tests != int(facts.get("python_tests_passed", -2)):
        verification.fail("PYTHON_MATRIX_COUNT", "Python matrix count is below the checkpoint baseline or differs from facts", relative)
    for key in ("failures", "errors", "skipped"):
        if int(totals.get(key, -1)) != 0:
            verification.fail("PYTHON_MATRIX_RESULT", f"Python matrix {key} must be zero", relative)
    results = matrix.get("results") if isinstance(matrix.get("results"), list) else []
    if len(results) != 10:
        verification.fail("PYTHON_MATRIX_SUITES", "expected ten isolated suite results", relative)
    summed = Counter()
    for result in results:
        if not isinstance(result, dict):
            verification.fail("PYTHON_SUITE_RECORD", "suite result must be an object", relative)
            continue
        for key in ("tests", "failures", "errors", "skipped"):
            summed[key] += int(result.get(key, 0))
        if result.get("status") not in {"passed", "passed_complete"} or int(result.get("exit_code", -1)) != 0:
            verification.fail("PYTHON_SUITE_STATUS", f"suite {result.get('name')} did not pass", relative)
        if result.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
            verification.fail("PYTHON_SUITE_SOURCE_ROOT", f"suite {result.get('name')} is bound to another source root", relative)
        for path_key, hash_key in (("junit_path", "junit_sha256"), ("log_path", "log_sha256"), ("shard_manifest_path", "shard_manifest_sha256")):
            path_value = result.get(path_key)
            expected_hash = result.get(hash_key)
            if not isinstance(path_value, str) or not isinstance(expected_hash, str):
                verification.fail("PYTHON_SUITE_ARTIFACT", f"suite {result.get('name')} lacks {path_key}", relative)
                continue
            try:
                validate_relative_path(path_value)
            except ValueError as exc:
                verification.fail("PYTHON_SUITE_PATH", str(exc), relative)
                continue
            artifact = root / path_value
            if not artifact.is_file():
                verification.fail("PYTHON_SUITE_ARTIFACT_MISSING", f"missing {path_value}", relative)
            elif sha256_file(artifact) != expected_hash:
                verification.fail("PYTHON_SUITE_ARTIFACT_HASH", f"hash differs for {path_value}", relative)
    for key in ("tests", "failures", "errors", "skipped"):
        if summed[key] != int(totals.get(key, -1)):
            verification.fail("PYTHON_MATRIX_SUM", f"suite sum for {key} differs from totals", relative)


def _verify_acceptance(root: Path, verification: Verification, facts: dict[str, Any]) -> None:
    relative = "build/reports/checkpoint-acceptance-gates.json"
    report = _read_json(root / relative, verification, code="ACCEPTANCE_INVALID")
    if report is None:
        return
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    if report.get("checkpoint_id") != CHECKPOINT_ID:
        verification.fail("ACCEPTANCE_CHECKPOINT", "acceptance identifies another checkpoint", relative)
    if source.get("commit") != facts.get("commit") or source.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
        verification.fail("ACCEPTANCE_BINDING", "acceptance is bound to another source", relative)
    if source.get("working_tree_clean") is not True:
        verification.fail("ACCEPTANCE_DIRTY", "acceptance did not run from a clean worktree", relative)
    if report.get("status") not in {"passed_complete", "passed_with_external_gaps"} or int(report.get("required_failure_count", -1)) != 0:
        verification.fail("ACCEPTANCE_STATUS", "required local acceptance did not pass", relative)
    if report.get("progress_09_authorized") is not True or report.get("progress_10_authorized") is not False or report.get("production_authorized") is not False:
        verification.fail("ACCEPTANCE_POSTURE", "acceptance incorrectly authorizes a later phase or production", relative)
    results = report.get("results") if isinstance(report.get("results"), list) else []
    if not results:
        verification.fail("ACCEPTANCE_RESULTS", "acceptance results are absent", relative)
    for item in results:
        if not isinstance(item, dict):
            verification.fail("ACCEPTANCE_RESULT", "acceptance result must be an object", relative)
            continue
        if item.get("execution_status") not in {"completed_successfully", "completed_with_error"}:
            verification.fail("ACCEPTANCE_EXECUTION_STATUS", "execution status is invalid", relative)
        if item.get("control_status") not in {"passed_complete", "passed_with_external_gaps", "blocked", "failed"}:
            verification.fail("ACCEPTANCE_CONTROL_STATUS", "control status is invalid", relative)
        if item.get("status") != item.get("control_status"):
            verification.fail("ACCEPTANCE_STATUS_COLLAPSED", "legacy status does not mirror control status", relative)
        child_path = item.get("child_report_path")
        child_hash = item.get("child_report_sha256")
        if child_path is not None or child_hash is not None:
            if not isinstance(child_path, str) or not isinstance(child_hash, str):
                verification.fail("ACCEPTANCE_CHILD_RECORD", "child report path/hash must be retained together", relative)
            else:
                try:
                    validate_relative_path(child_path)
                except ValueError as exc:
                    verification.fail("ACCEPTANCE_CHILD_PATH", str(exc), relative)
                else:
                    child = root / child_path
                    if not child.is_file():
                        verification.fail("ACCEPTANCE_CHILD_MISSING", f"missing {child_path}", relative)
                    elif sha256_file(child) != child_hash:
                        verification.fail("ACCEPTANCE_CHILD_HASH", f"hash differs for {child_path}", relative)

    readiness_relative = "build/reports/release-readiness-progress-09.json"
    readiness = _read_json(root / readiness_relative, verification, code="READINESS_INVALID")
    if readiness:
        source = readiness.get("source") if isinstance(readiness.get("source"), dict) else {}
        if readiness.get("status") != "blocked" or readiness.get("production_authorized") is not False or readiness.get("progress_09_authorized") is not True or readiness.get("progress_10_authorized") is not False:
            verification.fail("READINESS_POSTURE", "release readiness must remain blocked", readiness_relative)
        if source.get("commit") != facts.get("commit") or source.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
            verification.fail("READINESS_BINDING", "release readiness is bound to another source", readiness_relative)
        next_action = str(readiness.get("next_action", ""))
        if "True North" not in next_action or "Progress 09" not in next_action:
            verification.fail("READINESS_STALE", "release-readiness next action is stale", readiness_relative)


def _verify_migration(root: Path, verification: Verification) -> None:
    relative = "source/migrations/versions/0019_progress09_deployment_profiles.py"
    migration = root / relative
    if not migration.is_file():
        verification.fail("MIGRATION_0019_MISSING", "append-only Progress 09 migration is missing", relative)
        return
    if migration.stat().st_size != EXPECTED_MIGRATION_BYTES or sha256_file(migration) != EXPECTED_MIGRATION_SHA256:
        verification.fail("MIGRATION_0019_HASH", "Progress 09 migration bytes differ from the locked revision", relative)
    manifest = _read_json(root / "source/migrations/manifest.json", verification, code="MIGRATION_MANIFEST_INVALID")
    if manifest is None:
        return
    records = manifest.get("migrations") if isinstance(manifest.get("migrations"), list) else []
    matched = [item for item in records if isinstance(item, dict) and item.get("path") == "migrations/versions/0019_progress09_deployment_profiles.py"]
    if len(matched) != 1:
        verification.fail("MIGRATION_0019_MANIFEST", "migration manifest does not contain exactly one 0019 record", "source/migrations/manifest.json")
    else:
        item = matched[0]
        if int(item.get("byte_count", -1)) != EXPECTED_MIGRATION_BYTES or item.get("sha256") != EXPECTED_MIGRATION_SHA256:
            verification.fail("MIGRATION_0019_MANIFEST_HASH", "migration manifest lock differs", "source/migrations/manifest.json")


def _verify_status_and_evidence(root: Path, verification: Verification, source_record: dict[str, Any] | None) -> None:
    checkpoint_relative = "build/checkpoints/progress-09.json"
    checkpoint = _read_json(root / checkpoint_relative, verification, code="CHECKPOINT_INVALID")
    if checkpoint is None:
        return
    facts = _checkpoint_facts(checkpoint)
    required = {
        "checkpoint_id", "branch", "commit", "parent", "tree", "source_tree_root_sha256", "working_tree_clean",
        "tested_detached_worktree", "python_tests_passed", "swift_tests_passed", "web_runtime_tests_passed",
        "web_source_checks_passed", "desktop_tests_passed", "requirements_total", "requirements_by_status",
        "progress_09_authorized", "progress_10_authorized", "production_authorized",
    }
    for field in sorted(required - set(facts)):
        verification.fail("CHECKPOINT_FACT_MISSING", f"missing fact {field}", checkpoint_relative)
    if facts.get("checkpoint_id") != CHECKPOINT_ID or facts.get("branch") != "progress-09-deployment":
        verification.fail("CHECKPOINT_IDENTITY", "checkpoint ID or branch differs", checkpoint_relative)
    if not isinstance(facts.get("parent"), str) or len(str(facts.get("parent"))) != 40:
        verification.fail("CHECKPOINT_PARENT", "checkpoint first-parent identity is missing or malformed", checkpoint_relative)
    if facts.get("working_tree_clean") is not True or facts.get("tested_detached_worktree") is not True:
        verification.fail("CHECKPOINT_WORKTREE", "checkpoint must prove a clean detached acceptance worktree", checkpoint_relative)
    if int(facts.get("python_tests_passed", -1)) < MINIMUM_PYTHON_TESTS:
        verification.fail("CHECKPOINT_TEST_BASELINE", "Python test count is below the Progress 09 minimum", checkpoint_relative)
    if int(facts.get("requirements_total", -1)) != 1028:
        verification.fail("CHECKPOINT_REQUIREMENTS", "requirements total differs from 1,028", checkpoint_relative)
    if facts.get("progress_09_authorized") is not True or facts.get("progress_10_authorized") is not False or facts.get("production_authorized") is not False:
        verification.fail("CHECKPOINT_POSTURE", "Progress 09, Progress 10, or production posture is incorrect", checkpoint_relative)
    if checkpoint.get("milestone_wording") != MILESTONE_WORDING:
        verification.fail("CHECKPOINT_WORDING", "checkpoint wording differs from the authorized Progress 09 scope", checkpoint_relative)
    if source_record:
        for key in ("commit", "parent", "tree", "branch", "source_tree_root_sha256"):
            if facts.get(key) != source_record.get(key):
                verification.fail("CHECKPOINT_SOURCE_CONTRADICTION", f"{key} differs from SOURCE_COMMIT.json", checkpoint_relative)

    latest = _read_json(root / "build/release/latest.json", verification, code="LATEST_INVALID")
    if latest:
        for key in ("checkpoint_id", "commit", "tree", "branch", "source_tree_root_sha256"):
            if latest.get(key) != facts.get(key):
                verification.fail("LATEST_CONTRADICTION", f"latest.{key} differs from checkpoint facts", "build/release/latest.json")
        if latest.get("progress_09_authorized") is not True or latest.get("progress_10_authorized") is not False or latest.get("production_authorized") is not False:
            verification.fail("LATEST_POSTURE", "latest record has incorrect Progress 09/10 or production posture", "build/release/latest.json")

    _verify_scope_and_traceability(root, verification, facts)
    _verify_matrix(root, verification, facts)
    _verify_runtime_report(root, verification, relative="build/reports/swift-test-report.json", facts=facts, minimum_tests=13)
    _verify_runtime_report(root, verification, relative="build/reports/web-runtime-test-report.json", facts=facts, minimum_tests=14, minimum_source_checks=35)
    _verify_runtime_report(root, verification, relative="build/reports/desktop-review-test-report.json", facts=facts, minimum_tests=17)
    _verify_acceptance(root, verification, facts)
    _verify_migration(root, verification)

    index_relative = "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json"
    index = _read_json(root / index_relative, verification, code="EVIDENCE_INDEX_INVALID")
    if index:
        if index.get("checkpoint_id") != CHECKPOINT_ID or index.get("source_commit") != facts.get("commit") or index.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
            verification.fail("EVIDENCE_INDEX_BINDING", "authoritative evidence index is bound to another source", index_relative)
        entries = index.get("authoritative") if isinstance(index.get("authoritative"), dict) else {}
        if set(entries) != REQUIRED_EVIDENCE_CATEGORIES:
            verification.fail("EVIDENCE_CATEGORIES", f"expected {sorted(REQUIRED_EVIDENCE_CATEGORIES)}, got {sorted(entries)}", index_relative)
        seen: set[str] = set()
        for category, entry in entries.items():
            if not isinstance(entry, dict):
                verification.fail("EVIDENCE_ENTRY", f"{category} must be an object", index_relative)
                continue
            relative = str(entry.get("path", ""))
            if relative in seen:
                verification.fail("EVIDENCE_DUPLICATE_PATH", f"duplicate authoritative wrapper {relative}", index_relative)
            seen.add(relative)
            try:
                validate_relative_path(relative)
            except ValueError as exc:
                verification.fail("EVIDENCE_PATH", str(exc), index_relative)
                continue
            wrapper = root / relative
            if not wrapper.is_file():
                verification.fail("EVIDENCE_WRAPPER_MISSING", f"missing {relative}", index_relative)
                continue
            if sha256_file(wrapper) != entry.get("sha256"):
                verification.fail("EVIDENCE_WRAPPER_HASH", f"hash differs for {relative}", index_relative)
            _verify_evidence_wrapper(root=root, category=category, relative=relative, facts=facts, verification=verification)

    required_docs = (
        "IMPLEMENTATION_STATUS.md", "RESUME_IMPLEMENTATION.md", "requirements/coverage-report.md",
        "FINAL_IMPLEMENTATION_REPORT.md", "PROGRESS_09_MILESTONE_REPORT.md",
    )
    for relative in required_docs:
        path = root / relative
        if not path.is_file():
            verification.fail("STATUS_DOCUMENT_MISSING", "required checkpoint document is absent", relative)
            continue
        text = path.read_text(encoding="utf-8")
        for value, label in (
            (facts.get("commit"), "commit"),
            (facts.get("source_tree_root_sha256"), "source root"),
            (str(facts.get("python_tests_passed")), "Python test count"),
        ):
            if value is not None and str(value) not in text:
                verification.fail("STATUS_DOCUMENT_STALE", f"document lacks current {label}", relative)
        if "Progress 09" not in text or "Progress 10" not in text or not any(token in text for token in ("NO-GO", "blocked", "unauthorized", "not authorized")):
            verification.fail("STATUS_DOCUMENT_POSTURE", "document does not retain the blocked later-phase posture", relative)
    readme = root / "README_CHECKPOINT.md"
    if not readme.is_file() or f"git clone -b {facts.get('branch')}" not in readme.read_text(encoding="utf-8"):
        verification.fail("BUNDLE_CLONE_DOCUMENTATION", "checkpoint README lacks explicit branch clone instructions", "README_CHECKPOINT.md")
    verification.facts.update({
        "checkpoint_id": facts.get("checkpoint_id"),
        "source_commit": facts.get("commit"),
        "source_tree_root_sha256": facts.get("source_tree_root_sha256"),
        "python_tests_passed": facts.get("python_tests_passed"),
        "progress_09_authorized": True,
        "progress_10_authorized": False,
        "production_authorized": False,
    })


def verify_archive(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    verification = Verification(archive_path)
    if not archive_path.is_file():
        verification.fail("ARCHIVE_MISSING", "checkpoint ZIP does not exist", str(archive_path))
        return _report(verification)
    verification.facts["archive_sha256"] = sha256_file(archive_path)
    verification.facts["archive_size"] = archive_path.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-progress09-verify-") as temporary:
        extract_root = Path(temporary) / "extract"
        extract_root.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                top_level, _ = _validate_zip_metadata(archive, verification)
                _extract_checked(archive, extract_root, verification)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            verification.fail("ZIP_INVALID", str(exc), str(archive_path))
            return _report(verification)
        if top_level is None:
            return _report(verification)
        verification.facts["top_level"] = top_level
        if top_level != TOP_LEVEL:
            verification.fail("ZIP_TOP_LEVEL_NAME", f"expected {TOP_LEVEL}, got {top_level}")
        root = extract_root / top_level
        manifest = _verify_manifest(root, verification)
        if manifest:
            if manifest.get("top_level") != top_level:
                verification.fail("MANIFEST_TOP_LEVEL", "manifest top level differs", MANIFEST_PATH)
            if manifest.get("checkpoint_id") != CHECKPOINT_ID:
                verification.fail("MANIFEST_CHECKPOINT", "manifest identifies another checkpoint", MANIFEST_PATH)
        spec = root / "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
        if not spec.is_file():
            verification.fail("SPEC_MISSING", "authoritative specification ZIP is absent", "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip")
        elif sha256_file(spec) != EXPECTED_SPEC_SHA256:
            verification.fail("SPEC_HASH", "authoritative specification hash differs", "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip")
        else:
            verification.facts["specification_sha256"] = EXPECTED_SPEC_SHA256
        source_record = _verify_git_and_source(root, verification)
        _verify_accepted_base_ancestry(root, verification, source_record)
        if source_record and source_record.get("checkpoint_id") != CHECKPOINT_ID:
            verification.fail("SOURCE_CHECKPOINT", "SOURCE_COMMIT.json identifies another checkpoint", "SOURCE_COMMIT.json")
        _verify_predecessor(root, verification)
        _verify_status_and_evidence(root, verification, source_record)
    return _report(verification)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_archive(args.archive)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
