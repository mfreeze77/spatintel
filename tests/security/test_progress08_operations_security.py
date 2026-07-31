from __future__ import annotations

import io
import json
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sip.database import AuditEventRow, BudgetReservationRow, SupportAccessGrantRow, SupportBundleRow
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from tests.progress08_helpers import bootstrap, compute_profile, current_catalog_args, now


def _telemetry(service, tenant: str, project: str, *, correlation: str = "corr-sec", payload=None, labels=None):
    return service.record_telemetry(
        tenant_id=tenant,
        project_id=project,
        telemetry_type="log",
        service="control-api",
        release="1.1.0-progress08",
        correlation_id=correlation,
        trace_id="1" * 32,
        traceparent="00-" + "1" * 32 + "-" + "2" * 16 + "-01",
        operation_id="operation-sec",
        route_template="/v1/projects/{project_id}/operations",
        stage="support",
        model_id=None,
        checkpoint_hash=None,
        capture_profile=None,
        hardware_profile="cpu-reference",
        execution_profile="local",
        queue_class=None,
        vertical="construction",
        severity="warning",
        outcome="failed",
        stable_error_code="SYNTHETIC_ERROR",
        payload=payload or {"message_code": "synthetic_error", "duration_ms": 10.0, "retryable": False},
        labels=labels or {"support_profile": "metadata-only"},
        actor_id="ops-admin",
    )


def _estimate_stack(tmp_path: Path, *, name: str, hard_limit: float = 100.0, concurrency_limit: int = 1):
    context, tenant, project = bootstrap(tmp_path, name=name)
    service = context.operations_intelligence
    profile = service.register_compute_profile(**compute_profile())
    catalog = service.register_price_catalog(**current_catalog_args(tenant))
    estimate = service.estimate_cost(
        tenant_id=tenant,
        project_id=project,
        run_id=f"run-{name}",
        operation_id=None,
        capture_id=f"capture-{name}",
        compute_profile_id=profile["compute_profile_id"],
        price_catalog_id=catalog["price_catalog_id"],
        input_class={"frames": 10, "storage_bytes": 1000, "retention_days": 30},
        quantities={"cpu_seconds": 10.0, "requests": 1.0},
        ttl_seconds=3600,
        actor_id="ops-admin",
    )
    policy = service.register_budget_policy(
        tenant_id=tenant,
        project_id=project,
        revision="v1",
        currency="USD",
        period_seconds=86400,
        soft_limit=min(1.0, hard_limit),
        hard_limit=hard_limit,
        concurrency_limit=concurrency_limit,
        storage_limit_bytes=10_000,
        retention_limit_days=365,
        anomaly_threshold=1.5,
        actor_id="ops-admin",
    )
    return context, tenant, project, service, profile, catalog, estimate, policy


