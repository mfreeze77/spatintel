#!/usr/bin/env python3
"""Run the Progress 05 clean-source acceptance sequence and retain source-bound gate evidence."""
from __future__ import annotations

import argparse
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


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"attestation must be an object: {path}")
    return value


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
    return {
        "target": target,
        "command": ["make", target],
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "log_path": log_path.relative_to(ROOT).as_posix(),
        "log_sha256": __import__("hashlib").sha256(transcript.encode("utf-8")).hexdigest(),
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
            result["status"] = "passed_complete" if result["exit_code"] == 0 else "blocked"
        else:
            result["expected"] = "exit_zero"
            result["status"] = "passed_complete" if result["exit_code"] == 0 else "failed"
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
    required_failures = [item for item in results if item["target"] in required_names and item["status"] != "passed_complete"]
    local_failures = [item for item in results if item["target"] in ADDITIONAL_LOCAL_TARGETS and item["status"] == "failed"]
    blockers = [item for item in results if item["status"] == "blocked"]
    status = "failed" if required_failures or local_failures else ("passed_with_external_gaps" if blockers else "passed_complete")
    return {
        "schema": "sip.checkpoint-acceptance-gates/v1",
        "status": status,
        "checkpoint_id": "sip-v1.1.0-progress-05",
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
        "release_authorized": False,
        "release_block_reason": "Progress 05 requires independent True North acceptance and retains external validation gaps.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/checkpoint-acceptance-gates.json")
    args = parser.parse_args()
    report = run(attestation_path=args.attestation.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    readiness = {
        "schema": "sip.release-readiness/v2",
        "status": "blocked" if report["status"] != "failed" else "failed",
        "checkpoint_id": report["checkpoint_id"],
        "captured_at": report["captured_at"],
        "source": report["source"],
        "checkpoint_acceptance_status": report["status"],
        "checkpoint_acceptance_report": {
            "path": args.output.relative_to(ROOT).as_posix(),
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
        "next_action": "Build and independently verify the Progress 05 inner checkpoint and outer delivery envelope, then submit them for True North review; production remains NO-GO.",
    }
    readiness_path = ROOT / "build/reports/release-readiness-progress-05.json"
    readiness_path.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] in {"passed_complete", "passed_with_external_gaps"} else 1)


if __name__ == "__main__":
    main()
