from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from sip.canonical import canonical_sha256
from sip.database import OperationRow
from sip.errors import AuthenticationError, ConflictError, ValidationError
from sip.temporal import db_now
from sip.worker_manifest import load_worker_manifest
from sip.worker_protocol import SignedWorkerLease, WorkerLease, WorkerLeaseAuthority

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_signed_worker_lease_binds_input_identity_capability_budget_and_deadline(bootstrapped) -> None:
    """REQ: PLTGRPC-001 and PLTGRPC-005."""
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="pose.optimize",
        idempotency_key="signed-lease",
        input_manifest={"source_points": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "target_points": [[0, 0, 0], [1, 0, 0], [0, 1, 0]]},
        actor_id=actor,
    )
    operation = context.operations.lease(operation["operation_id"], worker_id="pose-worker", lease_seconds=120)
    manifest = load_worker_manifest(ROOT / "workers/pose-optimizer/worker-manifest.json", repository_root=ROOT)
    authority = WorkerLeaseAuthority(context.settings.signing_key)
    signed = authority.issue(operation=operation, manifest=manifest, lease_seconds=120)
    verified = authority.verify(signed, manifest)
    assert verified.input_manifest_hash == canonical_sha256(verified.input_manifest)
    assert verified.operation_type in verified.capabilities
    assert verified.workload_identity == manifest.workload_identity
    assert verified.output_staging_scope.mode == "write_only_quarantine"
    assert verified.output_staging_scope.maximum_bytes == manifest.resource_limits.max_output_bytes
    assert verified.cancellation_token


@pytest.mark.security
def test_signed_worker_lease_rejects_tampered_envelope(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="tampered-lease",
        input_manifest={"title": "A"},
        actor_id=actor,
    )
    operation = context.operations.lease(operation["operation_id"], worker_id="report-worker", lease_seconds=120)
    manifest = load_worker_manifest(ROOT / "workers/report-export/worker-manifest.json", repository_root=ROOT)
    authority = WorkerLeaseAuthority(context.settings.signing_key)
    signed = authority.issue(operation=operation, manifest=manifest, lease_seconds=120)
    raw = signed.lease.model_dump(mode="json")
    raw["adapter_profile"] = "tampered"
    tampered = SignedWorkerLease(lease=WorkerLease.model_validate(raw), token=signed.token)
    with pytest.raises(AuthenticationError) as exc:
        authority.verify(tampered, manifest)
    assert exc.value.code == "WORKER_LEASE_CLAIM_MISMATCH"


@pytest.mark.contract
def test_control_plane_rejects_output_hash_mismatch(bootstrapped) -> None:
    """REQ: PLTGRPC-004."""
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="hash-mismatch",
        input_manifest={"title": "A"},
        actor_id=actor,
    )
    context.operations.lease(operation["operation_id"], worker_id="worker-a")
    context.operations.start(operation["operation_id"], worker_id="worker-a")
    with pytest.raises(ValidationError) as exc:
        context.operations.complete(
            operation["operation_id"],
            worker_id="worker-a",
            output={"ok": True},
            claimed_output_hash="0" * 64,
        )
    assert exc.value.code == "WORKER_OUTPUT_HASH_MISMATCH"
    assert context.operations.get(operation["operation_id"])["state"] == "running"


@pytest.mark.contract
def test_checkpoint_sequence_is_monotonic_and_expired_leases_reconcile(bootstrapped) -> None:
    """REQ: PLTGRPC-003, PLTGRPC-006, HYBAPI-009, HYBAPI-010."""
    context, tenant_id, project_id, actor = bootstrapped
    safe = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="safe-expiry",
        input_manifest={"title": "A"},
        actor_id=actor,
    )
    context.operations.lease(safe["operation_id"], worker_id="worker-a")
    context.operations.start(safe["operation_id"], worker_id="worker-a")
    context.operations.checkpoint(
        safe["operation_id"],
        worker_id="worker-a",
        progress=0.5,
        checkpoint={"sequence": 1, "stage": "half", "safe_to_resume": True},
    )
    with pytest.raises(ConflictError) as exc:
        context.operations.checkpoint(
            safe["operation_id"],
            worker_id="worker-a",
            progress=0.6,
            checkpoint={"sequence": 1, "stage": "duplicate", "safe_to_resume": True},
        )
    assert exc.value.code == "CHECKPOINT_SEQUENCE_NOT_MONOTONIC"

    unsafe = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="unsafe-expiry",
        input_manifest={"title": "B"},
        actor_id=actor,
    )
    context.operations.lease(unsafe["operation_id"], worker_id="worker-b")
    context.operations.start(unsafe["operation_id"], worker_id="worker-b")
    with context.database.session() as session:
        for operation_id in (safe["operation_id"], unsafe["operation_id"]):
            row = session.get(OperationRow, operation_id)
            assert row is not None
            row.lease_expires_at = db_now() - timedelta(seconds=1)
    result = context.operations.reconcile_expired_leases()
    assert safe["operation_id"] in result["released"]
    assert unsafe["operation_id"] in result["quarantined"]
    assert context.operations.get(safe["operation_id"])["state"] == "pending"
    assert context.operations.get(unsafe["operation_id"])["state"] == "quarantined"

