from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, new_uuid
from .database import Database, OperationRow, OutboxEventRow
from .errors import ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import OperationState
from .observability import normalize_traceparent
from .temporal import db_now


class OperationService:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def create(
        self,
        *,
        tenant_id: str,
        project_id: str,
        operation_type: str,
        idempotency_key: str,
        input_manifest: dict[str, Any],
        actor_id: str,
        max_attempts: int = 3,
        traceparent: str | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key:
            raise ValidationError("IDEMPOTENCY_KEY_REQUIRED", "operation requires an idempotency key")
        input_hash = canonical_sha256(input_manifest)
        traceparent = normalize_traceparent(traceparent)
        with self.database.session() as session:
            prior = session.scalar(
                select(OperationRow).where(
                    OperationRow.tenant_id == tenant_id,
                    OperationRow.project_id == project_id,
                    OperationRow.operation_type == operation_type,
                    OperationRow.idempotency_key == idempotency_key,
                )
            )
            if prior:
                if prior.input_manifest_hash != input_hash:
                    raise ConflictError("IDEMPOTENCY_PAYLOAD_CONFLICT", "idempotency key was used with different input")
                return self._as_dict(prior)
            operation_id = new_uuid()
            row = OperationRow(
                operation_id=operation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                operation_type=operation_type,
                idempotency_key=idempotency_key,
                input_manifest_hash=input_hash,
                input_json=input_manifest,
                traceparent=traceparent,
                max_attempts=max_attempts,
                created_by=actor_id,
            )
            session.add(row)
            self._outbox(session, row, "operation.created", {"operation_type": operation_type, "input_manifest_hash": input_hash}, actor_id=actor_id)
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="operation:create",
                resource_type="operation",
                resource_id=operation_id,
                outcome="allowed",
                details={"operation_type": operation_type, "input_manifest_hash": input_hash},
                session=session,
            )
            return self._as_dict(row)

    def lease(self, operation_id: str, *, worker_id: str, lease_seconds: int = 60) -> dict[str, Any]:
        if lease_seconds < 1 or lease_seconds > 3600:
            raise ValidationError("LEASE_TTL_INVALID", "lease duration must be between 1 and 3600 seconds")
        now = db_now()
        with self.database.session() as session:
            row = session.get(OperationRow, operation_id)
            if not row:
                raise NotFoundError("operation", operation_id)
            lease_expired = row.lease_expires_at is not None and _naive(row.lease_expires_at) <= _naive(now)
            if row.state not in {OperationState.PENDING.value, OperationState.LEASED.value, OperationState.RUNNING.value, OperationState.FAILED.value}:
                raise ConflictError("OPERATION_NOT_LEASABLE", "operation is in a terminal or cancelling state", {"state": row.state})
            if row.lease_owner and not lease_expired and row.lease_owner != worker_id:
                raise ConflictError("OPERATION_ALREADY_LEASED", "operation has an active lease")
            if row.attempt >= row.max_attempts and row.state == OperationState.FAILED.value:
                raise ConflictError("OPERATION_ATTEMPTS_EXHAUSTED", "operation exhausted retry attempts")
            if row.state in {OperationState.PENDING.value, OperationState.FAILED.value} or lease_expired:
                row.attempt += 1
            row.state = OperationState.LEASED.value
            row.lease_owner = worker_id
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.updated_at = now
            self._outbox(session, row, "operation.leased", {"worker_id": worker_id, "attempt": row.attempt}, workload_identity=worker_id)
            return self._as_dict(row)

    def start(self, operation_id: str, *, worker_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._owned_lease(session, operation_id, worker_id)
            if row.cancel_requested:
                row.state = OperationState.CANCELLED.value
                row.lease_owner = None
                row.lease_expires_at = None
            else:
                row.state = OperationState.RUNNING.value
            row.updated_at = db_now()
            return self._as_dict(row)

    def heartbeat(self, operation_id: str, *, worker_id: str, lease_seconds: int = 60) -> dict[str, Any]:
        if lease_seconds < 1 or lease_seconds > 3600:
            raise ValidationError("LEASE_TTL_INVALID", "lease duration must be between 1 and 3600 seconds")
        with self.database.session() as session:
            row = self._owned_lease(session, operation_id, worker_id)
            row.lease_expires_at = db_now() + timedelta(seconds=lease_seconds)
            row.updated_at = db_now()
            self._outbox(
                session,
                row,
                "operation.lease_renewed",
                {"worker_id": worker_id, "lease_seconds": lease_seconds},
                workload_identity=worker_id,
            )
            return self._as_dict(row)

    def checkpoint(self, operation_id: str, *, worker_id: str, progress: float, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not 0 <= progress <= 1:
            raise ValidationError("PROGRESS_INVALID", "progress must be in [0, 1]")
        with self.database.session() as session:
            row = self._owned_lease(session, operation_id, worker_id)
            sequence = checkpoint.get("sequence")
            prior_sequence = row.checkpoint_json.get("sequence") if isinstance(row.checkpoint_json, dict) else None
            if sequence is not None:
                if not isinstance(sequence, int) or sequence < 1:
                    raise ValidationError("CHECKPOINT_SEQUENCE_INVALID", "checkpoint sequence must be a positive integer")
                if prior_sequence is not None and sequence <= prior_sequence:
                    raise ConflictError(
                        "CHECKPOINT_SEQUENCE_NOT_MONOTONIC",
                        "checkpoint sequence must advance monotonically",
                        {"prior_sequence": prior_sequence, "sequence": sequence},
                    )
            if progress < row.progress:
                raise ConflictError(
                    "CHECKPOINT_PROGRESS_REGRESSION",
                    "checkpoint progress cannot move backwards",
                    {"prior_progress": row.progress, "progress": progress},
                )
            persisted_checkpoint = dict(checkpoint)
            resume_manifest: dict[str, Any] | None = None
            if bool(persisted_checkpoint.get("safe_to_resume", False)):
                candidate = persisted_checkpoint.get("manifest")
                if candidate is not None and not isinstance(candidate, dict):
                    raise ValidationError("CHECKPOINT_MANIFEST_INVALID", "resumable checkpoint manifest must be an object")
                resume_manifest = dict(candidate) if isinstance(candidate, dict) else {
                    key: value for key, value in persisted_checkpoint.items() if key not in {"manifest", "checkpoint_hash"}
                }
                persisted_checkpoint["manifest"] = resume_manifest
                persisted_checkpoint["checkpoint_hash"] = canonical_sha256(resume_manifest)
            checkpoint_hash = canonical_sha256(persisted_checkpoint)
            if row.cancel_requested:
                row.state = OperationState.CANCELLED.value
                row.lease_owner = None
                row.lease_expires_at = None
            else:
                row.state = OperationState.RUNNING.value
                row.progress = progress
                row.checkpoint_json = persisted_checkpoint
            row.updated_at = db_now()
            self._outbox(
                session,
                row,
                "operation.checkpointed",
                {
                    "progress": progress,
                    "sequence": sequence,
                    "stage": checkpoint.get("stage"),
                    "safe_to_resume": bool(checkpoint.get("safe_to_resume", False)),
                    "checkpoint_hash": checkpoint_hash,
                },
                workload_identity=worker_id,
            )
            return self._as_dict(row)

    def request_cancel(self, operation_id: str, *, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(OperationRow, operation_id)
            if not row:
                raise NotFoundError("operation", operation_id)
            if row.state in {OperationState.SUCCEEDED.value, OperationState.FAILED.value, OperationState.CANCELLED.value}:
                return self._as_dict(row)
            row.cancel_requested = True
            row.state = OperationState.CANCEL_REQUESTED.value
            row.updated_at = db_now()
            self._outbox(session, row, "operation.cancel_requested", {"actor_id": actor_id}, actor_id=actor_id)
            return self._as_dict(row)

    def complete(
        self,
        operation_id: str,
        *,
        worker_id: str,
        output: dict[str, Any],
        claimed_output_hash: str | None = None,
    ) -> dict[str, Any]:
        calculated_output_hash = canonical_sha256(output)
        if claimed_output_hash is not None and claimed_output_hash != calculated_output_hash:
            raise ValidationError(
                "WORKER_OUTPUT_HASH_MISMATCH",
                "worker output hash does not match the submitted manifest",
                {"claimed": claimed_output_hash, "calculated": calculated_output_hash},
            )
        with self.database.session() as session:
            row = self._owned_lease(session, operation_id, worker_id)
            if row.cancel_requested:
                raise ConflictError("OPERATION_CANCEL_REQUESTED", "cancelled operation cannot publish output")
            row.output_json = output
            row.output_hash = calculated_output_hash
            row.progress = 1.0
            row.state = OperationState.SUCCEEDED.value
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = db_now()
            self._outbox(session, row, "operation.succeeded", {"output_hash": row.output_hash}, workload_identity=worker_id)
            return self._as_dict(row)

    def fail(self, operation_id: str, *, worker_id: str, code: str, message: str, retryable: bool) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._owned_lease(session, operation_id, worker_id)
            row.error_json = {"code": code, "message": message, "retryable": retryable}
            row.state = OperationState.FAILED.value
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = db_now()
            self._outbox(session, row, "operation.failed", row.error_json, workload_identity=worker_id)
            return self._as_dict(row)

    def reconcile_expired_leases(self) -> dict[str, list[str]]:
        """Release safely checkpointed leases and quarantine unsafe abandoned work."""
        now = db_now()
        released: list[str] = []
        quarantined: list[str] = []
        with self.database.session() as session:
            rows = session.scalars(
                select(OperationRow).where(
                    OperationRow.state.in_([OperationState.LEASED.value, OperationState.RUNNING.value]),
                    OperationRow.lease_expires_at.is_not(None),
                    OperationRow.lease_expires_at <= now,
                )
            ).all()
            for row in rows:
                checkpoint = row.checkpoint_json if isinstance(row.checkpoint_json, dict) else {}
                safe_to_resume = bool(checkpoint.get("safe_to_resume"))
                row.lease_owner = None
                row.lease_expires_at = None
                row.updated_at = now
                if safe_to_resume and row.attempt < row.max_attempts:
                    row.state = OperationState.PENDING.value
                    released.append(row.operation_id)
                    self._outbox(
                        session,
                        row,
                        "operation.lease_released",
                        {"checkpoint_hash": canonical_sha256(checkpoint), "attempt": row.attempt},
                    )
                else:
                    row.state = OperationState.QUARANTINED.value
                    row.error_json = {
                        "code": "OPERATION_LEASE_EXPIRED_UNSAFE",
                        "message": "expired lease lacked a safe resumable checkpoint",
                        "retryable": False,
                    }
                    quarantined.append(row.operation_id)
                    self._outbox(session, row, "operation.quarantined", row.error_json)
        return {"released": released, "quarantined": quarantined}

    def get(self, operation_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(OperationRow, operation_id)
            if not row:
                raise NotFoundError("operation", operation_id)
            return self._as_dict(row)

    @staticmethod
    def _owned_lease(session: Any, operation_id: str, worker_id: str) -> OperationRow:
        row = session.get(OperationRow, operation_id)
        if not row:
            raise NotFoundError("operation", operation_id)
        if row.lease_owner != worker_id or row.lease_expires_at is None or _naive(row.lease_expires_at) <= _naive(db_now()):
            raise ConflictError("OPERATION_LEASE_INVALID", "worker does not hold a valid lease")
        return row

    @staticmethod
    def _as_dict(row: OperationRow) -> dict[str, Any]:
        return {
            "operation_id": row.operation_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "operation_type": row.operation_type,
            "idempotency_key": row.idempotency_key,
            "input_manifest_hash": row.input_manifest_hash,
            "input_byte_count": len(canonical_json(row.input_json)),
            "input": row.input_json,
            "traceparent": row.traceparent,
            "state": row.state,
            "progress": row.progress,
            "attempt": row.attempt,
            "max_attempts": row.max_attempts,
            "lease_owner": row.lease_owner,
            "lease_expires_at": _utc(row.lease_expires_at),
            "checkpoint": row.checkpoint_json,
            "output": row.output_json,
            "output_hash": row.output_hash,
            "error": row.error_json,
            "cancel_requested": row.cancel_requested,
            "created_at": _utc(row.created_at),
            "updated_at": _utc(row.updated_at),
        }

    @classmethod
    def _outbox(
        cls,
        session: Any,
        row: OperationRow,
        event_type: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None = None,
        workload_identity: str | None = None,
    ) -> None:
        session.add(
            cls._events.create(
                session,
                event_type=event_type,
                schema_version="1.0.0",
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                aggregate_type="operation",
                aggregate_id=row.operation_id,
                payload=payload,
                producer="workflow-service",
                actor_id=actor_id,
                workload_identity=workload_identity,
                traceparent=row.traceparent,
                correlation_id=row.operation_id,
            )
        )



def _naive(value: Any) -> Any:
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _utc(value: Any) -> Any:
    if value is None:
        return None
    return value if getattr(value, "tzinfo", None) else value.replace(tzinfo=UTC)
