from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from tests.progress09_helpers import bootstrap, deployment_headers, profile_args, residency_args


def test_progress09_deployment_api_is_authenticated_scoped_and_generated(tmp_path: Path) -> None:
    """REQ: ARCDEP-001, ARCDEP-002, ARCDEP-003 authenticated deployment APIs preserve profile, residency, feature, and admission boundaries."""
    context, tenant, project = bootstrap(tmp_path, name="p09-api")
    client = TestClient(create_app(context=context, service_name="deployment-control"))
    admin = deployment_headers(tenant, project)
    viewer = deployment_headers(tenant, project, subject="viewer", role="viewer")

    denied = client.post("/v1/deployment/profiles", headers=viewer, json=profile_args())
    assert denied.status_code == 403
    created = client.post("/v1/deployment/profiles", headers=admin, json=profile_args())
    assert created.status_code == 201, created.text
    profile = created.json()
    read = client.get(f"/v1/deployment/profiles/{profile['deployment_profile_id']}", headers=admin)
    assert read.status_code == 200
    feature = client.get(f"/v1/deployment/profiles/{profile['deployment_profile_id']}/features/gpu_reconstruction", headers=admin)
    assert feature.status_code == 200 and feature.json()["requires_cloud_connectivity"] is True

    residency = client.post(f"/v1/projects/{project}/deployment/residency-policies", headers=admin, json=residency_args())
    assert residency.status_code == 201, residency.text
    binding = client.post(
        f"/v1/projects/{project}/deployment/profile", headers=admin,
        json={"deployment_profile_id": profile["deployment_profile_id"], "residency_policy_id": residency.json()["residency_policy_id"], "transfer_policy_id": None, "revision": "1.0.0", "feature_overrides": {}, "cloud_dependencies_acknowledged": True},
    )
    assert binding.status_code == 201, binding.text
    wrong_project = client.post(
        "/v1/projects/not-authorized/deployment/admissions", headers=admin,
        json={"admission_type": "worker_schedule", "deployment_profile_id": profile["deployment_profile_id"], "region": "us-east-1", "request": {"worker_class": "reference-worker"}},
    )
    assert wrong_project.status_code == 403


def test_progress09_api_keeps_production_and_cross_tenant_operations_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSHYB-003, OPSAWS-001, OPSAWS-005 deployment control derives tenant scope from authentication and refuses caller-only production evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p09-api-security")
    other = context.tenancy.create_tenant("other", tenant_id="p09-other", actor_id="bootstrap")
    other_project = context.tenancy.create_project(other, "other", vertical="platform", classification="internal", project_id="p09-other-project", actor_id="bootstrap")
    client = TestClient(create_app(context=context, service_name="deployment-control"))
    admin = deployment_headers(tenant, project)
    profile = client.post("/v1/deployment/profiles", headers=admin, json=profile_args(name="api-secure", digest_character="7")).json()
    cross_tenant = client.post(
        f"/v1/tenants/{other}/deployment/edge-nodes", headers=admin,
        json={"project_id": other_project, "deployment_profile_id": profile["deployment_profile_id"], "node_identity": "edge-cross", "identity_public_key_hash": "1" * 64, "software_manifest": {"image": "ghcr.io/spatial-intelligence-platform/edge:v1@sha256:" + "2" * 64, "source_commit": "3" * 40, "release": "1.0.0"}, "software_signature": "A" * 44, "signing_key_id": "key", "disk_encryption": {"enabled": True, "attested": True, "attestation_hash": "4" * 64}, "region": "us-east-1", "capabilities": {}},
    )
    assert cross_tenant.status_code == 403
    production = client.post(
        f"/v1/deployment/profiles/{profile['deployment_profile_id']}/production-admission", headers=admin,
        json={"aws_environment_id": None, "evidence": {"executed_compose": True}},
    )
    assert production.status_code == 403
    assert production.json()["error"]["code"] == "DEPLOYMENT_PRODUCTION_EVIDENCE_INCOMPLETE"
