from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine, event
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
    __table_args__ = (
        Index(
            "uq_scene_commit_workflow_event",
            "tenant_id",
            "project_id",
            "workflow_event_id",
            unique=True,
        ),
    )


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


class ViewerSessionRow(Base):
    __tablename__ = "viewer_sessions"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    principal_id: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    audience: Mapped[str] = mapped_column(String(64), index=True)
    publication_class: Mapped[str] = mapped_column(String(32), default="working", index=True)
    scene_commit_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    saved_hybrid_views_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    device_profile: Mapped[str] = mapped_column(String(128))
    intended_uses_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    spatial_region_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    camera_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    navigation_mode: Mapped[str] = mapped_column(String(32))
    layers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    clipping_planes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    section_box_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    selected_entity_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeline_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    redaction_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    accessibility_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    comparison_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    session_hash: Mapped[str] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_session_id: Mapped[str | None] = mapped_column(ForeignKey("viewer_sessions.session_id", ondelete="RESTRICT"), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "principal_id", "idempotency_key", name="uq_viewer_session_idempotency"),
    )


class ViewerSessionReplayRow(Base):
    __tablename__ = "viewer_session_replays"
    replay_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("viewer_sessions.session_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    principal_id: Mapped[str] = mapped_column(String(128), index=True)
    issued_views_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    exact: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    replay_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class TemporalComparisonRow(Base):
    __tablename__ = "temporal_comparisons"
    comparison_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    baseline_commit_id: Mapped[str] = mapped_column(ForeignKey("scene_commits.commit_id", ondelete="RESTRICT"), index=True)
    candidate_commit_id: Mapped[str] = mapped_column(ForeignKey("scene_commits.commit_id", ondelete="RESTRICT"), index=True)
    viewer_session_id: Mapped[str | None] = mapped_column(ForeignKey("viewer_sessions.session_id", ondelete="RESTRICT"), index=True)
    comparable_region_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    registration_quality_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    algorithm_id: Mapped[str] = mapped_column(String(128), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(64))
    executable_hash: Mapped[str] = mapped_column(String(64))
    parameters_hash: Mapped[str] = mapped_column(String(64))
    observed_coverage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    comparison_hash: Mapped[str] = mapped_column(String(64), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_temporal_comparison_idempotency"),
    )


class ChangeCandidateRow(Base):
    __tablename__ = "change_candidates"
    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("temporal_comparisons.comparison_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    change_class: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    region_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    coverage_status: Mapped[str] = mapped_column(String(32))
    difference_causes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    suppression_reason: Mapped[str | None] = mapped_column(String(256))
    candidate_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ChangeReviewRow(Base):
    __tablename__ = "change_reviews"
    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("temporal_comparisons.comparison_id", ondelete="RESTRICT"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("change_candidates.candidate_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(128), index=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    review_hash: Mapped[str] = mapped_column(String(64), unique=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "reviewer_id", "idempotency_key", name="uq_change_review_idempotency"),
    )


class SemanticChangeEventRow(Base):
    __tablename__ = "semantic_change_events"
    semantic_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("temporal_comparisons.comparison_id", ondelete="RESTRICT"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("change_candidates.candidate_id", ondelete="RESTRICT"), index=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("change_reviews.review_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_commit_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    applied_commit_id: Mapped[str | None] = mapped_column(ForeignKey("scene_commits.commit_id", ondelete="RESTRICT"), index=True)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ChangeBenchmarkRow(Base):
    __tablename__ = "change_benchmarks"
    benchmark_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    algorithm_id: Mapped[str] = mapped_column(String(128), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(64))
    executable_hash: Mapped[str] = mapped_column(String(64))
    benchmark_profile: Mapped[str] = mapped_column(String(128))
    fixture_root_hash: Mapped[str] = mapped_column(String(64))
    metrics_by_class_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    environment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    benchmark_hash: Mapped[str] = mapped_column(String(64), unique=True)
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
    usage_scope: Mapped[str] = mapped_column(String(32), default="local_internal")
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


class ConstructionSurveyRow(Base):
    __tablename__ = "construction_surveys"
    survey_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    objectives_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_place_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_system_types_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    sensitive_regions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    control_requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    measurement_requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    safety_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deliverables_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    baseline_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    return_visit_of_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    accepted_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    completion_hash: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_survey_idempotency"),
    )


class ConstructionVisitRow(Base):
    __tablename__ = "construction_visits"
    visit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    survey_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    exact_prior_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capture_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    checklist_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    detail_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    inaccessible_regions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    coverage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tracking_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    registration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    controls_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    inventory_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    unresolved_questions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    privacy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="in_progress", index=True)
    report_hash: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_visit_idempotency"),
    )


class ConstructionDocumentRevisionRow(Base):
    __tablename__ = "construction_document_revisions"
    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stable_document_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    revision: Mapped[str] = mapped_column(String(64))
    issue_date: Mapped[str] = mapped_column(String(64))
    issuer: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer)
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(64), index=True)
    page_regions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    spatial_links_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    extraction_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "stable_document_id", "revision", name="uq_construction_document_revision"),
    )


class ConstructionIssueRow(Base):
    __tablename__ = "construction_issues"
    issue_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    place_id: Mapped[str | None] = mapped_column(String(64), index=True)
    observed_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reporter_id: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(32), index=True)
    responsible_party: Mapped[str | None] = mapped_column(String(256))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="open", index=True)
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    history_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    residual_limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_issue_idempotency"),
    )


class ConstructionCommissioningRow(Base):
    __tablename__ = "construction_commissioning_runs"
    commissioning_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    system_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    issue_id: Mapped[str | None] = mapped_column(String(64), index=True)
    procedure_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prerequisites_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    participants_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    instruments_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    attachments_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    results_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retest_of_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="recorded", index=True)
    accepted_by: Mapped[str | None] = mapped_column(String(128))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_commissioning_idempotency"),
    )


