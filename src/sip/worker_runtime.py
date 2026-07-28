from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sqlalchemy import select

from .canonical import canonical_json, canonical_sha256, sha256_file
from .capture import CapturePackage, PolyformImporter
from .context import PlatformContext
from .database import CoordinateFrameRow, OperationRow, ProjectRow, SceneCommitRow
from .errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ValidationError
from .geometry import (
    change_detection,
    cleanup_mesh,
    detect_pose_anomalies,
    interaction_proxy,
    mesh_to_splats,
    ransac_similarity,
    splats_to_surface,
    unproject_depth,
    voxel_fuse,
)
from .observability import (
    PlatformObservability,
    configure_logging,
    operation_span,
    pseudonymize_identifier,
)
from .models import (
    AuthorityClass,
    Classification,
    OperationState,
    ProvenanceRef,
    RepresentationKind,
    SourceClass,
)
from .worker_manifest import WorkerManifest, WorkerResourceLimits, create_manifest_payload, load_worker_manifest
from .worker_protocol import (
    CandidatePackage,
    CandidateRequest,
    ProgressRecord,
    WorkerLease,
    WorkerLeaseAuthority,
    WorkerReceipt,
)
from .worker_sandbox import ExecutionSandbox, ResourceUsage, WorkerDeadlineExceeded

WorkerHandler = Callable[[dict[str, Any], "WorkerExecution"], dict[str, Any]]


@dataclass(frozen=True)
class CandidatePolicy:
    kind: RepresentationKind
    source_class: SourceClass
    authority_class: AuthorityClass
    lossy: bool
    disposable: bool
    output_role: str
    authority_ceiling: str


@dataclass(frozen=True)
class CandidateAdmission:
    request: CandidateRequest
    policy: CandidatePolicy
    classification: Classification
    provider: dict[str, Any]


_CLASSIFICATION_RANK: dict[Classification, int] = {
    Classification.PUBLIC: 0,
    Classification.INTERNAL: 1,
    Classification.CONFIDENTIAL: 2,
    Classification.RESTRICTED: 3,
    Classification.CRITICAL_INFRASTRUCTURE: 4,
    Classification.BIOMETRIC: 5,
    Classification.MINOR: 5,
}


_CANDIDATE_POLICIES: dict[str, CandidatePolicy] = {
    "fusion.tsdf": CandidatePolicy(
        RepresentationKind.METRIC,
        SourceClass.INFERRED,
        AuthorityClass.METRIC,
        False,
        False,
        "metric_surface",
        "metric_unverified",
    ),
    "geometry.cleanup": CandidatePolicy(
        RepresentationKind.METRIC,
        SourceClass.INFERRED,
        AuthorityClass.METRIC,
        False,
        False,
        "metric_mesh",
        "metric_unverified",
    ),
    "mesh.lod": CandidatePolicy(
        RepresentationKind.INTERACTION,
        SourceClass.GENERATED,
        AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        True,
        True,
        "interaction_proxy",
        "derived_non_authoritative",
    ),
    "collision.navigation": CandidatePolicy(
        RepresentationKind.INTERACTION,
        SourceClass.GENERATED,
        AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        True,
        True,
        "collision_navigation_proxy",
        "derived_non_authoritative",
    ),
    "splat.generate": CandidatePolicy(
        RepresentationKind.VISUAL,
        SourceClass.GENERATED,
        AuthorityClass.VISUAL,
        True,
        False,
        "visual_splats",
        "visual_non_metric",
    ),
    "splat.normalize": CandidatePolicy(
        RepresentationKind.VISUAL,
        SourceClass.GENERATED,
        AuthorityClass.VISUAL,
        True,
        False,
        "normalized_visual_splats",
        "visual_non_metric",
    ),
    "splat.surface": CandidatePolicy(
        RepresentationKind.INTERACTION,
        SourceClass.GENERATED,
        AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        True,
        True,
        "splat_surface_proxy",
        "derived_non_authoritative",
    ),
    "change.detect": CandidatePolicy(
        RepresentationKind.EVIDENCE,
        SourceClass.INFERRED,
        AuthorityClass.EVIDENCE,
        False,
        False,
        "temporal_change_evidence",
        "inferred_review_required",
    ),
}


