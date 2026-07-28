from __future__ import annotations

import pytest

from sip.errors import NotFoundError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass


@pytest.mark.security
@pytest.mark.integration
def test_tstsec_cross_tenant_asset_access_is_indistinguishable_from_missing(context) -> None:
    one = context.tenancy.create_tenant("One", tenant_id="tenant-one")
    two = context.tenancy.create_tenant("Two", tenant_id="tenant-two")
    p1 = context.tenancy.create_project(one, "P1", vertical="platform", classification="internal", project_id="project-one", actor_id="admin")
    p2 = context.tenancy.create_project(two, "P2", vertical="platform", classification="internal", project_id="project-two", actor_id="admin")
    asset = context.assets.ingest_bytes(
        tenant_id=one,
        project_id=p1,
        data=b"tenant-one-secret",
        media_type="application/octet-stream",
        original_name="secret.bin",
        classification=Classification.RESTRICTED,
        retention_class="record",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture"]),
        actor_id="admin",
    )
    with pytest.raises(NotFoundError):
        context.assets.read(two, p2, asset.asset_id, actor_id="attacker")