class ConstructionInterchangeRow(Base):
    __tablename__ = "construction_interchanges"
    interchange_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(16), index=True)
    source_asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(64))
    units: Mapped[str | None] = mapped_column(String(32))
    crs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    owner_history_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    global_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    classifications_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    properties_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    relationships_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    geometry_conversion_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    unsupported_constructs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    alignment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mappings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    truth_labels_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_interchange_idempotency"),
    )


class ConstructionHandoffRow(Base):
    __tablename__ = "construction_handoffs"
    handoff_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    accepted_scene_commit_id: Mapped[str] = mapped_column(String(64), index=True)
    inventory_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verified_attributes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    documents_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    tests_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warranties_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    training_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    open_issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    exclusions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    exports_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    representation_manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    audience_profiles_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    offline_viewer_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    checksums_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    root_hash: Mapped[str | None] = mapped_column(String(64))
    package_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_construction_handoff_idempotency"),
    )


class ConstructionRestrictedExportApprovalRow(Base):
    __tablename__ = "construction_restricted_export_approvals"
    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    classification: Mapped[str] = mapped_column(String(64), index=True)
    audience: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    approver_id: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    approval_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "request_hash",
            "approver_id",
            name="uq_construction_restricted_export_approval",
        ),
    )


class ConstructionRecordVerificationRow(Base):
    __tablename__ = "construction_record_verifications"
    verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    record_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    verifier_id: Mapped[str] = mapped_column(String(128), index=True)
    prior_state: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(128))
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    exclusions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    signature_asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    verification_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "idempotency_key",
            name="uq_construction_record_verification_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "record_id",
            name="uq_construction_record_verification_record",
        ),
    )


class LiveForeverRecordReviewRow(Base):
    __tablename__ = "liveforever_record_reviews"
    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    source_record_id: Mapped[str] = mapped_column(String(64), index=True)
    reviewed_record_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    reviewer_id: Mapped[str] = mapped_column(String(128), index=True)
    target_source_class: Mapped[str] = mapped_column(String(64), index=True)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    review_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "idempotency_key",
            name="uq_liveforever_record_review_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "reviewed_record_id",
            name="uq_liveforever_record_review_result",
        ),
    )


class LiveForeverGovernanceRow(Base):
    __tablename__ = "liveforever_governance"
    governance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    record_type: Mapped[str] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    consent_grant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    grantor_id: Mapped[str] = mapped_column(String(128))
    authority_basis: Mapped[str] = mapped_column(String(128))
    data_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    purposes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    modalities_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    audiences_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    providers_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    geography_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posthumous_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    successor_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    dispute_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    freeze_high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_liveforever_governance_idempotency"),
    )


class LiveForeverInterviewRow(Base):
    __tablename__ = "liveforever_interviews"
    interview_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    participants_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    consent_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recording_state: Mapped[str] = mapped_column(String(32), index=True)
    source_media_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeline_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    device_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    environment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    interruptions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    question_lineage_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    pacing_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_liveforever_interview_idempotency"),
    )


class LiveForeverTranscriptSegmentRow(Base):
    __tablename__ = "liveforever_transcript_segments"
    segment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    segment_index: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    speaker_label: Mapped[str] = mapped_column(String(256))
    speaker_confidence: Mapped[float] = mapped_column(Float)
    original_text: Mapped[str] = mapped_column(Text)
    edited_text: Mapped[str | None] = mapped_column(Text)
    correction_history_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    private_marks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_media_id: Mapped[str] = mapped_column(String(64), index=True)
    spatial_anchor_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    followup_suggestions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    review_state: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("interview_id", "segment_index", name="uq_liveforever_transcript_segment_index"),
    )


class LiveForeverEditionRow(Base):
    __tablename__ = "liveforever_editions"
    edition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))
    audience_profile: Mapped[str] = mapped_column(String(32), index=True)
    record_revisions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    presentation_choices_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scene_commit_id: Mapped[str | None] = mapped_column(String(64), index=True)
    narrative_path_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    truth_legend_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    policy_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    supersedes_edition_id: Mapped[str | None] = mapped_column(String(64), index=True)
    root_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_liveforever_edition_idempotency"),
    )


class LiveForeverDerivativeRow(Base):
    __tablename__ = "liveforever_derivatives"
    derivative_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    derivative_type: Mapped[str] = mapped_column(String(64), index=True)
    source_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    subject_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    consent_grant_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    audience: Mapped[str] = mapped_column(String(32), index=True)
    classification: Mapped[str] = mapped_column(String(64), index=True)
    retention_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    generation_lineage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    withdrawal_action: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_liveforever_derivative_idempotency"),
    )


class LiveForeverPreservationRow(Base):
    __tablename__ = "liveforever_preservation_releases"
    release_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    edition_id: Mapped[str] = mapped_column(String(64), index=True)
    originals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    technical_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rights_consent_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    transcripts_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    memory_graph_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scene_manifests_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    open_assets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    checksums_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    human_guide_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    offline_fallback_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fixity_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    replicas_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    format_migrations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    succession_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    shutdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    package_path: Mapped[str | None] = mapped_column(Text)
    root_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_liveforever_preservation_idempotency"),
    )


class ThreatManifestRow(Base):
    __tablename__ = "threat_manifests"
    threat_manifest_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32), index=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    review_trigger: Mapped[str] = mapped_column(String(128))
    owner: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    supersedes_manifest_id: Mapped[str | None] = mapped_column(String(64), index=True)
    __table_args__ = (UniqueConstraint("scope", "version", name="uq_threat_manifest_scope_version"),)


class PrivilegedAccessGrantRow(Base):
    __tablename__ = "privileged_access_grants"
    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    actions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    resource_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    purpose: Mapped[str] = mapped_column(String(128))
    mfa_method: Mapped[str] = mapped_column(String(64))
    mfa_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))
    __table_args__ = (UniqueConstraint("tenant_id", "request_hash", name="uq_privileged_access_request"),)


