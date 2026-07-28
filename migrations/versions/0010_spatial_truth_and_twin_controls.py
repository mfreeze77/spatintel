"""Canonical spatial truth, evidence, annotation, and hybrid binding controls.

This migration is additive and preserves prior scene, representation, and measurement
identifiers. Downgrade is recovery-only because removing evidence and transform lineage
would be destructive.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0010_spatial_truth_and_twin_controls"
down_revision = "0009_authorized_spatial_search_and_agents"
branch_labels = None
depends_on = None


JSON_OBJECT = sa.text("'{}'")
JSON_ARRAY = sa.text("'[]'")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    for column in [
        sa.Column("semantic_type", sa.String(length=128), nullable=False, server_default="local_cartesian"),
        sa.Column("original_units", sa.String(length=64), nullable=False, server_default="meter"),
        sa.Column("unit_scale_to_meters", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("original_unit_scale_to_meters", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("axis_convention", sa.String(length=128), nullable=False, server_default="right_handed_y_up"),
        sa.Column("axis_directions_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("handedness", sa.String(length=16), nullable=False, server_default="right"),
        sa.Column("origin_description", sa.Text(), nullable=False, server_default="capture_session_origin"),
        sa.Column("gravity_alignment", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="platform"),
        sa.Column("crs_identifier", sa.String(length=256), nullable=True),
        sa.Column("vertical_datum", sa.String(length=256), nullable=True),
        sa.Column("geodetic_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("supersedes_frame_id", sa.String(length=64), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        op.add_column("coordinate_frames", column)
    op.create_index("ix_coordinate_frames_supersedes_frame_id", "coordinate_frames", ["supersedes_frame_id"])
    op.create_index("ix_coordinate_frames_crs_identifier", "coordinate_frames", ["crs_identifier"])

    for column in [
        sa.Column("root_manifest_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("field_visit_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_event_id", sa.String(length=128), nullable=True),
        sa.Column("change_evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("policy_checks_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("signatures_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("review_state", sa.String(length=32), nullable=False, server_default="unreviewed"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]:
        op.add_column("scene_commits", column)
    for name, columns in [
        ("ix_scene_commits_field_visit_id", ["field_visit_id"]),
        ("ix_scene_commits_workflow_event_id", ["workflow_event_id"]),
        ("ix_scene_commits_review_state", ["review_state"]),
        ("ix_scene_commits_valid_from", ["valid_from"]),
        ("ix_scene_commits_valid_to", ["valid_to"]),
        ("ix_scene_commits_recorded_at", ["recorded_at"]),
    ]:
        op.create_index(name, "scene_commits", columns)

    for column in [
        sa.Column("format_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("derivation_policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("limitations_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("information_loss_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("privacy_inheritance_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("dependencies_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("fallback_representation_id", sa.String(length=64), nullable=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        op.add_column("representations", column)
    op.create_index("ix_representations_fallback_representation_id", "representations", ["fallback_representation_id"])
    op.create_index("ix_representations_manifest_hash", "representations", ["manifest_hash"])

    for column in [
        sa.Column("coordinate_frame_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "transform_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]]'"),
        ),
        sa.Column("authority_class", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column("authority_ceiling", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column("intended_uses_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("review_decision_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("audience_policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("client_profile_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
    ]:
        op.add_column("representation_bindings", column)

    for column in [
        sa.Column("measurement_type", sa.String(length=64), nullable=False, server_default="distance"),
        sa.Column("geometry_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("source_method", sa.String(length=128), nullable=False, server_default="unspecified"),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coordinate_frame_id", sa.String(length=64), nullable=True),
        sa.Column("source_commit_id", sa.String(length=64), nullable=True),
        sa.Column("permitted_uses_json", sa.JSON(), nullable=False, server_default=sa.text("'[\"reference\"]'")),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="measured"),
        sa.Column("supersedes_measurement_id", sa.String(length=64), nullable=True),
        sa.Column("originating_representation_id", sa.String(length=64), nullable=True),
        sa.Column("interaction_hit_json", sa.JSON(), nullable=True),
        sa.Column("resolved_metric_evidence_json", sa.JSON(), nullable=True),
    ]:
        op.add_column("measurements", column)
    for name, columns in [
        ("ix_measurements_measured_at", ["measured_at"]),
        ("ix_measurements_coordinate_frame_id", ["coordinate_frame_id"]),
        ("ix_measurements_source_commit_id", ["source_commit_id"]),
        ("ix_measurements_state", ["state"]),
        ("ix_measurements_supersedes_measurement_id", ["supersedes_measurement_id"]),
        ("ix_measurements_originating_representation_id", ["originating_representation_id"]),
    ]:
        op.create_index(name, "measurements", columns)

    op.create_table(
        "spatial_transforms",
        sa.Column("transform_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("source_frame_id", sa.String(length=64), nullable=False),
        sa.Column("target_frame_id", sa.String(length=64), nullable=False),
        sa.Column("transform_type", sa.String(length=16), nullable=False),
        sa.Column("matrix_json", sa.JSON(), nullable=False),
        sa.Column("declared_matrix_json", sa.JSON(), nullable=False),
        sa.Column("matrix_layout", sa.String(length=32), nullable=False, server_default="row_major"),
        sa.Column("multiplication_convention", sa.String(length=64), nullable=False, server_default="column_vector_pre_multiply"),
        sa.Column("direction", sa.String(length=32), nullable=False, server_default="source_to_target"),
        sa.Column("translation_units", sa.String(length=32), nullable=False, server_default="meter"),
        sa.Column("scale", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("covariance_json", sa.JSON(), nullable=True),
        sa.Column("residual_summary_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("uncertainty_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("authority_class", sa.String(length=64), nullable=False),
        sa.Column("calibration_id", sa.String(length=128), nullable=True),
        sa.Column("solver_run_id", sa.String(length=128), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("crs_pipeline", sa.Text(), nullable=True),
        sa.Column("grid_resources_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("supersedes_transform_id", sa.String(length=64), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("transform_id"),
    )
    _indexes("spatial_transforms", ["tenant_id", "project_id", "source_frame_id", "target_frame_id", "calibration_id", "solver_run_id", "valid_from", "valid_to", "observed_at", "supersedes_transform_id"])

    op.create_table(
        "geometry_asset_manifests",
        sa.Column("geometry_manifest_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("representation_id", sa.String(length=64), nullable=True),
        sa.Column("media_type", sa.String(length=256), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=False),
        sa.Column("profile", sa.String(length=128), nullable=False),
        sa.Column("format_version", sa.String(length=64), nullable=False),
        sa.Column("coordinate_frame_id", sa.String(length=64), nullable=False),
        sa.Column("units", sa.String(length=32), nullable=False),
        sa.Column("bounds_json", sa.JSON(), nullable=False),
        sa.Column("counts_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("compression_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.String(length=128), nullable=False),
        sa.Column("quality_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("limitations_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("visual_content_classes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("audience_policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("viewer_compatibility_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("exporter_compatibility_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("validation_state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("rebuild_recipe_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("truth_label", sa.Text(), nullable=True),
        sa.Column("supersedes_manifest_id", sa.String(length=64), nullable=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("geometry_manifest_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "manifest_hash",
            name="uq_geometry_asset_manifest_scope_hash",
        ),
    )
    _indexes("geometry_asset_manifests", ["tenant_id", "project_id", "asset_id", "representation_id", "coordinate_frame_id", "content_sha256", "source_run_id", "classification", "validation_state", "supersedes_manifest_id"])

    op.create_table(
        "evidence_records",
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_by", sa.String(length=128), nullable=False),
        sa.Column("device_or_tool", sa.String(length=256), nullable=False),
        sa.Column("location_context_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("relevant_region_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("relevant_time_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relevant_time_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("chain_of_custody_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_scope_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("access_policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    _indexes("evidence_records", ["tenant_id", "project_id", "asset_id", "source_type", "collected_at", "relevant_time_start", "relevant_time_end", "content_sha256"])

    op.create_table(
        "assertions",
        sa.Column("assertion_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("predicate", sa.String(length=256), nullable=False),
        sa.Column("object_json", sa.JSON(), nullable=False),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("authority_class", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_id", sa.String(length=128), nullable=True),
        sa.Column("producer_id", sa.String(length=256), nullable=True),
        sa.Column("conflicts_with_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("supersedes_assertion_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("assertion_id"),
    )
    _indexes("assertions", ["tenant_id", "project_id", "subject_id", "predicate", "source_class", "authority_class", "asserted_at", "valid_from", "valid_to", "author_id", "producer_id", "supersedes_assertion_id", "state"])

    op.create_table(
        "derivation_events",
        sa.Column("derivation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("activity_type", sa.String(length=128), nullable=False),
        sa.Column("input_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("input_hashes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("algorithm_id", sa.String(length=256), nullable=False),
        sa.Column("algorithm_version", sa.String(length=128), nullable=False),
        sa.Column("model_manifest_id", sa.String(length=128), nullable=True),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("environment_hash", sa.String(length=64), nullable=False),
        sa.Column("code_commit", sa.String(length=128), nullable=False),
        sa.Column("container_digest", sa.String(length=128), nullable=True),
        sa.Column("output_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("output_hashes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("software_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("quality_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("validation_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("workload_identity", sa.String(length=256), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("derivation_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("derivation_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "request_hash",
            name="uq_derivation_event_scope_request",
        ),
        sa.UniqueConstraint("derivation_hash", name="uq_derivation_event_hash"),
    )
    _indexes("derivation_events", ["tenant_id", "project_id", "activity_type", "algorithm_id", "model_manifest_id", "request_hash"])

    op.create_table(
        "spatial_annotations",
        sa.Column("annotation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("coordinate_frame_id", sa.String(length=64), nullable=False),
        sa.Column("support_type", sa.String(length=64), nullable=False),
        sa.Column("support_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("position_json", sa.JSON(), nullable=True),
        sa.Column("orientation_json", sa.JSON(), nullable=True),
        sa.Column("normal_json", sa.JSON(), nullable=True),
        sa.Column("uncertainty_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("authority_class", sa.String(length=64), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("authored_from_representation_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("annotation_id"),
    )
    _indexes("spatial_annotations", ["tenant_id", "project_id", "scene_id", "entity_id", "coordinate_frame_id", "lifecycle_state", "authored_from_representation_id"])

    op.create_table(
        "anchor_remaps",
        sa.Column("remap_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("source_representation_id", sa.String(length=64), nullable=False),
        sa.Column("target_representation_id", sa.String(length=64), nullable=False),
        sa.Column("resolved_annotation_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("unresolved_annotation_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("remap_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("remap_id"),
        sa.UniqueConstraint("remap_hash", name="uq_anchor_remap_hash"),
    )
    _indexes("anchor_remaps", ["tenant_id", "project_id", "scene_id", "source_representation_id", "target_representation_id"])

    op.create_table(
        "scene_tags",
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("commit_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tag_id"),
        sa.UniqueConstraint("tenant_id", "project_id", "scene_id", "name", name="uq_scene_tag"),
    )
    _indexes("scene_tags", ["tenant_id", "project_id", "scene_id", "commit_id"])

    if dialect == "postgresql":
        for table, columns in {
            "coordinate_frames": ["semantic_type", "original_units", "unit_scale_to_meters", "original_unit_scale_to_meters", "axis_convention", "axis_directions_json", "handedness", "origin_description", "source", "metadata_json"],
            "scene_commits": ["root_manifest_hash", "change_evidence_ids_json", "policy_checks_json", "signatures_json", "review_state", "recorded_at"],
            "representations": ["format_json", "derivation_policy_json", "limitations_json", "information_loss_json", "privacy_inheritance_json", "dependencies_json", "metadata_json"],
            "representation_bindings": ["coordinate_frame_id", "transform_json", "authority_class", "authority_ceiling", "intended_uses_json", "review_decision_json", "audience_policy_json", "client_profile_json"],
            "measurements": ["measurement_type", "geometry_json", "source_method", "state"],
        }.items():
            for column in columns:
                op.alter_column(table, column, server_default=None)


def _indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


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
    if invalid_evidence or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", rehearsal_id) is None:
        missing = ", ".join(invalid_evidence + (["SIP_DOWNGRADE_REHEARSAL_ID"] if not rehearsal_id else []))
        raise RuntimeError(
            "destructive downgrade denied; verified backup, dry-run, immutable audit references, "
            f"and a rehearsal identifier are mandatory (invalid or missing: {missing or 'rehearsal identifier'})"
        )

    # Recovery rehearsal only. Drop newly owned preservation tables first, then
    # remove additive columns from pre-existing tables in reverse dependency order.
    for table in (
        "scene_tags",
        "anchor_remaps",
        "spatial_annotations",
        "derivation_events",
        "assertions",
        "evidence_records",
        "geometry_asset_manifests",
        "spatial_transforms",
    ):
        op.drop_table(table)

    for index_name in (
        "ix_measurements_originating_representation_id",
        "ix_measurements_supersedes_measurement_id",
        "ix_measurements_state",
        "ix_measurements_source_commit_id",
        "ix_measurements_coordinate_frame_id",
        "ix_measurements_measured_at",
    ):
        op.drop_index(index_name, table_name="measurements")
    _drop_columns(
        "measurements",
        [
            "resolved_metric_evidence_json",
            "interaction_hit_json",
            "originating_representation_id",
            "supersedes_measurement_id",
            "state",
            "permitted_uses_json",
            "source_commit_id",
            "coordinate_frame_id",
            "measured_at",
            "source_method",
            "geometry_json",
            "measurement_type",
        ],
    )

    _drop_columns(
        "representation_bindings",
        [
            "client_profile_json",
            "audience_policy_json",
            "review_decision_json",
            "intended_uses_json",
            "authority_ceiling",
            "authority_class",
            "transform_json",
            "coordinate_frame_id",
        ],
    )

    for index_name in (
        "ix_representations_manifest_hash",
        "ix_representations_fallback_representation_id",
    ):
        op.drop_index(index_name, table_name="representations")
    _drop_columns(
        "representations",
        [
            "deprecated_at",
            "metadata_json",
            "manifest_hash",
            "fallback_representation_id",
            "dependencies_json",
            "privacy_inheritance_json",
            "information_loss_json",
            "limitations_json",
            "derivation_policy_json",
            "format_json",
        ],
    )

    for index_name in (
        "ix_scene_commits_recorded_at",
        "ix_scene_commits_valid_to",
        "ix_scene_commits_valid_from",
        "ix_scene_commits_review_state",
        "ix_scene_commits_workflow_event_id",
        "ix_scene_commits_field_visit_id",
    ):
        op.drop_index(index_name, table_name="scene_commits")
    _drop_columns(
        "scene_commits",
        [
            "recorded_at",
            "valid_to",
            "valid_from",
            "review_state",
            "signatures_json",
            "policy_checks_json",
            "change_evidence_ids_json",
            "workflow_event_id",
            "field_visit_id",
            "root_manifest_hash",
        ],
    )

    for index_name in (
        "ix_coordinate_frames_crs_identifier",
        "ix_coordinate_frames_supersedes_frame_id",
    ):
        op.drop_index(index_name, table_name="coordinate_frames")
    _drop_columns(
        "coordinate_frames",
        [
            "deprecated_at",
            "supersedes_frame_id",
            "metadata_json",
            "geodetic_json",
            "vertical_datum",
            "crs_identifier",
            "source",
            "gravity_alignment",
            "origin_description",
            "handedness",
            "axis_directions_json",
            "axis_convention",
            "original_unit_scale_to_meters",
            "unit_scale_to_meters",
            "original_units",
            "semantic_type",
        ],
    )


def _drop_columns(table: str, columns: list[str]) -> None:
    # Alembic batch mode is portable across PostgreSQL and SQLite and ensures the
    # isolated recovery rehearsal reconstructs the exact prior table shape.
    with op.batch_alter_table(table) as batch:
        for column in columns:
            batch.drop_column(column)
