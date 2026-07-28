from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .contracts import MeasurementContract
from .database import (
    AssetRefRow,
    CoordinateFrameRow,
    ConstructionRecordRow,
    Database,
    EvidenceRecordRow,
    MeasurementRow,
    ProjectRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
)
from .errors import ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import AuthorityClass, ProvenanceRef, SourceClass
from .temporal import db_now


@dataclass(frozen=True)
class ProxyHit:
    representation_id: str
    world_point: list[float]
    normal: list[float] | None
    support_hint: dict[str, Any]


class SceneService:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def create_scene(self, tenant_id: str, project_id: str, *, name: str, actor_id: str) -> dict[str, str]:
        scene_id = new_uuid()
        initial = {"scene_id": scene_id, "name": name, "entities": [], "representations": [], "schema_version": "1.0.0"}
        commit_id = new_uuid()
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id or project.status != "active":
                raise NotFoundError("project", project_id)
            snapshot_hash = canonical_sha256(initial)
            session.add(
                SceneCommitRow(
                    commit_id=commit_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    branch="main",
                    parent_ids_json=[],
                    message="Initialize scene",
                    semantic_snapshot_json=initial,
                    snapshot_hash=snapshot_hash,
                    root_manifest_hash=snapshot_hash,
                    policy_checks_json={"initialization": "passed"},
                    review_state="system_initialized",
                    recorded_at=db_now(),
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
                    protected=True,
                )
            )
            session.add(
                self._events.create(
                    session,
                    event_type="scene.committed",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="scene_commit",
                    aggregate_id=commit_id,
                    payload={"scene_id": scene_id, "branch": "main", "snapshot_hash": snapshot_hash, "parent_count": 0},
                    producer="scene-service",
                    actor_id=actor_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="scene:create",
                resource_type="scene",
                resource_id=scene_id,
                outcome="allowed",
                details={"commit_id": commit_id},
                session=session,
            )
        return {"scene_id": scene_id, "commit_id": commit_id, "branch": "main"}

    def create_entity(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        entity_type: str,
        name: str,
        attributes: dict[str, Any],
        source_class: SourceClass,
        authority_class: AuthorityClass,
        confidence: float,
        provenance: ProvenanceRef,
        policy: dict[str, Any],
        stable_support: dict[str, Any],
        actor_id: str,
        entity_id: str | None = None,
    ) -> str:
        if not 0 <= confidence <= 1:
            raise ValidationError("CONFIDENCE_INVALID", "confidence must be between zero and one")
        if any(key in stable_support for key in {"triangle_id", "gaussian_id", "voxel_id", "tile_id", "lod_element_id"}):
            raise ValidationError("UNSTABLE_SUPPORT_IDENTIFIER", "durable entity supports cannot depend on geometry element IDs")
        identifier = entity_id or new_uuid()
        with self.database.session() as session:
            scene_exists = session.scalar(
                select(SceneCommitRow.commit_id).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.scene_id == scene_id,
                ).limit(1)
            )
            if not scene_exists:
                raise NotFoundError("scene", scene_id)
            frame_id = stable_support.get("frame_id")
            if frame_id:
                frame = session.get(CoordinateFrameRow, str(frame_id))
                if (
                    not frame
                    or frame.tenant_id != tenant_id
                    or frame.project_id != project_id
                    or frame.deprecated_at is not None
                ):
                    raise NotFoundError("coordinate_frame", str(frame_id))
            if session.get(SceneEntityRow, identifier):
                raise ConflictError("ENTITY_EXISTS", "stable entity identifier already exists")
            session.add(
                SceneEntityRow(
                    entity_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    entity_type=entity_type,
                    name=name,
                    attributes_json=attributes,
                    source_class=source_class.value,
                    authority_class=authority_class.value,
                    confidence=confidence,
                    provenance_json=provenance.model_dump(mode="json"),
                    policy_json=policy,
                    stable_support_json=stable_support,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="scene_entity:create",
                resource_type="scene_entity",
                resource_id=identifier,
                outcome="allowed",
                details={"scene_id": scene_id, "entity_type": entity_type, "source_class": source_class.value},
                session=session,
            )
        return identifier

    def commit(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        branch: str,
        expected_head: str,
        message: str,
        actor_id: str,
        field_visit_id: str | None = None,
        workflow_event_id: str | None = None,
        change_evidence_ids: list[str] | None = None,
        policy_checks: dict[str, Any] | None = None,
        signatures: list[dict[str, Any]] | None = None,
        review_state: str = "unreviewed",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            return self.commit_in_session(
                session=session,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                branch=branch,
                expected_head=expected_head,
                message=message,
                actor_id=actor_id,
                field_visit_id=field_visit_id,
                workflow_event_id=workflow_event_id,
                change_evidence_ids=change_evidence_ids,
                policy_checks=policy_checks,
                signatures=signatures,
                review_state=review_state,
                valid_from=valid_from,
                valid_to=valid_to,
            )

    def commit_in_session(
        self,
        *,
        session: Session,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        branch: str,
        expected_head: str,
        message: str,
        actor_id: str,
        field_visit_id: str | None = None,
        workflow_event_id: str | None = None,
        change_evidence_ids: list[str] | None = None,
        policy_checks: dict[str, Any] | None = None,
        signatures: list[dict[str, Any]] | None = None,
        review_state: str = "unreviewed",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a scene commit inside a caller-owned transaction.

        The caller controls the transaction boundary so related workflow state can be
        committed or rolled back atomically with the scene commit. A workflow event ID
        is a project-scoped idempotency key and cannot be rebound to another scene.
        """
        change_evidence_ids = sorted(set(change_evidence_ids or []))
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError("SCENE_VALID_TIME_INVALID", "scene commit valid_to must be later than valid_from")

        if workflow_event_id:
            existing = session.scalar(
                select(SceneCommitRow).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.workflow_event_id == workflow_event_id,
                )
            )
            if existing is not None:
                if existing.scene_id != scene_id or existing.branch != branch or existing.review_state != review_state:
                    raise ConflictError(
                        "SCENE_WORKFLOW_EVENT_REBOUND",
                        "workflow event is already bound to a different scene commit scope",
                    )
                return self._commit_result(existing, idempotent_replay=True)

        for evidence_id in change_evidence_ids:
            evidence = session.get(EvidenceRecordRow, evidence_id)
            if not evidence or evidence.tenant_id != tenant_id or evidence.project_id != project_id:
                raise NotFoundError("evidence", evidence_id)
        branch_row = session.scalar(
            select(SceneBranchRow)
            .where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == scene_id,
                SceneBranchRow.name == branch,
            )
            .with_for_update()
        )
        if not branch_row:
            raise NotFoundError("scene_branch", branch)
        if branch_row.head_commit_id != expected_head:
            raise ConflictError(
                "SCENE_HEAD_CHANGED",
                "scene branch changed since the client read it",
                {"expected": expected_head, "actual": branch_row.head_commit_id},
            )
        entities = list(
            session.scalars(
                select(SceneEntityRow).where(
                    SceneEntityRow.tenant_id == tenant_id,
                    SceneEntityRow.project_id == project_id,
                    SceneEntityRow.scene_id == scene_id,
                    SceneEntityRow.superseded_at.is_(None),
                )
            )
        )
        bindings = list(
            session.scalars(
                select(RepresentationBindingRow).where(
                    RepresentationBindingRow.tenant_id == tenant_id,
                    RepresentationBindingRow.project_id == project_id,
                    RepresentationBindingRow.scene_id == scene_id,
                    RepresentationBindingRow.superseded_at.is_(None),
                )
            )
        )
        snapshot = {
            "schema_version": "1.0.0",
            "scene_id": scene_id,
            "entities": [
                {
                    "entity_id": item.entity_id,
                    "entity_type": item.entity_type,
                    "name": item.name,
                    "attributes": item.attributes_json,
                    "source_class": item.source_class,
                    "authority_class": item.authority_class,
                    "confidence": item.confidence,
                    "provenance": item.provenance_json,
                    "policy": item.policy_json,
                    "stable_support": item.stable_support_json,
                }
                for item in sorted(entities, key=lambda value: value.entity_id)
            ],
            "representations": [
                {
                    "binding_id": item.binding_id,
                    "representation_id": item.representation_id,
                    "role": item.role,
                    "coordinate_frame_id": item.coordinate_frame_id,
                    "transform": item.transform_json,
                    "authority_class": item.authority_class,
                    "authority_ceiling": item.authority_ceiling,
                    "intended_uses": item.intended_uses_json,
                    "audience_policy": item.audience_policy_json,
                }
                for item in sorted(bindings, key=lambda value: value.binding_id)
            ],
        }
        commit_id = new_uuid()
        snapshot_hash = canonical_sha256(snapshot)
        row = SceneCommitRow(
            commit_id=commit_id,
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            branch=branch,
            parent_ids_json=[expected_head],
            message=message,
            semantic_snapshot_json=snapshot,
            snapshot_hash=snapshot_hash,
            root_manifest_hash=snapshot_hash,
            field_visit_id=field_visit_id,
            workflow_event_id=workflow_event_id,
            change_evidence_ids_json=change_evidence_ids,
            policy_checks_json=policy_checks or {},
            signatures_json=signatures or [],
            review_state=review_state,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=db_now(),
            created_by=actor_id,
        )
        session.add(row)
        branch_row.head_commit_id = commit_id
        session.add(
            self._events.create(
                session,
                event_type="scene.committed",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="scene_commit",
                aggregate_id=commit_id,
                payload={
                    "scene_id": scene_id,
                    "branch": branch,
                    "snapshot_hash": snapshot_hash,
                    "parent_count": 1,
                    "review_state": review_state,
                    "change_evidence_count": len(change_evidence_ids),
                },
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
                causation_id=workflow_event_id,
            )
        )
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            action="scene:commit",
            resource_type="scene_commit",
            resource_id=commit_id,
            outcome="allowed",
            details={"scene_id": scene_id, "branch": branch, "parent": expected_head, "snapshot_hash": row.snapshot_hash},
            session=session,
        )
        session.flush()
        return self._commit_result(row, idempotent_replay=False)

    @staticmethod
    def _commit_result(row: SceneCommitRow, *, idempotent_replay: bool) -> dict[str, Any]:
        return {
            "commit_id": row.commit_id,
            "snapshot_hash": row.snapshot_hash,
            "root_manifest_hash": row.root_manifest_hash,
            "parent_ids": list(row.parent_ids_json),
            "branch": row.branch,
            "field_visit_id": row.field_visit_id,
            "workflow_event_id": row.workflow_event_id,
            "change_evidence_ids": list(row.change_evidence_ids_json),
            "review_state": row.review_state,
            "valid_from": row.valid_from,
            "valid_to": row.valid_to,
            "recorded_at": row.recorded_at,
            "idempotent_replay": idempotent_replay,
        }

    def create_branch(
        self,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        *,
        name: str,
        from_commit_id: str,
        protected: bool = False,
    ) -> str:
        with self.database.session() as session:
            commit = session.get(SceneCommitRow, from_commit_id)
            if not commit or commit.tenant_id != tenant_id or commit.project_id != project_id or commit.scene_id != scene_id:
                raise NotFoundError("scene_commit", from_commit_id)
            existing = session.scalar(
                select(SceneBranchRow).where(
                    SceneBranchRow.tenant_id == tenant_id,
                    SceneBranchRow.project_id == project_id,
                    SceneBranchRow.scene_id == scene_id,
                    SceneBranchRow.name == name,
                )
            )
            if existing:
                raise ConflictError("BRANCH_EXISTS", "scene branch already exists")
            branch_id = new_uuid()
            session.add(
                SceneBranchRow(
                    branch_id=branch_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    name=name,
                    head_commit_id=from_commit_id,
                    protected=protected,
                )
            )
            return branch_id

    def diff(self, left_commit_id: str, right_commit_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            left = session.get(SceneCommitRow, left_commit_id)
            right = session.get(SceneCommitRow, right_commit_id)
            if not left or not right or left.tenant_id != right.tenant_id or left.project_id != right.project_id or left.scene_id != right.scene_id:
                raise ValidationError("SCENE_DIFF_SCOPE_MISMATCH", "commits must exist in the same scene")
            left_entities = {item["entity_id"]: item for item in left.semantic_snapshot_json.get("entities", [])}
            right_entities = {item["entity_id"]: item for item in right.semantic_snapshot_json.get("entities", [])}
            added = sorted(set(right_entities) - set(left_entities))
            removed = sorted(set(left_entities) - set(right_entities))
            modified = sorted(key for key in set(left_entities) & set(right_entities) if left_entities[key] != right_entities[key])
            return {
                "left": left_commit_id,
                "right": right_commit_id,
                "entities": {"added": added, "removed": removed, "modified": modified},
                "representation_changed": left.semantic_snapshot_json.get("representations") != right.semantic_snapshot_json.get("representations"),
            }

    def rollback_branch(self, tenant_id: str, project_id: str, scene_id: str, branch: str, target_commit_id: str, *, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            target = session.get(SceneCommitRow, target_commit_id)
            branch_row = session.scalar(
                select(SceneBranchRow).where(
                    SceneBranchRow.tenant_id == tenant_id,
                    SceneBranchRow.project_id == project_id,
                    SceneBranchRow.scene_id == scene_id,
                    SceneBranchRow.name == branch,
                )
            )
            if not target or not branch_row or target.scene_id != scene_id:
                raise NotFoundError("scene_commit", target_commit_id)
            previous = branch_row.head_commit_id
            rollback_id = new_uuid()
            session.add(
                SceneCommitRow(
                    commit_id=rollback_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    branch=branch,
                    parent_ids_json=[previous],
                    message=f"Rollback semantic state to {target_commit_id}",
                    semantic_snapshot_json=target.semantic_snapshot_json,
                    snapshot_hash=target.snapshot_hash,
                    root_manifest_hash=target.root_manifest_hash or target.snapshot_hash,
                    field_visit_id=target.field_visit_id,
                    workflow_event_id=target.workflow_event_id,
                    change_evidence_ids_json=target.change_evidence_ids_json,
                    policy_checks_json={**(target.policy_checks_json or {}), "rollback": "passed"},
                    signatures_json=[],
                    review_state="rollback",
                    valid_from=target.valid_from,
                    valid_to=target.valid_to,
                    recorded_at=db_now(),
                    created_by=actor_id,
                    supersedes_commit_id=previous,
                )
            )
            branch_row.head_commit_id = rollback_id
            return {"commit_id": rollback_id, "restored_from": target_commit_id, "superseded": previous, "snapshot_hash": target.snapshot_hash}

    def create_measurement(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        entity_id: str | None,
        value: float,
        unit: str,
        uncertainty: float,
        source_asset_ids: list[str],
        calibration: dict[str, Any],
        verifier_id: str | None,
        verified: bool,
        actor_id: str,
        originating_representation_id: str | None = None,
        interaction_hit: dict[str, Any] | None = None,
        measurement_type: str = "distance",
        geometry: dict[str, Any] | None = None,
        source_method: str = "phone_spatial_capture",
        measured_at: datetime | None = None,
        coordinate_frame_id: str,
        source_commit_id: str | None = None,
        permitted_uses: list[str] | None = None,
        state: str = "measured",
        supersedes_measurement_id: str | None = None,
        proxy_tolerance_m: float = 0.03,
    ) -> str:
        if uncertainty < 0 or not math.isfinite(uncertainty) or not source_asset_ids:
            raise ValidationError(
                "MEASUREMENT_EVIDENCE_REQUIRED",
                "measurement requires non-negative uncertainty and source evidence",
            )
        if not geometry:
            raise ValidationError(
                "MEASUREMENT_GEOMETRY_REQUIRED",
                "measurement requires endpoints or explicit geometry",
            )
        effective_permitted_uses = sorted(set(permitted_uses or ["reference"]))
        if not effective_permitted_uses:
            raise ValidationError(
                "MEASUREMENT_PERMITTED_USE_REQUIRED",
                "measurement requires at least one permitted use",
            )
        forbidden_uses = {
            "survey",
            "fabrication",
            "contract_authoritative",
            "code_compliance_certification",
        }
        prohibited = forbidden_uses.intersection(effective_permitted_uses)
        if prohibited:
            raise ValidationError(
                "MEASUREMENT_PERMITTED_USE_INVALID",
                "SIP reference measurements cannot be authorized for survey, fabrication, contract authority, or code certification",
                {"forbidden_uses": sorted(prohibited)},
            )
        with self.database.session() as session:
            branch = session.scalar(
                select(SceneBranchRow).where(
                    SceneBranchRow.tenant_id == tenant_id,
                    SceneBranchRow.project_id == project_id,
                    SceneBranchRow.scene_id == scene_id,
                    SceneBranchRow.name == "main",
                )
            )
            if not branch:
                raise NotFoundError("scene", scene_id)
            effective_source_commit_id = source_commit_id or branch.head_commit_id
            source_commit = session.get(SceneCommitRow, effective_source_commit_id)
            if (
                not source_commit
                or source_commit.tenant_id != tenant_id
                or source_commit.project_id != project_id
                or source_commit.scene_id != scene_id
            ):
                raise NotFoundError("scene_commit", effective_source_commit_id)
            if entity_id:
                entity = session.get(SceneEntityRow, entity_id)
                scene_entity_valid = bool(
                    entity
                    and entity.tenant_id == tenant_id
                    and entity.project_id == project_id
                    and entity.scene_id == scene_id
                    and entity.superseded_at is None
                )
                construction_entity = session.scalar(
                    select(ConstructionRecordRow).where(
                        ConstructionRecordRow.tenant_id == tenant_id,
                        ConstructionRecordRow.project_id == project_id,
                        ConstructionRecordRow.entity_id == entity_id,
                        ConstructionRecordRow.superseded_at.is_(None),
                    )
                )
                if not scene_entity_valid and construction_entity is None:
                    raise NotFoundError("semantic_entity", entity_id)
            frame = session.get(CoordinateFrameRow, coordinate_frame_id)
            if (
                not frame
                or frame.tenant_id != tenant_id
                or frame.project_id != project_id
                or frame.deprecated_at is not None
            ):
                raise NotFoundError("coordinate_frame", coordinate_frame_id)

            normalized_interaction_hit: dict[str, Any] | None = None
            resolved_metric_evidence: dict[str, Any] | None = None
            if originating_representation_id:
                representation = session.get(RepresentationAssetRow, originating_representation_id)
                if (
                    not representation
                    or representation.tenant_id != tenant_id
                    or representation.project_id != project_id
                    or representation.scene_id != scene_id
                ):
                    raise NotFoundError("representation", originating_representation_id)
                if representation.kind == "interaction":
                    if verified:
                        raise ValidationError(
                            "PROXY_MEASUREMENT_CANNOT_BE_VERIFIED",
                            "a proxy interaction may create only a measured candidate after metric re-resolution; independent field verification must be a separate action",
                        )
                    if not interaction_hit:
                        raise ValidationError(
                            "PROXY_HIT_METRIC_RESOLUTION_REQUIRED",
                            "interaction-origin measurements require the original hit for server-side metric re-resolution",
                        )
                    if str(interaction_hit.get("representation_id")) != originating_representation_id:
                        raise ValidationError(
                            "PROXY_HIT_REPRESENTATION_MISMATCH",
                            "interaction hit representation does not match the originating representation",
                        )
                    try:
                        hit = ProxyHit(
                            representation_id=originating_representation_id,
                            world_point=[float(value) for value in interaction_hit["world_point"]],
                            normal=(
                                [float(value) for value in interaction_hit["normal"]]
                                if interaction_hit.get("normal") is not None
                                else None
                            ),
                            support_hint=dict(interaction_hit.get("support_hint") or {}),
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValidationError(
                            "PROXY_HIT_INVALID",
                            "interaction hit is malformed",
                        ) from exc
                    resolution = self._resolve_proxy_hit_in_session(
                        session,
                        tenant_id,
                        project_id,
                        hit,
                        tolerance_m=proxy_tolerance_m,
                    )
                    if not resolution["authoritative_measurement_allowed"]:
                        raise ValidationError(
                            "PROXY_HIT_METRIC_RESOLUTION_REQUIRED",
                            "proxy hit did not resolve to eligible metric evidence within tolerance",
                            {
                                "reason": resolution.get("reason"),
                                "estimated_residual_m": resolution.get("estimated_residual_m"),
                            },
                        )
                    normalized_interaction_hit = resolution["interaction_hit"]
                    resolved_metric_evidence = resolution["resolved_metric_evidence"]
                    required_metric_assets = set(
                        resolved_metric_evidence["metric_source_asset_ids"]
                    )
                    if not required_metric_assets.issubset(set(source_asset_ids)):
                        raise ValidationError(
                            "MEASUREMENT_METRIC_EVIDENCE_MISSING",
                            "measurement source assets must include the metric evidence used to resolve the proxy hit",
                            {"required_asset_ids": sorted(required_metric_assets)},
                        )
                elif interaction_hit is not None:
                    raise ValidationError(
                        "INTERACTION_HIT_ORIGIN_INVALID",
                        "interaction-hit metadata may only accompany an interaction representation",
                    )
                elif representation.kind == "visual":
                    raise ValidationError(
                        "NON_AUTHORITATIVE_MEASUREMENT_SOURCE",
                        "visual representations cannot directly create measurements; use an interaction hit re-resolved to metric evidence",
                        {
                            "representation_id": originating_representation_id,
                            "kind": representation.kind,
                        },
                    )
                elif representation.kind != "metric":
                    raise ValidationError(
                        "NON_AUTHORITATIVE_MEASUREMENT_SOURCE",
                        "only accepted metric representations or re-resolved interaction hits may originate measurements",
                        {
                            "representation_id": originating_representation_id,
                            "kind": representation.kind,
                        },
                    )
                elif (
                    representation.state != "published"
                    or representation.deprecated_at is not None
                    or "measurement" not in representation.intended_uses_json
                ):
                    raise ValidationError(
                        "METRIC_REPRESENTATION_NOT_APPROVED",
                        "metric representation is not currently published and approved for measurement",
                        {"representation_id": originating_representation_id},
                    )
                elif representation.coordinate_frame_id != coordinate_frame_id:
                    raise ValidationError(
                        "MEASUREMENT_FRAME_MISMATCH",
                        "metric representation and measurement must use the same coordinate frame",
                    )
            elif interaction_hit is not None:
                raise ValidationError(
                    "INTERACTION_HIT_ORIGIN_REQUIRED",
                    "interaction-hit metadata requires an originating representation",
                )

            scoped_assets = list(
                session.scalars(
                    select(AssetRefRow).where(
                        AssetRefRow.asset_id.in_(sorted(set(source_asset_ids))),
                        AssetRefRow.tenant_id == tenant_id,
                        AssetRefRow.project_id == project_id,
                        AssetRefRow.tombstoned_at.is_(None),
                    )
                )
            )
            if len(scoped_assets) != len(set(source_asset_ids)):
                raise ValidationError(
                    "MEASUREMENT_EVIDENCE_OUT_OF_SCOPE",
                    "measurement evidence assets are missing, tombstoned, or outside the project",
                )
            if supersedes_measurement_id:
                prior_measurement = session.get(MeasurementRow, supersedes_measurement_id)
                if (
                    not prior_measurement
                    or prior_measurement.tenant_id != tenant_id
                    or prior_measurement.project_id != project_id
                    or prior_measurement.scene_id != scene_id
                ):
                    raise NotFoundError("measurement", supersedes_measurement_id)
                if prior_measurement.state == "superseded":
                    raise ConflictError(
                        "MEASUREMENT_ALREADY_SUPERSEDED",
                        "measurement has already been superseded",
                    )
                prior_measurement.state = "superseded"
            if verified and (not verifier_id or not calibration or uncertainty == 0):
                raise ValidationError(
                    "VERIFIED_MEASUREMENT_METADATA_REQUIRED",
                    "verified measurement requires verifier, calibration, and explicit uncertainty",
                )
            if verified and verifier_id == actor_id:
                raise ValidationError(
                    "INDEPENDENT_VERIFIER_REQUIRED",
                    "verified measurements require a verifier distinct from the creator",
                )

            measurement_id = new_uuid()
            effective_measured_at = measured_at or db_now()
            effective_state = "verified" if verified else state
            authority_class = (
                AuthorityClass.FIELD_VERIFIED if verified else AuthorityClass.METRIC
            )
            verification_date = db_now() if verified else None
            contract = MeasurementContract(
                measurement_id=measurement_id,
                scene_id=scene_id,
                entity_id=entity_id,
                measurement_type=measurement_type,
                geometry=geometry,
                value=value,
                unit=unit,
                uncertainty=uncertainty,
                source_method=source_method,
                measured_at=effective_measured_at,
                coordinate_frame_id=coordinate_frame_id,
                source_commit_id=effective_source_commit_id,
                permitted_uses=effective_permitted_uses,
                source_asset_ids=source_asset_ids,
                calibration=calibration,
                creator_id=actor_id,
                verifier_id=verifier_id,
                verification_date=verification_date,
                verification_status=effective_state,
                authority_class=authority_class,
                originating_representation_id=originating_representation_id,
                interaction_hit=normalized_interaction_hit,
                resolved_metric_evidence=resolved_metric_evidence,
                supersedes_measurement_id=supersedes_measurement_id,
            )
            session.add(
                MeasurementRow(
                    measurement_id=measurement_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    entity_id=entity_id,
                    measurement_type=measurement_type,
                    geometry_json=geometry,
                    source_method=source_method,
                    measured_at=effective_measured_at,
                    coordinate_frame_id=coordinate_frame_id,
                    source_commit_id=effective_source_commit_id,
                    permitted_uses_json=effective_permitted_uses,
                    state=effective_state,
                    supersedes_measurement_id=supersedes_measurement_id,
                    originating_representation_id=originating_representation_id,
                    interaction_hit_json=normalized_interaction_hit,
                    resolved_metric_evidence_json=resolved_metric_evidence,
                    value=value,
                    unit=unit,
                    uncertainty=uncertainty,
                    source_asset_ids_json=source_asset_ids,
                    calibration_json=calibration,
                    verifier_id=verifier_id,
                    verified_at=verification_date,
                    authority_class=authority_class.value,
                    created_by=actor_id,
                )
            )
            payload = {
                "measurement_id": measurement_id,
                "scene_id": scene_id,
                "entity_id": entity_id,
                "verification_status": effective_state,
                "authority_class": authority_class.value,
                "source_commit_id": effective_source_commit_id,
                "interaction_resolved_to_metric": resolved_metric_evidence is not None,
                "contract_hash": canonical_sha256(contract.model_dump(mode="json")),
            }
            session.add(
                self._events.create(
                    session,
                    event_type="measurement.recorded",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="measurement",
                    aggregate_id=measurement_id,
                    payload=payload,
                    producer="scene-service",
                    actor_id=actor_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="measurement:record",
                resource_type="measurement",
                resource_id=measurement_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return measurement_id

    def get_measurement(
        self,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        measurement_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(MeasurementRow, measurement_id)
            if (
                not row
                or row.tenant_id != tenant_id
                or row.project_id != project_id
                or row.scene_id != scene_id
            ):
                raise NotFoundError("measurement", measurement_id)
            source_commit_id = row.source_commit_id
            if not source_commit_id:
                branch = session.scalar(
                    select(SceneBranchRow).where(
                        SceneBranchRow.tenant_id == tenant_id,
                        SceneBranchRow.project_id == project_id,
                        SceneBranchRow.scene_id == scene_id,
                        SceneBranchRow.name == "main",
                    )
                )
                source_commit_id = branch.head_commit_id if branch else "unknown"
            return MeasurementContract(
                measurement_id=row.measurement_id,
                scene_id=row.scene_id,
                entity_id=row.entity_id,
                measurement_type=row.measurement_type,
                geometry=row.geometry_json,
                value=row.value,
                unit=row.unit,
                uncertainty=row.uncertainty,
                source_method=row.source_method,
                measured_at=row.measured_at or row.created_at,
                coordinate_frame_id=row.coordinate_frame_id or "unknown",
                source_commit_id=source_commit_id,
                permitted_uses=row.permitted_uses_json or ["reference"],
                source_asset_ids=row.source_asset_ids_json,
                calibration=row.calibration_json,
                creator_id=row.created_by,
                verifier_id=row.verifier_id,
                verification_date=row.verified_at,
                verification_status=row.state,
                authority_class=AuthorityClass(row.authority_class),
                originating_representation_id=row.originating_representation_id,
                interaction_hit=row.interaction_hit_json,
                resolved_metric_evidence=row.resolved_metric_evidence_json,
                supersedes_measurement_id=row.supersedes_measurement_id,
            ).model_dump(mode="json")

    def _resolve_proxy_hit_in_session(
        self,
        session: Any,
        tenant_id: str,
        project_id: str,
        hit: ProxyHit,
        *,
        tolerance_m: float,
    ) -> dict[str, Any]:
        if not math.isfinite(tolerance_m) or tolerance_m <= 0:
            raise ValidationError(
                "PROXY_HIT_TOLERANCE_INVALID",
                "proxy-hit tolerance must be finite and positive",
            )
        if len(hit.world_point) != 3 or any(
            not math.isfinite(float(value)) for value in hit.world_point
        ):
            raise ValidationError(
                "PROXY_HIT_POINT_INVALID",
                "proxy hit must contain three finite world coordinates",
            )
        if hit.normal is not None and (
            len(hit.normal) != 3
            or any(not math.isfinite(float(value)) for value in hit.normal)
        ):
            raise ValidationError(
                "PROXY_HIT_NORMAL_INVALID",
                "proxy-hit normal must contain three finite values",
            )
        proxy = session.get(RepresentationAssetRow, hit.representation_id)
        if (
            not proxy
            or proxy.tenant_id != tenant_id
            or proxy.project_id != project_id
        ):
            raise NotFoundError("representation", hit.representation_id)
        if proxy.kind != "interaction":
            raise ValidationError(
                "PROXY_HIT_KIND_INVALID",
                "hit does not originate from an interaction representation",
            )
        interaction_record = {
            "representation_id": hit.representation_id,
            "representation_kind": proxy.kind,
            "world_point": [float(value) for value in hit.world_point],
            "normal": [float(value) for value in hit.normal] if hit.normal is not None else None,
            "support_hint": hit.support_hint,
        }
        if proxy.state != "published" or proxy.deprecated_at is not None:
            return {
                "resolved": False,
                "reason": "interaction_representation_not_published",
                "proxy_representation_id": hit.representation_id,
                "interaction_hit": interaction_record,
                "authoritative_measurement_allowed": False,
            }
        metric_id = proxy.support_map_json.get("metric_representation_id")
        metric = session.get(RepresentationAssetRow, metric_id) if metric_id else None
        metric_eligible = bool(
            metric
            and metric.tenant_id == tenant_id
            and metric.project_id == project_id
            and metric.scene_id == proxy.scene_id
            and metric.kind == "metric"
            and metric.state == "published"
            and metric.deprecated_at is None
            and metric.coordinate_frame_id == proxy.coordinate_frame_id
            and "measurement" in metric.intended_uses_json
            and metric.authority_class
            in {AuthorityClass.METRIC.value, AuthorityClass.FIELD_VERIFIED.value}
        )
        if not metric_eligible or metric is None:
            return {
                "resolved": False,
                "reason": "eligible_metric_support_unavailable",
                "proxy_representation_id": hit.representation_id,
                "interaction_hit": interaction_record,
                "authoritative_measurement_allowed": False,
            }
        try:
            residual = float(
                proxy.support_map_json.get("max_reprojection_error_m", math.inf)
            )
        except (TypeError, ValueError):
            residual = math.inf
        if not math.isfinite(residual) or residual < 0:
            return {
                "resolved": False,
                "reason": "metric_reprojection_residual_invalid",
                "proxy_representation_id": hit.representation_id,
                "interaction_hit": interaction_record,
                "authoritative_measurement_allowed": False,
            }
        candidate_asset_ids = {metric.asset_id}
        for candidate in metric.provenance_json.get("source_ids", []):
            if isinstance(candidate, str):
                candidate_asset_ids.add(candidate)
        metric_assets = list(
            session.scalars(
                select(AssetRefRow).where(
                    AssetRefRow.asset_id.in_(sorted(candidate_asset_ids)),
                    AssetRefRow.tenant_id == tenant_id,
                    AssetRefRow.project_id == project_id,
                    AssetRefRow.tombstoned_at.is_(None),
                )
            )
        )
        metric_source_asset_ids = sorted({row.asset_id for row in metric_assets})
        if metric.asset_id not in metric_source_asset_ids:
            return {
                "resolved": False,
                "reason": "metric_source_evidence_unavailable",
                "proxy_representation_id": hit.representation_id,
                "interaction_hit": interaction_record,
                "estimated_residual_m": residual,
                "authoritative_measurement_allowed": False,
            }
        resolved = residual <= tolerance_m
        resolved_evidence = {
            "metric_representation_id": metric.representation_id,
            "metric_source_asset_ids": metric_source_asset_ids,
            "estimated_residual_m": residual,
            "acceptance_threshold_m": tolerance_m,
            "coordinate_frame_id": metric.coordinate_frame_id,
            "resolution_method": "support_map_metric_reprojection",
        }
        return {
            "resolved": resolved,
            "reason": None if resolved else "metric_reprojection_residual_exceeds_tolerance",
            "proxy_representation_id": hit.representation_id,
            "metric_representation_id": metric.representation_id,
            "world_point": interaction_record["world_point"],
            "estimated_residual_m": residual,
            "acceptance_threshold_m": tolerance_m,
            "metric_source_asset_ids": metric_source_asset_ids,
            "interaction_hit": interaction_record,
            "resolved_metric_evidence": resolved_evidence,
            "authoritative_measurement_allowed": resolved,
        }

    def resolve_proxy_hit(
        self,
        tenant_id: str,
        project_id: str,
        hit: ProxyHit,
        *,
        tolerance_m: float = 0.03,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            return self._resolve_proxy_hit_in_session(
                session,
                tenant_id,
                project_id,
                hit,
                tolerance_m=tolerance_m,
            )
