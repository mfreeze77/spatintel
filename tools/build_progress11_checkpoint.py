#!/usr/bin/env python3
"""Build the deterministic Progress 11 QA-002 checkpoint from a clean exact commit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.checkpoint_common import (
    MANIFEST_PATH,
    build_content_manifest,
    pretty_json,
    sha256_file,
    write_deterministic_zip,
)
from tools.source_identity import source_identity

CHECKPOINT_ID = "sip-v1.1.0-progress-11"
TOP_LEVEL = "Spatial-Intelligence-Platform-v1.1.0-progress-11"
BRANCH = "progress-11-release-gates"
EXPECTED_BASE_COMMIT = "ab409f6ac7ca583535f69e5806b7a3bdbfe08214"
EXPECTED_BASE_ZIP_SHA256 = "46d850b6035d0ee86386ff256aabdc65751d49398f6ea4e4084eb4d50d6c669c"
EXPECTED_BASE_OUTER_SHA256 = "1e0c962a59a55a2a6395179c98467778ff56e2e394319b0ca46367551b5027dc"
EXPECTED_BASE_SOURCE_ROOT = "0c93009874f99c72c3670d6cfca47af00ff04b762e4f4ddddffa20ab03ed8678"
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
EXPECTED_SCOPE_TOTAL = 96
MIGRATION_PATH = "migrations/versions/0021_progress11_release_assurance.py"
MIN_PYTHON_TESTS = 455


def _matrix_counts(totals: dict[str, Any]) -> tuple[int, int, int, int]:
    """Normalize the canonical matrix totals schema and historical aliases."""

    passed = int(totals.get("tests", totals.get("passed", 0)))
    failed = int(totals.get("failures", totals.get("failed", 0)))
    errors = int(totals.get("errors", 0))
    skipped = int(totals.get("skipped", 0))
    return passed, failed, errors, skipped
MILESTONE_WORDING = (
    "Progress 11 implements the bounded QA-002 dual-vertical acceptance and release-assurance layer "
    "defined by the enclosed milestone scope. Local and synthetic evidence is retained separately from "
    "mounted-browser, physical-device, approved-model/GPU, credentialed-cloud, external-review, customer, "
    "family, legal, privacy, accessibility, penetration, and production evidence. Progress 12 remains "
    "unauthorized and production remains NO-GO."
)


def _run(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result


def _git(*args: str) -> str:
    return _run("git", *args).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        path.write_bytes(pretty_json(value))
    else:
        path.write_text(str(value), encoding="utf-8")


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=False)


def _complete_source_manifest(source_root: Path, *, commit: str) -> dict[str, Any]:
    raw = _run("git", "ls-tree", "-r", "-z", "--full-tree", commit).stdout
    records: list[dict[str, Any]] = []
    for entry in raw.split("\0"):
        if not entry:
            continue
        metadata, path_text = entry.split("\t", 1)
        mode, object_type, object_id = metadata.split(" ", 2)
        if object_type != "blob":
            continue
        path = source_root / path_text
        payload = path.read_bytes()
        records.append({
            "path": path_text,
            "git_mode": mode,
            "mode": "0755" if mode == "100755" else "0644",
            "git_blob": object_id,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    records.sort(key=lambda item: item["path"])
    root_hash = hashlib.sha256(
        (json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    ).hexdigest()
    return {
        "schema": "sip.source-file-manifest/v1",
        "commit": commit,
        "file_count": len(records),
        "total_bytes": sum(item["size"] for item in records),
        "content_root_sha256": root_hash,
        "files": records,
    }


def _evidence_record(stage: Path, relative: str) -> dict[str, Any]:
    path = stage / relative
    if not path.is_file():
        raise RuntimeError(f"authoritative evidence missing: {relative}")
    return {"path": relative, "sha256": sha256_file(path), "byte_count": path.stat().st_size}


def _render_status(checkpoint: dict[str, Any], counts: dict[str, int]) -> str:
    return f"""# SIP v1.1.0 Implementation Status — Progress 11

