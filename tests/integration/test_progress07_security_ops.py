from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.canonical import sha256_bytes
from sip.database import CacheInvalidationRow, OutboxEventRow, SecurityIncidentRow, SupplyChainReleaseRow
from sip.errors import AuthorizationError, ConflictError, ValidationError
from tests.progress07_helpers import bootstrap, fresh_now, output_checks, register_provider, threat_payload, valid_rights_outcomes


def test_progress07_threat_manifest_jit_and_workload_identity(tmp_path: Path) -> None:
    """REQ: OPSSEC-001, OPSSEC-002, OPSSEC-003, OPSSEC-006, OPSSRE-006, OPSTHR-007, OPSTHREA-001, OPSTHREA-002, OPSTHREA-003, OPSTHREA-004, OPSTHREA-005, OPSTHREA-006, SECEXT-001, SECEXT-002, TSTSEC-006 threat modeling, independently approved JIT access, and short-lived scoped workload identity fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p07-identity")
    threat = context.security_ops.register_threat_manifest(**threat_payload(), actor_id="security-officer")
    assert threat["version"] == 1 and threat["state"] == "active"
    assert context.security_ops.register_threat_manifest(**threat_payload(), actor_id="security-officer")["idempotent_replay"] is True

    with pytest.raises(ValidationError, match="critical threat catalog"):
        bad = threat_payload(); bad["threats"] = bad["threats"][:-1]
        context.security_ops.register_threat_manifest(**bad, actor_id="security-officer")
    with pytest.raises(AuthorizationError, match="phishing-resistant"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant, project_id=project, subject_id="operator", actions=["security:incident"],
            resource_scope={"project_id": project}, purpose="incident_response", mfa_method="sms",
            mfa_verified_at=fresh_now(), duration_seconds=300, requested_by="operator", approved_by="approver",
        )
    with pytest.raises(AuthorizationError, match="independent approval"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant, project_id=project, subject_id="operator", actions=["security:incident"],
            resource_scope={"project_id": project}, purpose="incident_response", mfa_method="webauthn",
            mfa_verified_at=fresh_now(), duration_seconds=300, requested_by="operator", approved_by="operator",
        )
    grant = context.security_ops.grant_privileged_access(
        tenant_id=tenant, project_id=project, subject_id="operator", actions=["security:incident"],
        resource_scope={"project_id": project}, purpose="incident_response", mfa_method="webauthn",
        mfa_verified_at=fresh_now(), duration_seconds=300, requested_by="operator", approved_by="approver",
    )
    assert context.security_ops.require_privileged_access(
        grant_id=grant["grant_id"], tenant_id=tenant, project_id=project, subject_id="operator",
        action="security:incident", purpose="incident_response", resource_scope={"project_id": project},
    )["grant_id"] == grant["grant_id"]
    with pytest.raises(AuthorizationError):
        context.security_ops.require_privileged_access(
            grant_id=grant["grant_id"], tenant_id=tenant, project_id=project, subject_id="operator",
            action="security:key_manage", purpose="incident_response", resource_scope={"project_id": project},
        )
    context.security_ops.revoke_privileged_access(grant_id=grant["grant_id"], tenant_id=tenant, actor_id="approver")
    with pytest.raises(AuthorizationError):
        context.security_ops.require_privileged_access(
            grant_id=grant["grant_id"], tenant_id=tenant, project_id=project, subject_id="operator",
            action="security:incident", purpose="incident_response", resource_scope={"project_id": project},
        )

    issued = context.security_ops.issue_workload_identity(
        tenant_id=tenant, project_id=project, workload_id="quality-worker", audience="worker-runtime",
        scopes=["asset:read", "operation:lease"], purpose="reconstruction", ttl_seconds=120,
        actor_id="security-officer",
    )
    validated = context.security_ops.validate_workload_identity(
        issued["token"], audience="worker-runtime", required_scope="asset:read", purpose="reconstruction",
        tenant_id=tenant, project_id=project, workload_id="quality-worker",
    )
    assert validated["workload_id"] == "quality-worker"
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            issued["token"], audience="wrong-audience", required_scope="asset:read", purpose="reconstruction",
            tenant_id=tenant, project_id=project, workload_id="quality-worker",
        )
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            issued["token"], audience="worker-runtime", required_scope="asset:delete", purpose="reconstruction",
            tenant_id=tenant, project_id=project, workload_id="quality-worker",
        )
    context.security_ops.revoke_workload_identity(grant_id=issued["grant_id"], tenant_id=tenant, actor_id="security-officer")
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            issued["token"], audience="worker-runtime", required_scope="asset:read", purpose="reconstruction",
            tenant_id=tenant, project_id=project, workload_id="quality-worker",
        )


def test_progress07_key_governance_privacy_rights_and_incidents(tmp_path: Path) -> None:
    """REQ: OPSKEY-001, OPSKEY-002, OPSKEY-003, OPSKEY-004, OPSKEY-005, OPSKEY-006, OPSPRIV-001, OPSPRIV-002, OPSPRIV-003, OPSPRIV-004, OPSPRIV-006 key lifecycle, privacy inventory, independent rights verification, complete store outcomes, and incident response are durable."""
    context, tenant, project = bootstrap(tmp_path, name="p07-privacy")
    key = context.security_ops.register_key_scope(
        tenant_id=tenant, project_id=project, person_id=None, key_id="kms-project-v1", backend="managed_kms",
        recovery_policy={"guardians": ["custodian-a", "custodian-b"], "quorum": 2, "single_person_recovery": False},
        actor_id="custodian-a",
    )
    assert key["state"] == "active"
    access = context.security_ops.record_key_access(
        key_scope_id=key["key_scope_id"], tenant_id=tenant, project_id=project,
        actor_or_workload="workload:quality", purpose="decrypt_capture", action="unwrap",
        resource_scope={"asset_id": "asset-a"}, outcome="allowed",
    )
    assert len(access["event_hash"]) == 64
    with pytest.raises(ValidationError):
        context.security_ops.register_key_scope(
            tenant_id=tenant, project_id=project, person_id=None, key_id="bad-key", backend="managed_kms",
            recovery_policy={"guardians": ["one"], "quorum": 1, "single_person_recovery": True}, actor_id="one",
        )
    revoked = context.security_ops.emergency_revoke_key(
        key_scope_id=key["key_scope_id"], tenant_id=tenant, project_id=project, actor_id="custodian-b",
        reason="synthetic compromise exercise", residual_timeline=[{"store": "backup", "expires_at": (fresh_now() + timedelta(days=30)).isoformat()}],
    )
    assert revoked["erasure_evidence_hash"]

    inventory = context.security_ops.register_privacy_inventory(
        tenant_id=tenant, project_id=project, data_category="spatial_capture", purpose="privacy",
        legal_basis="contract", consent_basis="project_authorization",
        processors=[{"name": "local", "approved_purposes": ["privacy"], "training_allowed": False}],
        residency={"regions": ["local"], "transfer_policy": "deny"},
        retention={"policy": "project-v1", "minimum_days": 30},
        security_controls=["envelope_encryption", "purpose_authorization"],
        rights_workflow={"contact": "privacy@example.invalid", "types": ["access", "deletion"]},
        classification="internal", actor_id="privacy-officer",
    )
    assert inventory["state"] == "active"
    impact = context.security_ops.assess_privacy_change(
        tenant_id=tenant, project_id=project, change_type="data_purpose", change_reference="vector-v2",
        purpose="privacy", data_categories=["spatial_capture"], processors=["local"],
        risks=[{"risk": "linkability", "severity": "moderate"}],
        controls=[{"control": "purpose_scoped_index", "owner": "privacy"}], residual_risk="low",
        decision="approved", reviewer_id="privacy-reviewer",
    )
    assert impact["decision"] == "approved"
    with pytest.raises(AuthorizationError):
        context.security_ops.create_rights_workflow(
            tenant_id=tenant, project_id=project, subject_id="subject-a", request_type="deletion",
            scope={"all_subject_data": True}, requested_by="same-person", verified_by="same-person",
        )
    rights = context.security_ops.create_rights_workflow(
        tenant_id=tenant, project_id=project, subject_id="subject-a", request_type="deletion",
        scope={"all_subject_data": True}, requested_by="subject-a", verified_by="privacy-verifier",
    )
    outcomes = valid_rights_outcomes()
    evidence = [{"reference": "rights-run-1", "sha256": sha256_bytes(b"rights-run-1")}]
    completed = context.security_ops.complete_rights_workflow(
        rights_request_id=rights["rights_request_id"], tenant_id=tenant, project_id=project,
        outcomes=outcomes, evidence=evidence, completed_by="privacy-officer",
    )
    assert completed["state"] == "completed"
    assert context.security_ops.complete_rights_workflow(
        rights_request_id=rights["rights_request_id"], tenant_id=tenant, project_id=project,
        outcomes=outcomes, evidence=evidence, completed_by="privacy-officer",
    )["idempotent_replay"] is True

    incident = context.security_ops.record_incident(
        tenant_id=tenant, project_id=project, incident_type="access_anomaly", severity="high",
        affected_subjects=["subject-a", "subject-a"],
        affected_resources=[{"resource_type": "asset", "resource_id": "asset-a"}],
        containment=[{"action": "revoke_credentials"}],
        notification_decision={"notify": False, "rationale": "synthetic exercise"},
        evidence=[{"reference": "incident-evidence", "sha256": sha256_bytes(b"incident")}],
        actor_id="incident-commander",
    )
    assert incident["state"] == "open"
    with context.database.session() as session:
        row = session.get(SecurityIncidentRow, incident["incident_id"])
        assert row.affected_subjects_json == ["subject-a"]


def test_progress07_audit_provider_cache_and_supply_chain_controls(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSAUDIT-004, OPSAUDIT-005, OPSCICD-001, OPSCICD-002, OPSCICD-003, OPSCICD-004, OPSCICD-005, OPSCICD-006, OPSTHR-011, SECEXT-003, SECEXT-004, SECEXT-005, SECEXT-009, SECEXT-010, SECEXT-011, SECEXT-012, SECEXT-013, SECEXT-015, SECEXT-016 audit verification, provider governance, cache invalidation, incident withdrawal, and release promotion fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p07-provider")
    provider_id = register_provider(context)
    denied = context.security_ops.authorize_provider_execution(
        provider_id=provider_id, tenant_id=tenant, project_id=project, classification="internal",
        purpose="reconstruction", region="local", external=False, telemetry={"frames": 12},
    )
    assert denied["authorized"] is True
    with pytest.raises(AuthorizationError):
        context.security_ops.authorize_provider_execution(
            provider_id=provider_id, tenant_id=tenant, project_id=project, classification="internal",
            purpose="reconstruction", region="local", external=True, telemetry={"frames": 12},
        )
    with pytest.raises(ValidationError):
        context.security_ops.authorize_provider_execution(
            provider_id=provider_id, tenant_id=tenant, project_id=project, classification="internal",
            purpose="reconstruction", region="local", external=False, telemetry={"precise_location": "secret"},
        )
    invalidation = context.security_ops.invalidate_caches(
        tenant_id=tenant, project_id=project, resource_id="asset-a", reason="consent_revoked",
        targets=["search", "vector", "viewer", "cdn", "signed_urls", "agent_cache", "exports"], actor_id="privacy-officer",
    )
    assert invalidation["state"] == "completed"
    withdrawal = context.security_ops.record_provider_incident_withdrawal(
        tenant_id=tenant, project_id=project, provider_id=provider_id,
        source_asset_ids=["source-a"], derivative_asset_ids=["derivative-a"], publication_ids=["publication-a"],
        cache_resource_ids=["cache-a"], export_ids=["export-a"],
        evidence=[{"reference": "provider-incident", "sha256": sha256_bytes(b"provider-incident")}],
        notification_decision={"notify": False, "rationale": "synthetic exercise"}, actor_id="security-officer",
    )
    assert withdrawal["investigation_evidence_preserved"] is True

    audit = context.security_ops.verify_audit_chain(tenant_id=tenant, project_id=project, referenced_manifests=[], verifier_id="auditor")
    assert audit["valid"] is True
    release = context.security_ops.create_release_record(
        version="1.1.0-progress07", source_commit="a" * 40, source_root="b" * 64,
        component_manifests={name: {"sha256": sha256_bytes(name.encode()), "signature": "sig"} for name in ["mobile", "web", "services", "workers", "infrastructure", "models", "schemas", "database"]},
        evidence={name: {"control_status": "passed_complete"} for name in ["tests", "security", "privacy", "license", "sbom", "benchmarks", "migrations", "backup_restore", "acceptance"]},
        rollback_plan={"services": "previous digests", "workers": "prior manifests", "configuration": "restore snapshot", "database_compatibility": "append-only compatible"},
        environment_policy={"production_authorized": False}, signed_by="release-manager",
    )
    assert release["state"] == "candidate"
    with pytest.raises(AuthorizationError):
        context.security_ops.promote_release(release_record_id=release["release_record_id"], actor_id="release-manager")
    with context.database.session() as session:
        assert session.scalar(select(SupplyChainReleaseRow).where(SupplyChainReleaseRow.release_record_id == release["release_record_id"])).state == "candidate"
        assert session.scalar(select(CacheInvalidationRow).where(CacheInvalidationRow.invalidation_id == invalidation["invalidation_id"])) is not None
        assert session.scalar(select(OutboxEventRow).where(OutboxEventRow.event_type == "provider.execution.denied")) is not None
