from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier


import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from sip.database import (
    AuditEventRow,
    ChangeCandidateRow,
    ChangeReviewRow,
    OutboxEventRow,
    SceneBranchRow,
    SceneCommitRow,
    SemanticChangeEventRow,
    TemporalComparisonRow,
    ViewerSessionReplayRow,
)
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SignedPrincipal, SourceClass


def _principal(tenant_id: str, project_id: str, subject: str, roles: list[str]) -> SignedPrincipal:
    return SignedPrincipal(
        subject_id=subject,
        tenant_id=tenant_id,
        project_ids=[project_id],
        roles=roles,
        purposes=["construction", "operations"],
        audience=Audience.PROJECT,
        attributes={"spatial_region_ids": ["room-101"]},
    )


def _evidence(context, tenant_id: str, project_id: str, actor: str) -> str:
    payload = b"progress-05 deterministic temporal evidence"
    asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name="temporal-evidence.bin",
        classification=Classification.INTERNAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic:progress-05-temporal"]),
        actor_id=actor,
    )
    now = datetime.now(UTC)
    record = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset.asset_id,
        source_type="synthetic_temporal_fixture",
        collected_at=now,
        collected_by=actor,
        device_or_tool="deterministic-fixture",
        location_context={"region_id": "room-101"},
        relevant_region={"region_id": "room-101"},
        relevant_time_start=now,
        relevant_time_end=now,
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"allowed_purposes": ["construction", "operations"], "allowed_audiences": ["project"]},
        actor_id=actor,
    )
    return str(record["evidence_id"])


def _scene_state(context, tenant_id: str, project_id: str, actor: str) -> tuple[str, str, str, str]:
    scene = context.scene.create_scene(tenant_id, project_id, name="Progress 05 room", actor_id=actor)
    scene_id = scene["scene_id"]
    first = scene["commit_id"]
    entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        entity_type="room",
        name="Room 101",
        attributes={"number": "101"},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=0.95,
        provenance=ProvenanceRef(source_ids=["synthetic:room-101"]),
        policy={},
        stable_support={"region_id": "room-101"},
        actor_id=actor,
    )
    second = context.scene.commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        branch="main",
        expected_head=first,
        message="Record observed room",
        actor_id=actor,
        policy_checks={"synthetic_fixture": "passed"},
    )["commit_id"]
    return scene_id, first, second, entity_id


def _session(context, principal: SignedPrincipal, project_id: str, scene_id: str, commits: list[str], entity_id: str):
    return context.scene_runtime.create_viewer_session(
        principal=principal,
        project_id=project_id,
        scene_id=scene_id,
        purpose="construction",
        audience=Audience.PROJECT,
        publication_class="working",
        scene_commit_ids=commits,
        saved_hybrid_views=[],
        device_profile="web_desktop_reference",
        intended_uses=["review"],
        spatial_region_ids=["room-101"],
        camera={"position": [1.0, 1.6, 2.0], "target": [0.0, 1.0, 0.0]},
        navigation_mode="walk",
        layers=[
            {"role": "metric", "binding_ids": [], "visible": True, "interactive": False, "authority_label": "metric evidence"},
            {"role": "interaction", "binding_ids": [], "visible": True, "interactive": True, "authority_label": "non-authoritative proxy"},
        ],
        clipping_planes=[{"normal": [1, 0, 0], "constant": 0}],
        section_box={"min": [-5, 0, -5], "max": [5, 4, 5]},
        selected_entity_ids=[entity_id],
        timeline={"position": "candidate"},
        filters={"systems": ["fire_alarm"]},
        redaction={"restricted_regions": []},
        accessibility={"reduced_motion": True, "high_contrast": True, "captions": True},
        comparison={"primary_commit_id": commits[0], "secondary_commit_id": commits[1]} if len(commits) == 2 else {},
        idempotency_key="viewer-session-progress-05",
    )


