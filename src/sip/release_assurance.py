from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, new_uuid
from .database import (
    Database,
    ProjectRow,
    QAAcceptanceCampaignRow,
    QAGateResultRow,
    QAReleaseCandidateRow,
    QAReleaseWaiverRow,
    QARollbackRehearsalRow,
    QAScenarioResultRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .temporal import db_now

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
CONTROL_STATUSES = {"passed_complete", "passed_with_external_gaps", "blocked", "failed"}
EXECUTION_STATUSES = {"completed_successfully", "completed_with_findings", "not_executed", "failed"}
EVIDENCE_CLASSES = {
    "synthetic",
    "local_controlled",
    "local_executed",
    "browser_executed",
    "device_executed",
    "cloud_executed",
    "external_witnessed",
}
SCENARIOS = {"construction", "liveforever"}
GATE_TYPES = {
    "requirements",
    "license_model_rights",
    "security_privacy",
    "accessibility",
    "load_performance",
    "backup_restore",
    "migration",
    "rollback",
    "open_export",
    "hybrid_authority",
    "support_recovery",
    "sbom_vulnerability",
    "release_manifest",
    "construction_acceptance",
    "liveforever_acceptance",
}
NO_WAIVER_PREFIXES = (
    "CONSENT",
    "AUTH",
    "TSTSEC",
    "CONAUTH",
    "LIFCONS",
    "LIFSAFE",
    "TSTGATE-009",
)
REQUIRED_ARTIFACT_FIELDS = {"path", "sha256", "byte_count", "media_type"}


def _is_sha256(value: str) -> bool:
    return SHA256_RE.fullmatch(value) is not None


def _is_source_commit(value: str) -> bool:
    return SOURCE_COMMIT_RE.fullmatch(value) is not None


def _dt(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _validate_evidence_items(items: list[dict[str, Any]], *, allow_empty: bool = False) -> None:
    if not items and not allow_empty:
        raise ValidationError("QA_EVIDENCE_REQUIRED", "retained evidence is required")
    seen: set[tuple[str, str]] = set()
    for item in items:
        path = str(item.get("path", ""))
        digest = str(item.get("sha256", ""))
        if not _safe_relative_path(path) or not _is_sha256(digest):
            raise ValidationError(
                "QA_EVIDENCE_INVALID",
                "evidence requires a safe relative path and SHA-256 digest",
                {"path": path},
            )
        key = (path, digest)
        if key in seen:
            raise ValidationError("QA_EVIDENCE_DUPLICATE", "duplicate evidence entry", {"path": path})
        seen.add(key)


def _release_artifact_findings(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if manifest.get("schema") != "sip.release-artifacts/v1":
        findings.append({"code": "QA_RELEASE_ARTIFACT_SCHEMA_INVALID"})
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        findings.append({"code": "QA_RELEASE_ARTIFACTS_MISSING"})
        return findings
    paths: set[str] = set()
    digests: set[str] = set()
    canonical_items: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict) or not REQUIRED_ARTIFACT_FIELDS <= set(artifact):
            findings.append({"code": "QA_RELEASE_ARTIFACT_INCOMPLETE", "index": index})
            continue
        path = str(artifact.get("path", ""))
        digest = str(artifact.get("sha256", ""))
        byte_count = artifact.get("byte_count")
        media_type = str(artifact.get("media_type", ""))
        if not _safe_relative_path(path):
            findings.append({"code": "QA_RELEASE_ARTIFACT_PATH_UNSAFE", "path": path})
        if not _is_sha256(digest):
            findings.append({"code": "QA_RELEASE_ARTIFACT_HASH_INVALID", "path": path})
        if not isinstance(byte_count, int) or byte_count < 0:
            findings.append({"code": "QA_RELEASE_ARTIFACT_SIZE_INVALID", "path": path})
        if not media_type:
            findings.append({"code": "QA_RELEASE_ARTIFACT_MEDIA_TYPE_MISSING", "path": path})
        if path in paths:
            findings.append({"code": "QA_RELEASE_ARTIFACT_PATH_DUPLICATE", "path": path})
        if digest in digests:
            findings.append({"code": "QA_RELEASE_ARTIFACT_HASH_DUPLICATE", "sha256": digest})
        paths.add(path)
        digests.add(digest)
        canonical_items.append(
            {"path": path, "sha256": digest, "byte_count": byte_count, "media_type": media_type}
        )
    expected_root = canonical_sha256(sorted(canonical_items, key=lambda item: item["path"]))
    if manifest.get("content_root_sha256") != expected_root:
        findings.append(
            {
                "code": "QA_RELEASE_CONTENT_ROOT_MISMATCH",
                "expected": expected_root,
                "actual": manifest.get("content_root_sha256"),
            }
        )
    if manifest.get("signed") is not True:
        findings.append({"code": "QA_RELEASE_ARTIFACT_MANIFEST_UNSIGNED"})
    if not str(manifest.get("signature_reference", "")).strip():
        findings.append({"code": "QA_RELEASE_SIGNATURE_REFERENCE_MISSING"})
    return findings


class ReleaseAssuranceService:
    """Durable QA-002 release evidence and fail-closed promotion control plane."""

    def __init__(self, database: Database, audit: AuditService, signing_key: bytes, *, environment: str) -> None:
        if len(signing_key) < 32:
            raise ValueError("release assurance signing key must be at least 32 bytes")
        self.database = database
        self.audit = audit
        self.environment = environment
        self._private_key = Ed25519PrivateKey.from_private_bytes(signing_key[:32])
        self._public_key = self._private_key.public_key()
        self.events = OutboxEventFactory()

    @staticmethod
    def _require_project(session: Session, tenant_id: str, project_id: str | None) -> ProjectRow | None:
        if project_id is None:
            return None
        row = session.get(ProjectRow, project_id)
        if row is None or row.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)
        return row

    @staticmethod
    def _campaign_row(session: Session, campaign_id: str, tenant_id: str) -> QAAcceptanceCampaignRow:
        campaign = session.get(QAAcceptanceCampaignRow, campaign_id)
        if campaign is None or campaign.tenant_id != tenant_id:
            raise NotFoundError("qa_campaign", campaign_id)
        return campaign

    def _emit(
        self,
        session: Session,
        *,
        event_type: str,
        tenant_id: str,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        actor_id: str,
        payload: dict[str, Any],
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
                producer="release-assurance",
                actor_id=actor_id,
                workload_identity=None,
                correlation_id=aggregate_id,
            )
        )

    def _audit_emit(
        self,
        session: Session,
        *,
        tenant_id: str,
        project_id: str | None,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any],
        event_type: str,
        payload: dict[str, Any],
        outcome: str = "allowed",
    ) -> None:
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details,
            session=session,
        )
        self._emit(
            session,
            event_type=event_type,
            tenant_id=tenant_id,
            project_id=project_id,
            aggregate_type=resource_type,
            aggregate_id=resource_id,
            actor_id=actor_id,
            payload=payload,
        )

    def create_campaign(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        checkpoint_id: str,
        release_class: str,
        scope: dict[str, Any],
        test_data: dict[str, Any],
        operating_envelope: dict[str, Any],
        limitations: list[dict[str, Any]],
        support_plan: dict[str, Any],
        recovery_plan: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        if release_class not in {"research", "development", "pilot", "production", "enterprise"}:
            raise ValidationError("QA_RELEASE_CLASS_INVALID", "unsupported release class")
        requirement_ids = scope.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids or len(set(requirement_ids)) != len(requirement_ids):
            raise ValidationError("QA_SCOPE_REQUIRED", "campaign requires a unique exact requirement scope")
        if scope.get("epic") != "QA-002":
            raise AuthorizationError("QA_SCOPE_OUTSIDE_AUTHORIZATION", "Progress 11 is bounded to QA-002")
        if test_data.get("classification") not in {"synthetic", "consented"}:
            raise ValidationError("QA_TEST_DATA_POLICY_INVALID", "QA data must be synthetic or documented-consent data")
        if test_data.get("customer_data") or test_data.get("human_subjects"):
            raise AuthorizationError("QA_LIVE_DATA_DENIED", "bounded QA campaign cannot use customer or human-subject data")
        if not operating_envelope.get("profiles") or operating_envelope.get("production_authorized") is not False:
            raise ValidationError("QA_OPERATING_ENVELOPE_INVALID", "operating envelope must be explicit and production-denying")
        if not support_plan.get("owner") or not support_plan.get("escalation"):
            raise ValidationError("QA_SUPPORT_PLAN_INCOMPLETE", "campaign requires support ownership and escalation")
        if not recovery_plan.get("rollback") or not recovery_plan.get("open_export"):
            raise ValidationError("QA_RECOVERY_PLAN_INCOMPLETE", "campaign requires rollback and open-export recovery")
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "checkpoint_id": checkpoint_id,
            "release_class": release_class,
            "scope": scope,
            "test_data": test_data,
            "operating_envelope": operating_envelope,
            "limitations": limitations,
            "support_plan": support_plan,
            "recovery_plan": recovery_plan,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            existing = session.scalar(
                select(QAAcceptanceCampaignRow).where(QAAcceptanceCampaignRow.campaign_hash == digest)
            )
            if existing:
                return self._campaign(existing, idempotent_replay=True)
            conflicting = session.scalar(
                select(QAAcceptanceCampaignRow).where(
                    QAAcceptanceCampaignRow.tenant_id == tenant_id,
                    QAAcceptanceCampaignRow.checkpoint_id == checkpoint_id,
                )
            )
            if conflicting:
                raise ConflictError("QA_CAMPAIGN_IMMUTABLE", "checkpoint already has a different QA campaign")
            row = QAAcceptanceCampaignRow(
                campaign_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                checkpoint_id=checkpoint_id,
                release_class=release_class,
                scope_json=scope,
                test_data_json=test_data,
                operating_envelope_json=operating_envelope,
                limitations_json=limitations,
                support_plan_json=support_plan,
                recovery_plan_json=recovery_plan,
                state="active",
                campaign_hash=digest,
                created_by=actor_id,
            )
            session.add(row)
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="qa:campaign_create",
                resource_type="qa_campaign",
                resource_id=row.campaign_id,
                details={"checkpoint_id": checkpoint_id, "release_class": release_class, "campaign_hash": digest},
                event_type="qa.campaign.created",
                payload={"checkpoint_id": checkpoint_id, "release_class": release_class, "campaign_hash": digest},
            )
            session.flush()
            return self._campaign(row, idempotent_replay=False)

    def record_scenario(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        project_id: str | None,
        scenario_type: str,
        profile: str,
        evidence_class: str,
        input_hashes: dict[str, str],
        output_hashes: dict[str, str],
        metrics: dict[str, Any],
        assertions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        environment: dict[str, Any],
        status: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if scenario_type not in SCENARIOS:
            raise ValidationError("QA_SCENARIO_INVALID", "scenario must be construction or liveforever")
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValidationError("QA_EVIDENCE_CLASS_INVALID", "unsupported evidence class")
        if status not in {"passed", "failed", "blocked"}:
            raise ValidationError("QA_SCENARIO_STATUS_INVALID", "scenario status is invalid")
        for name, digest in {**input_hashes, **output_hashes}.items():
            if not _is_sha256(str(digest)):
                raise ValidationError("QA_SCENARIO_HASH_INVALID", "scenario hashes must be SHA-256", {"name": name})
        _validate_evidence_items(evidence)
        if not assertions or any("requirement_id" not in item or "passed" not in item for item in assertions):
            raise ValidationError("QA_SCENARIO_ASSERTIONS_REQUIRED", "scenario requires requirement-bound assertions")
        if status == "passed" and any(item.get("passed") is not True for item in assertions):
            raise ValidationError("QA_SCENARIO_PASS_OVERCLAIM", "passed scenario contains a failed assertion")
        body = {
            "campaign_id": campaign_id,
            "project_id": project_id,
            "scenario_type": scenario_type,
            "profile": profile,
            "evidence_class": evidence_class,
            "input_hashes": input_hashes,
            "output_hashes": output_hashes,
            "metrics": metrics,
            "assertions": assertions,
            "evidence": evidence,
            "environment": environment,
            "status": status,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            campaign = self._campaign_row(session, campaign_id, tenant_id)
            if campaign.project_id != project_id:
                raise NotFoundError("qa_campaign", campaign_id)
            scope = set(campaign.scope_json.get("requirement_ids", []))
            out_of_scope = sorted({str(item["requirement_id"]) for item in assertions} - scope)
            if out_of_scope:
                raise AuthorizationError(
                    "QA_SCENARIO_REQUIREMENT_OUT_OF_SCOPE",
                    "scenario references requirements outside the campaign",
                    {"requirement_ids": out_of_scope},
                )
            existing = session.scalar(
                select(QAScenarioResultRow).where(
                    QAScenarioResultRow.campaign_id == campaign_id,
                    QAScenarioResultRow.scenario_type == scenario_type,
                    QAScenarioResultRow.profile == profile,
                )
            )
            if existing:
                if existing.scenario_hash != digest:
                    raise ConflictError("QA_SCENARIO_IMMUTABLE", "scenario profile already has different evidence")
                return self._scenario(existing, idempotent_replay=True)
            row = QAScenarioResultRow(
                scenario_result_id=new_uuid(),
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scenario_type=scenario_type,
                profile=profile,
                evidence_class=evidence_class,
                input_hashes_json=input_hashes,
                output_hashes_json=output_hashes,
                metrics_json=metrics,
                assertions_json=assertions,
                evidence_json=evidence,
                environment_json=environment,
                status=status,
                scenario_hash=digest,
                recorded_by=actor_id,
            )
            session.add(row)
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="qa:scenario_record",
                resource_type="qa_scenario",
                resource_id=row.scenario_result_id,
                details={"campaign_id": campaign_id, "scenario_type": scenario_type, "status": status},
                event_type="qa.scenario.recorded",
                payload={
                    "campaign_id": campaign_id,
                    "scenario_type": scenario_type,
                    "status": status,
                    "scenario_hash": digest,
                },
            )
            session.flush()
            return self._scenario(row, idempotent_replay=False)

    def record_gate(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        gate_type: str,
        required: bool,
        execution_status: str,
        control_status: str,
        thresholds: dict[str, Any],
        result: dict[str, Any],
        findings: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        external_gap: bool,
        actor_id: str,
    ) -> dict[str, Any]:
        if gate_type not in GATE_TYPES:
            raise ValidationError("QA_GATE_TYPE_INVALID", "unsupported QA gate type")
        if execution_status not in EXECUTION_STATUSES or control_status not in CONTROL_STATUSES:
            raise ValidationError("QA_GATE_STATUS_INVALID", "gate execution/control status is invalid")
        if execution_status == "not_executed" and not external_gap:
            raise ValidationError("QA_UNEXECUTED_GATE_UNCLASSIFIED", "unexecuted gate must be an explicit external gap")
        if control_status == "passed_complete" and (external_gap or findings or execution_status != "completed_successfully"):
            raise ValidationError("QA_GATE_PASS_OVERCLAIM", "complete pass requires successful execution without findings or gaps")
        if control_status == "passed_with_external_gaps" and not external_gap:
            raise ValidationError("QA_GATE_GAP_CLASSIFICATION_MISSING", "external-gap pass requires explicit external classification")
        _validate_evidence_items(evidence, allow_empty=execution_status == "not_executed")
        body = {
            "campaign_id": campaign_id,
            "gate_type": gate_type,
            "required": required,
            "execution_status": execution_status,
            "control_status": control_status,
            "thresholds": thresholds,
            "result": result,
            "findings": findings,
            "evidence": evidence,
            "external_gap": external_gap,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            campaign = self._campaign_row(session, campaign_id, tenant_id)
            existing = session.scalar(
                select(QAGateResultRow).where(
                    QAGateResultRow.campaign_id == campaign_id,
                    QAGateResultRow.gate_type == gate_type,
                )
            )
            if existing:
                if existing.gate_hash != digest:
                    raise ConflictError("QA_GATE_IMMUTABLE", "gate already has different evidence")
                return self._gate(existing, idempotent_replay=True)
            row = QAGateResultRow(
                gate_result_id=new_uuid(),
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                gate_type=gate_type,
                required=required,
                execution_status=execution_status,
                control_status=control_status,
                thresholds_json=thresholds,
                result_json=result,
                findings_json=findings,
                evidence_json=evidence,
                external_gap=external_gap,
                gate_hash=digest,
                recorded_by=actor_id,
            )
            session.add(row)
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=campaign.project_id,
                actor_id=actor_id,
                action="qa:gate_record",
                resource_type="qa_gate",
                resource_id=row.gate_result_id,
                details={"campaign_id": campaign_id, "gate_type": gate_type, "control_status": control_status},
                event_type="qa.gate.recorded",
                payload={
                    "campaign_id": campaign_id,
                    "gate_type": gate_type,
                    "control_status": control_status,
                    "gate_hash": digest,
                },
            )
            session.flush()
            return self._gate(row, idempotent_replay=False)

    def approve_waiver(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        requirement_id: str,
        priority: str,
        reason: str,
        compensating_control: dict[str, Any],
        owner: str,
        expires_at: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        if priority == "P0" or requirement_id.startswith(NO_WAIVER_PREFIXES):
            raise AuthorizationError(
                "QA_WAIVER_PROHIBITED",
                "P0, truth, consent, authority, and security stop-lines cannot be waived",
            )
        if expires_at <= db_now():
            raise ValidationError("QA_WAIVER_EXPIRED", "waiver expiration must be in the future")
        if not compensating_control.get("control") or not compensating_control.get("verification"):
            raise ValidationError("QA_COMPENSATING_CONTROL_REQUIRED", "waiver requires a verified compensating control")
        body = {
            "campaign_id": campaign_id,
            "requirement_id": requirement_id,
            "priority": priority,
            "reason": reason,
            "compensating_control": compensating_control,
            "owner": owner,
            "expires_at": _dt(expires_at),
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            campaign = self._campaign_row(session, campaign_id, tenant_id)
            if requirement_id not in set(campaign.scope_json.get("requirement_ids", [])):
                raise AuthorizationError("QA_WAIVER_REQUIREMENT_OUT_OF_SCOPE", "waiver requirement is outside campaign scope")
            existing = session.scalar(
                select(QAReleaseWaiverRow).where(
                    QAReleaseWaiverRow.campaign_id == campaign_id,
                    QAReleaseWaiverRow.requirement_id == requirement_id,
                )
            )
            if existing:
                if existing.waiver_hash != digest:
                    raise ConflictError("QA_WAIVER_IMMUTABLE", "requirement already has a different waiver")
                return self._waiver(existing, idempotent_replay=True)
            row = QAReleaseWaiverRow(
                waiver_id=new_uuid(),
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                requirement_id=requirement_id,
                priority=priority,
                reason=reason,
                compensating_control_json=compensating_control,
                owner=owner,
                expires_at=expires_at,
                state="active",
                waiver_hash=digest,
                approved_by=actor_id,
            )
            session.add(row)
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=campaign.project_id,
                actor_id=actor_id,
                action="qa:waiver_approve",
                resource_type="qa_waiver",
                resource_id=row.waiver_id,
                details={"requirement_id": requirement_id, "expires_at": _dt(expires_at)},
                event_type="qa.waiver.approved",
                payload={
                    "campaign_id": campaign_id,
                    "requirement_id": requirement_id,
                    "expires_at": _dt(expires_at),
                    "waiver_hash": digest,
                },
            )
            session.flush()
            return self._waiver(row, idempotent_replay=False)

    def record_rollback(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        from_release: str,
        to_release: str,
        recovery_point_id: str | None,
        before_hashes: dict[str, str],
        after_hashes: dict[str, str],
        steps: list[dict[str, Any]],
        verification: dict[str, Any],
        status: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if status not in {"passed", "failed", "blocked"}:
            raise ValidationError("QA_ROLLBACK_STATUS_INVALID", "rollback status is invalid")
        if not before_hashes or any(not _is_sha256(str(value)) for value in before_hashes.values()):
            raise ValidationError("QA_ROLLBACK_HASH_INVALID", "rollback pre-state hashes must be SHA-256")
        if not after_hashes or any(not _is_sha256(str(value)) for value in after_hashes.values()):
            raise ValidationError("QA_ROLLBACK_HASH_INVALID", "rollback post-state hashes must be SHA-256")
        if status == "passed" and before_hashes != after_hashes:
            raise ValidationError("QA_ROLLBACK_DATA_LOSS", "passed rollback must restore the prior hash set")
        if not steps or not verification.get("migration_reversed") or not verification.get("data_reconciled"):
            raise ValidationError(
                "QA_ROLLBACK_EVIDENCE_INCOMPLETE",
                "rollback requires steps, migration, and data reconciliation evidence",
            )
        body = {
            "campaign_id": campaign_id,
            "from_release": from_release,
            "to_release": to_release,
            "recovery_point_id": recovery_point_id,
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "steps": steps,
            "verification": verification,
            "status": status,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            campaign = self._campaign_row(session, campaign_id, tenant_id)
            existing = session.scalar(
                select(QARollbackRehearsalRow).where(
                    QARollbackRehearsalRow.campaign_id == campaign_id,
                    QARollbackRehearsalRow.from_release == from_release,
                    QARollbackRehearsalRow.to_release == to_release,
                )
            )
            if existing:
                if existing.rehearsal_hash != digest:
                    raise ConflictError("QA_ROLLBACK_IMMUTABLE", "rollback path already has different evidence")
                return self._rollback(existing, idempotent_replay=True)
            row = QARollbackRehearsalRow(
                rehearsal_id=new_uuid(),
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                from_release=from_release,
                to_release=to_release,
                recovery_point_id=recovery_point_id,
                before_hashes_json=before_hashes,
                after_hashes_json=after_hashes,
                steps_json=steps,
                verification_json=verification,
                status=status,
                rehearsal_hash=digest,
                rehearsed_by=actor_id,
            )
            session.add(row)
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=campaign.project_id,
                actor_id=actor_id,
                action="qa:rollback_record",
                resource_type="qa_rollback",
                resource_id=row.rehearsal_id,
                details={"from_release": from_release, "to_release": to_release, "status": status},
                event_type="qa.rollback.recorded",
                payload={"campaign_id": campaign_id, "status": status, "rehearsal_hash": digest},
            )
            session.flush()
            return self._rollback(row, idempotent_replay=False)

    def evaluate_and_sign_candidate(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        source_commit: str,
        source_root_sha256: str,
        release_manifest: dict[str, Any],
        signer_key_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        try:
            return self._evaluate_and_sign_candidate_once(
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                source_commit=source_commit,
                source_root_sha256=source_root_sha256,
                release_manifest=release_manifest,
                signer_key_id=signer_key_id,
                actor_id=actor_id,
            )
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc))
            expected = (
                "qa_release_candidates" in detail
                and (
                    "manifest_hash" in detail
                    or (
                        "campaign_id" in detail
                        and "source_commit" in detail
                        and "source_root_sha256" in detail
                    )
                )
            )
            if not expected:
                raise
            # A simultaneous writer won the project-scoped source-identity race.
            # Resolve through a fresh transaction; the regular immutable replay
            # path verifies that all campaign inputs and the canonical manifest
            # are equivalent before returning the existing governed result.
            return self._evaluate_and_sign_candidate_once(
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                source_commit=source_commit,
                source_root_sha256=source_root_sha256,
                release_manifest=release_manifest,
                signer_key_id=signer_key_id,
                actor_id=actor_id,
            )

    def _evaluate_and_sign_candidate_once(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        source_commit: str,
        source_root_sha256: str,
        release_manifest: dict[str, Any],
        signer_key_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if not _is_source_commit(source_commit) or not _is_sha256(source_root_sha256):
            raise ValidationError(
                "QA_SOURCE_IDENTITY_INVALID",
                "candidate requires full commit and source-root SHA-256 identities",
            )
        with self.database.session() as session:
            campaign = self._campaign_row(session, campaign_id, tenant_id)
            scenarios = list(
                session.scalars(select(QAScenarioResultRow).where(QAScenarioResultRow.campaign_id == campaign_id))
            )
            gates = list(session.scalars(select(QAGateResultRow).where(QAGateResultRow.campaign_id == campaign_id)))
            waivers = list(
                session.scalars(
                    select(QAReleaseWaiverRow).where(
                        QAReleaseWaiverRow.campaign_id == campaign_id,
                        QAReleaseWaiverRow.state == "active",
                    )
                )
            )
            rollbacks = list(
                session.scalars(
                    select(QARollbackRehearsalRow).where(QARollbackRehearsalRow.campaign_id == campaign_id)
                )
            )
            blockers: list[dict[str, Any]] = []
            external_gaps: list[dict[str, Any]] = []
            by_scenario = {row.scenario_type: row for row in scenarios}
            for required_scenario in sorted(SCENARIOS):
                row = by_scenario.get(required_scenario)
                if row is None or row.status != "passed":
                    blockers.append({"code": "QA_SCENARIO_MISSING_OR_FAILED", "scenario": required_scenario})
            by_gate = {row.gate_type: row for row in gates}
            for required_gate in sorted(GATE_TYPES):
                row = by_gate.get(required_gate)
                if row is None:
                    blockers.append({"code": "QA_GATE_MISSING", "gate": required_gate})
                    continue
                if row.external_gap:
                    external_gaps.append(
                        {"gate": required_gate, "status": row.control_status, "findings": row.findings_json}
                    )
                if row.required and row.control_status in {"blocked", "failed"}:
                    blockers.append(
                        {"code": "QA_GATE_NOT_PASSING", "gate": required_gate, "status": row.control_status}
                    )
            if not any(row.status == "passed" for row in rollbacks):
                blockers.append({"code": "QA_ROLLBACK_NOT_REHEARSED"})
            expired = [row.requirement_id for row in waivers if row.expires_at <= db_now()]
            if expired:
                blockers.append({"code": "QA_WAIVER_EXPIRED", "requirements": expired})
            blockers.extend(_release_artifact_findings(release_manifest))
            manifest_body = {
                "schema": "sip.qa-release-manifest/v1",
                "campaign_id": campaign_id,
                "checkpoint_id": campaign.checkpoint_id,
                "release_class": campaign.release_class,
                "source_commit": source_commit,
                "source_root_sha256": source_root_sha256,
                "scope": campaign.scope_json,
                "operating_envelope": campaign.operating_envelope_json,
                "known_limitations": campaign.limitations_json,
                "support_plan": campaign.support_plan_json,
                "recovery_plan": campaign.recovery_plan_json,
                "scenario_hashes": {
                    row.scenario_type: row.scenario_hash
                    for row in sorted(scenarios, key=lambda item: item.scenario_type)
                },
                "gate_hashes": {
                    row.gate_type: row.gate_hash for row in sorted(gates, key=lambda item: item.gate_type)
                },
                "waiver_hashes": [
                    row.waiver_hash for row in sorted(waivers, key=lambda item: item.requirement_id)
                ],
                "rollback_hashes": [
                    row.rehearsal_hash for row in sorted(rollbacks, key=lambda item: item.rehearsed_at)
                ],
                "release_artifacts": release_manifest,
                "blockers": blockers,
                "external_gaps": external_gaps,
                "production_authorized": False,
                "progress_12_authorized": False,
            }
            digest = canonical_sha256(manifest_body)
            existing = session.scalar(
                select(QAReleaseCandidateRow).where(
                    QAReleaseCandidateRow.campaign_id == campaign_id,
                    QAReleaseCandidateRow.source_commit == source_commit,
                    QAReleaseCandidateRow.source_root_sha256 == source_root_sha256,
                )
            )
            if existing:
                if existing.manifest_hash != digest:
                    raise ConflictError(
                        "QA_CANDIDATE_IMMUTABLE",
                        "source identity already has a different release manifest",
                    )
                return self._candidate(existing, idempotent_replay=True)
            signature = self._private_key.sign(canonical_json(manifest_body))
            public = self._public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            status = "blocked" if blockers else "passed_with_external_gaps" if external_gaps else "passed_complete"
            row = QAReleaseCandidateRow(
                release_candidate_id=new_uuid(),
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                source_commit=source_commit,
                source_root_sha256=source_root_sha256,
                manifest_json=manifest_body,
                manifest_hash=digest,
                signature=base64.b64encode(signature).decode("ascii"),
                public_key=base64.b64encode(public).decode("ascii"),
                signer_key_id=signer_key_id,
                blockers_json=blockers,
                external_gaps_json=external_gaps,
                status=status,
                production_authorized=False,
                created_by=actor_id,
            )
            session.add(row)
            campaign.state = "evaluated"
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=campaign.project_id,
                actor_id=actor_id,
                action="qa:candidate_sign",
                resource_type="qa_release_candidate",
                resource_id=row.release_candidate_id,
                details={
                    "manifest_hash": digest,
                    "status": status,
                    "blocker_count": len(blockers),
                    "external_gap_count": len(external_gaps),
                },
                event_type="qa.candidate.signed",
                payload={
                    "campaign_id": campaign_id,
                    "manifest_hash": digest,
                    "status": status,
                    "production_authorized": False,
                },
            )
            session.flush()
            return self._candidate(row, idempotent_replay=False)

    @staticmethod
    def verify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        manifest = candidate.get("manifest")
        if not isinstance(manifest, dict):
            raise ValidationError("QA_CANDIDATE_MANIFEST_MISSING", "candidate manifest is missing")
        digest = canonical_sha256(manifest)
        if digest != candidate.get("manifest_hash"):
            raise ValidationError("QA_CANDIDATE_HASH_MISMATCH", "candidate manifest hash does not match")
        try:
            public = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(str(candidate["public_key"]), validate=True)
            )
            signature = base64.b64decode(str(candidate["signature"]), validate=True)
            public.verify(signature, canonical_json(manifest))
        except Exception as exc:
            raise ValidationError("QA_CANDIDATE_SIGNATURE_INVALID", "candidate signature verification failed") from exc
        if candidate.get("production_authorized") is not False or manifest.get("production_authorized") is not False:
            raise AuthorizationError(
                "QA_PRODUCTION_AUTHORITY_INVALID",
                "bounded QA candidate cannot authorize production",
            )
        expected_status = (
            "blocked"
            if manifest.get("blockers")
            else "passed_with_external_gaps"
            if manifest.get("external_gaps")
            else "passed_complete"
        )
        if candidate.get("status") != expected_status:
            raise ValidationError("QA_CANDIDATE_STATUS_MISMATCH", "candidate status does not match manifest findings")
        return {
            "valid": True,
            "manifest_hash": digest,
            "status": candidate.get("status"),
            "production_authorized": False,
            "progress_12_authorized": False,
        }

    def candidate(self, *, tenant_id: str, release_candidate_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(QAReleaseCandidateRow, release_candidate_id)
            if row is None or row.tenant_id != tenant_id:
                raise NotFoundError("qa_release_candidate", release_candidate_id)
            result = self._candidate(row, idempotent_replay=False)
            return {**result, "verification": self.verify_candidate(result)}

    def production_admission(
        self,
        *,
        tenant_id: str,
        release_candidate_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(QAReleaseCandidateRow, release_candidate_id)
            if row is None or row.tenant_id != tenant_id:
                raise NotFoundError("qa_release_candidate", release_candidate_id)
            blockers = list(row.blockers_json)
            blockers.extend(
                {"code": "EXTERNAL_GATE_INCOMPLETE", **gap} for gap in row.external_gaps_json
            )
            blockers.append({"code": "TRUE_NORTH_PRODUCTION_AUTHORIZATION_MISSING"})
            if self.environment != "production":
                blockers.append({"code": "NON_PRODUCTION_ENVIRONMENT"})
            decision = {
                "release_candidate_id": release_candidate_id,
                "admitted": False,
                "production_authorized": False,
                "progress_12_authorized": False,
                "blockers": blockers,
                "evaluated_at": db_now().isoformat(),
            }
            self._audit_emit(
                session,
                tenant_id=tenant_id,
                project_id=None,
                actor_id=actor_id,
                action="qa:production_admit",
                resource_type="qa_release_candidate",
                resource_id=release_candidate_id,
                details=decision,
                event_type="qa.production_admission.denied",
                payload={
                    "release_candidate_id": release_candidate_id,
                    "blocker_count": len(blockers),
                    "production_authorized": False,
                },
                outcome="denied",
            )
            return decision

    def campaign_project_scope(self, *, tenant_id: str, campaign_id: str) -> str | None:
        """Return only the campaign project binding for pre-response authorization."""
        with self.database.session() as session:
            row = self._campaign_row(session, campaign_id, tenant_id)
            return row.project_id

    def candidate_project_scope(self, *, tenant_id: str, release_candidate_id: str) -> str | None:
        """Return only the candidate's campaign project binding for pre-response authorization."""
        with self.database.session() as session:
            candidate = session.get(QAReleaseCandidateRow, release_candidate_id)
            if candidate is None or candidate.tenant_id != tenant_id:
                raise NotFoundError("qa_release_candidate", release_candidate_id)
            campaign = self._campaign_row(session, candidate.campaign_id, tenant_id)
            return campaign.project_id

    def campaign(self, *, tenant_id: str, campaign_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._campaign_row(session, campaign_id, tenant_id)
            scenarios = [
                self._scenario(item, idempotent_replay=False)
                for item in session.scalars(
                    select(QAScenarioResultRow).where(QAScenarioResultRow.campaign_id == campaign_id)
                )
            ]
            gates = [
                self._gate(item, idempotent_replay=False)
                for item in session.scalars(
                    select(QAGateResultRow).where(QAGateResultRow.campaign_id == campaign_id)
                )
            ]
            waivers = [
                self._waiver(item, idempotent_replay=False)
                for item in session.scalars(
                    select(QAReleaseWaiverRow).where(QAReleaseWaiverRow.campaign_id == campaign_id)
                )
            ]
            rollbacks = [
                self._rollback(item, idempotent_replay=False)
                for item in session.scalars(
                    select(QARollbackRehearsalRow).where(QARollbackRehearsalRow.campaign_id == campaign_id)
                )
            ]
            candidates = [
                self._candidate(item, idempotent_replay=False)
                for item in session.scalars(
                    select(QAReleaseCandidateRow).where(QAReleaseCandidateRow.campaign_id == campaign_id)
                )
            ]
            return {
                **self._campaign(row, idempotent_replay=False),
                "scenarios": scenarios,
                "gates": gates,
                "waivers": waivers,
                "rollbacks": rollbacks,
                "candidates": candidates,
            }

    @staticmethod
    def _campaign(row: QAAcceptanceCampaignRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "checkpoint_id": row.checkpoint_id,
            "release_class": row.release_class,
            "scope": row.scope_json,
            "test_data": row.test_data_json,
            "operating_envelope": row.operating_envelope_json,
            "limitations": row.limitations_json,
            "support_plan": row.support_plan_json,
            "recovery_plan": row.recovery_plan_json,
            "state": row.state,
            "campaign_hash": row.campaign_hash,
            "created_by": row.created_by,
            "created_at": _dt(row.created_at),
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _scenario(row: QAScenarioResultRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "scenario_result_id": row.scenario_result_id,
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "scenario_type": row.scenario_type,
            "profile": row.profile,
            "evidence_class": row.evidence_class,
            "input_hashes": row.input_hashes_json,
            "output_hashes": row.output_hashes_json,
            "metrics": row.metrics_json,
            "assertions": row.assertions_json,
            "evidence": row.evidence_json,
            "environment": row.environment_json,
            "status": row.status,
            "scenario_hash": row.scenario_hash,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _gate(row: QAGateResultRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "gate_result_id": row.gate_result_id,
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "gate_type": row.gate_type,
            "required": row.required,
            "execution_status": row.execution_status,
            "control_status": row.control_status,
            "thresholds": row.thresholds_json,
            "result": row.result_json,
            "findings": row.findings_json,
            "evidence": row.evidence_json,
            "external_gap": row.external_gap,
            "gate_hash": row.gate_hash,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _waiver(row: QAReleaseWaiverRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "waiver_id": row.waiver_id,
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "requirement_id": row.requirement_id,
            "priority": row.priority,
            "reason": row.reason,
            "compensating_control": row.compensating_control_json,
            "owner": row.owner,
            "expires_at": _dt(row.expires_at),
            "state": row.state,
            "waiver_hash": row.waiver_hash,
            "approved_by": row.approved_by,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _rollback(row: QARollbackRehearsalRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "rehearsal_id": row.rehearsal_id,
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "from_release": row.from_release,
            "to_release": row.to_release,
            "recovery_point_id": row.recovery_point_id,
            "before_hashes": row.before_hashes_json,
            "after_hashes": row.after_hashes_json,
            "steps": row.steps_json,
            "verification": row.verification_json,
            "status": row.status,
            "rehearsal_hash": row.rehearsal_hash,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _candidate(row: QAReleaseCandidateRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "release_candidate_id": row.release_candidate_id,
            "campaign_id": row.campaign_id,
            "tenant_id": row.tenant_id,
            "source_commit": row.source_commit,
            "source_root_sha256": row.source_root_sha256,
            "manifest": row.manifest_json,
            "manifest_hash": row.manifest_hash,
            "signature": row.signature,
            "public_key": row.public_key,
            "signer_key_id": row.signer_key_id,
            "blockers": row.blockers_json,
            "external_gaps": row.external_gaps_json,
            "status": row.status,
            "production_authorized": row.production_authorized,
            "progress_12_authorized": False,
            "created_by": row.created_by,
            "created_at": _dt(row.created_at),
            "idempotent_replay": idempotent_replay,
        }