- Checkpoint: `{CHECKPOINT_ID}`
- Branch: `{checkpoint['branch']}`
- Commit: `{checkpoint['commit']}`
- Git tree: `{checkpoint['tree']}`
- Canonical source root: `{checkpoint['source_tree_root_sha256']}`
- Clean detached acceptance: `true`
- Python matrix: `{checkpoint['python_tests']['passed']} passed, 0 failed, 0 errors, 0 skipped`
- Progress 12 authorized: `false`
- Production authorized: `false`

## Requirements

| Status | Count |
|---|---:|
| VERIFIED | {counts.get('VERIFIED', 0)} |
| IMPLEMENTED_UNVERIFIED | {counts.get('IMPLEMENTED_UNVERIFIED', 0)} |
| IN_PROGRESS | {counts.get('IN_PROGRESS', 0)} |
| EXTERNAL_VALIDATION_REQUIRED | {counts.get('EXTERNAL_VALIDATION_REQUIRED', 0)} |
| NOT_STARTED | {counts.get('NOT_STARTED', 0)} |
| **Total** | **{sum(counts.values())}** |

{MILESTONE_WORDING}
"""


def _render_final_report(checkpoint: dict[str, Any], scope: dict[str, Any], counts: dict[str, int]) -> str:
    return f"""# SIP v1.1.0 Progress 11 Final Implementation Report

## Source identity

- Branch: `{checkpoint['branch']}`
- Commit: `{checkpoint['commit']}`
- Parent: `{checkpoint['parent']}`
- Git tree: `{checkpoint['tree']}`
- Source root: `{checkpoint['source_tree_root_sha256']}`
- Accepted Progress 10 ancestor: `{EXPECTED_BASE_COMMIT}`

## Milestone

- Authorized epic: `QA-002`
- Included requirements: `{scope['included_requirement_count']}`
- Deferred requirements: `{scope['deferred_requirement_count']}`
- Traceability findings: `0`
- Progress 12 authorized: `false`
- Production authorized: `false`

Progress 11 adds immutable QA campaigns, requirement-bound Construction and LiveForever acceptance scenarios, truthful release gates, rollback rehearsals, nonwaivable stop-lines, signed release candidates, release-manifest verification, operating-envelope and known-limitations evidence, support and escalation plans, synthetic load evidence, and fail-closed production admission.

## Verification

- Python: `{checkpoint['python_tests']['passed']} passed, 0 failed, 0 errors, 0 skipped`
- Swift Linux fixtures: `{checkpoint['additional_tests']['swift_passed']} passed`
- Web browser-independent runtime: `{checkpoint['additional_tests']['web_runtime_passed']} passed`
- Web source/accessibility checks: `{checkpoint['additional_tests']['web_source_passed']} passed`
- Desktop review: `{checkpoint['additional_tests']['desktop_passed']} passed`
- Acceptance status: `{checkpoint['acceptance_status']}`

## Requirements posture

{json.dumps(counts, indent=2, sort_keys=True)}

## External evidence

Mounted browser/runtime, physical iOS/LiDAR, approved LingBot checkpoint/GPU, credentialed cloud, external penetration/privacy/accessibility/legal/evidentiary review, customer Construction pilot, family or human-subject LiveForever pilot, and production certification remain external or unauthorized. Local and synthetic evidence is not represented as those evidence classes.

## Deployment and demonstrations

