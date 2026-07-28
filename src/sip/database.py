from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .temporal import db_now


class Base(DeclarativeBase):
    """Declarative root for every canonical SIP persistence model."""


class TenantRow(Base):
    __tablename__ = "tenants"
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ProjectRow(Base):
    __tablename__ = "projects"
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    vertical: Mapped[str] = mapped_column(String(64), default="platform")
    classification: Mapped[str] = mapped_column(String(64), default="internal")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class IdentityRow(Base):
    __tablename__ = "identities"
    identity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    identity_type: Mapped[str] = mapped_column(String(32), default="user")
    display_name: Mapped[str] = mapped_column(String(256))
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class RoleBindingRow(Base):
    __tablename__ = "role_bindings"
    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    identity_id: Mapped[str] = mapped_column(ForeignKey("identities.identity_id", ondelete="RESTRICT"), index=True)
    role: Mapped[str] = mapped_column(String(64))
    purposes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    spatial_restrictions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class AssetRow(Base):
    __tablename__ = "assets"
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    byte_count: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(256))
    storage_key: Mapped[str] = mapped_column(Text)
    encryption_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class AssetRefRow(Base):
    __tablename__ = "asset_refs"
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    sha256: Mapped[str] = mapped_column(ForeignKey("assets.sha256", ondelete="RESTRICT"), index=True)
    original_name: Mapped[str] = mapped_column(String(512))
    classification: Mapped[str] = mapped_column(String(64))
    retention_class: Mapped[str] = mapped_column(String(64))
    source_class: Mapped[str] = mapped_column(String(64))
    authority_class: Mapped[str] = mapped_column(String(64))
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MultipartUploadRow(Base):
    __tablename__ = "multipart_uploads"
    upload_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    expected_sha256: Mapped[str] = mapped_column(String(64))
    expected_bytes: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(256))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="open")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MultipartChunkRow(Base):
    __tablename__ = "multipart_chunks"
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("multipart_uploads.upload_id", ondelete="CASCADE"), index=True)
    part_number: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    byte_count: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("upload_id", "part_number", name="uq_upload_part"),)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(128))
    resource_id: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(32))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str] = mapped_column(String(128))


class OperationRow(Base):
    __tablename__ = "operations"
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_type: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    input_manifest_hash: Mapped[str] = mapped_column(String(64))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    traceparent: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "operation_type", "idempotency_key", name="uq_operation_idempotency"),)


class OutboxEventRow(Base):
    __tablename__ = "outbox_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    schema_version: Mapped[str] = mapped_column(String(32))
    aggregate_type: Mapped[str] = mapped_column(String(128))
    aggregate_id: Mapped[str] = mapped_column(String(128))
    producer: Mapped[str] = mapped_column(String(128), default="unknown-legacy")
    classification: Mapped[str] = mapped_column(String(64), default="internal")
    actor_id: Mapped[str | None] = mapped_column(String(128))
    workload_identity: Mapped[str | None] = mapped_column(String(256))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)


