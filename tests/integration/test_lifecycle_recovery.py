from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.canonical import sha256_bytes
from sip.database import AssetRefRow, BackupRunRow, DeletionEvidenceRow, KeyRotationRow, UsageLedgerRow
from sip.errors import ConflictError, ValidationError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass


def _ingest(context, tenant_id: str, project_id: str, actor: str, payload: bytes = b"immutable-source"):
    digest = sha256_bytes(payload)
    return context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name="source.bin",
        classification=Classification.INTERNAL,
        retention_class="project_record",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture:lifecycle"], output_hash=digest, validation_result_id=digest),
        actor_id=actor,
    )


@pytest.mark.integration
@pytest.mark.migration
def test_opsdr_002_backup_is_not_valid_until_isolated_restore_rehearsal(minimal_bootstrapped, tmp_path: Path) -> None:
    context, tenant_id, project_id, actor = minimal_bootstrapped
    asset = _ingest(context, tenant_id, project_id, actor)
    created = context.backup_recovery.create_local_backup(tmp_path / "backup", actor_id=actor)
    with context.database.session() as session:
        assert session.get(BackupRunRow, created["backup_id"]).state == "created"
    evidence = context.backup_recovery.verify_and_rehearse(created["backup_id"], actor_id="recovery-operator")
    assert evidence["state"] == "verified"
    assert evidence["database_integrity"] == "ok"
    assert evidence["objects_verified"] == 1
    assert evidence["write_reopen_allowed"] is True
    assert any(item["sha256"] == asset.sha256 for item in evidence["object_checks"])


@pytest.mark.integration
@pytest.mark.security
def test_opsdr_002_corrupt_backup_fails_before_restore_claim(bootstrapped, tmp_path: Path) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    _ingest(context, tenant_id, project_id, actor)
    created = context.backup_recovery.create_local_backup(tmp_path / "backup-corrupt", actor_id=actor)
    database_file = tmp_path / "backup-corrupt" / "database.sqlite3"
    database_file.write_bytes(database_file.read_bytes() + b"tamper")
    with pytest.raises(ValidationError) as error:
        context.backup_recovery.verify_and_rehearse(created["backup_id"], actor_id="recovery-operator")
    assert error.value.code == "BACKUP_INTEGRITY_FAILED"


@pytest.mark.integration
@pytest.mark.security
def test_dataret_001_deletion_requires_hold_release_backup_two_person_approval_and_evidence(bootstrapped, tmp_path: Path) -> None:
    """REQ: TSTSEC-005 destructive deletion requires hold release, verified backup, independent approval, and retained evidence."""
    context, tenant_id, project_id, actor = bootstrapped
    asset = _ingest(context, tenant_id, project_id, actor)
    context.lifecycle.set_retention_rule(
        tenant_id=tenant_id,
        project_id=project_id,
        retention_class="project_record",
        policy_source="fixture-policy-v1",
        minimum_days=0,
        maximum_days=3650,
        backup_expiry_days=14,
        deletion_mode="tombstone_then_erase",
        actor_id=actor,
    )
    hold_id = context.lifecycle.place_hold(
        tenant_id,
        project_id,
        "asset",
        asset.asset_id,
        reason="litigation hold",
        authority_reference="matter:2026-001",
        actor_id="legal-officer",
    )
    blocked = context.lifecycle.plan_asset_deletion(tenant_id, project_id, asset.asset_id)
    assert blocked["eligible"] is False
    assert "legal_hold_active" in blocked["blockers"]
    context.lifecycle.release_hold(tenant_id, project_id, hold_id, actor_id="legal-officer-2")

    backup = context.backup_recovery.create_local_backup(tmp_path / "delete-backup", actor_id=actor)
    context.backup_recovery.verify_and_rehearse(backup["backup_id"], actor_id="recovery-operator")
    deletion_id = context.lifecycle.request_asset_deletion(
        tenant_id,
        project_id,
        asset.asset_id,
        backup_id=backup["backup_id"],
        actor_id=actor,
    )
    with pytest.raises(ConflictError) as error:
        context.lifecycle.approve_deletion(tenant_id, project_id, deletion_id, actor_id=actor)
    assert error.value.code == "INDEPENDENT_APPROVER_REQUIRED"
    context.lifecycle.approve_deletion(tenant_id, project_id, deletion_id, actor_id="privacy-officer")
    result = context.lifecycle.execute_deletion(tenant_id, project_id, deletion_id, actor_id="deletion-operator")
    assert result["physical_object_will_be_removed"] is True
    assert not context.store.path_for(asset.sha256).exists()
    with context.database.session() as session:
        ref = session.get(AssetRefRow, asset.asset_id)
        evidence = session.get(DeletionEvidenceRow, result["evidence_id"])
        assert ref.tombstoned_at is not None
        assert evidence.evidence_hash == result["evidence_hash"]
        assert evidence.backup_expiry_deadline is not None
        assert any(location["location_type"] == "verified_backup" for location in evidence.residual_locations)


