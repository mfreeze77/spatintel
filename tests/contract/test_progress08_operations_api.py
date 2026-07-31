from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from tests.progress08_helpers import bootstrap, compute_profile, current_catalog_args, now


def _headers(tenant: str, project: str, *, subject: str, role: str) -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": role,
        "X-SIP-Purposes": "operations,support",
        "X-SIP-Audience": "private",
    }


def _telemetry_body() -> dict:
    return {
        "telemetry_type": "log",
        "service": "control-api",
        "release": "1.1.0-progress08",
        "correlation_id": "corr-api-ops08",
        "trace_id": "a" * 32,
        "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        "operation_id": "operation-api-ops08",
        "route_template": "/v1/projects/{project_id}/operations",
        "stage": "support",
        "hardware_profile": "cpu-reference",
        "execution_profile": "local",
        "vertical": "platform",
        "severity": "info",
        "outcome": "passed",
        "payload": {"message_code": "api_ok", "duration_ms": 2.0},
        "labels": {"support_profile": "metadata-only"},
    }


def test_progress08_operations_api_enforces_tenant_scope_and_observability_roles(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003 authenticated operations APIs enforce exact project scope and retain safe trace correlation."""
    context, tenant, project = bootstrap(tmp_path, name="ops08-api-observe")
    client = TestClient(create_app(context=context, service_name="operations-intelligence"))
    viewer = _headers(tenant, project, subject="viewer", role="viewer")
    ops = _headers(tenant, project, subject="ops", role="ops_admin")
    denied = client.post(f"/v1/projects/{project}/operations/telemetry", headers=viewer, json=_telemetry_body())
    assert denied.status_code == 403
    created = client.post(f"/v1/projects/{project}/operations/telemetry", headers=ops, json=_telemetry_body())
    assert created.status_code == 201, created.text
    assert created.json()["trace_id"] == "a" * 32
    queried = client.get(f"/v1/projects/{project}/operations/telemetry", headers=ops)
    assert queried.status_code == 200
    assert queried.json()["count"] == 1
    wrong_project = client.get("/v1/projects/project-not-authorized/operations/telemetry", headers=ops)
    assert wrong_project.status_code == 403
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'sip_ops_telemetry_records{telemetry_type="log"} 1' in metrics.text
    assert tenant not in metrics.text
    assert project not in metrics.text


def test_progress08_cost_override_and_support_approval_require_exact_roles(tmp_path: Path) -> None:
    """REQ: OPSCOST-001, OPSCOST-003, OPSCOST-004, OPSSUP-001, OPSSUP-002, OPSSUP-003, OPSSUP-006 cost and support approval routes require independent exact grants."""
    context, tenant, project = bootstrap(tmp_path, name="ops08-api-governance")
    client = TestClient(create_app(context=context, service_name="operations-intelligence"))
    ops = _headers(tenant, project, subject="ops", role="ops_admin")
    project_admin = _headers(tenant, project, subject="customer-requester", role="project_admin")
    budget_approver = _headers(tenant, project, subject="budget-approver", role="budget_approver")
    support_approver = _headers(tenant, project, subject="customer-approver", role="support_approver")
    support_engineer = _headers(tenant, project, subject="support-engineer", role="support_engineer")

    profile = client.post("/v1/operations/compute-profiles", headers=ops, json={k: v for k, v in compute_profile().items() if k != "actor_id"})
    assert profile.status_code == 201, profile.text
    catalog_args = current_catalog_args(tenant)
    catalog_payload = {k: v for k, v in catalog_args.items() if k not in {"tenant_id", "actor_id"}}
    catalog_payload["effective_at"] = catalog_payload["effective_at"].isoformat()
    catalog_payload["expires_at"] = catalog_payload["expires_at"].isoformat()
    catalog = client.post(f"/v1/tenants/{tenant}/operations/price-catalogs", headers=ops, json=catalog_payload)
    assert catalog.status_code == 201, catalog.text
    policy = client.post(
        f"/v1/tenants/{tenant}/operations/budgets",
        headers=ops,
        json={
            "project_id": project, "revision": "v1", "currency": "USD", "period_seconds": 86400,
            "soft_limit": 10.0, "hard_limit": 100.0, "concurrency_limit": 1,
            "storage_limit_bytes": 1000000, "retention_limit_days": 365, "anomaly_threshold": 1.5,
        },
    )
    assert policy.status_code == 201, policy.text
    override = client.post(
        f"/v1/projects/{project}/operations/budget-overrides",
        headers=ops,
        json={"budget_id": policy.json()["budget_id"], "reason": "synthetic capacity", "additional_amount": 10.0, "currency": "USD", "expires_at": (now() + timedelta(hours=1)).isoformat()},
    )
    assert override.status_code == 201, override.text
    routine_denied = client.post(f"/v1/projects/{project}/operations/budget-overrides/{override.json()['override_id']}/approve", headers=ops)
    assert routine_denied.status_code == 403
    approved = client.post(f"/v1/projects/{project}/operations/budget-overrides/{override.json()['override_id']}/approve", headers=budget_approver)
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "active"

    telemetry = client.post(f"/v1/projects/{project}/operations/telemetry", headers=ops, json=_telemetry_body())
    assert telemetry.status_code == 201
    request = client.post(
        f"/v1/projects/{project}/operations/support-access",
        headers=project_admin,
        json={
            "resource_scope": {"resource_ids": [telemetry.json()["telemetry_id"]], "telemetry_types": ["log"], "include_logs": True, "include_metrics": False, "include_traces": False, "classification": "internal", "audience": "private"},
            "purpose": "support", "personnel": ["support-engineer"], "duration_seconds": 3600,
        },
    )
    assert request.status_code == 201, request.text
    self_approval = client.post(f"/v1/projects/{project}/operations/support-access/{request.json()['grant_id']}/approve", headers=project_admin)
    assert self_approval.status_code == 403
    support_ok = client.post(f"/v1/projects/{project}/operations/support-access/{request.json()['grant_id']}/approve", headers=support_approver)
    assert support_ok.status_code == 200, support_ok.text
    bundle = client.post(
        f"/v1/projects/{project}/operations/support-bundles",
        headers=support_engineer,
        json={"grant_id": request.json()["grant_id"], "telemetry_ids": [telemetry.json()["telemetry_id"]], "hardware_profile": {"device_tier": "synthetic"}, "manifest_references": []},
    )
    assert bundle.status_code == 201, bundle.text
    assert bundle.json()["verification"]["valid"] is True
