from __future__ import annotations

import json

import numpy as np
import pytest
from sqlalchemy import select

from sip.database import CoordinateFrameRow, OutboxEventRow, RepresentationAssetRow, RepresentationBindingRow
from sip.errors import AuthorizationError, ConflictError
from sip.model_governance import lingbot_checkpoint_denied_manifest, lingbot_source_manifest
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from sip.worker_runtime import REGISTRY, WorkerRuntime


@pytest.mark.integration
def test_worker_registry_covers_all_declared_worker_boundaries() -> None:
    expected = {
        "capture.normalize",
        "capture.polyform.normalize",
        "capture.validate",
        "change.detect",
        "collision.navigation",
        "depth.normalize",
        "depth.unproject",
        "document.media.index",
        "fusion.tsdf",
        "geometry.cleanup",
        "lingbot.reconstruct",
        "mesh.lod",
        "pose.anomaly.detect",
        "pose.optimize",
        "report.export",
        "representation.quality",
        "semantics.suggest",
        "splat.generate",
        "splat.normalize",
        "splat.surface",
    }
    assert set(REGISTRY.operation_types) == expected


@pytest.mark.integration
def test_pose_worker_is_durable_idempotent_and_retains_evidence(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    rng = np.random.default_rng(11)
    source = rng.normal(size=(40, 3))
    scale = 1.2
    rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    translation = np.array([2.0, -0.5, 1.0])
    target = (scale * (rotation @ source.T)).T + translation
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="pose.optimize",
        idempotency_key="pose-fixture-1",
        input_manifest={
            "source_points": source.tolist(),
            "target_points": target.tolist(),
            "with_scale": True,
            "threshold_m": 0.001,
            "iterations": 200,
            "seed": 7,
        },
        actor_id=actor,
    )
    runtime = WorkerRuntime(context, worker_id="pose-worker", allowed_operation_types={"pose.optimize"})
    result = runtime.run_operation(operation["operation_id"])
    assert result["state"] == "succeeded"
    assert result["output_hash"]
    assert result["output"]["inlier_count"] == len(source)
    assert result["output"]["rmse_m"] < 1e-10
    assert result["output"]["authority"] == "metric_observation_derived_unverified"
    # Idempotency returns the same durable resource rather than duplicating work.
    duplicate = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="pose.optimize",
        idempotency_key="pose-fixture-1",
        input_manifest=operation["input"],
        actor_id=actor,
    )
    assert duplicate["operation_id"] == operation["operation_id"]


