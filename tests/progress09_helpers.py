from __future__ import annotations

import base64
import hmac
from hashlib import sha256
from pathlib import Path
from typing import Any

from sip.context import PlatformContext, temporary_settings

DIGEST_A = "a" * 64


def bootstrap(tmp_path: Path, *, name: str = "p09") -> tuple[PlatformContext, str, str]:
    context = PlatformContext.create(temporary_settings(tmp_path / name))
    tenant = context.tenancy.create_tenant(f"{name} tenant", tenant_id=f"{name}-tenant", actor_id="bootstrap")
    project = context.tenancy.create_project(
        tenant,
        f"{name} project",
        vertical="platform",
        classification="internal",
        project_id=f"{name}-project",
        actor_id="bootstrap",
    )
    return context, tenant, project


def feature_map(*, cloud_enabled: bool = False) -> dict[str, Any]:
    return {
        "capture": {
            "enabled": True,
            "requires_cloud_connectivity": False,
            "when_unavailable": "continue_local",
            "administrator_notice": "Capture remains available locally.",
        },
        "gpu_reconstruction": {
            "enabled": cloud_enabled,
            "requires_cloud_connectivity": True,
            "when_unavailable": "queue_or_use_cpu_reference",
            "administrator_notice": "Cloud GPU use requires explicit deployment acknowledgement.",
        },
        "hybrid-viewer": {
            "enabled": cloud_enabled,
            "requires_cloud_connectivity": cloud_enabled,
            "when_unavailable": "use_local_semantic_fallback",
            "administrator_notice": "Cloud visual layers require explicit deployment acknowledgement.",
        },
    }


def profile_args(
    *,
    name: str = "hybrid-profile",
    revision: str = "1.0.0",
    mode: str = "hybrid",
    regions: list[str] | None = None,
    cloud_enabled: bool | None = None,
    cloud: bool | None = None,
    image_digit: str = "1",
    digest_character: str | None = None,
) -> dict[str, Any]:
    digest = digest_character or image_digit
    if len(digest) != 1 or digest.lower() not in "0123456789abcdef":
        raise ValueError("digest character must be one lowercase hexadecimal character")
    if cloud_enabled is None:
        cloud_enabled = cloud if cloud is not None else mode in {"hybrid", "aws_reference"}
    if regions is None:
        regions = ["local", "us-east-1", "us-central-1"] if mode != "local_only" else ["local"]
    return {
        "name": name,
        "revision": revision,
        "mode": mode,
        "features": feature_map(cloud_enabled=bool(cloud_enabled)),
        "service_images": {
            "control-api": f"ghcr.io/spatial-intelligence-platform/control-api:v1@sha256:{digest * 64}",
            "workflow-service": f"ghcr.io/spatial-intelligence-platform/workflow-service:v1@sha256:{digest * 64}",
        },
        "infrastructure_versions": {
            "postgres": "16.4",
            "minio": "RELEASE.2025-01-20T14-49-07Z",
            "redis": "7.4.1",
        },
        "secret_references": {
            "database": "secret://sip/database",
            "object_store": "secret://sip/object-store",
        },
        "network_policy": {
            "default_deny_ingress": True,
            "default_deny_egress": True,
            "allowed_egress": ["dns", "object-store"],
        },
        "resource_limits": {
            "control-api": {"cpu": 1.0, "memory_mb": 512},
            "workflow-service": {"cpu": 2.0, "memory_mb": 1024},
        },
        "supported_regions": regions,
        "degraded_modes": {
            "cloud_unavailable": "local_queue",
            "provider_unavailable": "open_export",
        },
        "provider_replacements": {
            "database": {"contract": "postgresql", "export": "open-sql"},
            "object_store": {"contract": "s3-compatible", "export": "preservation-package"},
        },
        "production_approved": False,
    }


def residency_args(*, modes: list[str] | None = None, regions: list[str] | None = None) -> dict[str, Any]:
    modes = modes or ["local_only", "edge", "hybrid", "aws_reference"]
    regions = regions or ["local", "us-east-1", "us-central-1"]
    return {
        "revision": "1.0.0",
        "home_region": regions[0],
        "allowed_regions": regions,
        "allowed_modes": modes,
        "asset_rules": {
            "generic_asset": {"allowed_regions": regions, "allowed_modes": modes},
            "source": {"allowed_regions": [regions[0]], "allowed_modes": modes},
            "raw_capture": {"allowed_regions": [regions[0]], "allowed_modes": modes},
            "redacted_derivative": {"allowed_regions": regions, "allowed_modes": modes},
        },
        "worker_rules": {
            "reference-worker": {"allowed_regions": regions, "allowed_modes": modes},
            "cpu": {"allowed_regions": regions, "allowed_modes": modes},
            "gpu": {"allowed_regions": [r for r in regions if r != "local"] or regions, "allowed_modes": [m for m in modes if m != "local_only"] or modes},
            "reconstruction": {"allowed_regions": regions, "allowed_modes": modes},
        },
        "provider_rules": {
            "approved-local": {"allowed_regions": [regions[0]], "allowed_purposes": ["processing", "reconstruction"]},
        },
        "default_action": "deny",
    }


