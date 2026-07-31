from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.database import ActualCostRow, AuditEventRow, BudgetReservationRow, OutboxEventRow, PriceCatalogRow
from sip.errors import AuthorizationError, ConflictError
from tests.progress08_helpers import bootstrap, compute_profile, cost_estimate, current_catalog_args, now, price_catalog


def _all_usage() -> dict[str, float]:
    return {
        "cpu_seconds": 120.0,
        "gpu_seconds": 30.0,
        "memory_gb_seconds": 400.0,
        "object_bytes_hot": 1_000_000.0,
        "object_bytes_cold": 2_000_000.0,
        "database_bytes": 500_000.0,
        "requests": 200.0,
        "search_units": 12.0,
        "vector_units": 10.0,
        "egress_bytes": 800_000.0,
        "transcription_seconds": 60.0,
        "ocr_pages": 4.0,
        "model_api_units": 3.0,
        "support_minutes": 2.0,
    }


def test_progress08_cost_model_reconciliation_capacity_and_price_history(tmp_path: Path) -> None:
    """REQ: OPSCOST-001, OPSCOST-002, OPSCOST-005, OPSCOST-006, RECGPU-005 all resource classes, stage attribution, measured capacity, and immutable catalog history are retained."""
    context, tenant, project = bootstrap(tmp_path, name="p08-cost-model")
    service = context.operations_intelligence
    profile = compute_profile(context)
    catalog = price_catalog(context, tenant, version="2026-07-local")
    usage = _all_usage()

    estimate = service.estimate_cost(
        tenant_id=tenant,
        project_id=project,
        run_id="cost-run-complete",
        operation_id=None,
        capture_id="capture-complete",
        compute_profile_id=profile["compute_profile_id"],
        price_catalog_id=catalog["price_catalog_id"],
        input_class={
            "scene_minutes": 4.0,
            "frames": 7200,
            "area_m2": 125.0,
            "peak_concurrency": 2,
            "headroom_ratio": 1.35,
            "storage_bytes": 3_500_000,
            "retention_days": 30,
        },
        quantities=usage,
        ttl_seconds=3600,
        actor_id="cost-admin",
    )
    assert {item["stage"] for item in estimate["stage_estimates"]} == {
        "decode", "inference", "optimization", "fusion", "splat", "semantic", "storage", "egress"
    }
    assert set(estimate["input_class"]["quantities"]) == set(usage)

    actual = service.record_actual_cost(
        tenant_id=tenant,
        project_id=project,
        idempotency_key="actual-all-resources",
        run_id="cost-run-complete",
        stage="complete_pipeline",
        operation_id=None,
        capture_id="capture-complete",
        model_id="approved-local-baseline",
        checkpoint_hash="c" * 64,
        price_catalog_id=catalog["price_catalog_id"],
        usage=usage,
        occurred_at=now(),
        actor_id="cost-worker",
    )
    assert set(actual["usage"]["quantities"]) == set(usage)
    reconciliation = service.reconcile_cost(
        tenant_id=tenant, project_id=project, run_id="cost-run-complete", actor_id="cost-admin"
    )
    assert reconciliation["actual_ids"] == [actual["actual_id"]]
    assert reconciliation["catalog_hashes"] == [catalog["catalog_hash"]]

    rollup = service.cost_rollup(
        tenant_id=tenant,
        project_id=project,
        period_start=now() - timedelta(days=1),
        period_end=now() + timedelta(days=1),
        dimensions=["project", "capture", "run", "stage", "model", "calendar_day"],
    )
    assert rollup["record_count"] == 1
    assert tenant not in str(rollup) and project not in str(rollup["groups"][0]["dimensions"]["project"])

    capacity = service.register_capacity_plan(
        tenant_id=tenant,
        project_id=project,
        profile_name="construction-medium",
        measurement_window={"start": (now() - timedelta(hours=1)).isoformat(), "end": now().isoformat()},
        scene_minutes=120.0,
        frames=216_000,
        area_m2=2_500.0,
        peak_concurrency=4,
        headroom_ratio=1.35,
        required_capacity={"cpu_cores": 16, "gpu_slots": 2, "memory_gb": 64, "storage_bytes": 40_000_000_000},
        evidence_class="synthetic_local",
        source_manifest_hash="9" * 64,
        actor_id="capacity-admin",
    )
    assert capacity["scene_minutes"] == 120.0
    assert capacity["headroom_ratio"] == 1.35

    new_catalog = service.register_price_catalog(**current_catalog_args(tenant, version="2026-08-local"))
    assert new_catalog["supersedes_price_catalog_id"] == catalog["price_catalog_id"]
    with context.database.session() as session:
        retained_actual = session.get(ActualCostRow, actual["actual_id"])
        retained_old_catalog = session.get(PriceCatalogRow, catalog["price_catalog_id"])
        assert retained_actual is not None and retained_actual.price_catalog_id == catalog["price_catalog_id"]
        assert retained_actual.usage_json["catalog_hash"] == retained_old_catalog.catalog_hash


