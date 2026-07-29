from __future__ import annotations

import json
import re
import zipfile
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from .archive_safety import validate_zip_members
from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, merkle_root, new_uuid, sha256_bytes, sha256_file
from .database import (
    ConsentGrantRow,
    Database,
    LiveForeverDerivativeRow,
    LiveForeverEditionRow,
    LiveForeverGovernanceRow,
    LiveForeverInterviewRow,
    LiveForeverPreservationRow,
    LiveForeverTranscriptSegmentRow,
    MemoryRecordRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import Audience, SourceClass
from .temporal import db_now


MEMORY_TYPES = {
    "person", "relationship", "place", "object", "event", "memory", "timeline", "theme",
    "interview", "speaker", "transcript_segment", "photograph", "recording", "video",
    "document", "letter", "story_anchor", "edition", "generated_reconstruction",
}
EXPERIENCE_FEATURES_DEFAULT = {
    "voice_simulation": False, "likeness_simulation": False, "first_person_dialogue": False,
    "autonomous_persona": False, "quiet_mode": True, "safe_exit": True, "pause": True,
    "reset": True, "free_locomotion": False, "guided_mode": True, "timeline_mode": True,
    "person_mode": True, "place_mode": True, "object_mode": True, "evidence_mode": True,
}
TRUTH_LEGEND = {
    "direct_capture": "Direct capture or preservation master.",
    "source_document": "A source document or document-derived assertion.",
    "first_person_recollection": "A first-person recollection; it is not automatically historical fact.",
    "witness_recollection": "A witness recollection; it may conflict with other accounts.",
    "corroborated_synthesis": "A synthesis supported by multiple independently identified sources.",
    "inferred": "A platform or reviewer inference, not established fact.",
    "reconstructed": "A source-constrained reconstruction with stated assumptions and limitations.",
    "restored": "A restoration derivative; the preservation master remains unchanged.",
    "generated": "AI-generated reconstruction; not a historical fact.",
    "artistic": "An artistic interpretation rather than a factual reconstruction.",
    "disputed": "A claim or interpretation with an unresolved material dispute.",
    "unknown": "The source or truth class is not known.",
    "verified": "Independently reviewed against eligible evidence for the stated purpose.",
}
SOURCE_LABELS = frozenset(TRUTH_LEGEND)
DEFAULT_SOURCE_LABEL = {
    SourceClass.DIRECT_CAPTURE: "direct_capture",
    SourceClass.OBSERVED: "direct_capture",
    SourceClass.MEASURED: "direct_capture",
    SourceClass.VERIFIED: "verified",
    SourceClass.DESIGN: "source_document",
    SourceClass.PROPOSED: "reconstructed",
    SourceClass.INFERRED: "inferred",
    SourceClass.GENERATED: "generated",
    SourceClass.RECALLED: "first_person_recollection",
    SourceClass.CORROBORATED: "corroborated_synthesis",
    SourceClass.DISPUTED: "disputed",
    SourceClass.SUPERSEDED: "unknown",
}
CORRECTION_TYPES = frozenset({
    "transcription_correction", "factual_correction", "contributor_retraction",
    "consent_restriction", "alternate_interpretation",
})
T = TypeVar("T")


def _zip_write(handle: zipfile.ZipFile, name: str, data: bytes) -> str:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    handle.writestr(info, data)
    return sha256_bytes(data)


class LiveForeverService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit
        self.events = OutboxEventFactory()
        self.kill_switches: dict[str, bool] = {"all_generated_presence": True, "voice": True, "likeness": True, "dialogue": True}

    # Compatibility consent grant ---------------------------------------------------------------
    def grant_consent(self, *, tenant_id: str, project_id: str, subject_id: str, granted_by: str,
                      purposes: list[str], audiences: list[Audience], scopes: list[str],
                      derivative_policy: dict[str, Any], expires_at: datetime | None) -> str:
        if not purposes or not audiences or not scopes:
            raise ValidationError("CONSENT_SCOPE_REQUIRED", "consent requires purpose, audience, and scope")
        if expires_at and _aware(expires_at) <= db_now():
            raise ValidationError("CONSENT_EXPIRY_INVALID", "consent cannot be created already expired")
        grant_id = new_uuid()
        with self.database.session() as session:
            session.add(ConsentGrantRow(grant_id=grant_id, tenant_id=tenant_id, project_id=project_id,
                                        subject_id=subject_id, granted_by=granted_by, purposes_json=sorted(set(purposes)),
                                        audiences_json=sorted({a.value for a in audiences}), scopes_json=sorted(set(scopes)),
                                        derivative_policy_json=derivative_policy, expires_at=expires_at))
            self._record(session, tenant_id, project_id, granted_by, "consent:grant", "consent_grant", grant_id,
                         {"subject_id": subject_id, "purposes": sorted(set(purposes)),
                          "audiences": sorted({a.value for a in audiences}), "scopes": sorted(set(scopes))},
                         "liveforever.consent.granted", "consent_grant")
        return grant_id

    def create_governance_record(self, *, tenant_id: str, project_id: str, record_type: str, subject_id: str,
                                 grantor_id: str, authority_basis: str, data_scope: dict[str, Any],
                                 purposes: list[str], modalities: list[str], audiences: list[Audience],
                                 providers: list[str], geography: dict[str, Any], effective_at: datetime,
                                 expires_at: datetime | None, posthumous_rules: dict[str, Any],
                                 evidence_asset_ids: list[str], successor_ids: list[str], dispute: dict[str, Any],
                                 freeze_high_risk: bool, actor_id: str, idempotency_key: str,
                                 consent_grant_id: str | None = None) -> dict[str, Any]:
        allowed = {"consent", "guardian", "executor", "successor", "minor_protection", "living_third_party", "dispute", "freeze"}
        if record_type not in allowed:
            raise ValidationError("GOVERNANCE_RECORD_TYPE", "unsupported family-governance record type")
        if not purposes or not modalities or not audiences or not data_scope:
            raise ValidationError("GOVERNANCE_SCOPE_REQUIRED", "governance requires data, purpose, modality, and audience scope")
        if expires_at and _aware(expires_at) <= _aware(effective_at):
            raise ValidationError("GOVERNANCE_TIME_RANGE", "governance expiry must follow its effective time")
        request = {"record_type": record_type, "subject_id": subject_id, "consent_grant_id": consent_grant_id,
                   "grantor_id": grantor_id, "authority_basis": authority_basis, "data_scope": data_scope,
                   "purposes": sorted(set(purposes)), "modalities": sorted(set(modalities)),
                   "audiences": sorted({a.value for a in audiences}), "providers": sorted(set(providers)),
                   "geography": geography, "effective_at": _aware(effective_at).isoformat(),
                   "expires_at": _aware(expires_at).isoformat() if expires_at else None,
                   "posthumous_rules": posthumous_rules, "evidence_asset_ids": sorted(set(evidence_asset_ids)),
                   "successor_ids": sorted(set(successor_ids)), "dispute": dispute, "freeze_high_risk": freeze_high_risk}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, LiveForeverGovernanceRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._governance_result(prior, True)
            if consent_grant_id:
                grant = session.get(ConsentGrantRow, consent_grant_id)
                if not grant or grant.tenant_id != tenant_id or grant.project_id != project_id or grant.subject_id != subject_id:
                    raise ValidationError("GOVERNANCE_GRANT_SCOPE", "linked consent grant does not match governance scope")
            state = "disputed" if dispute.get("active") else "active"
            row = LiveForeverGovernanceRow(governance_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                            idempotency_key=idempotency_key, request_hash=request_hash,
                                            record_type=record_type, subject_id=subject_id,
                                            consent_grant_id=consent_grant_id, grantor_id=grantor_id,
                                            authority_basis=authority_basis, data_scope_json=data_scope,
                                            purposes_json=sorted(set(purposes)), modalities_json=sorted(set(modalities)),
                                            audiences_json=sorted({a.value for a in audiences}),
                                            providers_json=sorted(set(providers)), geography_json=geography,
                                            effective_at=_aware(effective_at), expires_at=_aware(expires_at) if expires_at else None,
                                            posthumous_rules_json=posthumous_rules,
                                            evidence_asset_ids_json=sorted(set(evidence_asset_ids)),
                                            successor_ids_json=sorted(set(successor_ids)), dispute_json=dispute,
                                            state=state, freeze_high_risk=freeze_high_risk, created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "liveforever:governance_create",
                         "liveforever_governance", row.governance_id,
                         {"record_type": record_type, "subject_id": subject_id, "state": state,
                          "freeze_high_risk": freeze_high_risk},
                         "liveforever.governance.recorded", "liveforever_governance")
            return self._governance_result(row, False)

    def revoke_consent(self, grant_id: str, *, actor_id: str, reason: str) -> dict[str, Any]:
        with self.database.session() as session:
            grant = session.get(ConsentGrantRow, grant_id)
            if not grant:
                raise NotFoundError("consent_grant", grant_id)
            if grant.state == "revoked":
                affected_derivatives = 0
                return {"grant_id": grant_id, "state": "revoked", "affected_records": 0,
                        "affected_derivatives": affected_derivatives, "idempotent_replay": True}
            grant.state = "revoked"
            grant.revoked_at = db_now()
            grant.revoked_by = actor_id
            affected = list(session.scalars(select(MemoryRecordRow).where(
                MemoryRecordRow.tenant_id == grant.tenant_id, MemoryRecordRow.project_id == grant.project_id,
                MemoryRecordRow.subject_id == grant.subject_id)))
            for row in affected:
                row.data_json = {**row.data_json, "access_state": "consent_revoked_review_required",
                                 "revoked_grant_id": grant_id, "revocation_reason": reason,
                                 "derivative_access_disabled": True}
            governance = list(session.scalars(select(LiveForeverGovernanceRow).where(
                LiveForeverGovernanceRow.tenant_id == grant.tenant_id,
                LiveForeverGovernanceRow.project_id == grant.project_id,
                LiveForeverGovernanceRow.consent_grant_id == grant_id)))
            for item in governance:
                item.state = "revoked"
                item.revoked_at = db_now()
                item.revoked_by = actor_id
                item.freeze_high_risk = True
            derivatives = list(session.scalars(select(LiveForeverDerivativeRow).where(
                LiveForeverDerivativeRow.tenant_id == grant.tenant_id,
                LiveForeverDerivativeRow.project_id == grant.project_id)))
            affected_derivatives = 0
            for derivative in derivatives:
                if grant_id in derivative.consent_grant_ids_json or grant.subject_id in derivative.subject_ids_json:
                    derivative.state = "withdrawn"
                    derivative.withdrawal_action = "disable_access_and_queue_deletion_review"
                    derivative.policy_json = {**derivative.policy_json, "revoked_grant_id": grant_id,
                                              "revocation_reason": reason, "access_disabled": True}
                    affected_derivatives += 1
            self._record(session, grant.tenant_id, grant.project_id, actor_id, "consent:revoke", "consent_grant",
                         grant_id, {"reason": reason, "affected_records": len(affected),
                                    "affected_derivatives": affected_derivatives},
                         "liveforever.consent.revoked", "consent_grant")
            return {"grant_id": grant_id, "state": "revoked", "affected_records": len(affected),
                    "affected_derivatives": affected_derivatives, "idempotent_replay": False}

    # Memory graph and interview workflows ------------------------------------------------------
    def create_record(self, *, tenant_id: str, project_id: str, record_type: str, subject_id: str | None,
                      related_ids: list[str], data: dict[str, Any], source_class: SourceClass,
                      confidence: float, evidence_asset_ids: list[str], audience: Audience,
                      actor_id: str, purpose: str = "preservation",
                      generated_lineage: dict[str, Any] | None = None) -> str:
        if record_type not in MEMORY_TYPES:
            raise ValidationError("MEMORY_RECORD_TYPE", "unsupported LiveForever record type")
        if not 0 <= confidence <= 1:
            raise ValidationError("MEMORY_CONFIDENCE", "confidence must be between zero and one")
        if source_class in {SourceClass.CORROBORATED, SourceClass.VERIFIED} and not evidence_asset_ids:
            raise ValidationError("MEMORY_EVIDENCE_REQUIRED", "corroborated or verified claims require evidence")
        source_label = str(data.get("source_label") or DEFAULT_SOURCE_LABEL.get(source_class, "unknown"))
        if source_label not in SOURCE_LABELS:
            raise ValidationError(
                "MEMORY_SOURCE_LABEL",
                "memory source label is not part of the governed truth legend",
                {"source_label": source_label, "allowed": sorted(SOURCE_LABELS)},
            )
        time_expression = _normalize_time_expression(data.get("time_expression"))
        consent_context: dict[str, Any] = {}
        if source_class == SourceClass.GENERATED:
            generated_lineage = self._validate_generated_lineage(generated_lineage)
            source_label = "generated" if source_label == DEFAULT_SOURCE_LABEL[SourceClass.GENERATED] else source_label
        if subject_id:
            grant = self._require_consent(
                tenant_id, project_id, subject_id, purpose=purpose, audience=audience, scope=record_type
            )
            consent_context = {
                "grant_id": grant.grant_id,
                "purpose": purpose,
                "audience": audience.value,
                "scope": record_type,
                "evaluated_at": db_now().isoformat(),
            }
            self._enforce_high_risk_freeze(
                tenant_id,
                project_id,
                subject_id,
                modality="generated" if source_class == SourceClass.GENERATED else "record",
            )
        record_id = new_uuid()
        working_label = str(
            data.get("working_label")
            or data.get("title")
            or data.get("name")
            or data.get("label")
            or f"{record_type}:{record_id[:8]}"
        )
        record_data = {
            **data,
            "working_label": working_label,
            "contributor_id": str(data.get("contributor_id") or actor_id),
            "source_label": source_label,
            "time_expression": time_expression,
            "themes": list(data.get("themes") or []),
            "emotional_sensitivity": data.get("emotional_sensitivity", "unspecified"),
            "assertions": list(data.get("assertions") or []),
            "consent_context": data.get("consent_context") or consent_context,
            "status": data.get("status", "active"),
            "access_state": "active",
        }
        if source_class == SourceClass.GENERATED:
            record_data["generated_label"] = "AI-GENERATED RECONSTRUCTION — NOT A HISTORICAL FACT"
        with self.database.session() as session:
            session.add(MemoryRecordRow(record_id=record_id, tenant_id=tenant_id, project_id=project_id,
                                        record_type=record_type, subject_id=subject_id,
                                        related_ids_json=sorted(set(related_ids)),
                                        data_json=record_data, source_class=source_class.value,
                                        confidence=confidence, evidence_asset_ids_json=sorted(set(evidence_asset_ids)),
                                        audience=audience.value, generated_lineage_json=generated_lineage, created_by=actor_id))
            self._record(session, tenant_id, project_id, actor_id, "liveforever:record_create", "memory_record",
                         record_id, {"record_type": record_type, "source_class": source_class.value,
                                     "source_label": source_label, "audience": audience.value},
                         "liveforever.memory.recorded", "memory_record")
        return record_id

    def revise_record(self, record_id: str, *, tenant_id: str, project_id: str, editor_id: str,
                      correction_type: str, reason: str, changes: dict[str, Any],
                      audience: Audience | None = None, purpose: str = "family_review") -> str:
        """Create an immutable family correction/restriction revision; never overwrite testimony."""
        if correction_type not in CORRECTION_TYPES:
            raise ValidationError(
                "MEMORY_CORRECTION_TYPE",
                "unsupported correction type",
                {"allowed": sorted(CORRECTION_TYPES)},
            )
        if not reason.strip() or not changes:
            raise ValidationError("MEMORY_CORRECTION_INVALID", "a correction requires a reason and explicit changes")
        with self.database.session() as session:
            original = self._scoped(session, MemoryRecordRow, record_id, tenant_id, project_id, "memory_record")
            original_payload = {
                "record_id": original.record_id,
                "record_type": original.record_type,
                "subject_id": original.subject_id,
                "related_ids": original.related_ids_json,
                "data": original.data_json,
                "source_class": original.source_class,
                "confidence": original.confidence,
                "evidence_asset_ids": original.evidence_asset_ids_json,
                "audience": original.audience,
                "generated_lineage": original.generated_lineage_json,
                "created_by": original.created_by,
                "created_at": original.created_at.isoformat(),
            }
        revised_data = {
            **original_payload["data"],
            **changes,
            "revision_of": record_id,
            "correction": {
                "type": correction_type,
                "reason": reason,
                "editor_id": editor_id,
                "original_hash": canonical_sha256(original_payload),
                "created_at": db_now().isoformat(),
            },
            "status": "restricted" if correction_type == "consent_restriction" else "active",
        }
        source_class = SourceClass(original_payload["source_class"])
        if correction_type in {"factual_correction", "alternate_interpretation"}:
            source_class = SourceClass.DISPUTED
            revised_data["source_label"] = "disputed"
        revised_id = self.create_record(
            tenant_id=tenant_id,
            project_id=project_id,
            record_type=original_payload["record_type"],
            subject_id=original_payload["subject_id"],
            related_ids=sorted(set([*original_payload["related_ids"], record_id])),
            data=revised_data,
            source_class=source_class,
            confidence=float(original_payload["confidence"]),
            evidence_asset_ids=original_payload["evidence_asset_ids"],
            audience=audience or Audience(original_payload["audience"]),
            actor_id=editor_id,
            purpose=purpose,
            generated_lineage=original_payload["generated_lineage"],
        )
        with self.database.session() as session:
            self._scoped(session, MemoryRecordRow, record_id, tenant_id, project_id, "memory_record")
            self._record(
                session,
                tenant_id,
                project_id,
                editor_id,
                "liveforever:record_revise",
                "memory_record",
                revised_id,
                {"supersedes_record_id": record_id, "correction_type": correction_type,
                 "original_preserved": True},
                "liveforever.memory.recorded",
                "memory_record",
            )
        return revised_id

    def conflicting_recollections(self, *, tenant_id: str, project_id: str, subject_id: str, event_key: str,
                                  recollections: list[dict[str, Any]], audience: Audience, actor_id: str) -> list[str]:
        if len(recollections) < 2:
            raise ValidationError("CONFLICT_REQUIRES_ALTERNATIVES", "conflicting recollection set requires at least two accounts")
        group_id = new_uuid()
        return [self.create_record(tenant_id=tenant_id, project_id=project_id, record_type="memory",
                                   subject_id=subject_id, related_ids=[],
                                   data={"event_key": event_key, "conflict_group_id": group_id,
                                         "account": item["account"], "recollector_id": item["recollector_id"],
                                         "conflict_status": "alternate_recollection"},
                                   source_class=SourceClass.RECALLED, confidence=float(item.get("confidence", .5)),
                                   evidence_asset_ids=item.get("evidence_asset_ids", []), audience=audience,
                                   actor_id=actor_id)
                for item in recollections]

    def create_interview(self, *, tenant_id: str, project_id: str, subject_id: str,
                         participants: list[dict[str, Any]], consent_context: dict[str, Any],
                         recording_state: str, source_media_ids: list[str], timeline: dict[str, Any],
                         device: dict[str, Any], environment: dict[str, Any], interruptions: list[dict[str, Any]],
                         question_lineage: list[dict[str, Any]], pacing_policy: dict[str, Any],
                         actor_id: str, idempotency_key: str, complete: bool = False) -> dict[str, Any]:
        if recording_state not in {"planned", "recording", "paused", "stopped", "not_recorded"}:
            raise ValidationError("INTERVIEW_RECORDING_STATE", "unsupported interview recording state")
        if not participants or not consent_context.get("confirmed"):
            raise ValidationError("INTERVIEW_CONSENT_REQUIRED", "interview requires participants and confirmed consent context")
        self._require_consent(tenant_id, project_id, subject_id, purpose="preservation",
                              audience=Audience.PRIVATE, scope="interview")
        request = {"subject_id": subject_id, "participants": participants, "consent_context": consent_context,
                   "recording_state": recording_state, "source_media_ids": sorted(set(source_media_ids)),
                   "timeline": timeline, "device": device, "environment": environment,
                   "interruptions": interruptions, "question_lineage": question_lineage,
                   "pacing_policy": pacing_policy, "complete": complete}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, LiveForeverInterviewRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._interview_result(prior, True)
            row = LiveForeverInterviewRow(interview_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                           idempotency_key=idempotency_key, request_hash=request_hash,
                                           subject_id=subject_id, participants_json=participants,
                                           consent_context_json=consent_context, recording_state=recording_state,
                                           source_media_ids_json=sorted(set(source_media_ids)), timeline_json=timeline,
                                           device_json=device, environment_json=environment,
                                           interruptions_json=interruptions, question_lineage_json=question_lineage,
                                           pacing_policy_json=pacing_policy, state="completed" if complete else "active",
                                           created_by=actor_id, completed_at=db_now() if complete else None)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "liveforever:interview_create", "liveforever_interview",
                         row.interview_id, {"subject_id": subject_id, "state": row.state,
                                            "recording_state": recording_state},
                         "liveforever.interview.recorded", "liveforever_interview")
            return self._interview_result(row, False)

    def add_transcript_segment(self, interview_id: str, *, tenant_id: str, project_id: str,
                               segment_index: int, start_ms: int, end_ms: int, speaker_label: str,
                               speaker_confidence: float, original_text: str, source_media_id: str,
                               spatial_anchor: dict[str, Any] | None, private_marks: list[dict[str, Any]],
                               followup_suggestions: list[dict[str, Any]], actor_id: str) -> dict[str, Any]:
        if segment_index < 0 or start_ms < 0 or end_ms <= start_ms or not original_text.strip():
            raise ValidationError("TRANSCRIPT_SEGMENT_INVALID", "transcript segment timing and text are invalid")
        if not 0 <= speaker_confidence <= 1:
            raise ValidationError("SPEAKER_CONFIDENCE", "speaker confidence must be between zero and one")
        with self.database.session() as session:
            interview = self._scoped(session, LiveForeverInterviewRow, interview_id, tenant_id, project_id, "interview")
            prior = session.scalar(select(LiveForeverTranscriptSegmentRow).where(
                LiveForeverTranscriptSegmentRow.interview_id == interview_id,
                LiveForeverTranscriptSegmentRow.segment_index == segment_index))
            body = {"start_ms": start_ms, "end_ms": end_ms, "speaker_label": speaker_label,
                    "speaker_confidence": speaker_confidence, "original_text": original_text,
                    "source_media_id": source_media_id, "spatial_anchor": spatial_anchor,
                    "private_marks": private_marks, "followup_suggestions": followup_suggestions}
            if prior:
                existing = {"start_ms": prior.start_ms, "end_ms": prior.end_ms, "speaker_label": prior.speaker_label,
                            "speaker_confidence": prior.speaker_confidence, "original_text": prior.original_text,
                            "source_media_id": prior.source_media_id, "spatial_anchor": prior.spatial_anchor_json,
                            "private_marks": prior.private_marks_json,
                            "followup_suggestions": prior.followup_suggestions_json}
                if canonical_sha256(existing) != canonical_sha256(body):
                    raise ConflictError("TRANSCRIPT_SEGMENT_CONFLICT", "segment index already exists with different content")
                return self._segment_result(prior, True)
            row = LiveForeverTranscriptSegmentRow(segment_id=new_uuid(), interview_id=interview_id,
                                                   tenant_id=tenant_id, project_id=project_id,
                                                   segment_index=segment_index, start_ms=start_ms, end_ms=end_ms,
                                                   speaker_label=speaker_label, speaker_confidence=speaker_confidence,
                                                   original_text=original_text, edited_text=None,
                                                   correction_history_json=[], private_marks_json=private_marks,
                                                   source_media_id=source_media_id, spatial_anchor_json=spatial_anchor,
                                                   followup_suggestions_json=followup_suggestions,
                                                   review_state="needs_speaker_review" if speaker_confidence < .75 else "unreviewed",
                                                   created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "liveforever:transcript_segment_create",
                         "liveforever_transcript_segment", row.segment_id,
                         {"interview_id": interview_id, "segment_index": segment_index,
                          "review_state": row.review_state},
                         "liveforever.transcript.segmented", "liveforever_transcript_segment")
            return self._segment_result(row, False)

    def correct_transcript_segment(self, segment_id: str, *, tenant_id: str, project_id: str,
                                   editor_id: str, edited_text: str, reason: str,
                                   review_state: str = "reviewed") -> dict[str, Any]:
        if not edited_text.strip() or review_state not in {"reviewed", "disputed", "private", "needs_speaker_review"}:
            raise ValidationError("TRANSCRIPT_CORRECTION_INVALID", "correction text or review state is invalid")
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverTranscriptSegmentRow, segment_id, tenant_id, project_id, "transcript_segment")
            history = list(row.correction_history_json)
            history.append({"prior_text": row.edited_text or row.original_text, "edited_text": edited_text,
                            "reason": reason, "editor_id": editor_id, "at": db_now().isoformat()})
            row.edited_text = edited_text
            row.correction_history_json = history
            row.review_state = review_state
            self._record(session, tenant_id, project_id, editor_id, "liveforever:transcript_segment_correct",
                         "liveforever_transcript_segment", segment_id,
                         {"review_state": review_state, "correction_count": len(history)},
                         "liveforever.transcript.corrected", "liveforever_transcript_segment")
            return self._segment_result(row, False)

    # Editions, derivatives and experiences -----------------------------------------------------
    def visible_records(self, tenant_id: str, project_id: str, *, audience: Audience, purpose: str,
                        subject_id: str | None = None) -> list[dict[str, Any]]:
        with self.database.session() as session:
            statement = select(MemoryRecordRow).where(MemoryRecordRow.tenant_id == tenant_id,
                                                       MemoryRecordRow.project_id == project_id)
            if subject_id:
                statement = statement.where(MemoryRecordRow.subject_id == subject_id)
            rows = list(session.scalars(statement))
        allowed_audiences = _allowed_record_audiences(audience)
        visible: list[dict[str, Any]] = []
        for row in rows:
            if row.audience not in allowed_audiences or row.data_json.get("derivative_access_disabled"):
                continue
            if row.subject_id:
                try:
                    self._require_consent(tenant_id, project_id, row.subject_id, purpose=purpose,
                                          audience=audience, scope=row.record_type)
                except AuthorizationError:
                    continue
            visible.append(self._memory_payload(row))
        return visible

    def create_edition(self, *, tenant_id: str, project_id: str, name: str, audience: Audience,
                       purpose: str, presentation_choices: dict[str, Any], scene_commit_id: str | None,
                       narrative_path: list[dict[str, Any]], policy_snapshot: dict[str, Any],
                       actor_id: str, idempotency_key: str, publish: bool = False,
                       supersedes_edition_id: str | None = None) -> dict[str, Any]:
        records = self.visible_records(tenant_id, project_id, audience=audience, purpose=purpose)
        record_revisions = [{"record_id": item["record_id"], "record_hash": canonical_sha256(item),
                             "source_class": item["source_class"],
                             "source_label": item.get("source_label", "unknown"),
                             "generated_label": item.get("data", {}).get("generated_label"),
                             "audience": item["audience"]}
                            for item in sorted(records, key=lambda record: record["record_id"])]
        request = {"name": name, "audience": audience.value, "purpose": purpose,
                   "record_revisions": record_revisions, "presentation_choices": presentation_choices,
                   "scene_commit_id": scene_commit_id, "narrative_path": narrative_path,
                   "truth_legend": TRUTH_LEGEND, "policy_snapshot": policy_snapshot,
                   "publish": publish, "supersedes_edition_id": supersedes_edition_id}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, LiveForeverEditionRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._edition_result(prior, True)
            if supersedes_edition_id:
                self._scoped(session, LiveForeverEditionRow, supersedes_edition_id, tenant_id, project_id, "edition")
            root = canonical_sha256({k: v for k, v in request.items() if k != "publish"})
            row = LiveForeverEditionRow(edition_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                         idempotency_key=idempotency_key, request_hash=request_hash, name=name,
                                         audience_profile=audience.value, record_revisions_json=record_revisions,
                                         presentation_choices_json={**presentation_choices, "purpose": purpose},
                                         scene_commit_id=scene_commit_id, narrative_path_json=narrative_path,
                                         truth_legend_json=TRUTH_LEGEND, policy_snapshot_json=policy_snapshot,
                                         state="published" if publish else "draft",
                                         supersedes_edition_id=supersedes_edition_id, root_hash=root,
                                         created_by=actor_id, published_at=db_now() if publish else None)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "liveforever:edition_create", "liveforever_edition",
                         row.edition_id, {"audience": audience.value, "state": row.state,
                                          "record_count": len(record_revisions), "root_hash": root},
                         "liveforever.edition.created", "liveforever_edition")
            return self._edition_result(row, False)

    def edition(self, tenant_id: str, project_id: str, *, audience: Audience, purpose: str) -> dict[str, Any]:
        records = self.visible_records(tenant_id, project_id, audience=audience, purpose=purpose)
        body = {"audience": audience.value, "purpose": purpose, "records": records,
                "generated_labels_preserved": True, "truth_legend": TRUTH_LEGEND}
        return {**body, "edition_hash": canonical_sha256(body)}

    def governance_record(self, tenant_id: str, project_id: str, governance_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverGovernanceRow, governance_id, tenant_id, project_id, "governance")
            return {
                "governance_id": row.governance_id, "record_type": row.record_type,
                "subject_id": row.subject_id, "consent_grant_id": row.consent_grant_id,
                "grantor_id": row.grantor_id, "authority_basis": row.authority_basis,
                "data_scope": row.data_scope_json, "purposes": row.purposes_json,
                "modalities": row.modalities_json, "audiences": row.audiences_json,
                "providers": row.providers_json, "geography": row.geography_json,
                "effective_at": row.effective_at.isoformat(),
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "posthumous_rules": row.posthumous_rules_json,
                "evidence_asset_ids": row.evidence_asset_ids_json, "successor_ids": row.successor_ids_json,
                "dispute": row.dispute_json, "state": row.state, "freeze_high_risk": row.freeze_high_risk,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
                "revoked_by": row.revoked_by, "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
            }

    def interview(self, tenant_id: str, project_id: str, interview_id: str, *,
                  include_private_marks: bool = False) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverInterviewRow, interview_id, tenant_id, project_id, "interview")
            segments = list(session.scalars(select(LiveForeverTranscriptSegmentRow).where(
                LiveForeverTranscriptSegmentRow.tenant_id == tenant_id,
                LiveForeverTranscriptSegmentRow.project_id == project_id,
                LiveForeverTranscriptSegmentRow.interview_id == interview_id,
            ).order_by(LiveForeverTranscriptSegmentRow.segment_index)))
            return {
                "interview_id": row.interview_id, "subject_id": row.subject_id,
                "participants": row.participants_json, "consent_context": row.consent_context_json,
                "recording_state": row.recording_state, "source_media_ids": row.source_media_ids_json,
                "timeline": row.timeline_json, "device": row.device_json, "environment": row.environment_json,
                "interruptions": row.interruptions_json, "question_lineage": row.question_lineage_json,
                "pacing_policy": row.pacing_policy_json, "state": row.state,
                "segments": [{
                    "segment_id": item.segment_id, "segment_index": item.segment_index,
                    "start_ms": item.start_ms, "end_ms": item.end_ms, "speaker_label": item.speaker_label,
                    "speaker_confidence": item.speaker_confidence,
                    "text": item.edited_text or item.original_text,
                    "original_text_hash": canonical_sha256({"text": item.original_text}),
                    "correction_history": item.correction_history_json,
                    "private_marks": item.private_marks_json if include_private_marks else [],
                    "private_marks_withheld": bool(item.private_marks_json) and not include_private_marks,
                    "source_media_id": item.source_media_id, "spatial_anchor": item.spatial_anchor_json,
                    "followup_suggestions": item.followup_suggestions_json, "review_state": item.review_state,
                } for item in segments],
            }

    def edition_by_id(self, tenant_id: str, project_id: str, edition_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverEditionRow, edition_id, tenant_id, project_id, "edition")
            return self._edition_payload(row)

    def derivative(self, tenant_id: str, project_id: str, derivative_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverDerivativeRow, derivative_id, tenant_id, project_id, "derivative")
            return {**self._derivative_result(row, False), "source_ids": row.source_ids_json,
                    "subject_ids": row.subject_ids_json, "consent_grant_ids": row.consent_grant_ids_json,
                    "audience": row.audience, "classification": row.classification,
                    "retention": row.retention_json, "provider": row.provider_json,
                    "generation_lineage": row.generation_lineage_json, "policy": row.policy_json,
                    "withdrawal_action": row.withdrawal_action}

    def preservation_release(self, tenant_id: str, project_id: str, release_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, LiveForeverPreservationRow, release_id, tenant_id, project_id, "preservation_release")
            return {**self._preservation_result(row, False), "edition_id": row.edition_id,
                    "originals": row.originals_json, "technical_metadata": row.technical_metadata_json,
                    "rights_consent": row.rights_consent_json, "transcripts": row.transcripts_json,
                    "memory_graph": row.memory_graph_json, "scene_manifests": row.scene_manifests_json,
                    "open_assets": row.open_assets_json, "human_guide": row.human_guide_json,
                    "offline_fallback": row.offline_fallback_json, "fixity": row.fixity_json,
                    "replicas": row.replicas_json, "format_migrations": row.format_migrations_json,
                    "succession": row.succession_json, "shutdown": row.shutdown_json}

    def memory_room(self, tenant_id: str, project_id: str, *, subject_id: str, audience: Audience,
                    purpose: str, include_private_transcript_marks: bool = False) -> dict[str, Any]:
        if include_private_transcript_marks and audience is not Audience.PRIVATE:
            raise AuthorizationError(
                "PRIVATE_TRANSCRIPT_MARKS_DENIED",
                "private transcript marks are available only in the private audience context",
            )
        records = self.visible_records(tenant_id, project_id, audience=audience, purpose=purpose)
        subject_records = [item for item in records if item.get("subject_id") in {None, subject_id}]
        visible_record_ids = {item["record_id"] for item in subject_records}
        with self.database.session() as session:
            editions = list(session.scalars(select(LiveForeverEditionRow).where(
                LiveForeverEditionRow.tenant_id == tenant_id,
                LiveForeverEditionRow.project_id == project_id,
                LiveForeverEditionRow.audience_profile == audience.value,
            ).order_by(LiveForeverEditionRow.created_at.desc())))
            interviews = list(session.scalars(select(LiveForeverInterviewRow).where(
                LiveForeverInterviewRow.tenant_id == tenant_id,
                LiveForeverInterviewRow.project_id == project_id,
                LiveForeverInterviewRow.subject_id == subject_id,
            ).order_by(LiveForeverInterviewRow.created_at)))
            disputes = list(session.scalars(select(LiveForeverGovernanceRow).where(
                LiveForeverGovernanceRow.tenant_id == tenant_id,
                LiveForeverGovernanceRow.project_id == project_id,
                LiveForeverGovernanceRow.subject_id == subject_id,
                LiveForeverGovernanceRow.record_type == "dispute",
            )))
        interview_summaries: list[dict[str, Any]] = []
        try:
            self._require_consent(
                tenant_id, project_id, subject_id, purpose=purpose, audience=audience, scope="interview"
            )
        except AuthorizationError:
            interviews_withheld = bool(interviews)
        else:
            interviews_withheld = False
            interview_summaries = [
                self.interview(
                    tenant_id, project_id, item.interview_id,
                    include_private_marks=include_private_transcript_marks,
                )
                for item in interviews
            ]
        selected_edition = None
        edition_withheld = False
        if editions:
            candidate = self._edition_payload(editions[0])
            revision_ids = {item.get("record_id") for item in candidate.get("record_revisions", [])}
            if revision_ids.issubset(visible_record_ids):
                selected_edition = candidate
            else:
                edition_withheld = True
        experience = self.experience_configuration(tenant_id, project_id, subject_id,
                                                    requested_features={"autoplay": False, "ambient_sound": False},
                                                    audience=audience)
        body = {
            "subject_id": subject_id, "audience": audience.value, "purpose": purpose,
            "edition": selected_edition, "edition_withheld_by_current_policy": edition_withheld,
            "records": subject_records, "interviews": interview_summaries,
            "interviews_withheld_by_current_policy": interviews_withheld,
            "disputes": [self.governance_record(tenant_id, project_id, item.governance_id) for item in disputes],
            "experience": experience, "truth_legend": TRUTH_LEGEND,
            "presentation_rules": {
                "generated_presence_disabled": True, "voice_cloning_disabled": True,
                "likeness_simulation_disabled": True, "conflicts_preserved": True,
                "evidence_mode_available": True, "quiet_mode_available": True,
                "safe_exit_persistent": True,
            },
        }
        return {**body, "room_hash": canonical_sha256(body)}

    def register_derivative(self, *, tenant_id: str, project_id: str, derivative_type: str,
                            source_ids: list[str], subject_ids: list[str], consent_grant_ids: list[str],
                            audience: Audience, classification: str, retention: dict[str, Any],
                            provider: dict[str, Any], generation_lineage: dict[str, Any],
                            policy: dict[str, Any], actor_id: str, idempotency_key: str) -> dict[str, Any]:
        if not source_ids or not subject_ids or not consent_grant_ids:
            raise ValidationError("DERIVATIVE_DEPENDENCIES", "derivative requires source, subject, and consent dependencies")
        external = provider.get("execution") == "external"
        if external:
            if not provider.get("approved"):
                raise AuthorizationError("EXTERNAL_PROVIDER_NOT_APPROVED", "external provider is denied by default")
            required_provider_fields = {
                "provider_id", "approval_receipt_sha256", "approved_region", "retention_days",
                "allowed_classifications", "allowed_purposes",
            }
            missing_provider_fields = sorted(
                key for key in required_provider_fields if provider.get(key) in (None, "", [], {})
            )
            if missing_provider_fields:
                raise AuthorizationError(
                    "EXTERNAL_PROVIDER_APPROVAL_INCOMPLETE",
                    "external execution requires a complete, reviewable provider approval receipt",
                    {"missing": missing_provider_fields},
                )
            receipt = str(provider["approval_receipt_sha256"]).removeprefix("sha256:").lower()
            if not re.fullmatch(r"[a-f0-9]{64}", receipt):
                raise AuthorizationError("EXTERNAL_PROVIDER_RECEIPT_INVALID", "provider approval receipt must be a SHA-256 digest")
            if classification not in set(provider.get("allowed_classifications", [])):
                raise AuthorizationError("EXTERNAL_PROVIDER_CLASSIFICATION_DENIED", "provider approval does not permit this classification")
            requested_purpose = policy.get("purpose", "preservation")
            if requested_purpose not in set(provider.get("allowed_purposes", [])):
                raise AuthorizationError("EXTERNAL_PROVIDER_PURPOSE_DENIED", "provider approval does not permit this purpose")
            if int(provider.get("retention_days", -1)) < 0:
                raise AuthorizationError("EXTERNAL_PROVIDER_RETENTION_INVALID", "provider retention must be explicit and non-negative")
            provider = {**provider, "approval_receipt_sha256": receipt}
        if derivative_type in {"voice", "likeness", "dialogue", "first_person"}:
            raise AuthorizationError("GENERATED_PRESENCE_DISABLED", "voice, likeness, dialogue, and first-person simulation remain disabled")
        lineage = self._validate_generated_lineage(generation_lineage) if generation_lineage else {}
        for subject in subject_ids:
            self._require_consent(tenant_id, project_id, subject, purpose=policy.get("purpose", "preservation"),
                                  audience=audience, scope=derivative_type)
            self._enforce_high_risk_freeze(tenant_id, project_id, subject, modality=derivative_type)
        request = {"derivative_type": derivative_type, "source_ids": sorted(set(source_ids)),
                   "subject_ids": sorted(set(subject_ids)), "consent_grant_ids": sorted(set(consent_grant_ids)),
                   "audience": audience.value, "classification": classification, "retention": retention,
                   "provider": provider, "generation_lineage": lineage, "policy": policy}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            for grant_id in consent_grant_ids:
                grant = session.get(ConsentGrantRow, grant_id)
                if not grant or grant.tenant_id != tenant_id or grant.project_id != project_id or grant.state != "active":
                    raise AuthorizationError("CONSENT_DEPENDENCY_INVALID", "derivative consent dependency is missing or inactive")
            prior = self._idempotent(session, LiveForeverDerivativeRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._derivative_result(prior, True)
            row = LiveForeverDerivativeRow(derivative_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                            idempotency_key=idempotency_key, request_hash=request_hash,
                                            derivative_type=derivative_type, source_ids_json=sorted(set(source_ids)),
                                            subject_ids_json=sorted(set(subject_ids)),
                                            consent_grant_ids_json=sorted(set(consent_grant_ids)),
                                            audience=audience.value, classification=classification,
                                            retention_json=retention, provider_json=provider,
                                            generation_lineage_json=lineage,
                                            policy_json={**policy, "generated_label": "AI-GENERATED / RECONSTRUCTED"},
                                            state="active", withdrawal_action=None, created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "liveforever:derivative_register",
                         "liveforever_derivative", row.derivative_id,
                         {"derivative_type": derivative_type, "audience": audience.value,
                          "provider_execution": provider.get("execution", "local")},
                         "liveforever.derivative.registered", "liveforever_derivative")
            return self._derivative_result(row, False)

    def experience_configuration(self, tenant_id: str, project_id: str, subject_id: str, *,
                                 requested_features: dict[str, bool], audience: Audience) -> dict[str, Any]:
        config = {**EXPERIENCE_FEATURES_DEFAULT}
        config.update({k: bool(v) for k, v in requested_features.items() if k in config})
        presence = {"voice_simulation", "likeness_simulation", "first_person_dialogue", "autonomous_persona"}
        enabled_presence = sorted(key for key in presence if config.get(key))
        if enabled_presence:
            if self.kill_switches.get("all_generated_presence", True):
                raise AuthorizationError("PRESENCE_KILL_SWITCH", "generated presence is disabled by the global kill switch")
            for feature in enabled_presence:
                switch = "dialogue" if feature in {"first_person_dialogue", "autonomous_persona"} else feature.split("_")[0]
                if self.kill_switches.get(switch, True):
                    raise AuthorizationError("PRESENCE_KILL_SWITCH", f"{feature} is disabled")
                self._require_consent(tenant_id, project_id, subject_id, purpose="immersive_presence",
                                      audience=audience, scope=feature)
                self._enforce_high_risk_freeze(tenant_id, project_id, subject_id, modality=feature)
        config.update({"quiet_mode": True, "safe_exit": True, "pause": True, "reset": True,
                       "free_locomotion": False, "evidence_mode": True})
        return {"subject_id": subject_id, "features": config,
                "generated_presence_label": "SIMULATED / GENERATED" if enabled_presence else None,
                "safe_exit_persistent": True, "reduced_motion_supported": True,
                "captions_required": True, "truth_legend": TRUTH_LEGEND,
                "navigation_alternatives": ["guided", "timeline", "person", "place", "object", "quiet", "evidence"]}

    def set_kill_switch(self, key: str, enabled: bool, *, actor_id: str) -> None:
        if key not in self.kill_switches:
            raise ValidationError("KILL_SWITCH_UNKNOWN", "unknown presence kill switch")
        self.kill_switches[key] = enabled

    # Open preservation -------------------------------------------------------------------------
    def create_preservation_release(self, *, tenant_id: str, project_id: str, edition_id: str,
                                    destination: Path, originals: list[dict[str, Any]],
                                    technical_metadata: dict[str, Any], rights_consent: list[dict[str, Any]],
                                    memory_graph: dict[str, Any], scene_manifests: list[dict[str, Any]],
                                    open_assets: list[dict[str, Any]], human_guide: dict[str, Any],
                                    offline_fallback: dict[str, Any], replicas: list[dict[str, Any]],
                                    format_migrations: list[dict[str, Any]], succession: dict[str, Any],
                                    shutdown: dict[str, Any], actor_id: str, idempotency_key: str) -> dict[str, Any]:
        if not originals or not human_guide or not offline_fallback:
            raise ValidationError("PRESERVATION_RELEASE_INCOMPLETE", "preservation requires originals, a human guide, and offline fallback")
        request = {"edition_id": edition_id, "originals": originals, "technical_metadata": technical_metadata,
                   "rights_consent": rights_consent, "memory_graph": memory_graph,
                   "scene_manifests": scene_manifests, "open_assets": open_assets,
                   "human_guide": human_guide, "offline_fallback": offline_fallback,
                   "replicas": replicas, "format_migrations": format_migrations,
                   "succession": succession, "shutdown": shutdown, "destination_name": destination.name}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            edition = self._scoped(session, LiveForeverEditionRow, edition_id, tenant_id, project_id, "edition")
            prior = self._idempotent(session, LiveForeverPreservationRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior and prior.status == "verified" and prior.package_path and Path(prior.package_path).is_file():
                return self._preservation_result(prior, True)
            edition_payload = self._edition_payload(edition)
            edition_audience = Audience(edition.audience_profile)
            edition_purpose = str(edition.presentation_choices_json.get("purpose", "preservation"))
            revision_by_id = {
                str(item.get("record_id")): item for item in edition.record_revisions_json if item.get("record_id")
            }
            record_ids = sorted(revision_by_id)
            record_rows = list(session.scalars(select(MemoryRecordRow).where(
                MemoryRecordRow.tenant_id == tenant_id,
                MemoryRecordRow.project_id == project_id,
                MemoryRecordRow.record_id.in_(record_ids) if record_ids else False,
            ))) if record_ids else []
            row_by_id = {row.record_id: row for row in record_rows}
            missing_records = sorted(set(record_ids) - set(row_by_id))
            if missing_records:
                raise AuthorizationError(
                    "PRESERVATION_EDITION_RECORD_MISSING",
                    "edition references records that are no longer available for preservation",
                    {"record_ids": missing_records},
                )
            active_grants = list(session.scalars(select(ConsentGrantRow).where(
                ConsentGrantRow.tenant_id == tenant_id,
                ConsentGrantRow.project_id == project_id,
                ConsentGrantRow.state == "active",
            )))
            grants_by_subject: dict[str, list[ConsentGrantRow]] = {}
            for grant in active_grants:
                grants_by_subject.setdefault(grant.subject_id, []).append(grant)
            preserved_records: list[dict[str, Any]] = []
            stale_or_denied: list[str] = []
            for record_id in record_ids:
                row = row_by_id[record_id]
                if row.audience not in _allowed_record_audiences(edition_audience) or row.data_json.get("derivative_access_disabled"):
                    stale_or_denied.append(record_id)
                    continue
                if row.subject_id and not any(
                    _grant_permits(grant, purpose=edition_purpose, audience=edition_audience, scope=row.record_type)
                    for grant in grants_by_subject.get(row.subject_id, [])
                ):
                    stale_or_denied.append(record_id)
                    continue
                payload = self._memory_payload(row)
                expected_hash = str(revision_by_id[record_id].get("record_hash", ""))
                if expected_hash and canonical_sha256(payload) != expected_hash:
                    raise ConflictError(
                        "PRESERVATION_EDITION_RECORD_DRIFT",
                        "edition record bytes no longer match the retained edition revision",
                        {"record_id": record_id},
                    )
                preserved_records.append(payload)
            if stale_or_denied:
                raise AuthorizationError(
                    "PRESERVATION_EDITION_POLICY_STALE",
                    "current consent or audience policy no longer permits every edition record",
                    {"record_ids": stale_or_denied},
                )
            subject_ids = sorted({item["subject_id"] for item in preserved_records if item.get("subject_id")})
            interview_rows = list(session.scalars(select(LiveForeverInterviewRow).where(
                LiveForeverInterviewRow.tenant_id == tenant_id,
                LiveForeverInterviewRow.project_id == project_id,
                LiveForeverInterviewRow.subject_id.in_(subject_ids) if subject_ids else False,
            ))) if subject_ids else []
            permitted_interview_ids = {
                interview.interview_id for interview in interview_rows
                if any(
                    _grant_permits(grant, purpose=edition_purpose, audience=edition_audience, scope="interview")
                    for grant in grants_by_subject.get(interview.subject_id, [])
                )
            }
            segments = list(session.scalars(select(LiveForeverTranscriptSegmentRow).where(
                LiveForeverTranscriptSegmentRow.tenant_id == tenant_id,
                LiveForeverTranscriptSegmentRow.project_id == project_id,
                LiveForeverTranscriptSegmentRow.interview_id.in_(sorted(permitted_interview_ids))
                if permitted_interview_ids else False,
            ).order_by(LiveForeverTranscriptSegmentRow.interview_id,
                       LiveForeverTranscriptSegmentRow.segment_index))) if permitted_interview_ids else []
            transcripts = [{"segment_id": segment.segment_id, "interview_id": segment.interview_id,
                            "index": segment.segment_index, "start_ms": segment.start_ms, "end_ms": segment.end_ms,
                            "speaker": segment.speaker_label, "speaker_confidence": segment.speaker_confidence,
                            "text": segment.edited_text or segment.original_text,
                            "original_text_hash": canonical_sha256({"text": segment.original_text}),
                            "corrections": segment.correction_history_json,
                            "private_marks": segment.private_marks_json if edition_audience is Audience.PRIVATE else [],
                            "private_marks_withheld": bool(segment.private_marks_json) and edition_audience is not Audience.PRIVATE,
                            "source_media_id": segment.source_media_id,
                            "spatial_anchor": segment.spatial_anchor_json, "review_state": segment.review_state}
                           for segment in segments]
            preserved_memory_graph = {**memory_graph, "edition_records": preserved_records,
                                      "truth_legend": TRUTH_LEGEND}
            body = {"format": "SIP-LIVEFOREVER-PRESERVATION-1.0", "project_id": project_id,
                    "edition": edition_payload, "originals": originals,
                    "technical_metadata": technical_metadata, "rights_consent": rights_consent,
                    "transcripts": transcripts, "memory_graph": preserved_memory_graph,
                    "scene_manifests": scene_manifests, "open_assets": open_assets,
                    "human_guide": human_guide, "offline_fallback": offline_fallback,
                    "replicas": replicas, "format_migrations": format_migrations,
                    "succession": succession, "shutdown": shutdown,
                    "truth_legend": TRUTH_LEGEND,
                    "limitations": ["No voice, likeness, dialogue, or first-person simulation is included.",
                                    "Recollection, corroboration, inference, reconstruction, and fact remain distinct."]}
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_suffix(destination.suffix + ".tmp")
            checks: dict[str, str] = {}
            with zipfile.ZipFile(temp, "w") as archive:
                files = {
                    "manifest.json": canonical_json({k: v for k, v in body.items() if k not in {"transcripts", "memory_graph"}}),
                    "data/edition.json": canonical_json(body["edition"]),
                    "data/transcripts.json": canonical_json(transcripts),
                    "data/memory-graph.json": canonical_json(body["memory_graph"]),
                    "data/rights-consent.json": canonical_json(rights_consent),
                    "data/scene-manifests.json": canonical_json(scene_manifests),
                    "data/originals.json": canonical_json(originals),
                    "data/open-assets.json": canonical_json(open_assets),
                    "viewer/index.html": self._offline_memory_viewer(body).encode(),
                    "README.txt": ("Open SIP LiveForever preservation package. Verify checksums.json.\n"
                                   "This package deliberately excludes voice cloning and likeness simulation.\n").encode(),
                }
                for name, data in sorted(files.items()):
                    checks[name] = _zip_write(archive, name, data)
                root = merkle_root(checks.items())
                _zip_write(archive, "checksums.json", canonical_json({"algorithm": "sha256", "files": checks, "root_hash": root}))
            temp.replace(destination)
            validation = self.verify_preservation_release(destination)
            if prior:
                row = prior
            else:
                row = LiveForeverPreservationRow(release_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                                  idempotency_key=idempotency_key, request_hash=request_hash,
                                                  edition_id=edition_id, originals_json=originals,
                                                  technical_metadata_json=technical_metadata,
                                                  rights_consent_json=rights_consent, transcripts_json=transcripts,
                                                  memory_graph_json=preserved_memory_graph, scene_manifests_json=scene_manifests,
                                                  open_assets_json=open_assets, checksums_json=checks,
                                                  human_guide_json=human_guide, offline_fallback_json=offline_fallback,
                                                  fixity_json={"algorithm": "sha256", "root_hash": validation["root_hash"]},
                                                  replicas_json=replicas, format_migrations_json=format_migrations,
                                                  succession_json=succession, shutdown_json=shutdown,
                                                  package_path=str(destination), root_hash=validation["root_hash"],
                                                  status="verified" if validation["valid"] else "failed",
                                                  validation_json=validation, created_by=actor_id)
                session.add(row)
            row.package_path = str(destination)
            row.root_hash = validation["root_hash"]
            row.status = "verified" if validation["valid"] else "failed"
            row.validation_json = validation
            self._record(session, tenant_id, project_id, actor_id, "liveforever:preservation_create",
                         "liveforever_preservation", row.release_id,
                         {"edition_id": edition_id, "root_hash": row.root_hash, "status": row.status},
                         "liveforever.preservation.created", "liveforever_preservation")
            return self._preservation_result(row, False)

    @staticmethod
    def verify_preservation_release(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ValidationError("PRESERVATION_PACKAGE_MISSING", "preservation package does not exist")
        with zipfile.ZipFile(path) as archive:
            names = validate_zip_members(archive.infolist(), code_prefix="PRESERVATION")
            required = {"manifest.json", "checksums.json", "viewer/index.html", "data/edition.json",
                        "data/transcripts.json", "data/memory-graph.json", "data/rights-consent.json"}
            missing = sorted(required - set(names))
            if missing:
                raise ValidationError("PRESERVATION_PACKAGE_INCOMPLETE", "package is incomplete", {"missing": missing})
            checks = json.loads(archive.read("checksums.json"))
            findings = []
            for name, expected in checks.get("files", {}).items():
                if name not in names:
                    findings.append({"path": name, "reason": "missing"})
                elif sha256_bytes(archive.read(name)) != expected:
                    findings.append({"path": name, "reason": "hash_mismatch"})
            root = merkle_root(checks.get("files", {}).items())
            if root != checks.get("root_hash"):
                findings.append({"path": "checksums.json", "reason": "root_mismatch"})
        return {"valid": not findings, "findings": findings, "root_hash": root,
                "zip_sha256": sha256_file(path), "member_count": len(names)}

    # Internal helpers --------------------------------------------------------------------------
    @staticmethod
    def _memory_payload(row: MemoryRecordRow) -> dict[str, Any]:
        return {
            "record_id": row.record_id,
            "record_type": row.record_type,
            "subject_id": row.subject_id,
            "related_ids": row.related_ids_json,
            "data": row.data_json,
            "source_class": row.source_class,
            "source_label": row.data_json.get("source_label", "unknown"),
            "confidence": row.confidence,
            "evidence_asset_ids": row.evidence_asset_ids_json,
            "audience": row.audience,
            "generated_lineage": row.generated_lineage_json,
            "contributor_id": row.created_by,
            "created_at": row.created_at.isoformat(),
            "status": row.data_json.get("status", "active"),
        }

    def _require_consent(self, tenant_id: str, project_id: str, subject_id: str, *, purpose: str,
                         audience: Audience, scope: str) -> ConsentGrantRow:
        with self.database.session() as session:
            grants = list(session.scalars(select(ConsentGrantRow).where(
                ConsentGrantRow.tenant_id == tenant_id, ConsentGrantRow.project_id == project_id,
                ConsentGrantRow.subject_id == subject_id, ConsentGrantRow.state == "active")))
        now = db_now()
        for grant in grants:
            if grant.expires_at and _aware(grant.expires_at) <= now:
                continue
            if purpose in grant.purposes_json and audience.value in grant.audiences_json and (scope in grant.scopes_json or "*" in grant.scopes_json):
                return grant
        raise AuthorizationError("CONSENT_REQUIRED", "no active consent grant permits this purpose, audience, and scope",
                                 {"subject_id": subject_id, "purpose": purpose, "audience": audience.value, "scope": scope})

    def _enforce_high_risk_freeze(self, tenant_id: str, project_id: str, subject_id: str, *, modality: str) -> None:
        high_risk = (
            modality in {"generated", "generated_reconstruction", "visual_reconstruction", "voice", "likeness",
                         "dialogue", "first_person", "first_person_dialogue", "autonomous_persona",
                         "immersive_presence"}
            or modality.startswith("generated_")
        )
        if not high_risk:
            return
        with self.database.session() as session:
            rows = list(session.scalars(select(LiveForeverGovernanceRow).where(
                LiveForeverGovernanceRow.tenant_id == tenant_id,
                LiveForeverGovernanceRow.project_id == project_id,
                LiveForeverGovernanceRow.subject_id == subject_id,
                LiveForeverGovernanceRow.freeze_high_risk.is_(True),
            )))
        blocking_types = {"dispute", "freeze", "minor_protection", "living_third_party"}
        blocking = [
            row for row in rows
            if row.record_type in blocking_types
            or row.state in {"disputed", "revoked"}
            or bool((row.dispute_json or {}).get("active"))
        ]
        if blocking:
            raise AuthorizationError("SUBJECT_HIGH_RISK_FROZEN", "high-risk generated use is frozen by family governance")

    @staticmethod
    def _validate_generated_lineage(value: dict[str, Any] | None) -> dict[str, Any]:
        if not value:
            raise ValidationError("GENERATED_LINEAGE_REQUIRED", "generated record requires model, prompt, input, and output lineage")
        required = {"model_manifest_id", "model_checkpoint_hash", "prompt_hash", "input_asset_ids", "output_hash"}
        missing = sorted(required - value.keys())
        if missing:
            raise ValidationError("GENERATED_LINEAGE_INCOMPLETE", "generated lineage is incomplete", {"missing": missing})
        for key in {"model_checkpoint_hash", "prompt_hash", "output_hash"}:
            if not re.fullmatch(r"[a-f0-9]{64}", str(value[key])):
                raise ValidationError("GENERATED_LINEAGE_HASH", f"{key} must be a SHA-256 digest")
        return value

    def _record(self, session: Session, tenant_id: str, project_id: str, actor_id: str, action: str,
                resource_type: str, resource_id: str, details: dict[str, Any], event_type: str,
                aggregate_type: str) -> None:
        self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action=action,
                          resource_type=resource_type, resource_id=resource_id, outcome="allowed",
                          details=details, session=session)
        event = self.events.create(session, event_type=event_type, schema_version="1.0.0", tenant_id=tenant_id,
                                   project_id=project_id, aggregate_type=aggregate_type, aggregate_id=resource_id,
                                   payload={"resource_id": resource_id, **details}, producer="liveforever",
                                   actor_id=actor_id, workload_identity=None)
        session.add(event)

    @staticmethod
    def _idempotent(session: Session, model: type[T], tenant_id: str, project_id: str,
                    key: str, request_hash: str) -> T | None:
        row = session.scalar(select(model).where(model.tenant_id == tenant_id, model.project_id == project_id,
                                                 model.idempotency_key == key))
        if row and row.request_hash != request_hash:
            raise ConflictError("IDEMPOTENCY_PAYLOAD_CONFLICT", "idempotency key was reused with different input")
        return row

    @staticmethod
    def _scoped(session: Session, model: type[T], identifier: str, tenant_id: str, project_id: str, label: str) -> T:
        row = session.get(model, identifier)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError(label, identifier)
        return row

    @staticmethod
    def _governance_result(row: LiveForeverGovernanceRow, replay: bool) -> dict[str, Any]:
        return {"governance_id": row.governance_id, "record_type": row.record_type, "subject_id": row.subject_id,
                "state": row.state, "freeze_high_risk": row.freeze_high_risk, "idempotent_replay": replay}

    @staticmethod
    def _interview_result(row: LiveForeverInterviewRow, replay: bool) -> dict[str, Any]:
        return {"interview_id": row.interview_id, "subject_id": row.subject_id, "state": row.state,
                "recording_state": row.recording_state, "idempotent_replay": replay}

    @staticmethod
    def _segment_result(row: LiveForeverTranscriptSegmentRow, replay: bool) -> dict[str, Any]:
        return {"segment_id": row.segment_id, "interview_id": row.interview_id,
                "segment_index": row.segment_index, "review_state": row.review_state,
                "speaker_confidence": row.speaker_confidence, "text": row.edited_text or row.original_text,
                "correction_count": len(row.correction_history_json), "idempotent_replay": replay}

    @staticmethod
    def _edition_result(row: LiveForeverEditionRow, replay: bool) -> dict[str, Any]:
        return {"edition_id": row.edition_id, "name": row.name, "audience": row.audience_profile,
                "state": row.state, "root_hash": row.root_hash,
                "record_count": len(row.record_revisions_json), "idempotent_replay": replay}

    @staticmethod
    def _edition_payload(row: LiveForeverEditionRow) -> dict[str, Any]:
        return {"edition_id": row.edition_id, "name": row.name, "audience": row.audience_profile,
                "record_revisions": row.record_revisions_json,
                "presentation_choices": row.presentation_choices_json,
                "scene_commit_id": row.scene_commit_id, "narrative_path": row.narrative_path_json,
                "truth_legend": row.truth_legend_json, "policy_snapshot": row.policy_snapshot_json,
                "state": row.state, "root_hash": row.root_hash}

    @staticmethod
    def _derivative_result(row: LiveForeverDerivativeRow, replay: bool) -> dict[str, Any]:
        return {"derivative_id": row.derivative_id, "derivative_type": row.derivative_type,
                "state": row.state, "withdrawal_action": row.withdrawal_action,
                "idempotent_replay": replay}

    @staticmethod
    def _preservation_result(row: LiveForeverPreservationRow, replay: bool) -> dict[str, Any]:
        return {"release_id": row.release_id, "edition_id": row.edition_id, "status": row.status,
                "package_path": row.package_path, "root_hash": row.root_hash,
                "validation": row.validation_json, "idempotent_replay": replay}

    @staticmethod
    def _offline_memory_viewer(body: dict[str, Any]) -> str:
        return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>LiveForever Preservation</title><style>body{font:16px system-ui;max-width:70rem;margin:auto;padding:2rem}.notice{border:2px solid;padding:1rem}</style>
<h1>%s</h1><p class='notice'>Recollection, corroboration, inference, generated reconstruction, and historical fact are shown as distinct source classes. No voice or likeness simulation is included.</p><p>Audience: %s</p><p>Records: %d</p><p>Transcripts: %d</p><p>This viewer is static, accessible, read-only, and does not require a proprietary renderer or network connection.</p></html>""" % (
            escape(body["edition"]["name"]), escape(body["edition"]["audience"]),
            len(body["edition"]["record_revisions"]), len(body["transcripts"]))


def _allowed_record_audiences(audience: Audience) -> set[str]:
    return {
        Audience.PRIVATE: {Audience.PRIVATE.value, Audience.FAMILY.value, Audience.PUBLIC.value},
        Audience.FAMILY: {Audience.FAMILY.value, Audience.PUBLIC.value},
        Audience.PUBLIC: {Audience.PUBLIC.value},
        Audience.PROJECT: {Audience.PROJECT.value, Audience.PUBLIC.value},
        Audience.OWNER: {Audience.OWNER.value, Audience.PROJECT.value, Audience.PUBLIC.value},
    }[audience]


def _grant_permits(grant: ConsentGrantRow, *, purpose: str, audience: Audience, scope: str) -> bool:
    if grant.state != "active":
        return False
    if grant.expires_at and _aware(grant.expires_at) <= db_now():
        return False
    return (
        purpose in grant.purposes_json
        and audience.value in grant.audiences_json
        and (scope in grant.scopes_json or "*" in grant.scopes_json)
    )


def _normalize_time_expression(value: Any) -> dict[str, Any]:
    if value in (None, "", {}):
        return {"kind": "unknown"}
    if isinstance(value, str):
        return {"kind": "qualitative", "label": value}
    if not isinstance(value, dict):
        raise ValidationError("MEMORY_TIME_EXPRESSION", "time expression must be a governed object or qualitative label")
    kind = str(value.get("kind", "unknown"))
    if kind == "approximate":
        if value.get("year") is not None:
            year = int(value["year"])
            return {"kind": "bounded", "start": f"{year:04d}-01-01", "end": f"{year:04d}-12-31",
                    "basis": value.get("basis", "approximate_year"), "confidence": value.get("confidence")}
        label = str(value.get("label") or value.get("value") or "approximately dated")
        return {"kind": "qualitative", "label": label, "basis": value.get("basis", "approximate")}
    if kind not in {"exact", "bounded", "qualitative", "unknown"}:
        raise ValidationError("MEMORY_TIME_EXPRESSION", "unsupported time-expression kind")
    if kind == "exact":
        if not value.get("value") or value.get("approximate") is True:
            raise ValidationError("MEMORY_TIME_PRECISION", "an approximate time cannot be represented as exact")
        return {"kind": "exact", "value": str(value["value"]), "basis": value.get("basis")}
    if kind == "bounded":
        if not value.get("start") or not value.get("end"):
            raise ValidationError("MEMORY_TIME_RANGE", "bounded time requires start and end")
        return {"kind": "bounded", "start": str(value["start"]), "end": str(value["end"]),
                "basis": value.get("basis"), "confidence": value.get("confidence")}
    if kind == "qualitative":
        if not str(value.get("label", "")).strip():
            raise ValidationError("MEMORY_TIME_QUALITATIVE", "qualitative time requires a label")
        return {"kind": "qualitative", "label": str(value["label"]), "basis": value.get("basis")}
    return {"kind": "unknown", "basis": value.get("basis")}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