class WorkloadIdentityGrantRow(Base):
    __tablename__ = "workload_identity_grants"
    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    workload_id: Mapped[str] = mapped_column(String(128), index=True)
    audience: Mapped[str] = mapped_column(String(256), index=True)
    scopes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    purpose: Mapped[str] = mapped_column(String(128))
    token_jti: Mapped[str] = mapped_column(String(64), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    issued_by: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "request_hash", name="uq_workload_identity_request"),)


class KeyScopeRow(Base):
    __tablename__ = "key_scopes"
    key_scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    person_id: Mapped[str | None] = mapped_column(String(128), index=True)
    key_id: Mapped[str] = mapped_column(String(128), unique=True)
    backend: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), index=True)
    recovery_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scope_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    rotated_from_key_id: Mapped[str | None] = mapped_column(String(128))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KeyAccessEventRow(Base):
    __tablename__ = "key_access_events"
    key_access_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    key_scope_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_or_workload: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    resource_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)


class PrivacyInventoryRow(Base):
    __tablename__ = "privacy_inventory"
    privacy_inventory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    data_category: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    legal_basis: Mapped[str] = mapped_column(String(128))
    consent_basis: Mapped[str | None] = mapped_column(String(128))
    processors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    residency_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retention_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    security_controls_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rights_workflow_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    classification: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    supersedes_inventory_id: Mapped[str | None] = mapped_column(String(64), index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "data_category", "purpose", "version", name="uq_privacy_inventory_version"),)


class PrivacyImpactAssessmentRow(Base):
    __tablename__ = "privacy_impact_assessments"
    assessment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    change_type: Mapped[str] = mapped_column(String(64), index=True)
    change_reference: Mapped[str] = mapped_column(String(256))
    purpose: Mapped[str] = mapped_column(String(128))
    data_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    processors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    risks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    controls_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    residual_risk: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    request_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class PrivacyRightsRequestRow(Base):
    __tablename__ = "privacy_rights_requests"
    rights_request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    request_type: Mapped[str] = mapped_column(String(64), index=True)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    verified_by: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    response_manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_hash: Mapped[str] = mapped_column(String(64), unique=True)


class SecurityIncidentRow(Base):
    __tablename__ = "security_incidents"
    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    incident_type: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    affected_subjects_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_resources_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    containment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notification_decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    incident_hash: Mapped[str] = mapped_column(String(64), unique=True)


class AuditVerificationRow(Base):
    __tablename__ = "audit_verifications"
    audit_verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_count: Mapped[int] = mapped_column(Integer)
    valid: Mapped[bool] = mapped_column(Boolean)
    head_hash: Mapped[str] = mapped_column(String(64))
    referenced_manifests_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verifier_id: Mapped[str] = mapped_column(String(128))
    report_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SupplyChainReleaseRow(Base):
    __tablename__ = "supply_chain_releases"
    release_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    source_commit: Mapped[str] = mapped_column(String(64))
    source_root: Mapped[str] = mapped_column(String(64))
    component_manifests_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rollback_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    environment_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    emergency_patch: Mapped[bool] = mapped_column(Boolean, default=False)
    retrospective_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), index=True)
    signed_by: Mapped[str] = mapped_column(String(128))
    signature: Mapped[str] = mapped_column(String(128))
    release_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderGovernanceExceptionRow(Base):
    __tablename__ = "provider_governance_exceptions"
    exception_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    purpose: Mapped[str] = mapped_column(String(128))
    prohibited_waivers_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved_by: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exception_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class CacheInvalidationRow(Base):
    __tablename__ = "cache_invalidations"
    invalidation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(String(128))
    targets_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidation_hash: Mapped[str] = mapped_column(String(64), unique=True)


class TransportVerificationRow(Base):
    __tablename__ = "transport_verifications"
    transport_verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    environment: Mapped[str] = mapped_column(String(64), index=True)
    endpoint: Mapped[str] = mapped_column(String(512))
    protocol: Mapped[str] = mapped_column(String(64))
    minimum_tls_version: Mapped[str] = mapped_column(String(32))
    certificate_validated: Mapped[bool] = mapped_column(Boolean)
    channel_authentication: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), index=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verification_hash: Mapped[str] = mapped_column(String(64), unique=True)
    verified_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class CaptureFinalizationAuditRow(Base):
    __tablename__ = "capture_finalization_audits"
    capture_finalization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    capture_id: Mapped[str] = mapped_column(String(128), index=True)
    package_root_hash: Mapped[str] = mapped_column(String(64), index=True)
    archive_sha256: Mapped[str] = mapped_column(String(64))
    device_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    app_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    signer_id: Mapped[str] = mapped_column(String(128))
    verification_result: Mapped[str] = mapped_column(String(32), index=True)
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    record_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ImmersiveSafetyDecisionRow(Base):
    __tablename__ = "immersive_safety_decisions"
    safety_decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    profile_hash: Mapped[str] = mapped_column(String(64), index=True)
    checks_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    disabled_modes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    fallback_mode: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), index=True)
    decision_hash: Mapped[str] = mapped_column(String(64), unique=True)
    decided_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ProviderOutputValidationRow(Base):
    __tablename__ = "provider_output_validations"
    output_validation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(128), index=True)
    operation_id: Mapped[str] = mapped_column(String(64), index=True)
    output_sha256: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(256))
    byte_count: Mapped[int] = mapped_column(BigInteger)
    validations_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), index=True)
    validation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    validated_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


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


