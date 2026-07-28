"""Durable W3C trace context for operation-to-worker correlation.

The nullable traceparent is correlation metadata only. It is never consulted for
identity, authorization, tenancy, consent, or provider admission decisions.
"""
from __future__ import annotations

import os

from alembic import op

revision = "0006_operation_trace_context"
down_revision = "0005_worker_candidate_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")
    op.execute("ALTER TABLE operations ADD COLUMN traceparent VARCHAR(128)")


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    # The nullable correlation column is intentionally retained in-place. A full
    # rebuild/downgrade drops the owning operations table in migration 0001.
