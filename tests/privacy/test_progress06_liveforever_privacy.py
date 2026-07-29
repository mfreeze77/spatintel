from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sip.database import LiveForeverDerivativeRow
from sip.errors import AuthorizationError
from sip.models import Audience, SourceClass


@pytest.mark.privacy
@pytest.mark.integration
def test_progress06_revocation_withholds_memory_room_interviews_editions_and_derivatives(bootstrapped) -> None:
    """REQ: LIFCONS-002, LIFCONS-005, LIFGRAPH-005, LIFGRAPH-006, LIFINT-004 revocation and audience policy propagate through the navigable memory-room experience."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "synthetic-memory-room-subject"
    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id, project_id=project_id, subject_id=subject, granted_by=subject,
        purposes=["preservation", "family_review"], audiences=[Audience.PRIVATE, Audience.FAMILY],
        scopes=["*"], derivative_policy={"local_only": True, "voice": False, "likeness": False},
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    memory_id = context.liveforever.create_record(
        tenant_id=tenant_id, project_id=project_id, record_type="memory", subject_id=subject,
        related_ids=[], data={"title": "Synthetic memory", "time_expression": {"kind": "approximate", "year": 1980}},
        source_class=SourceClass.RECALLED, confidence=0.6, evidence_asset_ids=[],
        audience=Audience.FAMILY, actor_id=actor, purpose="family_review",
    )
    interview = context.liveforever.create_interview(
        tenant_id=tenant_id, project_id=project_id, subject_id=subject,
        participants=[{"person_id": subject, "role": "narrator"}],
        consent_context={"confirmed": True, "grant_id": grant_id}, recording_state="stopped",
        source_media_ids=["synthetic-audio"], timeline={"started_ms": 0, "ended_ms": 2000},
        device={"type": "synthetic"}, environment={"location": "synthetic-room"}, interruptions=[],
        question_lineage=[{"source": "human", "text": "Tell me about the room."}],
        pacing_policy={"pause_allowed": True, "skip_allowed": True, "stop_allowed": True},
        actor_id=actor, idempotency_key="privacy-interview", complete=True,
    )
    context.liveforever.add_transcript_segment(
        interview["interview_id"], tenant_id=tenant_id, project_id=project_id, segment_index=0,
        start_ms=0, end_ms=2000, speaker_label="Narrator", speaker_confidence=0.99,
        original_text="A synthetic private recollection.", source_media_id="synthetic-audio",
        spatial_anchor={"entity_id": "synthetic-object"},
        private_marks=[{"start": 2, "end": 11, "reason": "family-private"}],
        followup_suggestions=[], actor_id=actor,
    )
    edition = context.liveforever.create_edition(
        tenant_id=tenant_id, project_id=project_id, name="Family edition", audience=Audience.FAMILY,
        purpose="family_review", presentation_choices={"evidence_first": True}, scene_commit_id=None,
        narrative_path=[{"record_id": memory_id}], policy_snapshot={"grant_ids": [grant_id]},
        actor_id=actor, idempotency_key="privacy-edition", publish=True,
    )
    derivative = context.liveforever.register_derivative(
        tenant_id=tenant_id, project_id=project_id, derivative_type="generated_reconstruction",
        source_ids=[memory_id], subject_ids=[subject], consent_grant_ids=[grant_id],
        audience=Audience.FAMILY, classification="private-family", retention={"class": "family-preservation"},
        provider={"execution": "local", "provider_id": "synthetic-local"},
        generation_lineage={
            "model_manifest_id": "synthetic-approved", "model_checkpoint_hash": "1" * 64,
            "prompt_hash": "2" * 64, "input_asset_ids": [memory_id], "output_hash": "3" * 64,
        },
        policy={"purpose": "family_review"}, actor_id=actor, idempotency_key="privacy-derivative",
    )

    before = context.liveforever.memory_room(
        tenant_id, project_id, subject_id=subject, audience=Audience.FAMILY, purpose="family_review"
    )
    assert before["edition"]["edition_id"] == edition["edition_id"]
    assert before["interviews"] and before["interviews"][0]["segments"][0]["private_marks"] == []
    assert before["interviews"][0]["segments"][0]["private_marks_withheld"] is True
    with pytest.raises(AuthorizationError) as private_marks:
        context.liveforever.memory_room(
            tenant_id, project_id, subject_id=subject, audience=Audience.FAMILY,
            purpose="family_review", include_private_transcript_marks=True,
        )
    assert private_marks.value.code == "PRIVATE_TRANSCRIPT_MARKS_DENIED"

    revocation = context.liveforever.revoke_consent(grant_id, actor_id=subject, reason="synthetic withdrawal")
    assert revocation["affected_derivatives"] == 1
    after = context.liveforever.memory_room(
        tenant_id, project_id, subject_id=subject, audience=Audience.FAMILY, purpose="family_review"
    )
    assert after["records"] == []
    assert after["interviews"] == []
    assert after["interviews_withheld_by_current_policy"] is True
    assert after["edition"] is None
    assert after["edition_withheld_by_current_policy"] is True
    with context.database.session() as session:
        row = session.get(LiveForeverDerivativeRow, derivative["derivative_id"])
        assert row is not None
        assert row.state == "withdrawn"
        assert row.withdrawal_action == "disable_access_and_queue_deletion_review"
        assert row.policy_json["access_disabled"] is True


@pytest.mark.privacy
@pytest.mark.security
def test_progress06_external_provider_requires_complete_scope_bound_approval(bootstrapped) -> None:
    """REQ: LIFCONS-001, LIFMEDIA-006, LIFHYB-008 external derivative execution requires complete classification, purpose, region, retention, and receipt approval."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "synthetic-provider-subject"
    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id, project_id=project_id, subject_id=subject, granted_by=subject,
        purposes=["preservation"], audiences=[Audience.PRIVATE], scopes=["visual_reconstruction"],
        derivative_policy={"external": False}, expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    common = dict(
        tenant_id=tenant_id, project_id=project_id, derivative_type="visual_reconstruction",
        source_ids=["synthetic-source"], subject_ids=[subject], consent_grant_ids=[grant_id],
        audience=Audience.PRIVATE, classification="private-family", retention={"class": "preservation"},
        generation_lineage={
            "model_manifest_id": "synthetic-approved", "model_checkpoint_hash": "a" * 64,
            "prompt_hash": "b" * 64, "input_asset_ids": ["synthetic-source"], "output_hash": "c" * 64,
        }, policy={"purpose": "preservation"}, actor_id=actor,
    )
    with pytest.raises(AuthorizationError) as incomplete:
        context.liveforever.register_derivative(
            **common, provider={"execution": "external", "approved": True},
            idempotency_key="external-incomplete",
        )
    assert incomplete.value.code == "EXTERNAL_PROVIDER_APPROVAL_INCOMPLETE"
    with pytest.raises(AuthorizationError) as classification:
        context.liveforever.register_derivative(
            **common,
            provider={
                "execution": "external", "approved": True, "provider_id": "synthetic-hosted",
                "approval_receipt_sha256": "d" * 64, "approved_region": "us-test-1", "retention_days": 0,
                "allowed_classifications": ["public"], "allowed_purposes": ["preservation"],
            },
            idempotency_key="external-classification-denied",
        )
    assert classification.value.code == "EXTERNAL_PROVIDER_CLASSIFICATION_DENIED"
