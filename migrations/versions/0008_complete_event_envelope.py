"""Complete event envelope for producer, classification, trace, and replay context.

The additive columns make the transactional outbox conform to the versioned event
contract. Legacy rows retain conservative defaults and are never promoted to a
more permissive classification.
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0008_complete_event_envelope"
down_revision = "0007_representation_authority_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")
    op.add_column("outbox_events", sa.Column("producer", sa.String(length=128), nullable=False, server_default="unknown-legacy"))
    op.add_column("outbox_events", sa.Column("classification", sa.String(length=64), nullable=False, server_default="internal"))
    op.add_column("outbox_events", sa.Column("actor_id", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("workload_identity", sa.String(length=256), nullable=True))
    op.add_column("outbox_events", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column("outbox_events", sa.Column("correlation_id", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("causation_id", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_outbox_events_trace_id", "outbox_events", ["trace_id"])
    op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"])
    if dialect == "postgresql":
        op.alter_column("outbox_events", "producer", server_default=None)
        op.alter_column("outbox_events", "classification", server_default=None)
        op.alter_column("outbox_events", "recorded_at", server_default=None)


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    # Envelope metadata is intentionally retained. A full isolated rebuild to an
    # earlier release drops the owning outbox table in migration 0001.
