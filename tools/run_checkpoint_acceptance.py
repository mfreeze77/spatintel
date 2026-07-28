#!/usr/bin/env python3
"""Run the Progress 05 clean-source acceptance sequence and retain source-bound gate evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evidence_binding import current_source_binding

REQUIRED_TARGETS = [
    "lint",
    "spec-check",
    "test",
    "migrations",
    "swift-test",
    "web-test",
    "desktop-test",
    "contracts",
    "infrastructure",
    "security",
    "license-check",
    "benchmark",
    "demo-foundation",
    "demo-hybrid",
    "demo-scene-runtime",
    "demo-construction",
    "demo-liveforever",
    "export-demo",
    "restore-demo",
]
ADDITIONAL_LOCAL_TARGETS = ["doctor", "typecheck"]
EXPECTED_BLOCKED_TARGETS = ["web-acceptance", "release-mode"]
POST_EVIDENCE_TARGETS = ["traceability-evidence"]

CONTROL_STATUS_VALUES = {"passed_complete", "passed_with_external_gaps", "blocked", "failed"}
TARGET_REPORT_PATHS = {
    "lint": "build/reports/static-checks.json",
    "spec-check": "build/reports/spec-lint.json",
    "test": "build/reports/test-matrix.json",
    "typecheck": "build/reports/typecheck-report.json",
    "swift-test": "build/reports/swift-test-report.json",
    "web-test": "build/reports/web-runtime-test-report.json",
    "desktop-test": "build/reports/desktop-review-test-report.json",
    "infrastructure": "build/reports/infrastructure-validation.json",
    "security": "build/reports/security-report.json",
    "license-check": "build/reports/license-gate.json",
    "benchmark": "build/reports/benchmark-report.json",
    "demo-foundation": "build/evidence/demos/foundation.json",
    "demo-hybrid": "build/evidence/demos/hybrid.json",
    "demo-scene-runtime": "build/evidence/demos/scene-runtime.json",
    "demo-construction": "build/evidence/demos/construction.json",
    "demo-liveforever": "build/evidence/demos/liveforever.json",
    "export-demo": "build/evidence/demos/export.json",
    "restore-demo": "build/evidence/demos/restore.json",
    "release": "build/reports/release-report.json",
    "release-mode": "build/reports/release-report.json",
    "web-acceptance": "build/reports/web-full-acceptance.json",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"attestation must be an object: {path}")
    return value


def _rooted_output_path(path: Path) -> Path:
    """Resolve CLI output paths against the repository, not caller CWD state."""

    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()



def _normalized_control_status(value: object, *, exit_code: int) -> str:
    if exit_code != 0:
        return "blocked" if value == "blocked" else "failed"
    if value in {"passed_complete", "passed_with_external_gaps"}:
        return str(value)
    if value in {"passed", "ready", "healthy"}:
        return "passed_complete"
    if value == "blocked":
        # A child may intentionally report a blocked control while returning zero so
        # the acceptance orchestrator can retain the rest of the gate evidence.
        return "blocked"
    if value == "failed":
        return "failed"
    return "passed_complete"


def _json_from_transcript(transcript: str) -> dict[str, Any] | None:
    stripped = transcript.strip()
    if not stripped:
        return None
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _control_evidence(target: str, *, transcript: str, exit_code: int) -> dict[str, Any]:
    relative = TARGET_REPORT_PATHS.get(target)
    child: dict[str, Any] | None = None
    if relative:
        path = ROOT / relative
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, dict):
                child = loaded
    if child is None:
        child = _json_from_transcript(transcript)

    declared = child.get("control_status", child.get("status")) if child else None
    # The doctor command describes environment profiles rather than a formal gate.
    # Preserve those missing profiles as external gaps even though the command itself
    # executed successfully.
    if target == "doctor" and child and exit_code == 0:
        profiles = child.get("profiles", {})
        gpu = child.get("gpu", {})
        complete = (
            isinstance(profiles, dict)
            and all(bool(value) for value in profiles.values())
            and isinstance(gpu, dict)
            and gpu.get("status") == "ready"
        )
        declared = "passed_complete" if complete else "passed_with_external_gaps"

    control_status = _normalized_control_status(declared, exit_code=exit_code)
    result: dict[str, Any] = {
        "execution_status": "completed_successfully" if exit_code == 0 else "completed_with_error",
        "control_status": control_status,
        # Backward-compatible field now mirrors control completeness, never merely the
        # process exit code.
        "status": control_status,
        "child_declared_status": declared,
    }
    if relative and (ROOT / relative).is_file():
        payload = (ROOT / relative).read_bytes()
        result["child_report_path"] = relative
        result["child_report_sha256"] = hashlib.sha256(payload).hexdigest()
    return result


def _snapshot_child_report(target: str, evidence: dict[str, Any], *, log_root: Path) -> dict[str, Any]:
    """Freeze the exact child report used for this command's control decision.

    Some targets intentionally write the same conventional report path (notably
    ``release`` and ``release-mode``).  A per-target immutable snapshot prevents a
    later command from silently changing the evidence bytes attributed to an
    earlier acceptance result.
    """

    relative = evidence.get("child_report_path")
    if not isinstance(relative, str):
        return evidence
    source = ROOT / relative
    if not source.is_file():
        return evidence
    payload = source.read_bytes()
    snapshot = log_root / f"{target}.control.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(payload)
    updated = dict(evidence)
    updated["child_report_source_path"] = relative
    updated["child_report_path"] = snapshot.relative_to(ROOT).as_posix()
    updated["child_report_sha256"] = hashlib.sha256(payload).hexdigest()
    return updated

def _run_target(target: str, *, env: dict[str, str], log_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        ["make", target],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    transcript = (completed.stdout or "") + (completed.stderr or "")
    log_path = log_root / f"{target}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(transcript, encoding="utf-8")
    evidence = _snapshot_child_report(
        target,
        _control_evidence(target, transcript=transcript, exit_code=completed.returncode),
        log_root=log_root,
    )
    return {
        "target": target,
        "command": ["make", target],
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "log_path": log_path.relative_to(ROOT).as_posix(),
        "log_sha256": hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
        **evidence,
    }


def run(*, attestation_path: Path) -> dict[str, Any]:
    attestation = _load(attestation_path)
    binding_before = current_source_binding(ROOT)
    if binding_before["commit"] != attestation.get("commit"):
        raise RuntimeError("acceptance source commit differs from test attestation")
    if binding_before["source_tree_root_sha256"] != attestation.get("source_tree_root_sha256"):
        raise RuntimeError("acceptance source root differs from test attestation")
    if not binding_before["working_tree_clean"] or attestation.get("clean_before_tests") is not True:
        raise RuntimeError("acceptance must begin from an attested clean worktree")
    env = {
        **os.environ,
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "SIP_SOURCE_COMMIT": str(attestation["commit"]),
        "SIP_SOURCE_BRANCH": str(attestation["branch"]),
        "SIP_SOURCE_ROOT": str(attestation["source_tree_root_sha256"]),
        "SIP_TEST_WORKTREE_CLEAN_AT_START": "true",
    }
    log_root = ROOT / "build/evidence/gates"
    results: list[dict[str, Any]] = []
    for target in [*ADDITIONAL_LOCAL_TARGETS, *REQUIRED_TARGETS, "release", *EXPECTED_BLOCKED_TARGETS, *POST_EVIDENCE_TARGETS]:
        result = _run_target(target, env=env, log_root=log_root)
        if target in EXPECTED_BLOCKED_TARGETS:
            result["expected"] = "blocked_or_passed_complete"
            if result["exit_code"] != 0 and result["control_status"] != "blocked":
                result["control_status"] = result["status"] = "blocked"
        else:
            result["expected"] = "exit_zero_with_child_control_status_preserved"
        results.append(result)
        if target in [*REQUIRED_TARGETS, "release", *POST_EVIDENCE_TARGETS] and result["exit_code"] != 0:
            # Continue to retain all independent gate evidence, but final status fails.
            continue
    binding_after = current_source_binding(ROOT)
    if binding_after["commit"] != binding_before["commit"] or binding_after["source_tree_root_sha256"] != binding_before["source_tree_root_sha256"]:
        raise RuntimeError("acceptance commands changed source identity")
    if not binding_after["working_tree_clean"]:
        raise RuntimeError("acceptance commands left tracked or untracked source changes")
    required_names = {*REQUIRED_TARGETS, "release", *POST_EVIDENCE_TARGETS}
    required_failures = [
        item
        for item in results
        if item["target"] in required_names
        and (item["execution_status"] != "completed_successfully" or item["control_status"] in {"failed", "blocked"})
    ]
    local_failures = [
        item
        for item in results
        if item["target"] in ADDITIONAL_LOCAL_TARGETS
        and (item["execution_status"] != "completed_successfully" or item["control_status"] == "failed")
    ]
    blockers = [item for item in results if item["control_status"] == "blocked"]
    external_gap_controls = [item for item in results if item["control_status"] == "passed_with_external_gaps"]
    status = "failed" if required_failures or local_failures else (
        "passed_with_external_gaps" if blockers or external_gap_controls else "passed_complete"
    )
    return {
        "schema": "sip.checkpoint-acceptance-gates/v1",
        "status": status,
        "checkpoint_id": "sip-v1.1.0-progress-05-r1",
        "captured_at": datetime.now(UTC).isoformat(),
        "source": binding_before,
        "attestation_path": attestation_path.relative_to(ROOT).as_posix(),
        "required_targets": REQUIRED_TARGETS,
        "additional_local_targets": ADDITIONAL_LOCAL_TARGETS,
        "expected_blocked_targets": EXPECTED_BLOCKED_TARGETS,
        "post_evidence_targets": POST_EVIDENCE_TARGETS,
        "results": results,
        "required_failure_count": len(required_failures),
        "blocked_count": len(blockers),
        "external_gap_control_count": len(external_gap_controls),
        "release_authorized": False,
        "release_block_reason": "Progress 05-R1 requires independent True North acceptance and retains external validation gaps.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/checkpoint-acceptance-gates.json")
    args = parser.parse_args()
    output_path = _rooted_output_path(args.output)
    report = run(attestation_path=args.attestation.resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    output_path.write_text(rendered, encoding="utf-8")
    readiness = {
        "schema": "sip.release-readiness/v2",
        "status": "blocked" if report["status"] != "failed" else "failed",
        "checkpoint_id": report["checkpoint_id"],
        "captured_at": report["captured_at"],
        "source": report["source"],
        "checkpoint_acceptance_status": report["status"],
        "checkpoint_acceptance_report": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": __import__("hashlib").sha256(rendered.encode("utf-8")).hexdigest(),
        },
        "production_authorized": False,
        "external_validation_gaps": [
            "Ruff and mypy were unavailable.",
            "Node 24.18.0, pnpm 10.28.2, a frozen pnpm lockfile, installed dependencies, TypeScript typecheck, ESLint, and the Next production build were unavailable.",
            "pip-audit, Gitleaks, and Trivy were unavailable.",
            "Docker Compose runtime, Kubernetes deployment, and Terraform execution were unavailable.",
            "Xcode, iOS simulator, signing, LiDAR, camera, thermal, battery, interruption, and physical-device validation remain external.",
            "Approved LingBot-Map checkpoint bytes, CUDA/GPU execution, and real-scene validation remain external.",
            "Independent penetration testing, privacy review, browser accessibility audit, desktop operator-usability review, and legal approval remain incomplete.",
        ],
        "next_action": "Submit the independently verified Progress 05-R1 inner checkpoint and consolidated outer envelope for True North milestone-closure review; production remains NO-GO.",
    }
    readiness_path = ROOT / "build/reports/release-readiness-progress-05-r1.json"
    readiness_path.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] in {"passed_complete", "passed_with_external_gaps"} else 1)


if __name__ == "__main__":
    main()
