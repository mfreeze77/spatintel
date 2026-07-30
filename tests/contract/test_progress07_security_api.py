from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from sip.canonical import sha256_bytes
from tests.progress07_helpers import bootstrap, fresh_now, headers, output_checks, register_provider, threat_payload, valid_rights_outcomes


def test_progress07_security_api_enforces_exact_privilege_and_workload_scope(tmp_path: Path) -> None:
    """REQ: OPSSEC-001, OPSSEC-002, OPSSEC-003, OPSSEC-006, OPSTHREA-001, OPSTHREA-002, OPSTHREA-003, OPSTHREA-004, OPSTHREA-005, OPSTHREA-006, SECEXT-001, SECEXT-002 the authenticated security API requires exact roles and issues purpose/audience/scope-bound credentials."""
    context, tenant, project = bootstrap(tmp_path, name="p07-api-identity")
    client = TestClient(create_app(context=context, service_name="security-ops"))
    viewer = headers(tenant, project, subject="viewer", role="viewer")
    admin = headers(tenant, project)
    denied = client.post("/v1/security/threat-manifests", headers=viewer, json=threat_payload())
    assert denied.status_code == 403
    created = client.post("/v1/security/threat-manifests", headers=admin, json=threat_payload())
    assert created.status_code == 201, created.text

    jit = client.post(
        f"/v1/tenants/{tenant}/security/privileged-access",
        headers=admin,
        json={
            "project_id": project,
            "subject_id": "incident-operator",
            "actions": ["security:incident"],
            "resource_scope": {"project_id": project},
            "purpose": "incident_response",
            "mfa_method": "webauthn",
            "mfa_verified_at": fresh_now().isoformat(),
            "duration_seconds": 300,
            "requested_by": "incident-operator",
        },
    )
    assert jit.status_code == 201, jit.text
    self_approved = client.post(
        f"/v1/tenants/{tenant}/security/privileged-access",
        headers=admin,
        json={
            "project_id": project,
            "subject_id": "security-admin",
            "actions": ["security:incident"],
            "resource_scope": {"project_id": project},
            "purpose": "incident_response",
            "mfa_method": "webauthn",
            "mfa_verified_at": fresh_now().isoformat(),
            "duration_seconds": 300,
            "requested_by": "security-admin",
        },
    )
    assert self_approved.status_code == 403

    issued = client.post(
        f"/v1/tenants/{tenant}/security/workload-identities",
        headers=admin,
        json={
            "project_id": project,
            "workload_id": "quality-worker",
            "audience": "worker-runtime",
            "scopes": ["asset:read", "operation:lease"],
            "purpose": "reconstruction",
            "ttl_seconds": 120,
        },
    )
    assert issued.status_code == 201, issued.text
    valid = client.post(
        f"/v1/tenants/{tenant}/security/workload-identities/validate",
        headers=admin,
        json={
            "token": issued.json()["token"],
            "workload_id": "quality-worker",
            "audience": "worker-runtime",
            "required_scope": "asset:read",
            "purpose": "reconstruction",
            "project_id": project,
        },
    )
    assert valid.status_code == 200, valid.text
    wrong = client.post(
        f"/v1/tenants/{tenant}/security/workload-identities/validate",
        headers=admin,
        json={
            "token": issued.json()["token"],
            "workload_id": "quality-worker",
            "audience": "wrong",
            "required_scope": "asset:read",
            "purpose": "reconstruction",
            "project_id": project,
        },
    )
    assert wrong.status_code == 403


