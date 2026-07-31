from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from tests.progress09_helpers import bind_local, create_profiles, create_residency


class RecoveryEnvironment(dict[str, Any]):
    """Mapping used by reusable helpers while retaining tuple-unpack compatibility."""

    def __iter__(self):
        yield self["context"]
        yield self["tenant"]
        yield self["project"]
        yield self["local"]


def bootstrap_recovery(tmp_path: Path, *, name: str = "p10") -> RecoveryEnvironment:
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
    local, hybrid = create_profiles(context)
    residency = create_residency(context, tenant, project)
    binding = bind_local(context, tenant, project, local, residency)
    return RecoveryEnvironment({
        "context": context,
        "tenant": tenant,
        "project": project,
        "local": local,
        "hybrid": hybrid,
        "residency": residency,
        "binding": binding,
    })


def ingest_evidence(
    context: PlatformContext,
    tenant: str,
    project: str,
    *,
    payload: bytes = b"progress-10-evidence",
    asset_id: str | None = None,
    retention_class: str = "project_record",
) -> dict[str, Any]:
    digest = sha256_bytes(payload)
    ref = context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=payload,
        media_type="application/octet-stream",
        original_name=f"{asset_id or 'evidence'}.bin",
        classification=Classification.INTERNAL,
        retention_class=retention_class,
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(
            source_ids=[f"fixture:{asset_id or digest}"],
            output_hash=digest,
            validation_result_id=digest,
        ),
        actor_id="fixture-builder",
        asset_id=asset_id,
        deployment_region="local",
        asset_class="source",
    )
    return {"asset_id": ref.asset_id, "sha256": ref.sha256}


def register_objective_and_point(
    env: dict[str, Any],
    *,
    idempotency_key: str = "recovery-point-1",
    requested_point_at: datetime | None = None,
    immutability_days: int = 30,
) -> tuple[dict[str, Any], dict[str, Any], datetime]:
    context: PlatformContext = env["context"]
    requested = requested_point_at or (datetime.now(timezone.utc) - timedelta(seconds=1))
    objective = context.recovery.register_recovery_objective(
        tenant_id=env["tenant"],
        project_id=env["project"],
        deployment_profile_id=env["local"]["deployment_profile_id"],
        data_class="project_record",
        service_class="canonical_control_plane",
        rpo_seconds=3600,
        rto_seconds=7200,
        degraded_behavior={"mode": "read_only", "writes": "closed_until_reconciled"},
        recovery_method={"type": "local_open_preservation", "portability_fallback": True},
        evidence_class="local_executed",
        actor_id="recovery-admin",
    )
    point = context.recovery.create_recovery_point(
        tenant_id=env["tenant"],
        project_id=env["project"],
        deployment_profile_id=env["local"]["deployment_profile_id"],
        region="local",
        requested_point_at=requested,
        immutability_days=immutability_days,
        evidence_class="local_executed",
        idempotency_key=idempotency_key,
        actor_id="recovery-admin",
    )
    return objective, point, requested


def verify_point(env: dict[str, Any], point: dict[str, Any]) -> dict[str, Any]:
    return env["context"].recovery.verify_recovery_point(
        tenant_id=env["tenant"],
        project_id=env["project"],
        recovery_point_id=point["recovery_point_id"],
        actor_id="recovery-operator",
    )


def isolated_target(env: dict[str, Any], suffix: str = "one") -> tuple[str, str]:
    return f"restore-{env['tenant']}-{suffix}", f"restore-{env['project']}-{suffix}"


def ingest_asset(
    context: PlatformContext,
    tenant: str,
    project: str,
    *,
    data: bytes = b"progress-10-asset",
    asset_id: str | None = None,
    retention_class: str = "project_record",
) -> dict[str, Any]:
    return ingest_evidence(
        context, tenant, project, payload=data, asset_id=asset_id, retention_class=retention_class
    )


def create_verified_point(
    context: PlatformContext,
    tenant: str,
    project: str,
    profile: dict[str, Any],
    *,
    key: str,
    requested_point_at: datetime | None = None,
) -> dict[str, Any]:
    requested = requested_point_at or (datetime.now(timezone.utc) - timedelta(seconds=1))
    point = context.recovery.create_recovery_point(
        tenant_id=tenant,
        project_id=project,
        deployment_profile_id=profile["deployment_profile_id"],
        region="local",
        requested_point_at=requested,
        immutability_days=30,
        evidence_class="local_executed",
        idempotency_key=key,
        actor_id="recovery-admin",
    )
    return context.recovery.verify_recovery_point(
        tenant_id=tenant,
        project_id=project,
        recovery_point_id=point["recovery_point_id"],
        actor_id="recovery-operator",
    )
