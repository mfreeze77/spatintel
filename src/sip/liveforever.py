from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .database import ConsentGrantRow, Database, MemoryRecordRow
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .models import Audience, SourceClass
from .temporal import db_now


MEMORY_TYPES = {
    "person",
    "relationship",
    "place",
    "object",
    "event",
    "memory",
    "timeline",
    "interview",
    "speaker",
    "transcript_segment",
    "photograph",
    "recording",
    "video",
    "document",
    "letter",
    "story_anchor",
    "edition",
    "generated_reconstruction",
}

EXPERIENCE_FEATURES_DEFAULT = {
    "voice_simulation": False,
    "likeness_simulation": False,
    "first_person_dialogue": False,
    "autonomous_persona": False,
    "quiet_mode": True,
    "safe_exit": True,
    "pause": True,
    "reset": True,
    "free_locomotion": False,
}


class LiveForeverService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit
        self.kill_switches: dict[str, bool] = {"all_generated_presence": True, "voice": True, "likeness": True, "dialogue": True}

    def grant_consent(
        self,
        *,
        tenant_id: str,
        project_id: str,
        subject_id: str,
        granted_by: str,
        purposes: list[str],
        audiences: list[Audience],
        scopes: list[str],
        derivative_policy: dict[str, Any],
        expires_at: datetime | None,
    ) -> str:
        if not purposes or not audiences or not scopes:
            raise ValidationError("CONSENT_SCOPE_REQUIRED", "consent requires purpose, audience, and scope")
        if expires_at and _aware(expires_at) <= db_now():
            raise ValidationError("CONSENT_EXPIRY_INVALID", "consent cannot be created already expired")
        grant_id = new_uuid()
        with self.database.session() as session:
            session.add(
                ConsentGrantRow(
                    grant_id=grant_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    subject_id=subject_id,
                    granted_by=granted_by,
                    purposes_json=purposes,
                    audiences_json=[item.value for item in audiences],
                    scopes_json=scopes,
                    derivative_policy_json=derivative_policy,
                    expires_at=expires_at,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=granted_by,
                action="consent:grant",
                resource_type="consent_grant",
                resource_id=grant_id,
                outcome="allowed",
                details={"subject_id": subject_id, "purposes": purposes, "audiences": [item.value for item in audiences], "scopes": scopes},
                session=session,
            )
        return grant_id

    def revoke_consent(self, grant_id: str, *, actor_id: str, reason: str) -> dict[str, Any]:
        with self.database.session() as session:
            grant = session.get(ConsentGrantRow, grant_id)
            if not grant:
                raise NotFoundError("consent_grant", grant_id)
            if grant.state == "revoked":
                return {"grant_id": grant_id, "state": "revoked", "affected_records": 0}
            grant.state = "revoked"
            grant.revoked_at = db_now()
            grant.revoked_by = actor_id
            affected = list(
                session.scalars(
                    select(MemoryRecordRow).where(
                        MemoryRecordRow.tenant_id == grant.tenant_id,
                        MemoryRecordRow.project_id == grant.project_id,
                        MemoryRecordRow.subject_id == grant.subject_id,
                    )
                )
            )
            for row in affected:
                row.data_json = {
                    **row.data_json,
                    "access_state": "consent_revoked_review_required",
                    "revoked_grant_id": grant_id,
                    "revocation_reason": reason,
                    "derivative_access_disabled": True,
                }
            self.audit.append(
                tenant_id=grant.tenant_id,
                project_id=grant.project_id,
                actor_id=actor_id,
                action="consent:revoke",
                resource_type="consent_grant",
                resource_id=grant_id,
                outcome="allowed",
                details={"reason": reason, "affected_records": len(affected)},
                session=session,
            )
            return {"grant_id": grant_id, "state": "revoked", "affected_records": len(affected)}

    def create_record(
        self,
        *,
        tenant_id: str,
        project_id: str,
        record_type: str,
        subject_id: str | None,
        related_ids: list[str],
        data: dict[str, Any],
        source_class: SourceClass,
        confidence: float,
        evidence_asset_ids: list[str],
        audience: Audience,
        actor_id: str,
        purpose: str = "preservation",
        generated_lineage: dict[str, Any] | None = None,
    ) -> str:
        if record_type not in MEMORY_TYPES:
            raise ValidationError("MEMORY_RECORD_TYPE", "unsupported LiveForever record type")
        if not 0 <= confidence <= 1:
            raise ValidationError("MEMORY_CONFIDENCE", "confidence must be between zero and one")
        if source_class in {SourceClass.CORROBORATED, SourceClass.VERIFIED} and not evidence_asset_ids:
            raise ValidationError("MEMORY_EVIDENCE_REQUIRED", "corroborated or verified claims require evidence")
        if source_class == SourceClass.GENERATED:
            if not generated_lineage:
                raise ValidationError("GENERATED_LINEAGE_REQUIRED", "generated record requires model, prompt, input, and output lineage")
            required = {"model_manifest_id", "model_checkpoint_hash", "prompt_hash", "input_asset_ids", "output_hash"}
            missing = sorted(required - generated_lineage.keys())
            if missing:
                raise ValidationError("GENERATED_LINEAGE_INCOMPLETE", "generated lineage is incomplete", {"missing": missing})
            data = {**data, "generated_label": "AI-GENERATED RECONSTRUCTION — NOT A HISTORICAL FACT"}
        if subject_id:
            self._require_consent(tenant_id, project_id, subject_id, purpose=purpose, audience=audience, scope=record_type)
        record_id = new_uuid()
        with self.database.session() as session:
            session.add(
                MemoryRecordRow(
                    record_id=record_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type=record_type,
                    subject_id=subject_id,
                    related_ids_json=related_ids,
                    data_json={**data, "access_state": "active"},
                    source_class=source_class.value,
                    confidence=confidence,
                    evidence_asset_ids_json=evidence_asset_ids,
                    audience=audience.value,
                    generated_lineage_json=generated_lineage,
                    created_by=actor_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="liveforever:record_create",
                resource_type="memory_record",
                resource_id=record_id,
                outcome="allowed",
                details={"record_type": record_type, "source_class": source_class.value, "audience": audience.value},
                session=session,
            )
        return record_id

    def conflicting_recollections(
        self,
        *,
        tenant_id: str,
        project_id: str,
        subject_id: str,
        event_key: str,
        recollections: list[dict[str, Any]],
        audience: Audience,
        actor_id: str,
    ) -> list[str]:
        if len(recollections) < 2:
            raise ValidationError("CONFLICT_REQUIRES_ALTERNATIVES", "conflicting recollection set requires at least two accounts")
        group_id = new_uuid()
        result: list[str] = []
        for item in recollections:
            result.append(
                self.create_record(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type="memory",
                    subject_id=subject_id,
                    related_ids=[],
                    data={
                        "event_key": event_key,
                        "conflict_group_id": group_id,
                        "account": item["account"],
                        "recollector_id": item["recollector_id"],
                        "conflict_status": "alternate_recollection",
                    },
                    source_class=SourceClass.RECALLED,
                    confidence=float(item.get("confidence", 0.5)),
                    evidence_asset_ids=item.get("evidence_asset_ids", []),
                    audience=audience,
                    actor_id=actor_id,
                )
            )
        return result

    def visible_records(self, tenant_id: str, project_id: str, *, audience: Audience, purpose: str, subject_id: str | None = None) -> list[dict[str, Any]]:
        with self.database.session() as session:
            statement = select(MemoryRecordRow).where(MemoryRecordRow.tenant_id == tenant_id, MemoryRecordRow.project_id == project_id)
            if subject_id:
                statement = statement.where(MemoryRecordRow.subject_id == subject_id)
            rows = list(session.scalars(statement))
        visible: list[dict[str, Any]] = []
        allowed_audiences = {
            Audience.PRIVATE: {Audience.PRIVATE.value, Audience.FAMILY.value, Audience.PUBLIC.value},
            Audience.FAMILY: {Audience.FAMILY.value, Audience.PUBLIC.value},
            Audience.PUBLIC: {Audience.PUBLIC.value},
            Audience.PROJECT: {Audience.PROJECT.value, Audience.PUBLIC.value},
            Audience.OWNER: {Audience.OWNER.value, Audience.PROJECT.value, Audience.PUBLIC.value},
        }[audience]
        for row in rows:
            if row.audience not in allowed_audiences or row.data_json.get("derivative_access_disabled"):
                continue
            if row.subject_id:
                try:
                    self._require_consent(tenant_id, project_id, row.subject_id, purpose=purpose, audience=audience, scope=row.record_type)
                except AuthorizationError:
                    continue
            visible.append(
                {
                    "record_id": row.record_id,
                    "record_type": row.record_type,
                    "subject_id": row.subject_id,
                    "data": row.data_json,
                    "source_class": row.source_class,
                    "confidence": row.confidence,
                    "evidence_asset_ids": row.evidence_asset_ids_json,
                    "audience": row.audience,
                    "generated_lineage": row.generated_lineage_json,
                }
            )
        return visible

    def experience_configuration(
        self,
        tenant_id: str,
        project_id: str,
        subject_id: str,
        *,
        requested_features: dict[str, bool],
        audience: Audience,
    ) -> dict[str, Any]:
        config = {**EXPERIENCE_FEATURES_DEFAULT}
        config.update({key: bool(value) for key, value in requested_features.items() if key in config})
        presence = {"voice_simulation", "likeness_simulation", "first_person_dialogue", "autonomous_persona"}
        enabled_presence = sorted(key for key in presence if config.get(key))
        if enabled_presence:
            if self.kill_switches.get("all_generated_presence", True):
                raise AuthorizationError("PRESENCE_KILL_SWITCH", "generated presence is disabled by the global kill switch")
            for feature in enabled_presence:
                switch = "dialogue" if feature in {"first_person_dialogue", "autonomous_persona"} else feature.split("_")[0]
                if self.kill_switches.get(switch, True):
                    raise AuthorizationError("PRESENCE_KILL_SWITCH", f"{feature} is disabled")
                self._require_consent(tenant_id, project_id, subject_id, purpose="immersive_presence", audience=audience, scope=feature)
        config["quiet_mode"] = True
        config["safe_exit"] = True
        config["pause"] = True
        config["reset"] = True
        config["free_locomotion"] = False
        return {
            "subject_id": subject_id,
            "features": config,
            "generated_presence_label": "SIMULATED / GENERATED" if enabled_presence else None,
            "safe_exit_persistent": True,
            "reduced_motion_supported": True,
            "captions_required": True,
        }

    def set_kill_switch(self, key: str, enabled: bool, *, actor_id: str) -> None:
        if key not in self.kill_switches:
            raise ValidationError("KILL_SWITCH_UNKNOWN", "unknown presence kill switch")
        self.kill_switches[key] = enabled

    def edition(self, tenant_id: str, project_id: str, *, audience: Audience, purpose: str) -> dict[str, Any]:
        records = self.visible_records(tenant_id, project_id, audience=audience, purpose=purpose)
        body = {"audience": audience.value, "purpose": purpose, "records": records, "generated_labels_preserved": True}
        return {**body, "edition_hash": canonical_sha256(body)}

    def _require_consent(self, tenant_id: str, project_id: str, subject_id: str, *, purpose: str, audience: Audience, scope: str) -> ConsentGrantRow:
        with self.database.session() as session:
            grants = list(
                session.scalars(
                    select(ConsentGrantRow).where(
                        ConsentGrantRow.tenant_id == tenant_id,
                        ConsentGrantRow.project_id == project_id,
                        ConsentGrantRow.subject_id == subject_id,
                        ConsentGrantRow.state == "active",
                    )
                )
            )
        now = db_now()
        for grant in grants:
            if grant.expires_at and _aware(grant.expires_at) <= now:
                continue
            if purpose in grant.purposes_json and audience.value in grant.audiences_json and (scope in grant.scopes_json or "*" in grant.scopes_json):
                return grant
        raise AuthorizationError(
            "CONSENT_REQUIRED",
            "no active consent grant permits this purpose, audience, and scope",
            {"subject_id": subject_id, "purpose": purpose, "audience": audience.value, "scope": scope},
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
