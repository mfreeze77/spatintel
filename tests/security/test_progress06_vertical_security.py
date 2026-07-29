from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient

from sip.api import create_app
from sip.errors import AuthorizationError, NotFoundError, ValidationError
from sip.models import Audience


def _headers(tenant: str, project: str, *, subject: str = "admin", roles: str = "tenant_admin") -> dict[str, str]:
    return {
        "X-SIP-Subject": subject,
        "X-SIP-Tenant": tenant,
        "X-SIP-Project": project,
        "X-SIP-Roles": roles,
    }


@pytest.mark.security
@pytest.mark.integration
def test_progress06_construction_records_fail_closed_across_tenants_and_redact_owner_security(context, tmp_path: Path) -> None:
    """REQ: CONAC-003, CONAC-006, CONFA-005, CONMEP-006, CONQC-006 construction vertical enforces tenant isolation and redacts restricted controller/programming data."""
    tenant_a = context.tenancy.create_tenant("Synthetic A", tenant_id="tenant-p06-con-a")
    tenant_b = context.tenancy.create_tenant("Synthetic B", tenant_id="tenant-p06-con-b")
    project_a = context.tenancy.create_project(tenant_a, "A", vertical="construction", classification="confidential", project_id="project-p06-con-a", actor_id="admin-a")
    project_b = context.tenancy.create_project(tenant_b, "B", vertical="construction", classification="confidential", project_id="project-p06-con-b", actor_id="admin-b")
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant_a, project_id=project_a, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id="admin-a",
    )
    controller = context.construction.create_system_record(
        tenant_id=tenant_a, project_id=project_a, system_type="access_controller", parent_id=room,
        entity_id="synthetic-controller", state="observed",
        data={
            "manufacturer": "Synthetic", "model": "CTRL-1", "location": "Synthetic Room",
            "network_address": "192.0.2.10", "controller_password": "never-export",
            "credential_secret": "never-export", "security_zone": "restricted-zone-a",
        },
        evidence_asset_ids=["synthetic-photo"], actor_id="admin-a",
    )
    exported = context.construction.export_system_pack(tenant_a, project_a, pack="access_control")
    row = next(item for item in exported["records"] if item["record_id"] == controller)
    assert "network_address" not in row["data"]
    assert "controller_password" not in row["data"]
    assert "credential_secret" not in row["data"]
    assert row["redacted_fields"] == ["controller_password", "credential_secret", "network_address"]
    cross_tenant_search = context.construction.search_facility_records(tenant_b, project_b, query="synthetic-controller")
    assert cross_tenant_search["items"] == []
    # The authenticated service surface may not accept a tenant/project/body override.
    client = TestClient(create_app(context=context, service_name="construction"))
    response = client.get(
        f"/v1/projects/{project_a}/construction/search",
        headers=_headers(tenant_b, project_b, subject="attacker", roles="viewer"),
        params={"query": "synthetic-controller"},
    )
    assert response.status_code in {403, 404}
    assert "never-export" not in response.text

    with pytest.raises(ValidationError) as credential_data:
        context.construction.record_commissioning(
            tenant_id=tenant_a, project_id=project_a, system_type="access_control",
            entity_ids=[controller], procedure={"id": "synthetic-access-test"}, prerequisites=[],
            steps=[{"step": 1, "expected": "locked", "actual": "locked", "result": "pass"}],
            participants=[{"id": "tester-a", "role": "tester", "credential_id": "must-not-retain"}],
            instruments=[{"id": "meter-a", "calibration_state": "current"}], attachments=[],
            results={"passed": True}, actor_id="tester-a", idempotency_key="credential-data-denied",
        )
    assert credential_data.value.code == "COMMISSIONING_CREDENTIAL_DATA_PROHIBITED"

    scene = context.scene.create_scene(tenant_a, project_a, name="Synthetic owner-security scene", actor_id="admin-a")
    handoff_path = tmp_path / "owner-handoff.zip"
    handoff = context.construction.create_owner_handoff(
        tenant_id=tenant_a, project_id=project_a, destination=handoff_path,
        scope={"systems": ["access_control"], "include_restricted_annex": False},
        accepted_scene_commit_id=scene["commit_id"], warranties=[], training=[], exclusions=[],
        audience_profiles={"owner": {"read_only": True}, "restricted_owner_export_approved": False},
        actor_id="admin-a", idempotency_key="security-owner-handoff",
    )
    assert handoff["status"] == "verified"
    with zipfile.ZipFile(handoff_path) as archive:
        inventory = json.loads(archive.read("data/inventory.json"))
        manifest = json.loads(archive.read("manifest.json"))
    exported_controller = next(item for item in inventory if item["record_id"] == controller)
    serialized = json.dumps(exported_controller, sort_keys=True)
    assert "192.0.2.10" not in serialized
    assert "never-export" not in serialized
    assert set(exported_controller["redacted_fields"]) == {"controller_password", "credential_secret", "network_address"}
    assert manifest["handoff_validation"]["restricted_annex_included"] is False
    assert manifest["handoff_validation"]["redactions"]


