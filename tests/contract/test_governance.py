from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sip.errors import AuthorizationError
from sip.models import Classification
from sip.provider_sdk import (
    DeniedExternalProvider,
    DeterministicRegistrationProvider,
    DeterministicRepresentationProvider,
    ProviderExecutionContext,
)
from tools.check_governance import validate

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_source_model_provider_governance_is_fail_closed() -> None:
    report = validate()
    assert report["status"] == "passed", report
    assert report["model_count"] >= 1
    assert report["unmanifested_model_file_count"] == 0
    lingbot = (ROOT / "third_party/models/lingbot-map-checkpoint.json").read_text()
    assert '"approval_state": "denied"' in lingbot


@pytest.mark.security
def test_denied_provider_cannot_execute() -> None:
    with pytest.raises(AuthorizationError) as caught:
        DeniedExternalProvider("hosted-manual-tool", "not audited").execute({"secret": True})
    assert caught.value.code == "PROVIDER_EXECUTION_DENIED"


@pytest.mark.unit
def test_reference_provider_protocols_are_deterministic_and_lossy_outputs_non_authoritative() -> None:
    context = ProviderExecutionContext(
        tenant_id="tenant",
        project_id="project",
        purpose="synthetic_evaluation",
        classification=Classification.PUBLIC,
    )
    source = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    target = source + np.asarray([2, -1, 3])
    estimate, inliers = DeterministicRegistrationProvider().register(
        source, target, estimate_scale=False, threshold_m=0.001, seed=9, context=context
    )
    assert inliers.all()
    assert np.allclose(estimate.apply(source), target)

    vertices = source
    faces = np.asarray([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=int)
    provider = DeterministicRepresentationProvider()
    visual = provider.mesh_to_visual(vertices, faces, samples=16, seed=3, context=context)
    assert visual["lossy"] is True and visual["authority"] == "visual_non_metric"
    proxy = provider.visual_to_interaction(np.asarray(visual["positions"]), context=context)
    assert proxy["lossy"] is True and proxy["authority"] == "derived_non_authoritative"
    assert "verified_measurement" in proxy["prohibited_uses"]
