from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sip.errors import AuthorizationError, ValidationError
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence, register_objective_and_point, verify_point


def test_progress10_fixity_format_migration_and_offboarding_are_open_and_verifiable(tmp_path: Path) -> None:
    """REQ: LIFPRESV-001, LIFPRESV-002, LIFPRESV-003, LIFPRESV-004, LIFPRESV-005, LIFPRESV-006, DATRET-005 preservation supports fixity, additive migration, offline viewing, succession/shutdown data, and verified tenant export."""
    env = bootstrap_recovery(tmp_path, name="p10-preservation")
    source = ingest_evidence(env["context"], env["tenant"], env["project"], payload=b"source-format", asset_id="format-source")
    derivative = ingest_evidence(env["context"], env["tenant"], env["project"], payload=b"derivative-format", asset_id="format-derivative")
    fixity = env["context"].recovery.check_fixity(
        tenant_id=env["tenant"], project_id=env["project"], asset_id=source["asset_id"],
        replica_asset_ids=[], repair_if_needed=False, actor_id="preservation-operator",
    )
    assert fixity["state"] == "valid"
    _, recovery_point, _ = register_objective_and_point(env, idempotency_key="fixity-replica-point")
    verify_point(env, recovery_point)
    env["context"].assets.store.delete(source["sha256"])
    repaired = env["context"].recovery.check_fixity(
        tenant_id=env["tenant"],
        project_id=env["project"],
        asset_id=source["asset_id"],
        replica_asset_ids=[],
        recovery_point_ids=[recovery_point["recovery_point_id"]],
        repair_if_needed=True,
        actor_id="preservation-operator",
    )
    assert repaired["state"] == "repaired"
    assert repaired["repair"]["successful"] is True
    assert env["context"].assets.store.read_bytes(source["sha256"]) == b"source-format"
    migration = env["context"].recovery.record_format_migration(
        tenant_id=env["tenant"], project_id=env["project"], source_asset_id=source["asset_id"],
        derivative_asset_id=derivative["asset_id"], source_format="application/x-source",
        target_format="model/gltf+json", migration_tool={"name": "synthetic-converter", "version": "1.0.0"},
        validation={"passed": True, "losses": ["material_extension_normalized"], "source_relationship_retained": True},
        actor_id="preservation-operator",
    )
    assert migration["original_preserved"] is True
    assert migration["source_sha256"] == source["sha256"]
    with pytest.raises(ValidationError) as missing_loss_declaration:
        env["context"].recovery.record_format_migration(
            tenant_id=env["tenant"], project_id=env["project"],
            source_asset_id=source["asset_id"], derivative_asset_id=derivative["asset_id"],
            source_format="application/x-source", target_format="model/gltf+json",
            migration_tool={"name": "synthetic-converter", "version": "1.0.0"},
            validation={"passed": True}, actor_id="preservation-operator",
        )
    assert missing_loss_declaration.value.code == "FORMAT_MIGRATION_EVIDENCE_INCOMPLETE"
    offboarding = env["context"].recovery.create_tenant_offboarding(
        tenant_id=env["tenant"], destination=tmp_path / "offboarding", actor_id="tenant-admin"
    )
    assert offboarding["state"] == "prepared"
    assert offboarding["export_manifest"]["projects"][0]["root_hash"]
    package = Path(offboarding["export_manifest"]["projects"][0]["path"])
    assert package.exists()
    verified = env["context"].preservation.verify_export(package)
    assert verified["root_hash"] == offboarding["export_manifest"]["projects"][0]["root_hash"]
    assert verified["package_sha256"] == offboarding["export_manifest"]["projects"][0]["sha256"]


