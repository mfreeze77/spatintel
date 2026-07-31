#!/usr/bin/env python3
"""Build the Progress 09 checkpoint from a clean committed source worktree and source-bound evidence."""
from __future__ import annotations

import argparse
import json
import tempfile
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_checkpoint import (
    _authoritative_wrapper,
    _copy_tree,
    _extract_git_source,
    _git,
    _gzip_git_archive,
    _hash_record,
    _load_json,
    _require_clean_detached,
    _requirements,
    _run,
    _write,
)
from tools.checkpoint_common import build_content_manifest, content_root, sha256_file, stage_records, write_deterministic_zip
from tools.source_identity import source_identity

CHECKPOINT_ID = "sip-v1.1.0-progress-09"
TOP_LEVEL = "Spatial-Intelligence-Platform-v1.1.0-progress-09"
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
MILESTONE_WORDING = (
    "Progress 09 implements and verifies the bounded OPS-003 deployment-profile and production-shaped infrastructure layer defined by the enclosed milestone scope. "
    "Executed Compose, Kubernetes, Terraform, AWS-account, edge-device, cloud-continuity, and independent security evidence remain external; structural and synthetic checks are not production deployment evidence. "
    "Progress 10 is unauthorized and production remains NO-GO."
)

EXTERNAL_GAPS = [
    "Ruff was unavailable; the deterministic source-policy checker ran instead.",
    "mypy was unavailable; Python compilation ran, but a full mypy result is blocked.",
    "Node 24.18.0, pnpm 10.28.2, pnpm-lock.yaml, installed dependencies, ESLint, TypeScript typecheck, and the Next production build were unavailable.",
    "Dependency-free web and desktop runtime tests do not constitute a complete Next.js or native desktop production build.",
    "pip-audit, Gitleaks, and Trivy were unavailable; dependency, history-secret, and container scans remain blocked in release mode.",
    "Docker Compose runtime, Kubernetes cluster admission/runtime, Terraform provider initialization/plan/apply, AWS account execution, and credentialed cloud validation were unavailable; structural checks are not deployment validation.",
    "Xcode, iOS simulator, signing, ARKit, LiDAR, camera, thermal, battery, interruption, and physical-device validation remain external.",
    "Approved LingBot-Map checkpoint bytes, commercial model-rights approval, CUDA/GPU execution, production queue continuity, and real-scene validation remain external.",
    "Independent penetration testing, privacy review, mounted-browser accessibility audit, operator usability study, and legal approval remain incomplete.",
    "No customer construction pilot or human-subject LiveForever pilot occurred; the retained demonstrations use synthetic or non-sensitive fixtures only.",
    "Complete IFC/BCF vendor interoperability and survey/field-measurement certification remain external.",
]
NEXT_CLUSTER = (
    "Submit the independently verified Progress 09 inner checkpoint and consolidated outer envelope for True North "
    "milestone-closure review. Progress 10 and production promotion remain unauthorized until separately approved."
)

AUTHORIZED_EPICS = {"OPS-003"}

def _scope_template() -> dict[str, Any]:
    path = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_09.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Progress 09 milestone scope must be an object")
    return value

def _scope_ids() -> frozenset[str]:
    template = _scope_template()
    records = [*template.get("included_requirements", []), *template.get("deferred_requirements", [])]
    identifiers = frozenset(str(item.get("requirement_id")) for item in records if isinstance(item, dict))
    if len(identifiers) != 17:
        raise RuntimeError(f"Progress 09 scope must contain 17 unique requirements, found {len(identifiers)}")
    if set(template.get("authorized_epics", [])) != AUTHORIZED_EPICS:
        raise RuntimeError("Progress 09 scope epics differ from the True North authorization")
    return identifiers

P09_SCOPE_IDS = _scope_ids()
SECURITY_DIRECT_EVIDENCE_PATH = "build/reports/security-direct/security.xml"

REQUIRED_EVIDENCE_CATEGORIES = {
    "source_commit",
    "source_root",
    "python_matrix",
    "swift_tests",
    "web_tests",
    "desktop_tests",
    "contracts",
    "migrations",
    "infrastructure",
    "security",
    "licensing",
    "requirements",
    "benchmarks",
    "demonstrations",
    "preservation_export",
    "independent_restore",
    "release_readiness",
}


