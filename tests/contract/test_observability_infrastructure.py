from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "infrastructure/observability"
COMPOSE = ROOT / "infrastructure/compose/docker-compose.yml"

API_SERVICES = {
    "control-api",
    "identity-policy",
    "capture-service",
    "workflow-service",
    "scene-service",
    "evidence-service",
    "search-service",
    "export-service",
    "notification-service",
    "audit-service",
    "representation-api",
    "provider-registry",
    "representation-publisher",
}
WORKERS = {f"worker-{path.parent.name}" for path in (ROOT / "workers").glob("*/worker-manifest.json")}


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_prometheus_scrapes_every_api_and_isolated_worker() -> None:
    """REQ: ARCOBS-002 worker and API telemetry must be discoverable without customer-derived targets."""
    config = yaml.safe_load((OBS / "prometheus.yaml").read_text(encoding="utf-8"))
    jobs = {item["job_name"]: item for item in config["scrape_configs"]}
    api_targets = set(jobs["sip-api"]["static_configs"][0]["targets"])
    worker_targets = set(jobs["sip-worker"]["static_configs"][0]["targets"])
    assert api_targets == {f"{name}:8080" for name in API_SERVICES}
    assert worker_targets == {f"{name}:9100" for name in WORKERS}


def test_observability_profile_is_hardened_and_digest_pinned() -> None:
    """REQ: ARCOBS-001, ARCDEP-002, OPSSEC-005 local telemetry services are opt-in, hardened, and immutable."""
    services = _compose()["services"]
    for name in ("otel-collector", "prometheus", "grafana"):
        service = services[name]
        assert service["profiles"] == ["observability"]
        assert "@sha256:" in service["image"]
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert service.get("privileged") is not True
    assert services["grafana"]["environment"]["GF_AUTH_ANONYMOUS_ENABLED"] == "false"
    assert services["grafana"]["environment"]["GF_SECURITY_ADMIN_PASSWORD__FILE"].startswith("/run/secrets/")


def test_workers_publish_metrics_without_broadening_compute_permissions() -> None:
    """REQ: ARCOBS-002, PLTGRPC-004 workers expose metrics but retain private staging and denied compute network."""
    services = _compose()["services"]
    for name in WORKERS:
        service = services[name]
        assert service["environment"]["SIP_WORKER_METRICS_PORT"] == "9100"
        assert service["environment"]["SIP_WORKER_COMPUTE_NETWORK_ACCESS"] == "denied"
        assert service["environment"]["SIP_WORKER_PUBLICATION_PERMISSION"] == "false"
        assert service["expose"] == ["9100"]
        runtime = [str(item) for item in service["volumes"] if ":/var/lib/sip/runtime" in str(item)]
        assert runtime == [f"{name}-runtime:/var/lib/sip/runtime"]


def test_kubernetes_workers_are_scrapeable_only_through_observability_policy() -> None:
    """REQ: ARCOBS-002 Kubernetes scrape access is explicit and does not grant worker publication privileges."""
    for name in WORKERS:
        deployment = yaml.safe_load(
            (ROOT / f"infrastructure/kubernetes/base/deployments/{name}.yaml").read_text(encoding="utf-8")
        )
        template = deployment["spec"]["template"]
        annotations = template["metadata"]["annotations"]
        assert annotations["prometheus.io/scrape"] == "true"
        assert annotations["prometheus.io/port"] == "9100"
        container = template["spec"]["containers"][0]
        assert {port["name"]: port["containerPort"] for port in container["ports"]}["metrics"] == 9100
        env = {item["name"]: item.get("value") for item in container["env"]}
        assert env["SIP_WORKER_METRICS_PORT"] == "9100"
        assert env["SIP_WORKER_PUBLICATION_PERMISSION"] == "false"
    policies = list(yaml.safe_load_all((ROOT / "infrastructure/kubernetes/base/network-policies.yaml").read_text()))
    policy = next(item for item in policies if item["metadata"]["name"] == "observability-scrape")
    source = policy["spec"]["ingress"][0]["from"][0]["namespaceSelector"]["matchLabels"]
    assert source["kubernetes.io/metadata.name"] == "sip-observability"
    assert {item["port"] for item in policy["spec"]["ingress"][0]["ports"]} == {8080, 9100}


def test_quality_dashboard_and_alerts_cover_required_operational_signals() -> None:
    """REQ: ARCOBS-004 dashboards retain drift, coverage, residual, confidence, failed-region and prior-delta signals."""
    dashboard = json.loads((OBS / "grafana/sip-overview.json").read_text(encoding="utf-8"))
    expressions = "\n".join(target["expr"] for panel in dashboard["panels"] for target in panel["targets"])
    required = {
        "sip:reconstruction_drift:p95_1h",
        "sip:reconstruction_coverage:p50_1h",
        "sip:reconstruction_residual:p95_1h",
        "sip:reconstruction_confidence:p50_1h",
        "sip_reconstruction_failed_regions",
        "sip:reconstruction_quality_delta:p50_1h",
        "sip:worker_queue_wait:p95_15m",
        "sip_worker_runs_total",
    }
    assert all(metric in expressions for metric in required)

    rules_text = (OBS / "prometheus-rules.yaml").read_text(encoding="utf-8")
    assert "sip_unhandled_errors_total" not in rules_text
    assert 'sip_errors_total{outcome="unhandled_error"}' in rules_text
    for alert in (
        "SIPWorkerFailureRatioHigh",
        "SIPWorkerQueueWaitHigh",
        "SIPReconstructionDriftHigh",
        "SIPReconstructionCoverageLow",
        "SIPReconstructionFailedRegions",
    ):
        assert f"alert: {alert}" in rules_text


def test_local_collector_is_non_exporting_and_privacy_filtered() -> None:
    """REQ: ARCOBS-001 local development telemetry cannot silently leave the machine."""
    local = yaml.safe_load((OBS / "otel-collector.local.yaml").read_text(encoding="utf-8"))
    assert set(local["exporters"]) == {"debug"}
    assert all(pipeline["exporters"] == ["debug"] for pipeline in local["service"]["pipelines"].values())
    actions = local["processors"]["attributes/privacy"]["actions"]
    deleted = {item["key"] for item in actions if item["action"] == "delete"}
    assert {"http.request.header.authorization", "http.request.header.cookie", "sip.asset.content"} <= deleted


def test_secret_bootstrap_covers_observability_password() -> None:
    source = (ROOT / "tools" / "bootstrap_secrets.py").read_text(encoding="utf-8")
    assert "grafana_admin_password.txt" in source
    compose = yaml.safe_load((ROOT / "infrastructure" / "compose" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["secrets"]["sip_grafana_admin_password"]["file"].endswith("grafana_admin_password.txt")


def test_observability_operator_documentation_covers_worker_quality_incidents() -> None:
    runbook = (ROOT / "docs" / "runbooks" / "OBSERVABILITY_INCIDENTS.md").read_text(encoding="utf-8")
    for heading in ("Worker failure ratio", "Excessive worker queue delay", "Reconstruction-quality regression"):
        assert heading in runbook
    compose_readme = (ROOT / "infrastructure" / "compose" / "README.md").read_text(encoding="utf-8")
    assert "--profile observability" in compose_readme
    assert "SIP_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318" in compose_readme
