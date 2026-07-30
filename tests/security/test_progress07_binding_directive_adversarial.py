from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from sip.canonical import canonical_sha256, sha256_bytes
from sip.database import (
    AuditEventRow,
    KeyScopeRow,
    OutboxEventRow,
    PrivilegedAccessGrantRow,
    PrivacyRightsRequestRow,
    WorkloadIdentityGrantRow,
)
from sip.errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ValidationError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from tests.progress07_helpers import bootstrap, fresh_now, output_checks, register_provider, valid_rights_outcomes


def _asset(context, tenant: str, project: str, name: str):
    payload = f"progress07:{name}".encode()
    return context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=payload,
        media_type="application/json",
        original_name=f"{name}.json",
        classification=Classification.INTERNAL,
        retention_class="security_evidence",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[f"synthetic:{name}"], output_hash=sha256_bytes(payload)),
        actor_id="security-fixture",
    )


def _approved_model_manifest(model_id: str, checkpoint_hash: str) -> dict:
    reviewed_at = datetime.now(UTC) - timedelta(days=1)
    return {
        "schema": "sip.model-manifest/v1.1",
        "schema_version": "1.1.0",
        "model_id": model_id,
        "provider": "sip.synthetic",
        "model_name": "progress07-adversarial-fixture",
        "version": "1.0.0",
        "revision": "fixture-1",
        "checkpoint_hash": checkpoint_hash,
        "source_urls": [f"local://models/{model_id}"],
        "license_documents": [
            {
                "component": component,
                "title": f"Synthetic {component} license",
                "license_id": "Apache-2.0",
                "source_url": f"local://licenses/{model_id}/{component}",
                "document_sha256": canonical_sha256({"model": model_id, "component": component}),
                "review_state": "verified",
            }
            for component in ("code", "weights", "dataset", "output")
        ],
        "code_revision": "fixture-code-1",
        "code_license": "Apache-2.0",
        "weights_license": "Apache-2.0",
        "dataset_terms": ["synthetic_fixture_only"],
        "output_terms": "Apache-2.0",
        "approval_state": "approved",
        "commercial_use": True,
        "allowed_classifications": ["internal"],
        "permitted_uses": ["security-test"],
        "prohibited_uses": ["biometric_identification"],
        "geographic_restrictions": {"mode": "allowlist", "values": ["local"]},
        "customer_restrictions": {"mode": "allowlist", "values": ["p07-model-tenant"]},
        "allowed_deployments": ["test"],
        "approved_by": "model-reviewer",
        "reviewed_at": reviewed_at,
        "review_due_at": reviewed_at + timedelta(days=365),
        "expires_at": reviewed_at + timedelta(days=365),
    }


