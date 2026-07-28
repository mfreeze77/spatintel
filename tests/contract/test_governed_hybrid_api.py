from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from sip.canonical import canonical_sha256
from sip.context import PlatformContext, temporary_settings
from sip.security import SignedTokenCodec


TENANT = "hybrid-api-tenant"
PROJECT = "hybrid-api-project"
PURPOSE = "construction_reference"
FRAME = "hybrid-api-frame"


def _headers(subject: str, *, roles: str = "tenant_admin", tenant: str = TENANT, project: str = PROJECT) -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": PURPOSE,
        "X-SIP-Audience": "project",
    }


def _license(component: str) -> dict[str, str]:
    return {
        "component": component,
        "title": f"Synthetic {component} license",
        "license_id": "Apache-2.0" if component == "code" else "commercial-output-rights",
        "source_url": f"local://licenses/{component}",
        "document_sha256": canonical_sha256({"license": component}),
        "review_state": "verified",
    }


def _descriptor() -> dict[str, object]:
    reviewed = datetime.now(UTC) - timedelta(days=1)
    return {
        "schema": "sip.provider-capability/v1.1",
        "schema_version": "1.1.0",
        "provider_id": "api-local-proxy",
        "provider_version": "1.0.0",
        "provider_class": "local_open_source",
        "source_url": "local://providers/api-local-proxy",
        "source_revision": "fixture-1",
        "executable_digest": canonical_sha256({"provider": "api-local-proxy"}),
        "execution_modes": ["isolated_container"],
        "deployment_modes": ["local_only"],
        "input_roles": ["metric_mesh"],
        "output_roles": ["interaction_proxy"],
        "capabilities": ["mesh_to_surface", "collision_proxy"],
        "supported_formats": {"input": ["model/gltf-binary"], "output": ["model/gltf-binary"]},
        "coordinate_contract": {
            "units": "meter",
            "handedness": "right",
            "up_axes": ["y"],
            "preserves_input_frame": True,
            "scale_behavior": "preserve",
            "requires_explicit_inverse_for_normalization": True,
        },
        "reproducibility": {"deterministic": True, "seed_policy": "fixed"},
        "security": {
            "network_required": False,
            "approved_egress_domains": [],
            "writes_outside_job_workspace": False,
            "supports_read_only_inputs": True,
            "supports_write_only_staging": True,
            "transient_cleanup": "verified",
            "external_processing": False,
        },
        "recovery": {
            "cancellation_bound_seconds": 30,
            "checkpoint_supported": True,
            "resume_supported": True,
            "cleanup_supported": True,
            "checkpoint_schema_version": "1.0.0",
            "objective_progress_units": ["frames", "tiles"],
        },
        "data_governance": {
            "source_data_use": "requested_operation_only",
            "training_use": "prohibited",
            "public_demonstration": "prohibited",
            "unrelated_retention": "prohibited",
            "processing_regions": ["local"],
            "subprocessor_disclosure_complete": True,
            "deletion_verification": "platform_verified",
            "data_use_terms_sha256": canonical_sha256({"provider": "api-local-proxy", "data-use": "requested-only"}),
        },
        "license_manifest_id": "license-api-local-proxy",
        "license_evidence": [_license("code"), _license("dependencies"), _license("output")],
        "model_manifest_ids": [],
        "dependency_inventory": [{"name": "synthetic", "version": "1.0.0", "sha256": canonical_sha256("synthetic")}],
        "benchmark_profile_ids": ["hybrid-cpu-reference-v1"],
        "allowed_classifications": ["internal"],
        "allowed_purposes": [PURPOSE],
        "allowed_regions": ["local"],
        "prohibited_purposes": ["life_safety_certification"],
        "output_rights": "commercial_derivatives_allowed",
        "retention_days": 0,
        "approval_state": "approved",
        "reviewed_at": reviewed.isoformat(),
        "review_due_at": (reviewed + timedelta(days=365)).isoformat(),
        "expires_at": (reviewed + timedelta(days=365)).isoformat(),
        "signed_by": "provider-governance",
    }


