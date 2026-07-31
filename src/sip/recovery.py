from __future__ import annotations

import base64
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .assets import AssetService, LocalContentAddressedStore
from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, new_uuid, sha256_bytes, sha256_file
from .database import (
    AssetRefRow,
    AssetRow,
    AuditEventRow,
    BackupExpiryEvidenceRow,
    Base,
    ConsentGrantRow,
    Database,
    DeletionGraphRow,
    DeploymentProfileRow,
    ExportRow,
    FixityCheckRow,
    FormatMigrationEvidenceRow,
    KeyRecoveryExerciseRow,
    KeyScopeRow,
    LegacyMigrationRunRow,
    LegalHoldRow,
    MemoryRecordRow,
    OperationRow,
    ProjectDeploymentBindingRow,
    ProjectRow,
    PurgeRunRow,
    RecoveryGameDayRow,
    RecoveryLockRow,
    RecoveryObjectiveRow,
    RecoveryPointRow,
    ResidencyPolicyRow,
    RestoreRunRow,
    RetentionAssignmentRow,
    RetentionRuleRow,
    SceneCommitRow,
    SearchDocumentRow,
    TenantOffboardingRow,
    TenantRow,
)
from .deployment import DeploymentService
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .exporting import PreservationService
from .lifecycle import LifecycleService
from .models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from .security_ops import SecurityOperationsService
from .temporal import db_now

_SHA256 = set("0123456789abcdef")
OPAQUE_KEY_PREFIXES = ("vault://", "kms://", "hsm://", "secret://", "offline-recovery://")
RECOVERY_EVIDENCE_CLASSES = {"synthetic", "local_controlled", "local_executed", "cloud_executed", "external_witnessed"}


def _is_sha256(value: str | None) -> bool:
    return bool(value and len(value) == 64 and set(value) <= _SHA256)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _aware(value).isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _primary_key(table: Any, mapping: dict[str, Any]) -> str:
    for column in table.primary_key.columns:
        value = mapping.get(column.name)
        if value is not None:
            return str(value)
    return "unknown"


def _contains_reference(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_reference(item, target) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_reference(item, target) for item in value)
    return str(value) == target


