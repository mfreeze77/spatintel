from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings
from sip.observability import redact


def _client(tmp_path: Path) -> TestClient:
    context = PlatformContext.create(temporary_settings(tmp_path / "runtime"))
    return TestClient(create_app(context=context, service_name="control-api"))


def test_metrics_use_route_templates_and_security_headers(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002 HTTP metrics and correlation/security headers are retained."""
    client = _client(tmp_path)
    response = client.get("/health/live", headers={"X-Request-ID": "request-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'sip_http_requests_total{method="GET",route="/health/live",service="control-api",status="200"} 1.0' in metrics.text
    assert "sip_http_request_duration_seconds_bucket" in metrics.text
    assert "request-123" not in metrics.text


def test_invalid_request_id_and_content_length_are_bounded(tmp_path: Path) -> None:
    """REQ: ARCOBS-002 untrusted request metadata cannot become unbounded labels or identifiers."""
    client = _client(tmp_path)
    response = client.get("/health/live", headers={"X-Request-ID": "bad request id with spaces"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] != "bad request id with spaces"
    assert len(response.headers["x-request-id"]) <= 128

    response = client.request("POST", "/v1/tenants", headers={"Content-Length": "not-an-integer"}, content=b"{}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CONTENT_LENGTH_INVALID"


def test_log_redaction_removes_credentials_and_large_binary_payloads() -> None:
    """REQ: ARCOBS-001 telemetry must not emit secrets or raw evidence payloads."""
    source = {
        "authorization": "Bearer private",
        "nested": {"password": "unsafe", "normal": "ok"},
        "content_base64": "very-large-evidence",
        "bytes": b"secret-image-bytes",
    }
    result = redact(source)
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"]["password"] == "[REDACTED]"
    assert result["nested"]["normal"] == "ok"
    assert result["content_base64"] == "[REDACTED]"
    assert result["bytes"] == "[BYTES:18]"


def test_structured_logs_include_required_safe_context_without_raw_identifiers() -> None:
    """REQ: ARCOBS-001 logs retain release/service/context/trace/operation/outcome/error code safely."""
    import json
    import logging

    from sip.observability import (
        BoundTelemetryContext,
        JsonFormatter,
        bind_telemetry_context,
        pseudonymize_identifier,
    )

    tenant_id = "tenant-secret-facility"
    project_id = "project-family-private"
    with bind_telemetry_context(
        BoundTelemetryContext(
            request_id="request-safe",
            trace_id="a" * 32,
            operation_id="operation-safe",
            tenant_context=pseudonymize_identifier(tenant_id, namespace="tenant", key=b"k" * 32),
            project_context=pseudonymize_identifier(project_id, namespace="project", key=b"k" * 32),
        )
    ):
        record = logging.LogRecord(
            name="sip.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="provider failed with Bearer secret-token and password=hunter2",
            args=(),
            exc_info=None,
        )
        record.service = "test-service"
        record.release = "1.1.0-test"
        record.outcome = "denied"
        record.error_code = "PROVIDER_DENIED"
        record.fields = {"authorization": "Bearer secret", "normal": "ok"}
        payload = json.loads(JsonFormatter().format(record))

    assert payload["release"] == "1.1.0-test"
    assert payload["service"] == "test-service"
    assert payload["trace_id"] == "a" * 32
    assert payload["operation_id"] == "operation-safe"
    assert payload["outcome"] == "denied"
    assert payload["error_code"] == "PROVIDER_DENIED"
    assert payload["tenant_context"].startswith("h:")
    assert payload["project_context"].startswith("h:")
    serialized = json.dumps(payload)
    assert tenant_id not in serialized
    assert project_id not in serialized
    assert "secret-token" not in serialized
    assert "hunter2" not in serialized
    assert payload["fields"]["authorization"] == "[REDACTED]"


def test_worker_and_quality_metrics_use_only_governed_low_cardinality_labels() -> None:
    """REQ: ARCOBS-002, ARCOBS-004 worker/quality metrics never expose customer identifiers."""
    from sip.observability import PlatformObservability

    telemetry = PlatformObservability.create("worker-test")
    raw_facility = "Main Hospital West Wing / Patient 123"
    checkpoint = "f" * 64
    telemetry.observe_worker_run(
        capability="fusion.tsdf",
        model=raw_facility,
        checkpoint=checkpoint,
        capture_profile="construction-lidar-v1",
        outcome="succeeded",
        duration_seconds=4.2,
        queue_wait_seconds=0.7,
    )
    telemetry.observe_quality(
        capability="fusion.tsdf",
        model=raw_facility,
        checkpoint=checkpoint,
        capture_profile="construction-lidar-v1",
        drift_ratio=0.01,
        coverage_ratio=0.92,
        residual_meters=0.018,
        confidence_ratio=0.88,
        failed_regions=2,
        prior_delta_ratio=0.03,
    )
    metrics = telemetry.render().decode("utf-8")
    assert raw_facility not in metrics
    assert 'model="invalid"' in metrics
    assert 'checkpoint="sha256:ffffffffffffffff"' in metrics
    for required in (
        "sip_reconstruction_drift_ratio",
        "sip_reconstruction_coverage_ratio",
        "sip_reconstruction_residual_meters",
        "sip_reconstruction_confidence_ratio",
        "sip_reconstruction_failed_regions",
        "sip_reconstruction_quality_delta_ratio",
    ):
        assert required in metrics


def test_error_responses_include_safe_correlation_and_retryability(tmp_path: Path) -> None:
    """REQ: ARCOBS-001 stable errors carry correlation IDs without leaking server exceptions."""
    client = _client(tmp_path)
    invalid = client.request(
        "POST",
        "/v1/tenants",
        headers={"Content-Length": "invalid", "X-Request-ID": "correlation-123"},
        content=b"{}",
    )
    assert invalid.status_code == 400
    error = invalid.json()["error"]
    assert error["code"] == "CONTENT_LENGTH_INVALID"
    assert error["retryable"] is False
    assert error["correlation"]["request_id"] == "correlation-123"
    assert invalid.headers["x-trace-id"] == error["correlation"]["trace_id"]

    app = create_app(
        context=PlatformContext.create(temporary_settings(tmp_path / "boom-runtime")),
        service_name="control-api",
    )

    @app.get("/test/unhandled")
    def unhandled() -> None:
        raise RuntimeError("password=must-not-leak")

    response = TestClient(app, raise_server_exceptions=False).get("/test/unhandled")
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "INTERNAL_ERROR"
    assert body["retryable"] is True
    assert "must-not-leak" not in response.text
    assert body["correlation"]["request_id"] == response.headers["x-request-id"]


def test_operation_depth_inflight_and_retry_metrics_are_governed(tmp_path: Path) -> None:
    """REQ: ARCOBS-002 operation queues, active work, and retries use bounded manifest-derived labels."""
    from sip.observability import PlatformObservability

    context = PlatformContext.create(temporary_settings(tmp_path / "operation-metrics"))
    tenant_id = context.tenancy.create_tenant("Metrics", tenant_id="tenant-metrics", actor_id="fixture")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Metrics",
        vertical="platform",
        classification="internal",
        project_id="project-metrics",
        actor_id="fixture",
    )
    context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="fusion.tsdf",
        idempotency_key="metrics-depth",
        input_manifest={"points": []},
        actor_id="fixture",
    )
    telemetry = PlatformObservability.create("workflow-service")
    telemetry.worker_started("fusion.tsdf")
    telemetry.observe_worker_run(
        capability="fusion.tsdf",
        model="deterministic-reference",
        checkpoint=None,
        capture_profile="construction-lidar-v1",
        outcome="succeeded",
        duration_seconds=1.0,
        attempt=2,
    )
    telemetry.worker_finished("fusion.tsdf")
    telemetry.refresh_operation_depth(context.database)
    metrics = telemetry.render().decode("utf-8")
    assert 'sip_operation_queue_depth{operation_type="fusion.tsdf",service="workflow-service",state="pending"} 1.0' in metrics
    assert 'sip_worker_retries_total{capability="fusion.tsdf",service="workflow-service"} 1.0' in metrics
    assert 'sip_worker_operations_in_flight{capability="fusion.tsdf",service="workflow-service"} 0.0' in metrics


def test_log_redaction_removes_transcripts_biometrics_precise_locations_and_restricted_facility_fields() -> None:
    """REQ: ARCOBS-001, OPSSUP-001 ordinary telemetry removes transcripts, biometrics, precise locations, and restricted facility details."""
    value = redact({
        "transcript": "private interview text",
        "biometric_template": "face-vector",
        "precise_location": {"latitude": 39.0, "longitude": -95.0},
        "restricted_facility_details": {"controller": "panel-7"},
        "nested": {"raw_audio": b"private", "safe_count": 2},
    })
    assert value["transcript"] == "[REDACTED]"
    assert value["biometric_template"] == "[REDACTED]"
    assert value["precise_location"] == "[REDACTED]"
    assert value["restricted_facility_details"] == "[REDACTED]"
    assert value["nested"]["raw_audio"] == "[REDACTED]"
    assert value["nested"]["safe_count"] == 2
    rendered = json.dumps(value, sort_keys=True)
    for secret in ("private interview", "face-vector", "39.0", "panel-7"):
        assert secret not in rendered
