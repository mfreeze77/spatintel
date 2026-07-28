from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sip.canonical import canonical_sha256, sha256_bytes
from sip.context import PlatformContext, temporary_settings
from sip.database import (
    AnchorRemapRow,
    AssetRefRow,
    AuditEventRow,
    CollaborationCommentRow,
    CollaborationTaskRow,
    ConsentGrantRow,
    ConstructionRecordRow,
    CoordinateFrameRow,
    DerivationEventRow,
    EvidenceRecordRow,
    GeometryAssetManifestRow,
    LegalHoldRow,
    MeasurementRow,
    ProviderManifestRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    RetentionRuleRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
    SearchDocumentRow,
    SpatialAnnotationRow,
    SpatialTransformRow,
)
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SourceClass
from sip.scene import ProxyHit


@pytest.mark.integration
@pytest.mark.acceptance
def test_pltio_foundation_open_export_collision_safe_import_preserves_hash_and_semantic_identity(bootstrapped, tmp_path: Path) -> None:
    """REQ: PLTIO-003, PLTIO-012 preservation import retains source hashes and reconstructs semantic scene identity without private vendor knowledge."""
    context, tenant_id, project_id, actor = bootstrapped
    payload = b"open-preservation-source"
    asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name="source.bin",
        classification=Classification.INTERNAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture"], output_hash=sha256_bytes(payload)),
        actor_id=actor,
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Export room", actor_id=actor)
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Export world",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="right_handed_y_up",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="export fixture origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="frame-export-world",
        metadata={"calibration_asset_id": asset.asset_id},
    )
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Export design",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="right_handed_y_up",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="export fixture design origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="frame-export-design",
    )
    transform = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-export-world",
        target_frame_id="frame-export-design",
        transform_type="SE3",
        matrix=[
            [1.0, 0.0, 0.0, 0.25],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        uncertainty={"translation_sigma_m": 0.005},
        source_type="registration",
        authority_class=AuthorityClass.METRIC,
        metadata={"calibration_asset_id": asset.asset_id},
    )
    now = datetime.now(UTC)
    evidence_record = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset.asset_id,
        source_type="field_photo",
        collected_at=now,
        collected_by=actor,
        device_or_tool="synthetic-camera",
        location_context={"scene_id": scene["scene_id"], "asset_id": asset.asset_id},
        relevant_region={"scene_id": scene["scene_id"], "mask_asset_id": asset.asset_id},
        relevant_time_start=now,
        relevant_time_end=now,
        retention_class="preservation",
        consent_scope={"basis": "project_authorization", "source_asset_id": asset.asset_id},
        access_policy={"inherit_project_policy": True, "redaction_asset_id": asset.asset_id},
        policy={"scene_id": scene["scene_id"]},
        actor_id=actor,
    )
    derivation = context.spatial_data.record_derivation(
        tenant_id=tenant_id,
        project_id=project_id,
        activity_type="preservation_fixture",
        input_ids=[evidence_record["evidence_id"]],
        input_hashes=[evidence_record["content_sha256"]],
        algorithm_id="sip.fixture.export",
        algorithm_version="1.0.0",
        parameters_hash="1" * 64,
        environment_hash="2" * 64,
        code_commit="3" * 40,
        output_ids=[asset.asset_id],
        output_hashes=[asset.sha256],
        software={"name": "sip.fixture.export", "version": "1.0.0", "configuration_asset_id": asset.asset_id},
        validation={"schema_valid": True, "evidence_id": evidence_record["evidence_id"]},
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        quality={"deterministic": True, "source_asset_id": asset.asset_id},
        actor_id=actor,
    )
    geometry_manifest = context.spatial_data.register_geometry_manifest(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        asset_id=asset.asset_id,
        media_type="model/gltf-binary",
        format="glb",
        profile="metric_mesh",
        format_version="2.0",
        coordinate_frame_id="frame-export-world",
        units="meter",
        bounds={"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]},
        classification="internal",
        counts={"triangles": 12},
        compression={"codec": "none"},
        source_run_id=derivation["derivation_id"],
        quality={"schema_valid": True},
        audience_policy={"evidence_id": evidence_record["evidence_id"]},
        validation_state="valid",
    )
    annotation = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        coordinate_frame_id="frame-export-world",
        support_type="world_point",
        support={"source_asset_id": asset.asset_id},
        uncertainty_m=0.01,
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        actor_id=actor,
        position=[0.25, 0.5, 0.75],
        policy={"evidence_id": evidence_record["evidence_id"]},
    )
    package_path = tmp_path / "project.sip-preservation.zip"
    package = context.preservation.export_project(tenant_id, project_id, package_path, actor_id=actor)
    verified = context.preservation.verify_export(package_path)
    assert verified["root_hash"] == package["root_hash"]
    restored = context.preservation.import_project(
        package_path,
        new_tenant_id="tenant-restored",
        new_project_id="project-restored",
        actor_id="restore-operator",
    )
    assert restored["source_root_hash"] == package["root_hash"]
    assert restored["native_replay"] is True
    # The source and destination share one database, so globally keyed rows must be
    # remapped while project-scoped scene identity remains stable.
    assert restored["id_maps"]["asset"][asset.asset_id] != asset.asset_id
    assert restored["id_maps"]["commit"][scene["commit_id"]] != scene["commit_id"]
    assert restored["scene_id"] == scene["scene_id"]
    with context.database.session() as session:
        restored_refs = list(session.scalars(select(AssetRefRow).where(AssetRefRow.project_id == "project-restored")))
        restored_commits = list(session.scalars(select(SceneCommitRow).where(SceneCommitRow.project_id == "project-restored")))
        restored_branches = list(session.scalars(select(SceneBranchRow).where(SceneBranchRow.project_id == "project-restored")))
    # One source object plus the immutable preservation package master are retained.
    assert len(restored_refs) == 2
    content_ref = next(row for row in restored_refs if row.sha256 == asset.sha256)
    assert context.assets.read("tenant-restored", "project-restored", content_ref.asset_id, actor_id="restore-operator") == payload
    assert len(restored_commits) == 1
    assert restored_commits[0].semantic_snapshot_json["scene_id"] == scene["scene_id"]
    assert restored_commits[0].snapshot_hash == canonical_sha256(restored_commits[0].semantic_snapshot_json)
    assert restored_branches[0].head_commit_id == restored_commits[0].commit_id
    mapped_asset = restored["id_maps"]["asset"][asset.asset_id]
    mapped_transform = restored["id_maps"]["spatial_transform"][transform["transform_id"]]
    mapped_evidence = restored["id_maps"]["evidence"][evidence_record["evidence_id"]]
    mapped_derivation = restored["id_maps"]["derivation"][derivation["derivation_id"]]
    mapped_manifest = restored["id_maps"]["geometry_manifest"][geometry_manifest["geometry_manifest_id"]]
    mapped_annotation = restored["id_maps"]["annotation"][annotation["annotation_id"]]
    mapped_world = restored["id_maps"]["frame"]["frame-export-world"]
    mapped_design = restored["id_maps"]["frame"]["frame-export-design"]
    with context.database.session() as session:
        restored_transform = session.get(SpatialTransformRow, mapped_transform)
        assert restored_transform.source_frame_id == mapped_world
        assert restored_transform.target_frame_id == mapped_design
        assert restored_transform.metadata_json["calibration_asset_id"] == mapped_asset
        assert restored_transform.uncertainty_json["translation_sigma_m"] == 0.005
        restored_evidence = session.get(EvidenceRecordRow, mapped_evidence)
        assert restored_evidence.asset_id == mapped_asset
        assert restored_evidence.relevant_region_json["mask_asset_id"] == mapped_asset
        assert restored_evidence.consent_scope_json["source_asset_id"] == mapped_asset
        assert restored_evidence.access_policy_json["redaction_asset_id"] == mapped_asset
        restored_derivation = session.get(DerivationEventRow, mapped_derivation)
        assert restored_derivation.input_ids_json == [mapped_evidence]
        assert restored_derivation.output_ids_json == [mapped_asset]
        assert restored_derivation.software_json["configuration_asset_id"] == mapped_asset
        assert restored_derivation.validation_json["evidence_id"] == mapped_evidence
        restored_manifest = session.get(GeometryAssetManifestRow, mapped_manifest)
        assert restored_manifest.asset_id == mapped_asset
        assert restored_manifest.coordinate_frame_id == mapped_world
        assert restored_manifest.source_run_id == mapped_derivation
        assert restored_manifest.audience_policy_json["evidence_id"] == mapped_evidence
        restored_annotation = session.get(SpatialAnnotationRow, mapped_annotation)
        assert restored_annotation.coordinate_frame_id == mapped_world
        assert restored_annotation.support_json["source_asset_id"] == mapped_asset
        assert restored_annotation.policy_json["evidence_id"] == mapped_evidence
    assert restored["preservation_package_asset_id"] in {row.asset_id for row in restored_refs}


