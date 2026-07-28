from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.canonical import canonical_sha256
from sip.contracts import EventEnvelopeContract
from sip.database import OutboxEventRow
from sip.errors import AuthorizationError, ConflictError, ValidationError
from sip.events import EventCatalog, EventRetryPolicy, IdempotentEventConsumer, OutboxEventFactory

ROOT = Path(__file__).resolve().parents[2]


def test_event_catalog_and_schemas_are_versioned_and_complete() -> None:
    """REQ: ARCEVT-001 every event includes identity, type/version, aggregate, tenant/project, timestamps, trace/correlation, producer, classification, and payload hash."""
    catalog = EventCatalog.load()
    for entry in catalog.document.events:
        schema_path = ROOT / "schemas/events" / entry.type / f"{entry.version}.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema["required"])
        assert {
            "event_id", "event_type", "schema_version", "tenant_id", "project_id", "aggregate_type",
            "aggregate_id", "occurred_at", "recorded_at", "actor_id", "workload_identity", "producer",
            "classification", "trace_id", "correlation_id", "causation_id", "payload", "payload_hash",
        } <= required
        assert schema["properties"]["event_type"]["const"] == entry.type
        assert schema["properties"]["schema_version"]["const"] == entry.version


def test_transactional_outbox_emits_complete_payload_hashed_envelope(bootstrapped) -> None:
    """REQ: ARCEVT-001, ARCEVT-003, HYBAPI-005 committed workflow state and its complete event envelope share one transaction."""
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="event-envelope",
        input_manifest={"title": "Event evidence"},
        actor_id=actor,
        traceparent="00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    )
    with context.database.session() as session:
        row = session.scalar(select(OutboxEventRow).where(OutboxEventRow.aggregate_id == operation["operation_id"]))
        assert row is not None
        envelope = OutboxEventFactory.to_envelope(row)
        assert envelope.producer == "workflow-service"
        assert envelope.classification == "internal"
        assert envelope.trace_id == "0123456789abcdef0123456789abcdef"
        assert envelope.correlation_id == operation["operation_id"]
        assert envelope.payload_hash == canonical_sha256(envelope.payload)
        assert envelope.recorded_at >= envelope.occurred_at


def test_consumer_deduplicates_event_id_and_hash_and_rejects_conflict(bootstrapped) -> None:
    """REQ: ARCEVT-002 consumers tolerate redelivery using event ID and immutable payload hash."""
    context, tenant_id, project_id, actor = bootstrapped
    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="report.export",
        idempotency_key="event-dedup",
        input_manifest={"title": "Dedup"},
        actor_id=actor,
    )
    with context.database.session() as session:
        row = session.scalar(select(OutboxEventRow).where(OutboxEventRow.aggregate_id == operation["operation_id"]))
        envelope = OutboxEventFactory.to_envelope(row)
    consumer = IdempotentEventConsumer()
    assert consumer.accept(envelope) is True
    assert consumer.accept(envelope) is False
    changed = envelope.model_copy(update={"payload_hash": "f" * 64})
    with pytest.raises(ConflictError):
        consumer.accept(changed)


def test_unregistered_producer_and_sensitive_payload_fail_before_outbox_write(bootstrapped) -> None:
    """REQ: ARCEVT-004, HYBAPI-007 producers and payloads fail closed before restricted data enters the event plane."""
    context, tenant_id, project_id, _ = bootstrapped
    factory = OutboxEventFactory()
    with context.database.session() as session:
        with pytest.raises(AuthorizationError):
            factory.create(
                session,
                event_type="operation.created", schema_version="1.0.0", tenant_id=tenant_id,
                project_id=project_id, aggregate_type="operation", aggregate_id="op-x", payload={},
                producer="scene-service", actor_id="actor", workload_identity=None,
            )
        with pytest.raises(ValidationError):
            factory.create(
                session,
                event_type="operation.created", schema_version="1.0.0", tenant_id=tenant_id,
                project_id=project_id, aggregate_type="operation", aggregate_id="op-x",
                payload={"transcript_text": "private"}, producer="workflow-service", actor_id="actor",
                workload_identity=None,
            )


def test_retry_and_dead_letter_policy_is_bounded_and_requires_remediation() -> None:
    """REQ: ARCEVT-005 retry, dead-letter, replay, and remediation are explicit and bounded."""
    payload = {"operation_id": "op-a"}
    envelope = EventEnvelopeContract(
        event_id="event-a", event_type="operation.failed", schema_version="1.0.0",
        tenant_id="tenant-a", project_id="project-a", aggregate_type="operation", aggregate_id="op-a",
        occurred_at="2026-07-27T00:00:00Z", recorded_at="2026-07-27T00:00:00Z",
        actor_id=None, workload_identity="sip-worker:test", producer="workflow-service", classification="internal",
        trace_id=None, causation_id=None, correlation_id="op-a", payload=payload,
        payload_hash=canonical_sha256(payload),
    )
    policy = EventRetryPolicy()
    assert policy.disposition("WORK_QUEUE_UNAVAILABLE", attempt=1)["retry"] is True
    assert policy.disposition("PROVIDER_EXECUTION_DENIED", attempt=1)["retry"] is False
    dead = policy.dead_letter(envelope, "PROVIDER_EXECUTION_DENIED", attempts=1)
    assert dead.replay_authorized is False
    with pytest.raises(AuthorizationError):
        policy.authorize_replay(dead, actor_id="", remediation_evidence_hash="x")
    authorized = policy.authorize_replay(dead, actor_id="operator-a", remediation_evidence_hash="a" * 64)
    assert authorized.replay_authorized is True