@pytest.mark.integration
@pytest.mark.security
def test_opskey_003_envelope_rotation_rewraps_keys_without_rewriting_ciphertext(minimal_bootstrapped) -> None:
    context, tenant_id, project_id, actor = minimal_bootstrapped
    one = _ingest(context, tenant_id, project_id, actor, b"one")
    two = _ingest(context, tenant_id, project_id, actor, b"two")
    before = {item.sha256: sha256_bytes(context.store.path_for(item.sha256).read_bytes()) for item in (one, two)}
    result = context.key_rotation.rotate_local_envelope_key(new_master_key=b"n" * 32, new_key_id="local-master-v2", actor_id="key-custodian")
    assert result["ciphertext_unchanged"] is True
    assert result["object_count"] == 2
    assert context.assets.read(tenant_id, project_id, one.asset_id, actor_id=actor) == b"one"
    assert context.assets.read(tenant_id, project_id, two.asset_id, actor_id=actor) == b"two"
    after = {item.sha256: sha256_bytes(context.store.path_for(item.sha256).read_bytes()) for item in (one, two)}
    assert before == after
    with context.database.session() as session:
        rotation = session.get(KeyRotationRow, result["rotation_id"])
        assert rotation.new_key_id == "local-master-v2"
        assert rotation.ciphertext_unchanged is True


@pytest.mark.integration
def test_opscost_001_quota_admission_and_immutable_price_source_attribution(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    context.admission.set_quota(
        tenant_id=tenant_id,
        project_id=project_id,
        resource_type="gpu_seconds",
        unit="seconds",
        period_seconds=3600,
        soft_limit=7,
        hard_limit=10,
        actor_id=actor,
    )
    first = context.admission.admit_and_record(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_id="op-a",
        resource_type="gpu_seconds",
        quantity=6,
        unit="seconds",
        unit_cost=0.02,
        currency="usd",
        price_source_version="price-sheet-2026-07-27",
        estimated=True,
        actor_id=actor,
    )
    assert first["attributed_cost"] == pytest.approx(0.12)
    second = context.admission.admit_and_record(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_id="op-b",
        resource_type="gpu_seconds",
        quantity=2,
        unit="seconds",
        unit_cost=0.03,
        currency="usd",
        price_source_version="price-sheet-2026-08-01",
        estimated=False,
        actor_id=actor,
    )
    assert second["soft_limit_exceeded"] is True
    with pytest.raises(ConflictError) as error:
        context.admission.admit_and_record(
            tenant_id=tenant_id,
            project_id=project_id,
            operation_id="op-c",
            resource_type="gpu_seconds",
            quantity=3,
            unit="seconds",
            unit_cost=0.01,
            currency="usd",
            price_source_version="price-sheet-2026-08-01",
            estimated=True,
            actor_id=actor,
        )
    assert error.value.code == "QUOTA_HARD_LIMIT"
    with context.database.session() as session:
        records = list(session.scalars(select(UsageLedgerRow).order_by(UsageLedgerRow.occurred_at)))
        assert [record.price_source_version for record in records] == ["price-sheet-2026-07-27", "price-sheet-2026-08-01"]
        assert [record.unit_cost for record in records] == [0.02, 0.03]
