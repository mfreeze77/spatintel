from __future__ import annotations

from pathlib import Path

import pytest

from tools.demo_progress11_release import run


@pytest.fixture(scope="module")
def progress11_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run the complete synthetic dual-vertical release demonstration once for direct assertions."""
    return run(tmp_path_factory.mktemp("progress11-release") / "evidence")


def test_progress11_construction_acceptance_is_complete_and_authority_safe(progress11_report: dict) -> None:
    """REQ: CONTEST-001, CONTEST-002, CONTEST-003, CONTEST-004, CONTEST-005, CONTEST-006, DELMVP-001, DELMVP-002, DELMVP-003, DELMVP-004, DELMVP-006, HYBTEST-004, HYBTEST-007, TSTGATE-008, TSTGATE-009, TSTGATE-010 Construction acceptance retains complete synthetic evidence, independent measurement authority, protected inventory, rollback, export, and restore without production claims."""
    construction = progress11_report["construction"]
    assertions = construction["assertions"]
    assert construction["scenario"]["status"] == "passed"
    assert assertions and all(assertions.values())
    assert assertions["independent_measurement_within_tolerance"] is True
    assert assertions["field_measurement_authoritative"] is True
    assert assertions["restricted_inventory_protected"] is True
    assert assertions["proxy_measurement_blocked"] is True
    assert assertions["proxy_replacement_preserves_history"] is True
    assert assertions["offline_owner_handoff_and_restore"] is True
    assert progress11_report["rollback"]["status"] == "passed"
    assert progress11_report["production_authorized"] is False


def test_progress11_hybrid_benchmark_evidence_is_profiled_and_conservative(progress11_report: dict) -> None:
    """REQ: DELDOD-007, DELDOD-008, DELDOD-009, DELDOD-010, DELDOD-011, HYBTEST-001, HYBTEST-002, HYBTEST-003, HYBTEST-005, HYBTEST-006, HYBTEST-008, HYBTEST-009, HYBTEST-010, HYBTEST-011, HYBTEST-012, HYBTEST-013, HYBTEST-014, HYBTEST-015, HYBTEST-016 Hybrid benchmark evidence is intended-use-profiled, independently grounded, authority-safe, reproducible, and explicit about external validation and representation loss."""
    benchmark = progress11_report["hybrid_benchmark"]
    assert benchmark["schema"] == "sip.hybrid-benchmark-evidence/v1"
    assert benchmark["ground_truth"]["independent"] is True
    assert benchmark["ground_truth"]["exact_geometry"] is True
    assert benchmark["metrics"]["global"]["hit_error_m"] == 0.0
    assert all(item["entity_recall"] == 1.0 for item in benchmark["metrics"]["critical_regions"].values())
    assert all(item["false_surface_count"] == 0 for item in benchmark["metrics"]["critical_regions"].values())
    assert benchmark["authority"] == {
        "proxy_authoritative": False,
        "visual_authoritative": False,
        "design_authoritative": False,
        "generated_authoritative": False,
        "provider_self_validation_authoritative": False,
        "metric_re_resolution_required": True,
    }
    assert set(benchmark["conformance"].values()) == {"passed"}
    assert benchmark["large_scene"]["status"] == "external_validation_required"
    assert benchmark["human_evaluation"]["status"] == "external_validation_required"
    assert benchmark["roundtrip"]["information_loss_reported"] is True
    assert benchmark["roundtrip"]["representation_equivalence_claimed"] is False
    assert benchmark["production_authorized"] is False


def test_progress11_liveforever_acceptance_preserves_truth_consent_and_safe_experience(progress11_report: dict) -> None:
    """REQ: DELMVP-005, LIFTEST-001, LIFTEST-002, LIFTEST-003, LIFTEST-004, LIFTEST-005, LIFTEST-006, TSTSEC-002 LiveForever acceptance preserves uncertainty, conflicting recollections, generated labels, consent propagation, safe experience modes, and independent offline preservation."""
    liveforever = progress11_report["liveforever"]
    assertions = liveforever["assertions"]
    assert liveforever["scenario"]["status"] == "passed"
    assert assertions and all(assertions.values())
    assert assertions["uncertain_date_preserved"] is True
    assert assertions["conflicting_recollections_preserved"] is True
    assert assertions["generated_content_labeled"] is True
    assert assertions["consent_revocation_propagated"] is True
    assert assertions["family_correction_preserves_original"] is True
    assert assertions["quiet_mode_safe_exit_and_evidence"] is True
    assert assertions["offline_preservation_and_restore"] is True
    assert progress11_report["production_authorized"] is False


def test_progress11_signed_candidate_retains_external_gaps_and_denies_production(progress11_report: dict) -> None:
    """REQ: DELDOD-001, DELDOD-005, DELDOD-006, DELDOD-012, TSTGATE-001, TSTGATE-002, TSTGATE-003, TSTGATE-004, TSTGATE-005, TSTGATE-006, TSTGATE-007, TSTGATE-011, TSTGATE-012, TSTSTRAT-001, TSTSTRAT-002, TSTSTRAT-003, TSTSTRAT-004, TSTSTRAT-005, TSTSTRAT-006 Signed release evidence preserves execution/control distinctions, external gaps, rollback, manifests, operating limits, and fail-closed production and next-milestone posture."""
    candidate = progress11_report["candidate"]
    verification = progress11_report["verification"]
    assert progress11_report["scope_requirement_count"] == 96
    assert candidate["status"] == "passed_with_external_gaps"
    assert candidate["blockers"] == []
    assert len(candidate["external_gaps"]) == 4
    assert verification["valid"] is True
    assert verification["status"] == "passed_with_external_gaps"
    assert verification["production_authorized"] is False
    assert verification["progress_12_authorized"] is False
    assert progress11_report["production_admission"]["production_authorized"] is False
    assert progress11_report["production_authorized"] is False
    assert progress11_report["progress_12_authorized"] is False
    assert all(gate["control_status"] in {"passed_complete", "passed_with_external_gaps"} for gate in progress11_report["gates"].values())
    assert any(gate["external_gap"] for gate in progress11_report["gates"].values())


def test_progress11_release_demonstration_is_repeatable_on_same_dedicated_root(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-003, TSTGATE-006 The complete release demonstration is repeatable on one dedicated root without stale database, package, or generated-evidence collisions."""
    output = tmp_path / "repeatable-release"
    first = run(output)
    second = run(output)
    for report in (first, second):
        assert report["status"] == "passed_with_external_gaps"
        assert report["scope_requirement_count"] == 96
        assert all(report["construction"]["assertions"].values())
        assert all(report["liveforever"]["assertions"].values())
        assert report["verification"]["valid"] is True
        assert report["production_authorized"] is False
        assert report["progress_12_authorized"] is False
    assert first["source_root_sha256"] == second["source_root_sha256"]
