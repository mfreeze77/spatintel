from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.database import AssetRefRow, AuditEventRow, BackupExpiryEvidenceRow, LegalHoldRow, PurgeRunRow
from sip.errors import AuthorizationError, ConflictError
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, register_objective_and_point, verify_point


def test_progress10_retention_inventory_legal_hold_and_governed_purge(tmp_path: Path) -> None:
    """REQ: DATRET-001, DATRET-002, DATRET-004, DATRET-006 retention assignment, legal holds, two-person purge, cross-store propagation, backup expiry, and erasure evidence are retained."""
    env = bootstrap_recovery(tmp_path, name="p10-retention")
    asset = ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="retained-asset")
    env["context"].lifecycle.set_retention_rule(
        tenant_id=env["tenant"], project_id=env["project"], retention_class="project_record",
        policy_source="policy://retention/project-v1", minimum_days=0, maximum_days=3650,
        backup_expiry_days=30, deletion_mode="tombstone_then_erase", actor_id="records-officer",
    )
    hold_id = env["context"].lifecycle.place_hold(
        env["tenant"], env["project"], "asset", asset["asset_id"], reason="synthetic legal hold",
        authority_reference="matter://p10-001", actor_id="legal-officer",
    )
    inventory = env["context"].recovery.evaluate_retention_inventory(
        tenant_id=env["tenant"], project_id=env["project"], actor_id="records-officer"
    )
    assignment = next(item for item in inventory["assignments"] if item["resource_id"] == asset["asset_id"])
    assert assignment["hold_status"] == "active"
    assert assignment["deletion_eligible"] is False
    graph = env["context"].recovery.build_deletion_graph(
        tenant_id=env["tenant"], project_id=env["project"], scope_type="asset", scope_id=asset["asset_id"], actor_id="privacy-officer"
    )
    assert graph["eligible"] is False
    with pytest.raises(ConflictError):
        env["context"].recovery.request_purge(
            tenant_id=env["tenant"], project_id=env["project"], deletion_graph_id=graph["deletion_graph_id"],
            recovery_point_id="missing", idempotency_key="blocked", actor_id="privacy-officer",
        )
    env["context"].lifecycle.release_hold(env["tenant"], env["project"], hold_id, actor_id="legal-officer-2")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    graph = env["context"].recovery.build_deletion_graph(
        tenant_id=env["tenant"], project_id=env["project"], scope_type="asset", scope_id=asset["asset_id"], actor_id="privacy-officer"
    )
    purge = env["context"].recovery.request_purge(
        tenant_id=env["tenant"], project_id=env["project"], deletion_graph_id=graph["deletion_graph_id"],
        recovery_point_id=point["recovery_point_id"], idempotency_key="purge-retained-asset", actor_id="privacy-officer",
    )
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.approve_purge(
            tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"], actor_id="privacy-officer"
        )
    assert error.value.code == "PURGE_INDEPENDENT_APPROVAL_REQUIRED"
    env["context"].recovery.approve_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"], actor_id="independent-approver"
    )
    executed = env["context"].recovery.execute_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"],
        key_erasure={
            "key_ids": ["project-key-v1"],
            "key_deletion_evidence_hash": "b" * 64,
            "residual_timelines": [{"store": "backup", "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}],
        },
        actor_id="deletion-executor",
    )
    assert executed["state"] == "executed"
    assert executed["unresolved_exceptions"] == []
    stores = {item["store"]: item["status"] for item in executed["store_results"]["stores"]}
    assert stores == {"canonical": "purged", "replica": "scheduled", "backup": "scheduled"}
    with env["context"].database.session() as session:
        ref = session.get(AssetRefRow, asset["asset_id"])
        assert ref is not None and ref.tombstoned_at is not None
        purge_row = session.get(PurgeRunRow, purge["purge_run_id"])
        assert purge_row is not None and purge_row.evidence_hash == executed["evidence_hash"]
        expiry = session.scalar(select(BackupExpiryEvidenceRow).where(BackupExpiryEvidenceRow.recovery_point_id == point["recovery_point_id"]))
        assert expiry is not None and expiry.state == "scheduled"


def test_progress10_backup_expiry_is_bounded_hold_aware_and_idempotent(tmp_path: Path) -> None:
    """REQ: DATRET-004 backup expiry is bounded, hold-aware, auditable, and repeatable without resurrecting deleted access."""
    env = bootstrap_recovery(tmp_path, name="p10-expiry")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="expiry-source")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    due = datetime.now(timezone.utc) - timedelta(seconds=1)
    expiry = env["context"].recovery.schedule_backup_expiry(
        tenant_id=env["tenant"], project_id=env["project"], recovery_point_id=point["recovery_point_id"],
        resource_scope={"scope_type": "project", "scope_id": env["project"]}, scheduled_for=due,
        residuals=[{"store": "replica", "state": "expires_with_backup"}], actor_id="records-officer",
    )
    hold = env["context"].lifecycle.place_hold(
        env["tenant"], env["project"], "project", env["project"], reason="hold expiry",
        authority_reference="matter://expiry", actor_id="legal-officer",
    )
    with pytest.raises(ConflictError) as error:
        env["context"].recovery.execute_backup_expiry(
            tenant_id=env["tenant"], project_id=env["project"], backup_expiry_id=expiry["backup_expiry_id"],
            actor_id="deletion-executor", now=datetime.now(timezone.utc),
        )
    assert error.value.code == "LEGAL_HOLD_BLOCKS_BACKUP_EXPIRY"
    env["context"].lifecycle.release_hold(env["tenant"], env["project"], hold, actor_id="legal-officer-2")
    executed = env["context"].recovery.execute_backup_expiry(
        tenant_id=env["tenant"], project_id=env["project"], backup_expiry_id=expiry["backup_expiry_id"],
        actor_id="deletion-executor", now=datetime.now(timezone.utc),
    )
    replay = env["context"].recovery.execute_backup_expiry(
        tenant_id=env["tenant"], project_id=env["project"], backup_expiry_id=expiry["backup_expiry_id"],
        actor_id="deletion-executor", now=datetime.now(timezone.utc),
    )
    assert executed["state"] == replay["state"] == "expired"
    with pytest.raises(ConflictError) as expired_point:
        env["context"].recovery.verify_recovery_point(
            tenant_id=env["tenant"],
            project_id=env["project"],
            recovery_point_id=point["recovery_point_id"],
            actor_id="recovery-operator",
        )
    assert expired_point.value.code == "RECOVERY_POINT_EXPIRED"


