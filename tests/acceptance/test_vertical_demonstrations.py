from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _demo_module():
    path = ROOT / "tools/run_demo.py"
    spec = importlib.util.spec_from_file_location("sip_demo_acceptance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.acceptance
def test_construction_synthetic_acceptance_demonstration(tmp_path: Path) -> None:
    """REQ: CONDEMO-001, CONDEMO-004, CONDEMO-005 construction workflow retains evidence and caveats."""
    report = _demo_module().construction(tmp_path / "construction")
    assert report["acceptance"]["drawing_imported"] is True
    assert report["acceptance"]["capture_pause_recovered"] is True
    assert report["acceptance"]["capture_finalized_locally"] is True
    assert report["acceptance"]["field_measurement_verified"] is True
    assert report["acceptance"]["deficiency_closed_after_retest"] is True
    assert report["acceptance"]["semantic_diff_reviewable"] is True
    assert report["acceptance"]["states_distinct"] is True
    assert report["acceptance"]["warning_present"] is True
    assert report["preservation"]["matching_root_hash"] is True


@pytest.mark.acceptance
@pytest.mark.privacy
def test_liveforever_synthetic_acceptance_demonstration(tmp_path: Path) -> None:
    """REQ: LIFDEMO-004, LIFDEMO-005, LIFTEST-005 consent and preservation remain enforceable."""
    report = _demo_module().liveforever(tmp_path / "liveforever")
    assert report["acceptance"]["conflicts_preserved"] is True
    assert report["acceptance"]["generated_content_labeled"] is True
    assert report["acceptance"]["revocation_propagated"] is True
    assert report["acceptance"]["quiet_mode"] is True
    assert report["acceptance"]["safe_exit"] is True
    assert report["preservation"]["matching_root_hash"] is True
