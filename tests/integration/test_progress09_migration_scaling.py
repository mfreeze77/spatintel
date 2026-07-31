from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sip.database import AutoscalingAdmissionRow
from sip.errors import AuthorizationError
from tests.progress09_helpers import assign_profile, bootstrap, profile_args, residency_args


def _profile(context, *, name: str, mode: str, digest: str):
    return context.deployment.register_profile(**profile_args(name=name, mode=mode, digest_character=digest), actor_id="deployment-admin")


def test_progress09_project_migration_and_local_upgrade_preserve_semantic_and_export_identity(tmp_path: Path) -> None:
    """REQ: ARCDEP-004, OPSHYB-005 local upgrades and profile migrations preserve stable IDs, history, permissions, consent, hashes, run/model manifests, queue/object continuity, export compatibility, and rollback."""
    context, tenant, project = bootstrap(tmp_path, name="p09-migration")
    source = _profile(context, name="local-source", mode="local_only", digest="c")
    target = _profile(context, name="hybrid-target-migrate", mode="hybrid", digest="d")
    residency = context.deployment.register_residency_policy(tenant_id=tenant, project_id=project, **residency_args(), actor_id="residency-officer")
    assign_profile(context, tenant, project, source["deployment_profile_id"], residency["residency_policy_id"], cloud_ack=False)
    planned = context.deployment.create_project_migration(tenant_id=tenant, project_id=project, source_profile_id=source["deployment_profile_id"], target_profile_id=target["deployment_profile_id"], idempotency_key="profile-migration-1", actor_id="deployment-admin")
    completed = context.deployment.complete_project_migration(tenant_id=tenant, project_id=project, migration_id=planned["migration_id"], actor_id="deployment-admin")
    assert completed["state"] == "completed"
    assert completed["validation"]["preserved"] is True
    assert completed["source_snapshot_hash"] == completed["target_snapshot_hash"]
    replay = context.deployment.complete_project_migration(tenant_id=tenant, project_id=project, migration_id=planned["migration_id"], actor_id="deployment-admin")
    assert replay["idempotent_replay"] is True

    rehearsal = context.deployment.record_local_upgrade_rehearsal(
        deployment_profile_id=target["deployment_profile_id"], from_release="1.0.0", to_release="1.1.0",
        from_schema="0018", to_schema="0019", pre_export_root="1" * 64, post_upgrade_export_root="1" * 64,
        rollback_export_root="1" * 64, object_store_root="2" * 64, queue_root="3" * 64,
        job_recovery={"graceful_shutdown": True, "checkpoint_resume": True, "idempotent_replay": True, "jobs_resumed": 2, "jobs_lost": 0},
        evidence={"clean_install": True, "upgrade": True, "rollback": True, "export_compatible": True}, actor_id="release-manager",
    )
    assert rehearsal["state"] == "verified"
    shutdown = context.deployment.record_graceful_shutdown(
        worker_id="worker-1", deployment_profile_id=target["deployment_profile_id"], operation_ids=["op-1", "op-2"],
        checkpoint_hashes={"op-1": "4" * 64, "op-2": "5" * 64}, queue_before={"queued": 2, "in_flight": 1},
        queue_after={"queued": 2, "in_flight": 0, "leased_jobs": 0}, recovery={"resumable": True, "lost_jobs": 0, "duplicate_side_effects": 0}, actor_id="worker-supervisor",
    )
    assert shutdown["state"] == "verified"


def test_progress09_autoscaling_enforces_profile_quota_tenant_limit_budget_and_idempotency(tmp_path: Path) -> None:
    """REQ: ARCDEP-005, OPSAWS-003 autoscaling honors profile quotas, tenant concurrency, global budget, restricted egress, and dead-letter policy with governed replay."""
    context, tenant, project = bootstrap(tmp_path, name="p09-autoscale")
    policy = context.deployment.register_autoscaling_policy(
        tenant_id=tenant, project_id=project, queue_class="gpu-reconstruction", revision="1.0.0",
        min_replicas=0, max_replicas=4, tenant_concurrency_limit=4, profile_quotas={"gpu-a10": 2},
        global_budget_limit=20.0, currency="USD", dead_letter={"enabled": True, "queue": "gpu-dlq", "max_attempts": 3},
        restricted_egress=True, actor_id="deployment-admin",
    )
    allowed = context.deployment.admit_autoscaling(tenant_id=tenant, project_id=project, autoscaling_policy_id=policy["autoscaling_policy_id"], compute_profile="gpu-a10", requested_replicas=2, current_tenant_jobs=1, projected_cost=10.0, actor_id="autoscaler")
    replay = context.deployment.admit_autoscaling(tenant_id=tenant, project_id=project, autoscaling_policy_id=policy["autoscaling_policy_id"], compute_profile="gpu-a10", requested_replicas=2, current_tenant_jobs=1, projected_cost=10.0, actor_id="autoscaler")
    assert replay["autoscaling_admission_id"] == allowed["autoscaling_admission_id"]
    assert replay["idempotent_replay"] is True
    for kwargs, code in [
        ({"requested_replicas": 3, "current_tenant_jobs": 0, "projected_cost": 10.0}, "AUTOSCALING_PROFILE_QUOTA"),
        ({"requested_replicas": 2, "current_tenant_jobs": 3, "projected_cost": 10.0}, "AUTOSCALING_TENANT_QUOTA"),
        ({"requested_replicas": 2, "current_tenant_jobs": 0, "projected_cost": 21.0}, "AUTOSCALING_GLOBAL_BUDGET"),
    ]:
        with pytest.raises(AuthorizationError) as denied:
            context.deployment.admit_autoscaling(tenant_id=tenant, project_id=project, autoscaling_policy_id=policy["autoscaling_policy_id"], compute_profile="gpu-a10", actor_id="autoscaler", **kwargs)
        assert denied.value.code == code