def test_progress07_privileged_access_directive_boundaries(tmp_path: Path) -> None:
    """REQ: OPSSEC-001, OPSSEC-002, OPSSEC-006, TSTSEC-001 stale, expired, revoked, replayed, cross-scope, and self-approved privileged grants fail closed with retained audit evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p07-jit-directive")
    other_project = context.tenancy.create_project(
        tenant,
        "other project",
        vertical="platform",
        classification="internal",
        project_id="p07-jit-other-project",
        actor_id="bootstrap",
    )

    with pytest.raises(AuthorizationError, match="fresh MFA"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant,
            project_id=project,
            subject_id="operator",
            actions=["security:incident"],
            resource_scope={"project_id": project, "asset_id": "asset-a"},
            purpose="incident_response",
            mfa_method="webauthn",
            mfa_verified_at=fresh_now() - timedelta(minutes=6),
            duration_seconds=300,
            requested_by="operator",
            approved_by="approver",
        )
    with pytest.raises(AuthorizationError, match="independent"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant,
            project_id=project,
            subject_id="operator",
            actions=["security:incident"],
            resource_scope={"project_id": project},
            purpose="incident_response",
            mfa_method="webauthn",
            mfa_verified_at=fresh_now(),
            duration_seconds=300,
            requested_by="operator",
            approved_by="operator",
        )

    kwargs = dict(
        tenant_id=tenant,
        project_id=project,
        subject_id="operator",
        actions=["security:incident"],
        resource_scope={"project_id": project, "asset_id": "asset-a"},
        purpose="incident_response",
        mfa_method="webauthn",
        mfa_verified_at=fresh_now(),
        duration_seconds=300,
        requested_by="operator",
        approved_by="approver",
    )
    grant = context.security_ops.grant_privileged_access(**kwargs)
    replay = context.security_ops.grant_privileged_access(**kwargs)
    assert replay["grant_id"] == grant["grant_id"]
    assert replay["idempotent_replay"] is True

    allowed = context.security_ops.require_privileged_access(
        grant_id=grant["grant_id"],
        tenant_id=tenant,
        project_id=project,
        subject_id="operator",
        action="security:incident",
        purpose="incident_response",
        resource_scope={"project_id": project, "asset_id": "asset-a"},
    )
    assert allowed["grant_id"] == grant["grant_id"]

    denied_cases = [
        {"tenant_id": "wrong-tenant", "project_id": project, "subject_id": "operator", "action": "security:incident", "purpose": "incident_response", "resource_scope": {"project_id": project, "asset_id": "asset-a"}},
        {"tenant_id": tenant, "project_id": other_project, "subject_id": "operator", "action": "security:incident", "purpose": "incident_response", "resource_scope": {"project_id": other_project, "asset_id": "asset-a"}},
        {"tenant_id": tenant, "project_id": project, "subject_id": "other", "action": "security:incident", "purpose": "incident_response", "resource_scope": {"project_id": project, "asset_id": "asset-a"}},
        {"tenant_id": tenant, "project_id": project, "subject_id": "operator", "action": "security:key_manage", "purpose": "incident_response", "resource_scope": {"project_id": project, "asset_id": "asset-a"}},
        {"tenant_id": tenant, "project_id": project, "subject_id": "operator", "action": "security:incident", "purpose": "other", "resource_scope": {"project_id": project, "asset_id": "asset-a"}},
        {"tenant_id": tenant, "project_id": project, "subject_id": "operator", "action": "security:incident", "purpose": "incident_response", "resource_scope": {"project_id": project, "asset_id": "asset-b"}},
    ]
    for case in denied_cases:
        with pytest.raises(AuthorizationError):
            context.security_ops.require_privileged_access(grant_id=grant["grant_id"], **case)

    with context.database.session() as session:
        row = session.get(PrivilegedAccessGrantRow, grant["grant_id"])
        row.expires_at = fresh_now() - timedelta(seconds=1)
    with pytest.raises(AuthorizationError, match="inactive or expired"):
        context.security_ops.require_privileged_access(
            grant_id=grant["grant_id"], tenant_id=tenant, project_id=project, subject_id="operator",
            action="security:incident", purpose="incident_response",
            resource_scope={"project_id": project, "asset_id": "asset-a"},
        )

    revoke_kwargs = {**kwargs, "resource_scope": {"project_id": project, "asset_id": "asset-revoke"}}
    revocable = context.security_ops.grant_privileged_access(**revoke_kwargs)
    context.security_ops.revoke_privileged_access(grant_id=revocable["grant_id"], tenant_id=tenant, actor_id="approver")
    with pytest.raises(AuthorizationError):
        context.security_ops.require_privileged_access(
            grant_id=revocable["grant_id"], tenant_id=tenant, project_id=project, subject_id="operator",
            action="security:incident", purpose="incident_response",
            resource_scope={"project_id": project, "asset_id": "asset-revoke"},
        )

    with context.database.session() as session:
        grants = list(session.scalars(select(PrivilegedAccessGrantRow).where(PrivilegedAccessGrantRow.tenant_id == tenant)))
        grant_audits = list(session.scalars(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant, AuditEventRow.action == "privileged_access:grant")))
        assert len(grants) == 2
        assert len(grant_audits) == 2
        assert all(event.details_json["purpose"] == "incident_response" for event in grant_audits)


def test_progress07_workload_and_key_directive_boundaries(tmp_path: Path) -> None:
    """REQ: OPSKEY-001, OPSKEY-002, OPSKEY-003, OPSKEY-004, OPSKEY-005, OPSKEY-006, OPSSEC-002, OPSSEC-003, TSTSEC-006 workload and key identities reject wrong workload, expiry, revocation, tampering, and cross-scope access while retaining rotation and erasure lineage."""
    context, tenant, project = bootstrap(tmp_path, name="p07-workload-key")
    other_project = context.tenancy.create_project(
        tenant, "other", vertical="platform", classification="internal",
        project_id="p07-workload-key-other-project", actor_id="bootstrap",
    )
    other_tenant = context.tenancy.create_tenant("other tenant", tenant_id="p07-workload-key-other-tenant", actor_id="bootstrap")
    context.tenancy.create_project(
        other_tenant, "other tenant project", vertical="platform", classification="internal",
        project_id="p07-workload-key-other-tenant-project", actor_id="bootstrap",
    )

    issued = context.security_ops.issue_workload_identity(
        tenant_id=tenant, project_id=project, workload_id="quality-worker", audience="worker-runtime",
        scopes=["asset:read"], purpose="reconstruction", ttl_seconds=120, actor_id="security-officer",
    )
    valid_args = dict(
        audience="worker-runtime", required_scope="asset:read", purpose="reconstruction",
        tenant_id=tenant, project_id=project, workload_id="quality-worker",
    )
    assert context.security_ops.validate_workload_identity(issued["token"], **valid_args)["workload_id"] == "quality-worker"
    for override in (
        {"workload_id": "other-worker"},
        {"audience": "other-runtime"},
        {"purpose": "other"},
        {"tenant_id": other_tenant, "project_id": "p07-workload-key-other-tenant-project"},
        {"project_id": other_project},
        {"required_scope": "asset:write"},
    ):
        with pytest.raises(AuthorizationError):
            context.security_ops.validate_workload_identity(issued["token"], **{**valid_args, **override})
    tampered = issued["token"][:-1] + ("A" if issued["token"][-1] != "A" else "B")
    with pytest.raises((AuthenticationError, AuthorizationError, ValidationError)):
        context.security_ops.validate_workload_identity(tampered, **valid_args)
    with context.database.session() as session:
        row = session.get(WorkloadIdentityGrantRow, issued["grant_id"])
        row.expires_at = fresh_now() - timedelta(seconds=1)
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(issued["token"], **valid_args)

    revoked = context.security_ops.issue_workload_identity(
        tenant_id=tenant, project_id=project, workload_id="revoked-worker", audience="worker-runtime",
        scopes=["asset:read"], purpose="reconstruction", ttl_seconds=120, actor_id="security-officer",
    )
    context.security_ops.revoke_workload_identity(grant_id=revoked["grant_id"], tenant_id=tenant, actor_id="security-officer")
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            revoked["token"], audience="worker-runtime", required_scope="asset:read", purpose="reconstruction",
            tenant_id=tenant, project_id=project, workload_id="revoked-worker",
        )

    recovery = {"guardians": ["custodian-a", "custodian-b"], "quorum": 2, "single_person_recovery": False}
    key_v1 = context.security_ops.register_key_scope(
        tenant_id=tenant, project_id=project, person_id=None, key_id="p07-key-v1",
        backend="managed_kms", recovery_policy=recovery, actor_id="custodian-a",
    )
    with pytest.raises(NotFoundError):
        context.security_ops.record_key_access(
            key_scope_id=key_v1["key_scope_id"], tenant_id=tenant, project_id=other_project,
            actor_or_workload="quality-worker", purpose="test", action="unwrap",
            resource_scope={"asset_id": "asset-a"}, outcome="allowed",
        )
    with pytest.raises(ConflictError):
        context.security_ops.register_key_scope(
            tenant_id=tenant, project_id=other_project, person_id=None, key_id="p07-key-cross-scope",
            backend="managed_kms", recovery_policy=recovery, actor_id="custodian-a",
            rotated_from_key_id="p07-key-v1",
        )
    key_v2 = context.security_ops.register_key_scope(
        tenant_id=tenant, project_id=project, person_id=None, key_id="p07-key-v2",
        backend="managed_kms", recovery_policy=recovery, actor_id="custodian-b",
        rotated_from_key_id="p07-key-v1",
    )
    with context.database.session() as session:
        prior = session.scalar(select(KeyScopeRow).where(KeyScopeRow.key_id == "p07-key-v1"))
        current = session.scalar(select(KeyScopeRow).where(KeyScopeRow.key_id == "p07-key-v2"))
        assert prior.state == "rotated"
        assert current.rotated_from_key_id == "p07-key-v1"
    with pytest.raises(NotFoundError):
        context.security_ops.emergency_revoke_key(
            key_scope_id=key_v2["key_scope_id"], tenant_id=tenant, project_id=other_project,
            actor_id="custodian-b", reason="synthetic compromise",
            residual_timeline=[{"store": "backup", "expires_at": (fresh_now() + timedelta(days=30)).isoformat()}],
        )
    revoked_key = context.security_ops.emergency_revoke_key(
        key_scope_id=key_v2["key_scope_id"], tenant_id=tenant, project_id=project,
        actor_id="custodian-b", reason="synthetic compromise",
        residual_timeline=[{"store": "backup", "expires_at": (fresh_now() + timedelta(days=30)).isoformat()}],
    )
    retained = {key: value for key, value in revoked_key.items() if key != "erasure_evidence_hash"}
    assert canonical_sha256(retained) == revoked_key["erasure_evidence_hash"]
    with pytest.raises(ValidationError, match="quorum"):
        context.security_ops.register_key_scope(
            tenant_id=tenant, project_id=project, person_id=None, key_id="p07-key-invalid",
            backend="managed_kms", recovery_policy={"guardians": ["one"], "quorum": 1, "single_person_recovery": True}, actor_id="one",
        )


def test_progress07_privacy_rights_directive_boundaries(tmp_path: Path) -> None:
    """REQ: OPSPRIV-003, OPSPRIV-004, OPSPRIV-006 subject-rights processing is idempotent, cross-tenant denied, complete across every store, and explicit about legal-hold and consent conflicts with immutable reviewer lineage."""
    context, tenant, project = bootstrap(tmp_path, name="p07-rights-directive")
    other_tenant = context.tenancy.create_tenant("other tenant", tenant_id="p07-rights-other-tenant", actor_id="bootstrap")
    other_project = context.tenancy.create_project(other_tenant, "other", vertical="platform", classification="internal", project_id="p07-rights-other-project", actor_id="bootstrap")
    request = context.security_ops.create_rights_workflow(
        tenant_id=tenant, project_id=project, subject_id="subject-a", request_type="deletion",
        scope={"all_subject_data": True, "consent_state": "revoked"}, requested_by="subject-a", verified_by="privacy-verifier",
    )
    incomplete = valid_rights_outcomes()
    incomplete.pop("exports")
    with pytest.raises(ValidationError, match="exactly every governed store"):
        context.security_ops.complete_rights_workflow(
            rights_request_id=request["rights_request_id"], tenant_id=tenant, project_id=project,
            outcomes=incomplete, evidence=[{"reference": "incomplete", "sha256": sha256_bytes(b"incomplete")}], completed_by="privacy-officer",
        )
    with pytest.raises(NotFoundError):
        context.security_ops.complete_rights_workflow(
            rights_request_id=request["rights_request_id"], tenant_id=other_tenant, project_id=other_project,
            outcomes=valid_rights_outcomes(), evidence=[{"reference": "cross", "sha256": sha256_bytes(b"cross")}], completed_by="privacy-officer",
        )
    legal_hold_missing = valid_rights_outcomes()
    legal_hold_missing["backups"] = {"state": "retained_legal_hold", "evidence_hash": sha256_bytes(b"hold")}
    with pytest.raises(ValidationError, match="legal-hold"):
        context.security_ops.complete_rights_workflow(
            rights_request_id=request["rights_request_id"], tenant_id=tenant, project_id=project,
            outcomes=legal_hold_missing, evidence=[{"reference": "hold", "sha256": sha256_bytes(b"hold")}], completed_by="privacy-officer",
        )
    outcomes = valid_rights_outcomes()
    outcomes["backups"] = {
        "state": "retained_legal_hold",
        "evidence_hash": sha256_bytes(b"hold-evidence"),
        "legal_hold_id": "hold-123",
        "conflict_type": "legal_hold",
    }
    evidence = [{"reference": "rights-complete", "sha256": sha256_bytes(b"rights-complete")}]
    completed = context.security_ops.complete_rights_workflow(
        rights_request_id=request["rights_request_id"], tenant_id=tenant, project_id=project,
        outcomes=outcomes, evidence=evidence, completed_by="privacy-officer",
    )
    replay = context.security_ops.complete_rights_workflow(
        rights_request_id=request["rights_request_id"], tenant_id=tenant, project_id=project,
        outcomes=outcomes, evidence=evidence, completed_by="privacy-officer",
    )
    assert completed["state"] == "completed"
    assert replay["idempotent_replay"] is True
    with context.database.session() as session:
        row = session.get(PrivacyRightsRequestRow, request["rights_request_id"])
        assert row.verified_by == "privacy-verifier"
        assert row.verification_json["completed_by"] == "privacy-officer"
        assert row.response_manifest_json["backups"]["legal_hold_id"] == "hold-123"


def test_progress07_audit_integrity_and_denial_durability(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSAUDIT-004, OPSAUDIT-005, TSTSEC-004 audit verification detects gaps, hashes, signatures, and manifest drift while provider denial evidence survives the rejected transaction."""
    def context_with_events(name: str):
        context, tenant, project = bootstrap(tmp_path, name=name)
        for index in range(3):
            context.audit.append(
                tenant_id=tenant, project_id=project, actor_id="auditor", action=f"synthetic:{index}",
                resource_type="fixture", resource_id=str(index), outcome="allowed", details={"index": index},
            )
        return context, tenant, project

    context, tenant, _ = context_with_events("p07-audit-gap")
    with context.database.session() as session:
        rows = list(session.scalars(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant).order_by(AuditEventRow.occurred_at, AuditEventRow.audit_id)))
        session.delete(rows[1])
    with pytest.raises(ValidationError, match="chain verification failed"):
        context.audit.verify(tenant)

    context, tenant, _ = context_with_events("p07-audit-hash")
    with context.database.session() as session:
        row = session.scalar(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant).order_by(AuditEventRow.occurred_at).limit(1))
        row.event_hash = "0" * 64
    with pytest.raises(ValidationError, match="chain verification failed"):
        context.audit.verify(tenant)

    context, tenant, _ = context_with_events("p07-audit-signature")
    with context.database.session() as session:
        row = session.scalar(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant).order_by(AuditEventRow.occurred_at).limit(1))
        row.signature = base64.b64encode(b"invalid-signature").decode()
    with pytest.raises(ValidationError, match="chain verification failed"):
        context.audit.verify(tenant)

    context, tenant, project = bootstrap(tmp_path, name="p07-audit-manifest")
    missing = context.security_ops.verify_audit_chain(
        tenant_id=tenant, project_id=project,
        referenced_manifests=[{"asset_id": "missing", "sha256": "a" * 64}], verifier_id="auditor",
    )
    assert missing["valid"] is False
    assert missing["findings"][0]["code"] == "AUDIT_MANIFEST_REFERENCE_MISSING_OR_MISMATCHED"
    asset = _asset(context, tenant, project, "manifest")
    mismatch = context.security_ops.verify_audit_chain(
        tenant_id=tenant, project_id=project,
        referenced_manifests=[{"asset_id": asset.asset_id, "sha256": "b" * 64}], verifier_id="auditor",
    )
    assert mismatch["valid"] is False

    provider_id = register_provider(context, provider_id="p07-denial-provider")
    with pytest.raises(AuthorizationError):
        context.security_ops.authorize_provider_execution(
            provider_id=provider_id, tenant_id=tenant, project_id=project,
            classification="internal", purpose="reconstruction", region="other", external=False,
        )
    with context.database.session() as session:
        assert session.scalar(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant, AuditEventRow.action == "provider:authorize", AuditEventRow.outcome == "denied")) is not None
        assert session.scalar(select(OutboxEventRow).where(OutboxEventRow.tenant_id == tenant, OutboxEventRow.event_type == "provider.execution.denied")) is not None