def assign_profile(
    context: PlatformContext,
    tenant: str,
    project: str,
    profile_id: str,
    residency_id: str | None,
    *,
    transfer_id: str | None = None,
    cloud_ack: bool = True,
) -> dict[str, Any]:
    return context.deployment.assign_project_profile(
        tenant_id=tenant,
        project_id=project,
        deployment_profile_id=profile_id,
        residency_policy_id=residency_id,
        transfer_policy_id=transfer_id,
        revision="1.0.0",
        feature_overrides={},
        cloud_dependencies_acknowledged=cloud_ack,
        actor_id="deployment-admin",
    )


def create_profiles(context: PlatformContext) -> tuple[dict[str, Any], dict[str, Any]]:
    local = context.deployment.register_profile(
        **profile_args(name="local-only", revision="1.0.0", mode="local_only", regions=["local"], image_digit="1"),
        actor_id="deployment-admin",
    )
    hybrid = context.deployment.register_profile(
        **profile_args(name="hybrid", revision="1.0.0", mode="hybrid", regions=["local", "us-east-1"], cloud_enabled=True, image_digit="2"),
        actor_id="deployment-admin",
    )
    return local, hybrid


def create_residency(context: PlatformContext, tenant: str, project: str, *, modes: list[str] | None = None) -> dict[str, Any]:
    return context.deployment.register_residency_policy(
        tenant_id=tenant,
        project_id=project,
        **residency_args(modes=modes or ["local_only", "hybrid"], regions=["local", "us-east-1"]),
        actor_id="residency-officer",
    )


def bind_local(context: PlatformContext, tenant: str, project: str, profile: dict[str, Any], residency: dict[str, Any]) -> dict[str, Any]:
    return assign_profile(
        context,
        tenant,
        project,
        profile["deployment_profile_id"],
        residency["residency_policy_id"],
        cloud_ack=False,
    )


def headers(
    tenant: str,
    project: str,
    *,
    subject: str = "deployment-admin",
    role: str = "deployment_admin",
    purposes: str = "operations,deployment,release,reconstruction",
) -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": role,
        "X-SIP-Purposes": purposes,
        "X-SIP-Audience": "private",
    }


def direct_digest_signature(context: PlatformContext, digest: str) -> str:
    return base64.b64encode(hmac.new(context.deployment.signing_key, digest.encode("ascii"), sha256).digest()).decode("ascii")


def edge_manifest(*, release: str = "1.0.0", image_digit: str = "3", commit_digit: str = "4") -> dict[str, Any]:
    return {
        "image": f"ghcr.io/spatial-intelligence-platform/edge:{release}@sha256:{image_digit * 64}",
        "source_commit": commit_digit * 40,
        "release": release,
    }

# Backward-compatible names used by the Progress 09 contract/security suites.
deployment_headers = headers


def aws_environment_args() -> dict[str, Any]:
    replacements = {
        key: {"contract": key.replace("_", "-"), "export": f"open-{key.replace('_', '-')}", "replacement": f"self-hosted-{key.replace('_', '-')}"}
        for key in ("database", "object_store", "queue", "workflow", "kms", "secrets", "cdn", "gpu")
    }
    return {
        "environment": "synthetic-aws-reference",
        "account_boundary": "sip-nonproduction",
        "region": "us-east-1",
        "infrastructure_versions": {
            "terraform": "1.9.8",
            "kubernetes": "1.31.4",
            "postgres": "16.4",
            "object_store": "1.0.0",
            "queue": "7.4.1",
        },
        "network": {
            "private_subnets": True,
            "default_deny_egress": True,
            "separate_environment_boundary": True,
            "ingress": "private-load-balancer",
        },
        "database": {
            "private": True,
            "encrypted": True,
            "backup_enabled": True,
            "approved_identity_only": True,
            "public_access": False,
            "secret_reference": "secret://aws/database",
        },
        "object_store": {
            "private": True,
            "encrypted": True,
            "backup_enabled": True,
            "approved_identity_only": True,
            "public_access": False,
            "secret_reference": "secret://aws/object-store",
        },
        "queue": {
            "dead_letter_enabled": True,
            "tenant_quota_enforced": True,
            "budget_enforced": True,
            "secret_reference": "secret://aws/queue",
        },
        "kms": {
            "least_privilege": True,
            "audit_enabled": True,
            "key_reference": "secret://aws/kms",
        },
        "secrets": {
            "least_privilege": True,
            "audit_enabled": True,
            "references_only": True,
            "store_reference": "secret://aws/secrets-manager",
        },
        "cdn": {
            "signed_authorization": True,
            "redacted_derivatives_only": True,
            "raw_asset_origin": False,
            "immutable_derivatives": True,
        },
        "gpu": {
            "isolated_subnets": True,
            "restricted_egress": True,
            "prebaked_approved_models": True,
            "autoscaling_budget_enforced": True,
        },
        "export_replacement_paths": replacements,
    }
