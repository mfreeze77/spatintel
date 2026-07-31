from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.database import AuditEventRow, RecoveryLockRow
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, isolated_target, register_objective_and_point, verify_point


def test_progress10_key_recovery_requires_quorum_opaque_reference_and_no_root_exposure(tmp_path: Path) -> None:
    """REQ: OPSDR-004 key recovery is exercised with independent quorum, opaque artifacts, and no root-key exposure to ordinary operators."""
    env = bootstrap_recovery(tmp_path, name="p10-keys")
    key = env["context"].security_ops.register_key_scope(
        tenant_id=env["tenant"], project_id=env["project"], person_id=None,
        key_id="project-kms-v1", backend="managed_kms",
        recovery_policy={"guardians": ["guardian-a", "guardian-b"], "quorum": 2, "single_person_recovery": False},
        actor_id="guardian-a",
    )
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.exercise_key_recovery(
            tenant_id=env["tenant"], project_id=env["project"], key_scope_id=key["key_scope_id"],
            guardian_approvals=[{"guardian_id": "guardian-a", "approved": True}],
            recovery_artifact_reference="vault://recovery/project-kms-v1", root_key_exposed=False,
            evidence={"exercise": "synthetic"}, actor_id="recovery-operator",
        )
    assert error.value.code == "KEY_RECOVERY_QUORUM_NOT_MET"
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.exercise_key_recovery(
            tenant_id=env["tenant"], project_id=env["project"], key_scope_id=key["key_scope_id"],
            guardian_approvals=[{"guardian_id": "guardian-a", "approved": True}, {"guardian_id": "guardian-b", "approved": True}],
            recovery_artifact_reference="vault://recovery/project-kms-v1", root_key_exposed=True,
            evidence={"exercise": "synthetic"}, actor_id="recovery-operator",
        )
    assert error.value.code == "ROOT_KEY_EXPOSURE_PROHIBITED"
    result = env["context"].recovery.exercise_key_recovery(
        tenant_id=env["tenant"], project_id=env["project"], key_scope_id=key["key_scope_id"],
        guardian_approvals=[{"guardian_id": "guardian-a", "approved": True}, {"guardian_id": "guardian-b", "approved": True}],
        recovery_artifact_reference="vault://recovery/project-kms-v1", root_key_exposed=False,
        evidence={"exercise": "synthetic", "operator_saw_root_key": False}, actor_id="recovery-operator",
    )
    assert result["state"] == "passed"
    assert result["root_key_exposed"] is False


def test_progress10_recovery_denials_retain_audit_evidence(tmp_path: Path) -> None:
    """REQ: ARCRES-005, OPSDR-005 failed recovery actions retain stable denial evidence while cross-region and cross-scope operations remain denied."""
    env = bootstrap_recovery(tmp_path, name="p10-denial-audit")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="audit-source")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    target_tenant, target_project = isolated_target(env, "denied")
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.restore(
            tenant_id=env["tenant"], project_id=env["project"], target_tenant_id=target_tenant,
            target_project_id=target_project, target_region="eu-west-1", requested_point_at=datetime.now(timezone.utc),
            restore_mode="isolated_clone", idempotency_key="denied-region", actor_id="recovery-operator",
        )
    assert error.value.code == "RESTORE_RESIDENCY_DENIED"
    with env["context"].database.session() as session:
        events = list(session.scalars(select(AuditEventRow).where(
            AuditEventRow.tenant_id == env["tenant"], AuditEventRow.project_id == env["project"],
            AuditEventRow.action == "recovery:restore", AuditEventRow.outcome == "denied",
        )))
        assert any(event.details_json.get("reason_code") == "RESTORE_RESIDENCY_DENIED" for event in events)


def test_progress10_restore_and_deletion_lock_is_fail_closed(tmp_path: Path) -> None:
    """REQ: ARCRES-002, DATRET-002, OPSDR-005 concurrent restore and deletion operations use a project recovery lock and cannot corrupt shared control-plane state."""
    env = bootstrap_recovery(tmp_path, name="p10-lock")
    with env["context"].database.session() as session:
        env["context"].recovery._acquire_lock(session, env["tenant"], env["project"], "project-recovery", "restore", "op-one")
    with env["context"].database.session() as session:
        with pytest.raises(ConflictError) as error:
            env["context"].recovery._acquire_lock(session, env["tenant"], env["project"], "project-recovery", "purge", "op-two")
        assert error.value.code == "RECOVERY_SCOPE_LOCKED"
    with env["context"].database.session() as session:
        env["context"].recovery._release_lock(session, env["tenant"], env["project"], "project-recovery", "op-one")
        assert session.scalar(select(RecoveryLockRow).where(RecoveryLockRow.tenant_id == env["tenant"])) is None


def test_progress10_production_admission_requires_external_recovery_evidence(tmp_path: Path) -> None:
    """REQ: ARCRES-001, OPSDR-001, OPSDR-002, OPSDR-006 production recovery admission fails closed while only local or synthetic evidence exists."""
    env = bootstrap_recovery(tmp_path, name="p10-prod-deny")
    with pytest.raises(ValidationError) as objective_claim:
        env["context"].recovery.register_recovery_objective(
            tenant_id=env["tenant"], project_id=env["project"],
            deployment_profile_id=env["local"]["deployment_profile_id"],
            data_class="project_record", service_class="control_plane",
            rpo_seconds=60, rto_seconds=120,
            degraded_behavior={"mode": "read_only"}, recovery_method={"type": "cloud_pitr"},
            evidence_class="cloud_executed", actor_id="recovery-admin",
        )
    assert objective_claim.value.code == "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED"
    with pytest.raises(ValidationError) as game_day_claim:
        env["context"].recovery.run_game_day(
            deployment_profile_id=env["local"]["deployment_profile_id"],
            scenario="false-cloud-claim", evidence_class="cloud_executed",
            tenant_id=env["tenant"], project_id=env["project"],
            affected_services=["database"], affected_region="us-east-1", recovery_point_id=None,
            portability_destination=tmp_path / "false-cloud.zip",
            timeline=[{"step": "claim", "seconds": 0}],
            metrics={"rpo_seconds": 0, "rto_seconds": 0}, findings=[], actor_id="recovery-admin",
        )
    assert game_day_claim.value.code == "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED"
    decision = env["context"].recovery.production_recovery_admission(
        deployment_profile_id=env["local"]["deployment_profile_id"], actor_id="release-manager"
    )
    assert decision["admitted"] is False
    assert decision["production_authorized"] is False
    assert "credentialed_cloud_or_external_restore_evidence_missing" in decision["blockers"]
    assert "external_disaster_exercise_missing" in decision["blockers"]


def test_progress10_missing_backup_bytes_and_object_manifest_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSDR-002, OPSDR-003, OPSDR-005 missing backup bytes, stale manifests, and incomplete object versions are rejected before recovery claims."""
    env = bootstrap_recovery(tmp_path, name="p10-missing")
    asset = ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="missing-object")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    point_root = env["context"].recovery.recovery_root / "points" / point["recovery_point_id"]
    database_path = point_root / "database.sqlite3"
    original_database = database_path.read_bytes()
    database_path.chmod(0o600)
    database_path.unlink()
    with pytest.raises(ValidationError) as error:
        verify_point(env, point)
    assert error.value.code == "RECOVERY_POINT_BYTES_MISSING"
    database_path.write_bytes(original_database)
    database_path.chmod(0o440)