The package retains the documented `make` commands and the Construction, LiveForever, hybrid, rollback, migration, backup/restore, open-export, security/privacy, accessibility-source, load-reference, and release-manifest evidence. Production admission remains fail-closed.
"""


def build(*, output: Path, attestation_path: Path, branch: str = BRANCH) -> dict[str, Any]:
    output = output.resolve()
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RuntimeError("checkpoint builder requires a clean worktree")
    commit = _git("rev-parse", "HEAD")
    tree = _git("show", "-s", "--format=%T", "HEAD")
    parent = _git("show", "-s", "--format=%P", "HEAD").split()[0]
    if _run("git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, commit, check=False).returncode != 0:
        raise RuntimeError("accepted Progress 10 commit is not an ancestor")
    branch_ref = _run("git", "show-ref", "--verify", f"refs/heads/{branch}", check=False)
    if branch_ref.returncode != 0 or branch_ref.stdout.split()[0] != commit:
        raise RuntimeError(f"branch {branch} does not identify the checkpoint commit")

    attestation = _load(attestation_path)
    source_identity_value = source_identity(ROOT)
    source_root = str(source_identity_value["source_tree_root_sha256"])
    if attestation.get("commit") != commit or attestation.get("source_tree_root_sha256") != source_root:
        raise RuntimeError("source attestation does not match checkpoint source")
    if attestation.get("detached") is not True or attestation.get("clean_before_tests") is not True:
        raise RuntimeError("source attestation is not clean and detached")

    acceptance = _load(ROOT / "build/reports/checkpoint-acceptance-gates.json")
    matrix = _load(ROOT / "build/reports/test-matrix.json")
    scope = _load(ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_11.json")
    audit = _load(ROOT / "requirements/progress-11-traceability-audit.json")
    ledger = _load(ROOT / "requirements/requirements-ledger.json")
    readiness = _load(ROOT / "build/reports/release-readiness-progress-11.json")
    if acceptance.get("checkpoint_id") != CHECKPOINT_ID or acceptance.get("source", {}).get("commit") != commit:
        raise RuntimeError("acceptance report is not bound to Progress 11 source")
    if acceptance.get("source", {}).get("source_tree_root_sha256") != source_root:
        raise RuntimeError("acceptance source root differs")
    if acceptance.get("status") not in {"passed_complete", "passed_with_external_gaps"}:
        raise RuntimeError("Progress 11 checkpoint acceptance did not pass")
    if int(acceptance.get("required_failure_count", -1)) != 0:
        raise RuntimeError("Progress 11 checkpoint acceptance reports required failures")
    totals = matrix.get("totals", {})
    passed, failed, errors, skipped = _matrix_counts(totals)
    if passed < MIN_PYTHON_TESTS or any((failed, errors, skipped)):
        raise RuntimeError("Python matrix does not satisfy Progress 11 acceptance")
    if scope.get("included_requirement_count") != EXPECTED_SCOPE_TOTAL or scope.get("deferred_requirement_count") != 0:
        raise RuntimeError("Progress 11 milestone scope count differs")
    if audit.get("status") != "passed_complete" or int(audit.get("finding_count", -1)) != 0:
        raise RuntimeError("Progress 11 traceability audit is not clean")
    if readiness.get("production_authorized") is not False or readiness.get("progress_12_authorized") is not False:
        raise RuntimeError("release-readiness posture is invalid")

    requirements = ledger.get("requirements", [])
    if len(requirements) != 1028:
        raise RuntimeError("requirements ledger must retain all 1,028 requirements")
    counts: dict[str, int] = {}
    for item in requirements:
        counts[str(item.get("implementation_status"))] = counts.get(str(item.get("implementation_status")), 0) + 1
    pview = next(item for item in requirements if item.get("requirement_id") == "PLTVIEW-007")
    if pview.get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        raise RuntimeError("PLTVIEW-007 status drifted")

    swift_report = _load(ROOT / "build/reports/swift-test-report.json")
    web_report = _load(ROOT / "build/reports/web-runtime-test-report.json")
    desktop_report = _load(ROOT / "build/reports/desktop-review-test-report.json")
    additional = {
        "swift_passed": int(swift_report.get("tests_passed", 0)),
        "web_runtime_passed": int(web_report.get("tests_passed", 0)),
        "web_source_passed": int(web_report.get("source_invariant_checks", 0)),
        "desktop_passed": int(desktop_report.get("tests_passed", 0)),
    }

    migration = ROOT / MIGRATION_PATH
    migration_hash = sha256_file(migration)
    migration_bytes = migration.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-progress11-build-") as temporary:
        temp = Path(temporary)
        stage = temp / "stage"
        source_stage = stage / "source"
        source_stage.mkdir(parents=True)
        archive_tar = temp / f"Spatial-Intelligence-Platform-v1.1.0-{commit}.tar.gz"
        _run("git", "archive", "--format=tar.gz", "--output", str(archive_tar), commit)
        with tarfile.open(archive_tar, "r:gz") as archive:
            archive.extractall(source_stage, filter="data")
        extracted_identity = source_identity(source_stage)
        if extracted_identity["source_tree_root_sha256"] != source_root:
            raise RuntimeError("git archive source root differs from tested source root")
        source_manifest = _complete_source_manifest(source_stage, commit=commit)

        artifacts = stage / "artifacts"
        artifacts.mkdir(parents=True)
        bundle = artifacts / f"Spatial-Intelligence-Platform-v1.1.0-progress-11-{commit}.bundle"
        _run("git", "bundle", "create", str(bundle), branch)
        copied_source_archive = artifacts / archive_tar.name
        shutil.copy2(archive_tar, copied_source_archive)

        for relative in ("build/reports", "build/evidence", "build/manifests", "build/release"):
            _copy_tree(ROOT / relative, stage / relative)
        # Preserve the exact attestation even when a caller used an ignored evidence path.
        attestation_destination = stage / "build/evidence/source-attestation.json"
        attestation_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(attestation_path, attestation_destination)

        predecessor = _load(ROOT / "PREDECESSOR_CHECKPOINT.json")
        predecessor["accepted_progress_10_checkpoint"] = {
            "checkpoint_id": "sip-v1.1.0-progress-10",
            "branch": "progress-10-recovery",
            "commit": EXPECTED_BASE_COMMIT,
            "tree": "ced38981c7f41891a9c1288b789400b597a28b44",
            "project_zip_sha256": EXPECTED_BASE_ZIP_SHA256,
            "outer_delivery_zip_sha256": EXPECTED_BASE_OUTER_SHA256,
            "source_tree_root_sha256": EXPECTED_BASE_SOURCE_ROOT,
            "relationship": "Accepted Progress 10 is the exact source-history and evidence base authorized by True North for bounded Progress 11 QA-002.",
        }
        _write(stage / "PREDECESSOR_CHECKPOINT.json", predecessor)

        source_commit = {
            "schema": "sip.source-commit/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "branch": branch,
            "commit": commit,
            "parent": parent,
            "tree": tree,
            "commit_timestamp": _git("show", "-s", "--format=%cI", commit),
            "source_tree_root_sha256": source_root,
            "source_root_file_count": source_identity_value["file_count"],
            "source_root_policy_sha256": source_identity_value["policy_sha256"],
            "clean_detached_acceptance": True,
            "accepted_base_commit": EXPECTED_BASE_COMMIT,
        }
        _write(stage / "SOURCE_COMMIT.json", source_commit)
        _write(stage / "SOURCE_FILE_MANIFEST.json", source_manifest)
        _write(stage / "MILESTONE_SCOPE_PROGRESS_11.json", scope)
        _write(stage / "progress-11-traceability-audit.json", audit)

        checkpoint = {
            "schema": "sip.checkpoint-record/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "wording": MILESTONE_WORDING,
            "branch": branch,
            "commit": commit,
            "parent": parent,
            "tree": tree,
            "source_tree_root_sha256": source_root,
            "source_root_file_count": source_identity_value["file_count"],
            "accepted_base_commit": EXPECTED_BASE_COMMIT,
            "accepted_base_is_ancestor": True,
            "acceptance_status": acceptance["status"],
            "python_tests": {"passed": passed, "failed": 0, "errors": 0, "skipped": 0},
            "additional_tests": additional,
            "scope": {"included": EXPECTED_SCOPE_TOTAL, "deferred": 0, "traceability_findings": 0},
            "migration": {"path": MIGRATION_PATH, "byte_count": migration_bytes, "sha256": migration_hash},
            "progress_11_authorized": True,
            "progress_12_authorized": False,
            "production_authorized": False,
            "created_at": datetime.now(UTC).isoformat(),
        }
        _write(stage / "build/checkpoints/progress-11.json", checkpoint)
        latest = {
            "schema": "sip.release-pointer/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "commit": commit,
            "source_tree_root_sha256": source_root,
            "acceptance_status": acceptance["status"],
            "progress_11_authorized": True,
            "progress_12_authorized": False,
            "production_authorized": False,
        }
        _write(stage / "build/release/latest.json", latest)
        _write(stage / "IMPLEMENTATION_STATUS.md", _render_status(checkpoint, counts))
        _write(stage / "FINAL_IMPLEMENTATION_REPORT.md", _render_final_report(checkpoint, scope, counts))
        _write(stage / "RESUME_IMPLEMENTATION.md", f"# Resume Implementation — Progress 11\n\nProgress 11 is delivered for independent True North milestone-closure review. Progress 12 and production remain unauthorized.\n\nCommit: `{commit}`\nSource root: `{source_root}`\n")
        _write(stage / "requirements-coverage-report.md", _render_status(checkpoint, counts))

        authoritative_paths = [
            "SOURCE_COMMIT.json",
            "SOURCE_FILE_MANIFEST.json",
            "PREDECESSOR_CHECKPOINT.json",
            "MILESTONE_SCOPE_PROGRESS_11.json",
            "progress-11-traceability-audit.json",
            "build/evidence/source-attestation.json",
            "build/reports/checkpoint-acceptance-gates.json",
            "build/reports/test-matrix.json",
            "build/reports/swift-test-report.json",
            "build/reports/web-runtime-test-report.json",
            "build/reports/desktop-review-test-report.json",
            "build/reports/security-report.json",
            "build/reports/infrastructure-validation.json",
            "build/reports/license-gate.json",
            "build/reports/benchmark-report.json",
            "build/reports/release-report.json",
            "build/reports/release-readiness-progress-11.json",
            "build/evidence/progress11-release/demo-progress11-release.json",
            "source/requirements/requirements-ledger.json",
            "source/requirements/requirements-ledger.csv",
            "source/requirements/requirements-ledger.sqlite",
            "source/requirements/implementation-map.json",
            "source/requirements/MILESTONE_SCOPE_PROGRESS_11.json",
            "source/requirements/progress-11-traceability-audit.json",
            f"source/{MIGRATION_PATH}",
            f"artifacts/{bundle.name}",
            f"artifacts/{copied_source_archive.name}",
        ]
        index = {
            "schema": "sip.authoritative-evidence-index/v1",
            "checkpoint_id": CHECKPOINT_ID,
            "commit": commit,
            "source_tree_root_sha256": source_root,
            "artifacts": [_evidence_record(stage, relative) for relative in authoritative_paths],
            "progress_12_authorized": False,
            "production_authorized": False,
        }
        _write(stage / "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json", index)

        manifest = build_content_manifest(stage, checkpoint_id=CHECKPOINT_ID, top_level=TOP_LEVEL)
        _write(stage / MANIFEST_PATH, manifest)
        write_deterministic_zip(stage, output, top_level=TOP_LEVEL)

    sha = sha256_file(output)
    sha_path = output.with_suffix(output.suffix + ".sha256")
    sha_path.write_text(f"{sha}  {output.name}\n", encoding="utf-8")
    manifest_sidecar = output.with_suffix(output.suffix + ".manifest.json")
    manifest_sidecar.write_bytes(pretty_json(manifest))
    integrity_path = output.with_suffix(output.suffix + ".unzip-test.txt")
    integrity = _run("unzip", "-t", str(output), cwd=output.parent, check=False)
    integrity_path.write_text(integrity.stdout + integrity.stderr, encoding="utf-8")
    if integrity.returncode != 0:
        raise RuntimeError("ZIP integrity test failed")
    report = {
        "schema": "sip.checkpoint-build-report/v1",
        "status": "passed_complete",
        "checkpoint_id": CHECKPOINT_ID,
        "archive": str(output),
        "archive_sha256": sha,
        "archive_size": output.stat().st_size,
        "content_root_sha256": manifest["content_root_sha256"],
        "manifest_file_count": manifest["file_count"],
        "commit": commit,
        "tree": tree,
        "source_tree_root_sha256": source_root,
        "progress_12_authorized": False,
        "production_authorized": False,
    }
    _write(output.with_suffix(output.suffix + ".build.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--branch", default=BRANCH)
    args = parser.parse_args()
    report = build(output=args.output, attestation_path=args.attestation.resolve(), branch=args.branch)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