class CoordinateFrameRow(Base):
    __tablename__ = "coordinate_frames"
    frame_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    parent_frame_id: Mapped[str | None] = mapped_column(String(64), index=True)
    semantic_type: Mapped[str] = mapped_column(String(128), default="local_cartesian")
    convention: Mapped[str] = mapped_column(String(128))
    units: Mapped[str] = mapped_column(String(32))
    unit_scale_to_meters: Mapped[float] = mapped_column(Float, default=1.0)
    original_units: Mapped[str] = mapped_column(String(64), default="meter")
    original_unit_scale_to_meters: Mapped[float] = mapped_column(Float, default=1.0)
    axis_convention: Mapped[str] = mapped_column(String(128), default="right_handed_y_up")
    axis_directions_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    handedness: Mapped[str] = mapped_column(String(16), default="right")
    origin_description: Mapped[str] = mapped_column(Text, default="capture_session_origin")
    gravity_alignment: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(128), default="platform")
    crs_identifier: Mapped[str | None] = mapped_column(String(256), index=True)
    vertical_datum: Mapped[str | None] = mapped_column(String(256))
    geodetic_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    transform_json: Mapped[list[list[float]] | None] = mapped_column(JSON)
    uncertainty_m: Mapped[float | None] = mapped_column(Float)
    supersedes_frame_id: Mapped[str | None] = mapped_column(String(64), index=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SpatialTransformRow(Base):
    __tablename__ = "spatial_transforms"
    transform_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    source_frame_id: Mapped[str] = mapped_column(String(64), index=True)
    target_frame_id: Mapped[str] = mapped_column(String(64), index=True)
    transform_type: Mapped[str] = mapped_column(String(16))
    matrix_json: Mapped[list[list[float]]] = mapped_column(JSON)
    declared_matrix_json: Mapped[list[list[float]]] = mapped_column(JSON)
    matrix_layout: Mapped[str] = mapped_column(String(32), default="row_major")
    multiplication_convention: Mapped[str] = mapped_column(String(64), default="column_vector_pre_multiply")
    direction: Mapped[str] = mapped_column(String(32), default="source_to_target")
    translation_units: Mapped[str] = mapped_column(String(32), default="meter")
    scale: Mapped[float] = mapped_column(Float, default=1.0)
    covariance_json: Mapped[list[list[float]] | None] = mapped_column(JSON)
    residual_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    uncertainty_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(64))
    authority_class: Mapped[str] = mapped_column(String(64))
    calibration_id: Mapped[str | None] = mapped_column(String(128), index=True)
    solver_run_id: Mapped[str | None] = mapped_column(String(128), index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    crs_pipeline: Mapped[str | None] = mapped_column(Text)
    grid_resources_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    supersedes_transform_id: Mapped[str | None] = mapped_column(String(64), index=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class GeometryAssetManifestRow(Base):
    __tablename__ = "geometry_asset_manifests"
    geometry_manifest_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    representation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(256))
    format: Mapped[str] = mapped_column(String(64))
    profile: Mapped[str] = mapped_column(String(128))
    format_version: Mapped[str] = mapped_column(String(64))
    coordinate_frame_id: Mapped[str] = mapped_column(String(64), index=True)
    units: Mapped[str] = mapped_column(String(32))
    bounds_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    counts_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    compression_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_run_id: Mapped[str] = mapped_column(String(128), index=True)
    quality_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    visual_content_classes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification: Mapped[str] = mapped_column(String(64), index=True)
    audience_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    viewer_compatibility_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    exporter_compatibility_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_state: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    rebuild_recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    truth_label: Mapped[str | None] = mapped_column(Text)
    supersedes_manifest_id: Mapped[str | None] = mapped_column(String(64), index=True)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "manifest_hash",
            name="uq_geometry_asset_manifest_scope_hash",
        ),
    )


class EvidenceRecordRow(Base):
    __tablename__ = "evidence_records"
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(128), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_by: Mapped[str] = mapped_column(String(128))
    device_or_tool: Mapped[str] = mapped_column(String(256))
    location_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    relevant_region_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    relevant_time_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    relevant_time_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    chain_of_custody_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    retention_class: Mapped[str] = mapped_column(String(64))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    access_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class AssertionRow(Base):
    __tablename__ = "assertions"
    assertion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    predicate: Mapped[str] = mapped_column(String(256), index=True)
    object_json: Mapped[Any] = mapped_column(JSON)
    source_class: Mapped[str] = mapped_column(String(64), index=True)
    authority_class: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    asserted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    author_id: Mapped[str | None] = mapped_column(String(128), index=True)
    producer_id: Mapped[str | None] = mapped_column(String(256), index=True)
    conflicts_with_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    supersedes_assertion_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class DerivationEventRow(Base):
    __tablename__ = "derivation_events"
    derivation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    activity_type: Mapped[str] = mapped_column(String(128), index=True)
    input_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_hashes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    algorithm_id: Mapped[str] = mapped_column(String(256), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(128))
    model_manifest_id: Mapped[str | None] = mapped_column(String(128), index=True)
    parameters_hash: Mapped[str] = mapped_column(String(64))
    environment_hash: Mapped[str] = mapped_column(String(64))
    code_commit: Mapped[str] = mapped_column(String(128))
    container_digest: Mapped[str | None] = mapped_column(String(128))
    output_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_hashes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    software_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    quality_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str | None] = mapped_column(String(128))
    workload_identity: Mapped[str | None] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    derivation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "request_hash",
            name="uq_derivation_event_scope_request",
        ),
    )


