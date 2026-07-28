from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, or_, select
from sqlalchemy.orm import Session

from .assets import AssetService
from .canonical import canonical_sha256, merkle_root, new_uuid, sha256_bytes, sha256_file
from .database import (
    AssetRefRow,
    AgentProposalRow,
    AnchorRemapRow,
    AssertionRow,
    AssetRow,
    AuditEventRow,
    CollaborationCommentRow,
    CollaborationTaskRow,
    ConsentGrantRow,
    ConstructionRecordRow,
    CoordinateFrameRow,
    Database,
    DerivationEventRow,
    EvidenceRecordRow,
    GeometryAssetManifestRow,
    DeletionEvidenceRow,
    DeletionRequestRow,
    ExportRow,
    LegalHoldRow,
    MeasurementRow,
    MemoryRecordRow,
    ModelManifestRow,
    NotificationRow,
    OperationRow,
    OutboxEventRow,
    ProjectRow,
    ProviderManifestRow,
    QuotaPolicyRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    RetentionRuleRow,
    RoleBindingRow,
    SavedQueryRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
    SceneTagRow,
    SpatialAnnotationRow,
    SpatialTransformRow,
    SearchDocumentRow,
    TenantRow,
    UsageLedgerRow,
)
from .errors import ConflictError, NotFoundError, ValidationError
from .models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from .temporal import db_now


# These rows are authoritative or reviewable project state and are safe to make
# operational after a verified import. Security identities/roles, executable provider
# approvals, queued work, notifications, derived indexes, and audit signatures are
# intentionally excluded from native replay.
_NATIVE_REPLAY_MODELS = (
    CoordinateFrameRow,
    SpatialTransformRow,
    EvidenceRecordRow,
    AssertionRow,
    DerivationEventRow,
    SceneCommitRow,
    SceneBranchRow,
    SceneTagRow,
    SceneEntityRow,
    RepresentationAssetRow,
    GeometryAssetManifestRow,
    RepresentationBindingRow,
    SpatialAnnotationRow,
    AnchorRemapRow,
    MeasurementRow,
    ConsentGrantRow,
    ConstructionRecordRow,
    MemoryRecordRow,
    CollaborationCommentRow,
    CollaborationTaskRow,
    RetentionRuleRow,
    LegalHoldRow,
)

# These records remain available inside the immutable source package but are not
# activated in the destination. This avoids replaying stale permissions, jobs, events,
# notifications, deletion operations, derived indexes, or cost controls.
_ARCHIVED_PROJECT_MODELS = (
    RoleBindingRow,
    SavedQueryRow,
    AgentProposalRow,
    AuditEventRow,
    OperationRow,
    OutboxEventRow,
    SearchDocumentRow,
    NotificationRow,
    ExportRow,
    DeletionRequestRow,
    DeletionEvidenceRow,
    QuotaPolicyRow,
    UsageLedgerRow,
)

_PRIMARY_KEY_FIELDS: dict[str, str] = {
    model.__tablename__: next(column.name for column in model.__table__.columns if column.primary_key)
    for model in (*_NATIVE_REPLAY_MODELS, *_ARCHIVED_PROJECT_MODELS, ProviderManifestRow, ModelManifestRow)
}

_ID_CATEGORIES: dict[str, str] = {
    CoordinateFrameRow.__tablename__: "frame",
    SpatialTransformRow.__tablename__: "spatial_transform",
    GeometryAssetManifestRow.__tablename__: "geometry_manifest",
    EvidenceRecordRow.__tablename__: "evidence",
    AssertionRow.__tablename__: "assertion",
    DerivationEventRow.__tablename__: "derivation",
    SpatialAnnotationRow.__tablename__: "annotation",
    AnchorRemapRow.__tablename__: "anchor_remap",
    SceneTagRow.__tablename__: "scene_tag",
    SceneCommitRow.__tablename__: "commit",
    SceneBranchRow.__tablename__: "branch",
    SceneEntityRow.__tablename__: "entity",
    RepresentationAssetRow.__tablename__: "representation",
    RepresentationBindingRow.__tablename__: "representation_binding",
    MeasurementRow.__tablename__: "measurement",
    ConsentGrantRow.__tablename__: "consent",
    ConstructionRecordRow.__tablename__: "construction",
    MemoryRecordRow.__tablename__: "memory",
    CollaborationCommentRow.__tablename__: "comment",
    CollaborationTaskRow.__tablename__: "task",
    RetentionRuleRow.__tablename__: "retention_rule",
    LegalHoldRow.__tablename__: "legal_hold",
}


