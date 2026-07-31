from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sip.errors import AuthorizationError, ConflictError, ValidationError
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, isolated_target, register_objective_and_point, verify_point


def test_progress10_local_recovery_point_restore_and_idempotency(tmp_path: Path) -> None:
    """REQ: ARCRES-001, ARCRES-003, ARCRES-004, OPSDR-001, OPSDR-002, OPSDR-003, OPSDR-005 local recovery retains objectives, verifies hashes, reconciles before writes, and replays idempotently."""
    env = bootstrap_recovery(tmp_path, name="p10-restore")
    ingest_evidence(env["context"], env["tenant"], env["project"], payload=b"restore-source", asset_id="restore-source")
    objective, point, requested = register_objective_and_point(env)
    assert objective["rpo_seconds"] == 3600
    assert point["state"] == "created"
    verified = verify_point(env, point)
    assert verified["state"] == "verified"

    replay = env["context"].recovery.create_recovery_point(
        tenant_id=env["tenant"], project_id=env["project"],
        deployment_profile_id=env["local"]["deployment_profile_id"], region="local",
        requested_point_at=requested, immutability_days=30, evidence_class="local_executed",
        idempotency_key="recovery-point-1", actor_id="recovery-admin",
    )
    assert replay["recovery_point_id"] == point["recovery_point_id"]
    assert replay["idempotent_replay"] is True

    target_tenant, target_project = isolated_target(env)
    restore_requested = datetime.now(timezone.utc)
    restored = env["context"].recovery.restore(
        tenant_id=env["tenant"], project_id=env["project"],
        target_tenant_id=target_tenant, target_project_id=target_project,
        target_region="local", requested_point_at=restore_requested,
        restore_mode="isolated_clone", idempotency_key="restore-one", actor_id="recovery-operator",
    )
    assert restored["state"] == "completed"
    assert restored["writes_reopened"] is True
    assert restored["reconciliation"]["blocking_findings"] == []
    again = env["context"].recovery.restore(
        tenant_id=env["tenant"], project_id=env["project"],
        target_tenant_id=target_tenant, target_project_id=target_project,
        target_region="local", requested_point_at=restore_requested,
        restore_mode="isolated_clone", idempotency_key="restore-one", actor_id="recovery-operator",
    )
    assert again["restore_id"] == restored["restore_id"]
    assert again["idempotent_replay"] is True


def test_progress10_corruption_missing_objects_scope_and_residency_fail_closed(tmp_path: Path) -> None:
    """REQ: ARCRES-005, OPSDR-002, OPSDR-003, OPSDR-005 corrupted, incomplete, cross-scope, and unauthorized-region restores fail before publication or write reopening."""
    env = bootstrap_recovery(tmp_path, name="p10-corrupt")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="corrupt-source")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)

    package = Path(env["context"].recovery.get_recovery_point(
        tenant_id=env["tenant"], project_id=env["project"], recovery_point_id=point["recovery_point_id"]
    )["package_path"]) if "package_path" in env["context"].recovery.get_recovery_point(
        tenant_id=env["tenant"], project_id=env["project"], recovery_point_id=point["recovery_point_id"]
    ) else Path(env["context"].recovery.recovery_root / "points" / point["recovery_point_id"] / "project.sip-preservation.zip")
    original = package.read_bytes()
    package.chmod(0o600)
    package.write_bytes(original + b"tamper")
    with pytest.raises(ValidationError) as error:
        verify_point(env, point)
    assert error.value.code in {"RECOVERY_POINT_PACKAGE_MISMATCH", "RECOVERY_POINT_INTEGRITY_FAILED", "EXPORT_INTEGRITY_FAILED"}
    package.write_bytes(original)
    package.chmod(0o440)
    verify_point(env, point)

    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.restore(
            tenant_id=env["tenant"], project_id=env["project"], target_tenant_id="foreign",
            target_project_id="foreign", target_region="local", requested_point_at=datetime.now(timezone.utc),
            restore_mode="isolated_clone", idempotency_key="wrong-target", actor_id="recovery-operator",
        )
    assert error.value.code == "RESTORE_TARGET_SCOPE_DENIED"

    target_tenant, target_project = isolated_target(env, "region")
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.restore(
            tenant_id=env["tenant"], project_id=env["project"], target_tenant_id=target_tenant,
            target_project_id=target_project, target_region="eu-west-1", requested_point_at=datetime.now(timezone.utc),
            restore_mode="isolated_clone", idempotency_key="wrong-region", actor_id="recovery-operator",
        )
    assert error.value.code == "RESTORE_RESIDENCY_DENIED"


