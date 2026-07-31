from __future__ import annotations

from pathlib import Path

from tools.demo_progress09_deployment import run


def test_progress09_synthetic_deployment_demonstration(tmp_path: Path) -> None:
    """REQ: ARCDEP-001, ARCDEP-003, ARCDEP-004, ARCDEP-005, OPSHYB-001, OPSHYB-005, OPSAWS-001, OPSAWS-003 synthetic profiles prove governed admission, portability, scaling, AWS structure, and production denial without claiming deployment."""
    result = run(tmp_path / "progress09-demo.json")
    assert result["status"] == "passed_complete"
    assert result["synthetic_only"] is True
    assert result["residency_denial_proven"] is True
    assert result["migration"]["preserved"] is True
    assert result["production_admission_denied"] is True
    assert result["production_authorized"] is False
    assert result["progress_10_authorized"] is False