class LocalWorkerControlGateway:
    """Narrow local equivalent of the typed WorkerControl RPC contract.

    Handlers receive this gateway only through ``WorkerExecution`` and never receive
    the platform context or publication service. Production deployments can replace
    this boundary with an authenticated RPC transport without changing handlers.
    """

    def __init__(self, context: PlatformContext, *, worker_id: str, lease_seconds: int) -> None:
        self._context = context
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def get(self, operation_id: str) -> dict[str, Any]:
        return self._context.operations.get(operation_id)

    def heartbeat(self, operation_id: str) -> dict[str, Any]:
        return self._context.operations.heartbeat(operation_id, worker_id=self.worker_id, lease_seconds=self.lease_seconds)

    def checkpoint(self, operation_id: str, *, progress: float, checkpoint: dict[str, Any]) -> dict[str, Any]:
        return self._context.operations.checkpoint(
            operation_id,
            worker_id=self.worker_id,
            progress=progress,
            checkpoint=checkpoint,
        )

    def authorize_lingbot(
        self,
        *,
        classification: Classification,
        purpose: str,
        region: str,
        checkpoint_hash: str,
        commercial: bool,
        customer_id: str,
    ) -> None:
        self._context.providers.authorize_execution(
            "lingbot-map-source-adapter",
            classification=classification,
            purpose=purpose,
            region=region,
            external=False,
        )
        self._context.models.authorize(
            "lingbot-map-checkpoint",
            checkpoint_hash=checkpoint_hash,
            purpose=purpose,
            commercial=commercial,
            classification=classification,
            deployment=self._context.settings.environment,
            region=region,
            customer_id=customer_id,
        )

    def stage_candidate(
        self,
        *,
        lease: WorkerLease,
        admission: "CandidateAdmission",
        handler_output: dict[str, Any],
        worker_manifest: WorkerManifest,
        code_commit: str,
        container_digest: str,
        environment_hash: str,
    ) -> CandidatePackage:
        """Persist an encrypted, idempotent, quarantined candidate.

        This gateway intentionally exposes no publication method. A separate
        publisher identity must validate and attach an approved representation.
        Exact identifiers are deterministic for one operation and output digest,
        making retries safe even if completion fails after staging.
        """

        request = admission.request
        policy = admission.policy
        tenant_id = lease.output_staging_scope.tenant_id
        project_id = lease.output_staging_scope.project_id
        payload_bytes = canonical_json(handler_output)
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        asset_id = _stable_identifier("asset", lease.operation_id, payload_hash)
        representation_id = _stable_identifier("representation", lease.operation_id, payload_hash)
        candidate_id = _stable_identifier("candidate", lease.operation_id, payload_hash)

        prior = self._context.representations.candidate_for_operation(
            tenant_id=tenant_id,
            project_id=project_id,
            operation_id=lease.operation_id,
        )
        if prior is not None:
            reference = self._context.assets.get(tenant_id, project_id, prior["asset_id"])
            expected = {
                "representation_id": representation_id,
                "asset_id": asset_id,
                "scene_id": request.scene_id,
                "provider_id": request.provider_id,
                "coordinate_frame_id": request.coordinate_frame_id,
                "kind": policy.kind.value,
                "source_class": policy.source_class.value,
                "authority_class": policy.authority_class.value,
            }
            actual = {key: prior.get(key) for key in expected}
            if reference.sha256 != payload_hash or actual != expected:
                raise ConflictError(
                    "WORKER_CANDIDATE_RETRY_MISMATCH",
                    "retry output or candidate policy does not match the operation's existing candidate",
                    {
                        "existing_hash": reference.sha256,
                        "retry_hash": payload_hash,
                        "expected": expected,
                        "actual": actual,
                    },
                )
            if prior["state"] != "quarantined":
                raise ConflictError(
                    "WORKER_CANDIDATE_STATE_CHANGED",
                    "operation retry cannot mutate a candidate that left quarantine",
                    {"state": prior["state"]},
                )
            return _candidate_package_from_persisted(
                lease=lease,
                request=request,
                policy=policy,
                candidate_id=candidate_id,
                representation_id=representation_id,
                asset_id=asset_id,
                asset_sha256=reference.sha256,
                payload_hash=payload_hash,
                provider=admission.provider,
                worker_manifest=worker_manifest,
                environment_hash=environment_hash,
                handler_output=handler_output,
            )

        provenance = ProvenanceRef(
            source_ids=request.source_asset_ids,
            run_id=lease.run_id,
            code_commit=code_commit if code_commit != "UNAVAILABLE" else None,
            container_digest=container_digest if container_digest != "UNAVAILABLE" else None,
            parameters_hash=lease.input_manifest_hash,
            environment_hash=environment_hash,
            output_hash=payload_hash,
            notes="Derived by an isolated worker; quarantined pending independent review.",
        )
        asset_reference = self._context.assets.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=payload_bytes,
            media_type=request.media_type,
            original_name=f"{lease.operation_type}-{lease.operation_id}.json",
            classification=admission.classification,
            retention_class=request.retention_class,
            source_class=policy.source_class,
            authority_class=policy.authority_class,
            provenance=provenance,
            actor_id=lease.workload_identity,
            asset_id=asset_id,
        )
        prohibited_uses = sorted(
            set(request.prohibited_uses) | {"automatic_publication", "verified_measurement"}
        )
        created_representation_id = self._context.representations.create_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=request.scene_id,
            asset_id=asset_reference.asset_id,
            operation_id=lease.operation_id,
            representation_id=representation_id,
            kind=policy.kind,
            provider_id=request.provider_id,
            coordinate_frame_id=request.coordinate_frame_id,
            source_class=policy.source_class,
            authority_class=policy.authority_class,
            lossy=policy.lossy,
            intended_uses=request.intended_uses,
            prohibited_uses=prohibited_uses,
            quality={
                **request.quality,
                "worker_handler_output_hash": payload_hash,
                "independent_review_required": True,
            },
            provenance={
                **provenance.model_dump(mode="json"),
                "worker_manifest_sha256": worker_manifest.manifest_sha256,
                "provider_manifest_hash": admission.provider["manifest_hash"],
            },
            support_map=request.support_map,
            actor_id=lease.workload_identity,
        )
        if created_representation_id != representation_id:
            raise ConflictError(
                "WORKER_CANDIDATE_IDENTIFIER_MISMATCH",
                "durable candidate identifier differs from the deterministic operation identifier",
            )
        return _candidate_package_from_persisted(
            lease=lease,
            request=request,
            policy=policy,
            candidate_id=candidate_id,
            representation_id=representation_id,
            asset_id=asset_reference.asset_id,
            asset_sha256=asset_reference.sha256,
            payload_hash=payload_hash,
            provider=admission.provider,
            worker_manifest=worker_manifest,
            environment_hash=environment_hash,
            handler_output=handler_output,
        )


