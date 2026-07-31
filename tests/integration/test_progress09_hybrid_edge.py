from __future__ import annotations

from pathlib import Path

import pytest

from sip.errors import AuthorizationError, ValidationError
from tests.progress09_helpers import assign_profile, bootstrap, direct_digest_signature, profile_args, residency_args


def _profile(context, *, name: str, mode: str, digest: str):
    return context.deployment.register_profile(**profile_args(name=name, mode=mode, digest_character=digest), actor_id="deployment-admin")


def test_progress09_hybrid_transfer_rules_block_sensitive_early_or_unapproved_transfer(tmp_path: Path) -> None:
    """REQ: OPSHYB-002 hybrid transfer policy governs asset class, processing stage, purpose, region, and independent approval before transfer."""
    context, tenant, project = bootstrap(tmp_path, name="p09-transfer")
    source = _profile(context, name="edge-source", mode="edge", digest="4")
    target = _profile(context, name="hybrid-target", mode="hybrid", digest="5")
    residency = context.deployment.register_residency_policy(tenant_id=tenant, project_id=project, **residency_args(), actor_id="residency-officer")

    with pytest.raises(ValidationError) as early:
        context.deployment.register_transfer_policy(
            tenant_id=tenant, project_id=project, revision="bad", source_profile_id=source["deployment_profile_id"],
            destination_profile_id=target["deployment_profile_id"], purpose="reconstruction",
            rules=[{"asset_class": "raw_capture", "minimum_stage": "raw", "allowed_regions": ["us-east-1"], "allowed_purposes": ["reconstruction"], "requires_approval": True}],
            actor_id="deployment-admin",
        )
    assert early.value.code == "TRANSFER_SENSITIVE_STAGE_TOO_EARLY"

    transfer = context.deployment.register_transfer_policy(
        tenant_id=tenant, project_id=project, revision="1.0.0", source_profile_id=source["deployment_profile_id"],
        destination_profile_id=target["deployment_profile_id"], purpose="reconstruction",
        rules=[{"asset_class": "raw_capture", "minimum_stage": "redacted_derivative", "allowed_regions": ["us-east-1"], "allowed_purposes": ["reconstruction"], "requires_approval": True}],
        actor_id="deployment-admin",
    )
    assign_profile(context, tenant, project, source["deployment_profile_id"], residency["residency_policy_id"], transfer_id=transfer["transfer_policy_id"])

    base = {"asset_class": "raw_capture", "purpose": "reconstruction"}
    with pytest.raises(AuthorizationError) as too_early:
        context.deployment.authorize_admission(tenant_id=tenant, project_id=project, admission_type="asset_transfer", deployment_profile_id=source["deployment_profile_id"], region="us-east-1", request={**base, "processing_stage": "normalized", "approval_receipt_valid": True}, actor_id="worker")
    assert too_early.value.code == "DEPLOYMENT_TRANSFER_STAGE_DENIED"
    with pytest.raises(AuthorizationError) as approval:
        context.deployment.authorize_admission(tenant_id=tenant, project_id=project, admission_type="asset_transfer", deployment_profile_id=source["deployment_profile_id"], region="us-east-1", request={**base, "processing_stage": "redacted_derivative"}, actor_id="worker")
    assert approval.value.code == "DEPLOYMENT_TRANSFER_APPROVAL_REQUIRED"
    allowed = context.deployment.authorize_admission(tenant_id=tenant, project_id=project, admission_type="asset_transfer", deployment_profile_id=source["deployment_profile_id"], region="us-east-1", request={**base, "processing_stage": "redacted_derivative", "approval_receipt_valid": True}, actor_id="worker")
    assert allowed["decision"] == "allow"


def test_progress09_edge_identity_health_signed_update_rollback_and_revocation(tmp_path: Path) -> None:
    """REQ: OPSHYB-003, OPSHYB-004 edge nodes use unique short-lived workload identity, signed software, disk encryption, health, revocation, and signed rollback-capable offline updates."""
    context, tenant, project = bootstrap(tmp_path, name="p09-edge")
    profile = _profile(context, name="edge-runtime", mode="edge", digest="6")
    manifest = {
        "image": f"ghcr.io/spatial-intelligence-platform/edge:1.0.0@sha256:{'6' * 64}",
        "source_commit": "a" * 40,
        "release": "1.0.0",
    }
    node = context.deployment.enroll_edge_node(
        tenant_id=tenant, project_id=project, deployment_profile_id=profile["deployment_profile_id"], node_identity="edge-node-001",
        identity_public_key_hash="7" * 64, software_manifest=manifest, software_signature=context.deployment.sign_manifest(manifest),
        signing_key_id="deployment-key-v1", disk_encryption={"enabled": True, "attested": True, "attestation_hash": "8" * 64},
        region="us-east-1", capabilities={"capture": True, "cpu_reference": True}, actor_id="edge-admin",
    )
    assert node["workload_identity_grant_id"]
    assert node["software_release"] == "1.0.0"
    health = context.deployment.report_edge_health(tenant_id=tenant, edge_node_id=node["edge_node_id"], health={"status": "healthy", "release": "1.0.0", "disk_encryption": "attested", "software_manifest_hash": node["software_manifest_hash"]}, actor_id="edge-agent")
    assert health["health"]["status"] == "healthy"

    update_manifest = {
        "from_release": "1.0.0", "to_release": "1.1.0", "bundle_hash": "9" * 64,
        "rollback_bundle_hash": "a" * 64, "rollback_signature": direct_digest_signature(context, "a" * 64),
        "service_images": {"edge": f"ghcr.io/spatial-intelligence-platform/edge:1.1.0@sha256:{'b' * 64}"},
        "migration_head": "0019_progress09_deployment_profiles", "compatible_export_versions": ["1.1.0"],
        "source_commit": "b" * 40,
    }
    update = context.deployment.register_offline_update(deployment_profile_id=profile["deployment_profile_id"], manifest=update_manifest, signature=context.deployment.sign_manifest(update_manifest), signing_key_id="deployment-key-v1", actor_id="release-manager")
    applied = context.deployment.apply_offline_update(tenant_id=tenant, edge_node_id=node["edge_node_id"], update_id=update["update_id"], current_release="1.0.0", actor_id="edge-admin")
    assert applied["state"] == "applied" and applied["release"] == "1.1.0"
    rolled_back = context.deployment.rollback_offline_update(tenant_id=tenant, edge_node_id=node["edge_node_id"], update_id=update["update_id"], reason="synthetic rollback rehearsal", actor_id="edge-admin")
    assert rolled_back["state"] == "rolled_back" and rolled_back["release"] == "1.0.0"
    revoked = context.deployment.revoke_edge_node(tenant_id=tenant, edge_node_id=node["edge_node_id"], reason="synthetic decommission", actor_id="edge-admin")
    assert revoked["state"] == "revoked"
    with pytest.raises(AuthorizationError) as denied:
        context.deployment.apply_offline_update(tenant_id=tenant, edge_node_id=node["edge_node_id"], update_id=update["update_id"], current_release="1.0.0", actor_id="edge-admin")
    assert denied.value.code == "EDGE_NODE_REVOKED"
