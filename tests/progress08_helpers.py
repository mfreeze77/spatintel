from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings


def now() -> datetime:
    return datetime.now(UTC)


def bootstrap(tmp_path: Path, *, name: str = "p08") -> tuple[PlatformContext, str, str]:
    context = PlatformContext.create(temporary_settings(tmp_path / name))
    tenant = context.tenancy.create_tenant(
        f"{name} tenant", tenant_id=f"{name}-tenant", actor_id="bootstrap"
    )
    project = context.tenancy.create_project(
        tenant,
        f"{name} project",
        vertical="platform",
        classification="internal",
        project_id=f"{name}-project",
        actor_id="bootstrap",
    )
    return context, tenant, project


def compute_profile(context: PlatformContext | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "cpu-reference",
        "revision": "progress08-v1",
        "resolution": "518x378",
        "dtype": "float32",
        "backend": "cpu",
        "model_id": "approved-local-baseline",
        "checkpoint_hash": "c" * 64,
        "window_policy": {"mode": "bounded", "frames": 320, "overlap": 32},
        "memory_limit_mb": 4096,
        "timeout_seconds": 3600,
        "output_class": "reference",
        "quality_tier": "synthetic-reference",
        "cuda_version": None,
        "driver_constraint": None,
        "container_digest": "ghcr.io/spatial-intelligence-platform/sip-python@sha256:" + "1" * 64,
        "tenant_isolation": "reference_local",
        "oom_fallback": {"mode": "fail_and_retain_checkpoint"},
        "expected_runtime_seconds": 120.0,
        "peak_vram_mb": 0,
        "peak_ram_mb": 2048,
        "cost_stage_weights": {
            "decode": 0.05,
            "inference": 0.30,
            "optimization": 0.15,
            "fusion": 0.15,
            "splat": 0.15,
            "semantic": 0.10,
            "storage": 0.05,
            "egress": 0.05,
        },
        "actor_id": "compute-governance",
    }
    if context is None:
        return payload
    return context.operations_intelligence.register_compute_profile(**payload)


def _prices() -> dict[str, dict[str, Any]]:
    units = {
        "cpu_seconds": "second",
        "gpu_seconds": "second",
        "memory_gb_seconds": "gb-second",
        "object_bytes_hot": "byte-month",
        "object_bytes_cold": "byte-month",
        "database_bytes": "byte-month",
        "requests": "request",
        "search_units": "unit",
        "vector_units": "unit",
        "egress_bytes": "byte",
        "transcription_seconds": "second",
        "ocr_pages": "page",
        "model_api_units": "unit",
        "support_minutes": "minute",
    }
    rates = {
        "cpu_seconds": 0.00002,
        "gpu_seconds": 0.0005,
        "memory_gb_seconds": 0.000003,
        "object_bytes_hot": 0.00000000003,
        "object_bytes_cold": 0.00000000001,
        "database_bytes": 0.00000000004,
        "requests": 0.000001,
        "search_units": 0.0002,
        "vector_units": 0.0003,
        "egress_bytes": 0.00000000009,
        "transcription_seconds": 0.0001,
        "ocr_pages": 0.001,
        "model_api_units": 0.01,
        "support_minutes": 0.05,
    }
    return {key: {"rate": rates[key], "unit": units[key]} for key in sorted(units)}


def current_catalog_args(tenant_id: str, *, version: str = "2026-07-local") -> dict[str, Any]:
    effective = now() - timedelta(days=1)
    return {
        "tenant_id": tenant_id,
        "version": version,
        "currency": "USD",
        "effective_at": effective,
        "expires_at": effective + timedelta(days=365),
        "prices": _prices(),
        "source_reference": f"synthetic-price-catalog:{version}",
        "source_hash": sha256_bytes(f"synthetic-price-catalog:{version}".encode("utf-8")),
        "actor_id": "cost-governance",
    }


def price_catalog(
    context: PlatformContext, tenant_id: str, *, version: str = "2026-07-local"
) -> dict[str, Any]:
    return context.operations_intelligence.register_price_catalog(
        **current_catalog_args(tenant_id, version=version)
    )


def cost_estimate(
    context: PlatformContext,
    tenant_id: str,
    project_id: str,
    compute_profile_id: str,
    price_catalog_id: str,
    *,
    run_id: str = "reference-run",
    quantity: float = 1.0,
) -> dict[str, Any]:
    return context.operations_intelligence.estimate_cost(
        tenant_id=tenant_id,
        project_id=project_id,
        run_id=run_id,
        operation_id=None,
        capture_id=f"capture-{run_id}",
        compute_profile_id=compute_profile_id,
        price_catalog_id=price_catalog_id,
        input_class={
            "scene_minutes": 1.0,
            "frames": 1800,
            "area_m2": 25.0,
            "peak_concurrency": 1,
            "headroom_ratio": 1.2,
        },
        quantities={"cpu_seconds": float(quantity)},
        ttl_seconds=3600,
        actor_id="cost-estimator",
    )


def telemetry(
    context: PlatformContext,
    tenant_id: str,
    project_id: str,
    *,
    telemetry_type: str = "log",
    correlation_id: str = "corr-progress08",
    payload: dict[str, Any] | None = None,
    labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return context.operations_intelligence.record_telemetry(
        tenant_id=tenant_id,
        project_id=project_id,
        telemetry_type=telemetry_type,
        service="control-api",
        release="1.1.0-progress08",
        correlation_id=correlation_id,
        trace_id="a" * 32,
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        operation_id="operation-progress08",
        route_template="/v1/projects/{project_id}/operations",
        stage="support",
        model_id=None,
        checkpoint_hash=None,
        capture_profile=None,
        hardware_profile="cpu-reference",
        execution_profile="local",
        queue_class=None,
        vertical="platform",
        severity="info",
        outcome="passed",
        stable_error_code=None,
        payload=payload or {"message_code": "operation_ok", "duration_ms": 2.0},
        labels=labels or {"support_profile": "metadata-only"},
        actor_id="ops-agent",
    )