@pytest.mark.integration
def test_policy_bound_viewer_session_is_immutable_replayable_and_never_persists_capabilities(bootstrapped) -> None:
    """REQ: PLTVIEW-001, PLTVIEW-003, PLTVIEW-006 saved viewer state is reproducible, policy-bound, and capability-free."""
    context, tenant_id, project_id, actor = bootstrapped
    scene_id, first, second, entity_id = _scene_state(context, tenant_id, project_id, actor)
    principal = _principal(tenant_id, project_id, actor, ["tenant_admin"])

    created = _session(context, principal, project_id, scene_id, [first, second], entity_id)
    repeated = _session(context, principal, project_id, scene_id, [first, second], entity_id)
    assert repeated["session_id"] == created["session_id"]
    assert created["immutable"] is True
    assert created["scene_commit_ids"] == [first, second]
    assert created["camera"] == {"position": [1.0, 1.6, 2.0], "target": [0.0, 1.0, 0.0]}
    assert created["navigation_mode"] == "walk"
    assert [layer["role"] for layer in created["layers"]] == ["metric", "interaction"]
    assert created["clipping_planes"] == [{"normal": [1.0, 0.0, 0.0], "constant": 0.0}]
    assert created["section_box"] == {"min": [-5.0, 0.0, -5.0], "max": [5.0, 4.0, 5.0]}
    assert created["selected_entity_ids"] == [entity_id]
    assert created["timeline"] == {"position": "candidate"}
    assert created["filters"] == {"systems": ["fire_alarm"]}
    assert created["redaction"]["server_enforced"] is True
    assert created["accessibility"] == {"reduced_motion": True, "high_contrast": True, "captions": True}
    assert "token" not in repr(created).lower()
    fetched = context.scene_runtime.get_viewer_session(
        tenant_id=tenant_id, project_id=project_id, session_id=created["session_id"]
    )
    for key in (
        "scene_commit_ids", "camera", "navigation_mode", "layers", "clipping_planes",
        "section_box", "selected_entity_ids", "timeline", "filters", "redaction", "accessibility",
    ):
        assert fetched[key] == created[key]
    assert fetched["session_hash"] == created["session_hash"]

    replay = context.scene_runtime.replay_viewer_session(
        principal=principal,
        project_id=project_id,
        session_id=created["session_id"],
        ttl_seconds=60,
    )
    # No published representations exist in this deterministic fixture, so replay is
    # honest and degraded rather than inventing a successful renderer binding.
    assert replay["replay"]["exact"] is False
    assert replay["replay"]["degraded_reasons"]
    assert replay["views"] == []
    with context.database.session() as db:
        stored = db.get(ViewerSessionReplayRow, replay["replay"]["replay_id"])
        assert stored is not None
        assert "token" not in repr(stored.issued_views_json).lower()

    with pytest.raises(ValidationError) as capability:
        context.scene_runtime.create_viewer_session(
            principal=principal,
            project_id=project_id,
            scene_id=scene_id,
            purpose="construction",
            audience=Audience.PROJECT,
            publication_class="working",
            scene_commit_ids=[second],
            saved_hybrid_views=[],
            device_profile="web_desktop_reference",
            intended_uses=["review"],
            spatial_region_ids=[],
            camera={"position": [0, 0, 0], "access_token": "must-not-persist"},
            navigation_mode="orbit",
            layers=[{"role": "metric", "binding_ids": [], "visible": True, "interactive": False, "authority_label": "metric"}],
            clipping_planes=[],
            section_box=None,
            selected_entity_ids=[],
            timeline={},
            filters={},
            redaction={},
            accessibility={"reduced_motion": False, "high_contrast": False, "captions": True},
            comparison={},
            idempotency_key="capability-denial",
        )
    assert capability.value.code == "VIEWER_SESSION_INVALID"