def test_progress08_telemetry_isolation_scrubbing_cardinality_and_trace_spoofing(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003 telemetry rejects sensitive content, unbounded labels, log injection, and spoofed trace context while preserving tenant isolation."""
    context, tenant_a, project_a = bootstrap(tmp_path, name="telemetry-security")
    tenant_b = context.tenancy.create_tenant("Other Tenant", tenant_id="tenant-telemetry-other", actor_id="system")
    project_b = context.tenancy.create_project(tenant_b, "Other Project", vertical="platform", classification="internal", project_id="project-telemetry-other", actor_id="system")
    service = context.operations_intelligence

    record = _telemetry(service, tenant_a, project_a)
    assert service.query_telemetry(tenant_id=tenant_a, project_id=project_a)["count"] == 1
    assert service.query_telemetry(tenant_id=tenant_b, project_id=project_b)["count"] == 0
    with pytest.raises(NotFoundError):
        service.query_telemetry(tenant_id=tenant_b, project_id=project_a)

    with pytest.raises(ValidationError) as secret:
        _telemetry(service, tenant_a, project_a, correlation="corr-secret", payload={"password": "SUPERSECRET"})
    assert secret.value.code == "TELEMETRY_FIELD_FORBIDDEN"

    with pytest.raises(ValidationError):
        _telemetry(service, tenant_a, project_a, correlation="corr-inject", payload={"message_code": "bad\nforged-entry"})
    with pytest.raises(ValidationError) as cardinality:
        _telemetry(service, tenant_a, project_a, correlation="corr-label", labels={f"k{i}": "v" for i in range(25)})
    assert cardinality.value.code in {"TELEMETRY_LABELS_INVALID", "TELEMETRY_LABEL_FORBIDDEN"}
    with pytest.raises(ValidationError) as spoofed:
        service.record_telemetry(
            tenant_id=tenant_a, project_id=project_a, telemetry_type="trace", service="control-api",
            release="1.1.0-progress08", correlation_id="corr-spoof", trace_id="3" * 32,
            traceparent="00-" + "4" * 32 + "-" + "5" * 16 + "-01", operation_id=None,
            route_template="/v1/projects/{project_id}/operations", stage="ingest", model_id=None,
            checkpoint_hash=None, capture_profile=None, hardware_profile=None, execution_profile="local",
            queue_class=None, vertical="construction", severity="info", outcome="passed",
            stable_error_code=None, payload={"duration_ms": 1.0}, labels={}, actor_id="ops-admin",
        )
    assert spoofed.value.code == "TELEMETRY_TRACE_CONTEXT_CONFLICT"
    assert tenant_a not in json.dumps(record) and project_a not in json.dumps(record)


def test_progress08_price_catalog_actual_cost_and_estimate_idempotency_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSCOST-001, OPSCOST-002, OPSCOST-004, OPSCOST-006 pricing is tenant-scoped, stale versions are denied, and retries do not double count."""
    context, tenant, project, service, profile, catalog, estimate, _ = _estimate_stack(tmp_path, name="cost-security")
    with pytest.raises(NotFoundError):
        service.register_price_catalog(
            tenant_id="tenant-does-not-exist", version="bad", currency="USD",
            effective_at=now() - timedelta(hours=1), expires_at=now() + timedelta(hours=1),
            prices=current_catalog_args(tenant)["prices"], source_reference="invalid", source_hash="9" * 64, actor_id="ops-admin",
        )

    stale = service.register_price_catalog(
        tenant_id=tenant, version="expired-v1", currency="USD",
        effective_at=now() - timedelta(days=2), expires_at=now() - timedelta(days=1),
        prices=current_catalog_args(tenant)["prices"], source_reference="expired-fixture", source_hash="8" * 64, actor_id="ops-admin",
    )
    with pytest.raises(ConflictError) as expired:
        service.estimate_cost(
            tenant_id=tenant, project_id=project, run_id="run-stale", operation_id=None, capture_id=None,
            compute_profile_id=profile["compute_profile_id"], price_catalog_id=stale["price_catalog_id"],
            input_class={"frames": 1}, quantities={"cpu_seconds": 1.0}, ttl_seconds=3600, actor_id="ops-admin",
        )
    assert expired.value.code == "PRICE_CATALOG_STALE"

    occurred = now().replace(microsecond=0)
    first = service.record_actual_cost(
        tenant_id=tenant, project_id=project, idempotency_key="actual-idem", run_id=estimate["run_id"],
        stage="inference", operation_id=None, capture_id=None, model_id=None, checkpoint_hash=None,
        price_catalog_id=catalog["price_catalog_id"], usage={"cpu_seconds": 2.0}, occurred_at=occurred,
        actor_id="worker",
    )
    replay = service.record_actual_cost(
        tenant_id=tenant, project_id=project, idempotency_key="actual-idem", run_id=estimate["run_id"],
        stage="inference", operation_id=None, capture_id=None, model_id=None, checkpoint_hash=None,
        price_catalog_id=catalog["price_catalog_id"], usage={"cpu_seconds": 2.0}, occurred_at=occurred,
        actor_id="worker",
    )
    assert replay["actual_id"] == first["actual_id"] and replay["idempotent_replay"] is True
    with pytest.raises(ConflictError) as changed:
        service.record_actual_cost(
            tenant_id=tenant, project_id=project, idempotency_key="actual-idem", run_id=estimate["run_id"],
            stage="inference", operation_id=None, capture_id=None, model_id=None, checkpoint_hash=None,
            price_catalog_id=catalog["price_catalog_id"], usage={"cpu_seconds": 3.0}, occurred_at=occurred,
            actor_id="worker",
        )
    assert changed.value.code == "ACTUAL_COST_IDEMPOTENCY_CONFLICT"
    rollup = service.cost_rollup(tenant_id=tenant, project_id=project, period_start=occurred - timedelta(hours=1), period_end=occurred + timedelta(hours=1), dimensions=["project"])
    assert rollup["record_count"] == 1


def test_progress08_quota_race_override_and_denial_evidence_are_governed(tmp_path: Path) -> None:
    """REQ: OPSCOST-003, OPSPERF-006 concurrent admission is atomic, denials survive rollback, and overrides require independent bounded approval."""
    context, tenant, project, service, _, _, estimate, policy = _estimate_stack(tmp_path, name="quota-race", concurrency_limit=1)
    barrier = threading.Barrier(2)

    def reserve(key: str):
        barrier.wait(timeout=10)
        try:
            return service.reserve_budget(
                tenant_id=tenant, project_id=project, estimate_id=estimate["estimate_id"],
                idempotency_key=key, operation_id=None, ttl_seconds=3600, requested_by="requester",
            )
        except ConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, ["race-a", "race-b"]))
    successes = [item for item in results if isinstance(item, dict)]
    denials = [item for item in results if isinstance(item, ConflictError)]
    assert len(successes) == 1
    assert len(denials) == 1 and denials[0].code == "BUDGET_CONCURRENCY_LIMIT"
    with context.database.session() as session:
        assert session.scalar(select(func.count()).select_from(BudgetReservationRow).where(BudgetReservationRow.tenant_id == tenant, BudgetReservationRow.project_id == project, BudgetReservationRow.state == "reserved")) == 1
        assert session.scalar(select(func.count()).select_from(AuditEventRow).where(AuditEventRow.tenant_id == tenant, AuditEventRow.project_id == project, AuditEventRow.resource_type == "budget_admission_denial")) == 1

    pending = service.request_budget_override(
        tenant_id=tenant, project_id=project, budget_id=policy["budget_id"], requested_by="same",
        reason="test", additional_amount=10.0, currency="USD", expires_at=now() + timedelta(hours=1),
    )
    with pytest.raises(AuthorizationError) as self_approved:
        service.approve_budget_override(
            tenant_id=tenant, project_id=project, override_id=pending["override_id"], approved_by="same",
        )
    assert self_approved.value.code == "BUDGET_OVERRIDE_SELF_APPROVAL_DENIED"
    with pytest.raises(ValidationError):
        service.request_budget_override(
            tenant_id=tenant, project_id=project, budget_id=policy["budget_id"], requested_by="requester",
            reason="test", additional_amount=10.0, currency="USD", expires_at=now() + timedelta(days=8),
        )


