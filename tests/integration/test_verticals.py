from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sip.errors import AuthorizationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SourceClass


@pytest.mark.integration
@pytest.mark.acceptance
def test_construction_complete_record_deficiency_retest_measurement_and_reports(bootstrapped, tmp_path) -> None:
    """REQ: CONHYB-007, CONMEAS-001 construction hierarchy, evidence-backed retest closure, verified measurement metadata, and handoff reports."""
    context, tenant_id, project_id, actor = bootstrapped
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="site", name="Synthetic Campus", parent_id=None, state="observed", actor_id=actor
    )
    building = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="building", name="Building A", parent_id=site, state="observed", actor_id=actor
    )
    level = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="level", name="Level 1", parent_id=building, state="observed", actor_id=actor
    )
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="room", name="Electrical 101", parent_id=level, state="observed", actor_id=actor
    )
    panel = context.construction.create_system_record(
        tenant_id=tenant_id,
        project_id=project_id,
        system_type="fire_alarm_panel",
        parent_id=room,
        entity_id="entity-panel",
        state="observed",
        data={"manufacturer": "Synthetic", "model": "FACP-1"},
        evidence_asset_ids=["photo-panel"],
        actor_id=actor,
    )
    deficiency = context.construction.create_deficiency(
        tenant_id=tenant_id,
        project_id=project_id,
        entity_id="entity-panel",
        description="Missing circuit label",
        severity="medium",
        evidence_asset_ids=["photo-before"],
        actor_id=actor,
    )
    correction = context.construction.correct_and_retest(
        deficiency,
        tenant_id=tenant_id,
        project_id=project_id,
        correction="Installed durable circuit label",
        correction_asset_ids=["photo-after"],
        test_result="pass",
        test_asset_ids=["test-record"],
        tester_id="commissioning-agent",
    )
    assert correction["state"] == "closed"
    scene = context.scene.create_scene(tenant_id, project_id, name="Construction scene", actor_id=actor)
    context.spatial_data.register_frame(
        tenant_id=tenant_id, project_id=project_id, name="Construction world",
        convention="right_handed_y_up_meters", units="meter", original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right", origin_description="synthetic construction origin",
        source="synthetic_fixture", actor_id=actor, frame_id="frame-construction-world",
    )
    tape_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic tape photograph",
        media_type="image/jpeg", original_name="tape-photo.jpg",
        classification=Classification.INTERNAL, retention_class="test",
        source_class=SourceClass.DIRECT_CAPTURE, authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-fixture"]), actor_id=actor,
    )
    calibration_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic calibration card",
        media_type="application/json", original_name="calibration-card.json",
        classification=Classification.INTERNAL, retention_class="test",
        source_class=SourceClass.VERIFIED, authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-fixture"]), actor_id=actor,
    )
    context.scene.create_entity(
        tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"],
        entity_type="fire_alarm_panel", name="Synthetic FACP-1",
        attributes={"construction_record_id": panel}, source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE, confidence=1.0,
        provenance=ProvenanceRef(source_ids=[tape_asset.asset_id]), policy={"audience": "project"},
        stable_support={"frame_id": "frame-construction-world", "point": [0.0, 1.52, 0.0]},
        actor_id=actor, entity_id="entity-panel",
    )
    measurement = context.scene.create_measurement(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id="entity-panel",
        value=1.52,
        unit="m",
        uncertainty=0.003,
        source_asset_ids=[tape_asset.asset_id, calibration_asset.asset_id],
        calibration={"instrument": "traceable laser", "certificate": "CAL-001", "asset_id": calibration_asset.asset_id},
        verifier_id="field-verifier",
        verified=True,
        actor_id=actor,
        measurement_type="height",
        geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [0.0, 1.52, 0.0]},
        source_method="field_verified_laser",
        coordinate_frame_id="frame-construction-world",
    )
    technical = context.construction.technical_report(tenant_id, project_id)
    assert technical["record_counts"]["fire_alarm_panel"] == 1
    assert any(item["measurement_id"] == measurement and item["verifier_id"] == "field-verifier" for item in technical["measurements"])
    assert "not survey-grade" in technical["warnings"][0]
    assert context.construction.export_bcf(tenant_id, project_id, tmp_path / "handoff.bcf.json")["topics"] == 1
    assert context.construction.export_ifc_handoff_manifest(tenant_id, project_id, tmp_path / "ifc-handoff.json")["format"]


@pytest.mark.integration
@pytest.mark.privacy
@pytest.mark.acceptance
def test_liveforever_conflicting_recollections_generated_label_audience_revocation_and_safe_exit(bootstrapped) -> None:
    """REQ: LIFOVR-002, LIFCONS-005, LIFHYB-007, LIFHYB-011 conflicting sources, generated labels, revocation, and safe experience gates remain distinct."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "person-alex"
    grant = context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        granted_by="alex",
        purposes=["preservation", "family_review"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["*"],
        derivative_policy={"generated_visual": True, "voice": False, "likeness": False},
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    person = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="person",
        subject_id=subject,
        related_ids=[],
        data={"name": "Alex Example"},
        source_class=SourceClass.CORROBORATED,
        confidence=1,
        evidence_asset_ids=["birth-record"],
        audience=Audience.FAMILY,
        actor_id=actor,
    )
    alternatives = context.liveforever.conflicting_recollections(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        event_key="family-trip-1984",
        recollections=[
            {"recollector_id": "alex", "account": "It rained all day", "confidence": 0.7, "evidence_asset_ids": ["interview-a"]},
            {"recollector_id": "sam", "account": "It was sunny by lunch", "confidence": 0.6, "evidence_asset_ids": ["interview-b"]},
        ],
        audience=Audience.FAMILY,
        actor_id=actor,
    )
    generated = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="generated_reconstruction",
        subject_id=subject,
        related_ids=[person],
        data={"description": "Illustrative reconstruction of the kitchen"},
        source_class=SourceClass.GENERATED,
        confidence=0.8,
        evidence_asset_ids=["photo-kitchen"],
        audience=Audience.FAMILY,
        actor_id=actor,
        generated_lineage={
            "model_manifest_id": "approved-synthetic",
            "model_checkpoint_hash": "a" * 64,
            "prompt_hash": "b" * 64,
            "input_asset_ids": ["photo-kitchen"],
            "output_hash": "c" * 64,
        },
    )
    family = context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review")
    assert {person, generated, *alternatives}.issubset({item["record_id"] for item in family["records"]})
    generated_record = next(item for item in family["records"] if item["record_id"] == generated)
    assert "AI-GENERATED" in generated_record["data"]["generated_label"]
    public = context.liveforever.edition(tenant_id, project_id, audience=Audience.PUBLIC, purpose="preservation")
    assert public["records"] == []
    safe = context.liveforever.experience_configuration(tenant_id, project_id, subject, requested_features={}, audience=Audience.FAMILY)
    assert safe["features"]["quiet_mode"] and safe["features"]["safe_exit"] and not safe["features"]["free_locomotion"]
    with pytest.raises(AuthorizationError):
        context.liveforever.experience_configuration(
            tenant_id, project_id, subject, requested_features={"voice_simulation": True}, audience=Audience.FAMILY
        )
    revoked = context.liveforever.revoke_consent(grant, tenant_id=tenant_id, project_id=project_id, actor_id="alex", reason="changed preference")
    assert revoked["affected_records"] >= 4
    assert context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review")["records"] == []
