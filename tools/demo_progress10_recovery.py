#!/usr/bin/env python3
"""Run the synthetic, local-only Progress 10 recovery and portability demonstration."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from sip.canonical import canonical_sha256
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, register_objective_and_point, verify_point

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build/evidence/demo-progress10-recovery.json"


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sip-progress10-demo-") as directory:
        root = Path(directory)
        env = bootstrap_recovery(root, name="p10-demo")
        asset = ingest_evidence(
            env["context"], env["tenant"], env["project"],
            payload=b"synthetic-progress-10-recovery-evidence",
            asset_id="p10-demo-source",
        )
        objective, point, requested = register_objective_and_point(env, idempotency_key="p10-demo-point")
        verified = verify_point(env, point)
        restore = env["context"].recovery.restore(
            tenant_id=env["tenant"],
            project_id=env["project"],
            requested_point_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            restore_mode="isolated_clone",
            target_tenant_id=f"restore-{env['tenant']}-demo",
            target_project_id=f"restore-{env['project']}-demo",
            target_region="local",
            idempotency_key="p10-demo-restore",
            actor_id="recovery-lead",
        )
        game_day = env["context"].recovery.run_game_day(
            deployment_profile_id=env["local"]["deployment_profile_id"],
            scenario="synthetic-object-store-and-control-plane-loss",
            evidence_class="local_executed",
            tenant_id=env["tenant"],
            project_id=env["project"],
            affected_services=["control-api", "object-store", "workflow-service"],
            affected_region="local",
            recovery_point_id=point["recovery_point_id"],
            portability_destination=root / "portability.zip",
            timeline=[
                {"step": "detect", "seconds": 0},
                {"step": "restore", "seconds": 4},
                {"step": "reconcile", "seconds": 7},
            ],
            metrics={"rpo_seconds": 5, "rto_seconds": 7, "writes_reopened": True},
            findings=[],
            actor_id="recovery-lead",
        )
        production = env["context"].recovery.production_recovery_admission(
            deployment_profile_id=env["local"]["deployment_profile_id"],
            actor_id="release-manager",
        )
        result: dict[str, object] = {
            "schema": "sip.progress10-recovery-demo/v1",
            "status": "passed_complete" if (
                verified["state"] == "verified"
                and restore["state"] == "completed"
                and restore["writes_reopened"] is True
                and game_day["state"] == "passed"
                and game_day["portability_export"]["verified"] is True
                and production["production_authorized"] is False
            ) else "failed",
            "synthetic_only": True,
            "evidence_class": "local_executed",
            "asset": asset,
            "objective_id": objective["recovery_objective_id"],
            "recovery_point_id": point["recovery_point_id"],
            "recovery_point_root_sha256": point["package_root_hash"],
            "restore": {
                "restore_run_id": restore["restore_id"],
                "state": restore["state"],
                "writes_reopened": restore["writes_reopened"],
                "blocking_findings": restore["reconciliation"]["blocking_findings"],
                "measured_rpo_seconds": restore["rpo_seconds_observed"],
                "measured_rto_seconds": restore["rto_seconds_observed"],
            },
            "game_day": {
                "game_day_id": game_day["recovery_game_day_id"],
                "state": game_day["state"],
                "evidence_class": game_day["evidence_class"],
                "portability_verified": game_day["portability_export"]["verified"],
            },
            "progress_11_authorized": False,
            "production_authorized": False,
            "production_admission": production,
            "external_gaps": [
                "managed PITR and object-version restore not executed",
                "multi-region, KMS, physical-edge, customer-data, and externally witnessed recovery not executed",
            ],
        }
        result["evidence_hash"] = canonical_sha256(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