def test_progress08_anomaly_suppression_requires_independent_bounded_approval(tmp_path: Path) -> None:
    """REQ: ARCOBS-004, OPSCOST-003 anomaly evidence is immutable and suppression cannot be self-approved or unbounded."""
    context, tenant, project = bootstrap(tmp_path, name="anomaly-security")
    service = context.operations_intelligence
    alert = service.record_anomaly(
        tenant_id=tenant, project_id=project, category="cost", severity="high", metric_name="gpu_seconds",
        observed_value=20.0, baseline_value=5.0, threshold=2.0,
        evidence={"correlation_id": "corr-anomaly", "source_manifest_hash": "7" * 64}, actor_id="detector",
    )
    with pytest.raises(AuthorizationError):
        service.acknowledge_anomaly(
            tenant_id=tenant, project_id=project, alert_id=alert["alert_id"], actor_id="detector",
            suppress_until=now() + timedelta(hours=1),
        )
    with pytest.raises(ValidationError):
        service.acknowledge_anomaly(
            tenant_id=tenant, project_id=project, alert_id=alert["alert_id"], actor_id="independent",
            suppress_until=now() + timedelta(days=8),
        )
    suppressed = service.acknowledge_anomaly(
        tenant_id=tenant, project_id=project, alert_id=alert["alert_id"], actor_id="independent",
        suppress_until=now() + timedelta(hours=1),
    )
    assert suppressed["state"] == "suppressed"
    assert suppressed["suppression_approved_by"] == "independent"


