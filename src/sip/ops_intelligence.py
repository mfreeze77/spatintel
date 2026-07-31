from __future__ import annotations

import io
import json
import math
import os
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .archive_safety import validate_zip_members, verify_checksum_manifest
from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, merkle_root, new_uuid, sha256_bytes, sha256_file
from .database import (
    ActualCostRow,
    AfterActionReviewRow,
    AuditEventRow,
    AnomalyAlertRow,
    BudgetOverrideRow,
    BudgetPolicyRow,
    BudgetReservationRow,
    CapacityPlanRow,
    CostReconciliationRow,
    ComputeProfileRow,
    CostEstimateRow,
    GameDayExerciseRow,
    IncidentActionRow,
    Database,
    OperationRow,
    PerformanceBudgetRow,
    PriceCatalogRow,
    ProjectRow,
    QueueSnapshotRow,
    ResilienceProfileRow,
    SLODefinitionRow,
    SLOMeasurementRow,
    SupportAccessGrantRow,
    SupportBundleRow,
    SupportTicketRow,
    TelemetryRecordRow,
    TenantRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .observability import controlled_metric_label, normalize_traceparent, pseudonymize_identifier, redact
from .temporal import db_now

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,63}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}$")
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:/@+,-]{0,255}$")
_RESOURCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,255}$")

_TELEMETRY_TYPES = {"log", "metric", "trace", "quality", "queue", "audit_correlation"}
_TELEMETRY_PAYLOAD_KEYS = {
    "message_code",
    "duration_ms",
    "count",
    "value",
    "unit",
    "percentile",
    "queue_depth",
    "in_flight",
    "retries",
    "oldest_age_seconds",
    "capacity",
    "drift_ratio",
    "coverage_ratio",
    "residual_meters",
    "confidence_ratio",
    "failed_regions",
    "prior_delta_ratio",
    "status_code",
    "retryable",
    "result_size",
    "frame_time_ms",
    "first_scene_ms",
    "memory_mb",
    "vram_mb",
    "network_bytes",
    "cpu_seconds",
    "gpu_seconds",
    "storage_bytes",
    "egress_bytes",
    "request_count",
    "search_units",
    "vector_units",
    "transcription_seconds",
    "ocr_pages",
    "model_api_units",
    "support_minutes",
    "quality_gate",
    "comparison",
    "threshold",
}
_TELEMETRY_LABEL_KEYS = {
    "endpoint_class",
    "result_size_class",
    "viewer_tier",
    "device_tier",
    "processing_profile",
    "quality_tier",
    "retry_class",
    "queue_state",
    "validation_state",
    "execution_profile",
    "scene_size_class",
    "thermal_condition",
    "input_class",
    "queue_class",
    "support_profile",
    "capture_device",
    "capture_profile",
}
_FORBIDDEN_TELEMETRY_KEYS = re.compile(
    r"(?:raw|media|image|audio|video|transcript|geometry|coordinates|facility|address|person|name|email|phone|"
    r"authorization|cookie|token|secret|password|credential|private[_-]?key|biometric|content|prompt|response)",
    re.IGNORECASE,
)
_FORBIDDEN_SECRET_TEXT = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(password|token|secret|credential|api[_-]?key|private[_-]?key)\s*[:=]"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

_COST_STAGES = {"decode", "inference", "optimization", "fusion", "splat", "semantic", "storage", "egress"}

_COST_RESOURCES = {
    "cpu_seconds",
    "gpu_seconds",
    "memory_gb_seconds",
    "object_bytes_hot",
    "object_bytes_cold",
    "database_bytes",
    "requests",
    "search_units",
    "vector_units",
    "egress_bytes",
    "transcription_seconds",
    "ocr_pages",
    "model_api_units",
    "support_minutes",
}
_ALLOWED_PROFILE_TYPES = {"api", "search", "viewer", "capture", "pipeline", "queue", "vertical"}
_ALLOWED_EXECUTION_PROFILES = {"local", "hybrid", "cloud", "edge", "synthetic"}
_ALLOWED_EVIDENCE_CLASSES = {
    "synthetic_local",
    "local_reference",
    "deployed",
    "physical_device",
    "browser_device",
    "approved_gpu",
    "external_review",
}
_ALLOWED_SUPPORT_MEMBERS = {
    "support-bundle.json",
    "versions.json",
    "manifests.json",
    "metrics.json",
    "errors.json",
    "logs.ndjson",
    "hardware-profile.json",
    "checksums.json",
}
_REQUIRED_SUPPORT_MEMBERS = set(_ALLOWED_SUPPORT_MEMBERS)
_HIGH_RISK_SUPPORT = {"liveforever", "security_system", "consent", "biometric", "critical_infrastructure"}
_SUPPORT_HARDWARE_STRING_KEYS = {
    "device_tier",
    "os_family",
    "os_version",
    "architecture",
    "cpu_class",
    "gpu_class",
    "browser_family",
    "browser_version",
    "app_version",
    "driver_version",
    "runtime_profile",
    "thermal_condition",
}
_SUPPORT_HARDWARE_INTEGER_KEYS = {"memory_mb", "vram_mb", "cpu_count"}
_SUPPORT_HARDWARE_BOOLEAN_KEYS = {"gpu_available", "lidar_available"}


def _normalize_support_hardware_profile(
    profile: dict[str, Any], *, tenant_id: str, project_id: str
) -> dict[str, Any]:
    """Accept only bounded, non-identifying hardware metadata for support bundles."""
    if not isinstance(profile, dict) or len(profile) > 24:
        raise ValidationError(
            "SUPPORT_HARDWARE_PROFILE_INVALID",
            "support hardware profile must be a bounded object",
        )
    allowed = _SUPPORT_HARDWARE_STRING_KEYS | _SUPPORT_HARDWARE_INTEGER_KEYS | _SUPPORT_HARDWARE_BOOLEAN_KEYS
    unknown = sorted(set(profile) - allowed)
    if unknown:
        raise ValidationError(
            "SUPPORT_HARDWARE_FIELD_FORBIDDEN",
            "support hardware profile contains a non-approved field",
            {"fields": unknown},
        )
    normalized: dict[str, Any] = {}
    for key in sorted(profile):
        value = profile[key]
        if key in _SUPPORT_HARDWARE_STRING_KEYS:
            if not isinstance(value, str):
                raise ValidationError(
                    "SUPPORT_HARDWARE_VALUE_INVALID",
                    "support hardware metadata must use controlled string values",
                    {"field": key},
                )
            candidate = value.strip()
            if tenant_id in candidate or project_id in candidate or any(pattern.search(candidate) for pattern in _FORBIDDEN_SECRET_TEXT):
                raise ValidationError(
                    "SUPPORT_HARDWARE_SENSITIVE_VALUE_REJECTED",
                    "support hardware metadata cannot contain scoped identifiers or credential-like content",
                    {"field": key},
                )
            if not candidate or len(candidate) > 128 or _RESOURCE_REF.fullmatch(candidate) is None:
                raise ValidationError(
                    "SUPPORT_HARDWARE_VALUE_INVALID",
                    "support hardware metadata contains an invalid controlled value",
                    {"field": key},
                )
            normalized[key] = candidate
        elif key in _SUPPORT_HARDWARE_INTEGER_KEYS:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 16_777_216:
                raise ValidationError(
                    "SUPPORT_HARDWARE_VALUE_INVALID",
                    "support hardware numeric metadata is outside the governed range",
                    {"field": key},
                )
            normalized[key] = value
        else:
            if not isinstance(value, bool):
                raise ValidationError(
                    "SUPPORT_HARDWARE_VALUE_INVALID",
                    "support hardware availability metadata must be boolean",
                    {"field": key},
                )
            normalized[key] = value
    encoded = canonical_json(normalized)
    if len(encoded) > 4096:
        raise ValidationError("SUPPORT_HARDWARE_PROFILE_TOO_LARGE", "support hardware profile is too large")
    return normalized


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _require_sha256(value: str, *, code: str, field: str) -> str:
    candidate = value.strip().lower()
    if _SHA256.fullmatch(candidate) is None:
        raise ValidationError(code, f"{field} must be a lowercase SHA-256 digest", {"field": field})
    return candidate


def _require_identifier(value: str, *, code: str, field: str, pattern: re.Pattern[str] = _RESOURCE_REF) -> str:
    candidate = value.strip()
    if pattern.fullmatch(candidate) is None:
        raise ValidationError(code, f"{field} is invalid", {"field": field})
    return candidate


def _bounded_string(value: str, *, code: str, field: str, limit: int = 512) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > limit or any(ord(ch) < 32 and ch not in "\t" for ch in candidate):
        raise ValidationError(code, f"{field} is invalid", {"field": field})
    return candidate.replace("\r", " ").replace("\n", " ")


