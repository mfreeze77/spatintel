from __future__ import annotations

import base64
import contextlib
import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

RELEASE = os.getenv("SIP_RELEASE", "1.1.0-dev")
_NONE = "none"
_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|token|secret|password|credential|private[_-]?key|master[_-]?key|signing[_-]?key|content_base64)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(password|token|secret|credential|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
)
_SAFE_METRIC_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,127}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_TRACEPARENT = re.compile(r"^00-([a-f0-9]{32})-([a-f0-9]{16})-([a-f0-9]{2})$")

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("sip_request_id", default=_NONE)
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("sip_trace_id", default=_NONE)
_operation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("sip_operation_id", default=_NONE)
_tenant_context_var: contextvars.ContextVar[str] = contextvars.ContextVar("sip_tenant_context", default=_NONE)
_project_context_var: contextvars.ContextVar[str] = contextvars.ContextVar("sip_project_context", default=_NONE)


def _safe_text(value: str, *, limit: int = 2048) -> str:
    result = value
    for pattern in _SENSITIVE_TEXT:
        result = pattern.sub("[REDACTED]", result)
    result = "".join(character if character >= " " or character in "\t" else "?" for character in result)
    return result if len(result) <= limit else result[:limit] + "[TRUNCATED]"


def redact(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded, log-safe copy without credential or evidence payload material."""
    if depth > 8:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:200]:
            key_text = _safe_text(str(key), limit=256)
            result[key_text] = "[REDACTED]" if _SENSITIVE_KEY.search(key_text) else redact(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [redact(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, bytes):
        return f"[BYTES:{len(value)}]"
    if isinstance(value, str):
        return _safe_text(value, limit=4096)
    return value


def _telemetry_key() -> bytes:
    encoded = os.getenv("SIP_TELEMETRY_PSEUDONYM_KEY_B64")
    if encoded:
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("SIP_TELEMETRY_PSEUDONYM_KEY_B64 must be valid base64") from exc
        if len(decoded) < 32:
            raise ValueError("SIP_TELEMETRY_PSEUDONYM_KEY_B64 must decode to at least 32 bytes")
        return decoded
    # This fallback is intentionally environment-specific and unsuitable for production.
    # Infrastructure validation requires an external secret in production profiles.
    return hashlib.sha256(f"sip-observability:{os.getenv('SIP_ENV', 'development')}".encode()).digest()


def pseudonymize_identifier(value: str | None, *, namespace: str, key: bytes | None = None) -> str:
    """Produce a non-reversible, bounded context label; never return the source identifier."""
    if not value:
        return _NONE
    digest = hmac.new(key or _telemetry_key(), f"{namespace}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"h:{digest[:20]}"


def controlled_metric_label(value: str | None, *, field: str) -> str:
    """Normalize a governed low-cardinality label without accepting customer identifiers.

    Model IDs, capabilities, and capture profiles must come from approved manifests. Values
    that do not fit that controlled vocabulary are collapsed to ``invalid`` rather than
    emitted to telemetry. Checkpoint hashes are deliberately shortened.
    """
    if not value:
        return _NONE
    candidate = value.strip()
    if field == "checkpoint" and _SHA256.fullmatch(candidate):
        return f"sha256:{candidate.lower()[:16]}"
    if not _SAFE_METRIC_LABEL.fullmatch(candidate):
        return "invalid"
    return candidate


@dataclass(frozen=True)
class BoundTelemetryContext:
    request_id: str = _NONE
    trace_id: str = _NONE
    operation_id: str = _NONE
    tenant_context: str = _NONE
    project_context: str = _NONE


@contextlib.contextmanager
def bind_telemetry_context(context: BoundTelemetryContext) -> Iterator[None]:
    tokens = (
        (_request_id_var, _request_id_var.set(context.request_id or _NONE)),
        (_trace_id_var, _trace_id_var.set(context.trace_id or _NONE)),
        (_operation_id_var, _operation_id_var.set(context.operation_id or _NONE)),
        (_tenant_context_var, _tenant_context_var.set(context.tenant_context or _NONE)),
        (_project_context_var, _project_context_var.set(context.project_context or _NONE)),
    )
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def current_telemetry_context() -> BoundTelemetryContext:
    return BoundTelemetryContext(
        request_id=_request_id_var.get(),
        trace_id=_trace_id_var.get(),
        operation_id=_operation_id_var.get(),
        tenant_context=_tenant_context_var.get(),
        project_context=_project_context_var.get(),
    )


class SIPLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that preserves call-site fields while enforcing service/release context."""

    def process(self, msg: object, kwargs: dict[str, Any]) -> tuple[object, dict[str, Any]]:
        supplied = kwargs.get("extra") or {}
        kwargs["extra"] = {**self.extra, **supplied}
        return msg, kwargs


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = current_telemetry_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "release": getattr(record, "release", RELEASE),
            "service": getattr(record, "service", "unknown"),
            "severity": record.levelname,
            "logger": record.name,
            "message": _safe_text(record.getMessage()),
            "request_id": getattr(record, "request_id", context.request_id) or _NONE,
            "trace_id": getattr(record, "trace_id", context.trace_id) or _NONE,
            "operation_id": getattr(record, "operation_id", context.operation_id) or _NONE,
            "tenant_context": getattr(record, "tenant_context", context.tenant_context) or _NONE,
            "project_context": getattr(record, "project_context", context.project_context) or _NONE,
            "outcome": getattr(record, "outcome", _NONE) or _NONE,
            "error_code": getattr(record, "error_code", _NONE) or _NONE,
        }
        event = getattr(record, "event", None)
        if event is not None:
            payload["event"] = controlled_metric_label(str(event), field="event")
        fields = getattr(record, "fields", None)
        if fields is not None:
            payload["fields"] = redact(fields)
        if record.exc_info:
            exception = record.exc_info[1]
            payload["exception"] = {
                "type": type(exception).__name__ if exception is not None else "UnknownException",
                "message": _safe_text(str(exception or ""), limit=1024),
            }
        return json.dumps(redact(payload), sort_keys=True, separators=(",", ":"), default=str)


