#!/usr/bin/env python3
"""Attest the exact clean detached Git source used for checkpoint acceptance."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_identity import source_identity


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(args)}\n{completed.stderr}")
    return completed


def _git(*args: str) -> str:
    return _run("git", *args).stdout.strip()


def create(*, branch: str) -> dict[str, Any]:
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RuntimeError("test-source attestation requires a clean worktree")
    symbolic = _run("git", "symbolic-ref", "-q", "HEAD", check=False)
    if symbolic.returncode == 0:
        raise RuntimeError("test-source attestation requires a detached worktree")
    commit = _git("rev-parse", "HEAD")
    branch_ref = _run("git", "show-ref", "--verify", f"refs/heads/{branch}", check=False)
    if branch_ref.returncode != 0 or branch_ref.stdout.split()[0] != commit:
        raise RuntimeError(f"branch {branch!r} does not identify detached commit {commit}")
    parents = _git("show", "-s", "--format=%P", "HEAD").split()
    if not parents:
        raise RuntimeError("checkpoint commit must have a parent")
    identity = source_identity(ROOT)
    return {
        "schema": "sip.test-source-attestation/v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "commit": commit,
        "parent": parents[0],
        "tree": _git("show", "-s", "--format=%T", "HEAD"),
        "branch": branch,
        "commit_timestamp": _git("show", "-s", "--format=%cI", "HEAD"),
        "detached": True,
        "clean_before_tests": True,
        "git_status": "",
        "git_status_sha256": __import__("hashlib").sha256(b"").hexdigest(),
        "source_tree_root_sha256": identity["source_tree_root_sha256"],
        "source_root_policy_path": identity["policy_path"],
        "source_root_policy_sha256": identity["policy_sha256"],
        "source_root_file_count": identity["file_count"],
        "environment": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "working_directory": str(ROOT),
            "user": os.environ.get("USER"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="progress-04-r1-remediation")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = create(branch=args.branch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