@pytest.mark.integration
def test_temporal_change_review_suppresses_unobserved_removal_and_requires_independent_review(bootstrapped) -> None:
    """REQ: RECCHANG-001, RECCHANG-002, RECCHANG-003, RECCHANG-004, RECCHANG-005, RECCHANG-006 comparisons preserve truth, review, controlled commits, and per-class metrics."""
    context, tenant_id, project_id, actor = bootstrapped
    scene_id, baseline, candidate_commit, entity_id = _scene_state(context, tenant_id, project_id, actor)
    evidence_id = _evidence(context, tenant_id, project_id, actor)
    requester = _principal(tenant_id, project_id, actor, ["tenant_admin"])
    viewer = _session(context, requester, project_id, scene_id, [baseline, candidate_commit], entity_id)

    comparison = context.scene_runtime.create_temporal_comparison(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        baseline_commit_id=baseline,
        candidate_commit_id=candidate_commit,
        viewer_session_id=viewer["session_id"],
        comparable_region={"region_id": "room-101", "bounds": [[0, 0, 0], [4, 3, 5]]},
        registration_quality={"accepted": True, "overlap_fraction": 0.91, "rmse_m": 0.012},
        thresholds={"distance_m": 0.05, "confidence": 0.8},
        evidence_ids=[evidence_id],
        algorithm_id="sip.synthetic.change-detector",
        algorithm_version="1.0.0",
        executable_hash="a" * 64,
        parameters_hash="b" * 64,
        observed_coverage={"room-101": 0.91},
        candidates=[
            {
                "change_class": "moved",
                "entity_id": entity_id,
                "region": {"region_id": "room-101"},
                "metrics": {"distance_m": 0.2, "confidence": 0.93},
                "evidence_ids": [evidence_id],
                "coverage_status": "observed",
                "difference_causes": ["geometry"],
            },
            {
                "change_class": "removed",
                "entity_id": "unobserved-device",
                "region": {"region_id": "room-101-edge"},
                "metrics": {"confidence": 0.99},
                "evidence_ids": [evidence_id],
                "coverage_status": "unobserved",
                "difference_causes": ["geometry"],
            },
            {
                "change_class": "modified",
                "entity_id": entity_id,
                "region": {"region_id": "room-101"},
                "metrics": {"confidence": 0.97},
                "evidence_ids": [evidence_id],
                "coverage_status": "observed",
                "difference_causes": ["lighting"],
            },
        ],
        idempotency_key="temporal-progress-05",
        actor_id=actor,
    )
    assert comparison["state"] == "pending_review"
    active = [item for item in comparison["candidates"] if item["state"] == "active"]
    suppressed = [item for item in comparison["candidates"] if item["state"] == "suppressed"]
    assert len(active) == 1
    assert len(suppressed) == 2
    assert any(item["change_class"] == "unobserved" for item in suppressed)
    assert any("lighting" in item["difference_causes"] for item in suppressed)

    ordinary = context.scene_runtime.get_temporal_comparison(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison["comparison_id"],
        include_suppression_details=False,
    )
    assert len(ordinary["candidates"]) == 1
    assert ordinary["suppression_summary"] == {"suppressed_count": 2, "details_withheld": True}

    with pytest.raises(AuthorizationError) as self_review:
        context.scene_runtime.review_change_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            comparison_id=comparison["comparison_id"],
            candidate_id=active[0]["candidate_id"],
            reviewer_id=actor,
            outcome="accepted",
            rationale="requester cannot self approve",
            evidence_ids=[evidence_id],
            policy_snapshot_hash="c" * 64,
            idempotency_key="self-review-denied",
        )
    assert self_review.value.code == "CHANGE_REVIEWER_NOT_INDEPENDENT"

    review = context.scene_runtime.review_change_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison["comparison_id"],
        candidate_id=active[0]["candidate_id"],
        reviewer_id="independent-reviewer",
        outcome="accepted",
        rationale="evidence and registration support the movement",
        evidence_ids=[evidence_id],
        policy_snapshot_hash="c" * 64,
        idempotency_key="independent-review-1",
    )
    assert review["semantic_event_id"]

    with pytest.raises(ConflictError) as suppressed_review:
        context.scene_runtime.review_change_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            comparison_id=comparison["comparison_id"],
            candidate_id=suppressed[0]["candidate_id"],
            reviewer_id="independent-reviewer",
            outcome="accepted",
            rationale="must remain denied",
            evidence_ids=[evidence_id],
            policy_snapshot_hash="d" * 64,
            idempotency_key="suppressed-review-denied",
        )
    assert suppressed_review.value.code == "CHANGE_SUPPRESSED_CANDIDATE_REVIEW_DENIED"

    applied = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison["comparison_id"],
        branch="main",
        expected_head=candidate_commit,
        message="Apply independently reviewed temporal change",
        actor_id="publisher",
    )
    assert applied["commit_id"] != candidate_commit
    replayed = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison["comparison_id"],
        branch="main",
        expected_head=candidate_commit,
        message="Idempotent replay",
        actor_id="publisher",
    )
    assert replayed["idempotent_replay"] is True
    assert replayed["commit_id"] == applied["commit_id"]

    benchmark = context.scene_runtime.record_change_benchmark(
        tenant_id=tenant_id,
        project_id=project_id,
        algorithm_id="sip.synthetic.change-detector",
        algorithm_version="1.0.0",
        executable_hash="a" * 64,
        benchmark_profile="progress-05-cpu-reference",
        fixture_root_hash="e" * 64,
        metrics_by_class={
            "moved": {"precision": 1.0, "recall": 1.0, "localization_error_m": 0.01, "false_action_rate": 0.0},
            "removed": {"precision": 1.0, "recall": 1.0, "localization_error_m": 0.0, "false_action_rate": 0.0},
        },
        environment={"fixture": "deterministic", "hardware": "cpu-reference"},
        actor_id="benchmark-runner",
    )
    assert benchmark["benchmark_hash"]

    with context.database.session() as db:
        assert db.scalar(select(ChangeReviewRow.review_id).where(ChangeReviewRow.review_id == review["review_id"]))
        event = db.scalar(select(SemanticChangeEventRow).where(SemanticChangeEventRow.comparison_id == comparison["comparison_id"]))
        assert event is not None and event.applied_commit_id == applied["commit_id"]
        emitted = {row.event_type for row in db.scalars(select(OutboxEventRow).where(OutboxEventRow.project_id == project_id))}
    assert {
        "viewer_session.created",
        "temporal_comparison.created",
        "change_candidate.reviewed",
        "scene.change.accepted",
        "scene.change.applied",
        "change_benchmark.recorded",
    } <= emitted


