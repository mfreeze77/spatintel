#!/usr/bin/env python3
"""Run all locally available language build/type checks and record unavailable profiles."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(name: str, command: list[str], *, cwd: Path = ROOT, required: bool = True) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": name,
        "status": "passed_complete" if completed.returncode == 0 else ("failed" if required else "blocked"),
        "required": required,
        "command": command,
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "output": ((completed.stdout or "") + (completed.stderr or ""))[-8000:],
    }


def _unavailable(name: str, tool: str, command: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "status": "blocked",
        "required": False,
        "command": command,
        "exit_code": None,
        "elapsed_seconds": 0,
        "output": f"{tool} is not installed in this execution environment",
    }


def run(*, release: bool = False) -> dict[str, object]:
    checks = [
        _run("python-compile", [sys.executable, "-m", "compileall", "-q", "src", "services", "workers", "tools"]),
        _run("web-source-contracts", ["node", "scripts/verify-source.mjs"], cwd=ROOT / "apps/web"),
        _run("swift-build", ["swift", "build"], cwd=ROOT / "apps/ios-capture"),
    ]
    optional = [
        ("python-ruff", "ruff", ["ruff", "check", "src", "services", "workers", "tools", "tests"]),
        ("python-mypy", "mypy", ["mypy", "src/sip"]),
    ]
    for name, tool, command in optional:
        checks.append(_run(name, command, required=release) if shutil.which(tool) else _unavailable(name, tool, command))
    node_modules = ROOT / "node_modules"
    if node_modules.exists() and shutil.which("npx"):
        checks.append(_run("typescript", ["npm", "--workspace", "apps/web", "run", "typecheck"], required=release))
    else:
        checks.append(_unavailable("typescript", "installed JavaScript dependency tree", ["npm", "--workspace", "apps/web", "run", "typecheck"]))
    failures = [item for item in checks if item["status"] == "failed"]
    blocked = [item for item in checks if item["status"] == "blocked"]
    aggregate = "failed" if failures else ("blocked" if release and blocked else ("passed_with_external_gaps" if blocked else "passed_complete"))
    return {
        "schema": "sip.typecheck-report/v1",
        "mode": "release" if release else "development",
        "status": aggregate,
        "checks": checks,
        "external_validation_required": [item["name"] for item in checks if item["status"] == "blocked"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/typecheck-report.json")
    args = parser.parse_args()
    report = run(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] in {"passed_complete", "passed_with_external_gaps"} else 1)


if __name__ == "__main__":
    main()
