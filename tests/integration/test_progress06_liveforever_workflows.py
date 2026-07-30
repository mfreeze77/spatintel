from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.database import MemoryRecordRow
from sip.errors import AuthorizationError, ValidationError
from sip.models import Audience, SourceClass


def _grant(context, tenant_id: str, project_id: str, subject: str) -> str:
    return context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        granted_by=subject,
        purposes=["preservation", "family_review"],
        audiences=[Audience.PRIVATE, Audience.FAMILY, Audience.PUBLIC],
        scopes=["*"],
        derivative_policy={"local_only": True, "generated_visual": True, "voice": False, "likeness": False},
        expires_at=datetime.now(UTC) + timedelta(days=3650),
    )


@pytest.mark.integration
def test_progress06_liveforever_graph_truth_labels_conflicts_and_immutable_family_correction(bootstrapped) -> None:
    """REQ: LIFGRAPH-001, LIFGRAPH-002, LIFGRAPH-003, LIFGRAPH-004, LIFGRAPH-005, LIFPLACE-001, LIFPLACE-002, LIFPLACE-003, LIFPLACE-005, LIFLABEL-001, LIFLABEL-002, LIFDISP-002, LIFDISP-004, LIFDISP-005 graph records retain governed uncertainty, truth labels, provenance, alternatives, and immutable corrections."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "synthetic-graph-subject"
    grant = _grant(context, tenant_id, project_id, subject)

    person_source = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="person",
        subject_id=subject,
        related_ids=[],
        data={
            "name": "Avery Example",
            "aliases": ["A. Example"],
            "relationships": [],
            "identity_evidence": ["synthetic-family-record"],
            "biometric_template_required": False,
            "source_label": "source_document",
            "time_expression": {"kind": "bounded", "start": "1940-01-01", "end": "1940-12-31", "basis": "family record"},
            "themes": ["family"],
            "emotional_sensitivity": "low",
            "assertions": [{"claim": "preferred name", "evidence": ["synthetic-family-record"]}],
        },
        source_class=SourceClass.OBSERVED,
        confidence=0.8,
        evidence_asset_ids=["synthetic-family-record"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
    )
    person = context.liveforever.review_record(
        person_source, tenant_id=tenant_id, project_id=project_id,
        reviewer_id="family-independent-reviewer", target_source_class=SourceClass.CORROBORATED,
        rationale="Two immutable family records independently support the identity assertion.",
        evidence_asset_ids=["synthetic-family-record", "synthetic-signed-consent"], confidence=0.98,
        idempotency_key="graph-person-corroboration",
    )["reviewed_record_id"]
    place = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="place",
        subject_id=subject,
        related_ids=[person],
        data={
            "name": "The Blue Kitchen",
            "aliases": ["Grandma's kitchen"],
            "privacy": {"address_precision": "region_only", "public_address_withheld": True},
            "validity": {"kind": "bounded", "start": "1975", "end": "1992"},
            "scenes": ["synthetic-memory-room"],
            "maps": [{"kind": "schematic", "asset_id": "synthetic-map"}],
            "stories": [],
            "source_label": "direct_capture",
            "time_expression": {"kind": "qualitative", "label": "during the childhood years"},
        },
        source_class=SourceClass.OBSERVED,
        confidence=0.9,
        evidence_asset_ids=["synthetic-room-photo"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
    )
    object_source = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="object",
        subject_id=subject,
        related_ids=[place],
        data={
            "name": "Blue tabletop radio",
            "physical_description": {"color": "blue", "material": "plastic"},
            "custody_history": [{"holder": subject, "period": "1980s"}],
            "spatial_anchor": {"frame_id": "synthetic-memory-room", "point": [1.2, 0.8, 0.9], "uncertainty_m": 0.08},
            "photographs": ["synthetic-radio-photo"],
            "documents": ["synthetic-radio-manual"],
            "preservation_status": "stored",
            "source_label": "source_document",
            "time_expression": {"kind": "unknown", "basis": "date not documented"},
        },
        source_class=SourceClass.OBSERVED,
        confidence=0.75,
        evidence_asset_ids=["synthetic-radio-photo", "synthetic-radio-manual"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
    )
    obj = context.liveforever.review_record(
        object_source, tenant_id=tenant_id, project_id=project_id,
        reviewer_id="family-independent-reviewer", target_source_class=SourceClass.CORROBORATED,
        rationale="The photograph and manual independently identify the preserved radio.",
        evidence_asset_ids=["synthetic-radio-photo", "synthetic-radio-manual"], confidence=0.92,
        idempotency_key="graph-radio-corroboration",
    )["reviewed_record_id"]
    memory = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="memory",
        subject_id=subject,
        related_ids=[person, place, obj],
        data={
            "title": "Breakfast before school",
            "source_label": "first_person_recollection",
            "time_expression": {"kind": "approximate", "year": 1984, "confidence": 0.5},
            "themes": ["school", "family"],
            "emotional_sensitivity": "medium",
            "assertions": [{"claim": "the radio played weather reports", "status": "recalled"}],
        },
        source_class=SourceClass.RECALLED,
        confidence=0.65,
        evidence_asset_ids=["synthetic-interview-a"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
    )
    generated = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="generated_reconstruction",
        subject_id=subject,
        related_ids=[place, obj, memory],
        data={"title": "Illustrative kitchen reconstruction", "source_label": "generated"},
        source_class=SourceClass.GENERATED,
        confidence=0.4,
        evidence_asset_ids=["synthetic-room-photo"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
        generated_lineage={
            "model_manifest_id": "synthetic-approved-model",
            "model_checkpoint_hash": "a" * 64,
            "prompt_hash": "b" * 64,
            "input_asset_ids": ["synthetic-room-photo"],
            "output_hash": "c" * 64,
            "operator_decisions": ["kept source-constrained wall geometry", "marked unknown cabinet finish"],
        },
    )
    alternatives = context.liveforever.conflicting_recollections(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        event_key="synthetic-breakfast-weather",
        recollections=[
            {"recollector_id": subject, "account": "It was raining.", "confidence": 0.6, "evidence_asset_ids": ["synthetic-interview-a"]},
            {"recollector_id": "synthetic-witness", "account": "The sun was out by breakfast.", "confidence": 0.55, "evidence_asset_ids": ["synthetic-interview-b"]},
        ],
        audience=Audience.FAMILY,
        actor_id=actor,
    )
    assert len(alternatives) == 2

    with context.database.session() as session:
        original_before = session.get(MemoryRecordRow, memory)
        assert original_before is not None
        original_hash = context.liveforever._memory_payload(original_before)
    revision = context.liveforever.revise_record(
        memory,
        tenant_id=tenant_id,
        project_id=project_id,
        editor_id=subject,
        correction_type="alternate_interpretation",
        reason="The contributor now recalls the report may have been on television, not the radio.",
        changes={"assertions": [{"claim": "a weather report was playing", "status": "alternate_interpretation"}]},
        audience=Audience.FAMILY,
        purpose="family_review",
    )
    assert revision != memory
    with context.database.session() as session:
        original_after = session.get(MemoryRecordRow, memory)
        revision_row = session.get(MemoryRecordRow, revision)
        assert original_after is not None and revision_row is not None
        assert context.liveforever._memory_payload(original_after) == original_hash
        assert revision_row.data_json["revision_of"] == memory
        assert revision_row.data_json["correction"]["type"] == "alternate_interpretation"
        assert revision_row.data_json["source_label"] == "disputed"

    family_records = context.liveforever.visible_records(
        tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review", subject_id=subject
    )
    by_id = {item["record_id"]: item for item in family_records}
    assert by_id[memory]["data"]["time_expression"] == {
        "kind": "bounded", "start": "1984-01-01", "end": "1984-12-31",
        "basis": "approximate_year", "confidence": 0.5,
    }
    assert by_id[generated]["source_label"] == "generated"
    assert by_id[generated]["data"]["generated_label"].startswith("AI-GENERATED")
    assert by_id[person]["data"]["consent_context"]["grant_id"] == grant
    assert by_id[obj]["data"]["spatial_anchor"]["uncertainty_m"] == 0.08
    assert {by_id[item]["data"]["conflict_group_id"] for item in alternatives}.__len__() == 1

    edition = context.liveforever.create_edition(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Family graph edition",
        audience=Audience.FAMILY,
        purpose="family_review",
        presentation_choices={"evidence_first": True, "generated_toggle": True},
        scene_commit_id="synthetic-scene-commit",
        narrative_path=[{"record_id": memory}, {"record_id": revision}],
        policy_snapshot={"grant_ids": [grant], "generated_presence": False},
        actor_id=actor,
        idempotency_key="lf-graph-edition",
        publish=True,
    )
    payload = context.liveforever.edition_by_id(tenant_id, project_id, edition["edition_id"])
    assert payload["scene_commit_id"] == "synthetic-scene-commit"
    assert any(item["source_label"] == "generated" and item["generated_label"] for item in payload["record_revisions"])
    assert payload["truth_legend"]["witness_recollection"]

    with pytest.raises(ValidationError) as fabricated_precision:
        context.liveforever.create_record(
            tenant_id=tenant_id,
            project_id=project_id,
            record_type="memory",
            subject_id=subject,
            related_ids=[],
            data={"title": "Invalid precision", "time_expression": {"kind": "exact", "value": "1984-01-01", "approximate": True}},
            source_class=SourceClass.RECALLED,
            confidence=0.5,
            evidence_asset_ids=[],
            audience=Audience.FAMILY,
            actor_id=actor,
            purpose="family_review",
        )
    assert fabricated_precision.value.code == "MEMORY_TIME_PRECISION"


@pytest.mark.integration
@pytest.mark.privacy
def test_progress06_liveforever_interview_governance_dispute_and_safe_experience(bootstrapped) -> None:
    """REQ: LIFINT-001, LIFINT-002, LIFINT-003, LIFINT-004, LIFINT-005, LIFINT-006, LIFCONS-001, LIFCONS-003, LIFCONS-006, LIFPRES-006, LIFUX-001, LIFUX-002, LIFUX-003, LIFUX-005 interview, family-governance, dispute, and generated-presence controls fail closed while preserving source testimony."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "synthetic-interview-subject"
    grant = _grant(context, tenant_id, project_id, subject)
    governance = context.liveforever.create_governance_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="consent",
        subject_id=subject,
        grantor_id=subject,
        authority_basis="documented synthetic self-consent",
        data_scope={"records": ["*"], "excluded": ["biometric_templates"]},
        purposes=["preservation", "family_review"],
        modalities=["text", "audio", "photo", "generated_visual"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        providers=["local-approved-only"],
        geography={"execution": "local", "export": "family-approved"},
        effective_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=3650),
        posthumous_rules={"executor_required": True, "expand_permissions": False},
        evidence_asset_ids=["synthetic-signed-consent"],
        successor_ids=["synthetic-executor"],
        dispute={},
        freeze_high_risk=False,
        actor_id=subject,
        idempotency_key="lf-governance-consent",
        consent_grant_id=grant,
    )
    detail = context.liveforever.governance_record(tenant_id, project_id, governance["governance_id"])
    assert detail["providers"] == ["local-approved-only"]
    assert detail["posthumous_rules"]["expand_permissions"] is False

    interview = context.liveforever.create_interview(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        participants=[{"person_id": subject, "role": "narrator"}, {"person_id": actor, "role": "interviewer"}],
        consent_context={"confirmed": True, "grant_id": grant, "recording_indicator": True},
        recording_state="stopped",
        source_media_ids=["synthetic-interview.wav"],
        timeline={"started_ms": 0, "ended_ms": 9000},
        device={"type": "synthetic-recorder", "clock": "monotonic"},
        environment={"location": "synthetic memory room", "privacy": "controlled"},
        interruptions=[{"at_ms": 4500, "kind": "pause", "reason": "participant requested a break"}],
        question_lineage=[
            {"question_id": "q-human", "source": "human", "text": "What do you remember?"},
            {"question_id": "q-agent", "source": "agent", "text": "Which object anchors that memory?",
             "model_manifest_id": "synthetic-question-model", "prompt_hash": "d" * 64},
        ],
        pacing_policy={"pause_allowed": True, "skip_allowed": True, "stop_allowed": True,
                       "distress_behavior": "pause_and_offer_human_handoff_without_diagnosis"},
        actor_id=actor,
        idempotency_key="lf-interview-safe",
        complete=True,
    )
    segment = context.liveforever.add_transcript_segment(
        interview["interview_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        segment_index=0,
        start_ms=1000,
        end_ms=4200,
        speaker_label="Narrator",
        speaker_confidence=0.62,
        original_text="The radio was near the window.",
        source_media_id="synthetic-interview.wav",
        spatial_anchor={"record_id": "synthetic-radio", "source_time_range_ms": [1000, 4200], "uncertainty_m": 0.1},
        private_marks=[{"start": 4, "end": 9, "reason": "family-private"}],
        followup_suggestions=[{"text": "Would you like to pause?", "policy": "human_review_before_use"}],
        actor_id=actor,
    )
    assert segment["review_state"] == "needs_speaker_review"
    corrected = context.liveforever.correct_transcript_segment(
        segment["segment_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        editor_id=subject,
        edited_text="The blue radio was near the window.",
        reason="speaker supplied the missing descriptor",
        review_state="reviewed",
    )
    assert corrected["correction_count"] == 1
    retained = context.liveforever.interview(
        tenant_id, project_id, interview["interview_id"], include_private_marks=True
    )
    retained_segment = retained["segments"][0]
    assert retained_segment["text"] == "The blue radio was near the window."
    assert retained_segment["correction_history"][0]["prior_text"] == "The radio was near the window."
    assert retained_segment["original_text_hash"]
    assert retained_segment["private_marks"]

    dispute = context.liveforever.create_governance_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="dispute",
        subject_id=subject,
        grantor_id=subject,
        authority_basis="synthetic contributor dispute",
        data_scope={"assertion_ids": ["synthetic-assertion"]},
        purposes=["family_review"],
        modalities=["generated", "voice", "likeness", "dialogue"],
        audiences=[Audience.PRIVATE, Audience.FAMILY],
        providers=[],
        geography={"execution": "local"},
        effective_at=datetime.now(UTC),
        expires_at=None,
        posthumous_rules={"preserve_due_process_access": True},
        evidence_asset_ids=["synthetic-dispute-statement"],
        successor_ids=[],
        dispute={"active": True, "issue": "authority is disputed", "visibility": "family",
                 "status": "open", "resolution": None, "edition_decision": "withhold_high_risk"},
        freeze_high_risk=True,
        actor_id=subject,
        idempotency_key="lf-dispute-freeze",
        consent_grant_id=grant,
    )
    assert dispute["state"] == "disputed" and dispute["freeze_high_risk"] is True
    with pytest.raises(AuthorizationError) as frozen:
        context.liveforever.register_derivative(
            tenant_id=tenant_id,
            project_id=project_id,
            derivative_type="generated_reconstruction",
            source_ids=["synthetic-source"],
            subject_ids=[subject],
            consent_grant_ids=[grant],
            audience=Audience.FAMILY,
            classification="private-family",
            retention={"class": "family-preservation"},
            provider={"execution": "local", "provider_id": "synthetic-local"},
            generation_lineage={
                "model_manifest_id": "synthetic-model", "model_checkpoint_hash": "a" * 64,
                "prompt_hash": "b" * 64, "input_asset_ids": ["synthetic-source"], "output_hash": "c" * 64,
            },
            policy={"purpose": "family_review"},
            actor_id=actor,
            idempotency_key="lf-frozen-derivative",
        )
    assert frozen.value.code == "SUBJECT_HIGH_RISK_FROZEN"

    safe = context.liveforever.experience_configuration(
        tenant_id, project_id, subject, requested_features={"quiet_mode": True, "ambient_sound": False},
        audience=Audience.FAMILY,
    )
    assert safe["features"]["quiet_mode"] is True
    assert safe["features"]["safe_exit"] is True
    assert safe["features"]["evidence_mode"] is True
    assert safe["captions_required"] is True
    with pytest.raises(AuthorizationError) as presence:
        context.liveforever.experience_configuration(
            tenant_id, project_id, subject,
            requested_features={"voice_simulation": True, "first_person_dialogue": True},
            audience=Audience.FAMILY,
        )
    assert presence.value.code == "PRESENCE_KILL_SWITCH"


@pytest.mark.integration
@pytest.mark.acceptance
def test_progress06_liveforever_open_preservation_is_policy_scoped_labeled_and_offline(bootstrapped, tmp_path: Path) -> None:
    """REQ: LIFPRESV-001, LIFPRESV-003, LIFPRESV-004, LIFPRESV-005, LIFPRESV-006, LIFLABEL-004, LIFLABEL-006, LIFEXP-012, LIFDEMO-006 preservation retains fixity, rights, exact labels, migration/succession controls, and a non-proprietary offline experience without leaking private transcript marks."""
    context, tenant_id, project_id, actor = bootstrapped
    subject = "synthetic-preservation-subject"
    grant = _grant(context, tenant_id, project_id, subject)
    memory = context.liveforever.create_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="memory",
        subject_id=subject,
        related_ids=[],
        data={"title": "A synthetic source-backed memory", "source_label": "witness_recollection",
              "time_expression": {"kind": "qualitative", "label": "one summer in the 1980s"}},
        source_class=SourceClass.RECALLED,
        confidence=0.7,
        evidence_asset_ids=["synthetic-interview.wav"],
        audience=Audience.FAMILY,
        actor_id=actor,
        purpose="family_review",
    )
    interview = context.liveforever.create_interview(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        participants=[{"person_id": subject, "role": "narrator"}],
        consent_context={"confirmed": True, "grant_id": grant},
        recording_state="stopped",
        source_media_ids=["synthetic-interview.wav"],
        timeline={"started_ms": 0, "ended_ms": 3000},
        device={"type": "synthetic"},
        environment={"location": "synthetic"},
        interruptions=[],
        question_lineage=[{"source": "human", "text": "Tell me about the summer."}],
        pacing_policy={"pause_allowed": True, "skip_allowed": True, "stop_allowed": True},
        actor_id=actor,
        idempotency_key="lf-preservation-interview",
        complete=True,
    )
    context.liveforever.add_transcript_segment(
        interview["interview_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        segment_index=0,
        start_ms=0,
        end_ms=3000,
        speaker_label="Narrator",
        speaker_confidence=0.99,
        original_text="A synthetic recollection for preservation.",
        source_media_id="synthetic-interview.wav",
        spatial_anchor={"record_id": memory},
        private_marks=[{"start": 2, "end": 11, "reason": "private note"}],
        followup_suggestions=[],
        actor_id=actor,
    )
    edition = context.liveforever.create_edition(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Family preservation edition",
        audience=Audience.FAMILY,
        purpose="family_review",
        presentation_choices={"evidence_first": True, "source_labels_persistent": True},
        scene_commit_id="synthetic-memory-scene-v1",
        narrative_path=[{"record_id": memory, "scene_commit_id": "synthetic-memory-scene-v1"}],
        policy_snapshot={"grant_ids": [grant], "audience": "family"},
        actor_id=actor,
        idempotency_key="lf-preservation-edition",
        publish=True,
    )
    destination = tmp_path / "synthetic-memory-room-preservation.zip"
    release = context.liveforever.create_preservation_release(
        tenant_id=tenant_id,
        project_id=project_id,
        edition_id=edition["edition_id"],
        destination=destination,
        originals=[{"asset_id": "synthetic-interview.wav", "sha256": "1" * 64,
                    "media_type": "audio/wav", "preservation_master": True,
                    "technical_metadata": {"sample_rate_hz": 48000},
                    "rights": {"grant_id": grant, "audience": "family"}}],
        technical_metadata={"package_profile": "SIP-LIVEFOREVER-PRESERVATION-1.0", "created_by": actor},
        rights_consent=[{"grant_id": grant, "subject_id": subject, "purpose": "family_review",
                         "audience": "family", "revocation_checked": True}],
        memory_graph={"nodes": [memory], "edges": [], "source": "synthetic-only"},
        scene_manifests=[{"scene_commit_id": "synthetic-memory-scene-v1", "representations": ["semantic", "evidence"]}],
        open_assets=[{"path": "data/memory-graph.json", "format": "JSON"},
                     {"path": "viewer/index.html", "format": "HTML"}],
        human_guide={"title": "Family preservation guide", "contact": "synthetic-executor"},
        offline_fallback={"viewer": "viewer/index.html", "network_required": False, "splat_required": False},
        replicas=[{"replica_id": "offline-copy-a", "independent": True, "fixity_schedule": "annual"}],
        format_migrations=[{"from": "v1", "to": "v1", "original_preserved": True, "validation": "sha256"}],
        succession={"administrators": ["synthetic-executor"], "recovery": "documented offline copy",
                    "keys": "family-controlled", "billing": "none", "prohibited_uses": ["voice cloning"]},
        shutdown={"bulk_export": True, "key_handoff_or_crypto_deletion": True,
                  "family_notice": "required", "generated_presence_disabled": True},
        actor_id=actor,
        idempotency_key="lf-preservation-release",
    )
    assert release["status"] == "verified"
    verification = context.liveforever.verify_preservation_release(destination)
    assert verification["valid"] and verification["root_hash"] == release["root_hash"]
    with zipfile.ZipFile(destination) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        graph = json.loads(archive.read("data/memory-graph.json"))
        transcripts = json.loads(archive.read("data/transcripts.json"))
        rights = json.loads(archive.read("data/rights-consent.json"))
        viewer = archive.read("viewer/index.html").decode()
        checks = json.loads(archive.read("checksums.json"))
    edition_record = next(item for item in graph["edition_records"] if item["record_id"] == memory)
    assert edition_record["source_label"] == "witness_recollection"
    assert graph["truth_legend"]["generated"]
    assert transcripts[0]["private_marks"] == []
    assert transcripts[0]["private_marks_withheld"] is True
    assert rights[0]["grant_id"] == grant
    assert manifest["replicas"][0]["fixity_schedule"] == "annual"
    assert manifest["format_migrations"][0]["original_preserved"] is True
    assert manifest["succession"]["prohibited_uses"] == ["voice cloning"]
    assert manifest["shutdown"]["bulk_export"] is True
    assert manifest["truth_legend"]["source_document"]
    assert checks["root_hash"] == release["root_hash"]
    assert "does not require a proprietary renderer or network connection" in viewer
    assert "No voice or likeness simulation is included" in viewer
