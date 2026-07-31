from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_progress08_resilience_gpu_incidents import (
    test_progress08_compute_profiles_compatibility_oom_cost_stages_and_resume as _compute_resume,
    test_progress08_incident_actions_after_action_reviews_and_game_days as _incident_game_day,
    test_progress08_resilience_profile_worker_exhaustion_and_postwrite_integrity as _resilience_profile,
)


def test_progress08_resilience_profiles_compute_compatibility_and_explicit_oom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ: ARCRES-001, ARCRES-002, ARCRES-004, ARCRES-005, RECGPU-001, RECGPU-002, RECGPU-003, RECGPU-004, OPSPERF-005 resilience profiles, compute compatibility, isolation, and explicit OOM behavior are integrated."""
    _resilience_profile(tmp_path / "resilience", monkeypatch)
    _compute_resume(tmp_path / "gpu")


def test_progress08_verified_checkpoint_resume_and_incident_evidence(tmp_path: Path) -> None:
    """REQ: RECGPU-006, OPSSRE-003 verified checkpoint resume and incident actions retain auditable evidence."""
    _compute_resume(tmp_path / "resume")
    _incident_game_day(tmp_path / "incident")


def test_progress08_game_day_and_after_action_create_corrective_requirements(tmp_path: Path) -> None:
    """REQ: OPSSRE-004, OPSSRE-005 game days and after-action reviews create owned corrective requirements and tests."""
    _incident_game_day(tmp_path / "game-day")