def test_progress10_legacy_migration_is_additive_conservative_and_signed(tmp_path: Path) -> None:
    """REQ: PLTIO-001, PLTIO-002, PLTIO-004, PLTIO-005, PLTIO-007, PLTIO-009, PLTIO-011, SIPMIG-001, SIPMIG-002, SIPMIG-003, SIPMIG-004, SIPMIG-005, SIPMIG-006, SIPMIG-007, SIPMIG-008, SIPMIG-009, SIPMIG-010 migration preserves bytes, classifies by provenance, quarantines ambiguity, retains policy, supports rollback, and signs reports."""
    env = bootstrap_recovery(tmp_path, name="p10-migration")
    source = ingest_evidence(env["context"], env["tenant"], env["project"], payload=b"legacy-splat", asset_id="legacy-visual")
    metric = ingest_evidence(env["context"], env["tenant"], env["project"], payload=b"legacy-metric", asset_id="legacy-metric")
    _, point, _ = register_objective_and_point(env)
    verify_point(env, point)
    report = env["context"].recovery.record_legacy_migration(
        tenant_id=env["tenant"], project_id=env["project"], source_backup_id=point["recovery_point_id"],
        source_release="1.0.0", target_release="1.1.0",
        candidates=[
            {"asset_id": source["asset_id"], "sha256": source["sha256"], "source_kind": "gaussian_splat", "provenance": {"source_ids": [source["asset_id"]]}, "verification": {"verified": False}},
            {"asset_id": metric["asset_id"], "sha256": metric["sha256"], "source_kind": "metric_mesh", "provenance": {"source_ids": [metric["asset_id"]]}, "verification": {"verified": True}},
        ],
        unresolved_anchors=[{"anchor_id": "legacy-anchor", "reason": "primitive_identity_removed"}],
        policy_diffs=[{"policy": "audience", "direction": "same"}],
        rollback_evidence={"recovery_point_id": point["recovery_point_id"], "verified": True},
        compatibility_report={"read_api": "conservative", "downlevel_omissions": ["splat_authority"]},
        actor_id="migration-operator",
    )
    assert report["state"] == "validated"
    assert report["asset_mappings"][0]["original_bytes_rewritten"] is False
    assert report["asset_mappings"][0]["authority_ceiling"] == "visualization_only"
    assert report["asset_mappings"][1]["authority_ceiling"] == "verified"
    assert report["signed_report"]
    with pytest.raises(AuthorizationError) as error:
        env["context"].recovery.record_legacy_migration(
            tenant_id=env["tenant"], project_id=env["project"], source_backup_id=point["recovery_point_id"],
            source_release="1.0.0", target_release="1.1.0",
            candidates=[{"asset_id": source["asset_id"], "sha256": source["sha256"], "source_kind": "gaussian_splat", "provenance": {}, "verification": {}}],
            unresolved_anchors=[], policy_diffs=[{"policy": "consent", "direction": "less_restrictive"}],
            rollback_evidence={"recovery_point_id": point["recovery_point_id"], "verified": True},
            compatibility_report={}, actor_id="migration-operator",
        )
    assert error.value.code == "MIGRATION_POLICY_RELAXATION_DENIED"


def test_progress10_hybrid_and_full_project_portability_reconstructs_offline(tmp_path: Path) -> None:
    """REQ: PLTIO-003, PLTIO-006, PLTIO-007, PLTIO-010, PLTIO-012 full export retains open assets, all representation roles, checksums, and reconstructs through the clean reference importer."""
    env = bootstrap_recovery(tmp_path, name="p10-portability")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="portable-source")
    package = tmp_path / "portable.sip-preservation.zip"
    exported = env["context"].preservation.export_project(env["tenant"], env["project"], package, actor_id="exporter")
    verified = env["context"].preservation.verify_export(package)
    restored = env["context"].preservation.import_project(
        package, new_tenant_id="portable-tenant", new_project_id="portable-project", actor_id="offline-importer"
    )
    assert exported["root_hash"] == verified["root_hash"] == restored["source_root_hash"]
    assert restored["native_replay"] is True
    assert restored["non_activated_evidence"]["search_reindex_required"] is True
