"""Governed hybrid-representation provider, conversion, validation, and view controls.

The migration is additive. Provider capability descriptors are retained as immutable
revisions; execution promotions, admitted conversion snapshots, quarantined outputs,
independent intended-use validations, controlled manual transfers, and signed view
manifests are durable control-plane records. Downgrade is recovery-only because removing
these records destroys governance and publication evidence.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0011_governed_hybrid_representation"
down_revision = "0010_spatial_truth_and_twin_controls"
branch_labels = None
depends_on = None

JSON_OBJECT = sa.text("'{}'")
JSON_ARRAY = sa.text("'[]'")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")

    # Extend the mutable provider pointer while preserving every approved descriptor
    # revision in provider_manifest_revisions below.
    for column in [
        sa.Column("provider_class", sa.String(length=64), nullable=False, server_default="local_open_source"),
        sa.Column("executable_digest", sa.String(length=128), nullable=True),
        sa.Column("deployments_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("execution_modes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("input_roles_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("output_roles_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("supported_formats_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("coordinate_contract_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("reproducibility_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("security_contract_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("recovery_contract_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("model_manifest_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("dependency_inventory_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("license_evidence_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("benchmark_profile_ids_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("descriptor_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("manifest_signature", sa.String(length=64), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        op.add_column("provider_manifests", column)

    op.create_table(
        "provider_manifest_revisions",
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("descriptor_json", sa.JSON(), nullable=False),
        sa.Column("manifest_signature", sa.String(length=64), nullable=False),
        sa.Column("approval_state", sa.String(length=32), nullable=False),
        sa.Column("signed_by", sa.String(length=128), nullable=False),
        sa.Column("registered_by", sa.String(length=128), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("manifest_hash"),
        sa.UniqueConstraint("provider_id", "provider_version", "manifest_hash", name="uq_provider_manifest_revision"),
    )
    op.create_index("ix_provider_manifest_revisions_provider_id", "provider_manifest_revisions", ["provider_id"])
    op.create_index("ix_provider_manifest_revisions_provider_version", "provider_manifest_revisions", ["provider_version"])
    op.create_index("ix_provider_manifest_revisions_approval_state", "provider_manifest_revisions", ["approval_state"])

    op.create_table(
        "provider_promotions",
        sa.Column("promotion_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("provider_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("data_classifications_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("scene_classes_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("output_roles_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("intended_uses_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("execution_zones_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("hardware_profiles_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("benchmark_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promotion_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_by", sa.String(length=128), nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["provider_manifests.provider_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("promotion_id"),
        sa.UniqueConstraint("promotion_hash"),
    )
    for name, columns in [
        ("ix_provider_promotions_provider_id", ["provider_id"]),
        ("ix_provider_promotions_provider_version", ["provider_version"]),
        ("ix_provider_promotions_provider_manifest_hash", ["provider_manifest_hash"]),
        ("ix_provider_promotions_state", ["state"]),
    ]:
        op.create_index(name, "provider_promotions", columns)

    op.create_table(
        "spatial_conversions",
        sa.Column("conversion_id", sa.String(length=64), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("scene_revision_id", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("intended_uses_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("output_roles_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("source_assets_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("reference_assets_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("constraints_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("policy_context_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("provider_selector_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("provider_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("promotion_id", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("admission_state", sa.String(length=32), nullable=False),
        sa.Column("admission_decision_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("admission_decision_hash", sa.String(length=64), nullable=False),
        sa.Column("resource_estimate_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("credential_claims_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("worker_lease_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("worker_token_hash", sa.String(length=64), nullable=True),
        sa.Column("worker_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("failure_hash", sa.String(length=64), nullable=True),
        sa.Column("cleanup_receipt_hash", sa.String(length=64), nullable=True),
        sa.Column("candidate_representation_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="admitted"),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider_manifests.provider_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["promotion_id"], ["provider_promotions.promotion_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("conversion_id"),
        sa.UniqueConstraint("operation_id"),
        sa.UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_spatial_conversion_idempotency"),
    )
    for name, columns in [
        ("ix_spatial_conversions_operation_id", ["operation_id"]),
        ("ix_spatial_conversions_tenant_id", ["tenant_id"]),
        ("ix_spatial_conversions_project_id", ["project_id"]),
        ("ix_spatial_conversions_scene_id", ["scene_id"]),
        ("ix_spatial_conversions_scene_revision_id", ["scene_revision_id"]),
        ("ix_spatial_conversions_purpose", ["purpose"]),
        ("ix_spatial_conversions_provider_id", ["provider_id"]),
        ("ix_spatial_conversions_promotion_id", ["promotion_id"]),
        ("ix_spatial_conversions_admission_state", ["admission_state"]),
        ("ix_spatial_conversions_candidate_representation_id", ["candidate_representation_id"]),
        ("ix_spatial_conversions_state", ["state"]),
    ]:
        op.create_index(name, "spatial_conversions", columns)

    op.create_table(
        "provider_progress",
        sa.Column("progress_id", sa.String(length=64), nullable=False),
        sa.Column("conversion_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=128), nullable=False),
        sa.Column("completed_work_units", sa.Float(), nullable=False),
        sa.Column("total_work_units", sa.Float(), nullable=True),
        sa.Column("work_unit_name", sa.String(length=64), nullable=False),
        sa.Column("resource_use_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("warnings_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("checkpoint_hash", sa.String(length=64), nullable=True),
        sa.Column("estimated_output_bytes", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversion_id"], ["spatial_conversions.conversion_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("progress_id"),
        sa.UniqueConstraint("conversion_id", "sequence", name="uq_provider_progress_sequence"),
    )
    op.create_index("ix_provider_progress_conversion_id", "provider_progress", ["conversion_id"])

    op.create_table(
        "intended_use_validations",
        sa.Column("validation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("conversion_id", sa.String(length=64), nullable=False),
        sa.Column("representation_id", sa.String(length=64), nullable=False),
        sa.Column("intended_use", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_version", sa.String(length=64), nullable=False),
        sa.Column("validator_id", sa.String(length=128), nullable=False),
        sa.Column("validator_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("thresholds_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("coverage_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("topology_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("coordinate_validation_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("behavior_validation_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("limitations_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("candidate_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversion_id"], ["spatial_conversions.conversion_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["representation_id"], ["representations.representation_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint("validation_hash"),
        sa.UniqueConstraint("representation_id", "intended_use", "profile_id", "profile_version", name="uq_representation_use_validation"),
    )
    for name, columns in [
        ("ix_intended_use_validations_tenant_id", ["tenant_id"]),
        ("ix_intended_use_validations_project_id", ["project_id"]),
        ("ix_intended_use_validations_conversion_id", ["conversion_id"]),
        ("ix_intended_use_validations_representation_id", ["representation_id"]),
        ("ix_intended_use_validations_intended_use", ["intended_use"]),
    ]:
        op.create_index(name, "intended_use_validations", columns)

    op.create_table(
        "manual_provider_transfers",
        sa.Column("transfer_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("conversion_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("outbound_manifest_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("outbound_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_decision_hash", sa.String(length=64), nullable=False),
        sa.Column("one_time_code_hash", sa.String(length=64), nullable=False),
        sa.Column("receipt_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("receipt_hash", sa.String(length=64), nullable=True),
        sa.Column("returned_outputs_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="exported"),
        sa.Column("exported_by", sa.String(length=128), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_by", sa.String(length=128), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversion_id"], ["spatial_conversions.conversion_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("transfer_id"),
    )
    for name, columns in [
        ("ix_manual_provider_transfers_tenant_id", ["tenant_id"]),
        ("ix_manual_provider_transfers_project_id", ["project_id"]),
        ("ix_manual_provider_transfers_conversion_id", ["conversion_id"]),
        ("ix_manual_provider_transfers_provider_id", ["provider_id"]),
        ("ix_manual_provider_transfers_state", ["state"]),
    ]:
        op.create_index(name, "manual_provider_transfers", columns)

    op.create_table(
        "hybrid_scene_views",
        sa.Column("view_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("scene_revision_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("device_profile", sa.String(length=128), nullable=False),
        sa.Column("time_context_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("bindings_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("excluded_summary_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("interaction_policy_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("truth_labels_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("streaming_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("view_id"),
        sa.UniqueConstraint("manifest_hash"),
    )
    for name, columns in [
        ("ix_hybrid_scene_views_tenant_id", ["tenant_id"]),
        ("ix_hybrid_scene_views_project_id", ["project_id"]),
        ("ix_hybrid_scene_views_scene_id", ["scene_id"]),
        ("ix_hybrid_scene_views_scene_revision_id", ["scene_revision_id"]),
        ("ix_hybrid_scene_views_principal_id", ["principal_id"]),
        ("ix_hybrid_scene_views_purpose", ["purpose"]),
        ("ix_hybrid_scene_views_audience", ["audience"]),
        ("ix_hybrid_scene_views_expires_at", ["expires_at"]),
    ]:
        op.create_index(name, "hybrid_scene_views", columns)

    op.create_table(
        "representation_families",
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("coordinate_frame_id", sa.String(length=64), nullable=False),
        sa.Column("tile_scheme_id", sa.String(length=128), nullable=False),
        sa.Column("lods_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("seam_validation_report_id", sa.String(length=128), nullable=True),
        sa.Column("fallback_representation_id", sa.String(length=64), nullable=True),
        sa.Column("family_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("family_id"),
        sa.UniqueConstraint("family_hash"),
    )
    for name, columns in [
        ("ix_representation_families_tenant_id", ["tenant_id"]),
        ("ix_representation_families_project_id", ["project_id"]),
        ("ix_representation_families_scene_id", ["scene_id"]),
        ("ix_representation_families_role", ["role"]),
    ]:
        op.create_index(name, "representation_families", columns)

    op.create_table(
        "interaction_profiles",
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("actor_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("intended_uses_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("limits_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("behavior_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("validation_json", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("safety_claims_json", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("validator_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_signature", sa.String(length=64), nullable=False),
        sa.Column("signed_by", sa.String(length=128), nullable=False),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("profile_id"),
        sa.UniqueConstraint("manifest_hash"),
    )
    op.create_index("ix_interaction_profiles_profile_type", "interaction_profiles", ["profile_type"])


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

    for table in (
        "hybrid_scene_views",
        "manual_provider_transfers",
        "intended_use_validations",
        "provider_progress",
        "representation_families",
        "interaction_profiles",
        "spatial_conversions",
        "provider_promotions",
        "provider_manifest_revisions",
    ):
        op.drop_table(table)

    _drop_columns(
        "provider_manifests",
        [
            "updated_at",
            "registered_at",
            "manifest_signature",
            "descriptor_json",
            "benchmark_profile_ids_json",
            "license_evidence_json",
            "dependency_inventory_json",
            "model_manifest_ids_json",
            "recovery_contract_json",
            "security_contract_json",
            "reproducibility_json",
            "coordinate_contract_json",
            "supported_formats_json",
            "output_roles_json",
            "input_roles_json",
            "execution_modes_json",
            "deployments_json",
            "executable_digest",
            "provider_class",
        ],
    )


def _drop_columns(table: str, columns: list[str]) -> None:
    with op.batch_alter_table(table) as batch:
        for column in columns:
            batch.drop_column(column)
