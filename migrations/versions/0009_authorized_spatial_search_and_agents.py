"""Authorized spatial search, semantic provenance, and immutable saved queries.

This migration is additive. Derived search rows remain archived evidence during
preservation restore, and saved-query permission records require explicit review
before reuse in another deployment.
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0009_authorized_spatial_search_and_agents"
down_revision = "0008_complete_event_envelope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    additions = [
        sa.Column("entity_type", sa.String(length=128), nullable=True),
        sa.Column("embedding_model_manifest_id", sa.String(length=128), nullable=True),
        sa.Column("embedding_source_region_json", sa.JSON(), nullable=True),
        sa.Column("spatial_frame_id", sa.String(length=64), nullable=True),
        sa.Column("floor_id", sa.String(length=64), nullable=True),
        sa.Column("room_id", sa.String(length=64), nullable=True),
        sa.Column("source_class", sa.String(length=64), nullable=False, server_default="observed"),
        sa.Column("authority_class", sa.String(length=64), nullable=False, server_default="evidence"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("workflow_status", sa.String(length=128), nullable=True),
        sa.Column("relationships_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("classification", sa.String(length=64), nullable=False, server_default="internal"),
        sa.Column("source_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("index_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("scene_commit_id", sa.String(length=64), nullable=True),
    ]
    for column in additions:
        op.add_column("search_documents", column)

    for name, columns in [
        ("ix_search_documents_entity_type", ["entity_type"]),
        ("ix_search_documents_embedding_model_manifest_id", ["embedding_model_manifest_id"]),
        ("ix_search_documents_spatial_frame_id", ["spatial_frame_id"]),
        ("ix_search_documents_floor_id", ["floor_id"]),
        ("ix_search_documents_room_id", ["room_id"]),
        ("ix_search_documents_source_class", ["source_class"]),
        ("ix_search_documents_authority_class", ["authority_class"]),
        ("ix_search_documents_workflow_status", ["workflow_status"]),
        ("ix_search_documents_classification", ["classification"]),
        ("ix_search_documents_scene_commit_id", ["scene_commit_id"]),
    ]:
        op.create_index(name, "search_documents", columns)

    op.create_table(
        "saved_queries",
        sa.Column("saved_query_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("author_id", sa.String(length=128), nullable=False),
        sa.Column("query_json", sa.JSON(), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("expected_result_contract_json", sa.JSON(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("supersedes_saved_query_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("saved_query_id"),
        sa.UniqueConstraint("tenant_id", "project_id", "name", "version", name="uq_saved_query_version"),
    )
    op.create_index("ix_saved_queries_tenant_id", "saved_queries", ["tenant_id"])
    op.create_index("ix_saved_queries_project_id", "saved_queries", ["project_id"])
    op.create_index("ix_saved_queries_author_id", "saved_queries", ["author_id"])
    op.create_index("ix_saved_queries_query_hash", "saved_queries", ["query_hash"])
    op.create_index("ix_saved_queries_supersedes_saved_query_id", "saved_queries", ["supersedes_saved_query_id"])

    op.create_table(
        "agent_proposals",
        sa.Column("proposal_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("proposal_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="review_required"),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("proposal_id"),
        sa.UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_agent_proposal_idempotency"),
    )
    op.create_index("ix_agent_proposals_tenant_id", "agent_proposals", ["tenant_id"])
    op.create_index("ix_agent_proposals_project_id", "agent_proposals", ["project_id"])
    op.create_index("ix_agent_proposals_state", "agent_proposals", ["state"])
    op.create_index("ix_agent_proposals_created_by", "agent_proposals", ["created_by"])

    if dialect == "postgresql":
        for name in [
            "source_class",
            "authority_class",
            "confidence",
            "tags_json",
            "relationships_json",
            "evidence_ids_json",
            "classification",
            "source_sequence",
            "index_sequence",
            "indexed_at",
        ]:
            op.alter_column("search_documents", name, server_default=None)
        op.alter_column("saved_queries", "version", server_default=None)
        op.alter_column("agent_proposals", "state", server_default=None)


def downgrade() -> None:
    if os.environ.get("SIP_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "destructive downgrade denied; restore a verified backup or set "
            "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE=1 in an isolated rehearsal"
        )
    # Search evidence and saved-query permission records are intentionally retained.
    # A full isolated rebuild to an earlier release removes their owning tables.
