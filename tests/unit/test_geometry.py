from __future__ import annotations

import numpy as np
import pytest

from sip.errors import ValidationError
from sip.geometry import (
    SimilarityTransform,
    change_detection,
    interaction_proxy,
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
