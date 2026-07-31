from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, isolated_target, register_objective_and_point, verify_point


def test_progress10_synthetic_recovery_game_day_and_portability_demo(tmp_path: Path) -> None:
    """REQ: OPSDR-006, DATRET-005, PLTIO-003, PLTIO-006, LIFPRESV-004 synthetic service-loss recovery includes a verified portability package and measurable RPO/RTO without production claims."""
    env = bootstrap_recovery(tmp_path, name="p10-demo")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="game-day-source")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    game_day = env["context"].recovery.run_game_day(
        deployment_profile_id=env["local"]["deployment_profile_id"],
        scenario="synthetic-object-store-and-control-plane-loss",
        evidence_class="local_executed",
        tenant_id=env["tenant"], project_id=env["project"],
        affected_services=["control-api", "object-store", "workflow-service"],
        affected_region="local", recovery_point_id=point["recovery_point_id"],
        portability_destination=tmp_path / "game-day-portability.zip",
        timeline=[{"step": "detect", "seconds": 0}, {"step": "restore", "seconds": 4}, {"step": "reconcile", "seconds": 7}],
        metrics={"rpo_seconds": 5, "rto_seconds": 7, "writes_reopened": True},
        findings=[], actor_id="recovery-lead",
    )
    assert game_day["state"] == "passed"
    assert game_day["portability_export"]["verified"] is True
    assert game_day["evidence_class"] == "local_executed"
    assert env["context"].recovery.production_recovery_admission(
        deployment_profile_id=env["local"]["deployment_profile_id"], actor_id="release-manager"
    )["production_authorized"] is False
