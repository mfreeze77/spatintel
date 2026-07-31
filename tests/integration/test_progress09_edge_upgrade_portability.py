from __future__ import annotations

from pathlib import Path

import pytest

from sip.errors import AuthorizationError, ConflictError, ValidationError
from tests.progress09_helpers import bind_local, bootstrap, create_profiles, create_residency


def test_progress09_edge_identity_signed_software_health_revocation_and_offline_rollback(tmp_path: Path) -> None:
    """REQ: OPSHYB-003, OPSHYB-004 edge enrollment uses unique identity, signed software, disk encryption, health, revocation, signed update, and rollback."""
    context, tenant, project = bootstrap(tmp_path, name="p09-edge")
    local, _ = create_profiles(context)
    manifest = {"image": "ghcr.io/spatial-intelligence-platform/edge:v1@sha256:" + "3" * 64, "source_commit": "4" * 40, "release": "1.0.0"}
    edge = context.deployment.enroll_edge_node(
        tenant_id=tenant, project_id=project, deployment_profile_id=local["deployment_profile_id"],
        node_identity="edge-node-01", identity_public_key_hash="5" * 64,
        software_manifest=manifest, software_signature=context.deployment.sign_manifest(manifest), signing_key_id="local-signing-key",
        disk_encryption={"enabled": True, "attested": True, "attestation_hash": "6" * 64},
        region="local", capabilities={"cpu": True, "offline": True}, actor_id="edge-admin",
    )
    assert edge["state"] == "enrolled"
    healthy = context.deployment.report_edge_health(
        tenant_id=tenant, edge_node_id=edge["edge_node_id"],
        health={"status": "healthy", "software_manifest_hash": edge["software_manifest_hash"]}, actor_id="edge-runtime",
    )
    assert healthy["state"] == "healthy"

    rollback_hash = "8" * 64
    update_manifest = {
        "from_release": "1.0.0", "to_release": "1.1.0", "bundle_hash": "7" * 64,
        "rollback_bundle_hash": rollback_hash, "rollback_signature": context.deployment.sign_manifest({}) if False else "",
        "service_images": {"edge": "ghcr.io/spatial-intelligence-platform/edge:v2@sha256:" + "9" * 64},
        "migration_head": "0019_progress09_deployment_profiles", "compatible_export_versions": ["1.1.0"], "source_commit": "a" * 40,
    }
    # rollback signatures sign the rollback bundle digest directly.
    import base64, hmac
    from hashlib import sha256
    update_manifest["rollback_signature"] = base64.b64encode(hmac.new(context.deployment.signing_key, rollback_hash.encode("ascii"), sha256).digest()).decode("ascii")
    signature = context.deployment.sign_manifest(update_manifest)
    update = context.deployment.register_offline_update(deployment_profile_id=local["deployment_profile_id"], manifest=update_manifest, signature=signature, signing_key_id="local-signing-key", actor_id="release-manager")
    applied = context.deployment.apply_offline_update(tenant_id=tenant, edge_node_id=edge["edge_node_id"], update_id=update["update_id"], current_release="1.0.0", actor_id="edge-admin")
    assert applied["release"] == "1.1.0"
    rolled_back = context.deployment.rollback_offline_update(tenant_id=tenant, edge_node_id=edge["edge_node_id"], update_id=update["update_id"], reason="synthetic rehearsal", actor_id="edge-admin")
    assert rolled_back["release"] == "1.0.0"
    revoked = context.deployment.revoke_edge_node(tenant_id=tenant, edge_node_id=edge["edge_node_id"], reason="retired", actor_id="edge-admin")
    assert revoked["state"] == "revoked"
    with pytest.raises(AuthorizationError) as revoked_health:
        context.deployment.report_edge_health(tenant_id=tenant, edge_node_id=edge["edge_node_id"], health={"status": "healthy", "software_manifest_hash": edge["software_manifest_hash"]}, actor_id="edge-runtime")
    assert revoked_health.value.code == "EDGE_NODE_REVOKED"


