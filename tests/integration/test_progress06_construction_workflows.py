from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sip.errors import ValidationError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass


@pytest.mark.integration
def test_progress06_construction_hierarchy_coordinate_frames_and_system_packs(bootstrapped) -> None:
    """REQ: CONHIER-001, CONHIER-002, CONHIER-004, CONFA-001, CONFA-002, CONAC-001, CONAC-004, CONMEP-001, CONMEP-002, CONMEP-003, CONMEP-004, CONMEP-005 system and place records retain stable spatial, evidence, and truth metadata without changing owner policy."""
    context, tenant_id, project_id, actor = bootstrapped
    site_frame = context.spatial_data.register_frame(
        tenant_id=tenant_id, project_id=project_id, name="Synthetic site frame",
        convention="right_handed_z_up_meters", units="meter", unit_scale_to_meters=1.0,
        original_units="meter", original_unit_scale_to_meters=1.0,
        axis_convention="ENU", axis_directions={"x": "east", "y": "north", "z": "up"},
        handedness="right", origin_description="Synthetic site benchmark", source="synthetic-control",
        actor_id=actor, semantic_type="site", frame_id="synthetic-site-frame",
    )
    building_frame = context.spatial_data.register_frame(
        tenant_id=tenant_id, project_id=project_id, name="Synthetic building frame",
        convention="right_handed_y_up_meters", units="meter", unit_scale_to_meters=1.0,
        original_units="foot", original_unit_scale_to_meters=0.3048,
        axis_convention="XYZ", axis_directions={"x": "east", "y": "up", "z": "south"},
        handedness="right", origin_description="Synthetic building grid A/1", source="synthetic-survey",
        actor_id=actor, semantic_type="building", frame_id="synthetic-building-frame",
        parent_frame_id=site_frame["frame_id"],
        transform_to_parent=[[1, 0, 0, 10], [0, 1, 0, 20], [0, 0, 1, 0], [0, 0, 0, 1]],
        uncertainty_m=0.01,
    )
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="site", name="Synthetic Campus",
        parent_id=None, state="observed", actor_id=actor,
        attributes={"aliases": ["Test Campus"], "coordinate_frame_id": site_frame["frame_id"],
                    "validity": {"from": "2026-01-01"}, "source": "synthetic-survey",
                    "access_classification": "internal", "evidence": ["synthetic-site-control"]},
    )
    building = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="building", name="Building A",
        parent_id=site, state="observed", actor_id=actor,
        attributes={"aliases": ["A"], "coordinate_frame_id": building_frame["frame_id"],
                    "source": "synthetic-survey", "access_classification": "confidential"},
    )
    level = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="level", name="Level 1",
        parent_id=building, state="observed", actor_id=actor,
    )
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="room", name="Electrical 101",
        parent_id=level, state="observed", actor_id=actor,
        attributes={"room_number_sources": {"signage": "E101", "drawing": "101", "owner": "EL-101"},
                    "mapping_state": "review_required"},
    )
    zone = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="zone", name="FA Notification Zone 1",
        parent_id=level, state="design", actor_id=actor,
        attributes={"zone_type": "fire_alarm_notification", "containment_rule": "semantic_not_geometric"},
    )
    assert room != zone

    facp = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="fire_alarm_panel", parent_id=room,
        entity_id="FACP-1", state="observed", actor_id=actor, evidence_asset_ids=["photo-facp"],
        data={"manufacturer": "Synthetic", "model": "FACP-1", "address": "1", "label": "FACP-1",
              "panel": "FACP-1", "loop": None, "circuit": "SLC-1", "location": "Electrical 101",
              "mount": "wall", "condition": "serviceable", "drawing_reference": "FA-101/A",
              "photograph": "photo-facp", "source_class": "observed", "test_status": "pending"},
    )
    door = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="access_opening", parent_id=room,
        entity_id="DOOR-101", state="observed", actor_id=actor, evidence_asset_ids=["photo-door"],
        data={"manufacturer": "Synthetic", "model": "Opening-1", "opening_id": "DOOR-101",
              "side": "secure", "handing": "RH", "frame_condition": "good", "door_condition": "good",
              "hardware": ["closer", "panic"], "power_transfer": "EPT", "lock": "electric strike",
              "reader": "R-101", "contact": "DPS-101", "rex": "REX-101", "egress_hardware": "panic",
              "controller_association": "CTRL-1", "pathway": "north corridor",
              "dimensions": {"width": 0.914, "height": 2.032, "unit": "m", "source": "field_verified"},
              "photographs": ["photo-door"], "location": "Electrical 101"},
    )
    equipment = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="mechanical_equipment", parent_id=room,
        entity_id="AHU-1", state="observed", actor_id=actor, evidence_asset_ids=["photo-nameplate"],
        data={"manufacturer": "Synthetic", "model": "AHU-1", "serial": "SYN-001", "tag": "AHU-1",
              "aliases": ["Air Handler 1"], "type": "air_handler", "capacities": {"airflow_cfm": 1000},
              "serves": [room], "power_connection": "PANEL-L1/1", "control_connection": "BAS-CTRL-1",
              "clearances": {"front_m": 0.9, "source": "scan_estimate"},
              "nameplate_media": ["photo-nameplate"], "documents": ["cutsheet-ahu"], "status": "operational"},
    )
    point = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="bas_point", parent_id=equipment,
        entity_id="AHU-1-SAT", state="observed", actor_id=actor, evidence_asset_ids=["trend-sat"],
        data={"manufacturer": "Synthetic", "model": "VirtualPoint", "equipment_id": equipment,
              "point_name": "SAT", "kind": "sensor", "source": "BAS export", "verification": "reviewed",
              "operational_data": {"source_system": "Synthetic BAS", "units": "degF",
                                   "timestamps": ["2026-07-29T00:00:00Z"], "quality_flags": ["good"],
                                   "retention": "30d"}},
    )
    dependency = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="system_interconnection", parent_id=room,
        entity_id="FA-AHU-SHUTDOWN", state="design", actor_id=actor, evidence_asset_ids=[],
        data={"manufacturer": "n/a", "model": "interface", "from": facp, "to": equipment,
              "function": "fire_alarm_shutdown", "source": "design_sequence"},
    )
    incomplete = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="access_reader", parent_id=room,
        entity_id="R-102", state="proposed", actor_id=actor, evidence_asset_ids=[], data={"location": "Unassigned"},
    )
    access = context.construction.export_system_pack(tenant_id, project_id, pack="access_control")
    by_id = {item["record_id"]: item for item in access["records"]}
    assert by_id[door]["data"]["opening_id"] == "DOOR-101"
    assert by_id[incomplete]["data"]["completeness_status"] == "incomplete_review_required"
    assert by_id[incomplete]["data"]["missing_required_fields"] == ["manufacturer", "model"]
    assert "access_policy" not in by_id[incomplete]["data"]
    mep = context.construction.export_system_pack(tenant_id, project_id, pack="mep")
    mep_ids = {item["record_id"] for item in mep["records"]}
    assert {equipment, point, dependency}.issubset(mep_ids)
    fire = context.construction.export_system_pack(tenant_id, project_id, pack="fire_alarm")
    assert next(item for item in fire["records"] if item["record_id"] == facp)["data"]["drawing_reference"] == "FA-101/A"