@pytest.mark.contract
def test_trace_context_is_durable_and_cryptographically_bound_to_worker_lease(bootstrapped) -> None:
    """REQ: ARCOBS-003 ingest-to-worker trace context survives retries without becoming authorization data."""
    context, tenant_id, project_id, actor = bootstrapped
    traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="trace-context",
        input_manifest={"title": "Trace"},
        actor_id=actor,
        traceparent=traceparent,
    )
    assert operation["traceparent"] == traceparent
    operation = context.operations.lease(operation["operation_id"], worker_id="report-worker", lease_seconds=120)
    manifest = load_worker_manifest(ROOT / "workers/report-export/worker-manifest.json", repository_root=ROOT)
    authority = WorkerLeaseAuthority(context.settings.signing_key)
    signed = authority.issue(operation=operation, manifest=manifest, lease_seconds=120)
    assert signed.lease.traceparent == traceparent
    assert authority.verify(signed, manifest).traceparent == traceparent

    raw = signed.lease.model_dump(mode="json")
    raw["traceparent"] = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"
    tampered = SignedWorkerLease(lease=WorkerLease.model_validate(raw), token=signed.token)
    with pytest.raises(AuthenticationError) as exc:
        authority.verify(tampered, manifest)
    assert exc.value.code == "WORKER_LEASE_CLAIM_MISMATCH"


@pytest.mark.contract
def test_invalid_trace_context_is_rejected_before_operation_persistence(bootstrapped) -> None:
    """REQ: ARCOBS-003 invalid or all-zero trace contexts fail closed."""
    context, tenant_id, project_id, actor = bootstrapped
    with pytest.raises(ValueError):
        context.operations.create(
            tenant_id=tenant_id,
            project_id=project_id,
            operation_type="report.export",
            idempotency_key="invalid-trace-context",
            input_manifest={"title": "Trace"},
            actor_id=actor,
            traceparent="00-00000000000000000000000000000000-0000000000000000-01",
        )

@pytest.mark.contract
def test_interaction_candidate_package_requires_exact_non_authoritative_ceiling_and_disposable() -> None:
    """REQ: RECHYB-002, DATHYB-004 worker candidates cannot drift from the proxy authority contract."""
    from pydantic import ValidationError as PydanticValidationError

    from sip.worker_protocol import CandidatePackage

    digest = "a" * 64
    base = {
        "candidate_id": "candidate",
        "representation_id": "representation",
        "asset_id": "asset",
        "asset_sha256": digest,
        "media_type": "model/gltf-binary",
        "operation_id": "operation",
        "operation_type": "mesh.lod",
        "output_role": "interaction_proxy",
        "representation_kind": "interaction",
        "coordinate_frame_id": "world",
        "source_asset_ids": ["metric-source"],
        "payload_hash": digest,
        "source_manifest_hash": "b" * 64,
        "parameters_hash": "c" * 64,
        "environment_manifest_hash": "d" * 64,
        "provider_id": "local-proxy",
        "provider_version": "1.0.0",
        "provider_executable_digest": "e" * 64,
        "authority_ceiling": "derived_non_authoritative",
        "disposable": True,
        "lossy": True,
        "intended_uses": ["picking"],
        "prohibited_uses": ["verified_measurement", "automatic_publication"],
    }
    assert CandidatePackage.model_validate(base).disposable is True
    for patch in ({"authority_ceiling": "interaction"}, {"authority_ceiling": "metric"}, {"disposable": False}):
        with pytest.raises(PydanticValidationError):
            CandidatePackage.model_validate({**base, **patch})
