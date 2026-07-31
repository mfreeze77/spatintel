#!/usr/bin/env python3
"""Run the synthetic, non-production Progress 09 deployment-profile demonstration."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from sip.canonical import canonical_sha256
from sip.context import PlatformContext, temporary_settings
from sip.errors import AuthorizationError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build/evidence/demo-progress09-deployment.json"


def _profile(*, name: str, mode: str, digest: str, cloud: bool) -> dict[str, Any]:
    return {
        "name": name,
        "revision": "1.0.0",
        "mode": mode,
        "features": {
            "capture": {"enabled": True, "requires_cloud_connectivity": False, "when_unavailable": "continue_local", "administrator_notice": "Capture remains local."},
            "gpu_reconstruction": {"enabled": cloud, "requires_cloud_connectivity": cloud, "when_unavailable": "queue_or_use_cpu_reference", "administrator_notice": "Cloud GPU use requires explicit admission."},
        },
        "service_images": {"control-api": f"ghcr.io/spatial-intelligence-platform/control-api:v1@sha256:{digest * 64}"},
        "infrastructure_versions": {"postgres": "16.4", "kubernetes": "1.31.4", "terraform": "1.9.8"},
        "secret_references": {"database": "secret://sip/database", "object_store": "secret://sip/object-store"},
        "network_policy": {"default_deny_ingress": True, "default_deny_egress": True, "allowed_egress": ["dns", "database", "object-store"]},
        "resource_limits": {"control-api": {"cpu": 1.0, "memory_mb": 512}},
        "supported_regions": ["local", "us-east-1"] if cloud else ["local"],
        "degraded_modes": {"cloud_unavailable": "local_queue", "provider_unavailable": "open_export"},
        "provider_replacements": {"database": {"contract": "postgresql", "export": "open-sql"}, "object_store": {"contract": "s3-compatible", "export": "preservation-package"}},
        "production_approved": False,
    }


def _aws() -> dict[str, Any]:
    replacements = {key: {"contract": key, "export": f"open-{key}"} for key in ("database", "object_store", "queue", "workflow", "kms", "secrets", "cdn", "gpu")}
    return {
        "environment": "synthetic-reference",
        "account_boundary": "nonproduction-account",
        "region": "us-east-1",
        "infrastructure_versions": {"terraform": "1.9.8", "kubernetes": "1.31.4"},
        "network": {"private_subnets": True, "default_deny_egress": True, "separate_environment_boundary": True},
        "database": {"private": True, "encrypted": True, "backup_enabled": True, "approved_identity_only": True, "public_access": False, "secret_reference": "secret://aws/database"},
        "object_store": {"private": True, "encrypted": True, "backup_enabled": True, "approved_identity_only": True, "public_access": False, "secret_reference": "secret://aws/object-store"},
        "queue": {"dead_letter_enabled": True, "tenant_quota_enforced": True, "budget_enforced": True, "secret_reference": "secret://aws/queue"},
        "kms": {"least_privilege": True, "audit_enabled": True, "key_reference": "secret://aws/kms"},
        "secrets": {"least_privilege": True, "audit_enabled": True, "references_only": True, "store_reference": "secret://aws/secrets"},
        "cdn": {"signed_authorization": True, "redacted_derivatives_only": True, "raw_asset_origin": False, "immutable_derivatives": True},
        "gpu": {"isolated_subnets": True, "restricted_egress": True, "prebaked_approved_models": True},
        "export_replacement_paths": replacements,
    }


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sip-progress09-demo-") as directory:
        context = PlatformContext.create(temporary_settings(Path(directory)))
        tenant = context.tenancy.create_tenant("Synthetic deployment tenant", tenant_id="p09-demo-tenant", actor_id="demo")
        project = context.tenancy.create_project(tenant, "Synthetic deployment project", vertical="platform", classification="internal", project_id="p09-demo-project", actor_id="demo")
        local = context.deployment.register_profile(**_profile(name="local-demo", mode="local_only", digest="1", cloud=False), actor_id="demo")
        hybrid = context.deployment.register_profile(**_profile(name="hybrid-demo", mode="hybrid", digest="2", cloud=True), actor_id="demo")
        residency = context.deployment.register_residency_policy(
            tenant_id=tenant, project_id=project, revision="1.0.0", home_region="local",
            allowed_regions=["local", "us-east-1"], allowed_modes=["local_only", "hybrid"],
            asset_rules={"raw_capture": {"allowed_regions": ["local"], "allowed_modes": ["local_only", "hybrid"]}, "redacted_derivative": {"allowed_regions": ["local", "us-east-1"], "allowed_modes": ["local_only", "hybrid"]}},
            worker_rules={"reference-worker": {"allowed_regions": ["local"], "allowed_modes": ["local_only", "hybrid"]}, "gpu": {"allowed_regions": ["us-east-1"], "allowed_modes": ["hybrid"]}},
            provider_rules={"approved-local": {"allowed_regions": ["local"], "allowed_purposes": ["processing"]}},
            default_action="deny", actor_id="demo",
        )
        binding = context.deployment.assign_project_profile(
            tenant_id=tenant, project_id=project, deployment_profile_id=local["deployment_profile_id"],
            residency_policy_id=residency["residency_policy_id"], transfer_policy_id=None, revision="1.0.0",
            feature_overrides={}, cloud_dependencies_acknowledged=False, actor_id="demo",
        )
        allowed = context.deployment.authorize_admission(
            tenant_id=tenant, project_id=project, admission_type="worker_schedule", deployment_profile_id=local["deployment_profile_id"],
            region="local", request={"worker_class": "reference-worker"}, actor_id="demo",
        )
        denied_region = False
        try:
            context.deployment.authorize_admission(
                tenant_id=tenant, project_id=project, admission_type="asset_upload", deployment_profile_id=local["deployment_profile_id"],
                region="us-east-1", request={"asset_class": "raw_capture"}, actor_id="demo",
            )
        except AuthorizationError:
            denied_region = True
        migration = context.deployment.create_project_migration(
            tenant_id=tenant, project_id=project, source_profile_id=local["deployment_profile_id"], target_profile_id=hybrid["deployment_profile_id"],
            idempotency_key="p09-demo-migration", actor_id="demo",
        )
        completed = context.deployment.complete_project_migration(tenant_id=tenant, project_id=project, migration_id=migration["migration_id"], actor_id="demo")
        policy = context.deployment.register_autoscaling_policy(
            tenant_id=tenant, project_id=project, queue_class="gpu", revision="1.0.0", min_replicas=0, max_replicas=2,
            tenant_concurrency_limit=2, profile_quotas={"gpu-a10": 1}, global_budget_limit=10.0, currency="USD",
            dead_letter={"enabled": True, "queue": "gpu-dlq", "max_attempts": 3}, restricted_egress=True, actor_id="demo",
        )
        scale = context.deployment.admit_autoscaling(
            tenant_id=tenant, project_id=project, autoscaling_policy_id=policy["autoscaling_policy_id"], compute_profile="gpu-a10",
            requested_replicas=1, current_tenant_jobs=0, projected_cost=5.0, current_replicas=0, actor_id="demo",
        )
        aws = context.deployment.register_aws_environment(**_aws(), actor_id="demo")
        production_denied = False
        try:
            context.deployment.production_admission(deployment_profile_id=hybrid["deployment_profile_id"], aws_environment_id=aws["aws_environment_id"], evidence={}, actor_id="demo")
        except AuthorizationError:
            production_denied = True
        result = {
            "schema": "sip.progress09-deployment-demo/v1",
            "status": "passed_complete" if all((allowed["decision"] == "allow", denied_region, completed["validation"]["preserved"], production_denied)) else "failed",
            "synthetic_only": True,
            "production_authorized": False,
            "progress_10_authorized": False,
            "profile_hashes": {"local": local["profile_hash"], "hybrid": hybrid["profile_hash"]},
            "binding_hash": binding["binding_hash"],
            "residency_denial_proven": denied_region,
            "migration": {"state": completed["state"], "preserved": completed["validation"]["preserved"], "source_snapshot_hash": completed["source_snapshot_hash"], "target_snapshot_hash": completed["target_snapshot_hash"]},
            "autoscaling": {"decision": scale["decision"], "admitted_replicas": scale["admitted_replicas"]},
            "aws": {"manifest_hash": aws["manifest_hash"], "evidence_class": aws["evidence_class"], "production_approved": aws["production_approved"]},
            "production_admission_denied": production_denied,
        }
        result["evidence_hash"] = canonical_sha256(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
