"""Canonical source binding embedded in generated checkpoint evidence."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from tools.source_identity import source_identity


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def current_source_binding(root: Path) -> dict[str, Any]:
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    identity = source_identity(root)
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "show", "-s", "--format=%T", "HEAD"),
        "branch": _git(root, "branch", "--show-current") or None,
        "working_tree_clean": status == "",
        "git_status_sha256": __import__("hashlib").sha256((status or "UNAVAILABLE").encode("utf-8")).hexdigest(),
        "source_tree_root_sha256": identity["source_tree_root_sha256"],
        "source_root_policy_sha256": identity["policy_sha256"],
        "source_root_file_count": identity["file_count"],
    }
