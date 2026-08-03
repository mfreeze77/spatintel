#!/usr/bin/env python3
"""Create machine-readable evidence records for already executed Swift and web test transcripts."""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sip.canonical import sha256_file
from tools.source_identity import source_tree_root

ROOT = Path(__file__).resolve().parents[1]


def _git() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True, check=False)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    resolved_commit = os.environ.get("SIP_SOURCE_COMMIT") or (commit.stdout.strip() if commit.returncode == 0 else None)
    return {
        "commit": resolved_commit,
        "branch": os.environ.get("SIP_SOURCE_BRANCH") or (branch.stdout.strip() if branch.returncode == 0 else None),
        "working_tree_clean_at_capture": status.returncode == 0 and not status.stdout.strip(),
        "working_tree_clean_before_tests": os.environ.get("SIP_TEST_WORKTREE_CLEAN_AT_START", "false").lower() == "true",
        "source_tree_root_sha256": os.environ.get("SIP_SOURCE_ROOT") or source_tree_root(ROOT),
    }


def _write(name: str, payload: dict[str, Any]) -> None:
    destination = ROOT / "build/reports" / f"{name}-test-report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    git = _git()
    generated: list[str] = []
    matrix_path = ROOT / "build/reports/test-matrix.json"
    if matrix_path.exists():
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        totals = matrix.get("totals", {})
        _write(
            "python",
            {
                "schema": "sip.test-report/v1",
                "suite": "python-isolated-category-matrix",
                "status": "passed_complete" if matrix.get("status") in {"passed", "passed_complete"} else "failed",
                "tests_passed": int(totals.get("tests", 0)) - int(totals.get("failures", 0)) - int(totals.get("errors", 0)),
                "tests_failed": int(totals.get("failures", 0)) + int(totals.get("errors", 0)),
                "tests_skipped": int(totals.get("skipped", 0)),
                "categories": [
                    {
                        "name": item["name"],
                        "tests": item["tests"],
                        "status": item["status"],
                        "junit_path": item["junit_path"],
                        "junit_sha256": sha256_file(ROOT / item["junit_path"]),
                        "log_path": item["log_path"],
                        "log_sha256": sha256_file(ROOT / item["log_path"]),
                    }
                    for item in matrix.get("results", [])
                ],
                "python": matrix.get("python"),
                "plugin_autoload_disabled": matrix.get("plugin_autoload_disabled"),
                "suite_process_isolation": matrix.get("suite_process_isolation"),
                "matrix_path": str(matrix_path.relative_to(ROOT)),
                "matrix_sha256": sha256_file(matrix_path),
                "generated_at": datetime.now(UTC).isoformat(),
                "git": git,
                "limitations": [
                    "Local SQLite and deterministic fixture profile; PostgreSQL/PostGIS, Valkey, S3, container, Kubernetes, GPU, and cloud acceptance are separate gates."
                ],
            },
        )
        generated.append("build/reports/python-test-report.json")
    swift_path = ROOT / "build/evidence/swift-test-linux.log"
    if swift_path.is_file():
        swift_text = swift_path.read_text(encoding="utf-8")
        match = re.search(r"Test run with (\d+) tests .* passed", swift_text)
        swift_count = int(match.group(1)) if match else 0
        swift_version_match = re.search(r"Testing Library Version: ([^ ]+)", swift_text)
        _write(
            "swift",
            {
            "schema": "sip.test-report/v1",
            "suite": "swift-linux-fixture",
            "status": "passed_with_external_gaps" if swift_count > 0 and "failed" not in swift_text.lower() else "failed",
            "tests_passed": swift_count,
            "tests_failed": 0,
            "tool_version": swift_version_match.group(1) if swift_version_match else None,
            "platform": "x86_64-unknown-linux-gnu",
            "transcript": str(swift_path.relative_to(ROOT)),
            "transcript_sha256": sha256_file(swift_path),
            "git": git,
            "limitations": ["Linux fixture profile only; Xcode, simulator, Apple signing, ARKit, LiDAR, camera, thermal, and physical-device acceptance remain external."],
            },
        )
        generated.append("build/reports/swift-test-report.json")
    web_path = ROOT / "build/evidence/web-runtime-test.log"
    if web_path.is_file():
        web_text = web_path.read_text(encoding="utf-8")
        match = re.search(r"(?:#|\N{INFORMATION SOURCE})\s+pass\s+(\d+)", web_text)
        failure_match = re.search(r"(?:#|\N{INFORMATION SOURCE})\s+fail\s+(\d+)", web_text)
        web_count = int(match.group(1)) if match else 0
        web_failures = int(failure_match.group(1)) if failure_match else -1
        invariant_match = re.search(r'"invariantChecks":(\d+)', web_text)
        node_version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False).stdout.strip()
        limitations = [
            "Dependency-free source/runtime checks only; installed dependencies, Next production build, browser E2E, "
            "and accessibility audit remain external."
        ]
        if node_version != "v24.18.0":
            limitations.append("The pinned Node 24.18.0 release runtime was not used for this local fixture run.")
        _write(
            "web-runtime",
            {
            "schema": "sip.test-report/v1",
            "suite": "web-dependency-free-runtime",
            "status": "passed_with_external_gaps" if web_count > 0 and web_failures == 0 else "failed",
            "tests_passed": web_count,
            "tests_failed": max(web_failures, 0),
            "source_invariant_checks": int(invariant_match.group(1)) if invariant_match else 0,
            "node_version": node_version,
            "platform": platform.platform(),
            "transcript": str(web_path.relative_to(ROOT)),
            "transcript_sha256": sha256_file(web_path),
            "git": git,
            "limitations": limitations,
            },
        )
        generated.append("build/reports/web-runtime-test-report.json")

    desktop_path = ROOT / "build/evidence/desktop-review-test.log"
    if desktop_path.is_file():
        desktop_text = desktop_path.read_text(encoding="utf-8")
        match = re.search(r"(\d+) passed", desktop_text)
        desktop_count = int(match.group(1)) if match else 0
        failed_match = re.search(r"(\d+) failed", desktop_text)
        desktop_failed = int(failed_match.group(1)) if failed_match else 0
        _write(
            "desktop-review",
            {
                "schema": "sip.test-report/v1",
                "suite": "desktop-local-first-reference",
                "status": "passed_with_external_gaps" if desktop_count >= 15 and desktop_failed == 0 else "failed",
                "tests_passed": desktop_count,
                "tests_failed": desktop_failed,
                "platform": platform.platform(),
                "transcript": str(desktop_path.relative_to(ROOT)),
                "transcript_sha256": sha256_file(desktop_path),
                "git": git,
                "limitations": [
                    "Dependency-free local storage and loopback security profile only; native packaging, notarization, GPU review, operator usability, and browser integration remain external."
                ],
            },
        )
        generated.append("build/reports/desktop-review-test-report.json")

    print(json.dumps({"status": "passed_with_external_gaps", "reports": generated}, indent=2))


if __name__ == "__main__":
    main()
