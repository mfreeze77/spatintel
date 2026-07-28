#!/usr/bin/env python3
"""Validate source/model/provider rights, notices, and dependency lock coverage."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_governance import validate as validate_governance
from tools.generate_third_party_lock import DESTINATION as THIRD_PARTY_LOCK, build as build_third_party_lock


def _declared_dependencies() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"dependencies\s*=\s*\[(.*?)\]\n", text, re.S)
    if not block:
        return []
    return sorted(set(re.findall(r'"([A-Za-z0-9_.-]+)==', block.group(1))))


def run(*, release: bool = False) -> dict[str, object]:
    governance = validate_governance(release=release)
    packages: list[dict[str, object]] = []
    errors: list[dict[str, str]] = list(governance["errors"])
    warnings: list[dict[str, str]] = list(governance["warnings"])
    for name in _declared_dependencies():
        try:
            distribution = importlib.metadata.distribution(name)
            metadata = distribution.metadata
            licenses = [value for key, value in metadata.items() if key == "Classifier" and value.startswith("License ::")]
            packages.append({"name": name, "version": distribution.version, "license": metadata.get("License"), "classifiers": licenses})
            if not metadata.get("License") and not licenses:
                warnings.append({"code": "PACKAGE_LICENSE_METADATA_MISSING", "path": name, "message": "installed package exposes no license metadata; retain upstream license in SBOM review"})
        except importlib.metadata.PackageNotFoundError:
            errors.append({"code": "PINNED_PACKAGE_NOT_INSTALLED", "path": name, "message": "declared runtime dependency is absent"})
    expected_lock = build_third_party_lock()
    if not THIRD_PARTY_LOCK.is_file():
        errors.append({"code": "THIRD_PARTY_LOCK_MISSING", "path": str(THIRD_PARTY_LOCK), "message": "deterministic third-party manifest lock is missing"})
    else:
        try:
            actual_lock = json.loads(THIRD_PARTY_LOCK.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"code": "THIRD_PARTY_LOCK_INVALID", "path": str(THIRD_PARTY_LOCK), "message": str(exc)})
        else:
            if actual_lock != expected_lock:
                errors.append({"code": "THIRD_PARTY_LOCK_DRIFT", "path": str(THIRD_PARTY_LOCK), "message": "regenerate with tools/generate_third_party_lock.py"})

    notice = ROOT / "THIRD_PARTY_NOTICES.md"
    if not notice.is_file() or notice.stat().st_size < 100:
        errors.append({"code": "THIRD_PARTY_NOTICE_INCOMPLETE", "path": str(notice), "message": "notice file is missing or empty"})
    return {
        "schema": "sip.license-check/v1",
        "mode": "release" if release else "structural",
        "status": "passed" if not errors else "failed",
        "packages": packages,
        "governance": governance,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/license-gate.json")
    args = parser.parse_args()
    report = run(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
