from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sip.api import create_app
from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings
from sip.database import MemoryRecordRow
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SourceClass


def _headers(tenant: str, project: str, *, subject: str = "vertical-admin", roles: str = "project_admin") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": roles,
        "X-SIP-Purposes": "construction,operations,preservation,memorialization",
        "X-SIP-Audience": "private",
    }


def _bootstrap(tmp_path: Path, vertical: str) -> tuple[PlatformContext, str, str]:
    context = PlatformContext.create(temporary_settings(tmp_path / vertical))
    tenant = context.tenancy.create_tenant(f"{vertical} tenant", tenant_id=f"{vertical}-api-tenant", actor_id="bootstrap")
    project = context.tenancy.create_project(
        tenant,
        f"{vertical} project",
        vertical=vertical,
        classification="internal",
        project_id=f"{vertical}-api-project",
        actor_id="bootstrap",
    )
    return context, tenant, project


def test_progress06_construction_api_round_trip_read_search_and_handoff(tmp_path: Path) -> None:
    """REQ: CONOVR-001, CONOVR-002, CONOVR-004, CONOVR-005, CONDOC-001, CONQC-001, CONQC-002, CONQC-003, CONQC-004, CONHAND-001, CONHAND-004 authenticated APIs support the full synthetic survey-to-owner-handoff workflow."""
    context, tenant, project = _bootstrap(tmp_path, "construction")
    client = TestClient(create_app(context=context, service_name="construction"))
    admin = _headers(tenant, project)
    viewer = _headers(tenant, project, subject="owner-viewer", roles="viewer")

    evidence_payload = b"synthetic non-sensitive construction evidence"
    evidence = context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=evidence_payload,
        media_type="application/pdf",
        original_name="synthetic-plan.pdf",
        classification=Classification.INTERNAL,
        retention_class="records",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic:progress06"], output_hash=sha256_bytes(evidence_payload)),
        actor_id="vertical-admin",
    )
    scene = context.scene.create_scene(tenant, project, name="Synthetic room", actor_id="vertical-admin")
    site = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="site", name="Synthetic Site",
        parent_id=None, state="observed", actor_id="vertical-admin",
    )
    building = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="building", name="Building A",
        parent_id=site, state="observed", actor_id="vertical-admin",
    )
    level = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="level", name="Level 1",
        parent_id=building, state="observed", actor_id="vertical-admin",
    )
    room = context.construction.create_hierarchy_item(
        tenant_id=tenant, project_id=project, record_type="room", name="Electrical 101",
        parent_id=level, state="observed", actor_id="vertical-admin",
    )
    panel = context.construction.create_system_record(
        tenant_id=tenant,
        project_id=project,
        system_type="fire_alarm_panel",
        parent_id=room,
        entity_id=None,
        state="observed",
        data={
            "manufacturer": "Synthetic Manufacturer",
            "model": "SYN-FACP-1",
            "location": "Electrical 101",
            "network_address": "restricted-synthetic-address",
        },
        evidence_asset_ids=[evidence.asset_id],
        actor_id="vertical-admin",
    )

    survey_response = client.post(
        f"/v1/projects/{project}/construction/surveys",
        headers=admin,
        json={
            "name": "Room and systems survey",
            "objectives": ["document room", "inventory systems"],
            "required_place_ids": [room],
            "required_system_types": ["fire_alarm_panel"],
            "sensitive_regions": [{"region_id": "panel-network", "classification": "restricted"}],
            "control_requirements": {"known_scale": True},
            "measurement_requirements": {"verified_dimensions": ["door_width"]},
            "safety": {"escort_required": False},
            "permissions": {"classification": "internal"},
            "deliverables": [{"kind": "owner_handoff"}],
            "idempotency_key": "construction-api-survey-1",
            "baseline_commit_id": scene["commit_id"],
        },
    )
    assert survey_response.status_code == 201, survey_response.text
    survey_id = survey_response.json()["survey_id"]

    visit_response = client.post(
        f"/v1/projects/{project}/construction/surveys/{survey_id}/visits",
        headers=admin,
        json={
            "scope": {"place_ids": [room]},
            "capture_ids": [evidence.asset_id],
            "checklist": [{"id": "room", "status": "pass", "required": True}],
            "detail_evidence": [{"asset_id": evidence.asset_id, "label": "panel nameplate"}],
            "inaccessible_regions": [{"label": "locked cabinet interior"}],
            "coverage": {"observed_fraction": 0.94},
            "tracking": {"state": "normal"},
            "registration": {"state": "accepted", "rmse_m": 0.01},
            "controls": {"known_scale_id": "synthetic-scale"},
            "inventory": {"record_ids": [panel]},
            "unresolved_questions": [{"question": "confirm spare circuit count"}],
            "privacy": {"faces_present": False},
            "idempotency_key": "construction-api-visit-1",
            "exact_prior_commit_id": scene["commit_id"],
            "complete": True,
        },
    )
    assert visit_response.status_code == 201, visit_response.text
    aggregate = client.get(f"/v1/projects/{project}/construction/surveys/{survey_id}", headers=viewer)
    assert aggregate.status_code == 200, aggregate.text
    assert aggregate.json()["visits"][0]["unresolved_questions"]
    assert aggregate.json()["truth_rule"].startswith("Inaccessible")

    accepted = client.post(
        f"/v1/projects/{project}/construction/surveys/{survey_id}/review",
        headers=_headers(tenant, project, subject="independent-reviewer"),
        json={
            "decision": "accept",
            "accepted_commit_id": scene["commit_id"],
            "checklist": {"items": [{"id": "survey_complete", "required": True, "status": "pass"}]},
            "limitations": ["locked cabinet interior not observed"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "accepted"

    revision = client.post(
        f"/v1/projects/{project}/construction/document-revisions",
        headers=admin,
        json={
            "document_type": "rfi",
            "title": "RFI 001 - panel spare circuits",
            "revision": "0",
            "issue_date": "2026-07-29",
            "issuer": "Synthetic GC",
            "status": "open",
            "asset_id": evidence.asset_id,
            "source_sha256": evidence.sha256,
            "page_count": 1,
            "permissions": {"audience": "project"},
            "page_regions": [{"page": 1, "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]], "label": "question"}],
            "spatial_links": [{"place_id": room, "record_id": panel}],
            "extraction": {"question": "Confirm spare circuit count", "confidence": 1.0, "review_required": True},
            "review": {"state": "reviewed", "reviewer": "vertical-admin"},
        },
    )
    assert revision.status_code == 201, revision.text
    revision_id = revision.json()["revision_id"]
    fetched_revision = client.get(
        f"/v1/projects/{project}/construction/document-revisions/{revision_id}", headers=viewer)
    assert fetched_revision.status_code == 200
    assert fetched_revision.json()["document_type"] == "rfi"

    issue = client.post(
        f"/v1/projects/{project}/construction/issues",
        headers=_headers(tenant, project, subject="field-inspector"),
        json={
            "issue_type": "deficiency",
            "description": "Missing circuit label",
            "evidence": [{"asset_id": evidence.asset_id, "kind": "before"}],
            "severity": "medium",
            "idempotency_key": "construction-api-issue-1",
            "place_id": room,
            "observed_commit_id": scene["commit_id"],
            "responsible_party": "Synthetic EC",
            "permissions": {"audience": "project"},
        },
    )
    assert issue.status_code == 201, issue.text
    issue_id = issue.json()["issue_id"]
    for actor, target, payload in [
        ("responsible-tech", "corrected", {"evidence": [{"asset_id": evidence.asset_id, "kind": "correction"}], "note": "Label installed"}),
        ("commissioning-tech", "retest_required", {"evidence": [{"asset_id": evidence.asset_id, "kind": "retest-plan"}], "note": "Retest scheduled"}),
        ("independent-verifier", "verified_closed", {"evidence": [{"asset_id": evidence.asset_id, "kind": "passed-retest"}], "note": "Retest passed", "residual_limitations": []}),
    ]:
        transitioned = client.post(
            f"/v1/projects/{project}/construction/issues/{issue_id}/transition",
            headers=_headers(tenant, project, subject=actor),
            json={"target_state": target, "residual_limitations": [], **payload},
        )
        assert transitioned.status_code == 200, transitioned.text
    fetched_issue = client.get(f"/v1/projects/{project}/construction/issues/{issue_id}", headers=viewer)
    assert fetched_issue.status_code == 200
    assert fetched_issue.json()["status"] == "verified_closed"

    commissioning = client.post(
        f"/v1/projects/{project}/construction/commissioning",
        headers=_headers(tenant, project, subject="commissioning-agent"),
        json={
            "system_type": "fire_alarm_panel",
            "entity_ids": [panel],
            "procedure": {"id": "SYN-CX-1", "revision": "1"},
            "prerequisites": [{"id": "issue_closed", "status": "pass"}],
            "steps": [{"step": 1, "expected": "alarm", "actual": "alarm", "result": "pass"}],
            "participants": [{"id": "commissioning-agent", "role": "tester"}],
            "instruments": [{"id": "synthetic-meter", "calibration_state": "current"}],
            "attachments": [evidence.asset_id],
            "results": {"overall": "pass", "passed": True},
            "idempotency_key": "construction-api-cx-1",
            "issue_id": issue_id,
            "accept": True,
        },
    )
    assert commissioning.status_code == 201, commissioning.text

    interchange = client.post(
        f"/v1/projects/{project}/construction/interchanges",
        headers=admin,
        json={
            "format": "IFC",
            "direction": "import",
            "source_asset_id": evidence.asset_id,
            "source_sha256": evidence.sha256,
            "schema_version": "IFC4",
            "units": "meter",
            "crs": {"name": "synthetic-local"},
            "owner_history": {"application": "synthetic"},
            "global_ids": ["SYNTHETIC-GLOBAL-ID"],
            "classifications": {"system": "fire_alarm"},
            "properties": {"manufacturer": "Synthetic Manufacturer"},
            "relationships": [{"from": panel, "to": room}],
            "geometry_conversion_report": {"converted": 1, "failed": 0},
            "unsupported_constructs": [{"type": "IfcSyntheticUnsupported", "action": "listed_not_flattened"}],
            "alignment": {"state": "accepted", "residual_m": 0.01},
            "mappings": [{"field_id": panel, "design_id": "SYNTHETIC-GLOBAL-ID", "state": "proposed"}],
            "issues": [],
            "truth_labels": {"design": "design_intent", "observed": "observed_evidence"},
            "idempotency_key": "construction-api-ifc-1",
        },
    )
    assert interchange.status_code == 201, interchange.text

    handoff = client.post(
        f"/v1/projects/{project}/construction/handoffs",
        headers=admin,
        json={
            "scope": {"place_ids": [room], "system_packs": ["fire_alarm"]},
            "accepted_scene_commit_id": scene["commit_id"],
            "warranties": [{"system": "fire_alarm", "status": "synthetic"}],
            "training": [{"topic": "owner viewer", "completed": True}],
            "exclusions": ["locked cabinet interior"],
            "audience_profiles": {"owner": {"restricted_fields": False}, "technical": {"restricted_fields": True}},
            "idempotency_key": "construction-api-handoff-1",
        },
    )
    assert handoff.status_code == 201, handoff.text
    handoff_id = handoff.json()["handoff_id"]
    fetched_handoff = client.get(f"/v1/projects/{project}/construction/handoffs/{handoff_id}", headers=viewer)
    assert fetched_handoff.status_code == 200
    assert fetched_handoff.json()["status"] == "verified"

    search = client.get(
        f"/v1/projects/{project}/construction/search",
        headers=viewer,
        params={"query": "SYN-FACP-1", "system_pack": "fire_alarm"},
    )
    assert search.status_code == 200, search.text
    assert all(item["id"] != panel for item in search.json()["items"])
    assert "network_address" not in search.text
    assert panel not in search.text

    denied = client.get(
        f"/v1/projects/{project}/construction/surveys/{survey_id}",
        headers=_headers("other-tenant", project, subject="attacker", roles="viewer"),
    )
    assert denied.status_code in {403, 404}


def test_progress06_liveforever_api_memory_room_consent_and_preservation(tmp_path: Path) -> None:
    """REQ: LIFOVR-001, LIFOVR-002, LIFOVR-003, LIFGRAPH-003, LIFCONS-001, LIFCONS-004, LIFUX-001, LIFUX-002, LIFUX-005, LIFPRESV-001 authenticated APIs preserve consent, conflicting memories, interviews, editions, and open offline handoff."""
    context, tenant, project = _bootstrap(tmp_path, "liveforever")
    client = TestClient(create_app(context=context, service_name="liveforever"))
    admin = _headers(tenant, project, roles="tenant_admin")
    subject = "person-synthetic-alex"

    media_payload = b"synthetic interview recording - no real person"
    media = context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=media_payload,
        media_type="audio/wav",
        original_name="synthetic-interview.wav",
        classification=Classification.CONFIDENTIAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic:documented-consent"], output_hash=sha256_bytes(media_payload)),
        actor_id="vertical-admin",
    )

    grant = client.post(
        f"/v1/projects/{project}/liveforever/consents",
        headers=admin,
        json={
            "subject_id": subject,
            "purposes": ["preservation", "memorialization"],
            "audiences": ["private", "family"],
            "scopes": ["person", "place", "object", "event", "memory", "interview", "visual_reconstruction"],
            "derivative_policy": {"local_only": True, "voice": False, "likeness": False},
            "expires_at": (datetime.now(UTC) + timedelta(days=3650)).isoformat(),
        },
    )
    assert grant.status_code == 201, grant.text
    grant_id = grant.json()["grant_id"]

    governance = client.post(
        f"/v1/projects/{project}/liveforever/governance",
        headers=admin,
        json={
            "record_type": "consent",
            "subject_id": subject,
            "grantor_id": subject,
            "authority_basis": "documented synthetic self-consent fixture",
            "data_scope": {"record_types": ["person", "place", "object", "event", "memory", "interview"]},
            "purposes": ["preservation", "memorialization"],
            "modalities": ["text", "photo", "audio", "visual_reconstruction"],
            "audiences": ["private", "family"],
            "providers": ["local-only"],
            "geography": {"execution": "local"},
            "effective_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=3650)).isoformat(),
            "posthumous_rules": {"administrator": "synthetic-executor", "expand_permissions": False},
            "evidence_asset_ids": [media.asset_id],
            "successor_ids": ["synthetic-executor"],
            "dispute": {},
            "freeze_high_risk": True,
            "idempotency_key": "live-api-governance-1",
            "consent_grant_id": grant_id,
        },
    )
    assert governance.status_code == 201, governance.text
    governance_id = governance.json()["governance_id"]
    fetched_governance = client.get(
        f"/v1/projects/{project}/liveforever/governance/{governance_id}", headers=admin)
    assert fetched_governance.status_code == 200
    assert fetched_governance.json()["freeze_high_risk"] is True

    record_ids: list[str] = []
    records = [
        ("person", {"name": "Alex Example", "synthetic": True}, "direct_capture", 1.0),
        ("place", {"name": "Family Kitchen", "synthetic": True}, "direct_capture", 1.0),
        ("object", {"name": "Blue Mug", "synthetic": True}, "direct_capture", 1.0),
        ("event", {"title": "Summer storm", "time_expression": {"kind": "approximate", "year": 1985}}, "recalled", 0.7),
        ("memory", {"title": "Lights failed before dinner", "account": "before dinner"}, "recalled", 0.7),
    ]
    for index, (record_type, data, source_class, confidence) in enumerate(records):
        response = client.post(
            f"/v1/projects/{project}/liveforever/records",
            headers=admin,
            json={
                "record_type": record_type,
                "subject_id": subject,
                "related_ids": record_ids[-2:],
                "data": data,
                "source_class": source_class,
                "confidence": confidence,
                "evidence_asset_ids": [media.asset_id] if source_class != "recalled" else [],
                "audience": "family",
                "purpose": "preservation",
            },
        )
        assert response.status_code == 201, response.text
        record_ids.append(response.json()["record_id"])

    conflicts = client.post(
        f"/v1/projects/{project}/liveforever/conflicting-recollections",
        headers=admin,
        json={
            "subject_id": subject,
            "event_key": "summer-storm-timing",
            "recollections": [
                {"recollector_id": "person-a", "account": "before dinner", "confidence": 0.7},
                {"recollector_id": "person-b", "account": "after dinner", "confidence": 0.65},
            ],
            "audience": "family",
        },
    )
    assert conflicts.status_code == 201, conflicts.text
    assert len(conflicts.json()) == 2

    interview = client.post(
        f"/v1/projects/{project}/liveforever/interviews",
        headers=admin,
        json={
            "subject_id": subject,
            "participants": [{"person_id": subject, "role": "narrator"}, {"person_id": "interviewer", "role": "interviewer"}],
            "consent_context": {"confirmed": True, "grant_id": grant_id, "recording_indicator": True},
            "recording_state": "stopped",
            "source_media_ids": [media.asset_id],
            "timeline": {"started_ms": 0, "ended_ms": 120000},
            "device": {"type": "synthetic-recorder"},
            "environment": {"location": "synthetic memory room"},
            "interruptions": [],
            "question_lineage": [{"question_id": "q1", "text": "What do you remember?", "source": "human"}],
            "pacing_policy": {"pause_allowed": True, "stop_allowed": True},
            "idempotency_key": "live-api-interview-1",
            "complete": True,
        },
    )
    assert interview.status_code == 201, interview.text
    interview_id = interview.json()["interview_id"]
    segment = client.post(
        f"/v1/projects/{project}/liveforever/interviews/{interview_id}/segments",
        headers=admin,
        json={
            "segment_index": 0,
            "start_ms": 0,
            "end_ms": 5000,
            "speaker_label": "Alex Example",
            "speaker_confidence": 0.98,
            "original_text": "I remember the lights going out before dinner.",
            "source_media_id": media.asset_id,
            "spatial_anchor": {"place_record_id": record_ids[1]},
            "private_marks": [{"range": [0, 1], "reason": "family-only annotation"}],
            "followup_suggestions": [{"question": "Who else was present?", "status": "suggestion_only"}],
        },
    )
    assert segment.status_code == 201, segment.text
    segment_id = segment.json()["segment_id"]
    corrected = client.post(
        f"/v1/projects/{project}/liveforever/transcript-segments/{segment_id}/corrections",
        headers=_headers(tenant, project, subject="family-reviewer"),
        json={"edited_text": "I remember the lights going out shortly before dinner.", "reason": "speaker correction", "review_state": "reviewed"},
    )
    assert corrected.status_code == 200, corrected.text

    public_interview = client.get(
        f"/v1/projects/{project}/liveforever/interviews/{interview_id}",
        headers=_headers(tenant, project, subject="family-viewer", roles="viewer"),
    )
    assert public_interview.status_code == 200
    assert public_interview.json()["segments"][0]["private_marks"] == []
    assert public_interview.json()["segments"][0]["private_marks_withheld"] is True
    private_interview = client.get(
        f"/v1/projects/{project}/liveforever/interviews/{interview_id}",
        headers=admin,
        params={"include_private_marks": "true"},
    )
    assert private_interview.status_code == 200
    assert private_interview.json()["segments"][0]["private_marks"]

    edition = client.post(
        f"/v1/projects/{project}/liveforever/editions",
        headers=admin,
        json={
            "name": "Synthetic family edition",
            "audience": "family",
            "purpose": "preservation",
            "presentation_choices": {"autoplay": False, "generated_presence": False, "evidence_controls": True},
            "narrative_path": [{"kind": "place", "record_id": record_ids[1]}, {"kind": "memory", "record_id": record_ids[-1]}],
            "policy_snapshot": {"grant_id": grant_id, "private_marks": "withheld"},
            "idempotency_key": "live-api-edition-1",
            "publish": True,
        },
    )
    assert edition.status_code == 201, edition.text
    edition_id = edition.json()["edition_id"]
    fetched_edition = client.get(
        f"/v1/projects/{project}/liveforever/edition-revisions/{edition_id}", headers=admin)
    assert fetched_edition.status_code == 200
    assert fetched_edition.json()["state"] == "published"

    derivative = client.post(
        f"/v1/projects/{project}/liveforever/derivatives",
        headers=admin,
        json={
            "derivative_type": "visual_reconstruction",
            "source_ids": [media.asset_id],
            "subject_ids": [subject],
            "consent_grant_ids": [grant_id],
            "audience": "family",
            "classification": "confidential",
            "retention": {"class": "preservation", "delete_on_revocation": True},
            "provider": {"execution": "local", "provider_id": "deterministic-reference"},
            "generation_lineage": {"model_manifest_id": "synthetic-local-reference", "model_checkpoint_hash": "0" * 64, "prompt_hash": "1" * 64, "input_asset_ids": [media.asset_id], "output_hash": "2" * 64},
            "policy": {"purpose": "preservation", "generated_label_required": True},
            "idempotency_key": "live-api-derivative-1",
        },
    )
    assert derivative.status_code == 201, derivative.text
    derivative_id = derivative.json()["derivative_id"]
    fetched_derivative = client.get(
        f"/v1/projects/{project}/liveforever/derivatives/{derivative_id}", headers=admin)
    assert fetched_derivative.status_code == 200
    assert fetched_derivative.json()["policy"]["generated_label"] == "AI-GENERATED / RECONSTRUCTED"

    room = client.get(
        f"/v1/projects/{project}/liveforever/memory-room/{subject}",
        headers=_headers(tenant, project, subject="family-viewer", roles="viewer"),
        params={"audience": "family", "purpose": "preservation"},
    )
    assert room.status_code == 200, room.text
    assert room.json()["presentation_rules"]["generated_presence_disabled"] is True
    assert room.json()["experience"]["features"]["quiet_mode"] is True
    assert room.json()["truth_legend"]

    release = client.post(
        f"/v1/projects/{project}/liveforever/preservation-releases",
        headers=admin,
        json={
            "edition_id": edition_id,
            "originals": [{"asset_id": media.asset_id, "sha256": media.sha256, "kind": "interview_audio"}],
            "technical_metadata": {"format": "wav", "synthetic": True},
            "rights_consent": [{"grant_id": grant_id, "state": "active"}],
            "memory_graph": {"record_ids": record_ids, "conflict_group_preserved": True},
            "scene_manifests": [],
            "open_assets": [{"format": "json", "path": "data/memory-graph.json"}],
            "human_guide": {"title": "Synthetic memory room preservation guide", "no_claim_of_consciousness": True},
            "offline_fallback": {"html": True, "network_required": False},
            "replicas": [{"location": "synthetic-offline-copy", "verified": True}],
            "format_migrations": [],
            "succession": {"administrator": "synthetic-executor", "cannot_expand_permissions": True},
            "shutdown": {"kill_generated_presence": True, "retain_originals": True},
            "idempotency_key": "live-api-release-1",
        },
    )
    assert release.status_code == 201, release.text
    release_id = release.json()["release_id"]
    fetched_release = client.get(
        f"/v1/projects/{project}/liveforever/preservation-releases/{release_id}", headers=admin)
    assert fetched_release.status_code == 200
    assert fetched_release.json()["status"] == "verified"

    external = client.post(
        f"/v1/projects/{project}/liveforever/derivatives",
        headers=admin,
        json={
            "derivative_type": "visual_reconstruction",
            "source_ids": [media.asset_id],
            "subject_ids": [subject],
            "consent_grant_ids": [grant_id],
            "audience": "family",
            "classification": "confidential",
            "retention": {},
            "provider": {"execution": "external", "approved": False},
            "generation_lineage": {},
            "policy": {"purpose": "preservation"},
            "idempotency_key": "live-api-external-denied",
        },
    )
    assert external.status_code == 403
    assert external.json()["error"]["code"] == "EXTERNAL_PROVIDER_NOT_APPROVED"

    voice = client.post(
        f"/v1/projects/{project}/liveforever/derivatives",
        headers=admin,
        json={
            "derivative_type": "voice",
            "source_ids": [media.asset_id],
            "subject_ids": [subject],
            "consent_grant_ids": [grant_id],
            "audience": "family",
            "classification": "confidential",
            "retention": {},
            "provider": {"execution": "local"},
            "generation_lineage": {},
            "policy": {"purpose": "preservation"},
            "idempotency_key": "live-api-voice-denied",
        },
    )
    assert voice.status_code == 403
    assert voice.json()["error"]["code"] == "GENERATED_PRESENCE_DISABLED"

    revoked = client.post(
        f"/v1/projects/{project}/liveforever/consents/{grant_id}/revoke",
        headers=admin,
        json={"reason": "synthetic participant withdrew consent"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["affected_derivatives"] == 1
    withdrawn = client.get(f"/v1/projects/{project}/liveforever/derivatives/{derivative_id}", headers=admin)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["state"] == "withdrawn"


def test_progress06_family_revision_api_preserves_original_testimony(tmp_path: Path) -> None:
    """REQ: LIFGRAPH-004, LIFDISP-002, LIFTEST-004 family corrections create attributed immutable revisions and never overwrite the original testimony."""
    context, tenant, project = _bootstrap(tmp_path, "liveforever-revision")
    client = TestClient(create_app(context=context, service_name="liveforever"))
    admin = _headers(tenant, project, subject="family-reviewer", roles="tenant_admin")
    consent = client.post(
        f"/v1/projects/{project}/liveforever/consents",
        headers=admin,
        json={
            "subject_id": "synthetic-person",
            "purposes": ["family_review"],
            "audiences": ["family"],
            "scopes": ["memory"],
            "derivative_policy": {"local_only": True},
            "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
        },
    )
    assert consent.status_code == 201, consent.text

    created = client.post(
        f"/v1/projects/{project}/liveforever/records",
        headers=admin,
        json={
            "record_type": "memory",
            "subject_id": "synthetic-person",
            "related_ids": [],
            "data": {"account": "The storm began before dinner.", "synthetic": True},
            "source_class": "recalled",
            "confidence": 0.7,
            "evidence_asset_ids": [],
            "audience": "family",
            "purpose": "family_review",
        },
    )
    assert created.status_code == 201, created.text
    original_id = created.json()["record_id"]

    with context.database.session() as session:
        original_before = session.scalar(select(MemoryRecordRow).where(MemoryRecordRow.record_id == original_id))
        assert original_before is not None
        original_data = dict(original_before.data_json)
        original_created_by = original_before.created_by

    revised = client.post(
        f"/v1/projects/{project}/liveforever/records/{original_id}/revisions",
        headers=admin,
        json={
            "correction_type": "alternate_interpretation",
            "reason": "A second family reviewer remembers the timing differently.",
            "changes": {"account": "The storm may have begun shortly after dinner."},
            "audience": "family",
            "purpose": "family_review",
        },
    )
    assert revised.status_code == 201, revised.text
    body = revised.json()
    assert body["revises_record_id"] == original_id
    assert body["original_preserved"] is True
    assert body["record_id"] != original_id

    with context.database.session() as session:
        original_after = session.scalar(select(MemoryRecordRow).where(MemoryRecordRow.record_id == original_id))
        revision = session.scalar(select(MemoryRecordRow).where(MemoryRecordRow.record_id == body["record_id"]))
        assert original_after is not None and revision is not None
        assert original_after.data_json == original_data
        assert original_after.created_by == original_created_by
        assert revision.data_json["revision_of"] == original_id
        assert revision.data_json["correction"]["type"] == "alternate_interpretation"
        assert revision.data_json["correction"]["editor_id"] == "family-reviewer"
        assert revision.data_json["correction"]["original_hash"]
        assert revision.data_json["source_label"] == "disputed"
        assert original_id in revision.related_ids_json

    denied = client.post(
        f"/v1/projects/{project}/liveforever/records/{original_id}/revisions",
        headers=_headers("other-tenant", project, subject="attacker", roles="tenant_admin"),
        json={
            "correction_type": "factual_correction",
            "reason": "unauthorized cross-tenant attempt",
            "changes": {"account": "tampered"},
            "audience": "family",
            "purpose": "family_review",
        },
    )
    assert denied.status_code in {403, 404}


def test_progress06_vertical_openapi_contracts_are_service_scoped(tmp_path: Path) -> None:
    """REQ: PLTAPI-001, CONOVR-001, LIFOVR-001 Progress 06 logical service contracts are generated and do not expose the other vertical's write surface."""
    context, tenant, project = _bootstrap(tmp_path, "platform")
    construction = TestClient(create_app(context=context, service_name="construction")).get("/openapi.json").json()
    liveforever = TestClient(create_app(context=context, service_name="liveforever")).get("/openapi.json").json()
    construction_paths = set(construction["paths"])
    liveforever_paths = set(liveforever["paths"])
    assert f"/v1/projects/{{project_id}}/construction/surveys" in construction_paths
    assert f"/v1/projects/{{project_id}}/construction/search" in construction_paths
    assert f"/v1/projects/{{project_id}}/liveforever/interviews" not in construction_paths
    assert f"/v1/projects/{{project_id}}/liveforever/interviews" in liveforever_paths
    assert f"/v1/projects/{{project_id}}/liveforever/memory-room/{{subject_id}}" in liveforever_paths
    assert f"/v1/projects/{{project_id}}/construction/issues" not in liveforever_paths
    for schema in (construction, liveforever):
        operation_ids = [operation["operationId"] for path in schema["paths"].values()
                         for method, operation in path.items() if method in {"get", "post", "put", "patch", "delete"}]
        assert len(operation_ids) == len(set(operation_ids))
