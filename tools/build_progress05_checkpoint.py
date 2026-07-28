#!/usr/bin/env python3
"""Build the Progress 05 checkpoint from a clean committed source worktree and source-bound evidence."""
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

CHECKPOINT_ID = "sip-v1.1.0-progress-05"
TOP_LEVEL = "Spatial-Intelligence-Platform-v1.1.0-progress-05"
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
MILESTONE_WORDING = (
    "Checkpoint 05 implements and locally verifies the scene-runtime review kernel: durable policy-bound viewer "
    "sessions, governed temporal comparison, a native hybrid-renderer reference, and a local-first desktop review "
    "application. Browser/GPU/device/deployment validation and production approval remain incomplete."
)
EXTERNAL_GAPS = [
    "Ruff was unavailable; the deterministic source-policy checker ran instead.",
    "mypy was unavailable; Python compilation ran, but a full mypy result is blocked.",
    "Node 24.18.0, pnpm 10.28.2, pnpm-lock.yaml, installed dependencies, ESLint, TypeScript typecheck, and the Next production build were unavailable.",
    "Dependency-free web and desktop runtime tests do not constitute a complete Next.js or native desktop production build.",
    "pip-audit, Gitleaks, and Trivy were unavailable; dependency, history-secret, and container scans remain blocked in release mode.",
    "Docker Compose runtime, Kubernetes deployment, and Terraform provider execution were not available; structural checks are not deployment validation.",
    "Xcode, iOS simulator, signing, LiDAR, camera, thermal, battery, interruption, and physical-device validation remain external.",
    "Approved LingBot-Map checkpoint bytes, commercial model-rights approval, CUDA/GPU execution, and real-scene validation remain external.",
    "Independent penetration testing, privacy review, browser accessibility audit, operator usability study, and legal approval remain incomplete.",
]
NEXT_CLUSTER = (
    "Continue dependency-ordered implementation of incomplete Phase 5 search/document/agent/runtime requirements, "
    "then Construction and LiveForever vertical completeness, production observability/recovery, external-platform "
    "validation plans, and remaining P0/P1 requirements. Production promotion remains fail-closed."
)
P05_SCOPE_IDS = {
    *(f"RECCHANG-{index:03d}" for index in range(1, 7)),
    *(f"PLTVIEW-{index:03d}" for index in range(1, 13)),
    *(f"PLTDESK-{index:03d}" for index in range(1, 7)),
    "DATGIT-003",
    "DATGIT-004",
    "DATDB-004",
    "DELDOD-002",
    "TSTSEC-001",
    "TSTGATE-003",
}
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
    selected = {
        str(item.get("requirement_id")): item
        for item in ledger["requirements"]
        if str(item.get("requirement_id")) in P05_SCOPE_IDS
    }
    missing = P05_SCOPE_IDS - set(selected)
    if missing:
        raise RuntimeError(f"Progress 05 scope contains unknown requirement IDs: {sorted(missing)}")
    included: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for requirement_id in sorted(P05_SCOPE_IDS):
        item = selected[requirement_id]
        status = str(item.get("implementation_status"))
        entry = {
            "requirement_id": requirement_id,
            "priority": item.get("priority"),
            "status": status,
            "source_document": item.get("source_document"),
            "source_line": item.get("source_line"),
            "requirement_text": item.get("text"),
            "implementation_files": item.get("implementation_files", []),
            "test_ids": item.get("test_ids", []),
            "evidence_paths": [str(path) for path in item.get("test_result_evidence_paths", []) if str(path)],
        }
        if status == "NOT_STARTED":
            entry["deferral_reason"] = "Retained in the Progress 05 problem domain but not implemented in this checkpoint."
            deferred.append(entry)
        else:
            included.append(entry)
    return {
        "schema": "sip.milestone-scope/v1",
        "checkpoint_id": facts["checkpoint_id"],
        "source_commit": facts["commit"],
        "source_tree_root_sha256": facts["source_tree_root_sha256"],
        "milestone": "Progress 05 scene-runtime review kernel",
        "authoritative_wording": MILESTONE_WORDING,
        "scope_requirement_ids": sorted(P05_SCOPE_IDS),
        "included_requirements": included,
        "deferred_requirements": deferred,
        "summary": {
            "scope_requirements_total": len(P05_SCOPE_IDS),
            "included": len(included),
            "deferred": len(deferred),
            "included_by_status": dict(sorted(Counter(item["status"] for item in included).items())),
        },
        "acceptance_criteria": [
            "Viewer sessions are immutable, policy-bound, reproducible, and contain no reusable capability material.",
            "Temporal comparisons preserve commit/evidence/algorithm identity and suppress unobserved removals and nuisance changes.",
            "Semantic changes require independent human review and explicit scene-commit linkage.",
            "Native metric, visual, design, interaction, and evidence roles remain distinct in the renderer reference.",
            "Proxy hits cannot directly create authoritative measurements.",
            "Desktop review is local-first, crash-safe at the deterministic storage layer, conflict-preserving, and export-gated.",
            "Migration 0012 is append-only and rollback/recovery tested in the local reference profile.",
            "The complete source-bound acceptance matrix and all available local gates pass from one clean detached commit.",
            "External browser, GPU, device, deployment, security, privacy, accessibility, and legal gaps remain explicit.",
        ],
        "final_result": "passed_with_external_gaps_pending_independent_true_north_review",
    }


