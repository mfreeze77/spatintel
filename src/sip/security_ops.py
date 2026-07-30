from __future__ import annotations

import base64
import hmac
import re
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, new_uuid, sha256_file
from .database import (
    AssetRefRow,
    AssetRow,
    AuditVerificationRow,
    CacheInvalidationRow,
    CaptureFinalizationAuditRow,
    ConsentGrantRow,
    Database,
    KeyAccessEventRow,
    KeyScopeRow,
    ImmersiveSafetyDecisionRow,
    PrivacyImpactAssessmentRow,
    PrivacyInventoryRow,
    PrivacyRightsRequestRow,
    PrivilegedAccessGrantRow,
    ProjectRow,
    ProviderGovernanceExceptionRow,
    ProviderOutputValidationRow,
    ProviderManifestRow,
    SecurityIncidentRow,
    SupplyChainReleaseRow,
    ThreatManifestRow,
    TransportVerificationRow,
    WorkloadIdentityGrantRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .security import SignedTokenCodec
from .temporal import db_now

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_MFA = {"webauthn", "passkey", "hardware_key", "piv", "smartcard"}
_CRITICAL_THREATS = {
    "capture_device_compromise",
    "upload_tampering",
    "archive_bomb",
    "parser_exploit",
    "gpu_escape",
    "cross_tenant_access",
    "signed_url_leakage",
    "viewer_scraping",
    "model_exfiltration",
    "prompt_injection",
    "insider_abuse",
    "destructive_deletion",
    "geometry_payload_parsing",
    "provider_egress",
    "topology_disclosure",
    "derivative_redaction",
    "authority_spoofing",
    "immersive_safety_failure",
}
_REVIEW_TRIGGERS = {"sensor", "model_provider", "sharing_mode", "plugin", "data_purpose", "scheduled", "incident"}
_PROHIBITED_EXCEPTION_WAIVERS = {"truth", "consent", "legal_hold", "authority", "tenant_isolation", "evidence_integrity"}
_REQUIRED_RELEASE_COMPONENTS = {"mobile", "web", "services", "workers", "infrastructure", "models", "schemas", "database"}
_REQUIRED_RELEASE_EVIDENCE = {"tests", "security", "privacy", "license", "sbom", "benchmarks", "migrations", "backup_restore", "acceptance"}


class SecurityOperationsService:
    """Fail-closed reference controls for the first production-readiness epic.

    The service stores immutable governance decisions and emits ordinary SIP audit records.
    It deliberately does not claim that local reference execution proves cloud IAM, physical
    MFA devices, Apple signing, external legal review, or third-party security testing.
    """

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        token_codec: SignedTokenCodec,
        signing_key: bytes,
        *,
        environment: str,
        local_only: bool = False,
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("security-operations signing key must be at least 32 bytes")
        self.database = database
        self.audit = audit
        self.token_codec = token_codec
        self.signing_key = signing_key
        self.environment = environment
        self.local_only = local_only
        self.events = OutboxEventFactory()

    def _emit(
        self,
        session,
        *,
        event_type: str,
        tenant_id: str,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        actor_id: str | None,
        workload_identity: str | None = None,
    ) -> None:
        session.add(
            self.events.create(
                session,
                event_type=event_type,
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                producer="security-ops",
                actor_id=actor_id,
                workload_identity=workload_identity,
            )
        )

    @staticmethod
    def _require_project_scope(session, tenant_id: str, project_id: str | None) -> None:
        if project_id is None:
            return
        project = session.get(ProjectRow, project_id)
        if not project or project.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)

    # ------------------------------------------------------------------ threats
    def register_threat_manifest(
        self,
        *,
        scope: str,
        threats: list[dict[str, Any]],
        misuse_cases: list[dict[str, Any]],
        public_viewer_analysis: dict[str, Any],
        residual_risks: list[dict[str, Any]],
        owner: str,
        review_trigger: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if not scope.strip() or not owner.strip():
            raise ValidationError("THREAT_MANIFEST_IDENTITY_INVALID", "threat scope and owner are required")
        if review_trigger not in _REVIEW_TRIGGERS:
            raise ValidationError("THREAT_REVIEW_TRIGGER_INVALID", "unsupported threat-model review trigger")
        by_id: dict[str, dict[str, Any]] = {}
        for threat in threats:
            threat_id = str(threat.get("threat_id", "")).strip()
            if not threat_id or threat_id in by_id:
                raise ValidationError("THREAT_ID_INVALID", "threat identifiers must be nonempty and unique")
            controls = threat.get("controls")
            if not isinstance(controls, dict) or any(not controls.get(kind) for kind in ("preventative", "detective", "recovery")):
                raise ValidationError("THREAT_CONTROL_MAP_INCOMPLETE", "each threat requires preventative, detective, and recovery controls", {"threat_id": threat_id})
            if not threat.get("owner") or not threat.get("test_ids"):
                raise ValidationError("THREAT_ACCOUNTABILITY_INCOMPLETE", "each threat requires an owner and retained test references", {"threat_id": threat_id})
            by_id[threat_id] = threat
        missing = sorted(_CRITICAL_THREATS - set(by_id))
        if missing:
            raise ValidationError("THREAT_CATALOG_INCOMPLETE", "critical threat catalog is incomplete", {"missing": missing})
        domains = {str(case.get("domain")) for case in misuse_cases}
        if not {"sensitive_facility", "private_family"}.issubset(domains):
            raise ValidationError("THREAT_MISUSE_CASES_INCOMPLETE", "facility and family misuse cases are required")
        if public_viewer_analysis.get("trusted_secrets") not in {False, 0}:
            raise ValidationError("PUBLIC_VIEWER_TRUST_INVALID", "public viewer must be modeled as hostile client code with no trusted secrets")
        if not public_viewer_analysis.get("scraping_controls") or not public_viewer_analysis.get("cache_controls"):
            raise ValidationError("PUBLIC_VIEWER_ANALYSIS_INCOMPLETE", "public viewer analysis requires scraping and cache controls")
        if not residual_risks or any(not item.get("risk") or not item.get("owner") or not item.get("release_disposition") for item in residual_risks):
            raise ValidationError("RESIDUAL_RISK_INCOMPLETE", "residual risks require owner and release disposition")
        body = {
            "scope": scope,
            "threats": sorted(threats, key=lambda item: str(item["threat_id"])),
            "misuse_cases": misuse_cases,
            "public_viewer_analysis": public_viewer_analysis,
            "residual_risks": residual_risks,
            "owner": owner,
            "review_trigger": review_trigger,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(ThreatManifestRow).where(ThreatManifestRow.manifest_hash == digest))
            if existing:
                return self._threat_result(existing, idempotent_replay=True)
            latest = session.scalar(select(ThreatManifestRow).where(ThreatManifestRow.scope == scope).order_by(ThreatManifestRow.version.desc()).limit(1))
            identifier = new_uuid()
            row = ThreatManifestRow(
                threat_manifest_id=identifier,
                scope=scope,
                version=(latest.version + 1) if latest else 1,
                state="active",
                manifest_json=body,
                manifest_hash=digest,
                review_trigger=review_trigger,
                owner=owner,
                created_by=actor_id,
                supersedes_manifest_id=latest.threat_manifest_id if latest else None,
            )
            if latest:
                latest.state = "superseded"
            session.add(row)
            self.audit.append(
                tenant_id="platform",
                project_id=None,
                actor_id=actor_id,
                action="threat_model:register",
                resource_type="threat_manifest",
                resource_id=identifier,
                outcome="allowed",
                details={"scope": scope, "version": row.version, "manifest_hash": digest, "review_trigger": review_trigger},
                session=session,
            )
            self._emit(session, event_type="threat_manifest.registered", tenant_id="platform", project_id=None, aggregate_type="threat_manifest", aggregate_id=identifier, payload={"scope": scope, "version": row.version, "manifest_hash": digest, "review_trigger": review_trigger}, actor_id=actor_id)
            return self._threat_result(row, idempotent_replay=False)

    @staticmethod
    def _threat_result(row: ThreatManifestRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "threat_manifest_id": row.threat_manifest_id,
            "scope": row.scope,
            "version": row.version,
            "state": row.state,
            "manifest_hash": row.manifest_hash,
            "idempotent_replay": idempotent_replay,
        }

    # ----------------------------------------------------------- privileged/JIT access
    def grant_privileged_access(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        subject_id: str,
        actions: list[str],
        resource_scope: dict[str, Any],
        purpose: str,
        mfa_method: str,
        mfa_verified_at: datetime,
        duration_seconds: int,
        requested_by: str,
        approved_by: str,
    ) -> dict[str, Any]:
        now = db_now()
        verified_at = _aware(mfa_verified_at)
        if mfa_method not in _ALLOWED_MFA:
            raise AuthorizationError("PHISHING_RESISTANT_MFA_REQUIRED", "privileged access requires a phishing-resistant MFA method")
        if verified_at > now + timedelta(seconds=30) or now - verified_at > timedelta(minutes=5):
            raise AuthorizationError("MFA_FRESHNESS_REQUIRED", "privileged access requires a fresh MFA assertion")
        if requested_by == approved_by or subject_id == approved_by:
            raise AuthorizationError("JIT_INDEPENDENT_APPROVER_REQUIRED", "privileged access requires independent approval")
        if duration_seconds < 60 or duration_seconds > 3600:
            raise ValidationError("JIT_DURATION_INVALID", "privileged elevation must be between 60 and 3600 seconds")
        normalized_actions = sorted({item.strip() for item in actions if item.strip()})
        if not normalized_actions or any(item == "*" for item in normalized_actions):
            raise ValidationError("JIT_ACTION_SCOPE_INVALID", "privileged grants require explicit bounded actions")
        if not isinstance(resource_scope, dict) or not resource_scope or any(str(value).strip() == "*" for value in resource_scope.values()):
            raise ValidationError("JIT_RESOURCE_SCOPE_INVALID", "privileged grants require an explicit bounded resource scope")
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "subject_id": subject_id,
            "actions": normalized_actions,
            "resource_scope": resource_scope,
            "purpose": purpose,
            "mfa_method": mfa_method,
            "mfa_verified_at": verified_at.isoformat(),
            "duration_seconds": duration_seconds,
            "requested_by": requested_by,
            "approved_by": approved_by,
        }
        request_hash = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(PrivilegedAccessGrantRow).where(PrivilegedAccessGrantRow.tenant_id == tenant_id, PrivilegedAccessGrantRow.request_hash == request_hash))
            if existing:
                return self._jit_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = PrivilegedAccessGrantRow(
                grant_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                subject_id=subject_id,
                actions_json=normalized_actions,
                resource_scope_json=resource_scope,
                purpose=purpose,
                mfa_method=mfa_method,
                mfa_verified_at=verified_at,
                requested_by=requested_by,
                approved_by=approved_by,
                request_hash=request_hash,
                state="active",
                expires_at=now + timedelta(seconds=duration_seconds),
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=approved_by,
                action="privileged_access:grant",
                resource_type="privileged_access_grant",
                resource_id=identifier,
                outcome="allowed",
                details={"subject_id": subject_id, "actions": normalized_actions, "purpose": purpose, "expires_at": row.expires_at.isoformat(), "mfa_method": mfa_method},
                session=session,
            )
            self._emit(session, event_type="privileged_access.granted", tenant_id=tenant_id, project_id=project_id, aggregate_type="privileged_access_grant", aggregate_id=identifier, payload={"subject_id": subject_id, "actions": normalized_actions, "purpose": purpose, "expires_at": row.expires_at.isoformat(), "mfa_method": mfa_method}, actor_id=approved_by)
            return self._jit_result(row, idempotent_replay=False)

    def require_privileged_access(
        self,
        *,
        grant_id: str,
        tenant_id: str,
        project_id: str | None,
        subject_id: str,
        action: str,
        purpose: str,
        resource_scope: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(PrivilegedAccessGrantRow, grant_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id or row.subject_id != subject_id:
                raise AuthorizationError("JIT_GRANT_NOT_FOUND", "privileged access grant is unavailable")
            if row.state != "active" or _aware(row.expires_at) <= db_now():
                raise AuthorizationError("JIT_GRANT_INACTIVE", "privileged access grant is inactive or expired")
            if action not in row.actions_json or purpose != row.purpose:
                raise AuthorizationError("JIT_GRANT_SCOPE_DENIED", "privileged access grant does not cover this action and purpose")
            if not _scope_contains(row.resource_scope_json, resource_scope):
                raise AuthorizationError("JIT_GRANT_RESOURCE_DENIED", "privileged access grant does not cover the requested resource scope")
            return self._jit_result(row, idempotent_replay=True)

    def revoke_privileged_access(self, *, grant_id: str, tenant_id: str, actor_id: str) -> None:
        with self.database.session() as session:
            row = session.get(PrivilegedAccessGrantRow, grant_id)
            if not row or row.tenant_id != tenant_id:
                raise NotFoundError("privileged_access_grant", grant_id)
            if row.state == "revoked":
                return
            row.state = "revoked"
            row.revoked_at = db_now()
            row.revoked_by = actor_id
            self.audit.append(
                tenant_id=tenant_id,
                project_id=row.project_id,
                actor_id=actor_id,
                action="privileged_access:revoke",
                resource_type="privileged_access_grant",
                resource_id=grant_id,
                outcome="allowed",
                details={"subject_id": row.subject_id},
                session=session,
            )
            self._emit(session, event_type="privileged_access.revoked", tenant_id=tenant_id, project_id=row.project_id, aggregate_type="privileged_access_grant", aggregate_id=grant_id, payload={"subject_id": row.subject_id, "revoked_at": row.revoked_at.isoformat()}, actor_id=actor_id)

    @staticmethod
    def _jit_result(row: PrivilegedAccessGrantRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"grant_id": row.grant_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "subject_id": row.subject_id, "actions": row.actions_json, "resource_scope": row.resource_scope_json, "purpose": row.purpose, "state": row.state, "expires_at": _aware(row.expires_at).isoformat(), "idempotent_replay": idempotent_replay}

    # --------------------------------------------------------------- workload identity
    def issue_workload_identity(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        workload_id: str,
        audience: str,
        scopes: list[str],
        purpose: str,
        ttl_seconds: int,
        actor_id: str,
    ) -> dict[str, Any]:
        if ttl_seconds < 30 or ttl_seconds > 900:
            raise ValidationError("WORKLOAD_TOKEN_TTL_INVALID", "workload credentials must live between 30 and 900 seconds")
        normalized_scopes = sorted({item.strip() for item in scopes if item.strip()})
        if not workload_id.strip() or not audience.strip() or not purpose.strip() or not normalized_scopes or "*" in normalized_scopes:
            raise ValidationError("WORKLOAD_IDENTITY_SCOPE_INVALID", "workload identity requires explicit workload, audience, purpose, and scopes")
        body = {"tenant_id": tenant_id, "project_id": project_id, "workload_id": workload_id, "audience": audience, "scopes": normalized_scopes, "purpose": purpose, "ttl_seconds": ttl_seconds}
        request_hash = canonical_sha256(body)
        now = db_now()
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(WorkloadIdentityGrantRow).where(WorkloadIdentityGrantRow.tenant_id == tenant_id, WorkloadIdentityGrantRow.request_hash == request_hash, WorkloadIdentityGrantRow.state == "active", WorkloadIdentityGrantRow.expires_at > now))
            if existing:
                token = self._encode_workload(existing)
                return self._workload_result(existing, token=token, idempotent_replay=True)
            identifier = new_uuid()
            jti = new_uuid()
            row = WorkloadIdentityGrantRow(
                grant_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                workload_id=workload_id,
                audience=audience,
                scopes_json=normalized_scopes,
                purpose=purpose,
                token_jti=jti,
                request_hash=request_hash,
                state="active",
                issued_by=actor_id,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            session.add(row)
            session.flush()
            token = self._encode_workload(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="workload_identity:issue",
                resource_type="workload_identity_grant",
                resource_id=identifier,
                outcome="allowed",
                details={"workload_id": workload_id, "audience": audience, "scopes": normalized_scopes, "expires_at": row.expires_at.isoformat()},
                session=session,
            )
            self._emit(session, event_type="workload_identity.issued", tenant_id=tenant_id, project_id=project_id, aggregate_type="workload_identity_grant", aggregate_id=identifier, payload={"workload_id": workload_id, "audience": audience, "scopes": normalized_scopes, "purpose": purpose, "expires_at": row.expires_at.isoformat()}, actor_id=actor_id, workload_identity=workload_id)
            return self._workload_result(row, token=token, idempotent_replay=False)

    def validate_workload_identity(
        self,
        token: str,
        *,
        audience: str,
        required_scope: str,
        purpose: str,
        tenant_id: str,
        project_id: str | None,
        workload_id: str,
    ) -> dict[str, Any]:
        claims = self.token_codec.decode(token)
        if claims.get("token_type") != "workload_identity" or claims.get("aud") != audience:
            raise AuthorizationError("WORKLOAD_TOKEN_AUDIENCE_DENIED", "workload token has the wrong audience")
        if claims.get("tenant_id") != tenant_id or claims.get("project_id") != project_id or claims.get("purpose") != purpose:
            raise AuthorizationError("WORKLOAD_TOKEN_CONTEXT_DENIED", "workload token is outside its governed context")
        if claims.get("workload_id") != workload_id:
            raise AuthorizationError("WORKLOAD_TOKEN_IDENTITY_DENIED", "workload token belongs to a different workload identity")
        if required_scope not in set(claims.get("scopes") or []):
            raise AuthorizationError("WORKLOAD_TOKEN_SCOPE_DENIED", "workload token lacks the required scope")
        with self.database.session() as session:
            row = session.scalar(select(WorkloadIdentityGrantRow).where(WorkloadIdentityGrantRow.token_jti == claims.get("jti")))
            if (
                not row
                or row.state != "active"
                or _aware(row.expires_at) <= db_now()
                or row.workload_id != workload_id
                or row.tenant_id != tenant_id
                or row.project_id != project_id
            ):
                raise AuthorizationError("WORKLOAD_TOKEN_REVOKED", "workload token is revoked, expired, unknown, or outside its stored scope")
            return self._workload_result(row, token=None, idempotent_replay=True)

    def revoke_workload_identity(self, *, grant_id: str, tenant_id: str, actor_id: str) -> None:
        with self.database.session() as session:
            row = session.get(WorkloadIdentityGrantRow, grant_id)
            if not row or row.tenant_id != tenant_id:
                raise NotFoundError("workload_identity_grant", grant_id)
            if row.state == "revoked":
                return
            row.state = "revoked"
            row.revoked_at = db_now()
            self.audit.append(tenant_id=tenant_id, project_id=row.project_id, actor_id=actor_id, action="workload_identity:revoke", resource_type="workload_identity_grant", resource_id=grant_id, outcome="allowed", details={"workload_id": row.workload_id}, session=session)
            self._emit(session, event_type="workload_identity.revoked", tenant_id=tenant_id, project_id=row.project_id, aggregate_type="workload_identity_grant", aggregate_id=grant_id, payload={"workload_id": row.workload_id, "revoked_at": row.revoked_at.isoformat()}, actor_id=actor_id, workload_identity=row.workload_id)

    def _encode_workload(self, row: WorkloadIdentityGrantRow) -> str:
        ttl = max(1, int((_aware(row.expires_at) - db_now()).total_seconds()))
        return self.token_codec.encode({"token_type": "workload_identity", "jti": row.token_jti, "tenant_id": row.tenant_id, "project_id": row.project_id, "workload_id": row.workload_id, "aud": row.audience, "scopes": row.scopes_json, "purpose": row.purpose}, ttl_seconds=ttl)

    @staticmethod
    def _workload_result(row: WorkloadIdentityGrantRow, *, token: str | None, idempotent_replay: bool) -> dict[str, Any]:
        result = {"grant_id": row.grant_id, "workload_id": row.workload_id, "audience": row.audience, "scopes": row.scopes_json, "purpose": row.purpose, "state": row.state, "expires_at": _aware(row.expires_at).isoformat(), "idempotent_replay": idempotent_replay}
        if token is not None:
            result["token"] = token
        return result

    # ---------------------------------------------------------------- key governance
    def register_key_scope(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        person_id: str | None,
        key_id: str,
        backend: str,
        recovery_policy: dict[str, Any],
        actor_id: str,
        rotated_from_key_id: str | None = None,
    ) -> dict[str, Any]:
        if backend not in {"local_hsm", "managed_kms", "offline_recovery"}:
            raise ValidationError("KEY_BACKEND_INVALID", "unsupported key backend")
        guardians = sorted({str(item) for item in recovery_policy.get("guardians", []) if str(item)})
        quorum = int(recovery_policy.get("quorum", 0))
        if len(guardians) < 2 or quorum < 2 or quorum > len(guardians):
            raise ValidationError("KEY_RECOVERY_QUORUM_INVALID", "key recovery requires at least two guardians and a valid quorum")
        if recovery_policy.get("single_person_recovery") is not False:
            raise ValidationError("KEY_SINGLE_PERSON_RECOVERY_PROHIBITED", "single-person permanent recovery is prohibited")
        body = {"tenant_id": tenant_id, "project_id": project_id, "person_id": person_id, "key_id": key_id, "backend": backend, "recovery_policy": {**recovery_policy, "guardians": guardians, "quorum": quorum}, "rotated_from_key_id": rotated_from_key_id}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(KeyScopeRow).where(KeyScopeRow.scope_hash == digest))
            if existing:
                return self._key_scope_result(existing, idempotent_replay=True)
            if session.scalar(select(KeyScopeRow).where(KeyScopeRow.key_id == key_id)):
                raise ConflictError("KEY_ID_CONFLICT", "key identifier is already registered")
            if rotated_from_key_id:
                prior = session.scalar(
                    select(KeyScopeRow).where(
                        KeyScopeRow.key_id == rotated_from_key_id,
                        KeyScopeRow.tenant_id == tenant_id,
                        KeyScopeRow.project_id == project_id,
                        KeyScopeRow.person_id == person_id,
                    )
                )
                if not prior or prior.state != "active":
                    raise ConflictError("KEY_ROTATION_SOURCE_INVALID", "rotation source key is not active in the exact governed scope")
                prior.state = "rotated"
            identifier = new_uuid()
            row = KeyScopeRow(key_scope_id=identifier, tenant_id=tenant_id, project_id=project_id, person_id=person_id, key_id=key_id, backend=backend, state="active", recovery_policy_json=body["recovery_policy"], scope_hash=digest, created_by=actor_id, rotated_from_key_id=rotated_from_key_id)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="key_scope:register", resource_type="key_scope", resource_id=identifier, outcome="allowed", details={"key_id": key_id, "backend": backend, "rotated_from_key_id": rotated_from_key_id, "quorum": quorum}, session=session)
            self._emit(session, event_type="key_scope.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="key_scope", aggregate_id=identifier, payload={"key_id": key_id, "backend": backend, "state": "active", "quorum": quorum, "rotated_from_key_id": rotated_from_key_id}, actor_id=actor_id)
            return self._key_scope_result(row, idempotent_replay=False)

    def record_key_access(self, *, key_scope_id: str, tenant_id: str, project_id: str | None, actor_or_workload: str, purpose: str, action: str, resource_scope: dict[str, Any], outcome: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        if outcome not in {"allowed", "denied", "failed"}:
            raise ValidationError("KEY_ACCESS_OUTCOME_INVALID", "key access outcome is invalid")
        with self.database.session() as session:
            scope = session.get(KeyScopeRow, key_scope_id)
            if not scope or scope.tenant_id != tenant_id or scope.project_id != project_id:
                raise NotFoundError("key_scope", key_scope_id)
            body = {"key_scope_id": key_scope_id, "tenant_id": tenant_id, "project_id": project_id, "actor_or_workload": actor_or_workload, "purpose": purpose, "action": action, "resource_scope": resource_scope, "outcome": outcome, "details": details or {}, "nonce": new_uuid()}
            event_hash = canonical_sha256(body)
            identifier = new_uuid()
            session.add(KeyAccessEventRow(key_access_event_id=identifier, tenant_id=tenant_id, project_id=project_id, key_scope_id=key_scope_id, actor_or_workload=actor_or_workload, purpose=purpose, action=action, resource_scope_json=resource_scope, outcome=outcome, details_json=details or {}, event_hash=event_hash))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_or_workload, action=f"key:{action}", resource_type="key_scope", resource_id=key_scope_id, outcome=outcome, details={"purpose": purpose, "resource_scope": resource_scope, "key_access_event_id": identifier}, session=session)
            self._emit(session, event_type="key_scope.accessed", tenant_id=tenant_id, project_id=project_id, aggregate_type="key_access_event", aggregate_id=identifier, payload={"key_scope_id": key_scope_id, "purpose": purpose, "action": action, "outcome": outcome, "event_hash": event_hash}, actor_id=actor_or_workload)
            return {"key_access_event_id": identifier, "event_hash": event_hash, "outcome": outcome}

    def emergency_revoke_key(self, *, key_scope_id: str, tenant_id: str, project_id: str | None, actor_id: str, reason: str, residual_timeline: list[dict[str, Any]]) -> dict[str, Any]:
        if not reason.strip() or not residual_timeline:
            raise ValidationError("KEY_REVOCATION_EVIDENCE_INCOMPLETE", "emergency revocation requires reason and residual replica/backup timeline")
        with self.database.session() as session:
            row = session.get(KeyScopeRow, key_scope_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("key_scope", key_scope_id)
            row.state = "revoked"
            row.revoked_at = db_now()
            evidence = {"key_scope_id": key_scope_id, "key_id": row.key_id, "reason": reason, "revoked_at": row.revoked_at.isoformat(), "residual_timeline": residual_timeline, "actor_id": actor_id}
            evidence_hash = canonical_sha256(evidence)
            self.audit.append(tenant_id=tenant_id, project_id=row.project_id, actor_id=actor_id, action="key:emergency_revoke", resource_type="key_scope", resource_id=key_scope_id, outcome="allowed", details={"reason": reason, "residual_timeline": residual_timeline, "erasure_evidence_hash": evidence_hash}, session=session)
            self._emit(session, event_type="key_scope.revoked", tenant_id=tenant_id, project_id=row.project_id, aggregate_type="key_scope", aggregate_id=key_scope_id, payload={"key_id": row.key_id, "state": "revoked", "reason": reason, "revoked_at": row.revoked_at.isoformat(), "erasure_evidence_hash": evidence_hash}, actor_id=actor_id)
            return {**evidence, "erasure_evidence_hash": evidence_hash}

    @staticmethod
    def _key_scope_result(row: KeyScopeRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"key_scope_id": row.key_scope_id, "key_id": row.key_id, "backend": row.backend, "state": row.state, "recovery_policy": row.recovery_policy_json, "scope_hash": row.scope_hash, "idempotent_replay": idempotent_replay}

    # --------------------------------------------------------------------- privacy
    def register_privacy_inventory(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        data_category: str,
        purpose: str,
        legal_basis: str,
        consent_basis: str | None,
        processors: list[dict[str, Any]],
        residency: dict[str, Any],
        retention: dict[str, Any],
        security_controls: list[str],
        rights_workflow: dict[str, Any],
        classification: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if not all([data_category.strip(), purpose.strip(), legal_basis.strip(), classification.strip()]):
            raise ValidationError("PRIVACY_INVENTORY_INCOMPLETE", "privacy inventory identity and basis are required")
        if not residency.get("regions") or not retention.get("policy") or not security_controls or not rights_workflow.get("contact"):
            raise ValidationError("PRIVACY_INVENTORY_CONTROLS_INCOMPLETE", "privacy inventory requires residency, retention, security, and rights workflow")
        for processor in processors:
            if not processor.get("name") or not processor.get("approved_purposes") or processor.get("training_allowed") is not False:
                raise ValidationError("PRIVACY_PROCESSOR_POLICY_INVALID", "processors require purpose limits and training must be disabled unless separately approved")
        body = {"tenant_id": tenant_id, "project_id": project_id, "data_category": data_category, "purpose": purpose, "legal_basis": legal_basis, "consent_basis": consent_basis, "processors": processors, "residency": residency, "retention": retention, "security_controls": sorted(set(security_controls)), "rights_workflow": rights_workflow, "classification": classification}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(PrivacyInventoryRow).where(PrivacyInventoryRow.content_hash == digest))
            if existing:
                return self._privacy_inventory_result(existing, idempotent_replay=True)
            latest = session.scalar(select(PrivacyInventoryRow).where(PrivacyInventoryRow.tenant_id == tenant_id, PrivacyInventoryRow.project_id == project_id, PrivacyInventoryRow.data_category == data_category, PrivacyInventoryRow.purpose == purpose).order_by(PrivacyInventoryRow.version.desc()).limit(1))
            identifier = new_uuid()
            row = PrivacyInventoryRow(privacy_inventory_id=identifier, tenant_id=tenant_id, project_id=project_id, data_category=data_category, purpose=purpose, legal_basis=legal_basis, consent_basis=consent_basis, processors_json=processors, residency_json=residency, retention_json=retention, security_controls_json=body["security_controls"], rights_workflow_json=rights_workflow, classification=classification, version=(latest.version + 1) if latest else 1, state="active", content_hash=digest, created_by=actor_id, supersedes_inventory_id=latest.privacy_inventory_id if latest else None)
            if latest:
                latest.state = "superseded"
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="privacy_inventory:register", resource_type="privacy_inventory", resource_id=identifier, outcome="allowed", details={"data_category": data_category, "purpose": purpose, "version": row.version, "content_hash": digest}, session=session)
            self._emit(session, event_type="privacy_inventory.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="privacy_inventory", aggregate_id=identifier, payload={"data_category": data_category, "purpose": purpose, "version": row.version, "classification": classification, "content_hash": digest}, actor_id=actor_id)
            return self._privacy_inventory_result(row, idempotent_replay=False)

    def assess_privacy_change(self, *, tenant_id: str, project_id: str | None, change_type: str, change_reference: str, purpose: str, data_categories: list[str], processors: list[str], risks: list[dict[str, Any]], controls: list[dict[str, Any]], residual_risk: str, decision: str, reviewer_id: str, expires_at: datetime | None = None) -> dict[str, Any]:
        if change_type not in {"data_purpose", "provider", "sensor", "sharing_mode", "plugin", "model"}:
            raise ValidationError("PRIVACY_CHANGE_TYPE_INVALID", "privacy impact review change type is unsupported")
        if decision not in {"approved", "denied", "needs_changes"} or residual_risk not in {"low", "medium", "high", "critical"}:
            raise ValidationError("PRIVACY_ASSESSMENT_DECISION_INVALID", "privacy impact review decision or residual risk is invalid")
        if not data_categories or not risks or not controls or any(not item.get("risk") for item in risks) or any(not item.get("control") for item in controls):
            raise ValidationError("PRIVACY_ASSESSMENT_INCOMPLETE", "privacy impact review requires data categories, risks, and controls")
        if decision == "approved" and residual_risk in {"high", "critical"}:
            raise AuthorizationError("PRIVACY_RISK_TOO_HIGH", "high or critical residual privacy risk cannot be approved")
        body = {"tenant_id": tenant_id, "project_id": project_id, "change_type": change_type, "change_reference": change_reference, "purpose": purpose, "data_categories": sorted(set(data_categories)), "processors": sorted(set(processors)), "risks": risks, "controls": controls, "residual_risk": residual_risk, "decision": decision, "reviewer_id": reviewer_id, "expires_at": _iso(expires_at)}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(PrivacyImpactAssessmentRow).where(PrivacyImpactAssessmentRow.request_hash == digest))
            if existing:
                return {"assessment_id": existing.assessment_id, "decision": existing.decision, "residual_risk": existing.residual_risk, "request_hash": existing.request_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = PrivacyImpactAssessmentRow(assessment_id=identifier, tenant_id=tenant_id, project_id=project_id, change_type=change_type, change_reference=change_reference, purpose=purpose, data_categories_json=body["data_categories"], processors_json=body["processors"], risks_json=risks, controls_json=controls, residual_risk=residual_risk, decision=decision, reviewer_id=reviewer_id, expires_at=_aware(expires_at) if expires_at else None, request_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=reviewer_id, action="privacy_impact:decide", resource_type="privacy_impact_assessment", resource_id=identifier, outcome="allowed", details={"change_type": change_type, "change_reference": change_reference, "decision": decision, "residual_risk": residual_risk}, session=session)
            self._emit(session, event_type="privacy_impact.decided", tenant_id=tenant_id, project_id=project_id, aggregate_type="privacy_impact_assessment", aggregate_id=identifier, payload={"change_type": change_type, "change_reference": change_reference, "purpose": purpose, "decision": decision, "residual_risk": residual_risk, "request_hash": digest}, actor_id=reviewer_id)
            return {"assessment_id": identifier, "decision": decision, "residual_risk": residual_risk, "request_hash": digest, "idempotent_replay": False}

    def create_subject_access_export(self, *, tenant_id: str, project_id: str | None, subject_id: str, requested_by: str, verified_by: str, scope: dict[str, Any], due_days: int = 30) -> dict[str, Any]:
        if requested_by == verified_by:
            raise AuthorizationError("SUBJECT_IDENTITY_VERIFICATION_INDEPENDENT", "subject-rights request requires independent identity verification")
        if due_days < 1 or due_days > 90:
            raise ValidationError("RIGHTS_REQUEST_DUE_INVALID", "rights request due period is outside the supported range")
        body = {"tenant_id": tenant_id, "project_id": project_id, "subject_id": subject_id, "request_type": "access", "scope": scope, "requested_by": requested_by, "verified_by": verified_by}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(PrivacyRightsRequestRow).where(PrivacyRightsRequestRow.request_hash == digest))
            if existing:
                return self._rights_result(existing, idempotent_replay=True)
            assets = list(session.scalars(select(AssetRefRow).where(AssetRefRow.tenant_id == tenant_id, AssetRefRow.project_id == project_id, AssetRefRow.tombstoned_at.is_(None)))) if project_id else []
            consents = list(session.scalars(select(ConsentGrantRow).where(ConsentGrantRow.tenant_id == tenant_id, ConsentGrantRow.project_id == project_id, ConsentGrantRow.subject_id == subject_id))) if project_id else []
            response = {
                "subject_id": subject_id,
                "source_records": [{"asset_id": row.asset_id, "source_class": row.source_class, "authority_class": row.authority_class, "classification": row.classification, "retention_class": row.retention_class, "created_at": _aware(row.created_at).isoformat()} for row in assets if _subject_related(row.provenance_json, subject_id)],
                "derivatives": [],
                "sharing": [],
                "consent": [{"consent_id": row.consent_id, "purposes": row.purposes_json, "audiences": row.audiences_json, "state": row.state, "expires_at": _iso(row.expires_at)} for row in consents],
                "automated_processing": [],
                "explanation": "This export distinguishes source evidence, derivatives, consent, sharing, and automated processing. Empty sections mean no in-scope record was found, not that no data exists outside the governed scope.",
            }
            identifier = new_uuid()
            row = PrivacyRightsRequestRow(rights_request_id=identifier, tenant_id=tenant_id, project_id=project_id, subject_id=subject_id, request_type="access", scope_json=scope, state="completed", requested_by=requested_by, verified_by=verified_by, due_at=db_now() + timedelta(days=due_days), response_manifest_json=response, verification_json={"identity_verified_by": verified_by, "scope_hash": canonical_sha256(scope)}, completed_at=db_now(), request_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=verified_by, action="privacy_rights:complete", resource_type="privacy_rights_request", resource_id=identifier, outcome="allowed", details={"subject_id": subject_id, "request_type": "access", "source_records": len(response["source_records"])}, session=session)
            self._emit(session, event_type="privacy_rights.completed", tenant_id=tenant_id, project_id=project_id, aggregate_type="privacy_rights_request", aggregate_id=identifier, payload={"subject_id": subject_id, "request_type": "access", "state": "completed", "source_record_count": len(response["source_records"]), "scope_hash": row.verification_json["scope_hash"]}, actor_id=verified_by)
            return self._rights_result(row, idempotent_replay=False)

    def create_rights_workflow(self, *, tenant_id: str, project_id: str | None, subject_id: str, request_type: str, scope: dict[str, Any], requested_by: str, verified_by: str, due_days: int = 30) -> dict[str, Any]:
        if request_type not in {"correction", "restriction", "deletion"}:
            raise ValidationError("RIGHTS_REQUEST_TYPE_INVALID", "unsupported subject-rights request type")
        if requested_by == verified_by:
            raise AuthorizationError("SUBJECT_IDENTITY_VERIFICATION_INDEPENDENT", "rights request requires independent identity verification")
        body = {"tenant_id": tenant_id, "project_id": project_id, "subject_id": subject_id, "request_type": request_type, "scope": scope, "requested_by": requested_by, "verified_by": verified_by}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(PrivacyRightsRequestRow).where(PrivacyRightsRequestRow.request_hash == digest))
            if existing:
                return self._rights_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = PrivacyRightsRequestRow(rights_request_id=identifier, tenant_id=tenant_id, project_id=project_id, subject_id=subject_id, request_type=request_type, scope_json=scope, state="in_progress", requested_by=requested_by, verified_by=verified_by, due_at=db_now() + timedelta(days=due_days), response_manifest_json={"canonical": "pending", "derivatives": "pending", "indexes": "pending", "caches": "pending", "exports": "pending", "backups": "expiry_tracked"}, verification_json={"identity_verified_by": verified_by, "scope_hash": canonical_sha256(scope)}, request_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=verified_by, action="privacy_rights:create", resource_type="privacy_rights_request", resource_id=identifier, outcome="allowed", details={"subject_id": subject_id, "request_type": request_type}, session=session)
            self._emit(session, event_type="privacy_rights.created", tenant_id=tenant_id, project_id=project_id, aggregate_type="privacy_rights_request", aggregate_id=identifier, payload={"subject_id": subject_id, "request_type": request_type, "state": "in_progress", "due_at": row.due_at.isoformat(), "scope_hash": row.verification_json["scope_hash"]}, actor_id=verified_by)
            return self._rights_result(row, idempotent_replay=False)

    def complete_rights_workflow(
        self,
        *,
        rights_request_id: str,
        tenant_id: str,
        project_id: str | None,
        outcomes: dict[str, Any],
        evidence: list[dict[str, Any]],
        completed_by: str,
    ) -> dict[str, Any]:
        required_stores = {"canonical", "derivatives", "indexes", "caches", "exports", "backups"}
        missing = sorted(required_stores - set(outcomes))
        unexpected = sorted(set(outcomes) - required_stores)
        if missing or unexpected:
            raise ValidationError("RIGHTS_COMPLETION_INCOMPLETE", "rights completion must account for exactly every governed store", {"missing": missing, "unexpected": unexpected})
        allowed_states = {"completed", "restricted", "deleted", "corrected", "not_found", "retained_legal_hold", "expiry_tracked"}
        invalid = sorted(name for name, value in outcomes.items() if not isinstance(value, dict) or value.get("state") not in allowed_states or not value.get("evidence_hash"))
        if invalid:
            raise ValidationError("RIGHTS_COMPLETION_EVIDENCE_INVALID", "each store outcome requires a governed state and evidence hash", {"invalid": invalid})
        for name, value in outcomes.items():
            if not _SHA256.fullmatch(str(value.get("evidence_hash", ""))):
                raise ValidationError("RIGHTS_COMPLETION_HASH_INVALID", "rights completion evidence hashes must be SHA-256", {"store": name})
            if value.get("state") == "retained_legal_hold" and (
                not str(value.get("legal_hold_id", "")).strip()
                or value.get("conflict_type") != "legal_hold"
            ):
                raise ValidationError(
                    "RIGHTS_LEGAL_HOLD_EVIDENCE_REQUIRED",
                    "legal-hold retention must identify the governing hold and conflict type",
                    {"store": name},
                )
        if not evidence or any(not item.get("reference") or not _SHA256.fullmatch(str(item.get("sha256", ""))) for item in evidence):
            raise ValidationError("RIGHTS_COMPLETION_MANIFEST_INVALID", "rights completion requires retained evidence references and hashes")
        with self.database.session() as session:
            row = session.get(PrivacyRightsRequestRow, rights_request_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("privacy_rights_request", rights_request_id)
            completion_hash = canonical_sha256({"rights_request_id": rights_request_id, "request_hash": row.request_hash, "outcomes": outcomes, "evidence": evidence})
            if row.state == "completed":
                if row.verification_json.get("completion_hash") != completion_hash:
                    raise ConflictError("RIGHTS_COMPLETION_CONFLICT", "completed rights request cannot be replayed with different evidence")
                return self._rights_result(row, idempotent_replay=True)
            row.state = "completed"
            row.response_manifest_json = outcomes
            row.verification_json = {**row.verification_json, "completed_by": completed_by, "completion_hash": completion_hash, "evidence": evidence}
            row.completed_at = db_now()
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=completed_by, action="privacy_rights:complete", resource_type="privacy_rights_request", resource_id=rights_request_id, outcome="allowed", details={"subject_id": row.subject_id, "request_type": row.request_type, "completion_hash": completion_hash, "stores": sorted(outcomes)}, session=session)
            self._emit(session, event_type="privacy_rights.completed", tenant_id=tenant_id, project_id=project_id, aggregate_type="privacy_rights_request", aggregate_id=rights_request_id, payload={"subject_id": row.subject_id, "request_type": row.request_type, "state": "completed", "completion_hash": completion_hash, "stores": sorted(outcomes)}, actor_id=completed_by)
            return self._rights_result(row, idempotent_replay=False)

    def record_incident(self, *, tenant_id: str, project_id: str | None, incident_type: str, severity: str, affected_subjects: list[str], affected_resources: list[dict[str, Any]], containment: list[dict[str, Any]], notification_decision: dict[str, Any], evidence: list[dict[str, Any]], actor_id: str) -> dict[str, Any]:
        if severity not in {"low", "medium", "high", "critical"} or not affected_resources or not containment or "notify" not in notification_decision or not notification_decision.get("rationale"):
            raise ValidationError("INCIDENT_RECORD_INCOMPLETE", "incident requires severity, affected resources, containment, and notification decision")
        # Never persist additional raw subject details in an incident summary.
        subjects = sorted(set(affected_subjects))
        if any(isinstance(item, dict) and any(key in item for key in ("raw_data", "transcript", "image", "precise_location")) for item in evidence):
            raise ValidationError("INCIDENT_EVIDENCE_TOO_SENSITIVE", "incident summary must reference evidence rather than embed sensitive payloads")
        body = {"tenant_id": tenant_id, "project_id": project_id, "incident_type": incident_type, "severity": severity, "affected_subjects": subjects, "affected_resources": affected_resources, "containment": containment, "notification_decision": notification_decision, "evidence": evidence}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(SecurityIncidentRow).where(SecurityIncidentRow.incident_hash == digest))
            if existing:
                return {"incident_id": existing.incident_id, "state": existing.state, "incident_hash": existing.incident_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = SecurityIncidentRow(incident_id=identifier, tenant_id=tenant_id, project_id=project_id, incident_type=incident_type, severity=severity, affected_subjects_json=subjects, affected_resources_json=affected_resources, containment_json=containment, notification_decision_json=notification_decision, evidence_json=evidence, state="open", created_by=actor_id, incident_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="incident:create", resource_type="security_incident", resource_id=identifier, outcome="allowed", details={"incident_type": incident_type, "severity": severity, "affected_subject_count": len(subjects), "affected_resource_count": len(affected_resources), "notification_decision": notification_decision.get("notify")}, session=session)
            self._emit(session, event_type="security_incident.created", tenant_id=tenant_id, project_id=project_id, aggregate_type="security_incident", aggregate_id=identifier, payload={"incident_type": incident_type, "severity": severity, "affected_subject_count": len(subjects), "affected_resource_count": len(affected_resources), "notification_required": bool(notification_decision.get("notify")), "incident_hash": digest}, actor_id=actor_id)
            return {"incident_id": identifier, "state": "open", "incident_hash": digest, "idempotent_replay": False}

    def record_provider_incident_withdrawal(
        self,
        *,
        tenant_id: str,
        project_id: str,
        provider_id: str,
        source_asset_ids: list[str],
        derivative_asset_ids: list[str],
        publication_ids: list[str],
        cache_resource_ids: list[str],
        export_ids: list[str],
        evidence: list[dict[str, Any]],
        notification_decision: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        categories = {
            "source": sorted(set(source_asset_ids)),
            "derivative": sorted(set(derivative_asset_ids)),
            "publication": sorted(set(publication_ids)),
            "cache": sorted(set(cache_resource_ids)),
            "export": sorted(set(export_ids)),
        }
        if not provider_id.strip() or any(not values for values in categories.values()):
            raise ValidationError("PROVIDER_INCIDENT_SCOPE_INCOMPLETE", "provider incident exercise must identify source, derivative, publication, cache, and export scope")
        affected = [
            {"resource_type": kind, "resource_id": identifier, "withdrawal_state": "blocked_or_invalidated"}
            for kind, identifiers in categories.items()
            for identifier in identifiers
        ]
        incident = self.record_incident(
            tenant_id=tenant_id,
            project_id=project_id,
            incident_type="external_provider",
            severity="high",
            affected_subjects=[],
            affected_resources=affected,
            containment=[
                {"action": "disable_provider", "provider_id": provider_id},
                {"action": "block_publication", "count": len(categories["publication"])},
                {"action": "invalidate_derivatives", "count": len(categories["derivative"])},
                {"action": "withdraw_exports", "count": len(categories["export"])},
            ],
            notification_decision=notification_decision,
            evidence=evidence,
            actor_id=actor_id,
        )
        invalidations = [
            self.invalidate_caches(
                tenant_id=tenant_id,
                project_id=project_id,
                resource_id=resource_id,
                reason=f"provider_incident:{provider_id}",
                targets=["search", "vector", "viewer", "cdn", "signed_urls", "agent_cache", "exports"],
                actor_id=actor_id,
            )
            for resource_id in categories["cache"]
        ]
        return {
            "incident": incident,
            "provider_id": provider_id,
            "withdrawal_scope": categories,
            "cache_invalidations": invalidations,
            "investigation_evidence_preserved": True,
        }

    @staticmethod
    def _privacy_inventory_result(row: PrivacyInventoryRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"privacy_inventory_id": row.privacy_inventory_id, "data_category": row.data_category, "purpose": row.purpose, "version": row.version, "state": row.state, "content_hash": row.content_hash, "idempotent_replay": idempotent_replay}

    @staticmethod
    def _rights_result(row: PrivacyRightsRequestRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"rights_request_id": row.rights_request_id, "subject_id": row.subject_id, "request_type": row.request_type, "state": row.state, "due_at": _aware(row.due_at).isoformat(), "response_manifest": row.response_manifest_json, "verification": row.verification_json, "idempotent_replay": idempotent_replay}


    # ------------------------------------------------ transport, capture, and runtime safety
    def verify_transport_profile(
        self,
        *,
        endpoint: str,
        protocol: str,
        minimum_tls_version: str,
        certificate_validated: bool,
        channel_authentication: str,
        evidence: dict[str, Any],
        verified_by: str,
    ) -> dict[str, Any]:
        allowed_protocols = {"https", "wss", "postgresql+tls", "redis+tls", "quic+tls", "network-framework-tls", "local-authenticated-encrypted"}
        if protocol not in allowed_protocols:
            raise ValidationError("TRANSPORT_PROTOCOL_DENIED", "transport protocol is not in the approved encrypted profile")
        if protocol != "local-authenticated-encrypted":
            if minimum_tls_version not in {"TLSv1.3", "TLSv1.2"}:
                raise AuthorizationError("TRANSPORT_TLS_VERSION_DENIED", "network transport requires TLS 1.2 or newer")
            if not certificate_validated:
                raise AuthorizationError("TRANSPORT_CERTIFICATE_VALIDATION_REQUIRED", "network transport requires certificate validation")
        if channel_authentication not in {"mutual_tls", "server_tls_plus_signed_principal", "network_framework_identity", "paired_local_key"}:
            raise AuthorizationError("TRANSPORT_CHANNEL_AUTH_REQUIRED", "transport requires an approved authenticated channel")
        if not endpoint.strip() or not evidence.get("test_id") or not evidence.get("observed_at"):
            raise ValidationError("TRANSPORT_EVIDENCE_INCOMPLETE", "transport verification requires endpoint and retained controlled evidence")
        body = {
            "environment": self.environment,
            "endpoint": endpoint,
            "protocol": protocol,
            "minimum_tls_version": minimum_tls_version,
            "certificate_validated": certificate_validated,
            "channel_authentication": channel_authentication,
            "evidence": evidence,
            "verified_by": verified_by,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(TransportVerificationRow).where(TransportVerificationRow.verification_hash == digest))
            if existing:
                return {"transport_verification_id": existing.transport_verification_id, "state": existing.state, "verification_hash": existing.verification_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = TransportVerificationRow(
                transport_verification_id=identifier,
                environment=self.environment,
                endpoint=endpoint,
                protocol=protocol,
                minimum_tls_version=minimum_tls_version,
                certificate_validated=certificate_validated,
                channel_authentication=channel_authentication,
                state="passed",
                evidence_json=evidence,
                verification_hash=digest,
                verified_by=verified_by,
            )
            session.add(row)
            self.audit.append(
                tenant_id="platform",
                project_id=None,
                actor_id=verified_by,
                action="transport:verify",
                resource_type="transport_verification",
                resource_id=identifier,
                outcome="allowed",
                purpose="security_validation",
                details={"endpoint": endpoint, "protocol": protocol, "minimum_tls_version": minimum_tls_version, "certificate_validated": certificate_validated, "verification_hash": digest},
                session=session,
            )
            self._emit(session, event_type="transport.verified", tenant_id="platform", project_id=None, aggregate_type="transport_verification", aggregate_id=identifier, payload={"endpoint": endpoint, "protocol": protocol, "minimum_tls_version": minimum_tls_version, "certificate_validated": certificate_validated, "state": "passed", "verification_hash": digest}, actor_id=verified_by)
            return {"transport_verification_id": identifier, "state": "passed", "verification_hash": digest, "idempotent_replay": False}

    def record_capture_finalization(
        self,
        *,
        tenant_id: str,
        project_id: str,
        capture_id: str,
        package_root_hash: str,
        archive_sha256: str,
        device: dict[str, Any],
        app: dict[str, Any],
        signer_id: str,
        verification_result: str,
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        if not _SHA256.fullmatch(package_root_hash) or not _SHA256.fullmatch(archive_sha256):
            raise ValidationError("CAPTURE_FINALIZATION_HASH_INVALID", "capture finalization requires exact package-root and archive SHA-256 hashes")
        if verification_result not in {"passed", "failed", "quarantined"}:
            raise ValidationError("CAPTURE_FINALIZATION_RESULT_INVALID", "capture finalization result is invalid")
        if not capture_id.strip() or not signer_id.strip() or not device.get("device_id") or not device.get("platform") or not app.get("bundle_id") or not app.get("version"):
            raise ValidationError("CAPTURE_FINALIZATION_IDENTITY_INCOMPLETE", "capture finalization requires capture, device, app, and signer identity")
        if verification.get("root_hash_verified") is not True or verification.get("archive_hash_verified") is not True:
            raise AuthorizationError("CAPTURE_FINALIZATION_VERIFICATION_INCOMPLETE", "capture finalization cannot pass without verified package and archive hashes")
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "capture_id": capture_id,
            "package_root_hash": package_root_hash,
            "archive_sha256": archive_sha256,
            "device": device,
            "app": app,
            "signer_id": signer_id,
            "verification_result": verification_result,
            "verification": verification,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            existing = session.scalar(select(CaptureFinalizationAuditRow).where(CaptureFinalizationAuditRow.record_hash == digest))
            if existing:
                return {"capture_finalization_id": existing.capture_finalization_id, "record_hash": existing.record_hash, "verification_result": existing.verification_result, "idempotent_replay": True}
            identifier = new_uuid()
            row = CaptureFinalizationAuditRow(
                capture_finalization_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                capture_id=capture_id,
                package_root_hash=package_root_hash,
                archive_sha256=archive_sha256,
                device_json=device,
                app_json=app,
                signer_id=signer_id,
                verification_result=verification_result,
                verification_json=verification,
                record_hash=digest,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=signer_id,
                action="capture:finalize",
                resource_type="capture_package",
                resource_id=capture_id,
                outcome="allowed" if verification_result == "passed" else "failed",
                purpose="capture_finalization",
                device_context=device,
                before_ref=None,
                after_ref={"package_root_hash": package_root_hash, "archive_sha256": archive_sha256},
                manifest_refs=[{"capture_id": capture_id, "package_root_hash": package_root_hash, "archive_sha256": archive_sha256}],
                details={"app": app, "signer_id": signer_id, "verification_result": verification_result, "verification": verification, "record_hash": digest},
                session=session,
            )
            self._emit(session, event_type="capture.finalized", tenant_id=tenant_id, project_id=project_id, aggregate_type="capture_finalization", aggregate_id=capture_id, payload={"package_root_hash": package_root_hash, "archive_sha256": archive_sha256, "verification_result": verification_result, "record_hash": digest, "app_version": app.get("version")}, actor_id=signer_id)
            return {"capture_finalization_id": identifier, "record_hash": digest, "verification_result": verification_result, "idempotent_replay": False}

    def validate_provider_output(
        self,
        *,
        tenant_id: str,
        project_id: str,
        provider_id: str,
        operation_id: str,
        output_sha256: str,
        media_type: str,
        byte_count: int,
        validations: dict[str, Any],
        validated_by: str,
    ) -> dict[str, Any]:
        required = {"malware_scan", "resource_limits", "format_validation", "transform_validation", "content_policy", "hash_verified", "quarantine_write_only"}
        allowed_media_types = {"model/gltf-binary", "model/gltf+json", "application/octet-stream", "application/zip", "application/json", "image/png", "image/jpeg", "text/plain"}
        if not _SHA256.fullmatch(output_sha256) or byte_count < 0:
            raise ValidationError("PROVIDER_OUTPUT_IDENTITY_INVALID", "provider output requires an exact hash and non-negative byte count")
        if byte_count > 20 * 1024**3:
            raise ValidationError("PROVIDER_OUTPUT_RESOURCE_LIMIT", "provider output exceeds the platform validation size limit")
        if media_type not in allowed_media_types:
            raise ValidationError("PROVIDER_OUTPUT_MEDIA_TYPE_DENIED", "provider output media type is not admitted for isolated parsing")
        missing = sorted(required - set(validations))
        if missing:
            raise ValidationError("PROVIDER_OUTPUT_VALIDATION_INCOMPLETE", "provider output lacks required isolated validations", {"missing": missing})
        malformed = []
        for name in sorted(required):
            receipt = validations.get(name)
            if not isinstance(receipt, dict) or not isinstance(receipt.get("passed"), bool) or not receipt.get("tool") or not receipt.get("version") or not _SHA256.fullmatch(str(receipt.get("report_sha256", ""))):
                malformed.append(name)
        if malformed:
            raise ValidationError("PROVIDER_OUTPUT_RECEIPT_INVALID", "provider validation receipts require tool, version, result, and report hash", {"checks": malformed})
        if validations["hash_verified"].get("observed_sha256") != output_sha256:
            raise ValidationError("PROVIDER_OUTPUT_HASH_RECEIPT_MISMATCH", "provider hash-validation receipt does not match the admitted output")
        if validations["quarantine_write_only"].get("workspace_policy") != "write_only_staging":
            raise ValidationError("PROVIDER_OUTPUT_QUARANTINE_RECEIPT_INVALID", "provider output must remain in write-only staging during validation")
        findings = [
            {"check": name, "detail": value.get("detail", "failed")}
            for name, value in validations.items()
            if value.get("passed") is not True
        ]
        state = "validated_quarantined" if not findings else "rejected_quarantined"
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "provider_id": provider_id,
            "operation_id": operation_id,
            "output_sha256": output_sha256,
            "media_type": media_type,
            "byte_count": byte_count,
            "validations": validations,
            "findings": findings,
            "state": state,
            "validated_by": validated_by,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            provider = session.get(ProviderManifestRow, provider_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            if not provider:
                raise NotFoundError("provider_manifest", provider_id)
            existing = session.scalar(select(ProviderOutputValidationRow).where(ProviderOutputValidationRow.validation_hash == digest))
            if existing:
                return {"output_validation_id": existing.output_validation_id, "state": existing.state, "findings": existing.findings_json, "validation_hash": existing.validation_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = ProviderOutputValidationRow(
                output_validation_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
                operation_id=operation_id,
                output_sha256=output_sha256,
                media_type=media_type,
                byte_count=byte_count,
                validations_json=validations,
                findings_json=findings,
                state=state,
                validation_hash=digest,
                validated_by=validated_by,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=validated_by,
                action="provider_output:validate",
                resource_type="provider_output_validation",
                resource_id=identifier,
                outcome="allowed" if not findings else "denied",
                purpose="provider_return_validation",
                manifest_refs=[{"output_sha256": output_sha256, "byte_count": byte_count, "media_type": media_type}],
                details={"provider_id": provider_id, "operation_id": operation_id, "state": state, "finding_count": len(findings), "validation_hash": digest},
                session=session,
            )
            self._emit(session, event_type="provider_output.validated", tenant_id=tenant_id, project_id=project_id, aggregate_type="provider_output_validation", aggregate_id=identifier, payload={"provider_id": provider_id, "operation_id": operation_id, "output_sha256": output_sha256, "media_type": media_type, "byte_count": byte_count, "state": state, "finding_count": len(findings), "validation_hash": digest}, actor_id=validated_by)
            return {"output_validation_id": identifier, "state": state, "findings": findings, "validation_hash": digest, "idempotent_replay": False}

    def evaluate_immersive_safety(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        checks: dict[str, Any],
        requested_modes: list[str],
        actor_id: str,
    ) -> dict[str, Any]:
        required = {"accepted_scale", "walkability", "openings", "stairs_and_falls", "safe_spawn", "safe_exit"}
        missing = sorted(required - set(checks))
        if missing:
            raise ValidationError("IMMERSIVE_SAFETY_CHECKS_INCOMPLETE", "immersive safety profile lacks mandatory checks", {"missing": missing})
        normalized_modes = sorted(set(requested_modes))
        allowed_modes = {"orbit", "guided", "teleport", "walk", "fly"}
        if not normalized_modes or not set(normalized_modes).issubset(allowed_modes):
            raise ValidationError("IMMERSIVE_MODE_INVALID", "requested locomotion modes are invalid")
        failing = {name for name, value in checks.items() if (value.get("passed") if isinstance(value, dict) else value) is not True}
        disabled: set[str] = set()
        if failing & {"accepted_scale", "walkability", "openings", "stairs_and_falls", "safe_spawn"}:
            disabled.update({"walk", "teleport", "fly"})
        if "safe_exit" in failing:
            disabled.update({"walk", "teleport", "fly", "guided"})
        disabled &= set(normalized_modes)
        fallback = "orbit" if "orbit" in normalized_modes else "static_semantic_view"
        state = "degraded_safe" if disabled else "accepted"
        profile_hash = canonical_sha256({"checks": checks, "requested_modes": normalized_modes})
        body = {"tenant_id": tenant_id, "project_id": project_id, "scene_id": scene_id, "profile_hash": profile_hash, "disabled_modes": sorted(disabled), "fallback_mode": fallback, "state": state, "actor_id": actor_id}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            existing = session.scalar(select(ImmersiveSafetyDecisionRow).where(ImmersiveSafetyDecisionRow.decision_hash == digest))
            if existing:
                return {"safety_decision_id": existing.safety_decision_id, "state": existing.state, "disabled_modes": existing.disabled_modes_json, "fallback_mode": existing.fallback_mode, "decision_hash": existing.decision_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = ImmersiveSafetyDecisionRow(
                safety_decision_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                profile_hash=profile_hash,
                checks_json=checks,
                disabled_modes_json=sorted(disabled),
                fallback_mode=fallback,
                state=state,
                decision_hash=digest,
                decided_by=actor_id,
            )
            session.add(row)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="immersive_safety:evaluate",
                resource_type="immersive_safety_decision",
                resource_id=identifier,
                outcome="allowed",
                purpose="safe_navigation",
                details={"scene_id": scene_id, "state": state, "disabled_modes": sorted(disabled), "fallback_mode": fallback, "failed_checks": sorted(failing), "decision_hash": digest},
                session=session,
            )
            self._emit(session, event_type="immersive_safety.decided", tenant_id=tenant_id, project_id=project_id, aggregate_type="immersive_safety_decision", aggregate_id=identifier, payload={"scene_id": scene_id, "state": state, "disabled_modes": sorted(disabled), "fallback_mode": fallback, "failed_checks": sorted(failing), "decision_hash": digest}, actor_id=actor_id)
            return {"safety_decision_id": identifier, "state": state, "disabled_modes": sorted(disabled), "fallback_mode": fallback, "decision_hash": digest, "idempotent_replay": False}

    # --------------------------------------------------------------- audit verification
    def verify_audit_chain(self, *, tenant_id: str, project_id: str | None, referenced_manifests: list[dict[str, Any]], verifier_id: str) -> dict[str, Any]:
        chain = self.audit.verify(tenant_id)
        findings: list[dict[str, Any]] = []
        with self.database.session() as session:
            for reference in referenced_manifests:
                asset_id = str(reference.get("asset_id", ""))
                expected = str(reference.get("sha256", ""))
                if not asset_id or not _SHA256.fullmatch(expected):
                    findings.append({"code": "AUDIT_MANIFEST_REFERENCE_INVALID", "asset_id": asset_id})
                    continue
                ref = session.get(AssetRefRow, asset_id)
                obj = session.get(AssetRow, ref.sha256) if ref else None
                if not ref or ref.tenant_id != tenant_id or (project_id is not None and ref.project_id != project_id) or ref.tombstoned_at is not None or not obj or obj.sha256 != expected:
                    findings.append({"code": "AUDIT_MANIFEST_REFERENCE_MISSING_OR_MISMATCHED", "asset_id": asset_id})
            body = {"tenant_id": tenant_id, "project_id": project_id, "event_count": chain["events"], "head_hash": chain["head_hash"], "referenced_manifests": referenced_manifests, "findings": findings, "verifier_id": verifier_id}
            digest = canonical_sha256(body)
            existing = session.scalar(select(AuditVerificationRow).where(AuditVerificationRow.report_hash == digest))
            if existing:
                return {"audit_verification_id": existing.audit_verification_id, "valid": existing.valid, "events": existing.event_count, "head_hash": existing.head_hash, "findings": existing.findings_json, "report_hash": existing.report_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = AuditVerificationRow(audit_verification_id=identifier, tenant_id=tenant_id, project_id=project_id, event_count=int(chain["events"]), valid=not findings, head_hash=str(chain["head_hash"]), referenced_manifests_json=referenced_manifests, findings_json=findings, verifier_id=verifier_id, report_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=verifier_id, action="audit:verify", resource_type="audit_verification", resource_id=identifier, outcome="allowed" if not findings else "failed", details={"events": chain["events"], "head_hash": chain["head_hash"], "finding_count": len(findings), "report_hash": digest}, session=session)
            self._emit(session, event_type="audit_verification.completed", tenant_id=tenant_id, project_id=project_id, aggregate_type="audit_verification", aggregate_id=identifier, payload={"valid": not findings, "event_count": chain["events"], "head_hash": chain["head_hash"], "finding_count": len(findings), "report_hash": digest}, actor_id=verifier_id)
            return {"audit_verification_id": identifier, "valid": not findings, "events": chain["events"], "head_hash": chain["head_hash"], "findings": findings, "report_hash": digest, "idempotent_replay": False}

    # --------------------------------------------------------- provider governance/caches
    def authorize_provider_execution(
        self,
        *,
        provider_id: str,
        tenant_id: str,
        project_id: str,
        classification: str,
        purpose: str,
        region: str,
        external: bool,
        audience: str = "private",
        retention_days: int = 0,
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        denial: AuthorizationError | NotFoundError | None = None
        result: dict[str, Any] | None = None
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            provider = session.get(ProviderManifestRow, provider_id)
            if not provider:
                denial = NotFoundError("provider_manifest", provider_id)
            elif provider.approval_state != "approved" or (provider.expires_at and _aware(provider.expires_at) <= db_now()):
                denial = AuthorizationError("PROVIDER_NOT_APPROVED", "provider is not currently approved")
            elif self.local_only and (external or "network_required" in set(provider.deployments_json or [])):
                denial = AuthorizationError("LOCAL_ONLY_PROVIDER_EGRESS_DENIED", "local-only deployment denies network-required provider execution")
            elif "splatedit" in f"{provider.provider_id} {provider.source_url}".lower() and classification not in {"synthetic", "public", "public_cleared"}:
                denial = AuthorizationError(
                    "SPLATEDIT_DATA_CLASS_DENIED",
                    "SplatEdit remains limited to synthetic, public, or explicitly public-cleared fixtures",
                )
            elif classification not in set(provider.allowed_classifications_json or []) or purpose not in set(provider.allowed_purposes_json or []) or region not in set(provider.allowed_regions_json or []):
                denial = AuthorizationError("PROVIDER_POLICY_DENIED", "provider approval does not cover classification, purpose, and region")
            elif audience not in set((provider.descriptor_json or {}).get("allowed_audiences") or ["private", "project"]):
                denial = AuthorizationError("PROVIDER_AUDIENCE_DENIED", "provider approval does not cover the requested audience")
            elif retention_days < 0 or (provider.retention_days is None and retention_days != 0) or (provider.retention_days is not None and retention_days > provider.retention_days):
                denial = AuthorizationError("PROVIDER_RETENTION_DENIED", "provider approval does not cover the requested retention period")
            elif external and classification in {"restricted", "critical_infrastructure", "biometric", "minor"}:
                denial = AuthorizationError("EXTERNAL_PROVIDER_SENSITIVE_DATA_DENIED", "sensitive data is denied to public external providers without a higher-order approval")
            else:
                safe_telemetry = _validate_provider_telemetry(telemetry or {})
                result = {"provider_id": provider_id, "authorized": True, "manifest_hash": provider.manifest_hash, "telemetry": safe_telemetry}

            if denial is not None:
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=provider_id,
                    action="provider:egress_attempt" if denial.code == "LOCAL_ONLY_PROVIDER_EGRESS_DENIED" else "provider:authorize",
                    resource_type="provider_manifest",
                    resource_id=provider_id,
                    outcome="denied",
                    purpose=purpose,
                    details={"purpose": purpose, "classification": classification, "region": region, "external": external, "audience": audience, "retention_days": retention_days, "local_only": self.local_only, "reason_code": denial.code},
                    session=session,
                )
                if provider is not None:
                    self._emit(session, event_type="provider.execution.denied", tenant_id=tenant_id, project_id=project_id, aggregate_type="provider_manifest", aggregate_id=provider_id, payload={"purpose": purpose, "classification": classification, "region": region, "external": external, "audience": audience, "retention_days": retention_days, "reason_code": denial.code}, actor_id=provider_id)
            else:
                assert result is not None
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=provider_id,
                    action="provider:authorize",
                    resource_type="provider_manifest",
                    resource_id=provider_id,
                    outcome="allowed",
                    purpose=purpose,
                    details={"classification": classification, "region": region, "external": external, "audience": audience, "retention_days": retention_days, "manifest_hash": result["manifest_hash"]},
                    session=session,
                )
                self._emit(session, event_type="provider.execution.authorized", tenant_id=tenant_id, project_id=project_id, aggregate_type="provider_manifest", aggregate_id=provider_id, payload={"purpose": purpose, "classification": classification, "region": region, "external": external, "audience": audience, "retention_days": retention_days, "manifest_hash": result["manifest_hash"]}, actor_id=provider_id)
        if denial is not None:
            raise denial
        assert result is not None
        return result

    def create_provider_exception(self, *, tenant_id: str, project_id: str | None, provider_id: str, scope: dict[str, Any], purpose: str, requested_waivers: list[str], approved_by: str, duration_seconds: int) -> dict[str, Any]:
        prohibited = sorted(_PROHIBITED_EXCEPTION_WAIVERS.intersection(requested_waivers))
        if prohibited:
            raise AuthorizationError("PROVIDER_EXCEPTION_PROHIBITED_WAIVER", "provider exceptions cannot waive truth, consent, legal hold, authority, isolation, or evidence rules", {"prohibited": prohibited})
        if duration_seconds < 60 or duration_seconds > 2_592_000:
            raise ValidationError("PROVIDER_EXCEPTION_DURATION_INVALID", "provider exception duration must be between one minute and thirty days")
        body = {"tenant_id": tenant_id, "project_id": project_id, "provider_id": provider_id, "scope": scope, "purpose": purpose, "requested_waivers": sorted(set(requested_waivers)), "approved_by": approved_by, "duration_seconds": duration_seconds}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            if not session.get(ProviderManifestRow, provider_id):
                raise NotFoundError("provider_manifest", provider_id)
            existing = session.scalar(select(ProviderGovernanceExceptionRow).where(ProviderGovernanceExceptionRow.exception_hash == digest))
            if existing:
                return {"exception_id": existing.exception_id, "state": existing.state, "expires_at": _aware(existing.expires_at).isoformat(), "exception_hash": existing.exception_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = ProviderGovernanceExceptionRow(exception_id=identifier, tenant_id=tenant_id, project_id=project_id, provider_id=provider_id, scope_json=scope, purpose=purpose, prohibited_waivers_json=sorted(_PROHIBITED_EXCEPTION_WAIVERS), approved_by=approved_by, state="active", expires_at=db_now() + timedelta(seconds=duration_seconds), exception_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=approved_by, action="provider_exception:create", resource_type="provider_exception", resource_id=identifier, outcome="allowed", details={"provider_id": provider_id, "purpose": purpose, "expires_at": row.expires_at.isoformat(), "waivers": body["requested_waivers"]}, session=session)
            self._emit(session, event_type="provider_exception.created", tenant_id=tenant_id, project_id=project_id, aggregate_type="provider_exception", aggregate_id=identifier, payload={"provider_id": provider_id, "purpose": purpose, "expires_at": row.expires_at.isoformat(), "waivers": body["requested_waivers"], "exception_hash": digest}, actor_id=approved_by)
            return {"exception_id": identifier, "state": "active", "expires_at": row.expires_at.isoformat(), "exception_hash": digest, "idempotent_replay": False}

    def invalidate_caches(self, *, tenant_id: str, project_id: str | None, resource_id: str, reason: str, targets: list[str], actor_id: str) -> dict[str, Any]:
        required = {"search", "vector", "viewer", "cdn", "signed_urls", "agent_cache", "exports"}
        normalized = sorted(set(targets))
        if not required.issubset(normalized):
            raise ValidationError("CACHE_INVALIDATION_TARGETS_INCOMPLETE", "privacy or authority invalidation must cover every derivative cache", {"missing": sorted(required - set(normalized))})
        body = {"tenant_id": tenant_id, "project_id": project_id, "resource_id": resource_id, "reason": reason, "targets": normalized}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project_scope(session, tenant_id, project_id)
            existing = session.scalar(select(CacheInvalidationRow).where(CacheInvalidationRow.invalidation_hash == digest))
            if existing:
                return {"invalidation_id": existing.invalidation_id, "state": existing.state, "targets": existing.targets_json, "invalidation_hash": existing.invalidation_hash, "idempotent_replay": True}
            identifier = new_uuid()
            row = CacheInvalidationRow(invalidation_id=identifier, tenant_id=tenant_id, project_id=project_id, resource_id=resource_id, reason=reason, targets_json=normalized, state="completed", requested_by=actor_id, completed_at=db_now(), invalidation_hash=digest)
            session.add(row)
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="cache:invalidate", resource_type="cache_invalidation", resource_id=identifier, outcome="allowed", details={"resource_id": resource_id, "reason": reason, "targets": normalized}, session=session)
            self._emit(session, event_type="cache_invalidation.completed", tenant_id=tenant_id, project_id=project_id, aggregate_type="cache_invalidation", aggregate_id=identifier, payload={"resource_id": resource_id, "reason": reason, "targets": normalized, "state": "completed", "invalidation_hash": digest}, actor_id=actor_id)
            return {"invalidation_id": identifier, "state": "completed", "targets": normalized, "invalidation_hash": digest, "idempotent_replay": False}

    # -------------------------------------------------------------- supply-chain release
    def create_release_record(self, *, version: str, source_commit: str, source_root: str, component_manifests: dict[str, Any], evidence: dict[str, Any], rollback_plan: dict[str, Any], environment_policy: dict[str, Any], signed_by: str, emergency_patch: bool = False, retrospective_review_due_at: datetime | None = None) -> dict[str, Any]:
        if not _SHA256.fullmatch(source_root) or not re.fullmatch(r"[a-f0-9]{40,64}", source_commit):
            raise ValidationError("RELEASE_SOURCE_IDENTITY_INVALID", "release source commit and root are invalid")
        missing_components = sorted(_REQUIRED_RELEASE_COMPONENTS - set(component_manifests))
        missing_evidence = sorted(_REQUIRED_RELEASE_EVIDENCE - set(evidence))
        if missing_components or missing_evidence:
            raise ValidationError("RELEASE_RECORD_INCOMPLETE", "release record lacks required component manifests or evidence", {"missing_components": missing_components, "missing_evidence": missing_evidence})
        for name, record in component_manifests.items():
            if not isinstance(record, dict) or not _SHA256.fullmatch(str(record.get("sha256", ""))):
                raise ValidationError("RELEASE_COMPONENT_MANIFEST_INVALID", "component manifest must retain a SHA-256 digest", {"component": name})
        if not rollback_plan.get("services") or not rollback_plan.get("workers") or not rollback_plan.get("configuration") or not rollback_plan.get("database_compatibility"):
            raise ValidationError("RELEASE_ROLLBACK_PLAN_INCOMPLETE", "rollback plan must cover services, workers/models, configuration, and database compatibility")
        if emergency_patch and not retrospective_review_due_at:
            raise ValidationError("EMERGENCY_PATCH_REVIEW_REQUIRED", "emergency patch requires a retrospective review due date")
        body = {"version": version, "source_commit": source_commit, "source_root": source_root, "component_manifests": component_manifests, "evidence": evidence, "rollback_plan": rollback_plan, "environment_policy": environment_policy, "emergency_patch": emergency_patch, "retrospective_review_due_at": _iso(retrospective_review_due_at), "signed_by": signed_by}
        digest = canonical_sha256(body)
        signature = base64.b64encode(hmac.new(self.signing_key, digest.encode(), sha256).digest()).decode()
        with self.database.session() as session:
            existing = session.scalar(select(SupplyChainReleaseRow).where(SupplyChainReleaseRow.release_hash == digest))
            if existing:
                return self._release_result(existing, idempotent_replay=True)
            identifier = new_uuid()
            row = SupplyChainReleaseRow(release_record_id=identifier, version=version, source_commit=source_commit, source_root=source_root, component_manifests_json=component_manifests, evidence_json=evidence, rollback_plan_json=rollback_plan, environment_policy_json=environment_policy, emergency_patch=emergency_patch, retrospective_review_due_at=_aware(retrospective_review_due_at) if retrospective_review_due_at else None, state="candidate", signed_by=signed_by, signature=signature, release_hash=digest)
            session.add(row)
            self.audit.append(tenant_id="platform", project_id=None, actor_id=signed_by, action="release_record:create", resource_type="supply_chain_release", resource_id=identifier, outcome="allowed", details={"version": version, "source_commit": source_commit, "source_root": source_root, "release_hash": digest, "emergency_patch": emergency_patch}, session=session)
            self._emit(session, event_type="supply_chain_release.created", tenant_id="platform", project_id=None, aggregate_type="supply_chain_release", aggregate_id=identifier, payload={"version": version, "source_commit": source_commit, "source_root": source_root, "release_hash": digest, "emergency_patch": emergency_patch, "state": "candidate"}, actor_id=signed_by)
            return self._release_result(row, idempotent_replay=False)

    def promote_release(self, *, release_record_id: str, actor_id: str) -> dict[str, Any]:
        if self.environment != "production":
            raise AuthorizationError("RELEASE_ENVIRONMENT_DENIED", "release promotion is unavailable outside an approved production control plane")
        with self.database.session() as session:
            row = session.get(SupplyChainReleaseRow, release_record_id)
            if not row:
                raise NotFoundError("supply_chain_release", release_record_id)
            expected_signature = base64.b64encode(hmac.new(self.signing_key, row.release_hash.encode(), sha256).digest()).decode()
            if not hmac.compare_digest(expected_signature, row.signature):
                raise AuthorizationError("RELEASE_SIGNATURE_INVALID", "release record signature is invalid")
            blocked = {name: record for name, record in row.evidence_json.items() if not isinstance(record, dict) or record.get("control_status") not in {"passed_complete", "passed_with_external_gaps"}}
            production_blockers = {name: record for name, record in row.evidence_json.items() if isinstance(record, dict) and record.get("production_blocking") and record.get("control_status") != "passed_complete"}
            if blocked or production_blockers or row.environment_policy_json.get("production_authorized") is not True:
                raise AuthorizationError("RELEASE_PROMOTION_DENIED", "release promotion lacks complete governed evidence or environment authorization", {"blocked": sorted(blocked), "production_blockers": sorted(production_blockers)})
            row.state = "promoted"
            row.promoted_at = db_now()
            self.audit.append(tenant_id="platform", project_id=None, actor_id=actor_id, action="release_record:promote", resource_type="supply_chain_release", resource_id=release_record_id, outcome="allowed", details={"version": row.version, "release_hash": row.release_hash}, session=session)
            self._emit(session, event_type="supply_chain_release.promoted", tenant_id="platform", project_id=None, aggregate_type="supply_chain_release", aggregate_id=release_record_id, payload={"version": row.version, "source_commit": row.source_commit, "source_root": row.source_root, "release_hash": row.release_hash, "state": "promoted", "promoted_at": row.promoted_at.isoformat()}, actor_id=actor_id)
            return self._release_result(row, idempotent_replay=False)

    @staticmethod
    def _release_result(row: SupplyChainReleaseRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {"release_record_id": row.release_record_id, "version": row.version, "source_commit": row.source_commit, "source_root": row.source_root, "state": row.state, "release_hash": row.release_hash, "signature": row.signature, "emergency_patch": row.emergency_patch, "idempotent_replay": idempotent_replay}


def _scope_contains(granted: Any, requested: Any) -> bool:
    """Return True only when the requested JIT scope is a subset of the grant."""
    if isinstance(granted, dict) and isinstance(requested, dict):
        return all(key in granted and _scope_contains(granted[key], value) for key, value in requested.items())
    if isinstance(granted, list) and isinstance(requested, list):
        granted_hashes = {canonical_sha256(item) for item in granted}
        return all(canonical_sha256(item) in granted_hashes for item in requested)
    return granted == requested



def _aware(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("datetime is required")
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).astimezone(UTC).isoformat() if value else None


def _subject_related(provenance: dict[str, Any], subject_id: str) -> bool:
    if provenance.get("subject_id") == subject_id:
        return True
    return subject_id in set(provenance.get("subject_ids") or [])


def _validate_provider_telemetry(telemetry: dict[str, Any]) -> dict[str, Any]:
    forbidden = {"geometry", "media", "transcript", "secret", "password", "precise_location", "coordinates", "raw_output"}
    for key in telemetry:
        normalized = key.lower()
        if any(fragment in normalized for fragment in forbidden):
            raise ValidationError("PROVIDER_TELEMETRY_SENSITIVE", "provider telemetry may not contain raw customer content or precise locations", {"field": key})
    encoded = canonical_json(telemetry)
    if len(encoded) > 16_384:
        raise ValidationError("PROVIDER_TELEMETRY_TOO_LARGE", "provider telemetry exceeds the privacy-safe summary limit")
    return telemetry
