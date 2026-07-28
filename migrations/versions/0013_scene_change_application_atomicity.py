"""Atomic and idempotent semantic-change application.

This append-only migration adds a project-scoped uniqueness guard for scene-commit
workflow event IDs. It prevents concurrent or retried temporal-comparison application
from producing more than one scene commit. The application transaction also updates the
branch head, semantic event links, outbox, and audit chain as one unit.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0013_scene_change_application_atomicity"
down_revision = "0012_scene_runtime_review"
branch_labels = None
depends_on = None

_INDEX = "uq_scene_commit_workflow_event"


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")
    duplicate = op.get_bind().execute(
        sa.text(
            """
            SELECT tenant_id, project_id, workflow_event_id, COUNT(*) AS duplicate_count
            FROM scene_commits
            WHERE workflow_event_id IS NOT NULL
            GROUP BY tenant_id, project_id, workflow_event_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "scene commit workflow-event uniqueness migration blocked by duplicate retained records"
        )
    op.create_index(
        _INDEX,
        "scene_commits",
        ["tenant_id", "project_id", "workflow_event_id"],
        unique=True,
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
    op.drop_index(_INDEX, table_name="scene_commits")