@pytest.mark.security
@pytest.mark.integration
def test_scene_runtime_scope_is_fail_closed_across_tenants(context) -> None:
    """REQ: TSTSEC-001 viewer and comparison records do not disclose cross-tenant existence."""
    tenant_one = context.tenancy.create_tenant("One", tenant_id="scene-runtime-one")
    tenant_two = context.tenancy.create_tenant("Two", tenant_id="scene-runtime-two")
    project_one = context.tenancy.create_project(tenant_one, "One", vertical="platform", classification="internal", project_id="scene-runtime-project-one", actor_id="admin")
    project_two = context.tenancy.create_project(tenant_two, "Two", vertical="platform", classification="internal", project_id="scene-runtime-project-two", actor_id="admin")
    scene_id, first, _, entity_id = _scene_state(context, tenant_one, project_one, "admin-one")
    created = _session(context, _principal(tenant_one, project_one, "admin-one", ["tenant_admin"]), project_one, scene_id, [first], entity_id)
    with pytest.raises(NotFoundError):
        context.scene_runtime.get_viewer_session(
            tenant_id=tenant_two,
            project_id=project_two,
            session_id=created["session_id"],
        )


def _accepted_change_fixture(context, tenant_id: str, project_id: str, actor: str):
    scene_id, baseline, candidate_commit, entity_id = _scene_state(context, tenant_id, project_id, actor)
    evidence_id = _evidence(context, tenant_id, project_id, actor)
    principal = _principal(tenant_id, project_id, actor, ["tenant_admin"])
    viewer = _session(context, principal, project_id, scene_id, [baseline, candidate_commit], entity_id)
    comparison = context.scene_runtime.create_temporal_comparison(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        baseline_commit_id=baseline,
        candidate_commit_id=candidate_commit,
        viewer_session_id=viewer["session_id"],
        comparable_region={"region_id": "room-101"},
        registration_quality={"accepted": True, "overlap_fraction": 0.95, "rmse_m": 0.01},
        thresholds={"distance_m": 0.05, "confidence": 0.8},
        evidence_ids=[evidence_id],
        algorithm_id="sip.synthetic.atomic-change",
        algorithm_version="1.0.0",
        executable_hash="1" * 64,
        parameters_hash="2" * 64,
        observed_coverage={"room-101": 0.95},
        candidates=[{
            "change_class": "moved",
            "entity_id": entity_id,
            "region": {"region_id": "room-101"},
            "metrics": {"distance_m": 0.12, "confidence": 0.94},
            "evidence_ids": [evidence_id],
            "coverage_status": "observed",
            "difference_causes": ["geometry"],
        }],
        idempotency_key="atomic-change-fixture",
        actor_id=actor,
    )
    candidate = next(item for item in comparison["candidates"] if item["state"] == "active")
    context.scene_runtime.review_change_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison["comparison_id"],
        candidate_id=candidate["candidate_id"],
        reviewer_id="independent-atomic-reviewer",
        outcome="accepted",
        rationale="deterministic accepted change for atomicity verification",
        evidence_ids=[evidence_id],
        policy_snapshot_hash="3" * 64,
        idempotency_key="atomic-change-review",
    )
    return comparison, candidate_commit


