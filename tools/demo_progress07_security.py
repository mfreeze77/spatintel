#!/usr/bin/env python3
"""Run the deterministic synthetic Progress 07 security/privacy control demonstration."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings

THREATS = [
    "capture_device_compromise", "upload_tampering", "archive_bomb", "parser_exploit",
    "gpu_escape", "cross_tenant_access", "signed_url_leakage", "viewer_scraping",
    "model_exfiltration", "prompt_injection", "insider_abuse", "destructive_deletion",
    "geometry_payload_parsing", "provider_egress", "topology_disclosure",
    "derivative_redaction", "authority_spoofing", "immersive_safety_failure",
]


def run_demo(runtime_root: Path) -> dict[str, object]:
    context = PlatformContext.create(temporary_settings(runtime_root))
    tenant = context.tenancy.create_tenant("Progress 07 synthetic tenant", tenant_id="p07-demo-tenant", actor_id="bootstrap")
    project = context.tenancy.create_project(tenant, "Progress 07 synthetic project", vertical="construction", classification="internal", project_id="p07-demo-project", actor_id="bootstrap")
    threat = context.security_ops.register_threat_manifest(
        scope="sip-platform",
        threats=[{
            "threat_id": item,
            "description": item.replace("_", " "),
            "owner": "security-team",
            "test_ids": [f"test:{item}"],
            "controls": {"preventative": ["deny"], "detective": ["audit"], "recovery": ["revoke-and-restore"]},
        } for item in THREATS],
        misuse_cases=[
            {"domain": "sensitive_facility", "case": "topology inference", "control": "pre-match authorization"},
            {"domain": "private_family", "case": "relationship inference", "control": "consent-scoped graph access"},
        ],
        public_viewer_analysis={"trusted_secrets": False, "scraping_controls": ["rate_limit"], "cache_controls": ["policy_etag"]},
        residual_risks=[{"risk": "screen capture", "owner": "security-team", "release_disposition": "watermark and disclose"}],
        owner="security-team", review_trigger="scheduled", actor_id="security-officer",
    )
    grant = context.security_ops.grant_privileged_access(
        tenant_id=tenant, project_id=project, subject_id="incident-operator", actions=["security:incident"],
        resource_scope={"project_id": project}, purpose="incident_response", mfa_method="webauthn",
        mfa_verified_at=datetime.now(UTC), duration_seconds=300, requested_by="incident-operator", approved_by="jit-approver",
    )
    workload = context.security_ops.issue_workload_identity(
        tenant_id=tenant, project_id=project, workload_id="quality-worker", audience="worker-runtime",
        scopes=["asset:read", "operation:lease"], purpose="reconstruction", ttl_seconds=120, actor_id="security-officer",
    )
    validated_workload = context.security_ops.validate_workload_identity(
        workload["token"], audience="worker-runtime", required_scope="asset:read", purpose="reconstruction", tenant_id=tenant, project_id=project, workload_id="quality-worker",
    )
    key = context.security_ops.register_key_scope(
        tenant_id=tenant, project_id=project, person_id=None, key_id="kms-project-v1", backend="managed_kms",
        recovery_policy={"guardians": ["custodian-a", "custodian-b"], "quorum": 2, "single_person_recovery": False},
        actor_id="key-custodian",
    )
    inventory = context.security_ops.register_privacy_inventory(
        tenant_id=tenant, project_id=project, data_category="spatial_capture", purpose="construction_reference",
        legal_basis="contract", consent_basis="project_authorization", processors=[{"name": "local", "approved_purposes": ["construction_reference"], "training_allowed": False}],
        residency={"regions": ["local"], "transfer_policy": "deny"}, retention={"policy": "project-v1", "minimum_days": 30},
        security_controls=["envelope_encryption", "purpose_authorization"], rights_workflow={"contact": "privacy@example.invalid", "types": ["access", "restriction", "deletion"]},
        classification="internal", actor_id="privacy-officer",
    )
    transport = context.security_ops.verify_transport_profile(
        endpoint="https://control-api.local", protocol="https", minimum_tls_version="TLSv1.3",
        certificate_validated=True, channel_authentication="mutual_tls",
        evidence={"test_id": "p07-demo-transport", "observed_at": datetime.now(UTC).isoformat()}, verified_by="security-officer",
    )
    context.providers.register({
        "provider_id": "p07-local-provider", "version": "1.0.0", "source_url": "local://p07/provider",
        "source_revision": "a" * 40, "license_id": "Apache-2.0", "approval_state": "approved",
        "allowed_classifications": ["internal"], "allowed_purposes": ["reconstruction"],
        "allowed_regions": ["local"], "deployments": ["local"],
    }, actor_id="security-officer")
    output_hash = sha256_bytes(b"progress07-provider-output")
    checks = {name: {"passed": True, "tool": f"sip-{name}", "version": "1.0.0", "report_sha256": sha256_bytes(name.encode())} for name in ["malware_scan", "resource_limits", "format_validation", "transform_validation", "content_policy", "hash_verified", "quarantine_write_only"]}
    checks["hash_verified"]["observed_sha256"] = output_hash
    checks["quarantine_write_only"]["workspace_policy"] = "write_only_staging"
    provider_output = context.security_ops.validate_provider_output(
        tenant_id=tenant, project_id=project, provider_id="p07-local-provider", operation_id="p07-operation",
        output_sha256=output_hash, media_type="application/octet-stream", byte_count=26, validations=checks, validated_by="security-officer",
    )
    immersive = context.security_ops.evaluate_immersive_safety(
        tenant_id=tenant, project_id=project, scene_id="p07-scene",
        checks={"accepted_scale": True, "walkability": False, "openings": True, "stairs_and_falls": True, "safe_spawn": True, "safe_exit": True},
        requested_modes=["orbit", "walk", "teleport"], actor_id="scene-reviewer",
    )
    audit = context.security_ops.verify_audit_chain(tenant_id=tenant, project_id=project, referenced_manifests=[], verifier_id="security-officer")
    report = {
        "schema": "sip.progress07-security-demo/v1",
        "status": "passed_complete",
        "tenant_id": tenant,
        "project_id": project,
        "threat_manifest": {k: threat[k] for k in ("threat_manifest_id", "version", "manifest_hash")},
        "jit_access": {"state": grant["state"], "expires_at": grant["expires_at"]},
        "workload_identity": {"workload_id": validated_workload["workload_id"], "audience": validated_workload["audience"], "scopes": validated_workload["scopes"]},
        "key_scope": {"state": key["state"], "backend": key["backend"]},
        "privacy_inventory": {"state": inventory["state"], "content_hash": inventory["content_hash"]},
        "transport": {"state": transport["state"], "verification_hash": transport["verification_hash"]},
        "provider_output": {"state": provider_output["state"], "validation_hash": provider_output["validation_hash"]},
        "immersive_safety": {"state": immersive["state"], "disabled_modes": immersive["disabled_modes"], "fallback_mode": immersive["fallback_mode"]},
        "audit": {"valid": audit["valid"], "finding_count": len(audit["findings"])},
        "production_authorized": False,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/evidence/demo-progress07-security.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sip-p07-demo-") as directory:
        report = run_demo(Path(directory))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
