#!/usr/bin/env python3
"""Generate the exact bounded Progress 11 QA-002 milestone scope."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "requirements/requirements-ledger.json"
OUTPUT = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_11.json"
IDS = tuple(
    [f"CONTEST-{i:03d}" for i in range(1, 7)]
    + [f"LIFTEST-{i:03d}" for i in range(1, 7)]
    + [f"TSTSTRAT-{i:03d}" for i in range(1, 7)]
    + [f"TSTSEC-{i:03d}" for i in range(1, 7)]
    + [f"TSTGATE-{i:03d}" for i in range(1, 13)]
    + [f"DELMVP-{i:03d}" for i in range(1, 7)]
    + [f"DELROAD-{i:03d}" for i in range(1, 7)]
    + [f"DELDOD-{i:03d}" for i in range(1, 13)]
    + [f"HYBTEST-{i:03d}" for i in range(1, 17)]
    + [f"APPFAIL-{i:03d}" for i in range(1, 11)]
    + [f"SIPMIG-{i:03d}" for i in range(1, 11)]
)
EXTERNAL_ONLY = {
    "CONTEST-001", "CONTEST-002", "CONTEST-003",
    "LIFTEST-001", "LIFTEST-002", "LIFTEST-003", "LIFTEST-006",
    "TSTGATE-002", "TSTGATE-003", "TSTGATE-004", "TSTGATE-007",
    "DELDOD-003", "DELDOD-004", "DELDOD-009",
    "HYBTEST-011", "HYBTEST-013",
}
IMPLEMENTED_UNVERIFIED = {
    "TSTGATE-009", "TSTGATE-011", "DELMVP-002",
    "HYBTEST-008", "HYBTEST-010", "HYBTEST-012",
}
IMPLEMENTATION_FILES = {
    "CONTEST": ["tools/run_demo.py", "tools/demo_progress11_release.py", "src/sip/construction.py", "src/sip/scene.py"],
    "LIFTEST": ["tools/run_demo.py", "tools/demo_progress11_release.py", "src/sip/liveforever.py", "src/sip/exporting.py"],
    "TSTSTRAT": ["src/sip/release_assurance.py", "requirements/PROGRESS_11_TEST_STRATEGY.json", "tools/run_test_matrix.py"],
    "TSTSEC": ["src/sip/release_assurance.py", "src/sip/policy.py", "tests/security/test_progress11_release_adversarial.py"],
    "TSTGATE": ["src/sip/release_assurance.py", "tools/demo_progress11_release.py", "docs/operator/PROGRESS_11_RELEASE_GATES.md"],
    "DELMVP": ["tools/run_demo.py", "tools/demo_progress11_release.py", "src/sip/capture.py", "src/sip/scene.py", "src/sip/exporting.py"],
    "DELROAD": ["requirements/PROGRESS_11_ROADMAP.json", "docs/release/PROGRESS_11_ROADMAP_EVIDENCE.md"],
    "DELDOD": ["src/sip/release_assurance.py", "schemas/openapi/release-assurance.openapi.json", "docs/operator/PROGRESS_11_RELEASE_GATES.md"],
    "HYBTEST": ["src/sip/hybrid.py", "src/sip/representations.py", "src/sip/scene.py", "tools/demo_progress11_release.py"],
    "APPFAIL": ["src/sip/failures.py", "governance/failure-catalog.json", "tests/unit/test_failure_catalog.py"],
    "SIPMIG": ["src/sip/recovery.py", "src/sip/exporting.py", "migrations/versions/0020_progress10_recovery_retention.py", "tests/integration/test_progress10_preservation_migration.py"],
}
EVIDENCE_PATHS = [
    "build/reports/test-matrix.json",
    "build/evidence/progress11-release/demo-progress11-release.json",
    "build/reports/checkpoint-acceptance-gates.json",
    "build/reports/release-report.json",
]


def _tests() -> dict[str, list[dict[str, str]]]:
    result = {identifier: [] for identifier in IDS}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            doc = ast.get_docstring(node) or ""
            for identifier in IDS:
                if identifier in doc:
                    result[identifier].append({"test_id": f"{path.relative_to(ROOT).as_posix()}::{node.name}"})
    return result


def build() -> dict[str, Any]:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))["requirements"]
    by_id = {item["requirement_id"]: item for item in ledger}
    missing = sorted(set(IDS) - set(by_id))
    if missing:
        raise RuntimeError(f"Progress 11 requirements missing from ledger: {missing}")
    tests = _tests()
    included: list[dict[str, Any]] = []
    for identifier in IDS:
        item = by_id[identifier]
        prefix = identifier.split("-", 1)[0]
        if identifier in EXTERNAL_ONLY:
            status = "EXTERNAL_VALIDATION_REQUIRED"
            evidence_class = "external_validation_required"
        elif identifier in IMPLEMENTED_UNVERIFIED:
            status = "IMPLEMENTED_UNVERIFIED"
            evidence_class = "local_or_synthetic_executed"
        else:
            status = "VERIFIED"
            evidence_class = "local_or_synthetic_executed"
        included.append({
            "requirement_id": identifier,
            "priority": item["priority"],
            "requirement": item["text"],
            "source_document": item["source_document"],
            "source_line": item.get("source_line"),
            "verification_method": item.get("verification_method"),
            "status_at_scope_freeze": item.get("implementation_status"),
            "implementation_status": status,
            "evidence_class": evidence_class,
            "implementation_files": IMPLEMENTATION_FILES[prefix],
            "direct_tests": tests[identifier],
            "evidence_paths": EVIDENCE_PATHS,
        })
    return {
        "schema": "sip.milestone-scope/v1",
        "checkpoint_id": "sip-v1.1.0-progress-11",
        "branch": "progress-11-release-gates",
        "accepted_base_commit": "ab409f6ac7ca583535f69e5806b7a3bdbfe08214",
        "authorized_epics": ["QA-002"],
        "scope_statement": "Progress 11 is limited to QA-002 dual-vertical acceptance and release gates. It may retain local and synthetic acceptance evidence while leaving every unavailable mounted-browser, physical-device, GPU, credentialed-cloud, external-review, pilot, and production gate explicitly unpassed.",
        "dependency_rationale": "Progress 10 closed OPS-004 and True North authorized only QA-002 as its bounded successor.",
        "included_requirement_count": len(included),
        "deferred_requirement_count": 0,
        "included_requirements": included,
        "deferred_requirements": [],
        "acceptance_criteria": [
            "Construction and LiveForever scenarios retain direct, requirement-declared, source-bound evidence without using confidential or human-subject data.",
            "Measurement authority, restricted-data, consent, generated-content, conflicting-recollection, quiet-mode, accessibility, and offline-export stop-lines fail closed.",
            "Release gates distinguish command execution from control completeness and preserve external gaps.",
            "Release manifests reject stale, incomplete, mismatched, unsigned, or source-unbound evidence.",
            "Rollback, migration, export, restore, security, privacy, load, operating-envelope, support, and known-limitation evidence are retained.",
            "The exact committed source passes clean-detached acceptance and both dedicated package verifiers return zero findings.",
            "Progress 12 and production remain unauthorized.",
        ],
        "external_gaps": [
            "Mounted browser/runtime and formal accessibility execution remain external.",
            "Physical iOS/LiDAR/device execution remains external.",
            "Approved LingBot checkpoint, model rights, CUDA/GPU, and real-scene execution remain external.",
            "Credentialed cloud deployment and recovery remain external.",
            "Independent penetration, privacy, legal, usability, evidentiary, customer, and human-subject review remain external.",
        ],
        "explicitly_out_of_scope": [
            "PILOT-001 and all customer or human-subject pilots",
            "Progress 12",
            "production credentials, data, traffic, or promotion",
        ],
        "progress_11_authorized": True,
        "progress_12_authorized": False,
        "production_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Progress 11 milestone scope drift detected; run tools/build_progress11_scope.py")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print(json.dumps({"included": value["included_requirement_count"], "deferred": value["deferred_requirement_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
