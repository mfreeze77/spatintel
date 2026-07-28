"""Durable policy-bound viewer sessions and governed temporal change review.

This migration is append-only. It persists reproducible viewer state without storing
capability tokens, exact temporal-comparison inputs and algorithm lineage, diagnostic
change candidates, independent human reviews, accepted semantic events, and quantitative
change-detection benchmarks. Downgrade is recovery-only because dropping these tables
would destroy audit, review, and scene-history evidence.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0012_scene_runtime_review"
down_revision = "0011_governed_hybrid_representation"
branch_labels = None
depends_on = None

JSON_OBJECT = sa.text("'{}'")
JSON_ARRAY = sa.text("'[]'")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    op.create_table(
        "viewer_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("publication_class", sa.String(length=32), nullable=False, server_default="working"),
        sa.Column("scene_commit_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("saved_hybrid_views_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("device_profile", sa.String(length=128), nullable=False),
        sa.Column("intended_uses_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("spatial_region_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("camera_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("navigation_mode", sa.String(length=32), nullable=False),
        sa.Column("layers_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("clipping_planes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("section_box_json", sa.JSON(), nullable=True),
        sa.Column("selected_entity_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("timeline_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("filters_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("redaction_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("accessibility_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("comparison_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("supersedes_session_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_session_id"], ["viewer_sessions.session_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("session_hash"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "principal_id", "idempotency_key",
            name="uq_viewer_session_idempotency",
        ),
    )
    _indexes(
        "viewer_sessions",
        {
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "scene_id": ["scene_id"],
            "principal_id": ["principal_id"],
            "purpose": ["purpose"],
            "audience": ["audience"],
            "publication_class": ["publication_class"],
            "policy_snapshot_hash": ["policy_snapshot_hash"],
            "request_hash": ["request_hash"],
            "supersedes_session_id": ["supersedes_session_id"],
        },
    )

    op.create_table(
        "viewer_session_replays",
        sa.Column("replay_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("issued_views_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("exact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("degraded_reasons_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("replay_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["viewer_sessions.session_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("replay_id"),
        sa.UniqueConstraint("replay_hash"),
    )
    _indexes(
        "viewer_session_replays",
        {
            "session_id": ["session_id"],
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "principal_id": ["principal_id"],
        },
    )

    op.create_table(
        "temporal_comparisons",
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("baseline_commit_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_commit_id", sa.String(length=64), nullable=False),
        sa.Column("viewer_session_id", sa.String(length=64), nullable=True),
        sa.Column("comparable_region_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("registration_quality_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("thresholds_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("algorithm_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("executable_hash", sa.String(length=64), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_coverage_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("comparison_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["baseline_commit_id"], ["scene_commits.commit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_commit_id"], ["scene_commits.commit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["viewer_session_id"], ["viewer_sessions.session_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("comparison_id"),
        sa.UniqueConstraint("comparison_hash"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "idempotency_key",
            name="uq_temporal_comparison_idempotency",
        ),
    )
    _indexes(
        "temporal_comparisons",
        {
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "scene_id": ["scene_id"],
            "baseline_commit_id": ["baseline_commit_id"],
            "candidate_commit_id": ["candidate_commit_id"],
            "viewer_session_id": ["viewer_session_id"],
            "algorithm_id": ["algorithm_id"],
            "state": ["state"],
            "request_hash": ["request_hash"],
        },
    )

    op.create_table(
        "change_candidates",
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("change_class", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("region_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("coverage_status", sa.String(length=32), nullable=False),
        sa.Column("difference_causes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("suppression_reason", sa.String(length=256), nullable=True),
        sa.Column("candidate_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["temporal_comparisons.comparison_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("candidate_id"),
        sa.UniqueConstraint("candidate_hash"),
    )
    _indexes(
        "change_candidates",
        {
            "comparison_id": ["comparison_id"],
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "scene_id": ["scene_id"],
            "change_class": ["change_class"],
            "entity_id": ["entity_id"],
            "state": ["state"],
        },
    )

    op.create_table(
        "change_reviews",
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("review_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["temporal_comparisons.comparison_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["change_candidates.candidate_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("review_hash"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "reviewer_id", "idempotency_key",
            name="uq_change_review_idempotency",
        ),
    )
    _indexes(
        "change_reviews",
        {
            "comparison_id": ["comparison_id"],
            "candidate_id": ["candidate_id"],
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "reviewer_id": ["reviewer_id"],
            "outcome": ["outcome"],
            "request_hash": ["request_hash"],
        },
    )

    op.create_table(
        "semantic_change_events",
        sa.Column("semantic_event_id", sa.String(length=64), nullable=False),
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("source_commit_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("applied_commit_id", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["temporal_comparisons.comparison_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["change_candidates.candidate_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_id"], ["change_reviews.review_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["applied_commit_id"], ["scene_commits.commit_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("semantic_event_id"),
        sa.UniqueConstraint("event_hash"),
    )
    _indexes(
        "semantic_change_events",
        {
            "comparison_id": ["comparison_id"],
            "candidate_id": ["candidate_id"],
            "review_id": ["review_id"],
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "scene_id": ["scene_id"],
            "event_type": ["event_type"],
            "entity_id": ["entity_id"],
            "applied_commit_id": ["applied_commit_id"],
        },
    )

    op.create_table(
        "change_benchmarks",
        sa.Column("benchmark_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("algorithm_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("executable_hash", sa.String(length=64), nullable=False),
        sa.Column("benchmark_profile", sa.String(length=128), nullable=False),
        sa.Column("fixture_root_hash", sa.String(length=64), nullable=False),
        sa.Column("metrics_by_class_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("environment_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("benchmark_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("benchmark_id"),
        sa.UniqueConstraint("benchmark_hash"),
    )
    _indexes(
        "change_benchmarks",
        {
            "tenant_id": ["tenant_id"],
            "project_id": ["project_id"],
            "algorithm_id": ["algorithm_id"],
        },
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

    for table in (
        "change_benchmarks",
        "semantic_change_events",
        "change_reviews",
        "change_candidates",
        "temporal_comparisons",
        "viewer_session_replays",
        "viewer_sessions",
    ):
        op.drop_table(table)


def _indexes(table: str, definitions: dict[str, list[str]]) -> None:
    for suffix, columns in definitions.items():
        op.create_index(f"ix_{table}_{suffix}", table, columns)
