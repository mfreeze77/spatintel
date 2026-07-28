"""Exact non-authoritative proxy contract and durable representation policy.

Adds an explicit authority ceiling and disposable marker to representation
assets. Existing interaction representations are conservatively reclassified
as derived_non_authoritative and disposable. No migration promotes authority.
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0007_representation_authority_contract"
down_revision = "0006_operation_trace_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    op.add_column(
        "representations",
        sa.Column("authority_ceiling", sa.String(length=64), nullable=False, server_default="none"),
    )
    op.add_column(
        "representations",
        sa.Column("disposable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE representations "
        "SET authority_class = 'derived_non_authoritative', "
        "authority_ceiling = 'derived_non_authoritative', disposable = 1 "
        "WHERE kind = 'interaction'"
    )
    # Legacy proxy asset references used the non-normative value ``interaction``.
    # The migration only lowers their authority; it never promotes an asset.
    op.execute(
        "UPDATE asset_refs SET authority_class = 'derived_non_authoritative' "
        "WHERE authority_class = 'interaction'"
    )
    op.execute(
        "UPDATE representations "
        "SET authority_ceiling = authority_class "
        "WHERE kind <> 'interaction' AND authority_ceiling = 'none'"
    )
    if dialect == "postgresql":
        op.alter_column("representations", "authority_ceiling", server_default=None)
        op.alter_column("representations", "disposable", server_default=None)


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    # Policy columns and conservative authority reclassification are retained
    # in-place. A full rebuild to an earlier release drops the owning table.