class PreservationService:
    FORMAT_VERSION = "1.1.0"
    DOMAIN_SCHEMA_VERSION = "1.1.0"

    def __init__(self, database: Database, assets: AssetService) -> None:
        self.database = database
        self.assets = assets

    def export_project(self, tenant_id: str, project_id: str, destination: Path, *, actor_id: str) -> dict[str, Any]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sip-preservation-") as temporary:
            root = Path(temporary) / "package"
            (root / "objects").mkdir(parents=True)
            (root / "evidence").mkdir(parents=True)
            (root / "governance").mkdir(parents=True)
            with self.database.session() as session:
                tenant = session.get(TenantRow, tenant_id)
                project = session.get(ProjectRow, project_id)
                if not tenant or not project or project.tenant_id != tenant_id:
                    raise NotFoundError("project", project_id)

                table_rows = {
                    model.__tablename__: _project_rows(session, model, tenant_id, project_id)
                    for model in _NATIVE_REPLAY_MODELS
                }
                archived_rows = {
                    model.__tablename__: _project_rows(session, model, tenant_id, project_id)
                    for model in _ARCHIVED_PROJECT_MODELS
                }
                governance_rows = _referenced_governance_rows(session, table_rows)

                refs = list(
                    session.scalars(
                        select(AssetRefRow).where(
                            AssetRefRow.tenant_id == tenant_id,
                            AssetRefRow.project_id == project_id,
                            AssetRefRow.tombstoned_at.is_(None),
                        )
                    )
                )
                refs.sort(key=lambda value: value.asset_id)
                assets_manifest: list[dict[str, Any]] = []
                for ref in refs:
                    obj = session.get(AssetRow, ref.sha256)
                    if not obj:
                        raise ValidationError("EXPORT_OBJECT_MISSING", "asset object metadata is missing", {"asset_id": ref.asset_id})
                    payload = self.assets.store.read_bytes(ref.sha256)
                    if sha256_bytes(payload) != ref.sha256:
                        raise ValidationError("EXPORT_OBJECT_INTEGRITY_FAILED", "asset plaintext does not match its content identity", {"asset_id": ref.asset_id})
                    object_path = root / "objects" / ref.sha256
                    if not object_path.exists():
                        object_path.write_bytes(payload)
                    assets_manifest.append({"reference": _serialize_model(ref), "object": _portable_asset_object(obj)})

                table_digests = {name: canonical_sha256(rows) for name, rows in sorted(table_rows.items())}
                archived_digests = {name: canonical_sha256(rows) for name, rows in sorted(archived_rows.items())}
                governance_digests = {name: canonical_sha256(rows) for name, rows in sorted(governance_rows.items())}
                archived_document = {
                    "schema": "sip.archived-project-records/v1",
                    "activation_policy": "preserved_only_not_replayed",
                    "tables": archived_rows,
                    "table_digests": archived_digests,
                }
                governance_document = {
                    "schema": "sip.preserved-governance/v1",
                    "activation_policy": "deny_by_default_reapproval_required",
                    "tables": governance_rows,
                    "table_digests": governance_digests,
                }
                (root / "evidence" / "archived-project-records.json").write_text(
                    json.dumps(archived_document, indent=2, sort_keys=True, default=_json_default) + "\n"
                )
                (root / "governance" / "provider-model-manifests.json").write_text(
                    json.dumps(governance_document, indent=2, sort_keys=True, default=_json_default) + "\n"
                )
                package = {
                    "format": "sip-open-preservation",
                    "format_version": self.FORMAT_VERSION,
                    "domain_schema_version": self.DOMAIN_SCHEMA_VERSION,
                    "created_at": db_now().isoformat(),
                    "created_by": actor_id,
                    "tenant": _serialize_model(tenant),
                    "project": _serialize_model(project),
                    "assets": assets_manifest,
                    "tables": table_rows,
                    "native_replay_tables": sorted(table_rows),
                    "table_digests": table_digests,
                    "archived_records": {
                        "path": "evidence/archived-project-records.json",
                        "tables": sorted(archived_rows),
                        "table_digests": archived_digests,
                    },
                    "preserved_governance": {
                        "path": "governance/provider-model-manifests.json",
                        "tables": sorted(governance_rows),
                        "table_digests": governance_digests,
                        "automatically_activated": False,
                    },
                    "restore_policy": {
                        "native_rows_replayed": True,
                        "stable_ids_preserved_unless_collision": True,
                        "security_identities_and_roles_replayed": False,
                        "provider_and_model_approvals_replayed": False,
                        "queued_operations_and_events_replayed": False,
                        "derived_search_indexes_replayed": False,
                        "historical_audit_rows_inserted_into_destination_chain": False,
                        "source_package_retained_as_immutable_evidence": True,
                    },
                    "truth_rules": {
                        "metric_visual_interaction_design_evidence_separate": True,
                        "generated_content_labeled": True,
                        "policy_records_included": True,
                        "provider_reapproval_required": True,
                    },
                }
            (root / "metadata.json").write_text(json.dumps(package, indent=2, sort_keys=True, default=_json_default) + "\n")
            entries = [(str(path.relative_to(root)), sha256_file(path)) for path in root.rglob("*") if path.is_file()]
            manifest = {
                "format": "sip-open-preservation-manifest",
                "format_version": self.FORMAT_VERSION,
                "files": [{"path": path, "sha256": digest} for path, digest in sorted(entries)],
                "root_hash": merkle_root(entries),
            }
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(root))
        export_id = new_uuid()
        with self.database.session() as session:
            session.add(
                ExportRow(
                    export_id=export_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    format="sip-open-preservation",
                    status="complete",
                    manifest_json=manifest,
                    root_hash=manifest["root_hash"],
                    path=str(destination),
                    created_by=actor_id,
                )
            )
        return {
            "export_id": export_id,
            "path": str(destination),
            "domain_schema_version": self.DOMAIN_SCHEMA_VERSION,
            "native_table_counts": {name: len(rows) for name, rows in table_rows.items()},
            "archived_table_counts": {name: len(rows) for name, rows in archived_rows.items()},
            **manifest,
        }

    @staticmethod
    def verify_export(path: Path) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="sip-verify-export-") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(path) as archive:
                _safe_extract_zip(archive, root)
            manifest_path = root / "manifest.json"
            if not manifest_path.exists():
                raise ValidationError("EXPORT_MANIFEST_MISSING", "preservation package has no manifest")
            manifest = json.loads(manifest_path.read_text())
            checks: list[dict[str, Any]] = []
            entries: list[tuple[str, str]] = []
            for item in manifest.get("files", []):
                target = root / item["path"]
                actual = sha256_file(target) if target.is_file() else None
                ok = actual == item["sha256"]
                checks.append({"path": item["path"], "expected": item["sha256"], "actual": actual, "valid": ok})
                if not ok:
                    raise ValidationError("EXPORT_FILE_INTEGRITY_FAILED", "preservation file hash mismatch", checks[-1])
                entries.append((item["path"], actual))
            actual_root = merkle_root(entries)
            if actual_root != manifest.get("root_hash"):
                raise ValidationError("EXPORT_ROOT_INTEGRITY_FAILED", "preservation root hash mismatch")
            metadata_path = root / "metadata.json"
            if not metadata_path.exists():
                raise ValidationError("EXPORT_METADATA_MISSING", "preservation package has no metadata")
            metadata = json.loads(metadata_path.read_text())
            if metadata.get("format") != "sip-open-preservation":
                raise ValidationError("EXPORT_FORMAT_UNSUPPORTED", "package is not a SIP open preservation export")
            _verify_supported_version(metadata.get("format_version", "0.0.0"), PreservationService.FORMAT_VERSION, "format")
            _verify_supported_version(
                metadata.get("domain_schema_version", metadata.get("format_version", "1.0.0")),
                PreservationService.DOMAIN_SCHEMA_VERSION,
                "domain schema",
            )
            _verify_table_digests(metadata.get("tables", {}), metadata.get("table_digests", {}), required=bool(metadata.get("native_replay_tables")))
            for descriptor_name in ("archived_records", "preserved_governance"):
                descriptor = metadata.get(descriptor_name)
                if not descriptor:
                    continue
                source = root / descriptor["path"]
                if not source.is_file():
                    raise ValidationError("EXPORT_EVIDENCE_MISSING", f"{descriptor_name} evidence file is missing")
                document = json.loads(source.read_text())
                _verify_table_digests(document.get("tables", {}), descriptor.get("table_digests", {}), required=True)
            return {
                "valid": True,
                "root_hash": actual_root,
                "files": len(checks),
                "metadata": metadata,
                "checks": checks,
                "package_sha256": sha256_file(path),
            }

    def import_project(
        self,
        path: Path,
        *,
        new_tenant_id: str | None = None,
        new_project_id: str | None = None,
        actor_id: str,
    ) -> dict[str, Any]:
        verified = self.verify_export(path)
        metadata = verified["metadata"]
        tenant_data = metadata["tenant"]
        project_data = metadata["project"]
        tenant_id = new_tenant_id or tenant_data["tenant_id"]
        project_id = new_project_id or project_data["project_id"]
        native_tables = metadata.get("native_replay_tables")
        if not native_tables:
            return self._import_legacy_snapshot(
                path,
                verified=verified,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
            )
        unknown = sorted(set(native_tables) - {_model.__tablename__ for _model in _NATIVE_REPLAY_MODELS})
        if unknown:
            raise ValidationError(
                "IMPORT_NATIVE_TABLE_UNSUPPORTED",
                "package requests native replay for unsupported tables",
                {"tables": unknown},
            )

        with tempfile.TemporaryDirectory(prefix="sip-import-") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(path) as archive:
                _safe_extract_zip(archive, root)
            with self.database.session() as session:
                _create_import_scope(session, tenant_id, project_id, tenant_data, project_data)
                maps: dict[str, dict[str, str]] = {category: {} for category in set(_ID_CATEGORIES.values()) | {"asset", "scene"}}
                asset_results = self._restore_assets(
                    session,
                    root,
                    metadata.get("assets", []),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    maps=maps,
                )
                tables = metadata.get("tables", {})
                _allocate_replay_ids(session, tables, maps)
                _allocate_scene_ids(tables, maps)
                replay_counts, unresolved = _replay_native_rows(
                    session,
                    tables,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    source_root_hash=verified["root_hash"],
                    maps=maps,
                )
                primary_scene_id, primary_commit_id, primary_snapshot_hash = _primary_scene_head(session, tenant_id, project_id)
                session.flush()

        package_asset = self.assets.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=path.read_bytes(),
            media_type="application/vnd.sip.preservation+zip",
            original_name=path.name,
            classification=_classification(project_data.get("classification", "internal")),
            retention_class="preservation_master",
            source_class=SourceClass.VERIFIED,
            authority_class=AuthorityClass.EVIDENCE,
            provenance=ProvenanceRef(
                source_ids=[f"preservation-root:{verified['root_hash']}"],
                output_hash=verified["package_sha256"],
                validation_result_id=f"verified:{verified['root_hash']}",
            ),
            actor_id=actor_id,
        )
        return {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "scene_id": primary_scene_id,
            "commit_id": primary_commit_id,
            "source_root_hash": verified["root_hash"],
            "semantic_snapshot_hash": primary_snapshot_hash,
            "domain_schema_version": metadata.get("domain_schema_version", metadata.get("format_version")),
            "native_replay": True,
            "replayed_counts": replay_counts,
            "restored_assets": asset_results,
            "preservation_package_asset_id": package_asset.asset_id,
            "preservation_package_sha256": package_asset.sha256,
            "id_maps": maps,
            "unresolved_references": unresolved,
            "non_activated_evidence": {
                "archived_tables": metadata.get("archived_records", {}).get("tables", []),
                "governance_tables": metadata.get("preserved_governance", {}).get("tables", []),
                "provider_model_reapproval_required": True,
                "security_bindings_replayed": False,
                "search_reindex_required": True,
            },
        }

    def _restore_assets(
        self,
        session: Session,
        root: Path,
        assets: list[dict[str, Any]],
        *,
        tenant_id: str,
        project_id: str,
        actor_id: str,
        maps: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        seen: set[str] = set()
        hashes: list[str] = []
        remapped = 0
        for asset in assets:
            ref_data = asset["reference"]
            obj_data = asset["object"]
            old_asset_id = ref_data["asset_id"]
            if old_asset_id in seen:
                raise ValidationError("IMPORT_DUPLICATE_ID", "asset identifier is duplicated in the package", {"asset_id": old_asset_id})
            seen.add(old_asset_id)
            digest = obj_data["sha256"]
            object_path = root / "objects" / digest
            if not object_path.is_file():
                raise ValidationError("IMPORT_OBJECT_MISSING", "preservation object is missing", {"sha256": digest})
            payload = object_path.read_bytes()
            if sha256_bytes(payload) != digest:
                raise ValidationError("IMPORT_OBJECT_INTEGRITY_FAILED", "preservation object does not match its content hash", {"sha256": digest})
            encryption_metadata = self.assets.store.write_bytes(digest, payload)
            existing_object = session.get(AssetRow, digest)
            if existing_object is None:
                session.add(
                    AssetRow(
                        sha256=digest,
                        byte_count=len(payload),
                        media_type=obj_data["media_type"],
                        storage_key=self.assets.store.storage_key(digest),
                        encryption_metadata=encryption_metadata,
                        created_at=_parse_datetime(obj_data.get("created_at")) or db_now(),
                    )
                )
                session.flush()
            elif existing_object.byte_count != len(payload):
                raise ConflictError("CAS_METADATA_CONFLICT", "stored object metadata conflicts with preservation payload")
            asset_id = _collision_safe_id(session, AssetRefRow, old_asset_id)
            if asset_id != old_asset_id:
                remapped += 1
            maps["asset"][old_asset_id] = asset_id
            provenance = _remap_json(ref_data.get("provenance_json", {}), maps)
            provenance = {
                **provenance,
                "preservation_import": {
                    "source_asset_id": old_asset_id,
                    "source_sha256": digest,
                },
            }
            legacy_authority = ref_data["authority_class"]
            normalized_authority = (
                "derived_non_authoritative" if legacy_authority == "interaction" else legacy_authority
            )
            if normalized_authority != legacy_authority:
                provenance["authority_migration"] = {
                    "source_value": legacy_authority,
                    "normalized_value": normalized_authority,
                    "reason": "legacy interaction proxy authority was non-normative",
                }
            session.add(
                AssetRefRow(
                    asset_id=asset_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    sha256=digest,
                    original_name=ref_data["original_name"],
                    classification=ref_data["classification"],
                    retention_class=ref_data["retention_class"],
                    source_class=ref_data["source_class"],
                    authority_class=normalized_authority,
                    provenance_json=provenance,
                    legal_hold=bool(ref_data.get("legal_hold", False)),
                    created_by=ref_data.get("created_by") or actor_id,
                    created_at=_parse_datetime(ref_data.get("created_at")) or db_now(),
                    tombstoned_at=None,
                )
            )
            hashes.append(digest)
            session.flush()
        return {"count": len(assets), "unique_objects": len(set(hashes)), "remapped_ids": remapped}

    def _import_legacy_snapshot(
        self,
        path: Path,
        *,
        verified: dict[str, Any],
        tenant_id: str,
        project_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        metadata = verified["metadata"]
        tenant_data = metadata["tenant"]
        project_data = metadata["project"]
        with tempfile.TemporaryDirectory(prefix="sip-import-legacy-") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(path) as archive:
                _safe_extract_zip(archive, root)
            with self.database.session() as session:
                _create_import_scope(session, tenant_id, project_id, tenant_data, project_data)
                maps: dict[str, dict[str, str]] = {"asset": {}, "scene": {}}
                asset_results = self._restore_assets(
                    session,
                    root,
                    metadata.get("assets", []),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    maps=maps,
                )
                snapshot = {
                    "schema_version": "legacy-preservation-import/v1",
                    "imported_tables": metadata.get("tables", {}),
                    "asset_id_map": maps["asset"],
                    "source_root_hash": verified["root_hash"],
                    "native_replay": False,
                }
                commit_id = new_uuid()
                scene_id = new_uuid()
                snapshot_hash = canonical_sha256(snapshot)
                session.add(
                    SceneCommitRow(
                        commit_id=commit_id,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        scene_id=scene_id,
                        branch="main",
                        parent_ids_json=[],
                        message="Legacy open preservation package import",
                        semantic_snapshot_json=snapshot,
                        snapshot_hash=snapshot_hash,
                        created_by=actor_id,
                    )
                )
                session.add(
                    SceneBranchRow(
                        branch_id=new_uuid(),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        scene_id=scene_id,
                        name="main",
                        head_commit_id=commit_id,
                    )
                )
        package_asset = self.assets.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=path.read_bytes(),
            media_type="application/vnd.sip.preservation+zip",
            original_name=path.name,
            classification=_classification(project_data.get("classification", "internal")),
            retention_class="preservation_master",
            source_class=SourceClass.VERIFIED,
            authority_class=AuthorityClass.EVIDENCE,
            provenance=ProvenanceRef(source_ids=[f"preservation-root:{verified['root_hash']}"], output_hash=verified["package_sha256"]),
            actor_id=actor_id,
        )
        return {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "commit_id": commit_id,
            "source_root_hash": verified["root_hash"],
            "semantic_snapshot_hash": snapshot_hash,
            "native_replay": False,
            "restored_assets": asset_results,
            "preservation_package_asset_id": package_asset.asset_id,
        }

    def backup_local(self, destination: Path) -> dict[str, Any]:
        source_db = self.database.sqlite_path
        if source_db is None:
            raise ValidationError("LOCAL_BACKUP_PROFILE_ONLY", "local backup requires a SQLite database")
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        database_copy = destination / "database.sqlite3"
        source = sqlite3.connect(source_db)
        target = sqlite3.connect(database_copy)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        self.assets.store.copy_to(destination / "object-store")
        entries = [(str(path.relative_to(destination)), sha256_file(path)) for path in destination.rglob("*") if path.is_file()]
        manifest = {
            "format": "sip-local-backup",
            "format_version": self.FORMAT_VERSION,
            "created_at": db_now().isoformat(),
            "files": [{"path": path, "sha256": digest} for path, digest in sorted(entries)],
            "root_hash": merkle_root(entries),
        }
        (destination / "backup-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest

    @staticmethod
    def restore_local_backup(backup: Path, database_path: Path, store_path: Path) -> dict[str, Any]:
        manifest_path = backup / "backup-manifest.json"
        if not manifest_path.exists():
            raise ValidationError("BACKUP_MANIFEST_MISSING", "backup manifest is missing")
        manifest = json.loads(manifest_path.read_text())
        entries: list[tuple[str, str]] = []
        checks: list[dict[str, Any]] = []
        for item in manifest.get("files", []):
            path = backup / item["path"]
            actual = sha256_file(path) if path.is_file() else None
            valid = actual == item["sha256"]
            checks.append({"path": item["path"], "expected": item["sha256"], "actual": actual, "valid": valid})
            if not valid:
                raise ValidationError("BACKUP_INTEGRITY_FAILED", "backup file integrity check failed", checks[-1])
            entries.append((item["path"], actual))
        actual_root = merkle_root(entries)
        if actual_root != manifest.get("root_hash"):
            raise ValidationError("BACKUP_INTEGRITY_FAILED", "backup root hash does not match")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / "database.sqlite3", database_path)
        if store_path.exists():
            shutil.rmtree(store_path)
        shutil.copytree(backup / "object-store", store_path)
        return {"root_hash": actual_root, "checks": checks, "database_path": str(database_path), "store_path": str(store_path)}


def _project_rows(session: Session, model: type[Any], tenant_id: str, project_id: str) -> list[dict[str, Any]]:
    table = model.__table__
    if "tenant_id" not in table.c:
        return []
    conditions = [table.c.tenant_id == tenant_id]
    if "project_id" in table.c:
        # Retention and authorization rows may be tenant-wide. They are preserved in
        # the archive but only project-scoped native policy rows are replayed.
        if model in _NATIVE_REPLAY_MODELS:
            conditions.append(table.c.project_id == project_id)
        else:
            conditions.append(or_(table.c.project_id == project_id, table.c.project_id.is_(None)))
    rows = list(session.scalars(select(model).where(*conditions)))
    key = _PRIMARY_KEY_FIELDS[model.__tablename__]
    rows.sort(key=lambda value: str(getattr(value, key)))
    return [_serialize_model(row) for row in rows]


def _referenced_governance_rows(session: Session, tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    provider_ids = {row.get("provider_id") for row in tables.get("representations", []) if row.get("provider_id")}
    model_ids: set[str] = set()
    for row in tables.get("memory_records", []):
        lineage = row.get("generated_lineage_json") or {}
        if lineage.get("model_manifest_id"):
            model_ids.add(lineage["model_manifest_id"])
    for row in tables.get("representations", []):
        provenance = row.get("provenance_json") or {}
        if provenance.get("model_manifest_id"):
            model_ids.add(provenance["model_manifest_id"])
    providers = [session.get(ProviderManifestRow, identifier) for identifier in sorted(provider_ids)]
    models = [session.get(ModelManifestRow, identifier) for identifier in sorted(model_ids)]
    return {
        ProviderManifestRow.__tablename__: [_serialize_model(row) for row in providers if row is not None],
        ModelManifestRow.__tablename__: [_serialize_model(row) for row in models if row is not None],
    }


def _portable_asset_object(row: AssetRow) -> dict[str, Any]:
    # Storage keys and encryption envelopes are deliberately deployment-local. The
    # preservation object contains verified plaintext and is re-encrypted on import.
    return {
        "sha256": row.sha256,
        "byte_count": row.byte_count,
        "media_type": row.media_type,
        "created_at": _json_default(row.created_at),
        "content_encoding": "identity",
        "encryption": "destination_managed_on_import",
    }


def _create_import_scope(
    session: Session,
    tenant_id: str,
    project_id: str,
    tenant_data: dict[str, Any],
    project_data: dict[str, Any],
) -> None:
    if session.get(ProjectRow, project_id):
        raise ConflictError("IMPORT_PROJECT_EXISTS", "destination project already exists")
    tenant = session.get(TenantRow, tenant_id)
    if tenant is None:
        session.add(
            TenantRow(
                tenant_id=tenant_id,
                name=tenant_data["name"],
                status="active",
                created_at=_parse_datetime(tenant_data.get("created_at")) or db_now(),
            )
        )
        session.flush()
    session.add(
        ProjectRow(
            project_id=project_id,
            tenant_id=tenant_id,
            name=project_data["name"],
            vertical=project_data.get("vertical", "platform"),
            classification=project_data.get("classification", "internal"),
            status="active",
            created_at=_parse_datetime(project_data.get("created_at")) or db_now(),
        )
    )
    session.flush()


def _allocate_replay_ids(session: Session, tables: dict[str, list[dict[str, Any]]], maps: dict[str, dict[str, str]]) -> None:
    for model in _NATIVE_REPLAY_MODELS:
        table_name = model.__tablename__
        primary_key = _PRIMARY_KEY_FIELDS[table_name]
        category = _ID_CATEGORIES[table_name]
        seen: set[str] = set()
        for row in tables.get(table_name, []):
            old = row.get(primary_key)
            if not isinstance(old, str) or not old:
                raise ValidationError("IMPORT_PRIMARY_KEY_INVALID", "native replay row has an invalid primary key", {"table": table_name})
            if old in seen:
                raise ValidationError("IMPORT_DUPLICATE_ID", "native replay table contains duplicate identifiers", {"table": table_name, "id": old})
            seen.add(old)
            maps[category][old] = _collision_safe_id(session, model, old)


def _allocate_scene_ids(tables: dict[str, list[dict[str, Any]]], maps: dict[str, dict[str, str]]) -> None:
    scene_ids = {
        row["scene_id"]
        for table_name in (
            "scene_commits", "scene_branches", "scene_tags", "scene_entities", "representations",
            "geometry_asset_manifests", "representation_bindings", "spatial_annotations", "anchor_remaps", "measurements",
        )
        for row in tables.get(table_name, [])
        if isinstance(row.get("scene_id"), str) and row["scene_id"]
    }
    # Scene identifiers are project-scoped rather than table primary keys. Keeping them
    # unchanged preserves semantic identity even when another project uses the same ID.
    maps["scene"].update({identifier: identifier for identifier in scene_ids})


def _replay_native_rows(
    session: Session,
    tables: dict[str, list[dict[str, Any]]],
    *,
    tenant_id: str,
    project_id: str,
    actor_id: str,
    source_root_hash: str,
    maps: dict[str, dict[str, str]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: dict[str, int] = {}
    for model in _NATIVE_REPLAY_MODELS:
        table_name = model.__tablename__
        rows = tables.get(table_name, [])
        for source in rows:
            values = _replay_values(
                model,
                source,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                source_root_hash=source_root_hash,
                maps=maps,
            )
            session.add(model(**values))
        if rows:
            session.flush()
        counts[table_name] = len(rows)
    unresolved = _find_unresolved_references(tables, maps)
    return counts, unresolved


def _replay_values(
    model: type[Any],
    source: dict[str, Any],
    *,
    tenant_id: str,
    project_id: str,
    actor_id: str,
    source_root_hash: str,
    maps: dict[str, dict[str, str]],
) -> dict[str, Any]:
    table_name = model.__tablename__
    primary_key = _PRIMARY_KEY_FIELDS[table_name]
    category = _ID_CATEGORIES[table_name]
    values: dict[str, Any] = {}
    for column in model.__table__.columns:
        name = column.name
        if name not in source:
            continue
        value = source[name]
        if isinstance(column.type, DateTime):
            value = _parse_datetime(value)
        values[name] = value
    values[primary_key] = maps[category][source[primary_key]]
    if "tenant_id" in model.__table__.c:
        values["tenant_id"] = tenant_id
    if "project_id" in model.__table__.c:
        values["project_id"] = project_id

    if model is CoordinateFrameRow:
        values["parent_frame_id"] = _mapped(maps, "frame", source.get("parent_frame_id"))
        values["supersedes_frame_id"] = _mapped(maps, "frame", source.get("supersedes_frame_id"))
        values["geodetic_json"] = _remap_json(source.get("geodetic_json"), maps)
        values["metadata_json"] = _remap_json(source.get("metadata_json", {}), maps)
    elif model is SpatialTransformRow:
        values["source_frame_id"] = _mapped(maps, "frame", source.get("source_frame_id"))
        values["target_frame_id"] = _mapped(maps, "frame", source.get("target_frame_id"))
        values["supersedes_transform_id"] = _mapped(maps, "spatial_transform", source.get("supersedes_transform_id"))
        for name in (
            "residual_summary_json",
            "uncertainty_json",
            "grid_resources_json",
            "metadata_json",
        ):
            default = [] if name == "grid_resources_json" else {}
            values[name] = _remap_json(source.get(name, default), maps)
    elif model is EvidenceRecordRow:
        values["asset_id"] = _mapped(maps, "asset", source.get("asset_id"))
        values["location_context_json"] = _remap_json(source.get("location_context_json", {}), maps)
        values["relevant_region_json"] = _remap_json(source.get("relevant_region_json", {}), maps)
        values["chain_of_custody_json"] = _remap_json(source.get("chain_of_custody_json", []), maps)
        values["consent_scope_json"] = _remap_json(source.get("consent_scope_json", {}), maps)
        values["access_policy_json"] = _remap_json(source.get("access_policy_json", {}), maps)
        values["policy_json"] = _remap_json(source.get("policy_json", {}), maps)
    elif model is AssertionRow:
        values["subject_id"] = _mapped_any(maps, source.get("subject_id"))
        values["object_json"] = _remap_json(source.get("object_json"), maps)
        values["evidence_ids_json"] = [_mapped(maps, "evidence", item) for item in source.get("evidence_ids_json", [])]
        values["conflicts_with_json"] = [_mapped(maps, "assertion", item) for item in source.get("conflicts_with_json", [])]
        values["supersedes_assertion_id"] = _mapped(maps, "assertion", source.get("supersedes_assertion_id"))
    elif model is DerivationEventRow:
        values["input_ids_json"] = [_mapped_any(maps, item) for item in source.get("input_ids_json", [])]
        values["output_ids_json"] = [_mapped_any(maps, item) for item in source.get("output_ids_json", [])]
        values["software_json"] = _remap_json(source.get("software_json", {}), maps)
        values["quality_json"] = _remap_json(source.get("quality_json", {}), maps)
        values["validation_json"] = _remap_json(source.get("validation_json", {}), maps)
        values["request_hash"] = canonical_sha256({
            "tenant_id": tenant_id,
            "project_id": project_id,
            "source_request_hash": source.get("request_hash"),
            "inputs": values["input_ids_json"],
            "input_hashes": source.get("input_hashes_json", []),
            "outputs": values["output_ids_json"],
            "output_hashes": source.get("output_hashes_json", []),
            "source_root_hash": source_root_hash,
        })
        # Remapping stable identifiers changes the derivation record but not the preserved source bytes.
        values["derivation_hash"] = canonical_sha256({
            "tenant_id": tenant_id,
            "project_id": project_id,
            "source_derivation_hash": source.get("derivation_hash"),
            "request_hash": values["request_hash"],
            "inputs": values["input_ids_json"],
            "input_hashes": source.get("input_hashes_json", []),
            "outputs": values["output_ids_json"],
            "output_hashes": source.get("output_hashes_json", []),
            "source_root_hash": source_root_hash,
        })
    elif model is SceneCommitRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["parent_ids_json"] = [_mapped(maps, "commit", item) for item in source.get("parent_ids_json", [])]
        values["supersedes_commit_id"] = _mapped(maps, "commit", source.get("supersedes_commit_id"))
        snapshot = _remap_json(source.get("semantic_snapshot_json", {}), maps)
        values["semantic_snapshot_json"] = snapshot
        values["snapshot_hash"] = canonical_sha256(snapshot)
        values["root_manifest_hash"] = values["snapshot_hash"]
        values["change_evidence_ids_json"] = [_mapped(maps, "evidence", item) for item in source.get("change_evidence_ids_json", [])]
        values["policy_checks_json"] = _remap_json(source.get("policy_checks_json", {}), maps)
        values["signatures_json"] = _remap_json(source.get("signatures_json", []), maps)
    elif model is SceneBranchRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["head_commit_id"] = _mapped(maps, "commit", source.get("head_commit_id"))
    elif model is SceneTagRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["commit_id"] = _mapped(maps, "commit", source.get("commit_id"))
        values["metadata_json"] = _remap_json(source.get("metadata_json", {}), maps)
    elif model is SceneEntityRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        for name in ("attributes_json", "provenance_json", "policy_json", "stable_support_json"):
            values[name] = _remap_json(source.get(name, {}), maps)
        values["provenance_json"] = {
            **values["provenance_json"],
            "preservation_import": {"source_root_hash": source_root_hash, "source_entity_id": source["entity_id"]},
        }
    elif model is RepresentationAssetRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["asset_id"] = _mapped(maps, "asset", source.get("asset_id"))
        values["coordinate_frame_id"] = _mapped(maps, "frame", source.get("coordinate_frame_id"))
        # Older preservation packages may predate the explicit proxy authority
        # contract. Import them conservatively; an import must never promote
        # authority or make an interaction derivative durable/authoritative.
        if source.get("kind") == "interaction":
            values["authority_class"] = "derived_non_authoritative"
            values["authority_ceiling"] = "derived_non_authoritative"
            values["disposable"] = True
        else:
            values["authority_ceiling"] = source.get("authority_ceiling") or source.get("authority_class") or "none"
            values["disposable"] = bool(source.get("disposable", False))
        for name in (
            "quality_json", "provenance_json", "support_map_json", "format_json", "derivation_policy_json",
            "privacy_inheritance_json", "metadata_json",
        ):
            values[name] = _remap_json(source.get(name, {}), maps)
        values["dependencies_json"] = [_mapped_any(maps, item) for item in source.get("dependencies_json", [])]
        values["fallback_representation_id"] = _mapped(maps, "representation", source.get("fallback_representation_id"))
        values["provenance_json"] = {
            **values["provenance_json"],
            "preservation_import": {
                "source_root_hash": source_root_hash,
                "source_representation_id": source["representation_id"],
                "provider_reapproval_required_for_new_execution": True,
            },
        }
    elif model is GeometryAssetManifestRow:
        values["asset_id"] = _mapped(maps, "asset", source.get("asset_id"))
        values["representation_id"] = _mapped(maps, "representation", source.get("representation_id"))
        values["coordinate_frame_id"] = _mapped(maps, "frame", source.get("coordinate_frame_id"))
        values["source_run_id"] = _mapped_any(maps, source.get("source_run_id"))
        values["supersedes_manifest_id"] = _mapped(maps, "geometry_manifest", source.get("supersedes_manifest_id"))
        for name in (
            "bounds_json", "counts_json", "compression_json", "quality_json", "audience_policy_json",
            "rebuild_recipe_json",
        ):
            values[name] = _remap_json(source.get(name, {}), maps)
        values["manifest_hash"] = canonical_sha256({
            "source_manifest_hash": source.get("manifest_hash"),
            "asset_id": values["asset_id"],
            "representation_id": values["representation_id"],
            "coordinate_frame_id": values["coordinate_frame_id"],
            "source_root_hash": source_root_hash,
        })
    elif model is RepresentationBindingRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["commit_id"] = _mapped(maps, "commit", source.get("commit_id"))
        values["representation_id"] = _mapped(maps, "representation", source.get("representation_id"))
        values["coordinate_frame_id"] = _mapped(maps, "frame", source.get("coordinate_frame_id"))
        for name in ("review_decision_json", "audience_policy_json", "client_profile_json"):
            values[name] = _remap_json(source.get(name, {}), maps)
    elif model is SpatialAnnotationRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["entity_id"] = _mapped(maps, "entity", source.get("entity_id"))
        values["coordinate_frame_id"] = _mapped(maps, "frame", source.get("coordinate_frame_id"))
        values["authored_from_representation_id"] = _mapped(maps, "representation", source.get("authored_from_representation_id"))
        values["support_json"] = _remap_json(source.get("support_json", {}), maps)
        values["policy_json"] = _remap_json(source.get("policy_json", {}), maps)
    elif model is AnchorRemapRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["source_representation_id"] = _mapped(maps, "representation", source.get("source_representation_id"))
        values["target_representation_id"] = _mapped(maps, "representation", source.get("target_representation_id"))
        values["resolved_annotation_ids_json"] = [_mapped(maps, "annotation", item) for item in source.get("resolved_annotation_ids_json", [])]
        values["unresolved_annotation_ids_json"] = [_mapped(maps, "annotation", item) for item in source.get("unresolved_annotation_ids_json", [])]
        values["metrics_json"] = _remap_json(source.get("metrics_json", {}), maps)
        values["remap_hash"] = canonical_sha256({
            "source_remap_hash": source.get("remap_hash"),
            "source_representation_id": values["source_representation_id"],
            "target_representation_id": values["target_representation_id"],
            "source_root_hash": source_root_hash,
        })
    elif model is MeasurementRow:
        values["scene_id"] = _mapped(maps, "scene", source.get("scene_id"))
        values["entity_id"] = _mapped(maps, "entity", source.get("entity_id"))
        values["source_asset_ids_json"] = [_mapped(maps, "asset", item) for item in source.get("source_asset_ids_json", [])]
        values["calibration_json"] = _remap_json(source.get("calibration_json", {}), maps)
        values["geometry_json"] = _remap_json(source.get("geometry_json", {}), maps)
        values["coordinate_frame_id"] = _mapped(maps, "frame", source.get("coordinate_frame_id"))
        values["source_commit_id"] = _mapped(maps, "commit", source.get("source_commit_id"))
        values["originating_representation_id"] = _mapped(
            maps, "representation", source.get("originating_representation_id")
        )
        values["interaction_hit_json"] = _remap_json(source.get("interaction_hit_json"), maps)
        values["resolved_metric_evidence_json"] = _remap_json(
            source.get("resolved_metric_evidence_json"), maps
        )
        values["supersedes_measurement_id"] = _mapped(maps, "measurement", source.get("supersedes_measurement_id"))
    elif model is ConstructionRecordRow:
        values["parent_id"] = _mapped(maps, "construction", source.get("parent_id"))
        values["entity_id"] = _mapped(maps, "entity", source.get("entity_id"))
        values["data_json"] = _remap_json(source.get("data_json", {}), maps)
        values["evidence_asset_ids_json"] = [_mapped(maps, "asset", item) for item in source.get("evidence_asset_ids_json", [])]
    elif model is MemoryRecordRow:
        values["related_ids_json"] = [_mapped_any(maps, item) for item in source.get("related_ids_json", [])]
        values["data_json"] = _remap_json(source.get("data_json", {}), maps)
        values["evidence_asset_ids_json"] = [_mapped(maps, "asset", item) for item in source.get("evidence_asset_ids_json", [])]
        values["generated_lineage_json"] = _remap_json(source.get("generated_lineage_json"), maps)
    elif model is ConsentGrantRow:
        values["derivative_policy_json"] = _remap_json(source.get("derivative_policy_json", {}), maps)
    elif model is CollaborationCommentRow:
        values["scene_commit_id"] = _mapped(maps, "commit", source.get("scene_commit_id"))
        values["entity_id"] = _mapped(maps, "entity", source.get("entity_id"))
        values["anchor_json"] = _remap_json(source.get("anchor_json"), maps)
        values["supersedes_comment_id"] = _mapped(maps, "comment", source.get("supersedes_comment_id"))
        values["body_hash"] = canonical_sha256(
            {
                "body": source.get("body", ""),
                "author_id": source.get("author_id"),
                "supersedes": values["supersedes_comment_id"],
            }
        )
    elif model is CollaborationTaskRow:
        values["entity_id"] = _mapped(maps, "entity", source.get("entity_id"))
    elif model is LegalHoldRow:
        values["resource_id"] = _map_legal_hold_resource(source.get("resource_type"), source.get("resource_id"), maps)
    if "created_by" in model.__table__.c and not values.get("created_by"):
        values["created_by"] = actor_id
    return values


def _primary_scene_head(session: Session, tenant_id: str, project_id: str) -> tuple[str | None, str | None, str | None]:
    branches = list(
        session.scalars(
            select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
            )
        )
    )
    if not branches:
        return None, None, None
    branches.sort(key=lambda row: (row.name != "main", row.scene_id, row.name))
    branch = branches[0]
    commit = session.get(SceneCommitRow, branch.head_commit_id)
    return branch.scene_id, branch.head_commit_id, commit.snapshot_hash if commit else None


def _collision_safe_id(session: Session, model: type[Any], preferred: str) -> str:
    if session.get(model, preferred) is None:
        return preferred
    candidate = new_uuid()
    while session.get(model, candidate) is not None:
        candidate = new_uuid()
    return candidate


def _mapped(maps: dict[str, dict[str, str]], category: str, value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    return maps.get(category, {}).get(value, value)


def _mapped_any(maps: dict[str, dict[str, str]], value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    for category in (
        "asset",
        "frame",
        "spatial_transform",
        "geometry_manifest",
        "evidence",
        "assertion",
        "derivation",
        "annotation",
        "anchor_remap",
        "scene_tag",
        "commit",
        "branch",
        "entity",
        "representation",
        "representation_binding",
        "measurement",
        "consent",
        "construction",
        "memory",
        "comment",
        "task",
        "retention_rule",
        "legal_hold",
        "scene",
    ):
        replacement = maps.get(category, {}).get(value)
        if replacement is not None:
            return replacement
    return value


def _remap_json(value: Any, maps: dict[str, dict[str, str]], *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {item_key: _remap_json(item_value, maps, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_remap_json(item, maps, key=key) for item in value]
    if not isinstance(value, str):
        return value
    normalized = (key or "").lower()
    if normalized == "scene_id" or normalized.endswith("_scene_id"):
        return _mapped(maps, "scene", value)
    if normalized in {"frame_id", "coordinate_frame_id", "parent_frame_id"} or normalized.endswith("_frame_id"):
        return _mapped(maps, "frame", value)
    if normalized in {"commit_id", "scene_commit_id", "head_commit_id", "supersedes_commit_id", "expected_head", "parent_ids"} or normalized.endswith("_commit_id"):
        return _mapped(maps, "commit", value)
    if normalized in {"entity_id", "semantic_support_id"} or normalized.endswith("_entity_id"):
        return _mapped(maps, "entity", value)
    if normalized in {"representation_id", "originating_representation_id", "replaces"} or normalized.endswith("_representation_id"):
        return _mapped(maps, "representation", value)
    if normalized == "binding_id" or normalized.endswith("_binding_id"):
        return _mapped(maps, "representation_binding", value)
    if normalized == "measurement_id" or normalized.endswith("_measurement_id"):
        return _mapped(maps, "measurement", value)
    if normalized in {"transform_id", "spatial_transform_id", "supersedes_transform_id"} or normalized.endswith("_transform_id"):
        return _mapped(maps, "spatial_transform", value)
    if normalized in {"geometry_manifest_id", "supersedes_manifest_id"} or normalized.endswith("_manifest_id"):
        return _mapped(maps, "geometry_manifest", value)
    if normalized in {"evidence_id", "change_evidence_id"} or normalized.endswith("_evidence_id"):
        return _mapped(maps, "evidence", value)
    if normalized in {"assertion_id", "supersedes_assertion_id"} or normalized.endswith("_assertion_id"):
        return _mapped(maps, "assertion", value)
    if normalized == "annotation_id" or normalized.endswith("_annotation_id"):
        return _mapped(maps, "annotation", value)
    if normalized in {"remap_id", "anchor_remap_id"} or normalized.endswith("_remap_id"):
        return _mapped(maps, "anchor_remap", value)
    if normalized == "grant_id" or normalized.endswith("_grant_id"):
        return _mapped(maps, "consent", value)
    if normalized in {"evidence_ids", "change_evidence_ids"}:
        return _mapped(maps, "evidence", value)
    if "asset_id" in normalized:
        return _mapped(maps, "asset", value)
    if normalized == "source_ids":
        return _mapped_any(maps, value)
    if normalized in {"related_ids", "record_id", "record_ids"}:
        return _mapped_any(maps, value)
    return value


def _map_legal_hold_resource(resource_type: Any, resource_id: Any, maps: dict[str, dict[str, str]]) -> Any:
    if not isinstance(resource_id, str):
        return resource_id
    normalized = str(resource_type or "").lower()
    if normalized in {"asset", "asset_ref", "capture", "evidence"}:
        return _mapped(maps, "asset", resource_id)
    if normalized in {"scene", "spatial_scene"}:
        return _mapped(maps, "scene", resource_id)
    if normalized in {"scene_entity", "entity"}:
        return _mapped(maps, "entity", resource_id)
    if normalized in {"scene_commit", "commit"}:
        return _mapped(maps, "commit", resource_id)
    if normalized in {"representation", "representation_asset"}:
        return _mapped(maps, "representation", resource_id)
    if normalized in {"measurement"}:
        return _mapped(maps, "measurement", resource_id)
    if normalized in {"construction_record", "construction"}:
        return _mapped(maps, "construction", resource_id)
    if normalized in {"memory_record", "memory"}:
        return _mapped(maps, "memory", resource_id)
    return _mapped_any(maps, resource_id)


def _find_unresolved_references(tables: dict[str, list[dict[str, Any]]], maps: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    known_assets = set(maps.get("asset", {}))
    unresolved: list[dict[str, Any]] = []
    checks = (
        ("measurements", "source_asset_ids_json"),
        ("construction_records", "evidence_asset_ids_json"),
        ("memory_records", "evidence_asset_ids_json"),
        ("evidence_records", "asset_id"),
        ("geometry_asset_manifests", "asset_id"),
    )
    for table_name, field in checks:
        for row in tables.get(table_name, []):
            raw = row.get(field, [])
            candidates = [raw] if isinstance(raw, str) else list(raw or [])
            missing = sorted({item for item in candidates if item not in known_assets})
            if missing:
                unresolved.append(
                    {
                        "table": table_name,
                        "row_id": row.get(_PRIMARY_KEY_FIELDS[table_name]),
                        "field": field,
                        "source_ids": missing,
                        "reason": "reference was not an active asset in the exported project; identifier was preserved as historical evidence",
                    }
                )
    return unresolved


def _verify_table_digests(tables: dict[str, Any], digests: dict[str, str], *, required: bool) -> None:
    if required and set(tables) != set(digests):
        raise ValidationError(
            "EXPORT_TABLE_DIGEST_SET_MISMATCH",
            "table digest keys do not match exported table keys",
            {"tables": sorted(tables), "digests": sorted(digests)},
        )
    for name, rows in tables.items():
        expected = digests.get(name)
        if expected is None:
            if required:
                raise ValidationError("EXPORT_TABLE_DIGEST_MISSING", "exported table has no digest", {"table": name})
            continue
        actual = canonical_sha256(rows)
        if actual != expected:
            raise ValidationError(
                "EXPORT_TABLE_DIGEST_FAILED",
                "exported table content does not match its digest",
                {"table": name, "expected": expected, "actual": actual},
            )


def _verify_supported_version(actual: str, supported: str, label: str) -> None:
    try:
        actual_parts = tuple(int(item) for item in actual.split("."))
        supported_parts = tuple(int(item) for item in supported.split("."))
    except (AttributeError, ValueError) as exc:
        raise ValidationError("EXPORT_VERSION_INVALID", f"{label} version is invalid", {"version": actual}) from exc
    if len(actual_parts) != 3 or len(supported_parts) != 3:
        raise ValidationError("EXPORT_VERSION_INVALID", f"{label} version must use semantic versioning", {"version": actual})
    if actual_parts[0] > supported_parts[0] or (actual_parts[0] == supported_parts[0] and actual_parts > supported_parts):
        raise ValidationError(
            "EXPORT_FUTURE_VERSION_UNSUPPORTED",
            f"{label} version is newer than this importer supports",
            {"actual": actual, "supported": supported},
        )


def _serialize_model(row: Any) -> dict[str, Any]:
    return {column.name: _json_default(getattr(row, column.name)) for column in row.__table__.columns}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValidationError("IMPORT_DATETIME_INVALID", "preservation datetime value is invalid", {"value": value})
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("IMPORT_DATETIME_INVALID", "preservation datetime value is invalid", {"value": value}) from exc


def _classification(value: Any) -> Classification:
    try:
        return Classification(str(value))
    except ValueError as exc:
        raise ValidationError("IMPORT_CLASSIFICATION_INVALID", "project classification is not supported", {"classification": value}) from exc


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    total = 0
    for info in archive.infolist():
        target = (destination / info.filename).resolve()
        if destination.resolve() not in target.parents and target != destination.resolve():
            raise ValidationError("ARCHIVE_PATH_TRAVERSAL", "archive contains an unsafe path")
        if info.file_size > 2 * 1024 * 1024 * 1024:
            raise ValidationError("ARCHIVE_ENTRY_TOO_LARGE", "archive entry exceeds safety limit")
        total += info.file_size
        if total > 10 * 1024 * 1024 * 1024:
            raise ValidationError("ARCHIVE_TOO_LARGE", "archive exceeds safety limit")
        if info.compress_size and info.file_size / info.compress_size > 200:
            raise ValidationError("ARCHIVE_COMPRESSION_RATIO", "archive entry has unsafe compression ratio")
    archive.extractall(destination)
