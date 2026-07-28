from __future__ import annotations

from pathlib import Path

import pytest

from sip.context import PlatformContext, temporary_settings


@pytest.fixture
def context(tmp_path: Path) -> PlatformContext:
    return PlatformContext.create(temporary_settings(tmp_path / "runtime"))


@pytest.fixture
def bootstrapped(context: PlatformContext):
    tenant_id = context.tenancy.create_tenant("Fixture Tenant", tenant_id="tenant-fixture", actor_id="system")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Fixture Project",
        vertical="platform",
        classification="internal",
        project_id="project-fixture",
        actor_id="admin-fixture",
    )
    return context, tenant_id, project_id, "admin-fixture"