def _ingest(client: TestClient, *, subject: str, name: str, data: bytes, source_class: str, authority_class: str) -> dict[str, object]:
    response = client.post(
        f"/v1/projects/{PROJECT}/assets",
        headers=_headers(subject),
        json={
            "content_base64": base64.b64encode(data).decode(),
            "media_type": "model/gltf-binary",
            "original_name": name,
            "classification": "internal",
            "retention_class": "test",
            "source_class": source_class,
            "authority_class": authority_class,
            "provenance": {"source_ids": [f"fixture:{name}"]},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _profile(client: TestClient, intended_use: str, *, subject: str) -> None:
    response = client.post(
        f"/v1/projects/{PROJECT}/hybrid/interaction-profiles",
        headers=_headers(subject),
        json={
            "profile_id": f"api-profile-{intended_use}",
            "profile_type": intended_use,
            "version": "1.0.0",
            "actor": {"shape": "capsule", "radius_m": 0.3, "height_m": 1.8},
            "intended_uses": [intended_use],
            "limits": {"maximum_error_m": 0.02},
            "behavior": {"fallback": "disable_use"},
            "validation": {"method": "deterministic-fixture", "passed": True, "validated_safety_claims": []},
            "safety_claims": [],
            "validator_id": f"api-profile-validator-{intended_use}",
            "validator_manifest_hash": canonical_sha256({"profile-validator": intended_use}),
            "validation_evidence_hash": canonical_sha256({"profile-evidence": intended_use}),
            "validated_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 201, response.text


def _validate(client: TestClient, conversion_id: str, intended_use: str, *, subject: str) -> dict[str, object]:
    response = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{conversion_id}/validations",
        headers=_headers(subject),
        json={
            "intended_use": intended_use,
            "profile_id": f"api-profile-{intended_use}",
            "profile_version": "1.0.0",
            "validator_manifest_hash": canonical_sha256({"validator": subject}),
            "metrics": {"error_m": 0.01},
            "thresholds": {"error_m": {"max": 0.02}},
            "coverage": {"passed": True, "fraction": 1.0},
            "topology": {"passed": True, "watertight_required": False},
            "coordinate_validation": {"passed": True, "frame_id": FRAME},
            "behavior_validation": {"passed": True, "use": intended_use},
            "limitations": ["non-authoritative interaction proxy"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_governed_hybrid_api_admits_quarantines_validates_publishes_and_issues_binding_only_view(tmp_path: Path) -> None:
    """REQ: ARCHHYB-003, HYBAPI-001, HYBAPI-002, HYBAPI-003, HYBAPI-004, HYBAPI-005, HYBAPI-006 governed provider execution remains least-privilege and quarantined until independent use-specific review and atomic publication."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    context.tenancy.create_tenant("Hybrid API tenant", tenant_id=TENANT, actor_id="bootstrap")
    context.tenancy.create_project(
        TENANT,
        "Hybrid API project",
        vertical="platform",
        classification="internal",
        project_id=PROJECT,
        actor_id="bootstrap",
    )
    context.policy.create_identity(TENANT, "viewer", "Hybrid viewer")
    context.policy.bind_role(
        binding_id="hybrid-viewer-binding",
        tenant_id=TENANT,
        project_id=PROJECT,
        identity_id="viewer",
        role="viewer",
        purposes=[PURPOSE],
        spatial_restrictions=[],
    )
    client = TestClient(create_app(context=context, service_name="all"))

    provider = client.post("/v1/providers/capabilities", headers=_headers("provider-admin"), json=_descriptor())
    assert provider.status_code == 201, provider.text
    assert provider.json()["descriptor_complete"] is True

    now = datetime.now(UTC)
    promotion = client.post(
        "/v1/providers/api-local-proxy/promotions",
        headers=_headers("provider-admin"),
        json={
            "state": "active",
            "data_classifications": ["internal"],
            "scene_classes": ["building"],
            "output_roles": ["interaction_proxy"],
            "intended_uses": ["picking", "collision"],
            "execution_zones": ["local-cpu"],
            "hardware_profiles": ["cpu-reference"],
            "benchmark_evidence_hash": canonical_sha256({"benchmark": "api-local-proxy"}),
            "policy_snapshot_hash": canonical_sha256({"policy": "api-local-proxy"}),
            "valid_from": (now - timedelta(minutes=1)).isoformat(),
            "valid_until": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert promotion.status_code == 201, promotion.text
    assert promotion.json()["provider_manifest_hash"] == provider.json()["manifest_hash"]

    scene = client.post(f"/v1/projects/{PROJECT}/scenes", headers=_headers("requester"), json={"name": "Hybrid room"})
    assert scene.status_code == 201, scene.text
    scene_data = scene.json()
    frame = client.post(
        f"/v1/projects/{PROJECT}/coordinate-frames",
        headers=_headers("requester"),
        json={
            "frame_id": FRAME,
            "name": "Hybrid world",
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
    assert frame.status_code == 201, frame.text
    source = _ingest(
        client,
        subject="requester",
        name="metric-source.glb",
        data=b"deterministic metric source" * 8,
        source_class="direct_capture",
        authority_class="evidence",
    )

    request_body = {
        "schema": "sip.spatial-conversion.request/1.1",
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "scene_id": scene_data["scene_id"],
        "scene_revision_id": scene_data["commit_id"],
        "purpose": PURPOSE,
        "intended_uses": ["picking", "collision"],
        "output_roles": ["interaction_proxy"],
        "source_assets": [{
            "asset_id": source["asset_id"],
            "role": "metric_mesh",
            "sha256": source["sha256"],
            "coordinate_frame_id": FRAME,
        }],
        "reference_assets": [],
        "constraints": {"maximum_output_multiplier": 4.0, "estimate_profile": "contract-v1"},
        "policy_context": {
            "scene_class": "building",
            "execution_zone": "local-cpu",
            "hardware_profile": "cpu-reference",
            "region": "local",
            "deployment_mode": "local_only",
            "commercial": True,
            "audience": "project",
            "allowed_audiences": ["project"],
            "allow_external_transfer": False,
        },
        "provider_selector": {
            "required_capabilities": ["mesh_to_surface"],
            "forbidden_capabilities": ["unbounded_external_upload"],
        },
        "requested_by": "requester",
        "idempotency_key": "hybrid-api-conversion-1",
    }
    admitted = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions",
        headers=_headers("requester"),
        json=request_body,
    )
    assert admitted.status_code == 201, admitted.text
    admitted_data = admitted.json()
    conversion_id = admitted_data["conversion_id"]
    worker_token = admitted_data["worker_token"]
    assert admitted_data["state"] == "admitted"
    assert "credential_claims" not in admitted_data
    worker_claims = SignedTokenCodec(context.settings.signing_key).decode(worker_token)
    assert worker_claims["publication_permission"] is False
    assert worker_claims["permissions"] == ["asset:read_exact", "quarantine:write", "operation:checkpoint", "operation:complete"]

    replay = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions",
        headers=_headers("requester"),
        json=request_body,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["conversion_id"] == conversion_id
    assert replay.json()["worker_token"] is None

    worker_headers = _headers("sip-provider:api-local-proxy:worker", roles="service_worker")
    forbidden_evidence_mutation = client.post(
        f"/v1/projects/{PROJECT}/evidence",
        headers={**worker_headers, "X-SIP-Worker-Token": worker_token},
        json={
            "asset_id": source["asset_id"],
            "source_type": "worker-forbidden-mutation",
            "collected_at": now.isoformat(),
            "collected_by": "sip-provider:api-local-proxy:worker",
            "device_or_tool": "provider-worker",
            "location_context": {"frame_id": FRAME},
            "relevant_region": {"type": "scene", "scene_id": scene_data["scene_id"]},
            "relevant_time_start": now.isoformat(),
            "relevant_time_end": now.isoformat(),
            "retention_class": "test",
            "consent_scope": {"purpose": PURPOSE},
            "access_policy": {"audience": "project"},
            "policy": {"authority_mutation": False},
        },
    )
    assert forbidden_evidence_mutation.status_code == 403, forbidden_evidence_mutation.text
    # The worker is authenticated but its service role is intentionally not authorized
    # to mutate evidence, so retain the policy engine's specific stable denial code.
    assert forbidden_evidence_mutation.json()["error"]["code"] == "ACTION_DENIED"

    progress = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{conversion_id}/progress",
        headers={**worker_headers, "X-SIP-Worker-Token": worker_token},
        json={
            "conversion_id": conversion_id,
            "sequence": 1,
            "stage": "proxy_generation",
            "completed_work_units": 8,
            "total_work_units": 8,
            "work_unit_name": "frames",
            "resource_use": {"cpu_seconds": 0.5},
            "warnings": [],
            "last_durable_checkpoint_hash": canonical_sha256({"checkpoint": 1}),
            "estimated_output_bytes": 512,
        },
    )
    assert progress.status_code == 200, progress.text

    renewed = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{conversion_id}/worker-lease:renew",
        headers={**worker_headers, "X-SIP-Worker-Token": worker_token},
        json={"lease_ttl_seconds": 45},
    )
    assert renewed.status_code == 200, renewed.text
    renewed_data = renewed.json()
    assert renewed_data["credential_generation"] == 2
    assert renewed_data["worker_lease_generation"] == 2
    old_token_replay = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{conversion_id}/progress",
        headers={**worker_headers, "X-SIP-Worker-Token": worker_token},
        json={
            "conversion_id": conversion_id,
            "sequence": 2,
            "stage": "superseded-token",
            "completed_work_units": 8,
            "total_work_units": 8,
            "work_unit_name": "frames",
            "resource_use": {},
            "warnings": [],
            "last_durable_checkpoint_hash": canonical_sha256({"checkpoint": "superseded"}),
            "estimated_output_bytes": 512,
        },
    )
    assert old_token_replay.status_code == 401, old_token_replay.text
    assert old_token_replay.json()["error"]["code"] in {
        "HYB_WORKER_CREDENTIAL_SUPERSEDED",
        "HYB_WORKER_TOKEN_SUPERSEDED",
    }
    worker_token = renewed_data["worker_token"]

    output = _ingest(
        client,
        subject="worker-output",
        name="interaction-proxy.glb",
        data=b"disposable interaction proxy" * 4,
        source_class="generated",
        authority_class="derived_non_authoritative",
    )
    completed = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{conversion_id}/candidate",
        headers={**worker_headers, "X-SIP-Worker-Token": worker_token},
        json={
            "output_asset_id": output["asset_id"],
            "output_asset_sha256": output["sha256"],
            "output_role": "interaction_proxy",
            "kind": "interaction",
            "coordinate_frame_id": FRAME,
            "source_class": "generated",
            "authority_class": "derived_non_authoritative",
            "lossy": True,
            "intended_uses": ["picking", "collision"],
            "prohibited_uses": ["verified_measurement", "survey_grade"],
            "quality": {"provider_claim": "candidate_only"},
            "support_map": {"stable_semantic_ids": True},
            "worker_receipt_hash": canonical_sha256({"worker": conversion_id}),
            "candidate_core_hash": canonical_sha256({"candidate": conversion_id}),
            "format_metadata": {"media_type": "model/gltf-binary"},
            "limitations": ["disposable", "non-authoritative"],
            "information_losses": ["surface simplification"],
        },
    )
    assert completed.status_code == 201, completed.text
    completed_data = completed.json()
    representation_id = completed_data["representation_id"]
    assert completed_data["state"] == "quarantined"

    premature = client.post(
        f"/v1/representations/{representation_id}/publish",
        headers=_headers("publisher"),
        json={
            "commit_id": scene_data["commit_id"],
            "role": "interaction_proxy",
            "intended_uses": ["picking", "collision"],
        },
    )
    assert premature.status_code == 409, premature.text

    _profile(client, "picking", subject="review-admin")
    _profile(client, "collision", subject="review-admin")
    assert _validate(client, conversion_id, "picking", subject="independent-picking")["passed"] is True
    assert _validate(client, conversion_id, "collision", subject="independent-collision")["passed"] is True

    published = client.post(
        f"/v1/representations/{representation_id}/publish",
        headers=_headers("publisher"),
        json={
            "commit_id": scene_data["commit_id"],
            "role": "interaction_proxy",
            "intended_uses": ["picking", "collision"],
        },
    )
    assert published.status_code == 200, published.text
    binding_id = published.json()["binding_id"]

    view = client.post(
        f"/v1/projects/{PROJECT}/scenes/{scene_data['scene_id']}/hybrid-view",
        headers=_headers("viewer", roles="viewer"),
        json={
            "scene_revision_id": scene_data["commit_id"],
            "purpose": PURPOSE,
            "audience": "project",
            "device_profile": "web-reference",
            "time_context": {"mode": "commit"},
            "intended_uses": ["picking", "collision"],
            "spatial_region_ids": [],
            "ttl_seconds": 300,
        },
    )
    assert view.status_code == 201, view.text
    view_data = view.json()
    assert binding_id in view_data["manifest"]["bindings"]["interaction_proxy"]
    serialized = str(view_data["manifest"])
    assert output["asset_id"] not in serialized
    assert "storage_key" not in serialized
    verified = context.hybrid.verify_view_token(view_data["token"], principal_id="viewer", purpose=PURPOSE)
    assert verified["view_id"] == view_data["manifest"]["view_id"]

    failure_request = {**request_body, "idempotency_key": "hybrid-api-conversion-failure"}
    failure_admission = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions",
        headers=_headers("requester"),
        json=failure_request,
    )
    assert failure_admission.status_code == 201, failure_admission.text
    failure_data = failure_admission.json()
    cleanup_hash = canonical_sha256({"cleanup": failure_data["conversion_id"], "verified": True})
    failed = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{failure_data['conversion_id']}/failure",
        headers={**worker_headers, "X-SIP-Worker-Token": failure_data["worker_token"]},
        json={
            "error_code": "PROVIDER_OOM",
            "retryable": True,
            "cleanup_receipt_hash": cleanup_hash,
            "cleanup_verified": True,
            "last_durable_checkpoint_hash": canonical_sha256({"checkpoint": "before-oom"}),
            "resource_use": {"peak_memory_bytes": 4096},
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["state"] == "failed_retryable"
    persisted_failure = client.get(
        f"/v1/projects/{PROJECT}/hybrid/conversions/{failure_data['conversion_id']}",
        headers=_headers("requester"),
    )
    assert persisted_failure.status_code == 200, persisted_failure.text
    assert persisted_failure.json()["failure_hash"] == failed.json()["failure_hash"]
    assert persisted_failure.json()["cleanup_receipt_hash"] == cleanup_hash


def test_hybrid_api_rejects_body_scope_mismatch_before_admission(tmp_path: Path) -> None:
    """REQ: ARCIAM-001 client-supplied tenant/project scope cannot override authenticated route scope."""
    context = PlatformContext.create(temporary_settings(tmp_path))
    context.tenancy.create_tenant("Hybrid API tenant", tenant_id=TENANT, actor_id="bootstrap")
    context.tenancy.create_project(
        TENANT,
        "Hybrid API project",
        vertical="platform",
        classification="internal",
        project_id=PROJECT,
        actor_id="bootstrap",
    )
    client = TestClient(create_app(context=context, service_name="representation-api"))
    response = client.post(
        f"/v1/projects/{PROJECT}/hybrid/conversions",
        headers=_headers("requester"),
        json={
            "schema": "sip.spatial-conversion.request/1.1",
            "tenant_id": "another-tenant",
            "project_id": PROJECT,
            "scene_id": "scene-x",
            "scene_revision_id": "commit-x",
            "purpose": PURPOSE,
            "intended_uses": ["picking"],
            "output_roles": ["interaction_proxy"],
            "source_assets": [{"asset_id": "asset-x", "role": "metric_mesh", "sha256": "a" * 64, "coordinate_frame_id": "frame-x"}],
            "policy_context": {"scene_class": "building"},
            "provider_selector": {"required_capabilities": ["mesh_to_surface"]},
            "requested_by": "requester",
            "idempotency_key": "scope-mismatch",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "HYB_API_SCOPE_MISMATCH"


def test_hybrid_service_manifests_isolate_provider_control_publication_and_runtime_boundaries() -> None:
    """REQ: ARCHHYB-001, ARCHHYB-002 hybrid control, provider registry, validation/runtime, and sole publisher boundaries remain logically isolated."""
    root = Path(__file__).resolve().parents[2]
    manifests = {
        name: json.loads((root / "services" / name / "service.json").read_text())
        for name in ("provider-registry", "representation-api", "representation-publisher")
    }
    assert all(item["logical_boundary"] is True for item in manifests.values())
    assert {item["service_name"] for item in manifests.values()} == set(manifests)

    operations = {
        name: {(item["method"], item["path"]) for item in manifest["operations"]}
        for name, manifest in manifests.items()
    }
    publish = ("POST", "/v1/representations/{representation_id}/publish")
    assert publish in operations["representation-publisher"]
    assert publish not in operations["provider-registry"]
    assert publish not in operations["representation-api"]
    assert any(path == "/v1/providers/capabilities" for _, path in operations["provider-registry"])
    assert all(not path.startswith("/v1/providers") for _, path in operations["representation-api"])
    assert any(path.endswith("/candidate") for _, path in operations["representation-api"])
    assert any(path.endswith("/validations") for _, path in operations["representation-api"])
    assert any(path.endswith("/hybrid-view") for _, path in operations["representation-api"])

    publisher_non_health = {item for item in operations["representation-publisher"] if not item[1].startswith("/health/")}
    assert publisher_non_health == {publish}