def test_progress08_concurrent_admission_is_atomic_idempotent_and_leak_free(tmp_path: Path) -> None:
    """REQ: OPSCOST-003, OPSPERF-006 concurrent quota admission permits one reservation, preserves denial evidence, and releases capacity without leakage."""
    context, tenant, project = bootstrap(tmp_path, name="p08-admission-race")
    service = context.operations_intelligence
    profile = compute_profile(context)
    catalog = price_catalog(context, tenant)
    estimate_a = cost_estimate(context, tenant, project, profile["compute_profile_id"], catalog["price_catalog_id"], run_id="race-a", quantity=2.0)
    estimate_b = cost_estimate(context, tenant, project, profile["compute_profile_id"], catalog["price_catalog_id"], run_id="race-b", quantity=2.0)
    policy = service.register_budget_policy(
        tenant_id=tenant,
        project_id=project,
        revision="race-v1",
        currency="USD",
        period_seconds=86_400,
        soft_limit=100.0,
        hard_limit=100.0,
        concurrency_limit=1,
        storage_limit_bytes=10_000_000,
        retention_limit_days=365,
        anomaly_threshold=1.5,
        actor_id="ops-admin",
    )

    barrier = threading.Barrier(2)
    results: list[dict] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def attempt(estimate_id: str, key: str) -> None:
        try:
            barrier.wait(timeout=10)
            value = service.reserve_budget(
                tenant_id=tenant,
                project_id=project,
                estimate_id=estimate_id,
                idempotency_key=key,
                operation_id=None,
                ttl_seconds=3600,
                requested_by=key,
            )
            with lock:
                results.append(value)
        except Exception as exc:  # noqa: BLE001 - assertion captures governed result
            with lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=attempt, args=(estimate_a["estimate_id"], "race-requester-a")),
        threading.Thread(target=attempt, args=(estimate_b["estimate_id"], "race-requester-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ConflictError)
    assert errors[0].code == "BUDGET_CONCURRENCY_LIMIT"

    winning = results[0]
    replay = service.reserve_budget(
        tenant_id=tenant,
        project_id=project,
        estimate_id=winning["estimate_id"],
        idempotency_key="race-requester-a" if winning["estimate_id"] == estimate_a["estimate_id"] else "race-requester-b",
        operation_id=None,
        ttl_seconds=3600,
        requested_by="race-requester-a" if winning["estimate_id"] == estimate_a["estimate_id"] else "race-requester-b",
    )
    assert replay["reservation_id"] == winning["reservation_id"]
    assert replay["idempotent_replay"] is True

    with context.database.session() as session:
        reservations = list(session.scalars(select(BudgetReservationRow).where(BudgetReservationRow.project_id == project)))
        denials = list(session.scalars(select(AuditEventRow).where(
            AuditEventRow.project_id == project,
            AuditEventRow.resource_type == "budget_admission_denial",
            AuditEventRow.outcome == "denied",
        )))
        denial_events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.project_id == project,
            OutboxEventRow.event_type == "budget.admission_denied",
        )))
        assert len([row for row in reservations if row.state == "reserved"]) == 1
        assert len(denials) == 1
        assert len(denial_events) == 1

    released = service.release_budget_reservation(
        tenant_id=tenant,
        project_id=project,
        reservation_id=winning["reservation_id"],
        reason="completed",
        actor_id="ops-admin",
    )
    assert released["state"] == "released"
    losing_estimate = estimate_b if winning["estimate_id"] == estimate_a["estimate_id"] else estimate_a
    after_release = service.reserve_budget(
        tenant_id=tenant,
        project_id=project,
        estimate_id=losing_estimate["estimate_id"],
        idempotency_key="after-release",
        operation_id=None,
        ttl_seconds=3600,
        requested_by="ops-admin",
    )
    assert after_release["state"] == "reserved"
    assert after_release["budget_id"] == policy["budget_id"]


def test_progress08_override_and_alert_approval_are_independent_and_expiring(tmp_path: Path) -> None:
    """REQ: OPSCOST-003 controlled overrides and alert suppression deny self-approval and retain expiry evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p08-override")
    service = context.operations_intelligence
    policy = service.register_budget_policy(
        tenant_id=tenant, project_id=project, revision="v1", currency="USD", period_seconds=86_400,
        soft_limit=1.0, hard_limit=2.0, concurrency_limit=1, storage_limit_bytes=1_000_000,
        retention_limit_days=30, anomaly_threshold=1.2, actor_id="requester",
    )
    override = service.request_budget_override(
        tenant_id=tenant, project_id=project, budget_id=policy["budget_id"], requested_by="requester",
        reason="controlled synthetic load test", additional_amount=10.0, currency="USD",
        expires_at=now() + timedelta(hours=1),
    )
    with pytest.raises(AuthorizationError, match="independent"):
        service.approve_budget_override(
            tenant_id=tenant, project_id=project, override_id=override["override_id"], approved_by="requester"
        )
    approved = service.approve_budget_override(
        tenant_id=tenant, project_id=project, override_id=override["override_id"], approved_by="budget-approver"
    )
    assert approved["state"] == "active"
    assert approved["approval_hash"]

    alert = service.record_anomaly(
        tenant_id=tenant, project_id=project, category="queue", severity="high", metric_name="queue_depth",
        observed_value=50.0, baseline_value=5.0, threshold=2.0,
        evidence={"snapshot_hash": "8" * 64}, actor_id="detector",
    )
    with pytest.raises(AuthorizationError, match="creator"):
        service.acknowledge_anomaly(
            tenant_id=tenant, project_id=project, alert_id=alert["alert_id"], actor_id="detector",
            suppress_until=now() + timedelta(hours=1),
        )
    suppressed = service.acknowledge_anomaly(
        tenant_id=tenant, project_id=project, alert_id=alert["alert_id"], actor_id="on-call",
        suppress_until=now() + timedelta(hours=1),
    )
    assert suppressed["state"] == "suppressed"
    assert suppressed["suppression_approved_by"] == "on-call"
