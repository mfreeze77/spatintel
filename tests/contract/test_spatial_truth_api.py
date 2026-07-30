from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings
from sip.database import AssertionRow, AuditEventRow
from sip.models import AuthorityClass, RepresentationKind, SourceClass


def _headers(tenant: str, project: str, *, subject: str = "spatial-api-admin") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": "tenant_admin",
        "X-SIP-Purposes": "construction,operations",
        "X-SIP-Audience": "private",
    }


def _ingest(client: TestClient, tenant_id: str, project_id: str, name: str, payload: bytes) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/assets",
        headers=_headers(tenant_id, project_id),
        json={
            "content_base64": base64.b64encode(payload).decode(),
            "media_type": "application/octet-stream",
            "original_name": name,
            "classification": "internal",
            "retention_class": "preservation",
            "source_class": "direct_capture",
            "authority_class": "evidence",
            "provenance": {"source_ids": [f"fixture:{name}"]},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["asset_id"]


def test_spatial_truth_and_twin_contracts_are_authenticated_and_round_trip(tmp_path: Path) -> None:
    """REQ: DATFRAME-001, DATGEOM-001, DATEVID-001, DATANCH-001, DATANCH-002, DATGIT-003 typed APIs preserve scope, evidence, measurements, and temporal scene identity."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("Spatial API tenant", tenant_id="spatial-api-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Spatial API project",
        vertical="platform",
        classification="internal",
        project_id="spatial-api-project",
        actor_id="bootstrap",
    )
    client = TestClient(create_app(context=context, service_name="all"))
    headers = _headers(tenant_id, project_id)

    geometry_asset_id = _ingest(client, tenant_id, project_id, "room.glb", b"deterministic geometry")
    evidence_asset_id = _ingest(client, tenant_id, project_id, "photo.bin", b"immutable field evidence")

    scene = client.post(
        f"/v1/projects/{project_id}/scenes",
        headers=headers,
        json={"name": "Spatial API room"},
    )
    assert scene.status_code == 201, scene.text
    scene_id = scene.json()["scene_id"]
    initial_commit_id = scene.json()["commit_id"]

    world = client.post(
        f"/v1/projects/{project_id}/coordinate-frames",
        headers=headers,
        json={
            "frame_id": "frame-world",
            "name": "World",
            "convention": "right_handed_y_up_meters",
            "units": "meter",
            "original_units": "meter",
            "axis_convention": "right_handed_y_up",
            "axis_directions": {"x": "+X right", "y": "+Y up", "z": "-Z forward"},
            "handedness": "right",
            "origin_description": "fixture origin",
            "source": "test",
        },
    )
    assert world.status_code == 201, world.text

    design = client.post(
        f"/v1/projects/{project_id}/coordinate-frames",
        headers=headers,
        json={
            "frame_id": "frame-design",
            "name": "Design",
            "convention": "right_handed_y_up_meters",
            "units": "meter",
            "original_units": "millimeter",
            "axis_convention": "right_handed_y_up",
            "axis_directions": {"x": "+X right", "y": "+Y up", "z": "-Z forward"},
            "handedness": "right",
            "origin_description": "design origin",
            "source": "ifc",
        },
    )
    assert design.status_code == 201, design.text

    transform = client.post(
        f"/v1/projects/{project_id}/spatial-transforms",
        headers=headers,
        json={
            "source_frame_id": "frame-world",
            "target_frame_id": "frame-design",
            "transform_type": "SE3",
            "matrix": [[1.0, 0.0, 0.0, 2.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            "source_type": "registration",
            "authority_class": "metric",
            "residual_summary": {"rmse_m": 0.01},
            "uncertainty": {"translation_sigma_m": 0.01, "rotation_sigma_rad": 0.001},
        },
    )
    assert transform.status_code == 201, transform.text
    resolved = client.get(
        f"/v1/projects/{project_id}/spatial-transforms/resolve",
        headers=headers,
        params={"source_frame_id": "frame-world", "target_frame_id": "frame-design"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["matrix"][0][3] == 2.0

    entity = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/entities",
        headers=headers,
        json={
            "entity_type": "room",
            "name": "Room 101",
            "attributes": {"number": "101"},
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.95,
            "provenance": {"source_ids": [evidence_asset_id]},
            "stable_support": {"coordinate_frame_id": "frame-world"},
        },
    )
    assert entity.status_code == 201, entity.text
    entity_id = entity.json()["entity_id"]

    collected_at = datetime.now(UTC)
    evidence = client.post(
        f"/v1/projects/{project_id}/evidence",
        headers=headers,
        json={
            "asset_id": evidence_asset_id,
            "source_type": "field_photo",
            "collected_at": collected_at.isoformat(),
            "collected_by": "field-tech-1",
            "device_or_tool": "synthetic-camera",
            "location_context": {"scene_id": scene_id, "entity_id": entity_id},
            "relevant_region": {"scene_id": scene_id, "entity_id": entity_id},
            "relevant_time_start": collected_at.isoformat(),
            "relevant_time_end": collected_at.isoformat(),
            "retention_class": "preservation",
            "consent_scope": {"basis": "project_authorization"},
            "access_policy": {"inherit_project_policy": True},
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_id = evidence.json()["evidence_id"]

    assertion = client.post(
        f"/v1/projects/{project_id}/assertions",
        headers=headers,
        json={
            "subject_id": entity_id,
            "predicate": "has_room_number",
            "object_value": "101",
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.95,
            "evidence_ids": [evidence_id],
        },
    )
    assert assertion.status_code == 201, assertion.text
    assert assertion.json()["evidence_ids"] == [evidence_id]
    assertion_id = assertion.json()["assertion_id"]
    fetched_evidence = client.get(
        f"/v1/projects/{project_id}/evidence/{evidence_id}",
        headers=headers,
        params={"purpose": "construction"},
    )
    assert fetched_evidence.status_code == 200, fetched_evidence.text
    assert fetched_evidence.json()["content_sha256"] == fetched_evidence.json()["asset"]["sha256"]
    fetched_assertion = client.get(
        f"/v1/projects/{project_id}/assertions/{assertion_id}",
        headers=headers,
        params={"purpose": "construction", "include_evidence": True},
    )
    assert fetched_assertion.status_code == 200, fetched_assertion.text
    assert fetched_assertion.json()["evidence"][0]["evidence_id"] == evidence_id
    assertion_evidence = client.get(
        f"/v1/projects/{project_id}/assertions/{assertion_id}/evidence",
        headers=headers,
        params={"purpose": "construction"},
    )
    assert assertion_evidence.status_code == 200, assertion_evidence.text
    assert assertion_evidence.json()["items"][0]["evidence_id"] == evidence_id
    assertion_list = client.get(
        f"/v1/projects/{project_id}/assertions",
        headers=headers,
        params={"purpose": "construction", "subject_id": entity_id},
    )
    assert assertion_list.status_code == 200, assertion_list.text
    assert assertion_id in {item["assertion_id"] for item in assertion_list.json()["items"]}

    derivation_body = {
        "activity_type": "capture_normalization",
        "input_ids": [evidence_id],
        "input_hashes": [fetched_evidence.json()["content_sha256"]],
        "algorithm_id": "sip.fixture.normalize",
        "algorithm_version": "1.0.0",
        "parameters_hash": "a" * 64,
        "environment_hash": "b" * 64,
        "code_commit": "c" * 40,
        "output_ids": [geometry_asset_id],
        "output_hashes": [hashlib.sha256(b"deterministic geometry").hexdigest()],
        "software": {"name": "sip.fixture.normalize", "version": "1.0.0"},
        "quality": {"deterministic": True},
        "validation": {"schema_valid": True, "hashes_verified": True},
        "started_at": collected_at.isoformat(),
        "completed_at": (collected_at + timedelta(seconds=1)).isoformat(),
    }
    derivation = client.post(
        f"/v1/projects/{project_id}/derivations",
        headers=headers,
        json=derivation_body,
    )
    assert derivation.status_code == 201, derivation.text
    repeated = client.post(
        f"/v1/projects/{project_id}/derivations",
        headers=headers,
        json=derivation_body,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["derivation_id"] == derivation.json()["derivation_id"]

    geometry = client.post(
        f"/v1/projects/{project_id}/geometry-manifests",
        headers=headers,
        json={
            "asset_id": geometry_asset_id,
            "media_type": "model/gltf-binary",
            "format": "glb",
            "profile": "metric_mesh",
            "format_version": "2.0",
            "coordinate_frame_id": "frame-world",
            "units": "meter",
            "bounds": {"min": [0.0, 0.0, 0.0], "max": [4.0, 3.0, 5.0]},
            "classification": "internal",
            "counts": {"triangles": 12},
            "compression": {"codec": "none"},
            "source_run_id": derivation.json()["derivation_id"],
            "quality": {"schema_valid": True, "bounds_validated": True},
            "validation_state": "valid",
            "truth_label": "observed_metric_fixture",
        },
    )
    assert geometry.status_code == 201, geometry.text
    assert geometry.json()["content_sha256"]

    annotation = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/annotations",
        headers=headers,
        json={
            "coordinate_frame_id": "frame-world",
            "support_type": "semantic_entity",
            "support": {"semantic_entity_id": entity_id},
            "uncertainty_m": 0.02,
            "source_class": "observed",
            "authority_class": "evidence",
            "entity_id": entity_id,
            "position": [1.0, 1.5, 2.0],
        },
    )
    assert annotation.status_code == 201, annotation.text

    measurement = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/measurements",
        headers=headers,
        json={
            "entity_id": entity_id,
            "measurement_type": "height",
            "geometry": {"type": "segment", "start": [1.0, 0.0, 2.0], "end": [1.0, 1.52, 2.0]},
            "value": 1.52,
            "unit": "m",
            "uncertainty": 0.003,
            "source_method": "field_verified_laser",
            "measured_at": collected_at.isoformat(),
            "coordinate_frame_id": "frame-world",
            "source_asset_ids": [evidence_asset_id],
            "calibration": {"certificate": "SYN-CAL-001", "asset_id": evidence_asset_id},
            "verifier_id": "field-verifier",
            "verified": True,
        },
    )
    assert measurement.status_code == 201, measurement.text
    measurement_body = measurement.json()
    assert measurement_body["entity_id"] == entity_id
    assert measurement_body["verification_status"] == "verified"
    assert measurement_body["authority_class"] == "field_verified"
    assert measurement_body["coordinate_frame_id"] == "frame-world"
    assert measurement_body["geometry"]["type"] == "segment"
    retrieved_measurement = client.get(
        f"/v1/projects/{project_id}/scenes/{scene_id}/measurements/{measurement_body['measurement_id']}",
        headers=headers,
    )
    assert retrieved_measurement.status_code == 200, retrieved_measurement.text
    assert retrieved_measurement.json() == measurement_body
    cross_tenant_measurement = client.get(
        f"/v1/projects/{project_id}/scenes/{scene_id}/measurements/{measurement_body['measurement_id']}",
        headers=_headers("other-tenant", project_id),
    )
    assert cross_tenant_measurement.status_code == 404

    committed = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/commits",
        headers=headers,
        json={
            "branch": "main",
            "expected_head": initial_commit_id,
            "message": "Record field evidence",
            "field_visit_id": "visit-2026-07-27",
            "change_evidence_ids": [evidence_id],
            "policy_checks": {"evidence_linked": True},
            "review_state": "reviewed",
            "valid_from": collected_at.isoformat(),
        },
    )
    assert committed.status_code == 201, committed.text
    commit_id = committed.json()["commit_id"]

    tagged = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/tags",
        headers=headers,
        json={"commit_id": commit_id, "name": "field-visit-1", "metadata": {"purpose": "acceptance"}},
    )
    assert tagged.status_code == 201, tagged.text
    as_of = client.get(
        f"/v1/projects/{project_id}/scenes/{scene_id}/as-of",
        headers=headers,
        params={"tag": "field-visit-1"},
    )
    assert as_of.status_code == 200, as_of.text
    assert as_of.json()["commit_id"] == commit_id
    assert as_of.json()["change_evidence_ids"] == [evidence_id]


def test_derivation_api_idempotency_is_tenant_scoped(tmp_path: Path) -> None:
    """REQ: ARCIAM-001, DATEVID-003 derivation idempotency remains deterministic and tenant-scoped."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    client = TestClient(create_app(context=context, service_name="all"))
    now = datetime.now(UTC)
    derivation_ids: list[str] = []
    shared_input = b"same immutable input bytes"
    shared_output = b"same immutable output bytes"
    for suffix in ("a", "b"):
        tenant_id = context.tenancy.create_tenant(f"Tenant {suffix}", tenant_id=f"tenant-{suffix}", actor_id="bootstrap")
        project_id = context.tenancy.create_project(
            tenant_id,
            f"Project {suffix}",
            vertical="platform",
            classification="internal",
            project_id=f"project-{suffix}",
            actor_id="bootstrap",
        )
        input_id = _ingest(client, tenant_id, project_id, "input.bin", shared_input)
        output_id = _ingest(client, tenant_id, project_id, "output.bin", shared_output)
        body = {
            "activity_type": "deterministic_fixture",
            "input_ids": [input_id],
            "input_hashes": [hashlib.sha256(shared_input).hexdigest()],
            "algorithm_id": "same-algorithm",
            "algorithm_version": "1.0.0",
            "parameters_hash": "1" * 64,
            "environment_hash": "2" * 64,
            "code_commit": "3" * 40,
            "output_ids": [output_id],
            "output_hashes": [hashlib.sha256(shared_output).hexdigest()],
            "software": {"name": "same-algorithm", "version": "1.0.0"},
            "quality": {"schema_valid": True},
            "validation": {"schema_valid": True, "hashes_verified": True},
            "started_at": now.isoformat(),
            "completed_at": (now + timedelta(seconds=1)).isoformat(),
        }
        first = client.post(
            f"/v1/projects/{project_id}/derivations",
            headers=_headers(tenant_id, project_id),
            json=body,
        )
        assert first.status_code == 201, first.text
        second = client.post(
            f"/v1/projects/{project_id}/derivations",
            headers=_headers(tenant_id, project_id),
            json=body,
        )
        assert second.status_code == 201, second.text
        assert second.json()["derivation_id"] == first.json()["derivation_id"]
        derivation_ids.append(first.json()["derivation_id"])
    assert derivation_ids[0] != derivation_ids[1]


def test_proxy_hit_api_reresolves_server_side_and_rejects_forged_metric_evidence(tmp_path: Path) -> None:
    """REQ: DATANCH-002, DATHYB-005 proxy clicks remain distinct from server-resolved metric evidence and cannot be client-forged."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("Proxy API tenant", tenant_id="proxy-api-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Proxy API project",
        vertical="platform",
        classification="internal",
        project_id="proxy-api-project",
        actor_id="bootstrap",
    )
    client = TestClient(create_app(context=context, service_name="all"))
    headers = _headers(tenant_id, project_id)
    scene = context.scene.create_scene(tenant_id, project_id, name="Proxy API room", actor_id="spatial-api-admin")
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="World",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="controlled proxy API origin",
        source="synthetic_fixture",
        actor_id="spatial-api-admin",
        frame_id="frame-world",
    )
    metric_asset_id = _ingest(client, tenant_id, project_id, "metric.glb", b"metric evidence bytes")
    proxy_asset_id = _ingest(client, tenant_id, project_id, "proxy.glb", b"disposable proxy bytes")
    for provider_id in ("proxy-api-metric", "proxy-api-interaction"):
        context.providers.register(
            {
                "provider_id": provider_id,
                "version": "1.0.0",
                "source_url": f"local://{provider_id}",
                "source_revision": "deterministic-fixture",
                "license_id": "Apache-2.0",
                "approval_state": "approved",
                "allowed_classifications": ["internal"],
                "allowed_purposes": ["construction"],
                "allowed_regions": ["local"],
            },
            actor_id="spatial-api-admin",
        )
    metric_id = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=metric_asset_id,
        kind=RepresentationKind.METRIC,
        provider_id="proxy-api-metric",
        coordinate_frame_id="frame-world",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement", "render"],
        prohibited_uses=[],
        quality={"rmse_m": 0.004},
        provenance={"source_ids": [metric_asset_id]},
        support_map={},
        actor_id="spatial-api-admin",
    )
    context.representations.review_quality(
        metric_id,
        reviewer_id="metric-reviewer",
        approved_uses=["measurement", "render"],
        metrics={"rmse_m": 0.004},
        passed=True,
    )
    context.publisher.publish(metric_id, commit_id=scene["commit_id"], role="measurement", publisher_id="publisher")
    proxy_id = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=proxy_asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id="proxy-api-interaction",
        coordinate_frame_id="frame-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking", "collision"],
        prohibited_uses=["verified_measurement"],
        quality={"collision_coverage": 1.0},
        provenance={"source_ids": [metric_id]},
        support_map={
            "metric_representation_id": metric_id,
            "max_reprojection_error_m": 0.008,
            "anchors": [],
        },
        actor_id="spatial-api-admin",
    )
    context.representations.review_quality(
        proxy_id,
        reviewer_id="proxy-reviewer",
        approved_uses=["picking", "collision"],
        metrics={"raycast_p95_ms": 2.0},
        passed=True,
    )
    context.publisher.publish(proxy_id, commit_id=scene["commit_id"], role="picking", publisher_id="publisher")

    resolved = client.post(
        f"/v1/projects/{project_id}/proxy-hits/resolve",
        headers=headers,
        json={"representation_id": proxy_id, "point": [1.0, 1.5, 2.0], "tolerance_m": 0.02},
    )
    assert resolved.status_code == 200, resolved.text
    resolution = resolved.json()
    assert resolution["interaction_hit"]["representation_id"] == proxy_id
    assert resolution["resolved_metric_evidence"]["metric_representation_id"] == metric_id
    assert resolution["resolved_metric_evidence"]["metric_source_asset_ids"] == [metric_asset_id]
    assert resolution["authoritative_measurement_allowed"] is True

    request_body = {
        "measurement_type": "clearance",
        "geometry": {"type": "segment", "start": [1.0, 1.5, 2.0], "end": [1.5, 1.5, 2.0]},
        "value": 0.5,
        "unit": "m",
        "uncertainty": 0.012,
        "source_asset_ids": [metric_asset_id],
        "calibration": {"resolution": "support_map_metric_reprojection"},
        "coordinate_frame_id": "frame-world",
        "originating_representation_id": proxy_id,
        "interaction_hit": resolution["interaction_hit"],
        "source_method": "proxy_click_metric_reresolution",
        "permitted_uses": ["reference", "facility_operations"],
        "proxy_tolerance_m": 0.02,
    }
    measured = client.post(
        f"/v1/projects/{project_id}/scenes/{scene['scene_id']}/measurements",
        headers=headers,
        json=request_body,
    )
    assert measured.status_code == 201, measured.text
    record = measured.json()
    assert record["source_commit_id"] == scene["commit_id"]
    assert record["permitted_uses"] == ["facility_operations", "reference"]
    assert record["interaction_hit"]["world_point"] == [1.0, 1.5, 2.0]
    assert record["resolved_metric_evidence"]["metric_representation_id"] == metric_id
    assert record["resolved_metric_evidence"]["estimated_residual_m"] == 0.008

    forged = client.post(
        f"/v1/projects/{project_id}/scenes/{scene['scene_id']}/measurements",
        headers=headers,
        json={
            **request_body,
            "resolved_metric_evidence": {
                "metric_representation_id": "attacker-controlled",
                "metric_source_asset_ids": [proxy_asset_id],
                "estimated_residual_m": 0.0,
            },
        },
    )
    assert forged.status_code == 422, forged.text
    assert forged.json()["error"]["code"] == "VALUE_INVALID"

    cross_tenant = client.post(
        f"/v1/projects/{project_id}/proxy-hits/resolve",
        headers=_headers("other-tenant", project_id),
        json={"representation_id": proxy_id, "point": [1.0, 1.5, 2.0]},
    )
    assert cross_tenant.status_code == 404


def test_evidence_and_assertion_reads_enforce_server_side_audience_purpose_and_scope(tmp_path: Path) -> None:
    """REQ: ARCIAM-001, DATEVID-004, OPSAUDIT-003, PLTREST-001 evidence inspection is server-authorized and cannot leak across audience, purpose, or tenant scope."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("Evidence read tenant", tenant_id="evidence-read-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Evidence read project",
        vertical="platform",
        classification="internal",
        project_id="evidence-read-project",
        actor_id="bootstrap",
    )
    client = TestClient(create_app(context=context, service_name="all"))
    asset_id = _ingest(client, tenant_id, project_id, "restricted-photo.bin", b"restricted evidence bytes")
    now = datetime.now(UTC)
    evidence = client.post(
        f"/v1/projects/{project_id}/evidence",
        headers=_headers(tenant_id, project_id),
        json={
            "asset_id": asset_id,
            "source_type": "controlled_restricted_fixture",
            "collected_at": now.isoformat(),
            "collected_by": "controlled-collector",
            "device_or_tool": "fixture-camera",
            "location_context": {"region_id": "room-restricted"},
            "relevant_region": {"region_id": "room-restricted"},
            "relevant_time_start": now.isoformat(),
            "relevant_time_end": now.isoformat(),
            "retention_class": "preservation",
            "consent_scope": {
                "allowed_audiences": ["project"],
                "allowed_purposes": ["construction"],
            },
            "access_policy": {
                "allowed_audiences": ["project"],
                "allowed_purposes": ["construction"],
                "allowed_roles": ["viewer", "tenant_admin"],
            },
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_id = evidence.json()["evidence_id"]
    assertion = client.post(
        f"/v1/projects/{project_id}/assertions",
        headers=_headers(tenant_id, project_id),
        json={
            "subject_id": "room-restricted",
            "predicate": "contains_sensitive_fixture",
            "object_value": True,
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.8,
            "evidence_ids": [evidence_id],
            "state": "disputed",
        },
    )
    assert assertion.status_code == 201, assertion.text
    assertion_id = assertion.json()["assertion_id"]

    allowed_headers = {
        "X-SIP-Tenant": tenant_id,
        "X-SIP-Subject": "project-viewer",
        "X-SIP-Projects": project_id,
        "X-SIP-Roles": "viewer",
        "X-SIP-Purposes": "construction",
        "X-SIP-Audience": "project",
        "X-SIP-Spatial-Regions": "room-restricted",
    }
    allowed = client.get(
        f"/v1/projects/{project_id}/evidence/{evidence_id}",
        headers=allowed_headers,
        params={"purpose": "construction"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["evidence_id"] == evidence_id
    allowed_assertion = client.get(
        f"/v1/projects/{project_id}/assertions/{assertion_id}",
        headers=allowed_headers,
        params={"purpose": "construction", "include_evidence": True},
    )
    assert allowed_assertion.status_code == 200, allowed_assertion.text
    assert allowed_assertion.json()["state"] == "disputed"
    with context.database.session() as session:
        assertion_evidence_reads = list(session.scalars(select(AuditEventRow).where(
            AuditEventRow.tenant_id == tenant_id,
            AuditEventRow.project_id == project_id,
            AuditEventRow.actor_id == "project-viewer",
            AuditEventRow.action == "evidence:read",
            AuditEventRow.resource_id == evidence_id,
            AuditEventRow.outcome == "allowed",
        )))
    assert any(
        event.details_json.get("via_assertion_id") == assertion_id
        for event in assertion_evidence_reads
    )

    wrong_audience_headers = {**allowed_headers, "X-SIP-Audience": "family"}
    denied_audience = client.get(
        f"/v1/projects/{project_id}/evidence/{evidence_id}",
        headers=wrong_audience_headers,
        params={"purpose": "construction"},
    )
    assert denied_audience.status_code == 403, denied_audience.text
    assert denied_audience.json()["error"]["code"] == "EVIDENCE_AUDIENCE_DENIED"
    denied_assertion = client.get(
        f"/v1/projects/{project_id}/assertions/{assertion_id}",
        headers=wrong_audience_headers,
        params={"purpose": "construction", "include_evidence": True},
    )
    assert denied_assertion.status_code == 403, denied_assertion.text
    with context.database.session() as session:
        denied_assertion_evidence_reads = list(session.scalars(select(AuditEventRow).where(
            AuditEventRow.tenant_id == tenant_id,
            AuditEventRow.project_id == project_id,
            AuditEventRow.actor_id == "project-viewer",
            AuditEventRow.action == "evidence:read",
            AuditEventRow.resource_id == evidence_id,
            AuditEventRow.outcome == "denied",
        )))
    assert any(
        event.details_json.get("via_assertion_id") == assertion_id
        and event.details_json.get("reason") == "EVIDENCE_AUDIENCE_DENIED"
        for event in denied_assertion_evidence_reads
    )
    denied_list = client.get(
        f"/v1/projects/{project_id}/assertions",
        headers=wrong_audience_headers,
        params={"purpose": "construction"},
    )
    assert denied_list.status_code == 200, denied_list.text
    assert denied_list.json()["items"] == []
    assert denied_list.json()["withheld_count"] is None

    wrong_purpose_headers = {**allowed_headers, "X-SIP-Purposes": "operations"}
    denied_purpose = client.get(
        f"/v1/projects/{project_id}/evidence/{evidence_id}",
        headers=wrong_purpose_headers,
        params={"purpose": "operations"},
    )
    assert denied_purpose.status_code == 403, denied_purpose.text
    assert denied_purpose.json()["error"]["code"] == "EVIDENCE_PURPOSE_DENIED"

    cross_tenant = client.get(
        f"/v1/projects/{project_id}/evidence/{evidence_id}",
        headers={**allowed_headers, "X-SIP-Tenant": "other-tenant"},
        params={"purpose": "construction"},
    )
    assert cross_tenant.status_code == 404, cross_tenant.text


def test_assertion_reads_require_project_authorization_even_without_linked_evidence(tmp_path: Path) -> None:
    """REQ: ARCIAM-001, PLTREST-001 evidence-free assertions cannot bypass project authorization."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("Assertion scope tenant", tenant_id="assertion-scope-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Assertion scope project",
        vertical="platform",
        classification="internal",
        project_id="assertion-scope-project",
        actor_id="bootstrap",
    )
    client = TestClient(create_app(context=context, service_name="all"))
    assertion_id = "legacy-evidence-free-assertion"
    with context.database.session() as session:
        session.add(
            AssertionRow(
                assertion_id=assertion_id,
                tenant_id=tenant_id,
                project_id=project_id,
                subject_id="legacy-evidence-free-subject",
                predicate="legacy_claim",
                object_json="unverified",
                source_class="inferred",
                authority_class="none",
                confidence=0.2,
                evidence_ids_json=[],
                asserted_at=datetime.now(UTC),
                valid_from=None,
                valid_to=None,
                author_id="legacy-import",
                producer_id=None,
                conflicts_with_json=[],
                supersedes_assertion_id=None,
                state="disputed",
                created_by="legacy-import",
            )
        )

    authorized = {
        "X-SIP-Tenant": tenant_id,
        "X-SIP-Subject": "authorized-viewer",
        "X-SIP-Projects": project_id,
        "X-SIP-Roles": "viewer",
        "X-SIP-Audience": "project",
    }
    assert client.get(
        f"/v1/projects/{project_id}/assertions/{assertion_id}", headers=authorized
    ).status_code == 200

    out_of_scope = {**authorized, "X-SIP-Subject": "out-of-scope-viewer", "X-SIP-Projects": "other-project"}
    denied = client.get(f"/v1/projects/{project_id}/assertions/{assertion_id}", headers=out_of_scope)
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "PROJECT_SCOPE_DENIED"
    denied_list = client.get(f"/v1/projects/{project_id}/assertions", headers=out_of_scope)
    assert denied_list.status_code == 403, denied_list.text
    assert denied_list.json()["error"]["code"] == "PROJECT_SCOPE_DENIED"
