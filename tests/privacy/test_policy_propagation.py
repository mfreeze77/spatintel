from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sip.models import Audience, SourceClass


@pytest.mark.privacy
def test_liveforever_revocation_removes_derivative_from_all_affected_audiences(bootstrapped) -> None:
    """REQ: LIFCONS-002, TSTSEC-002 consent revocation propagates to indexed and derivative records."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "person-policy-fixture"
    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        granted_by=subject,
        purposes=["family_review", "preservation"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["*"],
        derivative_policy={"generated_visual": True, "voice": False, "likeness": False},
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    record_id = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="generated_reconstruction",
        subject_id=subject,
        related_ids=[],
        data={"description": "synthetic reconstruction"},
        source_class=SourceClass.GENERATED,
        confidence=0.5,
        evidence_asset_ids=["asset-source"],
        audience=Audience.FAMILY,
        actor_id=actor,
        generated_lineage={
            "model_manifest_id": "synthetic-approved",
            "model_checkpoint_hash": "1" * 64,
            "prompt_hash": "2" * 64,
            "input_asset_ids": ["asset-source"],
            "output_hash": "3" * 64,
        },
    )
    before = context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review")
    assert record_id in {item["record_id"] for item in before["records"]}
    context.liveforever.revoke_consent(grant_id, tenant_id=tenant_id, project_id=project_id, actor_id=subject, reason="fixture revocation")
    after = context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review")
    assert record_id not in {item["record_id"] for item in after["records"]}
