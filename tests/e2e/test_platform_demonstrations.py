from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import func, select

from sip.capture import CapturePackage
from sip.database import RepresentationAssetRow
from sip.errors import ValidationError
from sip.geometry import mesh_to_splats, splats_to_surface

ROOT = Path(__file__).resolve().parents[2]


def _demo_module():
    path = ROOT / "tools/run_demo.py"
    spec = importlib.util.spec_from_file_location("sip_demo_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.e2e
def test_foundation_portability_demonstration(tmp_path: Path) -> None:
    """REQ: PLTIO-003, PLTIO-006, PLTIO-012, OPSDR-005 open export and clean restore preserve identity."""
    report = _demo_module().foundation(tmp_path / "foundation")
    assert report["preservation"]["matching_root_hash"] is True
    assert report["preservation"]["restored_assets"] >= 1
    assert report["preservation"]["operational_replay"]["matches_package"] is True
    assert report["acceptance"]["retry_resume_proved"] is True
    assert report["acceptance"]["cancel_proved"] is True
    assert report["durable_operation"]["attempts"] == 2
    assert report["cancellation"]["state"] == "cancelled"


@pytest.mark.e2e
def test_demo_evidence_wrapper_serializes_temporal_values_and_hashes_exact_report(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 retained demo evidence is strict JSON and hash-verifiable."""
    module = _demo_module()
    report = module.run("foundation", output=tmp_path / "foundation-evidence")
    assert report["status"] == "passed", report["error"]
    recorded_at = report["result"]["scene"]["metric_commit"]["recorded_at"]
    assert isinstance(recorded_at, str)
    retained_hash = report["evidence_hash"]
    hash_input = dict(report)
    del hash_input["evidence_hash"]
    assert module.canonical_sha256(hash_input) == retained_hash
    artifact_paths = [artifact["path"] for artifact in report["artifacts"]]
    assert artifact_paths
    assert all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in artifact_paths)
    assert all(str(tmp_path) not in path for path in artifact_paths)
    stored = json.loads((tmp_path / "foundation-evidence" / "demo-report.json").read_text(encoding="utf-8"))
    assert stored == report


@pytest.mark.e2e
def test_hybrid_representation_demonstration(tmp_path: Path) -> None:
    """REQ: HYBRUN-003, RECHYB-002, RECHYB-005, RECMESH-010 hybrid authority survives proxy replacement."""
    report = _demo_module().hybrid(tmp_path / "hybrid")
    assert report["direct_proxy_measurement_blocked"] is True
    assert report["acceptance"]["proxy_hit_re_resolved"] is True
    assert len(report["replacement"]["reprojected_anchor_ids"]) >= 1
    assert report["acceptance"]["unresolved_anchor_reported"] is True
    assert report["scene"]["before_replacement_commit"]["commit_id"] != report["scene"]["after_replacement_commit"]["commit_id"]


@pytest.mark.e2e
def test_scene_runtime_review_demonstration(tmp_path: Path) -> None:
    """REQ: PLTVIEW-001, PLTVIEW-003, RECCHANG-001, RECCHANG-002, RECCHANG-003, RECCHANG-004 deterministic scene review preserves truth and independent approval."""
    report = _demo_module().scene_runtime(tmp_path / "scene-runtime")
    acceptance = report["acceptance"]
    assert acceptance["session_immutable"] is True
    assert acceptance["capability_material_absent"] is True
    assert acceptance["unobserved_removal_suppressed"] is True
    assert acceptance["lighting_difference_suppressed"] is True
    assert acceptance["independent_review_recorded"] is True
    assert acceptance["semantic_event_created"] is True
    assert acceptance["controlled_commit_created"] is True
    assert acceptance["quantitative_benchmark_retained"] is True
    assert acceptance["production_claimed"] is False


@pytest.mark.e2e
def test_mesh_splat_surface_roundtrip_reports_irreversible_loss() -> None:
    """REQ: HYBTEST-015, RECBIDI-003, RECBIDI-008 conversion never claims representation equivalence."""
    vertices = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=float,
    )
    faces = np.asarray([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=int)
    visual = mesh_to_splats(vertices, faces, samples=64, seed=9)
    surface = splats_to_surface(np.asarray(visual["positions"]))
    for converted in (visual, surface):
        assert converted["lossy"] is True
        assert converted["representation_equivalent"] is False
        assert converted["information_loss"]
    assert visual["authority"] == "visual_non_metric"
    assert surface["authority"] == "derived_non_authoritative"
    assert "verified_measurement" in surface["prohibited_uses"]


@pytest.mark.e2e
@pytest.mark.security
def test_malformed_spatial_archive_is_bounded_and_cannot_publish(bootstrapped, tmp_path: Path) -> None:
    """REQ: HYBTEST-016, TSTLAY-002, TSTSEC-003 adversarial archives fail before any publication side effect."""
    context, _tenant_id, _project_id, _actor = bootstrapped
    with context.database.session() as session:
        before = session.scalar(select(func.count()).select_from(RepresentationAssetRow))

    traversal = tmp_path / "traversal.sipcapture"
    with zipfile.ZipFile(traversal, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"schema_version": "1.0.0"}))
        archive.writestr("../escaped.bin", b"not allowed")
    with pytest.raises(ValidationError) as traversal_error:
        CapturePackage.validate(traversal)
    assert traversal_error.value.code == "ARCHIVE_PATH_UNSAFE"

    bomb = tmp_path / "compression-bomb.sipcapture"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", b"0" * 2_000_000)
    with pytest.raises(ValidationError) as bomb_error:
        CapturePackage.validate(bomb)
    assert bomb_error.value.code == "ARCHIVE_COMPRESSION_RATIO"

    with context.database.session() as session:
        after = session.scalar(select(func.count()).select_from(RepresentationAssetRow))
    assert after == before == 0
