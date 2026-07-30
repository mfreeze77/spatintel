from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sip.api import create_app
from sip.canonical import sha256_bytes
from sip.database import ConstructionRecordRow
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SourceClass


def _headers(tenant: str, project: str, *, subject: str, roles: str, purposes: str = "construction,operations,preservation,family_review") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": purposes,
        "X-SIP-Audience": "private",
    }


def _asset(context, tenant: str, project: str, name: str, payload: bytes | None = None):
    data = payload or f"synthetic:{name}".encode()
    return context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=data,
        media_type="application/octet-stream",
        original_name=name,
        classification=Classification.INTERNAL,
        retention_class="records",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[f"synthetic:{name}"], output_hash=sha256_bytes(data)),
        actor_id="fixture-builder",
    )


def _project(context, suffix: str, vertical: str = "construction") -> tuple[str, str]:
    tenant = context.tenancy.create_tenant(f"R2 tenant {suffix}", tenant_id=f"r2-tenant-{suffix}")
    project = context.tenancy.create_project(
        tenant,
        f"R2 project {suffix}",
        vertical=vertical,
        classification="restricted" if vertical == "construction" else "confidential",
        project_id=f"r2-project-{suffix}",
        actor_id="bootstrap",
    )
    return tenant, project


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r2_restricted_search_authorizes_before_matching_and_hides_identity(context) -> None:
    """REQ: ARCIAM-001, CONAC-003, CONAC-006, CONMEP-006, CONQC-006 restricted data is authorized before search matching, counting, and disclosure."""
    tenant, project = _project(context, "restricted-search")
    evidence = _asset(context, tenant, project, "controller-photo.bin")
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id="builder",
    )
    record_id = context.construction.create_system_record(
        tenant_id=tenant,
        project_id=project,
        system_type="access_controller",
        parent_id=site,
        entity_id="controller-1",
        state="observed",
        data={
            "manufacturer": "Synthetic",
            "model": "CTRL-R2",
            "network_address": "192.0.2.44",
            "controller_password_vault_ref": "vault://construction/controller-1/password",
        },
        evidence_asset_ids=[evidence.asset_id],
        actor_id="builder",
    )
    # Insert one legacy row containing a raw secret to prove defense-in-depth
    # search scrubbing does not reveal the record by the secret value.
    with context.database.session() as session:
        session.add(ConstructionRecordRow(
            record_id="legacy-secret-record",
            tenant_id=tenant,
            project_id=project,
            record_type="access_controller",
            parent_id=site,
            entity_id="legacy-controller",
            state="observed",
            data_json={
                "manufacturer": "Synthetic",
                "model": "LEGACY",
                "controller_password": "SUPERSECRET",
                "network_address": "192.0.2.45",
            },
            evidence_asset_ids_json=[evidence.asset_id],
            created_by="legacy-import",
        ))
    programming = _asset(context, tenant, project, "restricted-programming-record.pdf")
    doc = context.construction.create_document_revision(
        tenant_id=tenant,
        project_id=project,
        stable_document_id=None,
        document_type="programming_record",
        title="RESTRICTED-PROGRAMMING-TITLE controller programming record",
        revision="1",
        issue_date="2026-07-29",
        issuer="Synthetic",
        status="current",
        asset_id=programming.asset_id,
        source_sha256=programming.sha256,
        page_count=1,
        permissions={"classification": "restricted", "search_visible": False, "owner_export": False},
        page_regions=[], spatial_links=[{"record_id": record_id}], extraction={}, review={"state": "reviewed"},
        actor_id="builder",
    )
    client = TestClient(create_app(context=context, service_name="construction"))
    viewer = _headers(tenant, project, subject="viewer", roles="viewer")
    project_admin = _headers(tenant, project, subject="routine-admin", roles="project_admin")
    restricted_reader = _headers(tenant, project, subject="restricted-reader", roles="restricted_reader")

    leaked = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=viewer,
        params={"query": "SUPERSECRET", "include_restricted": "false"},
    )
    assert leaked.status_code == 200, leaked.text
    assert leaked.json()["items"] == []
    assert "legacy-secret-record" not in leaked.text
    assert doc["revision_id"] not in leaked.text

    hidden_title = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=viewer,
        params={"query": "RESTRICTED-PROGRAMMING-TITLE", "include_restricted": "false"},
    )
    assert hidden_title.status_code == 200
    assert hidden_title.json()["items"] == []

    routine_admin = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=project_admin,
        params={"include_restricted": "true"},
    )
    assert routine_admin.status_code == 403
    assert routine_admin.json()["error"]["code"] == "ACTION_DENIED"

    raw_secret_probe = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=restricted_reader,
        params={"query": "SUPERSECRET", "include_restricted": "true"},
    )
    assert raw_secret_probe.status_code == 200, raw_secret_probe.text
    assert raw_secret_probe.json()["items"] == []

    authorized = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=restricted_reader,
        params={"query": "192.0.2.44", "include_restricted": "true"},
    )
    assert authorized.status_code == 200, authorized.text
    assert [item["id"] for item in authorized.json()["items"]] == [record_id]

    hidden_direct = client.get(
        f"/v1/projects/{project}/construction/document-revisions/{doc['revision_id']}", headers=viewer,
    )
    assert hidden_direct.status_code == 404
    direct = client.get(
        f"/v1/projects/{project}/construction/document-revisions/{doc['revision_id']}",
        headers=restricted_reader,
        params={"include_restricted": "true"},
    )
    assert direct.status_code == 200, direct.text


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r2_raw_secrets_are_rejected_and_never_exported(context) -> None:
    """REQ: CONAC-005, CONAC-006, CONFA-005, CONMEP-006 raw credentials are prohibited; only opaque restricted references may be retained."""
    tenant, project = _project(context, "raw-secret")
    evidence = _asset(context, tenant, project, "raw-secret-evidence.bin")
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id="builder",
    )
    client = TestClient(create_app(context=context, service_name="construction"))
    admin = _headers(tenant, project, subject="admin", roles="project_admin")
    rejected = client.post(
        f"/v1/projects/{project}/construction/systems",
        headers=admin,
        json={
            "system_type": "access_controller",
            "parent_id": site,
            "state": "observed",
            "data": {"manufacturer": "Synthetic", "model": "CTRL", "controller_password": "SUPERSECRET"},
            "evidence_asset_ids": [evidence.asset_id],
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "CONSTRUCTION_SYSTEM_RAW_SECRET_PROHIBITED"

    accepted = client.post(
        f"/v1/projects/{project}/construction/systems",
        headers=admin,
        json={
            "system_type": "access_controller",
            "parent_id": site,
            "state": "observed",
            "data": {
                "manufacturer": "Synthetic",
                "model": "CTRL",
                "controller_password_vault_ref": "vault://construction/controller/password",
            },
            "evidence_asset_ids": [evidence.asset_id],
        },
    )
    assert accepted.status_code == 201, accepted.text
    record_id = accepted.json()["record_id"]
    pack = context.construction.export_system_pack(tenant, project, pack="access_control", include_restricted=True)
    row = next(item for item in pack["records"] if item["record_id"] == record_id)
    assert row["data"]["controller_password_vault_ref"].startswith("vault://")
    assert "SUPERSECRET" not in str(pack)
    assert pack["raw_secrets_included"] is False


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r2_construction_verified_state_requires_governed_independent_transition(context) -> None:
    """REQ: CONFA-002, CONSURV-004, DATEVID-002 direct or forged verified Construction records are denied."""
    tenant, project = _project(context, "construction-verification")
    evidence = _asset(context, tenant, project, "verification-evidence.bin")
    signature = _asset(context, tenant, project, "verification-signature.bin")
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id="builder",
    )
    client = TestClient(create_app(context=context, service_name="construction"))
    creator = _headers(tenant, project, subject="creator", roles="project_admin")
    forged = client.post(
        f"/v1/projects/{project}/construction/systems",
        headers=creator,
        json={
            "system_type": "fire_alarm_panel", "parent_id": site, "state": "verified",
            "data": {"manufacturer": "Synthetic", "model": "PANEL", "verified_by": "invented"},
            "evidence_asset_ids": [evidence.asset_id],
        },
    )
    assert forged.status_code == 422
    assert forged.json()["error"]["code"] == "CONSTRUCTION_DIRECT_VERIFICATION_PROHIBITED"

    missing_evidence = client.post(
        f"/v1/projects/{project}/construction/systems",
        headers=creator,
        json={
            "system_type": "fire_alarm_panel", "parent_id": site, "state": "observed",
            "data": {"manufacturer": "Synthetic", "model": "PANEL"},
            "evidence_asset_ids": ["MISSING-EVIDENCE"],
        },
    )
    assert missing_evidence.status_code == 422
    assert missing_evidence.json()["error"]["code"] == "CONSTRUCTION_SYSTEM_EVIDENCE_ASSET_SCOPE"

    created = client.post(
        f"/v1/projects/{project}/construction/systems",
        headers=creator,
        json={
            "system_type": "fire_alarm_panel", "parent_id": site, "state": "observed",
            "data": {"manufacturer": "Synthetic", "model": "PANEL"},
            "evidence_asset_ids": [evidence.asset_id],
        },
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["record_id"]
    body = {
        "method": "independent field verification",
        "scope": {"attributes": ["manufacturer", "model"]},
        "exclusions": [],
        "evidence_asset_ids": [evidence.asset_id],
        "signature_asset_id": signature.asset_id,
        "idempotency_key": "verify-panel-r2",
    }
    routine_admin = client.post(
        f"/v1/projects/{project}/construction/systems/{record_id}/verify", headers=creator, json=body,
    )
    assert routine_admin.status_code == 403
    creator_verifier = _headers(tenant, project, subject="creator", roles="construction_verifier")
    self_verify = client.post(
        f"/v1/projects/{project}/construction/systems/{record_id}/verify", headers=creator_verifier, json=body,
    )
    assert self_verify.status_code == 422
    assert self_verify.json()["error"]["code"] == "CONSTRUCTION_INDEPENDENT_VERIFIER_REQUIRED"
    independent = _headers(tenant, project, subject="independent-verifier", roles="construction_verifier")
    verified = client.post(
        f"/v1/projects/{project}/construction/systems/{record_id}/verify", headers=independent, json=body,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "verified"
    assert verified.json()["verifier_id"] == "independent-verifier"


@pytest.mark.security
@pytest.mark.privacy
def test_progress06_r2_liveforever_truth_requires_scoped_evidence_consent_and_review(context) -> None:
    """REQ: DATEVID-006, LIFCONS-001, LIFCONS-002, LIFGRAPH-001, LIFLABEL-001, LIFOVR-002 fabricated evidence, blank subjects, and self-review fail closed."""
    tenant, project = _project(context, "live-truth", vertical="liveforever")
    context.liveforever.grant_consent(
        tenant_id=tenant, project_id=project, subject_id="subject-1", granted_by="subject-1",
        purposes=["preservation", "family_review"], audiences=[Audience.PRIVATE], scopes=["memory"],
        derivative_policy={"local_only": True}, expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    evidence_a = _asset(context, tenant, project, "memory-source-a.bin")
    evidence_b = _asset(context, tenant, project, "memory-source-b.bin")
    client = TestClient(create_app(context=context, service_name="liveforever"))
    contributor = _headers(tenant, project, subject="contributor", roles="project_admin", purposes="preservation,family_review")

    blank = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=contributor,
        json={
            "record_type": "memory", "subject_id": "", "related_ids": [],
            "data": {"title": "Blank subject bypass"}, "source_class": "verified", "confidence": 0.99,
            "evidence_asset_ids": ["MISSING-EVIDENCE"], "audience": "private", "purpose": "preservation",
        },
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "MEMORY_SUBJECT_BLANK"

    fabricated = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=contributor,
        json={
            "record_type": "memory", "subject_id": "subject-1", "related_ids": [],
            "data": {"title": "Unsupported claim"}, "source_class": "recalled", "confidence": 0.8,
            "evidence_asset_ids": ["MISSING-EVIDENCE"], "audience": "private", "purpose": "preservation",
        },
    )
    assert fabricated.status_code == 422
    assert fabricated.json()["error"]["code"] == "LIVEFOREVER_RECORD_EVIDENCE_ASSET_SCOPE"

    direct_strong = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=contributor,
        json={
            "record_type": "memory", "subject_id": "subject-1", "related_ids": [],
            "data": {"title": "Unreviewed corroboration"}, "source_class": "corroborated", "confidence": 0.9,
            "evidence_asset_ids": [evidence_a.asset_id, evidence_b.asset_id], "audience": "private", "purpose": "preservation",
        },
    )
    assert direct_strong.status_code == 422
    assert direct_strong.json()["error"]["code"] == "MEMORY_GOVERNED_REVIEW_REQUIRED"

    created = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=contributor,
        json={
            "record_type": "memory", "subject_id": "subject-1", "related_ids": [],
            "data": {"title": "First-person recollection"}, "source_class": "recalled", "confidence": 0.6,
            "evidence_asset_ids": [evidence_a.asset_id], "audience": "private", "purpose": "preservation",
        },
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["record_id"]
    review_body = {
        "target_source_class": "corroborated",
        "rationale": "Two independently retained source records agree",
        "evidence_asset_ids": [evidence_a.asset_id, evidence_b.asset_id],
        "confidence": 0.85,
        "idempotency_key": "review-memory-r2",
    }
    routine = client.post(
        f"/v1/projects/{project}/liveforever/records/{record_id}/review", headers=contributor, json=review_body,
    )
    assert routine.status_code == 403
    self_reviewer = _headers(tenant, project, subject="contributor", roles="liveforever_reviewer", purposes="family_review")
    self_review = client.post(
        f"/v1/projects/{project}/liveforever/records/{record_id}/review", headers=self_reviewer, json=review_body,
    )
    assert self_review.status_code == 422
    assert self_review.json()["error"]["code"] == "MEMORY_INDEPENDENT_REVIEWER_REQUIRED"
    reviewer = _headers(tenant, project, subject="family-reviewer", roles="liveforever_reviewer", purposes="family_review")
    reviewed = client.post(
        f"/v1/projects/{project}/liveforever/records/{record_id}/review", headers=reviewer, json=review_body,
    )
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["source_class"] == "corroborated"
    assert reviewed.json()["reviewer_id"] == "family-reviewer"

    subjectless = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=contributor,
        json={
            "record_type": "place", "subject_id": None,
            "subject_scope": {"kind": "place", "scope_id": "synthetic-room", "consent_basis": "non_personal_subject"},
            "related_ids": [], "data": {"title": "Synthetic memory room"},
            "source_class": "direct_capture", "confidence": 1.0,
            "evidence_asset_ids": [evidence_a.asset_id], "audience": "private", "purpose": "preservation",
        },
    )
    assert subjectless.status_code == 201, subjectless.text


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r2_legacy_document_adapter_requires_scoped_immutable_asset(context) -> None:
    """REQ: CONDOC-001, DATEVID-002 legacy document creation cannot bypass canonical immutable provenance."""
    tenant, project = _project(context, "legacy-doc")
    client = TestClient(create_app(context=context, service_name="construction"))
    admin = _headers(tenant, project, subject="admin", roles="project_admin")
    missing = client.post(
        f"/v1/projects/{project}/construction/documents",
        headers=admin,
        json={"document_type": "drawing", "asset_id": "MISSING-ASSET", "data": {"title": "Bad drawing"}},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "DOCUMENT_ASSET_SCOPE"
    asset = _asset(context, tenant, project, "legacy-drawing.pdf")
    accepted = client.post(
        f"/v1/projects/{project}/construction/documents",
        headers=admin,
        json={
            "document_type": "drawing", "asset_id": asset.asset_id,
            "data": {"title": "Legacy drawing", "revision": "A", "page_count": 1},
        },
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["canonical_revision"] is True
    fetched = client.get(
        f"/v1/projects/{project}/construction/document-revisions/{accepted.json()['revision_id']}", headers=admin,
    )
    assert fetched.status_code == 200
    assert fetched.json()["source_sha256"] == asset.sha256


@pytest.mark.security
@pytest.mark.integration
def test_progress06_r2_field_visit_and_generated_lineage_reject_missing_assets(context) -> None:
    """REQ: CONSURV-002, DATEVID-002, LIFREC-002 field captures, detail evidence, and generated lineage require live in-scope immutable assets."""
    tenant, project = _project(context, "nested-assets")
    capture = _asset(context, tenant, project, "capture.bin")
    detail = _asset(context, tenant, project, "detail.bin")
    source = _asset(context, tenant, project, "generated-input.bin")
    site = context.construction.create_hierarchy_item(tenant_id=tenant, project_id=project, record_type="site", name="Site", parent_id=None, state="observed", actor_id="builder")
    survey = context.construction.create_survey_plan(tenant_id=tenant, project_id=project, name="Survey", objectives=["capture"], required_place_ids=[site], required_system_types=[], sensitive_regions=[], control_requirements={}, measurement_requirements={}, safety={}, permissions={}, deliverables=[{"type": "survey_report"}], actor_id="builder", idempotency_key="nested-survey")
    with pytest.raises(Exception) as missing_capture:
        context.construction.record_field_visit(tenant_id=tenant, project_id=project, survey_id=survey["survey_id"], scope={"site": site}, capture_ids=["MISSING-CAPTURE"], checklist=[{"id": "capture", "status": "complete"}], detail_evidence=[], inaccessible_regions=[], coverage={"observed_fraction": 1.0}, tracking={}, registration={}, controls={}, inventory={}, unresolved_questions=[], privacy={}, actor_id="builder", idempotency_key="missing-capture")
    assert getattr(missing_capture.value, "code", "") == "FIELD_VISIT_CAPTURE_ASSET_SCOPE"
    with pytest.raises(Exception) as missing_detail:
        context.construction.record_field_visit(tenant_id=tenant, project_id=project, survey_id=survey["survey_id"], scope={"site": site}, capture_ids=[capture.asset_id], checklist=[{"id": "capture", "status": "complete"}], detail_evidence=[{"asset_id": "MISSING-DETAIL"}], inaccessible_regions=[], coverage={"observed_fraction": 1.0}, tracking={}, registration={}, controls={}, inventory={}, unresolved_questions=[], privacy={}, actor_id="builder", idempotency_key="missing-detail")
    assert getattr(missing_detail.value, "code", "") == "FIELD_VISIT_DETAIL_EVIDENCE_ASSET_SCOPE"
    visit = context.construction.record_field_visit(tenant_id=tenant, project_id=project, survey_id=survey["survey_id"], scope={"site": site}, capture_ids=[capture.asset_id], checklist=[{"id": "capture", "status": "complete"}], detail_evidence=[{"asset_id": detail.asset_id, "sha256": detail.sha256}], inaccessible_regions=[], coverage={"observed_fraction": 1.0}, tracking={}, registration={}, controls={}, inventory={}, unresolved_questions=[], privacy={}, actor_id="builder", idempotency_key="valid-visit")
    assert visit["state"] == "completed"
    subject = "nested-subject"
    context.liveforever.grant_consent(tenant_id=tenant, project_id=project, subject_id=subject, granted_by=subject, purposes=["preservation", "family_review"], audiences=[Audience.PRIVATE], scopes=["*"], derivative_policy={"local_only": True}, expires_at=datetime.now(UTC) + timedelta(days=30))
    with pytest.raises(Exception) as missing_lineage:
        context.liveforever.create_record(tenant_id=tenant, project_id=project, record_type="generated_reconstruction", subject_id=subject, related_ids=[], data={"title": "Generated"}, source_class=SourceClass.GENERATED, confidence=0.4, evidence_asset_ids=[source.asset_id], audience=Audience.PRIVATE, actor_id="builder", generated_lineage={"model_manifest_id": "synthetic", "model_checkpoint_hash": "a" * 64, "prompt_hash": "b" * 64, "input_asset_ids": ["MISSING-INPUT"], "output_hash": "c" * 64})
    assert getattr(missing_lineage.value, "code", "") == "GENERATED_LINEAGE_INPUT_ASSET_SCOPE"
    record = context.liveforever.create_record(tenant_id=tenant, project_id=project, record_type="generated_reconstruction", subject_id=subject, related_ids=[], data={"title": "Generated"}, source_class=SourceClass.GENERATED, confidence=0.4, evidence_asset_ids=[source.asset_id], audience=Audience.PRIVATE, actor_id="builder", generated_lineage={"model_manifest_id": "synthetic", "model_checkpoint_hash": "a" * 64, "prompt_hash": "b" * 64, "input_asset_ids": [source.asset_id], "output_hash": "c" * 64})
    assert record
