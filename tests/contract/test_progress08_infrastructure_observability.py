from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_progress08_operations_service_is_nonroot_readonly_and_scraped() -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003, OPSSRE-006 operations telemetry is isolated, least-privilege, and observable through governed endpoints."""
    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text())
    service = compose["services"]["operations-intelligence"]
    assert service["user"] == "10001:10001"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    deployment = yaml.safe_load((ROOT / "infrastructure/kubernetes/base/deployments/operations-intelligence.yaml").read_text())
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["serviceAccountName"] == "operations-intelligence"
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    prometheus = (ROOT / "infrastructure/observability/prometheus.yaml").read_text()
    assert "operations-intelligence:8080" in prometheus


def test_progress08_collector_scrubs_sensitive_content_before_export() -> None:
    """REQ: ARCOBS-001, ARCOBS-002, OPSSUP-001 observability export removes credentials, raw assets, transcripts, biometrics, and restricted facility data."""
    collector = yaml.safe_load((ROOT / "infrastructure/observability/otel-collector.yaml").read_text())
    actions = collector["processors"]["attributes/privacy"]["actions"]
    deleted = {item["key"] for item in actions if item["action"] == "delete"}
    assert {
        "http.request.header.authorization", "http.request.header.cookie",
        "sip.asset.content", "sip.transcript.content"
    } <= deleted
    source = (ROOT / "src/sip/observability.py").read_text()
    for marker in ("raw[_-]?(?:media", "biometric", "restricted[_-]?(?:construction", "private[_-]?key"):
        assert marker in source


def test_progress08_slo_cost_queue_quality_and_support_dashboards_are_declared() -> None:
    """REQ: ARCOBS-004, OPSCOST-002, OPSCOST-003, OPSCOST-005, OPSSRE-001 dashboards and alerts cover quality, SLO, queue, cost, quota, and support signals."""
    dashboard = json.loads((ROOT / "infrastructure/observability/grafana/sip-operations-intelligence.json").read_text())
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {"SLO error-budget burn", "Queue depth and wait", "Budget reserved vs hard limit", "Estimate vs actual", "Quality drift / coverage / residual", "Support access denials"} <= titles
    rules = (ROOT / "infrastructure/observability/prometheus-rules.yaml").read_text()
    for alert in ("SIPHighErrorBudgetBurnFast", "SIPWorkerQueueWaitHigh", "SIPBudgetAdmissionDeniedSpike", "SIPBudgetReservationLeakSuspected", "SIPSupportGrantExpiredInUse"):
        assert alert in rules


def test_progress08_audit_storage_remains_append_only_for_support_users() -> None:
    """REQ: ARCOBS-005 ordinary support cannot modify append-only audit evidence."""
    sql = (ROOT / "infrastructure/postgres/audit-immutability.sql").read_text().upper()
    assert "REVOKE UPDATE, DELETE" in sql
    assert "AUDIT_EVENTS" in sql
    assert "GRANT SELECT, INSERT" in sql
    assert "GRANT SELECT" in sql
