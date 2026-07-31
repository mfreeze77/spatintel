#!/usr/bin/env python3
"""Run the deterministic synthetic Progress 08 operations-intelligence demonstration."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings


def _prices() -> dict[str, dict[str, Any]]:
    units = {
        "cpu_seconds": "second", "gpu_seconds": "second", "memory_gb_seconds": "gb-second",
        "object_bytes_hot": "byte-month", "object_bytes_cold": "byte-month", "database_bytes": "byte-month",
        "requests": "request", "search_units": "unit", "vector_units": "unit", "egress_bytes": "byte",
        "transcription_seconds": "second", "ocr_pages": "page", "model_api_units": "unit", "support_minutes": "minute",
    }
    return {name: {"rate": 0.0001, "unit": unit} for name, unit in sorted(units.items())}


def run_demo(root: Path) -> dict[str, Any]:
    context = PlatformContext.create(temporary_settings(root / "runtime"))
    tenant = context.tenancy.create_tenant("Synthetic operations tenant", tenant_id="demo-ops-tenant", actor_id="demo")
    project = context.tenancy.create_project(
        tenant, "Synthetic operations project", vertical="platform", classification="internal",
        project_id="demo-ops-project", actor_id="demo",
    )
    service = context.operations_intelligence
    telemetry = service.record_telemetry(
        tenant_id=tenant, project_id=project, telemetry_type="log", service="control-api",
        release="1.1.0-progress08", correlation_id="demo-correlation", trace_id="a" * 32,
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01", operation_id="demo-operation",
        route_template="/v1/projects/{project_id}/operations", stage="admission", model_id=None,
        checkpoint_hash=None, capture_profile=None, hardware_profile="cpu-reference", execution_profile="local",
        queue_class="cpu-reference", vertical="platform", severity="info", outcome="passed",
        stable_error_code=None, payload={"message_code": "demo_ok", "duration_ms": 2.0},
        labels={"quality_tier": "synthetic-reference"}, actor_id="demo-ops",
    )
    slo = service.register_slo(
        tenant_id=tenant, project_id=project, name="demo API latency", target_type="api",
        dimensions={"endpoint_class": "operations", "result_size_class": "small"},
        indicator={"metric": "duration_ms", "comparison": "<=", "threshold": 250.0},
        objective=0.99, percentile=0.95, window_seconds=3600,
        budget={"duration_ms": 250.0, "error_rate": 0.01}, degradation_behavior="fail closed",
        evidence_class="synthetic_local", owner="sre", version="v1", actor_id="sre",
    )
    measurement = service.record_slo_measurement(
        tenant_id=tenant, project_id=project, slo_id=slo["slo_id"],
        window_start=datetime.now(UTC) - timedelta(minutes=5), window_end=datetime.now(UTC),
        numerator=1000, denominator=1000,
        dimensions={"endpoint_class": "operations", "result_size_class": "small"},
        source_profile="synthetic-local", source_manifest_hash="1" * 64, actor_id="sre",
    )
    profile = service.register_compute_profile(
        name="demo-cpu", revision="v1", resolution="518x378", dtype="float32", backend="cpu",
        model_id="approved-local-baseline", checkpoint_hash="c" * 64,
        window_policy={"mode": "bounded", "frames": 320, "overlap": 32}, memory_limit_mb=4096,
        timeout_seconds=3600, output_class="reference", quality_tier="synthetic-reference",
        cuda_version=None, driver_constraint=None,
        container_digest="ghcr.io/spatial-intelligence-platform/sip-python@sha256:" + "1" * 64,
        tenant_isolation="reference_local", oom_fallback={"mode": "fail_and_retain_checkpoint"},
        expected_runtime_seconds=120.0, peak_vram_mb=0, peak_ram_mb=2048,
        cost_stage_weights={"decode": .05, "inference": .30, "optimization": .15, "fusion": .15, "splat": .15, "semantic": .10, "storage": .05, "egress": .05},
        actor_id="compute-governance",
    )
    effective = datetime.now(UTC) - timedelta(days=1)
    source_reference = "synthetic-price-catalog:demo-v1"
    catalog = service.register_price_catalog(
        tenant_id=tenant, version="demo-v1", currency="USD", effective_at=effective,
        expires_at=effective + timedelta(days=365), prices=_prices(), source_reference=source_reference,
        source_hash=sha256_bytes(source_reference.encode()), actor_id="cost-governance",
    )
    estimate = service.estimate_cost(
        tenant_id=tenant, project_id=project, run_id="demo-run", operation_id=None,
        capture_id="demo-capture", compute_profile_id=profile["compute_profile_id"],
        price_catalog_id=catalog["price_catalog_id"],
        input_class={"scene_minutes": 1.0, "frames": 1800, "area_m2": 25.0, "peak_concurrency": 1, "headroom_ratio": 1.2},
        quantities={"cpu_seconds": 120.0}, ttl_seconds=3600, actor_id="cost-estimator",
    )
    service.register_budget_policy(
        tenant_id=tenant, project_id=project, revision="demo-v1", currency="USD", period_seconds=86400,
        soft_limit=100.0, hard_limit=100.0, concurrency_limit=2, storage_limit_bytes=10_000_000,
        retention_limit_days=365, anomaly_threshold=1.5, actor_id="ops-admin",
    )
    reservation = service.reserve_budget(
        tenant_id=tenant, project_id=project, estimate_id=estimate["estimate_id"],
        idempotency_key="demo-reservation", operation_id=None, ttl_seconds=3600, requested_by="demo-operator",
    )
    requested = service.request_support_access(
        tenant_id=tenant, project_id=project,
        resource_scope={"resource_ids": [telemetry["telemetry_id"]], "telemetry_types": ["log"], "include_logs": True, "include_metrics": False, "include_traces": False},
        purpose="support", personnel=["support-engineer"], requested_by="customer-admin", duration_seconds=3600,
    )
    grant = service.approve_support_access(
        tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="customer-approver",
    )
    bundle = service.create_support_bundle(
        tenant_id=tenant, project_id=project, grant_id=grant["grant_id"],
        telemetry_ids=[telemetry["telemetry_id"]], hardware_profile={"device_tier": "synthetic-reference"},
        manifest_references=[{"kind": "release", "sha256": "2" * 64}], actor_id="support-engineer",
    )
    verified = service.verify_support_bundle(
        tenant_id=tenant, project_id=project, bundle_id=bundle["bundle_id"], actor_id="support-engineer",
    )
    return {
        "schema": "sip.progress08-operations-demo/v1",
        "status": "passed_complete",
        "evidence_class": "synthetic_local",
        "telemetry": {"telemetry_id": telemetry["telemetry_id"], "raw_data_included": False},
        "slo": {"slo_id": slo["slo_id"], "measurement_id": measurement["measurement_id"], "compliant": measurement["status"] == "met"},
        "cost": {"estimate_id": estimate["estimate_id"], "price_catalog_hash": catalog["catalog_hash"], "estimated_total": estimate["total_amount"]},
        "admission": {"reservation_id": reservation["reservation_id"], "state": reservation["state"]},
        "support": {"grant_state": grant["state"], "bundle_valid": verified["verification"]["valid"], "raw_media_included": bundle["manifest"]["raw_media_included"]},
        "progress_09_authorized": False,
        "production_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runtime/demo-progress08"))
    parser.add_argument("--output", type=Path, default=Path("build/evidence/demo-progress08-operations.json"))
    args = parser.parse_args()
    report = run_demo(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