def test_progress07_privacy_key_audit_and_incident_api_round_trip(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSAUDIT-004, OPSAUDIT-005, OPSKEY-001, OPSKEY-002, OPSKEY-003, OPSKEY-004, OPSKEY-005, OPSKEY-006, OPSPRIV-001, OPSPRIV-002, OPSPRIV-003, OPSPRIV-004, OPSPRIV-006 key, privacy, rights, incident, and audit controls retain scoped evidence through authenticated APIs."""
    context, tenant, project = bootstrap(tmp_path, name="p07-api-privacy")
    client = TestClient(create_app(context=context, service_name="security-ops"))
    admin = headers(tenant, project)
    key = client.post(
        f"/v1/tenants/{tenant}/security/key-scopes", headers=admin,
        json={
            "project_id": project,
            "key_id": "kms-api-v1",
            "backend": "managed_kms",
            "recovery_policy": {"guardians": ["a", "b"], "quorum": 2, "single_person_recovery": False},
        },
    )
    assert key.status_code == 201, key.text
    access = client.post(
        f"/v1/tenants/{tenant}/security/key-scopes/{key.json()['key_scope_id']}/access", headers=admin,
        json={
            "project_id": project,
            "actor_or_workload": "worker:a",
            "purpose": "privacy",
            "action": "unwrap",
            "resource_scope": {"asset_id": "a"},
            "outcome": "allowed",
        },
    )
    assert access.status_code == 201, access.text
    inventory = client.post(
        f"/v1/tenants/{tenant}/privacy/inventory", headers=admin,
        json={
            "project_id": project,
            "data_category": "family_media",
            "purpose": "privacy",
            "legal_basis": "consent",
            "consent_basis": "grant",
            "processors": [{"name": "local", "approved_purposes": ["privacy"], "training_allowed": False}],
            "residency": {"regions": ["local"]},
            "retention": {"policy": "subject-v1"},
            "security_controls": ["encryption"],
            "rights_workflow": {"contact": "privacy@example.invalid"},
            "classification": "confidential",
        },
    )
    assert inventory.status_code == 201, inventory.text
    impact = client.post(
        f"/v1/tenants/{tenant}/privacy/impact-assessments", headers=admin,
        json={
            "project_id": project,
            "change_type": "data_purpose",
            "change_reference": "purpose-v2",
            "purpose": "privacy",
            "data_categories": ["family_media"],
            "processors": ["local"],
            "risks": [{"risk": "linkability"}],
            "controls": [{"control": "purpose_limit"}],
            "residual_risk": "low",
            "decision": "approved",
        },
    )
    assert impact.status_code == 201, impact.text
    rights = client.post(
        f"/v1/tenants/{tenant}/privacy/rights-requests", headers=admin,
        json={
            "project_id": project,
            "subject_id": "subject-a",
            "request_type": "deletion",
            "scope": {"all_subject_data": True},
            "requested_by": "subject-a",
            "due_days": 30,
        },
    )
    assert rights.status_code == 201, rights.text
    complete = client.post(
        f"/v1/tenants/{tenant}/privacy/rights-requests/{rights.json()['rights_request_id']}/complete", headers=admin,
        json={
            "project_id": project,
            "outcomes": valid_rights_outcomes(),
            "evidence": [{"reference": "rights-api", "sha256": sha256_bytes(b"rights-api")}],
        },
    )
    assert complete.status_code == 200, complete.text
    incident = client.post(
        f"/v1/tenants/{tenant}/security/incidents", headers=admin,
        json={
            "project_id": project,
            "incident_type": "access_anomaly",
            "severity": "high",
            "affected_subjects": ["subject-a"],
            "affected_resources": [{"resource_type": "asset", "resource_id": "a"}],
            "containment": [{"action": "revoke"}],
            "notification_decision": {"notify": False, "rationale": "synthetic"},
            "evidence": [{"reference": "incident", "sha256": sha256_bytes(b"incident")}],
        },
    )
    assert incident.status_code == 201, incident.text
    audit = client.post(
        f"/v1/tenants/{tenant}/audit/security-verify", headers=admin,
        json={"project_id": project, "referenced_manifests": []},
    )
    assert audit.status_code == 200, audit.text
    assert audit.json()["valid"] is True


def test_progress07_transport_capture_provider_output_and_immersive_routes(tmp_path: Path) -> None:
    """REQ: OPSSEC-004, OPSTHR-008, OPSTHR-011, OPSTHR-012, SECEXT-003, SECEXT-004, SECEXT-005, SECEXT-006, SECEXT-007, SECEXT-008, SECEXT-012, TSTSEC-004 transport, capture receipt, provider quarantine, and immersive fallback routes fail closed with retained evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p07-api-runtime")
    provider_id = register_provider(context)
    client = TestClient(create_app(context=context, service_name="security-ops"))
    admin = headers(tenant, project)
    transport = client.post(
        "/v1/security/transport-verifications", headers=admin,
        json={
            "endpoint": "https://api.local",
            "protocol": "https",
            "minimum_tls_version": "TLSv1.3",
            "certificate_validated": True,
            "channel_authentication": "mutual_tls",
            "evidence": {"test_id": "transport-api", "observed_at": fresh_now().isoformat()},
        },
    )
    assert transport.status_code == 201, transport.text
    insecure = client.post(
        "/v1/security/transport-verifications", headers=admin,
        json={
            "endpoint": "http://api.local",
            "protocol": "https",
            "minimum_tls_version": "TLSv1.0",
            "certificate_validated": False,
            "channel_authentication": "mutual_tls",
            "evidence": {"test_id": "bad", "observed_at": fresh_now().isoformat()},
        },
    )
    assert insecure.status_code == 403
    capture = client.post(
        f"/v1/projects/{project}/security/capture-finalizations", headers=admin,
        json={
            "capture_id": "capture-a",
            "package_root_hash": "a" * 64,
            "archive_sha256": "b" * 64,
            "device": {"device_id": "device-a", "platform": "ios"},
            "app": {"bundle_id": "ai.sip.capture", "version": "1.1.0"},
            "signer_id": "capture-signer",
            "verification_result": "passed",
            "verification": {"root_hash_verified": True, "archive_hash_verified": True},
        },
    )
    assert capture.status_code == 201, capture.text
    output_hash, checks = output_checks()
    output = client.post(
        f"/v1/projects/{project}/security/provider-outputs", headers=admin,
        json={
            "provider_id": provider_id,
            "operation_id": "op-a",
            "output_sha256": output_hash,
            "media_type": "application/octet-stream",
            "byte_count": 26,
            "validations": checks,
        },
    )
    assert output.status_code == 201, output.text
    assert output.json()["state"] == "validated_quarantined"
    immersive = client.post(
        f"/v1/projects/{project}/security/immersive-safety", headers=admin,
        json={
            "scene_id": "scene-a",
            "checks": {"accepted_scale": True, "walkability": False, "openings": True, "stairs_and_falls": True, "safe_spawn": True, "safe_exit": True},
            "requested_modes": ["orbit", "walk", "teleport"],
        },
    )
    assert immersive.status_code == 201, immersive.text
    assert set(immersive.json()["disabled_modes"]) == {"walk", "teleport"}


def test_progress07_release_provider_and_cache_api_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSCICD-001, OPSCICD-002, OPSCICD-003, OPSCICD-004, OPSCICD-005, OPSCICD-006, OPSPRIV-004, OPSPRIV-006, OPSTHR-011, SECEXT-009, SECEXT-010, SECEXT-011, SECEXT-012, SECEXT-013, SECEXT-015, SECEXT-016 provider execution, exceptions, incident withdrawal, caches, and release promotion remain fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p07-api-release")
    provider_id = register_provider(context)
    client = TestClient(create_app(context=context, service_name="security-ops"))
    admin = headers(tenant, project)
    authorized = client.post(
        f"/v1/projects/{project}/security/providers/{provider_id}/authorize", headers=admin,
        json={"classification": "internal", "purpose": "reconstruction", "region": "local", "external": False, "telemetry": {"frames": 5}},
    )
    assert authorized.status_code == 200, authorized.text
    external = client.post(
        f"/v1/projects/{project}/security/providers/{provider_id}/authorize", headers=admin,
        json={"classification": "internal", "purpose": "reconstruction", "region": "local", "external": True, "telemetry": {}},
    )
    assert external.status_code == 403
    prohibited = client.post(
        f"/v1/projects/{project}/security/providers/{provider_id}/exceptions", headers=admin,
        json={"scope": {"operation": "x"}, "purpose": "reconstruction", "requested_waivers": ["consent"], "duration_seconds": 300},
    )
    assert prohibited.status_code == 403
    invalidation = client.post(
        f"/v1/projects/{project}/security/cache-invalidations", headers=admin,
        json={"resource_id": "asset-a", "reason": "consent_revoked", "targets": ["search", "viewer", "signed_urls", "agent_cache", "cdn", "exports", "vector"]},
    )
    assert invalidation.status_code == 201, invalidation.text
    release = client.post(
        "/v1/security/releases", headers=admin,
        json={
            "version": "1.1.0-progress07",
            "source_commit": "a" * 40,
            "source_root": "b" * 64,
            "component_manifests": {name: {"sha256": sha256_bytes(name.encode())} for name in ["mobile", "web", "services", "workers", "infrastructure", "models", "schemas", "database"]},
            "evidence": {name: {"control_status": "passed_complete"} for name in ["tests", "security", "privacy", "license", "sbom", "benchmarks", "migrations", "backup_restore", "acceptance"]},
            "rollback_plan": {"services": "prior", "workers": "prior", "configuration": "prior", "database_compatibility": "append-only"},
            "environment_policy": {"production_authorized": False},
        },
    )
    assert release.status_code == 201, release.text
    promotion = client.post(f"/v1/security/releases/{release.json()['release_record_id']}/promote", headers=admin)
    assert promotion.status_code == 403