@dataclass
class WorkerExecution:
    lease: WorkerLease
    worker_id: str
    control: LocalWorkerControlGateway
    sandbox: ExecutionSandbox
    checkpoints: list[ProgressRecord] = field(default_factory=list)
    _sequence: int = 0
    _progress_floor: float = 0.0

    def __post_init__(self) -> None:
        prior_sequence = self.lease.resume_checkpoint.get("sequence")
        if isinstance(prior_sequence, int) and prior_sequence > 0:
            self._sequence = prior_sequence
        self._progress_floor = self.lease.resume_progress

    @property
    def operation_id(self) -> str:
        return self.lease.operation_id

    @property
    def tenant_id(self) -> str:
        return self.lease.output_staging_scope.tenant_id

    @property
    def project_id(self) -> str:
        return self.lease.output_staging_scope.project_id

    def checkpoint(self, progress: float, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        if now >= self.lease.deadline_at:
            raise WorkerDeadlineExceeded()
        self._sequence += 1
        effective_progress = max(progress, self._progress_floor)
        self._progress_floor = effective_progress
        usage = self.sandbox.usage()
        stage = str(payload.get("stage", "unspecified"))
        record_payload = {
            "sequence": self._sequence,
            "stage": stage,
            "progress": effective_progress,
            "completed_units": payload.get("completed_units"),
            "total_units": payload.get("total_units"),
            "unit": payload.get("unit"),
            "warnings": list(payload.get("warnings", [])),
            "quality": dict(payload.get("quality", {})),
            "resource_use": {
                "elapsed_wall_seconds": usage.elapsed_wall_seconds,
                "elapsed_cpu_seconds": usage.elapsed_cpu_seconds,
                "maximum_rss_bytes": usage.maximum_rss_bytes,
            },
            "safe_to_resume": bool(payload.get("safe_to_resume", True)),
            "payload": payload,
        }
        record = ProgressRecord(**record_payload, checkpoint_hash=canonical_sha256(record_payload))
        checkpoint_document = record.model_dump(mode="json")
        with self.sandbox.trusted_control_io():
            current = self.control.get(self.operation_id)
            if not current["cancel_requested"]:
                self.control.heartbeat(self.operation_id)
            updated = self.control.checkpoint(
                self.operation_id,
                progress=effective_progress,
                checkpoint=checkpoint_document,
            )
        self.checkpoints.append(record)
        if current["cancel_requested"] or updated["state"] == OperationState.CANCELLED.value:
            raise ConflictError("OPERATION_CANCELLED", "worker observed a cancellation request at a declared safe point")

    def authorize_lingbot(
        self,
        *,
        classification: Classification,
        purpose: str,
        region: str,
        checkpoint_hash: str,
        commercial: bool,
    ) -> None:
        with self.sandbox.trusted_control_io():
            self.control.authorize_lingbot(
                classification=classification,
                purpose=purpose,
                region=region,
                checkpoint_hash=checkpoint_hash,
                commercial=commercial,
                customer_id=self.lease.output_staging_scope.tenant_id,
            )


class CapabilityRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, WorkerHandler] = {}

    def register(self, operation_type: str) -> Callable[[WorkerHandler], WorkerHandler]:
        def decorator(handler: WorkerHandler) -> WorkerHandler:
            if operation_type in self._handlers:
                raise RuntimeError(f"duplicate worker capability {operation_type}")
            self._handlers[operation_type] = handler
            return handler

        return decorator

    def execute(self, operation_type: str, manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
        if operation_type != execution.lease.operation_type or canonical_sha256(manifest) != execution.lease.input_manifest_hash:
            raise AuthenticationError("WORKER_LEASE_INPUT_MISMATCH", "worker input is not bound to the signed lease")
        handler = self._handlers.get(operation_type)
        if handler is None:
            raise ValidationError(
                "WORKER_CAPABILITY_UNKNOWN",
                "no worker implements the operation type",
                {"operation_type": operation_type},
            )
        result = handler(manifest, execution)
        if not isinstance(result, dict):
            raise ValidationError("WORKER_OUTPUT_INVALID", "worker output must be an object")
        return result

    @property
    def operation_types(self) -> list[str]:
        return sorted(self._handlers)


REGISTRY = CapabilityRegistry()


def _points(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not np.isfinite(array).all():
        raise ValidationError("POINTS_INVALID", f"{name} must be a finite Nx3 array")
    return array


@REGISTRY.register("capture.validate")
def validate_capture(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    path = Path(str(manifest["package_path"]))
    execution.checkpoint(0.2, {"stage": "archive_limits"})
    report = CapturePackage.validate(path)
    execution.checkpoint(0.9, {"stage": "root_hash_verified", "root_hash": report["root_hash"]})
    return {"capture": report, "source_path": str(path), "authoritative_source_preserved": True}


@REGISTRY.register("capture.polyform.normalize")
def normalize_polyform(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    source = Path(str(manifest["source_path"]))
    destination = Path(str(manifest["destination_path"]))
    execution.checkpoint(0.15, {"stage": "inspect_source"})
    report = PolyformImporter().convert(source, destination)
    execution.checkpoint(0.9, {"stage": "canonical_package_written", "destination": str(destination)})
    return report


@REGISTRY.register("capture.normalize")
def normalize_capture(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    package = Path(str(manifest["package_path"]))
    report = CapturePackage.validate(package)
    frames = report.get("frame_count", 0)
    execution.checkpoint(0.5, {"stage": "frame_correspondence", "frame_count": frames})
    return {
        "normalized_capture_root_hash": report["root_hash"],
        "frame_count": frames,
        "coordinate_convention": report.get("coordinate_convention", "right_handed_y_up_meters"),
        "metric_observation_lane": "preserved",
    }


@REGISTRY.register("pose.optimize")
def optimize_pose(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    source = _points(manifest["source_points"], "source_points")
    target = _points(manifest["target_points"], "target_points")
    if len(source) != len(target):
        raise ValidationError("CORRESPONDENCE_COUNT_MISMATCH", "source and target correspondence counts differ")
    execution.checkpoint(0.2, {"stage": "validity_checks", "correspondences": len(source)})
    estimate, inliers = ransac_similarity(
        source,
        target,
        estimate_scale=bool(manifest.get("with_scale", True)),
        threshold_m=float(manifest.get("threshold_m", 0.05)),
        iterations=int(manifest.get("iterations", 500)),
        seed=int(manifest.get("seed", 0)),
    )
    residual = np.linalg.norm(estimate.apply(source[inliers]) - target[inliers], axis=1)
    execution.checkpoint(0.85, {"stage": "robust_refinement", "inliers": int(inliers.sum())})
    return {
        "transform": estimate.matrix().tolist(),
        "scale": estimate.scale,
        "inlier_count": int(inliers.sum()),
        "correspondence_count": int(len(source)),
        "rmse_m": float(np.sqrt(np.mean(residual**2))),
        "authority": "metric_observation_derived_unverified",
    }


@REGISTRY.register("pose.anomaly.detect")
def pose_anomaly(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    poses = [np.asarray(item, dtype=np.float64) for item in manifest["poses"]]
    report = detect_pose_anomalies(poses)
    execution.checkpoint(0.9, {"stage": "pose_anomaly_complete", "reason_count": len(report["reasons"])})
    return {"analysis": report, "accepted": report["valid"]}


@REGISTRY.register("depth.normalize")
def normalize_depth(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    depth = np.asarray(manifest["depth_m"], dtype=np.float64)
    confidence = np.asarray(manifest.get("confidence", np.ones_like(depth)), dtype=np.float64)
    if depth.shape != confidence.shape or depth.ndim != 2:
        raise ValidationError("DEPTH_SHAPE_INVALID", "depth and confidence must be equal-sized 2D arrays")
    valid = np.isfinite(depth) & (depth > 0) & (confidence >= float(manifest.get("minimum_confidence", 0.5)))
    normalized = np.where(valid, depth, np.nan)
    execution.checkpoint(0.9, {"stage": "validity_mask", "valid_pixels": int(valid.sum())})
    return {
        "depth_m": normalized.tolist(),
        "valid_mask": valid.astype(np.uint8).tolist(),
        "valid_fraction": float(valid.mean()),
        "source_aware_uncertainty": {"invalid_low_confidence": int((~valid).sum())},
    }


@REGISTRY.register("depth.unproject")
def depth_unproject(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    depth = np.asarray(manifest["depth_m"], dtype=np.float64)
    intrinsics = np.asarray(manifest["intrinsics"], dtype=np.float64)
    confidence = np.asarray(manifest["confidence"], dtype=np.float64) if "confidence" in manifest else None
    pose = np.asarray(manifest.get("pose_camera_to_world", np.eye(4)), dtype=np.float64)
    points, weights = unproject_depth(
        depth,
        intrinsics,
        pose,
        confidence=confidence,
        minimum_confidence=int(manifest.get("minimum_confidence", 1)),
        max_depth_m=float(manifest.get("max_depth_m", 5.0)),
        stride=int(manifest.get("stride", 1)),
    )
    uncertainty = 1.0 / np.sqrt(np.maximum(weights, 1e-12))
    execution.checkpoint(0.9, {"stage": "unprojected", "points": len(points)})
    return {"points": points.tolist(), "weights": weights.tolist(), "uncertainty_m": uncertainty.tolist()}


@REGISTRY.register("fusion.tsdf")
def fuse_tsdf(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    points = _points(manifest["points"], "points")
    uncertainty = np.asarray(manifest["uncertainty_m"], dtype=np.float64)
    if uncertainty.shape != (len(points),) or np.any(uncertainty <= 0):
        raise ValidationError("FUSION_UNCERTAINTY_INVALID", "uncertainty must be positive and aligned with points")
    weights = 1.0 / np.square(uncertainty)
    execution.checkpoint(0.3, {"stage": "weighted_fusion", "point_count": len(points)})
    result = voxel_fuse([points], [weights], voxel_size_m=float(manifest.get("voxel_size_m", 0.05)))
    execution.checkpoint(0.9, {"stage": "metric_fusion_complete", "voxel_count": len(result["points"])})
    return {
        "voxel_centers": result["points"].tolist(),
        "voxel_uncertainty_m": result["uncertainty_m"].tolist(),
        "voxel_weights": result["weights"].tolist(),
        "voxel_size_m": float(manifest.get("voxel_size_m", 0.05)),
        "authority": "metric_unverified",
    }


@REGISTRY.register("geometry.cleanup")
def geometry_cleanup(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    vertices = _points(manifest["vertices"], "vertices")
    faces = np.asarray(manifest["faces"], dtype=np.int64)
    cleaned = cleanup_mesh(vertices, faces)
    execution.checkpoint(0.9, {"stage": "mesh_cleaned", "face_count": len(cleaned["faces"])})
    return {
        "vertices": cleaned["vertices"].tolist(),
        "faces": cleaned["faces"].tolist(),
        "repair": {"input_vertices": len(vertices), "output_vertices": len(cleaned["vertices"]), "input_faces": len(faces), "output_faces": len(cleaned["faces"])},
    }


@REGISTRY.register("mesh.lod")
def mesh_lod(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    vertices = _points(manifest["vertices"], "vertices")
    faces = np.asarray(manifest["faces"], dtype=np.int64)
    target_faces = int(manifest.get("target_faces", max(1, len(faces) // 2)))
    proxy = interaction_proxy(vertices, faces, target_faces=target_faces)
    execution.checkpoint(0.9, {"stage": "lod_complete", "faces": len(proxy["faces"])})
    return {
        "vertices": proxy["vertices"].tolist(),
        "faces": proxy["faces"].tolist(),
        "lod": {"source_faces": len(faces), "target_faces": target_faces, "actual_faces": len(proxy["faces"])},
        "authority": "derived_non_authoritative",
    }


@REGISTRY.register("collision.navigation")
def collision_navigation(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    result = mesh_lod(manifest, execution)
    vertices = np.asarray(result["vertices"], dtype=np.float64)
    faces = np.asarray(result["faces"], dtype=np.int64)
    normals = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    lengths = np.linalg.norm(normals, axis=1)
    normals = normals / np.maximum(lengths[:, None], 1e-12)
    walkable = np.where(normals[:, 1] >= np.cos(np.deg2rad(float(manifest.get("maximum_slope_degrees", 35)))))[0]
    result.update({"walkable_face_indices": walkable.tolist(), "collision_ready": True, "safe_navigation_review_required": True})
    return result


@REGISTRY.register("splat.generate")
def generate_splat(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    vertices = _points(manifest["vertices"], "vertices")
    faces = np.asarray(manifest["faces"], dtype=np.int64)
    splats = mesh_to_splats(vertices, faces, samples=int(manifest.get("count", 1024)), seed=int(manifest.get("seed", 0)))
    execution.checkpoint(0.9, {"stage": "mesh_to_splat", "splat_count": len(splats["positions"])})
    return {key: value.tolist() if hasattr(value, "tolist") else value for key, value in splats.items()} | {
        "lossy": True,
        "authority": "visual_non_metric",
    }


@REGISTRY.register("splat.normalize")
def normalize_splat(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    positions = _points(manifest["positions"], "positions")
    scales = np.asarray(manifest["scales"], dtype=np.float64)
    opacities = np.asarray(manifest["opacities"], dtype=np.float64)
    if scales.shape not in {(len(positions),), (len(positions), 3)} or opacities.shape != (len(positions),):
        raise ValidationError("SPLAT_SHAPE_INVALID", "splat scales/opacities do not match positions")
    opacities = np.clip(opacities, 0, 1)
    execution.checkpoint(0.9, {"stage": "splat_normalized", "splat_count": len(positions)})
    return {"positions": positions.tolist(), "scales": scales.tolist(), "opacities": opacities.tolist(), "coordinate_frame_id": manifest["coordinate_frame_id"]}


@REGISTRY.register("splat.surface")
def splat_surface(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    positions = _points(manifest["positions"], "positions")
    surface = splats_to_surface(positions)
    execution.checkpoint(0.9, {"stage": "splat_to_surface", "face_count": len(surface["faces"])})
    return {
        "vertices": surface["vertices"].tolist(),
        "faces": surface["faces"].tolist(),
        "lossy": True,
        "authority": "derived_non_authoritative",
        "quality_review_required": True,
    }


@REGISTRY.register("change.detect")
def detect_change(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    before = _points(manifest["before_points"], "before_points")
    after = _points(manifest["after_points"], "after_points")
    report = change_detection(before, after, threshold=float(manifest.get("threshold_m", 0.05)))
    execution.checkpoint(0.9, {"stage": "change_detected"})
    return {key: value.tolist() if hasattr(value, "tolist") else value for key, value in report.items()} | {"review_required": True}


@REGISTRY.register("representation.quality")
def representation_quality(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    intended_use = str(manifest["intended_use"])
    metrics = dict(manifest["metrics"])
    thresholds = dict(manifest["thresholds"])
    missing = sorted(set(thresholds) - set(metrics))
    if missing:
        raise ValidationError("QUALITY_METRICS_MISSING", "required quality metrics are missing", {"missing": missing})
    failures = {key: {"actual": metrics[key], "minimum": limit} for key, limit in thresholds.items() if float(metrics[key]) < float(limit)}
    execution.checkpoint(0.9, {"stage": "quality_evaluated", "passed": not failures})
    return {"intended_use": intended_use, "passed": not failures, "failures": failures, "metrics": metrics, "thresholds": thresholds}


@REGISTRY.register("semantics.suggest")
def semantics_suggest(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    labels = []
    for candidate in manifest.get("candidates", []):
        confidence = float(candidate.get("confidence", 0))
        if confidence >= float(manifest.get("minimum_confidence", 0.5)):
            labels.append({**candidate, "state": "proposed", "authority": "inferred", "human_review_required": True})
    execution.checkpoint(0.9, {"stage": "semantic_suggestions", "count": len(labels)})
    return {"suggestions": labels, "auto_published": False}


@REGISTRY.register("document.media.index")
def document_media(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    text = str(manifest.get("text", ""))
    normalized = " ".join(text.split())
    terms = sorted({token.lower().strip(".,:;!?()[]{}") for token in normalized.split() if len(token) > 1})
    execution.checkpoint(0.9, {"stage": "document_indexed", "term_count": len(terms)})
    return {"normalized_text": normalized, "terms": terms, "source_asset_id": manifest.get("source_asset_id"), "semantic_review_required": True}


@REGISTRY.register("report.export")
def report_export(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    report = {"title": manifest["title"], "sections": manifest.get("sections", []), "generated_from": manifest.get("source_ids", [])}
    execution.checkpoint(0.9, {"stage": "report_manifest"})
    return {"report": report, "report_hash": canonical_sha256(report), "format": manifest.get("format", "json")}


@REGISTRY.register("lingbot.reconstruct")
def lingbot_reconstruct(manifest: dict[str, Any], execution: WorkerExecution) -> dict[str, Any]:
    classification = Classification(str(manifest.get("classification", Classification.INTERNAL.value)))
    execution.authorize_lingbot(
        classification=classification,
        purpose=str(manifest.get("purpose", "research_shadow")),
        region=str(manifest.get("region", "local")),
        checkpoint_hash=str(manifest.get("checkpoint_hash", "UNAVAILABLE")),
        commercial=bool(manifest.get("commercial", False)),
    )
    raise AuthorizationError("LINGBOT_EXECUTION_UNREACHABLE", "governance unexpectedly allowed the denied-by-default LingBot checkpoint")

class WorkerRuntime:
    def __init__(
        self,
        context: PlatformContext,
        *,
        worker_id: str,
        allowed_operation_types: set[str] | None = None,
        manifest: WorkerManifest | None = None,
        observability: PlatformObservability | None = None,
    ) -> None:
        self.context = context
        self.worker_id = worker_id
        requested = allowed_operation_types or set(manifest.capabilities if manifest else REGISTRY.operation_types)
        unknown = requested - set(REGISTRY.operation_types)
        if unknown:
            raise ValidationError(
                "WORKER_CAPABILITY_UNKNOWN",
                "worker requested unknown capabilities",
                {"operation_types": sorted(unknown)},
            )
        self.manifest = manifest or _development_manifest(worker_id, requested)
        if requested != set(self.manifest.capabilities):
            raise ValidationError(
                "WORKER_MANIFEST_CAPABILITY_MISMATCH",
                "runtime capabilities must exactly match immutable worker manifest",
                {"runtime": sorted(requested), "manifest": self.manifest.capabilities},
            )
        self.allowed_operation_types = requested
        self.lease_authority = WorkerLeaseAuthority(context.settings.signing_key)
        self.observability = observability or PlatformObservability.create(self.manifest.name)
        self.logger = configure_logging(self.manifest.name)

    def _telemetry_dimensions(self, operation: dict[str, Any]) -> dict[str, str | None]:
        manifest = operation.get("input") if isinstance(operation.get("input"), dict) else {}
        artifacts = _model_artifacts(manifest)
        model = artifacts.get("model_manifest_id") or artifacts.get("provider_id")
        checkpoint = artifacts.get("model_checkpoint_hash") or artifacts.get("checkpoint_hash")
        capture_profile = _find_manifest_value(manifest, "capture_profile")
        return {
            "capability": operation["operation_type"],
            "model": str(model) if model is not None else "deterministic-reference",
            "checkpoint": str(checkpoint) if checkpoint is not None else None,
            "capture_profile": str(capture_profile) if capture_profile is not None else "unspecified",
        }

    def _log_fields(self, operation: dict[str, Any]) -> dict[str, Any]:
        return {
            "operation_id": operation["operation_id"],
            "tenant_context": pseudonymize_identifier(
                operation.get("tenant_id"), namespace="tenant", key=self.context.settings.signing_key
            ),
            "project_context": pseudonymize_identifier(
                operation.get("project_id"), namespace="project", key=self.context.settings.signing_key
            ),
        }

    def run_operation(self, operation_id: str) -> dict[str, Any]:
        operation = self.context.operations.get(operation_id)
        telemetry_started = time.perf_counter()
        telemetry_dimensions = self._telemetry_dimensions(operation)
        log_fields = self._log_fields(operation)
        if operation["operation_type"] not in self.allowed_operation_types:
            raise AuthorizationError("WORKER_CAPABILITY_DENIED", "worker is not scoped to this operation type")

        lease_seconds = min(3600, max(60, self.manifest.resource_limits.max_wall_seconds + 30))
        operation = self.context.operations.lease(operation_id, worker_id=self.worker_id, lease_seconds=lease_seconds)
        span_manager = operation_span(
            f"worker {operation['operation_type']}",
            traceparent=operation.get("traceparent"),
            kind="consumer",
            attributes={
                "sip.operation.type": operation["operation_type"],
                "sip.worker.name": self.manifest.name,
                "sip.operation.attempt": int(operation["attempt"]),
            },
        )
        span_manager.__enter__()
        self.observability.worker_started(operation["operation_type"])
        try:
            calculated_input_hash = canonical_sha256(operation["input"])
            if calculated_input_hash != operation["input_manifest_hash"]:
                raise AuthenticationError(
                    "WORKER_OPERATION_INPUT_TAMPERED",
                    "operation input does not match its persisted integrity hash",
                    {"persisted": operation["input_manifest_hash"], "calculated": calculated_input_hash},
                )

            sandbox = ExecutionSandbox(self.manifest.resource_limits)
            with operation_span(
                "worker.validate_input",
                traceparent=None,
                kind="internal",
                attributes={"sip.operation.type": operation["operation_type"]},
            ):
                input_byte_count = sandbox.validate_input(
                    operation["input"],
                    filesystem_read_scopes=self.manifest.filesystem_read_scopes,
                    filesystem_write_scopes=self.manifest.filesystem_write_scopes,
                )
            if input_byte_count != operation["input_byte_count"]:
                raise AuthenticationError(
                    "WORKER_OPERATION_INPUT_SIZE_MISMATCH",
                    "operation input byte count changed after creation",
                    {"persisted": operation["input_byte_count"], "calculated": input_byte_count},
                )

            raw_candidate = operation["input"].get("candidate")
            admission: CandidateAdmission | None = None
            if operation["operation_type"] in _CANDIDATE_POLICIES:
                if raw_candidate is None:
                    raise ValidationError(
                        "WORKER_CANDIDATE_REQUEST_REQUIRED",
                        "representation-producing operations require an admitted candidate request",
                        {"operation_type": operation["operation_type"]},
                    )
                request = _parse_candidate_request(raw_candidate)
                admission = _admit_candidate(self.context, operation, request)
            elif raw_candidate is not None:
                raise ValidationError(
                    "WORKER_CANDIDATE_REQUEST_UNSUPPORTED",
                    "operation type cannot stage a representation candidate",
                    {"operation_type": operation["operation_type"]},
                )

            signed_lease = self.lease_authority.issue(
                operation=operation,
                manifest=self.manifest,
                lease_seconds=lease_seconds,
                adapter_profile=self.manifest.name,
            )
            lease = self.lease_authority.verify(signed_lease, self.manifest)
            operation = self.context.operations.start(operation_id, worker_id=self.worker_id)
            if operation["state"] == OperationState.CANCELLED.value:
                return operation

            control = LocalWorkerControlGateway(self.context, worker_id=self.worker_id, lease_seconds=lease_seconds)
            execution = WorkerExecution(lease=lease, worker_id=self.worker_id, control=control, sandbox=sandbox)
            environment = _execution_environment(self.manifest)
            started_at = datetime.now(UTC)
            usage = ResourceUsage(0.0, 0.0, 0)
            with sandbox:
                execution.checkpoint(
                    0.01,
                    {
                        "stage": "startup",
                        "safe_to_resume": True,
                        "worker_manifest_sha256": self.manifest.manifest_sha256,
                        "input_manifest_hash": lease.input_manifest_hash,
                        "resumed_from_sequence": lease.resume_checkpoint.get("sequence"),
                    },
                )
                with operation_span(
                    "worker.compute",
                    traceparent=None,
                    kind="internal",
                    attributes={"sip.operation.type": operation["operation_type"]},
                ):
                    handler_output = REGISTRY.execute(operation["operation_type"], lease.input_manifest, execution)
                with operation_span("worker.validate_output", traceparent=None, kind="internal"):
                    sandbox.validate_output(handler_output)
                execution.checkpoint(
                    0.99,
                    {
                        "stage": "stage_output",
                        "safe_to_resume": True,
                        "handler_output_hash": canonical_sha256(handler_output),
                        "completed_units": 1,
                        "total_units": 1,
                        "unit": "candidate_output",
                    },
                )
                usage = sandbox.usage()

            candidate: CandidatePackage | None = None
            if admission is not None:
                with operation_span("worker.stage_candidate", traceparent=None, kind="producer"):
                    candidate = control.stage_candidate(
                        lease=lease,
                        admission=admission,
                        handler_output=handler_output,
                        worker_manifest=self.manifest,
                        code_commit=environment["code_commit"],
                        container_digest=environment["container_digest"],
                        environment_hash=environment["environment_hash"],
                    )

            completed_at = datetime.now(UTC)
            candidate_core_hash = candidate.candidate_core_hash if candidate else None
            resume_checkpoint_hash = canonical_sha256(lease.resume_checkpoint) if lease.resume_checkpoint else None
            receipt_payload: dict[str, Any] = {
                "lease_id": lease.lease_id,
                "run_id": lease.run_id,
                "operation_id": lease.operation_id,
                "operation_type": lease.operation_type,
                "adapter_profile": lease.adapter_profile,
                "attempt": lease.attempt,
                "worker_name": self.manifest.name,
                "workload_identity": lease.workload_identity,
                "lease_hash": lease.lease_hash,
                "worker_manifest_sha256": self.manifest.manifest_sha256,
                "runtime_sha256": self.manifest.runtime_sha256,
                "protocol_sha256": self.manifest.protocol_sha256,
                "sandbox_sha256": self.manifest.sandbox_sha256,
                "input_manifest_hash": lease.input_manifest_hash,
                "parameters_hash": lease.input_manifest_hash,
                "traceparent": lease.traceparent,
                "handler_output_hash": canonical_sha256(handler_output),
                "candidate_core_hash": candidate_core_hash,
                "resume_checkpoint_hash": resume_checkpoint_hash,
                "checkpoints": execution.checkpoints,
                "execution_environment": environment["profile"],
                "model_artifacts": _model_artifacts(lease.input_manifest),
                "started_at": started_at,
                "completed_at": completed_at,
                "elapsed_wall_seconds": usage.elapsed_wall_seconds,
                "elapsed_cpu_seconds": usage.elapsed_cpu_seconds,
                "maximum_rss_bytes": usage.maximum_rss_bytes,
                "input_byte_count": lease.input_byte_count,
                "handler_output_byte_count": len(canonical_json(handler_output)),
                "software_version": self.manifest.version,
                "code_commit": environment["code_commit"],
                "container_digest": environment["container_digest"],
                "python_version": environment["python_version"],
                "platform_profile": environment["platform_profile"],
                "environment_hash": environment["environment_hash"],
                "shell_access_allowed": False,
                "network_access_allowed": False,
                "publication_permission": False,
            }
            receipt = WorkerReceipt.seal(receipt_payload)

            if candidate is not None:
                candidate_data = candidate.model_dump(mode="json")
                candidate_data["worker_receipt_hash"] = receipt.receipt_sha256
                candidate = CandidatePackage.model_validate(candidate_data)
                self.context.representations.attach_worker_receipt(
                    tenant_id=lease.output_staging_scope.tenant_id,
                    project_id=lease.output_staging_scope.project_id,
                    operation_id=lease.operation_id,
                    worker_receipt_hash=receipt.receipt_sha256,
                    candidate_core_hash=candidate_core_hash or candidate.candidate_core_hash,
                    actor_id=lease.workload_identity,
                )
                output: dict[str, Any] = {
                    "status": "candidate_complete",
                    "handler_output_hash": receipt.handler_output_hash,
                    "handler_output_byte_count": receipt.handler_output_byte_count,
                    "result_summary": _bounded_result_summary(handler_output),
                    "candidate_package": candidate.model_dump(mode="json"),
                    "worker_receipt": receipt.model_dump(mode="json"),
                }
            else:
                output = {**handler_output, "worker_receipt": receipt.model_dump(mode="json")}

            sandbox.validate_output(output)
            claimed_output_hash = canonical_sha256(output)
            with operation_span("worker.complete_operation", traceparent=None, kind="producer"):
                completed = self.context.operations.complete(
                    operation_id,
                    worker_id=self.worker_id,
                    output=output,
                    claimed_output_hash=claimed_output_hash,
                )
            self.observability.observe_worker_run(
                **telemetry_dimensions,
                outcome="succeeded",
                duration_seconds=time.perf_counter() - telemetry_started,
                queue_wait_seconds=_queue_wait_seconds(operation),
                attempt=int(operation.get("attempt") or 0),
            )
            _observe_worker_quality(
                self.observability,
                dimensions=telemetry_dimensions,
                operation_type=operation["operation_type"],
                handler_output=handler_output,
            )
            self.logger.info(
                "worker operation complete",
                extra={
                    **log_fields,
                    "event": "worker.operation.complete",
                    "outcome": "succeeded",
                    "error_code": "none",
                    "fields": {
                        "operation_type": operation["operation_type"],
                        "attempt": operation["attempt"],
                        "elapsed_seconds": round(time.perf_counter() - telemetry_started, 6),
                        "candidate_staged": candidate is not None,
                    },
                },
            )
            return completed
        except ConflictError as exc:
            if exc.code == "OPERATION_CANCELLED":
                cancelled = self.context.operations.get(operation_id)
                self.observability.observe_worker_run(
                    **telemetry_dimensions,
                    outcome="cancelled",
                    duration_seconds=time.perf_counter() - telemetry_started,
                    queue_wait_seconds=_queue_wait_seconds(operation),
                    attempt=int(operation.get("attempt") or 0),
                )
                return cancelled
            self._record_failure(operation_id, exc, retryable=False)
            self.observability.observe_worker_run(
                **telemetry_dimensions,
                outcome="failed",
                duration_seconds=time.perf_counter() - telemetry_started,
                queue_wait_seconds=_queue_wait_seconds(operation),
                attempt=int(operation.get("attempt") or 0),
            )
            self.logger.warning(
                "worker operation failed",
                extra={
                    **log_fields,
                    "event": "worker.operation.failed",
                    "outcome": "failed",
                    "error_code": exc.code,
                    "fields": {"operation_type": operation["operation_type"], "retryable": False},
                },
            )
            raise
        except Exception as exc:
            code = exc.code if hasattr(exc, "code") else "WORKER_EXECUTION_FAILED"
            retryable_codes = {
                "WORKER_DEADLINE_EXCEEDED",
                "WORKER_CPU_LIMIT_EXCEEDED",
                "WORKER_MEMORY_LIMIT_EXCEEDED",
            }
            retryable = code in retryable_codes or not isinstance(
                exc,
                (ValidationError, AuthorizationError, AuthenticationError),
            )
            self._record_failure(operation_id, exc, retryable=retryable)
            self.observability.observe_worker_run(
                **telemetry_dimensions,
                outcome="failed",
                duration_seconds=time.perf_counter() - telemetry_started,
                queue_wait_seconds=_queue_wait_seconds(operation),
                attempt=int(operation.get("attempt") or 0),
            )
            self.logger.error(
                "worker operation failed",
                extra={
                    **log_fields,
                    "event": "worker.operation.failed",
                    "outcome": "failed",
                    "error_code": str(code),
                    "fields": {"operation_type": operation["operation_type"], "retryable": retryable},
                },
            )
            raise
        finally:
            self.observability.worker_finished(operation["operation_type"])
            span_manager.__exit__(*sys.exc_info())

    def _record_failure(self, operation_id: str, exc: Exception, *, retryable: bool) -> None:
        """Record failure only while this worker still owns a valid lease."""
        current = self.context.operations.get(operation_id)
        if current["lease_owner"] != self.worker_id or current["state"] not in {
            OperationState.LEASED.value,
            OperationState.RUNNING.value,
        }:
            return
        code = exc.code if hasattr(exc, "code") else "WORKER_EXECUTION_FAILED"
        message = exc.message if hasattr(exc, "message") else str(exc)
        try:
            self.context.operations.fail(
                operation_id,
                worker_id=self.worker_id,
                code=code,
                message=message,
                retryable=retryable,
            )
        except ConflictError:
            # A cancellation or lease-expiry race wins over failure reporting.
            return

    def run_once(self) -> dict[str, Any] | None:
        self.context.operations.reconcile_expired_leases()
        with self.context.database.session() as session:
            row = session.scalar(
                select(OperationRow)
                .where(
                    OperationRow.operation_type.in_(self.allowed_operation_types),
                    OperationRow.state.in_([OperationState.PENDING.value, OperationState.FAILED.value]),
                )
                .order_by(OperationRow.created_at, OperationRow.operation_id)
            )
            operation_id = row.operation_id if row else None
        if operation_id is None:
            return None
        try:
            return self.run_operation(operation_id)
        except ConflictError as exc:
            if exc.code == "OPERATION_ALREADY_LEASED":
                return None
            raise


def _admit_candidate(
    context: PlatformContext,
    operation: dict[str, Any],
    request: CandidateRequest,
) -> CandidateAdmission:
    """Perform policy and reference admission before provider computation starts."""
    policy = _CANDIDATE_POLICIES.get(operation["operation_type"])
    if policy is None:
        raise ValidationError(
            "WORKER_CANDIDATE_UNSUPPORTED",
            "operation type cannot produce a representation candidate",
            {"operation_type": operation["operation_type"]},
        )
    tenant_id = operation["tenant_id"]
    project_id = operation["project_id"]
    with context.database.session() as session:
        project = session.get(ProjectRow, project_id)
        if project is None or project.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)
        if request.source_scene_revision_id:
            revision = session.get(SceneCommitRow, request.source_scene_revision_id)
            if (
                revision is None
                or revision.tenant_id != tenant_id
                or revision.project_id != project_id
                or revision.scene_id != request.scene_id
            ):
                raise NotFoundError("scene_revision", request.source_scene_revision_id)
        else:
            scene_exists = session.scalar(
                select(SceneCommitRow.commit_id)
                .where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.scene_id == request.scene_id,
                )
                .limit(1)
            )
            if scene_exists is None:
                raise NotFoundError("scene", request.scene_id)
        frame = session.get(CoordinateFrameRow, request.coordinate_frame_id)
        if frame is None or frame.tenant_id != tenant_id or frame.project_id != project_id:
            raise NotFoundError("coordinate_frame", request.coordinate_frame_id)
        try:
            classifications = [Classification(project.classification), Classification(request.classification)]
        except ValueError as exc:
            raise ValidationError(
                "WORKER_CANDIDATE_CLASSIFICATION_INVALID",
                "candidate classification is not recognized",
                {"classification": request.classification},
            ) from exc

    for source_asset_id in request.source_asset_ids:
        source_reference = context.assets.get(tenant_id, project_id, source_asset_id)
        classifications.append(Classification(source_reference.classification))
    classification = _most_restrictive_classification(classifications)
    provider = context.providers.authorize_execution(
        request.provider_id,
        classification=classification,
        purpose=request.purpose,
        region=request.region,
        external=False,
    )
    return CandidateAdmission(
        request=request,
        policy=policy,
        classification=classification,
        provider=provider,
    )


def _most_restrictive_classification(values: list[Classification]) -> Classification:
    specialized = {item for item in values if item in {Classification.BIOMETRIC, Classification.MINOR}}
    if len(specialized) > 1:
        raise ValidationError(
            "WORKER_CANDIDATE_CLASSIFICATION_AMBIGUOUS",
            "mixed biometric and minor data requires an explicit composite policy decision",
        )
    return max(values, key=lambda item: _CLASSIFICATION_RANK[item])


def _candidate_package_from_persisted(
    *,
    lease: WorkerLease,
    request: CandidateRequest,
    policy: CandidatePolicy,
    candidate_id: str,
    representation_id: str,
    asset_id: str,
    asset_sha256: str,
    payload_hash: str,
    provider: dict[str, Any],
    worker_manifest: WorkerManifest,
    environment_hash: str,
    handler_output: dict[str, Any],
) -> CandidatePackage:
    prohibited_uses = sorted(
        set(request.prohibited_uses) | {"automatic_publication", "verified_measurement"}
    )
    limitations = set(request.limitations)
    limitations.add("independent validation required before publication")
    if policy.kind == RepresentationKind.VISUAL:
        limitations.add("visual output carries no metric authority")
    if policy.kind == RepresentationKind.INTERACTION:
        limitations.add("interaction proxy is disposable and non-authoritative")
    if policy.source_class == SourceClass.INFERRED:
        limitations.add("inferred output is not independently verified")
    return CandidatePackage(
        candidate_id=candidate_id,
        representation_id=representation_id,
        asset_id=asset_id,
        asset_sha256=asset_sha256,
        media_type=request.media_type,
        operation_id=lease.operation_id,
        operation_type=lease.operation_type,
        output_role=_OUTPUT_ROLES[lease.operation_type],
        representation_kind=policy.kind.value,
        coordinate_frame_id=request.coordinate_frame_id,
        source_scene_revision_id=request.source_scene_revision_id,
        source_asset_ids=request.source_asset_ids,
        payload_hash=payload_hash,
        source_manifest_hash=lease.input_manifest_hash,
        parameters_hash=lease.input_manifest_hash,
        environment_manifest_hash=environment_hash,
        provider_id=request.provider_id,
        provider_version=str(provider["provider_version"]),
        provider_executable_digest=worker_manifest.manifest_sha256,
        authority_ceiling=policy.authority_ceiling,
        disposable=policy.kind == RepresentationKind.INTERACTION,
        lossy=policy.lossy,
        intended_uses=request.intended_uses,
        prohibited_uses=prohibited_uses,
        provider_metrics=_provider_metrics(handler_output),
        limitations=sorted(limitations),
        human_review_required=True,
    )


def _parse_candidate_request(raw: Any) -> CandidateRequest:
    if not isinstance(raw, dict):
        raise ValidationError(
            "WORKER_CANDIDATE_REQUEST_INVALID",
            "candidate request must be an object",
        )
    try:
        return CandidateRequest.model_validate(raw)
    except Exception as exc:
        raise ValidationError(
            "WORKER_CANDIDATE_REQUEST_INVALID",
            "candidate request violates the immutable staging contract",
            {"validation_error": str(exc)},
        ) from exc


def _stable_identifier(kind: str, operation_id: str, payload_hash: str) -> str:
    namespace = uuid.UUID("faed6068-c89b-5d71-a05f-1197a65b5637")
    return str(uuid.uuid5(namespace, f"sip:{kind}:{operation_id}:{payload_hash}"))


_OUTPUT_ROLES: dict[str, str] = {
    "fusion.tsdf": "metric_fusion",
    "geometry.cleanup": "metric_mesh",
    "mesh.lod": "interaction_proxy",
    "collision.navigation": "collision_navigation_proxy",
    "splat.generate": "visual_splat",
    "splat.normalize": "normalized_visual_splat",
    "splat.surface": "splat_derived_interaction_proxy",
    "change.detect": "change_evidence",
}


def _provider_metrics(value: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, item in sorted(value.items()):
        if isinstance(item, bool) or item is None:
            metrics[key] = item
        elif isinstance(item, (int, float)):
            metrics[key] = item
        elif isinstance(item, list):
            metrics[f"{key}_count"] = len(item)
        elif isinstance(item, dict):
            scalar = {
                nested_key: nested_value
                for nested_key, nested_value in sorted(item.items())
                if isinstance(nested_value, (bool, int, float, str)) or nested_value is None
            }
            if scalar:
                metrics[key] = scalar
            metrics[f"{key}_field_count"] = len(item)
        elif isinstance(item, str) and len(item) <= 128 and not key.endswith("_path"):
            metrics[key] = item
    return metrics


def _bounded_result_summary(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded API-safe summary without embedding geometry or media."""
    if depth >= 3:
        return {"type": type(value).__name__, "sha256": canonical_sha256(value)}
    if isinstance(value, dict):
        return {
            str(key): _bounded_result_summary(item, depth=depth + 1)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "count": len(value),
            "sha256": canonical_sha256(value),
        }
    if isinstance(value, str):
        if len(value) <= 256:
            return value
        return {"type": "string", "length": len(value), "sha256": canonical_sha256(value)}
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return {"type": type(value).__name__, "sha256": canonical_sha256(str(value))}


def _execution_environment(manifest: WorkerManifest) -> dict[str, Any]:
    code_commit = os.getenv("SIP_RELEASE_COMMIT") or _read_git_commit() or "UNAVAILABLE"
    container_digest = os.getenv("SIP_CONTAINER_DIGEST", "UNAVAILABLE")
    python_version = platform.python_version()
    platform_profile = "-".join(
        filter(None, [platform.system().lower(), platform.release(), platform.machine().lower()])
    )
    profile = {
        "python_implementation": platform.python_implementation(),
        "python_version": python_version,
        "numpy_version": np.__version__,
        "platform_profile": platform_profile,
        "processor": platform.processor() or "unreported",
        "logical_cpu_count": os.cpu_count(),
        "worker_version": manifest.version,
        "worker_manifest_sha256": manifest.manifest_sha256,
        "runtime_sha256": manifest.runtime_sha256,
        "protocol_sha256": manifest.protocol_sha256,
        "sandbox_sha256": manifest.sandbox_sha256,
        "resource_limits": manifest.resource_limits.model_dump(mode="json"),
        "code_commit": code_commit,
        "source_tree_status": os.getenv("SIP_SOURCE_TREE_STATUS", "unreported"),
        "container_digest": container_digest,
    }
    return {
        "profile": profile,
        "environment_hash": canonical_sha256(profile),
        "python_version": python_version,
        "platform_profile": platform_profile,
        "code_commit": code_commit,
        "container_digest": container_digest,
    }


def _read_git_commit() -> str | None:
    root = Path(__file__).resolve().parents[2]
    head = root / ".git/HEAD"
    if not head.is_file():
        return None
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        target = root / ".git" / value[5:]
        if target.is_file():
            return target.read_text(encoding="utf-8").strip()
        packed = root / ".git/packed-refs"
        if packed.is_file():
            reference = value[5:]
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line and not line.startswith(("#", "^")):
                    digest, name = line.split(" ", 1)
                    if name == reference:
                        return digest
        return None
    return value if len(value) == 40 else None


def _model_artifacts(input_manifest: dict[str, Any]) -> dict[str, Any]:
    retained: dict[str, Any] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {
                    "provider_id",
                    "model_manifest_id",
                    "model_checkpoint_hash",
                    "checkpoint_hash",
                    "model_version",
                    "source_revision",
                } and child is not None:
                    retained[key] = child
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(input_manifest)
    return retained


def _find_manifest_value(value: Any, key: str) -> Any | None:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_manifest_value(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_manifest_value(child, key)
            if found is not None:
                return found
    return None


def _queue_wait_seconds(operation: dict[str, Any]) -> float | None:
    created_at = operation.get("created_at")
    if not isinstance(created_at, datetime):
        return None
    value = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - value).total_seconds())


def _numeric_metric(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _observe_worker_quality(
    observability: PlatformObservability,
    *,
    dimensions: dict[str, str | None],
    operation_type: str,
    handler_output: dict[str, Any],
) -> None:
    metrics = handler_output.get("metrics") if isinstance(handler_output.get("metrics"), dict) else {}
    quality = handler_output.get("quality") if isinstance(handler_output.get("quality"), dict) else {}
    combined = {**quality, **metrics}
    failures = handler_output.get("failures")
    failed_regions: int | None = None
    if isinstance(failures, dict):
        failed_regions = len(failures)
    elif isinstance(failures, list):
        failed_regions = len(failures)
    values = {
        "drift_ratio": _numeric_metric(combined, "drift_ratio", "drift"),
        "coverage_ratio": _numeric_metric(combined, "coverage_ratio", "coverage"),
        "residual_meters": _numeric_metric(combined, "residual_meters", "residual_m", "rmse_m"),
        "confidence_ratio": _numeric_metric(combined, "confidence_ratio", "confidence"),
        "failed_regions": failed_regions,
        "prior_delta_ratio": _numeric_metric(combined, "prior_delta_ratio", "quality_delta_ratio"),
    }
    if any(value is not None for value in values.values()):
        observability.observe_quality(**dimensions, **values)


def _development_manifest(worker_id: str, capabilities: set[str]) -> WorkerManifest:
    root = Path(__file__).resolve().parents[2]
    safe_name = re.sub(r"[^a-z0-9-]+", "-", worker_id.lower()).strip("-") or "development-worker"
    payload = create_manifest_payload(
        repository_root=root,
        name=safe_name,
        version="1.1.0-dev",
        entrypoint="src/sip/worker_runtime.py",
        capabilities=sorted(capabilities),
        governance="test_or_development_reference",
        resource_limits=WorkerResourceLimits(max_memory_bytes=4_294_967_296),
        requirement_ids=["PLTGRPC-001", "PLTGRPC-004", "PLTGRPC-006", "PLTSDK-003", "HYBAPI-003"],
    )
    return WorkerManifest.model_validate(payload)


def _verify_runtime_deployment_contract(
    manifest: WorkerManifest,
    *,
    production: bool,
    environment: dict[str, str] | None = None,
) -> None:
    """Fail closed when deployment metadata diverges from the immutable manifest.

    Container annotations are useful evidence, but only environment values are
    available to the process at startup. Production therefore requires the
    orchestrator to bind identity, manifest digest, publication denial, and
    compute-network denial explicitly. Development may omit those bindings, but
    any supplied value must still be correct.
    """

    values = environment if environment is not None else os.environ
    required = {
        "SIP_WORKLOAD_IDENTITY": manifest.workload_identity,
        "SIP_WORKER_MANIFEST_SHA256": manifest.manifest_sha256,
        "SIP_WORKER_PUBLICATION_PERMISSION": "false",
        "SIP_WORKER_COMPUTE_NETWORK_ACCESS": "denied",
    }
    errors: dict[str, dict[str, str | None]] = {}
    for key, expected in required.items():
        actual = values.get(key)
        if (production and actual is None) or (actual is not None and actual != expected):
            errors[key] = {"expected": expected, "actual": actual}
    if errors:
        raise AuthenticationError(
            "WORKER_DEPLOYMENT_CONTRACT_MISMATCH",
            "runtime deployment metadata does not match the immutable worker manifest",
            {"mismatches": errors, "worker": manifest.name},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="SIP capability-scoped durable worker")
    parser.add_argument("--operation-id")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--capability", action="append", dest="capabilities")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    context = PlatformContext.create()
    if context.settings.environment == "production" and args.manifest is None:
        raise ValidationError("WORKER_MANIFEST_REQUIRED", "production workers require an immutable worker manifest")
    if args.manifest is not None and args.capabilities:
        raise ValidationError("WORKER_CAPABILITY_OVERRIDE_DENIED", "capabilities cannot override an immutable worker manifest")
    manifest = load_worker_manifest(args.manifest) if args.manifest is not None else None
    capabilities = set(manifest.capabilities if manifest else args.capabilities or REGISTRY.operation_types)
    worker_id = os.getenv("SIP_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
    if manifest is not None:
        _verify_runtime_deployment_contract(
            manifest,
            production=context.settings.environment == "production",
        )
    runtime = WorkerRuntime(
        context,
        worker_id=worker_id,
        allowed_operation_types=capabilities,
        manifest=manifest,
    )
    metrics_port = int(os.getenv("SIP_WORKER_METRICS_PORT", "0"))
    if metrics_port:
        if not 1024 <= metrics_port <= 65535:
            raise ValidationError("WORKER_METRICS_PORT_INVALID", "worker metrics port must be between 1024 and 65535")
        from prometheus_client import start_http_server

        start_http_server(metrics_port, addr="0.0.0.0", registry=runtime.observability.registry)
    if args.operation_id:
        print(json.dumps(runtime.run_operation(args.operation_id), sort_keys=True, default=str))
        return
    while True:
        result = runtime.run_once()
        if result is not None:
            print(json.dumps(result, sort_keys=True, default=str), flush=True)
        if args.once:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