@pytest.mark.integration
def test_semantic_change_application_is_atomic_and_retry_is_idempotent(bootstrapped, monkeypatch) -> None:
    """REQ: RECCHANG-005 accepted changes commit, link, audit, and publish atomically and idempotently."""
    context, tenant_id, project_id, actor = bootstrapped
    comparison, candidate_commit = _accepted_change_fixture(context, tenant_id, project_id, actor)
    comparison_id = comparison["comparison_id"]
    workflow_event_id = f"temporal-comparison:{comparison_id}"
    original_create = context.scene_runtime._events.create

    def fail_after_scene_commit(session, **kwargs):
        if kwargs.get("event_type") == "scene.change.applied":
            raise RuntimeError("injected failure after scene commit creation")
        return original_create(session, **kwargs)

    monkeypatch.setattr(context.scene_runtime._events, "create", fail_after_scene_commit)
    with pytest.raises(RuntimeError, match="injected failure"):
        context.scene_runtime.apply_accepted_changes(
            tenant_id=tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            branch="main",
            expected_head=candidate_commit,
            message="Atomic application must roll back on failure",
            actor_id="publisher",
        )

    with context.database.session() as db:
        branch = db.scalar(
            select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == comparison["scene_id"],
                SceneBranchRow.name == "main",
            )
        )
        workflow_commit = db.scalar(
            select(SceneCommitRow).where(
                SceneCommitRow.tenant_id == tenant_id,
                SceneCommitRow.project_id == project_id,
                SceneCommitRow.workflow_event_id == workflow_event_id,
            )
        )
        events = list(db.scalars(select(SemanticChangeEventRow).where(SemanticChangeEventRow.comparison_id == comparison_id)))
        stored_comparison = db.get(TemporalComparisonRow, comparison_id)
        applied_outbox = list(db.scalars(select(OutboxEventRow).where(OutboxEventRow.event_type == "scene.change.applied", OutboxEventRow.aggregate_id == comparison_id)))
        applied_audit = list(db.scalars(select(AuditEventRow).where(AuditEventRow.action == "semantic_change:apply", AuditEventRow.project_id == project_id)))
    assert branch is not None and branch.head_commit_id == candidate_commit
    assert workflow_commit is None
    assert events and all(event.applied_commit_id is None for event in events)
    assert stored_comparison is not None and stored_comparison.state == "reviewed"
    assert applied_outbox == []
    assert applied_audit == []

    monkeypatch.setattr(context.scene_runtime._events, "create", original_create)
    applied = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison_id,
        branch="main",
        expected_head=candidate_commit,
        message="Atomic application succeeds after retry",
        actor_id="publisher",
    )
    replay = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison_id,
        branch="main",
        expected_head=candidate_commit,
        message="Replay cannot create another commit",
        actor_id="publisher",
    )
    assert replay["idempotent_replay"] is True
    assert replay["commit_id"] == applied["commit_id"]
    with context.database.session() as db:
        commits = list(
            db.scalars(
                select(SceneCommitRow).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.workflow_event_id == workflow_event_id,
                )
            )
        )
    assert len(commits) == 1


