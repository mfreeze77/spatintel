"""Construction and LiveForever vertical MVP durable records.

This append-only migration introduces auditable survey/visit, document, issue,
commissioning, interchange, owner-handoff, consent-governance, interview, transcript,
edition, derivative-policy, and preservation-release records. Downgrade is recovery-only.
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0014_vertical_mvp"
down_revision = "0013_scene_change_application_atomicity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"unsupported migration dialect: {dialect}")


    op.create_table(
        "construction_surveys",
        sa.Column("survey_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("objectives_json", sa.JSON(), nullable=False),
        sa.Column("required_place_ids_json", sa.JSON(), nullable=False),
        sa.Column("required_system_types_json", sa.JSON(), nullable=False),
        sa.Column("sensitive_regions_json", sa.JSON(), nullable=False),
        sa.Column("control_requirements_json", sa.JSON(), nullable=False),
        sa.Column("measurement_requirements_json", sa.JSON(), nullable=False),
        sa.Column("safety_json", sa.JSON(), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("deliverables_json", sa.JSON(), nullable=False),
        sa.Column("baseline_commit_id", sa.String(length=64), nullable=True),
        sa.Column("return_visit_of_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("review_json", sa.JSON(), nullable=False),
        sa.Column("accepted_commit_id", sa.String(length=64), nullable=True),
        sa.Column("completion_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('survey_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_survey_idempotency'),
    )
    op.create_index('ix_construction_surveys_accepted_commit_id', 'construction_surveys', ['accepted_commit_id'], unique=False)
    op.create_index('ix_construction_surveys_baseline_commit_id', 'construction_surveys', ['baseline_commit_id'], unique=False)
    op.create_index('ix_construction_surveys_project_id', 'construction_surveys', ['project_id'], unique=False)
    op.create_index('ix_construction_surveys_return_visit_of_id', 'construction_surveys', ['return_visit_of_id'], unique=False)
    op.create_index('ix_construction_surveys_state', 'construction_surveys', ['state'], unique=False)
    op.create_index('ix_construction_surveys_tenant_id', 'construction_surveys', ['tenant_id'], unique=False)

    op.create_table(
        "construction_visits",
        sa.Column("visit_id", sa.String(length=64), nullable=False),
        sa.Column("survey_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("exact_prior_commit_id", sa.String(length=64), nullable=True),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("capture_ids_json", sa.JSON(), nullable=False),
        sa.Column("checklist_json", sa.JSON(), nullable=False),
        sa.Column("detail_evidence_json", sa.JSON(), nullable=False),
        sa.Column("inaccessible_regions_json", sa.JSON(), nullable=False),
        sa.Column("coverage_json", sa.JSON(), nullable=False),
        sa.Column("tracking_json", sa.JSON(), nullable=False),
        sa.Column("registration_json", sa.JSON(), nullable=False),
        sa.Column("controls_json", sa.JSON(), nullable=False),
        sa.Column("inventory_json", sa.JSON(), nullable=False),
        sa.Column("unresolved_questions_json", sa.JSON(), nullable=False),
        sa.Column("privacy_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('visit_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_visit_idempotency'),
    )
    op.create_index('ix_construction_visits_exact_prior_commit_id', 'construction_visits', ['exact_prior_commit_id'], unique=False)
    op.create_index('ix_construction_visits_project_id', 'construction_visits', ['project_id'], unique=False)
    op.create_index('ix_construction_visits_state', 'construction_visits', ['state'], unique=False)
    op.create_index('ix_construction_visits_survey_id', 'construction_visits', ['survey_id'], unique=False)
    op.create_index('ix_construction_visits_tenant_id', 'construction_visits', ['tenant_id'], unique=False)

    op.create_table(
        "construction_document_revisions",
        sa.Column("revision_id", sa.String(length=64), nullable=False),
        sa.Column("stable_document_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("issue_date", sa.String(length=64), nullable=False),
        sa.Column("issuer", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("supersedes_revision_id", sa.String(length=64), nullable=True),
        sa.Column("page_regions_json", sa.JSON(), nullable=False),
        sa.Column("spatial_links_json", sa.JSON(), nullable=False),
        sa.Column("extraction_json", sa.JSON(), nullable=False),
        sa.Column("review_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('revision_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'stable_document_id', 'revision', name='uq_construction_document_revision'),
    )
    op.create_index('ix_construction_document_revisions_asset_id', 'construction_document_revisions', ['asset_id'], unique=False)
    op.create_index('ix_construction_document_revisions_document_type', 'construction_document_revisions', ['document_type'], unique=False)
    op.create_index('ix_construction_document_revisions_project_id', 'construction_document_revisions', ['project_id'], unique=False)
    op.create_index('ix_construction_document_revisions_stable_document_id', 'construction_document_revisions', ['stable_document_id'], unique=False)
    op.create_index('ix_construction_document_revisions_status', 'construction_document_revisions', ['status'], unique=False)
    op.create_index('ix_construction_document_revisions_supersedes_revision_id', 'construction_document_revisions', ['supersedes_revision_id'], unique=False)
    op.create_index('ix_construction_document_revisions_tenant_id', 'construction_document_revisions', ['tenant_id'], unique=False)

    op.create_table(
        "construction_issues",
        sa.Column("issue_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=None), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("place_id", sa.String(length=64), nullable=True),
        sa.Column("observed_commit_id", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("reporter_id", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("responsible_party", sa.String(length=256), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("history_json", sa.JSON(), nullable=False),
        sa.Column("residual_limitations_json", sa.JSON(), nullable=False),
        sa.Column("verification_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('issue_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_issue_idempotency'),
    )
    op.create_index('ix_construction_issues_entity_id', 'construction_issues', ['entity_id'], unique=False)
    op.create_index('ix_construction_issues_issue_type', 'construction_issues', ['issue_type'], unique=False)
    op.create_index('ix_construction_issues_observed_commit_id', 'construction_issues', ['observed_commit_id'], unique=False)
    op.create_index('ix_construction_issues_place_id', 'construction_issues', ['place_id'], unique=False)
    op.create_index('ix_construction_issues_project_id', 'construction_issues', ['project_id'], unique=False)
    op.create_index('ix_construction_issues_severity', 'construction_issues', ['severity'], unique=False)
    op.create_index('ix_construction_issues_status', 'construction_issues', ['status'], unique=False)
    op.create_index('ix_construction_issues_tenant_id', 'construction_issues', ['tenant_id'], unique=False)

    op.create_table(
        "construction_commissioning_runs",
        sa.Column("commissioning_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("system_type", sa.String(length=64), nullable=False),
        sa.Column("entity_ids_json", sa.JSON(), nullable=False),
        sa.Column("issue_id", sa.String(length=64), nullable=True),
        sa.Column("procedure_json", sa.JSON(), nullable=False),
        sa.Column("prerequisites_json", sa.JSON(), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("participants_json", sa.JSON(), nullable=False),
        sa.Column("instruments_json", sa.JSON(), nullable=False),
        sa.Column("attachments_json", sa.JSON(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("retest_of_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("accepted_by", sa.String(length=128), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('commissioning_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_commissioning_idempotency'),
    )
    op.create_index('ix_construction_commissioning_runs_issue_id', 'construction_commissioning_runs', ['issue_id'], unique=False)
    op.create_index('ix_construction_commissioning_runs_project_id', 'construction_commissioning_runs', ['project_id'], unique=False)
    op.create_index('ix_construction_commissioning_runs_retest_of_id', 'construction_commissioning_runs', ['retest_of_id'], unique=False)
    op.create_index('ix_construction_commissioning_runs_state', 'construction_commissioning_runs', ['state'], unique=False)
    op.create_index('ix_construction_commissioning_runs_system_type', 'construction_commissioning_runs', ['system_type'], unique=False)
    op.create_index('ix_construction_commissioning_runs_tenant_id', 'construction_commissioning_runs', ['tenant_id'], unique=False)

    op.create_table(
        "construction_interchanges",
        sa.Column("interchange_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("source_asset_id", sa.String(length=64), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("units", sa.String(length=32), nullable=True),
        sa.Column("crs_json", sa.JSON(), nullable=False),
        sa.Column("owner_history_json", sa.JSON(), nullable=False),
        sa.Column("global_ids_json", sa.JSON(), nullable=False),
        sa.Column("classifications_json", sa.JSON(), nullable=False),
        sa.Column("properties_json", sa.JSON(), nullable=False),
        sa.Column("relationships_json", sa.JSON(), nullable=False),
        sa.Column("geometry_conversion_report_json", sa.JSON(), nullable=False),
        sa.Column("unsupported_constructs_json", sa.JSON(), nullable=False),
        sa.Column("alignment_json", sa.JSON(), nullable=False),
        sa.Column("mappings_json", sa.JSON(), nullable=False),
        sa.Column("issues_json", sa.JSON(), nullable=False),
        sa.Column("truth_labels_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('interchange_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_interchange_idempotency'),
    )
    op.create_index('ix_construction_interchanges_direction', 'construction_interchanges', ['direction'], unique=False)
    op.create_index('ix_construction_interchanges_format', 'construction_interchanges', ['format'], unique=False)
    op.create_index('ix_construction_interchanges_project_id', 'construction_interchanges', ['project_id'], unique=False)
    op.create_index('ix_construction_interchanges_source_asset_id', 'construction_interchanges', ['source_asset_id'], unique=False)
    op.create_index('ix_construction_interchanges_status', 'construction_interchanges', ['status'], unique=False)
    op.create_index('ix_construction_interchanges_tenant_id', 'construction_interchanges', ['tenant_id'], unique=False)

    op.create_table(
        "construction_handoffs",
        sa.Column("handoff_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("accepted_scene_commit_id", sa.String(length=64), nullable=False),
        sa.Column("inventory_json", sa.JSON(), nullable=False),
        sa.Column("verified_attributes_json", sa.JSON(), nullable=False),
        sa.Column("documents_json", sa.JSON(), nullable=False),
        sa.Column("tests_json", sa.JSON(), nullable=False),
        sa.Column("warranties_json", sa.JSON(), nullable=False),
        sa.Column("training_json", sa.JSON(), nullable=False),
        sa.Column("open_issues_json", sa.JSON(), nullable=False),
        sa.Column("exclusions_json", sa.JSON(), nullable=False),
        sa.Column("exports_json", sa.JSON(), nullable=False),
        sa.Column("representation_manifest_json", sa.JSON(), nullable=False),
        sa.Column("audience_profiles_json", sa.JSON(), nullable=False),
        sa.Column("offline_viewer_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("checksums_json", sa.JSON(), nullable=False),
        sa.Column("root_hash", sa.String(length=64), nullable=True),
        sa.Column("package_path", sa.String(length=None), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('handoff_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_construction_handoff_idempotency'),
    )
    op.create_index('ix_construction_handoffs_accepted_scene_commit_id', 'construction_handoffs', ['accepted_scene_commit_id'], unique=False)
    op.create_index('ix_construction_handoffs_project_id', 'construction_handoffs', ['project_id'], unique=False)
    op.create_index('ix_construction_handoffs_status', 'construction_handoffs', ['status'], unique=False)
    op.create_index('ix_construction_handoffs_tenant_id', 'construction_handoffs', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_governance",
        sa.Column("governance_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("consent_grant_id", sa.String(length=64), nullable=True),
        sa.Column("grantor_id", sa.String(length=128), nullable=False),
        sa.Column("authority_basis", sa.String(length=128), nullable=False),
        sa.Column("data_scope_json", sa.JSON(), nullable=False),
        sa.Column("purposes_json", sa.JSON(), nullable=False),
        sa.Column("modalities_json", sa.JSON(), nullable=False),
        sa.Column("audiences_json", sa.JSON(), nullable=False),
        sa.Column("providers_json", sa.JSON(), nullable=False),
        sa.Column("geography_json", sa.JSON(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posthumous_rules_json", sa.JSON(), nullable=False),
        sa.Column("evidence_asset_ids_json", sa.JSON(), nullable=False),
        sa.Column("successor_ids_json", sa.JSON(), nullable=False),
        sa.Column("dispute_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("freeze_high_risk", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('governance_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_liveforever_governance_idempotency'),
    )
    op.create_index('ix_liveforever_governance_consent_grant_id', 'liveforever_governance', ['consent_grant_id'], unique=False)
    op.create_index('ix_liveforever_governance_project_id', 'liveforever_governance', ['project_id'], unique=False)
    op.create_index('ix_liveforever_governance_record_type', 'liveforever_governance', ['record_type'], unique=False)
    op.create_index('ix_liveforever_governance_state', 'liveforever_governance', ['state'], unique=False)
    op.create_index('ix_liveforever_governance_subject_id', 'liveforever_governance', ['subject_id'], unique=False)
    op.create_index('ix_liveforever_governance_tenant_id', 'liveforever_governance', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_interviews",
        sa.Column("interview_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("participants_json", sa.JSON(), nullable=False),
        sa.Column("consent_context_json", sa.JSON(), nullable=False),
        sa.Column("recording_state", sa.String(length=32), nullable=False),
        sa.Column("source_media_ids_json", sa.JSON(), nullable=False),
        sa.Column("timeline_json", sa.JSON(), nullable=False),
        sa.Column("device_json", sa.JSON(), nullable=False),
        sa.Column("environment_json", sa.JSON(), nullable=False),
        sa.Column("interruptions_json", sa.JSON(), nullable=False),
        sa.Column("question_lineage_json", sa.JSON(), nullable=False),
        sa.Column("pacing_policy_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('interview_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_liveforever_interview_idempotency'),
    )
    op.create_index('ix_liveforever_interviews_project_id', 'liveforever_interviews', ['project_id'], unique=False)
    op.create_index('ix_liveforever_interviews_recording_state', 'liveforever_interviews', ['recording_state'], unique=False)
    op.create_index('ix_liveforever_interviews_state', 'liveforever_interviews', ['state'], unique=False)
    op.create_index('ix_liveforever_interviews_subject_id', 'liveforever_interviews', ['subject_id'], unique=False)
    op.create_index('ix_liveforever_interviews_tenant_id', 'liveforever_interviews', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_transcript_segments",
        sa.Column("segment_id", sa.String(length=64), nullable=False),
        sa.Column("interview_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("speaker_label", sa.String(length=256), nullable=False),
        sa.Column("speaker_confidence", sa.Float(), nullable=False),
        sa.Column("original_text", sa.String(length=None), nullable=False),
        sa.Column("edited_text", sa.String(length=None), nullable=True),
        sa.Column("correction_history_json", sa.JSON(), nullable=False),
        sa.Column("private_marks_json", sa.JSON(), nullable=False),
        sa.Column("source_media_id", sa.String(length=64), nullable=False),
        sa.Column("spatial_anchor_json", sa.JSON(), nullable=True),
        sa.Column("followup_suggestions_json", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('segment_id'),
        sa.UniqueConstraint('interview_id', 'segment_index', name='uq_liveforever_transcript_segment_index'),
    )
    op.create_index('ix_liveforever_transcript_segments_interview_id', 'liveforever_transcript_segments', ['interview_id'], unique=False)
    op.create_index('ix_liveforever_transcript_segments_project_id', 'liveforever_transcript_segments', ['project_id'], unique=False)
    op.create_index('ix_liveforever_transcript_segments_review_state', 'liveforever_transcript_segments', ['review_state'], unique=False)
    op.create_index('ix_liveforever_transcript_segments_source_media_id', 'liveforever_transcript_segments', ['source_media_id'], unique=False)
    op.create_index('ix_liveforever_transcript_segments_tenant_id', 'liveforever_transcript_segments', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_editions",
        sa.Column("edition_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("audience_profile", sa.String(length=32), nullable=False),
        sa.Column("record_revisions_json", sa.JSON(), nullable=False),
        sa.Column("presentation_choices_json", sa.JSON(), nullable=False),
        sa.Column("scene_commit_id", sa.String(length=64), nullable=True),
        sa.Column("narrative_path_json", sa.JSON(), nullable=False),
        sa.Column("truth_legend_json", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("supersedes_edition_id", sa.String(length=64), nullable=True),
        sa.Column("root_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('edition_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_liveforever_edition_idempotency'),
    )
    op.create_index('ix_liveforever_editions_audience_profile', 'liveforever_editions', ['audience_profile'], unique=False)
    op.create_index('ix_liveforever_editions_project_id', 'liveforever_editions', ['project_id'], unique=False)
    op.create_index('ix_liveforever_editions_scene_commit_id', 'liveforever_editions', ['scene_commit_id'], unique=False)
    op.create_index('ix_liveforever_editions_state', 'liveforever_editions', ['state'], unique=False)
    op.create_index('ix_liveforever_editions_supersedes_edition_id', 'liveforever_editions', ['supersedes_edition_id'], unique=False)
    op.create_index('ix_liveforever_editions_tenant_id', 'liveforever_editions', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_derivatives",
        sa.Column("derivative_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("derivative_type", sa.String(length=64), nullable=False),
        sa.Column("source_ids_json", sa.JSON(), nullable=False),
        sa.Column("subject_ids_json", sa.JSON(), nullable=False),
        sa.Column("consent_grant_ids_json", sa.JSON(), nullable=False),
        sa.Column("audience", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("retention_json", sa.JSON(), nullable=False),
        sa.Column("provider_json", sa.JSON(), nullable=False),
        sa.Column("generation_lineage_json", sa.JSON(), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("withdrawal_action", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('derivative_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_liveforever_derivative_idempotency'),
    )
    op.create_index('ix_liveforever_derivatives_audience', 'liveforever_derivatives', ['audience'], unique=False)
    op.create_index('ix_liveforever_derivatives_classification', 'liveforever_derivatives', ['classification'], unique=False)
    op.create_index('ix_liveforever_derivatives_derivative_type', 'liveforever_derivatives', ['derivative_type'], unique=False)
    op.create_index('ix_liveforever_derivatives_project_id', 'liveforever_derivatives', ['project_id'], unique=False)
    op.create_index('ix_liveforever_derivatives_state', 'liveforever_derivatives', ['state'], unique=False)
    op.create_index('ix_liveforever_derivatives_tenant_id', 'liveforever_derivatives', ['tenant_id'], unique=False)

    op.create_table(
        "liveforever_preservation_releases",
        sa.Column("release_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("edition_id", sa.String(length=64), nullable=False),
        sa.Column("originals_json", sa.JSON(), nullable=False),
        sa.Column("technical_metadata_json", sa.JSON(), nullable=False),
        sa.Column("rights_consent_json", sa.JSON(), nullable=False),
        sa.Column("transcripts_json", sa.JSON(), nullable=False),
        sa.Column("memory_graph_json", sa.JSON(), nullable=False),
        sa.Column("scene_manifests_json", sa.JSON(), nullable=False),
        sa.Column("open_assets_json", sa.JSON(), nullable=False),
        sa.Column("checksums_json", sa.JSON(), nullable=False),
        sa.Column("human_guide_json", sa.JSON(), nullable=False),
        sa.Column("offline_fallback_json", sa.JSON(), nullable=False),
        sa.Column("fixity_json", sa.JSON(), nullable=False),
        sa.Column("replicas_json", sa.JSON(), nullable=False),
        sa.Column("format_migrations_json", sa.JSON(), nullable=False),
        sa.Column("succession_json", sa.JSON(), nullable=False),
        sa.Column("shutdown_json", sa.JSON(), nullable=False),
        sa.Column("package_path", sa.String(length=None), nullable=True),
        sa.Column("root_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('release_id'),
        sa.UniqueConstraint('tenant_id', 'project_id', 'idempotency_key', name='uq_liveforever_preservation_idempotency'),
    )
    op.create_index('ix_liveforever_preservation_releases_edition_id', 'liveforever_preservation_releases', ['edition_id'], unique=False)
    op.create_index('ix_liveforever_preservation_releases_project_id', 'liveforever_preservation_releases', ['project_id'], unique=False)
    op.create_index('ix_liveforever_preservation_releases_status', 'liveforever_preservation_releases', ['status'], unique=False)
    op.create_index('ix_liveforever_preservation_releases_tenant_id', 'liveforever_preservation_releases', ['tenant_id'], unique=False)


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

    op.drop_table("liveforever_preservation_releases")
    op.drop_table("liveforever_derivatives")
    op.drop_table("liveforever_editions")
    op.drop_table("liveforever_transcript_segments")
    op.drop_table("liveforever_interviews")
    op.drop_table("liveforever_governance")
    op.drop_table("construction_handoffs")
    op.drop_table("construction_interchanges")
    op.drop_table("construction_commissioning_runs")
    op.drop_table("construction_issues")
    op.drop_table("construction_document_revisions")
    op.drop_table("construction_visits")
    op.drop_table("construction_surveys")