class SpatialAnnotationRow(Base):
    __tablename__ = "spatial_annotations"
    annotation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    coordinate_frame_id: Mapped[str] = mapped_column(String(64), index=True)
    support_type: Mapped[str] = mapped_column(String(64))
    support_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    position_json: Mapped[list[float] | None] = mapped_column(JSON)
    orientation_json: Mapped[list[float] | None] = mapped_column(JSON)
    normal_json: Mapped[list[float] | None] = mapped_column(JSON)
    uncertainty_m: Mapped[float] = mapped_column(Float, default=0.0)
    source_class: Mapped[str] = mapped_column(String(64))
    authority_class: Mapped[str] = mapped_column(String(64))
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lifecycle_state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    authored_from_representation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnchorRemapRow(Base):
    __tablename__ = "anchor_remaps"
    remap_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    source_representation_id: Mapped[str] = mapped_column(String(64), index=True)
    target_representation_id: Mapped[str] = mapped_column(String(64), index=True)
    resolved_annotation_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    unresolved_annotation_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    remap_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SceneTagRow(Base):
    __tablename__ = "scene_tags"
    tag_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    commit_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "scene_id", "name", name="uq_scene_tag"),)


class SceneCommitRow(Base):
    __tablename__ = "scene_commits"
    commit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    branch: Mapped[str] = mapped_column(String(128), default="main")
    parent_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    message: Mapped[str] = mapped_column(Text)
    semantic_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    root_manifest_hash: Mapped[str] = mapped_column(String(64), default="")
    field_visit_id: Mapped[str | None] = mapped_column(String(128), index=True)
    workflow_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    change_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_checks_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    signatures_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    review_state: Mapped[str] = mapped_column(String(32), default="unreviewed", index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    supersedes_commit_id: Mapped[str | None] = mapped_column(String(64))


class SceneBranchRow(Base):
    __tablename__ = "scene_branches"
    branch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    head_commit_id: Mapped[str] = mapped_column(String(64))
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "scene_id", "name", name="uq_scene_branch"),)


class SceneEntityRow(Base):
    __tablename__ = "scene_entities"
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(512))
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_class: Mapped[str] = mapped_column(String(64))
    authority_class: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stable_support_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepresentationAssetRow(Base):
    __tablename__ = "representations"
    representation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    coordinate_frame_id: Mapped[str] = mapped_column(String(64))
    source_class: Mapped[str] = mapped_column(String(64))
    authority_class: Mapped[str] = mapped_column(String(64))
    authority_ceiling: Mapped[str] = mapped_column(String(64), default="none")
    disposable: Mapped[bool] = mapped_column(Boolean, default=False)
    lossy: Mapped[bool] = mapped_column(Boolean, default=False)
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    prohibited_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    quality_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    support_map_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    format_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    derivation_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    information_loss_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    privacy_inheritance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dependencies_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    fallback_representation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), default="quarantined")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "operation_id", name="uq_representation_operation"),
    )


