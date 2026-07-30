"""Progress 06-R2 governed truth promotion and restricted-data controls.

This append-only revision adds durable Construction record-verification and
LiveForever record-review receipts. Raw secrets remain prohibited at the
application boundary and therefore are deliberately not assigned ordinary
schema columns.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0016_progress06_r2_truth_and_restricted_data"
down_revision = "0015_progress06_r1_security_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    op.create_table(
        "construction_record_verifications",
        sa.Column("verification_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("verifier_id", sa.String(length=128), nullable=False),
        sa.Column("prior_state", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=128), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("exclusions_json", sa.JSON(), nullable=False),
        sa.Column("evidence_asset_ids_json", sa.JSON(), nullable=False),
        sa.Column("signature_asset_id", sa.String(length=64), nullable=True),
        sa.Column("verification_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("verification_id"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "idempotency_key",
            name="uq_construction_record_verification_idempotency",
        ),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "record_id",
            name="uq_construction_record_verification_record",
        ),
    )
    for column in (
        "tenant_id", "project_id", "record_id", "verifier_id", "signature_asset_id"
    ):
        op.create_index(
            f"ix_construction_record_verifications_{column}",
            "construction_record_verifications",
            [column],
            unique=False,
        )

    op.create_table(
        "liveforever_record_reviews",
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=64), nullable=False),
        sa.Column("reviewed_record_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("target_source_class", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_asset_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "idempotency_key",
            name="uq_liveforever_record_review_idempotency",
        ),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "reviewed_record_id",
            name="uq_liveforever_record_review_result",
        ),
    )
    for column in (
        "tenant_id", "project_id", "source_record_id", "reviewed_record_id",
        "reviewer_id", "target_source_class",
    ):
        op.create_index(
            f"ix_liveforever_record_reviews_{column}",
            "liveforever_record_reviews",
            [column],
            unique=False,
        )


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
        name for name, value in evidence_variables.items()
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
    op.drop_table("liveforever_record_reviews")
    op.drop_table("construction_record_verifications")