@pytest.mark.integration
def test_reference_fusion_worker_propagates_uncertainty(bootstrapped) -> None:
    """REQ: HYBAPI-003, HYBAPI-004, HYBAPI-005, RECPROV-013."""
    context, tenant_id, project_id, actor = bootstrapped
    scene = context.scene.create_scene(tenant_id, project_id, name="Synthetic room", actor_id=actor)
    frame_id = "frame-fusion-fixture"
    with context.database.session() as session:
        session.add(
            CoordinateFrameRow(
                frame_id=frame_id,
                tenant_id=tenant_id,
                project_id=project_id,
                name="Synthetic metric frame",
                parent_frame_id=None,
                convention="right_handed_y_up_meters",
                units="meter",
                transform_json=None,
                uncertainty_m=0.001,
            )
        )
    source = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"synthetic metric observations",
        media_type="application/octet-stream",
        original_name="observations.bin",
        classification=Classification.INTERNAL,
        retention_class="evidence",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-fixture"]),
        actor_id=actor,
    )
    provider_id = "local.reference.fusion"
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.1.0",
            "source_url": "local://sip/fusion-tsdf",
            "source_revision": "deterministic-reference",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["synthetic_evaluation"],
            "allowed_regions": ["local"],
            "retention_days": 30,
        },
        actor_id=actor,
    )
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="fusion.tsdf",
        idempotency_key="fusion-fixture-1",
        input_manifest={
            "points": [[0.01, 0.01, 0.0], [0.02, 0.0, 0.01], [1.0, 1.0, 1.0]],
            "uncertainty_m": [0.01, 0.02, 0.10],
            "voxel_size_m": 0.1,
            "candidate": {
                "scene_id": scene["scene_id"],
                "source_scene_revision_id": scene["commit_id"],
                "coordinate_frame_id": frame_id,
                "provider_id": provider_id,
                "purpose": "synthetic_evaluation",
                "region": "local",
                "classification": "internal",
                "source_asset_ids": [source.asset_id],
                "intended_uses": ["metric_review"],
                "prohibited_uses": ["fabrication", "survey_grade"],
                "quality": {"fixture": True},
                "support_map": {"frame_id": frame_id},
                "limitations": ["synthetic fixture"],
            },
        },
        actor_id=actor,
    )
    result = WorkerRuntime(context, worker_id="fusion-worker", allowed_operation_types={"fusion.tsdf"}).run_operation(
        operation["operation_id"]
    )
    assert result["state"] == "succeeded"
    assert result["output"]["status"] == "candidate_complete"
    assert "voxel_centers" not in result["output"]  # REST/job state carries bounded references, not geometry.
    candidate = result["output"]["candidate_package"]
    payload = json.loads(context.assets.read(tenant_id, project_id, candidate["asset_id"], actor_id=actor))
    assert len(payload["voxel_centers"]) == 2
    assert all(value > 0 for value in payload["voxel_uncertainty_m"])
    assert payload["authority"] == "metric_unverified"
    assert candidate["state"] == "quarantined"
    assert candidate["publication_permission"] is False
    assert candidate["independent_validation_required"] is True
    assert candidate["source_manifest_hash"] == operation["input_manifest_hash"]
    assert candidate["asset_sha256"] == candidate["payload_hash"]
    assert candidate["worker_receipt_hash"]
    assert "automatic_publication" in candidate["prohibited_uses"]
    receipt = result["output"]["worker_receipt"]
    assert receipt["workload_identity"].startswith("sip-worker:")
    assert receipt["network_access_allowed"] is False
    assert receipt["shell_access_allowed"] is False
    assert receipt["publication_permission"] is False
    assert receipt["candidate_core_hash"]
    assert [item["sequence"] for item in receipt["checkpoints"]] == list(range(1, len(receipt["checkpoints"]) + 1))
    persisted = context.representations.candidate_for_operation(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_id=operation["operation_id"],
    )
    assert persisted is not None and persisted["state"] == "quarantined"
    assert persisted["provenance"]["worker_receipt_hash"] == receipt["receipt_sha256"]
    with context.database.session() as session:
        events = session.scalars(
            select(OutboxEventRow).where(
                OutboxEventRow.event_type == "representation.candidate_created",
                OutboxEventRow.aggregate_id == candidate["representation_id"],
            )
        ).all()
        bindings = session.scalars(
            select(RepresentationBindingRow).where(
                RepresentationBindingRow.representation_id == candidate["representation_id"]
            )
        ).all()
    assert len(events) == 1
    assert bindings == []

    with pytest.raises(ConflictError) as exc:
        context.publisher.publish(
            candidate["representation_id"],
            commit_id=scene["commit_id"],
            role="metric_review",
            publisher_id="sip-publisher:test",
        )
    assert exc.value.code == "REPRESENTATION_NOT_APPROVED"
    with pytest.raises(AuthorizationError) as exc:
        context.representations.review_quality(
            candidate["representation_id"],
            reviewer_id="sip-worker:fusion-tsdf",
            approved_uses=["metric_review"],
            metrics={"rmse_m": 0.01},
            passed=True,
        )
    assert exc.value.code == "WORKER_REVIEWER_NOT_INDEPENDENT"

    review = context.representations.review_quality(
        candidate["representation_id"],
        reviewer_id=actor,
        approved_uses=["metric_review"],
        metrics={"rmse_m": 0.01, "fixture": True},
        passed=True,
    )
    assert review["state"] == "approved"
    with pytest.raises(AuthorizationError) as exc:
        context.publisher.publish(
            candidate["representation_id"],
            commit_id=scene["commit_id"],
            role="metric_review",
            publisher_id="sip-worker:fusion-tsdf",
        )
    assert exc.value.code == "WORKER_PUBLICATION_DENIED"

    # Current provider governance is checked again at publication time. A policy
    # change cannot inherit the prior admission or review silently.
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.1.1",
            "source_url": "local://sip/fusion-tsdf",
            "source_revision": "changed-after-review",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["synthetic_evaluation"],
            "allowed_regions": ["local"],
            "retention_days": 30,
        },
        actor_id=actor,
    )
    with pytest.raises(AuthorizationError) as exc:
        context.publisher.publish(
            candidate["representation_id"],
            commit_id=scene["commit_id"],
            role="metric_review",
            publisher_id="sip-publisher:test",
        )
    assert exc.value.code == "PROVIDER_MANIFEST_CHANGED"
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.1.0",
            "source_url": "local://sip/fusion-tsdf",
            "source_revision": "deterministic-reference",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["synthetic_evaluation"],
            "allowed_regions": ["local"],
            "retention_days": 30,
        },
        actor_id=actor,
    )
    binding_id = context.publisher.publish(
        candidate["representation_id"],
        commit_id=scene["commit_id"],
        role="metric_review",
        publisher_id="sip-publisher:test",
    )
    assert binding_id
    with context.database.session() as session:
        binding = session.get(RepresentationBindingRow, binding_id)
        assert binding is not None
        assert binding.representation_id == candidate["representation_id"]


