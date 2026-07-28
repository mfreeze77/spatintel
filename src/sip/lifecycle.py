from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .assets import AssetService, LocalContentAddressedStore
from .audit import AuditService
from .canonical import canonical_sha256, new_uuid, sha256_file
from .database import (
    AssetRefRow,
    AssetRow,
    BackupRunRow,
    Base,
    Database,
    DeletionEvidenceRow,
    DeletionRequestRow,
    ExportRow,
    KeyRotationRow,
    LegalHoldRow,
    OperationRow,
    ProjectRow,
    QuotaPolicyRow,
    RetentionRuleRow,
    TenantRow,
    UsageLedgerRow,
)
from .errors import ConflictError, NotFoundError, ValidationError
from .exporting import PreservationService
from .security import EnvelopeCipher
from .temporal import db_now


class LifecycleService:
    """Retention, legal hold, destructive-operation planning, and erasure evidence.

    A deletion is a four-step workflow: deterministic dry run, verified backup,
    independent approval, and execution against an unchanged dependency snapshot.
    """

    def __init__(self, database: Database, assets: AssetService, audit: AuditService) -> None:
        self.database = database
        self.assets = assets
        self.audit = audit

    def set_retention_rule(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        retention_class: str,
        policy_source: str,
        minimum_days: int,
        maximum_days: int | None,
        backup_expiry_days: int,
        deletion_mode: str,
        actor_id: str,
    ) -> str:
        if minimum_days < 0 or backup_expiry_days < 0 or (maximum_days is not None and maximum_days < minimum_days):
            raise ValidationError("RETENTION_RANGE_INVALID", "retention duration bounds are invalid")
        if deletion_mode not in {"tombstone_then_erase", "tombstone_only", "manual_review"}:
            raise ValidationError("RETENTION_MODE_INVALID", "unsupported retention deletion mode")
        with self.database.session() as session:
            if not session.get(TenantRow, tenant_id):
                raise NotFoundError("tenant", tenant_id)
            if project_id:
                project = session.get(ProjectRow, project_id)
                if not project or project.tenant_id != tenant_id:
                    raise NotFoundError("project", project_id)
            prior = session.scalar(
                select(func.max(RetentionRuleRow.version)).where(
                    RetentionRuleRow.tenant_id == tenant_id,
                    RetentionRuleRow.project_id == project_id,
                    RetentionRuleRow.retention_class == retention_class,
                )
            ) or 0
            for row in session.scalars(
                select(RetentionRuleRow).where(
                    RetentionRuleRow.tenant_id == tenant_id,
                    RetentionRuleRow.project_id == project_id,
                    RetentionRuleRow.retention_class == retention_class,
                    RetentionRuleRow.active.is_(True),
                )
            ):
                row.active = False
            identifier = new_uuid()
            session.add(
                RetentionRuleRow(
                    retention_rule_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    retention_class=retention_class,
                    policy_source=policy_source,
                    minimum_days=minimum_days,
                    maximum_days=maximum_days,
                    backup_expiry_days=backup_expiry_days,
                    deletion_mode=deletion_mode,
                    active=True,
                    version=int(prior) + 1,
                    created_by=actor_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="retention:rule_create",
                resource_type="retention_rule",
                resource_id=identifier,
                outcome="allowed",
                details={"retention_class": retention_class, "version": int(prior) + 1, "policy_source": policy_source},
                session=session,
            )
            return identifier

    def place_hold(
        self,
        tenant_id: str,
        project_id: str,
        resource_type: str,
        resource_id: str,
        *,
        reason: str,
        authority_reference: str,
        actor_id: str,
    ) -> str:
        with self.database.session() as session:
            existing = session.scalar(
                select(LegalHoldRow).where(
                    LegalHoldRow.tenant_id == tenant_id,
                    LegalHoldRow.project_id == project_id,
                    LegalHoldRow.resource_type == resource_type,
                    LegalHoldRow.resource_id == resource_id,
                    LegalHoldRow.state == "active",
                )
            )
            if existing:
                return existing.hold_id
            if resource_type == "asset":
                ref = session.get(AssetRefRow, resource_id)
                if not ref or ref.tenant_id != tenant_id or ref.project_id != project_id:
                    raise NotFoundError("asset", resource_id)
                ref.legal_hold = True
            identifier = new_uuid()
            session.add(
                LegalHoldRow(
                    hold_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    reason=reason,
                    authority_reference=authority_reference,
                    state="active",
                    placed_by=actor_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="legal_hold:place",
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="allowed",
                details={"hold_id": identifier, "authority_reference": authority_reference, "reason": reason},
                session=session,
            )
            return identifier

    def release_hold(self, tenant_id: str, project_id: str, hold_id: str, *, actor_id: str) -> None:
        with self.database.session() as session:
            hold = session.get(LegalHoldRow, hold_id)
            if not hold or hold.tenant_id != tenant_id or hold.project_id != project_id:
                raise NotFoundError("legal_hold", hold_id)
            if hold.state != "active":
                return
            hold.state = "released"
            hold.released_by = actor_id
            hold.released_at = db_now()
            if hold.resource_type == "asset":
                active = session.scalar(
                    select(func.count()).select_from(LegalHoldRow).where(
                        LegalHoldRow.tenant_id == tenant_id,
                        LegalHoldRow.project_id == project_id,
                        LegalHoldRow.resource_type == "asset",
                        LegalHoldRow.resource_id == hold.resource_id,
                        LegalHoldRow.state == "active",
                        LegalHoldRow.hold_id != hold_id,
                    )
                ) or 0
                ref = session.get(AssetRefRow, hold.resource_id)
                if ref and not active:
                    ref.legal_hold = False
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="legal_hold:release",
                resource_type=hold.resource_type,
                resource_id=hold.resource_id,
                outcome="allowed",
                details={"hold_id": hold_id},
                session=session,
            )

    def plan_asset_deletion(self, tenant_id: str, project_id: str, asset_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            ref = session.get(AssetRefRow, asset_id)
            if not ref or ref.tenant_id != tenant_id or ref.project_id != project_id:
                raise NotFoundError("asset", asset_id)
            obj = session.get(AssetRow, ref.sha256)
            if not obj:
                raise ValidationError("OBJECT_REFERENCE_BROKEN", "asset metadata is missing")
            holds = list(
                session.scalars(
                    select(LegalHoldRow).where(
                        LegalHoldRow.tenant_id == tenant_id,
                        LegalHoldRow.project_id == project_id,
                        LegalHoldRow.state == "active",
                        LegalHoldRow.resource_type.in_(["asset", "project"]),
                    )
                )
            )
            matching_holds = [
                {"hold_id": row.hold_id, "resource_type": row.resource_type, "resource_id": row.resource_id, "authority_reference": row.authority_reference}
                for row in holds
                if (row.resource_type == "asset" and row.resource_id == asset_id)
                or (row.resource_type == "project" and row.resource_id == project_id)
            ]
            dependencies = self._dependencies(session, tenant_id, project_id, asset_id, ref.sha256)
            other_active_refs = session.scalar(
                select(func.count()).select_from(AssetRefRow).where(
                    AssetRefRow.sha256 == ref.sha256,
                    AssetRefRow.tombstoned_at.is_(None),
                    AssetRefRow.asset_id != asset_id,
                )
            ) or 0
            rule = self._retention_rule(session, tenant_id, project_id, ref.retention_class)
            age_days = max(0, (db_now().replace(tzinfo=None) - ref.created_at.replace(tzinfo=None)).days)
            minimum_met = not rule or age_days >= rule.minimum_days
            blockers: list[str] = []
            if ref.legal_hold or matching_holds:
                blockers.append("legal_hold_active")
            if not minimum_met:
                blockers.append("minimum_retention_not_met")
            if ref.tombstoned_at:
                blockers.append("already_tombstoned")
            snapshot = {
                "asset_id": asset_id,
                "sha256": ref.sha256,
                "dependencies": dependencies,
                "other_active_references": int(other_active_refs),
                "legal_holds": matching_holds,
                "retention_rule_id": rule.retention_rule_id if rule else None,
                "retention_rule_version": rule.version if rule else None,
                "retention_class": ref.retention_class,
                "age_days": age_days,
                "minimum_retention_met": minimum_met,
                "blockers": blockers,
            }
            return {
                "schema_version": "1.0.0",
                **snapshot,
                "dependency_snapshot_hash": canonical_sha256(snapshot),
                "eligible": not blockers,
                "physical_object_will_be_removed": int(other_active_refs) == 0,
                "required_controls": [
                    "dry_run",
                    "verified_backup_reference",
                    "independent_approval",
                    "unchanged_dependency_snapshot",
                    "audit_and_erasure_evidence",
                    "index_cache_export_dependency_review",
                ],
            }

    def request_asset_deletion(
        self,
        tenant_id: str,
        project_id: str,
        asset_id: str,
        *,
        backup_id: str,
        actor_id: str,
    ) -> str:
        plan = self.plan_asset_deletion(tenant_id, project_id, asset_id)
        if not plan["eligible"]:
            raise ConflictError("DELETION_INELIGIBLE", "asset deletion is blocked", {"blockers": plan["blockers"]})
        with self.database.session() as session:
            backup = session.get(BackupRunRow, backup_id)
            if not backup or backup.state != "verified" or backup.restore_rehearsed_at is None:
                raise ConflictError("VERIFIED_BACKUP_REQUIRED", "deletion requires a successfully rehearsed backup")
            identifier = new_uuid()
            session.add(
                DeletionRequestRow(
                    deletion_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_type="asset",
                    resource_id=asset_id,
                    dry_run_report=plan,
                    backup_reference=backup_id,
                    state="awaiting_approval",
                    requested_by=actor_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:request",
                resource_type="asset",
                resource_id=asset_id,
                outcome="allowed",
                details={"deletion_id": identifier, "backup_id": backup_id, "snapshot_hash": plan["dependency_snapshot_hash"]},
                session=session,
            )
            return identifier

    def approve_deletion(self, tenant_id: str, project_id: str, deletion_id: str, *, actor_id: str) -> None:
        with self.database.session() as session:
            row = session.get(DeletionRequestRow, deletion_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("deletion_request", deletion_id)
            if row.requested_by == actor_id:
                raise ConflictError("INDEPENDENT_APPROVER_REQUIRED", "requester cannot approve destructive deletion")
            if row.state != "awaiting_approval":
                raise ConflictError("DELETION_STATE_INVALID", "deletion request is not awaiting approval")
            row.approved_by = actor_id
            row.state = "approved"
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:approve",
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                outcome="allowed",
                details={"deletion_id": deletion_id, "requested_by": row.requested_by},
                session=session,
            )

    def execute_deletion(self, tenant_id: str, project_id: str, deletion_id: str, *, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(DeletionRequestRow, deletion_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("deletion_request", deletion_id)
            if row.state != "approved" or not row.approved_by:
                raise ConflictError("DELETION_NOT_APPROVED", "deletion request lacks independent approval")
            asset_id = row.resource_id
            expected_snapshot = str(row.dry_run_report["dependency_snapshot_hash"])
            ref = session.get(AssetRefRow, asset_id)
            if not ref:
                raise NotFoundError("asset", asset_id)
            obj = session.get(AssetRow, ref.sha256)
            key_ids = [str(obj.encryption_metadata.get("key_id"))] if obj and obj.encryption_metadata.get("key_id") else []
            backup_id = row.backup_reference
            approved_by = row.approved_by
        current = self.plan_asset_deletion(tenant_id, project_id, asset_id)
        if current["dependency_snapshot_hash"] != expected_snapshot:
            raise ConflictError(
                "DELETION_DEPENDENCIES_CHANGED",
                "deletion impact changed after approval; a new dry run is required",
                {"expected": expected_snapshot, "actual": current["dependency_snapshot_hash"]},
            )
        if not current["eligible"]:
            raise ConflictError("DELETION_INELIGIBLE", "asset deletion is now blocked", {"blockers": current["blockers"]})
        impact = self.assets.tombstone(tenant_id, project_id, asset_id, actor_id=actor_id, dry_run=False)
        with self.database.session() as session:
            row = session.get(DeletionRequestRow, deletion_id)
            assert row is not None
            rule = self._retention_rule(session, tenant_id, project_id, str(current["retention_class"]))
            deadline = db_now() + timedelta(days=rule.backup_expiry_days if rule else 30)
            residuals = [
                {"location_type": "verified_backup", "reference": backup_id, "access_state": "restricted", "expiry_deadline": deadline.isoformat()},
                *[{"location_type": "dependency", **item} for item in current["dependencies"]],
            ]
            evidence_body = {
                "deletion_id": deletion_id,
                "asset_id": asset_id,
                "sha256": current["sha256"],
                "impact": impact,
                "approved_by": approved_by,
                "executed_by": actor_id,
                "key_ids": key_ids,
                "residual_locations": residuals,
                "backup_expiry_deadline": deadline.isoformat(),
            }
            evidence_id = new_uuid()
            evidence_hash = canonical_sha256(evidence_body)
            session.add(
                DeletionEvidenceRow(
                    evidence_id=evidence_id,
                    deletion_id=deletion_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_type="asset",
                    resource_id=asset_id,
                    action="tombstone_and_object_erasure" if impact["physical_object_will_be_removed"] else "tombstone_shared_object_retained",
                    affected_references=current["dependencies"],
                    key_ids=key_ids,
                    residual_locations=residuals,
                    backup_expiry_deadline=deadline,
                    evidence_hash=evidence_hash,
                )
            )
            row.state = "executed"
            row.executed_at = db_now()
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="deletion:execute",
                resource_type="asset",
                resource_id=asset_id,
                outcome="allowed",
                details={"deletion_id": deletion_id, "evidence_id": evidence_id, "evidence_hash": evidence_hash, **impact},
                session=session,
            )
            return {**impact, "deletion_id": deletion_id, "evidence_id": evidence_id, "evidence_hash": evidence_hash, "backup_expiry_deadline": deadline.isoformat()}

    @staticmethod
    def _retention_rule(session: Any, tenant_id: str, project_id: str, retention_class: str) -> RetentionRuleRow | None:
        project = session.scalar(
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
        if project:
            return project
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
    def _dependencies(session: Any, tenant_id: str, project_id: str, asset_id: str, digest: str) -> list[dict[str, Any]]:
        dependencies: list[dict[str, Any]] = []
        excluded = {
            "assets",
            "asset_refs",
            "audit_events",
            "deletion_requests",
            "deletion_evidence",
            "backup_runs",
            "legal_holds",
            "retention_rules",
            "key_rotations",
            "usage_ledger",
            "quota_policies",
        }
        for table_name, table in Base.metadata.tables.items():
            if table_name in excluded:
                continue
            columns = table.c
            if "tenant_id" not in columns:
                continue
            statement = select(table).where(columns.tenant_id == tenant_id)
            if "project_id" in columns:
                statement = statement.where(columns.project_id == project_id)
            for row in session.execute(statement):
                mapping = dict(row._mapping)
                if _contains_reference(mapping, asset_id) or _contains_reference(mapping, digest):
                    primary = next((mapping[col.name] for col in table.primary_key.columns if mapping.get(col.name) is not None), "unknown")
                    dependencies.append({"table": table_name, "record_id": str(primary), "disposition": _dependency_disposition(table_name)})
        for export in session.scalars(select(ExportRow).where(ExportRow.tenant_id == tenant_id, ExportRow.project_id == project_id)):
            dependencies.append({"table": "exports", "record_id": export.export_id, "disposition": "must_be_invalidated_or_reissued", "status": export.status})
        return sorted(dependencies, key=lambda item: (str(item["table"]), str(item["record_id"])))


class BackupRecoveryService:
    """Local-profile backup plus isolated restore rehearsal and graph reconciliation."""

    def __init__(self, database: Database, preservation: PreservationService, assets: AssetService, audit: AuditService) -> None:
        self.database = database
        self.preservation = preservation
        self.assets = assets
        self.audit = audit

    def create_local_backup(self, destination: Path, *, actor_id: str) -> dict[str, Any]:
        manifest = self.preservation.backup_local(destination)
        identifier = new_uuid()
        fingerprint = _schema_fingerprint()
        with self.database.session() as session:
            session.add(
                BackupRunRow(
                    backup_id=identifier,
                    tenant_id=None,
                    profile="local-sqlite-cas",
                    backup_path=str(destination),
                    root_hash=str(manifest["root_hash"]),
                    schema_fingerprint=fingerprint,
                    state="created",
                    created_by=actor_id,
                    evidence={"backup_manifest": manifest},
                )
            )
            for tenant_id in session.scalars(select(TenantRow.tenant_id)):
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=None,
                    actor_id=actor_id,
                    action="backup:create",
                    resource_type="backup",
                    resource_id=identifier,
                    outcome="allowed",
                    details={"root_hash": manifest["root_hash"], "profile": "local-sqlite-cas"},
                    session=session,
                )
        return {"backup_id": identifier, **manifest}

    def verify_and_rehearse(self, backup_id: str, *, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(BackupRunRow, backup_id)
            if not row:
                raise NotFoundError("backup", backup_id)
            backup = Path(row.backup_path)
            expected_root = row.root_hash
        with tempfile.TemporaryDirectory(prefix="sip-restore-rehearsal-") as temporary:
            root = Path(temporary)
            database_path = root / "restored.sqlite3"
            store_path = root / "object-store"
            restored = PreservationService.restore_local_backup(backup, database_path, store_path)
            if restored["root_hash"] != expected_root:
                raise ValidationError("BACKUP_ROOT_MISMATCH", "restored root differs from recorded backup")
            connection = sqlite3.connect(database_path)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            if integrity != "ok":
                raise ValidationError("DATABASE_INTEGRITY_FAILED", str(integrity))
            target = Database(f"sqlite:///{database_path}")
            target_store = LocalContentAddressedStore(store_path, self.assets.store.cipher)
            object_checks: list[dict[str, Any]] = []
            orphan_refs: list[str] = []
            reconciliation: list[dict[str, Any]] = []
            with target.session() as session:
                assets = list(session.scalars(select(AssetRow)))
                for obj in assets:
                    payload = target_store.read_bytes(obj.sha256)
                    object_checks.append({"sha256": obj.sha256, "bytes": len(payload), "verified": True})
                for ref in session.scalars(select(AssetRefRow)):
                    if session.get(AssetRow, ref.sha256) is None:
                        orphan_refs.append(ref.asset_id)
                for operation in session.scalars(select(OperationRow).where(OperationRow.state.in_(["leased", "running"]))):
                    reconciliation.append({"operation_id": operation.operation_id, "required_action": "clear_lease_and_resume_from_checkpoint"})
                tenant_ids = list(session.scalars(select(TenantRow.tenant_id)))
            if orphan_refs:
                raise ValidationError("RESTORE_ORPHAN_ASSET_REFS", "restored database contains missing object references", {"asset_ids": orphan_refs})
            audit_checks = [AuditService(target, self.audit.signing_key).verify(tenant_id) for tenant_id in tenant_ids]
            evidence = {
                "database_integrity": integrity,
                "objects_verified": len(object_checks),
                "object_checks": object_checks,
                "audit_chains": audit_checks,
                "reconciliation_required": reconciliation,
                "schema_fingerprint": _schema_fingerprint(),
                "root_hash": restored["root_hash"],
                "write_reopen_allowed": not reconciliation,
            }
        with self.database.session() as session:
            row = session.get(BackupRunRow, backup_id)
            assert row is not None
            row.state = "verified" if not reconciliation else "verified_reconciliation_required"
            row.verified_at = db_now()
            row.restore_rehearsed_at = db_now()
            row.evidence = {**row.evidence, "restore_rehearsal": evidence}
            for tenant_id in session.scalars(select(TenantRow.tenant_id)):
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=None,
                    actor_id=actor_id,
                    action="backup:restore_rehearsal",
                    resource_type="backup",
                    resource_id=backup_id,
                    outcome="allowed",
                    details={"root_hash": expected_root, "objects_verified": len(object_checks), "write_reopen_allowed": not reconciliation},
                    session=session,
                )
        return {"backup_id": backup_id, "state": "verified" if not reconciliation else "verified_reconciliation_required", **evidence}


class KeyRotationService:
    def __init__(self, database: Database, assets: AssetService, audit: AuditService) -> None:
        self.database = database
        self.assets = assets
        self.audit = audit

    def rotate_local_envelope_key(self, *, new_master_key: bytes, new_key_id: str, actor_id: str) -> dict[str, Any]:
        new_cipher = EnvelopeCipher(new_master_key, new_key_id)
        result = self.assets.store.rotate_envelope_key(new_cipher)
        evidence_hash = canonical_sha256(result)
        rotation_id = new_uuid()
        with self.database.session() as session:
            for obj in session.scalars(select(AssetRow)):
                metadata_path = self.assets.store.path_for(obj.sha256).with_suffix(".meta.json")
                obj.encryption_metadata = json.loads(metadata_path.read_text())
            session.add(
                KeyRotationRow(
                    rotation_id=rotation_id,
                    old_key_id=str(result["old_key_id"]),
                    new_key_id=new_key_id,
                    object_count=int(result["object_count"]),
                    ciphertext_unchanged=bool(result["ciphertext_unchanged"]),
                    evidence_hash=evidence_hash,
                    state="committed",
                    rotated_by=actor_id,
                )
            )
            for tenant_id in session.scalars(select(TenantRow.tenant_id)):
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=None,
                    actor_id=actor_id,
                    action="encryption:key_rotate",
                    resource_type="key_rotation",
                    resource_id=rotation_id,
                    outcome="allowed",
                    details={"old_key_id": result["old_key_id"], "new_key_id": new_key_id, "object_count": result["object_count"], "ciphertext_unchanged": result["ciphertext_unchanged"], "evidence_hash": evidence_hash},
                    session=session,
                )
        return {"rotation_id": rotation_id, "evidence_hash": evidence_hash, **result}


class AdmissionController:
    """Database-backed local reference for quota and cost admission.

    Distributed profiles map the same contract to Redis atomic counters and a durable
    PostgreSQL cost ledger; this implementation stays deterministic for tests and edge use.
    """

    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def set_quota(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        resource_type: str,
        unit: str,
        period_seconds: int,
        soft_limit: float,
        hard_limit: float,
        actor_id: str,
    ) -> str:
        if period_seconds <= 0 or soft_limit < 0 or hard_limit <= 0 or soft_limit > hard_limit:
            raise ValidationError("QUOTA_INVALID", "quota values are invalid")
        with self.database.session() as session:
            existing = session.scalar(
                select(QuotaPolicyRow).where(
                    QuotaPolicyRow.tenant_id == tenant_id,
                    QuotaPolicyRow.project_id == project_id,
                    QuotaPolicyRow.resource_type == resource_type,
                )
            )
            identifier = existing.quota_id if existing else new_uuid()
            if existing:
                existing.unit = unit
                existing.period_seconds = period_seconds
                existing.soft_limit = soft_limit
                existing.hard_limit = hard_limit
                existing.active = True
                existing.created_by = actor_id
            else:
                session.add(QuotaPolicyRow(quota_id=identifier, tenant_id=tenant_id, project_id=project_id, resource_type=resource_type, unit=unit, period_seconds=period_seconds, soft_limit=soft_limit, hard_limit=hard_limit, active=True, created_by=actor_id))
            return identifier

    def admit_and_record(
        self,
        *,
        tenant_id: str,
        project_id: str,
        operation_id: str | None,
        resource_type: str,
        quantity: float,
        unit: str,
        unit_cost: float,
        currency: str,
        price_source_version: str,
        estimated: bool,
        actor_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if quantity < 0 or unit_cost < 0 or len(currency) != 3:
            raise ValidationError("USAGE_RECORD_INVALID", "usage or cost values are invalid")
        now = db_now()
        with self.database.session() as session:
            quota = session.scalar(
                select(QuotaPolicyRow).where(
                    QuotaPolicyRow.tenant_id == tenant_id,
                    QuotaPolicyRow.resource_type == resource_type,
                    QuotaPolicyRow.active.is_(True),
                    (QuotaPolicyRow.project_id == project_id) | (QuotaPolicyRow.project_id.is_(None)),
                ).order_by(QuotaPolicyRow.project_id.desc()).limit(1)
            )
            current = 0.0
            if quota:
                start = now - timedelta(seconds=quota.period_seconds)
                current = float(session.scalar(select(func.coalesce(func.sum(UsageLedgerRow.quantity), 0.0)).where(UsageLedgerRow.tenant_id == tenant_id, UsageLedgerRow.project_id == project_id, UsageLedgerRow.resource_type == resource_type, UsageLedgerRow.occurred_at >= start)) or 0.0)
                if unit != quota.unit:
                    raise ValidationError("QUOTA_UNIT_MISMATCH", "usage unit does not match quota")
                if current + quantity > quota.hard_limit:
                    self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="quota:admit", resource_type=resource_type, resource_id=operation_id or "unbound", outcome="denied", details={"current": current, "requested": quantity, "hard_limit": quota.hard_limit}, session=session)
                    raise ConflictError("QUOTA_HARD_LIMIT", "operation exceeds the configured hard quota", {"current": current, "requested": quantity, "hard_limit": quota.hard_limit})
            usage_id = new_uuid()
            session.add(UsageLedgerRow(usage_id=usage_id, tenant_id=tenant_id, project_id=project_id, operation_id=operation_id, resource_type=resource_type, quantity=quantity, unit=unit, unit_cost=unit_cost, currency=currency.upper(), price_source_version=price_source_version, estimated=estimated, metadata_json=metadata or {}, occurred_at=now))
            projected = current + quantity
            return {"admitted": True, "usage_id": usage_id, "current": current, "projected": projected, "soft_limit_exceeded": bool(quota and projected > quota.soft_limit), "hard_limit": quota.hard_limit if quota else None, "attributed_cost": quantity * unit_cost, "currency": currency.upper(), "price_source_version": price_source_version}


def _contains_reference(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_reference(item, target) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_reference(item, target) for item in value)
    return str(value) == target


def _dependency_disposition(table_name: str) -> str:
    if table_name in {"representations", "representation_bindings", "scene_commits"}:
        return "withdraw_or_supersede_derivative"
    if table_name in {"search_documents"}:
        return "purge_index"
    if table_name in {"notifications"}:
        return "redact_notification_payload"
    if table_name in {"construction_records", "memory_records", "collaboration_comments", "collaboration_tasks"}:
        return "review_shared_rights_and_redact_or_tombstone"
    return "review_dependency"


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