@pytest.mark.integration
def test_semantic_change_application_concurrent_callers_resolve_to_one_governed_result(bootstrapped) -> None:
    """REQ: RECCHANG-005 concurrent semantic-change application is governed and idempotent."""
    context, tenant_id, project_id, actor = bootstrapped
    comparison, candidate_commit = _accepted_change_fixture(context, tenant_id, project_id, actor)
    comparison_id = comparison["comparison_id"]
    workflow_event_id = f"temporal-comparison:{comparison_id}"
    flush_barrier = Barrier(2)

    def synchronize_competing_scene_commit_flushes(session, flush_context, instances) -> None:
        del flush_context, instances
        if session.info.get("r2_workflow_flush_synchronized"):
            return
        if any(
            isinstance(item, SceneCommitRow) and item.workflow_event_id == workflow_event_id
            for item in session.new
        ):
            session.info["r2_workflow_flush_synchronized"] = True
            flush_barrier.wait(timeout=20)

    def apply() -> dict:
        return context.scene_runtime.apply_accepted_changes(
            tenant_id=tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            branch="main",
            expected_head=candidate_commit,
            message="Concurrent callers must converge on one governed commit",
            actor_id="publisher",
        )

    event.listen(Session, "before_flush", synchronize_competing_scene_commit_flushes)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(apply) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
    finally:
        event.remove(Session, "before_flush", synchronize_competing_scene_commit_flushes)

    assert {result["commit_id"] for result in results} == {results[0]["commit_id"]}
    assert sorted(result["idempotent_replay"] for result in results) == [False, True]

    with context.database.session() as db:
        commits = list(
            db.scalars(
                select(SceneCommitRow).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.workflow_event_id == workflow_event_id,
                )
            )
        )
        branch_row = db.scalar(
            select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == comparison["scene_id"],
                SceneBranchRow.name == "main",
            )
        )
        semantic_events = list(
            db.scalars(
                select(SemanticChangeEventRow).where(
                    SemanticChangeEventRow.tenant_id == tenant_id,
                    SemanticChangeEventRow.project_id == project_id,
                    SemanticChangeEventRow.comparison_id == comparison_id,
                )
            )
        )
        outbox = list(
            db.scalars(
                select(OutboxEventRow).where(
                    OutboxEventRow.tenant_id == tenant_id,
                    OutboxEventRow.project_id == project_id,
                    OutboxEventRow.event_type == "scene.change.applied",
                    OutboxEventRow.aggregate_id == comparison_id,
                )
            )
        )
        committed_outbox = list(
            db.scalars(
                select(OutboxEventRow).where(
                    OutboxEventRow.tenant_id == tenant_id,
                    OutboxEventRow.project_id == project_id,
                    OutboxEventRow.event_type == "scene.committed",
                    OutboxEventRow.aggregate_id == results[0]["commit_id"],
                )
            )
        )
        audits = list(
            db.scalars(
                select(AuditEventRow).where(
                    AuditEventRow.tenant_id == tenant_id,
                    AuditEventRow.project_id == project_id,
                    AuditEventRow.action == "semantic_change:apply",
                )
            )
        )
        commit_audits = list(
            db.scalars(
                select(AuditEventRow).where(
                    AuditEventRow.tenant_id == tenant_id,
                    AuditEventRow.project_id == project_id,
                    AuditEventRow.action == "scene:commit",
                    AuditEventRow.resource_id == results[0]["commit_id"],
                )
            )
        )

    assert len(commits) == 1
    commit_id = commits[0].commit_id
    assert branch_row is not None and branch_row.head_commit_id == commit_id
    assert semantic_events and {event_row.applied_commit_id for event_row in semantic_events} == {commit_id}
    assert len(outbox) == 1 and outbox[0].payload_json["commit_id"] == commit_id
    assert len(committed_outbox) == 1
    assert len(audits) == 1 and audits[0].resource_id == commit_id
    assert len(commit_audits) == 1
    assert commit_audits[0].details_json["parent"] == candidate_commit


@pytest.mark.integration
def test_concurrent_replay_integrity_gap_returns_stable_sip_conflict(bootstrapped) -> None:
    """REQ: RECCHANG-005 inconsistent concurrent replay state fails with a stable SIP conflict."""
    context, tenant_id, project_id, actor = bootstrapped
    comparison, candidate_commit = _accepted_change_fixture(context, tenant_id, project_id, actor)
    comparison_id = comparison["comparison_id"]
    applied = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=comparison_id,
        branch="main",
        expected_head=candidate_commit,
        message="Create the governed result before integrity-gap injection",
        actor_id="publisher",
    )
    with context.database.session() as db:
        branch_row = db.scalar(
            select(SceneBranchRow).where(
                SceneBranchRow.tenant_id == tenant_id,
                SceneBranchRow.project_id == project_id,
                SceneBranchRow.scene_id == comparison["scene_id"],
                SceneBranchRow.name == "main",
            )
        )
        assert branch_row is not None
        branch_row.head_commit_id = candidate_commit

    with pytest.raises(ConflictError) as captured:
        context.scene_runtime._resolve_concurrent_change_application(
            tenant_id=tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            branch="main",
            expected_head=candidate_commit,
        )
    assert captured.value.code == "CHANGE_APPLICATION_CONCURRENT_STATE_CONFLICT"
    assert captured.value.details["reason"] == "branch_head_mismatch"
    assert captured.value.details["commit_id"] == applied["commit_id"]
