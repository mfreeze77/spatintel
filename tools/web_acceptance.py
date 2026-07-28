#!/usr/bin/env python3
"""Run the frozen full web acceptance profile or record an explicit blocker."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"
EXPECTED_NODE = "v24.18.0"
EXPECTED_PNPM = "10.28.2"


def _capture(command: list[str], *, cwd: Path = ROOT, timeout: int = 600) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "command": command,
            "cwd": str(cwd.relative_to(ROOT)) if cwd != ROOT else ".",
            "exit_code": completed.returncode,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd.relative_to(ROOT)) if cwd != ROOT else ".",
            "exit_code": 124,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            "stderr": ((exc.stderr or "")[-12000:] if isinstance(exc.stderr, str) else "") + "\ncommand timed out",
        }


def _version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def run() -> dict[str, Any]:
    node = _version(["node", "--version"])
    corepack = _version(["corepack", "--version"])
    pnpm = _version(["pnpm", "--version"])
    lockfile = ROOT / "pnpm-lock.yaml"
    blockers: list[str] = []
    attempts: list[dict[str, Any]] = []
    if node != EXPECTED_NODE:
        blockers.append(f"Node {EXPECTED_NODE} is required; available version is {node or 'unavailable'}")
    if corepack is None:
        blockers.append("Corepack is unavailable")
    if pnpm != EXPECTED_PNPM:
        if corepack is not None:
            attempts.append(_capture(["corepack", "enable"], timeout=60))
            attempts.append(_capture(["corepack", "prepare", f"pnpm@{EXPECTED_PNPM}", "--activate"], timeout=120))
            pnpm = _version(["pnpm", "--version"])
        if pnpm != EXPECTED_PNPM:
            blockers.append(f"pnpm {EXPECTED_PNPM} is required; available version is {pnpm or 'unavailable'}")
    if not lockfile.is_file():
        blockers.append("pnpm-lock.yaml is absent because registry access was unavailable; frozen installation cannot be proven")
    commands = [
        ["pnpm", "install"],
        ["pnpm", "install", "--frozen-lockfile"],
        ["pnpm", "--dir", "apps/web", "lint"],
        ["pnpm", "--dir", "apps/web", "typecheck"],
        ["pnpm", "--dir", "apps/web", "build"],
        ["pnpm", "--dir", "apps/web", "test"],
    ]
    if not blockers:
        for command in commands:
            attempt = _capture(command, timeout=1200)
            attempts.append(attempt)
            if attempt["exit_code"] != 0:
                blockers.append(f"command failed: {' '.join(command)}")
                break
    status = "passed_complete" if not blockers and all(item["exit_code"] == 0 for item in attempts) else "blocked"
    return {
        "schema": "sip.web-acceptance-report/v1",
        "status": status,
        "captured_at": datetime.now(UTC).isoformat(),
        "required_toolchain": {"node": EXPECTED_NODE, "pnpm": EXPECTED_PNPM},
        "observed_toolchain": {"node": node, "corepack": corepack, "pnpm": pnpm},
        "lockfile": {"path": "pnpm-lock.yaml", "present": lockfile.is_file()},
        "required_commands": commands,
        "attempts": attempts,
        "blockers": blockers,
        "limitations": [
            "A dependency-free runtime/source suite is a separate control and does not replace lint, TypeScript typecheck, Next production build, or browser acceptance."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/web-full-acceptance.json")
    parser.add_argument("--transcript", type=Path, default=ROOT / "build/evidence/web-full-acceptance.log")
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.transcript.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    args.transcript.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["status"] == "passed_complete" else 2)


if __name__ == "__main__":
    main()