class TelemetryRecordRow(Base):
    __tablename__ = "telemetry_records"
    telemetry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    telemetry_type: Mapped[str] = mapped_column(String(32), index=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    release: Mapped[str] = mapped_column(String(128))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    route_template: Mapped[str | None] = mapped_column(String(256), index=True)
    stage: Mapped[str | None] = mapped_column(String(64), index=True)
    model_id: Mapped[str | None] = mapped_column(String(128), index=True)
    checkpoint_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    capture_profile: Mapped[str | None] = mapped_column(String(128), index=True)
    hardware_profile: Mapped[str | None] = mapped_column(String(128), index=True)
    execution_profile: Mapped[str | None] = mapped_column(String(64), index=True)
    queue_class: Mapped[str | None] = mapped_column(String(64), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    outcome: Mapped[str] = mapped_column(String(64), index=True)
    stable_error_code: Mapped[str | None] = mapped_column(String(128), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    labels_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, index=True)
    __table_args__ = (
        Index("ix_telemetry_scope_time", "tenant_id", "project_id", "created_at"),
        Index("ix_telemetry_correlation", "tenant_id", "project_id", "correlation_id"),
    )


class SLODefinitionRow(Base):
    __tablename__ = "slo_definitions"
    slo_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    dimensions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    indicator_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    objective: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float] = mapped_column(Float)
    window_seconds: Mapped[int] = mapped_column(Integer)
    budget_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    degradation_behavior: Mapped[str] = mapped_column(String(256))
    evidence_class: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    definition_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "name", "version", name="uq_slo_scope_name_version"),)


class SLOMeasurementRow(Base):
    __tablename__ = "slo_measurements"
    measurement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slo_id: Mapped[str] = mapped_column(ForeignKey("slo_definitions.slo_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    numerator: Mapped[float] = mapped_column(Float)
    denominator: Mapped[float] = mapped_column(Float)
    observed_value: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))
    dimensions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_profile: Mapped[str] = mapped_column(String(128))
    source_manifest_hash: Mapped[str] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class PerformanceBudgetRow(Base):
    __tablename__ = "performance_budgets"
    performance_budget_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    profile_type: Mapped[str] = mapped_column(String(32), index=True)
    profile_name: Mapped[str] = mapped_column(String(128), index=True)
    input_class_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hardware_profile: Mapped[str] = mapped_column(String(128), index=True)
    execution_profile: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str | None] = mapped_column(String(128), index=True)
    checkpoint_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    queue_class: Mapped[str | None] = mapped_column(String(64), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), index=True)
    percentile: Mapped[float] = mapped_column(Float)
    warm_state: Mapped[str] = mapped_column(String(16))
    concurrency: Mapped[int] = mapped_column(Integer)
    budgets_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    degradation_behavior: Mapped[str] = mapped_column(String(256))
    evidence_class: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(64))
    budget_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "profile_type", "profile_name", "version", name="uq_perf_budget_scope_profile_version"),)


class ResilienceProfileRow(Base):
    __tablename__ = "resilience_profiles"
    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    component: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(128))
    blast_radius: Mapped[str] = mapped_column(String(64))
    retry_safety: Mapped[str] = mapped_column(String(64))
    recovery_point_seconds: Mapped[int] = mapped_column(Integer)
    recovery_time_seconds: Mapped[int] = mapped_column(Integer)
    degraded_behavior_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dependencies_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    profile_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("component", "version", name="uq_resilience_component_version"),)


class ComputeProfileRow(Base):
    __tablename__ = "compute_profiles"
    compute_profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    resolution: Mapped[str] = mapped_column(String(64))
    dtype: Mapped[str] = mapped_column(String(32))
    backend: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(128))
    checkpoint_hash: Mapped[str] = mapped_column(String(64))
    window_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    memory_limit_mb: Mapped[int] = mapped_column(Integer)
    timeout_seconds: Mapped[int] = mapped_column(Integer)
    output_class: Mapped[str] = mapped_column(String(64))
    quality_tier: Mapped[str] = mapped_column(String(64))
    cuda_version: Mapped[str | None] = mapped_column(String(64))
    driver_constraint: Mapped[str | None] = mapped_column(String(128))
    container_digest: Mapped[str] = mapped_column(String(160))
    tenant_isolation: Mapped[str] = mapped_column(String(64))
    oom_fallback_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expected_runtime_seconds: Mapped[float] = mapped_column(Float)
    peak_vram_mb: Mapped[int] = mapped_column(Integer)
    peak_ram_mb: Mapped[int] = mapped_column(Integer)
    cost_stage_weights_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("name", "revision", name="uq_compute_profile_revision"),)


class PriceCatalogRow(Base):
    __tablename__ = "price_catalogs"
    price_catalog_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    version: Mapped[str] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prices_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_reference: Mapped[str] = mapped_column(String(512))
    source_hash: Mapped[str] = mapped_column(String(64))
    supersedes_price_catalog_id: Mapped[str | None] = mapped_column(String(64), index=True)
    catalog_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_price_catalog_tenant_version"),)


class CostEstimateRow(Base):
    __tablename__ = "cost_estimates"
    estimate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    capture_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    compute_profile_id: Mapped[str] = mapped_column(ForeignKey("compute_profiles.compute_profile_id", ondelete="RESTRICT"), index=True)
    price_catalog_id: Mapped[str] = mapped_column(ForeignKey("price_catalogs.price_catalog_id", ondelete="RESTRICT"), index=True)
    input_class_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stage_estimates_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    total_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    estimate_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "run_id", name="uq_cost_estimate_run"),)


class ActualCostRow(Base):
    __tablename__ = "actual_costs"
    actual_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    capture_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str | None] = mapped_column(String(128), index=True)
    checkpoint_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    price_catalog_id: Mapped[str] = mapped_column(ForeignKey("price_catalogs.price_catalog_id", ondelete="RESTRICT"), index=True)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    actual_hash: Mapped[str] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    recorded_by: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_actual_cost_idempotency"),)


