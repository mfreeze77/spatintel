from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module():
    path=ROOT / "tools/demo_progress08_operations.py"
    spec=importlib.util.spec_from_file_location("sip_progress08_demo", path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


@pytest.mark.acceptance
def test_progress08_synthetic_operations_demonstration(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003, OPSCOST-001, OPSCOST-002, OPSCOST-003, OPSCOST-004, OPSCOST-005, OPSCOST-006, OPSSUP-001, OPSSUP-002, OPSSUP-003, OPSSUP-004, OPSSUP-005, OPSSUP-006 Progress 08 demonstrates privacy-safe telemetry, SLO, cost, quota, queue, and independently verified support handling."""
    report=_module().run_demo(tmp_path / "operations")
    assert report["status"] == "passed_complete"
    assert report["telemetry"]["raw_data_included"] is False
    assert report["slo"]["compliant"] is True
    assert report["cost"]["price_catalog_hash"]
    assert report["admission"]["state"] == "reserved"
    assert report["support"]["grant_state"] == "active"
    assert report["support"]["bundle_valid"] is True
    assert report["support"]["raw_media_included"] is False
    assert report["evidence_class"] == "synthetic_local"
    assert report["progress_09_authorized"] is False
    assert report["production_authorized"] is False
