from __future__ import annotations

from pathlib import Path

import pytest

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass


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
    # Positive-path legacy fixtures now reference real immutable assets. Negative
    # probes deliberately use names such as MISSING-*, nonexistent-*, cross-*,
    # or tombstoned-* and are intentionally absent from this allow-list.
    synthetic_asset_ids = {
        "asset-source", "birth-record", "capture-baseline", "cutsheet-ahu",
        "interview-a", "interview-b", "photo-after", "photo-before", "photo-door",
        "photo-facp", "photo-kitchen", "photo-nameplate", "photo-panel",
        "synthetic-audio", "synthetic-controller-photo", "synthetic-correction",
        "synthetic-dispute-statement", "synthetic-family-record", "synthetic-interview-a",
        "synthetic-interview-b", "synthetic-interview.wav", "synthetic-observation-b",
        "synthetic-photo", "synthetic-radio-manual", "synthetic-radio-photo",
        "synthetic-retest", "synthetic-room-photo", "synthetic-signed-consent",
        "synthetic-source", "synthetic-source-a", "synthetic-source-b", "test-record",
        "trend-sat",
    }
    for asset_id in sorted(synthetic_asset_ids):
        payload = f"fixture:{asset_id}".encode("utf-8")
        context.assets.ingest_bytes(
            tenant_id=tenant_id, project_id=project_id, data=payload,
            media_type="application/octet-stream", original_name=asset_id,
            classification=Classification.INTERNAL, retention_class="test-fixture",
            source_class=SourceClass.DIRECT_CAPTURE, authority_class=AuthorityClass.EVIDENCE,
            provenance=ProvenanceRef(source_ids=[f"fixture:{asset_id}"], output_hash=sha256_bytes(payload)),
            actor_id="fixture-builder", asset_id=asset_id,
        )
    return context, tenant_id, project_id, "admin-fixture"


@pytest.fixture
def minimal_bootstrapped(context: PlatformContext):
    """A clean tenant/project without the positive-path compatibility asset corpus."""
    tenant_id = context.tenancy.create_tenant(
        "Minimal Fixture Tenant", tenant_id="tenant-minimal-fixture", actor_id="system"
    )
    project_id = context.tenancy.create_project(
        tenant_id,
        "Minimal Fixture Project",
        vertical="platform",
        classification="internal",
        project_id="project-minimal-fixture",
        actor_id="admin-minimal-fixture",
    )
    return context, tenant_id, project_id, "admin-minimal-fixture"