@pytest.mark.integration
def test_progress06_construction_documents_reports_bim_and_owner_handoff(bootstrapped, tmp_path: Path) -> None:
    """REQ: CONDOC-001, CONDOC-002, CONDOC-003, CONDOC-004, CONDOC-005, CONDOC-006, CONHAND-001, CONHAND-002, CONHAND-003, CONHAND-004, CONHAND-006, CONREP-001, CONREP-002, CONREP-003, CONREP-004, CONREP-005, DATBIM-001, DATBIM-002, DATBIM-003, DATBIM-005, DATBIM-006 owner handoff preserves exact revisions, reviewed mappings, truth labels, redaction, deterministic report identity, and offline access."""
    context, tenant_id, project_id, actor = bootstrapped
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id=actor,
    )
    building = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="building", name="Building A",
        parent_id=site, state="observed", actor_id=actor,
    )
    level = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="level", name="Level 1",
        parent_id=building, state="observed", actor_id=actor,
    )
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="room", name="Room 101",
        parent_id=level, state="observed", actor_id=actor,
    )
    panel = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="fire_alarm_panel", parent_id=room,
        entity_id="FACP-1", state="observed", actor_id=actor, evidence_asset_ids=["photo-facp"],
        data={"manufacturer": "Synthetic", "model": "FACP-1", "location": "Room 101",
              "network_address": "192.0.2.10", "programming_password": "never-export"},
    )
    context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="access_reader", parent_id=room,
        entity_id="R-INCOMPLETE", state="proposed", actor_id=actor, evidence_asset_ids=[], data={"location": "Room 101"},
    )
    drawing = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic drawing A", media_type="application/pdf",
        original_name="FA-101-A.pdf", classification=Classification.INTERNAL, retention_class="project-record",
        source_class=SourceClass.DESIGN, authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-design"]), actor_id=actor,
    )
    rev_a = context.construction.create_document_revision(
        tenant_id=tenant_id, project_id=project_id, stable_document_id="FA-101", document_type="drawing",
        title="Fire Alarm Plan", revision="A", issue_date="2026-07-01", issuer="Synthetic Engineer",
        status="issued_for_reference", asset_id=drawing.asset_id, source_sha256=drawing.sha256, page_count=1,
        permissions={"audiences": ["project", "owner"], "owner_export": True},
        page_regions=[{"page": 1, "coordinate_system": "pdf_points", "polygon": [[10, 10], [100, 10], [100, 80], [10, 80]],
                       "label": "FACP-1", "evidence_asset_id": drawing.asset_id}],
        spatial_links=[{"page": 1, "region_label": "FACP-1", "entity_id": panel, "space_id": room,
                        "review_state": "accepted"}],
        extraction={"proposals": [{"page": 1, "region": [10, 10, 100, 80], "confidence": 0.94}],
                    "authoritative": False},
        review={"state": "accepted", "reviewer": actor, "accepted_mappings": [panel]}, actor_id=actor,
    )
    drawing_b = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic drawing B", media_type="application/pdf",
        original_name="FA-101-B.pdf", classification=Classification.INTERNAL, retention_class="project-record",
        source_class=SourceClass.DESIGN, authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[drawing.asset_id]), actor_id=actor,
    )
    rev_b = context.construction.create_document_revision(
        tenant_id=tenant_id, project_id=project_id, stable_document_id="FA-101", document_type="drawing",
        title="Fire Alarm Plan", revision="B", issue_date="2026-07-15", issuer="Synthetic Engineer",
        status="issued_for_reference", asset_id=drawing_b.asset_id, source_sha256=drawing_b.sha256, page_count=1,
        permissions={"audiences": ["project", "owner"], "owner_export": True}, page_regions=[],
        spatial_links=[{"page": 1, "entity_id": panel, "space_id": room, "review_state": "accepted"}],
        extraction={"proposals": [], "authoritative": False},
        review={"state": "accepted", "reviewer": actor}, actor_id=actor,
        supersedes_revision_id=rev_a["revision_id"],
    )
    rfi_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic RFI response", media_type="text/plain",
        original_name="RFI-001.txt", classification=Classification.INTERNAL, retention_class="project-record",
        source_class=SourceClass.DESIGN, authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[rev_b["revision_id"]]), actor_id=actor,
    )
    rfi = context.construction.create_document_revision(
        tenant_id=tenant_id, project_id=project_id, stable_document_id="RFI-001", document_type="rfi",
        title="Confirm panel mounting", revision="1", issue_date="2026-07-20", issuer="Synthetic GC",
        status="answered", asset_id=rfi_asset.asset_id, source_sha256=rfi_asset.sha256, page_count=1,
        permissions={"audiences": ["project", "owner"], "owner_export": True}, page_regions=[],
        spatial_links=[{"entity_id": panel, "space_id": room, "affected_scene_commit_id": None}],
        extraction={"question": "Confirm mounting", "context": "Room 101", "responsible_parties": ["Synthetic EC"],
                    "due_date": "2026-07-25", "response": "Mount as shown", "attachments": [rev_b["revision_id"]],
                    "confidence": 1.0, "authoritative": True},
        review={"state": "accepted", "reviewer": actor}, actor_id=actor,
    )
    exact = context.construction.document_revision(tenant_id, project_id, rev_b["revision_id"])
    assert exact["supersedes_revision_id"] == rev_a["revision_id"]
    assert exact["spatial_links"][0]["entity_id"] == panel
    assert context.construction.document_revision(tenant_id, project_id, rfi["revision_id"])["extraction"]["response"] == "Mount as shown"

    ifc = context.assets.ingest_bytes(
        tenant_id=tenant_id, project_id=project_id, data=b"synthetic ifc", media_type="application/x-step",
        original_name="synthetic.ifc", classification=Classification.INTERNAL, retention_class="project-record",
        source_class=SourceClass.DESIGN, authority_class=AuthorityClass.DESIGN,
        provenance=ProvenanceRef(source_ids=["synthetic-bim"]), actor_id=actor,
    )
    context.construction.record_interchange(
        tenant_id=tenant_id, project_id=project_id, format="IFC", direction="import",
        source_asset_id=ifc.asset_id, source_sha256=ifc.sha256, schema_version="IFC4", units="meter",
        crs={"identifier": "SYNTHETIC:LOCAL"}, owner_history={"application": "Synthetic BIM"},
        global_ids=["SYN-FACP-1"], classifications={"SYN-FACP-1": "IfcDistributionControlElement"},
        properties={"SYN-FACP-1": {"manufacturer": "Synthetic"}},
        relationships=[{"from": "SYN-FACP-1", "to": room, "type": "contained_in"}],
        geometry_conversion_report={"converted": 1, "failed": 0, "representation": "design"},
        unsupported_constructs=[{"type": "IfcSyntheticUnsupported", "action": "retained_in_report"}],
        alignment={"transform_type": "SE3", "residual_m": 0.01, "controls": ["synthetic-control"]},
        mappings=[{"design_id": "SYN-FACP-1", "field_id": panel, "state": "proposed"}], issues=[],
        truth_labels={"SYN-FACP-1": "design", panel: "observed"}, actor_id=actor, idempotency_key="ifc-import",
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Synthetic handoff scene", actor_id=actor)
    report_a = context.construction.technical_report(
        tenant_id, project_id, scope={"rooms": [room]}, scene_commit_id=scene["commit_id"],
        author_id=actor, template_version="p06.1", filters={"state": ["observed", "design"]},
        design_revision_ids=[rev_b["revision_id"]], representations_used=["metric", "design", "evidence"],
        excluded_areas=[{"region": "restricted-rack", "reason": "policy"}],
    )
    report_b = context.construction.technical_report(
        tenant_id, project_id, scope={"rooms": [room]}, scene_commit_id=scene["commit_id"],
        author_id=actor, template_version="p06.1", filters={"state": ["observed", "design"]},
        design_revision_ids=[rev_b["revision_id"]], representations_used=["metric", "design", "evidence"],
        excluded_areas=[{"region": "restricted-rack", "reason": "policy"}],
    )
    assert report_a["report_hash"] == report_b["report_hash"]
    assert report_a["scene_commit_id"] == scene["commit_id"]
    assert report_a["measurement_authority"]["scan_estimate"].startswith("unverified")

    destination = tmp_path / "construction-owner-handoff.zip"
    result = context.construction.create_owner_handoff(
        tenant_id=tenant_id, project_id=project_id, destination=destination,
        scope={"rooms": [room], "systems": ["fire_alarm", "access_control"]},
        accepted_scene_commit_id=scene["commit_id"], warranties=[{"equipment_id": panel, "status": "synthetic"}],
        training=[{"topic": "owner navigation", "status": "complete"}], exclusions=["restricted programming files"],
        audience_profiles={"owner": {"read_only": True}, "restricted_owner_export_approved": False},
        actor_id=actor, idempotency_key="owner-handoff-conformance",
    )
    assert result["status"] == "verified"
    with zipfile.ZipFile(destination) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        inventory = json.loads(archive.read("data/inventory.json"))
        interchange = json.loads(archive.read("data/interchange.json"))
        validation = json.loads(archive.read("data/handoff-validation.json"))
        html = archive.read("viewer/index.html").decode()
    panel_export = next(item for item in inventory if item["record_id"] == panel)
    assert "network_address" not in panel_export["data"]
    assert "programming_password" not in panel_export["data"]
    assert manifest["scope"]["rooms"] == [room]
    assert manifest["accepted_scene_commit_id"] == scene["commit_id"]
    assert manifest["warranties"] and manifest["training"] and manifest["exclusions"]
    assert validation["status"] == "needs_review"
    assert validation["required_field_findings"]
    assert interchange[0]["truth_labels"][panel] == "observed"
    assert "requires no network connection" in html
    search = context.construction.search_facility_records(tenant_id, project_id, query="FACP-1")
    assert any(item["kind"] == "record" and item["id"] == panel for item in search["items"])


@pytest.mark.integration
def test_progress06_construction_return_visit_and_coverage_safe_temporal_review(bootstrapped) -> None:
    """REQ: CONSURV-006, CONPROG-001, CONPROG-002, CONPROG-004, CONPROG-005, CONHYB-009 return visits preserve exact accepted baselines and temporal gaps remain review candidates rather than automatic removals or payment conclusions."""
    context, tenant_id, project_id, actor = bootstrapped
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id=actor,
    )
    building = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="building", name="Building A",
        parent_id=site, state="observed", actor_id=actor,
    )
    level = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="level", name="Level 1",
        parent_id=building, state="observed", actor_id=actor,
    )
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant_id, project_id=project_id, record_type="room", name="Room 101",
        parent_id=level, state="observed", actor_id=actor,
    )
    before = context.construction.create_system_record(
        tenant_id=tenant_id, project_id=project_id, system_type="fire_alarm_device", parent_id=room,
        entity_id="SD-1", state="observed", data={"manufacturer": "Synthetic", "model": "Smoke",
        "location": "Room 101"}, evidence_asset_ids=["photo-before"], actor_id=actor,
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Baseline", actor_id=actor)
    survey = context.construction.create_survey_plan(
        tenant_id=tenant_id, project_id=project_id, name="Baseline survey", objectives=["document room"],
        required_place_ids=[room], required_system_types=["fire_alarm_device"], sensitive_regions=[],
        control_requirements={"known_scale": True}, measurement_requirements={}, safety={"stop_work": True},
        permissions={"capture": "approved"}, deliverables=[{"type": "survey_report"}], actor_id=actor,
        idempotency_key="baseline-survey", baseline_commit_id=scene["commit_id"],
    )
    context.construction.record_field_visit(
        tenant_id=tenant_id, project_id=project_id, survey_id=survey["survey_id"], scope={"rooms": [room]},
        capture_ids=["capture-baseline"], checklist=[{"id": "room", "status": "complete"}], detail_evidence=[],
        inaccessible_regions=[], coverage={"observed_fraction": 1.0}, tracking={"state": "normal"},
        registration={"state": "accepted"}, controls={"known_scale": True}, inventory={"systems": [before]},
        unresolved_questions=[], privacy={}, actor_id=actor, idempotency_key="baseline-visit",
        exact_prior_commit_id=scene["commit_id"], complete=True,
    )
    context.construction.review_survey(
        survey["survey_id"], tenant_id=tenant_id, project_id=project_id, reviewer_id="independent-reviewer",
        decision="accept", checklist={"items": [{"id": "coverage", "required": True, "status": "pass"}]},
        accepted_commit_id=scene["commit_id"], limitations=[],
    )
    return_survey = context.construction.create_survey_plan(
        tenant_id=tenant_id, project_id=project_id, name="Return survey", objectives=["compare room"],
        required_place_ids=[room], required_system_types=["fire_alarm_device"], sensitive_regions=[],
        control_requirements={"known_scale": True}, measurement_requirements={}, safety={"stop_work": True},
        permissions={"capture": "approved"}, deliverables=[{"type": "progress_report"}], actor_id=actor,
        idempotency_key="return-survey", baseline_commit_id=scene["commit_id"], return_visit_of_id=survey["survey_id"],
    )
    assert context.construction.survey(tenant_id, project_id, return_survey["survey_id"])["return_visit_of_id"] == survey["survey_id"]
    comparison = context.construction.compare_temporal_states(
        tenant_id, project_id, before_ids=[before], after_ids=[], unobserved_ids=[before],
        baseline_commit_id=scene["commit_id"], comparison_commit_id=scene["commit_id"],
        comparable_coverage={"fraction": 0.6, "limitations": ["ceiling occluded"]},
    )
    assert comparison["removed"] == []
    assert comparison["unobserved"] == [before]
    assert comparison["review_required"] == [before]
    assert comparison["semantic_state_changed"] is False
    assert "payment" not in comparison
    with pytest.raises(ValidationError) as invalid:
        context.construction.compare_temporal_states(
            tenant_id, project_id, before_ids=[before], after_ids=[], confirmed_removed_ids=[before],
            unobserved_ids=[before], baseline_commit_id=scene["commit_id"], comparison_commit_id=scene["commit_id"],
        )
    assert invalid.value.code == "TEMPORAL_REMOVAL_COVERAGE_CONFLICT"
