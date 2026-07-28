from __future__ import annotations

from pathlib import Path

import pytest

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings


@pytest.mark.parametrize(
    ("service", "required_prefix", "forbidden_prefix"),
    [
        ("capture-service", "/v1/projects/{project_id}/assets", "/v1/projects/{project_id}/scenes"),
        ("workflow-service", "/v1/projects/{project_id}/operations", "/v1/providers"),
        ("scene-service", "/v1/projects/{project_id}/scenes", "/v1/projects/{project_id}/assets"),
        ("provider-registry", "/v1/providers", "/v1/representations/{representation_id}/publish"),
        ("representation-publisher", "/v1/representations/{representation_id}/publish", "/v1/providers"),
    ],
)
def test_logical_service_exposes_only_owned_contracts(
    tmp_path: Path, service: str, required_prefix: str, forbidden_prefix: str
) -> None:
    context = PlatformContext.create(temporary_settings(tmp_path / service))
    paths = create_app(context=context, service_name=service).openapi()["paths"]
    assert required_prefix in paths
    assert forbidden_prefix not in paths