class BudgetPolicyRow(Base):
    __tablename__ = "budget_policies"
    budget_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    period_seconds: Mapped[int] = mapped_column(Integer)
    soft_limit: Mapped[float] = mapped_column(Float)
    hard_limit: Mapped[float] = mapped_column(Float)
    concurrency_limit: Mapped[int] = mapped_column(Integer)
    storage_limit_bytes: Mapped[int] = mapped_column(BigInteger)
    retention_limit_days: Mapped[int] = mapped_column(Integer)
    anomaly_threshold: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class BudgetReservationRow(Base):
    __tablename__ = "budget_reservations"
    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("budget_policies.budget_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    estimate_id: Mapped[str] = mapped_column(ForeignKey("cost_estimates.estimate_id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_budget_reservation_idempotency"),)


class BudgetOverrideRow(Base):
    __tablename__ = "budget_overrides"
    override_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("budget_policies.budget_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    additional_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    override_hash: Mapped[str] = mapped_column(String(64), unique=True)
    approval_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))


class AnomalyAlertRow(Base):
    __tablename__ = "anomaly_alerts"
    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    metric_name: Mapped[str] = mapped_column(String(128))
    observed_value: Mapped[float] = mapped_column(Float)
    baseline_value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(32), default="open")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    alert_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(128))
    suppressed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppression_approved_by: Mapped[str | None] = mapped_column(String(128))


class QueueSnapshotRow(Base):
    __tablename__ = "queue_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    queue_class: Mapped[str] = mapped_column(String(64), index=True)
    depth: Mapped[int] = mapped_column(Integer)
    in_flight: Mapped[int] = mapped_column(Integer)
    retries: Mapped[int] = mapped_column(Integer)
    oldest_age_seconds: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    snapshot_hash: Mapped[str] = mapped_column(String(64), unique=True)


class CapacityPlanRow(Base):
    __tablename__ = "capacity_plans"
    capacity_plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    profile_name: Mapped[str] = mapped_column(String(128), index=True)
    measurement_window_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scene_minutes: Mapped[float] = mapped_column(Float)
    frames: Mapped[int] = mapped_column(BigInteger)
    area_m2: Mapped[float] = mapped_column(Float)
    peak_concurrency: Mapped[int] = mapped_column(Integer)
    headroom_ratio: Mapped[float] = mapped_column(Float)
    required_capacity_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_class: Mapped[str] = mapped_column(String(64))
    source_manifest_hash: Mapped[str] = mapped_column(String(64))
    plan_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class CostReconciliationRow(Base):
    __tablename__ = "cost_reconciliations"
    reconciliation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    estimate_id: Mapped[str] = mapped_column(String(64), index=True)
    actual_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    estimated_amount: Mapped[float] = mapped_column(Float)
    actual_amount: Mapped[float] = mapped_column(Float)
    delta_amount: Mapped[float] = mapped_column(Float)
    ratio: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    catalog_hashes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    reconciliation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "run_id", name="uq_cost_reconciliation_run"),)


class SupportAccessGrantRow(Base):
    __tablename__ = "support_access_grants"
    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    purpose: Mapped[str] = mapped_column(String(128))
    personnel_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approval_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class SupportBundleRow(Base):
    __tablename__ = "support_bundles"
    bundle_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("support_access_grants.grant_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    bundle_path: Mapped[str] = mapped_column(Text)
    zip_hash: Mapped[str] = mapped_column(String(64), unique=True)
    root_hash: Mapped[str] = mapped_column(String(64))
    scope_hash: Mapped[str] = mapped_column(String(64))
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="verified")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "scope_hash", name="uq_support_bundle_scope"),)


class SupportTicketRow(Base):
    __tablename__ = "support_tickets"
    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    risk_class: Mapped[str] = mapped_column(String(64))
    issue_type: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)
    affected_release: Mapped[str | None] = mapped_column(String(128))
    remediation_reference: Mapped[str | None] = mapped_column(String(512))
    retention_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    routed_role: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="open")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    resolved_by: Mapped[str | None] = mapped_column(String(128))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameDayExerciseRow(Base):
    __tablename__ = "game_day_exercises"
    exercise_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scenario: Mapped[str] = mapped_column(String(128))
    runbook_reference: Mapped[str] = mapped_column(String(512))
    participants_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    observations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    corrective_requirements_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    test_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))


class AfterActionReviewRow(Base):
    __tablename__ = "after_action_reviews"
    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    incident_reference: Mapped[str] = mapped_column(String(128), index=True)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    corrective_requirements_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    test_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    owner: Mapped[str] = mapped_column(String(128))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), default="open")
    review_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class IncidentActionRow(Base):
    __tablename__ = "incident_actions"
    incident_action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    incident_reference: Mapped[str] = mapped_column(String(128), index=True)
    runbook_reference: Mapped[str] = mapped_column(String(512))
    action_type: Mapped[str] = mapped_column(String(128), index=True)
    command_reference: Mapped[str | None] = mapped_column(String(512))
    decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_references_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rollback_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    communication_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sensitive_copy_created: Mapped[bool] = mapped_column(Boolean, default=False)
    action_hash: Mapped[str] = mapped_column(String(64), unique=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class DeploymentProfileRow(Base):
    __tablename__ = "deployment_profiles"
    deployment_profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(32), index=True)
    canonical_contracts_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    canonical_contracts_hash: Mapped[str] = mapped_column(String(64), index=True)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    service_images_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    infrastructure_versions_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    secret_references_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    network_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_limits_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    supported_regions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    degraded_modes_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_replacements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    production_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    profile_hash: Mapped[str] = mapped_column(String(64), unique=True)
    supersedes_profile_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("name", "revision", name="uq_deployment_profile_revision"),)


class ProjectDeploymentBindingRow(Base):
    __tablename__ = "project_deployment_bindings"
    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(ForeignKey("deployment_profiles.deployment_profile_id", ondelete="RESTRICT"), index=True)
    residency_policy_id: Mapped[str | None] = mapped_column(String(64), index=True)
    transfer_policy_id: Mapped[str | None] = mapped_column(String(64), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    feature_overrides_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cloud_dependencies_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    binding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "revision", name="uq_project_deployment_binding_revision"),)