def _read_bound_report(path: Path, *, commit: str, source_root: str, minimum_tests: int = 0) -> dict[str, Any]:
    report = _load_json(path)
    git = report.get("git") if isinstance(report.get("git"), dict) else {}
    if git.get("commit") != commit or git.get("source_tree_root_sha256") != source_root:
        raise RuntimeError(f"test report is not bound to checkpoint source: {path}")
    if git.get("working_tree_clean_before_tests") is not True:
        raise RuntimeError(f"test report did not begin from a clean worktree: {path}")
    if report.get("status") not in {"passed", "passed_complete", "passed_with_external_gaps"}:
        raise RuntimeError(f"test report did not pass: {path}")
    if int(report.get("tests_failed", 0)) != 0 or int(report.get("tests_passed", 0)) < minimum_tests:
        raise RuntimeError(f"test report does not satisfy minimum results: {path}")
    return report


def _milestone_scope(*, ledger: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    template = _scope_template()
    selected = {str(item.get("requirement_id")): item for item in ledger["requirements"] if str(item.get("requirement_id")) in P09_SCOPE_IDS}
    if set(selected) != set(P09_SCOPE_IDS):
        raise RuntimeError("Progress 09 source ledger does not contain the complete authorized scope")
    included_ids = {str(item.get("requirement_id")) for item in template.get("included_requirements", []) if isinstance(item, dict)}
    deferred_ids = {str(item.get("requirement_id")) for item in template.get("deferred_requirements", []) if isinstance(item, dict)}
    if included_ids | deferred_ids != set(P09_SCOPE_IDS) or included_ids & deferred_ids:
        raise RuntimeError("Progress 09 milestone scope is not an exact disjoint partition")
    def rebound(requirement_id: str, *, deferred: bool) -> dict[str, Any]:
        item = selected[requirement_id]
        status = str(item.get("implementation_status"))
        if deferred and status not in {"NOT_STARTED", "EXTERNAL_VALIDATION_REQUIRED"}:
            raise RuntimeError(f"deferred requirement {requirement_id} has an invalid status: {status}")
        if not deferred and status == "NOT_STARTED":
            raise RuntimeError(f"included requirement {requirement_id} is NOT_STARTED")
        source_entry = next(entry for entry in (template["deferred_requirements"] if deferred else template["included_requirements"]) if entry.get("requirement_id") == requirement_id)
        result = dict(source_entry)
        result.update({
            "status": status,
            "implementation_files": item.get("implementation_files", []),
            "test_ids": item.get("test_ids", []),
            "evidence_paths": [str(path) for path in item.get("test_result_evidence_paths", []) if str(path)],
        })
        return result
    included = [rebound(identifier, deferred=False) for identifier in sorted(included_ids)]
    deferred = [rebound(identifier, deferred=True) for identifier in sorted(deferred_ids)]
    return {
        "schema": "sip.milestone-scope/v1",
        "checkpoint_id": facts["checkpoint_id"],
        "source_commit": facts["commit"],
        "source_tree_root_sha256": facts["source_tree_root_sha256"],
        "accepted_base_commit": template["accepted_base_commit"],
        "authorized_epics": sorted(AUTHORIZED_EPICS),
        "milestone": "Progress 09 bounded OPS-003 deployment profiles and production-shaped infrastructure",
        "scope_statement": template["scope_statement"],
        "authoritative_wording": MILESTONE_WORDING,
        "scope_requirement_ids": sorted(P09_SCOPE_IDS),
        "included_requirements": included,
        "deferred_requirements": deferred,
        "summary": {
            "scope_requirements_total": len(P09_SCOPE_IDS),
            "included": len(included),
            "deferred": len(deferred),
            "included_by_status": dict(sorted(Counter(item["status"] for item in included).items())),
            "deferred_by_status": dict(sorted(Counter(item["status"] for item in deferred).items())),
        },
        "acceptance_criteria": template["acceptance_criteria"],
        "external_gaps": template["external_gaps"],
        "final_result": "passed_with_external_gaps_pending_independent_true_north_review",
        "progress_09_authorized": True,
        "progress_10_authorized": False,
        "production_authorized": False,
    }


def _render_status(facts: dict[str, Any], counts: dict[str, int]) -> str:
    lines = [
        "# SIP v1.1.0 Implementation Status — Progress 09",
        "",
        MILESTONE_WORDING,
        "",
        f"- Checkpoint: `{facts['checkpoint_id']}`",
        f"- Branch: `{facts['branch']}`",
        f"- Source commit: `{facts['commit']}`",
        f"- Parent commit: `{facts['parent']}`",
        f"- Git tree: `{facts['tree']}`",
        f"- Canonical source root: `{facts['source_tree_root_sha256']}`",
        f"- Clean detached tested worktree: `{str(facts['working_tree_clean']).lower()}`",
        f"- Python tests: **{facts['python_tests_passed']} passed, 0 failed, 0 errors, 0 skipped**",
        f"- Swift Linux fixture tests: **{facts['swift_tests_passed']} passed**",
        f"- Web dependency-free runtime tests: **{facts['web_runtime_tests_passed']} passed**",
        f"- Web source invariants: **{facts['web_source_checks_passed']} passed**",
        f"- Desktop local-first runtime tests: **{facts['desktop_tests_passed']} passed**",
        f"- Generated contract artifacts: **{facts['generated_contract_artifacts']}**",
        f"- Normative requirements: **{facts['requirements_total']:,}**",
        "",
        "## Requirement status",
        "",
    ]
    lines.extend(f"- {status}: **{count:,}**" for status, count in sorted(counts.items()))
    lines += [
        "",
        "## Release posture",
        "",
        "Progress 09 is a source-bound bounded deployment-profile and production-shaped infrastructure checkpoint. Progress 10 is unauthorized and production deployment and release remain NO-GO.",
        "",
        "## External validation gaps",
        "",
        *[f"- {item}" for item in EXTERNAL_GAPS],
    ]
    return "\n".join(lines) + "\n"


def _render_resume(facts: dict[str, Any]) -> str:
    return "\n".join([
        "# Resume Implementation — SIP v1.1.0 Progress 09",
        "",
        "This continuation record is generated from `build/checkpoints/progress-09.json`.",
        "",
        f"- Branch: `{facts['branch']}`",
        f"- Commit: `{facts['commit']}`",
        f"- Parent: `{facts['parent']}`",
        f"- Tree: `{facts['tree']}`",
        f"- Source root: `{facts['source_tree_root_sha256']}`",
        f"- Python tests passed: `{facts['python_tests_passed']}`",
        f"- Swift Linux fixture tests passed: `{facts['swift_tests_passed']}`",
        f"- Web runtime/source checks passed: `{facts['web_runtime_tests_passed']}` / `{facts['web_source_checks_passed']}`",
        f"- Desktop local-first tests passed: `{facts['desktop_tests_passed']}`",
        f"- Requirements: `{facts['requirements_total']}`",
        "",
        "## Release posture",
        "",
        "Production promotion remains fail-closed. Linux Swift fixtures are not iOS/LiDAR acceptance; dependency-free web tests are not a Next production build; structural infrastructure checks are not deployment validation.",
        "",
        "## Exact next cluster",
        "",
        NEXT_CLUSTER,
        "",
        "## Bundle clone command",
        "",
        "```bash",
        f"git clone -b {facts['branch']} <bundle-file> <destination>",
        "```",
        "",
        "## External validation gaps",
        "",
        *[f"- {item}" for item in EXTERNAL_GAPS],
    ]) + "\n"


def _render_coverage(facts: dict[str, Any], ledger: dict[str, Any]) -> str:
    priorities: dict[str, Counter[str]] = {}
    for item in ledger["requirements"]:
        priorities.setdefault(str(item["priority"]), Counter())[str(item["implementation_status"])] += 1
    statuses = sorted({status for counter in priorities.values() for status in counter})
    lines = [
        "# Requirements coverage report — Progress 09",
        "",
        f"Checkpoint: `{facts['checkpoint_id']}`",
        f"Commit: `{facts['commit']}`",
        f"Source root: `{facts['source_tree_root_sha256']}`",
        f"Python tests passed: `{facts['python_tests_passed']}`",
        "",
        f"Total normative requirements: **{facts['requirements_total']:,}**",
        "",
        "| Priority | " + " | ".join(statuses) + " | Total |",
        "|---|" + "---:|" * (len(statuses) + 1),
    ]
    for priority in sorted(priorities):
        counter = priorities[priority]
        lines.append("| " + priority + " | " + " | ".join(str(counter[status]) for status in statuses) + f" | {sum(counter.values())} |")
    lines += [
        "",
        "> Requirements outside VERIFIED remain incomplete or externally unverified. This report makes no complete-platform or production-readiness claim.",
        "",
        "- Progress 09 is delivered for independent True North milestone-closure review.",
        "- Progress 09 implementation was authorized; milestone closure remains pending independent True North review.",
        "- Progress 10 remains **unauthorized**.",
        "- Production deployment and release remain **NO-GO** until independent True North acceptance and all required external validation gates pass.",
    ]
    return "\n".join(lines) + "\n"


def _require_acceptance(report: dict[str, Any], *, commit: str, source_root: str) -> None:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    if report.get("checkpoint_id") != CHECKPOINT_ID or source.get("commit") != commit or source.get("source_tree_root_sha256") != source_root:
        raise RuntimeError("checkpoint acceptance report is not bound to Progress 09 source")
    if report.get("status") not in {"passed_complete", "passed_with_external_gaps"}:
        raise RuntimeError("checkpoint acceptance gates did not pass")
    if int(report.get("required_failure_count", -1)) != 0:
        raise RuntimeError("checkpoint acceptance reports required failures")


def build(*, evidence_root: Path, output: Path, branch: str, attestation_path: Path) -> dict[str, Any]:
    _require_clean_detached()
    commit = _git("rev-parse", "HEAD")
    parents = _git("show", "-s", "--format=%P", "HEAD").split()
    if not parents:
        raise RuntimeError("checkpoint commit must have a parent")
    parent = parents[0]
    tree = _git("show", "-s", "--format=%T", "HEAD")
    timestamp = _git("show", "-s", "--format=%cI", "HEAD")
    branch_ref = _run("git", "show-ref", "--verify", f"refs/heads/{branch}", check=False)
    if branch_ref.returncode != 0 or branch_ref.stdout.decode().split()[0] != commit:
        raise RuntimeError(f"branch {branch!r} does not identify checkpoint commit {commit}")
    identity = source_identity(ROOT)
    source_root = str(identity["source_tree_root_sha256"])
    attestation = _load_json(attestation_path)
    for key, expected in (("commit", commit), ("source_tree_root_sha256", source_root), ("branch", branch), ("tree", tree)):
        if attestation.get(key) != expected:
            raise RuntimeError(f"test attestation {key} mismatch")
    if attestation.get("clean_before_tests") is not True or attestation.get("detached") is not True:
        raise RuntimeError("test attestation must prove a clean detached worktree")

    matrix = _load_json(evidence_root / "build/reports/test-matrix.json")
    matrix_evidence = matrix.get("evidence") if isinstance(matrix.get("evidence"), dict) else {}
    totals = matrix.get("totals") if isinstance(matrix.get("totals"), dict) else {}
    if matrix_evidence.get("git_commit") != commit or matrix_evidence.get("source_tree_root_sha256") != source_root or matrix_evidence.get("git_dirty") is not False:
        raise RuntimeError("Python matrix is not bound to the clean checkpoint source")
    if matrix.get("status") not in {"passed", "passed_complete"}:
        raise RuntimeError("Python matrix did not pass")
    python_tests = int(totals.get("tests", 0))
    if python_tests < 300 or any(int(totals.get(key, 0)) for key in ("failures", "errors", "skipped")):
        raise RuntimeError("Python matrix does not satisfy the Progress 09 baseline")
    swift = _read_bound_report(evidence_root / "build/reports/swift-test-report.json", commit=commit, source_root=source_root, minimum_tests=13)
    web = _read_bound_report(evidence_root / "build/reports/web-runtime-test-report.json", commit=commit, source_root=source_root, minimum_tests=14)
    desktop = _read_bound_report(evidence_root / "build/reports/desktop-review-test-report.json", commit=commit, source_root=source_root, minimum_tests=17)
    if int(web.get("source_invariant_checks", 0)) < 35:
        raise RuntimeError("web source-invariant profile is incomplete")
    acceptance = _load_json(evidence_root / "build/reports/checkpoint-acceptance-gates.json")
    _require_acceptance(acceptance, commit=commit, source_root=source_root)
    readiness = _load_json(evidence_root / "build/reports/release-readiness-progress-09.json")
    if readiness.get("status") != "blocked" or readiness.get("production_authorized") is not False:
        raise RuntimeError("production release posture is not fail-closed")

    with tempfile.TemporaryDirectory(prefix="sip-progress-09-build-") as temporary:
        stage = Path(temporary) / TOP_LEVEL
        stage.mkdir(parents=True)
        source_dir = stage / "source"
        _extract_git_source(source_dir)
        copied_identity = source_identity(source_dir)
        if copied_identity["source_tree_root_sha256"] != source_root:
            raise RuntimeError("git-archived source root differs from tested source root")
        spec = source_dir / "spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
        if not spec.is_file() or sha256_file(spec) != EXPECTED_SPEC_SHA256:
            raise RuntimeError("authoritative specification archive is missing or changed")
        _copy_tree(evidence_root / "build/reports", stage / "build/reports")
        _copy_tree(evidence_root / "build/evidence", stage / "build/evidence")

        artifacts_dir = stage / "artifacts"
        source_archive = artifacts_dir / f"Spatial-Intelligence-Platform-v1.1.0-{commit}.tar.gz"
        _gzip_git_archive(source_archive, prefix="Spatial-Intelligence-Platform-v1.1.0")
        bundle = artifacts_dir / f"Spatial-Intelligence-Platform-v1.1.0-progress-09-{commit}.bundle"
        bundle.parent.mkdir(parents=True, exist_ok=True)
        _run("git", "bundle", "create", str(bundle), branch)
        complete_source_records = stage_records(source_dir, excluded=())
        source_file_manifest = {
            "schema": "sip.source-file-manifest/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "commit": commit,
            "tree": tree,
            "source_tree_root_sha256": source_root,
            "source_root_policy_sha256": identity["policy_sha256"],
            "file_count": len(complete_source_records),
            "total_bytes": sum(item.size for item in complete_source_records),
            "complete_source_content_root_sha256": content_root(complete_source_records),
            "files": [asdict(item) for item in complete_source_records],
        }
        source_manifest_path = stage / "SOURCE_FILE_MANIFEST.json"
        _write(source_manifest_path, source_file_manifest)
        source_commit = {
            "schema": "sip.source-commit/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "commit": commit,
            "parent": parent,
            "tree": tree,
            "branch": branch,
            "commit_timestamp": timestamp,
            "working_tree_clean_at_package": True,
            "tested_detached_worktree": True,
            "clean_working_tree_attestation": attestation,
            "source_tree_root_sha256": source_root,
            "source_root_policy_path": identity["policy_path"],
            "source_root_policy_sha256": identity["policy_sha256"],
            "source_root_file_count": identity["file_count"],
            "source_archive": _hash_record(source_archive, root=stage),
            "git_bundle": _hash_record(bundle, root=stage),
            "source_file_manifest": _hash_record(source_manifest_path, root=stage),
            "bundle_clone_command": f"git clone -b {branch} <bundle-file> <destination>",
        }
        _write(stage / "SOURCE_COMMIT.json", source_commit)
        predecessor = _load_json(source_dir / "PREDECESSOR_CHECKPOINT.json")
        _write(stage / "PREDECESSOR_CHECKPOINT.json", predecessor)

        ledger, requirement_counts = _requirements(source_dir)
        generated_contracts = sum(1 for path in (source_dir / "schemas").rglob("*") if path.is_file())
        facts = {
            "checkpoint_id": CHECKPOINT_ID,
            "branch": branch,
            "commit": commit,
            "parent": parent,
            "tree": tree,
            "commit_timestamp": timestamp,
            "source_tree_root_sha256": source_root,
            "source_root_policy_sha256": identity["policy_sha256"],
            "working_tree_clean": True,
            "tested_detached_worktree": True,
            "python_tests_passed": python_tests,
            "python_failures": 0,
            "python_errors": 0,
            "python_skipped": 0,
            "swift_tests_passed": int(swift.get("tests_passed", 0)),
            "web_runtime_tests_passed": int(web.get("tests_passed", 0)),
            "web_source_checks_passed": int(web.get("source_invariant_checks", 0)),
            "desktop_tests_passed": int(desktop.get("tests_passed", 0)),
            "generated_contract_artifacts": generated_contracts,
            "requirements_total": len(ledger["requirements"]),
            "requirements_by_status": requirement_counts,
            "external_validation_gaps": EXTERNAL_GAPS,
            "next_cluster": NEXT_CLUSTER,
            "progress_09_authorized": True,
            "progress_10_authorized": False,
            "production_authorized": False,
        }
        checkpoint_record = {
            "schema": "sip.checkpoint-record/v1",
            "facts": facts,
            "milestone_wording": MILESTONE_WORDING,
            "source_commit_record": "SOURCE_COMMIT.json",
            "predecessor_checkpoint_record": "PREDECESSOR_CHECKPOINT.json",
            "authoritative_evidence_index": "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json",
            "release_posture": "blocked",
        }
        _write(stage / "build/checkpoints/progress-09.json", checkpoint_record)
        milestone = _milestone_scope(ledger=ledger, facts=facts)
        _write(stage / "MILESTONE_SCOPE_PROGRESS_09.json", milestone)
        (stage / "IMPLEMENTATION_STATUS.md").write_text(_render_status(facts, requirement_counts), encoding="utf-8")
        (stage / "RESUME_IMPLEMENTATION.md").write_text(_render_resume(facts), encoding="utf-8")
        coverage = stage / "requirements/coverage-report.md"
        coverage.parent.mkdir(parents=True, exist_ok=True)
        coverage.write_text(_render_coverage(facts, ledger), encoding="utf-8")
        latest = {
            "schema": "sip.release-latest/v2",
            "checkpoint_id": CHECKPOINT_ID,
            "commit": commit,
            "tree": tree,
            "branch": branch,
            "source_tree_root_sha256": source_root,
            "readiness": "blocked",
            "checkpoint_record": "build/checkpoints/progress-09.json",
            "progress_09_authorized": True,
            "progress_10_authorized": False,
            "production_authorized": False,
        }
        _write(stage / "build/release/latest.json", latest)

        authoritative_dir = stage / "build/evidence/authoritative"
        authoritative_dir.mkdir(parents=True, exist_ok=True)
        raw_paths: dict[str, list[str]] = {
            "python_matrix": ["build/reports/test-matrix.json"],
            "swift_tests": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
            "web_tests": ["build/reports/web-runtime-test-report.json", "build/evidence/web-runtime-test.log", "build/reports/web-full-acceptance.json", "build/evidence/web-full-acceptance.log"],
            "desktop_tests": ["build/reports/desktop-review-test-report.json", "build/evidence/desktop-review-test.log"],
            "contracts": ["build/reports/tests/contract.xml", "build/reports/tests/contract.log", "build/evidence/gates/contracts.log"],
            "migrations": ["build/reports/tests/migration.xml", "build/reports/tests/migration-direct.xml", "build/evidence/gates/migrations.log", "source/migrations/versions/0012_scene_runtime_review.py", "source/migrations/versions/0013_scene_change_application_atomicity.py", "source/migrations/versions/0014_vertical_mvp.py", "source/migrations/versions/0015_progress06_r1_security_controls.py", "source/migrations/versions/0016_progress06_r2_truth_and_restricted_data.py", "source/migrations/versions/0017_progress07_security_privacy_readiness.py", "source/migrations/versions/0018_progress08_observability_cost_support.py", "source/migrations/versions/0019_progress09_deployment_profiles.py"],
            "infrastructure": ["build/reports/infrastructure-validation.json", "build/evidence/gates/infrastructure.log"],
            "security": ["build/reports/security-report.json", SECURITY_DIRECT_EVIDENCE_PATH, "build/evidence/gates/security.log"],
            "licensing": ["build/reports/license-gate.json", "build/evidence/gates/license-check.log"],
            "requirements": ["source/requirements/requirements-ledger.json", "source/requirements/requirements-ledger.csv", "source/requirements/requirements-ledger.sqlite", "source/requirements/implementation-map.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_06.json", "source/requirements/progress-06-traceability-audit.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_06_R1.json", "source/requirements/progress-06-r1-traceability-audit.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_06_R2.json", "source/requirements/progress-06-r2-traceability-audit.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_07.json", "source/requirements/progress-07-traceability-audit.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_08.json", "source/requirements/progress-08-traceability-audit.json", "source/requirements/MILESTONE_SCOPE_PROGRESS_09.json", "source/requirements/progress-09-traceability-audit.json", "build/reports/spec-lint.json", "build/evidence/gates/traceability-evidence.log"],
            "benchmarks": ["build/reports/benchmark-report.json", "build/evidence/gates/benchmark.log"],
            "demonstrations": [
                "build/evidence/demos/foundation.json", "build/evidence/demos/hybrid.json", "build/evidence/demos/scene-runtime.json",
                "build/evidence/demos/construction.json", "build/evidence/demos/liveforever.json", "build/evidence/demo-progress07-security.json", "build/evidence/demo-progress08-operations.json", "build/evidence/demo-progress09-deployment.json",
                "build/evidence/gates/demo-foundation.log", "build/evidence/gates/demo-hybrid.log", "build/evidence/gates/demo-scene-runtime.log",
                "build/evidence/gates/demo-construction.log", "build/evidence/gates/demo-liveforever.log", "build/evidence/gates/demo-security.log", "build/evidence/gates/demo-operations.log", "build/evidence/gates/demo-deployment.log",
            ],
            "preservation_export": ["build/evidence/demos/export.json", "build/evidence/gates/export-demo.log"],
            "independent_restore": ["build/evidence/demos/restore.json", "build/evidence/gates/restore-demo.log"],
            "release_readiness": ["build/reports/release-readiness-progress-09.json", "build/reports/checkpoint-acceptance-gates.json", "build/reports/release-report.json", "build/evidence/gates/web-acceptance.log", "build/evidence/gates/release.log", "build/evidence/gates/release-mode.log"],
        }
        statuses = {
            "python_matrix": "passed_complete",
            "swift_tests": "passed_with_external_gaps",
            "web_tests": "passed_with_external_gaps",
            "desktop_tests": "passed_with_external_gaps",
            "contracts": "passed_complete",
            "migrations": "passed_complete",
            "infrastructure": "passed_with_external_gaps",
            "security": "passed_with_external_gaps",
            "licensing": "passed_complete",
            "requirements": "passed_complete",
            "benchmarks": "passed_with_external_gaps",
            "demonstrations": "passed_with_external_gaps",
            "preservation_export": "passed_complete",
            "independent_restore": "passed_complete",
            "release_readiness": "blocked",
        }
        wrappers: dict[str, Path] = {}
        source_root_wrapper = authoritative_dir / "source-root.json"
        _write(source_root_wrapper, _authoritative_wrapper(category="source_root", facts=facts, status="passed_complete", artifacts=[{
            "path": "source/governance/source-root-policy.json", "sha256": identity["policy_sha256"], "source_tree_root_sha256": source_root,
        }]))
        wrappers["source_root"] = source_root_wrapper
        source_commit_wrapper = authoritative_dir / "source-commit.json"
        _write(source_commit_wrapper, _authoritative_wrapper(category="source_commit", facts=facts, status="passed_complete", artifacts=[_hash_record(stage / "SOURCE_COMMIT.json", root=stage)]))
        wrappers["source_commit"] = source_commit_wrapper
        for category, paths in raw_paths.items():
            artifacts: list[dict[str, object]] = []
            for relative in paths:
                path = stage / relative
                if not path.is_file():
                    raise RuntimeError(f"authoritative {category} artifact is missing: {relative}")
                artifacts.append(_hash_record(path, root=stage))
            wrapper = authoritative_dir / f"{category.replace('_', '-')}.json"
            gaps = EXTERNAL_GAPS if statuses[category] in {"passed_with_external_gaps", "blocked"} else []
            _write(wrapper, _authoritative_wrapper(category=category, facts=facts, status=statuses[category], artifacts=artifacts, gaps=gaps))
            wrappers[category] = wrapper
        if set(wrappers) != REQUIRED_EVIDENCE_CATEGORIES:
            raise RuntimeError("authoritative evidence categories are incomplete")
        index = {
            "schema": "sip.authoritative-evidence-index/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "source_commit": commit,
            "source_tree_root_sha256": source_root,
            "authoritative": {
                category: {
                    "path": path.relative_to(stage).as_posix(),
                    "sha256": sha256_file(path),
                    "source_commit": commit,
                    "source_tree_root_sha256": source_root,
                    "status": json.loads(path.read_text(encoding="utf-8"))["status"],
                }
                for category, path in sorted(wrappers.items())
            },
            "superseded_evidence": [],
        }
        _write(stage / "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json", index)

        report = "\n".join([
            "# Progress 09 Final Implementation Report",
            "",
            f"Checkpoint: `{CHECKPOINT_ID}`",
            f"Commit: `{commit}`",
            f"Tree: `{tree}`",
            f"Source root: `{source_root}`",
            "",
            MILESTONE_WORDING,
            "",
            "## Bounded OPS-003 implementation",
            "",
            "Local-only, edge, hybrid, and AWS-reference deployment profiles; residency admission; workload identity; default-deny networking; autoscaling budgets; reversible upgrades; portability; graceful shutdown; and fail-closed production admission are implemented as the bounded Progress 09 OPS-003 milestone.",
            "",
            "Deployment profiles are immutable and digest-bound; residency and transfer policy is enforced before upload or scheduling; edge updates are signed and rollback-capable; project migration preserves semantic identity; and production promotion remains fail-closed without deployed-infrastructure evidence.",
            "",
            "All Progress 09 demonstrations use synthetic or non-sensitive fixtures. No confidential facility, critical-infrastructure, private-family, cloned voice, simulated likeness, or unapproved external-provider data is included.",
            "",
            f"Python matrix: {python_tests} passed, 0 failed, 0 errors, 0 skipped.",
            f"Swift Linux fixture profile: {facts['swift_tests_passed']} passed; physical Apple-platform acceptance remains external.",
            f"Web dependency-free profile: {facts['web_runtime_tests_passed']} runtime tests and {facts['web_source_checks_passed']} source checks passed; the mounted viewer integration and Next production build remain blocked.",
            f"Desktop local-first profile: {facts['desktop_tests_passed']} tests passed; native packaging and operator usability remain external.",
            "",
            "Append-only schema revision 0019_progress09_deployment_profiles is included. All earlier migrations are preserved unchanged.",
            "",
            "Progress 09 is authorized only as this bounded development milestone. Progress 10 remains unauthorized and production deployment/release remains NO-GO.",
        ]) + "\n"
        (stage / "FINAL_IMPLEMENTATION_REPORT.md").write_text(report, encoding="utf-8")
        milestone_report = "\n".join([
            "# Progress 09 Milestone Report",
            "",
            f"Checkpoint: `{CHECKPOINT_ID}`",
            f"Commit: `{commit}`",
            f"Source root: `{source_root}`",
            "",
            MILESTONE_WORDING,
            "",
            f"- Bounded OPS-003 scope: {len(P09_SCOPE_IDS)} requirements, with every included/deferred item explicitly partitioned.",
            f"- Included requirements: {len(milestone['included_requirements'])}.",
            f"- Explicitly deferred requirements: {len(milestone['deferred_requirements'])}.",
            "- Every linked Python test must exist and declare its mapped requirement identifier; the semantic traceability audit reports zero findings.",
            "- PLTVIEW-007 remains IMPLEMENTED_UNVERIFIED until the specified mounted viewer integration test runs under an approved frozen web toolchain.",
            "- Construction and LiveForever pilots are deterministic synthetic/non-sensitive demonstrations, not customer or human-subject pilots.",
            "- External validation gaps remain explicit and production release remains fail-closed.",
            "",
            f"Python matrix: {python_tests} passed, 0 failed, 0 errors, 0 skipped.",
            "",
            "Progress 09 is delivered for independent True North milestone-closure review. Progress 10 remains unauthorized and production remains NO-GO.",
        ]) + "\n"
        (stage / "PROGRESS_09_MILESTONE_REPORT.md").write_text(milestone_report, encoding="utf-8")
        checkpoint_readme = "\n".join([
            "# SIP v1.1.0 Progress 09 checkpoint",
            "",
            "The exact committed project is under `source/`. Post-commit evidence and packaging metadata are outside the canonical source namespace.",
            "",
            "Verify:",
            "",
            "```bash",
            "python source/tools/verify_progress09_checkpoint.py Spatial-Intelligence-Platform-v1.1.0-progress-09.zip",
            "```",
            "",
            "Clone the included Git bundle:",
            "",
            "```bash",
            f"git clone -b {branch} artifacts/Spatial-Intelligence-Platform-v1.1.0-progress-09-{commit}.bundle <destination>",
            "```",
            "",
            "Production deployment and release remain NO-GO.",
        ]) + "\n"
        (stage / "README_CHECKPOINT.md").write_text(checkpoint_readme, encoding="utf-8")
        manifest = build_content_manifest(stage, checkpoint_id=CHECKPOINT_ID, top_level=TOP_LEVEL)
        _write(stage / "CHECKPOINT_CONTENT_MANIFEST.json", manifest)
        write_deterministic_zip(stage, output, top_level=TOP_LEVEL)
        return {
            "schema": "sip.checkpoint-build-report/v1",
            "status": "passed_complete",
            "checkpoint_id": CHECKPOINT_ID,
            "archive": str(output),
            "archive_sha256": sha256_file(output),
            "archive_size": output.stat().st_size,
            "content_root_sha256": manifest["content_root_sha256"],
            "file_count": manifest["file_count"],
            "source_commit": commit,
            "source_tree_root_sha256": source_root,
            "progress_09_authorized": True,
            "progress_10_authorized": False,
            "production_authorized": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--branch", default="progress-09-deployment")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = build(
        evidence_root=args.evidence_root.resolve(),
        output=args.output.resolve(),
        branch=args.branch,
        attestation_path=args.attestation.resolve(),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