@pytest.mark.integration
def test_candidate_staging_is_idempotent_when_completion_fails_then_retries(bootstrapped, monkeypatch) -> None:
    """REQ: RECPROV-007, HYBAPI-003, HYBAPI-003, RECPROV-013; crash-safe exactly-once candidate staging."""
    context, tenant_id, project_id, actor = bootstrapped
    scene = context.scene.create_scene(tenant_id, project_id, name="Retry fixture", actor_id=actor)
    frame_id = "frame-fusion-retry"
    with context.database.session() as session:
        session.add(
            CoordinateFrameRow(
                frame_id=frame_id,
                tenant_id=tenant_id,
                project_id=project_id,
                name="Retry metric frame",
                parent_frame_id=None,
                convention="right_handed_y_up_meters",
                units="meter",
                transform_json=None,
                uncertainty_m=0.001,
            )
        )
    source = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"retry-safe synthetic metric observations",
        media_type="application/octet-stream",
        original_name="retry-observations.bin",
        classification=Classification.INTERNAL,
        retention_class="evidence",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["retry-synthetic-fixture"]),
        actor_id=actor,
    )
    provider_id = "local.reference.fusion.retry"
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.1.0",
            "source_url": "local://sip/fusion-tsdf",
            "source_revision": "deterministic-reference",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["synthetic_evaluation"],
            "allowed_regions": ["local"],
            "retention_days": 30,
        },
        actor_id=actor,
    )
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="fusion.tsdf",
        idempotency_key="fusion-retry-fixture-1",
        input_manifest={
            "points": [[0.01, 0.01, 0.0], [0.02, 0.0, 0.01], [1.0, 1.0, 1.0]],
            "uncertainty_m": [0.01, 0.02, 0.10],
            "voxel_size_m": 0.1,
            "candidate": {
                "scene_id": scene["scene_id"],
                "source_scene_revision_id": scene["commit_id"],
                "coordinate_frame_id": frame_id,
                "provider_id": provider_id,
                "purpose": "synthetic_evaluation",
                "region": "local",
                "classification": "internal",
                "source_asset_ids": [source.asset_id],
                "intended_uses": ["metric_review"],
                "prohibited_uses": ["fabrication", "survey_grade"],
                "quality": {"fixture": True},
                "support_map": {"frame_id": frame_id},
                "limitations": ["synthetic fixture"],
            },
        },
        actor_id=actor,
    )
    runtime = WorkerRuntime(context, worker_id="fusion-retry-worker", allowed_operation_types={"fusion.tsdf"})
    complete = context.operations.complete

    def interrupted_complete(*args, **kwargs):
        raise RuntimeError("simulated control-plane interruption after durable staging")

    monkeypatch.setattr(context.operations, "complete", interrupted_complete)
    with pytest.raises(RuntimeError, match="simulated control-plane interruption"):
        runtime.run_operation(operation["operation_id"])

    failed = context.operations.get(operation["operation_id"])
    assert failed["state"] == "failed"
    assert failed["error"]["retryable"] is True
    first_candidate = context.representations.candidate_for_operation(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_id=operation["operation_id"],
    )
    assert first_candidate is not None and first_candidate["state"] == "quarantined"
    first_receipts = list(first_candidate["provenance"]["worker_receipts"])

    monkeypatch.setattr(context.operations, "complete", complete)
    succeeded = runtime.run_operation(operation["operation_id"])
    assert succeeded["state"] == "succeeded"
    assert succeeded["attempt"] == 2
    retried_package = succeeded["output"]["candidate_package"]
    assert retried_package["representation_id"] == first_candidate["representation_id"]
    assert retried_package["asset_id"] == first_candidate["asset_id"]

    persisted = context.representations.candidate_for_operation(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_id=operation["operation_id"],
    )
    assert persisted is not None
    assert persisted["representation_id"] == first_candidate["representation_id"]
    assert persisted["asset_id"] == first_candidate["asset_id"]
    assert len(persisted["provenance"]["worker_receipts"]) == len(first_receipts) + 1
    with context.database.session() as session:
        candidates = session.scalars(
            select(RepresentationAssetRow).where(RepresentationAssetRow.operation_id == operation["operation_id"])
        ).all()
        events = session.scalars(
            select(OutboxEventRow).where(
                OutboxEventRow.event_type == "representation.candidate_created",
                OutboxEventRow.aggregate_id == first_candidate["representation_id"],
            )
        ).all()
        bindings = session.scalars(
            select(RepresentationBindingRow).where(
                RepresentationBindingRow.representation_id == first_candidate["representation_id"]
            )
        ).all()
    assert len(candidates) == 1
    assert len(events) == 1
    assert bindings == []