def test_progress09_project_mode_migration_and_local_upgrade_preserve_semantics(tmp_path: Path) -> None:
    """REQ: ARCDEP-004, OPSHYB-005 local upgrade rollback and project-mode migration preserve export identity, history, permissions, consent, hashes, and run manifests."""
    context, tenant, project = bootstrap(tmp_path, name="p09-migrate")
    local, hybrid = create_profiles(context)
    residency = create_residency(context, tenant, project)
    bind_local(context, tenant, project, local, residency)
    planned = context.deployment.create_project_migration(
        tenant_id=tenant, project_id=project, source_profile_id=local["deployment_profile_id"],
        target_profile_id=hybrid["deployment_profile_id"], idempotency_key="local-to-hybrid", actor_id="deployment-admin",
    )
    completed = context.deployment.complete_project_migration(tenant_id=tenant, project_id=project, migration_id=planned["migration_id"], actor_id="deployment-admin")
    assert completed["state"] == "completed"
    assert completed["validation"]["preserved"] is True
    root = "b" * 64
    rehearsal = context.deployment.record_local_upgrade_rehearsal(
        deployment_profile_id=local["deployment_profile_id"], from_release="1.0.0", to_release="1.1.0",
        from_schema="0018", to_schema="0019", pre_export_root=root, post_upgrade_export_root=root,
        rollback_export_root=root, object_store_root="c" * 64, queue_root="d" * 64,
        job_recovery={"resumable": True, "duplicate_side_effects": 0, "object_store_continuity": True, "queue_continuity": True, "graceful_shutdown": True, "checkpoint_resume": True, "idempotent_replay": True},
        evidence={"migration_clean": True, "rollback_clean": True}, actor_id="release-manager",
    )
    assert rehearsal["state"] == "verified"


def test_progress09_graceful_worker_shutdown_requires_checkpoint_coverage(tmp_path: Path) -> None:
    """REQ: ARCDEP-004, OPSAWS-003 graceful termination releases leases and proves duplicate-free job recovery."""
    context, _, _ = bootstrap(tmp_path, name="p09-shutdown")
    local, _ = create_profiles(context)
    with pytest.raises(ValidationError):
        context.deployment.record_graceful_shutdown(
            worker_id="worker-1", deployment_profile_id=local["deployment_profile_id"], operation_ids=["op-1"], checkpoint_hashes={},
            queue_before={"leased_jobs": 1}, queue_after={"leased_jobs": 0}, recovery={"resumable": True, "duplicate_side_effects": 0}, actor_id="operator",
        )
    result = context.deployment.record_graceful_shutdown(
        worker_id="worker-1", deployment_profile_id=local["deployment_profile_id"], operation_ids=["op-1"], checkpoint_hashes={"op-1": "e" * 64},
        queue_before={"leased_jobs": 1}, queue_after={"leased_jobs": 0}, recovery={"resumable": True, "duplicate_side_effects": 0}, actor_id="operator",
    )
    assert result["state"] == "verified"


def test_progress09_edge_workload_identity_scope_expiry_and_configuration_drift(tmp_path: Path) -> None:
    """REQ: OPSHYB-003, OPSAWS-005 edge workload identity is short-lived and scope-bound, while configuration drift is recorded against the pinned profile."""
    from sip.database import WorkloadIdentityGrantRow
    from sip.errors import AuthorizationError

    context, tenant, project = bootstrap(tmp_path, name="p09-edge-identity")
    local, _ = create_profiles(context)
    manifest = {"image": "ghcr.io/spatial-intelligence-platform/edge:v1@sha256:" + "3" * 64, "source_commit": "4" * 40, "release": "1.0.0"}
    edge = context.deployment.enroll_edge_node(
        tenant_id=tenant, project_id=project, deployment_profile_id=local["deployment_profile_id"],
        node_identity="edge-identity-01", identity_public_key_hash="5" * 64,
        software_manifest=manifest, software_signature=context.deployment.sign_manifest(manifest), signing_key_id="local-signing-key",
        disk_encryption={"enabled": True, "attested": True, "attestation_hash": "6" * 64},
        region="local", capabilities={"cpu": True}, actor_id="edge-admin",
    )
    with context.database.session() as session:
        grant = session.get(WorkloadIdentityGrantRow, edge["workload_identity_grant_id"])
        assert grant is not None
        token = context.security_ops._encode_workload(grant)
    valid = context.security_ops.validate_workload_identity(
        token, audience="sip-edge-runtime", required_scope="deployment:edge_runtime", purpose="edge_runtime",
        tenant_id=tenant, project_id=project, workload_id="edge:edge-identity-01",
    )
    assert valid["grant_id"] == edge["workload_identity_grant_id"]
    with pytest.raises(AuthorizationError):
        context.security_ops.validate_workload_identity(
            token, audience="wrong-audience", required_scope="deployment:edge_runtime", purpose="edge_runtime",
            tenant_id=tenant, project_id=project, workload_id="edge:edge-identity-01",
        )
    observed = context.deployment.get_profile(local["deployment_profile_id"])
    clean = context.deployment.detect_drift(deployment_profile_id=local["deployment_profile_id"], observed_manifest=observed, actor_id="operator")
    assert clean["status"] == "passed"
    drifted = dict(observed)
    drifted["service_images"] = {**observed["service_images"], "control-api": "ghcr.io/sip/control-api:v2@sha256:" + "9" * 64}
    drift = context.deployment.detect_drift(deployment_profile_id=local["deployment_profile_id"], observed_manifest=drifted, actor_id="operator")
    assert drift["status"] == "drift_detected"
    assert any(item["field"] == "service_images" for item in drift["findings"])
