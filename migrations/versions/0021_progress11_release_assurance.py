"""Progress 11 dual-vertical acceptance and release assurance controls."""
from __future__ import annotations

import os
import re

from alembic import op
import sqlalchemy as sa

revision = "0021_progress11_release_assurance"
down_revision = "0020_progress10_recovery_retention"
branch_labels = None
depends_on = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "qa_acceptance_campaigns",
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("release_class", sa.String(length=32), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("test_data_json", sa.JSON(), nullable=False),
        sa.Column("operating_envelope_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("support_plan_json", sa.JSON(), nullable=False),
        sa.Column("recovery_plan_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("campaign_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("campaign_id"),
        sa.UniqueConstraint("campaign_hash"),
        sa.UniqueConstraint("tenant_id", "checkpoint_id", name="uq_qa_campaign_checkpoint"),
    )
    _indexes("qa_acceptance_campaigns", ("tenant_id", "project_id", "checkpoint_id", "release_class", "state"))

    op.create_table(
        "qa_scenario_results",
        sa.Column("scenario_result_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("scenario_type", sa.String(length=64), nullable=False),
        sa.Column("profile", sa.String(length=128), nullable=False),
        sa.Column("evidence_class", sa.String(length=64), nullable=False),
        sa.Column("input_hashes_json", sa.JSON(), nullable=False),
        sa.Column("output_hashes_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("assertions_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("environment_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scenario_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qa_acceptance_campaigns.campaign_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("scenario_result_id"),
        sa.UniqueConstraint("scenario_hash"),
        sa.UniqueConstraint("campaign_id", "scenario_type", "profile", name="uq_qa_scenario_profile"),
    )
    _indexes("qa_scenario_results", ("campaign_id", "tenant_id", "project_id", "scenario_type", "profile", "evidence_class", "status"))

    op.create_table(
        "qa_gate_results",
        sa.Column("gate_result_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("gate_type", sa.String(length=64), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("execution_status", sa.String(length=64), nullable=False),
        sa.Column("control_status", sa.String(length=64), nullable=False),
        sa.Column("thresholds_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("external_gap", sa.Boolean(), nullable=False),
        sa.Column("gate_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qa_acceptance_campaigns.campaign_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("gate_result_id"),
        sa.UniqueConstraint("gate_hash"),
        sa.UniqueConstraint("campaign_id", "gate_type", name="uq_qa_gate_type"),
    )
    _indexes("qa_gate_results", ("campaign_id", "tenant_id", "gate_type", "execution_status", "control_status", "external_gap"))

    op.create_table(
        "qa_release_waivers",
        sa.Column("waiver_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("requirement_id", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("compensating_control_json", sa.JSON(), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("waiver_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qa_acceptance_campaigns.campaign_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("waiver_id"),
        sa.UniqueConstraint("waiver_hash"),
        sa.UniqueConstraint("campaign_id", "requirement_id", name="uq_qa_waiver_requirement"),
    )
    _indexes("qa_release_waivers", ("campaign_id", "tenant_id", "requirement_id", "priority", "expires_at", "state"))

    op.create_table(
        "qa_rollback_rehearsals",
        sa.Column("rehearsal_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("from_release", sa.String(length=128), nullable=False),
        sa.Column("to_release", sa.String(length=128), nullable=False),
        sa.Column("recovery_point_id", sa.String(length=64), nullable=True),
        sa.Column("before_hashes_json", sa.JSON(), nullable=False),
        sa.Column("after_hashes_json", sa.JSON(), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("verification_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rehearsal_hash", sa.String(length=64), nullable=False),
        sa.Column("rehearsed_by", sa.String(length=128), nullable=False),
        sa.Column("rehearsed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qa_acceptance_campaigns.campaign_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("rehearsal_id"),
        sa.UniqueConstraint("rehearsal_hash"),
        sa.UniqueConstraint("campaign_id", "from_release", "to_release", name="uq_qa_rollback_path"),
    )
    _indexes("qa_rollback_rehearsals", ("campaign_id", "tenant_id", "recovery_point_id", "status"))

    op.create_table(
        "qa_release_candidates",
        sa.Column("release_candidate_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("source_root_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("signer_key_id", sa.String(length=128), nullable=False),
        sa.Column("blockers_json", sa.JSON(), nullable=False),
        sa.Column("external_gaps_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("production_authorized", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qa_acceptance_campaigns.campaign_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("release_candidate_id"),
        sa.UniqueConstraint("manifest_hash"),
        sa.UniqueConstraint("campaign_id", "source_commit", "source_root_sha256", name="uq_qa_candidate_source"),
    )
    _indexes("qa_release_candidates", ("campaign_id", "tenant_id", "source_commit", "source_root_sha256", "status", "production_authorized"))


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
    for table in (
        "qa_release_candidates",
        "qa_rollback_rehearsals",
        "qa_release_waivers",
        "qa_gate_results",
        "qa_scenario_results",
        "qa_acceptance_campaigns",
    ):
        op.drop_table(table)
