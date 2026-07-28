from __future__ import annotations

import base64
import hmac
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .canonical import canonical_sha256, new_uuid
from .database import AuditEventRow, Database
from .errors import ValidationError
from .temporal import db_now


class AuditService:
    def __init__(self, database: Database, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("audit signing key must be at least 32 bytes")
        self.database = database
        self.signing_key = signing_key

    def append(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: str,
        details: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> str:
        owns_session = session is None
        if session is None:
            session = self.database.session_factory()
        try:
            previous = session.scalar(
                select(AuditEventRow)
                .where(AuditEventRow.tenant_id == tenant_id)
                .order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.audit_id.desc())
                .limit(1)
            )
            audit_id = new_uuid()
            occurred_at = db_now()
            previous_hash = previous.event_hash if previous else "0" * 64
            body = {
                "audit_id": audit_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
                "details": details or {},
                "occurred_at": _timestamp(occurred_at),
                "previous_hash": previous_hash,
            }
            event_hash = canonical_sha256(body)
            signature = base64.b64encode(hmac.new(self.signing_key, event_hash.encode(), sha256).digest()).decode()
            session.add(
                AuditEventRow(
                    audit_id=audit_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome=outcome,
                    details_json=details or {},
                    occurred_at=occurred_at,
                    previous_hash=previous_hash,
                    event_hash=event_hash,
                    signature=signature,
                )
            )
            if owns_session:
                session.commit()
            return audit_id
        except Exception:
            if owns_session:
                session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    def verify(self, tenant_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            rows = list(
                session.scalars(
                    select(AuditEventRow)
                    .where(AuditEventRow.tenant_id == tenant_id)
                    .order_by(AuditEventRow.occurred_at, AuditEventRow.audit_id)
                )
            )
        previous_hash = "0" * 64
        for index, row in enumerate(rows):
            body = {
                "audit_id": row.audit_id,
                "tenant_id": row.tenant_id,
                "project_id": row.project_id,
                "actor_id": row.actor_id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "outcome": row.outcome,
                "details": row.details_json,
                "occurred_at": _timestamp(row.occurred_at),
                "previous_hash": previous_hash,
            }
            expected_hash = canonical_sha256(body)
            expected_signature = hmac.new(self.signing_key, expected_hash.encode(), sha256).digest()
            try:
                actual_signature = base64.b64decode(row.signature)
            except Exception as exc:
                raise ValidationError("AUDIT_SIGNATURE_MALFORMED", "audit signature is not valid base64", {"index": index}) from exc
            if row.previous_hash != previous_hash or row.event_hash != expected_hash or not hmac.compare_digest(actual_signature, expected_signature):
                raise ValidationError(
                    "AUDIT_CHAIN_INVALID",
                    "audit chain verification failed",
                    {"index": index, "audit_id": row.audit_id},
                )
            previous_hash = row.event_hash
        return {"tenant_id": tenant_id, "events": len(rows), "valid": True, "head_hash": previous_hash}


def _timestamp(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()