class ResidencyPolicyRow(Base):
    __tablename__ = "residency_policies"
    residency_policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    home_region: Mapped[str] = mapped_column(String(64))
    allowed_regions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_modes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    asset_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    worker_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    default_action: Mapped[str] = mapped_column(String(16), default="deny")
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "revision", name="uq_residency_policy_revision"),)


class HybridTransferPolicyRow(Base):
    __tablename__ = "hybrid_transfer_policies"
    transfer_policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    source_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    destination_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    purpose: Mapped[str] = mapped_column(String(128))
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "revision", name="uq_transfer_policy_revision"),)


class EdgeNodeRow(Base):
    __tablename__ = "edge_nodes"
    edge_node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    node_identity: Mapped[str] = mapped_column(String(128), unique=True)
    identity_public_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    workload_identity_grant_id: Mapped[str] = mapped_column(String(64), unique=True)
    software_release: Mapped[str] = mapped_column(String(128))
    software_manifest_hash: Mapped[str] = mapped_column(String(64), index=True)
    software_signature: Mapped[str] = mapped_column(Text)
    signing_key_id: Mapped[str] = mapped_column(String(128))
    disk_encryption_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    region: Mapped[str] = mapped_column(String(64), index=True)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    health_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="enrolled", index=True)
    enrollment_hash: Mapped[str] = mapped_column(String(64), unique=True)
    enrolled_by: Mapped[str] = mapped_column(String(128))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(128))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(256))


class OfflineUpdatePackageRow(Base):
    __tablename__ = "offline_update_packages"
    update_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    from_release: Mapped[str] = mapped_column(String(128))
    to_release: Mapped[str] = mapped_column(String(128))
    bundle_hash: Mapped[str] = mapped_column(String(64), unique=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str] = mapped_column(Text)
    signing_key_id: Mapped[str] = mapped_column(String(128))
    rollback_bundle_hash: Mapped[str] = mapped_column(String(64))
    rollback_signature: Mapped[str] = mapped_column(Text)
    compatible_export_versions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), default="verified", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class EdgeUpdateApplicationRow(Base):
    __tablename__ = "edge_update_applications"
    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    edge_node_id: Mapped[str] = mapped_column(ForeignKey("edge_nodes.edge_node_id", ondelete="RESTRICT"), index=True)
    update_id: Mapped[str] = mapped_column(ForeignKey("offline_update_packages.update_id", ondelete="RESTRICT"), index=True)
    previous_release: Mapped[str] = mapped_column(String(128))
    target_release: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), default="applied", index=True)
    application_hash: Mapped[str] = mapped_column(String(64), unique=True)
    applied_by: Mapped[str] = mapped_column(String(128))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rollback_reason: Mapped[str | None] = mapped_column(String(256))
    __table_args__ = (UniqueConstraint("edge_node_id", "update_id", name="uq_edge_update_application"),)


class ProjectDeploymentMigrationRow(Base):
    __tablename__ = "project_deployment_migrations"
    migration_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    source_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    target_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    source_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64))
    target_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    target_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    migration_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_project_deployment_migration_idempotency"),)


class LocalUpgradeRehearsalRow(Base):
    __tablename__ = "local_upgrade_rehearsals"
    rehearsal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    from_release: Mapped[str] = mapped_column(String(128))
    to_release: Mapped[str] = mapped_column(String(128))
    from_schema: Mapped[str] = mapped_column(String(128))
    to_schema: Mapped[str] = mapped_column(String(128))
    pre_export_root: Mapped[str] = mapped_column(String(64))
    post_upgrade_export_root: Mapped[str] = mapped_column(String(64))
    rollback_export_root: Mapped[str] = mapped_column(String(64))
    object_store_root: Mapped[str] = mapped_column(String(64))
    queue_root: Mapped[str] = mapped_column(String(64))
    job_recovery_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rehearsal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="verified", index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class AutoscalingPolicyRow(Base):
    __tablename__ = "autoscaling_policies"
    autoscaling_policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    queue_class: Mapped[str] = mapped_column(String(64), index=True)
    revision: Mapped[str] = mapped_column(String(64))
    min_replicas: Mapped[int] = mapped_column(Integer)
    max_replicas: Mapped[int] = mapped_column(Integer)
    tenant_concurrency_limit: Mapped[int] = mapped_column(Integer)
    profile_quotas_json: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    global_budget_limit: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    dead_letter_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    restricted_egress: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "queue_class", "revision", name="uq_autoscaling_policy_revision"),)


class AutoscalingAdmissionRow(Base):
    __tablename__ = "autoscaling_admissions"
    admission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    autoscaling_policy_id: Mapped[str] = mapped_column(String(64), index=True)
    queue_class: Mapped[str] = mapped_column(String(64), index=True)
    capability_profile: Mapped[str] = mapped_column(String(128), index=True)
    current_replicas: Mapped[int] = mapped_column(Integer)
    requested_replicas: Mapped[int] = mapped_column(Integer)
    admitted_replicas: Mapped[int] = mapped_column(Integer)
    active_jobs: Mapped[int] = mapped_column(Integer)
    estimated_incremental_cost: Mapped[float] = mapped_column(Float)
    global_cost_after: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    reason_code: Mapped[str] = mapped_column(String(128), index=True)
    decision_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class AwsEnvironmentManifestRow(Base):
    __tablename__ = "aws_environment_manifests"
    aws_environment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    environment: Mapped[str] = mapped_column(String(32), index=True)
    account_boundary: Mapped[str] = mapped_column(String(128), index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    infrastructure_versions_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    network_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    database_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    object_store_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    queue_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    kms_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    secrets_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cdn_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    gpu_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    export_replacement_paths_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_class: Mapped[str] = mapped_column(String(64), default="synthetic_structural")
    production_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("environment", "account_boundary", "region", name="uq_aws_environment_boundary"),)