@pytest.mark.integration
def test_lingbot_checkpoint_is_hard_denied_and_operation_records_failure(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    context.providers.register(lingbot_source_manifest(), actor_id=actor)
    context.models.register(lingbot_checkpoint_denied_manifest())
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="lingbot.reconstruct",
        idempotency_key="lingbot-denied-1",
        input_manifest={
            "classification": "internal",
            "purpose": "research_shadow",
            "region": "local",
            "checkpoint_hash": "UNAVAILABLE",
            "commercial": False,
        },
        actor_id=actor,
    )
    runtime = WorkerRuntime(context, worker_id="lingbot-worker", allowed_operation_types={"lingbot.reconstruct"})
    with pytest.raises(AuthorizationError):
        runtime.run_operation(operation["operation_id"])
    failed = context.operations.get(operation["operation_id"])
    assert failed["state"] == "failed"
    assert failed["error"]["code"] == "MODEL_EXECUTION_DENIED"
    assert failed["error"]["retryable"] is False


@pytest.mark.security
def test_worker_cannot_execute_outside_its_capability(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="scope-test",
        input_manifest={"title": "Report"},
        actor_id=actor,
    )
    runtime = WorkerRuntime(context, worker_id="pose-only", allowed_operation_types={"pose.optimize"})
    with pytest.raises(AuthorizationError) as exc:
        runtime.run_operation(operation["operation_id"])
    assert exc.value.code == "WORKER_CAPABILITY_DENIED"
    assert context.operations.get(operation["operation_id"])["state"] == "pending"