def test_progress07_provider_model_and_runtime_directive_boundaries(tmp_path: Path) -> None:
    """REQ: OPSSEC-003, OPSSEC-004, OPSTHR-008, OPSTHR-011, OPSTHR-012, SECEXT-001, SECEXT-002, SECEXT-003, SECEXT-004, SECEXT-005, SECEXT-009, SECEXT-010, SECEXT-011, SECEXT-012, SECEXT-013, SECEXT-014, SECEXT-015, SECEXT-016 providers and models fail closed for missing approval, checkpoint, policy, retention, audience, egress, quarantine, incident, exception, and immersive-safety violations."""
    context, tenant, project = bootstrap(tmp_path, name="p07-provider-directive")
    with pytest.raises(NotFoundError):
        context.security_ops.authorize_provider_execution(
            provider_id="missing", tenant_id=tenant, project_id=project,
            classification="internal", purpose="reconstruction", region="local", external=False,
        )
    context.providers.register(
        {
            "provider_id": "denied-provider", "version": "1.0.0", "source_url": "local://denied",
            "source_revision": "a" * 40, "license_id": "Apache-2.0", "approval_state": "denied",
            "allowed_classifications": ["internal"], "allowed_purposes": ["reconstruction"],
            "allowed_regions": ["local"], "deployments": ["local"], "retention_days": 0,
            "output_rights": "commercial_derivatives_allowed",
        }, actor_id="governance",
    )
    with pytest.raises(AuthorizationError):
        context.security_ops.authorize_provider_execution(
            provider_id="denied-provider", tenant_id=tenant, project_id=project,
            classification="internal", purpose="reconstruction", region="local", external=False,
        )
    provider_id = register_provider(context, provider_id="p07-policy-provider")
    provider_request = {
        "provider_id": provider_id,
        "tenant_id": tenant,
        "project_id": project,
        "classification": "internal",
        "purpose": "reconstruction",
        "region": "local",
        "external": False,
        "audience": "private",
        "retention_days": 0,
    }
    for override in (
        {"classification": "restricted"},
        {"purpose": "other"},
        {"region": "other"},
        {"audience": "public"},
        {"retention_days": 1},
        {"external": True},
    ):
        with pytest.raises(AuthorizationError):
            context.security_ops.authorize_provider_execution(**{**provider_request, **override})

    checkpoint = sha256_bytes(b"p07-model")
    context.models.register(_approved_model_manifest("p07-model", checkpoint), actor_id="model-reviewer")
    with pytest.raises(AuthorizationError) as wrong_checkpoint:
        context.models.authorize(
            "p07-model", checkpoint_hash="0" * 64, purpose="security-test", commercial=True,
            classification=Classification.INTERNAL, deployment="test", region="local", customer_id="p07-model-tenant",
        )
    assert "checkpoint_hash_mismatch" in wrong_checkpoint.value.details["reasons"]
    with pytest.raises(AuthorizationError):
        context.models.authorize(
            "p07-model", checkpoint_hash=checkpoint, purpose="other", commercial=True,
            classification=Classification.INTERNAL, deployment="test", region="local", customer_id="p07-model-tenant",
        )

    output_hash, checks = output_checks()
    checks["quarantine_write_only"]["workspace_policy"] = "read_write"
    with pytest.raises(ValidationError, match="write-only staging"):
        context.security_ops.validate_provider_output(
            tenant_id=tenant, project_id=project, provider_id=provider_id, operation_id="op-quarantine-denied",
            output_sha256=output_hash, media_type="application/octet-stream", byte_count=26,
            validations=checks, validated_by="security-reviewer",
        )
    output_hash, checks = output_checks()
    checks["malware_scan"]["passed"] = False
    rejected = context.security_ops.validate_provider_output(
        tenant_id=tenant, project_id=project, provider_id=provider_id, operation_id="op-rejected",
        output_sha256=output_hash, media_type="application/octet-stream", byte_count=26,
        validations=checks, validated_by="security-reviewer",
    )
    assert rejected["state"] == "rejected_quarantined"

    withdrawal = context.security_ops.record_provider_incident_withdrawal(
        tenant_id=tenant, project_id=project, provider_id=provider_id,
        source_asset_ids=["source"], derivative_asset_ids=["derivative"], publication_ids=["publication"],
        cache_resource_ids=["cache"], export_ids=["export"],
        evidence=[{"reference": "incident", "sha256": sha256_bytes(b"incident")}],
        notification_decision={"notify": False, "rationale": "synthetic"}, actor_id="security-officer",
    )
    assert withdrawal["investigation_evidence_preserved"] is True
    for waiver in ("truth", "consent", "legal_hold", "authority", "tenant_isolation", "evidence_integrity"):
        with pytest.raises(AuthorizationError):
            context.security_ops.create_provider_exception(
                tenant_id=tenant, project_id=project, provider_id=provider_id,
                scope={"operation": "test"}, purpose="reconstruction", requested_waivers=[waiver],
                approved_by="security-officer", duration_seconds=300,
            )

    decision = context.security_ops.evaluate_immersive_safety(
        tenant_id=tenant, project_id=project, scene_id="scene-a",
        checks={
            "accepted_scale": True,
            "walkability": False,
            "openings": True,
            "stairs_and_falls": True,
            "safe_spawn": True,
            "safe_exit": False,
        },
        requested_modes=["walk", "fly", "teleport", "guided", "orbit"], actor_id="safety-reviewer",
    )
    assert decision["state"] == "degraded_safe"
    assert decision["fallback_mode"] == "orbit"
    assert set(decision["disabled_modes"]) >= {"walk", "fly", "teleport", "guided"}