class CdnDerivativeDeliveryRow(Base):
    __tablename__ = "cdn_derivative_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    immutable_sha256: Mapped[str] = mapped_column(String(64))
    redaction_profile: Mapped[str] = mapped_column(String(128))
    redaction_hash: Mapped[str] = mapped_column(String(64))
    signed_authorization_required: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_origin: Mapped[bool] = mapped_column(Boolean, default=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    delivery_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class ProviderReplacementPathRow(Base):
    __tablename__ = "provider_replacement_paths"
    replacement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(128), index=True)
    service_class: Mapped[str] = mapped_column(String(128), index=True)
    export_format: Mapped[str] = mapped_column(String(128))
    adapter_contract: Mapped[str] = mapped_column(String(256))
    replacement_steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    data_exit_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    replacement_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (UniqueConstraint("provider_name", "service_class", name="uq_provider_replacement_path"),)


class DeploymentAdmissionRow(Base):
    __tablename__ = "deployment_admissions"
    admission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    admission_type: Mapped[str] = mapped_column(String(64), index=True)
    deployment_profile_id: Mapped[str | None] = mapped_column(String(64), index=True)
    region: Mapped[str | None] = mapped_column(String(64), index=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    reason_code: Mapped[str] = mapped_column(String(128), index=True)
    obligations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    decided_by: Mapped[str] = mapped_column(String(128))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class DeploymentDriftReportRow(Base):
    __tablename__ = "deployment_drift_reports"
    drift_report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    expected_hash: Mapped[str] = mapped_column(String(64))
    observed_hash: Mapped[str] = mapped_column(String(64))
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), index=True)
    report_hash: Mapped[str] = mapped_column(String(64), unique=True)
    observed_by: Mapped[str] = mapped_column(String(128))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class GracefulShutdownEvidenceRow(Base):
    __tablename__ = "graceful_shutdown_evidence"
    shutdown_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(128), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    operation_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    checkpoint_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    queue_before_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    queue_after_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recovery_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    shutdown_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="verified", index=True)
    recorded_by: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)



class RecoveryObjectiveRow(Base):
    __tablename__ = "recovery_objectives"
    recovery_objective_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    data_class: Mapped[str] = mapped_column(String(128), index=True)
    service_class: Mapped[str] = mapped_column(String(128), index=True)
    rpo_seconds: Mapped[int] = mapped_column(Integer)
    rto_seconds: Mapped[int] = mapped_column(Integer)
    degraded_behavior_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recovery_method_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_class: Mapped[str] = mapped_column(String(64), index=True)
    objective_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        Index("ix_recovery_objective_scope", "tenant_id", "project_id", "deployment_profile_id", "data_class", "service_class", "state"),
    )


class RecoveryPointRow(Base):
    __tablename__ = "recovery_points"
    recovery_point_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    evidence_class: Mapped[str] = mapped_column(String(64), index=True)
    database_profile: Mapped[str] = mapped_column(String(128))
    package_path: Mapped[str] = mapped_column(Text)
    package_sha256: Mapped[str] = mapped_column(String(64))
    package_root_hash: Mapped[str] = mapped_column(String(64))
    database_snapshot_path: Mapped[str | None] = mapped_column(Text)
    database_sha256: Mapped[str | None] = mapped_column(String(64))
    object_manifest_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    object_root_hash: Mapped[str] = mapped_column(String(64))
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    audit_heads_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    queue_manifest_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    key_references_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    requested_point_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    immutable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="created", index=True)
    recovery_point_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_recovery_point_scope_time", "tenant_id", "project_id", "snapshot_at", "state"),
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_recovery_point_idempotency"),
    )


class RestoreRunRow(Base):
    __tablename__ = "recovery_restore_runs"
    restore_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    recovery_point_id: Mapped[str] = mapped_column(String(64), index=True)
    target_tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    target_project_id: Mapped[str] = mapped_column(String(64), index=True)
    target_region: Mapped[str] = mapped_column(String(64), index=True)
    requested_point_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    restore_mode: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(64), default="requested", index=True)
    reconciliation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    writes_reopened: Mapped[bool] = mapped_column(Boolean, default=False)
    rpo_seconds_observed: Mapped[int | None] = mapped_column(Integer)
    rto_seconds_observed: Mapped[int | None] = mapped_column(Integer)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_recovery_restore_idempotency"),
    )


class KeyRecoveryExerciseRow(Base):
    __tablename__ = "key_recovery_exercises"
    key_recovery_exercise_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    key_scope_id: Mapped[str] = mapped_column(String(64), index=True)
    guardians_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    approvals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recovery_artifact_reference: Mapped[str] = mapped_column(String(512))
    root_key_exposed: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), index=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    exercise_hash: Mapped[str] = mapped_column(String(64), unique=True)
    exercised_by: Mapped[str] = mapped_column(String(128))
    exercised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class RetentionAssignmentRow(Base):
    __tablename__ = "retention_assignments"
    retention_assignment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(128), index=True)
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    retention_class: Mapped[str] = mapped_column(String(64), index=True)
    policy_source: Mapped[str] = mapped_column(Text)
    hold_status: Mapped[str] = mapped_column(String(32), index=True)
    deletion_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deletion_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    assignment_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    evaluated_by: Mapped[str] = mapped_column(String(128))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        Index("ix_retention_assignment_resource", "tenant_id", "project_id", "resource_type", "resource_id", "state"),
    )


class DeletionGraphRow(Base):
    __tablename__ = "deletion_dependency_graphs"
    deletion_graph_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), index=True)
    scope_id: Mapped[str] = mapped_column(String(128), index=True)
    nodes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    edges_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    holds_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    store_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    exceptions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    state: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    graph_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class PurgeRunRow(Base):
    __tablename__ = "purge_runs"
    purge_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    deletion_graph_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    store_results_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    unresolved_exceptions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    backup_expiry_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    cryptographic_erasure_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    executed_by: Mapped[str | None] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "idempotency_key", name="uq_purge_run_idempotency"),
    )


