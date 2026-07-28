"""Worker candidate idempotency and operation provenance.

Adds a nullable operation identifier to representation candidates and a scoped
unique index. Existing candidates remain valid; new durable worker retries can
resolve the same quarantined candidate rather than creating duplicates.
"""
from __future__ import annotations

import os

from alembic import op

revision = "0005_worker_candidate_idempotency"
down_revision = "0004_lifecycle_recovery_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")
    op.execute("ALTER TABLE representations ADD COLUMN operation_id VARCHAR(64)")
    op.execute("CREATE INDEX ix_representations_operation_id ON representations (operation_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_representation_operation "
        "ON representations (tenant_id, project_id, operation_id) "
        "WHERE operation_id IS NOT NULL"
    )


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    op.execute("DROP INDEX IF EXISTS uq_representation_operation")
    op.execute("DROP INDEX IF EXISTS ix_representations_operation_id")
    # The nullable column is intentionally retained during an in-place rehearsal.
    # A full downgrade continues to drop the owning representations table in 0002.
