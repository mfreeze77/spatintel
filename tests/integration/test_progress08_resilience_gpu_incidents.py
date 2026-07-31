from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sip.canonical import canonical_sha256
from sip.database import AssetRefRow, AuditEventRow
from sip.errors import AuthorizationError, ConflictError, ValidationError
from sip.models import Audience, SignedPrincipal
from sip.spatial_query import SearchQuerySpec
from sip.temporal import db_now
from sip.worker_manifest import WorkerResourceLimits
from sip.worker_sandbox import ExecutionSandbox
from tests.progress08_helpers import bootstrap, compute_profile, now


def test_progress08_resilience_profile_worker_exhaustion_and_postwrite_integrity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ: ARCRES-001, ARCRES-002, ARCRES-003 components declare recovery behavior, worker exhaustion is job-contained, and object bytes are reverified before publication."""
    context, tenant, project = bootstrap(tmp_path, name="resilience")
    service = context.operations_intelligence
    profile = service.register_resilience_profile(
        component="reconstruction-worker",
        version="v1",
        owner="sre",
        blast_radius="job",
        retry_safety="checkpointed",
        recovery_point_seconds=30,
        recovery_time_seconds=300,
        degraded_behavior={
            "mode": "queue_and_resume",
            "user_message": "Processing paused; verified work is retained.",
            "authorization_behavior": "fail_closed",
            "data_integrity_behavior": "verified_checkpoint_only",
        },
        dependencies=[{"component": "object-store", "failure_behavior": "fail_closed"}],
        actor_id="sre",
    )
    replay = service.register_resilience_profile(
        component="reconstruction-worker",
        version="v1",
        owner="sre",
        blast_radius="job",
        retry_safety="checkpointed",
        recovery_point_seconds=30,
        recovery_time_seconds=300,
        degraded_behavior={
            "mode": "queue_and_resume",
            "user_message": "Processing paused; verified work is retained.",
            "authorization_behavior": "fail_closed",
            "data_integrity_behavior": "verified_checkpoint_only",
        },
        dependencies=[{"component": "object-store", "failure_behavior": "fail_closed"}],
        actor_id="sre",
    )
    assert replay["profile_id"] == profile["profile_id"]
    assert replay["idempotent_replay"] is True

    sandbox = ExecutionSandbox(WorkerResourceLimits(max_output_bytes=32, max_memory_bytes=4_294_967_296))
    with sandbox:
        with pytest.raises(ValidationError) as exhausted:
            sandbox.validate_output({"payload": "x" * 256})
    assert exhausted.value.code == "WORKER_OUTPUT_LIMIT_EXCEEDED"
    # The shared control plane remains usable after the isolated job is terminated.
    assert context.tenancy.create_project(tenant, "Still responsive", vertical="platform", classification="internal", project_id="resilience-still-live", actor_id="sre") == "resilience-still-live"

    original_read = context.assets.store.read_bytes
    monkeypatch.setattr(context.assets.store, "read_bytes", lambda digest: b"corrupted-after-write")
    from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass

    with pytest.raises(ValidationError) as corrupt:
        context.assets.ingest_bytes(
            tenant_id=tenant,
            project_id=project,
            data=b"immutable source",
            media_type="application/octet-stream",
            original_name="source.bin",
            classification=Classification.INTERNAL,
            retention_class="test",
            source_class=SourceClass.DIRECT_CAPTURE,
            authority_class=AuthorityClass.EVIDENCE,
            provenance=ProvenanceRef(source_ids=["fixture"], output_hash=None),
            actor_id="capture",
        )
    assert corrupt.value.code == "OBJECT_POST_WRITE_VERIFICATION_FAILED"
    with context.database.session() as session:
        assert session.scalar(select(func.count()).select_from(AssetRefRow).where(AssetRefRow.tenant_id == tenant, AssetRefRow.project_id == project)) == 0
    monkeypatch.setattr(context.assets.store, "read_bytes", original_read)


def test_progress08_index_outage_metadata_fallback_authorizes_before_navigation(tmp_path: Path) -> None:
    """REQ: ARCRES-004 index outage falls back to bounded fresh canonical metadata without unauthorized counts, snippets, ranking, or stale critical results."""
    context, tenant, project = bootstrap(tmp_path, name="fallback")
    context.search.index(
        tenant_id=tenant,
        project_id=project,
        text="Visible fire panel",
        entity_id="panel-visible",
        entity_type="fire_alarm_panel",
        asset_id="asset-visible",
        embedding=None,
        spatial_bounds=None,
        temporal_start=None,
        temporal_end=None,
        policy={"audience": "project"},
        source_sequence=2,
        index_sequence=2,
        tags=["visible"],
    )
    context.search.index(
        tenant_id=tenant,
        project_id=project,
        text="Private secret panel",
        entity_id="panel-private",
        entity_type="fire_alarm_panel",
        asset_id="asset-private",
        embedding=None,
        spatial_bounds=None,
        temporal_start=None,
        temporal_end=None,
        policy={"audience": "private", "allowed_subject_ids": ["another-user"]},
        source_sequence=2,
        index_sequence=2,
        tags=["private"],
    )
    context.search.index(
        tenant_id=tenant,
        project_id=project,
        text="Stale panel",
        entity_id="panel-stale",
        entity_type="fire_alarm_panel",
        asset_id="asset-stale",
        embedding=None,
        spatial_bounds=None,
        temporal_start=None,
        temporal_end=None,
        policy={"audience": "project"},
        source_sequence=3,
        index_sequence=2,
        tags=["stale"],
    )
    principal = SignedPrincipal(
        subject_id="viewer",
        tenant_id=tenant,
        project_ids=[project],
        roles=["viewer"],
        purposes=["facility_operations"],
        audience=Audience.PROJECT,
        attributes={},
    )
    result = context.search.metadata_fallback(
        principal=principal,
        spec=SearchQuerySpec(
            tenant_id=tenant,
            project_id=project,
            full_text="secret",
            entity_types=["fire_alarm_panel"],
            critical_workflow=True,
            limit=200,
        ),
    )
    assert result["degraded_mode"] == "bounded_metadata_navigation"
    assert result["authorization_before_navigation"] is True
    assert result["full_text_applied"] is False
    assert result["semantic_ranking_applied"] is False
    assert result["authorized_count"] == 1
    assert result["items"][0]["entity_id"] == "panel-visible"
    assert "private" not in str(result).lower()
    assert result["freshness"]["critical_stale_results_omitted"] == 1
    assert result["freshness"]["canonical_lookup_required"] is True


def test_progress08_compute_profiles_compatibility_oom_cost_stages_and_resume(tmp_path: Path) -> None:
    """REQ: RECGPU-001, RECGPU-002, RECGPU-003, RECGPU-004, RECGPU-005, RECGPU-006 compute profiles are complete, scheduler admission is compatible and isolated, OOM is recorded, and verified checkpoints resume."""
    context, tenant, project = bootstrap(tmp_path, name="gpu")
    service = context.operations_intelligence
    incomplete = compute_profile()
    incomplete["cost_stage_weights"] = {"inference": 1.0}
    with pytest.raises(ValidationError) as missing:
        service.register_compute_profile(**incomplete)
    assert missing.value.code == "COMPUTE_COST_STAGES_INCOMPLETE"

    args = compute_profile()
    args.update(
        name="gpu-reference",
        backend="cuda",
        dtype="bf16",
        cuda_version="12.8",
        driver_constraint="570.x",
        peak_vram_mb=12288,
        tenant_isolation="dedicated_container",
        oom_fallback={"mode": "resume_checkpoint"},
    )
    profile = service.register_compute_profile(**args)
    denied = service.check_compute_compatibility(
        compute_profile_id=profile["compute_profile_id"],
        runtime={
            "backend": "cuda",
            "dtype": "bf16",
            "cuda_version": "12.7",
            "driver_version": "560.1",
            "container_digest": args["container_digest"],
            "tenant_context": tenant,
            "batch_tenant_contexts": [tenant, "other-tenant"],
            "job_isolation": "container",
        },
    )
    assert denied["execution_allowed"] is False
    assert {item["field"] for item in denied["mismatches"]} >= {"cuda_version", "driver_version", "batch_tenant_contexts"}
    allowed = service.check_compute_compatibility(
        compute_profile_id=profile["compute_profile_id"],
        runtime={
            "backend": "cuda",
            "dtype": "bf16",
            "cuda_version": "12.8",
            "driver_version": "570.9",
            "container_digest": args["container_digest"],
            "tenant_context": tenant,
            "batch_tenant_contexts": [tenant],
            "job_isolation": "container",
        },
    )
    assert allowed["execution_allowed"] is True
    assert allowed["single_tenant_context_enforced"] is True
    with pytest.raises(ConflictError) as no_checkpoint:
        service.explicit_oom_disposition(compute_profile_id=profile["compute_profile_id"], checkpoint_id=None, tenant_id=tenant, actor_id="gpu-worker")
    assert no_checkpoint.value.code == "OOM_CHECKPOINT_REQUIRED"
    oom = service.explicit_oom_disposition(compute_profile_id=profile["compute_profile_id"], checkpoint_id="checkpoint-1", tenant_id=tenant, actor_id="gpu-worker")
    assert oom["silent_parameter_reduction"] is False
    assert oom["operator_visible"] is True

    operation = context.operations.create(
        tenant_id=tenant,
        project_id=project,
        operation_type="report.export",
        idempotency_key="resume-verified",
        input_manifest={"title": "Synthetic"},
        actor_id="operator",
    )
    context.operations.lease(operation["operation_id"], worker_id="worker-1")
    context.operations.start(operation["operation_id"], worker_id="worker-1")
    context.operations.checkpoint(
        operation["operation_id"],
        worker_id="worker-1",
        progress=0.5,
        checkpoint={"sequence": 1, "stage": "half", "safe_to_resume": True, "completed_units": 5, "total_units": 10},
    )
    resume = service.verified_checkpoint_resume(tenant_id=tenant, project_id=project, operation_id=operation["operation_id"], actor_id="operator")
    assert resume["resume_authorized"] is True
    assert resume["checkpoint_hash"] == canonical_sha256({"sequence": 1, "stage": "half", "safe_to_resume": True, "completed_units": 5, "total_units": 10})


def test_progress08_incident_actions_after_action_reviews_and_game_days(tmp_path: Path) -> None:
    """REQ: OPSSRE-001, OPSSRE-002, OPSSRE-003, OPSSRE-004, OPSSRE-005 incident evidence is noncopying and auditable, reviews create tracked tests, and runbooks are exercised."""
    context, tenant, project = bootstrap(tmp_path, name="incident")
    service = context.operations_intelligence
    occurred = now() - timedelta(minutes=1)
    with pytest.raises(AuthorizationError) as copied:
        service.record_incident_action(
            tenant_id=tenant,
            project_id=project,
            incident_reference="incident-1",
            runbook_reference="docs/runbooks/OPERATIONS_INCIDENTS.md#database-outage",
            action_type="contain",
            command_reference="control:pause-writes",
            decision={"decision": "pause writes", "reason_code": "integrity_uncertain"},
            evidence_references=[{"kind": "audit", "reference": "audit://incident-1"}],
            validation={"control": "database-integrity-check", "result": "pending"},
            rollback={"control": "resume-writes", "criteria": "integrity verified"},
            communication={"audience": "incident-team", "message_code": "database_outage"},
            sensitive_copy_created=True,
            occurred_at=occurred,
            actor_id="incident-commander",
        )
    assert copied.value.code == "INCIDENT_SENSITIVE_COPY_DENIED"
    action = service.record_incident_action(
        tenant_id=tenant,
        project_id=project,
        incident_reference="incident-1",
        runbook_reference="docs/runbooks/OPERATIONS_INCIDENTS.md#database-outage",
        action_type="contain",
        command_reference="control:pause-writes",
        decision={"decision": "pause writes", "reason_code": "integrity_uncertain"},
        evidence_references=[{"kind": "audit", "reference": "audit://incident-1"}],
        validation={"control": "database-integrity-check", "result": "passed"},
        rollback={"control": "resume-writes", "criteria": "integrity verified"},
        communication={"audience": "incident-team", "message_code": "database_outage"},
        sensitive_copy_created=False,
        occurred_at=occurred,
        actor_id="incident-commander",
    )
    assert action["sensitive_copy_created"] is False
    review = service.create_after_action_review(
        tenant_id=tenant,
        project_id=project,
        incident_reference="incident-1",
        findings=[{"finding": "retry envelope unclear", "severity": "medium"}],
        corrective_requirements=[{"requirement_id": "CORR-INC-001", "owner": "sre", "due_at": (now() + timedelta(days=7)).isoformat()}],
        test_ids=["tests/integration/test_progress08_resilience_gpu_incidents.py::test_progress08_incident_actions_after_action_reviews_and_game_days"],
        owner="sre",
        due_at=now() + timedelta(days=7),
        actor_id="incident-commander",
    )
    assert review["state"] == "open"
    exercise = service.record_game_day(
        tenant_id=tenant,
        project_id=project,
        scenario="synthetic queue backlog",
        runbook_reference="docs/runbooks/OPERATIONS_INCIDENTS.md#queue-backlog",
        participants=["sre", "support"],
        observations=[{"observation": "queue alert fired", "result": "passed"}],
        corrective_requirements=[{"requirement_id": "CORR-GD-001", "owner": "sre", "due_at": (now() + timedelta(days=14)).isoformat()}],
        test_ids=["tests/integration/test_progress08_resilience_gpu_incidents.py::test_progress08_incident_actions_after_action_reviews_and_game_days"],
        started_at=now() - timedelta(minutes=15),
        completed_at=now() - timedelta(minutes=1),
        actor_id="sre",
    )
    assert exercise["state"] == "completed"
    with context.database.session() as session:
        actions = list(session.scalars(select(AuditEventRow).where(AuditEventRow.tenant_id == tenant, AuditEventRow.project_id == project)))
    assert {row.action for row in actions} >= {"incident_action:record", "after_action_review:create", "game_day:record"}
