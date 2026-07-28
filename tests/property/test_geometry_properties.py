from __future__ import annotations

import numpy as np
import pytest

from sip.geometry import SimilarityTransform, umeyama


@pytest.mark.property
def test_similarity_estimator_round_trips_seeded_metric_transforms() -> None:
    """REQ: RECALIGN-001 metric similarity estimation preserves known transforms."""
    for seed in range(12):
        rng = np.random.default_rng(seed)
        source = rng.normal(size=(40, 3))
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        angle = float(rng.uniform(-1.2, 1.2))
        skew = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
        rotation = np.eye(3) + np.sin(angle) * skew + (1 - np.cos(angle)) * (skew @ skew)
        scale = float(rng.uniform(0.4, 2.5))
        translation = rng.normal(size=3)
        target = (scale * (rotation @ source.T)).T + translation
        recovered = umeyama(source, target, estimate_scale=True)
        assert isinstance(recovered, SimilarityTransform)
        assert recovered.scale == pytest.approx(scale, rel=1e-10, abs=1e-10)
        assert np.max(np.abs(recovered.apply(source) - target)) < 1e-9
