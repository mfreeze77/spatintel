from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings
from sip.worker_runtime import REGISTRY

ROOT = Path(__file__).resolve().parents[2]
SERVICES = {
    "control-api", "identity-policy", "capture-service", "workflow-service", "scene-service", "evidence-service",
    "search-service", "export-service", "notification-service", "audit-service", "representation-api",
    "provider-registry", "representation-publisher",
}

@pytest.mark.contract
def test_service_entrypoints_and_manifests_match_openapi(tmp_path: Path) -> None:
    # A service boundary changes route ownership, not persistence semantics.
    # Reuse one fully migrated context so this contract test validates all
    # logical boundaries without repeating the same database migration thirteen
    # times. Each app still receives a distinct ``service_name`` and therefore
    # generates its independently scoped OpenAPI surface.
    context = PlatformContext.create(temporary_settings(tmp_path / "shared-context"))
    for service in SERVICES:
        directory = ROOT / "services" / service
        assert (directory / "main.py").is_file()
        manifest = json.loads((directory / "service.json").read_text())
        app = create_app(context=context, service_name=service)
        actual = sorted(
            (method.upper(), path, operation.get("operationId"))
            for path, methods in app.openapi()["paths"].items()
            for method, operation in methods.items()
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        )
        expected = sorted((item["method"], item["path"], item["operation_id"]) for item in manifest["operations"])
        assert actual == expected
        assert manifest["logical_boundary"] is True

@pytest.mark.contract
def test_worker_manifests_reference_only_registered_capabilities() -> None:
    worker_dirs = [path for path in (ROOT / "workers").iterdir() if path.is_dir()]
    assert worker_dirs
    for directory in worker_dirs:
        manifest = json.loads((directory / "worker.json").read_text())
        assert set(manifest["capabilities"]).issubset(REGISTRY.operation_types)
        assert manifest["durable"] and manifest["idempotent"] and manifest["cancellable"]
