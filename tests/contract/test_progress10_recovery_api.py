from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from tests.progress10_helpers import bootstrap_recovery, ingest_evidence


def _headers(tenant: str, project: str, *, subject: str = "recovery-admin", role: str = "recovery_admin") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": role,
        "X-SIP-Purposes": "operations,recovery,privacy,preservation,migration",
        "X-SIP-Audience": "private",
    }


def test_progress10_recovery_api_is_authenticated_scoped_and_idempotent(tmp_path: Path) -> None:
    """REQ: OPSDR-001, OPSDR-002, OPSDR-003, OPSDR-005 recovery APIs are authenticated, scope-bound, immutable, and idempotent."""
    env = bootstrap_recovery(tmp_path, name="p10-api")
    ingest_evidence(env["context"], env["tenant"], env["project"], asset_id="api-source")
    client = TestClient(create_app(context=env["context"], service_name="recovery-control"))
    admin = _headers(env["tenant"], env["project"])
    viewer = _headers(env["tenant"], env["project"], subject="viewer", role="viewer")

    objective_body = {
        "project_id": env["project"],
        "deployment_profile_id": env["local"]["deployment_profile_id"],
        "data_class": "project_record",
        "service_class": "canonical_control_plane",
        "rpo_seconds": 3600,
        "rto_seconds": 7200,
        "degraded_behavior": {"mode": "read_only"},
        "recovery_method": {"type": "local_open_preservation"},
        "evidence_class": "local_executed",
    }
    assert client.post(f"/v1/tenants/{env['tenant']}/recovery/objectives", headers=viewer, json=objective_body).status_code == 403
    objective = client.post(f"/v1/tenants/{env['tenant']}/recovery/objectives", headers=admin, json=objective_body)
    assert objective.status_code == 201, objective.text

    requested = datetime.now(timezone.utc) - timedelta(seconds=1)
    point_body = {
        "deployment_profile_id": env["local"]["deployment_profile_id"],
        "region": "local",
        "requested_point_at": requested.isoformat(),
        "immutability_days": 30,
        "evidence_class": "local_executed",
        "idempotency_key": "api-point-1",
    }
    created = client.post(f"/v1/projects/{env['project']}/recovery/points", headers=admin, json=point_body)
    assert created.status_code == 201, created.text
    replay = client.post(f"/v1/projects/{env['project']}/recovery/points", headers=admin, json=point_body)
    assert replay.status_code == 201, replay.text
    assert replay.json()["recovery_point_id"] == created.json()["recovery_point_id"]
    assert replay.json()["idempotent_replay"] is True

    wrong_project = client.get(f"/v1/projects/not-authorized/recovery/points/{created.json()['recovery_point_id']}", headers=admin)
    assert wrong_project.status_code == 403


def test_progress10_recovery_api_keeps_destructive_and_production_paths_fail_closed(tmp_path: Path) -> None:
    """REQ: DATRET-002, DATRET-004, OPSDR-004, OPSDR-006 destructive recovery operations require exact authority and production admission remains denied."""
    env = bootstrap_recovery(tmp_path, name="p10-api-deny")
    client = TestClient(create_app(context=env["context"], service_name="recovery-control"))
    admin = _headers(env["tenant"], env["project"])
    viewer = _headers(env["tenant"], env["project"], subject="viewer", role="viewer")

    graph = client.post(
        f"/v1/projects/{env['project']}/deletion-graphs",
        headers=viewer,
        json={"scope_type": "project", "scope_id": env["project"]},
    )
    assert graph.status_code == 403

    production = client.post(
        f"/v1/deployment/profiles/{env['local']['deployment_profile_id']}/recovery/production-admission",
        headers=admin,
    )
    assert production.status_code == 200
    assert production.json()["admitted"] is False
    assert production.json()["production_authorized"] is False
