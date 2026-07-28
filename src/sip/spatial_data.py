from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import heapq
import math
from typing import Any

import numpy as np
from sqlalchemy import and_, or_, select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .contracts import (
    AssertionContract,
    CoordinateFrameContract,
    DerivationEventContract,
    EvidenceRecordContract,
    GeometryAssetManifestContract,
    SpatialAnnotationContract,
    SpatialTransformContract,
)
from .database import (
    AnchorRemapRow,
    AssertionRow,
    AssetRefRow,
    ConsentGrantRow,
    CoordinateFrameRow,
    Database,
    DerivationEventRow,
    EvidenceRecordRow,
    GeometryAssetManifestRow,
    RepresentationAssetRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
    SceneTagRow,
    SpatialAnnotationRow,
    SpatialTransformRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .model_governance import ModelRegistry
from .models import Audience, AuthorityClass, Classification, SignedPrincipal, SourceClass
from .policy import CLASSIFICATION_ORDER, PolicyService
from .temporal import db_now


class SpatialDataService:
    """Canonical coordinate, geometry, evidence, annotation, and twin-version control."""

    PROTECTED_MERGE_KEYS = {
        "authority_class",
        "source_class",
        "measurement",
        "measurements",
        "consent",
        "policy",
        "safety",
        "code_compliance",
        "verification",
    }

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        policy: PolicyService,
        models: ModelRegistry,
    ) -> None:
        self.database = database
        self.audit = audit
        self.policy = policy
        self.models = models
        self.events = OutboxEventFactory()

    def register_frame(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        convention: str,
        units: str,
        original_units: str,
        axis_convention: str,
        axis_directions: dict[str, str],
        handedness: str,
        origin_description: str,
        source: str,
        actor_id: str,
        semantic_type: str = "local_cartesian",
        unit_scale_to_meters: float | None = None,
        original_unit_scale_to_meters: float | None = None,
        crs_identifier: str | None = None,
        vertical_datum: str | None = None,
        frame_id: str | None = None,
        parent_frame_id: str | None = None,
        transform_to_parent: list[list[float]] | None = None,
        uncertainty_m: float | None = None,
        gravity_alignment: str | None = None,
        geodetic: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        supersedes_frame_id: str | None = None,
    ) -> dict[str, Any]:
        frame_id = frame_id or new_uuid()
        contract = CoordinateFrameContract(
            frame_id=frame_id,
            parent_frame_id=parent_frame_id,
            semantic_type=semantic_type,
            convention=convention,
            units=units,
            unit_scale_to_meters=unit_scale_to_meters,
            original_units=original_units,
            original_unit_scale_to_meters=original_unit_scale_to_meters,
            axis_convention=axis_convention,
            axis_directions=axis_directions,
            handedness=handedness,
            origin_description=origin_description,
            gravity_alignment=gravity_alignment,
            source=source,
            crs_identifier=crs_identifier,
            vertical_datum=vertical_datum,
            geodetic=geodetic,
            metadata=metadata or {},
            transform_to_parent=transform_to_parent,
            uncertainty_m=uncertainty_m,
            supersedes_frame_id=supersedes_frame_id,
        )
        if parent_frame_id and transform_to_parent is None:
            raise ValidationError("FRAME_PARENT_TRANSFORM_REQUIRED", "child coordinate frames require an explicit transform to parent")
        with self.database.session() as session:
            if session.get(CoordinateFrameRow, frame_id):
                raise ConflictError("FRAME_EXISTS", "coordinate frame identifier already exists", {"frame_id": frame_id})
            parent = self._scoped_frame(session, tenant_id, project_id, parent_frame_id) if parent_frame_id else None
            superseded = self._scoped_frame(session, tenant_id, project_id, supersedes_frame_id) if supersedes_frame_id else None
            if parent and parent.frame_id == frame_id:
                raise ValidationError("FRAME_CYCLE", "coordinate frame cannot parent itself")
            if parent:
                self._assert_frame_parent_chain_acyclic(
                    session,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    new_frame_id=frame_id,
                    parent_frame_id=parent.frame_id,
                )
            if superseded:
                if superseded.deprecated_at is not None:
                    raise ConflictError("FRAME_ALREADY_SUPERSEDED", "coordinate frame is already deprecated")
                superseded.deprecated_at = db_now()
            row = CoordinateFrameRow(
                frame_id=frame_id,
                tenant_id=tenant_id,
                project_id=project_id,
                name=name,
                parent_frame_id=parent_frame_id,
                semantic_type=contract.semantic_type,
                convention=contract.convention,
                units=contract.units,
                unit_scale_to_meters=contract.unit_scale_to_meters,
                original_units=contract.original_units,
                original_unit_scale_to_meters=contract.original_unit_scale_to_meters,
                axis_convention=contract.axis_convention,
                axis_directions_json=contract.axis_directions,
                handedness=contract.handedness,
                origin_description=contract.origin_description,
                gravity_alignment=contract.gravity_alignment,
                source=contract.source,
                crs_identifier=contract.crs_identifier,
                vertical_datum=contract.vertical_datum,
                geodetic_json=contract.geodetic,
                metadata_json=contract.metadata,
                transform_json=contract.transform_to_parent,
                uncertainty_m=contract.uncertainty_m,
                supersedes_frame_id=contract.supersedes_frame_id,
            )
            session.add(row)
            payload = {
                "frame_id": frame_id,
                "parent_frame_id": parent_frame_id,
                "semantic_type": contract.semantic_type,
                "convention": convention,
                "units": units,
                "unit_scale_to_meters": contract.unit_scale_to_meters,
                "axis_directions": contract.axis_directions,
                "frame_contract_hash": canonical_sha256(contract.model_dump(mode="json")),
            }
            session.add(self.events.create(
                session,
                event_type="coordinate_frame.registered",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="coordinate_frame",
                aggregate_id=frame_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="coordinate_frame:register",
                resource_type="coordinate_frame",
                resource_id=frame_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
        return {**contract.model_dump(mode="json"), "name": name}

    def register_transform(
        self,
        *,
        tenant_id: str,
        project_id: str,
        actor_id: str,
        source_frame_id: str,
        target_frame_id: str,
        transform_type: str,
        matrix: list[list[float]],
        source_type: str,
        authority_class: AuthorityClass,
        uncertainty: dict[str, Any],
        matrix_layout: str = "row_major",
        multiplication_convention: str = "column_vector_pre_multiply",
        direction: str = "source_to_target",
        translation_units: str = "meter",
        scale: float = 1.0,
        covariance: list[list[float]] | None = None,
        residual_summary: dict[str, float] | None = None,
        calibration_id: str | None = None,
        solver_run_id: str | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        observed_at: datetime | None = None,
        crs_pipeline: str | None = None,
        grid_resources: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        supersedes_transform_id: str | None = None,
        transform_id: str | None = None,
    ) -> dict[str, Any]:
        transform_id = transform_id or new_uuid()
        effective_observed_at = observed_at or db_now()
        contract = SpatialTransformContract(
            transform_id=transform_id,
            source_frame_id=source_frame_id,
            target_frame_id=target_frame_id,
            transform_type=transform_type,
            matrix=matrix,
            matrix_layout=matrix_layout,
            multiplication_convention=multiplication_convention,
            direction=direction,
            translation_units=translation_units,
            scale=scale,
            covariance=covariance,
            residual_summary=residual_summary or {},
            uncertainty=uncertainty,
            source_type=source_type,
            authority_class=authority_class,
            calibration_id=calibration_id,
            solver_run_id=solver_run_id,
            valid_from=valid_from,
            valid_to=valid_to,
            observed_at=effective_observed_at,
            crs_pipeline=crs_pipeline,
            grid_resources=grid_resources or [],
            metadata=metadata or {},
            supersedes_transform_id=supersedes_transform_id,
        )
        canonical_matrix = self._canonical_transform_matrix(contract)
        with self.database.session() as session:
            self._scoped_frame(session, tenant_id, project_id, source_frame_id)
            self._scoped_frame(session, tenant_id, project_id, target_frame_id)
            active = session.scalar(select(SpatialTransformRow).where(
                SpatialTransformRow.tenant_id == tenant_id,
                SpatialTransformRow.project_id == project_id,
                or_(
                    and_(
                        SpatialTransformRow.source_frame_id == source_frame_id,
                        SpatialTransformRow.target_frame_id == target_frame_id,
                    ),
                    and_(
                        SpatialTransformRow.source_frame_id == target_frame_id,
                        SpatialTransformRow.target_frame_id == source_frame_id,
                    ),
                ),
                SpatialTransformRow.deprecated_at.is_(None),
            ))
            if active and supersedes_transform_id != active.transform_id:
                raise ConflictError(
                    "TRANSFORM_ACTIVE_CONFLICT",
                    "an active transform already exists; replacement must explicitly supersede it",
                    {"active_transform_id": active.transform_id},
                )
            if supersedes_transform_id:
                prior = session.get(SpatialTransformRow, supersedes_transform_id)
                if not prior or prior.tenant_id != tenant_id or prior.project_id != project_id:
                    raise NotFoundError("spatial_transform", supersedes_transform_id)
                if prior.deprecated_at is not None:
                    raise ConflictError(
                        "TRANSFORM_ALREADY_SUPERSEDED",
                        "the selected transform is already deprecated",
                        {"transform_id": supersedes_transform_id},
                    )
                if {prior.source_frame_id, prior.target_frame_id} != {source_frame_id, target_frame_id}:
                    raise ValidationError(
                        "TRANSFORM_SUPERSESSION_SCOPE_MISMATCH",
                        "a replacement transform must connect the same coordinate-frame pair",
                    )
                prior.deprecated_at = db_now()
            row = SpatialTransformRow(
                transform_id=transform_id,
                tenant_id=tenant_id,
                project_id=project_id,
                source_frame_id=source_frame_id,
                target_frame_id=target_frame_id,
                transform_type=transform_type,
                matrix_json=canonical_matrix,
                declared_matrix_json=matrix,
                matrix_layout=matrix_layout,
                multiplication_convention=multiplication_convention,
                direction=direction,
                translation_units=translation_units,
                scale=scale,
                covariance_json=covariance,
                residual_summary_json=residual_summary or {},
                uncertainty_json=contract.uncertainty,
                source_type=source_type,
                authority_class=authority_class.value,
                calibration_id=calibration_id,
                solver_run_id=solver_run_id,
                valid_from=valid_from,
                valid_to=valid_to,
                observed_at=effective_observed_at,
                crs_pipeline=contract.crs_pipeline,
                grid_resources_json=[item.model_dump(mode="json") for item in contract.grid_resources],
                metadata_json=metadata or {},
                supersedes_transform_id=supersedes_transform_id,
                created_by=actor_id,
            )
            session.add(row)
            payload = {
                "transform_id": transform_id,
                "source_frame_id": source_frame_id,
                "target_frame_id": target_frame_id,
                "transform_type": transform_type,
                "matrix_layout": matrix_layout,
                "multiplication_convention": multiplication_convention,
                "direction": direction,
                "translation_units": translation_units,
                "uncertainty": contract.uncertainty,
                "crs_pipeline": contract.crs_pipeline,
                "grid_resources": [item.model_dump(mode="json") for item in contract.grid_resources],
                "authority_class": authority_class.value,
                "contract_hash": canonical_sha256(contract.model_dump(mode="json")),
            }
            session.add(self.events.create(
                session,
                event_type="spatial_transform.registered",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="spatial_transform",
                aggregate_id=transform_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="spatial_transform:register",
                resource_type="spatial_transform",
                resource_id=transform_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
        return {**contract.model_dump(mode="json"), "canonical_matrix": canonical_matrix}

    def convert_units(
        self,
        *,
        tenant_id: str,
        project_id: str,
        frame_id: str,
        values: list[float],
        from_units: str,
        to_units: str = "meter",
        from_scale_to_meters: float | None = None,
        to_scale_to_meters: float | None = None,
    ) -> dict[str, Any]:
        """Convert values at an explicit unit boundary while retaining the source declaration."""
        with self.database.session() as session:
            frame = self._scoped_frame(session, tenant_id, project_id, frame_id)
        source_scale = self._unit_scale(from_units, from_scale_to_meters)
        target_scale = self._unit_scale(to_units, to_scale_to_meters)
        converted = [float(value) * source_scale / target_scale for value in values]
        return {
            "frame_id": frame_id,
            "values": converted,
            "from_units": from_units,
            "to_units": to_units,
            "from_scale_to_meters": source_scale,
            "to_scale_to_meters": target_scale,
            "frame_units": frame.units,
            "frame_original_units": frame.original_units,
            "conversion_hash": canonical_sha256({
                "frame_id": frame_id,
                "values": values,
                "from_units": from_units,
                "to_units": to_units,
                "from_scale_to_meters": source_scale,
                "to_scale_to_meters": target_scale,
            }),
        }

    def resolve_transform(
        self,
        tenant_id: str,
        project_id: str,
        source_frame_id: str,
        target_frame_id: str,
        *,
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        if source_frame_id == target_frame_id:
            return {
                "source_frame_id": source_frame_id,
                "target_frame_id": target_frame_id,
                "matrix": np.eye(4).tolist(),
                "transform_ids": [],
                "uncertainty_m": 0.0,
                "uncertainty_complete": True,
                "unquantified_transform_ids": [],
                "authority_path": [],
                "at_time": at_time.isoformat() if at_time else None,
            }
        with self.database.session() as session:
            frame_predicate = [
                CoordinateFrameRow.tenant_id == tenant_id,
                CoordinateFrameRow.project_id == project_id,
            ]
            transform_predicate = [
                SpatialTransformRow.tenant_id == tenant_id,
                SpatialTransformRow.project_id == project_id,
            ]
            if at_time is None:
                frame_predicate.append(CoordinateFrameRow.deprecated_at.is_(None))
                transform_predicate.append(SpatialTransformRow.deprecated_at.is_(None))
            else:
                frame_predicate.extend([
                    CoordinateFrameRow.created_at <= at_time,
                    or_(CoordinateFrameRow.deprecated_at.is_(None), CoordinateFrameRow.deprecated_at > at_time),
                ])
                transform_predicate.extend([
                    SpatialTransformRow.created_at <= at_time,
                    or_(SpatialTransformRow.deprecated_at.is_(None), SpatialTransformRow.deprecated_at > at_time),
                    or_(SpatialTransformRow.valid_from.is_(None), SpatialTransformRow.valid_from <= at_time),
                    or_(SpatialTransformRow.valid_to.is_(None), SpatialTransformRow.valid_to > at_time),
                ])
            frames = list(session.scalars(select(CoordinateFrameRow).where(*frame_predicate)))
            ids = {item.frame_id for item in frames}
            if source_frame_id not in ids:
                raise NotFoundError("coordinate_frame", source_frame_id)
            if target_frame_id not in ids:
                raise NotFoundError("coordinate_frame", target_frame_id)
            transforms = list(session.scalars(
                select(SpatialTransformRow)
                .where(*transform_predicate)
                .order_by(SpatialTransformRow.created_at.desc(), SpatialTransformRow.transform_id.desc())
            ))

        graph: dict[str, list[tuple[str, np.ndarray, str, float | None, str]]] = {
            frame_id: [] for frame_id in ids
        }
        for frame in frames:
            if frame.parent_frame_id and frame.parent_frame_id in ids and frame.transform_json:
                matrix = np.asarray(frame.transform_json, dtype=np.float64)
                uncertainty = float(frame.uncertainty_m) if frame.uncertainty_m is not None else None
                graph[frame.frame_id].append(
                    (frame.parent_frame_id, matrix, f"frame:{frame.frame_id}", uncertainty, "metric")
                )
                graph[frame.parent_frame_id].append(
                    (frame.frame_id, np.linalg.inv(matrix), f"frame:{frame.frame_id}:inverse", uncertainty, "metric")
                )
        seen_pairs: set[frozenset[str]] = set()
        for transform in transforms:
            pair = frozenset({transform.source_frame_id, transform.target_frame_id})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            matrix = np.asarray(transform.matrix_json, dtype=np.float64)
            uncertainty = self._transform_uncertainty_m(transform)
            graph[transform.source_frame_id].append(
                (transform.target_frame_id, matrix, transform.transform_id, uncertainty, transform.authority_class)
            )
            graph[transform.target_frame_id].append(
                (
                    transform.source_frame_id,
                    np.linalg.inv(matrix),
                    f"{transform.transform_id}:inverse",
                    uncertainty,
                    transform.authority_class,
                )
            )

        # Prefer paths with fully quantified uncertainty, then minimum accumulated
        # translational variance, then minimum hops.  A missing uncertainty declaration
        # is never silently treated as zero.
        serial = 0
        queue: list[tuple[int, float, int, int, str, np.ndarray, list[str], list[str], list[str]]] = [
            (0, 0.0, 0, serial, source_frame_id, np.eye(4), [], [], [])
        ]
        best: dict[str, tuple[int, float, int]] = {source_frame_id: (0, 0.0, 0)}
        while queue:
            unknown_count, variance, hops, _, current, composite, path, authorities, unknown_ids = heapq.heappop(queue)
            if best.get(current) != (unknown_count, variance, hops):
                continue
            if current == target_frame_id:
                return {
                    "source_frame_id": source_frame_id,
                    "target_frame_id": target_frame_id,
                    "matrix": composite.tolist(),
                    "transform_ids": path,
                    "uncertainty_m": float(math.sqrt(variance)) if unknown_count == 0 else None,
                    "uncertainty_complete": unknown_count == 0,
                    "unquantified_transform_ids": unknown_ids,
                    "authority_path": authorities,
                    "at_time": at_time.isoformat() if at_time else None,
                }
            for next_frame, edge, transform_id, uncertainty, authority in graph.get(current, []):
                next_unknown = unknown_count + (1 if uncertainty is None else 0)
                next_variance = variance + (0.0 if uncertainty is None else uncertainty**2)
                next_hops = hops + 1
                cost = (next_unknown, next_variance, next_hops)
                if next_frame in best and best[next_frame] <= cost:
                    continue
                best[next_frame] = cost
                serial += 1
                heapq.heappush(
                    queue,
                    (
                        next_unknown,
                        next_variance,
                        next_hops,
                        serial,
                        next_frame,
                        edge @ composite,
                        [*path, transform_id],
                        [*authorities, authority],
                        [*unknown_ids, transform_id] if uncertainty is None else list(unknown_ids),
                    ),
                )
        raise NotFoundError("coordinate_transform_path", f"{source_frame_id}->{target_frame_id}")

    def register_geometry_manifest(
        self,
        *,
        tenant_id: str,
        project_id: str,
        actor_id: str,
        asset_id: str,
        media_type: str,
        format: str,
        profile: str,
        format_version: str,
        coordinate_frame_id: str,
        units: str,
        bounds: dict[str, list[float]],
        classification: str,
        counts: dict[str, int],
        compression: dict[str, Any],
        source_run_id: str,
        quality: dict[str, Any],
        limitations: list[str] | None = None,
        visual_content_classes: list[str] | None = None,
        audience_policy: dict[str, Any] | None = None,
        viewer_compatibility: list[str] | None = None,
        exporter_compatibility: list[str] | None = None,
        validation_state: str = "pending",
        rebuild_recipe: dict[str, Any] | None = None,
        truth_label: str | None = None,
        representation_id: str | None = None,
        supersedes_manifest_id: str | None = None,
    ) -> dict[str, Any]:
        """Register an immutable, scoped, content-stable geometry declaration.

        The manifest hash deliberately excludes the generated record identifier so
        retries are idempotent. Classification can only remain equal to or become
        more restrictive than the referenced immutable asset, and any linked
        representation must point to the same asset and coordinate frame.
        """
        with self.database.session() as session:
            asset = session.get(AssetRefRow, asset_id)
            if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id or asset.tombstoned_at is not None:
                raise NotFoundError("asset", asset_id)
            self._scoped_frame(session, tenant_id, project_id, coordinate_frame_id)

            try:
                requested_classification = Classification(classification)
                asset_classification = Classification(asset.classification)
            except ValueError as exc:
                raise ValidationError(
                    "GEOMETRY_CLASSIFICATION_INVALID",
                    "geometry and source-asset classifications must use canonical values",
                    {"requested": classification, "asset_classification": asset.classification},
                ) from exc
            if CLASSIFICATION_ORDER[requested_classification.value] < CLASSIFICATION_ORDER[asset_classification.value]:
                raise ValidationError(
                    "GEOMETRY_CLASSIFICATION_DOWNGRADE",
                    "a geometry manifest cannot weaken the source asset classification",
                    {
                        "asset_classification": asset_classification.value,
                        "requested_classification": requested_classification.value,
                    },
                )
            special_classes = {
                Classification.CRITICAL_INFRASTRUCTURE,
                Classification.BIOMETRIC,
                Classification.MINOR,
            }
            if asset_classification in special_classes and requested_classification != asset_classification:
                raise ValidationError(
                    "GEOMETRY_SPECIAL_CLASSIFICATION_MISMATCH",
                    "critical-infrastructure, biometric, and minor classifications propagate without substitution",
                    {
                        "asset_classification": asset_classification.value,
                        "requested_classification": requested_classification.value,
                    },
                )

            representation: RepresentationAssetRow | None = None
            if representation_id:
                representation = session.get(RepresentationAssetRow, representation_id)
                if (
                    not representation
                    or representation.tenant_id != tenant_id
                    or representation.project_id != project_id
                    or representation.deprecated_at is not None
                ):
                    raise NotFoundError("representation", representation_id)
                if representation.asset_id != asset_id:
                    raise ValidationError(
                        "GEOMETRY_REPRESENTATION_ASSET_MISMATCH",
                        "the geometry manifest asset must match the linked representation asset",
                        {"representation_asset_id": representation.asset_id, "manifest_asset_id": asset_id},
                    )
                if representation.coordinate_frame_id != coordinate_frame_id:
                    raise ValidationError(
                        "GEOMETRY_REPRESENTATION_FRAME_MISMATCH",
                        "the geometry manifest frame must match the linked representation frame",
                        {
                            "representation_frame_id": representation.coordinate_frame_id,
                            "manifest_frame_id": coordinate_frame_id,
                        },
                    )

            normalized_candidate = GeometryAssetManifestContract(
                geometry_manifest_id="pending-idempotent-identity",
                asset_id=asset_id,
                representation_id=representation_id,
                media_type=media_type,
                format=format,
                profile=profile,
                format_version=format_version,
                coordinate_frame_id=coordinate_frame_id,
                units=units,
                bounds=bounds,
                counts=counts,
                compression=compression,
                content_sha256=asset.sha256,
                source_run_id=source_run_id,
                quality=quality,
                limitations=sorted(set(limitations or [])),
                visual_content_classes=sorted(set(visual_content_classes or [])),
                classification=requested_classification,
                audience_policy=audience_policy or {},
                viewer_compatibility=sorted(set(viewer_compatibility or [])),
                exporter_compatibility=sorted(set(exporter_compatibility or [])),
                validation_state=validation_state,
                rebuild_recipe=rebuild_recipe or {},
                truth_label=truth_label,
                supersedes_manifest_id=supersedes_manifest_id,
                manifest_hash="0" * 64,
            )
            normalized_body = normalized_candidate.model_dump(mode="json")
            normalized_body.pop("geometry_manifest_id")
            normalized_body.pop("manifest_hash")
            manifest_hash = canonical_sha256(normalized_body)

            existing = session.scalar(select(GeometryAssetManifestRow).where(
                GeometryAssetManifestRow.tenant_id == tenant_id,
                GeometryAssetManifestRow.project_id == project_id,
                GeometryAssetManifestRow.manifest_hash == manifest_hash,
            ))
            if existing:
                return self._geometry_manifest_contract_from_row(existing)

            prior: GeometryAssetManifestRow | None = None
            if supersedes_manifest_id:
                prior = session.get(GeometryAssetManifestRow, supersedes_manifest_id)
                if not prior or prior.tenant_id != tenant_id or prior.project_id != project_id:
                    raise NotFoundError("geometry_manifest", supersedes_manifest_id)
                if prior.deprecated_at is not None or prior.validation_state == "deprecated":
                    raise ConflictError(
                        "GEOMETRY_MANIFEST_ALREADY_SUPERSEDED",
                        "the selected geometry manifest is already deprecated",
                        {"geometry_manifest_id": supersedes_manifest_id},
                    )
                if prior.representation_id != representation_id or prior.profile != profile:
                    raise ValidationError(
                        "GEOMETRY_MANIFEST_SUPERSESSION_SCOPE_MISMATCH",
                        "a replacement manifest must preserve its representation binding and profile",
                        {
                            "prior_representation_id": prior.representation_id,
                            "replacement_representation_id": representation_id,
                            "prior_profile": prior.profile,
                            "replacement_profile": profile,
                        },
                    )

            geometry_manifest_id = new_uuid()
            contract = normalized_candidate.model_copy(update={
                "geometry_manifest_id": geometry_manifest_id,
                "manifest_hash": manifest_hash,
            })
            if prior:
                prior.deprecated_at = db_now()
                prior.validation_state = "deprecated"
            session.add(GeometryAssetManifestRow(
                geometry_manifest_id=geometry_manifest_id,
                tenant_id=tenant_id,
                project_id=project_id,
                asset_id=asset_id,
                representation_id=representation_id,
                media_type=contract.media_type,
                format=contract.format,
                profile=contract.profile,
                format_version=contract.format_version,
                coordinate_frame_id=contract.coordinate_frame_id,
                units=contract.units,
                bounds_json=contract.bounds,
                counts_json=contract.counts,
                compression_json=contract.compression,
                content_sha256=contract.content_sha256,
                source_run_id=contract.source_run_id,
                quality_json=contract.quality,
                limitations_json=contract.limitations,
                visual_content_classes_json=contract.visual_content_classes,
                classification=contract.classification.value,
                audience_policy_json=contract.audience_policy,
                viewer_compatibility_json=contract.viewer_compatibility,
                exporter_compatibility_json=contract.exporter_compatibility,
                validation_state=contract.validation_state,
                rebuild_recipe_json=contract.rebuild_recipe,
                truth_label=contract.truth_label,
                supersedes_manifest_id=contract.supersedes_manifest_id,
                manifest_hash=manifest_hash,
                created_by=actor_id,
            ))
            payload = {
                "geometry_manifest_id": geometry_manifest_id,
                "asset_id": asset_id,
                "representation_id": representation_id,
                "manifest_hash": manifest_hash,
                "validation_state": contract.validation_state,
            }
            session.add(self.events.create(
                session,
                event_type="geometry_manifest.registered",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="geometry_manifest",
                aggregate_id=geometry_manifest_id,
                payload=payload,
                producer="evidence-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="geometry_manifest:register",
                resource_type="geometry_manifest",
                resource_id=geometry_manifest_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return contract.model_dump(mode="json")

    def record_evidence(
        self,
        *,
        tenant_id: str,
        project_id: str,
        asset_id: str,
        source_type: str,
        collected_at: datetime,
        collected_by: str,
        device_or_tool: str,
        location_context: dict[str, Any],
        relevant_region: dict[str, Any],
        relevant_time_start: datetime,
        relevant_time_end: datetime,
        retention_class: str,
        consent_scope: dict[str, Any],
        access_policy: dict[str, Any],
        actor_id: str,
        chain_of_custody: list[dict[str, Any]] | None = None,
        legal_hold: bool = False,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence_id = new_uuid()
        with self.database.session() as session:
            asset = session.get(AssetRefRow, asset_id)
            if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id:
                raise NotFoundError("asset", asset_id)
            if asset.tombstoned_at is not None:
                raise ValidationError("EVIDENCE_ASSET_TOMBSTONED", "tombstoned assets cannot be introduced as new evidence")
            custody = chain_of_custody or [{
                "action": "collected",
                "actor_id": collected_by,
                "timestamp": collected_at.isoformat(),
                "asset_sha256": asset.sha256,
            }]
            relevance_start = relevant_time_start
            relevance_end = relevant_time_end
            region = relevant_region
            effective_access_policy = access_policy
            contract = EvidenceRecordContract(
                evidence_id=evidence_id,
                asset_id=asset_id,
                source_type=source_type,
                collected_at=collected_at,
                collected_by=collected_by,
                device_or_tool=device_or_tool,
                location_context=location_context,
                relevant_region=region,
                relevant_time_start=relevance_start,
                relevant_time_end=relevance_end,
                content_sha256=asset.sha256,
                chain_of_custody=custody,
                retention_class=retention_class,
                legal_hold=legal_hold,
                consent_scope=consent_scope,
                access_policy=effective_access_policy,
                policy=policy or {},
            )
            session.add(EvidenceRecordRow(
                evidence_id=evidence_id,
                tenant_id=tenant_id,
                project_id=project_id,
                asset_id=asset_id,
                source_type=source_type,
                collected_at=collected_at,
                collected_by=collected_by,
                device_or_tool=device_or_tool,
                location_context_json=location_context,
                relevant_region_json=region,
                relevant_time_start=relevance_start,
                relevant_time_end=relevance_end,
                content_sha256=asset.sha256,
                chain_of_custody_json=custody,
                retention_class=retention_class,
                legal_hold=legal_hold,
                consent_scope_json=consent_scope,
                access_policy_json=effective_access_policy,
                policy_json=policy or {},
            ))
            payload = {"evidence_id": evidence_id, "asset_id": asset_id, "content_sha256": asset.sha256, "source_type": source_type}
            session.add(self.events.create(
                session,
                event_type="evidence.recorded",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="evidence",
                aggregate_id=evidence_id,
                payload=payload,
                producer="evidence-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="evidence:record",
                resource_type="evidence",
                resource_id=evidence_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return contract.model_dump(mode="json")

    def get_evidence(
        self,
        *,
        tenant_id: str,
        project_id: str,
        evidence_id: str,
        principal: SignedPrincipal,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Return an evidence record only after project, classification, consent, and row policy checks."""
        denial: dict[str, Any] | None = None
        with self.database.session() as session:
            row = session.get(EvidenceRecordRow, evidence_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("evidence", evidence_id)
            asset = session.get(AssetRefRow, row.asset_id)
            if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id:
                raise ValidationError(
                    "EVIDENCE_ASSET_REFERENCE_BROKEN",
                    "evidence references an unavailable or out-of-scope source asset",
                    {"evidence_id": evidence_id},
                )
            decision = self._evidence_access_decision(
                session,
                row=row,
                asset=asset,
                principal=principal,
                purpose=purpose,
            )
            if not decision["allowed"]:
                denial = decision
            else:
                result = self._evidence_dict(row, asset)
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=principal.subject_id,
                    action="evidence:read",
                    resource_type="evidence",
                    resource_id=evidence_id,
                    outcome="allowed",
                    details={
                        "purpose": decision.get("purpose"),
                        "audience": principal.audience.value,
                        "classification": asset.classification,
                    },
                    session=session,
                )
                return result
        assert denial is not None
        reason = str(denial["reason"])
        self._audit_evidence_denial(
            tenant_id=tenant_id,
            project_id=project_id,
            evidence_id=evidence_id,
            principal=principal,
            reason=reason,
        )
        raise AuthorizationError(
            reason,
            "evidence access denied by server-side consent or access policy",
            {"evidence_id": evidence_id},
        )

    def get_assertion(
        self,
        *,
        tenant_id: str,
        project_id: str,
        assertion_id: str,
        principal: SignedPrincipal,
        purpose: str | None = None,
        include_evidence: bool = False,
    ) -> dict[str, Any]:
        self._require_assertion_collection_access(
            tenant_id=tenant_id,
            project_id=project_id,
            principal=principal,
            purpose=purpose,
            action="assertion:read",
            resource_id=assertion_id,
        )
        denial: AuthorizationError | None = None
        with self.database.session() as session:
            row = session.get(AssertionRow, assertion_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("assertion", assertion_id)
            try:
                evidence = self._authorized_assertion_evidence(
                    session,
                    row=row,
                    principal=principal,
                    purpose=purpose,
                    deny_on_failure=True,
                    audit_disclosure=include_evidence,
                )
            except AuthorizationError as exc:
                denial = exc
            else:
                assert evidence is not None
                result = self._assertion_dict(row)
                result["evidence_access"] = {
                    "authorized_count": len(evidence),
                    "all_authorized": True,
                }
                if include_evidence:
                    result["evidence"] = evidence
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=principal.subject_id,
                    action="assertion:read",
                    resource_type="assertion",
                    resource_id=assertion_id,
                    outcome="allowed",
                    details={"evidence_count": len(evidence), "state": row.state},
                    session=session,
                )
                return result
        assert denial is not None
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            action="assertion:read",
            resource_type="assertion",
            resource_id=assertion_id,
            outcome="denied",
            details={"reason": denial.code},
        )
        raise denial

    def list_assertions(
        self,
        *,
        tenant_id: str,
        project_id: str,
        principal: SignedPrincipal,
        purpose: str | None = None,
        subject_id: str | None = None,
        predicate: str | None = None,
        states: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        self._require_assertion_collection_access(
            tenant_id=tenant_id,
            project_id=project_id,
            principal=principal,
            purpose=purpose,
            action="assertion:list",
            resource_id=project_id,
        )
        if limit < 1 or limit > 500:
            raise ValidationError("ASSERTION_LIST_LIMIT_INVALID", "assertion list limit must be between 1 and 500")
        normalized_states = sorted(set(states or []))
        allowed_states = {"active", "disputed", "superseded", "withdrawn"}
        if set(normalized_states) - allowed_states:
            raise ValidationError(
                "ASSERTION_STATE_FILTER_INVALID",
                "assertion state filter contains an unsupported value",
                {"states": normalized_states},
            )
        with self.database.session() as session:
            query = select(AssertionRow).where(
                AssertionRow.tenant_id == tenant_id,
                AssertionRow.project_id == project_id,
            )
            if subject_id:
                query = query.where(AssertionRow.subject_id == subject_id)
            if predicate:
                query = query.where(AssertionRow.predicate == predicate)
            if normalized_states:
                query = query.where(AssertionRow.state.in_(normalized_states))
            rows = list(session.scalars(query.order_by(
                AssertionRow.asserted_at.desc(), AssertionRow.assertion_id.desc()
            ).limit(limit)))
            items: list[dict[str, Any]] = []
            withheld = 0
            for row in rows:
                evidence = self._authorized_assertion_evidence(
                    session,
                    row=row,
                    principal=principal,
                    purpose=purpose,
                    deny_on_failure=False,
                    audit_disclosure=False,
                )
                if evidence is None:
                    withheld += 1
                    continue
                item = self._assertion_dict(row)
                item["evidence_access"] = {
                    "authorized_count": len(evidence),
                    "all_authorized": True,
                }
                items.append(item)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action="assertion:list",
                resource_type="assertion_collection",
                resource_id=project_id,
                outcome="allowed",
                details={
                    "returned_count": len(items),
                    "withheld_count": withheld,
                    "states": normalized_states,
                },
                session=session,
            )
            privileged_policy_roles = {
                "tenant_admin",
                "project_admin",
                "privacy_officer",
                "reviewer",
            }
            # Ordinary callers must not be able to infer the number of assertions
            # hidden by evidence-level consent or audience restrictions.  Exact
            # counts remain in the immutable audit record and are returned only to
            # roles explicitly trusted to inspect policy enforcement outcomes.
            disclosed_withheld_count = (
                withheld
                if privileged_policy_roles.intersection(principal.roles)
                else None
            )
            return {
                "items": items,
                "withheld_count": disclosed_withheld_count,
                "limit": limit,
            }

    def get_assertion_evidence(
        self,
        *,
        tenant_id: str,
        project_id: str,
        assertion_id: str,
        principal: SignedPrincipal,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        assertion = self.get_assertion(
            tenant_id=tenant_id,
            project_id=project_id,
            assertion_id=assertion_id,
            principal=principal,
            purpose=purpose,
            include_evidence=True,
        )
        return {
            "assertion_id": assertion_id,
            "items": assertion.pop("evidence"),
            "assertion": assertion,
        }

    def record_assertion(
        self,
        *,
        tenant_id: str,
        project_id: str,
        subject_id: str,
        predicate: str,
        object_value: Any,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        confidence: float,
        evidence_ids: list[str],
        actor_id: str,
        asserted_at: datetime | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        producer_id: str | None = None,
        conflicts_with_assertion_ids: list[str] | None = None,
        supersedes_assertion_id: str | None = None,
        state: str = "active",
    ) -> dict[str, Any]:
        assertion_id = new_uuid()
        asserted_at = asserted_at or db_now()
        normalized_evidence_ids = list(dict.fromkeys(evidence_ids))
        with self.database.session() as session:
            evidence_rows = list(session.scalars(select(EvidenceRecordRow).where(
                EvidenceRecordRow.evidence_id.in_(normalized_evidence_ids),
                EvidenceRecordRow.tenant_id == tenant_id,
                EvidenceRecordRow.project_id == project_id,
            )))
            if len(evidence_rows) != len(normalized_evidence_ids):
                raise ValidationError("ASSERTION_EVIDENCE_INCOMPLETE", "assertion evidence references are missing or out of scope")
            self._require_assertion_provenance(
                session,
                evidence_rows=evidence_rows,
                source_class=source_class,
                authority_class=authority_class,
            )
            conflicts = sorted(set(conflicts_with_assertion_ids or []))
            if conflicts:
                conflict_rows = list(session.scalars(select(AssertionRow).where(
                    AssertionRow.assertion_id.in_(conflicts),
                    AssertionRow.tenant_id == tenant_id,
                    AssertionRow.project_id == project_id,
                )))
                if len(conflict_rows) != len(conflicts):
                    raise ValidationError("ASSERTION_CONFLICT_REFERENCE_INVALID", "conflicting assertions are missing or out of scope")
            if supersedes_assertion_id:
                prior = session.get(AssertionRow, supersedes_assertion_id)
                if not prior or prior.tenant_id != tenant_id or prior.project_id != project_id:
                    raise NotFoundError("assertion", supersedes_assertion_id)
                if prior.subject_id != subject_id or prior.predicate != predicate:
                    raise ValidationError(
                        "ASSERTION_SUPERSESSION_SCOPE_MISMATCH",
                        "an assertion may supersede only the same subject and predicate",
                        {
                            "supersedes_assertion_id": supersedes_assertion_id,
                            "expected_subject_id": prior.subject_id,
                            "expected_predicate": prior.predicate,
                        },
                    )
                if prior.state in {"superseded", "withdrawn"}:
                    raise ConflictError(
                        "ASSERTION_ALREADY_INACTIVE",
                        "the assertion selected for supersession is already inactive",
                        {"supersedes_assertion_id": supersedes_assertion_id, "state": prior.state},
                    )
                prior.state = "superseded"
            contract = AssertionContract(
                assertion_id=assertion_id,
                subject_id=subject_id,
                predicate=predicate,
                object_value=object_value,
                source_class=source_class,
                authority_class=authority_class,
                confidence=confidence,
                evidence_ids=normalized_evidence_ids,
                asserted_at=asserted_at,
                valid_from=valid_from,
                valid_to=valid_to,
                author_id=actor_id,
                producer_id=producer_id,
                conflicts_with_assertion_ids=conflicts,
                supersedes_assertion_id=supersedes_assertion_id,
                state=state,
            )
            session.add(AssertionRow(
                assertion_id=assertion_id,
                tenant_id=tenant_id,
                project_id=project_id,
                subject_id=subject_id,
                predicate=predicate,
                object_json=object_value,
                source_class=source_class.value,
                authority_class=authority_class.value,
                confidence=confidence,
                evidence_ids_json=normalized_evidence_ids,
                asserted_at=asserted_at,
                valid_from=valid_from,
                valid_to=valid_to,
                author_id=actor_id,
                producer_id=producer_id,
                conflicts_with_json=conflicts,
                supersedes_assertion_id=supersedes_assertion_id,
                state=state,
                created_by=actor_id,
            ))
            payload = {
                "assertion_id": assertion_id,
                "subject_id": subject_id,
                "predicate": predicate,
                "authority_class": authority_class.value,
                "source_class": source_class.value,
                "asserted_at": asserted_at.isoformat(),
                "valid_from": valid_from.isoformat() if valid_from else None,
                "valid_to": valid_to.isoformat() if valid_to else None,
                "evidence_count": len(normalized_evidence_ids),
                "conflict_count": len(conflicts),
            }
            session.add(self.events.create(
                session,
                event_type="assertion.recorded",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="assertion",
                aggregate_id=assertion_id,
                payload=payload,
                producer="evidence-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="assertion:record",
                resource_type="assertion",
                resource_id=assertion_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return contract.model_dump(mode="json")

    def record_derivation(
        self,
        *,
        tenant_id: str,
        project_id: str,
        activity_type: str,
        input_ids: list[str],
        input_hashes: list[str],
        algorithm_id: str,
        algorithm_version: str,
        parameters_hash: str,
        environment_hash: str,
        code_commit: str,
        output_ids: list[str],
        output_hashes: list[str],
        software: dict[str, Any],
        validation: dict[str, Any],
        started_at: datetime,
        completed_at: datetime,
        quality: dict[str, Any],
        actor_id: str | None = None,
        workload_identity: str | None = None,
        model_manifest_id: str | None = None,
        container_digest: str | None = None,
    ) -> dict[str, Any]:
        derivation_id = new_uuid()
        software = deepcopy(software)
        validation = deepcopy(validation)
        quality = deepcopy(quality)
        if not str(software.get("name", "")).strip() or not str(software.get("version", "")).strip():
            raise ValidationError(
                "DERIVATION_SOFTWARE_IDENTITY_INCOMPLETE",
                "derivation software must declare a name and exact version",
            )

        # The request hash excludes server-generated governance receipts.  It is
        # retained separately from the final derivation hash so an exact retry can
        # return the immutable historical event even after an input is tombstoned
        # or a model approval is later revoked.  Scope is mandatory in both hashes.
        request_hash = canonical_sha256({
            "tenant_id": tenant_id,
            "project_id": project_id,
            "request": {
                "activity_type": activity_type,
                "input_ids": input_ids,
                "input_hashes": input_hashes,
                "algorithm_id": algorithm_id,
                "algorithm_version": algorithm_version,
                "model_manifest_id": model_manifest_id,
                "parameters_hash": parameters_hash,
                "environment_hash": environment_hash,
                "code_commit": code_commit,
                "container_digest": container_digest,
                "output_ids": output_ids,
                "output_hashes": output_hashes,
                "software": software,
                "quality": quality,
                "validation": validation,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "actor_id": actor_id,
                "workload_identity": workload_identity,
            },
        })
        with self.database.session() as session:
            existing = session.scalar(select(DerivationEventRow).where(
                DerivationEventRow.tenant_id == tenant_id,
                DerivationEventRow.project_id == project_id,
                DerivationEventRow.request_hash == request_hash,
            ))
            if existing:
                return self._derivation_dict(existing)

        if model_manifest_id:
            execution = validation.get("execution_context")
            if not isinstance(execution, dict):
                raise ValidationError(
                    "DERIVATION_MODEL_EXECUTION_CONTEXT_REQUIRED",
                    "model-backed derivations require purpose, classification, deployment, region, and commercial-use context",
                )
            required_execution = {"purpose", "classification", "deployment", "region", "commercial"}
            missing_execution = sorted(required_execution - execution.keys())
            if missing_execution:
                raise ValidationError(
                    "DERIVATION_MODEL_EXECUTION_CONTEXT_INCOMPLETE",
                    "model-backed derivation execution context is incomplete",
                    {"missing": missing_execution},
                )
            checkpoint_hash = software.get("model_checkpoint_hash")
            if not isinstance(checkpoint_hash, str) or len(checkpoint_hash) != 64:
                raise ValidationError(
                    "DERIVATION_MODEL_CHECKPOINT_REQUIRED",
                    "model-backed derivations require an exact checkpoint SHA-256",
                )
            try:
                classification = Classification(str(execution["classification"]))
            except ValueError as exc:
                raise ValidationError(
                    "DERIVATION_MODEL_CLASSIFICATION_INVALID",
                    "model execution classification is not recognized",
                ) from exc
            receipt = self.models.authorize(
                model_manifest_id,
                checkpoint_hash=checkpoint_hash,
                purpose=str(execution["purpose"]),
                commercial=bool(execution["commercial"]),
                classification=classification,
                deployment=str(execution["deployment"]),
                region=str(execution["region"]),
                customer_id=str(execution["customer_id"]) if execution.get("customer_id") is not None else None,
            )
            software["model_manifest_id"] = model_manifest_id
            software["model_manifest_hash"] = receipt["manifest_hash"]
            validation["model_governance_receipt"] = receipt
        elif any(key in software for key in ("model_checkpoint_hash", "model_manifest_hash")):
            raise ValidationError(
                "DERIVATION_MODEL_MANIFEST_REQUIRED",
                "model checkpoint metadata cannot be recorded without a governed model manifest identifier",
            )

        contract = DerivationEventContract(
            derivation_id=derivation_id,
            activity_type=activity_type,
            input_ids=input_ids,
            input_hashes=input_hashes,
            algorithm_id=algorithm_id,
            algorithm_version=algorithm_version,
            model_manifest_id=model_manifest_id,
            parameters_hash=parameters_hash,
            environment_hash=environment_hash,
            code_commit=code_commit,
            container_digest=container_digest,
            output_ids=output_ids,
            output_hashes=output_hashes,
            software=software,
            quality=quality,
            validation=validation,
            started_at=started_at,
            completed_at=completed_at,
            actor_id=actor_id,
            workload_identity=workload_identity,
        )
        derivation_hash = canonical_sha256({
            "tenant_id": tenant_id,
            "project_id": project_id,
            "request_hash": request_hash,
            "derivation": contract.model_dump(mode="json", exclude={"derivation_id"}),
        })
        with self.database.session() as session:
            # Recheck after model authorization to close the ordinary retry race.
            existing = session.scalar(select(DerivationEventRow).where(
                DerivationEventRow.tenant_id == tenant_id,
                DerivationEventRow.project_id == project_id,
                DerivationEventRow.request_hash == request_hash,
            ))
            if existing:
                return self._derivation_dict(existing)
            self._validate_derivation_references(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                input_ids=contract.input_ids,
                input_hashes=contract.input_hashes,
                output_ids=contract.output_ids,
                output_hashes=contract.output_hashes,
            )
            session.add(DerivationEventRow(
                derivation_id=derivation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                activity_type=activity_type,
                input_ids_json=input_ids,
                input_hashes_json=input_hashes,
                algorithm_id=algorithm_id,
                algorithm_version=algorithm_version,
                model_manifest_id=model_manifest_id,
                parameters_hash=parameters_hash,
                environment_hash=environment_hash,
                code_commit=code_commit,
                container_digest=container_digest,
                output_ids_json=output_ids,
                output_hashes_json=output_hashes,
                software_json=software,
                quality_json=quality,
                validation_json=validation,
                started_at=started_at,
                completed_at=completed_at,
                actor_id=actor_id,
                workload_identity=workload_identity,
                request_hash=request_hash,
                derivation_hash=derivation_hash,
            ))
            payload = {
                "derivation_id": derivation_id,
                "activity_type": activity_type,
                "algorithm_id": algorithm_id,
                "algorithm_version": algorithm_version,
                "input_count": len(input_ids),
                "output_count": len(output_ids),
                "request_hash": request_hash,
                "derivation_hash": derivation_hash,
            }
            session.add(self.events.create(
                session,
                event_type="derivation.recorded",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="derivation",
                aggregate_id=derivation_id,
                payload=payload,
                producer="evidence-service",
                actor_id=actor_id,
                workload_identity=workload_identity,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id or workload_identity or "unknown",
                action="derivation:record",
                resource_type="derivation",
                resource_id=derivation_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
        return {
            **contract.model_dump(mode="json"),
            "request_hash": request_hash,
            "derivation_hash": derivation_hash,
        }

    def create_annotation(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        coordinate_frame_id: str,
        support_type: str,
        support: dict[str, Any],
        uncertainty_m: float,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        actor_id: str,
        entity_id: str | None = None,
        position: list[float] | None = None,
        orientation: list[float] | None = None,
        normal: list[float] | None = None,
        policy: dict[str, Any] | None = None,
        authored_from_representation_id: str | None = None,
    ) -> dict[str, Any]:
        annotation_id = new_uuid()
        contract = SpatialAnnotationContract(
            annotation_id=annotation_id,
            scene_id=scene_id,
            entity_id=entity_id,
            coordinate_frame_id=coordinate_frame_id,
            support_type=support_type,
            support=support,
            position=position,
            orientation=orientation,
            normal=normal,
            uncertainty_m=uncertainty_m,
            source_class=source_class,
            authority_class=authority_class,
            policy=policy or {},
            authored_from_representation_id=authored_from_representation_id,
        )
        with self.database.session() as session:
            self._scene_exists(session, tenant_id, project_id, scene_id)
            self._scoped_frame(session, tenant_id, project_id, coordinate_frame_id)
            if entity_id:
                entity = session.get(SceneEntityRow, entity_id)
                if (
                    not entity
                    or entity.tenant_id != tenant_id
                    or entity.project_id != project_id
                    or entity.scene_id != scene_id
                    or entity.superseded_at is not None
                ):
                    raise NotFoundError("scene_entity", entity_id)
            if authored_from_representation_id:
                representation = session.get(RepresentationAssetRow, authored_from_representation_id)
                if not representation or representation.tenant_id != tenant_id or representation.project_id != project_id:
                    raise NotFoundError("representation", authored_from_representation_id)
                if representation.kind == "interaction":
                    if authority_class != AuthorityClass.DERIVED_NON_AUTHORITATIVE:
                        raise ValidationError(
                            "PROXY_ANNOTATION_AUTHORITY_INVALID",
                            "annotations authored through interaction proxies remain non-authoritative",
                        )
                    if not support.get("metric_representation_id") and not support.get("semantic_entity_id"):
                        raise ValidationError(
                            "PROXY_ANNOTATION_METRIC_SUPPORT_REQUIRED",
                            "proxy-authored annotations require metric or stable semantic support",
                        )
            session.add(SpatialAnnotationRow(
                annotation_id=annotation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                entity_id=entity_id,
                coordinate_frame_id=coordinate_frame_id,
                support_type=support_type,
                support_json=support,
                position_json=position,
                orientation_json=orientation,
                normal_json=normal,
                uncertainty_m=uncertainty_m,
                source_class=source_class.value,
                authority_class=authority_class.value,
                policy_json=policy or {},
                lifecycle_state="active",
                authored_from_representation_id=authored_from_representation_id,
                created_by=actor_id,
            ))
            payload = {
                "annotation_id": annotation_id,
                "scene_id": scene_id,
                "support_type": support_type,
                "coordinate_frame_id": coordinate_frame_id,
                "authority_class": authority_class.value,
            }
            session.add(self.events.create(
                session,
                event_type="annotation.created",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="annotation",
                aggregate_id=annotation_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="annotation:create",
                resource_type="annotation",
                resource_id=annotation_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
        return contract.model_dump(mode="json")

    def remap_annotations(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        source_representation_id: str,
        target_representation_id: str,
        actor_id: str,
        max_residual_m: float = 0.05,
        min_confidence: float = 0.8,
    ) -> dict[str, Any]:
        if max_residual_m < 0 or not 0 <= min_confidence <= 1:
            raise ValidationError(
                "ANCHOR_REMAP_THRESHOLD_INVALID",
                "anchor remap thresholds must be non-negative and confidence must be within [0,1]",
            )
        with self.database.session() as session:
            source = self._scoped_representation(session, tenant_id, project_id, source_representation_id)
            target = self._scoped_representation(session, tenant_id, project_id, target_representation_id)
            if source.scene_id != scene_id or target.scene_id != scene_id or source.coordinate_frame_id != target.coordinate_frame_id:
                raise ValidationError("ANCHOR_REMAP_SCOPE_MISMATCH", "representations must share scene and coordinate frame")
            annotations = list(session.scalars(select(SpatialAnnotationRow).where(
                SpatialAnnotationRow.tenant_id == tenant_id,
                SpatialAnnotationRow.project_id == project_id,
                SpatialAnnotationRow.scene_id == scene_id,
                SpatialAnnotationRow.authored_from_representation_id == source_representation_id,
                SpatialAnnotationRow.lifecycle_state == "active",
            )))

            target_semantic_ids = {str(value) for value in target.support_map_json.get("semantic_entity_ids", [])}
            target_anchor_ids: set[str] = set()
            target_anchors: dict[str, list[dict[str, Any]]] = {}
            for anchor_index, raw_anchor in enumerate(target.support_map_json.get("anchors", [])):
                if not isinstance(raw_anchor, dict):
                    continue
                position = raw_anchor.get("position", raw_anchor.get("world_position"))
                normalized_position: list[float] | None = None
                if isinstance(position, list) and len(position) == 3:
                    candidate = [float(value) for value in position]
                    if all(math.isfinite(value) for value in candidate):
                        normalized_position = candidate
                confidence = float(raw_anchor.get("confidence", 1.0))
                if not math.isfinite(confidence):
                    confidence = 0.0
                details = {
                    "position": normalized_position,
                    "confidence": max(0.0, min(1.0, confidence)),
                    "anchor_index": anchor_index,
                }
                anchor_id = raw_anchor.get("anchor_id")
                semantic_id = raw_anchor.get("semantic_entity_id")
                keys = {str(value) for value in (anchor_id, semantic_id) if value is not None}
                for key in keys:
                    if anchor_id is not None and key == str(anchor_id):
                        target_anchor_ids.add(key)
                    if semantic_id is not None and key == str(semantic_id):
                        target_semantic_ids.add(key)
                    target_anchors.setdefault(key, []).append(details)

            resolved: list[str] = []
            unresolved: list[str] = []
            review_required: list[str] = []
            per_annotation: list[dict[str, Any]] = []
            remap_id = new_uuid()
            for annotation in annotations:
                support = annotation.support_json
                stable_id_value = support.get("semantic_entity_id") or support.get("anchor_id") or support.get("surface_patch_id")
                stable_id = str(stable_id_value) if stable_id_value is not None else None
                world_stable = annotation.support_type in {"world_point", "plane", "line", "volume"}
                residual_m: float | None = None
                confidence = 1.0 if world_stable else 0.0
                error: str | None = None
                needs_review = False
                candidate_count = 0

                if world_stable:
                    # The two representations have already been proven to share the
                    # same coordinate frame, so an authoritative world-space anchor
                    # does not move merely because a disposable proxy was replaced.
                    residual_m = 0.0
                elif stable_id is None:
                    error = "stable_support_missing"
                elif stable_id not in target_semantic_ids and stable_id not in target_anchor_ids and stable_id not in target_anchors:
                    error = "stable_support_not_found"
                else:
                    candidates = target_anchors.get(stable_id, [])
                    candidate_count = len(candidates)
                    if candidate_count > 1:
                        error = "ambiguous_target_support"
                        needs_review = True
                    elif annotation.support_type == "semantic_entity" and stable_id in target_semantic_ids and not candidates:
                        # Semantic identity is stable across representation revisions.  Since
                        # both representations are in the same canonical coordinate frame,
                        # preserve the annotation's world-space pose even when a disposable
                        # proxy does not publish a duplicate anchor position.
                        residual_m = 0.0
                        confidence = 1.0
                    elif not candidates or candidates[0]["position"] is None:
                        error = "target_position_missing"
                        needs_review = True
                    elif annotation.position_json is None or len(annotation.position_json) != 3:
                        error = "source_position_missing"
                        needs_review = True
                    else:
                        target_anchor = candidates[0]
                        source_position = np.asarray(annotation.position_json, dtype=np.float64)
                        target_position = np.asarray(target_anchor["position"], dtype=np.float64)
                        if not np.isfinite(source_position).all():
                            error = "source_position_non_finite"
                            needs_review = True
                        else:
                            residual_m = float(np.linalg.norm(target_position - source_position))
                            confidence = float(target_anchor["confidence"])
                            if residual_m > max_residual_m:
                                error = "residual_exceeds_threshold"
                                needs_review = True
                            elif confidence < min_confidence:
                                error = "confidence_below_threshold"
                                needs_review = True

                if error is None:
                    annotation.authored_from_representation_id = target_representation_id
                    annotation.lifecycle_state = "active"
                    resolved.append(annotation.annotation_id)
                    decision = "resolved"
                else:
                    annotation.lifecycle_state = "unresolved"
                    unresolved.append(annotation.annotation_id)
                    if needs_review:
                        review_required.append(annotation.annotation_id)
                        decision = "review_required"
                    else:
                        decision = "unresolved"

                prior_support = {
                    key: deepcopy(value)
                    for key, value in support.items()
                    if key != "remap_history"
                }
                remap_history = list(support.get("remap_history", []))
                remap_history.append({
                    "remap_id": remap_id,
                    "source_representation_id": source_representation_id,
                    "target_representation_id": target_representation_id,
                    "prior_support": prior_support,
                    "prior_position": deepcopy(annotation.position_json),
                    "decision": decision,
                    "residual_m": residual_m,
                    "confidence": confidence,
                    "error": error,
                })
                annotation.support_json = {**prior_support, "remap_history": remap_history}

                per_annotation.append({
                    "annotation_id": annotation.annotation_id,
                    "stable_support_id": stable_id,
                    "decision": decision,
                    "residual_m": residual_m,
                    "confidence": confidence,
                    "error": error,
                    "candidate_count": candidate_count,
                })

            metrics = {
                "total": len(annotations),
                "resolved": len(resolved),
                "unresolved": len(unresolved),
                "review_required": len(review_required),
                "resolved_fraction": len(resolved) / len(annotations) if annotations else 1.0,
                "max_residual_m": max_residual_m,
                "min_confidence": min_confidence,
                "per_annotation": sorted(per_annotation, key=lambda item: item["annotation_id"]),
                "review_required_annotation_ids": sorted(review_required),
            }
            body = {
                "remap_id": remap_id,
                "scene_id": scene_id,
                "source_representation_id": source_representation_id,
                "target_representation_id": target_representation_id,
                "resolved_annotation_ids": sorted(resolved),
                "unresolved_annotation_ids": sorted(unresolved),
                "metrics": metrics,
            }
            remap_hash = canonical_sha256(body)
            session.add(AnchorRemapRow(
                remap_id=remap_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                source_representation_id=source_representation_id,
                target_representation_id=target_representation_id,
                resolved_annotation_ids_json=sorted(resolved),
                unresolved_annotation_ids_json=sorted(unresolved),
                metrics_json=metrics,
                remap_hash=remap_hash,
                created_by=actor_id,
            ))
            payload = {
                "remap_id": remap_id,
                "source_representation_id": source_representation_id,
                "target_representation_id": target_representation_id,
                "resolved_count": len(resolved),
                "unresolved_count": len(unresolved),
                "review_required_count": len(review_required),
                "max_residual_m": max_residual_m,
                "remap_hash": remap_hash,
            }
            session.add(self.events.create(
                session,
                event_type="anchor.remapped",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="anchor_remap",
                aggregate_id=remap_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="annotation:remap",
                resource_type="anchor_remap",
                resource_id=remap_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return {**body, "remap_hash": remap_hash}

    def tag_commit(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        commit_id: str,
        name: str,
        actor_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            commit = session.get(SceneCommitRow, commit_id)
            if not commit or commit.tenant_id != tenant_id or commit.project_id != project_id or commit.scene_id != scene_id:
                raise NotFoundError("scene_commit", commit_id)
            existing = session.scalar(select(SceneTagRow).where(
                SceneTagRow.tenant_id == tenant_id,
                SceneTagRow.project_id == project_id,
                SceneTagRow.scene_id == scene_id,
                SceneTagRow.name == name,
            ))
            if existing:
                raise ConflictError("SCENE_TAG_IMMUTABLE", "scene tag names are immutable and cannot be moved")
            tag_id = new_uuid()
            session.add(SceneTagRow(
                tag_id=tag_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                commit_id=commit_id,
                name=name,
                immutable=True,
                metadata_json=metadata or {},
                created_by=actor_id,
            ))
            payload = {"tag_id": tag_id, "scene_id": scene_id, "commit_id": commit_id, "name": name}
            session.add(self.events.create(
                session,
                event_type="scene.tagged",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="scene_tag",
                aggregate_id=tag_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="scene:tag",
                resource_type="scene_tag",
                resource_id=tag_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return payload

    def query_scene_as_of(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        commit_id: str | None = None,
        tag: str | None = None,
        recorded_at: datetime | None = None,
        valid_at: datetime | None = None,
        field_visit_id: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        selectors = [commit_id is not None, tag is not None, recorded_at is not None, valid_at is not None, field_visit_id is not None, branch is not None]
        if sum(selectors) != 1:
            raise ValidationError("TWIN_QUERY_SELECTOR_REQUIRED", "exactly one commit, tag, branch, field visit, recorded time, or valid time selector is required")
        with self.database.session() as session:
            if commit_id:
                commit = session.get(SceneCommitRow, commit_id)
            elif tag:
                tag_row = session.scalar(select(SceneTagRow).where(
                    SceneTagRow.tenant_id == tenant_id,
                    SceneTagRow.project_id == project_id,
                    SceneTagRow.scene_id == scene_id,
                    SceneTagRow.name == tag,
                ))
                commit = session.get(SceneCommitRow, tag_row.commit_id) if tag_row else None
            elif branch:
                branch_row = session.scalar(select(SceneBranchRow).where(
                    SceneBranchRow.tenant_id == tenant_id,
                    SceneBranchRow.project_id == project_id,
                    SceneBranchRow.scene_id == scene_id,
                    SceneBranchRow.name == branch,
                ))
                commit = session.get(SceneCommitRow, branch_row.head_commit_id) if branch_row else None
            else:
                conditions = [
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.scene_id == scene_id,
                ]
                if field_visit_id:
                    conditions.append(SceneCommitRow.field_visit_id == field_visit_id)
                if recorded_at:
                    conditions.append(SceneCommitRow.recorded_at <= recorded_at)
                if valid_at:
                    conditions.extend([
                        or_(SceneCommitRow.valid_from.is_(None), SceneCommitRow.valid_from <= valid_at),
                        or_(SceneCommitRow.valid_to.is_(None), SceneCommitRow.valid_to > valid_at),
                    ])
                commit = session.scalar(select(SceneCommitRow).where(*conditions).order_by(SceneCommitRow.recorded_at.desc(), SceneCommitRow.created_at.desc()))
            if not commit or commit.tenant_id != tenant_id or commit.project_id != project_id or commit.scene_id != scene_id:
                raise NotFoundError("scene_commit", commit_id or tag or branch or field_visit_id or "as_of")
            if canonical_sha256(commit.semantic_snapshot_json) != commit.snapshot_hash:
                raise ValidationError("SCENE_SNAPSHOT_INTEGRITY_FAILED", "scene snapshot hash does not match stored semantic state")
            return self._commit_dict(commit)

    def merge_branches(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        target_branch: str,
        source_branch: str,
        base_commit_id: str,
        actor_id: str,
        message: str,
        approved_review_categories: list[str] | None = None,
    ) -> dict[str, Any]:
        approved = set(approved_review_categories or [])
        with self.database.session() as session:
            target = session.scalar(select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == scene_id,
                SceneBranchRow.name == target_branch,
            ))
            source = session.scalar(select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == scene_id,
                SceneBranchRow.name == source_branch,
            ))
            base = session.get(SceneCommitRow, base_commit_id)
            if not target or not source or not base:
                raise NotFoundError("scene_merge_input", f"{target_branch}:{source_branch}:{base_commit_id}")
            left = session.get(SceneCommitRow, target.head_commit_id)
            right = session.get(SceneCommitRow, source.head_commit_id)
            commits = (base, left, right)
            if any(commit is None for commit in commits) or any(
                commit.tenant_id != tenant_id
                or commit.project_id != project_id
                or commit.scene_id != scene_id
                for commit in commits
                if commit is not None
            ):
                raise ValidationError("SCENE_MERGE_SCOPE_INVALID", "merge commits are outside the requested tenant, project, or scene")
            if base_commit_id not in self._ancestor_ids(session, left.commit_id) or base_commit_id not in self._ancestor_ids(session, right.commit_id):
                raise ValidationError("SCENE_MERGE_BASE_INVALID", "merge base must be an ancestor of both branch heads")
            merged, conflicts = self._semantic_merge(
                base.semantic_snapshot_json,
                left.semantic_snapshot_json,
                right.semantic_snapshot_json,
            )
            protected = sorted({
                category
                for conflict in conflicts
                for category in conflict["categories"]
                if category in self.PROTECTED_MERGE_KEYS
            })
            required_review_categories = protected or (["semantic_conflict"] if conflicts else [])
            unapproved = sorted(set(required_review_categories) - approved)
            if conflicts and unapproved:
                return {
                    "status": "review_required",
                    "target_head": left.commit_id,
                    "source_head": right.commit_id,
                    "base_commit_id": base_commit_id,
                    "conflicts": conflicts,
                    "required_review_categories": required_review_categories,
                    "unapproved_review_categories": unapproved,
                    "published": False,
                }
            if conflicts:
                # Explicit approvals do not select values. The target side remains until
                # a reviewer provides a superseding semantic edit, avoiding silent wins.
                merged = left.semantic_snapshot_json
            snapshot_hash = canonical_sha256(merged)
            commit_id = new_uuid()
            policy_checks = {
                "merge_base": base_commit_id,
                "conflict_count": len(conflicts),
                "approved_review_categories": sorted(approved),
                "automatic_conflict_resolution": False,
            }
            session.add(SceneCommitRow(
                commit_id=commit_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                branch=target_branch,
                parent_ids_json=[left.commit_id, right.commit_id],
                message=message,
                semantic_snapshot_json=merged,
                snapshot_hash=snapshot_hash,
                root_manifest_hash=snapshot_hash,
                change_evidence_ids_json=[],
                policy_checks_json=policy_checks,
                signatures_json=[],
                review_state="approved" if conflicts else "automatic_nonconflicting",
                recorded_at=db_now(),
                created_by=actor_id,
            ))
            target.head_commit_id = commit_id
            payload = {
                "scene_id": scene_id,
                "commit_id": commit_id,
                "parent_ids": [left.commit_id, right.commit_id],
                "snapshot_hash": snapshot_hash,
                "merge_base": base_commit_id,
                "conflict_count": len(conflicts),
            }
            session.add(self.events.create(
                session,
                event_type="scene.committed",
                schema_version="1.0.0",
                tenant_id=tenant_id,
                project_id=project_id,
                aggregate_type="scene_commit",
                aggregate_id=commit_id,
                payload=payload,
                producer="scene-service",
                actor_id=actor_id,
                workload_identity=None,
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="scene:merge",
                resource_type="scene_commit",
                resource_id=commit_id,
                outcome="allowed",
                details=payload,
                session=session,
            )
            return {
                "status": "merged",
                "published": True,
                **self._commit_dict_from_values(
                    commit_id,
                    tenant_id,
                    project_id,
                    scene_id,
                    [left.commit_id, right.commit_id],
                    message,
                    merged,
                    snapshot_hash,
                    policy_checks,
                    branch=target_branch,
                ),
            }

    @staticmethod
    def _ancestor_ids(session: Any, commit_id: str) -> set[str]:
        """Return the commit and all reachable parents, rejecting malformed cycles."""
        ancestors: set[str] = set()
        pending = [commit_id]
        while pending:
            current_id = pending.pop()
            if current_id in ancestors:
                continue
            ancestors.add(current_id)
            current = session.get(SceneCommitRow, current_id)
            if current is None:
                raise ValidationError("SCENE_COMMIT_GRAPH_INVALID", "scene history contains a missing parent", {"commit_id": current_id})
            pending.extend(parent_id for parent_id in current.parent_ids_json if parent_id not in ancestors)
        return ancestors

    @staticmethod
    def _semantic_merge(base: dict[str, Any], left: dict[str, Any], right: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Three-way semantic merge supporting canonical list-based scene snapshots."""
        def entity_map(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
            raw = snapshot.get("entities", [])
            if isinstance(raw, dict):
                return {str(key): deepcopy(value) for key, value in raw.items()}, True
            return {
                str(item["entity_id"]): deepcopy(item)
                for item in raw
                if isinstance(item, dict) and item.get("entity_id") is not None
            }, False

        base_entities, dict_style = entity_map(base)
        left_entities, _ = entity_map(left)
        right_entities, _ = entity_map(right)
        merged_entities: dict[str, dict[str, Any]] = {}
        conflicts: list[dict[str, Any]] = []
        for entity_id in sorted(set(base_entities) | set(left_entities) | set(right_entities)):
            prior = base_entities.get(entity_id)
            left_value = left_entities.get(entity_id)
            right_value = right_entities.get(entity_id)
            if left_value == right_value:
                if left_value is not None:
                    merged_entities[entity_id] = left_value
            elif left_value == prior:
                if right_value is not None:
                    merged_entities[entity_id] = right_value
            elif right_value == prior:
                if left_value is not None:
                    merged_entities[entity_id] = left_value
            else:
                changed_keys: set[str] = set()
                for value in (left_value, right_value):
                    if isinstance(value, dict):
                        changed_keys.update(str(key) for key in value)
                        if isinstance(value.get("attributes"), dict):
                            changed_keys.update(str(key) for key in value["attributes"])
                categories = sorted(changed_keys & SpatialDataService.PROTECTED_MERGE_KEYS)
                conflicts.append({
                    "entity_id": entity_id,
                    "categories": categories or ["semantic_conflict"],
                    "left_hash": canonical_sha256(left_value),
                    "right_hash": canonical_sha256(right_value),
                    "base_hash": canonical_sha256(prior),
                })
                if left_value is not None:
                    merged_entities[entity_id] = left_value

        merged = deepcopy(base)
        merged["entities"] = merged_entities if dict_style else [merged_entities[key] for key in sorted(merged_entities)]
        for top_level in sorted((set(base) | set(left) | set(right)) - {"entities"}):
            prior = base.get(top_level)
            left_value = left.get(top_level)
            right_value = right.get(top_level)
            if left_value == right_value:
                merged[top_level] = deepcopy(left_value)
            elif left_value == prior:
                merged[top_level] = deepcopy(right_value)
            elif right_value == prior:
                merged[top_level] = deepcopy(left_value)
            else:
                conflicts.append({
                    "entity_id": f"scene:{top_level}",
                    "categories": ["representation_binding" if top_level == "representations" else "semantic_conflict"],
                    "left_hash": canonical_sha256(left_value),
                    "right_hash": canonical_sha256(right_value),
                    "base_hash": canonical_sha256(prior),
                })
                merged[top_level] = deepcopy(left_value)
        return merged, conflicts

    def _validate_derivation_references(
        self,
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        input_ids: list[str],
        input_hashes: list[str],
        output_ids: list[str],
        output_hashes: list[str],
    ) -> None:
        """Bind derivation lineage to existing immutable, in-scope records.

        A caller cannot establish provenance by supplying an arbitrary identifier and
        plausible-looking digest.  Every declared input/output must resolve within the
        same tenant/project, must not depend on tombstoned content, and its retained
        immutable hash must exactly match the declared hash.
        """
        if len(set(input_ids)) != len(input_ids) or len(set(output_ids)) != len(output_ids):
            raise ValidationError(
                "DERIVATION_REFERENCE_DUPLICATE",
                "derivation input and output identifiers must be unique within each set",
            )
        overlap = sorted(set(input_ids).intersection(output_ids))
        if overlap:
            raise ValidationError(
                "DERIVATION_IN_PLACE_MUTATION_DENIED",
                "derivations must create immutable outputs rather than overwrite inputs",
                {"reference_ids": overlap},
            )
        for role, identifiers, hashes in (
            ("input", input_ids, input_hashes),
            ("output", output_ids, output_hashes),
        ):
            for reference_id, declared_hash in zip(identifiers, hashes, strict=True):
                actual_hash = self._derivation_reference_hash(
                    session,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    reference_id=reference_id,
                )
                if actual_hash != declared_hash:
                    raise ValidationError(
                        "DERIVATION_REFERENCE_HASH_MISMATCH",
                        "derivation reference hash does not match retained immutable content",
                        {
                            "role": role,
                            "reference_id": reference_id,
                            "declared_hash": declared_hash,
                            "actual_hash": actual_hash,
                        },
                    )

    @staticmethod
    def _derivation_reference_hash(
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        reference_id: str,
    ) -> str:
        """Resolve one scoped lineage identifier to exactly one retained digest.

        SIP identifiers are stable within a resource type but are not assumed to
        be globally type-tagged.  A collision across resource tables is therefore
        rejected rather than resolved by lookup order.
        """
        candidates: list[tuple[str, str]] = []

        asset = session.get(AssetRefRow, reference_id)
        if asset is not None and asset.tenant_id == tenant_id and asset.project_id == project_id:
            if asset.tombstoned_at is not None:
                raise ValidationError(
                    "DERIVATION_REFERENCE_TOMBSTONED",
                    "derivation reference points to tombstoned immutable content",
                    {"reference_id": reference_id, "resource_type": "asset"},
                )
            candidates.append(("asset", asset.sha256))

        evidence = session.get(EvidenceRecordRow, reference_id)
        if evidence is not None and evidence.tenant_id == tenant_id and evidence.project_id == project_id:
            source_asset = session.get(AssetRefRow, evidence.asset_id)
            if (
                source_asset is None
                or source_asset.tenant_id != tenant_id
                or source_asset.project_id != project_id
                or source_asset.tombstoned_at is not None
                or source_asset.sha256 != evidence.content_sha256
            ):
                raise ValidationError(
                    "DERIVATION_EVIDENCE_INTEGRITY_INVALID",
                    "derivation evidence no longer resolves to intact immutable source content",
                    {"reference_id": reference_id},
                )
            candidates.append(("evidence", evidence.content_sha256))

        geometry = session.get(GeometryAssetManifestRow, reference_id)
        if geometry is not None and geometry.tenant_id == tenant_id and geometry.project_id == project_id:
            if geometry.deprecated_at is not None:
                raise ValidationError(
                    "DERIVATION_REFERENCE_DEPRECATED",
                    "new derivations cannot use a deprecated geometry manifest",
                    {"reference_id": reference_id, "resource_type": "geometry_manifest"},
                )
            source_asset = session.get(AssetRefRow, geometry.asset_id)
            if (
                source_asset is None
                or source_asset.tenant_id != tenant_id
                or source_asset.project_id != project_id
                or source_asset.tombstoned_at is not None
                or source_asset.sha256 != geometry.content_sha256
            ):
                raise ValidationError(
                    "DERIVATION_GEOMETRY_SOURCE_INVALID",
                    "geometry manifest does not resolve to its intact immutable content",
                    {"reference_id": reference_id},
                )
            candidates.append(("geometry_manifest", geometry.manifest_hash))

        representation = session.get(RepresentationAssetRow, reference_id)
        if representation is not None and representation.tenant_id == tenant_id and representation.project_id == project_id:
            if representation.deprecated_at is not None or not representation.manifest_hash:
                raise ValidationError(
                    "DERIVATION_REFERENCE_DEPRECATED",
                    "new derivations require an active immutable representation manifest",
                    {"reference_id": reference_id, "resource_type": "representation"},
                )
            source_asset = session.get(AssetRefRow, representation.asset_id)
            if (
                source_asset is None
                or source_asset.tenant_id != tenant_id
                or source_asset.project_id != project_id
                or source_asset.tombstoned_at is not None
            ):
                raise ValidationError(
                    "DERIVATION_REPRESENTATION_SOURCE_INVALID",
                    "representation derivation reference does not resolve to intact source content",
                    {"reference_id": reference_id},
                )
            candidates.append(("representation", representation.manifest_hash))

        commit = session.get(SceneCommitRow, reference_id)
        if commit is not None and commit.tenant_id == tenant_id and commit.project_id == project_id:
            candidates.append(("scene_commit", commit.root_manifest_hash or commit.snapshot_hash))

        prior_derivation = session.get(DerivationEventRow, reference_id)
        if prior_derivation is not None and prior_derivation.tenant_id == tenant_id and prior_derivation.project_id == project_id:
            candidates.append(("derivation", prior_derivation.derivation_hash))

        frame = session.get(CoordinateFrameRow, reference_id)
        if frame is not None and frame.tenant_id == tenant_id and frame.project_id == project_id:
            if frame.deprecated_at is not None:
                raise ValidationError(
                    "DERIVATION_REFERENCE_DEPRECATED",
                    "new derivations cannot use a deprecated coordinate frame",
                    {"reference_id": reference_id, "resource_type": "coordinate_frame"},
                )
            candidates.append(("coordinate_frame", canonical_sha256({
                "frame_id": frame.frame_id,
                "name": frame.name,
                "parent_frame_id": frame.parent_frame_id,
                "semantic_type": frame.semantic_type,
                "convention": frame.convention,
                "units": frame.units,
                "unit_scale_to_meters": frame.unit_scale_to_meters,
                "original_units": frame.original_units,
                "original_unit_scale_to_meters": frame.original_unit_scale_to_meters,
                "axis_convention": frame.axis_convention,
                "axis_directions": frame.axis_directions_json,
                "handedness": frame.handedness,
                "origin_description": frame.origin_description,
                "gravity_alignment": frame.gravity_alignment,
                "source": frame.source,
                "crs_identifier": frame.crs_identifier,
                "vertical_datum": frame.vertical_datum,
                "geodetic": frame.geodetic_json,
                "metadata": frame.metadata_json,
                "transform_to_parent": frame.transform_json,
                "uncertainty_m": frame.uncertainty_m,
                "supersedes_frame_id": frame.supersedes_frame_id,
            })))

        transform = session.get(SpatialTransformRow, reference_id)
        if transform is not None and transform.tenant_id == tenant_id and transform.project_id == project_id:
            if transform.deprecated_at is not None:
                raise ValidationError(
                    "DERIVATION_REFERENCE_DEPRECATED",
                    "new derivations cannot use a deprecated spatial transform",
                    {"reference_id": reference_id, "resource_type": "spatial_transform"},
                )
            candidates.append(("spatial_transform", canonical_sha256({
                "transform_id": transform.transform_id,
                "source_frame_id": transform.source_frame_id,
                "target_frame_id": transform.target_frame_id,
                "transform_type": transform.transform_type,
                "matrix": transform.matrix_json,
                "declared_matrix": transform.declared_matrix_json,
                "matrix_layout": transform.matrix_layout,
                "multiplication_convention": transform.multiplication_convention,
                "direction": transform.direction,
                "translation_units": transform.translation_units,
                "scale": transform.scale,
                "covariance": transform.covariance_json,
                "residual_summary": transform.residual_summary_json,
                "uncertainty": transform.uncertainty_json,
                "source_type": transform.source_type,
                "authority_class": transform.authority_class,
                "calibration_id": transform.calibration_id,
                "solver_run_id": transform.solver_run_id,
                "valid_from": transform.valid_from.isoformat() if transform.valid_from else None,
                "valid_to": transform.valid_to.isoformat() if transform.valid_to else None,
                "observed_at": transform.observed_at.isoformat() if transform.observed_at else None,
                "crs_pipeline": transform.crs_pipeline,
                "grid_resources": transform.grid_resources_json,
                "metadata": transform.metadata_json,
                "supersedes_transform_id": transform.supersedes_transform_id,
                "created_by": transform.created_by,
            })))

        assertion = session.get(AssertionRow, reference_id)
        if assertion is not None and assertion.tenant_id == tenant_id and assertion.project_id == project_id:
            candidates.append(("assertion", canonical_sha256({
                "assertion_id": assertion.assertion_id,
                "subject_id": assertion.subject_id,
                "predicate": assertion.predicate,
                "object": assertion.object_json,
                "source_class": assertion.source_class,
                "authority_class": assertion.authority_class,
                "confidence": assertion.confidence,
                "evidence_ids": assertion.evidence_ids_json,
                "asserted_at": assertion.asserted_at.isoformat(),
                "valid_from": assertion.valid_from.isoformat() if assertion.valid_from else None,
                "valid_to": assertion.valid_to.isoformat() if assertion.valid_to else None,
                "author_id": assertion.author_id,
                "producer_id": assertion.producer_id,
                "conflicts_with": assertion.conflicts_with_json,
                "supersedes_assertion_id": assertion.supersedes_assertion_id,
            })))

        annotation = session.get(SpatialAnnotationRow, reference_id)
        if annotation is not None and annotation.tenant_id == tenant_id and annotation.project_id == project_id:
            candidates.append(("spatial_annotation", canonical_sha256({
                "annotation_id": annotation.annotation_id,
                "scene_id": annotation.scene_id,
                "entity_id": annotation.entity_id,
                "coordinate_frame_id": annotation.coordinate_frame_id,
                "support_type": annotation.support_type,
                "support": annotation.support_json,
                "position": annotation.position_json,
                "orientation": annotation.orientation_json,
                "normal": annotation.normal_json,
                "uncertainty_m": annotation.uncertainty_m,
                "source_class": annotation.source_class,
                "authority_class": annotation.authority_class,
                "policy": annotation.policy_json,
                "lifecycle_state": annotation.lifecycle_state,
                "authored_from_representation_id": annotation.authored_from_representation_id,
                "created_by": annotation.created_by,
                "created_at": annotation.created_at.isoformat(),
            })))

        if not candidates:
            raise NotFoundError("derivation_reference", reference_id)
        if len(candidates) > 1:
            raise ValidationError(
                "DERIVATION_REFERENCE_AMBIGUOUS",
                "lineage identifier resolves to more than one resource type",
                {"reference_id": reference_id, "resource_types": sorted(kind for kind, _ in candidates)},
            )
        return candidates[0][1]

    def _require_assertion_collection_access(
        self,
        *,
        tenant_id: str,
        project_id: str,
        principal: SignedPrincipal,
        purpose: str | None,
        action: str,
        resource_id: str,
    ) -> None:
        """Authorize the assertion resource even when it has no linked evidence.

        Linked evidence applies stricter row-level classification, region, consent,
        and audience checks.  This project-level guard prevents evidence-free or
        malformed legacy assertions from bypassing tenant/project/action policy.
        """
        normalized_purpose = purpose.strip() if isinstance(purpose, str) and purpose.strip() else None
        decision = self.policy.authorize(
            principal,
            action="scene:read",
            tenant_id=tenant_id,
            project_id=project_id,
            purpose=normalized_purpose,
            classification=Classification.INTERNAL.value,
            audit_denial=False,
        )
        if decision.allowed:
            return
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            action=action,
            resource_type="assertion" if action == "assertion:read" else "assertion_collection",
            resource_id=resource_id,
            outcome="denied",
            details={"reason": decision.reason_code, "purpose": normalized_purpose},
        )
        raise AuthorizationError(
            decision.reason_code,
            "assertion access denied by server-side project policy",
            {"resource_id": resource_id},
        )

    def _evidence_access_decision(
        self,
        session: Any,
        *,
        row: EvidenceRecordRow,
        asset: AssetRefRow,
        principal: SignedPrincipal,
        purpose: str | None,
    ) -> dict[str, Any]:
        """Evaluate every server-side evidence policy without trusting client filtering.

        Project authorization, asset classification, spatial restrictions, evidence
        access policy, inline consent declarations, and referenced consent grants all
        participate in one fail-closed decision.  The method intentionally returns a
        small reason code rather than policy contents so denial paths cannot disclose
        protected subjects, grants, or regions.
        """
        normalized_purpose = purpose.strip() if isinstance(purpose, str) and purpose.strip() else None
        if asset.tombstoned_at is not None:
            return {"allowed": False, "reason": "EVIDENCE_SOURCE_TOMBSTONED", "purpose": normalized_purpose}

        region = row.relevant_region_json or {}
        spatial_region_id = region.get("region_id")
        decision = self.policy.authorize(
            principal,
            action="asset:read",
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            purpose=normalized_purpose,
            classification=asset.classification,
            spatial_region_id=str(spatial_region_id) if spatial_region_id else None,
            audit_denial=False,
        )
        if not decision.allowed:
            return {
                "allowed": False,
                "reason": decision.reason_code,
                "purpose": normalized_purpose,
                "obligations": decision.obligations,
            }

        policy = row.access_policy_json or {}
        if bool(policy.get("deny_all")):
            return {"allowed": False, "reason": "EVIDENCE_POLICY_DENY_ALL", "purpose": normalized_purpose}

        denied_subjects = {str(value) for value in policy.get("denied_subject_ids", [])}
        if principal.subject_id in denied_subjects:
            return {"allowed": False, "reason": "EVIDENCE_SUBJECT_DENIED", "purpose": normalized_purpose}

        allowed_subjects = {str(value) for value in policy.get("allowed_subject_ids", [])}
        if allowed_subjects and principal.subject_id not in allowed_subjects:
            return {"allowed": False, "reason": "EVIDENCE_SUBJECT_NOT_ALLOWED", "purpose": normalized_purpose}

        allowed_roles = {str(value) for value in policy.get("allowed_roles", [])}
        if allowed_roles and not allowed_roles.intersection(principal.roles):
            return {"allowed": False, "reason": "EVIDENCE_ROLE_DENIED", "purpose": normalized_purpose}

        allowed_audiences = {str(value) for value in policy.get("allowed_audiences", [])}
        # The platform-wide policy model treats PRIVATE as the most restrictive
        # administrative/reviewer audience.  Inline consent below remains exact.
        if (
            allowed_audiences
            and principal.audience.value not in allowed_audiences
            and principal.audience is not Audience.PRIVATE
        ):
            return {"allowed": False, "reason": "EVIDENCE_AUDIENCE_DENIED", "purpose": normalized_purpose}

        allowed_purposes = {str(value) for value in policy.get("allowed_purposes", [])}
        if allowed_purposes:
            if normalized_purpose is None:
                return {"allowed": False, "reason": "EVIDENCE_PURPOSE_REQUIRED", "purpose": None}
            if normalized_purpose not in allowed_purposes:
                return {"allowed": False, "reason": "EVIDENCE_PURPOSE_DENIED", "purpose": normalized_purpose}
            if normalized_purpose not in principal.purposes and "tenant_admin" not in principal.roles:
                return {"allowed": False, "reason": "PURPOSE_DENIED", "purpose": normalized_purpose}

        consent = row.consent_scope_json or {}
        state = str(consent.get("state", "active")).strip().lower()
        if bool(consent.get("revoked")) or state in {"revoked", "withdrawn", "denied"}:
            return {"allowed": False, "reason": "EVIDENCE_CONSENT_REVOKED", "purpose": normalized_purpose}

        expires_at = self._policy_time(consent.get("expires_at"))
        now = db_now()
        if expires_at is not None and expires_at <= now:
            return {"allowed": False, "reason": "EVIDENCE_CONSENT_EXPIRED", "purpose": normalized_purpose}

        consent_audiences = {str(value) for value in consent.get("allowed_audiences", [])}
        if consent_audiences and principal.audience.value not in consent_audiences:
            return {"allowed": False, "reason": "EVIDENCE_CONSENT_AUDIENCE_DENIED", "purpose": normalized_purpose}

        consent_purposes = {str(value) for value in consent.get("allowed_purposes", [])}
        if consent_purposes:
            if normalized_purpose is None:
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_PURPOSE_REQUIRED", "purpose": None}
            if normalized_purpose not in consent_purposes:
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_PURPOSE_DENIED", "purpose": normalized_purpose}

        grant_ids = sorted({
            str(value)
            for key in ("consent_grant_ids", "grant_ids")
            for value in consent.get(key, [])
            if str(value).strip()
        })
        raw_required_scopes = consent.get("required_scopes", ["evidence:read"])
        if isinstance(raw_required_scopes, str):
            required_scopes = {raw_required_scopes}
        else:
            required_scopes = {str(value) for value in (raw_required_scopes or ["evidence:read"])}
        required_scopes.discard("")
        if not required_scopes:
            required_scopes = {"evidence:read"}

        for grant_id in grant_ids:
            grant = session.get(ConsentGrantRow, grant_id)
            if not grant or grant.tenant_id != row.tenant_id or grant.project_id != row.project_id:
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_UNAVAILABLE", "purpose": normalized_purpose}
            if grant.state != "active" or grant.revoked_at is not None:
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_REVOKED", "purpose": normalized_purpose}
            if grant.expires_at is not None and self._aware_time(grant.expires_at) <= now:
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_EXPIRED", "purpose": normalized_purpose}
            if normalized_purpose is None or normalized_purpose not in set(grant.purposes_json or []):
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_PURPOSE_DENIED", "purpose": normalized_purpose}
            if principal.audience.value not in set(grant.audiences_json or []):
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_AUDIENCE_DENIED", "purpose": normalized_purpose}
            grant_scopes = {str(value) for value in (grant.scopes_json or [])}
            if "*" not in grant_scopes and not required_scopes.issubset(grant_scopes):
                return {"allowed": False, "reason": "EVIDENCE_CONSENT_GRANT_SCOPE_DENIED", "purpose": normalized_purpose}

        return {
            "allowed": True,
            "reason": "ALLOW",
            "purpose": normalized_purpose,
            "obligations": decision.obligations,
        }

    def _audit_evidence_denial(
        self,
        *,
        tenant_id: str,
        project_id: str,
        evidence_id: str,
        principal: SignedPrincipal,
        reason: str,
    ) -> None:
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            action="evidence:read",
            resource_type="evidence",
            resource_id=evidence_id,
            outcome="denied",
            details={"reason": reason},
        )

    @staticmethod
    def _evidence_dict(row: EvidenceRecordRow, asset: AssetRefRow) -> dict[str, Any]:
        return {
            "evidence_id": row.evidence_id,
            "asset_id": row.asset_id,
            "source_type": row.source_type,
            "collected_at": row.collected_at,
            "collected_by": row.collected_by,
            "device_or_tool": row.device_or_tool,
            "location_context": row.location_context_json,
            "relevant_region": row.relevant_region_json,
            "relevant_time_start": row.relevant_time_start,
            "relevant_time_end": row.relevant_time_end,
            "content_sha256": row.content_sha256,
            "chain_of_custody": row.chain_of_custody_json,
            "retention_class": row.retention_class,
            "legal_hold": row.legal_hold,
            "consent_scope": row.consent_scope_json,
            "access_policy": row.access_policy_json,
            "policy": row.policy_json,
            "created_at": row.created_at,
            "asset": {
                "asset_id": asset.asset_id,
                "sha256": asset.sha256,
                "classification": asset.classification,
                "retention_class": asset.retention_class,
                "source_class": asset.source_class,
                "authority_class": asset.authority_class,
                "provenance": asset.provenance_json,
                "legal_hold": asset.legal_hold,
                "tombstoned": asset.tombstoned_at is not None,
            },
        }

    def _authorized_assertion_evidence(
        self,
        session: Any,
        *,
        row: AssertionRow,
        principal: SignedPrincipal,
        purpose: str | None,
        deny_on_failure: bool,
        audit_disclosure: bool,
    ) -> list[dict[str, Any]] | None:
        results: list[dict[str, Any]] = []
        for evidence_id in dict.fromkeys(row.evidence_ids_json or []):
            evidence = session.get(EvidenceRecordRow, evidence_id)
            if not evidence or evidence.tenant_id != row.tenant_id or evidence.project_id != row.project_id:
                if audit_disclosure:
                    self.audit.append(
                        tenant_id=row.tenant_id,
                        project_id=row.project_id,
                        actor_id=principal.subject_id,
                        action="evidence:read",
                        resource_type="evidence",
                        resource_id=evidence_id,
                        outcome="denied",
                        details={
                            "reason": "ASSERTION_EVIDENCE_UNAVAILABLE",
                            "via_assertion_id": row.assertion_id,
                        },
                        session=session,
                    )
                if deny_on_failure:
                    raise AuthorizationError(
                        "ASSERTION_EVIDENCE_UNAVAILABLE",
                        "assertion evidence is unavailable or outside the authorized scope",
                        {"assertion_id": row.assertion_id},
                    )
                return None
            asset = session.get(AssetRefRow, evidence.asset_id)
            if not asset or asset.tenant_id != row.tenant_id or asset.project_id != row.project_id:
                if audit_disclosure:
                    self.audit.append(
                        tenant_id=row.tenant_id,
                        project_id=row.project_id,
                        actor_id=principal.subject_id,
                        action="evidence:read",
                        resource_type="evidence",
                        resource_id=evidence_id,
                        outcome="denied",
                        details={
                            "reason": "ASSERTION_EVIDENCE_UNAVAILABLE",
                            "via_assertion_id": row.assertion_id,
                        },
                        session=session,
                    )
                if deny_on_failure:
                    raise AuthorizationError(
                        "ASSERTION_EVIDENCE_UNAVAILABLE",
                        "assertion evidence source is unavailable or outside the authorized scope",
                        {"assertion_id": row.assertion_id},
                    )
                return None
            decision = self._evidence_access_decision(
                session,
                row=evidence,
                asset=asset,
                principal=principal,
                purpose=purpose,
            )
            if not decision["allowed"]:
                if audit_disclosure:
                    self.audit.append(
                        tenant_id=row.tenant_id,
                        project_id=row.project_id,
                        actor_id=principal.subject_id,
                        action="evidence:read",
                        resource_type="evidence",
                        resource_id=evidence_id,
                        outcome="denied",
                        details={
                            "reason": str(decision["reason"]),
                            "via_assertion_id": row.assertion_id,
                        },
                        session=session,
                    )
                if deny_on_failure:
                    raise AuthorizationError(
                        str(decision["reason"]),
                        "assertion access denied because linked evidence is not authorized",
                        {"assertion_id": row.assertion_id},
                    )
                return None
            if audit_disclosure:
                self.audit.append(
                    tenant_id=row.tenant_id,
                    project_id=row.project_id,
                    actor_id=principal.subject_id,
                    action="evidence:read",
                    resource_type="evidence",
                    resource_id=evidence_id,
                    outcome="allowed",
                    details={
                        "purpose": decision.get("purpose"),
                        "audience": principal.audience.value,
                        "classification": asset.classification,
                        "via_assertion_id": row.assertion_id,
                    },
                    session=session,
                )
            results.append(self._evidence_dict(evidence, asset))
        return results

    def _require_assertion_provenance(
        self,
        session: Any,
        *,
        evidence_rows: list[EvidenceRecordRow],
        source_class: SourceClass,
        authority_class: AuthorityClass,
    ) -> None:
        gated = source_class in {SourceClass.VERIFIED, SourceClass.CORROBORATED} or authority_class is AuthorityClass.FIELD_VERIFIED
        if not gated:
            return

        gaps: list[dict[str, Any]] = []
        independence_keys: set[str] = set()
        distinct_assets: set[str] = set()
        for evidence in evidence_rows:
            asset = session.get(AssetRefRow, evidence.asset_id)
            evidence_gaps: list[str] = []
            if not asset or asset.tenant_id != evidence.tenant_id or asset.project_id != evidence.project_id:
                evidence_gaps.append("immutable_source_asset_missing")
                asset = None
            elif asset.tombstoned_at is not None:
                evidence_gaps.append("immutable_source_asset_tombstoned")
            else:
                distinct_assets.add(asset.asset_id)
                if evidence.content_sha256 != asset.sha256:
                    evidence_gaps.append("content_hash_mismatch")
                provenance = asset.provenance_json or {}
                source_ids = [str(value) for value in provenance.get("source_ids", []) if str(value).strip()]
                if not source_ids:
                    evidence_gaps.append("source_ids_missing")
                if provenance.get("output_hash") != asset.sha256:
                    evidence_gaps.append("provenance_output_hash_missing_or_mismatched")
                validation_result_id = provenance.get("validation_result_id")
                if not isinstance(validation_result_id, str) or not validation_result_id.strip():
                    evidence_gaps.append("validation_result_missing")
                independence_keys.add(canonical_sha256({
                    "asset_sha256": asset.sha256,
                    "source_ids": sorted(set(source_ids)),
                    "source_type": evidence.source_type,
                    "collected_by": evidence.collected_by,
                }))

                if asset.source_class in {
                    SourceClass.INFERRED.value,
                    SourceClass.GENERATED.value,
                    SourceClass.CORROBORATED.value,
                }:
                    derivation = next((
                        row
                        for row in session.scalars(select(DerivationEventRow).where(
                            DerivationEventRow.tenant_id == evidence.tenant_id,
                            DerivationEventRow.project_id == evidence.project_id,
                        ))
                        if asset.asset_id in (row.output_ids_json or [])
                        and asset.sha256 in (row.output_hashes_json or [])
                    ), None)
                    if derivation is None:
                        evidence_gaps.append("derivation_event_missing")
                    else:
                        if not derivation.input_ids_json:
                            evidence_gaps.append("derivation_inputs_missing")
                        if not derivation.software_json or not derivation.validation_json:
                            evidence_gaps.append("derivation_software_or_validation_missing")
                        if not derivation.parameters_hash or not derivation.environment_hash or not derivation.code_commit:
                            evidence_gaps.append("derivation_execution_identity_missing")
                        if asset.source_class in {SourceClass.INFERRED.value, SourceClass.GENERATED.value} and not derivation.model_manifest_id:
                            evidence_gaps.append("model_manifest_missing")

            if not evidence.relevant_region_json:
                evidence_gaps.append("relevant_region_missing")
            if evidence.relevant_time_start is None or evidence.relevant_time_end is None:
                evidence_gaps.append("relevant_time_missing")
            elif evidence.relevant_time_end < evidence.relevant_time_start:
                evidence_gaps.append("relevant_time_invalid")
            if not evidence.chain_of_custody_json:
                evidence_gaps.append("chain_of_custody_missing")
            else:
                for index, entry in enumerate(evidence.chain_of_custody_json):
                    if not isinstance(entry, dict) or not {
                        "action", "actor_id", "timestamp", "asset_sha256"
                    }.issubset(entry):
                        evidence_gaps.append(f"chain_of_custody_entry_{index}_incomplete")
            if not evidence.consent_scope_json:
                evidence_gaps.append("consent_scope_missing")
            if not evidence.access_policy_json:
                evidence_gaps.append("access_policy_missing")
            if not evidence.collected_by or not evidence.device_or_tool:
                evidence_gaps.append("contributor_or_device_missing")
            if evidence_gaps:
                gaps.append({"evidence_id": evidence.evidence_id, "gaps": sorted(set(evidence_gaps))})

        if gaps:
            raise ValidationError(
                "ASSERTION_PROVENANCE_INCOMPLETE",
                "a provenance gap prevents verified, field-verified, or corroborated status",
                {"evidence_gaps": gaps},
            )

        if source_class is SourceClass.CORROBORATED:
            if len(evidence_rows) < 2 or len(distinct_assets) < 2 or len(independence_keys) < 2:
                raise ValidationError(
                    "ASSERTION_CORROBORATION_INSUFFICIENT",
                    "corroborated status requires at least two independently rooted immutable evidence sources",
                    {
                        "evidence_count": len(evidence_rows),
                        "distinct_asset_count": len(distinct_assets),
                        "independent_source_count": len(independence_keys),
                    },
                )

    @staticmethod
    def _assertion_dict(row: AssertionRow) -> dict[str, Any]:
        return {
            "assertion_id": row.assertion_id,
            "subject_id": row.subject_id,
            "predicate": row.predicate,
            "object_value": row.object_json,
            "source_class": row.source_class,
            "authority_class": row.authority_class,
            "confidence": row.confidence,
            "evidence_ids": row.evidence_ids_json,
            "asserted_at": row.asserted_at,
            "valid_from": row.valid_from,
            "valid_to": row.valid_to,
            "author_id": row.author_id,
            "producer_id": row.producer_id,
            "conflicts_with_assertion_ids": row.conflicts_with_json,
            "supersedes_assertion_id": row.supersedes_assertion_id,
            "state": row.state,
            "created_by": row.created_by,
            "created_at": row.created_at,
        }

    @staticmethod
    def _aware_time(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @staticmethod
    def _policy_time(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return SpatialDataService._aware_time(value)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = f"{normalized[:-1]}+00:00"
            try:
                return SpatialDataService._aware_time(datetime.fromisoformat(normalized))
            except ValueError as exc:
                raise ValidationError(
                    "EVIDENCE_POLICY_TIME_INVALID",
                    "evidence consent expiry must be an ISO-8601 timestamp",
                ) from exc
        raise ValidationError(
            "EVIDENCE_POLICY_TIME_INVALID",
            "evidence consent expiry must be an ISO-8601 timestamp",
        )

    @staticmethod
    def _geometry_manifest_contract_from_row(row: GeometryAssetManifestRow) -> dict[str, Any]:
        return GeometryAssetManifestContract(
            geometry_manifest_id=row.geometry_manifest_id,
            asset_id=row.asset_id,
            representation_id=row.representation_id,
            media_type=row.media_type,
            format=row.format,
            profile=row.profile,
            format_version=row.format_version,
            coordinate_frame_id=row.coordinate_frame_id,
            units=row.units,
            bounds=row.bounds_json,
            counts=row.counts_json,
            compression=row.compression_json,
            content_sha256=row.content_sha256,
            source_run_id=row.source_run_id,
            quality=row.quality_json,
            limitations=row.limitations_json,
            visual_content_classes=row.visual_content_classes_json,
            classification=row.classification,
            audience_policy=row.audience_policy_json,
            viewer_compatibility=row.viewer_compatibility_json,
            exporter_compatibility=row.exporter_compatibility_json,
            validation_state=row.validation_state,
            rebuild_recipe=row.rebuild_recipe_json,
            truth_label=row.truth_label,
            supersedes_manifest_id=row.supersedes_manifest_id,
            manifest_hash=row.manifest_hash,
        ).model_dump(mode="json")

    @staticmethod
    def _unit_scale(units: str, explicit_scale: float | None = None) -> float:
        known = {
            "meter": 1.0,
            "metre": 1.0,
            "millimeter": 0.001,
            "millimetre": 0.001,
            "centimeter": 0.01,
            "centimetre": 0.01,
            "foot": 0.3048,
            "feet": 0.3048,
            "inch": 0.0254,
        }.get(units.strip().lower())
        if explicit_scale is None:
            if known is None:
                raise ValidationError(
                    "UNIT_SCALE_REQUIRED",
                    "unknown units require an explicit scale to meters",
                    {"units": units},
                )
            return known
        if explicit_scale <= 0 or not math.isfinite(explicit_scale):
            raise ValidationError("UNIT_SCALE_INVALID", "unit scale must be a finite positive value")
        if known is not None and not math.isclose(explicit_scale, known, rel_tol=0, abs_tol=1e-12):
            raise ValidationError(
                "UNIT_SCALE_CONFLICT",
                "explicit scale conflicts with the declared standard unit",
                {"units": units, "expected": known, "provided": explicit_scale},
            )
        return float(explicit_scale)

    @staticmethod
    def _canonical_transform_matrix(contract: SpatialTransformContract) -> list[list[float]]:
        """Normalize declared storage/direction conventions to row-major, source-to-target, meters."""
        matrix = np.asarray(contract.matrix, dtype=np.float64)
        if contract.matrix_layout == "column_major":
            matrix = matrix.T
        if contract.multiplication_convention == "row_vector_post_multiply":
            matrix = matrix.T
        if not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
            raise ValidationError(
                "TRANSFORM_HOMOGENEOUS_INVALID",
                "the declared layout and multiplication convention do not normalize to a homogeneous matrix",
            )
        rotation = matrix[:3, :3]
        gram = rotation.T @ rotation
        determinant = float(np.linalg.det(rotation))
        if not np.allclose(gram, np.eye(3), rtol=0, atol=1e-7) or not math.isclose(
            determinant, 1.0, rel_tol=0, abs_tol=1e-7
        ):
            raise ValidationError(
                "TRANSFORM_RIGID_COMPONENT_INVALID",
                "SE3/SIM3 matrices require a proper orthonormal rotation; shear, reflection, and embedded scale are rejected",
                {"determinant": determinant},
            )
        translation_scale = SpatialDataService._unit_scale(contract.translation_units)
        matrix = matrix.copy()
        matrix[:3, 3] *= translation_scale
        if contract.transform_type == "SIM3" and not math.isclose(contract.scale, 1.0, rel_tol=0, abs_tol=1e-12):
            matrix[:3, :3] *= contract.scale
        if contract.direction == "target_to_source":
            try:
                matrix = np.linalg.inv(matrix)
            except np.linalg.LinAlgError as exc:
                raise ValidationError("TRANSFORM_NOT_INVERTIBLE", "target-to-source transform cannot be inverted") from exc
        if not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
            raise ValidationError("TRANSFORM_CANONICALIZATION_FAILED", "transform did not normalize to a finite homogeneous matrix")
        return matrix.tolist()

    @staticmethod
    def _transform_uncertainty_m(row: SpatialTransformRow) -> float | None:
        if row.covariance_json:
            covariance = np.asarray(row.covariance_json, dtype=np.float64)
            if covariance.ndim == 2 and covariance.shape[0] >= 3 and covariance.shape[1] >= 3:
                translation_variance = float(np.trace(covariance[:3, :3]))
                if math.isfinite(translation_variance) and translation_variance >= 0:
                    return math.sqrt(translation_variance)
        declaration = row.uncertainty_json or {}
        for key in (
            "translation_sigma_m",
            "uncertainty_m",
            "rmse_m",
            "sigma_m",
            "residual_m",
        ):
            raw = declaration.get(key)
            if isinstance(raw, (int, float)) and math.isfinite(float(raw)) and float(raw) >= 0:
                return float(raw)
        return None

    @staticmethod
    def _assert_frame_parent_chain_acyclic(
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        new_frame_id: str,
        parent_frame_id: str,
    ) -> None:
        visited: set[str] = set()
        current_id: str | None = parent_frame_id
        while current_id is not None:
            if current_id == new_frame_id or current_id in visited:
                raise ValidationError(
                    "FRAME_CYCLE",
                    "coordinate-frame parent hierarchy contains a cycle",
                    {"frame_id": new_frame_id, "parent_frame_id": parent_frame_id},
                )
            visited.add(current_id)
            row = session.get(CoordinateFrameRow, current_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("coordinate_frame", current_id)
            current_id = row.parent_frame_id

    @staticmethod
    def _scoped_frame(session: Any, tenant_id: str, project_id: str, frame_id: str | None) -> CoordinateFrameRow:
        if not frame_id:
            raise NotFoundError("coordinate_frame", "missing")
        row = session.get(CoordinateFrameRow, frame_id)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id or row.deprecated_at is not None:
            raise NotFoundError("coordinate_frame", frame_id)
        return row

    @staticmethod
    def _scene_exists(session: Any, tenant_id: str, project_id: str, scene_id: str) -> None:
        commit = session.scalar(select(SceneCommitRow).where(
            SceneCommitRow.tenant_id == tenant_id,
            SceneCommitRow.project_id == project_id,
            SceneCommitRow.scene_id == scene_id,
        ))
        if not commit:
            raise NotFoundError("scene", scene_id)

    @staticmethod
    def _scoped_representation(session: Any, tenant_id: str, project_id: str, representation_id: str) -> RepresentationAssetRow:
        row = session.get(RepresentationAssetRow, representation_id)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("representation", representation_id)
        return row

    @staticmethod
    def _derivation_dict(row: DerivationEventRow) -> dict[str, Any]:
        return {
            "derivation_id": row.derivation_id,
            "activity_type": row.activity_type,
            "input_ids": row.input_ids_json,
            "input_hashes": row.input_hashes_json,
            "algorithm_id": row.algorithm_id,
            "algorithm_version": row.algorithm_version,
            "model_manifest_id": row.model_manifest_id,
            "parameters_hash": row.parameters_hash,
            "environment_hash": row.environment_hash,
            "code_commit": row.code_commit,
            "container_digest": row.container_digest,
            "output_ids": row.output_ids_json,
            "output_hashes": row.output_hashes_json,
            "software": row.software_json,
            "quality": row.quality_json,
            "validation": row.validation_json,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "actor_id": row.actor_id,
            "workload_identity": row.workload_identity,
            "request_hash": row.request_hash,
            "derivation_hash": row.derivation_hash,
        }

    @staticmethod
    def _commit_dict(row: SceneCommitRow) -> dict[str, Any]:
        return SpatialDataService._commit_dict_from_values(
            row.commit_id,
            row.tenant_id,
            row.project_id,
            row.scene_id,
            row.parent_ids_json,
            row.message,
            row.semantic_snapshot_json,
            row.snapshot_hash,
            row.policy_checks_json,
            root_manifest_hash=row.root_manifest_hash,
            field_visit_id=row.field_visit_id,
            workflow_event_id=row.workflow_event_id,
            change_evidence_ids=row.change_evidence_ids_json,
            signatures=row.signatures_json,
            review_state=row.review_state,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            recorded_at=row.recorded_at,
            branch=row.branch,
        )

    @staticmethod
    def _commit_dict_from_values(
        commit_id: str,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        parents: list[str],
        message: str,
        snapshot: dict[str, Any],
        snapshot_hash: str,
        policy_checks: dict[str, Any],
        *,
        root_manifest_hash: str | None = None,
        field_visit_id: str | None = None,
        workflow_event_id: str | None = None,
        change_evidence_ids: list[str] | None = None,
        signatures: list[dict[str, Any]] | None = None,
        review_state: str = "unreviewed",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        recorded_at: datetime | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        return {
            "commit_id": commit_id,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "branch": branch,
            "parent_ids": parents,
            "message": message,
            "semantic_snapshot": snapshot,
            "snapshot_hash": snapshot_hash,
            "root_manifest_hash": root_manifest_hash or snapshot_hash,
            "field_visit_id": field_visit_id,
            "workflow_event_id": workflow_event_id,
            "change_evidence_ids": change_evidence_ids or [],
            "policy_checks": policy_checks,
            "signatures": signatures or [],
            "review_state": review_state,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "recorded_at": recorded_at,
        }