def configure_logging(service_name: str, level: str | None = None) -> SIPLoggerAdapter:
    logger = logging.getLogger("sip")
    if not getattr(logger, "_sip_configured", False):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False
        logger._sip_configured = True  # type: ignore[attr-defined]
    logger.setLevel((level or os.getenv("SIP_LOG_LEVEL", "INFO")).upper())
    return SIPLoggerAdapter(logger, {"service": service_name, "release": RELEASE})


@dataclass
class PlatformObservability:
    service_name: str
    registry: CollectorRegistry
    requests: Counter
    latency: Histogram
    in_flight: Gauge
    errors: Counter
    readiness_failures: Counter
    worker_runs: Counter
    worker_duration: Histogram
    queue_wait: Histogram
    worker_in_flight: Gauge
    worker_retries: Counter
    operation_depth: Gauge
    quality_drift: Histogram
    quality_coverage: Histogram
    quality_residual: Histogram
    quality_confidence: Histogram
    quality_failed_regions: Gauge
    quality_prior_delta: Histogram

    @classmethod
    def create(cls, service_name: str) -> "PlatformObservability":
        registry = CollectorRegistry(auto_describe=True)
        requests = Counter(
            "sip_http_requests_total",
            "HTTP requests handled by a SIP logical service.",
            ["service", "method", "route", "status"],
            registry=registry,
        )
        latency = Histogram(
            "sip_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ["service", "method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
            registry=registry,
        )
        in_flight = Gauge(
            "sip_http_requests_in_flight",
            "Current HTTP requests in flight.",
            ["service"],
            registry=registry,
        )
        errors = Counter(
            "sip_errors_total",
            "Handled and unhandled errors by stable code.",
            ["service", "error_code", "outcome"],
            registry=registry,
        )
        readiness_failures = Counter(
            "sip_readiness_failures_total",
            "Readiness probe failures by dependency.",
            ["service", "dependency"],
            registry=registry,
        )
        worker_labels = ["service", "capability", "model", "checkpoint", "capture_profile", "outcome"]
        worker_runs = Counter(
            "sip_worker_runs_total",
            "Governed worker runs; labels are manifest-derived and contain no customer identifiers.",
            worker_labels,
            registry=registry,
        )
        worker_duration = Histogram(
            "sip_worker_duration_seconds",
            "Worker computation duration by governed profile.",
            worker_labels,
            buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 15, 60, 300, 1800, 7200),
            registry=registry,
        )
        queue_wait = Histogram(
            "sip_worker_queue_wait_seconds",
            "Time from operation admission to lease acquisition.",
            ["service", "capability", "capture_profile"],
            buckets=(0.01, 0.1, 1, 5, 15, 60, 300, 1800),
            registry=registry,
        )
        worker_in_flight = Gauge(
            "sip_worker_operations_in_flight",
            "Currently executing worker operations by governed capability.",
            ["service", "capability"],
            registry=registry,
        )
        worker_retries = Counter(
            "sip_worker_retries_total",
            "Worker executions whose durable operation attempt is greater than one.",
            ["service", "capability"],
            registry=registry,
        )
        operation_depth = Gauge(
            "sip_operation_queue_depth",
            "Durable operations by governed operation type and state.",
            ["service", "operation_type", "state"],
            registry=registry,
        )
        quality_labels = ["service", "capability", "model", "checkpoint", "capture_profile"]
        quality_drift = Histogram(
            "sip_reconstruction_drift_ratio",
            "Reconstruction drift ratio reported by validation.",
            quality_labels,
            buckets=(0.0001, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
            registry=registry,
        )
        quality_coverage = Histogram(
            "sip_reconstruction_coverage_ratio",
            "Validated scene coverage ratio.",
            quality_labels,
            buckets=(0.1, 0.25, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
            registry=registry,
        )
        quality_residual = Histogram(
            "sip_reconstruction_residual_meters",
            "Metric residual in meters.",
            quality_labels,
            buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5),
            registry=registry,
        )
        quality_confidence = Histogram(
            "sip_reconstruction_confidence_ratio",
            "Validation confidence distribution.",
            quality_labels,
            buckets=(0.1, 0.25, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
            registry=registry,
        )
        quality_failed_regions = Gauge(
            "sip_reconstruction_failed_regions",
            "Count of validation regions that failed the selected intended-use gate.",
            quality_labels,
            registry=registry,
        )
        quality_prior_delta = Histogram(
            "sip_reconstruction_quality_delta_ratio",
            "Quality delta relative to the prior accepted version.",
            quality_labels,
            buckets=(-1, -0.5, -0.25, -0.1, -0.05, -0.01, 0, 0.01, 0.05, 0.1, 0.25, 0.5, 1),
            registry=registry,
        )
        return cls(
            service_name,
            registry,
            requests,
            latency,
            in_flight,
            errors,
            readiness_failures,
            worker_runs,
            worker_duration,
            queue_wait,
            worker_in_flight,
            worker_retries,
            operation_depth,
            quality_drift,
            quality_coverage,
            quality_residual,
            quality_confidence,
            quality_failed_regions,
            quality_prior_delta,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)

    def observe(self, *, method: str, route: str, status: int, duration_seconds: float) -> None:
        labels = {"service": self.service_name, "method": method, "route": route}
        self.requests.labels(status=str(status), **labels).inc()
        self.latency.labels(**labels).observe(duration_seconds)

    def observe_error(self, *, error_code: str, outcome: str) -> None:
        self.errors.labels(
            service=self.service_name,
            error_code=controlled_metric_label(error_code, field="error_code"),
            outcome=controlled_metric_label(outcome, field="outcome"),
        ).inc()

    def _worker_labels(
        self,
        *,
        capability: str,
        model: str | None,
        checkpoint: str | None,
        capture_profile: str | None,
        outcome: str | None = None,
    ) -> dict[str, str]:
        labels = {
            "service": self.service_name,
            "capability": controlled_metric_label(capability, field="capability"),
            "model": controlled_metric_label(model, field="model"),
            "checkpoint": controlled_metric_label(checkpoint, field="checkpoint"),
            "capture_profile": controlled_metric_label(capture_profile, field="capture_profile"),
        }
        if outcome is not None:
            labels["outcome"] = controlled_metric_label(outcome, field="outcome")
        return labels

    def observe_worker_run(
        self,
        *,
        capability: str,
        model: str | None,
        checkpoint: str | None,
        capture_profile: str | None,
        outcome: str,
        duration_seconds: float,
        queue_wait_seconds: float | None = None,
        attempt: int | None = None,
    ) -> None:
        labels = self._worker_labels(
            capability=capability,
            model=model,
            checkpoint=checkpoint,
            capture_profile=capture_profile,
            outcome=outcome,
        )
        self.worker_runs.labels(**labels).inc()
        self.worker_duration.labels(**labels).observe(max(0.0, duration_seconds))
        if queue_wait_seconds is not None:
            self.queue_wait.labels(
                service=self.service_name,
                capability=labels["capability"],
                capture_profile=labels["capture_profile"],
            ).observe(max(0.0, queue_wait_seconds))
        if attempt is not None and attempt > 1:
            self.worker_retries.labels(service=self.service_name, capability=labels["capability"]).inc()

    def worker_started(self, capability: str) -> None:
        self.worker_in_flight.labels(
            service=self.service_name,
            capability=controlled_metric_label(capability, field="capability"),
        ).inc()

    def worker_finished(self, capability: str) -> None:
        self.worker_in_flight.labels(
            service=self.service_name,
            capability=controlled_metric_label(capability, field="capability"),
        ).dec()

    def refresh_operation_depth(self, database: Any) -> None:
        """Refresh low-cardinality durable-operation depth without exposing tenant or project IDs."""
        try:
            from sqlalchemy import func, select
            from .database import OperationRow

            with database.session() as session:
                rows = session.execute(
                    select(OperationRow.operation_type, OperationRow.state, func.count(OperationRow.operation_id))
                    .group_by(OperationRow.operation_type, OperationRow.state)
                ).all()
            self.operation_depth.clear()
            for operation_type, state, count in rows:
                self.operation_depth.labels(
                    service=self.service_name,
                    operation_type=controlled_metric_label(str(operation_type), field="operation_type"),
                    state=controlled_metric_label(str(state), field="state"),
                ).set(int(count))
        except Exception:
            # Metrics collection must never mutate queue state or break the application endpoint.
            return

    def observe_quality(
        self,
        *,
        capability: str,
        model: str | None,
        checkpoint: str | None,
        capture_profile: str | None,
        drift_ratio: float | None = None,
        coverage_ratio: float | None = None,
        residual_meters: float | None = None,
        confidence_ratio: float | None = None,
        failed_regions: int | None = None,
        prior_delta_ratio: float | None = None,
    ) -> None:
        labels = self._worker_labels(
            capability=capability,
            model=model,
            checkpoint=checkpoint,
            capture_profile=capture_profile,
        )
        if drift_ratio is not None:
            self.quality_drift.labels(**labels).observe(max(0.0, drift_ratio))
        if coverage_ratio is not None:
            self.quality_coverage.labels(**labels).observe(min(1.0, max(0.0, coverage_ratio)))
        if residual_meters is not None:
            self.quality_residual.labels(**labels).observe(max(0.0, residual_meters))
        if confidence_ratio is not None:
            self.quality_confidence.labels(**labels).observe(min(1.0, max(0.0, confidence_ratio)))
        if failed_regions is not None:
            self.quality_failed_regions.labels(**labels).set(max(0, failed_regions))
        if prior_delta_ratio is not None:
            self.quality_prior_delta.labels(**labels).observe(min(1.0, max(-1.0, prior_delta_ratio)))


class RequestTimer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started



def normalize_traceparent(value: str | None) -> str | None:
    """Validate and normalize a W3C version-00 traceparent without accepting baggage.

    Trace identifiers are correlation metadata, not authorization. All-zero identifiers
    and unsupported versions are rejected so durable operations never retain an invalid
    parent that silently forks a trace.
    """
    if value is None or not value.strip():
        return None
    candidate = value.strip().lower()
    match = _TRACEPARENT.fullmatch(candidate)
    if not match or match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
        raise ValueError("traceparent must be a valid W3C version-00 trace context")
    return candidate


def current_traceparent() -> str | None:
    """Inject the active trace context as a W3C traceparent when one exists."""
    try:
        from opentelemetry.propagate import inject

        carrier: dict[str, str] = {}
        inject(carrier)
        return normalize_traceparent(carrier.get("traceparent"))
    except Exception:
        return None


@contextlib.contextmanager
def operation_span(
    name: str,
    *,
    traceparent: str | None,
    kind: str = "consumer",
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> Iterator[Any]:
    """Continue a durable operation trace without trusting trace metadata for policy.

    The helper remains a no-op when the optional SDK is absent. Only ``traceparent`` is
    propagated; baggage is deliberately excluded because it can contain unbounded or
    customer-derived values.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.propagate import extract
        from opentelemetry.trace import SpanKind

        parent = normalize_traceparent(traceparent)
        context = extract({"traceparent": parent}) if parent else None
        span_kind = {
            "consumer": SpanKind.CONSUMER,
            "producer": SpanKind.PRODUCER,
            "internal": SpanKind.INTERNAL,
            "client": SpanKind.CLIENT,
        }.get(kind, SpanKind.INTERNAL)
        tracer = trace.get_tracer("sip.operation", RELEASE)
        manager = tracer.start_as_current_span(
            name,
            context=context,
            kind=span_kind,
            attributes=dict(attributes or {}),
        )
    except Exception:
        yield None
        return
    with manager as span:
        yield span

def current_trace_id() -> str | None:
    """Return the active OpenTelemetry trace id when the optional SDK is active."""
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            return f"{context.trace_id:032x}"
    except Exception:
        return None
    return None


@contextlib.contextmanager
def server_span(*, service_name: str, method: str, carrier: Mapping[str, str] | None = None) -> Iterator[Any]:
    """Start a server span when OpenTelemetry is available; otherwise remain a no-op."""
    try:
        from opentelemetry import trace
        from opentelemetry.propagate import extract
        from opentelemetry.trace import SpanKind
    except Exception:
        yield None
        return

    tracer = trace.get_tracer("sip.http", RELEASE)
    try:
        parent_context = extract(dict(carrier)) if carrier else None
        span_context = tracer.start_as_current_span(
            f"HTTP {method}",
            context=parent_context,
            kind=SpanKind.SERVER,
            attributes={"service.name": service_name, "http.request.method": method},
        )
    except Exception:
        yield None
        return
    with span_context as span:
        yield span


def configure_tracing(service_name: str) -> bool:
    """Configure OTLP tracing when optional packages and an endpoint are present."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or os.getenv("SIP_DISABLE_TRACING", "false").lower() == "true":
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            return True
        provider = TracerProvider(resource=Resource.create({"service.name": service_name, "service.version": RELEASE}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
        trace.set_tracer_provider(provider)
        return True
    except Exception:
        return False
