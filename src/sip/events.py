from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from .canonical import canonical_json, canonical_sha256, new_uuid
from .contracts import EventEnvelopeContract
from .database import OutboxEventRow, ProjectRow
from .errors import AuthorizationError, ConflictError, ValidationError
from .failures import FailureCatalog
from .temporal import db_now


class EventCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    version: str
    aggregate: str
    owner: str
    classification: str


class EventCatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    json_schema_uri: str = Field(alias="$schema", serialization_alias="$schema")
    catalog_version: str
    compatibility_policy: str
    delivery_semantics: str
    events: list[EventCatalogEntry]

    @model_validator(mode="after")
    def unique_versions(self) -> "EventCatalogDocument":
        keys = [(item.type, item.version) for item in self.events]
        if len(keys) != len(set(keys)):
            raise ValueError("event type/version pairs must be unique")
        return self


class EventCatalog:
    def __init__(self, document: EventCatalogDocument) -> None:
        self.document = document
        self._entries = {(entry.type, entry.version): entry for entry in document.events}

    @classmethod
    def load(cls, path: Path | None = None) -> "EventCatalog":
        path = path or Path(__file__).resolve().parents[2] / "schemas" / "events" / "event-catalog.json"
        try:
            return cls(EventCatalogDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception as exc:
            raise ValidationError("EVENT_CATALOG_INVALID", "event catalog is invalid", {"path": str(path)}) from exc

    def get(self, event_type: str, version: str) -> EventCatalogEntry:
        entry = self._entries.get((event_type, version))
        if entry is None:
            raise ValidationError(
                "EVENT_SCHEMA_UNREGISTERED",
                "event type and version are not registered",
                {"event_type": event_type, "schema_version": version},
            )
        return entry


class OutboxEventFactory:
    """Create bounded, complete outbox events after domain state is committed in-session."""

    FORBIDDEN_PAYLOAD_FRAGMENTS = {
        "raw_geometry",
        "mesh_vertices",
        "gaussians",
        "media_bytes",
        "image_bytes",
        "audio_bytes",
        "transcript_text",
        "precise_coordinates",
        "secret",
        "password",
        "access_token",
    }

    def __init__(self, catalog: EventCatalog | None = None) -> None:
        self.catalog = catalog or EventCatalog.load()

    def create(
        self,
        session: Session,
        *,
        event_type: str,
        schema_version: str,
        tenant_id: str,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        producer: str,
        actor_id: str | None,
        workload_identity: str | None,
        traceparent: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> OutboxEventRow:
        entry = self.catalog.get(event_type, schema_version)
        if producer != entry.owner:
            raise AuthorizationError(
                "EVENT_PRODUCER_DENIED",
                "event producer does not own this event contract",
                {"event_type": event_type, "expected": entry.owner, "actual": producer},
            )
        if entry.aggregate != aggregate_type:
            raise ValidationError(
                "EVENT_AGGREGATE_MISMATCH",
                "event aggregate does not match the catalog",
                {"event_type": event_type, "expected": entry.aggregate, "actual": aggregate_type},
            )
        self._validate_payload(payload)
        project = session.get(ProjectRow, project_id) if project_id else None
        classification = project.classification if project else "internal"
        trace_id = _trace_id(traceparent)
        now = db_now()
        row = OutboxEventRow(
            event_id=new_uuid(),
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=event_type,
            schema_version=schema_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            producer=producer,
            classification=classification,
            actor_id=actor_id,
            workload_identity=workload_identity,
            trace_id=trace_id,
            correlation_id=correlation_id or aggregate_id,
            causation_id=causation_id,
            payload_json=payload,
            payload_hash=canonical_sha256(payload),
            occurred_at=now,
            recorded_at=now,
        )
        # Contract validation occurs before the row is accepted into the session.
        self.to_envelope(row)
        return row

    @staticmethod
    def to_envelope(row: OutboxEventRow) -> EventEnvelopeContract:
        return EventEnvelopeContract(
            event_id=row.event_id,
            event_type=row.event_type,
            schema_version=row.schema_version,
            tenant_id=row.tenant_id,
            project_id=row.project_id,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            occurred_at=row.occurred_at,
            recorded_at=row.recorded_at,
            actor_id=row.actor_id,
            workload_identity=row.workload_identity,
            producer=row.producer,
            classification=row.classification,
            trace_id=row.trace_id,
            causation_id=row.causation_id,
            correlation_id=row.correlation_id,
            payload=row.payload_json,
            payload_hash=row.payload_hash,
        )

    @classmethod
    def _validate_payload(cls, payload: dict[str, Any]) -> None:
        if len(canonical_json(payload)) > 65_536:
            raise ValidationError("EVENT_PAYLOAD_TOO_LARGE", "event payload exceeds the bounded summary limit")

        def walk(value: Any, path: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = str(key).lower()
                    if any(fragment in normalized for fragment in cls.FORBIDDEN_PAYLOAD_FRAGMENTS):
                        raise ValidationError(
                            "EVENT_PAYLOAD_SENSITIVE",
                            "event payload contains a forbidden raw or sensitive field",
                            {"path": f"{path}.{key}".lstrip(".")},
                        )
                    walk(child, f"{path}.{key}" if path else str(key))
            elif isinstance(value, list):
                if len(value) > 256:
                    raise ValidationError("EVENT_PAYLOAD_UNBOUNDED", "event payload list exceeds the bounded item limit", {"path": path})
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")

        walk(payload)


class IdempotentEventConsumer:
    """Reference deduplication state: event ID plus immutable payload hash."""

    def __init__(self) -> None:
        self._processed: dict[str, str] = {}

    def accept(self, envelope: EventEnvelopeContract) -> bool:
        prior = self._processed.get(envelope.event_id)
        if prior is None:
            self._processed[envelope.event_id] = envelope.payload_hash
            return True
        if prior != envelope.payload_hash:
            raise ConflictError(
                "EVENT_ID_PAYLOAD_CONFLICT",
                "an event identifier was replayed with a different payload hash",
                {"event_id": envelope.event_id},
            )
        return False


class DeadLetterRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["sip.dead-letter/v1"] = Field(default="sip.dead-letter/v1", alias="schema", serialization_alias="schema")
    dead_letter_id: str
    event_id: str
    event_type: str
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    failure_code: str
    retry_class: str
    attempts: int = Field(ge=1)
    remediation_required: bool = True
    replay_authorized: bool = False
    created_at: datetime


class EventRetryPolicy:
    def __init__(self, failures: FailureCatalog | None = None) -> None:
        self.failures = failures or FailureCatalog.load()

    def disposition(self, failure_code: str, *, attempt: int, max_attempts: int = 5) -> dict[str, Any]:
        definition = self.failures.resolve(failure_code)
        retry = definition.retryable and attempt < max_attempts
        return {
            "retry": retry,
            "retry_class": definition.retry_class,
            "attempt": attempt,
            "maximum_attempts": max_attempts,
            "backoff_seconds": min(300, 2 ** max(0, attempt - 1)) if retry else None,
            "dead_letter": not retry,
        }

    def dead_letter(self, envelope: EventEnvelopeContract, failure_code: str, *, attempts: int) -> DeadLetterRecord:
        disposition = self.disposition(failure_code, attempt=attempts, max_attempts=attempts)
        return DeadLetterRecord(
            dead_letter_id=new_uuid(),
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            payload_hash=envelope.payload_hash,
            failure_code=failure_code,
            retry_class=disposition["retry_class"],
            attempts=attempts,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def authorize_replay(record: DeadLetterRecord, *, actor_id: str, remediation_evidence_hash: str) -> DeadLetterRecord:
        if not actor_id or len(remediation_evidence_hash) != 64:
            raise AuthorizationError(
                "DEAD_LETTER_REPLAY_DENIED",
                "dead-letter replay requires an authorized actor and remediation evidence hash",
            )
        return record.model_copy(update={"replay_authorized": True})


def _trace_id(traceparent: str | None) -> str | None:
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) == 4 else None