class RepresentationBindingRow(Base):
    __tablename__ = "representation_bindings"
    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    commit_id: Mapped[str] = mapped_column(String(64), index=True)
    representation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(64))
    coordinate_frame_id: Mapped[str] = mapped_column(String(64), default="")
    transform_json: Mapped[list[list[float]]] = mapped_column(JSON, default=lambda: [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
    authority_class: Mapped[str] = mapped_column(String(64), default="none")
    authority_ceiling: Mapped[str] = mapped_column(String(64), default="none")
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    audience_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    client_profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    published_by: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderManifestRow(Base):
    __tablename__ = "provider_manifests"
    provider_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(64))
    provider_class: Mapped[str] = mapped_column(String(64), default="local_open_source")
    source_url: Mapped[str] = mapped_column(Text)
    source_revision: Mapped[str] = mapped_column(String(128))
    image_digest: Mapped[str | None] = mapped_column(String(128))
    executable_digest: Mapped[str | None] = mapped_column(String(128))
    license_id: Mapped[str] = mapped_column(String(128))
    approval_state: Mapped[str] = mapped_column(String(32), default="denied")
    allowed_classifications_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_purposes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_regions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    deployments_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution_modes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_roles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_roles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    supported_formats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    coordinate_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reproducibility_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    security_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recovery_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_manifest_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    dependency_inventory_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    license_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    benchmark_profile_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    descriptor_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retention_days: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    manifest_signature: Mapped[str | None] = mapped_column(String(64))
    signed_by: Mapped[str | None] = mapped_column(String(128))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderManifestRevisionRow(Base):
    __tablename__ = "provider_manifest_revisions"
    manifest_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    provider_version: Mapped[str] = mapped_column(String(64), index=True)
    descriptor_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    manifest_signature: Mapped[str] = mapped_column(String(64))
    approval_state: Mapped[str] = mapped_column(String(32), index=True)
    signed_by: Mapped[str] = mapped_column(String(128))
    registered_by: Mapped[str] = mapped_column(String(128))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("provider_id", "provider_version", "manifest_hash", name="uq_provider_manifest_revision"),
    )