@pytest.mark.integration
@pytest.mark.acceptance
@pytest.mark.privacy
def test_open_preservation_clean_restore_rehydrates_authoritative_rows_and_fails_closed_for_executable_state(bootstrapped, tmp_path: Path) -> None:
    """REQ: PLTIO-003, PLTIO-006, PLTIO-012, OPSDR-005 clean restore reconciles native records and keeps executable/governance state fail-closed."""
    source, tenant_id, project_id, actor = bootstrapped
    payload = b"verified preservation evidence"
    evidence = source.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name="evidence.bin",
        classification=Classification.CONFIDENTIAL,
        retention_class="records",
        source_class=SourceClass.VERIFIED,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["test-fixture"], output_hash=sha256_bytes(payload)),
        actor_id=actor,
    )
    source.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="World",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="right_handed_y_up",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="preservation fixture origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="frame-world-preservation",
        uncertainty_m=0.002,
    )
    provider = source.providers.register(
        {
            "provider_id": "local-preservation-provider",
            "version": "1.0.0",
            "source_url": "local://preservation-test",
            "source_revision": "fixture-v1",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal", "confidential"],
            "allowed_purposes": ["preservation-test"],
            "allowed_regions": ["local"],
            "retention_days": 0,
        },
        actor_id=actor,
    )
    scene = source.scene.create_scene(tenant_id, project_id, name="Preserved Scene", actor_id=actor)
    entity = source.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="fire_alarm_panel",
        name="FACP-1",
        attributes={"location": "Electrical 101"},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=[evidence.asset_id], output_hash=evidence.sha256),
        policy={"audience": "project", "classification": "confidential"},
        stable_support={"frame_id": "frame-world-preservation", "point": [1.0, 1.5, 0.0]},
        actor_id=actor,
    )
    representation = source.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=evidence.asset_id,
        kind=RepresentationKind.METRIC,
        provider_id="local-preservation-provider",
        coordinate_frame_id="frame-world-preservation",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement"],
        prohibited_uses=["survey"],
        quality={"uncertainty_m": 0.002},
        provenance={"source_ids": [evidence.asset_id], "provider_manifest_hash": provider["manifest_hash"]},
        support_map={"entity_ids": [entity]},
        actor_id=actor,
    )
    source.representations.review_quality(
        representation,
        reviewer_id="independent-reviewer",
        approved_uses=["measurement"],
        metrics={"rmse_m": 0.001},
        passed=True,
    )
    binding = source.publisher.publish(representation, commit_id=scene["commit_id"], role="measurement", publisher_id="publisher")
    final_commit = source.scene.commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        branch="main",
        expected_head=scene["commit_id"],
        message="Preservation-ready metric state",
        actor_id=actor,
    )
    measurement = source.scene.create_measurement(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=entity,
        value=1.52,
        unit="m",
        uncertainty=0.003,
        source_asset_ids=[evidence.asset_id],
        calibration={"asset_id": evidence.asset_id, "certificate": "SYN-CAL-001"},
        verifier_id="field-verifier",
        verified=True,
        actor_id=actor,
        originating_representation_id=representation,
        measurement_type="height",
        geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [0.0, 1.52, 0.0]},
        source_method="field_verified_laser",
        coordinate_frame_id="frame-world-preservation",
    )
    site = source.construction.create_hierarchy_item(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="site",
        name="Synthetic Campus",
        parent_id=None,
        state="observed",
        actor_id=actor,
    )
    building = source.construction.create_hierarchy_item(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="building",
        name="Building A",
        parent_id=site,
        state="observed",
        actor_id=actor,
    )
    level = source.construction.create_hierarchy_item(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="level",
        name="Level 1",
        parent_id=building,
        state="observed",
        actor_id=actor,
    )
    room = source.construction.create_hierarchy_item(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="room",
        name="Electrical 101",
        parent_id=level,
        state="observed",
        actor_id=actor,
    )
    construction_record = source.construction.create_system_record(
        tenant_id=tenant_id,
        project_id=project_id,
        system_type="fire_alarm_panel",
        parent_id=room,
        entity_id=entity,
        state="verified",
        data={"verified_by": "field-verifier", "photo_asset_id": evidence.asset_id},
        evidence_asset_ids=[evidence.asset_id],
        actor_id=actor,
    )
    subject = "person-preservation-subject"
    consent = source.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        granted_by="subject",
        purposes=["preservation"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["*"],
        derivative_policy={"generated_visual": False, "voice": False},
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    memory = source.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="person",
        subject_id=subject,
        related_ids=[],
        data={"name": "Preservation Person", "portrait_asset_id": evidence.asset_id},
        source_class=SourceClass.CORROBORATED,
        confidence=0.95,
        evidence_asset_ids=[evidence.asset_id],
        audience=Audience.FAMILY,
        actor_id=actor,
    )
    comment = source.collaboration.comment(
        tenant_id=tenant_id,
        project_id=project_id,
        body="Verify the panel location.",
        author_id=actor,
        scene_commit_id=final_commit["commit_id"],
        entity_id=entity,
    )
    task = source.collaboration.create_task(
        tenant_id=tenant_id,
        project_id=project_id,
        title="Review panel evidence",
        description="Confirm evidence and measurement.",
        created_by=actor,
        entity_id=entity,
        assignee_id="reviewer",
        priority="high",
    )
    retention = source.lifecycle.set_retention_rule(
        tenant_id=tenant_id,
        project_id=project_id,
        retention_class="records",
        policy_source="synthetic policy",
        minimum_days=365,
        maximum_days=None,
        backup_expiry_days=30,
        deletion_mode="manual_review",
        actor_id=actor,
    )
    hold = source.lifecycle.place_hold(
        tenant_id,
        project_id,
        "asset",
        evidence.asset_id,
        reason="preservation test",
        authority_reference="SYN-HOLD-001",
        actor_id=actor,
    )
    source.search.index(
        tenant_id=tenant_id,
        project_id=project_id,
        text="Fire alarm panel in Electrical 101",
        entity_id=entity,
        asset_id=evidence.asset_id,
        embedding=[1.0, 0.0],
        embedding_model_manifest_id="embedding-fixture-v1",
        embedding_source_region={"asset_id": evidence.asset_id, "bounds": [0, 0, 100, 100]},
        spatial_bounds={"min": [0, 0, 0], "max": [2, 2, 2]},
        spatial_frame_id="frame-1",
        temporal_start=None,
        temporal_end=None,
        policy={"audience": "project"},
    )

    package_path = tmp_path / "native.sip-preservation.zip"
    exported = source.preservation.export_project(tenant_id, project_id, package_path, actor_id=actor)
    verified = source.preservation.verify_export(package_path)
    assert verified["metadata"]["domain_schema_version"] == "1.1.0"
    assert "search_documents" in verified["metadata"]["archived_records"]["tables"]
    assert "provider_manifests" in verified["metadata"]["preserved_governance"]["tables"]

    destination = PlatformContext.create(temporary_settings(tmp_path / "clean-restore"))
    result = destination.preservation.import_project(
        package_path,
        new_tenant_id="tenant-clean-restored",
        new_project_id="project-clean-restored",
        actor_id="restore-operator",
    )
    assert result["native_replay"] is True
    assert result["source_root_hash"] == exported["root_hash"]
    # A clean restore preserves stable semantic identifiers.
    assert result["id_maps"]["asset"][evidence.asset_id] == evidence.asset_id
    assert result["id_maps"]["entity"][entity] == entity
    assert result["id_maps"]["representation"][representation] == representation
    assert result["id_maps"]["commit"][final_commit["commit_id"]] == final_commit["commit_id"]
    assert result["id_maps"]["measurement"][measurement] == measurement
    assert result["id_maps"]["construction"][construction_record] == construction_record
    assert result["id_maps"]["memory"][memory] == memory
    assert result["id_maps"]["consent"][consent] == consent
    assert result["id_maps"]["comment"][comment] == comment
    assert result["id_maps"]["task"][task] == task
    assert result["id_maps"]["retention_rule"][retention] == retention
    assert result["id_maps"]["legal_hold"][hold] == hold

    technical = destination.construction.technical_report("tenant-clean-restored", "project-clean-restored")
    assert technical["record_counts"]["fire_alarm_panel"] == 1
    assert any(item["measurement_id"] == measurement and item["verifier_id"] == "field-verifier" for item in technical["measurements"])
    family = destination.liveforever.edition(
        "tenant-clean-restored",
        "project-clean-restored",
        audience=Audience.FAMILY,
        purpose="preservation",
    )
    assert {item["record_id"] for item in family["records"]} == {memory}
    with destination.database.session() as session:
        assert session.get(CoordinateFrameRow, "frame-world-preservation") is not None
        assert session.get(SceneEntityRow, entity).stable_support_json["frame_id"] == "frame-world-preservation"
        assert session.get(RepresentationAssetRow, representation).asset_id == evidence.asset_id
        assert session.get(RepresentationAssetRow, representation).provenance_json["preservation_import"]["provider_reapproval_required_for_new_execution"] is True
        assert session.get(RepresentationBindingRow, binding).commit_id == scene["commit_id"]
        assert session.get(MeasurementRow, measurement).calibration_json["asset_id"] == evidence.asset_id
        assert session.get(ConstructionRecordRow, construction_record).parent_id == room
        assert session.get(ConsentGrantRow, consent).state == "active"
        assert session.get(CollaborationCommentRow, comment).scene_commit_id == final_commit["commit_id"]
        assert session.get(CollaborationTaskRow, task).entity_id == entity
        assert session.get(RetentionRuleRow, retention).project_id == "project-clean-restored"
        restored_hold = session.get(LegalHoldRow, hold)
        assert restored_hold.resource_id == evidence.asset_id and restored_hold.state == "active"
        assert session.get(AssetRefRow, evidence.asset_id).legal_hold is True
        assert session.scalar(select(func.count()).select_from(SearchDocumentRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProviderManifestRow)) == 0
        # Original audit rows are retained in the package, not inserted into the new
        # signing chain. Only destination-native import evidence may exist here.
        destination_audits = list(session.scalars(select(AuditEventRow)))
        assert destination_audits and all(row.action == "asset:ingest" for row in destination_audits)
        package_ref = session.get(AssetRefRow, result["preservation_package_asset_id"])
        assert package_ref is not None and package_ref.retention_class == "preservation_master"
    assert destination.assets.read(
        "tenant-clean-restored",
        "project-clean-restored",
        result["preservation_package_asset_id"],
        actor_id="restore-verifier",
    ) == package_path.read_bytes()
    assert result["non_activated_evidence"]["provider_model_reapproval_required"] is True
    assert result["non_activated_evidence"]["security_bindings_replayed"] is False
    assert result["non_activated_evidence"]["search_reindex_required"] is True