class BackupExpiryEvidenceRow(Base):
    __tablename__ = "backup_expiry_evidence"
    backup_expiry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    recovery_point_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    residuals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_by: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FixityCheckRow(Base):
    __tablename__ = "fixity_checks"
    fixity_check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    expected_sha256: Mapped[str] = mapped_column(String(64))
    observed_sha256: Mapped[str | None] = mapped_column(String(64))
    replicas_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    repair_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    check_hash: Mapped[str] = mapped_column(String(64), unique=True)
    checked_by: Mapped[str] = mapped_column(String(128))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class FormatMigrationEvidenceRow(Base):
    __tablename__ = "format_migration_evidence"
    format_migration_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    source_asset_id: Mapped[str] = mapped_column(String(64), index=True)
    derivative_asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    derivative_sha256: Mapped[str] = mapped_column(String(64))
    source_format: Mapped[str] = mapped_column(String(128))
    target_format: Mapped[str] = mapped_column(String(128))
    migration_tool_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    migration_hash: Mapped[str] = mapped_column(String(64), unique=True)
    migrated_by: Mapped[str] = mapped_column(String(128))
    migrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class TenantOffboardingRow(Base):
    __tablename__ = "tenant_offboarding_runs"
    offboarding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    export_manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retention_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deletion_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    offboarding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class RecoveryGameDayRow(Base):
    __tablename__ = "recovery_game_days"
    recovery_game_day_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    deployment_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    recovery_point_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario: Mapped[str] = mapped_column(String(128), index=True)
    affected_region: Mapped[str | None] = mapped_column(String(64))
    affected_services_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeline_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    portability_export_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence_class: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    game_day_hash: Mapped[str] = mapped_column(String(64), unique=True)
    conducted_by: Mapped[str] = mapped_column(String(128))
    conducted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class LegacyMigrationRunRow(Base):
    __tablename__ = "legacy_migration_runs"
    legacy_migration_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    source_release: Mapped[str] = mapped_column(String(64))
    target_release: Mapped[str] = mapped_column(String(64))
    source_backup_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_mappings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    quarantines_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    unresolved_anchors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    policy_diffs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rollback_evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    compatibility_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), index=True)
    report_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signed_report: Mapped[str] = mapped_column(Text)
    migrated_by: Mapped[str] = mapped_column(String(128))
    migrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)


class RecoveryLockRow(Base):
    __tablename__ = "recovery_locks"
    recovery_lock_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    lock_scope: Mapped[str] = mapped_column(String(128), index=True)
    operation_type: Mapped[str] = mapped_column(String(64))
    owner_operation_id: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "lock_scope", name="uq_recovery_lock_scope"),
    )



class QAAcceptanceCampaignRow(Base):
    __tablename__ = "qa_acceptance_campaigns"
    campaign_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), index=True)
    release_class: Mapped[str] = mapped_column(String(32), index=True)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    test_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    operating_envelope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    support_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recovery_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    campaign_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now, onupdate=db_now)
    __table_args__ = (
        UniqueConstraint("tenant_id", "checkpoint_id", name="uq_qa_campaign_checkpoint"),
    )


class QAScenarioResultRow(Base):
    __tablename__ = "qa_scenario_results"
    scenario_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("qa_acceptance_campaigns.campaign_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), index=True)
    scenario_type: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[str] = mapped_column(String(128), index=True)
    evidence_class: Mapped[str] = mapped_column(String(64), index=True)
    input_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    output_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    assertions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    environment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True)
    scenario_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_by: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "scenario_type", "profile", name="uq_qa_scenario_profile"),
    )


class QAGateResultRow(Base):
    __tablename__ = "qa_gate_results"
    gate_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("qa_acceptance_campaigns.campaign_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    gate_type: Mapped[str] = mapped_column(String(64), index=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_status: Mapped[str] = mapped_column(String(64), index=True)
    control_status: Mapped[str] = mapped_column(String(64), index=True)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    external_gap: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    gate_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_by: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "gate_type", name="uq_qa_gate_type"),
    )


class QAReleaseWaiverRow(Base):
    __tablename__ = "qa_release_waivers"
    waiver_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("qa_acceptance_campaigns.campaign_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    requirement_id: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[str] = mapped_column(String(8), index=True)
    reason: Mapped[str] = mapped_column(Text)
    compensating_control_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    owner: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    waiver_hash: Mapped[str] = mapped_column(String(64), unique=True)
    approved_by: Mapped[str] = mapped_column(String(128))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "requirement_id", name="uq_qa_waiver_requirement"),
    )


class QARollbackRehearsalRow(Base):
    __tablename__ = "qa_rollback_rehearsals"
    rehearsal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("qa_acceptance_campaigns.campaign_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    from_release: Mapped[str] = mapped_column(String(128))
    to_release: Mapped[str] = mapped_column(String(128))
    recovery_point_id: Mapped[str | None] = mapped_column(String(64), index=True)
    before_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    after_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True)
    rehearsal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    rehearsed_by: Mapped[str] = mapped_column(String(128))
    rehearsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "from_release", "to_release", name="uq_qa_rollback_path"),
    )


class QAReleaseCandidateRow(Base):
    __tablename__ = "qa_release_candidates"
    release_candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("qa_acceptance_campaigns.campaign_id", ondelete="RESTRICT"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), index=True)
    source_commit: Mapped[str] = mapped_column(String(64), index=True)
    source_root_sha256: Mapped[str] = mapped_column(String(64), index=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str] = mapped_column(Text)
    public_key: Mapped[str] = mapped_column(Text)
    signer_key_id: Mapped[str] = mapped_column(String(128))
    blockers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    external_gaps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(64), index=True)
    production_authorized: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=db_now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "source_commit", "source_root_sha256", name="uq_qa_candidate_source"),
    )

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
