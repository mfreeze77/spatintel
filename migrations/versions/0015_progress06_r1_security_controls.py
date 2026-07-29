"""Progress 06-R1 restricted-export approval controls.

This append-only migration adds immutable, tenant/project-scoped approvals for
restricted Construction owner handoffs. Routine project administration cannot
create these records; admission is enforced by the exact
``construction:restricted_export`` policy action.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0015_progress06_r1_security_controls"
down_revision = "0014_vertical_mvp"
branch_labels = None
depends_on = None

_TABLE = "construction_restricted_export_approvals"
_UNIQUE = "uq_construction_restricted_export_approval"


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")
    op.create_table(
        _TABLE,
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("approver_id", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("approval_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "request_hash",
            "approver_id",
            name=_UNIQUE,
        ),
    )
    for column in (
        "tenant_id",
        "project_id",
        "request_hash",
        "classification",
        "audience",
        "purpose",
        "approver_id",
        "expires_at",
    ):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column], unique=False)


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; an isolated recovery rehearsal must explicitly set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1"
        )
    evidence_variables = {
        "SIP_VERIFIED_BACKUP_REFERENCE": os.environ.get("SIP_VERIFIED_BACKUP_REFERENCE", ""),
        "SIP_DOWNGRADE_DRY_RUN_REFERENCE": os.environ.get("SIP_DOWNGRADE_DRY_RUN_REFERENCE", ""),
        "SIP_DOWNGRADE_AUDIT_REFERENCE": os.environ.get("SIP_DOWNGRADE_AUDIT_REFERENCE", ""),
    }
    invalid_evidence = [
        name
        for name, value in evidence_variables.items()
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
    ]
    rehearsal_id = os.environ.get("SIP_DOWNGRADE_REHEARSAL_ID", "")
    rehearsal_valid = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", rehearsal_id) is not None
    if invalid_evidence or not rehearsal_valid:
        invalid = invalid_evidence + ([] if rehearsal_valid else ["SIP_DOWNGRADE_REHEARSAL_ID"])
        raise RuntimeError(
            "destructive downgrade denied; verified backup, dry-run, immutable audit references, "
            f"and a rehearsal identifier are mandatory (invalid or missing: {', '.join(invalid)})"
        )
    op.drop_table(_TABLE)