def _render_status(facts: dict[str, Any], counts: dict[str, int]) -> str:
    lines = [
        "# SIP v1.1.0 Implementation Status — Progress 05",
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
        "Progress 05 is a source-bound development checkpoint. Production deployment and release remain NO-GO.",
        "",
        "## External validation gaps",
        "",
        *[f"- {item}" for item in EXTERNAL_GAPS],
    ]
    return "\n".join(lines) + "\n"


def _render_resume(facts: dict[str, Any]) -> str:
    return "\n".join([
        "# Resume Implementation — SIP v1.1.0 Progress 05",
        "",
        "This continuation record is generated from `build/checkpoints/progress-05.json`.",
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
        "# Requirements coverage report — Progress 05",
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
    lines += ["", "> Requirements outside VERIFIED remain incomplete or externally unverified. This report makes no complete-platform or production-readiness claim."]
    return "\n".join(lines) + "\n"


def _require_acceptance(report: dict[str, Any], *, commit: str, source_root: str) -> None:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    if report.get("checkpoint_id") != CHECKPOINT_ID or source.get("commit") != commit or source.get("source_tree_root_sha256") != source_root:
        raise RuntimeError("checkpoint acceptance report is not bound to Progress 05 source")
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
    if python_tests < 220 or any(int(totals.get(key, 0)) for key in ("failures", "errors", "skipped")):
        raise RuntimeError("Python matrix does not satisfy the Progress 05 baseline")
    swift = _read_bound_report(evidence_root / "build/reports/swift-test-report.json", commit=commit, source_root=source_root, minimum_tests=13)
    web = _read_bound_report(evidence_root / "build/reports/web-runtime-test-report.json", commit=commit, source_root=source_root, minimum_tests=12)
    desktop = _read_bound_report(evidence_root / "build/reports/desktop-review-test-report.json", commit=commit, source_root=source_root, minimum_tests=15)
    if int(web.get("source_invariant_checks", 0)) < 26:
        raise RuntimeError("web source-invariant profile is incomplete")
    acceptance = _load_json(evidence_root / "build/reports/checkpoint-acceptance-gates.json")
    _require_acceptance(acceptance, commit=commit, source_root=source_root)
    readiness = _load_json(evidence_root / "build/reports/release-readiness-progress-05.json")
    if readiness.get("status") != "blocked" or readiness.get("production_authorized") is not False:
        raise RuntimeError("production release posture is not fail-closed")

    with tempfile.TemporaryDirectory(prefix="sip-progress-05-build-") as temporary:
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
        bundle = artifacts_dir / f"Spatial-Intelligence-Platform-v1.1.0-progress-05-{commit}.bundle"
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
        _write(stage / "build/checkpoints/progress-05.json", checkpoint_record)
        milestone = _milestone_scope(ledger=ledger, facts=facts)
        _write(stage / "MILESTONE_SCOPE_PROGRESS_05.json", milestone)
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
            "checkpoint_record": "build/checkpoints/progress-05.json",
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
            "migrations": ["build/reports/tests/migration.xml", "build/reports/tests/migration-direct.xml", "build/evidence/gates/migrations.log", "source/migrations/versions/0012_scene_runtime_review.py"],
            "infrastructure": ["build/reports/infrastructure-validation.json", "build/evidence/gates/infrastructure.log"],
            "security": ["build/reports/security-report.json", "build/reports/tests/security-direct.xml", "build/evidence/gates/security.log"],
            "licensing": ["build/reports/license-gate.json", "build/evidence/gates/license-check.log"],
            "requirements": ["source/requirements/requirements-ledger.json", "source/requirements/implementation-map.json", "build/reports/spec-lint.json", "build/evidence/gates/traceability-evidence.log"],
            "benchmarks": ["build/reports/benchmark-report.json", "build/evidence/gates/benchmark.log"],
            "demonstrations": [
                "build/evidence/demos/foundation.json", "build/evidence/demos/hybrid.json", "build/evidence/demos/scene-runtime.json",
                "build/evidence/demos/construction.json", "build/evidence/demos/liveforever.json",
                "build/evidence/gates/demo-foundation.log", "build/evidence/gates/demo-hybrid.log", "build/evidence/gates/demo-scene-runtime.log",
                "build/evidence/gates/demo-construction.log", "build/evidence/gates/demo-liveforever.log",
            ],
            "preservation_export": ["build/evidence/demos/export.json", "build/evidence/gates/export-demo.log"],
            "independent_restore": ["build/evidence/demos/restore.json", "build/evidence/gates/restore-demo.log"],
            "release_readiness": ["build/reports/release-readiness-progress-05.json", "build/reports/checkpoint-acceptance-gates.json", "build/reports/release-report.json", "build/evidence/gates/web-acceptance.log", "build/evidence/gates/release.log", "build/evidence/gates/release-mode.log"],
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
            "# Progress 05 Implementation Report",
            "",
            f"Checkpoint: `{CHECKPOINT_ID}`",
            f"Commit: `{commit}`",
            f"Tree: `{tree}`",
            f"Source root: `{source_root}`",
            "",
            MILESTONE_WORDING,
            "",
            "The implementation includes durable viewer-session and temporal-comparison control planes, append-only migration 0012, authenticated APIs and events, a native hybrid renderer reference, a local-first desktop review application, and expanded security/privacy/property/accessibility controls.",
            "",
            f"Python matrix: {python_tests} passed, 0 failed, 0 errors, 0 skipped.",
            f"Swift Linux fixture profile: {facts['swift_tests_passed']} passed; physical Apple-platform acceptance remains external.",
            f"Web dependency-free profile: {facts['web_runtime_tests_passed']} runtime tests and {facts['web_source_checks_passed']} source checks passed; the Next production build remains blocked.",
            f"Desktop local-first profile: {facts['desktop_tests_passed']} tests passed; native packaging/GPU operator validation remains external.",
            "",
            "Production release remains blocked.",
        ]) + "\n"
        (stage / "FINAL_IMPLEMENTATION_REPORT.md").write_text(report, encoding="utf-8")
        checkpoint_readme = "\n".join([
            "# SIP v1.1.0 Progress 05 checkpoint",
            "",
            "The exact committed project is under `source/`. Post-commit evidence and packaging metadata are outside the canonical source namespace.",
            "",
            "Verify:",
            "",
            "```bash",
            "python source/tools/verify_progress05_checkpoint.py Spatial-Intelligence-Platform-v1.1.0-progress-05.zip",
            "```",
            "",
            "Clone the included Git bundle:",
            "",
            "```bash",
            f"git clone -b {branch} artifacts/Spatial-Intelligence-Platform-v1.1.0-progress-05-{commit}.bundle <destination>",
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
            "production_authorized": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--branch", default="progress-05-scene-runtime")
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