class ProviderPromotionRow(Base):
    __tablename__ = "provider_promotions"
    promotion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("provider_manifests.provider_id", ondelete="RESTRICT"), index=True)
    provider_version: Mapped[str] = mapped_column(String(64), index=True)
    provider_manifest_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    data_classifications_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    scene_classes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_roles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution_zones_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    hardware_profiles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    benchmark_evidence_hash: Mapped[str] = mapped_column(String(64))
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promotion_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signed_by: Mapped[str] = mapped_column(String(128))
    signature: Mapped[str] = mapped_column(String(64))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SpatialConversionRow(Base):
    __tablename__ = "spatial_conversions"
    conversion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("operations.operation_id", ondelete="RESTRICT"), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_revision_id: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_roles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_assets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reference_assets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    constraints_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_selector_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_id: Mapped[str] = mapped_column(ForeignKey("provider_manifests.provider_id", ondelete="RESTRICT"), index=True)
    provider_version: Mapped[str] = mapped_column(String(64))
    provider_manifest_hash: Mapped[str] = mapped_column(String(64))
    promotion_id: Mapped[str] = mapped_column(ForeignKey("provider_promotions.promotion_id", ondelete="RESTRICT"), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    admission_state: Mapped[str] = mapped_column(String(32), index=True)
    admission_decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    admission_decision_hash: Mapped[str] = mapped_column(String(64))
    resource_estimate_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    credential_claims_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    worker_lease_generation: Mapped[int] = mapped_column(Integer, default=1)
    worker_token_hash: Mapped[str | None] = mapped_column(String(64))
    worker_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_hash: Mapped[str | None] = mapped_column(String(64))
    cleanup_receipt_hash: Mapped[str | None] = mapped_column(String(64))
    candidate_representation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="admitted", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    requested_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_spatial_conversion_idempotency"),)


class ProviderProgressRow(Base):
    __tablename__ = "provider_progress"
    progress_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversion_id: Mapped[str] = mapped_column(ForeignKey("spatial_conversions.conversion_id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(128))
    completed_work_units: Mapped[float] = mapped_column(Float)
    total_work_units: Mapped[float | None] = mapped_column(Float)
    work_unit_name: Mapped[str] = mapped_column(String(64))
    resource_use_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    checkpoint_hash: Mapped[str | None] = mapped_column(String(64))
    estimated_output_bytes: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("conversion_id", "sequence", name="uq_provider_progress_sequence"),)


class IntendedUseValidationRow(Base):
    __tablename__ = "intended_use_validations"
    validation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    conversion_id: Mapped[str] = mapped_column(ForeignKey("spatial_conversions.conversion_id", ondelete="RESTRICT"), index=True)
    representation_id: Mapped[str] = mapped_column(ForeignKey("representations.representation_id", ondelete="RESTRICT"), index=True)
    intended_use: Mapped[str] = mapped_column(String(128), index=True)
    profile_id: Mapped[str] = mapped_column(String(128))
    profile_version: Mapped[str] = mapped_column(String(64))
    validator_id: Mapped[str] = mapped_column(String(128))
    validator_manifest_hash: Mapped[str] = mapped_column(String(64))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    coverage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    topology_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    coordinate_validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    behavior_validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    passed: Mapped[bool] = mapped_column(Boolean)
    candidate_snapshot_hash: Mapped[str] = mapped_column(String(64))
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    validation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("representation_id", "intended_use", "profile_id", "profile_version", name="uq_representation_use_validation"),)


class ManualProviderTransferRow(Base):
    __tablename__ = "manual_provider_transfers"
    transfer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    conversion_id: Mapped[str] = mapped_column(ForeignKey("spatial_conversions.conversion_id", ondelete="RESTRICT"), index=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    outbound_manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outbound_manifest_hash: Mapped[str] = mapped_column(String(64))
    policy_decision_hash: Mapped[str] = mapped_column(String(64))
    one_time_code_hash: Mapped[str] = mapped_column(String(64))
    receipt_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    receipt_hash: Mapped[str | None] = mapped_column(String(64))
    returned_outputs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), default="exported", index=True)
    exported_by: Mapped[str] = mapped_column(String(128))
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    returned_by: Mapped[str | None] = mapped_column(String(128))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HybridSceneViewRow(Base):
    __tablename__ = "hybrid_scene_views"
    view_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_revision_id: Mapped[str] = mapped_column(String(64), index=True)
    principal_id: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    audience: Mapped[str] = mapped_column(String(64), index=True)
    device_profile: Mapped[str] = mapped_column(String(128))
    time_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    bindings_json: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    excluded_summary_json: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    interaction_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    truth_labels_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    streaming_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class RepresentationFamilyRow(Base):
    __tablename__ = "representation_families"
    family_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(64), index=True)
    coordinate_frame_id: Mapped[str] = mapped_column(String(64))
    tile_scheme_id: Mapped[str] = mapped_column(String(128))
    lods_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    seam_validation_report_id: Mapped[str | None] = mapped_column(String(128))
    fallback_representation_id: Mapped[str | None] = mapped_column(String(64))
    family_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class InteractionProfileRow(Base):
    __tablename__ = "interaction_profiles"
    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_type: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[str] = mapped_column(String(64))
    actor_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    limits_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    behavior_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    safety_claims_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    validator_manifest_hash: Mapped[str] = mapped_column(String(64))
    validation_evidence_hash: Mapped[str] = mapped_column(String(64))
    manifest_signature: Mapped[str] = mapped_column(String(64))
    signed_by: Mapped[str] = mapped_column(String(128))
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ModelManifestRow(Base):
    __tablename__ = "model_manifests"
    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(64))
    checkpoint_hash: Mapped[str] = mapped_column(String(128))
    code_revision: Mapped[str] = mapped_column(String(128))
    code_license: Mapped[str] = mapped_column(String(128))
    weights_license: Mapped[str] = mapped_column(String(128))
    dataset_terms_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_terms: Mapped[str] = mapped_column(Text, default="unknown")
    approval_state: Mapped[str] = mapped_column(String(32), default="denied")
    commercial_use: Mapped[bool] = mapped_column(Boolean, default=False)
    # Retained for append-only compatibility with v1.0 rows. New manifests also
    # persist the canonical permitted_uses_json field added in migration 0008.
    allowed_purposes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(32))
    provider: Mapped[str | None] = mapped_column(String(256))
    model_name: Mapped[str | None] = mapped_column(String(256))
    revision: Mapped[str | None] = mapped_column(String(128))
    source_urls_json: Mapped[list[str] | None] = mapped_column(JSON)
    license_documents_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    allowed_classifications_json: Mapped[list[str] | None] = mapped_column(JSON)
    permitted_uses_json: Mapped[list[str] | None] = mapped_column(JSON)
    prohibited_uses_json: Mapped[list[str] | None] = mapped_column(JSON)
    geographic_restrictions_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    customer_restrictions_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    allowed_deployments_json: Mapped[list[str] | None] = mapped_column(JSON)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest_signature: Mapped[str | None] = mapped_column(String(64))
    signed_by: Mapped[str | None] = mapped_column(String(128))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MeasurementRow(Base):
    __tablename__ = "measurements"
    measurement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    measurement_type: Mapped[str] = mapped_column(String(64), default="distance")
    geometry_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_method: Mapped[str] = mapped_column(String(128), default="unspecified")
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    coordinate_frame_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    permitted_uses_json: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["reference"])
    state: Mapped[str] = mapped_column(String(32), default="measured", index=True)
    supersedes_measurement_id: Mapped[str | None] = mapped_column(String(64), index=True)
    originating_representation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    interaction_hit_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resolved_metric_evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    uncertainty: Mapped[float] = mapped_column(Float)
    source_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    calibration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verifier_id: Mapped[str | None] = mapped_column(String(128))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority_class: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ConsentGrantRow(Base):
    __tablename__ = "consent_grants"
    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    granted_by: Mapped[str] = mapped_column(String(128))
    purposes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    audiences_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    scopes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    derivative_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SearchDocumentRow(Base):
    __tablename__ = "search_documents"
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    terms_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    embedding_json: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model_manifest_id: Mapped[str | None] = mapped_column(String(128), index=True)
    embedding_source_region_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    spatial_bounds_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    spatial_frame_id: Mapped[str | None] = mapped_column(String(64), index=True)
    floor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    room_id: Mapped[str | None] = mapped_column(String(64), index=True)
    temporal_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    temporal_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_class: Mapped[str] = mapped_column(String(64), default="observed", index=True)
    authority_class: Mapped[str] = mapped_column(String(64), default="evidence", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    workflow_status: Mapped[str | None] = mapped_column(String(128), index=True)
    relationships_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    classification: Mapped[str] = mapped_column(String(64), default="internal", index=True)
    source_sequence: Mapped[int] = mapped_column(Integer, default=0)
    index_sequence: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    scene_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))


