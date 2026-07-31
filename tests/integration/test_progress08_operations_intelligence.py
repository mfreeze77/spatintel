from __future__ import annotations

from pathlib import Path

from tests.integration.test_progress08_observability_slo import (
    test_progress08_privacy_safe_telemetry_trace_and_quality_dashboard as _telemetry_dashboard,
    test_progress08_slos_performance_budgets_and_external_evidence_labels as _slo_budgets,
)
from tests.integration.test_progress08_cost_quota import (
    test_progress08_concurrent_admission_is_atomic_idempotent_and_leak_free as _admission_race,
    test_progress08_cost_model_reconciliation_capacity_and_price_history as _cost_model,
)
from tests.security.test_progress08_support_observability_security import (
    test_progress08_high_risk_support_routes_and_retains_no_raw_customer_data as _support_ticket,
    test_progress08_support_bundle_rejects_unchecked_unexpected_symlink_and_changed_replay as _support_bundle,
    test_progress08_support_scope_approval_expiration_revocation_and_cross_tenant_isolation as _support_scope,
)


def test_progress08_observability_slos_and_performance_budgets(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003, ARCOBS-004, ARCOBS-005, OPSPERF-001, OPSPERF-002, OPSPERF-003, OPSPERF-004, OPSPERF-005 observability, SLOs, and budgets are integrated through the authoritative service."""
    _telemetry_dashboard(tmp_path / "telemetry")
    _slo_budgets(tmp_path / "slo")


def test_progress08_cost_estimation_actuals_rollups_and_quota_admission(tmp_path: Path) -> None:
    """REQ: OPSCOST-001, OPSCOST-002, OPSCOST-003, OPSCOST-004, OPSCOST-005, OPSCOST-006, OPSPERF-006 cost estimates, actuals, rollups, and quota admission are integrated and idempotent."""
    _cost_model(tmp_path / "cost")
    _admission_race(tmp_path / "admission")


def test_progress08_customer_approved_support_bundle_and_ticket_routing(tmp_path: Path) -> None:
    """REQ: OPSSUP-001, OPSSUP-002, OPSSUP-003, OPSSUP-004, OPSSUP-005, OPSSUP-006 customer-approved support access, safe bundles, verification, and routing are integrated."""
    _support_scope(tmp_path / "scope")
    _support_bundle(tmp_path / "bundle")
    _support_ticket(tmp_path / "ticket")
