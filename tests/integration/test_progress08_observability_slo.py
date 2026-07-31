from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sip.errors import NotFoundError, ValidationError
from tests.progress08_helpers import bootstrap, telemetry


def test_progress08_privacy_safe_telemetry_trace_and_quality_dashboard(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003, ARCOBS-004, ARCOBS-005 structured tenant-safe logs, metrics, traces, quality signals, and immutable audit correlation fail closed."""
    context, tenant, project = bootstrap(tmp_path, name="p08-observe")
    recorded = telemetry(context, tenant, project)
    assert recorded["trace_id"] == "a" * 32
    assert tenant not in str(recorded)
    assert project not in str(recorded)
    quality = context.operations_intelligence.record_telemetry(
        tenant_id=tenant, project_id=project, telemetry_type="quality", service="reconstruction-worker",
        release="1.1.0-progress08", correlation_id="quality-1", trace_id="a" * 32,
        traceparent="00-" + "a" * 32 + "-" + "c" * 16 + "-01", operation_id="operation-1",
        route_template=None, stage="registration", model_id="model-a", checkpoint_hash="d" * 64,
        capture_profile="room-reference", hardware_profile="cpu-reference", execution_profile="synthetic",
        queue_class="cpu-reference", vertical="platform", severity="warning", outcome="failed",
        stable_error_code="REGISTRATION_QUALITY_LOW",
        payload={"drift_ratio": 0.03, "coverage_ratio": 0.92, "residual_meters": 0.02, "confidence_ratio": 0.81, "failed_regions": 1, "prior_delta_ratio": 0.01},
        labels={"quality_tier": "reference"}, actor_id="ops-agent",
    )
    dashboard = context.operations_intelligence.quality_dashboard(tenant_id=tenant, project_id=project)
    assert dashboard["record_count"] == 1
    assert dashboard["groups"][0]["failed_regions"] == 1
    assert dashboard["raw_data_included"] is False
    query = context.operations_intelligence.query_telemetry(tenant_id=tenant, project_id=project, correlation_id="quality-1")
    assert query["count"] == 1 and query["records"][0]["telemetry_id"] == quality["telemetry_id"]

    other_tenant = context.tenancy.create_tenant("Other", tenant_id="p08-other-tenant", actor_id="bootstrap")
    other_project = context.tenancy.create_project(other_tenant, "Other", vertical="platform", classification="internal", project_id="p08-other-project", actor_id="bootstrap")
    with pytest.raises(NotFoundError):
        context.operations_intelligence.query_telemetry(tenant_id=other_tenant, project_id=project)
    assert context.operations_intelligence.query_telemetry(tenant_id=other_tenant, project_id=other_project)["count"] == 0

    with pytest.raises(ValidationError, match="non-approved field"):
        context.operations_intelligence.record_telemetry(
            tenant_id=tenant, project_id=project, telemetry_type="log", service="api", release="v1",
            correlation_id="secret-probe", trace_id=None, traceparent=None, operation_id=None,
            route_template=None, stage=None, model_id=None, checkpoint_hash=None, capture_profile=None,
            hardware_profile=None, execution_profile=None, queue_class=None, vertical=None,
            severity="info", outcome="success", stable_error_code=None,
            payload={"password": "SUPERSECRET"}, labels={}, actor_id="ops-agent",
        )
    with pytest.raises(ValidationError, match="different traces"):
        context.operations_intelligence.record_telemetry(
            tenant_id=tenant, project_id=project, telemetry_type="trace", service="api", release="v1",
            correlation_id="trace-spoof", trace_id="a" * 32,
            traceparent="00-" + "b" * 32 + "-" + "c" * 16 + "-01", operation_id=None,
            route_template=None, stage=None, model_id=None, checkpoint_hash=None, capture_profile=None,
            hardware_profile=None, execution_profile=None, queue_class=None, vertical=None,
            severity="info", outcome="success", stable_error_code=None,
            payload={"duration_ms": 1}, labels={}, actor_id="ops-agent",
        )


def test_progress08_slos_performance_budgets_and_external_evidence_labels(tmp_path: Path) -> None:
    """REQ: OPSPERF-001, OPSPERF-002, OPSPERF-003, OPSPERF-004, OPSPERF-005, OPSPERF-006 endpoint, viewer, capture, upload, pipeline, and noisy-neighbor budgets distinguish synthetic from external evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p08-slo")
    service = context.operations_intelligence
    slo = service.register_slo(
        tenant_id=tenant, project_id=project, name="search latency", target_type="search",
        dimensions={"endpoint_class": "search", "result_size_class": "small"},
        indicator={"metric": "duration_ms", "comparison": "<=", "threshold": 250.0},
        objective=0.99, percentile=0.95, window_seconds=3600,
        budget={"duration_ms": 250.0, "error_rate": 0.01}, degradation_behavior="bounded metadata navigation",
        evidence_class="synthetic_local", owner="sre", version="v1", actor_id="sre",
    )
    measured = service.record_slo_measurement(
        tenant_id=tenant, project_id=project, slo_id=slo["slo_id"],
        window_start=datetime.now(UTC) - timedelta(minutes=10), window_end=datetime.now(UTC),
        numerator=995, denominator=1000,
        dimensions={"endpoint_class": "search", "result_size_class": "small"},
        source_profile="local-reference", source_manifest_hash="1" * 64, actor_id="sre",
    )
    assert measured["status"] == "met"

    budget = service.register_performance_budget(
        tenant_id=tenant, project_id=project, profile_type="viewer", profile_name="desktop-small",
        input_class={"scene_size": "small"}, hardware_profile="desktop-reference",
        execution_profile="synthetic", model_id=None, checkpoint_hash=None, queue_class=None,
        vertical="platform", percentile=0.95, warm_state="warm", concurrency=1,
        budgets={"frame_time_ms": 33.3, "first_scene_ms": 2000, "memory_mb": 2048, "network_bytes": 10000000},
        degradation_behavior="semantic fallback", evidence_class="browser_device", version="v1", actor_id="sre",
    )
    evaluation = service.evaluate_performance_budget(
        tenant_id=tenant, project_id=project, performance_budget_id=budget["performance_budget_id"],
        observed={"frame_time_ms": 20, "first_scene_ms": 1000, "memory_mb": 1000, "network_bytes": 1000},
        evidence_class="synthetic_local", source_manifest_hash="2" * 64,
    )
    assert evaluation["passed"] is False
    assert evaluation["external_validation_required"] is True

    with pytest.raises(ValidationError, match="controlled vocabulary|high-cardinality"):
        service.register_slo(
            tenant_id=tenant, project_id=project, name="bad", target_type="api",
            dimensions={"asset_id": "asset-a"}, indicator={"metric": "duration_ms", "comparison": "<=", "threshold": 1},
            objective=0.9, percentile=0.9, window_seconds=60, budget={"duration_ms": 1},
            degradation_behavior="fail closed", evidence_class="synthetic_local", owner="sre", version="v1", actor_id="sre",
        )
