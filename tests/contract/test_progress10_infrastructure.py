from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_progress10_recovery_service_is_production_shaped_and_fail_closed() -> None:
    """REQ: ARCRES-001, ARCRES-002, OPSDR-001, OPSDR-003 recovery-control has non-root health-checked service boundaries, immutable storage intent, and production denial."""
    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text())
    service = compose["services"]["recovery-control"]
    assert service["environment"]["SIP_SERVICE_NAME"] == "recovery-control"
    assert service["environment"]["SIP_PRODUCTION_AUTHORIZED"] == "false"
    assert service["environment"]["SIP_RECOVERY_WRITES_REOPEN"] == "reconciled-only"
    deployment = yaml.safe_load((ROOT / "infrastructure/kubernetes/base/deployments/recovery-control.yaml").read_text())
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["serviceAccountName"] == "recovery-control"
    assert pod["automountServiceAccountToken"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"
    assert "@sha256:" in container["image"]


def test_progress10_generated_service_and_openapi_contracts_are_current() -> None:
    """REQ: OPSDR-001, OPSDR-005, DATRET-002, DATRET-005 recovery APIs and operation ownership are generated from the logical recovery-control boundary."""
    service = json.loads((ROOT / "services/recovery-control/service.json").read_text())
    openapi = json.loads((ROOT / "schemas/openapi/recovery-control.openapi.json").read_text())
    operations = {item["operation_id"] for item in service["operations"]}
    assert {
        "register_recovery_objective", "create_recovery_point", "verify_recovery_point",
        "create_recovery_restore", "build_deletion_graph", "request_recovery_purge",
        "approve_recovery_purge", "execute_recovery_purge", "create_tenant_offboarding",
        "run_recovery_game_day", "record_legacy_migration", "evaluate_recovery_production_admission",
    }.issubset(operations)
    assert len(openapi["paths"]) >= 15
    catalog = json.loads((ROOT / "governance/service-catalog.json").read_text())
    entry = next(item for item in catalog["components"] if item["name"] == "recovery-control")
    assert entry["inbound_apis"] == service["operations"]
