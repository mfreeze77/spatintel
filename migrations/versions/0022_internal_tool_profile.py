"""Adopt the local-internal model execution profile."""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0022_internal_tool_profile"
down_revision = "0021_progress11_release_assurance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_manifests") as batch_op:
        batch_op.add_column(
            sa.Column("usage_scope", sa.String(length=32), nullable=False, server_default="local_internal")
        )
        batch_op.drop_column("commercial_use")
    with op.batch_alter_table("model_manifests") as batch_op:
        batch_op.alter_column("usage_scope", server_default=None)


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; set SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 only in an isolated recovery rehearsal"
        )
    required = {
        "SIP_VERIFIED_BACKUP_REFERENCE": os.environ.get("SIP_VERIFIED_BACKUP_REFERENCE", ""),
        "SIP_DOWNGRADE_DRY_RUN_REFERENCE": os.environ.get("SIP_DOWNGRADE_DRY_RUN_REFERENCE", ""),
        "SIP_DOWNGRADE_AUDIT_REFERENCE": os.environ.get("SIP_DOWNGRADE_AUDIT_REFERENCE", ""),
    }
    invalid = [
        name
        for name, value in required.items()
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
    ]
    rehearsal = os.environ.get("SIP_DOWNGRADE_REHEARSAL_ID", "")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", rehearsal) is None:
        invalid.append("SIP_DOWNGRADE_REHEARSAL_ID")
    if invalid:
        raise RuntimeError(
            "destructive downgrade denied; verified backup, dry-run, audit, and rehearsal evidence are required: "
            + ", ".join(invalid)
        )
    with op.batch_alter_table("model_manifests", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("commercial_use", sa.Boolean(), nullable=False, server_default=sa.false()),
            insert_after="approval_state",
        )
        batch_op.drop_column("usage_scope")
    with op.batch_alter_table("model_manifests") as batch_op:
        batch_op.alter_column("commercial_use", server_default=None)