class SavedQueryRow(Base):
    __tablename__ = "saved_queries"
    saved_query_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    schema_version: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    author_id: Mapped[str] = mapped_column(String(128), index=True)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expected_result_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    supersedes_saved_query_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "name", "version", name="uq_saved_query_version"),
    )


class AgentProposalRow(Base):
    __tablename__ = "agent_proposals"
    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    input_hash: Mapped[str] = mapped_column(String(64))
    proposal_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32), default="review_required", index=True)
    created_by: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_agent_proposal_idempotency"),
    )


class ExportRow(Base):
    __tablename__ = "exports"
    export_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    format: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="created")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    root_hash: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class NotificationRow(Base):
    __tablename__ = "notifications"
    notification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_id: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    template_id: Mapped[str] = mapped_column(String(128))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class CollaborationCommentRow(Base):
    __tablename__ = "collaboration_comments"
    comment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    anchor_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64))
    author_id: Mapped[str] = mapped_column(String(128))
    supersedes_comment_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class CollaborationTaskRow(Base):
    __tablename__ = "collaboration_tasks"
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="open")
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    assignee_id: Mapped[str | None] = mapped_column(String(128))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ConstructionRecordRow(Base):
    __tablename__ = "construction_records"
    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    record_type: Mapped[str] = mapped_column(String(128), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(64))
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryRecordRow(Base):
    __tablename__ = "memory_records"
    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    record_type: Mapped[str] = mapped_column(String(128), index=True)
    subject_id: Mapped[str | None] = mapped_column(String(128), index=True)
    related_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_class: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    evidence_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    audience: Mapped[str] = mapped_column(String(32))
    generated_lineage_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetentionRuleRow(Base):
    __tablename__ = "retention_rules"
    retention_rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    retention_class: Mapped[str] = mapped_column(String(64))
    policy_source: Mapped[str] = mapped_column(Text)
    minimum_days: Mapped[int] = mapped_column(Integer)
    maximum_days: Mapped[int | None] = mapped_column(Integer)
    backup_expiry_days: Mapped[int] = mapped_column(Integer)
    deletion_mode: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "retention_class", "version", name="uq_retention_rule_version"),)


