from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from sip.api import create_app
from sip.canonical import sha256_bytes
from sip.database import ConsentGrantRow, ConstructionRecordRow
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SourceClass


def _headers(
    tenant: str,
    project: str,
    *,
    subject: str,
    roles: str,
    purposes: str = "construction,operations,preservation,memorialization",
) -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": purposes,
        "X-SIP-Audience": "private",
    }


def _asset(context, tenant: str, project: str, name: str):
    payload = f"synthetic:{name}".encode("utf-8")
    return context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=payload,
        media_type="application/octet-stream",
        original_name=name,
        classification=Classification.INTERNAL,
        retention_class="records",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[f"synthetic:{name}"], output_hash=sha256_bytes(payload)),
        actor_id="fixture-builder",
    )


def _two_projects(context, *, vertical: str) -> tuple[str, str, str, str]:
    tenant_a = context.tenancy.create_tenant(f"R1 {vertical} tenant A", tenant_id=f"r1-{vertical}-tenant-a")
    tenant_b = context.tenancy.create_tenant(f"R1 {vertical} tenant B", tenant_id=f"r1-{vertical}-tenant-b")
    project_a = context.tenancy.create_project(
        tenant_a,
        "A",
        vertical=vertical,
        classification="confidential",
        project_id=f"r1-{vertical}-project-a",
        actor_id="bootstrap-a",
    )
    project_b = context.tenancy.create_project(
        tenant_b,
        "B",
        vertical=vertical,
        classification="confidential",
        project_id=f"r1-{vertical}-project-b",
        actor_id="bootstrap-b",
    )
    return tenant_a, project_a, tenant_b, project_b


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r1_consent_revocation_is_tenant_and_project_scoped(context) -> None:
    """REQ: LIFCONS-001, LIFCONS-005, ARCIAM-001 unscoped and cross-tenant consent revocation fail closed while the owning project can revoke."""
    tenant_a, project_a, tenant_b, project_b = _two_projects(context, vertical="liveforever")
    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_b,
        project_id=project_b,
        subject_id="synthetic-subject-b",
        granted_by="subject-b",
        purposes=["preservation"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["memory"],
        derivative_policy={"local_only": True},
        expires_at=datetime.now(UTC) + timedelta(days=90),
    )
    client = TestClient(create_app(context=context, service_name="liveforever"))
    attacker = _headers(
        tenant_a,
        project_b,
        subject="privacy-officer-a",
        roles="privacy_officer",
        purposes="preservation",
    )

    legacy = client.post(
        f"/v1/liveforever/consents/{grant_id}/revoke",
        headers=attacker,
        json={"reason": "cross-tenant exploit"},
    )
    assert legacy.status_code == 403
    assert legacy.json()["error"]["code"] == "PROJECT_SCOPE_REQUIRED"

    scoped_attack = client.post(
        f"/v1/projects/{project_b}/liveforever/consents/{grant_id}/revoke",
        headers=attacker,
        json={"reason": "cross-tenant exploit"},
    )
    assert scoped_attack.status_code == 404

    with context.database.session() as session:
        grant = session.get(ConsentGrantRow, grant_id)
        assert grant is not None
        assert grant.tenant_id == tenant_b
        assert grant.project_id == project_b
        assert grant.state == "active"

    owner = _headers(
        tenant_b,
        project_b,
        subject="privacy-officer-b",
        roles="privacy_officer",
        purposes="preservation",
    )
    legitimate = client.post(
        f"/v1/projects/{project_b}/liveforever/consents/{grant_id}/revoke",
        headers=owner,
        json={"reason": "documented synthetic withdrawal"},
    )
    assert legitimate.status_code == 200, legitimate.text
    assert legitimate.json()["grant_id"] == grant_id

    with context.database.session() as session:
        assert session.get(ConsentGrantRow, grant_id).state == "revoked"


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r1_deficiency_retest_is_tenant_and_project_scoped(context) -> None:
    """REQ: CONQC-003, CONQC-006, ARCIAM-001 unscoped and cross-tenant deficiency mutation fail closed while the owning project can retest."""
    tenant_a, project_a, tenant_b, project_b = _two_projects(context, vertical="construction")
    observation = _asset(context, tenant_b, project_b, "synthetic-observation-b")
    correction = _asset(context, tenant_b, project_b, "synthetic-correction")
    retest = _asset(context, tenant_b, project_b, "synthetic-retest")
    deficiency_id = context.construction.create_deficiency(
        tenant_id=tenant_b,
        project_id=project_b,
        entity_id="synthetic-device-b",
        description="Synthetic deficiency",
        severity="high",
        evidence_asset_ids=[observation.asset_id],
        actor_id="reporter-b",
    )
    client = TestClient(create_app(context=context, service_name="construction"))
    attacker = _headers(tenant_a, project_b, subject="construction-admin-a", roles="project_admin")
    body = {
        "correction": "Synthetic correction",
        "correction_asset_ids": [correction.asset_id],
        "test_result": "pass",
        "test_asset_ids": [retest.asset_id],
    }

    legacy = client.post(
        f"/v1/construction/deficiencies/{deficiency_id}/retest",
        headers=attacker,
        json=body,
    )
    assert legacy.status_code == 403
    assert legacy.json()["error"]["code"] == "PROJECT_SCOPE_REQUIRED"

    scoped_attack = client.post(
        f"/v1/projects/{project_b}/construction/deficiencies/{deficiency_id}/retest",
        headers=attacker,
        json=body,
    )
    assert scoped_attack.status_code == 404

    with context.database.session() as session:
        deficiency = session.get(ConstructionRecordRow, deficiency_id)
        assert deficiency is not None
        assert deficiency.tenant_id == tenant_b
        assert deficiency.project_id == project_b
        assert deficiency.state == "open"

    owner = _headers(tenant_b, project_b, subject="construction-admin-b", roles="project_admin")
    legitimate = client.post(
        f"/v1/projects/{project_b}/construction/deficiencies/{deficiency_id}/retest",
        headers=owner,
        json=body,
    )
    assert legitimate.status_code == 200, legitimate.text
    assert legitimate.json()["state"] == "closed"


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r1_issue_verifier_is_authenticated_and_independent(context) -> None:
    """REQ: CONQC-003, CONQC-004, ARCIAM-001 issue closure derives verifier identity from authentication and enforces separation of duties."""
    tenant = context.tenancy.create_tenant("R1 issue tenant", tenant_id="r1-issue-tenant")
    project = context.tenancy.create_project(
        tenant,
        "R1 issue project",
        vertical="construction",
        classification="internal",
        project_id="r1-issue-project",
        actor_id="bootstrap",
    )
    observation = _asset(context, tenant, project, "observation-1")
    correction = _asset(context, tenant, project, "correction-1")
    retest = _asset(context, tenant, project, "retest-1")
    issue = context.construction.create_issue(
        tenant_id=tenant,
        project_id=project,
        issue_type="deficiency",
        description="Synthetic device failed test",
        evidence=[{"asset_id": observation.asset_id}],
        reporter_id="reporter",
        severity="high",
        idempotency_key="r1-issue-create",
    )
    issue_id = issue["issue_id"]
    context.construction.transition_issue(
        issue_id,
        tenant_id=tenant,
        project_id=project,
        actor_id="reporter",
        target_state="corrected",
        evidence=[{"asset_id": correction.asset_id}],
        note="corrected",
    )
    context.construction.transition_issue(
        issue_id,
        tenant_id=tenant,
        project_id=project,
        actor_id="reporter",
        target_state="retest_required",
        evidence=[{"asset_id": correction.asset_id}],
        note="ready for retest",
    )
    client = TestClient(create_app(context=context, service_name="construction"))
    reporter = _headers(tenant, project, subject="reporter", roles="project_admin")

    forged = client.post(
        f"/v1/projects/{project}/construction/issues/{issue_id}/transition",
        headers=reporter,
        json={
            "target_state": "verified_closed",
            "evidence": [{"asset_id": retest.asset_id}],
            "note": "attempt self-close",
            "verifier_id": "invented-independent-verifier",
        },
    )
    assert forged.status_code == 422
    assert forged.json()["error"]["code"] == "VALUE_INVALID"

    self_close = client.post(
        f"/v1/projects/{project}/construction/issues/{issue_id}/transition",
        headers=reporter,
        json={
            "target_state": "verified_closed",
            "evidence": [{"asset_id": retest.asset_id}],
            "note": "attempt self-close",
        },
    )
    assert self_close.status_code == 422
    assert self_close.json()["error"]["code"] == "ISSUE_INDEPENDENT_VERIFIER"

    independent = _headers(tenant, project, subject="independent-verifier", roles="project_admin")
    closed = client.post(
        f"/v1/projects/{project}/construction/issues/{issue_id}/transition",
        headers=independent,
        json={
            "target_state": "verified_closed",
            "evidence": [{"asset_id": retest.asset_id}],
            "note": "independent retest passed",
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "verified_closed"
    assert closed.json()["verification"]["verifier_id"] == "independent-verifier"


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r1_restricted_annex_requires_scoped_server_approval(context) -> None:
    """REQ: CONAC-006, CONHAND-001, CONHAND-004, CONMEP-006, SECEXT-005 restricted annexes require exact server authorization, immutable approval, and separation of duties."""
    tenant = context.tenancy.create_tenant("R1 restricted tenant", tenant_id="r1-restricted-tenant")
    project = context.tenancy.create_project(
        tenant,
        "R1 restricted project",
        vertical="construction",
        classification="restricted",
        project_id="r1-restricted-project",
        actor_id="bootstrap",
    )
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant,
        project_id=project,
        record_type="site",
        name="Synthetic restricted site",
        parent_id=None,
        state="observed",
        actor_id="bootstrap",
    )
    controller_photo = _asset(context, tenant, project, "synthetic-controller-photo")
    controller_record_id = context.construction.create_system_record(
        tenant_id=tenant,
        project_id=project,
        system_type="access_controller",
        parent_id=site,
        entity_id="r1-controller",
        state="observed",
        data={
            "manufacturer": "Synthetic",
            "model": "CTRL-R1",
            "network_address": "192.0.2.55",
            "controller_password_vault_ref": "vault://construction/r1-controller/password",
            "location": "Synthetic room",
        },
        evidence_asset_ids=[controller_photo.asset_id],
        actor_id="bootstrap",
    )
    scene = context.scene.create_scene(tenant, project, name="Synthetic restricted scene", actor_id="bootstrap")
    client = TestClient(create_app(context=context, service_name="construction"))
    project_admin = _headers(tenant, project, subject="handoff-requester", roles="project_admin")
    scope = {"systems": ["access_control"], "include_restricted_annex": True}
    base_body = {
        "scope": scope,
        "accepted_scene_commit_id": scene["commit_id"],
        "warranties": [],
        "training": [],
        "exclusions": [],
        "audience_profiles": {"owner": {"read_only": True}},
        "idempotency_key": "r1-restricted-handoff",
        "classification": "restricted",
        "audience": "owner",
        "purpose": "owner_handoff",
    }

    self_asserted = client.post(
        f"/v1/projects/{project}/construction/handoffs",
        headers=project_admin,
        json={
            **base_body,
            "audience_profiles": {
                "owner": {"read_only": True},
                "restricted_owner_export_approved": True,
            },
        },
    )
    assert self_asserted.status_code == 422
    assert self_asserted.json()["error"]["code"] == "RESTRICTED_EXPORT_CALLER_ASSERTION_PROHIBITED"

    no_approval = client.post(
        f"/v1/projects/{project}/construction/handoffs",
        headers=project_admin,
        json=base_body,
    )
    assert no_approval.status_code == 403
    assert no_approval.json()["error"]["code"] == "RESTRICTED_EXPORT_APPROVAL_REQUIRED"

    approval_body = {
        "scope": scope,
        "accepted_scene_commit_id": scene["commit_id"],
        "warranties": [],
        "training": [],
        "exclusions": [],
        "audience_profiles": {"owner": {"read_only": True}},
        "handoff_idempotency_key": "r1-restricted-handoff",
        "classification": "restricted",
        "audience": "owner",
        "purpose": "owner_handoff",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    unauthorized_approval = client.post(
        f"/v1/projects/{project}/construction/restricted-export-approvals",
        headers=project_admin,
        json=approval_body,
    )
    assert unauthorized_approval.status_code == 403
    assert unauthorized_approval.json()["error"]["code"] == "ACTION_DENIED"

    combined = _headers(
        tenant,
        project,
        subject="restricted-approver",
        roles="restricted_export_approver,project_admin",
        purposes="owner_handoff",
    )
    approved = client.post(
        f"/v1/projects/{project}/construction/restricted-export-approvals",
        headers=combined,
        json=approval_body,
    )
    assert approved.status_code == 201, approved.text
    approval_id = approved.json()["approval_id"]
    assert approved.json()["approver_id"] == "restricted-approver"

    self_use = client.post(
        f"/v1/projects/{project}/construction/handoffs",
        headers=combined,
        json={**base_body, "restricted_export_approval_id": approval_id},
    )
    assert self_use.status_code == 403
    assert self_use.json()["error"]["code"] == "RESTRICTED_EXPORT_SEPARATION_OF_DUTIES"

    accepted = client.post(
        f"/v1/projects/{project}/construction/handoffs",
        headers=project_admin,
        json={**base_body, "restricted_export_approval_id": approval_id},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["status"] == "verified"
    package_path = Path(accepted.json()["package_path"])
    with zipfile.ZipFile(package_path) as archive:
        inventory = json.loads(archive.read("data/inventory.json"))
    controller = next(item for item in inventory if item["record_id"] == controller_record_id)
    assert controller["data"]["network_address"] == "192.0.2.55"
    assert controller["data"]["controller_password_vault_ref"] == "vault://construction/r1-controller/password"
    assert "controller_password" not in controller["data"]
    assert "synthetic-restricted-password" not in json.dumps(controller, sort_keys=True)