def _safe_telemetry_payload(payload: dict[str, Any], *, tenant_id: str, project_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or len(payload) > 64:
        raise ValidationError("TELEMETRY_PAYLOAD_INVALID", "telemetry payload must be a bounded object")
    safe: dict[str, Any] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        if key not in _TELEMETRY_PAYLOAD_KEYS or _FORBIDDEN_TELEMETRY_KEYS.search(key):
            raise ValidationError("TELEMETRY_FIELD_FORBIDDEN", "telemetry payload contains a non-approved field", {"field": key})
        if isinstance(value, bool):
            safe[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if not math.isfinite(number) or abs(number) > 1e18:
                raise ValidationError("TELEMETRY_VALUE_INVALID", "telemetry number is non-finite or unbounded", {"field": key})
            safe[key] = value
        elif isinstance(value, str):
            if key not in {"message_code", "unit", "quality_gate", "comparison"}:
                raise ValidationError("TELEMETRY_STRING_FORBIDDEN", "free-form strings are not accepted in telemetry", {"field": key})
            if not _SAFE_TEXT.fullmatch(value.strip()):
                raise ValidationError("TELEMETRY_STRING_INVALID", "telemetry string is not a controlled value", {"field": key})
            if any(pattern.search(value) for pattern in _FORBIDDEN_SECRET_TEXT):
                raise ValidationError("TELEMETRY_SECRET_REJECTED", "telemetry contains credential-like content", {"field": key})
            safe[key] = value.strip()
        else:
            raise ValidationError("TELEMETRY_VALUE_TYPE_INVALID", "telemetry values must be scalar", {"field": key})
    encoded = canonical_json(safe)
    if len(encoded) > 16_384:
        raise ValidationError("TELEMETRY_PAYLOAD_TOO_LARGE", "telemetry payload exceeds the bounded record size")
    serialized = encoded.decode("utf-8")
    if tenant_id in serialized or project_id in serialized:
        raise ValidationError("TELEMETRY_SCOPE_IDENTIFIER_REJECTED", "tenant or project identifiers cannot appear in telemetry payload")
    return safe


def _safe_telemetry_labels(labels: dict[str, Any], *, tenant_id: str, project_id: str) -> dict[str, str]:
    if not isinstance(labels, dict) or len(labels) > 20:
        raise ValidationError("TELEMETRY_LABELS_INVALID", "telemetry labels must be a bounded object")
    result: dict[str, str] = {}
    for raw_key, raw_value in labels.items():
        key = str(raw_key)
        if key not in _TELEMETRY_LABEL_KEYS:
            raise ValidationError("TELEMETRY_LABEL_FORBIDDEN", "telemetry label is not in the controlled vocabulary", {"field": key})
        value = str(raw_value).strip()
        if value in {tenant_id, project_id}:
            raise ValidationError("TELEMETRY_SCOPE_IDENTIFIER_REJECTED", "tenant or project identifiers cannot be telemetry labels")
        controlled = controlled_metric_label(value, field=key)
        if controlled in {"invalid", "none"} and value not in {"none", ""}:
            raise ValidationError("TELEMETRY_LABEL_INVALID", "telemetry label value is invalid", {"field": key})
        result[key] = controlled
    return result


def _zip_write(handle: zipfile.ZipFile, name: str, data: bytes) -> str:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o100644 & 0xFFFF) << 16
    handle.writestr(info, data)
    return sha256_bytes(data)


class OperationsIntelligenceService:
    """Governed observability, SLO, cost, quota, and support tooling.

    The reference path is deliberately local and deterministic. It preserves the same
    tenant/project contracts required by distributed deployments while making no claim
    that local synthetic evidence proves physical-device, browser, GPU, or cloud SLOs.
    """

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        *,
        bundle_root: Path,
        release: str,
        environment: str,
    ) -> None:
        self.database = database
        self.audit = audit
        self.bundle_root = bundle_root
        self.bundle_root.mkdir(parents=True, exist_ok=True)
        self.release = release
        self.environment = environment
        self.events = OutboxEventFactory()

    def _emit(
        self,
        session: Session,
        *,
        event_type: str,
        tenant_id: str,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        actor_id: str | None,
    ) -> None:
        session.add(
            self.events.create(
                session,
                event_type=event_type,
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                producer="operations-intelligence",
                actor_id=actor_id,
                workload_identity=None,
                correlation_id=aggregate_id,
            )
        )

    @staticmethod
    def _require_project(session: Session, tenant_id: str, project_id: str) -> ProjectRow:
        project = session.get(ProjectRow, project_id)
        if project is None or project.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)
        return project

    @staticmethod
    def _prometheus_label(value: str | None, *, field: str) -> str:
        controlled = controlled_metric_label(value, field=field)
        return controlled.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def render_aggregate_prometheus_metrics(self) -> bytes:
        """Render privacy-safe aggregate operational metrics without tenant/project labels."""
        lines = [
            "# HELP sip_ops_telemetry_records Retained governed telemetry records by controlled type.",
            "# TYPE sip_ops_telemetry_records gauge",
        ]
        with self.database.session() as session:
            for telemetry_type, count in session.execute(
                select(TelemetryRecordRow.telemetry_type, func.count(TelemetryRecordRow.telemetry_id))
                .group_by(TelemetryRecordRow.telemetry_type)
                .order_by(TelemetryRecordRow.telemetry_type)
            ):
                label = self._prometheus_label(telemetry_type, field="telemetry_type")
                lines.append(f'sip_ops_telemetry_records{{telemetry_type="{label}"}} {int(count)}')

            lines.extend([
                "# HELP sip_ops_budget_reservations Current budget reservations by governed state.",
                "# TYPE sip_ops_budget_reservations gauge",
            ])
            for state, count in session.execute(
                select(BudgetReservationRow.state, func.count(BudgetReservationRow.reservation_id))
                .group_by(BudgetReservationRow.state)
                .order_by(BudgetReservationRow.state)
            ):
                label = self._prometheus_label(state, field="state")
                lines.append(f'sip_ops_budget_reservations{{state="{label}"}} {int(count)}')

            denied = session.scalar(
                select(func.count(AuditEventRow.audit_id)).where(
                    AuditEventRow.resource_type == "budget_admission_denial",
                    AuditEventRow.outcome == "denied",
                )
            ) or 0
            expired_reservations = session.scalar(
                select(func.count(BudgetReservationRow.reservation_id)).where(
                    BudgetReservationRow.state == "reserved",
                    BudgetReservationRow.expires_at <= db_now(),
                )
            ) or 0
            lines.extend([
                "# HELP sip_ops_budget_admission_denials_total Governed budget admissions denied.",
                "# TYPE sip_ops_budget_admission_denials_total counter",
                f"sip_ops_budget_admission_denials_total {int(denied)}",
                "# HELP sip_ops_budget_expired_active_reservations Active reservations whose bounded lease expired.",
                "# TYPE sip_ops_budget_expired_active_reservations gauge",
                f"sip_ops_budget_expired_active_reservations {int(expired_reservations)}",
                "# HELP sip_ops_cost_estimates_currency_total Current retained estimates by currency without tenant labels.",
                "# TYPE sip_ops_cost_estimates_currency_total gauge",
            ])
            for currency, amount in session.execute(
                select(CostEstimateRow.currency, func.coalesce(func.sum(CostEstimateRow.total_amount), 0.0))
                .group_by(CostEstimateRow.currency)
                .order_by(CostEstimateRow.currency)
            ):
                label = self._prometheus_label(currency, field="currency")
                lines.append(f'sip_ops_cost_estimates_currency_total{{currency="{label}"}} {float(amount):.12g}')
            lines.extend([
                "# HELP sip_ops_actual_cost_currency_total Retained actual cost by currency without tenant labels.",
                "# TYPE sip_ops_actual_cost_currency_total gauge",
            ])
            for currency, amount in session.execute(
                select(ActualCostRow.currency, func.coalesce(func.sum(ActualCostRow.amount), 0.0))
                .group_by(ActualCostRow.currency)
                .order_by(ActualCostRow.currency)
            ):
                label = self._prometheus_label(currency, field="currency")
                lines.append(f'sip_ops_actual_cost_currency_total{{currency="{label}"}} {float(amount):.12g}')

            lines.extend([
                "# HELP sip_ops_anomaly_alerts Current anomaly alerts by controlled state and severity.",
                "# TYPE sip_ops_anomaly_alerts gauge",
            ])
            for state, severity, count in session.execute(
                select(AnomalyAlertRow.state, AnomalyAlertRow.severity, func.count(AnomalyAlertRow.alert_id))
                .group_by(AnomalyAlertRow.state, AnomalyAlertRow.severity)
                .order_by(AnomalyAlertRow.state, AnomalyAlertRow.severity)
            ):
                state_label = self._prometheus_label(state, field="state")
                severity_label = self._prometheus_label(severity, field="severity")
                lines.append(f'sip_ops_anomaly_alerts{{state="{state_label}",severity="{severity_label}"}} {int(count)}')

            support_denied = session.scalar(
                select(func.count(AuditEventRow.audit_id)).where(
                    AuditEventRow.resource_type == "support_access_grant",
                    AuditEventRow.outcome == "denied",
                )
            ) or 0
            expired_support = session.scalar(
                select(func.count(SupportAccessGrantRow.grant_id)).where(
                    SupportAccessGrantRow.state == "active",
                    SupportAccessGrantRow.expires_at <= db_now(),
                )
            ) or 0
            lines.extend([
                "# HELP sip_ops_support_access_denials_total Governed support-access denials.",
                "# TYPE sip_ops_support_access_denials_total counter",
                f"sip_ops_support_access_denials_total {int(support_denied)}",
                "# HELP sip_ops_support_expired_active_grants Support grants still marked active after expiration.",
                "# TYPE sip_ops_support_expired_active_grants gauge",
                f"sip_ops_support_expired_active_grants {int(expired_support)}",
                "# HELP sip_ops_support_grants Current customer-approved support grants by state.",
                "# TYPE sip_ops_support_grants gauge",
            ])
            for state, count in session.execute(
                select(SupportAccessGrantRow.state, func.count(SupportAccessGrantRow.grant_id))
                .group_by(SupportAccessGrantRow.state)
                .order_by(SupportAccessGrantRow.state)
            ):
                label = self._prometheus_label(state, field="state")
                lines.append(f'sip_ops_support_grants{{state="{label}"}} {int(count)}')
            lines.extend([
                "# HELP sip_ops_slo_measurements Retained SLO measurements by governed compliance state.",
                "# TYPE sip_ops_slo_measurements gauge",
            ])
            for status, count in session.execute(
                select(SLOMeasurementRow.status, func.count(SLOMeasurementRow.measurement_id))
                .group_by(SLOMeasurementRow.status)
                .order_by(SLOMeasurementRow.status)
            ):
                state = "compliant" if status == "met" else "violating"
                lines.append(f'sip_ops_slo_measurements{{state="{state}"}} {int(count)}')

            latest_by_scope: dict[tuple[str | None, str | None, str], QueueSnapshotRow] = {}
            for row in session.scalars(select(QueueSnapshotRow).order_by(QueueSnapshotRow.sampled_at.desc())):
                latest_by_scope.setdefault((row.tenant_id, row.project_id, row.queue_class), row)
            queue_aggregates: dict[str, dict[str, float]] = defaultdict(lambda: {"depth": 0.0, "in_flight": 0.0, "oldest": 0.0})
            for row in latest_by_scope.values():
                aggregate = queue_aggregates[row.queue_class]
                aggregate["depth"] += row.depth
                aggregate["in_flight"] += row.in_flight
                aggregate["oldest"] = max(aggregate["oldest"], row.oldest_age_seconds)
            lines.extend([
                "# HELP sip_ops_queue_depth Latest aggregate queue depth by controlled queue class.",
                "# TYPE sip_ops_queue_depth gauge",
                "# HELP sip_ops_queue_in_flight Latest aggregate work in flight by controlled queue class.",
                "# TYPE sip_ops_queue_in_flight gauge",
                "# HELP sip_ops_queue_oldest_age_seconds Oldest queued item age by controlled queue class.",
                "# TYPE sip_ops_queue_oldest_age_seconds gauge",
            ])
            for queue_class in sorted(queue_aggregates):
                label = self._prometheus_label(queue_class, field="queue_class")
                aggregate = queue_aggregates[queue_class]
                lines.append(f'sip_ops_queue_depth{{queue_class="{label}"}} {aggregate["depth"]:.12g}')
                lines.append(f'sip_ops_queue_in_flight{{queue_class="{label}"}} {aggregate["in_flight"]:.12g}')
                lines.append(f'sip_ops_queue_oldest_age_seconds{{queue_class="{label}"}} {aggregate["oldest"]:.12g}')
        return ("\n".join(lines) + "\n").encode("utf-8")

    # ---------------------------------------------------------------- telemetry
    def record_telemetry(
        self,
        *,
        tenant_id: str,
        project_id: str,
        telemetry_type: str,
        service: str,
        release: str,
        correlation_id: str,
        trace_id: str | None,
        traceparent: str | None = None,
        operation_id: str | None,
        route_template: str | None,
        stage: str | None,
        model_id: str | None,
        checkpoint_hash: str | None,
        capture_profile: str | None,
        hardware_profile: str | None,
        execution_profile: str | None,
        queue_class: str | None,
        vertical: str | None,
        severity: str,
        outcome: str,
        stable_error_code: str | None,
        payload: dict[str, Any],
        labels: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        if telemetry_type not in _TELEMETRY_TYPES:
            raise ValidationError("TELEMETRY_TYPE_INVALID", "unsupported telemetry type")
        service = _require_identifier(service, code="TELEMETRY_SERVICE_INVALID", field="service")
        release = _require_identifier(release, code="TELEMETRY_RELEASE_INVALID", field="release")
        correlation_id = _require_identifier(correlation_id, code="TELEMETRY_CORRELATION_INVALID", field="correlation_id", pattern=_CORRELATION_ID)
        normalized_parent: str | None = None
        if traceparent is not None:
            try:
                normalized_parent = normalize_traceparent(traceparent)
            except ValueError as exc:
                raise ValidationError("TELEMETRY_TRACEPARENT_INVALID", str(exc)) from exc
        parent_trace_id = normalized_parent.split("-")[1] if normalized_parent else None
        if trace_id is not None:
            trace_id = trace_id.lower()
            if _TRACE_ID.fullmatch(trace_id) is None or trace_id == "0" * 32:
                raise ValidationError("TELEMETRY_TRACE_INVALID", "trace identifier must be a nonzero 32-character hexadecimal value")
        if parent_trace_id is not None and trace_id is not None and parent_trace_id != trace_id:
            raise ValidationError("TELEMETRY_TRACE_CONTEXT_CONFLICT", "traceparent and trace_id identify different traces")
        trace_id = trace_id or parent_trace_id
        if checkpoint_hash is not None:
            checkpoint_hash = _require_sha256(checkpoint_hash, code="TELEMETRY_CHECKPOINT_INVALID", field="checkpoint_hash")
        for field, value in (
            ("operation_id", operation_id),
            ("stage", stage),
            ("model_id", model_id),
            ("capture_profile", capture_profile),
            ("hardware_profile", hardware_profile),
            ("execution_profile", execution_profile),
            ("queue_class", queue_class),
            ("vertical", vertical),
            ("stable_error_code", stable_error_code),
        ):
            if value is not None:
                _require_identifier(value, code="TELEMETRY_CONTEXT_INVALID", field=field)
        if route_template is not None:
            route_template = _bounded_string(route_template, code="TELEMETRY_ROUTE_INVALID", field="route_template", limit=256)
            route_segments = {segment for segment in route_template.split("/") if segment}
            if tenant_id in route_segments or project_id in route_segments or "?" in route_template:
                raise ValidationError("TELEMETRY_ROUTE_UNSAFE", "route telemetry must use a parameterized template without query values")
        severity = controlled_metric_label(severity.lower(), field="severity")
        outcome = controlled_metric_label(outcome.lower(), field="outcome")
        if severity == "invalid" or outcome == "invalid":
            raise ValidationError("TELEMETRY_CONTEXT_INVALID", "severity or outcome is not controlled")
        safe_payload = _safe_telemetry_payload(payload, tenant_id=tenant_id, project_id=project_id)
        safe_labels = _safe_telemetry_labels(labels, tenant_id=tenant_id, project_id=project_id)
        body = {
            "tenant_context": pseudonymize_identifier(tenant_id, namespace="tenant"),
            "project_context": pseudonymize_identifier(project_id, namespace="project"),
            "telemetry_type": telemetry_type,
            "service": service,
            "release": release,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "traceparent": normalized_parent,
            "operation_id": operation_id,
            "route_template": route_template,
            "stage": stage,
            "model_id": model_id,
            "checkpoint_hash": checkpoint_hash,
            "capture_profile": capture_profile,
            "hardware_profile": hardware_profile,
            "execution_profile": execution_profile,
            "queue_class": queue_class,
            "vertical": vertical,
            "severity": severity,
            "outcome": outcome,
            "stable_error_code": stable_error_code,
            "payload": safe_payload,
            "labels": safe_labels,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(TelemetryRecordRow).where(TelemetryRecordRow.payload_hash == digest))
            if existing is not None:
                if existing.tenant_id != tenant_id or existing.project_id != project_id:
                    raise ConflictError("TELEMETRY_HASH_SCOPE_CONFLICT", "telemetry hash is already bound to another scope")
                return self._telemetry_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = TelemetryRecordRow(
                telemetry_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                telemetry_type=telemetry_type,
                service=service,
                release=release,
                correlation_id=correlation_id,
                trace_id=trace_id,
                operation_id=operation_id,
                route_template=route_template,
                stage=stage,
                model_id=model_id,
                checkpoint_hash=checkpoint_hash,
                capture_profile=capture_profile,
                hardware_profile=hardware_profile,
                execution_profile=execution_profile,
                queue_class=queue_class,
                vertical=vertical,
                severity=severity,
                outcome=outcome,
                stable_error_code=stable_error_code,
                payload_json=safe_payload,
                labels_json=safe_labels,
                payload_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="observability:record",
                resource_type="telemetry_record",
                resource_id=identifier,
                outcome="allowed",
                details={"type": telemetry_type, "service": service, "outcome": outcome, "payload_hash": digest},
                trace_id=trace_id,
                session=session,
            )
            self._emit(
                session,
                event_type="telemetry.recorded",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="telemetry_record",
                aggregate_id=identifier,
                payload={"type": telemetry_type, "service": service, "outcome": outcome, "payload_hash": digest},
                actor_id=actor_id,
            )
            return self._telemetry_result(row, idempotent_replay=False)

    @staticmethod
    def _telemetry_result(row: TelemetryRecordRow, *, idempotent_replay: bool = False) -> dict[str, Any]:
        return {
            "telemetry_id": row.telemetry_id,
            "telemetry_type": row.telemetry_type,
            "service": row.service,
            "release": row.release,
            "correlation_id": row.correlation_id,
            "trace_id": row.trace_id,
            "operation_id": row.operation_id,
            "route_template": row.route_template,
            "stage": row.stage,
            "model_id": row.model_id,
            "checkpoint_hash": row.checkpoint_hash,
            "capture_profile": row.capture_profile,
            "hardware_profile": row.hardware_profile,
            "execution_profile": row.execution_profile,
            "queue_class": row.queue_class,
            "vertical": row.vertical,
            "severity": row.severity,
            "outcome": row.outcome,
            "stable_error_code": row.stable_error_code,
            "payload": row.payload_json,
            "labels": row.labels_json,
            "payload_hash": row.payload_hash,
            "created_at": row.created_at.isoformat(),
            "idempotent_replay": idempotent_replay,
        }

    def query_telemetry(
        self,
        *,
        tenant_id: str,
        project_id: str,
        telemetry_type: str | None = None,
        correlation_id: str | None = None,
        service: str | None = None,
        stage: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise ValidationError("TELEMETRY_LIMIT_INVALID", "telemetry query limit must be between 1 and 500")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            statement = select(TelemetryRecordRow).where(
                TelemetryRecordRow.tenant_id == tenant_id,
                TelemetryRecordRow.project_id == project_id,
            )
            if telemetry_type is not None:
                statement = statement.where(TelemetryRecordRow.telemetry_type == telemetry_type)
            if correlation_id is not None:
                statement = statement.where(TelemetryRecordRow.correlation_id == correlation_id)
            if service is not None:
                statement = statement.where(TelemetryRecordRow.service == service)
            if stage is not None:
                statement = statement.where(TelemetryRecordRow.stage == stage)
            if outcome is not None:
                statement = statement.where(TelemetryRecordRow.outcome == outcome)
            rows = list(session.scalars(statement.order_by(TelemetryRecordRow.created_at.desc()).limit(limit)))
        return {
            "tenant_context": pseudonymize_identifier(tenant_id, namespace="tenant"),
            "project_context": pseudonymize_identifier(project_id, namespace="project"),
            "records": [self._telemetry_result(row) for row in rows],
            "count": len(rows),
        }

    def quality_dashboard(self, *, tenant_id: str, project_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            rows = list(
                session.scalars(
                    select(TelemetryRecordRow).where(
                        TelemetryRecordRow.tenant_id == tenant_id,
                        TelemetryRecordRow.project_id == project_id,
                        TelemetryRecordRow.telemetry_type.in_(["quality", "queue"]),
                    )
                )
            )
        groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.stage or "none", row.model_id or "none", row.checkpoint_hash or "none", row.capture_profile or "none")
            group = groups.setdefault(
                key,
                {
                    "stage": key[0],
                    "model_id": key[1],
                    "checkpoint_hash": key[2],
                    "capture_profile": key[3],
                    "signals": 0,
                    "failures": 0,
                    "drift": [],
                    "coverage": [],
                    "residual": [],
                    "confidence": [],
                    "failed_regions": 0,
                    "prior_delta": [],
                },
            )
            group["signals"] += 1
            if row.outcome not in {"success", "succeeded", "passed"}:
                group["failures"] += 1
            payload = row.payload_json
            for source, target in (
                ("drift_ratio", "drift"),
                ("coverage_ratio", "coverage"),
                ("residual_meters", "residual"),
                ("confidence_ratio", "confidence"),
                ("prior_delta_ratio", "prior_delta"),
            ):
                if source in payload:
                    group[target].append(float(payload[source]))
            group["failed_regions"] += int(payload.get("failed_regions", 0))
        result = []
        for key in sorted(groups):
            group = groups[key]
            for field in ("drift", "coverage", "residual", "confidence", "prior_delta"):
                values = group[field]
                group[field] = {
                    "count": len(values),
                    "mean": (sum(values) / len(values)) if values else None,
                    "minimum": min(values) if values else None,
                    "maximum": max(values) if values else None,
                }
            result.append(group)
        return {"groups": result, "record_count": len(rows), "raw_data_included": False}

    # --------------------------------------------------------------------- SLOs
    def register_slo(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        target_type: str,
        dimensions: dict[str, Any],
        indicator: dict[str, Any],
        objective: float,
        percentile: float,
        window_seconds: int,
        budget: dict[str, Any],
        degradation_behavior: str,
        evidence_class: str,
        owner: str,
        version: str,
        actor_id: str,
    ) -> dict[str, Any]:
        name = _bounded_string(name, code="SLO_NAME_INVALID", field="name", limit=128)
        target_type = _require_identifier(target_type, code="SLO_TARGET_INVALID", field="target_type")
        version = _require_identifier(version, code="SLO_VERSION_INVALID", field="version", pattern=_VERSION)
        owner = _require_identifier(owner, code="SLO_OWNER_INVALID", field="owner")
        if not (0 < objective <= 1) or not (0 < percentile <= 1) or window_seconds <= 0:
            raise ValidationError("SLO_VALUES_INVALID", "SLO objective, percentile, or window is invalid")
        if evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            raise ValidationError("SLO_EVIDENCE_CLASS_INVALID", "unsupported SLO evidence class")
        if not indicator.get("metric") or indicator.get("comparison") not in {"<=", ">=", "<", ">"}:
            raise ValidationError("SLO_INDICATOR_INVALID", "SLO indicator requires metric, comparison, and threshold")
        threshold = indicator.get("threshold")
        if not isinstance(threshold, (int, float)) or not math.isfinite(float(threshold)):
            raise ValidationError("SLO_INDICATOR_INVALID", "SLO threshold must be finite")
        _safe_telemetry_labels(dimensions, tenant_id=tenant_id, project_id=project_id or "none")
        if not isinstance(budget, dict) or not budget:
            raise ValidationError("SLO_BUDGET_INVALID", "SLO requires a measurable budget")
        degradation_behavior = _bounded_string(degradation_behavior, code="SLO_DEGRADATION_INVALID", field="degradation_behavior", limit=256)
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "name": name,
            "target_type": target_type,
            "dimensions": dimensions,
            "indicator": indicator,
            "objective": objective,
            "percentile": percentile,
            "window_seconds": window_seconds,
            "budget": budget,
            "degradation_behavior": degradation_behavior,
            "evidence_class": evidence_class,
            "owner": owner,
            "version": version,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(SLODefinitionRow).where(SLODefinitionRow.definition_hash == digest))
            if existing is not None:
                return self._slo_result(existing, idempotent_replay=True)
            conflict = session.scalar(
                select(SLODefinitionRow).where(
                    SLODefinitionRow.tenant_id == tenant_id,
                    SLODefinitionRow.project_id == project_id,
                    SLODefinitionRow.name == name,
                    SLODefinitionRow.version == version,
                )
            )
            if conflict is not None:
                raise ConflictError("SLO_VERSION_CONFLICT", "SLO name/version is already bound to a different definition")
            identifier = new_uuid()
            row = SLODefinitionRow(
                slo_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                name=name,
                target_type=target_type,
                dimensions_json=dimensions,
                indicator_json=indicator,
                objective=objective,
                percentile=percentile,
                window_seconds=window_seconds,
                budget_json=budget,
                degradation_behavior=degradation_behavior,
                evidence_class=evidence_class,
                owner=owner,
                version=version,
                active=True,
                definition_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="slo:register",
                resource_type="slo_definition",
                resource_id=identifier,
                outcome="allowed",
                details={"name": name, "version": version, "definition_hash": digest, "evidence_class": evidence_class},
                session=session,
            )
            self._emit(session, event_type="slo.definition_registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="slo_definition", aggregate_id=identifier, payload={"name": name, "version": version, "definition_hash": digest, "evidence_class": evidence_class}, actor_id=actor_id)
            return self._slo_result(row, idempotent_replay=False)

    @staticmethod
    def _slo_result(row: SLODefinitionRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "slo_id": row.slo_id,
            "name": row.name,
            "target_type": row.target_type,
            "dimensions": row.dimensions_json,
            "indicator": row.indicator_json,
            "objective": row.objective,
            "percentile": row.percentile,
            "window_seconds": row.window_seconds,
            "budget": row.budget_json,
            "degradation_behavior": row.degradation_behavior,
            "evidence_class": row.evidence_class,
            "owner": row.owner,
            "version": row.version,
            "definition_hash": row.definition_hash,
            "active": row.active,
            "idempotent_replay": idempotent_replay,
        }

    def record_slo_measurement(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        slo_id: str,
        window_start: datetime,
        window_end: datetime,
        numerator: float,
        denominator: float,
        dimensions: dict[str, Any],
        source_profile: str,
        source_manifest_hash: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if denominator <= 0 or numerator < 0 or numerator > denominator:
            raise ValidationError("SLO_MEASUREMENT_INVALID", "SLO numerator and denominator are invalid")
        start, end = _aware(window_start), _aware(window_end)
        if end <= start:
            raise ValidationError("SLO_WINDOW_INVALID", "SLO measurement window is invalid")
        source_manifest_hash = _require_sha256(source_manifest_hash, code="SLO_SOURCE_MANIFEST_INVALID", field="source_manifest_hash")
        source_profile = _require_identifier(source_profile, code="SLO_SOURCE_PROFILE_INVALID", field="source_profile")
        observed = numerator / denominator
        with self.database.session() as session:
            row = session.get(SLODefinitionRow, slo_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("slo_definition", slo_id)
            comparison = row.indicator_json["comparison"]
            threshold = float(row.indicator_json["threshold"])
            status = "met" if _compare(observed, comparison, threshold) and observed >= row.objective else "breached"
            body = {
                "slo_id": slo_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "numerator": numerator,
                "denominator": denominator,
                "observed": observed,
                "dimensions": dimensions,
                "source_profile": source_profile,
                "source_manifest_hash": source_manifest_hash,
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(SLOMeasurementRow).where(SLOMeasurementRow.evidence_hash == digest))
            if existing is not None:
                return self._slo_measurement_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            measurement = SLOMeasurementRow(
                measurement_id=identifier,
                slo_id=slo_id,
                tenant_id=tenant_id,
                project_id=project_id,
                window_start=start,
                window_end=end,
                numerator=numerator,
                denominator=denominator,
                observed_value=observed,
                status=status,
                dimensions_json=dimensions,
                source_profile=source_profile,
                source_manifest_hash=source_manifest_hash,
                evidence_hash=digest,
            )
            session.add(measurement)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="slo:measure", resource_type="slo_measurement", resource_id=identifier, outcome="allowed", details={"slo_id": slo_id, "status": status, "evidence_hash": digest, "source_profile": source_profile}, session=session)
            self._emit(session, event_type="slo.measurement_recorded", tenant_id=tenant_id, project_id=project_id, aggregate_type="slo_measurement", aggregate_id=identifier, payload={"slo_id": slo_id, "status": status, "observed_value": observed, "evidence_hash": digest, "source_profile": source_profile}, actor_id=actor_id)
            return self._slo_measurement_result(measurement, idempotent_replay=False)

    @staticmethod
    def _slo_measurement_result(row: SLOMeasurementRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "measurement_id": row.measurement_id,
            "slo_id": row.slo_id,
            "window_start": row.window_start.isoformat(),
            "window_end": row.window_end.isoformat(),
            "numerator": row.numerator,
            "denominator": row.denominator,
            "observed_value": row.observed_value,
            "status": row.status,
            "dimensions": row.dimensions_json,
            "source_profile": row.source_profile,
            "source_manifest_hash": row.source_manifest_hash,
            "evidence_hash": row.evidence_hash,
            "idempotent_replay": idempotent_replay,
        }

    def register_performance_budget(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        profile_type: str,
        profile_name: str,
        input_class: dict[str, Any],
        hardware_profile: str,
        execution_profile: str,
        model_id: str | None,
        checkpoint_hash: str | None,
        queue_class: str | None,
        vertical: str | None,
        percentile: float,
        warm_state: str,
        concurrency: int,
        budgets: dict[str, float],
        degradation_behavior: str,
        evidence_class: str,
        version: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if profile_type not in _ALLOWED_PROFILE_TYPES:
            raise ValidationError("PERFORMANCE_PROFILE_TYPE_INVALID", "unsupported performance profile type")
        if execution_profile not in _ALLOWED_EXECUTION_PROFILES:
            raise ValidationError("PERFORMANCE_EXECUTION_PROFILE_INVALID", "unsupported execution profile")
        if evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            raise ValidationError("PERFORMANCE_EVIDENCE_CLASS_INVALID", "unsupported evidence class")
        if warm_state not in {"warm", "cold", "mixed"} or not (0 < percentile <= 1) or concurrency < 1:
            raise ValidationError("PERFORMANCE_BUDGET_VALUES_INVALID", "performance percentile, warm state, or concurrency is invalid")
        if not budgets or any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0 for value in budgets.values()):
            raise ValidationError("PERFORMANCE_BUDGET_INVALID", "performance budgets must be positive finite values")
        if checkpoint_hash is not None:
            checkpoint_hash = _require_sha256(checkpoint_hash, code="PERFORMANCE_CHECKPOINT_INVALID", field="checkpoint_hash")
        profile_name = _require_identifier(profile_name, code="PERFORMANCE_PROFILE_NAME_INVALID", field="profile_name")
        hardware_profile = _require_identifier(hardware_profile, code="PERFORMANCE_HARDWARE_PROFILE_INVALID", field="hardware_profile")
        version = _require_identifier(version, code="PERFORMANCE_VERSION_INVALID", field="version", pattern=_VERSION)
        degradation_behavior = _bounded_string(degradation_behavior, code="PERFORMANCE_DEGRADATION_INVALID", field="degradation_behavior", limit=256)
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "profile_type": profile_type,
            "profile_name": profile_name,
            "input_class": input_class,
            "hardware_profile": hardware_profile,
            "execution_profile": execution_profile,
            "model_id": model_id,
            "checkpoint_hash": checkpoint_hash,
            "queue_class": queue_class,
            "vertical": vertical,
            "percentile": percentile,
            "warm_state": warm_state,
            "concurrency": concurrency,
            "budgets": budgets,
            "degradation_behavior": degradation_behavior,
            "evidence_class": evidence_class,
            "version": version,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(PerformanceBudgetRow).where(PerformanceBudgetRow.budget_hash == digest))
            if existing is not None:
                return self._performance_budget_result(existing, idempotent_replay=True)
            conflict = session.scalar(select(PerformanceBudgetRow).where(PerformanceBudgetRow.tenant_id == tenant_id, PerformanceBudgetRow.project_id == project_id, PerformanceBudgetRow.profile_type == profile_type, PerformanceBudgetRow.profile_name == profile_name, PerformanceBudgetRow.version == version))
            if conflict is not None:
                raise ConflictError("PERFORMANCE_BUDGET_VERSION_CONFLICT", "performance budget version is already bound to different values")
            identifier = new_uuid()
            row = PerformanceBudgetRow(
                performance_budget_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                profile_type=profile_type,
                profile_name=profile_name,
                input_class_json=input_class,
                hardware_profile=hardware_profile,
                execution_profile=execution_profile,
                model_id=model_id,
                checkpoint_hash=checkpoint_hash,
                queue_class=queue_class,
                vertical=vertical,
                percentile=percentile,
                warm_state=warm_state,
                concurrency=concurrency,
                budgets_json={key: float(value) for key, value in budgets.items()},
                degradation_behavior=degradation_behavior,
                evidence_class=evidence_class,
                version=version,
                budget_hash=digest,
                active=True,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="performance_budget:register", resource_type="performance_budget", resource_id=identifier, outcome="allowed", details={"profile_type": profile_type, "profile_name": profile_name, "version": version, "budget_hash": digest, "evidence_class": evidence_class}, session=session)
            self._emit(session, event_type="performance_budget.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="performance_budget", aggregate_id=identifier, payload={"profile_type": profile_type, "profile_name": profile_name, "version": version, "budget_hash": digest, "evidence_class": evidence_class}, actor_id=actor_id)
            return self._performance_budget_result(row, idempotent_replay=False)

    @staticmethod
    def _performance_budget_result(row: PerformanceBudgetRow, *, idempotent_replay: bool) -> dict[str, Any]:
        externally_validated = row.evidence_class in {"deployed", "physical_device", "browser_device", "approved_gpu", "external_review"}
        return {
            "performance_budget_id": row.performance_budget_id,
            "profile_type": row.profile_type,
            "profile_name": row.profile_name,
            "input_class": row.input_class_json,
            "hardware_profile": row.hardware_profile,
            "execution_profile": row.execution_profile,
            "model_id": row.model_id,
            "checkpoint_hash": row.checkpoint_hash,
            "queue_class": row.queue_class,
            "vertical": row.vertical,
            "percentile": row.percentile,
            "warm_state": row.warm_state,
            "concurrency": row.concurrency,
            "budgets": row.budgets_json,
            "degradation_behavior": row.degradation_behavior,
            "evidence_class": row.evidence_class,
            "external_validation_status": "validated" if externally_validated else "external_validation_required",
            "version": row.version,
            "budget_hash": row.budget_hash,
            "idempotent_replay": idempotent_replay,
        }

    def evaluate_performance_budget(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        performance_budget_id: str,
        observed: dict[str, float],
        evidence_class: str,
        source_manifest_hash: str,
    ) -> dict[str, Any]:
        source_manifest_hash = _require_sha256(source_manifest_hash, code="PERFORMANCE_SOURCE_MANIFEST_INVALID", field="source_manifest_hash")
        if evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            raise ValidationError("PERFORMANCE_EVIDENCE_CLASS_INVALID", "unsupported evidence class")
        with self.database.session() as session:
            row = session.get(PerformanceBudgetRow, performance_budget_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("performance_budget", performance_budget_id)
            findings = []
            for metric, limit in row.budgets_json.items():
                if metric not in observed:
                    findings.append({"metric": metric, "reason": "measurement_missing"})
                    continue
                value = float(observed[metric])
                if not math.isfinite(value):
                    raise ValidationError("PERFORMANCE_MEASUREMENT_INVALID", "performance measurement must be finite", {"metric": metric})
                if value > float(limit):
                    findings.append({"metric": metric, "reason": "budget_exceeded", "observed": value, "budget": limit})
            external_required = row.evidence_class in {"physical_device", "browser_device", "approved_gpu", "deployed", "external_review"} and evidence_class not in {"physical_device", "browser_device", "approved_gpu", "deployed", "external_review"}
            return {
                "performance_budget_id": performance_budget_id,
                "passed": not findings and not external_required,
                "findings": findings,
                "source_manifest_hash": source_manifest_hash,
                "evidence_class": evidence_class,
                "external_validation_required": external_required,
                "degradation_behavior": row.degradation_behavior if findings or external_required else None,
            }

    # ------------------------------------------------------------ compute/costs
    def register_compute_profile(
        self,
        *,
        name: str,
        revision: str,
        resolution: str,
        dtype: str,
        backend: str,
        model_id: str,
        checkpoint_hash: str,
        window_policy: dict[str, Any],
        memory_limit_mb: int,
        timeout_seconds: int,
        output_class: str,
        quality_tier: str,
        cuda_version: str | None,
        driver_constraint: str | None,
        container_digest: str,
        tenant_isolation: str,
        oom_fallback: dict[str, Any],
        expected_runtime_seconds: float,
        peak_vram_mb: int,
        peak_ram_mb: int,
        cost_stage_weights: dict[str, float],
        actor_id: str,
    ) -> dict[str, Any]:
        checkpoint_hash = _require_sha256(checkpoint_hash, code="COMPUTE_CHECKPOINT_INVALID", field="checkpoint_hash")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}", container_digest):
            raise ValidationError("COMPUTE_CONTAINER_DIGEST_INVALID", "compute profile requires an immutable image digest")
        if memory_limit_mb <= 0 or timeout_seconds <= 0 or expected_runtime_seconds <= 0 or peak_vram_mb < 0 or peak_ram_mb <= 0:
            raise ValidationError("COMPUTE_PROFILE_LIMIT_INVALID", "compute profile resource limits are invalid")
        if tenant_isolation not in {"dedicated_process", "dedicated_container", "dedicated_node", "reference_local"}:
            raise ValidationError("COMPUTE_TENANT_ISOLATION_INVALID", "compute profile tenant isolation is invalid")
        if not cost_stage_weights or any(value < 0 or not math.isfinite(float(value)) for value in cost_stage_weights.values()) or sum(cost_stage_weights.values()) <= 0:
            raise ValidationError("COMPUTE_STAGE_WEIGHTS_INVALID", "compute stage weights must be nonnegative and have positive total")
        missing_cost_stages = sorted(_COST_STAGES - set(cost_stage_weights))
        if missing_cost_stages:
            raise ValidationError(
                "COMPUTE_COST_STAGES_INCOMPLETE",
                "compute profile must account for every reconstruction cost stage",
                {"missing_stages": missing_cost_stages},
            )
        body = {
            "name": name,
            "revision": revision,
            "resolution": resolution,
            "dtype": dtype,
            "backend": backend,
            "model_id": model_id,
            "checkpoint_hash": checkpoint_hash,
            "window_policy": window_policy,
            "memory_limit_mb": memory_limit_mb,
            "timeout_seconds": timeout_seconds,
            "output_class": output_class,
            "quality_tier": quality_tier,
            "cuda_version": cuda_version,
            "driver_constraint": driver_constraint,
            "container_digest": container_digest,
            "tenant_isolation": tenant_isolation,
            "oom_fallback": oom_fallback,
            "expected_runtime_seconds": expected_runtime_seconds,
            "peak_vram_mb": peak_vram_mb,
            "peak_ram_mb": peak_ram_mb,
            "cost_stage_weights": cost_stage_weights,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(ComputeProfileRow).where(ComputeProfileRow.profile_hash == digest))
            if existing is not None:
                return self._compute_profile_result(existing, idempotent_replay=True)
            conflict = session.scalar(select(ComputeProfileRow).where(ComputeProfileRow.name == name, ComputeProfileRow.revision == revision))
            if conflict is not None:
                raise ConflictError("COMPUTE_PROFILE_REVISION_CONFLICT", "compute profile name/revision is already bound to another manifest")
            identifier = new_uuid()
            row = ComputeProfileRow(
                compute_profile_id=identifier,
                name=name,
                revision=revision,
                resolution=resolution,
                dtype=dtype,
                backend=backend,
                model_id=model_id,
                checkpoint_hash=checkpoint_hash,
                window_policy_json=window_policy,
                memory_limit_mb=memory_limit_mb,
                timeout_seconds=timeout_seconds,
                output_class=output_class,
                quality_tier=quality_tier,
                cuda_version=cuda_version,
                driver_constraint=driver_constraint,
                container_digest=container_digest,
                tenant_isolation=tenant_isolation,
                oom_fallback_json=oom_fallback,
                expected_runtime_seconds=expected_runtime_seconds,
                peak_vram_mb=peak_vram_mb,
                peak_ram_mb=peak_ram_mb,
                cost_stage_weights_json={key: float(value) for key, value in cost_stage_weights.items()},
                active=True,
                profile_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id="platform", project_id=None, actor_id=actor_id, action="compute_profile:register", resource_type="compute_profile", resource_id=identifier, outcome="allowed", details={"name": name, "revision": revision, "profile_hash": digest, "checkpoint_hash": checkpoint_hash}, session=session)
            self._emit(session, event_type="compute_profile.registered", tenant_id="platform", project_id=None, aggregate_type="compute_profile", aggregate_id=identifier, payload={"name": name, "revision": revision, "profile_hash": digest, "checkpoint_hash": checkpoint_hash}, actor_id=actor_id)
            return self._compute_profile_result(row, idempotent_replay=False)

    @staticmethod
    def _compute_profile_result(row: ComputeProfileRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "compute_profile_id": row.compute_profile_id,
            "name": row.name,
            "revision": row.revision,
            "model_id": row.model_id,
            "checkpoint_hash": row.checkpoint_hash,
            "expected_runtime_seconds": row.expected_runtime_seconds,
            "peak_vram_mb": row.peak_vram_mb,
            "peak_ram_mb": row.peak_ram_mb,
            "profile_hash": row.profile_hash,
            "idempotent_replay": idempotent_replay,
        }

    def register_price_catalog(
        self,
        *,
        tenant_id: str,
        version: str,
        currency: str,
        effective_at: datetime,
        expires_at: datetime | None,
        prices: dict[str, dict[str, Any]],
        source_reference: str,
        source_hash: str,
        actor_id: str,
    ) -> dict[str, Any]:
        version = _require_identifier(version, code="PRICE_VERSION_INVALID", field="version", pattern=_VERSION)
        currency = currency.upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValidationError("PRICE_CURRENCY_INVALID", "price currency must be an ISO-style three-letter code")
        source_hash = _require_sha256(source_hash, code="PRICE_SOURCE_HASH_INVALID", field="source_hash")
        source_reference = _bounded_string(source_reference, code="PRICE_SOURCE_REFERENCE_INVALID", field="source_reference", limit=512)
        if not prices or set(prices) - _COST_RESOURCES:
            raise ValidationError("PRICE_RESOURCE_INVALID", "price catalog contains unknown or empty resource entries", {"unknown": sorted(set(prices) - _COST_RESOURCES)})
        normalized: dict[str, dict[str, Any]] = {}
        for resource, entry in prices.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("rate"), (int, float)) or float(entry["rate"]) < 0 or not math.isfinite(float(entry["rate"])) or not entry.get("unit"):
                raise ValidationError("PRICE_ENTRY_INVALID", "price entry requires nonnegative rate and unit", {"resource": resource})
            normalized[resource] = {"rate": float(entry["rate"]), "unit": str(entry["unit"])}
        effective = _aware(effective_at)
        expiration = _aware(expires_at) if expires_at is not None else None
        if expiration is not None and expiration <= effective:
            raise ValidationError("PRICE_VALIDITY_INVALID", "price catalog expiration must follow effective time")
        body = {
            "tenant_id": tenant_id,
            "version": version,
            "currency": currency,
            "effective_at": effective.isoformat(),
            "expires_at": expiration.isoformat() if expiration else None,
            "prices": normalized,
            "source_reference": source_reference,
            "source_hash": source_hash,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            tenant = session.get(TenantRow, tenant_id)
            if tenant is None or tenant.status != "active":
                raise NotFoundError("tenant", tenant_id)
            existing = session.scalar(select(PriceCatalogRow).where(PriceCatalogRow.catalog_hash == digest))
            if existing is not None:
                return self._price_catalog_result(existing, idempotent_replay=True)
            conflict = session.scalar(select(PriceCatalogRow).where(PriceCatalogRow.tenant_id == tenant_id, PriceCatalogRow.version == version))
            if conflict is not None:
                raise ConflictError("PRICE_VERSION_CONFLICT", "price catalog version is already bound to different inputs")
            latest = session.scalar(select(PriceCatalogRow).where(PriceCatalogRow.tenant_id == tenant_id).order_by(PriceCatalogRow.effective_at.desc()).limit(1))
            identifier = new_uuid()
            row = PriceCatalogRow(
                price_catalog_id=identifier,
                tenant_id=tenant_id,
                version=version,
                currency=currency,
                effective_at=effective,
                expires_at=expiration,
                prices_json=normalized,
                source_reference=source_reference,
                source_hash=source_hash,
                supersedes_price_catalog_id=latest.price_catalog_id if latest else None,
                catalog_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=None, actor_id=actor_id, action="price_catalog:register", resource_type="price_catalog", resource_id=identifier, outcome="allowed", details={"version": version, "currency": currency, "source_hash": source_hash, "catalog_hash": digest}, session=session)
            self._emit(session, event_type="price_catalog.registered", tenant_id=tenant_id, project_id=None, aggregate_type="price_catalog", aggregate_id=identifier, payload={"version": version, "currency": currency, "source_hash": source_hash, "catalog_hash": digest}, actor_id=actor_id)
            return self._price_catalog_result(row, idempotent_replay=False)

    @staticmethod
    def _price_catalog_result(row: PriceCatalogRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "price_catalog_id": row.price_catalog_id,
            "version": row.version,
            "currency": row.currency,
            "effective_at": row.effective_at.isoformat(),
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "prices": row.prices_json,
            "source_reference": row.source_reference,
            "source_hash": row.source_hash,
            "catalog_hash": row.catalog_hash,
            "supersedes_price_catalog_id": row.supersedes_price_catalog_id,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _require_catalog_current(row: PriceCatalogRow, now: datetime) -> None:
        effective = _aware(row.effective_at)
        expires = _aware(row.expires_at) if row.expires_at else None
        if effective > now or (expires is not None and expires <= now):
            raise ConflictError("PRICE_CATALOG_STALE", "price catalog is not current for new admission", {"version": row.version})

    @staticmethod
    def _cost_line_items(prices: dict[str, dict[str, Any]], quantities: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
        unknown = set(quantities) - set(prices)
        if unknown:
            raise ValidationError("COST_RESOURCE_PRICE_MISSING", "cost quantities reference resources absent from the catalog", {"resources": sorted(unknown)})
        line_items: list[dict[str, Any]] = []
        total = 0.0
        for resource in sorted(quantities):
            quantity = quantities[resource]
            if not isinstance(quantity, (int, float)) or not math.isfinite(float(quantity)) or float(quantity) < 0:
                raise ValidationError("COST_QUANTITY_INVALID", "cost quantity must be a nonnegative finite number", {"resource": resource})
            rate = float(prices[resource]["rate"])
            amount = float(quantity) * rate
            line_items.append({"resource": resource, "quantity": float(quantity), "unit": prices[resource]["unit"], "unit_rate": rate, "amount": amount})
            total += amount
        return line_items, total

    def estimate_cost(
        self,
        *,
        tenant_id: str,
        project_id: str,
        run_id: str,
        operation_id: str | None,
        capture_id: str | None,
        compute_profile_id: str,
        price_catalog_id: str,
        input_class: dict[str, Any],
        quantities: dict[str, Any],
        ttl_seconds: int,
        actor_id: str,
    ) -> dict[str, Any]:
        if ttl_seconds < 60 or ttl_seconds > 86_400:
            raise ValidationError("COST_ESTIMATE_TTL_INVALID", "cost estimate TTL must be between 60 and 86400 seconds")
        run_id = _require_identifier(run_id, code="COST_RUN_ID_INVALID", field="run_id")
        now = db_now()
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            profile = session.get(ComputeProfileRow, compute_profile_id)
            if profile is None or not profile.active:
                raise NotFoundError("compute_profile", compute_profile_id)
            catalog = session.get(PriceCatalogRow, price_catalog_id)
            if catalog is None or catalog.tenant_id != tenant_id:
                raise NotFoundError("price_catalog", price_catalog_id)
            self._require_catalog_current(catalog, now)
            line_items, total = self._cost_line_items(catalog.prices_json, quantities)
            weights = profile.cost_stage_weights_json
            weight_total = sum(float(value) for value in weights.values())
            stage_estimates = [
                {"stage": stage, "amount": total * float(weight) / weight_total, "weight": float(weight)}
                for stage, weight in sorted(weights.items())
            ]
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "capture_id": capture_id,
                "compute_profile_id": compute_profile_id,
                "profile_hash": profile.profile_hash,
                "price_catalog_id": price_catalog_id,
                "catalog_hash": catalog.catalog_hash,
                "input_class": input_class,
                "quantities": quantities,
                "line_items": line_items,
                "stage_estimates": stage_estimates,
                "total": total,
                "currency": catalog.currency,
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(CostEstimateRow).where(CostEstimateRow.tenant_id == tenant_id, CostEstimateRow.project_id == project_id, CostEstimateRow.run_id == run_id))
            if existing is not None:
                if existing.estimate_hash != digest:
                    raise ConflictError("COST_ESTIMATE_IDEMPOTENCY_CONFLICT", "run identifier is already bound to a different estimate")
                return self._cost_estimate_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = CostEstimateRow(
                estimate_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                operation_id=operation_id,
                capture_id=capture_id,
                run_id=run_id,
                compute_profile_id=compute_profile_id,
                price_catalog_id=price_catalog_id,
                input_class_json={**input_class, "quantities": quantities, "catalog_hash": catalog.catalog_hash, "profile_hash": profile.profile_hash},
                stage_estimates_json=stage_estimates,
                total_amount=total,
                currency=catalog.currency,
                estimate_hash=digest,
                state="active",
                expires_at=now + timedelta(seconds=ttl_seconds),
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="cost:estimate", resource_type="cost_estimate", resource_id=identifier, outcome="allowed", details={"run_id": run_id, "estimate_hash": digest, "total": total, "currency": catalog.currency, "catalog_hash": catalog.catalog_hash}, session=session)
            self._emit(session, event_type="cost.estimated", tenant_id=tenant_id, project_id=project_id, aggregate_type="cost_estimate", aggregate_id=identifier, payload={"run_id": run_id, "estimate_hash": digest, "total": total, "currency": catalog.currency, "catalog_hash": catalog.catalog_hash}, actor_id=actor_id)
            return self._cost_estimate_result(row, idempotent_replay=False)

    @staticmethod
    def _cost_estimate_result(row: CostEstimateRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "estimate_id": row.estimate_id,
            "run_id": row.run_id,
            "operation_id": row.operation_id,
            "capture_id": row.capture_id,
            "compute_profile_id": row.compute_profile_id,
            "price_catalog_id": row.price_catalog_id,
            "input_class": row.input_class_json,
            "stage_estimates": row.stage_estimates_json,
            "total_amount": row.total_amount,
            "currency": row.currency,
            "estimate_hash": row.estimate_hash,
            "state": row.state,
            "expires_at": row.expires_at.isoformat(),
            "idempotent_replay": idempotent_replay,
        }

    def record_actual_cost(
        self,
        *,
        tenant_id: str,
        project_id: str,
        idempotency_key: str,
        run_id: str,
        stage: str,
        operation_id: str | None,
        capture_id: str | None,
        model_id: str | None,
        checkpoint_hash: str | None,
        price_catalog_id: str,
        usage: dict[str, Any],
        occurred_at: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        idempotency_key = _require_identifier(idempotency_key, code="ACTUAL_COST_IDEMPOTENCY_INVALID", field="idempotency_key")
        stage = _require_identifier(stage, code="ACTUAL_COST_STAGE_INVALID", field="stage")
        if checkpoint_hash is not None:
            checkpoint_hash = _require_sha256(checkpoint_hash, code="ACTUAL_COST_CHECKPOINT_INVALID", field="checkpoint_hash")
        occurred = _aware(occurred_at)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            catalog = session.get(PriceCatalogRow, price_catalog_id)
            if catalog is None or catalog.tenant_id != tenant_id:
                raise NotFoundError("price_catalog", price_catalog_id)
            effective = _aware(catalog.effective_at)
            expiration = _aware(catalog.expires_at) if catalog.expires_at else None
            if occurred < effective or (expiration is not None and occurred >= expiration):
                raise ConflictError("ACTUAL_COST_PRICE_TIME_MISMATCH", "actual usage time is outside the retained catalog validity window")
            line_items, total = self._cost_line_items(catalog.prices_json, usage)
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "idempotency_key": idempotency_key,
                "run_id": run_id,
                "stage": stage,
                "operation_id": operation_id,
                "capture_id": capture_id,
                "model_id": model_id,
                "checkpoint_hash": checkpoint_hash,
                "price_catalog_id": price_catalog_id,
                "catalog_hash": catalog.catalog_hash,
                "usage": usage,
                "line_items": line_items,
                "amount": total,
                "currency": catalog.currency,
                "occurred_at": occurred.isoformat(),
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(ActualCostRow).where(ActualCostRow.tenant_id == tenant_id, ActualCostRow.project_id == project_id, ActualCostRow.idempotency_key == idempotency_key))
            if existing is not None:
                if existing.actual_hash != digest:
                    raise ConflictError("ACTUAL_COST_IDEMPOTENCY_CONFLICT", "actual-cost idempotency key is already bound to different usage")
                return self._actual_cost_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = ActualCostRow(
                actual_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                operation_id=operation_id,
                capture_id=capture_id,
                run_id=run_id,
                stage=stage,
                model_id=model_id,
                checkpoint_hash=checkpoint_hash,
                price_catalog_id=price_catalog_id,
                usage_json={"quantities": usage, "line_items": line_items, "catalog_hash": catalog.catalog_hash, "occurred_at": occurred.isoformat()},
                amount=total,
                currency=catalog.currency,
                actual_hash=digest,
                idempotency_key=idempotency_key,
                recorded_by=actor_id,
                recorded_at=occurred,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="cost:record_actual", resource_type="actual_cost", resource_id=identifier, outcome="allowed", details={"run_id": run_id, "stage": stage, "actual_hash": digest, "amount": total, "currency": catalog.currency, "catalog_hash": catalog.catalog_hash}, session=session)
            self._emit(session, event_type="cost.actual_recorded", tenant_id=tenant_id, project_id=project_id, aggregate_type="actual_cost", aggregate_id=identifier, payload={"run_id": run_id, "stage": stage, "actual_hash": digest, "amount": total, "currency": catalog.currency, "catalog_hash": catalog.catalog_hash}, actor_id=actor_id)
            estimate = session.scalar(select(CostEstimateRow).where(CostEstimateRow.tenant_id == tenant_id, CostEstimateRow.project_id == project_id, CostEstimateRow.run_id == run_id))
            if estimate is not None and estimate.total_amount > 0:
                ratio = total / estimate.total_amount
                policy = self._active_budget_policy(session, tenant_id, project_id)
                threshold = policy.anomaly_threshold if policy is not None else 1.5
                if ratio >= threshold:
                    self._create_anomaly_in_session(session, tenant_id=tenant_id, project_id=project_id, category="cost_reconciliation", severity="high", metric_name="actual_to_estimate_ratio", observed_value=ratio, baseline_value=1.0, threshold=threshold, evidence={"estimate_id": estimate.estimate_id, "actual_id": identifier, "estimate_hash": estimate.estimate_hash, "actual_hash": digest}, actor_id=actor_id)
            return self._actual_cost_result(row, idempotent_replay=False)

    @staticmethod
    def _actual_cost_result(row: ActualCostRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "actual_id": row.actual_id,
            "run_id": row.run_id,
            "stage": row.stage,
            "operation_id": row.operation_id,
            "capture_id": row.capture_id,
            "model_id": row.model_id,
            "checkpoint_hash": row.checkpoint_hash,
            "price_catalog_id": row.price_catalog_id,
            "usage": row.usage_json,
            "amount": row.amount,
            "currency": row.currency,
            "actual_hash": row.actual_hash,
            "recorded_at": row.recorded_at.isoformat(),
            "idempotent_replay": idempotent_replay,
        }

    def cost_rollup(
        self,
        *,
        tenant_id: str,
        project_id: str,
        period_start: datetime,
        period_end: datetime,
        dimensions: list[str],
    ) -> dict[str, Any]:
        allowed_dimensions = {"project", "capture", "run", "stage", "model", "calendar_day"}
        if set(dimensions) - allowed_dimensions or not dimensions:
            raise ValidationError("COST_ROLLUP_DIMENSIONS_INVALID", "cost rollup dimensions are invalid")
        start, end = _aware(period_start), _aware(period_end)
        if end <= start:
            raise ValidationError("COST_ROLLUP_PERIOD_INVALID", "cost rollup period is invalid")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            rows = list(session.scalars(select(ActualCostRow).where(ActualCostRow.tenant_id == tenant_id, ActualCostRow.project_id == project_id, ActualCostRow.recorded_at >= start, ActualCostRow.recorded_at < end)))
        groups: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in rows:
            values: list[str] = []
            labels: dict[str, str] = {}
            for dimension in dimensions:
                if dimension == "project":
                    value = pseudonymize_identifier(project_id, namespace="project")
                elif dimension == "capture":
                    value = row.capture_id or "none"
                elif dimension == "run":
                    value = row.run_id
                elif dimension == "stage":
                    value = row.stage
                elif dimension == "model":
                    value = row.model_id or "none"
                else:
                    value = _aware(row.recorded_at).date().isoformat()
                values.append(value)
                labels[dimension] = value
            key = tuple(values)
            group = groups.setdefault(key, {"dimensions": labels, "amount": 0.0, "currency": row.currency, "records": 0})
            if group["currency"] != row.currency:
                raise ConflictError("COST_ROLLUP_CURRENCY_CONFLICT", "rollup cannot combine currencies")
            group["amount"] += row.amount
            group["records"] += 1
        return {"period_start": start.isoformat(), "period_end": end.isoformat(), "groups": [groups[key] for key in sorted(groups)], "record_count": len(rows)}

    def reconcile_cost(self, *, tenant_id: str, project_id: str, run_id: str, actor_id: str) -> dict[str, Any]:
        run_id = _require_identifier(run_id, code="COST_RUN_ID_INVALID", field="run_id")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            estimate = session.scalar(select(CostEstimateRow).where(CostEstimateRow.tenant_id == tenant_id, CostEstimateRow.project_id == project_id, CostEstimateRow.run_id == run_id))
            if estimate is None:
                raise NotFoundError("cost_estimate", run_id)
            actuals = list(session.scalars(select(ActualCostRow).where(ActualCostRow.tenant_id == tenant_id, ActualCostRow.project_id == project_id, ActualCostRow.run_id == run_id).order_by(ActualCostRow.actual_id)))
            if not actuals:
                raise ConflictError("COST_RECONCILIATION_ACTUALS_MISSING", "cost reconciliation requires retained actual usage")
            currency = estimate.currency
            if any(row.currency != currency for row in actuals):
                raise ConflictError("COST_RECONCILIATION_CURRENCY_CONFLICT", "actual records do not share the estimate currency")
            total = sum(row.amount for row in actuals)
            ratio = total / estimate.total_amount if estimate.total_amount else 0.0
            catalog_hashes: list[str] = []
            for row in actuals:
                catalog = session.get(PriceCatalogRow, row.price_catalog_id)
                if catalog is None:
                    raise ConflictError("COST_RECONCILIATION_CATALOG_MISSING", "historical price catalog is unavailable")
                catalog_hashes.append(catalog.catalog_hash)
            body = {"tenant_id": tenant_id, "project_id": project_id, "run_id": run_id, "estimate_id": estimate.estimate_id, "actual_ids": [row.actual_id for row in actuals], "estimated_amount": estimate.total_amount, "actual_amount": total, "currency": currency, "catalog_hashes": sorted(set(catalog_hashes))}
            digest = canonical_sha256(body)
            existing = session.scalar(select(CostReconciliationRow).where(CostReconciliationRow.tenant_id == tenant_id, CostReconciliationRow.project_id == project_id, CostReconciliationRow.run_id == run_id))
            if existing is not None:
                if existing.reconciliation_hash != digest:
                    raise ConflictError("COST_RECONCILIATION_CHANGED", "new actual records require a new governed run identity")
                return self._cost_reconciliation_result(existing, idempotent_replay=True)
            row = CostReconciliationRow(reconciliation_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, run_id=run_id, estimate_id=estimate.estimate_id, actual_ids_json=[item.actual_id for item in actuals], estimated_amount=estimate.total_amount, actual_amount=total, delta_amount=total-estimate.total_amount, ratio=ratio, currency=currency, catalog_hashes_json=sorted(set(catalog_hashes)), reconciliation_hash=digest, created_by=actor_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="cost:reconcile", resource_type="cost_reconciliation", resource_id=row.reconciliation_id, outcome="allowed", details={"run_id": run_id, "reconciliation_hash": digest, "estimated": estimate.total_amount, "actual": total}, session=session)
            self._emit(session, event_type="cost.reconciled", tenant_id=tenant_id, project_id=project_id, aggregate_type="cost_reconciliation", aggregate_id=row.reconciliation_id, payload={"run_id": run_id, "reconciliation_hash": digest, "ratio": ratio}, actor_id=actor_id)
            return self._cost_reconciliation_result(row, idempotent_replay=False)

    @staticmethod
    def _cost_reconciliation_result(row: CostReconciliationRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"reconciliation_id": row.reconciliation_id, "run_id": row.run_id, "estimate_id": row.estimate_id, "actual_ids": row.actual_ids_json, "estimated_amount": row.estimated_amount, "actual_amount": row.actual_amount, "delta_amount": row.delta_amount, "ratio": row.ratio, "currency": row.currency, "catalog_hashes": row.catalog_hashes_json, "reconciliation_hash": row.reconciliation_hash, "idempotent_replay": idempotent_replay}

    def register_capacity_plan(self, *, tenant_id: str, project_id: str | None, profile_name: str, measurement_window: dict[str, Any], scene_minutes: float, frames: int, area_m2: float, peak_concurrency: int, headroom_ratio: float, required_capacity: dict[str, Any], evidence_class: str, source_manifest_hash: str, actor_id: str) -> dict[str, Any]:
        profile_name = _require_identifier(profile_name, code="CAPACITY_PROFILE_INVALID", field="profile_name")
        source_manifest_hash = _require_sha256(source_manifest_hash, code="CAPACITY_SOURCE_MANIFEST_INVALID", field="source_manifest_hash")
        if evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            raise ValidationError("CAPACITY_EVIDENCE_CLASS_INVALID", "unsupported capacity evidence class")
        if scene_minutes <= 0 or frames <= 0 or area_m2 <= 0 or peak_concurrency <= 0 or headroom_ratio < 1.0:
            raise ValidationError("CAPACITY_INPUT_INVALID", "capacity plans require measured workload and headroom")
        if not measurement_window.get("start") or not measurement_window.get("end") or not required_capacity:
            raise ValidationError("CAPACITY_EVIDENCE_INCOMPLETE", "capacity plans require a measurement window and required resources")
        body = {"tenant_id": tenant_id, "project_id": project_id, "profile_name": profile_name, "measurement_window": measurement_window, "scene_minutes": scene_minutes, "frames": frames, "area_m2": area_m2, "peak_concurrency": peak_concurrency, "headroom_ratio": headroom_ratio, "required_capacity": required_capacity, "evidence_class": evidence_class, "source_manifest_hash": source_manifest_hash}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(CapacityPlanRow).where(CapacityPlanRow.plan_hash == digest))
            if existing is not None:
                return self._capacity_plan_result(existing, idempotent_replay=True)
            row = CapacityPlanRow(capacity_plan_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, profile_name=profile_name, measurement_window_json=measurement_window, scene_minutes=scene_minutes, frames=frames, area_m2=area_m2, peak_concurrency=peak_concurrency, headroom_ratio=headroom_ratio, required_capacity_json=required_capacity, evidence_class=evidence_class, source_manifest_hash=source_manifest_hash, plan_hash=digest, created_by=actor_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="capacity_plan:create", resource_type="capacity_plan", resource_id=row.capacity_plan_id, outcome="allowed", details={"profile_name": profile_name, "plan_hash": digest, "evidence_class": evidence_class}, session=session)
            self._emit(session, event_type="capacity.plan_registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="capacity_plan", aggregate_id=row.capacity_plan_id, payload={"profile_name": profile_name, "plan_hash": digest, "evidence_class": evidence_class}, actor_id=actor_id)
            return self._capacity_plan_result(row, idempotent_replay=False)

    @staticmethod
    def _capacity_plan_result(row: CapacityPlanRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"capacity_plan_id": row.capacity_plan_id, "profile_name": row.profile_name, "measurement_window": row.measurement_window_json, "scene_minutes": row.scene_minutes, "frames": row.frames, "area_m2": row.area_m2, "peak_concurrency": row.peak_concurrency, "headroom_ratio": row.headroom_ratio, "required_capacity": row.required_capacity_json, "evidence_class": row.evidence_class, "source_manifest_hash": row.source_manifest_hash, "plan_hash": row.plan_hash, "idempotent_replay": idempotent_replay}

    # -------------------------------------------------------------- admission
    def register_budget_policy(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        revision: str,
        currency: str,
        period_seconds: int,
        soft_limit: float,
        hard_limit: float,
        concurrency_limit: int,
        storage_limit_bytes: int,
        retention_limit_days: int,
        anomaly_threshold: float,
        actor_id: str,
    ) -> dict[str, Any]:
        currency = currency.upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValidationError("BUDGET_CURRENCY_INVALID", "budget currency is invalid")
        revision = _require_identifier(revision, code="BUDGET_REVISION_INVALID", field="revision", pattern=_VERSION)
        if period_seconds <= 0 or soft_limit < 0 or hard_limit <= 0 or soft_limit > hard_limit or concurrency_limit < 1 or storage_limit_bytes < 0 or retention_limit_days < 1 or anomaly_threshold <= 1:
            raise ValidationError("BUDGET_POLICY_INVALID", "budget policy values are invalid")
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "revision": revision,
            "currency": currency,
            "period_seconds": period_seconds,
            "soft_limit": soft_limit,
            "hard_limit": hard_limit,
            "concurrency_limit": concurrency_limit,
            "storage_limit_bytes": storage_limit_bytes,
            "retention_limit_days": retention_limit_days,
            "anomaly_threshold": anomaly_threshold,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(BudgetPolicyRow).where(BudgetPolicyRow.policy_hash == digest))
            if existing is not None:
                return self._budget_policy_result(existing, idempotent_replay=True)
            latest = session.scalar(select(BudgetPolicyRow).where(BudgetPolicyRow.tenant_id == tenant_id, BudgetPolicyRow.project_id == project_id, BudgetPolicyRow.active.is_(True)).limit(1))
            if latest is not None:
                latest.active = False
            identifier = new_uuid()
            row = BudgetPolicyRow(
                budget_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                revision=revision,
                currency=currency,
                period_seconds=period_seconds,
                soft_limit=soft_limit,
                hard_limit=hard_limit,
                concurrency_limit=concurrency_limit,
                storage_limit_bytes=storage_limit_bytes,
                retention_limit_days=retention_limit_days,
                anomaly_threshold=anomaly_threshold,
                active=True,
                policy_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="budget_policy:register", resource_type="budget_policy", resource_id=identifier, outcome="allowed", details={"revision": revision, "currency": currency, "soft_limit": soft_limit, "hard_limit": hard_limit, "concurrency_limit": concurrency_limit, "policy_hash": digest}, session=session)
            self._emit(session, event_type="budget.policy_registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="budget_policy", aggregate_id=identifier, payload={"revision": revision, "currency": currency, "soft_limit": soft_limit, "hard_limit": hard_limit, "concurrency_limit": concurrency_limit, "policy_hash": digest}, actor_id=actor_id)
            return self._budget_policy_result(row, idempotent_replay=False)

    @staticmethod
    def _budget_policy_result(row: BudgetPolicyRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "budget_id": row.budget_id,
            "revision": row.revision,
            "currency": row.currency,
            "period_seconds": row.period_seconds,
            "soft_limit": row.soft_limit,
            "hard_limit": row.hard_limit,
            "concurrency_limit": row.concurrency_limit,
            "storage_limit_bytes": row.storage_limit_bytes,
            "retention_limit_days": row.retention_limit_days,
            "anomaly_threshold": row.anomaly_threshold,
            "policy_hash": row.policy_hash,
            "active": row.active,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _active_budget_policy(session: Session, tenant_id: str, project_id: str) -> BudgetPolicyRow | None:
        return session.scalar(
            select(BudgetPolicyRow)
            .where(
                BudgetPolicyRow.tenant_id == tenant_id,
                BudgetPolicyRow.active.is_(True),
                (BudgetPolicyRow.project_id == project_id) | (BudgetPolicyRow.project_id.is_(None)),
            )
            .order_by(BudgetPolicyRow.project_id.desc())
            .limit(1)
        )

    def request_budget_override(
        self,
        *,
        tenant_id: str,
        project_id: str,
        budget_id: str,
        requested_by: str,
        reason: str,
        additional_amount: float,
        currency: str,
        expires_at: datetime,
    ) -> dict[str, Any]:
        if additional_amount <= 0 or not math.isfinite(additional_amount):
            raise ValidationError("BUDGET_OVERRIDE_AMOUNT_INVALID", "budget override amount must be positive")
        reason = _bounded_string(reason, code="BUDGET_OVERRIDE_REASON_INVALID", field="reason", limit=512)
        requester = _require_identifier(requested_by, code="BUDGET_OVERRIDE_REQUESTER_INVALID", field="requested_by")
        expiration = _aware(expires_at)
        now = db_now()
        if expiration <= now or expiration > now + timedelta(days=7):
            raise ValidationError("BUDGET_OVERRIDE_EXPIRY_INVALID", "budget override must expire within seven days")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            policy = session.get(BudgetPolicyRow, budget_id)
            if policy is None or policy.tenant_id != tenant_id or policy.project_id not in {None, project_id}:
                raise NotFoundError("budget_policy", budget_id)
            if currency.upper() != policy.currency:
                raise ValidationError("BUDGET_OVERRIDE_CURRENCY_INVALID", "override currency must match policy")
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "budget_id": budget_id,
                "requested_by": requester,
                "reason": reason,
                "additional_amount": additional_amount,
                "currency": policy.currency,
                "expires_at": expiration.isoformat(),
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(BudgetOverrideRow).where(BudgetOverrideRow.override_hash == digest))
            if existing is not None:
                return self._budget_override_result(existing, idempotent_replay=True)
            row = BudgetOverrideRow(
                override_id=new_uuid(), budget_id=budget_id, tenant_id=tenant_id, project_id=project_id,
                requested_by=requester, approved_by=None, reason=reason,
                additional_amount=additional_amount, currency=policy.currency, expires_at=expiration,
                state="pending", override_hash=digest, approval_hash=None,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id, project_id=project_id, actor_id=requester,
                action="budget_override:request", resource_type="budget_override", resource_id=row.override_id,
                outcome="allowed", details={"budget_id": budget_id, "additional_amount": additional_amount,
                "expires_at": expiration.isoformat(), "override_hash": digest}, session=session,
            )
            self._emit(
                session, event_type="budget.override_requested", tenant_id=tenant_id, project_id=project_id,
                aggregate_type="budget_override", aggregate_id=row.override_id,
                payload={"budget_id": budget_id, "additional_amount": additional_amount,
                "currency": policy.currency, "expires_at": expiration.isoformat(), "override_hash": digest},
                actor_id=requester,
            )
            return self._budget_override_result(row, idempotent_replay=False)

    def approve_budget_override(
        self,
        *,
        tenant_id: str,
        project_id: str,
        override_id: str,
        approved_by: str,
    ) -> dict[str, Any]:
        approver = _require_identifier(approved_by, code="BUDGET_OVERRIDE_APPROVER_INVALID", field="approved_by")
        with self.database.session() as session:
            row = session.get(BudgetOverrideRow, override_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("budget_override", override_id)
            if row.requested_by == approver:
                raise AuthorizationError("BUDGET_OVERRIDE_SELF_APPROVAL_DENIED", "budget override requires independent approval")
            if row.state == "active":
                if row.approved_by != approver:
                    raise ConflictError("BUDGET_OVERRIDE_ALREADY_APPROVED", "override was approved by a different principal")
                return self._budget_override_result(row, idempotent_replay=True)
            if row.state != "pending" or _aware(row.expires_at) <= db_now():
                raise ConflictError("BUDGET_OVERRIDE_NOT_APPROVABLE", "budget override is expired, revoked, or not pending")
            approval_body = {
                "override_hash": row.override_hash,
                "approved_by": approver,
                "approved_at": db_now().isoformat(),
            }
            row.approved_by = approver
            row.approved_at = db_now()
            row.approval_hash = canonical_sha256({**approval_body, "approved_at": row.approved_at.isoformat()})
            row.state = "active"
            self.audit.append(
                tenant_id=tenant_id, project_id=project_id, actor_id=approver,
                action="budget_override:approve", resource_type="budget_override", resource_id=row.override_id,
                outcome="allowed", details={"budget_id": row.budget_id, "requested_by": row.requested_by,
                "additional_amount": row.additional_amount, "expires_at": row.expires_at.isoformat(),
                "override_hash": row.override_hash, "approval_hash": row.approval_hash}, session=session,
            )
            self._emit(
                session, event_type="budget.override_approved", tenant_id=tenant_id, project_id=project_id,
                aggregate_type="budget_override", aggregate_id=row.override_id,
                payload={"budget_id": row.budget_id, "additional_amount": row.additional_amount,
                "currency": row.currency, "expires_at": row.expires_at.isoformat(),
                "override_hash": row.override_hash, "approval_hash": row.approval_hash}, actor_id=approver,
            )
            return self._budget_override_result(row, idempotent_replay=False)

    @staticmethod
    def _budget_override_result(row: BudgetOverrideRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "override_id": row.override_id,
            "budget_id": row.budget_id,
            "requested_by": row.requested_by,
            "approved_by": row.approved_by,
            "additional_amount": row.additional_amount,
            "currency": row.currency,
            "expires_at": row.expires_at.isoformat(),
            "state": row.state,
            "override_hash": row.override_hash,
            "approval_hash": row.approval_hash,
            "idempotent_replay": idempotent_replay,
        }

    def reserve_budget(
        self,
        *,
        tenant_id: str,
        project_id: str,
        estimate_id: str,
        idempotency_key: str,
        operation_id: str | None,
        ttl_seconds: int,
        requested_by: str,
        override_id: str | None = None,
    ) -> dict[str, Any]:
        if ttl_seconds < 30 or ttl_seconds > 86_400:
            raise ValidationError("BUDGET_RESERVATION_TTL_INVALID", "reservation TTL must be between 30 and 86400 seconds")
        idempotency_key = _require_identifier(idempotency_key, code="BUDGET_RESERVATION_IDEMPOTENCY_INVALID", field="idempotency_key")
        now = db_now()
        denial: tuple[str, str, dict[str, Any]] | None = None
        result: dict[str, Any] | None = None
        try:
            session = self.database.session_factory()
            try:
                if self.database.url.startswith("sqlite"):
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                self._require_project(session, tenant_id, project_id)
                existing = session.scalar(select(BudgetReservationRow).where(BudgetReservationRow.tenant_id == tenant_id, BudgetReservationRow.project_id == project_id, BudgetReservationRow.idempotency_key == idempotency_key))
                estimate = session.get(CostEstimateRow, estimate_id)
                if estimate is None or estimate.tenant_id != tenant_id or estimate.project_id != project_id:
                    raise NotFoundError("cost_estimate", estimate_id)
                if _aware(estimate.expires_at) <= now or estimate.state != "active":
                    raise ConflictError("COST_ESTIMATE_EXPIRED", "cost estimate is not eligible for admission")
                if existing is not None:
                    if existing.estimate_id != estimate_id or existing.amount != estimate.total_amount or existing.currency != estimate.currency:
                        raise ConflictError("BUDGET_RESERVATION_IDEMPOTENCY_CONFLICT", "reservation idempotency key is bound to a different request")
                    result = self._reservation_result(existing, idempotent_replay=True)
                    session.rollback()
                    return result
                policy_statement = select(BudgetPolicyRow).where(BudgetPolicyRow.tenant_id == tenant_id, BudgetPolicyRow.active.is_(True), (BudgetPolicyRow.project_id == project_id) | (BudgetPolicyRow.project_id.is_(None))).order_by(BudgetPolicyRow.project_id.desc()).limit(1)
                if not self.database.url.startswith("sqlite"):
                    policy_statement = policy_statement.with_for_update()
                policy = session.scalar(policy_statement)
                if policy is None:
                    denial = ("BUDGET_POLICY_MISSING", "no active budget policy applies to the project", {})
                elif policy.currency != estimate.currency:
                    denial = ("BUDGET_CURRENCY_MISMATCH", "estimate currency does not match the budget policy", {})
                else:
                    session.query(BudgetReservationRow).filter(BudgetReservationRow.tenant_id == tenant_id, BudgetReservationRow.project_id == project_id, BudgetReservationRow.state == "reserved", BudgetReservationRow.expires_at <= now).update({"state": "expired"}, synchronize_session=False)
                    active_reservations = list(session.scalars(select(BudgetReservationRow).where(BudgetReservationRow.tenant_id == tenant_id, BudgetReservationRow.project_id == project_id, BudgetReservationRow.state == "reserved", BudgetReservationRow.expires_at > now)))
                    period_start = now - timedelta(seconds=policy.period_seconds)
                    actual_spend = float(session.scalar(select(func.coalesce(func.sum(ActualCostRow.amount), 0.0)).where(ActualCostRow.tenant_id == tenant_id, ActualCostRow.project_id == project_id, ActualCostRow.recorded_at >= period_start, ActualCostRow.currency == policy.currency)) or 0.0)
                    reserved_spend = sum(item.amount for item in active_reservations)
                    allowed = policy.hard_limit
                    override = None
                    if override_id is not None:
                        override = session.get(BudgetOverrideRow, override_id)
                        if override is None or override.tenant_id != tenant_id or override.project_id != project_id or override.budget_id != policy.budget_id or override.state != "active" or _aware(override.expires_at) <= now or override.currency != policy.currency or override.requested_by != requested_by:
                            denial = ("BUDGET_OVERRIDE_INVALID", "budget override is missing, expired, wrong-scope, or requester-mismatched", {})
                        else:
                            allowed += override.additional_amount
                    input_class = estimate.input_class_json
                    storage_bytes = int(input_class.get("storage_bytes", 0))
                    retention_days = int(input_class.get("retention_days", 1))
                    if denial is None and len(active_reservations) >= policy.concurrency_limit:
                        denial = ("BUDGET_CONCURRENCY_LIMIT", "project concurrent-job limit has been reached", {"active": len(active_reservations), "limit": policy.concurrency_limit})
                    elif denial is None and storage_bytes > policy.storage_limit_bytes:
                        denial = ("BUDGET_STORAGE_LIMIT", "estimated retained storage exceeds the project policy", {"requested": storage_bytes, "limit": policy.storage_limit_bytes})
                    elif denial is None and retention_days > policy.retention_limit_days:
                        denial = ("BUDGET_RETENTION_LIMIT", "requested retention exceeds the project policy", {"requested": retention_days, "limit": policy.retention_limit_days})
                    elif denial is None and actual_spend + reserved_spend + estimate.total_amount > allowed:
                        denial = ("BUDGET_HARD_LIMIT", "operation exceeds the project hard budget", {"actual": actual_spend, "reserved": reserved_spend, "requested": estimate.total_amount, "limit": allowed})
                    if denial is None:
                        identifier = new_uuid()
                        row = BudgetReservationRow(
                            reservation_id=identifier,
                            budget_id=policy.budget_id,
                            tenant_id=tenant_id,
                            project_id=project_id,
                            operation_id=operation_id,
                            estimate_id=estimate_id,
                            idempotency_key=idempotency_key,
                            amount=estimate.total_amount,
                            currency=estimate.currency,
                            state="reserved",
                            requested_by=requested_by,
                            expires_at=now + timedelta(seconds=ttl_seconds),
                            release_reason=None,
                        )
                        session.add(row)
                        session.flush()
                        self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=requested_by, action="budget:reserve", resource_type="budget_reservation", resource_id=identifier, outcome="allowed", details={"budget_id": policy.budget_id, "estimate_id": estimate_id, "amount": estimate.total_amount, "currency": estimate.currency, "expires_at": row.expires_at.isoformat(), "override_id": override.override_id if override else None}, session=session)
                        self._emit(session, event_type="budget.reservation_admitted", tenant_id=tenant_id, project_id=project_id, aggregate_type="budget_reservation", aggregate_id=identifier, payload={"budget_id": policy.budget_id, "estimate_id": estimate_id, "amount": estimate.total_amount, "currency": estimate.currency, "expires_at": row.expires_at.isoformat(), "override_id": override.override_id if override else None}, actor_id=requested_by)
                        result = self._reservation_result(row, idempotent_replay=False)
                if denial is not None:
                    session.rollback()
                else:
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except IntegrityError:
            with self.database.session() as replay_session:
                existing = replay_session.scalar(select(BudgetReservationRow).where(BudgetReservationRow.tenant_id == tenant_id, BudgetReservationRow.project_id == project_id, BudgetReservationRow.idempotency_key == idempotency_key))
                if existing is None or existing.estimate_id != estimate_id:
                    raise ConflictError("BUDGET_RESERVATION_CONCURRENT_CONFLICT", "concurrent reservation completed with inconsistent state")
                return self._reservation_result(existing, idempotent_replay=True)
        if denial is not None:
            code, message, details = denial
            self._record_admission_denial(tenant_id=tenant_id, project_id=project_id, actor_id=requested_by, estimate_id=estimate_id, code=code, details=details)
            raise ConflictError(code, message, details)
        if result is None:
            raise ConflictError("BUDGET_ADMISSION_INCOMPLETE", "budget admission did not produce a governed result")
        return result

    def _record_admission_denial(self, *, tenant_id: str, project_id: str, actor_id: str, estimate_id: str, code: str, details: dict[str, Any]) -> None:
        with self.database.session() as session:
            denial_id = new_uuid()
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="budget:reserve", resource_type="budget_admission_denial", resource_id=denial_id, outcome="denied", details={"estimate_id": estimate_id, "reason_code": code, **details}, session=session)
            self._emit(session, event_type="budget.admission_denied", tenant_id=tenant_id, project_id=project_id, aggregate_type="cost_estimate", aggregate_id=estimate_id, payload={"denial_id": denial_id, "estimate_id": estimate_id, "reason_code": code}, actor_id=actor_id)

    @staticmethod
    def _reservation_result(row: BudgetReservationRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"reservation_id": row.reservation_id, "budget_id": row.budget_id, "estimate_id": row.estimate_id, "operation_id": row.operation_id, "amount": row.amount, "currency": row.currency, "state": row.state, "expires_at": row.expires_at.isoformat(), "released_at": row.released_at.isoformat() if row.released_at else None, "release_reason": row.release_reason, "idempotent_replay": idempotent_replay}

    def release_budget_reservation(self, *, tenant_id: str, project_id: str, reservation_id: str, reason: str, actor_id: str) -> dict[str, Any]:
        reason = _bounded_string(reason, code="BUDGET_RELEASE_REASON_INVALID", field="reason", limit=256)
        with self.database.session() as session:
            row = session.get(BudgetReservationRow, reservation_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("budget_reservation", reservation_id)
            if row.state in {"released", "expired"}:
                return self._reservation_result(row, idempotent_replay=True)
            row.state = "released"
            row.released_at = db_now()
            row.release_reason = reason
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="budget:release", resource_type="budget_reservation", resource_id=reservation_id, outcome="allowed", details={"reason": reason, "released_at": row.released_at.isoformat()}, session=session)
            self._emit(session, event_type="budget.reservation_released", tenant_id=tenant_id, project_id=project_id, aggregate_type="budget_reservation", aggregate_id=reservation_id, payload={"reason": reason, "released_at": row.released_at.isoformat()}, actor_id=actor_id)
            return self._reservation_result(row, idempotent_replay=False)

    # ---------------------------------------------------------- anomaly/queues
    def _create_anomaly_in_session(
        self,
        session: Session,
        *,
        tenant_id: str,
        project_id: str,
        category: str,
        severity: str,
        metric_name: str,
        observed_value: float,
        baseline_value: float,
        threshold: float,
        evidence: dict[str, Any],
        actor_id: str,
    ) -> AnomalyAlertRow:
        body = {"tenant_id": tenant_id, "project_id": project_id, "category": category, "severity": severity, "metric_name": metric_name, "observed_value": observed_value, "baseline_value": baseline_value, "threshold": threshold, "evidence": evidence}
        digest = canonical_sha256(body)
        existing = session.scalar(select(AnomalyAlertRow).where(AnomalyAlertRow.alert_hash == digest))
        if existing is not None:
            return existing
        row = AnomalyAlertRow(alert_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, category=category, severity=severity, metric_name=metric_name, observed_value=observed_value, baseline_value=baseline_value, threshold=threshold, state="open", evidence_json=evidence, alert_hash=digest, created_by=actor_id)
        session.add(row)
        self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="anomaly:detect", resource_type="anomaly_alert", resource_id=row.alert_id, outcome="allowed", details={"category": category, "severity": severity, "metric_name": metric_name, "alert_hash": digest}, session=session)
        self._emit(session, event_type="anomaly.detected", tenant_id=tenant_id, project_id=project_id, aggregate_type="anomaly_alert", aggregate_id=row.alert_id, payload={"category": category, "severity": severity, "metric_name": metric_name, "alert_hash": digest}, actor_id=actor_id)
        return row

    def record_anomaly(self, *, tenant_id: str, project_id: str, category: str, severity: str, metric_name: str, observed_value: float, baseline_value: float, threshold: float, evidence: dict[str, Any], actor_id: str) -> dict[str, Any]:
        if severity not in {"info", "warning", "high", "critical"} or not all(math.isfinite(float(v)) for v in (observed_value, baseline_value, threshold)):
            raise ValidationError("ANOMALY_VALUES_INVALID", "anomaly severity or values are invalid")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            row = self._create_anomaly_in_session(session, tenant_id=tenant_id, project_id=project_id, category=category, severity=severity, metric_name=metric_name, observed_value=observed_value, baseline_value=baseline_value, threshold=threshold, evidence=evidence, actor_id=actor_id)
            return self._anomaly_result(row)

    @staticmethod
    def _anomaly_result(row: AnomalyAlertRow) -> dict[str, Any]:
        return {"alert_id": row.alert_id, "category": row.category, "severity": row.severity, "metric_name": row.metric_name, "observed_value": row.observed_value, "baseline_value": row.baseline_value, "threshold": row.threshold, "state": row.state, "evidence": row.evidence_json, "alert_hash": row.alert_hash, "suppressed_until": row.suppressed_until.isoformat() if row.suppressed_until else None, "suppression_approved_by": row.suppression_approved_by, "acknowledged_by": row.acknowledged_by, "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None}

    def acknowledge_anomaly(self, *, tenant_id: str, project_id: str, alert_id: str, actor_id: str, suppress_until: datetime | None = None) -> dict[str, Any]:
        now = db_now()
        with self.database.session() as session:
            row = session.get(AnomalyAlertRow, alert_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("anomaly_alert", alert_id)
            if suppress_until is not None:
                until = _aware(suppress_until)
                if row.created_by == actor_id:
                    raise AuthorizationError("ALERT_SUPPRESSION_SELF_APPROVAL_DENIED", "the alert creator cannot approve its suppression")
                if until <= now or until > now + timedelta(days=7):
                    raise ValidationError("ALERT_SUPPRESSION_EXPIRY_INVALID", "alert suppression expiry is invalid")
                row.suppressed_until = until
                row.suppression_approved_by = actor_id
                row.state = "suppressed"
            else:
                row.state = "acknowledged"
            row.acknowledged_at = now
            row.acknowledged_by = actor_id
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="anomaly:acknowledge", resource_type="anomaly_alert", resource_id=alert_id, outcome="allowed", details={"state": row.state, "suppressed_until": row.suppressed_until.isoformat() if row.suppressed_until else None, "suppression_approved_by": row.suppression_approved_by}, session=session)
            self._emit(session, event_type="anomaly.acknowledged", tenant_id=tenant_id, project_id=project_id, aggregate_type="anomaly_alert", aggregate_id=alert_id, payload={"state": row.state, "suppressed_until": row.suppressed_until.isoformat() if row.suppressed_until else None}, actor_id=actor_id)
            return self._anomaly_result(row)

    def record_queue_snapshot(self, *, tenant_id: str | None, project_id: str | None, queue_class: str, depth: int, in_flight: int, retries: int, oldest_age_seconds: float, capacity: int, actor_id: str) -> dict[str, Any]:
        if min(depth, in_flight, retries, capacity) < 0 or oldest_age_seconds < 0 or capacity < in_flight:
            raise ValidationError("QUEUE_SNAPSHOT_INVALID", "queue snapshot contains invalid values")
        queue_class = _require_identifier(queue_class, code="QUEUE_CLASS_INVALID", field="queue_class")
        body = {"tenant_id": tenant_id, "project_id": project_id, "queue_class": queue_class, "depth": depth, "in_flight": in_flight, "retries": retries, "oldest_age_seconds": oldest_age_seconds, "capacity": capacity}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if tenant_id and project_id:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(QueueSnapshotRow).where(QueueSnapshotRow.snapshot_hash == digest))
            if existing is not None:
                return self._queue_result(existing, idempotent_replay=True)
            row = QueueSnapshotRow(snapshot_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, queue_class=queue_class, depth=depth, in_flight=in_flight, retries=retries, oldest_age_seconds=oldest_age_seconds, capacity=capacity, snapshot_hash=digest)
            session.add(row)
            self._emit(session, event_type="queue.snapshot_recorded", tenant_id=tenant_id or "platform", project_id=project_id, aggregate_type="queue_snapshot", aggregate_id=row.snapshot_id, payload={"queue_class": queue_class, "depth": depth, "in_flight": in_flight, "retries": retries, "capacity": capacity, "snapshot_hash": digest}, actor_id=actor_id)
            return self._queue_result(row, idempotent_replay=False)

    @staticmethod
    def _queue_result(row: QueueSnapshotRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"snapshot_id": row.snapshot_id, "queue_class": row.queue_class, "depth": row.depth, "in_flight": row.in_flight, "retries": row.retries, "oldest_age_seconds": row.oldest_age_seconds, "capacity": row.capacity, "sampled_at": row.sampled_at.isoformat(), "snapshot_hash": row.snapshot_hash, "idempotent_replay": idempotent_replay}

    def queue_dashboard(self, *, tenant_id: str, project_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            rows = list(session.scalars(select(QueueSnapshotRow).where(QueueSnapshotRow.tenant_id == tenant_id, QueueSnapshotRow.project_id == project_id).order_by(QueueSnapshotRow.sampled_at.desc()).limit(500)))
            latest: dict[str, QueueSnapshotRow] = {}
            for row in rows:
                latest.setdefault(row.queue_class, row)
        return {"queues": [self._queue_result(latest[key], idempotent_replay=False) for key in sorted(latest)], "raw_data_included": False}

    # --------------------------------------------------------------- support
    def request_support_access(
        self,
        *,
        tenant_id: str,
        project_id: str,
        resource_scope: dict[str, Any],
        purpose: str,
        personnel: list[str],
        requested_by: str,
        duration_seconds: int,
    ) -> dict[str, Any]:
        normalized_personnel = sorted({_require_identifier(item, code="SUPPORT_PERSONNEL_INVALID", field="personnel") for item in personnel})
        if not normalized_personnel:
            raise ValidationError("SUPPORT_PERSONNEL_REQUIRED", "support access requires at least one named person")
        if duration_seconds < 60 or duration_seconds > 28_800:
            raise ValidationError("SUPPORT_DURATION_INVALID", "support access must be between 60 seconds and 8 hours")
        purpose = _bounded_string(purpose, code="SUPPORT_PURPOSE_INVALID", field="purpose", limit=128)
        if purpose not in {"support", "diagnostic", "incident_response"}:
            raise ValidationError("SUPPORT_PURPOSE_UNSUPPORTED", "support access purpose is not approved")
        allowed_scope_keys = {"resource_ids", "operation_ids", "telemetry_types", "include_logs", "include_metrics", "include_traces", "classification", "audience"}
        if set(resource_scope) - allowed_scope_keys or not resource_scope:
            raise ValidationError("SUPPORT_SCOPE_INVALID", "support access scope contains unsupported or empty fields")
        for key in ("resource_ids", "operation_ids", "telemetry_types"):
            if key in resource_scope:
                values = resource_scope[key]
                if not isinstance(values, list) or len(values) > 100 or any(not isinstance(value, str) or not value or value == "*" for value in values):
                    raise ValidationError("SUPPORT_SCOPE_INVALID", "support scope lists must be bounded and cannot contain wildcards", {"field": key})
        if resource_scope.get("include_raw_media") or resource_scope.get("unrestricted_signed_urls"):
            raise AuthorizationError("SUPPORT_RAW_ACCESS_DENIED", "support access cannot authorize raw media or unrestricted signed URLs")
        high_risk = str(resource_scope.get("classification", "")).lower() in {"restricted", "critical_infrastructure", "biometric"}
        if high_risk and not all(item.startswith("specialized-") or item == "specialized-support" for item in normalized_personnel):
            raise AuthorizationError("SUPPORT_SPECIALIZED_PERSONNEL_REQUIRED", "high-risk support scopes require explicitly named specialized personnel")
        expires_at = db_now() + timedelta(seconds=duration_seconds)
        request_body = {"tenant_id": tenant_id, "project_id": project_id, "resource_scope": resource_scope, "purpose": purpose, "personnel": normalized_personnel, "requested_by": requested_by, "expires_at": expires_at.isoformat()}
        request_hash = canonical_sha256(request_body)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(SupportAccessGrantRow).where(SupportAccessGrantRow.approval_hash == request_hash))
            if existing is not None:
                return self._support_grant_result(existing, idempotent_replay=True)
            row = SupportAccessGrantRow(
                grant_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                resource_scope_json=resource_scope, purpose=purpose, personnel_json=normalized_personnel,
                requested_by=requested_by, approved_by=None, approval_hash=request_hash,
                state="pending", expires_at=expires_at,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=requested_by, action="support_access:request", resource_type="support_access_grant", resource_id=row.grant_id, outcome="allowed", details={"purpose": purpose, "expires_at": expires_at.isoformat(), "request_hash": request_hash, "scope_hash": canonical_sha256(resource_scope)}, session=session)
            self._emit(session, event_type="support.access_requested", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_access_grant", aggregate_id=row.grant_id, payload={"purpose": purpose, "expires_at": expires_at.isoformat(), "request_hash": request_hash, "scope_hash": canonical_sha256(resource_scope)}, actor_id=requested_by)
            return self._support_grant_result(row, idempotent_replay=False)

    def approve_support_access(self, *, tenant_id: str, project_id: str, grant_id: str, approved_by: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(SupportAccessGrantRow, grant_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("support_access_grant", grant_id)
            if row.state == "active":
                if row.approved_by != approved_by:
                    raise ConflictError("SUPPORT_APPROVAL_ACTOR_CONFLICT", "support grant was approved by another actor")
                return self._support_grant_result(row, idempotent_replay=True)
            if row.state != "pending" or _aware(row.expires_at) <= db_now():
                raise AuthorizationError("SUPPORT_ACCESS_INACTIVE", "support request is expired, revoked, or no longer pending")
            if approved_by == row.requested_by or approved_by in row.personnel_json:
                raise AuthorizationError("SUPPORT_ACCESS_INDEPENDENT_APPROVAL_REQUIRED", "support access requires customer approval independent of requester and support personnel")
            approval_body = {
                "tenant_id": tenant_id, "project_id": project_id, "grant_id": row.grant_id,
                "resource_scope": row.resource_scope_json, "purpose": row.purpose,
                "personnel": row.personnel_json, "requested_by": row.requested_by,
                "approved_by": approved_by, "expires_at": _aware(row.expires_at).isoformat(),
            }
            row.approved_by = approved_by
            row.approval_hash = canonical_sha256(approval_body)
            row.state = "active"
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=approved_by, action="support_access:approve", resource_type="support_access_grant", resource_id=grant_id, outcome="allowed", details={"approval_hash": row.approval_hash, "expires_at": row.expires_at.isoformat()}, session=session)
            self._emit(session, event_type="support.access_granted", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_access_grant", aggregate_id=grant_id, payload={"approval_hash": row.approval_hash, "expires_at": row.expires_at.isoformat(), "personnel_count": len(row.personnel_json)}, actor_id=approved_by)
            return self._support_grant_result(row, idempotent_replay=False)

    def grant_support_access(
        self,
        *,
        tenant_id: str,
        project_id: str,
        resource_scope: dict[str, Any],
        purpose: str,
        personnel: list[str],
        requested_by: str,
        approved_by: str,
        duration_seconds: int,
    ) -> dict[str, Any]:
        request = self.request_support_access(
            tenant_id=tenant_id, project_id=project_id, resource_scope=resource_scope,
            purpose=purpose, personnel=personnel, requested_by=requested_by,
            duration_seconds=duration_seconds,
        )
        return self.approve_support_access(
            tenant_id=tenant_id, project_id=project_id,
            grant_id=request["grant_id"], approved_by=approved_by,
        )

    @staticmethod
    def _support_grant_result(row: SupportAccessGrantRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"grant_id": row.grant_id, "purpose": row.purpose, "personnel": row.personnel_json, "resource_scope": row.resource_scope_json, "requested_by": row.requested_by, "approved_by": row.approved_by, "state": row.state, "expires_at": row.expires_at.isoformat(), "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None, "approval_hash": row.approval_hash, "idempotent_replay": idempotent_replay}

    def revoke_support_access(self, *, tenant_id: str, project_id: str, grant_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(SupportAccessGrantRow, grant_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("support_access_grant", grant_id)
            if row.state == "revoked":
                return self._support_grant_result(row, idempotent_replay=True)
            row.state = "revoked"
            row.revoked_at = db_now()
            row.revoked_by = actor_id
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="support_access:revoke", resource_type="support_access_grant", resource_id=grant_id, outcome="allowed", details={"revoked_at": row.revoked_at.isoformat()}, session=session)
            self._emit(session, event_type="support.access_revoked", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_access_grant", aggregate_id=grant_id, payload={"revoked_at": row.revoked_at.isoformat()}, actor_id=actor_id)
            return self._support_grant_result(row, idempotent_replay=False)

    @staticmethod
    def _require_active_support_grant(row: SupportAccessGrantRow, *, actor_id: str, tenant_id: str, project_id: str) -> None:
        if row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("support_access_grant", row.grant_id)
        if row.state != "active" or _aware(row.expires_at) <= db_now() or row.revoked_at is not None:
            raise AuthorizationError("SUPPORT_ACCESS_INACTIVE", "support access is expired or revoked")
        if actor_id not in row.personnel_json:
            raise AuthorizationError("SUPPORT_PERSONNEL_DENIED", "actor is not named in the customer-approved support grant")

    def create_support_bundle(
        self,
        *,
        tenant_id: str,
        project_id: str,
        grant_id: str,
        telemetry_ids: list[str] | None,
        hardware_profile: dict[str, Any],
        manifest_references: list[dict[str, Any]],
        actor_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            grant = session.get(SupportAccessGrantRow, grant_id)
            if grant is None:
                raise NotFoundError("support_access_grant", grant_id)
            self._require_active_support_grant(grant, actor_id=actor_id, tenant_id=tenant_id, project_id=project_id)
            statement = select(TelemetryRecordRow).where(TelemetryRecordRow.tenant_id == tenant_id, TelemetryRecordRow.project_id == project_id)
            approved_resource_ids = set(grant.resource_scope_json.get("resource_ids", []))
            if telemetry_ids:
                if len(telemetry_ids) > 500:
                    raise ValidationError("SUPPORT_TELEMETRY_SELECTION_TOO_LARGE", "support telemetry selection is too large")
                requested_ids = set(telemetry_ids)
                if approved_resource_ids and not requested_ids <= approved_resource_ids:
                    raise AuthorizationError("SUPPORT_RESOURCE_SCOPE_DENIED", "requested telemetry is outside the customer-approved resource scope")
                statement = statement.where(TelemetryRecordRow.telemetry_id.in_(telemetry_ids))
            elif approved_resource_ids:
                statement = statement.where(TelemetryRecordRow.telemetry_id.in_(sorted(approved_resource_ids)))
            else:
                statement = statement.order_by(TelemetryRecordRow.created_at.desc()).limit(200)
            records = list(session.scalars(statement))
            if telemetry_ids and len(records) != len(set(telemetry_ids)):
                raise NotFoundError("telemetry_record", "one_or_more")
            scope_types = set(grant.resource_scope_json.get("telemetry_types", []))
            if scope_types:
                records = [row for row in records if row.telemetry_type in scope_types]
            operation_scope = set(grant.resource_scope_json.get("operation_ids", []))
            if operation_scope:
                records = [row for row in records if row.operation_id in operation_scope]
            selected_ids = sorted(row.telemetry_id for row in records)
            if approved_resource_ids and not set(selected_ids) <= approved_resource_ids:
                raise AuthorizationError("SUPPORT_RESOURCE_SCOPE_DENIED", "support selection escaped the approved resource scope")
            if len(manifest_references) > 100:
                raise ValidationError("SUPPORT_MANIFEST_REFERENCE_LIMIT", "support manifest reference selection is too large")
            normalized_references: list[dict[str, str]] = []
            for reference in manifest_references:
                if not isinstance(reference, dict) or set(reference) != {"kind", "sha256"}:
                    raise ValidationError("SUPPORT_MANIFEST_REFERENCE_INVALID", "manifest references require only kind and sha256")
                normalized_references.append({
                    "kind": _require_identifier(str(reference["kind"]), code="SUPPORT_MANIFEST_KIND_INVALID", field="manifest_kind"),
                    "sha256": _require_sha256(str(reference["sha256"]), code="SUPPORT_MANIFEST_HASH_INVALID", field="manifest_hash"),
                })
            normalized_references.sort(key=lambda item: (item["kind"], item["sha256"]))
            normalized_hardware_profile = _normalize_support_hardware_profile(
                hardware_profile, tenant_id=tenant_id, project_id=project_id
            )
            scope_hash = canonical_sha256({"grant_id": grant_id, "telemetry_ids": selected_ids, "hardware_profile": normalized_hardware_profile, "manifest_references": normalized_references, "release": self.release})
            existing = session.scalar(select(SupportBundleRow).where(SupportBundleRow.tenant_id == tenant_id, SupportBundleRow.project_id == project_id, SupportBundleRow.scope_hash == scope_hash))
            if existing is not None:
                verification = self._verify_support_bundle_row(existing)
                if not verification["valid"]:
                    raise ConflictError("SUPPORT_BUNDLE_REPLAY_CHANGED", "existing support bundle no longer verifies", {"findings": verification["findings"]})
                return self._support_bundle_result(existing, verification=verification, idempotent_replay=True)
            telemetry_payloads = [self._telemetry_result(row) for row in sorted(records, key=lambda item: (item.created_at, item.telemetry_id))]
            logs = [record for record in telemetry_payloads if record["telemetry_type"] == "log"] if grant.resource_scope_json.get("include_logs", True) else []
            metrics = [record for record in telemetry_payloads if record["telemetry_type"] in {"metric", "quality", "queue"}] if grant.resource_scope_json.get("include_metrics", True) else []
            traces = [record for record in telemetry_payloads if record["telemetry_type"] == "trace"] if grant.resource_scope_json.get("include_traces", False) else []
            errors = [record for record in telemetry_payloads if record["stable_error_code"]]
            bundle_manifest = {
                "schema": "sip.support-bundle/v1",
                "tenant_context": pseudonymize_identifier(tenant_id, namespace="tenant"),
                "project_context": pseudonymize_identifier(project_id, namespace="project"),
                "grant_id": grant_id,
                "purpose": grant.purpose,
                "scope_hash": scope_hash,
                "personnel": [pseudonymize_identifier(item, namespace="support-personnel") for item in grant.personnel_json],
                "created_by": pseudonymize_identifier(actor_id, namespace="support-personnel"),
                "raw_media_included": False,
                "unrestricted_signed_urls_included": False,
                "telemetry_record_count": len(telemetry_payloads),
                "release": self.release,
            }
            files = {
                "support-bundle.json": canonical_json(bundle_manifest),
                "versions.json": canonical_json({"platform_release": self.release, "environment": self.environment, "services": sorted({row.service for row in records})}),
                "manifests.json": canonical_json({"references": normalized_references, "support_grant_hash": grant.approval_hash}),
                "metrics.json": canonical_json({"records": metrics, "trace_summaries": traces}),
                "errors.json": canonical_json({"records": errors}),
                "logs.ndjson": b"".join(canonical_json(record) + b"\n" for record in logs),
                "hardware-profile.json": canonical_json(normalized_hardware_profile),
            }
            checksums = {name: sha256_bytes(data) for name, data in sorted(files.items())}
            root_hash = merkle_root(checksums.items())
            checksums_body = canonical_json({"algorithm": "sha256", "files": checksums, "root_hash": root_hash})
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                for name, data in sorted(files.items()):
                    _zip_write(archive, name, data)
                _zip_write(archive, "checksums.json", checksums_body)
            data = buffer.getvalue()
            zip_hash = sha256_bytes(data)
            identifier = new_uuid()
            target_dir = self.bundle_root / tenant_id / project_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{identifier}.zip"
            with tempfile.NamedTemporaryFile(dir=target_dir, delete=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, target)
            row = SupportBundleRow(bundle_id=identifier, grant_id=grant_id, tenant_id=tenant_id, project_id=project_id, bundle_path=str(target), zip_hash=zip_hash, root_hash=root_hash, scope_hash=scope_hash, manifest_json={**bundle_manifest, "checksums": checksums}, state="verified", created_by=actor_id, verified_at=db_now())
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="support_bundle:create", resource_type="support_bundle", resource_id=identifier, outcome="allowed", details={"grant_id": grant_id, "scope_hash": scope_hash, "zip_hash": zip_hash, "root_hash": root_hash, "raw_media_included": False}, session=session)
            self._emit(session, event_type="support.bundle_created", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_bundle", aggregate_id=identifier, payload={"grant_id": grant_id, "scope_hash": scope_hash, "zip_hash": zip_hash, "root_hash": root_hash, "raw_media_included": False}, actor_id=actor_id)
            verification = self._verify_support_bundle_row(row)
            if not verification["valid"]:
                raise ValidationError("SUPPORT_BUNDLE_SELF_VERIFICATION_FAILED", "created support bundle did not pass independent verification", {"findings": verification["findings"]})
            return self._support_bundle_result(row, verification=verification, idempotent_replay=False)

    @staticmethod
    def verify_support_bundle_bytes(data: bytes) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = validate_zip_members(archive.infolist(), code_prefix="SUPPORT_BUNDLE", max_members=64, max_member_bytes=16 * 1024 * 1024, max_total_bytes=64 * 1024 * 1024, max_compression_ratio=50)
                verification = verify_checksum_manifest(archive, names, allowed_members=_ALLOWED_SUPPORT_MEMBERS, required_members=_REQUIRED_SUPPORT_MEMBERS, code_prefix="SUPPORT_BUNDLE")
                if verification["valid"]:
                    manifest = json.loads(archive.read("support-bundle.json"))
                    if manifest.get("schema") != "sip.support-bundle/v1" or manifest.get("raw_media_included") is not False or manifest.get("unrestricted_signed_urls_included") is not False:
                        verification["findings"].append({"path": "support-bundle.json", "reason": "support_manifest_policy_invalid"})
                        verification["valid"] = False
                verification["zip_sha256"] = sha256_bytes(data)
                return verification
        except zipfile.BadZipFile:
            return {"valid": False, "findings": [{"path": "archive", "reason": "not_a_zip"}], "root_hash": "", "zip_sha256": sha256_bytes(data)}

    def _verify_support_bundle_row(self, row: SupportBundleRow) -> dict[str, Any]:
        path = Path(row.bundle_path)
        if not path.is_file():
            return {"valid": False, "findings": [{"path": str(path), "reason": "bundle_missing"}], "root_hash": "", "zip_sha256": ""}
        data = path.read_bytes()
        result = self.verify_support_bundle_bytes(data)
        if result.get("zip_sha256") != row.zip_hash:
            result["findings"].append({"path": "archive", "reason": "zip_hash_changed"})
            result["valid"] = False
        if result.get("root_hash") != row.root_hash:
            result["findings"].append({"path": "checksums.json", "reason": "retained_root_changed"})
            result["valid"] = False
        return result

    def verify_support_bundle(self, *, tenant_id: str, project_id: str, bundle_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(SupportBundleRow, bundle_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("support_bundle", bundle_id)
            grant = session.get(SupportAccessGrantRow, row.grant_id)
            if grant is None:
                raise NotFoundError("support_access_grant", row.grant_id)
            self._require_active_support_grant(grant, actor_id=actor_id, tenant_id=tenant_id, project_id=project_id)
            verification = self._verify_support_bundle_row(row)
            if verification["valid"]:
                row.verified_at = db_now()
                row.state = "verified"
            else:
                row.state = "invalid"
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="support_bundle:verify", resource_type="support_bundle", resource_id=bundle_id, outcome="allowed" if verification["valid"] else "denied", details={"valid": verification["valid"], "finding_count": len(verification["findings"]), "zip_hash": verification.get("zip_sha256"), "root_hash": verification.get("root_hash")}, session=session)
            return self._support_bundle_result(row, verification=verification, idempotent_replay=False)

    @staticmethod
    def _support_bundle_result(row: SupportBundleRow, *, verification: dict[str, Any], idempotent_replay: bool) -> dict[str, Any]:
        return {"bundle_id": row.bundle_id, "grant_id": row.grant_id, "zip_hash": row.zip_hash, "root_hash": row.root_hash, "scope_hash": row.scope_hash, "state": row.state, "manifest": row.manifest_json, "verification": verification, "created_at": row.created_at.isoformat(), "verified_at": row.verified_at.isoformat() if row.verified_at else None, "idempotent_replay": idempotent_replay}

    def create_support_ticket(self, *, tenant_id: str, project_id: str, risk_class: str, issue_type: str, summary: str, stable_error_codes: list[str], actor_id: str) -> dict[str, Any]:
        risk_class = _require_identifier(risk_class, code="SUPPORT_RISK_CLASS_INVALID", field="risk_class")
        issue_type = _require_identifier(issue_type, code="SUPPORT_ISSUE_TYPE_INVALID", field="issue_type")
        summary = _bounded_string(summary, code="SUPPORT_SUMMARY_INVALID", field="summary", limit=512)
        safe_summary = str(redact(summary))
        routed_role = "specialized_support" if risk_class in _HIGH_RISK_SUPPORT or issue_type in _HIGH_RISK_SUPPORT else "support_engineer"
        codes = sorted({_require_identifier(code, code="SUPPORT_ERROR_CODE_INVALID", field="stable_error_code") for code in stable_error_codes})
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            identifier = new_uuid()
            row = SupportTicketRow(ticket_id=identifier, tenant_id=tenant_id, project_id=project_id, risk_class=risk_class, issue_type=issue_type, summary=safe_summary, affected_release=None, remediation_reference=None, retention_json={"stable_error_codes": codes, "raw_customer_data_retained": False}, routed_role=routed_role, state="open", created_by=actor_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="support_ticket:create", resource_type="support_ticket", resource_id=identifier, outcome="allowed", details={"risk_class": risk_class, "issue_type": issue_type, "routed_role": routed_role, "stable_error_codes": codes}, session=session)
            self._emit(session, event_type="support.ticket_created", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_ticket", aggregate_id=identifier, payload={"risk_class": risk_class, "issue_type": issue_type, "routed_role": routed_role, "stable_error_code_count": len(codes)}, actor_id=actor_id)
            return self._support_ticket_result(row)

    def resolve_support_ticket(self, *, tenant_id: str, project_id: str, ticket_id: str, remediation_reference: str, affected_release: str, actor_id: str) -> dict[str, Any]:
        remediation_reference = _bounded_string(remediation_reference, code="SUPPORT_REMEDIATION_REFERENCE_INVALID", field="remediation_reference", limit=512)
        affected_release = _require_identifier(affected_release, code="SUPPORT_RELEASE_INVALID", field="affected_release")
        with self.database.session() as session:
            row = session.get(SupportTicketRow, ticket_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("support_ticket", ticket_id)
            if row.state == "resolved":
                if row.remediation_reference != remediation_reference or row.affected_release != affected_release:
                    raise ConflictError("SUPPORT_TICKET_RESOLUTION_CONFLICT", "resolved ticket cannot be rebound to different remediation")
                return self._support_ticket_result(row, idempotent_replay=True)
            row.state = "resolved"
            row.remediation_reference = remediation_reference
            row.affected_release = affected_release
            row.retention_json = {"stable_error_codes": row.retention_json.get("stable_error_codes", []), "raw_customer_data_retained": False}
            row.resolved_by = actor_id
            row.resolved_at = db_now()
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="support_ticket:resolve", resource_type="support_ticket", resource_id=ticket_id, outcome="allowed", details={"remediation_reference": remediation_reference, "affected_release": affected_release, "raw_customer_data_retained": False}, session=session)
            self._emit(session, event_type="support.ticket_resolved", tenant_id=tenant_id, project_id=project_id, aggregate_type="support_ticket", aggregate_id=ticket_id, payload={"remediation_reference": remediation_reference, "affected_release": affected_release, "raw_customer_data_retained": False}, actor_id=actor_id)
            return self._support_ticket_result(row)

    @staticmethod
    def _support_ticket_result(row: SupportTicketRow, *, idempotent_replay: bool = False) -> dict[str, Any]:
        return {"ticket_id": row.ticket_id, "risk_class": row.risk_class, "issue_type": row.issue_type, "summary": row.summary, "routed_role": row.routed_role, "state": row.state, "affected_release": row.affected_release, "remediation_reference": row.remediation_reference, "retention": row.retention_json, "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None, "idempotent_replay": idempotent_replay}


    # ------------------------------------------------------------- resilience
    def register_resilience_profile(
        self,
        *,
        component: str,
        version: str,
        owner: str,
        blast_radius: str,
        retry_safety: str,
        recovery_point_seconds: int,
        recovery_time_seconds: int,
        degraded_behavior: dict[str, Any],
        dependencies: list[dict[str, Any]],
        actor_id: str,
    ) -> dict[str, Any]:
        component = _require_identifier(component, code="RESILIENCE_COMPONENT_INVALID", field="component")
        version = _require_identifier(version, code="RESILIENCE_VERSION_INVALID", field="version", pattern=_VERSION)
        owner = _require_identifier(owner, code="RESILIENCE_OWNER_INVALID", field="owner")
        if blast_radius not in {"job", "worker", "queue", "project", "tenant", "control_plane"}:
            raise ValidationError("RESILIENCE_BLAST_RADIUS_INVALID", "unsupported blast-radius classification")
        if retry_safety not in {"idempotent", "checkpointed", "manual_recovery", "non_retryable"}:
            raise ValidationError("RESILIENCE_RETRY_SAFETY_INVALID", "unsupported retry-safety classification")
        if recovery_point_seconds < 0 or recovery_time_seconds <= 0:
            raise ValidationError("RESILIENCE_RECOVERY_BUDGET_INVALID", "recovery budgets must be bounded")
        required = {"mode", "user_message", "authorization_behavior", "data_integrity_behavior"}
        if not required <= set(degraded_behavior):
            raise ValidationError("RESILIENCE_DEGRADED_BEHAVIOR_INCOMPLETE", "degraded behavior is missing required controls")
        for dependency in dependencies:
            if not isinstance(dependency, dict) or not dependency.get("component") or dependency.get("failure_behavior") not in {"fail_closed", "bounded_fallback", "retry", "manual"}:
                raise ValidationError("RESILIENCE_DEPENDENCY_INVALID", "each dependency requires a component and governed failure behavior")
        body = {
            "component": component,
            "version": version,
            "owner": owner,
            "blast_radius": blast_radius,
            "retry_safety": retry_safety,
            "recovery_point_seconds": recovery_point_seconds,
            "recovery_time_seconds": recovery_time_seconds,
            "degraded_behavior": degraded_behavior,
            "dependencies": dependencies,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(ResilienceProfileRow).where(ResilienceProfileRow.profile_hash == digest))
            if existing is not None:
                return self._resilience_result(existing, idempotent_replay=True)
            conflict = session.scalar(select(ResilienceProfileRow).where(ResilienceProfileRow.component == component, ResilienceProfileRow.version == version))
            if conflict is not None:
                raise ConflictError("RESILIENCE_PROFILE_IMMUTABLE", "component/version is already bound to different resilience controls")
            row = ResilienceProfileRow(
                profile_id=new_uuid(), component=component, version=version, owner=owner,
                blast_radius=blast_radius, retry_safety=retry_safety,
                recovery_point_seconds=recovery_point_seconds, recovery_time_seconds=recovery_time_seconds,
                degraded_behavior_json=degraded_behavior, dependencies_json=dependencies,
                profile_hash=digest, created_by=actor_id,
            )
            session.add(row)
            self.audit.append(tenant_id="platform", project_id=None, actor_id=actor_id, action="resilience_profile:create", resource_type="resilience_profile", resource_id=row.profile_id, outcome="allowed", details={"component": component, "version": version, "profile_hash": digest}, session=session)
            self._emit(session, event_type="resilience.profile_registered", tenant_id="platform", project_id=None, aggregate_type="resilience_profile", aggregate_id=row.profile_id, payload={"component": component, "version": version, "profile_hash": digest}, actor_id=actor_id)
            return self._resilience_result(row, idempotent_replay=False)

    @staticmethod
    def _resilience_result(row: ResilienceProfileRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "profile_id": row.profile_id,
            "component": row.component,
            "version": row.version,
            "owner": row.owner,
            "blast_radius": row.blast_radius,
            "retry_safety": row.retry_safety,
            "recovery_point_seconds": row.recovery_point_seconds,
            "recovery_time_seconds": row.recovery_time_seconds,
            "degraded_behavior": row.degraded_behavior_json,
            "dependencies": row.dependencies_json,
            "profile_hash": row.profile_hash,
            "idempotent_replay": idempotent_replay,
        }

    def check_compute_compatibility(self, *, compute_profile_id: str, runtime: dict[str, Any]) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ComputeProfileRow, compute_profile_id)
            if row is None:
                raise NotFoundError("compute_profile", compute_profile_id)
        mismatches: list[dict[str, str]] = []
        expected = {"cuda_version": row.cuda_version, "container_digest": row.container_digest, "backend": row.backend, "dtype": row.dtype}
        for field, value in expected.items():
            if value is not None and runtime.get(field) != value:
                mismatches.append({"field": field, "expected": str(value), "actual": str(runtime.get(field))})
        driver = str(runtime.get("driver_version", ""))
        if row.driver_constraint and not _version_constraint_matches(driver, row.driver_constraint):
            mismatches.append({"field": "driver_version", "expected": row.driver_constraint, "actual": driver})
        tenant_context = runtime.get("tenant_context")
        isolated_modes = {"dedicated_process", "dedicated_container", "dedicated_node", "reference_local"}
        if row.tenant_isolation in isolated_modes:
            if not isinstance(tenant_context, str) or not tenant_context.strip():
                mismatches.append({"field": "tenant_context", "expected": "nonempty isolated tenant context", "actual": str(tenant_context)})
            batch_tenants = runtime.get("batch_tenant_contexts", [])
            if batch_tenants not in (None, []):
                if not isinstance(batch_tenants, list) or set(map(str, batch_tenants)) != {str(tenant_context)}:
                    mismatches.append({"field": "batch_tenant_contexts", "expected": "one tenant security context", "actual": str(batch_tenants)})
        if runtime.get("job_isolation") not in {"process", "container", "node", "reference_local"}:
            mismatches.append({"field": "job_isolation", "expected": "process/container/node/reference_local", "actual": str(runtime.get("job_isolation"))})
        return {
            "compatible": not mismatches,
            "compute_profile_id": compute_profile_id,
            "mismatches": mismatches,
            "execution_allowed": not mismatches,
            "evidence_class": "local_reference",
            "single_tenant_context_enforced": not any(item["field"] in {"tenant_context", "batch_tenant_contexts"} for item in mismatches),
        }

    def explicit_oom_disposition(
        self,
        *,
        compute_profile_id: str,
        checkpoint_id: str | None,
        tenant_id: str = "platform",
        actor_id: str = "system",
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ComputeProfileRow, compute_profile_id)
            if row is None:
                raise NotFoundError("compute_profile", compute_profile_id)
            fallback = dict(row.oom_fallback_json)
            mode = fallback.get("mode")
            if mode not in {"fail", "alternate_profile", "resume_checkpoint", "manual"}:
                raise ValidationError("OOM_FALLBACK_INVALID", "compute profile does not have a governed OOM fallback")
            if mode == "resume_checkpoint" and not checkpoint_id:
                raise ConflictError("OOM_CHECKPOINT_REQUIRED", "profile requires a verified checkpoint for OOM recovery")
            result = {"outcome": "oom", "silent_parameter_reduction": False, "fallback_mode": mode, "alternate_profile": fallback.get("alternate_profile"), "checkpoint_id": checkpoint_id, "operator_visible": True}
            self.audit.append(tenant_id=tenant_id, project_id=None, actor_id=actor_id, action="compute_profile:oom_disposition", resource_type="compute_profile", resource_id=compute_profile_id, outcome="allowed", details=result, session=session)
            self._emit(session, event_type="compute_profile.oom_recorded", tenant_id=tenant_id, project_id=None, aggregate_type="compute_profile", aggregate_id=compute_profile_id, payload=result, actor_id=actor_id)
            return result

    # ------------------------------------------------------- incident actions
    def record_incident_action(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        incident_reference: str,
        runbook_reference: str,
        action_type: str,
        command_reference: str | None,
        decision: dict[str, Any],
        evidence_references: list[dict[str, Any]],
        validation: dict[str, Any],
        rollback: dict[str, Any],
        communication: dict[str, Any],
        sensitive_copy_created: bool,
        occurred_at: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        incident_reference = _require_identifier(incident_reference, code="INCIDENT_REFERENCE_INVALID", field="incident_reference")
        runbook_reference = _bounded_string(runbook_reference, code="INCIDENT_RUNBOOK_INVALID", field="runbook_reference", limit=512)
        action_type = _require_identifier(action_type, code="INCIDENT_ACTION_TYPE_INVALID", field="action_type")
        if command_reference is not None:
            command_reference = _bounded_string(command_reference, code="INCIDENT_COMMAND_REFERENCE_INVALID", field="command_reference", limit=512)
        if sensitive_copy_created:
            raise AuthorizationError("INCIDENT_SENSITIVE_COPY_DENIED", "incident actions must reference evidence without making unnecessary sensitive copies")
        if not decision or not validation or not rollback or not communication:
            raise ValidationError("INCIDENT_ACTION_EVIDENCE_INCOMPLETE", "incident action requires decision, validation, rollback, and communication records")
        if len(evidence_references) > 50 or any(not isinstance(item, dict) or not item.get("kind") or not item.get("reference") for item in evidence_references):
            raise ValidationError("INCIDENT_EVIDENCE_REFERENCE_INVALID", "incident evidence references are incomplete or unbounded")
        occurred = _aware(occurred_at)
        if occurred > db_now() + timedelta(minutes=5):
            raise ValidationError("INCIDENT_ACTION_TIME_INVALID", "incident action time cannot be in the future")
        body = {
            "tenant_id": tenant_id, "project_id": project_id,
            "incident_reference": incident_reference, "runbook_reference": runbook_reference,
            "action_type": action_type, "command_reference": command_reference,
            "decision": decision, "evidence_references": evidence_references,
            "validation": validation, "rollback": rollback, "communication": communication,
            "sensitive_copy_created": False, "occurred_at": occurred.isoformat(), "actor_id": actor_id,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(IncidentActionRow).where(IncidentActionRow.action_hash == digest))
            if existing is not None:
                return self._incident_action_result(existing, idempotent_replay=True)
            row = IncidentActionRow(
                incident_action_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                incident_reference=incident_reference, runbook_reference=runbook_reference,
                action_type=action_type, command_reference=command_reference,
                decision_json=decision, evidence_references_json=evidence_references,
                validation_json=validation, rollback_json=rollback, communication_json=communication,
                sensitive_copy_created=False, action_hash=digest, actor_id=actor_id, occurred_at=occurred,
            )
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="incident_action:record", resource_type="incident_action", resource_id=row.incident_action_id, outcome="allowed", details={"incident_reference": incident_reference, "runbook_reference": runbook_reference, "action_type": action_type, "action_hash": digest, "evidence_reference_count": len(evidence_references), "sensitive_copy_created": False}, session=session)
            self._emit(session, event_type="incident.action_recorded", tenant_id=tenant_id, project_id=project_id, aggregate_type="incident_action", aggregate_id=row.incident_action_id, payload={"incident_reference": incident_reference, "runbook_reference": runbook_reference, "action_type": action_type, "action_hash": digest, "evidence_reference_count": len(evidence_references)}, actor_id=actor_id)
            return self._incident_action_result(row, idempotent_replay=False)

    @staticmethod
    def _incident_action_result(row: IncidentActionRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "incident_action_id": row.incident_action_id,
            "incident_reference": row.incident_reference,
            "runbook_reference": row.runbook_reference,
            "action_type": row.action_type,
            "command_reference": row.command_reference,
            "decision": row.decision_json,
            "evidence_references": row.evidence_references_json,
            "validation": row.validation_json,
            "rollback": row.rollback_json,
            "communication": row.communication_json,
            "sensitive_copy_created": row.sensitive_copy_created,
            "action_hash": row.action_hash,
            "actor_id": row.actor_id,
            "occurred_at": _aware(row.occurred_at).isoformat(),
            "idempotent_replay": idempotent_replay,
        }

    def verified_checkpoint_resume(self, *, tenant_id: str, project_id: str, operation_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            row = session.get(OperationRow, operation_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("operation", operation_id)
            checkpoint = row.checkpoint_json if isinstance(row.checkpoint_json, dict) else {}
            if not checkpoint or checkpoint.get("safe_to_resume") is not True:
                raise ConflictError("CHECKPOINT_NOT_RESUMABLE", "operation does not contain a verified resumable checkpoint")
            claimed = checkpoint.get("checkpoint_hash")
            manifest = checkpoint.get("manifest")
            if not isinstance(claimed, str) or _SHA256.fullmatch(claimed) is None or not isinstance(manifest, dict):
                raise ConflictError("CHECKPOINT_VERIFICATION_MISSING", "resumable checkpoint lacks a governed manifest and digest")
            calculated = canonical_sha256(manifest)
            if calculated != claimed:
                raise ConflictError("CHECKPOINT_HASH_MISMATCH", "resumable checkpoint manifest no longer matches its retained digest")
            if row.state not in {"pending", "failed", "quarantined", "running", "leased"}:
                raise ConflictError("CHECKPOINT_RESUME_STATE_INVALID", "operation state is not eligible for checkpoint resume", {"state": row.state})
            evidence = {"operation_id": operation_id, "checkpoint_hash": claimed, "sequence": checkpoint.get("sequence"), "stage": checkpoint.get("stage"), "state": row.state}
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="operation:resume_checkpoint", resource_type="operation", resource_id=operation_id, outcome="allowed", details=evidence, session=session)
            self._emit(session, event_type="operation.checkpoint_resume_authorized", tenant_id=tenant_id, project_id=project_id, aggregate_type="operation", aggregate_id=operation_id, payload=evidence, actor_id=actor_id)
            return {**evidence, "resume_authorized": True, "silent_parameter_reduction": False}

    # ------------------------------------------------------- exercises/reviews
    def record_game_day(
        self,
        *,
        tenant_id: str | None,
        project_id: str | None,
        scenario: str,
        runbook_reference: str,
        participants: list[str],
        observations: list[dict[str, Any]],
        corrective_requirements: list[dict[str, Any]],
        test_ids: list[str],
        started_at: datetime,
        completed_at: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        scenario = _bounded_string(scenario, code="GAME_DAY_SCENARIO_INVALID", field="scenario", limit=256)
        runbook_reference = _bounded_string(runbook_reference, code="GAME_DAY_RUNBOOK_INVALID", field="runbook_reference", limit=512)
        if _aware(completed_at) <= _aware(started_at) or not participants or not test_ids:
            raise ValidationError("GAME_DAY_INCOMPLETE", "game-day exercise requires participants, timing, runbook, and tests")
        if any(not item.get("requirement_id") or not item.get("owner") or not item.get("due_at") for item in corrective_requirements):
            raise ValidationError("GAME_DAY_CORRECTIVE_ACTION_INCOMPLETE", "corrective requirements require ID, owner, and due date")
        body = {"tenant_id": tenant_id, "project_id": project_id, "scenario": scenario, "runbook_reference": runbook_reference, "participants": sorted(participants), "observations": observations, "corrective_requirements": corrective_requirements, "test_ids": sorted(test_ids), "started_at": _aware(started_at).isoformat(), "completed_at": _aware(completed_at).isoformat()}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if tenant_id is not None and project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(GameDayExerciseRow).where(GameDayExerciseRow.evidence_hash == digest))
            if existing is not None:
                return self._game_day_result(existing, idempotent_replay=True)
            row = GameDayExerciseRow(exercise_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, scenario=scenario, runbook_reference=runbook_reference, participants_json=sorted(participants), observations_json=observations, corrective_requirements_json=corrective_requirements, test_ids_json=sorted(test_ids), evidence_hash=digest, state="completed", started_at=started_at, completed_at=completed_at, created_by=actor_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id or "platform", project_id=project_id, actor_id=actor_id, action="game_day:record", resource_type="game_day_exercise", resource_id=row.exercise_id, outcome="allowed", details={"scenario": scenario, "evidence_hash": digest}, session=session)
            self._emit(session, event_type="game_day.completed", tenant_id=tenant_id or "platform", project_id=project_id, aggregate_type="game_day_exercise", aggregate_id=row.exercise_id, payload={"scenario": scenario, "runbook_reference": runbook_reference, "evidence_hash": digest, "corrective_requirement_count": len(corrective_requirements)}, actor_id=actor_id)
            return self._game_day_result(row, idempotent_replay=False)

    @staticmethod
    def _game_day_result(row: GameDayExerciseRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"exercise_id": row.exercise_id, "scenario": row.scenario, "runbook_reference": row.runbook_reference, "participants": row.participants_json, "observations": row.observations_json, "corrective_requirements": row.corrective_requirements_json, "test_ids": row.test_ids_json, "evidence_hash": row.evidence_hash, "state": row.state, "evidence_class": "synthetic_local" if row.tenant_id is None else "controlled", "idempotent_replay": idempotent_replay}

    def create_after_action_review(
        self,
        *,
        tenant_id: str | None,
        project_id: str | None,
        incident_reference: str,
        findings: list[dict[str, Any]],
        corrective_requirements: list[dict[str, Any]],
        test_ids: list[str],
        owner: str,
        due_at: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        incident_reference = _bounded_string(incident_reference, code="AFTER_ACTION_INCIDENT_INVALID", field="incident_reference", limit=512)
        owner = _require_identifier(owner, code="AFTER_ACTION_OWNER_INVALID", field="owner")
        if not findings or not corrective_requirements or not test_ids or _aware(due_at) <= db_now():
            raise ValidationError("AFTER_ACTION_REVIEW_INCOMPLETE", "after-action review requires findings, corrective requirements, tests, owner, and future due date")
        body = {"tenant_id": tenant_id, "project_id": project_id, "incident_reference": incident_reference, "findings": findings, "corrective_requirements": corrective_requirements, "test_ids": sorted(test_ids), "owner": owner, "due_at": _aware(due_at).isoformat()}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            if tenant_id is not None and project_id is not None:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(AfterActionReviewRow).where(AfterActionReviewRow.review_hash == digest))
            if existing is not None:
                return self._after_action_result(existing, idempotent_replay=True)
            row = AfterActionReviewRow(review_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, incident_reference=incident_reference, findings_json=findings, corrective_requirements_json=corrective_requirements, test_ids_json=sorted(test_ids), owner=owner, due_at=due_at, state="open", review_hash=digest, created_by=actor_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id or "platform", project_id=project_id, actor_id=actor_id, action="after_action_review:create", resource_type="after_action_review", resource_id=row.review_id, outcome="allowed", details={"incident_reference": incident_reference, "review_hash": digest}, session=session)
            self._emit(session, event_type="after_action_review.created", tenant_id=tenant_id or "platform", project_id=project_id, aggregate_type="after_action_review", aggregate_id=row.review_id, payload={"incident_reference": incident_reference, "review_hash": digest, "corrective_requirement_count": len(corrective_requirements), "test_count": len(test_ids)}, actor_id=actor_id)
            return self._after_action_result(row, idempotent_replay=False)

    @staticmethod
    def _after_action_result(row: AfterActionReviewRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"review_id": row.review_id, "incident_reference": row.incident_reference, "findings": row.findings_json, "corrective_requirements": row.corrective_requirements_json, "test_ids": row.test_ids_json, "owner": row.owner, "due_at": _aware(row.due_at).isoformat(), "state": row.state, "review_hash": row.review_hash, "idempotent_replay": idempotent_replay}


def _compare(value: float, comparison: str, threshold: float) -> bool:
    if comparison == "<=":
        return value <= threshold
    if comparison == ">=":
        return value >= threshold
    if comparison == "<":
        return value < threshold
    if comparison == ">":
        return value > threshold
    raise ValidationError("SLO_COMPARISON_INVALID", "unsupported SLO comparison")


def _version_constraint_matches(actual: str, constraint: str) -> bool:
    if constraint.endswith(".x"):
        return actual.startswith(constraint[:-1])
    return actual == constraint
