from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.canonical import sha256_bytes
from sip.database import (
    AuditEventRow,
    CacheInvalidationRow,
    OutboxEventRow,
    ProviderOutputValidationRow,
    SecurityIncidentRow,
)
from sip.errors import AuthenticationError, AuthorizationError, ValidationError
from tests.progress07_helpers import bootstrap, fresh_now, output_checks, register_provider, threat_payload


def test_progress07_events_are_bounded_and_owned_by_security_service(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSSEC-006, SECEXT-005 Progress 07 security decisions emit bounded, attributable security-ops events without credential material."""
    context, tenant, project = bootstrap(tmp_path, name="p07-events")
    context.security_ops.register_threat_manifest(**threat_payload(), actor_id="security-officer")
    context.security_ops.issue_workload_identity(
        tenant_id=tenant,
        project_id=project,
        workload_id="quality-worker",
        audience="worker-runtime",
        scopes=["asset:read"],
        purpose="reconstruction",
        ttl_seconds=120,
        actor_id="security-officer",
    )
    with context.database.session() as session:
        events = list(session.scalars(select(OutboxEventRow).order_by(OutboxEventRow.occurred_at)))
    assert events
    security_events = [event for event in events if event.producer == "security-ops"]
    assert len(security_events) >= 2
    catalog = json.loads((Path(__file__).resolve().parents[2] / "schemas/events/event-catalog.json").read_text(encoding="utf-8"))
    owners = {entry["type"]: entry["owner"] for entry in catalog["events"]}
    for event in security_events:
        assert owners[event.event_type] == "security-ops"
        encoded = json.dumps(event.payload_json, sort_keys=True)
        assert len(encoded.encode()) < 64 * 1024
        lowered = encoded.lower()
        assert "password" not in lowered
        assert "private_key" not in lowered
        assert "bearer" not in lowered
        assert "token" not in lowered


def test_progress07_jit_and_workload_identity_adversarial_boundaries(tmp_path: Path) -> None:
    """REQ: OPSSEC-001, OPSSEC-002, OPSSEC-003, OPSSEC-006, SECEXT-001, SECEXT-002, TSTSEC-001, TSTSEC-006 JIT access and workload credentials reject stale, broad, tampered, revoked, and cross-scope use."""
    context, tenant, project = bootstrap(tmp_path, name="p07-identity-adversarial")
    other_tenant = context.tenancy.create_tenant("other tenant", tenant_id="p07-other-tenant", actor_id="bootstrap")
    other_project = context.tenancy.create_project(other_tenant, "other project", vertical="platform", classification="internal", project_id="p07-other-project", actor_id="bootstrap")

    with pytest.raises(AuthorizationError, match="fresh MFA"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant,
            project_id=project,
            subject_id="operator",
            actions=["security:incident"],
            resource_scope={"project_id": project, "workload_id": "quality-worker"},
            purpose="incident_response",
            mfa_method="webauthn",
            mfa_verified_at=fresh_now() - timedelta(minutes=10),
            duration_seconds=300,
            requested_by="operator",
            approved_by="approver",
        )
    with pytest.raises(ValidationError, match="explicit bounded actions"):
        context.security_ops.grant_privileged_access(
            tenant_id=tenant,
            project_id=project,
            subject_id="operator",
            actions=["*"],
            resource_scope={"project_id": project, "workload_id": "quality-worker"},
            purpose="incident_response",
            mfa_method="webauthn",
            mfa_verified_at=fresh_now(),
            duration_seconds=300,
            requested_by="operator",
            approved_by="approver",
        )

    issued = context.security_ops.issue_workload_identity(
        tenant_id=tenant,
        project_id=project,
        workload_id="quality-worker",
        audience="worker-runtime",
        scopes=["asset:read", "operation:lease"],
        purpose="reconstruction",
        ttl_seconds=120,
        actor_id="security-officer",
    )
    for wrong in (
        {"audience": "other-runtime", "required_scope": "asset:read", "purpose": "reconstruction", "tenant_id": tenant, "project_id": project, "workload_id": "quality-worker"},
        {"audience": "worker-runtime", "required_scope": "asset:write", "purpose": "reconstruction", "tenant_id": tenant, "project_id": project, "workload_id": "quality-worker"},
        {"audience": "worker-runtime", "required_scope": "asset:read", "purpose": "other", "tenant_id": tenant, "project_id": project, "workload_id": "quality-worker"},
        {"audience": "worker-runtime", "required_scope": "asset:read", "purpose": "reconstruction", "tenant_id": other_tenant, "project_id": other_project, "workload_id": "quality-worker"},
    ):
        with pytest.raises(AuthorizationError):
            context.security_ops.validate_workload_identity(issued["token"], **wrong)
    tampered = issued["token"][:-1] + ("A" if issued["token"][-1] != "A" else "B")
    with pytest.raises((AuthenticationError, AuthorizationError, ValidationError)):
        context.security_ops.validate_workload_identity(
            tampered,
            audience="worker-runtime",
            required_scope="asset:read",
            purpose="reconstruction",
            tenant_id=tenant,
            project_id=project,
            workload_id="quality-worker",
        )
    context.security_ops.revoke_workload_identity(grant_id=issued["grant_id"], tenant_id=tenant, actor_id="security-officer")
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            issued["token"],
            audience="worker-runtime",
            required_scope="asset:read",
            purpose="reconstruction",
            tenant_id=tenant,
            project_id=project,
            workload_id="quality-worker",
        )


def test_progress07_provider_output_quarantine_and_immersive_fallback(tmp_path: Path) -> None:
    """REQ: OPSTHR-008, OPSTHR-012, SECEXT-003, SECEXT-004, SECEXT-005, SECEXT-009, SECEXT-015 provider outputs remain quarantined and unsafe immersive modes degrade to a safe fallback."""
    context, tenant, project = bootstrap(tmp_path, name="p07-output")
    provider_id = register_provider(context)
    output_hash, checks = output_checks()
    checks["malware_scan"]["passed"] = False
    checks["malware_scan"]["detail"] = "synthetic signature"
    rejected = context.security_ops.validate_provider_output(
        tenant_id=tenant,
        project_id=project,
        provider_id=provider_id,
        operation_id="operation-rejected",
        output_sha256=output_hash,
        media_type="application/octet-stream",
        byte_count=26,
        validations=checks,
        validated_by="security-officer",
    )
    assert rejected["state"] == "rejected_quarantined"
    assert rejected["findings"]

    output_hash, checks = output_checks(b"accepted-output")
    accepted = context.security_ops.validate_provider_output(
        tenant_id=tenant,
        project_id=project,
        provider_id=provider_id,
        operation_id="operation-accepted",
        output_sha256=output_hash,
        media_type="application/octet-stream",
        byte_count=len(b"accepted-output"),
        validations=checks,
        validated_by="security-officer",
    )
    assert accepted["state"] == "validated_quarantined"
    with context.database.session() as session:
        row = session.get(ProviderOutputValidationRow, accepted["output_validation_id"])
        assert row.state == "validated_quarantined"

    unsafe = context.security_ops.evaluate_immersive_safety(
        tenant_id=tenant,
        project_id=project,
        scene_id="scene-a",
        checks={
            "accepted_scale": True,
            "walkability": False,
            "openings": True,
            "stairs_and_falls": True,
            "safe_spawn": True,
            "safe_exit": True,
        },
        requested_modes=["orbit", "walk", "teleport", "fly"],
        actor_id="scene-reviewer",
    )
    assert unsafe["state"] == "degraded_safe"
    assert set(unsafe["disabled_modes"]) == {"walk", "teleport", "fly"}
    assert unsafe["fallback_mode"] == "orbit"


def test_progress07_provider_policy_exception_cache_and_telemetry_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSPRIV-004, OPSPRIV-006, OPSTHR-011, SECEXT-001, SECEXT-002, SECEXT-003, SECEXT-005, SECEXT-006, SECEXT-008, SECEXT-010, SECEXT-011, SECEXT-012, SECEXT-013, SECEXT-014, SECEXT-016 provider policy, exceptions, telemetry, and derivative invalidation fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p07-provider-policy")
    provider_id = register_provider(context)
    assert context.security_ops.authorize_provider_execution(
        provider_id=provider_id,
        tenant_id=tenant,
        project_id=project,
        classification="internal",
        purpose="reconstruction",
        region="local",
        external=False,
        telemetry={"frames": 5, "latency_ms": 20},
    )["authorized"] is True
    with pytest.raises(AuthorizationError, match="local-only"):
        context.security_ops.authorize_provider_execution(
            provider_id=provider_id,
            tenant_id=tenant,
            project_id=project,
            classification="internal",
            purpose="reconstruction",
            region="local",
            external=True,
            telemetry={},
        )
    with pytest.raises(ValidationError, match="telemetry"):
        context.security_ops.authorize_provider_execution(
            provider_id=provider_id,
            tenant_id=tenant,
            project_id=project,
            classification="internal",
            purpose="reconstruction",
            region="local",
            external=False,
            telemetry={"coordinates": [1, 2, 3]},
        )
    with pytest.raises(AuthorizationError, match="cannot waive"):

        context.security_ops.create_provider_exception(
            tenant_id=tenant,
            project_id=project,
            provider_id=provider_id,
            scope={"operation": "x"},
            purpose="reconstruction",
            requested_waivers=["tenant_isolation"],
            approved_by="security-officer",
            duration_seconds=300,
        )
    with pytest.raises(ValidationError, match="every derivative cache"):
        context.security_ops.invalidate_caches(
            tenant_id=tenant,
            project_id=project,
            resource_id="asset-a",
            reason="consent_revoked",
            targets=["search", "viewer"],
            actor_id="privacy-officer",
        )
    complete = context.security_ops.invalidate_caches(
        tenant_id=tenant,
        project_id=project,
        resource_id="asset-a",
        reason="consent_revoked",
        targets=["search", "vector", "viewer", "cdn", "signed_urls", "agent_cache", "exports"],
        actor_id="privacy-officer",
    )
    assert complete["state"] == "completed"


def test_progress07_release_record_and_audit_integrity_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSAUDIT-004, OPSAUDIT-005, OPSCICD-001, OPSCICD-002, OPSCICD-003, OPSCICD-004, OPSCICD-005, OPSCICD-006 release promotion and audit integrity remain source-bound and fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p07-release-audit")
    context.audit.append(
        tenant_id=tenant,
        project_id=project,
        actor_id="security-officer",
        action="security:test",
        resource_type="test",
        resource_id="resource-a",
        outcome="allowed",
        purpose="security",
        workload_identity="security-worker",
        source_ip="127.0.0.1",
        trace_id="trace-a",
        before_ref={"sha256": "a" * 64},
        after_ref={"sha256": "b" * 64},
    )
    assert context.audit.verify(tenant)["valid"] is True
    with context.database.session() as session:
        row = session.scalar(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant))
        row.details_json = {"tampered": True}
    with pytest.raises(ValidationError, match="audit chain"):
        context.audit.verify(tenant)

    components = {
        name: {"sha256": sha256_bytes(name.encode()), "signature": "sig"}
        for name in ["mobile", "web", "services", "workers", "infrastructure", "models", "schemas", "database"]
    }
    evidence = {
        name: {"control_status": "passed_complete"}
        for name in ["tests", "security", "privacy", "license", "sbom", "benchmarks", "migrations", "backup_restore", "acceptance"]
    }
    release = context.security_ops.create_release_record(
        version="1.1.0-progress07",
        source_commit="a" * 40,
        source_root="b" * 64,
        component_manifests=components,
        evidence=evidence,
        rollback_plan={
            "services": "previous digests",
            "workers": "previous manifests",
            "configuration": "restore snapshot",
            "database_compatibility": "append-only compatible",
        },
        environment_policy={"production_authorized": False},
        signed_by="release-manager",
    )
    with pytest.raises(AuthorizationError, match="outside an approved production"):
        context.security_ops.promote_release(release_record_id=release["release_record_id"], actor_id="release-manager")


def test_progress07_transport_and_capture_finalization_audit(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSKEY-001, OPSSEC-004, OPSSEC-006 transport and capture finalization retain exact identity and fail closed on weak or inconsistent evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p07-transport-capture")
    with pytest.raises(AuthorizationError):
        context.security_ops.verify_transport_profile(
            endpoint="http://api.local",
            protocol="https",
            minimum_tls_version="TLSv1.0",
            certificate_validated=False,
            channel_authentication="none",
            evidence={"test_id": "bad", "observed_at": fresh_now().isoformat()},
            verified_by="security-officer",
        )
    valid = context.security_ops.verify_transport_profile(
        endpoint="https://api.local",
        protocol="https",
        minimum_tls_version="TLSv1.3",
        certificate_validated=True,
        channel_authentication="mutual_tls",
        evidence={"test_id": "transport", "observed_at": fresh_now().isoformat()},
        verified_by="security-officer",
    )
    assert valid["state"] == "passed"
    with pytest.raises(ValidationError):
        context.security_ops.record_capture_finalization(
            tenant_id=tenant,
            project_id=project,
            capture_id="capture-a",
            package_root_hash="bad",
            archive_sha256="b" * 64,
            device={"device_id": "device-a", "platform": "ios"},
            app={"bundle_id": "ai.sip.capture", "version": "1.1.0"},
            signer_id="capture-signer",
            verification_result="passed",
            verification={"root_hash_verified": True, "archive_hash_verified": True},
        )
    capture = context.security_ops.record_capture_finalization(
        tenant_id=tenant,
        project_id=project,
        capture_id="capture-a",
        package_root_hash="a" * 64,
        archive_sha256="b" * 64,
        device={"device_id": "device-a", "platform": "ios"},
        app={"bundle_id": "ai.sip.capture", "version": "1.1.0"},
        signer_id="capture-signer",
        verification_result="passed",
        verification={"root_hash_verified": True, "archive_hash_verified": True},
    )
    assert capture["verification_result"] == "passed"
    replay = context.security_ops.record_capture_finalization(
        tenant_id=tenant,
        project_id=project,
        capture_id="capture-a",
        package_root_hash="a" * 64,
        archive_sha256="b" * 64,
        device={"device_id": "device-a", "platform": "ios"},
        app={"bundle_id": "ai.sip.capture", "version": "1.1.0"},
        signer_id="capture-signer",
        verification_result="passed",
        verification={"root_hash_verified": True, "archive_hash_verified": True},
    )
    assert replay["idempotent_replay"] is True


def test_progress07_provider_incident_withdrawal_preserves_evidence_and_invalidates_every_surface(tmp_path: Path) -> None:
    """REQ: SECEXT-012, TSTSEC-006 provider incidents withdraw every derived surface while preserving immutable investigation evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p07-provider-incident")
    provider_id = register_provider(context, provider_id="incident-provider")
    evidence = [{"reference": "provider-incident-evidence", "sha256": sha256_bytes(b"provider-incident-evidence")}]
    kwargs = {
        "tenant_id": tenant,
        "project_id": project,
        "provider_id": provider_id,
        "source_asset_ids": ["source-a"],
        "derivative_asset_ids": ["derivative-a"],
        "publication_ids": ["publication-a"],
        "cache_resource_ids": ["cache-a"],
        "export_ids": ["export-a"],
        "evidence": evidence,
        "notification_decision": {"notify": False, "rationale": "synthetic incident exercise"},
        "actor_id": "incident-commander",
    }

    first = context.security_ops.record_provider_incident_withdrawal(**kwargs)
    second = context.security_ops.record_provider_incident_withdrawal(**kwargs)

    assert first["investigation_evidence_preserved"] is True
    assert first["withdrawal_scope"] == {
        "source": ["source-a"],
        "derivative": ["derivative-a"],
        "publication": ["publication-a"],
        "cache": ["cache-a"],
        "export": ["export-a"],
    }
    assert second["incident"]["idempotent_replay"] is True
    assert second["cache_invalidations"][0]["idempotent_replay"] is True
    assert second["incident"]["incident_id"] == first["incident"]["incident_id"]
    assert second["cache_invalidations"][0]["invalidation_id"] == first["cache_invalidations"][0]["invalidation_id"]

    with context.database.session() as session:
        incident = session.get(SecurityIncidentRow, first["incident"]["incident_id"])
        invalidation = session.get(CacheInvalidationRow, first["cache_invalidations"][0]["invalidation_id"])
        assert incident is not None
        assert incident.evidence_json == evidence
        assert {item["resource_type"] for item in incident.affected_resources_json} == {
            "source", "derivative", "publication", "cache", "export"
        }
        assert invalidation is not None
        assert invalidation.targets_json == ["agent_cache", "cdn", "exports", "search", "signed_urls", "vector", "viewer"]
        audit_actions = set(session.scalars(select(AuditEventRow.action).where(AuditEventRow.tenant_id == tenant)))
        event_types = set(session.scalars(select(OutboxEventRow.event_type).where(OutboxEventRow.tenant_id == tenant)))
        assert {"incident:create", "cache:invalidate"}.issubset(audit_actions)
        assert {"security_incident.created", "cache_invalidation.completed"}.issubset(event_types)


def test_progress07_local_only_and_splatedit_provider_boundaries_are_audited(tmp_path: Path) -> None:
    """REQ: SECEXT-013, SECEXT-014 local-only and SplatEdit boundaries deny prohibited execution and retain governed denial evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p07-provider-boundaries")
    local_provider = register_provider(context, provider_id="local-provider")

    with pytest.raises(AuthorizationError) as local_error:
        context.security_ops.authorize_provider_execution(
            provider_id=local_provider,
            tenant_id=tenant,
            project_id=project,
            classification="internal",
            purpose="reconstruction",
            region="local",
            external=True,
            telemetry={"frames": 1},
        )
    assert local_error.value.code == "LOCAL_ONLY_PROVIDER_EGRESS_DENIED"

    splatedit_provider = "splatedit-manual-provider"
    context.providers.register(
        {
            "provider_id": splatedit_provider,
            "version": "1.0.0",
            "source_url": "https://splatedit.example.invalid/manual",
            "source_revision": "b" * 40,
            "license_id": "approval-required",
            "approval_state": "approved",
            "allowed_classifications": ["internal", "synthetic", "public", "public_cleared"],
            "allowed_purposes": ["reconstruction"],
            "allowed_regions": ["local"],
            "deployments": ["local"],
            "retention_days": 0,
            "output_rights": "fixture_only",
        },
        actor_id="provider-governance",
    )
    with pytest.raises(AuthorizationError) as splatedit_error:
        context.security_ops.authorize_provider_execution(
            provider_id=splatedit_provider,
            tenant_id=tenant,
            project_id=project,
            classification="internal",
            purpose="reconstruction",
            region="local",
            external=False,
            telemetry={"frames": 1},
        )
    assert splatedit_error.value.code == "SPLATEDIT_DATA_CLASS_DENIED"

    allowed = context.security_ops.authorize_provider_execution(
        provider_id=splatedit_provider,
        tenant_id=tenant,
        project_id=project,
        classification="synthetic",
        purpose="reconstruction",
        region="local",
        external=False,
        telemetry={"frames": 1},
    )
    assert allowed["authorized"] is True

    with context.database.session() as session:
        denied = list(
            session.scalars(
                select(AuditEventRow)
                .where(AuditEventRow.tenant_id == tenant, AuditEventRow.outcome == "denied")
                .order_by(AuditEventRow.occurred_at)
            )
        )
        reason_codes = {event.details_json.get("reason_code") for event in denied}
        actions = {event.action for event in denied}
        assert {"LOCAL_ONLY_PROVIDER_EGRESS_DENIED", "SPLATEDIT_DATA_CLASS_DENIED"}.issubset(reason_codes)
        assert "provider:egress_attempt" in actions
        assert "provider:authorize" in actions
        denied_events = list(
            session.scalars(
                select(OutboxEventRow).where(
                    OutboxEventRow.tenant_id == tenant,
                    OutboxEventRow.event_type == "provider.execution.denied",
                )
            )
        )
        assert {event.payload_json["reason_code"] for event in denied_events} >= {
            "LOCAL_ONLY_PROVIDER_EGRESS_DENIED",
            "SPLATEDIT_DATA_CLASS_DENIED",
        }
