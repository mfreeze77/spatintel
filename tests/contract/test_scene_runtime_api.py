from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings


def _headers(tenant: str, project: str, subject: str, roles: str = "tenant_admin") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": "construction,operations",
        "X-SIP-Audience": "project",
    }


def test_scene_runtime_openapi_and_authenticated_viewer_session_contract(tmp_path: Path) -> None:
    """REQ: PLTVIEW-001, RECCHANG-001 generated APIs expose policy-bound viewer and temporal review contracts."""
    context = PlatformContext.create(temporary_settings(tmp_path / "runtime"))
    tenant = context.tenancy.create_tenant("Runtime API", tenant_id="runtime-api-tenant", actor_id="bootstrap")
    project = context.tenancy.create_project(tenant, "Runtime API", vertical="platform", classification="internal", project_id="runtime-api-project", actor_id="bootstrap")
    client = TestClient(create_app(context=context, service_name="scene-service"))
    headers = _headers(tenant, project, "runtime-admin")

    scene = client.post(f"/v1/projects/{project}/scenes", headers=headers, json={"name": "Runtime scene"})
    assert scene.status_code == 201, scene.text
    scene_id = scene.json()["scene_id"]
    commit_id = scene.json()["commit_id"]

    created = client.post(
        f"/v1/projects/{project}/scenes/{scene_id}/viewer-sessions",
        headers=headers,
        json={
            "purpose": "construction",
            "audience": "project",
            "scene_commit_ids": [commit_id],
            "device_profile": "browser-independent-reference",
            "intended_uses": ["review"],
            "camera": {"position": [0, 1.6, 2], "target": [0, 1, 0]},
            "navigation_mode": "orbit",
            "layers": [{"role": "metric", "binding_ids": [], "visible": True, "interactive": False, "authority_label": "metric evidence"}],
            "redaction": {},
            "accessibility": {"reduced_motion": True, "high_contrast": True, "captions": True},
            "idempotency_key": "api-viewer-session-1",
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]
    fetched = client.get(
        f"/v1/projects/{project}/scenes/{scene_id}/viewer-sessions/{session_id}",
        headers=headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["session_hash"] == created.json()["session_hash"]

    denied = client.get(
        f"/v1/projects/{project}/scenes/{scene_id}/viewer-sessions/{session_id}",
        headers=_headers(tenant, project, "other-viewer", roles="viewer"),
    )
    assert denied.status_code == 403

    unauthenticated = client.get(f"/v1/projects/{project}/scenes/{scene_id}/viewer-sessions/{session_id}")
    assert unauthenticated.status_code == 401

    schema = client.get("/openapi.json").json()
    required = {
        f"/v1/projects/{{project_id}}/scenes/{{scene_id}}/viewer-sessions",
        f"/v1/projects/{{project_id}}/scenes/{{scene_id}}/viewer-sessions/{{session_id}}/replays",
        f"/v1/projects/{{project_id}}/scenes/{{scene_id}}/temporal-comparisons",
        f"/v1/projects/{{project_id}}/scenes/{{scene_id}}/temporal-comparisons/{{comparison_id}}/candidates/{{candidate_id}}/reviews",
        f"/v1/projects/{{project_id}}/scenes/{{scene_id}}/temporal-comparisons/{{comparison_id}}/apply",
        f"/v1/projects/{{project_id}}/change-benchmarks",
    }
    assert required <= set(schema["paths"])