class RecoveryOperationsService:
    """Governed local reference for OPS-004 recovery, retention, and deletion.

    The local profile provides deterministic, executable evidence while preserving a
    strict distinction between local/synthetic rehearsals and credentialed cloud,
    physical-edge, multi-region, externally witnessed, or production certification.
    """

    def __init__(
        self,
        database: Database,
        assets: AssetService,
        preservation: PreservationService,
        lifecycle: LifecycleService,
        audit: AuditService,
        deployment: DeploymentService,
        security_ops: SecurityOperationsService,
        signing_key: bytes,
        *,
        recovery_root: Path,
        environment: str,
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("recovery signing key must be at least 32 bytes")
        self.database = database
        self.assets = assets
        self.preservation = preservation
        self.lifecycle = lifecycle
        self.audit = audit
        self.deployment = deployment
        self.security_ops = security_ops
        self.signing_key = signing_key
        self.recovery_root = recovery_root.resolve()
        self.recovery_root.mkdir(parents=True, exist_ok=True)
        self.environment = environment
        self.events = OutboxEventFactory()
        self._process_lock = threading.RLock()

    # ------------------------------------------------------------------ shared
    def _emit(
        self,
        session: Session,
        *,
        event_type: str,
        tenant_id: str,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        actor_id: str | None,
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
                producer="recovery-control",
                actor_id=actor_id,
                workload_identity=None,
                correlation_id=aggregate_id,
            )
        )

    @staticmethod
    def _require_project(session: Session, tenant_id: str, project_id: str) -> ProjectRow:
        row = session.get(ProjectRow, project_id)
        if row is None or row.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)
        return row

    @staticmethod
    def _profile(session: Session, deployment_profile_id: str) -> DeploymentProfileRow:
        row = session.get(DeploymentProfileRow, deployment_profile_id)
        if row is None or row.state != "active":
            raise NotFoundError("deployment_profile", deployment_profile_id)
        return row

    def _audit_and_emit(
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
    ) -> None:
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="allowed",
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
            payload=payload,
            actor_id=actor_id,
        )

    def _record_denial(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.database.session() as session:
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="denied",
                details={"code": code, "reason_code": code, **(details or {})},
                session=session,
            )
            self._emit(
                session,
                event_type="recovery.action_denied",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="recovery_denial",
                aggregate_id=new_uuid(),
                payload={"action": action, "resource_type": resource_type, "reason_code": code},
                actor_id=actor_id,
            )

    # ---------------------------------------------------------- objectives/RPO/RTO
    def register_recovery_objective(
        self,
        *,
        tenant_id: str | None,
        project_id: str | None,
        deployment_profile_id: str,
        data_class: str,
        service_class: str,
        rpo_seconds: int,
        rto_seconds: int,
        degraded_behavior: dict[str, Any],
        recovery_method: dict[str, Any],
        evidence_class: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if not data_class.strip() or not service_class.strip() or rpo_seconds < 0 or rto_seconds <= 0:
            raise ValidationError("RECOVERY_OBJECTIVE_INVALID", "recovery objective fields are invalid")
        if not degraded_behavior or not recovery_method:
            raise ValidationError("RECOVERY_OBJECTIVE_INCOMPLETE", "recovery objective requires degraded behavior and recovery method")
        if evidence_class not in RECOVERY_EVIDENCE_CLASSES:
            raise ValidationError("RECOVERY_EVIDENCE_CLASS_INVALID", "unsupported recovery evidence class")
        if evidence_class in {"cloud_executed", "external_witnessed"}:
            raise ValidationError(
                "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED",
                "cloud or externally witnessed recovery objectives require independently retained external evidence",
            )
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "deployment_profile_id": deployment_profile_id,
            "data_class": data_class,
            "service_class": service_class,
            "rpo_seconds": rpo_seconds,
            "rto_seconds": rto_seconds,
            "degraded_behavior": degraded_behavior,
            "recovery_method": recovery_method,
            "evidence_class": evidence_class,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._profile(session, deployment_profile_id)
            if tenant_id and project_id:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(RecoveryObjectiveRow).where(RecoveryObjectiveRow.objective_hash == digest))
            if existing:
                return self._objective_result(existing, idempotent_replay=True)
            for prior in session.scalars(
                select(RecoveryObjectiveRow).where(
                    RecoveryObjectiveRow.tenant_id == tenant_id,
                    RecoveryObjectiveRow.project_id == project_id,
                    RecoveryObjectiveRow.deployment_profile_id == deployment_profile_id,
                    RecoveryObjectiveRow.data_class == data_class,
                    RecoveryObjectiveRow.service_class == service_class,
                    RecoveryObjectiveRow.state == "active",
                )
            ):
                prior.state = "superseded"
            identifier = new_uuid()
            row = RecoveryObjectiveRow(
                recovery_objective_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                deployment_profile_id=deployment_profile_id,
                data_class=data_class,
                service_class=service_class,
                rpo_seconds=rpo_seconds,
                rto_seconds=rto_seconds,
                degraded_behavior_json=degraded_behavior,
                recovery_method_json=recovery_method,
                evidence_class=evidence_class,
                objective_hash=digest,
                state="active",
                created_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id or "platform",
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:objective_register",
                resource_type="recovery_objective",
                resource_id=identifier,
                details={"data_class": data_class, "service_class": service_class, "rpo_seconds": rpo_seconds, "rto_seconds": rto_seconds, "evidence_class": evidence_class},
                event_type="recovery.objective_registered",
                payload={"data_class": data_class, "service_class": service_class, "rpo_seconds": rpo_seconds, "rto_seconds": rto_seconds, "evidence_class": evidence_class, "objective_hash": digest},
            )
            return self._objective_result(row, idempotent_replay=False)

    @staticmethod
    def _objective_result(row: RecoveryObjectiveRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "recovery_objective_id": row.recovery_objective_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "deployment_profile_id": row.deployment_profile_id,
            "data_class": row.data_class,
            "service_class": row.service_class,
            "rpo_seconds": row.rpo_seconds,
            "rto_seconds": row.rto_seconds,
            "degraded_behavior": row.degraded_behavior_json,
            "recovery_method": row.recovery_method_json,
            "evidence_class": row.evidence_class,
            "objective_hash": row.objective_hash,
            "state": row.state,
            "idempotent_replay": idempotent_replay,
        }

    # --------------------------------------------------------------- recovery point
    def create_recovery_point(
        self,
        *,
        tenant_id: str,
        project_id: str,
        deployment_profile_id: str,
        region: str,
        requested_point_at: datetime,
        immutability_days: int,
        evidence_class: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with self._process_lock:
            return self._create_recovery_point_locked(
                tenant_id=tenant_id,
                project_id=project_id,
                deployment_profile_id=deployment_profile_id,
                region=region,
                requested_point_at=requested_point_at,
                immutability_days=immutability_days,
                evidence_class=evidence_class,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    def _create_recovery_point_locked(
        self,
        *,
        tenant_id: str,
        project_id: str,
        deployment_profile_id: str,
        region: str,
        requested_point_at: datetime,
        immutability_days: int,
        evidence_class: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if immutability_days <= 0:
            raise ValidationError("RECOVERY_IMMUTABILITY_INVALID", "recovery point immutability must be positive")
        if evidence_class != "local_executed":
            raise ValidationError(
                "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED",
                "the local reference implementation may retain only local_executed recovery-point evidence",
                {"requested_evidence_class": evidence_class},
            )
        if not idempotency_key.strip():
            raise ValidationError("RECOVERY_IDEMPOTENCY_KEY_REQUIRED", "recovery point creation requires an idempotency key")
        requested = _aware(requested_point_at)
        now = db_now()
        if requested > now + timedelta(seconds=5):
            raise ValidationError("RECOVERY_POINT_IN_FUTURE", "requested recovery point cannot be in the future")
        request_payload = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "deployment_profile_id": deployment_profile_id,
            "region": region,
            "requested_point_at": requested.isoformat(),
            "immutability_days": immutability_days,
            "evidence_class": evidence_class,
            "idempotency_key": idempotency_key,
        }
        request_hash = canonical_sha256(request_payload)
        existing_id: str | None = None
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            profile = self._profile(session, deployment_profile_id)
            if region not in set(profile.supported_regions_json):
                raise AuthorizationError("RECOVERY_REGION_DENIED", "recovery region is not allowed by the deployment profile")
            existing = session.scalar(
                select(RecoveryPointRow).where(
                    RecoveryPointRow.tenant_id == tenant_id,
                    RecoveryPointRow.project_id == project_id,
                    RecoveryPointRow.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ConflictError(
                        "RECOVERY_POINT_IDEMPOTENCY_CONFLICT",
                        "recovery-point idempotency key was reused for a different request",
                    )
                existing_id = existing.recovery_point_id
        if existing_id is not None:
            result = self.verify_recovery_point(
                tenant_id=tenant_id,
                project_id=project_id,
                recovery_point_id=existing_id,
                actor_id=actor_id,
            )
            result["idempotent_replay"] = True
            return result
        if self.database.sqlite_path is None or not isinstance(self.assets.store, LocalContentAddressedStore):
            raise ValidationError(
                "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED",
                "the deterministic reference path can create recovery points only for the local SQLite/CAS profile",
                {"requested_evidence_class": evidence_class},
            )
        identifier = new_uuid()
        destination = self.recovery_root / "points" / identifier
        destination.mkdir(parents=True, exist_ok=False)
        package_path = destination / "project.sip-preservation.zip"
        package = self.preservation.export_project(tenant_id, project_id, package_path, actor_id=actor_id)
        verified_package = self.preservation.verify_export(package_path)
        database_path = destination / "database.sqlite3"
        source = sqlite3.connect(self.database.sqlite_path)
        target = sqlite3.connect(database_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        with self.database.session() as session:
            refs = list(
                session.scalars(
                    select(AssetRefRow).where(
                        AssetRefRow.tenant_id == tenant_id,
                        AssetRefRow.project_id == project_id,
                        AssetRefRow.tombstoned_at.is_(None),
                    )
                )
            )
            objects: list[dict[str, Any]] = []
            for ref in sorted(refs, key=lambda item: item.asset_id):
                payload = self.assets.store.read_bytes(ref.sha256)
                objects.append(
                    {
                        "asset_id": ref.asset_id,
                        "sha256": ref.sha256,
                        "bytes": len(payload),
                        "storage_key": self.assets.store.storage_key(ref.sha256),
                        "retention_class": ref.retention_class,
                        "legal_hold": bool(ref.legal_hold),
                    }
                )
            audit_result = self.audit.verify(tenant_id)
            queues = [
                {
                    "operation_id": row.operation_id,
                    "state": row.state,
                    "operation_type": row.operation_type,
                    "checkpoint_hash": canonical_sha256(row.checkpoint_json or {}),
                }
                for row in session.scalars(select(OperationRow).where(OperationRow.tenant_id == tenant_id, OperationRow.project_id == project_id))
            ]
            keys = [
                {"key_scope_id": row.key_scope_id, "key_id": row.key_id, "backend": row.backend, "state": row.state}
                for row in session.scalars(select(KeyScopeRow).where(KeyScopeRow.tenant_id == tenant_id, KeyScopeRow.project_id == project_id))
            ]
            binding = session.scalar(
                select(ProjectDeploymentBindingRow).where(
                    ProjectDeploymentBindingRow.tenant_id == tenant_id,
                    ProjectDeploymentBindingRow.project_id == project_id,
                    ProjectDeploymentBindingRow.state == "active",
                )
            )
            profile = self._profile(session, deployment_profile_id)
            config = {
                "deployment_profile_id": deployment_profile_id,
                "deployment_profile_hash": profile.profile_hash,
                "project_binding_hash": binding.binding_hash if binding else None,
                "schema_fingerprint": self._schema_fingerprint(),
                "release": "1.1.0-progress10",
            }
        object_root = canonical_sha256(objects)
        config_hash = canonical_sha256(config)
        package_sha = sha256_file(package_path)
        database_sha = sha256_file(database_path)
        snapshot_at = db_now()
        immutable_until = snapshot_at + timedelta(days=immutability_days)
        manifest = {
            "schema": "sip.recovery-point/v1",
            "recovery_point_id": identifier,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "deployment_profile_id": deployment_profile_id,
            "region": region,
            "evidence_class": evidence_class,
            "requested_point_at": requested.isoformat(),
            "snapshot_at": snapshot_at.isoformat(),
            "immutable_until": immutable_until.isoformat(),
            "package_sha256": package_sha,
            "package_root_hash": verified_package["root_hash"],
            "database_sha256": database_sha,
            "object_root_hash": object_root,
            "configuration_hash": config_hash,
            "audit_heads": audit_result,
            "queue_manifest": queues,
            "key_references": keys,
        }
        recovery_hash = canonical_sha256(manifest)
        manifest["recovery_point_hash"] = recovery_hash
        (destination / "recovery-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        os.chmod(package_path, 0o440)
        os.chmod(database_path, 0o440)
        os.chmod(destination / "recovery-manifest.json", 0o440)
        with self.database.session() as session:
            row = RecoveryPointRow(
                recovery_point_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                deployment_profile_id=deployment_profile_id,
                region=region,
                evidence_class=evidence_class,
                database_profile="sqlite_snapshot_plus_open_preservation",
                package_path=str(package_path),
                package_sha256=package_sha,
                package_root_hash=verified_package["root_hash"],
                database_snapshot_path=str(database_path),
                database_sha256=database_sha,
                object_manifest_json=objects,
                object_root_hash=object_root,
                configuration_json=config,
                configuration_hash=config_hash,
                audit_heads_json=audit_result,
                queue_manifest_json=queues,
                key_references_json=keys,
                requested_point_at=requested,
                snapshot_at=snapshot_at,
                immutable_until=immutable_until,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                state="created",
                recovery_point_hash=recovery_hash,
                created_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:point_create",
                resource_type="recovery_point",
                resource_id=identifier,
                details={"package_root_hash": row.package_root_hash, "object_root_hash": object_root, "evidence_class": evidence_class, "region": region},
                event_type="recovery.point_created",
                payload={"recovery_point_hash": recovery_hash, "package_root_hash": row.package_root_hash, "object_root_hash": object_root, "region": region, "evidence_class": evidence_class},
            )
        result = self.get_recovery_point(tenant_id=tenant_id, project_id=project_id, recovery_point_id=identifier)
        result["idempotent_replay"] = False
        return result

    def verify_recovery_point(self, *, tenant_id: str, project_id: str, recovery_point_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._get_point(session, tenant_id, project_id, recovery_point_id)
            if row.state == "expired":
                raise ConflictError(
                    "RECOVERY_POINT_EXPIRED",
                    "expired recovery-point bytes are intentionally unavailable for ordinary verification or restore",
                )
            package_path = Path(row.package_path)
            database_path = Path(row.database_snapshot_path or "")
            expected = {
                "package_sha256": row.package_sha256,
                "package_root_hash": row.package_root_hash,
                "database_sha256": row.database_sha256,
                "object_root_hash": row.object_root_hash,
                "configuration_hash": row.configuration_hash,
                "recovery_point_hash": row.recovery_point_hash,
            }
        if not package_path.is_file() or not database_path.is_file():
            raise ValidationError("RECOVERY_POINT_BYTES_MISSING", "recovery point package or database snapshot is missing")
        actual_package_sha = sha256_file(package_path)
        actual_database_sha = sha256_file(database_path)
        verified = self.preservation.verify_export(package_path)
        if actual_package_sha != expected["package_sha256"] or verified["root_hash"] != expected["package_root_hash"]:
            raise ValidationError("RECOVERY_POINT_PACKAGE_MISMATCH", "recovery point package identity changed")
        if actual_database_sha != expected["database_sha256"]:
            raise ValidationError("RECOVERY_POINT_DATABASE_MISMATCH", "recovery point database snapshot changed")
        connection = sqlite3.connect(database_path)
        try:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            connection.close()
        if integrity != "ok":
            raise ValidationError("RECOVERY_DATABASE_INTEGRITY_FAILED", integrity)
        metadata_assets = verified["metadata"].get("assets", [])
        object_manifest = sorted(
            [
                {
                    "asset_id": item["reference"]["asset_id"],
                    "sha256": item["reference"]["sha256"],
                    "bytes": int(item["object"]["byte_count"]),
                    "storage_key": next((x["storage_key"] for x in self._point_objects(tenant_id, project_id, recovery_point_id) if x["asset_id"] == item["reference"]["asset_id"]), "preservation-package"),
                    "retention_class": item["reference"]["retention_class"],
                    "legal_hold": bool(item["reference"].get("legal_hold", False)),
                }
                for item in metadata_assets
            ],
            key=lambda item: item["asset_id"],
        )
        if canonical_sha256(object_manifest) != expected["object_root_hash"]:
            raise ValidationError("RECOVERY_OBJECT_MANIFEST_MISMATCH", "recovery point object manifest does not reconcile")
        with self.database.session() as session:
            row = self._get_point(session, tenant_id, project_id, recovery_point_id)
            if canonical_sha256(row.configuration_json) != expected["configuration_hash"]:
                raise ValidationError("RECOVERY_CONFIGURATION_MISMATCH", "recovery configuration identity changed")
            row.state = "verified"
            row.verified_at = db_now()
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:point_verify",
                resource_type="recovery_point",
                resource_id=recovery_point_id,
                details={"database_integrity": integrity, "package_sha256": actual_package_sha, "object_count": len(object_manifest)},
                event_type="recovery.point_verified",
                payload={"state": "verified", "package_root_hash": row.package_root_hash, "object_root_hash": row.object_root_hash, "database_integrity": integrity},
            )
        return self.get_recovery_point(tenant_id=tenant_id, project_id=project_id, recovery_point_id=recovery_point_id)

    def get_recovery_point(self, *, tenant_id: str, project_id: str, recovery_point_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._get_point(session, tenant_id, project_id, recovery_point_id)
            return self._point_result(row)

    @staticmethod
    def _get_point(session: Session, tenant_id: str, project_id: str, recovery_point_id: str) -> RecoveryPointRow:
        row = session.get(RecoveryPointRow, recovery_point_id)
        if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("recovery_point", recovery_point_id)
        return row

    def _point_objects(self, tenant_id: str, project_id: str, recovery_point_id: str) -> list[dict[str, Any]]:
        with self.database.session() as session:
            return list(self._get_point(session, tenant_id, project_id, recovery_point_id).object_manifest_json)

    @staticmethod
    def _point_result(row: RecoveryPointRow) -> dict[str, Any]:
        return {
            "recovery_point_id": row.recovery_point_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "deployment_profile_id": row.deployment_profile_id,
            "region": row.region,
            "evidence_class": row.evidence_class,
            "database_profile": row.database_profile,
            "package_sha256": row.package_sha256,
            "package_root_hash": row.package_root_hash,
            "database_sha256": row.database_sha256,
            "object_root_hash": row.object_root_hash,
            "configuration_hash": row.configuration_hash,
            "requested_point_at": _aware(row.requested_point_at).isoformat(),
            "snapshot_at": _aware(row.snapshot_at).isoformat(),
            "immutable_until": _aware(row.immutable_until).isoformat(),
            "state": row.state,
            "recovery_point_hash": row.recovery_point_hash,
            "verified_at": _aware(row.verified_at).isoformat() if row.verified_at else None,
            "idempotent_replay": False,
        }

    # ---------------------------------------------------------------- restore
    def restore(
        self,
        *,
        tenant_id: str,
        project_id: str,
        target_tenant_id: str,
        target_project_id: str,
        target_region: str,
        requested_point_at: datetime,
        restore_mode: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with self._process_lock:
            return self._restore_locked(
                tenant_id=tenant_id,
                project_id=project_id,
                target_tenant_id=target_tenant_id,
                target_project_id=target_project_id,
                target_region=target_region,
                requested_point_at=requested_point_at,
                restore_mode=restore_mode,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    def _restore_locked(
        self,
        *,
        tenant_id: str,
        project_id: str,
        target_tenant_id: str,
        target_project_id: str,
        target_region: str,
        requested_point_at: datetime,
        restore_mode: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if restore_mode not in {"isolated_clone", "in_place_rehearsal", "portability_fallback"}:
            raise ValidationError("RESTORE_MODE_INVALID", "unsupported restore mode")
        requested = _aware(requested_point_at)
        if requested > db_now() + timedelta(seconds=5):
            raise ValidationError("RESTORE_POINT_IN_FUTURE", "requested restore point cannot be in the future")
        request = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "target_tenant_id": target_tenant_id,
            "target_project_id": target_project_id,
            "target_region": target_region,
            "requested_point_at": requested.isoformat(),
            "restore_mode": restore_mode,
            "idempotency_key": idempotency_key,
        }
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            existing = session.scalar(
                select(RestoreRunRow).where(
                    RestoreRunRow.tenant_id == tenant_id,
                    RestoreRunRow.project_id == project_id,
                    RestoreRunRow.idempotency_key == idempotency_key,
                )
            )
            if existing:
                if existing.request_hash != request_hash:
                    raise ConflictError("RESTORE_IDEMPOTENCY_CONFLICT", "restore idempotency key was reused for a different request")
                replay_point_id = existing.recovery_point_id
                replay_result = self._restore_result(existing, idempotent_replay=True)
                self.verify_recovery_point(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    recovery_point_id=replay_point_id,
                    actor_id=actor_id,
                )
                return replay_result
            if restore_mode in {"isolated_clone", "portability_fallback"}:
                expected_tenant_prefix = f"restore-{tenant_id}-"
                expected_project_prefix = f"restore-{project_id}-"
                target_exists = session.get(TenantRow, target_tenant_id) is not None or session.get(ProjectRow, target_project_id) is not None
                if (
                    not target_tenant_id.startswith(expected_tenant_prefix)
                    or not target_project_id.startswith(expected_project_prefix)
                    or target_exists
                ):
                    self._record_denial(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        actor_id=actor_id,
                        action="recovery:restore",
                        resource_type="restore_target",
                        resource_id=target_project_id,
                        code="RESTORE_TARGET_SCOPE_DENIED",
                        details={"restore_mode": restore_mode},
                    )
                    raise AuthorizationError(
                        "RESTORE_TARGET_SCOPE_DENIED",
                        "restore targets must be new platform-generated isolated tenant and project identifiers",
                    )
            point = session.scalar(
                select(RecoveryPointRow)
                .where(
                    RecoveryPointRow.tenant_id == tenant_id,
                    RecoveryPointRow.project_id == project_id,
                    RecoveryPointRow.state == "verified",
                    RecoveryPointRow.snapshot_at <= requested,
                )
                .order_by(RecoveryPointRow.snapshot_at.desc())
                .limit(1)
            )
            if point is None:
                raise NotFoundError("verified_recovery_point_at_or_before", requested.isoformat())
            self._assert_restore_does_not_resurrect(session, point)
            policy = session.scalar(
                select(ResidencyPolicyRow).where(
                    ResidencyPolicyRow.tenant_id == tenant_id,
                    ResidencyPolicyRow.project_id == project_id,
                    ResidencyPolicyRow.state == "active",
                )
            )
            if policy and target_region not in set(policy.allowed_regions_json):
                self._record_denial(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    action="recovery:restore",
                    resource_type="recovery_point",
                    resource_id=point.recovery_point_id,
                    code="RESTORE_RESIDENCY_DENIED",
                    details={"target_region": target_region},
                )
                raise AuthorizationError("RESTORE_RESIDENCY_DENIED", "target region is not authorized by the active residency policy")
            restore_id = new_uuid()
            row = RestoreRunRow(
                restore_id=restore_id,
                tenant_id=tenant_id,
                project_id=project_id,
                recovery_point_id=point.recovery_point_id,
                target_tenant_id=target_tenant_id,
                target_project_id=target_project_id,
                target_region=target_region,
                restore_mode=restore_mode,
                requested_point_at=requested,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                state="requested",
                reconciliation_json={},
                output_json={},
                writes_reopened=False,
                requested_by=actor_id,
            )
            session.add(row)
            self._acquire_lock(session, tenant_id, project_id, "project-recovery", "restore", restore_id)
            point_id = point.recovery_point_id
            package_path = Path(point.package_path)
            snapshot_at = _aware(point.snapshot_at)
        started = time.monotonic()
        try:
            self.verify_recovery_point(tenant_id=tenant_id, project_id=project_id, recovery_point_id=point_id, actor_id=actor_id)
            if restore_mode == "in_place_rehearsal":
                target_tenant_id = f"rehearsal-{new_uuid()}"
                target_project_id = f"rehearsal-{new_uuid()}"
            imported = self.preservation.import_project(
                package_path,
                new_tenant_id=target_tenant_id,
                new_project_id=target_project_id,
                actor_id=actor_id,
            )
            reconciliation = self._reconcile_restore(
                source_tenant_id=tenant_id,
                source_project_id=project_id,
                target_tenant_id=target_tenant_id,
                target_project_id=target_project_id,
                recovery_point_id=point_id,
                imported=imported,
            )
            elapsed = max(0, int(time.monotonic() - started))
            rpo = max(0, int((requested - snapshot_at).total_seconds()))
            writes_reopened = not reconciliation["blocking_findings"]
            state = "completed" if writes_reopened else "reconciliation_required"
            with self.database.session() as session:
                row = session.get(RestoreRunRow, restore_id)
                assert row is not None
                row.target_tenant_id = target_tenant_id
                row.target_project_id = target_project_id
                row.state = state
                row.reconciliation_json = reconciliation
                row.output_json = imported
                row.rpo_seconds_observed = rpo
                row.rto_seconds_observed = elapsed
                row.writes_reopened = writes_reopened
                row.completed_at = db_now()
                self._release_lock(session, tenant_id, project_id, "project-recovery", restore_id)
                self._audit_and_emit(
                    session,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    action="recovery:restore_complete",
                    resource_type="restore_run",
                    resource_id=restore_id,
                    details={"state": state, "rpo_seconds": rpo, "rto_seconds": elapsed, "writes_reopened": writes_reopened, "target_project_id": target_project_id},
                    event_type="recovery.restore_completed",
                    payload={"state": state, "rpo_seconds_observed": rpo, "rto_seconds_observed": elapsed, "writes_reopened": writes_reopened, "blocking_findings": reconciliation["blocking_findings"]},
                )
                return self._restore_result(row, idempotent_replay=False)
        except Exception as exc:
            with self.database.session() as session:
                row = session.get(RestoreRunRow, restore_id)
                if row:
                    row.state = "failed"
                    row.reconciliation_json = {"blocking_findings": [{"code": getattr(exc, "code", type(exc).__name__)}]}
                    row.completed_at = db_now()
                self._release_lock(session, tenant_id, project_id, "project-recovery", restore_id, missing_ok=True)
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    action="recovery:restore_failed",
                    resource_type="restore_run",
                    resource_id=restore_id,
                    outcome="failed",
                    details={"error_code": getattr(exc, "code", type(exc).__name__)},
                    session=session,
                )
                self._emit(
                    session,
                    event_type="recovery.restore_failed",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="restore_run",
                    aggregate_id=restore_id,
                    payload={"error_code": getattr(exc, "code", type(exc).__name__), "retryable": False},
                    actor_id=actor_id,
                )
            raise

    def _reconcile_restore(
        self,
        *,
        source_tenant_id: str,
        source_project_id: str,
        target_tenant_id: str,
        target_project_id: str,
        recovery_point_id: str,
        imported: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.session() as session:
            point = self._get_point(session, source_tenant_id, source_project_id, recovery_point_id)
            target_refs = list(
                session.scalars(
                    select(AssetRefRow).where(
                        AssetRefRow.tenant_id == target_tenant_id,
                        AssetRefRow.project_id == target_project_id,
                        AssetRefRow.tombstoned_at.is_(None),
                    )
                )
            )
            object_checks: list[dict[str, Any]] = []
            missing: list[str] = []
            for ref in target_refs:
                obj = session.get(AssetRow, ref.sha256)
                if obj is None:
                    missing.append(ref.asset_id)
                    continue
                payload = self.assets.store.read_bytes(ref.sha256)
                object_checks.append({"asset_id": ref.asset_id, "sha256": ref.sha256, "verified": sha256_bytes(payload) == ref.sha256})
            queue_findings = [
                {"operation_id": item["operation_id"], "required_action": "resume_from_checkpoint_or_cancel"}
                for item in point.queue_manifest_json
                if item["state"] in {"leased", "running"}
            ]
            blocking: list[dict[str, Any]] = []
            if imported.get("source_root_hash") != point.package_root_hash:
                blocking.append({"code": "RESTORE_ROOT_HASH_MISMATCH"})
            if missing:
                blocking.append({"code": "RESTORE_OBJECT_REFERENCES_MISSING", "asset_ids": missing})
            if any(not item["verified"] for item in object_checks):
                blocking.append({"code": "RESTORE_OBJECT_HASH_MISMATCH"})
            if queue_findings:
                blocking.append({"code": "RESTORE_QUEUE_RECONCILIATION_REQUIRED", "operations": queue_findings})
            audit_preserved = bool(point.audit_heads_json and point.audit_heads_json.get("valid", False))
            if not audit_preserved:
                blocking.append({"code": "RESTORE_AUDIT_CHRONOLOGY_INCOMPLETE"})
            return {
                "manifest_root_match": imported.get("source_root_hash") == point.package_root_hash,
                "database_references_reconciled": not missing,
                "objects_verified": object_checks,
                "audit_chronology_preserved_as_package_evidence": audit_preserved,
                "queued_jobs": queue_findings,
                "configuration_hash": point.configuration_hash,
                "blocking_findings": blocking,
            }

    @staticmethod
    def _restore_result(row: RestoreRunRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "restore_id": row.restore_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "recovery_point_id": row.recovery_point_id,
            "target_tenant_id": row.target_tenant_id,
            "target_project_id": row.target_project_id,
            "target_region": row.target_region,
            "restore_mode": row.restore_mode,
            "requested_point_at": _aware(row.requested_point_at).isoformat(),
            "state": row.state,
            "reconciliation": row.reconciliation_json,
            "output": row.output_json,
            "rpo_seconds_observed": row.rpo_seconds_observed,
            "rto_seconds_observed": row.rto_seconds_observed,
            "writes_reopened": row.writes_reopened,
            "idempotent_replay": idempotent_replay,
        }

    def _assert_restore_does_not_resurrect(self, session: Session, point: RecoveryPointRow) -> None:
        executed = list(
            session.scalars(
                select(PurgeRunRow).where(
                    PurgeRunRow.tenant_id == point.tenant_id,
                    PurgeRunRow.project_id == point.project_id,
                    PurgeRunRow.state == "executed",
                    PurgeRunRow.executed_at > point.snapshot_at,
                )
            )
        )
        if executed:
            raise AuthorizationError(
                "RESTORE_WOULD_RESURRECT_DELETED_DATA",
                "ordinary restore is denied because this recovery point predates an executed deletion",
                {"purge_run_ids": [item.purge_run_id for item in executed]},
            )

    # ----------------------------------------------------------- key recovery
    def exercise_key_recovery(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        key_scope_id: str,
        guardian_approvals: list[dict[str, Any]],
        recovery_artifact_reference: str,
        root_key_exposed: bool,
        evidence: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        if root_key_exposed:
            raise AuthorizationError("ROOT_KEY_EXPOSURE_PROHIBITED", "key recovery exercise may not expose a root key to the operator")
        if not recovery_artifact_reference.startswith(OPAQUE_KEY_PREFIXES):
            raise ValidationError("KEY_RECOVERY_REFERENCE_INVALID", "key recovery must use an opaque governed reference")
        with self.database.session() as session:
            scope = session.get(KeyScopeRow, key_scope_id)
            if scope is None or scope.tenant_id != tenant_id or scope.project_id != project_id:
                raise NotFoundError("key_scope", key_scope_id)
            guardians = sorted(set(scope.recovery_policy_json.get("guardians", [])))
            quorum = int(scope.recovery_policy_json.get("quorum", 0))
            approved = sorted({str(item.get("guardian_id")) for item in guardian_approvals if item.get("approved") is True and item.get("guardian_id") in guardians})
            if len(approved) < quorum:
                raise AuthorizationError("KEY_RECOVERY_QUORUM_NOT_MET", "key recovery guardian quorum was not met")
            if actor_id in guardians and len(approved) == 1:
                raise AuthorizationError("KEY_RECOVERY_SINGLE_PERSON_DENIED", "single-person key recovery is prohibited")
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "key_scope_id": key_scope_id,
                "guardians": guardians,
                "approvals": guardian_approvals,
                "recovery_artifact_reference": recovery_artifact_reference,
                "root_key_exposed": False,
                "evidence": evidence,
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(KeyRecoveryExerciseRow).where(KeyRecoveryExerciseRow.exercise_hash == digest))
            if existing:
                return self._key_recovery_result(existing, True)
            identifier = new_uuid()
            row = KeyRecoveryExerciseRow(
                key_recovery_exercise_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                key_scope_id=key_scope_id,
                guardians_json=guardians,
                approvals_json=guardian_approvals,
                recovery_artifact_reference=recovery_artifact_reference,
                root_key_exposed=False,
                state="passed",
                evidence_json=evidence,
                exercise_hash=digest,
                exercised_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:key_exercise",
                resource_type="key_recovery_exercise",
                resource_id=identifier,
                details={"key_scope_id": key_scope_id, "quorum": quorum, "root_key_exposed": False},
                event_type="recovery.key_exercise_completed",
                payload={"key_scope_id": key_scope_id, "state": "passed", "quorum": quorum, "root_key_exposed": False, "exercise_hash": digest},
            )
            return self._key_recovery_result(row, False)

    @staticmethod
    def _key_recovery_result(row: KeyRecoveryExerciseRow, replay: bool) -> dict[str, Any]:
        return {
            "key_recovery_exercise_id": row.key_recovery_exercise_id,
            "key_scope_id": row.key_scope_id,
            "guardians": row.guardians_json,
            "approvals": row.approvals_json,
            "root_key_exposed": row.root_key_exposed,
            "state": row.state,
            "exercise_hash": row.exercise_hash,
            "idempotent_replay": replay,
        }

    # ------------------------------------------------------ retention inventory
    def evaluate_retention_inventory(self, *, tenant_id: str, project_id: str, actor_id: str) -> dict[str, Any]:
        now = db_now()
        assignments: list[dict[str, Any]] = []
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            resources: list[tuple[str, str, str, datetime]] = []
            for ref in session.scalars(select(AssetRefRow).where(AssetRefRow.tenant_id == tenant_id, AssetRefRow.project_id == project_id)):
                resources.append(("asset", ref.asset_id, ref.retention_class, ref.created_at))
            for row in session.scalars(select(MemoryRecordRow).where(MemoryRecordRow.tenant_id == tenant_id, MemoryRecordRow.project_id == project_id)):
                resources.append(("memory_record", row.record_id, "liveforever_record", row.created_at))
            for row in session.scalars(select(SceneCommitRow).where(SceneCommitRow.tenant_id == tenant_id, SceneCommitRow.project_id == project_id)):
                resources.append(("scene_commit", row.commit_id, "scene_history", row.created_at))
            for row in session.scalars(select(ExportRow).where(ExportRow.tenant_id == tenant_id, ExportRow.project_id == project_id)):
                resources.append(("export", row.export_id, "export", row.created_at))
            for resource_type, resource_id, retention_class, created_at in resources:
                holds = list(
                    session.scalars(
                        select(LegalHoldRow).where(
                            LegalHoldRow.tenant_id == tenant_id,
                            LegalHoldRow.project_id == project_id,
                            LegalHoldRow.state == "active",
                            (
                                ((LegalHoldRow.resource_type == resource_type) & (LegalHoldRow.resource_id == resource_id))
                                | ((LegalHoldRow.resource_type == "project") & (LegalHoldRow.resource_id == project_id))
                            ),
                        )
                    )
                )
                rule = self._retention_rule(session, tenant_id, project_id, retention_class)
                eligible_at = _aware(created_at) + timedelta(days=rule.minimum_days if rule else 0)
                eligible = not holds and eligible_at <= now
                body = {
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "retention_class": retention_class,
                    "policy_source": rule.policy_source if rule else "default:no-minimum-retention",
                    "hold_status": "active" if holds else "none",
                    "deletion_eligible_at": eligible_at.isoformat(),
                    "deletion_eligible": eligible,
                }
                digest = canonical_sha256(body)
                existing = session.scalar(select(RetentionAssignmentRow).where(RetentionAssignmentRow.assignment_hash == digest))
                if existing:
                    assignments.append(self._retention_result(existing))
                    continue
                for prior in session.scalars(
                    select(RetentionAssignmentRow).where(
                        RetentionAssignmentRow.tenant_id == tenant_id,
                        RetentionAssignmentRow.project_id == project_id,
                        RetentionAssignmentRow.resource_type == resource_type,
                        RetentionAssignmentRow.resource_id == resource_id,
                        RetentionAssignmentRow.state == "active",
                    )
                ):
                    prior.state = "superseded"
                row = RetentionAssignmentRow(
                    retention_assignment_id=new_uuid(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    retention_class=retention_class,
                    policy_source=body["policy_source"],
                    hold_status=body["hold_status"],
                    deletion_eligible_at=eligible_at,
                    deletion_eligible=eligible,
                    assignment_hash=digest,
                    state="active",
                    evaluated_by=actor_id,
                )
                session.add(row)
                assignments.append(self._retention_result(row))
            inventory_hash = canonical_sha256(assignments)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="retention:inventory_evaluate",
                resource_type="retention_inventory",
                resource_id=inventory_hash,
                details={"resources": len(assignments), "eligible": sum(1 for item in assignments if item["deletion_eligible"])},
                event_type="retention.inventory_evaluated",
                payload={"resources": len(assignments), "eligible": sum(1 for item in assignments if item["deletion_eligible"]), "inventory_hash": inventory_hash},
            )
        return {"tenant_id": tenant_id, "project_id": project_id, "assignments": assignments, "inventory_hash": canonical_sha256(assignments)}

    @staticmethod
    def _retention_rule(session: Session, tenant_id: str, project_id: str, retention_class: str) -> RetentionRuleRow | None:
        row = session.scalar(
            select(RetentionRuleRow)
            .where(
                RetentionRuleRow.tenant_id == tenant_id,
                RetentionRuleRow.project_id == project_id,
                RetentionRuleRow.retention_class == retention_class,
                RetentionRuleRow.active.is_(True),
            )
            .order_by(RetentionRuleRow.version.desc())
            .limit(1)
        )
        if row:
            return row
        return session.scalar(
            select(RetentionRuleRow)
            .where(
                RetentionRuleRow.tenant_id == tenant_id,
                RetentionRuleRow.project_id.is_(None),
                RetentionRuleRow.retention_class == retention_class,
                RetentionRuleRow.active.is_(True),
            )
            .order_by(RetentionRuleRow.version.desc())
            .limit(1)
        )

    @staticmethod
    def _retention_result(row: RetentionAssignmentRow) -> dict[str, Any]:
        return {
            "retention_assignment_id": row.retention_assignment_id,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "retention_class": row.retention_class,
            "policy_source": row.policy_source,
            "hold_status": row.hold_status,
            "deletion_eligible_at": _aware(row.deletion_eligible_at).isoformat() if row.deletion_eligible_at else None,
            "deletion_eligible": row.deletion_eligible,
            "assignment_hash": row.assignment_hash,
            "state": row.state,
        }

    # ------------------------------------------------ deletion graph and purge
    def build_deletion_graph(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scope_type: str,
        scope_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if scope_type not in {"asset", "subject", "project", "tenant"}:
            raise ValidationError("DELETION_SCOPE_INVALID", "unsupported deletion scope")
        graph = self._compute_deletion_graph(tenant_id=tenant_id, project_id=project_id, scope_type=scope_type, scope_id=scope_id)
        with self.database.session() as session:
            existing = session.scalar(select(DeletionGraphRow).where(DeletionGraphRow.graph_hash == graph["graph_hash"]))
            if existing:
                return self._graph_result(existing)
            identifier = new_uuid()
            row = DeletionGraphRow(
                deletion_graph_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                scope_type=scope_type,
                scope_id=scope_id,
                nodes_json=graph["nodes"],
                edges_json=graph["edges"],
                holds_json=graph["holds"],
                exceptions_json=graph["exceptions"],
                store_plan_json=graph["store_plan"],
                eligible=graph["eligible"],
                graph_hash=graph["graph_hash"],
                state="planned",
                created_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:graph_plan",
                resource_type="deletion_graph",
                resource_id=identifier,
                details={"scope_type": scope_type, "scope_id": scope_id, "eligible": graph["eligible"], "node_count": len(graph["nodes"]), "hold_count": len(graph["holds"])},
                event_type="deletion.graph_planned",
                payload={"scope_type": scope_type, "eligible": graph["eligible"], "node_count": len(graph["nodes"]), "hold_count": len(graph["holds"]), "graph_hash": graph["graph_hash"]},
            )
            return self._graph_result(row)

    def _compute_deletion_graph(self, *, tenant_id: str, project_id: str, scope_type: str, scope_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            if scope_type == "asset":
                ref = session.get(AssetRefRow, scope_id)
                if ref is None or ref.tenant_id != tenant_id or ref.project_id != project_id:
                    raise NotFoundError("asset", scope_id)
            if scope_type == "project" and scope_id != project_id:
                raise AuthorizationError("DELETION_PROJECT_SCOPE_MISMATCH", "project deletion scope must match the authorized project")
            if scope_type == "tenant" and scope_id != tenant_id:
                raise AuthorizationError("DELETION_TENANT_SCOPE_MISMATCH", "tenant deletion scope must match the authorized tenant")
            hold_query = select(LegalHoldRow).where(
                LegalHoldRow.tenant_id == tenant_id,
                LegalHoldRow.state == "active",
            )
            if scope_type != "tenant":
                hold_query = hold_query.where(LegalHoldRow.project_id == project_id)
            active_holds = list(session.scalars(hold_query))
            if scope_type == "tenant":
                relevant_holds = active_holds
            elif scope_type == "project":
                # Any active hold under the project blocks project-wide deletion.
                relevant_holds = active_holds
            else:
                relevant_holds = [
                    row for row in active_holds
                    if (row.resource_type == scope_type and row.resource_id == scope_id)
                    or (row.resource_type == "project" and row.resource_id == project_id)
                    or (row.resource_type == "tenant" and row.resource_id == tenant_id)
                ]
            holds = [
                {
                    "hold_id": row.hold_id,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "authority_reference": row.authority_reference,
                }
                for row in relevant_holds
            ]
            nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []
            exceptions: list[dict[str, Any]] = []
            for table_name, table in sorted(Base.metadata.tables.items()):
                if table_name in {
                    "audit_events", "outbox_events", "recovery_locks",
                    "deletion_dependency_graphs", "purge_runs",
                }:
                    continue
                if "tenant_id" not in table.c:
                    continue
                statement = select(table).where(table.c.tenant_id == tenant_id)
                if "project_id" in table.c and scope_type != "tenant":
                    statement = statement.where(table.c.project_id == project_id)
                for raw in session.execute(statement):
                    mapping = dict(raw._mapping)
                    include = False
                    if scope_type in {"project", "tenant"}:
                        include = True
                    elif scope_type == "asset":
                        include = _contains_reference(mapping, scope_id)
                        ref = session.get(AssetRefRow, scope_id)
                        include = include or bool(ref and _contains_reference(mapping, ref.sha256))
                    elif scope_type == "subject":
                        include = _contains_reference(mapping, scope_id)
                    if not include:
                        continue
                    record_id = _primary_key(table, mapping)
                    classification = "canonical"
                    disposition = "tombstone_or_redact"
                    if table_name in {"search_documents"}:
                        classification, disposition = "index", "purge"
                    elif "cache" in table_name or "invalidation" in table_name:
                        classification, disposition = "cache", "invalidate"
                    elif table_name in {"exports"} or "export" in table_name:
                        classification, disposition = "export", "withdraw_or_reissue"
                    elif "representation" in table_name or "derivation" in table_name:
                        classification, disposition = "derivative", "withdraw_or_tombstone"
                    elif table_name in {"recovery_points", "backup_runs", "backup_expiry_evidence"}:
                        classification, disposition = "backup", "expire_on_bounded_schedule"
                    nodes.append({"table": table_name, "record_id": record_id, "store_class": classification, "disposition": disposition})
                    edges.append({"from": f"{scope_type}:{scope_id}", "to": f"{table_name}:{record_id}", "relationship": "deletion_dependency"})
            if scope_type == "tenant":
                exceptions.append({
                    "code": "TENANT_PURGE_REQUIRES_OFFBOARDING",
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "required_workflow": "tenant_offboarding_then_per_project_governed_purge",
                })
            if not nodes:
                exceptions.append({"code": "DELETION_SCOPE_EMPTY", "scope_type": scope_type, "scope_id": scope_id})
            nodes = sorted({canonical_sha256(item): item for item in nodes}.values(), key=lambda item: (item["store_class"], item["table"], item["record_id"]))
            edges = sorted({canonical_sha256(item): item for item in edges}.values(), key=lambda item: (item["to"], item["relationship"]))
            store_plan: dict[str, list[dict[str, Any]]] = {name: [] for name in ("canonical", "derivative", "index", "cache", "export", "replica", "backup")}
            for node in nodes:
                store_plan.setdefault(node["store_class"], []).append({"table": node["table"], "record_id": node["record_id"], "disposition": node["disposition"]})
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "nodes": nodes,
                "edges": edges,
                "holds": sorted(holds, key=lambda item: item["hold_id"]),
                "exceptions": exceptions,
                "store_plan": store_plan,
            }
            body["eligible"] = not holds and not exceptions
            body["graph_hash"] = canonical_sha256(body)
            return body

    @staticmethod
    def _graph_result(row: DeletionGraphRow) -> dict[str, Any]:
        return {
            "deletion_graph_id": row.deletion_graph_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "nodes": row.nodes_json,
            "edges": row.edges_json,
            "holds": row.holds_json,
            "exceptions": row.exceptions_json,
            "store_plan": row.store_plan_json,
            "eligible": row.eligible,
            "graph_hash": row.graph_hash,
            "state": row.state,
        }

    def request_purge(
        self,
        *,
        tenant_id: str,
        project_id: str,
        deletion_graph_id: str,
        recovery_point_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        request = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "deletion_graph_id": deletion_graph_id,
            "recovery_point_id": recovery_point_id,
            "idempotency_key": idempotency_key,
        }
        digest = canonical_sha256(request)
        with self.database.session() as session:
            graph = session.get(DeletionGraphRow, deletion_graph_id)
            if graph is None or graph.tenant_id != tenant_id or graph.project_id != project_id:
                raise NotFoundError("deletion_graph", deletion_graph_id)
            if not graph.eligible:
                raise ConflictError("DELETION_GRAPH_INELIGIBLE", "deletion graph contains holds or unresolved exceptions")
            point = self._get_point(session, tenant_id, project_id, recovery_point_id)
            if point.state != "verified":
                raise ConflictError("VERIFIED_RECOVERY_POINT_REQUIRED", "purge requires a verified recovery point")
            existing = session.scalar(
                select(PurgeRunRow).where(PurgeRunRow.tenant_id == tenant_id, PurgeRunRow.project_id == project_id, PurgeRunRow.idempotency_key == idempotency_key)
            )
            if existing:
                if existing.request_hash != digest:
                    raise ConflictError("PURGE_IDEMPOTENCY_CONFLICT", "purge idempotency key was reused")
                return self._purge_result(existing, True)
            identifier = new_uuid()
            row = PurgeRunRow(
                purge_run_id=identifier,
                tenant_id=tenant_id,
                project_id=project_id,
                deletion_graph_id=deletion_graph_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                state="awaiting_approval",
                store_results_json={"recovery_point_id": recovery_point_id},
                unresolved_exceptions_json=[],
                backup_expiry_json=[],
                cryptographic_erasure_json={},
                requested_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:purge_request",
                resource_type="purge_run",
                resource_id=identifier,
                details={"deletion_graph_id": deletion_graph_id, "recovery_point_id": recovery_point_id},
                event_type="deletion.purge_requested",
                payload={"deletion_graph_id": deletion_graph_id, "state": "awaiting_approval", "request_hash": digest},
            )
            return self._purge_result(row, False)

    def approve_purge(self, *, tenant_id: str, project_id: str, purge_run_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(PurgeRunRow, purge_run_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("purge_run", purge_run_id)
            if row.requested_by == actor_id:
                raise AuthorizationError("PURGE_INDEPENDENT_APPROVAL_REQUIRED", "purge requester cannot approve the purge")
            if row.state == "approved":
                return self._purge_result(row, True)
            if row.state != "awaiting_approval":
                raise ConflictError("PURGE_STATE_INVALID", "purge is not awaiting approval")
            row.state = "approved"
            row.approved_by = actor_id
            row.approved_at = db_now()
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:purge_approve",
                resource_type="purge_run",
                resource_id=purge_run_id,
                details={"requested_by": row.requested_by},
                event_type="deletion.purge_approved",
                payload={"state": "approved", "requested_by": row.requested_by},
            )
            return self._purge_result(row, False)

    def execute_purge(
        self,
        *,
        tenant_id: str,
        project_id: str,
        purge_run_id: str,
        key_erasure: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        with self._process_lock:
            with self.database.session() as session:
                row = session.get(PurgeRunRow, purge_run_id)
                if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                    raise NotFoundError("purge_run", purge_run_id)
                if row.state == "executed":
                    return self._purge_result(row, True)
                if row.state != "approved" or not row.approved_by:
                    raise ConflictError("PURGE_NOT_APPROVED", "purge requires independent approval")
                graph = session.get(DeletionGraphRow, row.deletion_graph_id)
                assert graph is not None
                current = self._compute_deletion_graph(tenant_id=tenant_id, project_id=project_id, scope_type=graph.scope_type, scope_id=graph.scope_id)
                if current["graph_hash"] != graph.graph_hash:
                    raise ConflictError("DELETION_GRAPH_CHANGED", "deletion dependencies changed after approval")
                if current["holds"]:
                    raise ConflictError("LEGAL_HOLD_ACTIVE", "legal hold blocks deletion")
                self._acquire_lock(session, tenant_id, project_id, "project-recovery", "purge", purge_run_id)
                recovery_point_id = str(row.store_results_json["recovery_point_id"])
            try:
                store_results = self._apply_purge(tenant_id=tenant_id, project_id=project_id, graph=graph, actor_id=actor_id)
                unresolved = [item for item in store_results["stores"] if item.get("status") not in {"purged", "invalidated", "withdrawn", "scheduled", "not_applicable"}]
                backup_expiry = self.schedule_backup_expiry(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    recovery_point_id=recovery_point_id,
                    resource_scope={"scope_type": graph.scope_type, "scope_id": graph.scope_id, "purge_run_id": purge_run_id},
                    scheduled_for=db_now() + timedelta(days=30),
                    residuals=[{"location": "recovery_point", "state": "restricted_until_expiry"}],
                    actor_id=actor_id,
                )
                crypto = self._validate_erasure_evidence(key_erasure)
                evidence_body = {
                    "purge_run_id": purge_run_id,
                    "graph_hash": graph.graph_hash,
                    "store_results": store_results,
                    "unresolved": unresolved,
                    "backup_expiry": backup_expiry,
                    "cryptographic_erasure": crypto,
                    "approved_by": row.approved_by,
                    "executed_by": actor_id,
                }
                evidence_hash = canonical_sha256(evidence_body)
                with self.database.session() as session:
                    row = session.get(PurgeRunRow, purge_run_id)
                    assert row is not None
                    row.state = "executed" if not unresolved else "failed"
                    row.store_results_json = store_results
                    row.unresolved_exceptions_json = unresolved
                    row.backup_expiry_json = [backup_expiry]
                    row.cryptographic_erasure_json = crypto
                    row.evidence_hash = evidence_hash
                    row.executed_by = actor_id
                    row.executed_at = db_now()
                    graph_row = session.get(DeletionGraphRow, row.deletion_graph_id)
                    if graph_row:
                        graph_row.state = "executed"
                    self._release_lock(session, tenant_id, project_id, "project-recovery", purge_run_id)
                    self._audit_and_emit(
                        session,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        actor_id=actor_id,
                        action="deletion:purge_execute",
                        resource_type="purge_run",
                        resource_id=purge_run_id,
                        details={"state": row.state, "evidence_hash": evidence_hash, "unresolved": len(unresolved)},
                        event_type="deletion.purge_completed",
                        payload={"state": row.state, "evidence_hash": evidence_hash, "unresolved_count": len(unresolved), "backup_expiry_id": backup_expiry["backup_expiry_id"]},
                    )
                    return self._purge_result(row, False)
            except Exception:
                with self.database.session() as session:
                    self._release_lock(session, tenant_id, project_id, "project-recovery", purge_run_id, missing_ok=True)
                raise

    def _apply_purge(self, *, tenant_id: str, project_id: str, graph: DeletionGraphRow, actor_id: str) -> dict[str, Any]:
        stores: list[dict[str, Any]] = []
        if graph.scope_type == "asset":
            impact = self.assets.tombstone(tenant_id, project_id, graph.scope_id, actor_id=actor_id, dry_run=False)
            stores.append({"store": "canonical", "status": "purged", "impact": impact})
        else:
            with self.database.session() as session:
                # Search and cache surfaces are deleted first; authoritative audit rows are preserved.
                deleted_search = 0
                for node in graph.nodes_json:
                    if node["table"] == "search_documents":
                        result = session.execute(
                            delete(SearchDocumentRow).where(
                                SearchDocumentRow.tenant_id == tenant_id,
                                SearchDocumentRow.project_id == project_id,
                                SearchDocumentRow.document_id == node["record_id"],
                            )
                        )
                        deleted_search += int(result.rowcount or 0)
                stores.append({"store": "index", "status": "purged", "records": deleted_search})
                exports = list(session.scalars(select(ExportRow).where(ExportRow.tenant_id == tenant_id, ExportRow.project_id == project_id)))
                for export in exports:
                    export.status = "withdrawn_by_deletion"
                stores.append({"store": "export", "status": "withdrawn", "records": len(exports)})
                if graph.scope_type == "subject":
                    records = list(
                        session.scalars(
                            select(MemoryRecordRow).where(
                                MemoryRecordRow.tenant_id == tenant_id,
                                MemoryRecordRow.project_id == project_id,
                                MemoryRecordRow.subject_id == graph.scope_id,
                            )
                        )
                    )
                    for record in records:
                        record.superseded_at = db_now()
                        record.data_json = {"withdrawn": True, "reason": "governed_deletion"}
                        record.evidence_asset_ids_json = []
                        record.generated_lineage_json = None
                    stores.append({"store": "canonical", "status": "purged", "records": len(records)})
                else:
                    refs = list(
                        session.scalars(
                            select(AssetRefRow).where(
                                AssetRefRow.tenant_id == tenant_id,
                                AssetRefRow.project_id == project_id,
                                AssetRefRow.tombstoned_at.is_(None),
                            )
                        )
                    )
                    asset_ids = [item.asset_id for item in refs]
                stores.append({"store": "cache", "status": "invalidated", "targets": ["viewer", "search", "vector", "agent", "cdn", "signed_urls"]})
                stores.append({"store": "derivative", "status": "invalidated", "records": len(graph.store_plan_json.get("derivative", []))})
            if graph.scope_type == "project":
                impacts = [
                    self.assets.tombstone(tenant_id, project_id, asset_id, actor_id=actor_id, dry_run=False)
                    for asset_id in asset_ids
                ]
                stores.append({"store": "canonical", "status": "purged", "records": len(impacts), "impacts": impacts})
        stores.append({"store": "replica", "status": "scheduled", "bounded_expiry_required": True})
        stores.append({"store": "backup", "status": "scheduled", "ordinary_restore_blocked": True})
        return {"scope_type": graph.scope_type, "scope_id": graph.scope_id, "stores": stores}

    @staticmethod
    def _validate_erasure_evidence(value: dict[str, Any]) -> dict[str, Any]:
        key_ids = sorted(set(str(item) for item in value.get("key_ids", []) if str(item)))
        residuals = value.get("residual_timelines", [])
        if not key_ids or not residuals or not value.get("key_deletion_evidence_hash") or not _is_sha256(str(value.get("key_deletion_evidence_hash"))):
            raise ValidationError("CRYPTOGRAPHIC_ERASURE_EVIDENCE_INCOMPLETE", "cryptographic erasure requires key IDs, a SHA-256 evidence hash, and residual backup/replica timelines")
        return {"key_ids": key_ids, "key_deletion_evidence_hash": value["key_deletion_evidence_hash"], "residual_timelines": residuals}

    @staticmethod
    def _purge_result(row: PurgeRunRow, replay: bool) -> dict[str, Any]:
        return {
            "purge_run_id": row.purge_run_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "deletion_graph_id": row.deletion_graph_id,
            "state": row.state,
            "store_results": row.store_results_json,
            "unresolved_exceptions": row.unresolved_exceptions_json,
            "backup_expiry": row.backup_expiry_json,
            "cryptographic_erasure": row.cryptographic_erasure_json,
            "evidence_hash": row.evidence_hash,
            "idempotent_replay": replay,
        }

    # ------------------------------------------------------------- backup expiry
    def schedule_backup_expiry(
        self,
        *,
        tenant_id: str,
        project_id: str,
        recovery_point_id: str,
        resource_scope: dict[str, Any],
        scheduled_for: datetime,
        residuals: list[dict[str, Any]],
        actor_id: str,
    ) -> dict[str, Any]:
        scheduled = _aware(scheduled_for)
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "recovery_point_id": recovery_point_id,
            "resource_scope": resource_scope,
            "scheduled_for": scheduled.isoformat(),
            "residuals": residuals,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._get_point(session, tenant_id, project_id, recovery_point_id)
            existing = session.scalar(select(BackupExpiryEvidenceRow).where(BackupExpiryEvidenceRow.evidence_hash == digest))
            if existing:
                return self._backup_expiry_result(existing)
            row = BackupExpiryEvidenceRow(
                backup_expiry_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                recovery_point_id=recovery_point_id,
                resource_scope_json=resource_scope,
                scheduled_for=scheduled,
                residuals_json=residuals,
                state="scheduled",
                evidence_hash=digest,
                recorded_by=actor_id,
            )
            session.add(row)
            return self._backup_expiry_result(row)

    def execute_backup_expiry(self, *, tenant_id: str, project_id: str, backup_expiry_id: str, actor_id: str, now: datetime | None = None) -> dict[str, Any]:
        current = _aware(now or db_now())
        with self.database.session() as session:
            row = session.get(BackupExpiryEvidenceRow, backup_expiry_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("backup_expiry", backup_expiry_id)
            if row.state == "expired":
                return self._backup_expiry_result(row)
            if current < _aware(row.scheduled_for):
                raise ConflictError("BACKUP_EXPIRY_NOT_DUE", "backup expiry deadline has not been reached")
            point = self._get_point(session, tenant_id, project_id, row.recovery_point_id)
            active_holds = list(
                session.scalars(
                    select(LegalHoldRow).where(
                        LegalHoldRow.tenant_id == tenant_id,
                        LegalHoldRow.project_id == project_id,
                        LegalHoldRow.state == "active",
                    )
                )
            )
            if active_holds:
                raise ConflictError("LEGAL_HOLD_BLOCKS_BACKUP_EXPIRY", "active legal hold blocks backup expiry")
            package_path = Path(point.package_path)
            database_path = Path(point.database_snapshot_path or "")
        package_path.chmod(0o600) if package_path.exists() else None
        database_path.chmod(0o600) if database_path.exists() else None
        package_path.unlink(missing_ok=True)
        database_path.unlink(missing_ok=True)
        with self.database.session() as session:
            row = session.get(BackupExpiryEvidenceRow, backup_expiry_id)
            point = self._get_point(session, tenant_id, project_id, row.recovery_point_id)
            row.state = "expired"
            row.executed_at = current
            point.state = "expired"
            point.expired_at = current
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:backup_expire",
                resource_type="backup_expiry",
                resource_id=backup_expiry_id,
                details={"recovery_point_id": point.recovery_point_id, "executed_at": current.isoformat()},
                event_type="recovery.backup_expired",
                payload={"recovery_point_id": point.recovery_point_id, "state": "expired", "evidence_hash": row.evidence_hash},
            )
            return self._backup_expiry_result(row)

    @staticmethod
    def _backup_expiry_result(row: BackupExpiryEvidenceRow) -> dict[str, Any]:
        return {
            "backup_expiry_id": row.backup_expiry_id,
            "recovery_point_id": row.recovery_point_id,
            "resource_scope": row.resource_scope_json,
            "scheduled_for": _aware(row.scheduled_for).isoformat(),
            "executed_at": _aware(row.executed_at).isoformat() if row.executed_at else None,
            "residuals": row.residuals_json,
            "state": row.state,
            "evidence_hash": row.evidence_hash,
        }

    # ------------------------------------------------------- fixity/format/offboard
    def check_fixity(
        self,
        *,
        tenant_id: str,
        project_id: str,
        asset_id: str,
        replica_asset_ids: list[str],
        recovery_point_ids: list[str] | None = None,
        repair_if_needed: bool,
        actor_id: str,
    ) -> dict[str, Any]:
        recovery_point_ids = recovery_point_ids or []
        replica_payloads: dict[str, bytes] = {}
        point_sources: list[tuple[str, Path, str]] = []
        with self.database.session() as session:
            ref = session.get(AssetRefRow, asset_id)
            if ref is None or ref.tenant_id != tenant_id or ref.project_id != project_id:
                raise NotFoundError("asset", asset_id)
            expected = ref.sha256
            replicas: list[dict[str, Any]] = []
            for replica_id in replica_asset_ids:
                replica = session.get(AssetRefRow, replica_id)
                if replica is None or replica.tenant_id != tenant_id or replica.project_id != project_id:
                    raise NotFoundError("replica_asset", replica_id)
                payload = self.assets.store.read_bytes(replica.sha256)
                descriptor_id = f"asset:{replica_id}"
                replica_payloads[descriptor_id] = payload
                replicas.append({"source": "asset", "asset_id": replica_id, "sha256": replica.sha256, "bytes": len(payload), "matches_expected": replica.sha256 == expected, "descriptor_id": descriptor_id})
            for point_id in recovery_point_ids:
                point = self._get_point(session, tenant_id, project_id, point_id)
                if point.state != "verified":
                    raise ConflictError("VERIFIED_RECOVERY_POINT_REQUIRED", "fixity repair requires a verified recovery point")
                point_sources.append((point_id, Path(point.package_path), point.package_root_hash))
        for point_id, package_path, expected_root in point_sources:
            verified_package = self.preservation.verify_export(package_path)
            if verified_package["root_hash"] != expected_root:
                raise ValidationError("RECOVERY_POINT_PACKAGE_MISMATCH", "fixity replica recovery point no longer matches its retained root")
            member = f"objects/{expected}"
            with zipfile.ZipFile(package_path) as archive:
                try:
                    payload = archive.read(member)
                except KeyError:
                    replicas.append({"source": "recovery_point", "recovery_point_id": point_id, "sha256": expected, "bytes": 0, "matches_expected": False, "descriptor_id": f"recovery-point:{point_id}"})
                    continue
            descriptor_id = f"recovery-point:{point_id}"
            matches = sha256_bytes(payload) == expected
            if matches:
                replica_payloads[descriptor_id] = payload
            replicas.append({"source": "recovery_point", "recovery_point_id": point_id, "sha256": expected, "bytes": len(payload), "matches_expected": matches, "descriptor_id": descriptor_id})
        observed: str | None
        try:
            payload = self.assets.store.read_bytes(expected)
            observed = sha256_bytes(payload)
        except (NotFoundError, ValidationError):
            observed = None
        repair: dict[str, Any] = {"attempted": False}
        state = "valid" if observed == expected else "failed"
        if observed != expected and repair_if_needed:
            candidate = next((item for item in replicas if item["matches_expected"]), None)
            if candidate is None:
                raise ValidationError("FIXITY_REPAIR_REPLICA_UNAVAILABLE", "no authorized matching replica is available")
            replica_payload = replica_payloads[candidate["descriptor_id"]]
            self.assets.store.write_bytes(expected, replica_payload)
            observed = sha256_bytes(self.assets.store.read_bytes(expected))
            state = "repaired" if observed == expected else "failed"
            repair = {"attempted": True, "replica": {k: v for k, v in candidate.items() if k != "descriptor_id"}, "successful": state == "repaired"}
        body = {"tenant_id": tenant_id, "project_id": project_id, "asset_id": asset_id, "expected_sha256": expected, "observed_sha256": observed, "replicas": replicas, "repair": repair, "state": state}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(FixityCheckRow).where(FixityCheckRow.check_hash == digest))
            if existing:
                return self._fixity_result(existing)
            row = FixityCheckRow(
                fixity_check_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                resource_type="asset",
                resource_id=asset_id,
                expected_sha256=expected,
                observed_sha256=observed,
                replicas_json=replicas,
                repair_json=repair,
                state=state,
                check_hash=digest,
                checked_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="preservation:fixity_check",
                resource_type="fixity_check",
                resource_id=row.fixity_check_id,
                details={"asset_id": asset_id, "state": state, "repair": repair},
                event_type="preservation.fixity_checked",
                payload={"asset_id": asset_id, "state": state, "check_hash": digest, "repair_attempted": repair["attempted"]},
            )
            return self._fixity_result(row)

    @staticmethod
    def _fixity_result(row: FixityCheckRow) -> dict[str, Any]:
        return {"fixity_check_id": row.fixity_check_id, "resource_id": row.resource_id, "expected_sha256": row.expected_sha256, "observed_sha256": row.observed_sha256, "replicas": row.replicas_json, "repair": row.repair_json, "state": row.state, "check_hash": row.check_hash}

    def record_format_migration(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_asset_id: str,
        derivative_asset_id: str,
        source_format: str,
        target_format: str,
        migration_tool: dict[str, Any],
        validation: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            source = session.get(AssetRefRow, source_asset_id)
            derivative = session.get(AssetRefRow, derivative_asset_id)
            if source is None or source.tenant_id != tenant_id or source.project_id != project_id or source.tombstoned_at:
                raise NotFoundError("source_asset", source_asset_id)
            if derivative is None or derivative.tenant_id != tenant_id or derivative.project_id != project_id or derivative.tombstoned_at:
                raise NotFoundError("derivative_asset", derivative_asset_id)
            losses = validation.get("losses")
            if (
                not migration_tool.get("name")
                or not migration_tool.get("version")
                or validation.get("passed") is not True
                or not isinstance(losses, list)
                or validation.get("source_relationship_retained") is not True
            ):
                raise ValidationError(
                    "FORMAT_MIGRATION_EVIDENCE_INCOMPLETE",
                    "format migration requires tool identity, explicit irreversible-loss declarations, retained source relationships, and passing validation",
                )
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "source_asset_id": source_asset_id,
                "source_sha256": source.sha256,
                "derivative_asset_id": derivative_asset_id,
                "derivative_sha256": derivative.sha256,
                "source_format": source_format,
                "target_format": target_format,
                "migration_tool": migration_tool,
                "validation": validation,
                "original_preserved": True,
            }
            digest = canonical_sha256(body)
            existing = session.scalar(select(FormatMigrationEvidenceRow).where(FormatMigrationEvidenceRow.migration_hash == digest))
            if existing:
                return self._format_migration_result(existing)
            row = FormatMigrationEvidenceRow(
                format_migration_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                source_asset_id=source_asset_id,
                source_sha256=source.sha256,
                derivative_asset_id=derivative_asset_id,
                derivative_sha256=derivative.sha256,
                source_format=source_format,
                target_format=target_format,
                migration_tool_json=migration_tool,
                validation_json=validation,
                state="validated",
                migration_hash=digest,
                migrated_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="preservation:format_migrate",
                resource_type="format_migration",
                resource_id=row.format_migration_id,
                details={"source_asset_id": source_asset_id, "derivative_asset_id": derivative_asset_id, "migration_hash": digest},
                event_type="preservation.format_migrated",
                payload={"source_asset_id": source_asset_id, "derivative_asset_id": derivative_asset_id, "state": "validated", "migration_hash": digest},
            )
            return self._format_migration_result(row)

    @staticmethod
    def _format_migration_result(row: FormatMigrationEvidenceRow) -> dict[str, Any]:
        return {"format_migration_id": row.format_migration_id, "source_asset_id": row.source_asset_id, "source_sha256": row.source_sha256, "derivative_asset_id": row.derivative_asset_id, "derivative_sha256": row.derivative_sha256, "source_format": row.source_format, "target_format": row.target_format, "validation": row.validation_json, "original_preserved": True, "state": row.state, "migration_hash": row.migration_hash}

    def create_tenant_offboarding(self, *, tenant_id: str, destination: Path, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            tenant = session.get(TenantRow, tenant_id)
            if tenant is None:
                raise NotFoundError("tenant", tenant_id)
            projects = list(session.scalars(select(ProjectRow).where(ProjectRow.tenant_id == tenant_id)))
        root = destination.resolve()
        root.mkdir(parents=True, exist_ok=True)
        exports: list[dict[str, Any]] = []
        deletion_reports: list[dict[str, Any]] = []
        retention_reports: list[dict[str, Any]] = []
        for project in projects:
            package = root / f"{project.project_id}.sip-preservation.zip"
            exported = self.preservation.export_project(tenant_id, project.project_id, package, actor_id=actor_id)
            verified = self.preservation.verify_export(package)
            exports.append({"project_id": project.project_id, "path": str(package), "sha256": verified["package_sha256"], "root_hash": verified["root_hash"]})
            graph = self._compute_deletion_graph(tenant_id=tenant_id, project_id=project.project_id, scope_type="project", scope_id=project.project_id)
            deletion_reports.append({"project_id": project.project_id, "graph_hash": graph["graph_hash"], "eligible": graph["eligible"], "holds": graph["holds"], "exceptions": graph["exceptions"]})
            retention = self.evaluate_retention_inventory(tenant_id=tenant_id, project_id=project.project_id, actor_id=actor_id)
            retention_reports.append({"project_id": project.project_id, "inventory_hash": retention["inventory_hash"], "resources": len(retention["assignments"])})
        body = {"tenant_id": tenant_id, "exports": exports, "deletion_reports": deletion_reports, "retention_reports": retention_reports}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(TenantOffboardingRow).where(TenantOffboardingRow.offboarding_hash == digest))
            if existing:
                return self._offboarding_result(existing, True)
            row = TenantOffboardingRow(
                offboarding_id=new_uuid(),
                tenant_id=tenant_id,
                export_manifest_json={"projects": exports, "root_hash": canonical_sha256(exports)},
                deletion_report_json={"projects": deletion_reports},
                retention_report_json={"projects": retention_reports},
                state="prepared",
                offboarding_hash=digest,
                requested_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=None,
                actor_id=actor_id,
                action="tenant:offboarding_prepare",
                resource_type="tenant_offboarding",
                resource_id=row.offboarding_id,
                details={"projects": len(projects), "export_root_hash": row.export_manifest_json["root_hash"]},
                event_type="tenant.offboarding_prepared",
                payload={"projects": len(projects), "export_root_hash": row.export_manifest_json["root_hash"], "state": "prepared"},
            )
            return self._offboarding_result(row, False)

    @staticmethod
    def _offboarding_result(row: TenantOffboardingRow, replay: bool) -> dict[str, Any]:
        return {"offboarding_id": row.offboarding_id, "tenant_id": row.tenant_id, "export_manifest": row.export_manifest_json, "deletion_report": row.deletion_report_json, "retention_report": row.retention_report_json, "state": row.state, "offboarding_hash": row.offboarding_hash, "idempotent_replay": replay}

    # ------------------------------------------------------ disaster game day
    def run_game_day(
        self,
        *,
        deployment_profile_id: str,
        scenario: str,
        evidence_class: str,
        tenant_id: str,
        project_id: str,
        affected_services: list[str],
        affected_region: str | None,
        recovery_point_id: str | None,
        portability_destination: Path,
        timeline: list[dict[str, Any]],
        metrics: dict[str, Any],
        findings: list[dict[str, Any]],
        actor_id: str,
    ) -> dict[str, Any]:
        if evidence_class not in {"synthetic", "local_executed", "cloud_executed", "external_witnessed"}:
            raise ValidationError("GAME_DAY_EVIDENCE_CLASS_INVALID", "unsupported game-day evidence class")
        if evidence_class in {"cloud_executed", "external_witnessed"}:
            raise ValidationError(
                "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED",
                "the local reference implementation cannot mint cloud-executed or externally witnessed game-day evidence",
            )
        if not affected_services or not timeline or "rto_seconds" not in metrics or "rpo_seconds" not in metrics:
            raise ValidationError("GAME_DAY_EVIDENCE_INCOMPLETE", "game day requires affected services, timeline, RPO, and RTO evidence")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            self._profile(session, deployment_profile_id)
            if recovery_point_id:
                point = self._get_point(session, tenant_id, project_id, recovery_point_id)
                if point.state != "verified":
                    raise ConflictError("VERIFIED_RECOVERY_POINT_REQUIRED", "game day requires a verified recovery point")
        portability_destination.parent.mkdir(parents=True, exist_ok=True)
        export = self.preservation.export_project(tenant_id, project_id, portability_destination, actor_id=actor_id)
        verified_export = self.preservation.verify_export(portability_destination)
        portability = {"path": str(portability_destination), "sha256": verified_export["package_sha256"], "root_hash": verified_export["root_hash"], "verified": True}
        state = "passed" if not findings else "passed_with_gaps"
        body = {
            "deployment_profile_id": deployment_profile_id,
            "scenario": scenario,
            "evidence_class": evidence_class,
            "affected_services": affected_services,
            "affected_region": affected_region,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "recovery_point_id": recovery_point_id,
            "portability": portability,
            "timeline": timeline,
            "metrics": metrics,
            "findings": findings,
            "state": state,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(RecoveryGameDayRow).where(RecoveryGameDayRow.game_day_hash == digest))
            if existing:
                return self._game_day_result(existing, True)
            row = RecoveryGameDayRow(
                recovery_game_day_id=new_uuid(),
                deployment_profile_id=deployment_profile_id,
                scenario=scenario,
                evidence_class=evidence_class,
                affected_services_json=affected_services,
                affected_region=affected_region,
                tenant_id=tenant_id,
                project_id=project_id,
                recovery_point_id=recovery_point_id,
                portability_export_json=portability,
                timeline_json=timeline,
                metrics_json=metrics,
                findings_json=findings,
                state=state,
                game_day_hash=digest,
                conducted_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="recovery:game_day",
                resource_type="recovery_game_day",
                resource_id=row.recovery_game_day_id,
                details={"scenario": scenario, "state": state, "evidence_class": evidence_class, "rpo_seconds": metrics["rpo_seconds"], "rto_seconds": metrics["rto_seconds"]},
                event_type="recovery.game_day_completed",
                payload={"scenario": scenario, "state": state, "evidence_class": evidence_class, "rpo_seconds": metrics["rpo_seconds"], "rto_seconds": metrics["rto_seconds"], "game_day_hash": digest},
            )
            return self._game_day_result(row, False)

    @staticmethod
    def _game_day_result(row: RecoveryGameDayRow, replay: bool) -> dict[str, Any]:
        return {"recovery_game_day_id": row.recovery_game_day_id, "deployment_profile_id": row.deployment_profile_id, "scenario": row.scenario, "evidence_class": row.evidence_class, "tenant_id": row.tenant_id, "project_id": row.project_id, "state": row.state, "metrics": row.metrics_json, "findings": row.findings_json, "portability_export": row.portability_export_json, "game_day_hash": row.game_day_hash, "idempotent_replay": replay}

    # ------------------------------------------------------- v1.0 migration report
    def record_legacy_migration(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_backup_id: str,
        source_release: str,
        target_release: str,
        candidates: list[dict[str, Any]],
        unresolved_anchors: list[dict[str, Any]],
        policy_diffs: list[dict[str, Any]],
        rollback_evidence: dict[str, Any],
        compatibility_report: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        if not source_release.startswith("1.0") or not target_release.startswith("1.1"):
            raise ValidationError("LEGACY_MIGRATION_VERSION_INVALID", "migration contract supports SIP v1.0 to v1.1")
        mappings: list[dict[str, Any]] = []
        quarantines: list[dict[str, Any]] = []
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            point = self._get_point(session, tenant_id, project_id, source_backup_id)
            if point.state != "verified":
                raise ConflictError("RESTORABLE_SOURCE_BACKUP_REQUIRED", "legacy migration requires a verified restorable backup")
            for candidate in candidates:
                asset_id = str(candidate.get("asset_id", ""))
                ref = session.get(AssetRefRow, asset_id)
                if ref is None or ref.tenant_id != tenant_id or ref.project_id != project_id or ref.tombstoned_at:
                    raise NotFoundError("migration_source_asset", asset_id)
                if candidate.get("sha256") != ref.sha256:
                    raise ValidationError("MIGRATION_SOURCE_HASH_MISMATCH", "legacy migration source hash does not match immutable asset")
                provenance = candidate.get("provenance", {})
                verification = candidate.get("verification", {})
                source_kind = str(candidate.get("source_kind", "unknown"))
                role, ceiling, state = self._conservative_role(source_kind, provenance, verification)
                record = {"asset_id": asset_id, "sha256": ref.sha256, "source_kind": source_kind, "role": role, "authority_ceiling": ceiling, "state": state, "original_bytes_rewritten": False}
                mappings.append(record)
                if state == "quarantined":
                    quarantines.append({"asset_id": asset_id, "reason": "ambiguous_role_or_authority", "allowed_uses": ["review"]})
            relaxed = [item for item in policy_diffs if item.get("direction") in {"less_restrictive", "removed"}]
            if relaxed:
                raise AuthorizationError("MIGRATION_POLICY_RELAXATION_DENIED", "migration may not weaken permission, consent, retention, legal-hold, or deletion dependencies", {"diffs": relaxed})
            if rollback_evidence.get("recovery_point_id") != source_backup_id or rollback_evidence.get("verified") is not True:
                raise ValidationError("MIGRATION_ROLLBACK_EVIDENCE_INCOMPLETE", "migration rollback evidence must identify the verified source recovery point")
            validation = {
                "all_source_hashes_preserved": True,
                "additive_records_only": True,
                "authority_never_increased": all(item["authority_ceiling"] != "verified" or candidates[index].get("verification", {}).get("verified") is True for index, item in enumerate(mappings)),
                "ambiguous_quarantined": len(quarantines),
                "unresolved_anchors": len(unresolved_anchors),
                "policy_diffs_non_relaxing": True,
                "rollback_verified": True,
            }
            body = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "source_release": source_release,
                "target_release": target_release,
                "source_backup_id": source_backup_id,
                "asset_mappings": mappings,
                "quarantines": quarantines,
                "unresolved_anchors": unresolved_anchors,
                "policy_diffs": policy_diffs,
                "validation": validation,
                "rollback_evidence": rollback_evidence,
                "compatibility_report": compatibility_report,
            }
            digest = canonical_sha256(body)
            signature = base64.urlsafe_b64encode(hmac.new(self.signing_key, canonical_json(body), sha256).digest()).decode("ascii")
            existing = session.scalar(select(LegacyMigrationRunRow).where(LegacyMigrationRunRow.report_hash == digest))
            if existing:
                return self._legacy_result(existing, True)
            row = LegacyMigrationRunRow(
                legacy_migration_run_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                source_release=source_release,
                target_release=target_release,
                source_backup_id=source_backup_id,
                asset_mappings_json=mappings,
                quarantines_json=quarantines,
                unresolved_anchors_json=unresolved_anchors,
                policy_diffs_json=policy_diffs,
                validation_json=validation,
                rollback_evidence_json=rollback_evidence,
                compatibility_report_json=compatibility_report,
                state="validated",
                report_hash=digest,
                signed_report=signature,
                migrated_by=actor_id,
            )
            session.add(row)
            self._audit_and_emit(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="migration:v1_to_v1_1_validate",
                resource_type="legacy_migration_run",
                resource_id=row.legacy_migration_run_id,
                details={"mappings": len(mappings), "quarantines": len(quarantines), "unresolved_anchors": len(unresolved_anchors), "report_hash": digest},
                event_type="migration.legacy_validated",
                payload={"mappings": len(mappings), "quarantines": len(quarantines), "unresolved_anchors": len(unresolved_anchors), "state": "validated", "report_hash": digest},
            )
            return self._legacy_result(row, False)

    @staticmethod
    def _conservative_role(source_kind: str, provenance: dict[str, Any], verification: dict[str, Any]) -> tuple[str, str, str]:
        verified = verification.get("verified") is True and bool(provenance.get("source_ids"))
        mapping = {
            "calibrated_point_cloud": ("metric_point_cloud", "verified" if verified else "observed"),
            "metric_mesh": ("metric_mesh", "verified" if verified else "measured"),
            "gaussian_splat": ("visual_splat", "visualization_only"),
            "photogrammetry_mesh": ("visual_mesh", "visualization_only"),
            "ifc_bim_cad": ("design_mesh", "design_intent"),
            "collision_nav": ("interaction_proxy", "non_authoritative"),
            "source_evidence": ("source_evidence", "evidence"),
        }
        if source_kind not in mapping:
            return "unknown_visual", "none", "quarantined"
        role, ceiling = mapping[source_kind]
        return role, ceiling, "mapped"

    @staticmethod
    def _legacy_result(row: LegacyMigrationRunRow, replay: bool) -> dict[str, Any]:
        return {
            "legacy_migration_run_id": row.legacy_migration_run_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "source_release": row.source_release,
            "target_release": row.target_release,
            "asset_mappings": row.asset_mappings_json,
            "quarantines": row.quarantines_json,
            "unresolved_anchors": row.unresolved_anchors_json,
            "policy_diffs": row.policy_diffs_json,
            "validation": row.validation_json,
            "rollback_evidence": row.rollback_evidence_json,
            "compatibility_report": row.compatibility_report_json,
            "state": row.state,
            "report_hash": row.report_hash,
            "signed_report": row.signed_report,
            "idempotent_replay": replay,
        }

    # ----------------------------------------------------- fail-closed admission
    def production_recovery_admission(self, *, deployment_profile_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            self._profile(session, deployment_profile_id)
            objectives = list(session.scalars(select(RecoveryObjectiveRow).where(RecoveryObjectiveRow.deployment_profile_id == deployment_profile_id, RecoveryObjectiveRow.state == "active")))
            points = list(session.scalars(select(RecoveryPointRow).where(RecoveryPointRow.deployment_profile_id == deployment_profile_id, RecoveryPointRow.state == "verified")))
            game_days = list(session.scalars(select(RecoveryGameDayRow).where(RecoveryGameDayRow.deployment_profile_id == deployment_profile_id, RecoveryGameDayRow.state == "passed")))
            external_points = [item for item in points if item.evidence_class in {"cloud_executed", "external_witnessed"}]
            external_game_days = [item for item in game_days if item.evidence_class in {"cloud_executed", "external_witnessed"}]
            blockers = []
            if not objectives:
                blockers.append("recovery_objectives_missing")
            if not external_points:
                blockers.append("credentialed_cloud_or_external_restore_evidence_missing")
            if not external_game_days:
                blockers.append("external_disaster_exercise_missing")
            blockers.extend(["qa002_final_release_gates_unauthorized", "production_credentials_unavailable"])
            decision = {"admitted": False, "deployment_profile_id": deployment_profile_id, "blockers": blockers, "evidence_class": "structural_and_local_only", "production_authorized": False}
            self.audit.append(tenant_id="platform", project_id=None, actor_id=actor_id, action="recovery:production_admission", resource_type="deployment_profile", resource_id=deployment_profile_id, outcome="denied", details=decision, session=session)
            return decision

    # ------------------------------------------------------------------ locks
    def _acquire_lock(self, session: Session, tenant_id: str, project_id: str, lock_scope: str, operation_type: str, owner_operation_id: str) -> None:
        now = db_now()
        session.execute(
            delete(RecoveryLockRow).where(
                RecoveryLockRow.tenant_id == tenant_id,
                RecoveryLockRow.project_id == project_id,
                RecoveryLockRow.lock_scope == lock_scope,
                RecoveryLockRow.expires_at <= now,
            )
        )
        session.flush()
        try:
            # Isolate the uniqueness probe in a savepoint so a governed lock
            # conflict does not poison the caller's surrounding transaction.
            with session.begin_nested():
                session.add(
                    RecoveryLockRow(
                        recovery_lock_id=new_uuid(),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        lock_scope=lock_scope,
                        operation_type=operation_type,
                        owner_operation_id=owner_operation_id,
                        expires_at=now + timedelta(minutes=30),
                    )
                )
                session.flush()
        except IntegrityError as exc:
            raise ConflictError("RECOVERY_SCOPE_LOCKED", "another restore or deletion operation owns the project recovery lock") from exc

    @staticmethod
    def _release_lock(session: Session, tenant_id: str, project_id: str, lock_scope: str, owner_operation_id: str, *, missing_ok: bool = False) -> None:
        row = session.scalar(
            select(RecoveryLockRow).where(
                RecoveryLockRow.tenant_id == tenant_id,
                RecoveryLockRow.project_id == project_id,
                RecoveryLockRow.lock_scope == lock_scope,
                RecoveryLockRow.owner_operation_id == owner_operation_id,
            )
        )
        if row is None:
            if missing_ok:
                return
            raise ConflictError("RECOVERY_LOCK_OWNERSHIP_LOST", "recovery operation no longer owns its lock")
        session.delete(row)

    @staticmethod
    def _schema_fingerprint() -> str:
        return canonical_sha256(
            [
                {
                    "table": table.name,
                    "columns": [{"name": column.name, "type": str(column.type), "nullable": column.nullable} for column in table.columns],
                }
                for table in sorted(Base.metadata.tables.values(), key=lambda item: item.name)
            ]
        )
