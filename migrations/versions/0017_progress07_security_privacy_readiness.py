"""Progress 07 security, privacy, audit, key, and supply-chain readiness.

Revision ID: 0017_progress07_security_privacy_readiness
Revises: 0016_progress06_r2_truth_and_restricted_data
Create Date: 2026-07-30
"""
from __future__ import annotations

import os
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_progress07_security_privacy_readiness"
down_revision: Union[str, None] = "0016_progress06_r2_truth_and_restricted_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("workload_identity", sa.String(length=256), nullable=True))
    op.add_column("audit_events", sa.Column("purpose", sa.String(length=128), nullable=True))
    op.add_column("audit_events", sa.Column("source_ip", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("device_context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("audit_events", sa.Column("trace_id", sa.String(length=128), nullable=True))
    op.add_column("audit_events", sa.Column("before_ref_json", sa.JSON(), nullable=True))
    op.add_column("audit_events", sa.Column("after_ref_json", sa.JSON(), nullable=True))
    op.add_column("audit_events", sa.Column("manifest_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_index("ix_audit_events_workload_identity", "audit_events", ["workload_identity"], unique=False)
    op.create_index("ix_audit_events_purpose", "audit_events", ["purpose"], unique=False)
    op.create_index("ix_audit_events_trace_id", "audit_events", ["trace_id"], unique=False)
    op.create_table(
        "threat_manifests",
        sa.Column("threat_manifest_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("review_trigger", sa.String(length=128), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_manifest_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("threat_manifest_id"),
        sa.UniqueConstraint("manifest_hash"),
        sa.UniqueConstraint("scope", "version", name="uq_threat_manifest_scope_version"),
    )
    for column in ("scope", "state", "supersedes_manifest_id"):
        op.create_index(f"ix_threat_manifests_{column}", "threat_manifests", [column], unique=False)

    op.create_table(
        "privileged_access_grants",
        sa.Column("grant_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("resource_scope_json", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("mfa_method", sa.String(length=64), nullable=False),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("grant_id"),
        sa.UniqueConstraint("tenant_id", "request_hash", name="uq_privileged_access_request"),
    )
    for column in ("tenant_id", "project_id", "subject_id", "request_hash", "state", "expires_at"):
        op.create_index(f"ix_privileged_access_grants_{column}", "privileged_access_grants", [column], unique=False)

    op.create_table(
        "workload_identity_grants",
        sa.Column("grant_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("workload_id", sa.String(length=128), nullable=False),
        sa.Column("audience", sa.String(length=256), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("token_jti", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("issued_by", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("grant_id"),
        sa.UniqueConstraint("token_jti"),
        sa.UniqueConstraint("tenant_id", "request_hash", name="uq_workload_identity_request"),
    )
    for column in ("tenant_id", "project_id", "workload_id", "audience", "request_hash", "state", "expires_at"):
        op.create_index(f"ix_workload_identity_grants_{column}", "workload_identity_grants", [column], unique=False)

    op.create_table(
        "key_scopes",
        sa.Column("key_scope_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("person_id", sa.String(length=128), nullable=True),
        sa.Column("key_id", sa.String(length=128), nullable=False),
        sa.Column("backend", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("recovery_policy_json", sa.JSON(), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_from_key_id", sa.String(length=128), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_scope_id"),
        sa.UniqueConstraint("key_id"),
        sa.UniqueConstraint("scope_hash"),
    )
    for column in ("tenant_id", "project_id", "person_id", "state"):
        op.create_index(f"ix_key_scopes_{column}", "key_scopes", [column], unique=False)

    op.create_table(
        "key_access_events",
        sa.Column("key_access_event_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("key_scope_id", sa.String(length=64), nullable=False),
        sa.Column("actor_or_workload", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_scope_json", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("key_access_event_id"),
        sa.UniqueConstraint("event_hash"),
    )
    for column in ("tenant_id", "project_id", "key_scope_id", "actor_or_workload", "outcome"):
        op.create_index(f"ix_key_access_events_{column}", "key_access_events", [column], unique=False)

    op.create_table(
        "privacy_inventory",
        sa.Column("privacy_inventory_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("data_category", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("legal_basis", sa.String(length=128), nullable=False),
        sa.Column("consent_basis", sa.String(length=128), nullable=True),
        sa.Column("processors_json", sa.JSON(), nullable=False),
        sa.Column("residency_json", sa.JSON(), nullable=False),
        sa.Column("retention_json", sa.JSON(), nullable=False),
        sa.Column("security_controls_json", sa.JSON(), nullable=False),
        sa.Column("rights_workflow_json", sa.JSON(), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_inventory_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("privacy_inventory_id"),
        sa.UniqueConstraint("content_hash"),
        sa.UniqueConstraint("tenant_id", "project_id", "data_category", "purpose", "version", name="uq_privacy_inventory_version"),
    )
    for column in ("tenant_id", "project_id", "data_category", "purpose", "state", "supersedes_inventory_id"):
        op.create_index(f"ix_privacy_inventory_{column}", "privacy_inventory", [column], unique=False)

    op.create_table(
        "privacy_impact_assessments",
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("change_reference", sa.String(length=256), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("data_categories_json", sa.JSON(), nullable=False),
        sa.Column("processors_json", sa.JSON(), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("controls_json", sa.JSON(), nullable=False),
        sa.Column("residual_risk", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("request_hash"),
    )
    for column in ("tenant_id", "project_id", "change_type", "change_reference", "decision"):
        op.create_index(f"ix_privacy_impact_assessments_{column}", "privacy_impact_assessments", [column], unique=False)

    op.create_table(
        "privacy_rights_requests",
        sa.Column("rights_request_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("verified_by", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_manifest_json", sa.JSON(), nullable=False),
        sa.Column("verification_json", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("rights_request_id"),
        sa.UniqueConstraint("request_hash"),
    )
    for column in ("tenant_id", "project_id", "subject_id", "request_type", "state"):
        op.create_index(f"ix_privacy_rights_requests_{column}", "privacy_rights_requests", [column], unique=False)

    op.create_table(
        "security_incidents",
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("incident_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("affected_subjects_json", sa.JSON(), nullable=False),
        sa.Column("affected_resources_json", sa.JSON(), nullable=False),
        sa.Column("containment_json", sa.JSON(), nullable=False),
        sa.Column("notification_decision_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("incident_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("incident_id"),
        sa.UniqueConstraint("incident_hash"),
    )
    for column in ("tenant_id", "project_id", "incident_type", "severity", "state"):
        op.create_index(f"ix_security_incidents_{column}", "security_incidents", [column], unique=False)

    op.create_table(
        "audit_verifications",
        sa.Column("audit_verification_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("head_hash", sa.String(length=64), nullable=False),
        sa.Column("referenced_manifests_json", sa.JSON(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("verifier_id", sa.String(length=128), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("audit_verification_id"),
        sa.UniqueConstraint("report_hash"),
    )
    for column in ("tenant_id", "project_id"):
        op.create_index(f"ix_audit_verifications_{column}", "audit_verifications", [column], unique=False)

    op.create_table(
        "supply_chain_releases",
        sa.Column("release_record_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("source_root", sa.String(length=64), nullable=False),
        sa.Column("component_manifests_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("rollback_plan_json", sa.JSON(), nullable=False),
        sa.Column("environment_policy_json", sa.JSON(), nullable=False),
        sa.Column("emergency_patch", sa.Boolean(), nullable=False),
        sa.Column("retrospective_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("signed_by", sa.String(length=128), nullable=False),
        sa.Column("signature", sa.String(length=128), nullable=False),
        sa.Column("release_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("release_record_id"),
        sa.UniqueConstraint("release_hash"),
    )
    op.create_index("ix_supply_chain_releases_version", "supply_chain_releases", ["version"], unique=False)
    op.create_index("ix_supply_chain_releases_state", "supply_chain_releases", ["state"], unique=False)

    op.create_table(
        "provider_governance_exceptions",
        sa.Column("exception_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("prohibited_waivers_json", sa.JSON(), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exception_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("exception_id"),
        sa.UniqueConstraint("exception_hash"),
    )
    for column in ("tenant_id", "project_id", "provider_id", "state", "expires_at"):
        op.create_index(f"ix_provider_governance_exceptions_{column}", "provider_governance_exceptions", [column], unique=False)

    op.create_table(
        "cache_invalidations",
        sa.Column("invalidation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("targets_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("invalidation_id"),
        sa.UniqueConstraint("invalidation_hash"),
    )
    for column in ("tenant_id", "project_id", "resource_id", "state"):
        op.create_index(f"ix_cache_invalidations_{column}", "cache_invalidations", [column], unique=False)


    op.create_table(
        "transport_verifications",
        sa.Column("transport_verification_id", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=False),
        sa.Column("protocol", sa.String(length=64), nullable=False),
        sa.Column("minimum_tls_version", sa.String(length=32), nullable=False),
        sa.Column("certificate_validated", sa.Boolean(), nullable=False),
        sa.Column("channel_authentication", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("verification_hash", sa.String(length=64), nullable=False),
        sa.Column("verified_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("transport_verification_id"),
        sa.UniqueConstraint("verification_hash"),
    )
    op.create_index("ix_transport_verifications_environment", "transport_verifications", ["environment"], unique=False)
    op.create_index("ix_transport_verifications_state", "transport_verifications", ["state"], unique=False)

    op.create_table(
        "capture_finalization_audits",
        sa.Column("capture_finalization_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("capture_id", sa.String(length=128), nullable=False),
        sa.Column("package_root_hash", sa.String(length=64), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("device_json", sa.JSON(), nullable=False),
        sa.Column("app_json", sa.JSON(), nullable=False),
        sa.Column("signer_id", sa.String(length=128), nullable=False),
        sa.Column("verification_result", sa.String(length=32), nullable=False),
        sa.Column("verification_json", sa.JSON(), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("capture_finalization_id"),
        sa.UniqueConstraint("record_hash"),
    )
    for column in ("tenant_id", "project_id", "capture_id", "package_root_hash", "verification_result"):
        op.create_index(f"ix_capture_finalization_audits_{column}", "capture_finalization_audits", [column], unique=False)

    op.create_table(
        "immersive_safety_decisions",
        sa.Column("safety_decision_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("disabled_modes_json", sa.JSON(), nullable=False),
        sa.Column("fallback_mode", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("decision_hash", sa.String(length=64), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("safety_decision_id"),
        sa.UniqueConstraint("decision_hash"),
    )
    for column in ("tenant_id", "project_id", "scene_id", "profile_hash", "state"):
        op.create_index(f"ix_immersive_safety_decisions_{column}", "immersive_safety_decisions", [column], unique=False)

    op.create_table(
        "provider_output_validations",
        sa.Column("output_validation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("output_sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=256), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), nullable=False),
        sa.Column("validations_json", sa.JSON(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("validation_hash", sa.String(length=64), nullable=False),
        sa.Column("validated_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("output_validation_id"),
        sa.UniqueConstraint("validation_hash"),
    )
    for column in ("tenant_id", "project_id", "provider_id", "operation_id", "output_sha256", "state"):
        op.create_index(f"ix_provider_output_validations_{column}", "provider_output_validations", [column], unique=False)


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
    for table in (
        "provider_output_validations",
        "immersive_safety_decisions",
        "capture_finalization_audits",
        "transport_verifications",
        "cache_invalidations",
        "provider_governance_exceptions",
        "supply_chain_releases",
        "audit_verifications",
        "security_incidents",
        "privacy_rights_requests",
        "privacy_impact_assessments",
        "privacy_inventory",
        "key_access_events",
        "key_scopes",
        "workload_identity_grants",
        "privileged_access_grants",
        "threat_manifests",
    ):
        op.drop_table(table)
    for index_name in ("ix_audit_events_trace_id", "ix_audit_events_purpose", "ix_audit_events_workload_identity"):
        op.drop_index(index_name, table_name="audit_events")
    for column_name in ("manifest_refs_json", "after_ref_json", "before_ref_json", "trace_id", "device_context_json", "source_ip", "purpose", "workload_identity"):
        op.drop_column("audit_events", column_name)
