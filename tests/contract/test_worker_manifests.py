from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from sip.errors import ValidationError
from sip.worker_manifest import load_worker_manifest
from sip.worker_runtime import REGISTRY, _verify_runtime_deployment_contract

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_worker_manifests_are_immutable_least_privilege_and_cover_registry() -> None:
    """REQ: PLTGRPC-001, PLTSDK-003, HYBAPI-003, HYBAPI-004, TSTLAY-004."""
    manifests = [load_worker_manifest(path, repository_root=ROOT) for path in sorted((ROOT / "workers").glob("*/worker-manifest.json"))]
    assert manifests
    identities = {manifest.workload_identity for manifest in manifests}
    assert len(identities) == len(manifests)
    declared = {capability for manifest in manifests for capability in manifest.capabilities}
    assert declared == set(REGISTRY.operation_types)
    for manifest in manifests:
        assert manifest.shell_access is False
        assert manifest.network_access is False
        assert manifest.publication_permission is False
        assert manifest.output_mode == "quarantine_candidate"
        assert manifest.least_privilege is True
        assert manifest.manifest_sha256 == manifest.calculated_digest()
        assert manifest.resource_limits.max_wall_seconds > 0
        assert manifest.resource_limits.max_memory_bytes > 0


@pytest.mark.contract
def test_worker_manifest_json_schema_accepts_every_committed_manifest() -> None:
    schema = json.loads((ROOT / "schemas/jsonschema/worker-manifest.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json")):
        errors = sorted(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))), key=lambda item: list(item.path))
        assert not errors, f"{path}: {[error.message for error in errors]}"


@pytest.mark.security
def test_worker_manifest_tampering_fails_before_execution(tmp_path: Path) -> None:
    source = ROOT / "workers/pose-optimizer/worker-manifest.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["capabilities"].append("report.export")
    tampered = tmp_path / "worker-manifest.json"
    tampered.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_worker_manifest(tampered, verify_files=False)
    assert exc.value.code == "WORKER_MANIFEST_INVALID"


@pytest.mark.contract
def test_worker_entrypoints_do_not_accept_runtime_capability_injection() -> None:
    for path in sorted((ROOT / "workers").glob("*/main.py")):
        source = path.read_text(encoding="utf-8")
        assert "worker-manifest.json" in source
        assert "--manifest" in source
        assert "--capability" not in source


@pytest.mark.security
def test_production_worker_requires_exact_deployment_bindings() -> None:
    """REQ: PLTGRPC-004 production worker identity and denial controls fail closed."""
    manifest = load_worker_manifest(ROOT / "workers/fusion-tsdf/worker-manifest.json", repository_root=ROOT)
    correct = {
        "SIP_WORKLOAD_IDENTITY": manifest.workload_identity,
        "SIP_WORKER_MANIFEST_SHA256": manifest.manifest_sha256,
        "SIP_WORKER_PUBLICATION_PERMISSION": "false",
        "SIP_WORKER_COMPUTE_NETWORK_ACCESS": "denied",
    }
    _verify_runtime_deployment_contract(manifest, production=True, environment=correct)
    for key in correct:
        broken = dict(correct)
        broken.pop(key)
        with pytest.raises(Exception) as exc:
            _verify_runtime_deployment_contract(manifest, production=True, environment=broken)
        assert getattr(exc.value, "code", None) == "WORKER_DEPLOYMENT_CONTRACT_MISMATCH"
    broken = dict(correct, SIP_WORKER_PUBLICATION_PERMISSION="true")
    with pytest.raises(Exception) as exc:
        _verify_runtime_deployment_contract(manifest, production=True, environment=broken)
    assert getattr(exc.value, "code", None) == "WORKER_DEPLOYMENT_CONTRACT_MISMATCH"
