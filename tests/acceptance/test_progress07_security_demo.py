from __future__ import annotations

from pathlib import Path

from tools.demo_progress07_security import run_demo
from tools.progress07_supply_chain_check import run as run_supply_chain


def test_progress07_security_privacy_and_supply_chain_demo(tmp_path: Path) -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-005, OPSCICD-001, OPSKEY-001, OPSKEY-002, OPSPRIV-001, OPSSEC-001, OPSSEC-002, OPSSEC-003, OPSTHR-008, OPSTHR-012, OPSTHREA-002, SECEXT-003 synthetic security, privacy, provider, immersive, and supply-chain controls execute together without authorizing production."""
    report = run_demo(tmp_path / "runtime")
    assert report["status"] == "passed_complete"
    assert report["threat_manifest"]["version"] == 1
    assert report["jit_access"]["state"] == "active"
    assert report["workload_identity"]["audience"] == "worker-runtime"
    assert report["key_scope"]["state"] == "active"
    assert report["privacy_inventory"]["state"] == "active"
    assert report["transport"]["state"] == "passed"
    assert report["provider_output"]["state"] == "validated_quarantined"
    assert report["immersive_safety"]["state"] == "degraded_safe"
    assert report["audit"]["valid"] is True
    assert report["production_authorized"] is False
    supply = run_supply_chain()
    assert supply["status"] in {"passed_complete", "passed_with_external_gaps"}
    assert supply["findings"] == []
    assert supply["production_authorized"] is False
