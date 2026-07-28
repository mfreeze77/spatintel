from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings


def _headers(
    tenant: str,
    project: str,
    *,
    roles: str = "viewer",
    subject: str = "viewer-a",
    audience: str = "private",
) -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": "construction,memorialization,operations",
        "X-SIP-Audience": audience,
    }


@pytest.fixture
def api_fixture(tmp_path: Path):
    context = PlatformContext.create(temporary_settings(tmp_path))
    tenant_id = context.tenancy.create_tenant("Search tenant", tenant_id="search-tenant", actor_id="bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Search project",
        vertical="platform",
        classification="internal",
        project_id="search-project",
        actor_id="bootstrap",
    )
    with TestClient(create_app(context=context, service_name="all")) as client:
        yield client, context, tenant_id, project_id


def test_public_query_contract_excludes_authorization_scope(api_fixture) -> None:
    """REQ: PLTSQL-001, PLTSQL-002 the public AST is bounded and authorization scope remains server controlled."""
    client, _, tenant_id, project_id = api_fixture
    schema = client.get("/openapi.json").json()
    properties = schema["components"]["schemas"]["SearchQuery"]["properties"]
    assert "tenant_id" not in properties
    assert "project_id" not in properties
    assert "allowed_audiences" not in properties

    response = client.post(
        f"/v1/projects/{project_id}/search",
        headers=_headers(tenant_id, project_id),
        json={"full_text": "panel", "tenant_id": "attacker", "allowed_audiences": ["private"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALUE_INVALID"


def test_api_search_filters_before_counts_snippets_and_vector_metadata(api_fixture) -> None:
    """REQ: DATSEARC-001, DATSEARC-002 unauthorized rows never influence counts, snippets, or ranking metadata."""
    client, _, tenant_id, project_id = api_fixture
    admin = _headers(tenant_id, project_id, roles="tenant_admin", subject="admin")
    viewer = _headers(tenant_id, project_id, roles="viewer", subject="viewer-a")

    visible = client.post(
        f"/v1/projects/{project_id}/search/documents",
        headers=admin,
        json={
            "text": "Fire alarm panel observed in electrical room",
            "entity_id": "entity-visible",
            "entity_type": "fire_alarm_panel",
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.9,
            "classification": "internal",
            "policy": {"audience": "private", "allowed_subject_ids": ["viewer-a"]},
            "embedding": [1.0, 0.0],
            "embedding_model_manifest_id": "approved-embedding-v1",
            "embedding_source_region": {"asset_id": "asset-visible", "region_id": "page-1"},
            "source_sequence": 1,
            "index_sequence": 1,
        },
    )
    hidden = client.post(
        f"/v1/projects/{project_id}/search/documents",
        headers=admin,
        json={
            "text": "Fire alarm panel restricted security detail",
            "entity_id": "entity-hidden",
            "entity_type": "fire_alarm_panel",
            "source_class": "observed",
            "authority_class": "evidence",
            "confidence": 0.99,
            "classification": "restricted",
            "policy": {"audience": "private", "allowed_subject_ids": ["different-user"]},
            "embedding": [1.0, 0.0],
            "embedding_model_manifest_id": "approved-embedding-v1",
            "embedding_source_region": {"asset_id": "asset-hidden", "region_id": "page-2"},
            "source_sequence": 1,
            "index_sequence": 1,
        },
    )
    assert visible.status_code == 201, visible.text
    assert hidden.status_code == 201, hidden.text

    result = client.post(
        f"/v1/projects/{project_id}/search",
        headers=viewer,
        json={
            "full_text": "fire alarm panel",
            "embedding": [1.0, 0.0],
            "embedding_model_manifest_id": "approved-embedding-v1",
            "include_snippets": True,
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["authorized_count"] == body["authorized_match_count"] == 1
    assert [item["entity_id"] for item in body["items"]] == ["entity-visible"]
    assert "restricted security detail" not in str(body)
    assert body["items"][0]["embedding_provenance"]["embedding_returned"] is False
    assert body["ranking"]["permission_filters_applied_before_ranking"] is True


def test_agent_api_is_grounded_and_refuses_life_safety_control(api_fixture) -> None:
    """REQ: PLTAGENT-001, PLTAGENT-002 agents expose constrained tools and refuse life-safety control authority."""
    client, _, tenant_id, project_id = api_fixture
    headers = _headers(tenant_id, project_id)

    tools = client.get(f"/v1/projects/{project_id}/agent-tools", headers=headers)
    assert tools.status_code == 200, tools.text
    names = {item["name"] for item in tools.json()["items"]}
    assert names == {"measure_metric_distance", "propose_annotation", "search_evidence"}
    for item in tools.json()["items"]:
        assert "publish_scene" in item["prohibited_actions"]
        assert "life_safety_control" in item["prohibited_actions"]

    refused = client.post(
        f"/v1/projects/{project_id}/agent-requests:check",
        headers=headers,
        json={"request_kind": "life_safety_control"},
    )
    assert refused.status_code == 200, refused.text
    refusal = refused.json()
    assert refusal["refused"] is True
    assert refusal["refusal_code"] == "AGENT_LIFE_SAFETY_CONTROL_DENIED"
    assert refusal["generated_content"] is True
    assert refusal["persistent_label"] == "AI-generated; verify against cited evidence"
    assert refusal["claims"][0]["claim_type"] == "unknown"
    assert refusal["claims"][0]["evidence_ids"] == []

    ungrounded = client.post(
        f"/v1/projects/{project_id}/agent-answers:validate",
        headers=headers,
        json={"claims": [{"text": "The panel passed inspection.", "claim_type": "fact"}]},
    )
    assert ungrounded.status_code == 400
    assert ungrounded.json()["error"]["code"] == "VALUE_INVALID"
