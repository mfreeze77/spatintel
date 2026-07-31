#!/usr/bin/env python3
"""Generate deterministic Progress 09 deployment-profile fixtures.

The generated profiles are structural, synthetic, and deliberately production-denied.
They are suitable for contract tests and operator planning, not proof that Docker,
Kubernetes, edge hardware, or AWS has actually been deployed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "infrastructure" / "deployment" / "profiles"
IMAGE_LOCK = ROOT / "infrastructure" / "deployment" / "image-lock.json"
SCHEMA = "sip.deployment-profile-fixture/v1"
ZERO = "0" * 64

SERVICES = (
    "control-api", "identity-policy", "capture-service", "workflow-service",
    "scene-service", "evidence-service", "search-service", "export-service",
    "audit-service", "security-ops", "operations-intelligence", "deployment-control",
)


def _image(name: str) -> str:
    return f"ghcr.io/spatial-intelligence-platform/{name}:1.1.0@sha256:{ZERO}"


def _base(mode: str, regions: list[str], *, cloud: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "revision": "1.0.0",
        "mode": mode,
        "evidence_class": "synthetic_structural",
        "production_authorized": False,
        "image_digest_state": "unresolved-development-sentinel",
        "service_images": {name: _image(name) for name in SERVICES},
        "infrastructure_versions": {
            "docker_compose": "2.39.1",
            "kubernetes": "1.34.0",
            "terraform": "1.13.0",
            "postgresql": "17.5",
            "valkey": "8.1.3",
            "object_store_api": "s3-compatible-v1",
        },
        "secret_references": {
            "database": "secret://sip/database",
            "object_store": "secret://sip/object-store",
            "signing": "vault://sip/signing",
            "workload_identity": "secret://sip/workload-identity",
        },
        "network_policy": {
            "default_deny_ingress": True,
            "default_deny_egress": True,
            "allowed_egress": ["dns", "postgresql", "valkey", "object-store"],
        },
        "resource_limits": {
            "control_api": {"cpu": 2.0, "memory_mb": 2048},
            "worker_reference": {"cpu": 4.0, "memory_mb": 8192},
        },
        "supported_regions": regions,
        "features": {
            "capture": {"enabled": True, "requires_cloud_connectivity": False, "when_unavailable": "continue_local", "administrator_notice": "Capture remains local."},
            "gpu_reconstruction": {"enabled": cloud, "requires_cloud_connectivity": cloud, "when_unavailable": "queue_or_cpu_reference", "administrator_notice": "Cloud GPU execution is not available without residency and deployment admission."},
            "semantic_viewer": {"enabled": True, "requires_cloud_connectivity": False, "when_unavailable": "static_semantic_fallback", "administrator_notice": "Viewer degrades without changing authority."},
        },
        "provider_replacement_paths": {
            "database": "docs/operator/provider-replacement/database.md",
            "object_store": "docs/operator/provider-replacement/object-store.md",
            "queue": "docs/operator/provider-replacement/queue.md",
            "workflow": "docs/operator/provider-replacement/workflow.md",
            "kms": "docs/operator/provider-replacement/kms.md",
            "secrets": "docs/operator/provider-replacement/secrets.md",
            "cdn": "docs/operator/provider-replacement/cdn.md",
            "gpu": "docs/operator/provider-replacement/gpu.md",
        },
    }


def documents() -> dict[str, dict[str, Any]]:
    local = _base("local_only", ["local"], cloud=False)
    local.update({
        "profile_id": "local-only",
        "cloud_dependencies": [],
        "storage": {"database": "local-postgresql", "object_store": "local-s3-compatible", "queue": "local-valkey"},
        "upgrade": {"offline": True, "signed_packages": True, "rollback_required": True, "export_compatibility_required": True},
    })
    edge = _base("edge", ["local-edge"], cloud=False)
    edge.update({
        "profile_id": "edge",
        "edge": {"unique_identity": True, "short_lived_workload_identity": True, "disk_encryption_attestation": True, "signed_offline_updates": True, "health_and_revocation": True},
        "cloud_dependencies": [],
    })
    hybrid = _base("hybrid", ["local-edge", "us-east-1"], cloud=True)
    hybrid.update({
        "profile_id": "hybrid",
        "cloud_dependencies": ["approved_gpu_pool"],
        "transfer": {"default_action": "deny", "minimum_sensitive_stage": "redacted_derivative", "approval_required": True},
        "residency": {"admission_before_upload": True, "admission_before_worker_schedule": True},
    })
    aws = _base("aws_reference", ["us-east-1"], cloud=True)
    aws.update({
        "profile_id": "aws-reference",
        "account_boundary": "separate-environment-account",
        "network_policy": {"default_deny_ingress": True, "default_deny_egress": True, "allowed_egress": ["dns", "private-postgresql", "private-object-store", "private-queue"], "private_subnets": True},
        "database": {"private": True, "encrypted": True, "backup_enabled": True, "approved_identity_only": True, "public_access": False},
        "object_store": {"private": True, "encrypted": True, "backup_enabled": True, "approved_identity_only": True, "public_access": False},
        "queue": {"dead_letter_enabled": True, "tenant_quota_enforced": True, "budget_enforced": True, "restricted_egress": True},
        "cdn": {"signed_authorization": True, "redacted_derivatives_only": True, "raw_asset_origin": False, "immutable_derivatives": True},
        "kms": {"least_privilege": True, "audit_enabled": True},
        "secrets": {"least_privilege": True, "audit_enabled": True},
        "gpu": {"isolated_subnets": True, "restricted_egress": True, "prebaked_approved_models": True},
        "provider_replacement_paths": _base("aws_reference", ["us-east-1"], cloud=True)["provider_replacement_paths"],
        "production_blockers": ["executed_terraform", "executed_kubernetes", "external_security_review", "production_image_digests"],
    })
    return {"local-only.json": local, "edge.json": edge, "hybrid.json": hybrid, "aws-reference.json": aws}


def _render(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def generate(*, check: bool = False) -> int:
    expected = documents()
    image_lock = {
        "schema": "sip.image-lock/v1",
        "state": "development_sentinels_unresolved",
        "production_authorized": False,
        "images": {name: _image(name) for name in SERVICES},
        "content_sha256": hashlib.sha256(_render({name: _image(name) for name in SERVICES}).encode()).hexdigest(),
    }
    targets = {OUTPUT / name: _render(value) for name, value in expected.items()}
    targets[IMAGE_LOCK] = _render(image_lock)
    drift = []
    for path, content in targets.items():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if drift:
        raise SystemExit("deployment profile drift: " + ", ".join(drift))
    print(f"deployment profiles: {'current' if check else 'generated'} ({len(targets)} artifacts)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return generate(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