class LegalHoldRow(Base):
    __tablename__ = "legal_holds"
    hold_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    resource_type: Mapped[str] = mapped_column(String(128))
    resource_id: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    authority_reference: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default="active")
    placed_by: Mapped[str] = mapped_column(String(128))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    released_by: Mapped[str | None] = mapped_column(String(128))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_legal_hold_resource", "tenant_id", "project_id", "resource_type", "resource_id"),)


class BackupRunRow(Base):
    __tablename__ = "backup_runs"
    backup_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    profile: Mapped[str] = mapped_column(String(64))
    backup_path: Mapped[str] = mapped_column(Text)
    root_hash: Mapped[str] = mapped_column(String(64))
    schema_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(64), default="created")
    created_by: Mapped[str] = mapped_column(String(128))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restore_rehearsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionRequestRow(Base):
    __tablename__ = "deletion_requests"
    deletion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(128))
    resource_id: Mapped[str] = mapped_column(String(128))
    dry_run_report: Mapped[dict[str, Any]] = mapped_column(JSON)
    backup_reference: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    executed_by: Mapped[str | None] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionEvidenceRow(Base):
    __tablename__ = "deletion_evidence"
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deletion_id: Mapped[str] = mapped_column(ForeignKey("deletion_requests.deletion_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(128))
    resource_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    affected_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    key_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    residual_locations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    backup_expiry_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class KeyRotationRow(Base):
    __tablename__ = "key_rotations"
    rotation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    old_key_id: Mapped[str] = mapped_column(String(128))
    new_key_id: Mapped[str] = mapped_column(String(128))
    object_count: Mapped[int] = mapped_column(Integer)
    ciphertext_unchanged: Mapped[bool] = mapped_column(Boolean)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32))
    rotated_by: Mapped[str] = mapped_column(String(128))
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    retired_key_destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuotaPolicyRow(Base):
    __tablename__ = "quota_policies"
    quota_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(32))
    period_seconds: Mapped[int] = mapped_column(Integer)
    soft_limit: Mapped[float] = mapped_column(Float)
    hard_limit: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "resource_type", name="uq_quota_scope_resource"),)


class UsageLedgerRow(Base):
    __tablename__ = "usage_ledger"
    usage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    unit_cost: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    price_source_version: Mapped[str] = mapped_column(String(128))
    estimated: Mapped[bool] = mapped_column(Boolean)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class Database:
    def __init__(self, url: str, *, create: bool = False) -> None:
        self.url = url
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            path = self.sqlite_path
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, future=True, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        if create:
            Base.metadata.create_all(self.engine)

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.url.startswith(prefix):
            return None
        raw = self.url[len(prefix) :]
        return Path(raw).resolve()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
