from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"


def _node(*args: str) -> str:
    completed = subprocess.run(
        ["node", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout + completed.stderr


def test_pltview_007_reference_layer_contract_is_implemented_but_not_viewer_integrated() -> None:
    """REQ: PLTVIEW-007 reference layer implementation exists; mounted viewer integration remains unverified."""
    viewer = (WEB / "components/HybridViewer.tsx").read_text(encoding="utf-8")
    canvas = (WEB / "components/HybridCanvas.tsx").read_text(encoding="utf-8")
    runtime = (WEB / "lib/spatial-runtime.ts").read_text(encoding="utf-8")

    assert "<HybridCanvas layers={layers}" in viewer
    assert "buildLayerRenderDirectives(layers, comparisonSplit)" in canvas
    assert 'layerDirective(directives, "metric")' in canvas
    assert 'layerDirective(directives, "visual")' in canvas
    assert 'layerDirective(directives, "design")' in canvas
    assert 'layerDirective(directives, "interaction")' in canvas
    assert 'layerDirective(directives, "evidence")' in canvas
    assert "interactionDirective.pickable" in canvas
    assert "interaction.userData.authorized" in canvas
    assert "LAYER_AUTHORIZATION_DENIED" in runtime
    assert "evidence / immutable source record" in runtime

    output = _node(
        "--test",
        "--test-name-pattern=PLTVIEW-007",
        "apps/web/test/runtime.test.mjs",
    )
    assert "PLTVIEW-007 reference layer directives cover visibility opacity labels and pickability" in output
    assert "# pass 1" in output


def test_pltview_005_accessibility_controls_and_semantic_fallback_are_executable() -> None:
    """REQ: PLTVIEW-005 keyboard, semantic metadata, captions, reduced motion, and contrast controls are executable."""
    viewer = (WEB / "components/HybridViewer.tsx").read_text(encoding="utf-8")
    canvas = (WEB / "components/HybridCanvas.tsx").read_text(encoding="utf-8")
    for required in (
        "Arrow keys or W A S D navigate",
        "Reduced motion",
        "High contrast",
        "Captions and semantic alternatives enabled",
        'aria-label="Semantic scene tree"',
    ):
        assert required in viewer
    assert 'className="sr-only"' in canvas
    assert "Semantic scene navigation and evidence remain available" in canvas

    runtime_output = _node(
        "--test",
        "--test-name-pattern=semantic fallback and keyboard navigation",
        "apps/web/test/runtime.test.mjs",
    )
    assert "# pass 1" in runtime_output
    source_output = _node("apps/web/scripts/verify-source.mjs")
    assert '"status":"passed"' in source_output