def _rewrite_zip(data: bytes, *, extra: tuple[str, bytes] | None = None, omit: str | None = None, duplicate: str | None = None) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(data))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            if info.filename == omit:
                continue
            payload = source.read(info.filename)
            target.writestr(info, payload)
            if duplicate == info.filename:
                target.writestr(info, payload)
        if extra:
            target.writestr(extra[0], extra[1])
    return buffer.getvalue()


def test_progress08_support_authorization_scope_and_archive_attacks_fail_closed(tmp_path: Path) -> None:
    """REQ: OPSSUP-001, OPSSUP-002, OPSSUP-003, OPSSUP-004, OPSSUP-005, OPSSUP-006 support access is independent, time-bound, scope-safe, and bundle verification rejects malicious or stale content."""
    context, tenant, project = bootstrap(tmp_path, name="support-security")
    service = context.operations_intelligence
    telemetry = _telemetry(service, tenant, project, correlation="corr-bundle")
    with pytest.raises(ValidationError):
        service.request_support_access(
            tenant_id=tenant, project_id=project, resource_scope={"resource_ids": ["*"]}, purpose="support",
            personnel=["support-engineer"], requested_by="customer", duration_seconds=3600,
        )
    requested = service.request_support_access(
        tenant_id=tenant, project_id=project,
        resource_scope={"resource_ids": [telemetry["telemetry_id"]], "telemetry_types": ["log"], "include_logs": True, "include_metrics": False, "include_traces": False, "classification": "internal", "audience": "private"},
        purpose="support", personnel=["support-engineer"], requested_by="customer", duration_seconds=3600,
    )
    with pytest.raises(AuthorizationError):
        service.approve_support_access(tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="customer")
    active = service.approve_support_access(tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="independent-customer-approver")
    with pytest.raises(AuthorizationError):
        service.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=active["grant_id"], telemetry_ids=[telemetry["telemetry_id"]],
            hardware_profile={"device_tier": "desktop"}, manifest_references=[], actor_id="not-approved",
        )
    bundle = service.create_support_bundle(
        tenant_id=tenant, project_id=project, grant_id=active["grant_id"], telemetry_ids=[telemetry["telemetry_id"]],
        hardware_profile={"device_tier": "desktop"}, manifest_references=[{"kind": "source", "sha256": "6" * 64}], actor_id="support-engineer",
    )
    with context.database.session() as session:
        row = session.get(SupportBundleRow, bundle["bundle_id"])
        assert row is not None
        original = Path(row.bundle_path).read_bytes()
    assert service.verify_support_bundle_bytes(original)["valid"] is True
    with pytest.raises(ValidationError):
        service.verify_support_bundle_bytes(_rewrite_zip(original, extra=("../escape.txt", b"x")))
    assert service.verify_support_bundle_bytes(_rewrite_zip(original, extra=("evil.js", b"alert(1)")))["valid"] is False
    assert service.verify_support_bundle_bytes(_rewrite_zip(original, omit="checksums.json"))["valid"] is False
    with pytest.raises(ValidationError):
        service.verify_support_bundle_bytes(_rewrite_zip(original, duplicate="support-bundle.json"))

    service.revoke_support_access(tenant_id=tenant, project_id=project, grant_id=active["grant_id"], actor_id="customer")
    with pytest.raises(AuthorizationError):
        service.verify_support_bundle(tenant_id=tenant, project_id=project, bundle_id=bundle["bundle_id"], actor_id="support-engineer")

    with context.database.session() as session:
        grant = session.get(SupportAccessGrantRow, active["grant_id"])
        grant.state = "active"
        grant.revoked_at = None
        row = session.get(SupportBundleRow, bundle["bundle_id"])
        path = Path(row.bundle_path)
        path.write_bytes(_rewrite_zip(original, extra=("evil.js", b"x")))
    with pytest.raises(ConflictError) as stale:
        service.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=active["grant_id"], telemetry_ids=[telemetry["telemetry_id"]],
            hardware_profile={"device_tier": "desktop"}, manifest_references=[{"kind": "source", "sha256": "6" * 64}], actor_id="support-engineer",
        )
    assert stale.value.code == "SUPPORT_BUNDLE_REPLAY_CHANGED"
