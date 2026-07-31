#!/usr/bin/env python3
"""Generate the exact bounded Progress 09 OPS-003 milestone scope."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "requirements/requirements-ledger.json"
OUTPUT = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_09.json"
IDS = tuple(
    [f"ARCDEP-{index:03d}" for index in range(1, 6)]
    + [f"OPSHYB-{index:03d}" for index in range(1, 7)]
    + [f"OPSAWS-{index:03d}" for index in range(1, 7)]
)
VERIFIED_LOCALLY = {"ARCDEP-003", "ARCDEP-005", "OPSHYB-003", "OPSHYB-005"}
IMPLEMENTATION_FILES = {
    "ARCDEP": [
        "src/sip/deployment.py", "src/sip/api.py", "src/sip/assets.py", "src/sip/operations.py",
        "src/sip/database.py", "infrastructure/deployment/profiles", "infrastructure/compose/docker-compose.yml",
        "infrastructure/kubernetes/base", "infrastructure/terraform", "migrations/versions/0019_progress09_deployment_profiles.py",
    ],
    "OPSHYB": [
        "src/sip/deployment.py", "src/sip/security_ops.py", "src/sip/api.py", "src/sip/database.py",
        "infrastructure/deployment/profiles", "migrations/versions/0019_progress09_deployment_profiles.py",
        "docs/operator/PROGRESS_09_DEPLOYMENT_RUNBOOK.md",
    ],
    "OPSAWS": [
        "src/sip/deployment.py", "src/sip/api.py", "src/sip/database.py",
        "infrastructure/terraform/modules/aws-platform", "infrastructure/deployment/profiles/aws-reference.json",
        "migrations/versions/0019_progress09_deployment_profiles.py", "docs/operator/PROGRESS_09_DEPLOYMENT_RUNBOOK.md",
    ],
}


def _tests() -> dict[str, list[dict[str, str]]]:
    result = {identifier: [] for identifier in IDS}
    for path in sorted((ROOT / "tests").rglob("test_progress09*.py")):
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
    tests = _tests()
    included = []
    for identifier in IDS:
        item = by_id[identifier]
        prefix = identifier.split("-", 1)[0]
        status = "VERIFIED" if identifier in VERIFIED_LOCALLY else "IMPLEMENTED_UNVERIFIED"
        included.append({
            "requirement_id": identifier,
            "priority": item["priority"],
            "requirement": item["text"],
            "source_document": item["source_document"],
            "source_line": item.get("source_line"),
            "verification_method": item.get("verification_method"),
            "status_at_scope_freeze": item.get("implementation_status"),
            "implementation_status": status,
            "implementation_files": IMPLEMENTATION_FILES[prefix],
            "direct_tests": tests[identifier],
            "evidence_paths": [
                "build/reports/test-matrix.json",
                "build/reports/tests/contract.xml",
                "build/reports/tests/integration.xml",
                "build/reports/tests/security.xml",
                "build/evidence/demo-progress09-deployment.json",
            ],
        })
    return {
        "schema": "sip.milestone-scope/v1",
        "checkpoint_id": "sip-v1.1.0-progress-09",
        "branch": "progress-09-deployment",
        "accepted_base_commit": "cc3c24ca3acff704144ed7d112566a2acaa88d79",
        "authorized_epics": ["OPS-003"],
        "scope_statement": "Progress 09 is limited to OPS-003 deployment profiles and production-shaped infrastructure. OPS-004, QA-002, pilots, Progress 10, production data, production traffic, and production promotion remain unauthorized.",
        "dependency_rationale": "Progress 08 closed OPS-002 and True North authorized only OPS-003 as its bounded successor.",
        "included_requirement_count": len(included),
        "deferred_requirement_count": 0,
        "included_requirements": included,
        "deferred_requirements": [],
        "acceptance_criteria": [
            "cross-tenant deployment boundaries fail closed",
            "default-deny network policy is explicit and generated",
            "region and residency admission occurs before upload and scheduling",
            "source, images, manifests, logs, and support evidence contain no embedded secrets",
            "service images and release manifests bind immutable digests and exact source commits",
            "edge workload identities are short-lived, scope-bound, revocable, and signed",
            "autoscaling enforces tenant/profile quotas and global budget limits under concurrency",
            "local upgrades and offline edge updates are signed, reversible, and export compatible",
            "project migrations preserve stable IDs, history, permissions, consent, hashes, and model/run manifests",
            "object-store and queue continuity plus graceful job recovery are retained",
            "configuration drift is detected against immutable profile intent",
            "production admission remains fail closed without external executed deployment evidence",
            "complete exact-commit acceptance and both dedicated package verifiers return zero findings",
        ],
        "external_gaps": [
            "Docker Compose structural validation is not an executed deployment.",
            "Kubernetes manifests and policies require an executable cluster and independent network-policy validation.",
            "Terraform syntax and structural checks require provider initialization, plan, apply, and credentialed AWS evidence.",
            "Image digest sentinels require approved built, signed, and scanned release images.",
            "Edge-node controls require physical encrypted hardware, update, rollback, revocation, and offline operation evidence.",
            "Cloud autoscaling, object-store, queue, database, CDN, KMS, secrets, and GPU controls require deployed infrastructure evidence.",
        ],
        "explicitly_out_of_scope": [
            "OPS-004 disaster recovery certification",
            "QA-002 final release gates",
            "customer or human-subject pilots",
            "production credentials, data, or traffic",
            "Progress 10",
            "production promotion",
        ],
        "progress_09_authorized": True,
        "progress_10_authorized": False,
        "production_authorized": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Progress 09 milestone scope drift detected; run tools/build_progress09_scope.py")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print(json.dumps({"included": value["included_requirement_count"], "deferred": value["deferred_requirement_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
