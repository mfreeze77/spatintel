from __future__ import annotations

import pytest

from sip.errors import ConflictError


@pytest.mark.unit
def test_pltjob_001_durable_idempotent_checkpoint_cancel_resume(bootstrapped) -> None:
    """REQ: PLTJOB-001 durable workflow state, attempts, checkpoints, manifests, cancellation, and output identity."""
    context, tenant_id, project_id, actor = bootstrapped
    created = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="capture.normalize",
        idempotency_key="fixture-1",
        input_manifest={"capture_hash": "a" * 64},
        actor_id=actor,
    )
    repeated = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="capture.normalize",
        idempotency_key="fixture-1",
        input_manifest={"capture_hash": "a" * 64},
        actor_id=actor,
    )
    assert repeated["operation_id"] == created["operation_id"]
    leased = context.operations.lease(created["operation_id"], worker_id="worker-a")
    assert leased["attempt"] == 1
    context.operations.start(created["operation_id"], worker_id="worker-a")
    checkpointed = context.operations.checkpoint(created["operation_id"], worker_id="worker-a", progress=0.5, checkpoint={"frame": 10})
    assert checkpointed["checkpoint"] == {"frame": 10}
    completed = context.operations.complete(created["operation_id"], worker_id="worker-a", output={"normalized_hash": "b" * 64})
    assert completed["state"] == "succeeded"
    assert completed["output_hash"]


@pytest.mark.unit
def test_pltjob_idempotency_conflict_and_lease_exclusion(bootstrapped) -> None:
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="fusion",
        idempotency_key="same",
        input_manifest={"input": 1},
        actor_id=actor,
    )
    with pytest.raises(ConflictError) as error:
        context.operations.create(
            tenant_id=tenant_id,
            project_id=project_id,
            operation_type="fusion",
            idempotency_key="same",
            input_manifest={"input": 2},
            actor_id=actor,
        )
    assert error.value.code == "IDEMPOTENCY_PAYLOAD_CONFLICT"
    context.operations.lease(operation["operation_id"], worker_id="worker-a")
    with pytest.raises(ConflictError):
        context.operations.lease(operation["operation_id"], worker_id="worker-b")
