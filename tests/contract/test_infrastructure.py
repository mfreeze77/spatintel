from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _validator():
    path = ROOT / "tools/validate_infrastructure.py"
    spec = importlib.util.spec_from_file_location("validate_infrastructure", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_infrastructure_structural_policy_gate() -> None:
    """REQ: ARCDEP-002 generated infrastructure must satisfy static policy gates."""
    report = _validator().run(release=False)
    assert report["status"] == "passed", report["findings"]
    assert report["errors"] == 0
    assert report["counts"]["kubernetes"]["workloads"] >= 20
    assert report["counts"]["compose"]["services"] >= 20
    assert report["counts"]["terraform"]["resources"] >= 25


def test_release_gate_fails_closed_before_images_and_outputs_exist() -> None:
    """REQ: ARCDEP-002, OPSCICD-003 release must fail closed until CI replaces digests and Terraform outputs."""
    report = _validator().run(release=True)
    assert report["status"] == "failed"
    codes = {finding["code"] for finding in report["findings"] if finding["severity"] == "error"}
    assert "K8S_IMAGE_SENTINEL" in codes
    assert "K8S_AWS_OUTPUT_PLACEHOLDER" in codes


def test_compose_workers_have_private_staging_volumes() -> None:
    """REQ: PLTGRPC-004 workers may write only to identity-private staging storage."""
    import yaml

    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    sources: list[str] = []
    for name, service in services.items():
        if not name.startswith("worker-"):
            continue
        mounts = [str(item).split(":") for item in service.get("volumes", [])]
        runtime = [parts for parts in mounts if len(parts) >= 2 and parts[1] == "/var/lib/sip/runtime"]
        assert runtime == [[f"{name}-runtime", "/var/lib/sip/runtime"]]
        sources.append(runtime[0][0])
    assert len(sources) == 16
    assert len(set(sources)) == len(sources)