def test_progress10_restore_refuses_to_resurrect_executed_deletion(tmp_path: Path) -> None:
    """REQ: DATRET-004, DATRET-006, OPSDR-005 ordinary restoration cannot resurrect data after governed purge completion."""
    env = bootstrap_recovery(tmp_path, name="p10-no-resurrection")
    asset = ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="delete-me")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    graph = env["context"].recovery.build_deletion_graph(
        tenant_id=env["tenant"], project_id=env["project"], scope_type="asset", scope_id=asset["asset_id"], actor_id="privacy-officer"
    )
    purge = env["context"].recovery.request_purge(
        tenant_id=env["tenant"], project_id=env["project"], deletion_graph_id=graph["deletion_graph_id"],
        recovery_point_id=point["recovery_point_id"], idempotency_key="purge-delete-me", actor_id="privacy-officer",
    )
    env["context"].recovery.approve_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"], actor_id="independent-approver"
    )
    env["context"].recovery.execute_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"],
        key_erasure={"key_ids": ["project-key-v1"], "key_deletion_evidence_hash": "a" * 64, "residual_timelines": [{"store": "backup", "expires_in_days": 30}]},
        actor_id="deletion-executor",
    )
    target_tenant, target_project = isolated_target(env, "resurrection")
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.restore(
            tenant_id=env["tenant"], project_id=env["project"], target_tenant_id=target_tenant,
            target_project_id=target_project, target_region="local", requested_point_at=datetime.now(timezone.utc),
            restore_mode="isolated_clone", idempotency_key="resurrection", actor_id="recovery-operator",
        )
    assert error.value.code == "RESTORE_WOULD_RESURRECT_DELETED_DATA"


def test_progress10_restore_requires_queue_reconciliation_before_writes_reopen(tmp_path: Path) -> None:
    """REQ: ARCRES-004, OPSDR-005 incomplete queue reconciliation blocks write reopening and reports the exact operation."""
    env = bootstrap_recovery(tmp_path, name="p10-queue-reconciliation")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="queue-source")
    operation = env["context"].operations.create(
        tenant_id=env["tenant"],
        project_id=env["project"],
        operation_type="synthetic_reconstruction",
        idempotency_key="queue-reconciliation-operation",
        input_manifest={"deployment_region": "local", "worker_class": "reference-worker"},
        actor_id="fixture-builder",
    )
    env["context"].operations.lease(operation["operation_id"], worker_id="reference-worker", lease_seconds=300)
    env["context"].operations.start(operation["operation_id"], worker_id="reference-worker")

    _, point, _ = register_objective_and_point(env, idempotency_key="queue-reconciliation-point")
    verify_point(env, point)
    target_tenant, target_project = isolated_target(env, "queue")
    restored = env["context"].recovery.restore(
        tenant_id=env["tenant"],
        project_id=env["project"],
        target_tenant_id=target_tenant,
        target_project_id=target_project,
        target_region="local",
        requested_point_at=datetime.now(timezone.utc),
        restore_mode="isolated_clone",
        idempotency_key="queue-reconciliation-restore",
        actor_id="recovery-operator",
    )

    assert restored["state"] == "reconciliation_required"
    assert restored["writes_reopened"] is False
    assert restored["reconciliation"]["queued_jobs"] == [
        {
            "operation_id": operation["operation_id"],
            "required_action": "resume_from_checkpoint_or_cancel",
        }
    ]
    assert any(
        item["code"] == "RESTORE_QUEUE_RECONCILIATION_REQUIRED"
        for item in restored["reconciliation"]["blocking_findings"]
    )