@pytest.mark.integration
@pytest.mark.acceptance
@pytest.mark.privacy
def test_preservation_collision_remaps_proxy_measurement_and_anchor_history(bootstrapped, tmp_path: Path) -> None:
    """REQ: PLTIO-003, DATANCH-001, DATHYB-006, CONMEAS-001 preservation remaps proxy lineage without promoting authority."""
    context, tenant_id, project_id, actor = bootstrapped

    def ingest(payload: bytes, name: str, *, generated: bool = False):
        return context.assets.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=payload,
            media_type="model/gltf-binary" if generated else "application/octet-stream",
            original_name=name,
            classification=Classification.INTERNAL,
            retention_class="preservation",
            source_class=SourceClass.GENERATED if generated else SourceClass.DIRECT_CAPTURE,
            authority_class=(
                AuthorityClass.DERIVED_NON_AUTHORITATIVE if generated else AuthorityClass.EVIDENCE
            ),
            provenance=ProvenanceRef(
                source_ids=[f"synthetic-fixture:{name}"],
                output_hash=sha256_bytes(payload),
            ),
            actor_id=actor,
        )

    metric_asset = ingest(b"preservation metric surface", "preservation-metric.bin")
    source_proxy_asset = ingest(b"preservation source proxy", "preservation-source-proxy.glb", generated=True)
    target_proxy_asset = ingest(b"preservation target proxy", "preservation-target-proxy.glb", generated=True)
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Preservation proxy world",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="synthetic preservation proxy origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="frame-preservation-proxy-world",
    )
    provider_id = "preservation-proxy-provider"
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.0.0",
            "source_url": f"local://{provider_id}",
            "source_revision": "deterministic-fixture",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["measurement", "picking"],
            "allowed_regions": ["local"],
        },
        actor_id=actor,
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Preservation proxy scene", actor_id=actor)
    entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="equipment",
        name="Synthetic equipment",
        attributes={},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=[metric_asset.asset_id]),
        policy={},
        stable_support={"frame_id": "frame-preservation-proxy-world", "point": [0.0, 0.0, 0.0]},
        actor_id=actor,
    )
    metric = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=metric_asset.asset_id,
        kind=RepresentationKind.METRIC,
        provider_id=provider_id,
        coordinate_frame_id="frame-preservation-proxy-world",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement"],
        prohibited_uses=[],
        quality={"rmse_m": 0.005},
        provenance={"source_ids": [metric_asset.asset_id]},
        support_map={},
        actor_id=actor,
    )
    context.representations.review_quality(
        metric,
        reviewer_id="metric-reviewer",
        approved_uses=["measurement"],
        metrics={"rmse_m": 0.005},
        passed=True,
    )
    context.publisher.publish(
        metric,
        commit_id=scene["commit_id"],
        role="measurement",
        publisher_id="publisher",
    )

    source_proxy = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=source_proxy_asset.asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id=provider_id,
        coordinate_frame_id="frame-preservation-proxy-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking"],
        prohibited_uses=["verified_measurement"],
        quality={"collision_coverage": 1.0},
        provenance={"source_ids": [metric]},
        support_map={
            "metric_representation_id": metric,
            "max_reprojection_error_m": 0.01,
            "semantic_entity_ids": [entity_id],
            "anchors": [{"semantic_entity_id": entity_id, "position": [0.0, 0.0, 0.0], "confidence": 1.0}],
        },
        information_losses=["decimated_surface"],
        dependencies=[metric],
        actor_id=actor,
    )
    target_proxy = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=target_proxy_asset.asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id=provider_id,
        coordinate_frame_id="frame-preservation-proxy-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking"],
        prohibited_uses=["verified_measurement"],
        quality={"collision_coverage": 1.0},
        provenance={"source_ids": [metric]},
        support_map={
            "metric_representation_id": metric,
            "max_reprojection_error_m": 0.01,
            "semantic_entity_ids": [entity_id],
            "anchors": [{"semantic_entity_id": entity_id, "position": [0.01, 0.0, 0.0], "confidence": 0.99}],
        },
        information_losses=["decimated_surface"],
        dependencies=[metric],
        actor_id=actor,
    )
    for proxy_id in (source_proxy, target_proxy):
        context.representations.review_quality(
            proxy_id,
            reviewer_id="interaction-reviewer",
            approved_uses=["picking"],
            metrics={"raycast_p95_ms": 2.0},
            passed=True,
        )
    context.publisher.publish(
        target_proxy,
        commit_id=scene["commit_id"],
        role="picking",
        publisher_id="publisher",
    )

    annotation = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=entity_id,
        coordinate_frame_id="frame-preservation-proxy-world",
        support_type="semantic_entity",
        support={"semantic_entity_id": entity_id},
        position=[0.0, 0.0, 0.0],
        uncertainty_m=0.02,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        actor_id=actor,
        authored_from_representation_id=source_proxy,
    )
    remap = context.spatial_data.remap_annotations(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        source_representation_id=source_proxy,
        target_representation_id=target_proxy,
        actor_id=actor,
    )
    assert remap["resolved_annotation_ids"] == [annotation["annotation_id"]]

    resolved = context.scene.resolve_proxy_hit(
        tenant_id,
        project_id,
        ProxyHit(
            representation_id=target_proxy,
            world_point=[0.25, 0.0, 0.0],
            normal=[0.0, 1.0, 0.0],
            support_hint={"semantic_entity_id": entity_id},
        ),
    )
    measurement_id = context.scene.create_measurement(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=entity_id,
        value=0.25,
        unit="m",
        uncertainty=0.02,
        source_asset_ids=resolved["metric_source_asset_ids"],
        calibration={"method": "server_metric_reprojection", "asset_id": metric_asset.asset_id},
        verifier_id=None,
        verified=False,
        actor_id=actor,
        originating_representation_id=target_proxy,
        interaction_hit=resolved["interaction_hit"],
        geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [0.25, 0.0, 0.0]},
        coordinate_frame_id="frame-preservation-proxy-world",
        permitted_uses=["reference"],
    )

    package_path = tmp_path / "proxy-lineage.sip-preservation.zip"
    context.preservation.export_project(tenant_id, project_id, package_path, actor_id=actor)
    restored = context.preservation.import_project(
        package_path,
        new_tenant_id="tenant-proxy-restored",
        new_project_id="project-proxy-restored",
        actor_id="restore-operator",
    )
    mapped_metric_asset = restored["id_maps"]["asset"][metric_asset.asset_id]
    mapped_metric = restored["id_maps"]["representation"][metric]
    mapped_source_proxy = restored["id_maps"]["representation"][source_proxy]
    mapped_target_proxy = restored["id_maps"]["representation"][target_proxy]
    mapped_entity = restored["id_maps"]["entity"][entity_id]
    mapped_annotation = restored["id_maps"]["annotation"][annotation["annotation_id"]]
    mapped_remap = restored["id_maps"]["anchor_remap"][remap["remap_id"]]
    mapped_measurement = restored["id_maps"]["measurement"][measurement_id]
    assert mapped_target_proxy != target_proxy
    assert mapped_measurement != measurement_id

    with context.database.session() as session:
        restored_measurement = session.get(MeasurementRow, mapped_measurement)
        assert restored_measurement is not None
        assert restored_measurement.entity_id == mapped_entity
        assert restored_measurement.originating_representation_id == mapped_target_proxy
        assert restored_measurement.source_asset_ids_json == [mapped_metric_asset]
        assert restored_measurement.calibration_json["asset_id"] == mapped_metric_asset
        assert restored_measurement.interaction_hit_json["representation_id"] == mapped_target_proxy
        assert restored_measurement.resolved_metric_evidence_json["metric_representation_id"] == mapped_metric
        assert restored_measurement.resolved_metric_evidence_json["metric_source_asset_ids"] == [mapped_metric_asset]
        assert restored_measurement.state == "measured"
        assert restored_measurement.verified_at is None

        restored_annotation = session.get(SpatialAnnotationRow, mapped_annotation)
        assert restored_annotation is not None
        assert restored_annotation.entity_id == mapped_entity
        assert restored_annotation.authored_from_representation_id == mapped_target_proxy
        history = restored_annotation.support_json["remap_history"]
        assert history[-1]["remap_id"] == mapped_remap
        assert history[-1]["source_representation_id"] == mapped_source_proxy
        assert history[-1]["target_representation_id"] == mapped_target_proxy
        assert history[-1]["prior_support"] == {"semantic_entity_id": mapped_entity}

        restored_remap = session.get(AnchorRemapRow, mapped_remap)
        assert restored_remap is not None
        assert restored_remap.source_representation_id == mapped_source_proxy
        assert restored_remap.target_representation_id == mapped_target_proxy
        assert restored_remap.resolved_annotation_ids_json == [mapped_annotation]
        assert restored_remap.unresolved_annotation_ids_json == []
        assert restored_remap.metrics_json["per_annotation"][0]["annotation_id"] == mapped_annotation
