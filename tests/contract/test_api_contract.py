from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings


def _headers(tenant: str, project: str, *, roles: str = "tenant_admin", subject: str = "api-admin") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": "construction,memorialization,operations",
        "X-SIP-Audience": "private",
    }


def _client(tmp_path: Path) -> tuple[TestClient, str, str]:
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("API tenant", tenant_id="api-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "API project",
        vertical="platform",
        classification="internal",
        project_id="api-project",
        actor_id="bootstrap",
    )
    return TestClient(create_app(context=context, service_name="all")), tenant_id, project_id


def test_api_openapi_is_stable_unique_and_uses_server_side_auth(tmp_path: Path) -> None:
    """REQ: PLTAPI-001, PLTAPI-005 OpenAPI operations are unique and unauthenticated/error behavior is stable and non-disclosing."""
    client, tenant_id, project_id = _client(tmp_path)
    schema = client.get("/openapi.json").json()
    assert schema["openapi"].startswith("3.1")
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids)) == 143
    assert client.get(f"/v1/projects/{project_id}/assets/missing").status_code == 401
    response = client.get(
        f"/v1/projects/{project_id}/assets/missing",
        headers=_headers(tenant_id, project_id, roles="viewer"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_api_asset_operation_scene_round_trip(tmp_path: Path) -> None:
    """REQ: PLTREST-001, PLTREST-005 typed REST paths create/read assets, operations, scenes, and entities with durable status."""
    client, tenant_id, project_id = _client(tmp_path)
    headers = _headers(tenant_id, project_id)
    payload = b"authoritative immutable evidence"
    ingest = client.post(
        f"/v1/projects/{project_id}/assets",
        headers=headers,
        json={
            "content_base64": base64.b64encode(payload).decode(),
            "media_type": "application/octet-stream",
            "original_name": "evidence.bin",
            "classification": "internal",
            "retention_class": "preservation",
            "source_class": "direct_capture",
            "authority_class": "evidence",
            "provenance": {"source_ids": ["api-fixture"]},
        },
    )
    assert ingest.status_code == 201, ingest.text
    asset_id = ingest.json()["asset_id"]
    read = client.get(f"/v1/projects/{project_id}/assets/{asset_id}/content", headers=headers)
    assert read.status_code == 200
    assert read.content == payload

    operation = client.post(
        f"/v1/projects/{project_id}/operations",
        headers=headers,
        json={"operation_type": "capture.normalize", "idempotency_key": "api-op-1", "input_manifest": {"asset_id": asset_id}},
    )
    assert operation.status_code == 202, operation.text
    operation_id = operation.json()["operation_id"]
    assert client.get(f"/v1/operations/{operation_id}", headers=headers).json()["state"] == "pending"

    scene = client.post(f"/v1/projects/{project_id}/scenes", headers=headers, json={"name": "API scene"})
    assert scene.status_code == 201, scene.text
    scene_id = scene.json()["scene_id"]
    entity = client.post(
        f"/v1/projects/{project_id}/scenes/{scene_id}/entities",
        headers=headers,
        json={
            "entity_type": "room",
            "name": "Room 101",
            "attributes": {"floor": 1},
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.9,
            "provenance": {"source_ids": [asset_id]},
            "stable_support": {"coordinate_frame_id": "world"},
        },
    )
    assert entity.status_code == 201, entity.text


def test_cross_tenant_api_scope_is_denied_without_disclosure(tmp_path: Path) -> None:
    """REQ: ARCIAM-001 cross-tenant API object access is denied without revealing existence."""
    client, tenant_id, project_id = _client(tmp_path)
    response = client.get(
        f"/v1/projects/{project_id}/assets/nonexistent",
        headers=_headers("other-tenant", project_id, roles="tenant_admin"),
    )
    # Cross-tenant object identifiers are deliberately non-disclosing.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
