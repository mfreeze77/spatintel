from __future__ import annotations

import numpy as np
import pytest

from sip.errors import ValidationError
from sip.geometry import (
    change_detection,
    cleanup_mesh,
    compose_mesh_representations,
    interaction_proxy,
    mesh_quality_report,
    mesh_to_splats,
    ransac_similarity,
    splats_to_surface,
    unproject_depth,
    voxel_fuse,
)


@pytest.mark.unit
def test_recalign_001_ransac_recovers_metric_sim3_with_outliers() -> None:
    rng = np.random.default_rng(5)
    source = rng.normal(size=(100, 3))
    angle = 0.3
    rotation = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    target = (1.25 * (rotation @ source.T)).T + np.array([2.0, -0.5, 1.0])
    target[:10] += 10
    transform, mask = ransac_similarity(source, target, threshold_m=0.02, iterations=400, seed=7)
    assert transform.scale == pytest.approx(1.25, rel=1e-5)
    assert transform.inlier_count == 90
    assert int(mask.sum()) == 90


@pytest.mark.unit
def test_recdepth_rectsdf_source_aware_depth_fusion_and_uncertainty() -> None:
    depth = np.array([[1.0, 1.0], [1.0, 10.0]])
    confidence = np.array([[2, 2], [0, 2]], dtype=np.uint8)
    intrinsics = np.array([[1, 0, 0.5], [0, 1, 0.5], [0, 0, 1]], dtype=float)
    points, weights = unproject_depth(depth, intrinsics, np.eye(4), confidence=confidence, minimum_confidence=1, max_depth_m=5)
    assert len(points) == 2
    fused = voxel_fuse([points], [weights], voxel_size_m=0.1)
    assert len(fused["points"]) == 2
    assert np.all(fused["uncertainty_m"] > 0)


@pytest.mark.unit
def test_recbidi_rechyb_lossy_proxy_never_authoritative() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    proxy = interaction_proxy(vertices, faces)
    assert proxy["authoritative"] is False
    assert "verified_measurement" in proxy["prohibited_uses"]
    splats = mesh_to_splats(vertices, faces, samples=64, seed=4)
    assert splats["lossy"] is True
    surface = splats_to_surface(splats["positions"])
    assert surface["authoritative"] is False
    assert surface["lossy"] is True


@pytest.mark.unit
def test_recchang_temporal_change_detection() -> None:
    reference = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    comparison = np.array([[0, 0, 0], [1, 0, 0], [3, 0, 0]], dtype=float)
    result = change_detection(reference, comparison, threshold_m=0.2)
    assert result["added_indices"] == [2]
    assert result["removed_indices"] == [2]


@pytest.mark.unit
def test_cleanup_mesh_deduplicates_faces_without_destroying_winding() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2], [2, 1, 0]])
    clean = cleanup_mesh(vertices, faces)
    assert len(clean["faces"]) == 1
    a, b, c = clean["vertices"][clean["faces"][0]]
    assert np.cross(b - a, c - a)[2] > 0


@pytest.mark.unit
def test_mesh_quality_report_exposes_open_boundaries_and_color_coverage() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]], dtype=float)
    report = mesh_quality_report(vertices, faces, vertex_colors=colors)
    assert report["surface_area_m2"] == pytest.approx(1.0)
    assert report["boundary_edge_count"] == 4
    assert report["nonmanifold_edge_count"] == 0
    assert report["watertight"] is False
    assert report["vertex_color_coverage"] == pytest.approx(0.75)


@pytest.mark.unit
def test_mesh_composition_preserves_metric_visual_and_interaction_lanes() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]])
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=float)
    result = compose_mesh_representations(
        vertices,
        faces,
        vertex_colors=colors,
        splat_samples=64,
        lod_target_faces=4,
        seed=7,
    )
    assert result["metric"]["authority"] == "metric_unverified"
    assert result["visual"]["authority"] == "visual_non_metric"
    assert len(result["visual"]["colors"]) == 64
    assert result["interaction"]["authoritative"] is False
    assert result["composition"]["authority_lanes_preserved"] is True
    assert result["quality"]["watertight"] is True


@pytest.mark.unit
def test_mesh_to_splats_rejects_nonpositive_sample_count() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    with pytest.raises(ValidationError) as exc:
        mesh_to_splats(vertices, np.array([[0, 1, 2]]), samples=0)
    assert exc.value.code == "SPLAT_SAMPLE_COUNT_INVALID"