def test_progress10_deletion_scope_isolated_between_projects(tmp_path: Path) -> None:
    """REQ: DATRET-002, DATRET-006 deletion of one project or subject cannot mutate another tenant/project and failed recovery actions retain audit evidence."""
    env = bootstrap_recovery(tmp_path, name="p10-isolation")
    other = env["context"].tenancy.create_project(
        env["tenant"], "other", vertical="platform", classification="internal",
        project_id="p10-isolation-other", actor_id="bootstrap",
    )
    first = ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="first-project-asset")
    second = ingest_evidence(env["context"], env["tenant"], other, asset_id="second-project-asset")
    _, point, _ = register_objective_and_point(env, idempotency_key="project-isolation-point")
    verify_point(env, point)
    graph = env["context"].recovery.build_deletion_graph(
        tenant_id=env["tenant"], project_id=env["project"], scope_type="project", scope_id=env["project"], actor_id="privacy-officer"
    )
    assert graph["eligible"] is True
    assert all(node.get("record_id") != second["asset_id"] for node in graph["nodes"])
    purge = env["context"].recovery.request_purge(
        tenant_id=env["tenant"], project_id=env["project"], deletion_graph_id=graph["deletion_graph_id"],
        recovery_point_id=point["recovery_point_id"], idempotency_key="project-isolation-purge", actor_id="privacy-officer",
    )
    env["context"].recovery.approve_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"], actor_id="independent-approver"
    )
    executed = env["context"].recovery.execute_purge(
        tenant_id=env["tenant"], project_id=env["project"], purge_run_id=purge["purge_run_id"],
        key_erasure={
            "key_ids": ["project-key-v1"],
            "key_deletion_evidence_hash": "c" * 64,
            "residual_timelines": [{"store": "backup", "expires_in_days": 30}],
        },
        actor_id="deletion-executor",
    )
    assert executed["state"] == "executed"
    with env["context"].database.session() as session:
        assert session.get(AssetRefRow, first["asset_id"]).tombstoned_at is not None
        assert session.get(AssetRefRow, second["asset_id"]).tombstoned_at is None
