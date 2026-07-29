from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .contracts import (
    ChangeBenchmarkContract,
    ChangeCandidateContract,
    ChangeReviewContract,
    TemporalComparisonContract,
    ViewerSessionContract,
    ViewerSessionReplayContract,
)
from .database import (
    AssetRefRow,
    AuditEventRow,
    ChangeBenchmarkRow,
    ChangeCandidateRow,
    ChangeReviewRow,
    Database,
    EvidenceRecordRow,
    OutboxEventRow,
    ProjectRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
    SemanticChangeEventRow,
    TemporalComparisonRow,
    ViewerSessionReplayRow,
    ViewerSessionRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .hybrid import HybridControlService
from .models import Audience, SignedPrincipal
from .policy import PolicyService
from .scene import SceneService
from .temporal import db_now


_NAVIGATION_MODES = {"orbit", "walk", "fly", "teleport", "guided"}
_CHANGE_CLASSES = {"added", "removed", "moved", "modified", "occluded", "unobserved", "uncertain"}
_NUISANCE_CAUSES = {"lod", "lighting", "exposure", "dynamic_object", "missing_coverage"}
_REVIEW_OUTCOMES = {"accepted", "rejected", "disputed"}


@dataclass(frozen=True)
class ReplayedView:
    manifest: dict[str, Any]
    token: str


class SceneRuntimeService:
    """Policy-bound viewer state and governed temporal change review.

    Viewer sessions retain reproducible state but never reusable capabilities. Temporal
    comparisons preserve exact commit/evidence/algorithm identity. Detector candidates
    remain non-authoritative until an independent reviewer accepts them and an explicit
    scene commit applies the resulting semantic event.
    """

    _events = OutboxEventFactory()

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        policy: PolicyService,
        hybrid: HybridControlService,
        scene: SceneService,
    ) -> None:
        self.database = database
        self.audit = audit
        self.policy = policy
        self.hybrid = hybrid
        self.scene = scene

    # ------------------------------------------------------------------ viewer sessions
    def create_viewer_session(
        self,
        *,
        principal: SignedPrincipal,
        project_id: str,
        scene_id: str,
        purpose: str,
        audience: Audience | str,
        publication_class: str,
        scene_commit_ids: list[str],
        saved_hybrid_views: list[dict[str, Any]],
        device_profile: str,
        intended_uses: list[str],
        spatial_region_ids: list[str],
        camera: dict[str, Any],
        navigation_mode: str,
        layers: list[dict[str, Any]],
        clipping_planes: list[dict[str, Any]],
        section_box: dict[str, Any] | None,
        selected_entity_ids: list[str],
        timeline: dict[str, Any],
        filters: dict[str, Any],
        redaction: dict[str, Any],
        accessibility: dict[str, Any],
        comparison: dict[str, Any],
        idempotency_key: str,
        supersedes_session_id: str | None = None,
    ) -> dict[str, Any]:
        audience_value = audience.value if isinstance(audience, Audience) else str(audience)
        if navigation_mode not in _NAVIGATION_MODES:
            raise ValidationError("VIEWER_NAVIGATION_MODE_INVALID", "viewer navigation mode is unsupported")
        self.policy.require(
            principal,
            action="scene:read",
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=purpose,
            required_audience=Audience(audience_value),
        )
        body = {
            "tenant_id": principal.tenant_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "principal_id": principal.subject_id,
            "purpose": purpose,
            "audience": audience_value,
            "publication_class": publication_class,
            "scene_commit_ids": list(scene_commit_ids),
            "saved_hybrid_views": saved_hybrid_views,
            "device_profile": device_profile,
            "intended_uses": list(intended_uses),
            "spatial_region_ids": list(spatial_region_ids),
            "camera": camera,
            "navigation_mode": navigation_mode,
            "layers": layers,
            "clipping_planes": clipping_planes,
            "section_box": section_box,
            "selected_entity_ids": list(selected_entity_ids),
            "timeline": timeline,
            "filters": filters,
            "redaction": {**redaction, "server_enforced": True},
            "accessibility": accessibility,
            "comparison": comparison,
            "idempotency_key": idempotency_key,
            "supersedes_session_id": supersedes_session_id,
        }
        request_hash = canonical_sha256(body)
        policy_snapshot = self._policy_snapshot(
            principal=principal,
            project_id=project_id,
            purpose=purpose,
            audience=audience_value,
            spatial_region_ids=spatial_region_ids,
            redaction=body["redaction"],
        )
        policy_snapshot_hash = canonical_sha256(policy_snapshot)

        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != principal.tenant_id or project.status != "active":
                raise NotFoundError("project", project_id)
            prior = session.scalar(
                select(ViewerSessionRow).where(
                    ViewerSessionRow.tenant_id == principal.tenant_id,
                    ViewerSessionRow.project_id == project_id,
                    ViewerSessionRow.principal_id == principal.subject_id,
                    ViewerSessionRow.idempotency_key == idempotency_key,
                )
            )
            if prior:
                if prior.request_hash != request_hash:
                    raise ConflictError(
                        "VIEWER_SESSION_IDEMPOTENCY_CONFLICT",
                        "viewer session idempotency key is already bound to different state",
                    )
                return self._viewer_session_dict(prior)
            self._validate_scene_commits(
                session,
                tenant_id=principal.tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                commit_ids=scene_commit_ids,
            )
            self._validate_selected_entities(
                session,
                tenant_id=principal.tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                entity_ids=selected_entity_ids,
            )
            if supersedes_session_id:
                superseded = self._scoped_viewer_session(
                    session,
                    supersedes_session_id,
                    principal.tenant_id,
                    project_id,
                )
                if superseded.scene_id != scene_id or superseded.principal_id != principal.subject_id:
                    raise ValidationError(
                        "VIEWER_SESSION_SUPERSESSION_SCOPE_INVALID",
                        "viewer session can supersede only a prior session for the same scene and principal",
                    )
            session_id = new_uuid()
            created_at = db_now()
            persisted = {
                "schema": "sip.viewer-session/v1.1",
                "schema_version": "1.1.0",
                "session_id": session_id,
                **body,
                "policy_snapshot_hash": policy_snapshot_hash,
                "request_hash": request_hash,
                "session_hash": "0" * 64,
                "immutable": True,
                "created_by": principal.subject_id,
                "created_at": created_at.isoformat(),
            }
            persisted["session_hash"] = canonical_sha256({k: v for k, v in persisted.items() if k != "session_hash"})
            try:
                contract = ViewerSessionContract.model_validate(persisted)
            except PydanticValidationError as exc:
                raise ValidationError(
                    "VIEWER_SESSION_INVALID",
                    "viewer session violates the canonical contract",
                    {"errors": _safe_errors(exc)},
                ) from exc
            row = ViewerSessionRow(
                session_id=contract.session_id,
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                scene_id=contract.scene_id,
                principal_id=contract.principal_id,
                purpose=contract.purpose,
                audience=contract.audience.value,
                publication_class=contract.publication_class,
                scene_commit_ids_json=contract.scene_commit_ids,
                saved_hybrid_views_json=contract.saved_hybrid_views,
                device_profile=contract.device_profile,
                intended_uses_json=contract.intended_uses,
                spatial_region_ids_json=contract.spatial_region_ids,
                camera_json=contract.camera,
                navigation_mode=contract.navigation_mode,
                layers_json=[layer.model_dump(mode="json") for layer in contract.layers],
                clipping_planes_json=contract.clipping_planes,
                section_box_json=contract.section_box,
                selected_entity_ids_json=contract.selected_entity_ids,
                timeline_json=contract.timeline,
                filters_json=contract.filters,
                redaction_json=contract.redaction,
                accessibility_json=contract.accessibility,
                comparison_json=contract.comparison,
                policy_snapshot_hash=contract.policy_snapshot_hash,
                request_hash=contract.request_hash,
                session_hash=contract.session_hash,
                idempotency_key=contract.idempotency_key,
                immutable=True,
                supersedes_session_id=contract.supersedes_session_id,
                created_by=contract.created_by,
                created_at=contract.created_at,
            )
            session.add(row)
            session.add(
                self._events.create(
                    session,
                    event_type="viewer_session.created",
                    schema_version="1.0.0",
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    aggregate_type="viewer_session",
                    aggregate_id=session_id,
                    payload={
                        "session_id": session_id,
                        "scene_id": scene_id,
                        "commit_count": len(scene_commit_ids),
                        "session_hash": contract.session_hash,
                        "publication_class": contract.publication_class,
                    },
                    producer="scene-service",
                    actor_id=principal.subject_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=principal.tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action="viewer_session:create",
                resource_type="viewer_session",
                resource_id=session_id,
                outcome="allowed",
                details={
                    "session_hash": contract.session_hash,
                    "request_hash": request_hash,
                    "policy_snapshot_hash": policy_snapshot_hash,
                    "commit_count": len(scene_commit_ids),
                },
                session=session,
            )
            return contract.model_dump(mode="json", by_alias=True)

    def get_viewer_session(
        self,
        *,
        tenant_id: str,
        project_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped_viewer_session(session, session_id, tenant_id, project_id)
            return self._viewer_session_dict(row)

    def replay_viewer_session(
        self,
        *,
        principal: SignedPrincipal,
        project_id: str,
        session_id: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped_viewer_session(session, session_id, principal.tenant_id, project_id)
            retained = self._viewer_session_dict(row)
        self.policy.require(
            principal,
            action="scene:read",
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=retained["purpose"],
            required_audience=Audience(retained["audience"]),
        )
        if principal.subject_id != retained["principal_id"] and not set(principal.roles).intersection(
            {"tenant_admin", "project_admin", "reviewer"}
        ):
            raise AuthorizationError(
                "VIEWER_SESSION_PRINCIPAL_DENIED",
                "viewer session replay is limited to its principal or a trusted reviewer",
            )

        issued_for_storage: list[dict[str, Any]] = []
        transient_views: list[ReplayedView] = []
        degraded: list[str] = []
        descriptors = retained["saved_hybrid_views"]
        if not descriptors:
            descriptors = [
                {
                    "scene_revision_id": commit_id,
                    "purpose": retained["purpose"],
                    "audience": retained["audience"],
                    "device_profile": retained["device_profile"],
                    "time_context": retained["timeline"],
                    "intended_uses": retained["intended_uses"],
                    "spatial_region_ids": retained["spatial_region_ids"],
                }
                for commit_id in retained["scene_commit_ids"]
            ]
        for descriptor in descriptors:
            revision = str(descriptor.get("scene_revision_id") or "")
            if revision not in retained["scene_commit_ids"]:
                degraded.append(f"unretained_scene_revision:{revision or 'missing'}")
                continue
            try:
                issued = self.hybrid.create_view_manifest(
                    principal=principal,
                    project_id=project_id,
                    scene_id=retained["scene_id"],
                    scene_revision_id=revision,
                    purpose=str(descriptor.get("purpose") or retained["purpose"]),
                    audience=str(descriptor.get("audience") or retained["audience"]),
                    device_profile=str(descriptor.get("device_profile") or retained["device_profile"]),
                    time_context=dict(descriptor.get("time_context") or retained["timeline"]),
                    intended_uses=list(descriptor.get("intended_uses") or retained["intended_uses"]),
                    spatial_region_ids=list(descriptor.get("spatial_region_ids") or retained["spatial_region_ids"]),
                    ttl_seconds=ttl_seconds,
                )
            except (AuthorizationError, NotFoundError, ValidationError) as exc:
                degraded.append(f"{revision}:{exc.code}")
                continue
            manifest = dict(issued["manifest"])
            transient_views.append(ReplayedView(manifest=manifest, token=str(issued["token"])))
            issued_for_storage.append(
                {
                    "view_id": manifest["view_id"],
                    "scene_revision_id": manifest["scene_revision_id"],
                    "manifest_hash": manifest["manifest_hash"],
                    "policy_snapshot_hash": manifest["policy_snapshot_hash"],
                    "expires_at": manifest["expires_at"],
                }
            )

        current_policy_snapshot = self._policy_snapshot(
            principal=principal,
            project_id=project_id,
            purpose=retained["purpose"],
            audience=retained["audience"],
            spatial_region_ids=retained["spatial_region_ids"],
            redaction=retained["redaction"],
        )
        current_policy_hash = canonical_sha256(current_policy_snapshot)
        if current_policy_hash != retained["policy_snapshot_hash"]:
            degraded.append("policy_snapshot_changed")
        exact = not degraded and len(issued_for_storage) == len(descriptors)
        replay_id = new_uuid()
        created_at = db_now()
        replay_body = {
            "schema": "sip.viewer-session-replay/v1.1",
            "schema_version": "1.1.0",
            "replay_id": replay_id,
            "session_id": session_id,
            "tenant_id": principal.tenant_id,
            "project_id": project_id,
            "principal_id": principal.subject_id,
            "issued_views": issued_for_storage,
            "exact": exact,
            "degraded_reasons": sorted(set(degraded)),
            "policy_snapshot_hash": current_policy_hash,
            "replay_hash": "0" * 64,
            "created_at": created_at.isoformat(),
        }
        replay_body["replay_hash"] = canonical_sha256({k: v for k, v in replay_body.items() if k != "replay_hash"})
        contract = ViewerSessionReplayContract.model_validate(replay_body)
        with self.database.session() as session:
            session.add(
                ViewerSessionReplayRow(
                    replay_id=contract.replay_id,
                    session_id=contract.session_id,
                    tenant_id=contract.tenant_id,
                    project_id=contract.project_id,
                    principal_id=contract.principal_id,
                    issued_views_json=contract.issued_views,
                    exact=contract.exact,
                    degraded_reasons_json=contract.degraded_reasons,
                    policy_snapshot_hash=contract.policy_snapshot_hash,
                    replay_hash=contract.replay_hash,
                    created_at=contract.created_at,
                )
            )
            session.add(
                self._events.create(
                    session,
                    event_type="viewer_session.replayed",
                    schema_version="1.0.0",
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    aggregate_type="viewer_session_replay",
                    aggregate_id=replay_id,
                    payload={
                        "replay_id": replay_id,
                        "session_id": session_id,
                        "exact": exact,
                        "issued_view_count": len(issued_for_storage),
                        "degraded_reason_count": len(contract.degraded_reasons),
                        "replay_hash": contract.replay_hash,
                    },
                    producer="scene-service",
                    actor_id=principal.subject_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=principal.tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action="viewer_session:replay",
                resource_type="viewer_session_replay",
                resource_id=replay_id,
                outcome="allowed",
                details={
                    "session_id": session_id,
                    "exact": exact,
                    "issued_view_count": len(issued_for_storage),
                    "degraded_reasons": contract.degraded_reasons,
                },
                session=session,
            )
        return {
            "replay": contract.model_dump(mode="json", by_alias=True),
            "views": [asdict(item) for item in transient_views],
        }

    # -------------------------------------------------------------- temporal comparison
    def create_temporal_comparison(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        baseline_commit_id: str,
        candidate_commit_id: str,
        viewer_session_id: str | None,
        comparable_region: dict[str, Any],
        registration_quality: dict[str, Any],
        thresholds: dict[str, Any],
        evidence_ids: list[str],
        algorithm_id: str,
        algorithm_version: str,
        executable_hash: str,
        parameters_hash: str,
        observed_coverage: dict[str, Any],
        candidates: list[dict[str, Any]],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if baseline_commit_id == candidate_commit_id:
            raise ValidationError("CHANGE_COMMITS_IDENTICAL", "temporal comparison requires distinct scene commits")
        if registration_quality.get("accepted") is not True:
            raise ValidationError("CHANGE_REGISTRATION_REJECTED", "temporal comparison requires accepted registration")
        if float(registration_quality.get("overlap_fraction", 0.0)) <= 0:
            raise ValidationError("CHANGE_REGISTRATION_NO_OVERLAP", "temporal comparison requires positive overlap")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValidationError("CHANGE_EVIDENCE_DUPLICATE", "temporal comparison evidence identifiers must be unique")

        normalized_candidates = [self._normalize_candidate(candidate) for candidate in candidates]
        request = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "baseline_commit_id": baseline_commit_id,
            "candidate_commit_id": candidate_commit_id,
            "viewer_session_id": viewer_session_id,
            "comparable_region": comparable_region,
            "registration_quality": registration_quality,
            "thresholds": thresholds,
            "evidence_ids": sorted(evidence_ids),
            "algorithm_id": algorithm_id,
            "algorithm_version": algorithm_version,
            "executable_hash": executable_hash,
            "parameters_hash": parameters_hash,
            "observed_coverage": observed_coverage,
            "candidates": normalized_candidates,
            "idempotency_key": idempotency_key,
        }
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = session.scalar(
                select(TemporalComparisonRow).where(
                    TemporalComparisonRow.tenant_id == tenant_id,
                    TemporalComparisonRow.project_id == project_id,
                    TemporalComparisonRow.idempotency_key == idempotency_key,
                )
            )
            if prior:
                if prior.request_hash != request_hash:
                    raise ConflictError(
                        "CHANGE_COMPARISON_IDEMPOTENCY_CONFLICT",
                        "temporal comparison idempotency key is already bound to different input",
                    )
                return self._comparison_dict(session, prior)
            self._validate_scene_commits(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                commit_ids=[baseline_commit_id, candidate_commit_id],
            )
            if viewer_session_id:
                viewer = self._scoped_viewer_session(session, viewer_session_id, tenant_id, project_id)
                if viewer.scene_id != scene_id or not {baseline_commit_id, candidate_commit_id}.issubset(
                    set(viewer.scene_commit_ids_json)
                ):
                    raise ValidationError(
                        "CHANGE_VIEWER_SESSION_SCOPE_INVALID",
                        "comparison viewer session does not retain both compared commits",
                    )
            all_evidence = set(evidence_ids)
            for candidate in normalized_candidates:
                all_evidence.update(candidate["evidence_ids"])
            self._validate_evidence(session, tenant_id, project_id, sorted(all_evidence))
            comparison_id = new_uuid()
            created_at = db_now()
            candidate_contracts: list[ChangeCandidateContract] = []
            for item in normalized_candidates:
                candidate_id = new_uuid()
                candidate_payload = {
                    "candidate_id": candidate_id,
                    **item,
                    "candidate_hash": "0" * 64,
                }
                candidate_payload["candidate_hash"] = canonical_sha256(
                    {k: v for k, v in candidate_payload.items() if k != "candidate_hash"}
                )
                candidate_contracts.append(ChangeCandidateContract.model_validate(candidate_payload))
            comparison_payload = {
                "schema": "sip.temporal-comparison/v1.1",
                "schema_version": "1.1.0",
                "comparison_id": comparison_id,
                **request,
                "candidates": [item.model_dump(mode="json") for item in candidate_contracts],
                "state": "pending_review",
                "comparison_hash": "0" * 64,
                "request_hash": request_hash,
                "created_by": actor_id,
                "created_at": created_at.isoformat(),
            }
            comparison_payload["comparison_hash"] = canonical_sha256(
                {k: v for k, v in comparison_payload.items() if k != "comparison_hash"}
            )
            try:
                contract = TemporalComparisonContract.model_validate(comparison_payload)
            except PydanticValidationError as exc:
                raise ValidationError(
                    "CHANGE_COMPARISON_INVALID",
                    "temporal comparison violates the canonical contract",
                    {"errors": _safe_errors(exc)},
                ) from exc
            row = TemporalComparisonRow(
                comparison_id=contract.comparison_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                baseline_commit_id=baseline_commit_id,
                candidate_commit_id=candidate_commit_id,
                viewer_session_id=viewer_session_id,
                comparable_region_json=contract.comparable_region,
                registration_quality_json=contract.registration_quality,
                thresholds_json=contract.thresholds,
                evidence_ids_json=contract.evidence_ids,
                algorithm_id=contract.algorithm_id,
                algorithm_version=contract.algorithm_version,
                executable_hash=contract.executable_hash,
                parameters_hash=contract.parameters_hash,
                observed_coverage_json=contract.observed_coverage,
                state=contract.state,
                comparison_hash=contract.comparison_hash,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                created_by=actor_id,
                created_at=created_at,
            )
            session.add(row)
            # Flush the parent before candidates. The service deliberately avoids ORM
            # relationships so tenant/project scope remains explicit; SQLite therefore
            # needs the foreign-key parent materialized before an autoflush from the
            # event factory can occur.
            session.flush()
            for item in candidate_contracts:
                session.add(
                    ChangeCandidateRow(
                        candidate_id=item.candidate_id,
                        comparison_id=comparison_id,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        scene_id=scene_id,
                        change_class=item.change_class,
                        entity_id=item.entity_id,
                        region_json=item.region,
                        metrics_json=item.metrics,
                        evidence_ids_json=item.evidence_ids,
                        coverage_status=item.coverage_status,
                        difference_causes_json=item.difference_causes,
                        state=item.state,
                        suppression_reason=item.suppression_reason,
                        candidate_hash=item.candidate_hash,
                        created_at=created_at,
                    )
                )
            session.flush()
            session.add(
                self._events.create(
                    session,
                    event_type="temporal_comparison.created",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="temporal_comparison",
                    aggregate_id=comparison_id,
                    payload={
                        "comparison_id": comparison_id,
                        "scene_id": scene_id,
                        "baseline_commit_id": baseline_commit_id,
                        "candidate_commit_id": candidate_commit_id,
                        "candidate_count": len(candidate_contracts),
                        "suppressed_count": sum(item.state == "suppressed" for item in candidate_contracts),
                        "comparison_hash": contract.comparison_hash,
                    },
                    producer="scene-service",
                    actor_id=actor_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="temporal_comparison:create",
                resource_type="temporal_comparison",
                resource_id=comparison_id,
                outcome="allowed",
                details={
                    "comparison_hash": contract.comparison_hash,
                    "request_hash": request_hash,
                    "candidate_count": len(candidate_contracts),
                    "suppressed_count": sum(item.state == "suppressed" for item in candidate_contracts),
                },
                session=session,
            )
            return contract.model_dump(mode="json", by_alias=True)

    def get_temporal_comparison(
        self,
        *,
        tenant_id: str,
        project_id: str,
        comparison_id: str,
        include_suppression_details: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped_comparison(session, comparison_id, tenant_id, project_id)
            result = self._comparison_dict(session, row)
        if include_suppression_details:
            return result
        suppressed_count = sum(item["state"] == "suppressed" for item in result["candidates"])
        result["candidates"] = [item for item in result["candidates"] if item["state"] != "suppressed"]
        result["suppression_summary"] = {"suppressed_count": suppressed_count, "details_withheld": True}
        return result

    def review_change_candidate(
        self,
        *,
        tenant_id: str,
        project_id: str,
        comparison_id: str,
        candidate_id: str,
        reviewer_id: str,
        outcome: str,
        rationale: str,
        evidence_ids: list[str],
        policy_snapshot_hash: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if outcome not in _REVIEW_OUTCOMES:
            raise ValidationError("CHANGE_REVIEW_OUTCOME_INVALID", "change-review outcome is unsupported")
        if not rationale.strip():
            raise ValidationError("CHANGE_REVIEW_RATIONALE_REQUIRED", "change review requires a rationale")
        request = {
            "comparison_id": comparison_id,
            "candidate_id": candidate_id,
            "reviewer_id": reviewer_id,
            "outcome": outcome,
            "rationale": rationale,
            "evidence_ids": sorted(set(evidence_ids)),
            "policy_snapshot_hash": policy_snapshot_hash,
            "idempotency_key": idempotency_key,
        }
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = session.scalar(
                select(ChangeReviewRow).where(
                    ChangeReviewRow.tenant_id == tenant_id,
                    ChangeReviewRow.project_id == project_id,
                    ChangeReviewRow.reviewer_id == reviewer_id,
                    ChangeReviewRow.idempotency_key == idempotency_key,
                )
            )
            if prior:
                if prior.request_hash != request_hash:
                    raise ConflictError(
                        "CHANGE_REVIEW_IDEMPOTENCY_CONFLICT",
                        "change-review idempotency key is bound to different content",
                    )
                return self._change_review_dict(prior)
            comparison = self._scoped_comparison(session, comparison_id, tenant_id, project_id)
            candidate = session.get(ChangeCandidateRow, candidate_id)
            if (
                not candidate
                or candidate.comparison_id != comparison_id
                or candidate.tenant_id != tenant_id
                or candidate.project_id != project_id
            ):
                raise NotFoundError("change_candidate", candidate_id)
            if candidate.state == "suppressed":
                raise ConflictError(
                    "CHANGE_SUPPRESSED_CANDIDATE_REVIEW_DENIED",
                    "suppressed nuisance or unobserved candidates cannot be accepted",
                )
            if candidate.state in {"accepted", "rejected", "disputed"}:
                raise ConflictError("CHANGE_CANDIDATE_ALREADY_REVIEWED", "change candidate already has a terminal review")
            if reviewer_id == comparison.created_by or reviewer_id.startswith(("sip-worker:", "sip-provider:")):
                raise AuthorizationError(
                    "CHANGE_REVIEWER_NOT_INDEPENDENT",
                    "detector, provider, worker, or requester cannot independently approve a change",
                )
            self._validate_evidence(session, tenant_id, project_id, request["evidence_ids"])
            review_id = new_uuid()
            reviewed_at = db_now()
            review_payload = {
                "schema": "sip.change-review/v1.1",
                "schema_version": "1.1.0",
                "review_id": review_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                **request,
                "request_hash": request_hash,
                "review_hash": "0" * 64,
                "reviewed_at": reviewed_at.isoformat(),
            }
            review_payload["review_hash"] = canonical_sha256(
                {k: v for k, v in review_payload.items() if k != "review_hash"}
            )
            contract = ChangeReviewContract.model_validate(review_payload)
            row = ChangeReviewRow(
                review_id=review_id,
                comparison_id=comparison_id,
                candidate_id=candidate_id,
                tenant_id=tenant_id,
                project_id=project_id,
                reviewer_id=reviewer_id,
                outcome=outcome,
                rationale=rationale,
                evidence_ids_json=contract.evidence_ids,
                policy_snapshot_hash=policy_snapshot_hash,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                review_hash=contract.review_hash,
                reviewed_at=reviewed_at,
            )
            session.add(row)
            candidate.state = outcome
            semantic_event: SemanticChangeEventRow | None = None
            if outcome == "accepted":
                semantic_event = self._create_semantic_change_event(session, comparison, candidate, row)
                session.add(semantic_event)
            active_remaining = session.scalar(
                select(ChangeCandidateRow.candidate_id).where(
                    ChangeCandidateRow.comparison_id == comparison_id,
                    ChangeCandidateRow.state == "active",
                    ChangeCandidateRow.candidate_id != candidate_id,
                ).limit(1)
            )
            if active_remaining is None:
                comparison.state = "reviewed"
            session.add(
                self._events.create(
                    session,
                    event_type="change_candidate.reviewed",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="change_review",
                    aggregate_id=review_id,
                    payload={
                        "review_id": review_id,
                        "comparison_id": comparison_id,
                        "candidate_id": candidate_id,
                        "outcome": outcome,
                        "review_hash": contract.review_hash,
                        "semantic_event_created": semantic_event is not None,
                    },
                    producer="scene-service",
                    actor_id=reviewer_id,
                    workload_identity=None,
                )
            )
            if semantic_event is not None:
                session.add(
                    self._events.create(
                        session,
                        event_type="scene.change.accepted",
                        schema_version="1.0.0",
                        tenant_id=tenant_id,
                        project_id=project_id,
                        aggregate_type="semantic_change_event",
                        aggregate_id=semantic_event.semantic_event_id,
                        payload={
                            "semantic_event_id": semantic_event.semantic_event_id,
                            "comparison_id": comparison_id,
                            "candidate_id": candidate_id,
                            "event_type": semantic_event.event_type,
                            "event_hash": semantic_event.event_hash,
                        },
                        producer="scene-service",
                        actor_id=reviewer_id,
                        workload_identity=None,
                    )
                )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=reviewer_id,
                action="change_candidate:review",
                resource_type="change_review",
                resource_id=review_id,
                outcome="allowed",
                details={
                    "comparison_id": comparison_id,
                    "candidate_id": candidate_id,
                    "outcome": outcome,
                    "review_hash": contract.review_hash,
                    "semantic_event_id": semantic_event.semantic_event_id if semantic_event else None,
                },
                session=session,
            )
            result = contract.model_dump(mode="json", by_alias=True)
            result["semantic_event_id"] = semantic_event.semantic_event_id if semantic_event else None
            return result

    def apply_accepted_changes(
        self,
        *,
        tenant_id: str,
        project_id: str,
        comparison_id: str,
        branch: str,
        expected_head: str,
        message: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Atomically apply accepted changes with concurrent idempotent recovery.

        The project-scoped workflow-event uniqueness constraint is the final concurrency
        arbiter. If two transactions race after both pass their initial reads, the losing
        transaction is rolled back by :class:`Database` and this method resolves the
        winner from a fresh transaction. Only an equivalent, internally consistent
        result is returned as an idempotent replay; every mismatch fails with a stable
        SIP conflict code rather than leaking a database exception.
        """
        try:
            return self._apply_accepted_changes_once(
                tenant_id=tenant_id,
                project_id=project_id,
                comparison_id=comparison_id,
                branch=branch,
                expected_head=expected_head,
                message=message,
                actor_id=actor_id,
            )
        except IntegrityError as exc:
            if not self._is_workflow_event_uniqueness_conflict(exc):
                raise
            return self._resolve_concurrent_change_application(
                tenant_id=tenant_id,
                project_id=project_id,
                comparison_id=comparison_id,
                branch=branch,
                expected_head=expected_head,
            )

    def _apply_accepted_changes_once(
        self,
        *,
        tenant_id: str,
        project_id: str,
        comparison_id: str,
        branch: str,
        expected_head: str,
        message: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Execute one transactional semantic-change application attempt."""
        workflow_event_id = f"temporal-comparison:{comparison_id}"
        result: dict[str, Any]
        with self.database.session() as session:
            comparison = session.scalar(
                select(TemporalComparisonRow)
                .where(
                    TemporalComparisonRow.comparison_id == comparison_id,
                    TemporalComparisonRow.tenant_id == tenant_id,
                    TemporalComparisonRow.project_id == project_id,
                )
                .with_for_update()
            )
            if comparison is None:
                raise NotFoundError("temporal_comparison", comparison_id)

            events = list(
                session.scalars(
                    select(SemanticChangeEventRow)
                    .where(
                        SemanticChangeEventRow.comparison_id == comparison_id,
                        SemanticChangeEventRow.tenant_id == tenant_id,
                        SemanticChangeEventRow.project_id == project_id,
                    )
                    .with_for_update()
                )
            )
            pending = [event for event in events if event.applied_commit_id is None]
            already_applied = [event for event in events if event.applied_commit_id is not None]
            existing_commit = session.scalar(
                select(SceneCommitRow).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.workflow_event_id == workflow_event_id,
                )
            )

            if not pending:
                if already_applied:
                    commit_ids = {str(event.applied_commit_id) for event in already_applied}
                    if len(commit_ids) != 1:
                        raise ConflictError(
                            "CHANGE_APPLICATION_INTEGRITY_GAP",
                            "semantic change events are linked to multiple scene commits",
                        )
                    commit_id = next(iter(commit_ids))
                    if existing_commit is None or existing_commit.commit_id != commit_id:
                        raise ConflictError(
                            "CHANGE_APPLICATION_INTEGRITY_GAP",
                            "semantic event links do not match the idempotent workflow commit",
                        )
                    result = {
                        "comparison_id": comparison_id,
                        "commit_id": commit_id,
                        "semantic_event_ids": sorted(event.semantic_event_id for event in already_applied),
                        "idempotent_replay": True,
                    }
                    return result
                raise ConflictError(
                    "CHANGE_NO_ACCEPTED_EVENTS",
                    "comparison has no accepted semantic change events eligible for a scene commit",
                )

            if existing_commit is not None:
                # A commit with pending unlinked events can only originate from legacy
                # non-atomic behavior or manual corruption. Do not silently complete it.
                raise ConflictError(
                    "CHANGE_APPLICATION_INTEGRITY_GAP",
                    "workflow commit exists while semantic events remain unapplied",
                    {"commit_id": existing_commit.commit_id},
                )
            if already_applied:
                raise ConflictError(
                    "CHANGE_APPLICATION_INTEGRITY_GAP",
                    "comparison contains a partial semantic-event application",
                )
            if comparison.state not in {"reviewed", "partially_applied"}:
                raise ConflictError(
                    "CHANGE_COMPARISON_NOT_REVIEWED",
                    "all active change candidates must be reviewed before a scene commit",
                    {"state": comparison.state},
                )

            evidence_ids = sorted({item for event in pending for item in event.evidence_ids_json})
            semantic_event_ids = sorted(event.semantic_event_id for event in pending)
            commit = self.scene.commit_in_session(
                session=session,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=comparison.scene_id,
                branch=branch,
                expected_head=expected_head,
                message=message,
                actor_id=actor_id,
                workflow_event_id=workflow_event_id,
                change_evidence_ids=evidence_ids,
                policy_checks={
                    "temporal_comparison_reviewed": "passed",
                    "comparison_id": comparison_id,
                    "semantic_event_ids": semantic_event_ids,
                    "atomic_application": "passed",
                    "idempotency_key": workflow_event_id,
                },
                review_state="accepted_change_commit",
            )
            commit_id = str(commit["commit_id"])
            for event in pending:
                event.applied_commit_id = commit_id
            comparison.state = "applied"
            session.add(
                self._events.create(
                    session,
                    event_type="scene.change.applied",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="temporal_comparison",
                    aggregate_id=comparison_id,
                    payload={
                        "comparison_id": comparison_id,
                        "commit_id": commit_id,
                        "semantic_event_count": len(pending),
                        "branch": branch,
                        "atomic": True,
                        "idempotency_key": workflow_event_id,
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
                action="semantic_change:apply",
                resource_type="scene_commit",
                resource_id=commit_id,
                outcome="allowed",
                details={
                    "comparison_id": comparison_id,
                    "semantic_event_ids": semantic_event_ids,
                    "atomic": True,
                    "idempotency_key": workflow_event_id,
                },
                session=session,
            )
            session.flush()
            result = {
                "comparison_id": comparison_id,
                "commit_id": commit_id,
                "semantic_event_ids": semantic_event_ids,
                "idempotent_replay": False,
            }
        return result

    @staticmethod
    def _is_workflow_event_uniqueness_conflict(exc: IntegrityError) -> bool:
        """Recognize only the scene workflow-event uniqueness constraint.

        PostgreSQL exposes the constraint name through ``diag.constraint_name``. SQLite
        reports the constrained columns in its error text. No other integrity failure is
        converted into an idempotent replay.
        """
        original = exc.orig
        diagnostic = getattr(original, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == "uq_scene_commit_workflow_event":
            return True
        message = str(original).lower()
        return (
            "unique constraint failed" in message
            and "scene_commits.tenant_id" in message
            and "scene_commits.project_id" in message
            and "scene_commits.workflow_event_id" in message
        )

    def _resolve_concurrent_change_application(
        self,
        *,
        tenant_id: str,
        project_id: str,
        comparison_id: str,
        branch: str,
        expected_head: str,
    ) -> dict[str, Any]:
        """Resolve a losing concurrent caller from a fresh read transaction.

        The winner is accepted only when commit scope, branch ancestry, semantic-event
        links, comparison state, outbox publication, and immutable audit evidence all
        agree. This makes a successful replay distinguishable from corruption or an
        idempotency-key rebound.
        """
        workflow_event_id = f"temporal-comparison:{comparison_id}"

        def conflict(reason: str, **details: Any) -> ConflictError:
            return ConflictError(
                "CHANGE_APPLICATION_CONCURRENT_STATE_CONFLICT",
                "concurrent semantic-change application did not resolve to an equivalent governed result",
                {"reason": reason, **details},
            )

        with self.database.session() as session:
            comparison = session.scalar(
                select(TemporalComparisonRow).where(
                    TemporalComparisonRow.comparison_id == comparison_id,
                    TemporalComparisonRow.tenant_id == tenant_id,
                    TemporalComparisonRow.project_id == project_id,
                )
            )
            if comparison is None:
                raise conflict("comparison_missing")

            commits = list(
                session.scalars(
                    select(SceneCommitRow).where(
                        SceneCommitRow.tenant_id == tenant_id,
                        SceneCommitRow.project_id == project_id,
                        SceneCommitRow.workflow_event_id == workflow_event_id,
                    )
                )
            )
            if len(commits) != 1:
                raise conflict("workflow_commit_cardinality", observed=len(commits))
            commit = commits[0]
            if (
                commit.scene_id != comparison.scene_id
                or commit.branch != branch
                or commit.review_state != "accepted_change_commit"
                or list(commit.parent_ids_json) != [expected_head]
            ):
                raise conflict(
                    "workflow_commit_scope_mismatch",
                    commit_id=commit.commit_id,
                    observed_branch=commit.branch,
                )

            semantic_events = list(
                session.scalars(
                    select(SemanticChangeEventRow).where(
                        SemanticChangeEventRow.tenant_id == tenant_id,
                        SemanticChangeEventRow.project_id == project_id,
                        SemanticChangeEventRow.comparison_id == comparison_id,
                    )
                )
            )
            semantic_event_ids = sorted(event.semantic_event_id for event in semantic_events)
            if not semantic_events or any(
                event.scene_id != comparison.scene_id or event.applied_commit_id != commit.commit_id
                for event in semantic_events
            ):
                raise conflict("semantic_event_link_mismatch", commit_id=commit.commit_id)

            policy_checks = dict(commit.policy_checks_json or {})
            if (
                policy_checks.get("comparison_id") != comparison_id
                or sorted(policy_checks.get("semantic_event_ids") or []) != semantic_event_ids
                or policy_checks.get("idempotency_key") != workflow_event_id
                or policy_checks.get("atomic_application") != "passed"
            ):
                raise conflict("workflow_commit_policy_mismatch", commit_id=commit.commit_id)
            if comparison.state != "applied":
                raise conflict("comparison_not_applied", observed_state=comparison.state)

            branch_row = session.scalar(
                select(SceneBranchRow).where(
                    SceneBranchRow.tenant_id == tenant_id,
                    SceneBranchRow.project_id == project_id,
                    SceneBranchRow.scene_id == comparison.scene_id,
                    SceneBranchRow.name == branch,
                )
            )
            if branch_row is None or branch_row.head_commit_id != commit.commit_id:
                raise conflict("branch_head_mismatch", commit_id=commit.commit_id)

            applied_events = list(
                session.scalars(
                    select(OutboxEventRow).where(
                        OutboxEventRow.tenant_id == tenant_id,
                        OutboxEventRow.project_id == project_id,
                        OutboxEventRow.event_type == "scene.change.applied",
                        OutboxEventRow.aggregate_id == comparison_id,
                        OutboxEventRow.causation_id == workflow_event_id,
                    )
                )
            )
            committed_events = list(
                session.scalars(
                    select(OutboxEventRow).where(
                        OutboxEventRow.tenant_id == tenant_id,
                        OutboxEventRow.project_id == project_id,
                        OutboxEventRow.event_type == "scene.committed",
                        OutboxEventRow.aggregate_id == commit.commit_id,
                        OutboxEventRow.causation_id == workflow_event_id,
                    )
                )
            )
            if (
                len(applied_events) != 1
                or applied_events[0].payload_json.get("commit_id") != commit.commit_id
                or applied_events[0].payload_json.get("semantic_event_count") != len(semantic_events)
                or len(committed_events) != 1
            ):
                raise conflict("outbox_evidence_mismatch", commit_id=commit.commit_id)

            application_audits = list(
                session.scalars(
                    select(AuditEventRow).where(
                        AuditEventRow.tenant_id == tenant_id,
                        AuditEventRow.project_id == project_id,
                        AuditEventRow.action == "semantic_change:apply",
                        AuditEventRow.resource_type == "scene_commit",
                        AuditEventRow.resource_id == commit.commit_id,
                    )
                )
            )
            commit_audits = list(
                session.scalars(
                    select(AuditEventRow).where(
                        AuditEventRow.tenant_id == tenant_id,
                        AuditEventRow.project_id == project_id,
                        AuditEventRow.action == "scene:commit",
                        AuditEventRow.resource_type == "scene_commit",
                        AuditEventRow.resource_id == commit.commit_id,
                    )
                )
            )
            if (
                len(application_audits) != 1
                or application_audits[0].details_json.get("comparison_id") != comparison_id
                or sorted(application_audits[0].details_json.get("semantic_event_ids") or []) != semantic_event_ids
                or application_audits[0].details_json.get("idempotency_key") != workflow_event_id
                or len(commit_audits) != 1
                or commit_audits[0].details_json.get("branch") != branch
                or commit_audits[0].details_json.get("parent") != expected_head
            ):
                raise conflict("audit_evidence_mismatch", commit_id=commit.commit_id)

            return {
                "comparison_id": comparison_id,
                "commit_id": commit.commit_id,
                "semantic_event_ids": semantic_event_ids,
                "idempotent_replay": True,
            }

    def record_change_benchmark(
        self,
        *,
        tenant_id: str,
        project_id: str,
        algorithm_id: str,
        algorithm_version: str,
        executable_hash: str,
        benchmark_profile: str,
        fixture_root_hash: str,
        metrics_by_class: dict[str, dict[str, float]],
        environment: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        payload = {
            "schema": "sip.change-benchmark/v1.1",
            "schema_version": "1.1.0",
            "benchmark_id": new_uuid(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "algorithm_id": algorithm_id,
            "algorithm_version": algorithm_version,
            "executable_hash": executable_hash,
            "benchmark_profile": benchmark_profile,
            "fixture_root_hash": fixture_root_hash,
            "metrics_by_class": metrics_by_class,
            "environment": environment,
            "benchmark_hash": "0" * 64,
            "created_by": actor_id,
            "created_at": db_now().isoformat(),
        }
        payload["benchmark_hash"] = canonical_sha256({k: v for k, v in payload.items() if k != "benchmark_hash"})
        try:
            contract = ChangeBenchmarkContract.model_validate(payload)
        except PydanticValidationError as exc:
            raise ValidationError(
                "CHANGE_BENCHMARK_INVALID",
                "change-detection benchmark violates the canonical contract",
                {"errors": _safe_errors(exc)},
            ) from exc
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            prior = session.scalar(
                select(ChangeBenchmarkRow).where(ChangeBenchmarkRow.benchmark_hash == contract.benchmark_hash)
            )
            if prior:
                return self._benchmark_dict(prior)
            session.add(
                ChangeBenchmarkRow(
                    benchmark_id=contract.benchmark_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    algorithm_id=algorithm_id,
                    algorithm_version=algorithm_version,
                    executable_hash=executable_hash,
                    benchmark_profile=benchmark_profile,
                    fixture_root_hash=fixture_root_hash,
                    metrics_by_class_json=metrics_by_class,
                    environment_json=environment,
                    benchmark_hash=contract.benchmark_hash,
                    created_by=actor_id,
                    created_at=contract.created_at,
                )
            )
            session.add(
                self._events.create(
                    session,
                    event_type="change_benchmark.recorded",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="change_benchmark",
                    aggregate_id=contract.benchmark_id,
                    payload={
                        "benchmark_id": contract.benchmark_id,
                        "algorithm_id": algorithm_id,
                        "algorithm_version": algorithm_version,
                        "class_count": len(metrics_by_class),
                        "benchmark_hash": contract.benchmark_hash,
                    },
                    producer="scene-service",
                    actor_id=actor_id,
                    workload_identity=None,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="change_benchmark:record",
                resource_type="change_benchmark",
                resource_id=contract.benchmark_id,
                outcome="allowed",
                details={
                    "algorithm_id": algorithm_id,
                    "benchmark_profile": benchmark_profile,
                    "benchmark_hash": contract.benchmark_hash,
                },
                session=session,
            )
            return contract.model_dump(mode="json", by_alias=True)

    # ------------------------------------------------------------------------- helpers
    @staticmethod
    def _policy_snapshot(
        *,
        principal: SignedPrincipal,
        project_id: str,
        purpose: str,
        audience: str,
        spatial_region_ids: list[str],
        redaction: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "principal_id": principal.subject_id,
            "tenant_id": principal.tenant_id,
            "project_id": project_id,
            "roles": sorted(principal.roles),
            "purposes": sorted(principal.purposes),
            "audience": audience,
            "requested_purpose": purpose,
            "spatial_region_ids": sorted(spatial_region_ids),
            "redaction": redaction,
            "policy_version": "sip-policy-1.1.0",
        }

    @staticmethod
    def _validate_scene_commits(
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        commit_ids: Iterable[str],
    ) -> None:
        identifiers = list(commit_ids)
        if not identifiers or len(identifiers) > 2 or len(identifiers) != len(set(identifiers)):
            raise ValidationError(
                "VIEWER_SCENE_COMMITS_INVALID",
                "viewer/comparison state requires one or two unique scene commits",
            )
        for commit_id in identifiers:
            commit = session.get(SceneCommitRow, commit_id)
            if (
                not commit
                or commit.tenant_id != tenant_id
                or commit.project_id != project_id
                or commit.scene_id != scene_id
            ):
                raise NotFoundError("scene_commit", commit_id)

    @staticmethod
    def _validate_selected_entities(
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        entity_ids: Iterable[str],
    ) -> None:
        identifiers = list(entity_ids)
        if len(identifiers) != len(set(identifiers)):
            raise ValidationError("VIEWER_ENTITY_DUPLICATE", "selected entity identifiers must be unique")
        for entity_id in identifiers:
            row = session.get(SceneEntityRow, entity_id)
            if (
                not row
                or row.tenant_id != tenant_id
                or row.project_id != project_id
                or row.scene_id != scene_id
                or row.superseded_at is not None
            ):
                raise NotFoundError("scene_entity", entity_id)

    @staticmethod
    def _validate_evidence(session: Any, tenant_id: str, project_id: str, evidence_ids: Iterable[str]) -> None:
        for evidence_id in evidence_ids:
            row = session.get(EvidenceRecordRow, evidence_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("evidence", evidence_id)
            asset = session.get(AssetRefRow, row.asset_id)
            if (
                not asset
                or asset.tenant_id != tenant_id
                or asset.project_id != project_id
                or asset.tombstoned_at is not None
            ):
                raise NotFoundError("evidence", evidence_id)

    @staticmethod
    def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        change_class = str(candidate.get("change_class") or "uncertain")
        if change_class not in _CHANGE_CLASSES:
            raise ValidationError("CHANGE_CLASS_INVALID", "change candidate class is unsupported")
        coverage = str(candidate.get("coverage_status") or "unobserved")
        if coverage not in {"observed", "partially_observed", "unobserved"}:
            raise ValidationError("CHANGE_COVERAGE_INVALID", "change coverage status is unsupported")
        causes = sorted({str(value) for value in candidate.get("difference_causes", [])})
        unknown_causes = set(causes) - {
            "geometry",
            "lod",
            "lighting",
            "exposure",
            "dynamic_object",
            "missing_coverage",
            "registration",
            "unknown",
        }
        if unknown_causes:
            raise ValidationError(
                "CHANGE_DIFFERENCE_CAUSE_INVALID",
                "change candidate contains unsupported difference causes",
                {"causes": sorted(unknown_causes)},
            )
        state = "active"
        reason: str | None = None
        if change_class == "removed" and coverage != "observed":
            change_class = "unobserved"
            causes = sorted(set(causes) | {"missing_coverage"})
            state = "suppressed"
            reason = "unobserved_region_cannot_be_reported_as_removed"
        nuisance = sorted(set(causes) & _NUISANCE_CAUSES)
        if nuisance:
            state = "suppressed"
            reason = reason or "suppressed_nuisance_difference:" + ",".join(nuisance)
        evidence_ids = [str(value) for value in candidate.get("evidence_ids", [])]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValidationError("CHANGE_CANDIDATE_EVIDENCE_DUPLICATE", "candidate evidence identifiers must be unique")
        region = candidate.get("region")
        if not isinstance(region, dict) or not region:
            raise ValidationError("CHANGE_CANDIDATE_REGION_REQUIRED", "change candidate requires a bounded comparable region")
        return {
            "change_class": change_class,
            "entity_id": candidate.get("entity_id"),
            "region": region,
            "metrics": dict(candidate.get("metrics") or {}),
            "evidence_ids": evidence_ids,
            "coverage_status": coverage,
            "difference_causes": causes,
            "state": state,
            "suppression_reason": reason,
        }

    @staticmethod
    def _scoped_viewer_session(session: Any, session_id: str, tenant_id: str, project_id: str) -> ViewerSessionRow:
        row = session.get(ViewerSessionRow, session_id)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("viewer_session", session_id)
        return row

    @staticmethod
    def _scoped_comparison(session: Any, comparison_id: str, tenant_id: str, project_id: str) -> TemporalComparisonRow:
        row = session.get(TemporalComparisonRow, comparison_id)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("temporal_comparison", comparison_id)
        return row

    @staticmethod
    def _viewer_session_dict(row: ViewerSessionRow) -> dict[str, Any]:
        return ViewerSessionContract(
            session_id=row.session_id,
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            scene_id=row.scene_id,
            principal_id=row.principal_id,
            purpose=row.purpose,
            audience=Audience(row.audience),
            publication_class=row.publication_class,
            scene_commit_ids=row.scene_commit_ids_json,
            saved_hybrid_views=row.saved_hybrid_views_json,
            device_profile=row.device_profile,
            intended_uses=row.intended_uses_json,
            spatial_region_ids=row.spatial_region_ids_json,
            camera=row.camera_json,
            navigation_mode=row.navigation_mode,
            layers=row.layers_json,
            clipping_planes=row.clipping_planes_json,
            section_box=row.section_box_json,
            selected_entity_ids=row.selected_entity_ids_json,
            timeline=row.timeline_json,
            filters=row.filters_json,
            redaction=row.redaction_json,
            accessibility=row.accessibility_json,
            comparison=row.comparison_json,
            policy_snapshot_hash=row.policy_snapshot_hash,
            request_hash=row.request_hash,
            session_hash=row.session_hash,
            idempotency_key=row.idempotency_key,
            immutable=True,
            supersedes_session_id=row.supersedes_session_id,
            created_by=row.created_by,
            created_at=row.created_at,
        ).model_dump(mode="json", by_alias=True)

    @staticmethod
    def _change_candidate_dict(row: ChangeCandidateRow) -> dict[str, Any]:
        return ChangeCandidateContract(
            candidate_id=row.candidate_id,
            change_class=row.change_class,
            entity_id=row.entity_id,
            region=row.region_json,
            metrics=row.metrics_json,
            evidence_ids=row.evidence_ids_json,
            coverage_status=row.coverage_status,
            difference_causes=row.difference_causes_json,
            state=row.state,
            suppression_reason=row.suppression_reason,
            candidate_hash=row.candidate_hash,
        ).model_dump(mode="json")

    def _comparison_dict(self, session: Any, row: TemporalComparisonRow) -> dict[str, Any]:
        candidates = list(
            session.scalars(
                select(ChangeCandidateRow)
                .where(ChangeCandidateRow.comparison_id == row.comparison_id)
                .order_by(ChangeCandidateRow.created_at, ChangeCandidateRow.candidate_id)
            )
        )
        return TemporalComparisonContract(
            comparison_id=row.comparison_id,
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            scene_id=row.scene_id,
            baseline_commit_id=row.baseline_commit_id,
            candidate_commit_id=row.candidate_commit_id,
            viewer_session_id=row.viewer_session_id,
            comparable_region=row.comparable_region_json,
            registration_quality=row.registration_quality_json,
            thresholds=row.thresholds_json,
            evidence_ids=row.evidence_ids_json,
            algorithm_id=row.algorithm_id,
            algorithm_version=row.algorithm_version,
            executable_hash=row.executable_hash,
            parameters_hash=row.parameters_hash,
            observed_coverage=row.observed_coverage_json,
            candidates=[self._change_candidate_dict(item) for item in candidates],
            state=row.state,
            comparison_hash=row.comparison_hash,
            request_hash=row.request_hash,
            idempotency_key=row.idempotency_key,
            created_by=row.created_by,
            created_at=row.created_at,
        ).model_dump(mode="json", by_alias=True)

    @staticmethod
    def _change_review_dict(row: ChangeReviewRow) -> dict[str, Any]:
        return ChangeReviewContract(
            review_id=row.review_id,
            comparison_id=row.comparison_id,
            candidate_id=row.candidate_id,
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            reviewer_id=row.reviewer_id,
            outcome=row.outcome,
            rationale=row.rationale,
            evidence_ids=row.evidence_ids_json,
            policy_snapshot_hash=row.policy_snapshot_hash,
            request_hash=row.request_hash,
            idempotency_key=row.idempotency_key,
            review_hash=row.review_hash,
            reviewed_at=row.reviewed_at,
        ).model_dump(mode="json", by_alias=True)

    @staticmethod
    def _benchmark_dict(row: ChangeBenchmarkRow) -> dict[str, Any]:
        return ChangeBenchmarkContract(
            benchmark_id=row.benchmark_id,
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            algorithm_id=row.algorithm_id,
            algorithm_version=row.algorithm_version,
            executable_hash=row.executable_hash,
            benchmark_profile=row.benchmark_profile,
            fixture_root_hash=row.fixture_root_hash,
            metrics_by_class=row.metrics_by_class_json,
            environment=row.environment_json,
            benchmark_hash=row.benchmark_hash,
            created_by=row.created_by,
            created_at=row.created_at,
        ).model_dump(mode="json", by_alias=True)

    @staticmethod
    def _create_semantic_change_event(
        session: Any,
        comparison: TemporalComparisonRow,
        candidate: ChangeCandidateRow,
        review: ChangeReviewRow,
    ) -> SemanticChangeEventRow:
        semantic_event_id = new_uuid()
        event_type = f"scene.entity.{candidate.change_class}"
        payload = {
            "change_class": candidate.change_class,
            "entity_id": candidate.entity_id,
            "region": candidate.region_json,
            "metrics": candidate.metrics_json,
            "authority": "reviewed_change_event_not_applied",
        }
        body = {
            "semantic_event_id": semantic_event_id,
            "comparison_id": comparison.comparison_id,
            "candidate_id": candidate.candidate_id,
            "review_id": review.review_id,
            "tenant_id": comparison.tenant_id,
            "project_id": comparison.project_id,
            "scene_id": comparison.scene_id,
            "event_type": event_type,
            "entity_id": candidate.entity_id,
            "payload": payload,
            "evidence_ids": sorted(set(candidate.evidence_ids_json + review.evidence_ids_json)),
            "source_commit_ids": [comparison.baseline_commit_id, comparison.candidate_commit_id],
        }
        return SemanticChangeEventRow(
            semantic_event_id=semantic_event_id,
            comparison_id=comparison.comparison_id,
            candidate_id=candidate.candidate_id,
            review_id=review.review_id,
            tenant_id=comparison.tenant_id,
            project_id=comparison.project_id,
            scene_id=comparison.scene_id,
            event_type=event_type,
            entity_id=candidate.entity_id,
            payload_json=payload,
            evidence_ids_json=body["evidence_ids"],
            source_commit_ids_json=body["source_commit_ids"],
            applied_commit_id=None,
            event_hash=canonical_sha256(body),
            created_at=db_now(),
        )


def _safe_errors(exc: PydanticValidationError) -> list[dict[str, Any]]:
    return [
        {
            "type": item.get("type"),
            "loc": [str(part) for part in item.get("loc", ())],
            "msg": item.get("msg"),
        }
        for item in exc.errors(include_url=False)
    ]