@pytest.mark.security
@pytest.mark.integration
def test_progress06_liveforever_scope_and_generated_presence_fail_closed(context) -> None:
    """REQ: LIFCONS-001, LIFCONS-003, LIFPRES-003, LIFPRES-005, LIFHYB-007, LIFHYB-008 consent scope, tenant isolation, and generated-presence/provider gates fail closed."""
    tenant_a = context.tenancy.create_tenant("Synthetic Family A", tenant_id="tenant-p06-lif-a")
    tenant_b = context.tenancy.create_tenant("Synthetic Family B", tenant_id="tenant-p06-lif-b")
    project_a = context.tenancy.create_project(tenant_a, "A", vertical="liveforever", classification="confidential", project_id="project-p06-lif-a", actor_id="admin-a")
    project_b = context.tenancy.create_project(tenant_b, "B", vertical="liveforever", classification="confidential", project_id="project-p06-lif-b", actor_id="admin-b")
    subject = "synthetic-subject-a"
    grant = context.liveforever.grant_consent(
        tenant_id=tenant_a, project_id=project_a, subject_id=subject, granted_by=subject,
        purposes=["preservation"], audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["memory", "interview", "visual_reconstruction"],
        derivative_policy={"local_only": True, "voice": False, "likeness": False},
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    interview = context.liveforever.create_interview(
        tenant_id=tenant_a, project_id=project_a, subject_id=subject,
        participants=[{"person_id": subject, "role": "narrator"}],
        consent_context={"confirmed": True, "grant_id": grant}, recording_state="stopped",
        source_media_ids=["synthetic-audio"], timeline={"started_ms": 0, "ended_ms": 1000},
        device={"type": "synthetic"}, environment={"location": "synthetic-room"},
        interruptions=[], question_lineage=[{"source": "human", "text": "Synthetic question"}],
        pacing_policy={"pause_allowed": True, "stop_allowed": True}, actor_id="admin-a",
        idempotency_key="p06-security-interview", complete=True,
    )
    with pytest.raises(NotFoundError):
        context.liveforever.interview(tenant_b, project_b, interview["interview_id"])
    common = dict(
        tenant_id=tenant_a, project_id=project_a, source_ids=["synthetic-audio"], subject_ids=[subject],
        consent_grant_ids=[grant], audience=Audience.FAMILY, classification="confidential",
        retention={"class": "preservation"}, generation_lineage={}, policy={"purpose": "preservation"},
        actor_id="admin-a",
    )
    with pytest.raises(AuthorizationError) as external:
        context.liveforever.register_derivative(
            **common, derivative_type="visual_reconstruction",
            provider={"execution": "external", "approved": False}, idempotency_key="external-denied",
        )
    assert external.value.code == "EXTERNAL_PROVIDER_NOT_APPROVED"
    with pytest.raises(AuthorizationError) as voice:
        context.liveforever.register_derivative(
            **common, derivative_type="voice", provider={"execution": "local"}, idempotency_key="voice-denied",
        )
    assert voice.value.code == "GENERATED_PRESENCE_DISABLED"
