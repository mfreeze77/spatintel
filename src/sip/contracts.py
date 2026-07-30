from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Audience, AuthorityClass, Classification, RepresentationKind, SourceClass


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HashRef(ContractModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_count: int = Field(ge=0)
    media_type: str


class CoordinateFrameContract(ContractModel):
    frame_id: str
    parent_frame_id: str | None = None
    semantic_type: str = Field(default="local_cartesian", min_length=1, max_length=128)
    convention: Literal["right_handed_y_up_meters", "right_handed_z_up_meters", "source_native"]
    units: Literal["meter", "millimeter"] = "meter"
    unit_scale_to_meters: float | None = Field(default=None, gt=0)
    original_units: str = "meter"
    original_unit_scale_to_meters: float | None = Field(default=None, gt=0)
    axis_convention: str = "right_handed_y_up"
    axis_directions: dict[str, str] = Field(min_length=3)
    handedness: Literal["right", "left"] = "right"
    origin_description: str = "capture_session_origin"
    gravity_alignment: str | None = None
    source: str = "platform"
    crs_identifier: str | None = None
    vertical_datum: str | None = None
    geodetic: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    transform_to_parent: list[list[float]] | None = None
    uncertainty_m: float | None = Field(default=None, ge=0)
    supersedes_frame_id: str | None = None

    @field_validator("transform_to_parent")
    @classmethod
    def matrix_is_4x4(cls, value: list[list[float]] | None) -> list[list[float]] | None:
        if value is not None:
            _validate_matrix(value, 4, 4, "transform_to_parent")
            if value[3] != [0.0, 0.0, 0.0, 1.0]:
                raise ValueError("transform_to_parent requires homogeneous final row [0,0,0,1]")
        return value

    @model_validator(mode="after")
    def declare_unit_boundaries(self) -> "CoordinateFrameContract":
        canonical_scale = {"meter": 1.0, "millimeter": 0.001}[self.units]
        if self.unit_scale_to_meters is None:
            self.unit_scale_to_meters = canonical_scale
        elif not math.isclose(self.unit_scale_to_meters, canonical_scale, rel_tol=0, abs_tol=1e-12):
            raise ValueError("unit_scale_to_meters does not match units")

        known_source_scale = {"meter": 1.0, "metre": 1.0, "millimeter": 0.001, "millimetre": 0.001}.get(
            self.original_units.lower()
        )
        if self.original_unit_scale_to_meters is None:
            if known_source_scale is None:
                raise ValueError("custom original_units require original_unit_scale_to_meters")
            self.original_unit_scale_to_meters = known_source_scale
        elif known_source_scale is not None and not math.isclose(
            self.original_unit_scale_to_meters, known_source_scale, rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError("original_unit_scale_to_meters does not match original_units")
        if self.geodetic and not self.crs_identifier:
            raise ValueError("geodetic coordinate frames require crs_identifier")
        if set(self.axis_directions) != {"x", "y", "z"}:
            raise ValueError("axis_directions must explicitly declare x, y, and z")
        if any(not str(value).strip() for value in self.axis_directions.values()):
            raise ValueError("axis direction declarations cannot be empty")
        return self


class CRSGridResourceContract(ContractModel):
    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    uri: str | None = None
    version: str | None = None


class SpatialTransformContract(ContractModel):
    transform_id: str
    source_frame_id: str
    target_frame_id: str
    transform_type: Literal["SE3", "SIM3"]
    matrix: list[list[float]]
    matrix_layout: Literal["row_major", "column_major"] = "row_major"
    multiplication_convention: Literal["column_vector_pre_multiply", "row_vector_post_multiply"] = "column_vector_pre_multiply"
    direction: Literal["source_to_target", "target_to_source"] = "source_to_target"
    translation_units: Literal["meter", "millimeter"] = "meter"
    scale: float = Field(default=1.0, gt=0)
    covariance: list[list[float]] | None = None
    residual_summary: dict[str, float] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(min_length=1)
    source_type: Literal["calibration", "registration", "control", "manual", "geodetic", "import"]
    authority_class: AuthorityClass
    calibration_id: str | None = None
    solver_run_id: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    crs_pipeline: str | None = None
    grid_resources: list[CRSGridResourceContract] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    supersedes_transform_id: str | None = None

    @model_validator(mode="after")
    def validate_transform_contract(self) -> "SpatialTransformContract":
        _validate_matrix(self.matrix, 4, 4, "matrix")
        if self.source_frame_id == self.target_frame_id:
            raise ValueError("source and target frames must differ")
        if self.transform_type == "SE3" and not math.isclose(self.scale, 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("SE3 transforms cannot contain scale")
        if self.covariance is not None:
            size = 6 if self.transform_type == "SE3" else 7
            _validate_matrix(self.covariance, size, size, "covariance")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.observed_at is None and self.valid_from is None:
            raise ValueError("transform requires observed_at or valid_from")
        if self.source_type == "geodetic" and not self.crs_pipeline:
            raise ValueError("geodetic transforms require the exact CRS pipeline")
        for key, value in self.uncertainty.items():
            if isinstance(value, (int, float)) and (
                not math.isfinite(float(value)) or float(value) < 0
            ):
                raise ValueError(f"uncertainty value {key!r} must be finite and non-negative")
        return self


class GeometryAssetManifestContract(ContractModel):
    geometry_manifest_id: str
    asset_id: str
    representation_id: str | None = None
    media_type: str
    format: str
    profile: str
    format_version: str
    coordinate_frame_id: str
    units: Literal["meter", "millimeter"]
    bounds: dict[str, list[float]]
    counts: dict[str, int] = Field(min_length=1)
    compression: dict[str, Any] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_run_id: str = Field(min_length=1)
    quality: dict[str, Any] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    visual_content_classes: list[
        Literal["captured", "corrected", "reconstructed", "inpainted", "relit", "generated", "mixed"]
    ] = Field(default_factory=list)
    classification: Classification
    audience_policy: dict[str, Any] = Field(default_factory=dict)
    viewer_compatibility: list[str] = Field(default_factory=list)
    exporter_compatibility: list[str] = Field(default_factory=list)
    validation_state: Literal["pending", "valid", "invalid", "deprecated"] = "pending"
    rebuild_recipe: dict[str, Any] = Field(default_factory=dict)
    truth_label: str | None = None
    supersedes_manifest_id: str | None = None
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_geometry_bounds(self) -> "GeometryAssetManifestContract":
        minimum = self.bounds.get("min")
        maximum = self.bounds.get("max")
        if minimum is None or maximum is None or len(minimum) != 3 or len(maximum) != 3:
            raise ValueError("bounds require three-dimensional min and max")
        if any(not math.isfinite(float(value)) for value in [*minimum, *maximum]):
            raise ValueError("bounds must be finite")
        if any(float(low) > float(high) for low, high in zip(minimum, maximum, strict=True)):
            raise ValueError("bounds min cannot exceed max")
        if self.format.lower() in {"splat", "gaussian-splat", "ply-splat"} and not self.truth_label:
            raise ValueError("splat geometry manifests require an explicit truth label")
        visual_format = self.format.lower() in {
            "splat",
            "gaussian-splat",
            "ply-splat",
            "nerf",
            "neural-radiance-field",
            "texture",
            "image",
            "video",
        }
        visual_media = self.media_type.startswith(("image/", "video/")) or "splat" in self.media_type.lower()
        if (visual_format or visual_media) and not self.visual_content_classes:
            raise ValueError("visual assets require explicit captured/corrected/reconstructed/generated content labels")
        if any(value < 0 for value in self.counts.values()):
            raise ValueError("geometry counts cannot be negative")
        if not str(self.compression.get("codec", "")).strip():
            raise ValueError("compression must declare a codec, including 'none'")
        return self


class EvidenceRecordContract(ContractModel):
    evidence_id: str
    asset_id: str
    source_type: str
    collected_at: datetime
    collected_by: str
    device_or_tool: str
    location_context: dict[str, Any] = Field(min_length=1)
    relevant_region: dict[str, Any] = Field(min_length=1)
    relevant_time_start: datetime
    relevant_time_end: datetime
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chain_of_custody: list[dict[str, Any]] = Field(min_length=1)
    retention_class: str
    legal_hold: bool = False
    consent_scope: dict[str, Any] = Field(min_length=1)
    access_policy: dict[str, Any] = Field(min_length=1)
    policy: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relevance_window(self) -> "EvidenceRecordContract":
        if self.relevant_time_end < self.relevant_time_start:
            raise ValueError("relevant evidence time range cannot run backwards")
        if not self.relevant_region:
            raise ValueError("evidence requires a relevant spatial or document region")
        return self


class AssertionContract(ContractModel):
    assertion_id: str
    subject_id: str
    predicate: str
    object_value: Any
    source_class: SourceClass
    authority_class: AuthorityClass
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    asserted_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    author_id: str | None = None
    producer_id: str | None = None
    conflicts_with_assertion_ids: list[str] = Field(default_factory=list)
    supersedes_assertion_id: str | None = None
    state: Literal["active", "disputed", "superseded", "withdrawn"] = "active"

    @model_validator(mode="after")
    def validate_assertion_identity_and_validity(self) -> "AssertionContract":
        if not self.author_id and not self.producer_id:
            raise ValueError("assertion requires an author_id or producer_id")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("assertion valid_to must be after valid_from")
        return self


class DerivationEventContract(ContractModel):
    derivation_id: str
    activity_type: str = Field(min_length=1)
    input_ids: list[str] = Field(min_length=1)
    input_hashes: list[str] = Field(min_length=1)
    algorithm_id: str
    algorithm_version: str
    model_manifest_id: str | None = None
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_commit: str
    container_digest: str | None = None
    output_ids: list[str] = Field(min_length=1)
    output_hashes: list[str] = Field(min_length=1)
    software: dict[str, Any] = Field(min_length=1)
    quality: dict[str, Any] = Field(min_length=1)
    validation: dict[str, Any] = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    actor_id: str | None = None
    workload_identity: str | None = None

    @model_validator(mode="after")
    def validate_derivation(self) -> "DerivationEventContract":
        if len(self.input_ids) != len(self.input_hashes):
            raise ValueError("input_ids and input_hashes must align")
        if len(self.output_ids) != len(self.output_hashes):
            raise ValueError("output_ids and output_hashes must align")
        if any(not _is_sha256(value) for value in [*self.input_hashes, *self.output_hashes]):
            raise ValueError("derivation input and output hashes must be lowercase SHA-256 values")
        if self.completed_at < self.started_at:
            raise ValueError("derivation completion cannot precede start")
        if not self.actor_id and not self.workload_identity:
            raise ValueError("derivation requires actor_id or workload_identity")
        return self


class SpatialAnnotationContract(ContractModel):
    annotation_id: str
    scene_id: str
    entity_id: str | None = None
    coordinate_frame_id: str
    support_type: Literal[
        "world_point",
        "semantic_entity",
        "surface_coordinate",
        "plane",
        "line",
        "volume",
        "document_region",
    ]
    support: dict[str, Any]
    position: list[float] | None = None
    orientation: list[float] | None = None
    normal: list[float] | None = None
    uncertainty_m: float = Field(ge=0)
    source_class: SourceClass
    authority_class: AuthorityClass
    policy: dict[str, Any] = Field(default_factory=dict)
    lifecycle_state: Literal["active", "unresolved", "superseded", "deleted"] = "active"
    authored_from_representation_id: str | None = None

    @model_validator(mode="after")
    def stable_support_only(self) -> "SpatialAnnotationContract":
        forbidden = {"triangle_id", "gaussian_id", "voxel_id", "tile_id", "lod_id", "vertex_id", "face_id"}
        if forbidden & set(self.support):
            raise ValueError("annotation support cannot depend on representation-local primitive identifiers")
        if self.position is not None and len(self.position) != 3:
            raise ValueError("position must have three values")
        if self.normal is not None and len(self.normal) != 3:
            raise ValueError("normal must have three values")
        if self.support_type == "semantic_entity" and not self.support.get("semantic_entity_id"):
            raise ValueError("semantic_entity support requires semantic_entity_id")
        if self.support_type == "surface_coordinate":
            required = {"geometry_manifest_id", "surface_patch_id", "barycentric_coordinates", "fallback"}
            if not required.issubset(self.support):
                raise ValueError("surface_coordinate support requires a stable patch, barycentric coordinates, and fallback")
            barycentric = self.support.get("barycentric_coordinates")
            if not isinstance(barycentric, list) or len(barycentric) != 3:
                raise ValueError("barycentric_coordinates must contain three values")
            if not math.isclose(sum(float(value) for value in barycentric), 1.0, rel_tol=0, abs_tol=1e-6):
                raise ValueError("barycentric_coordinates must sum to one")
        return self


def _validate_matrix(value: list[list[float]], rows: int, columns: int, name: str) -> None:
    if len(value) != rows or any(len(row) != columns for row in value):
        raise ValueError(f"{name} must be {rows}x{columns}")
    if any(not math.isfinite(float(item)) for row in value for item in row):
        raise ValueError(f"{name} must contain finite values")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


class CaptureAssetContract(HashRef):
    asset_id: str
    relative_path: str
    role: str
    immutable: bool = True
    encryption: dict[str, Any] | None = None


class CaptureFrameContract(ContractModel):
    frame_id: str
    timestamp_ns: int = Field(ge=0)
    coordinate_frame_id: str
    rgb_asset_id: str
    depth_asset_id: str | None = None
    confidence_asset_id: str | None = None
    camera_pose: list[list[float]]
    intrinsics: list[list[float]]
    tracking_state: str
    exposure: dict[str, float] = Field(default_factory=dict)
    quality: dict[str, float] = Field(default_factory=dict)
    restricted_region_ids: list[str] = Field(default_factory=list)

    @field_validator("camera_pose")
    @classmethod
    def pose_is_4x4(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) != 4 or any(len(row) != 4 for row in value):
            raise ValueError("camera_pose must be 4x4")
        return value

    @field_validator("intrinsics")
    @classmethod
    def intrinsics_is_3x3(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) != 3 or any(len(row) != 3 for row in value):
            raise ValueError("intrinsics must be 3x3")
        return value


class CaptureRootContract(ContractModel):
    schema_name: Literal["sip.cscp"] = Field(default="sip.cscp", alias="schema", serialization_alias="schema")
    schema_version: str = "1.1.0"
    package_id: str
    created_at: datetime
    capture_profile: str
    source_adapter: str
    native_source_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    coordinate_frames: list[CoordinateFrameContract] = Field(min_length=1)
    assets: list[CaptureAssetContract]
    frames: list[CaptureFrameContract]
    policy: dict[str, Any]
    journal_root_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    merkle_root: str = Field(pattern=r"^[a-f0-9]{64}$")


class EventEnvelopeContract(ContractModel):
    event_id: str
    event_type: str
    schema_version: str
    tenant_id: str
    project_id: str | None
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    recorded_at: datetime
    actor_id: str | None
    workload_identity: str | None
    producer: str
    classification: str
    trace_id: str | None
    causation_id: str | None
    correlation_id: str | None
    payload: dict[str, Any]
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def verify_payload_hash(self) -> "EventEnvelopeContract":
        from .canonical import canonical_sha256

        if self.payload_hash != canonical_sha256(self.payload):
            raise ValueError("event payload hash does not match payload")
        if self.recorded_at < self.occurred_at:
            raise ValueError("event recorded time cannot precede occurrence time")
        return self


class OperationContract(ContractModel):
    operation_id: str
    tenant_id: str
    project_id: str
    operation_type: str
    idempotency_key: str
    state: Literal["pending", "leased", "running", "succeeded", "failed", "cancel_requested", "cancelled", "quarantined"]
    progress: float = Field(ge=0, le=1)
    attempt: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    input_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint: dict[str, Any]
    output_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    error: dict[str, Any]


class ProviderManifestContract(ContractModel):
    provider_id: str
    version: str
    provider_class: Literal["local_open_source", "private_managed", "external_api", "manual_external", "research_shadow"]
    source_url: str
    source_revision: str
    image_digest: str | None = None
    license_id: str
    approval_state: Literal["approved", "denied", "expired", "revoked", "research_only", "pending"]
    allowed_classifications: list[Classification]
    allowed_purposes: list[str]
    allowed_regions: list[str]
    deployments: list[str] = Field(default_factory=list)
    retention_days: int | None = Field(default=None, ge=0)
    output_rights: str
    expires_at: datetime | None = None
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LicenseDocumentContract(ContractModel):
    component: Literal["code", "dependencies", "weights", "dataset", "hosted_service", "output"]
    title: str = Field(min_length=1, max_length=256)
    license_id: str = Field(min_length=1, max_length=128)
    source_url: str = Field(min_length=1, max_length=2048)
    document_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    review_state: Literal["verified", "missing", "pending", "incompatible"]

class ProviderCoordinateContract(ContractModel):
    units: Literal["meter", "millimeter", "source_native"]
    handedness: Literal["right", "left"]
    up_axes: list[Literal["x", "y", "z"]] = Field(min_length=1)
    preserves_input_frame: bool
    scale_behavior: Literal["preserve", "explicit_transform", "estimated_with_uncertainty", "unresolved_visual_only"]
    requires_explicit_inverse_for_normalization: bool = True

    @field_validator("up_axes")
    @classmethod
    def unique_axes(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("up_axes must be unique")
        return value


class ProviderSecurityContract(ContractModel):
    network_required: bool
    approved_egress_domains: list[str] = Field(default_factory=list)
    writes_outside_job_workspace: bool
    supports_read_only_inputs: bool
    supports_write_only_staging: bool
    transient_cleanup: Literal["verified", "declared", "unsupported"]
    external_processing: bool = False

    @model_validator(mode="after")
    def enforce_egress_declaration(self) -> "ProviderSecurityContract":
        if not self.network_required and self.approved_egress_domains:
            raise ValueError("network-free providers cannot declare egress domains")
        if self.network_required and not self.approved_egress_domains:
            raise ValueError("networked providers require an explicit egress allowlist")
        return self


class ProviderRecoveryContract(ContractModel):
    cancellation_bound_seconds: int = Field(ge=1, le=86400)
    checkpoint_supported: bool
    resume_supported: bool
    cleanup_supported: bool
    checkpoint_schema_version: str
    objective_progress_units: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_recovery(self) -> "ProviderRecoveryContract":
        if self.resume_supported and not self.checkpoint_supported:
            raise ValueError("resume support requires checkpoint support")
        return self


class ProviderDataGovernanceContract(ContractModel):
    source_data_use: Literal["requested_operation_only"] = "requested_operation_only"
    training_use: Literal["prohibited", "separate_authorization_required"]
    public_demonstration: Literal["prohibited", "separate_authorization_required"]
    unrelated_retention: Literal["prohibited", "separate_authorization_required"]
    processing_regions: list[str] = Field(min_length=1)
    subprocessor_disclosure_complete: bool
    deletion_verification: Literal["platform_verified", "provider_receipt", "not_applicable"]
    data_use_terms_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("processing_regions")
    @classmethod
    def unique_processing_regions(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("processing regions must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("processing regions must be unique")
        return normalized


class ProviderCapabilityDescriptorContract(ContractModel):
    schema_name: Literal["sip.provider-capability/v1.1"] = Field(
        default="sip.provider-capability/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    provider_id: str = Field(min_length=1, max_length=128)
    provider_version: str = Field(min_length=1, max_length=64)
    provider_class: Literal["local_open_source", "private_managed", "external_api", "manual_external", "research_shadow"]
    source_url: str = Field(min_length=1, max_length=2048)
    source_revision: str = Field(min_length=1, max_length=128)
    executable_digest: str = Field(pattern=r"^(sha256:)?[a-f0-9]{64}$")
    execution_modes: list[Literal["local_process", "isolated_container", "private_managed", "external_api", "manual_external"]] = Field(min_length=1)
    deployment_modes: list[Literal["local_only", "hybrid", "managed_cloud", "manual_external"]] = Field(min_length=1)
    input_roles: list[str] = Field(min_length=1)
    output_roles: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    supported_formats: dict[str, list[str]]
    coordinate_contract: ProviderCoordinateContract
    reproducibility: dict[str, Any] = Field(min_length=1)
    security: ProviderSecurityContract
    recovery: ProviderRecoveryContract
    data_governance: ProviderDataGovernanceContract
    license_manifest_id: str = Field(min_length=1, max_length=128)
    license_evidence: list[LicenseDocumentContract] = Field(min_length=1)
    model_manifest_ids: list[str] = Field(default_factory=list)
    dependency_inventory: list[dict[str, Any]] = Field(min_length=1)
    benchmark_profile_ids: list[str] = Field(min_length=1)
    allowed_classifications: list[Classification] = Field(min_length=1)
    allowed_purposes: list[str] = Field(min_length=1)
    allowed_regions: list[str] = Field(min_length=1)
    prohibited_purposes: list[str] = Field(default_factory=list)
    output_rights: str = Field(min_length=1)
    retention_days: int | None = Field(default=None, ge=0)
    approval_state: Literal["approved", "denied", "expired", "revoked", "research_only", "pending"]
    reviewed_at: datetime
    review_due_at: datetime
    expires_at: datetime | None = None
    signed_by: str = Field(min_length=1, max_length=128)
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator(
        "execution_modes", "deployment_modes", "input_roles", "output_roles", "capabilities",
        "model_manifest_ids", "benchmark_profile_ids", "allowed_purposes", "allowed_regions", "prohibited_purposes"
    )
    @classmethod
    def unique_nonempty_lists(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("provider descriptor list entries must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("provider descriptor list entries must be unique")
        return normalized

    @field_validator("allowed_classifications")
    @classmethod
    def unique_classifications(cls, value: list[Classification]) -> list[Classification]:
        if len(set(value)) != len(value):
            raise ValueError("allowed_classifications entries must be unique")
        return value

    @model_validator(mode="after")
    def validate_descriptor(self) -> "ProviderCapabilityDescriptorContract":
        if set(self.allowed_purposes) & set(self.prohibited_purposes):
            raise ValueError("allowed and prohibited purposes cannot overlap")
        if self.review_due_at <= self.reviewed_at:
            raise ValueError("review_due_at must be after reviewed_at")
        if self.expires_at and self.expires_at <= self.reviewed_at:
            raise ValueError("expires_at must be after reviewed_at")
        if self.provider_class == "manual_external" and "manual_external" not in self.execution_modes:
            raise ValueError("manual external provider class requires manual_external execution mode")
        if self.provider_class in {"external_api", "manual_external"} and not self.security.external_processing:
            raise ValueError("external provider classes must declare external processing")
        if self.provider_class == "local_open_source" and self.security.external_processing:
            raise ValueError("local open-source providers cannot declare external processing")
        if not set(self.data_governance.processing_regions).issubset(set(self.allowed_regions)):
            raise ValueError("data-governance processing regions must be within allowed_regions")
        if self.approval_state == "approved" and not self.data_governance.subprocessor_disclosure_complete:
            raise ValueError("approved providers require a complete subprocessor disclosure")
        if self.security.external_processing and self.data_governance.deletion_verification == "not_applicable":
            raise ValueError("external providers require deletion-verification evidence")
        if not self.security.supports_read_only_inputs or not self.security.supports_write_only_staging:
            raise ValueError("executable providers require read-only inputs and write-only staging")
        return self


class ProviderPromotionContract(ContractModel):
    promotion_id: str
    provider_id: str
    provider_version: str
    provider_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: Literal["discovered", "research_isolated", "shadow", "limited", "active", "deprecated", "blocked"]
    data_classifications: list[Classification] = Field(min_length=1)
    scene_classes: list[str] = Field(min_length=1)
    output_roles: list[str] = Field(min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    execution_zones: list[str] = Field(min_length=1)
    hardware_profiles: list[str] = Field(min_length=1)
    benchmark_evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    valid_from: datetime
    valid_until: datetime | None = None
    signed_by: str
    promotion_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_promotion_dates(self) -> "ProviderPromotionContract":
        if self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class SpatialConversionAssetContract(ContractModel):
    asset_id: str
    role: str
    sha256: str = Field(pattern=r"^(sha256:)?[a-f0-9]{64}$")
    coordinate_frame_id: str
    use: str | None = None


class SpatialConversionRequestContract(ContractModel):
    schema_name: Literal["sip.spatial-conversion.request/1.1"] = Field(
        default="sip.spatial-conversion.request/1.1", alias="schema", serialization_alias="schema"
    )
    operation_id: str | None = None
    tenant_id: str
    project_id: str
    scene_id: str
    scene_revision_id: str
    purpose: str
    intended_uses: list[str] = Field(min_length=1)
    output_roles: list[str] = Field(min_length=1)
    source_assets: list[SpatialConversionAssetContract] = Field(min_length=1)
    reference_assets: list[SpatialConversionAssetContract] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    policy_context: dict[str, Any] = Field(min_length=1)
    provider_selector: dict[str, Any] = Field(min_length=1)
    requested_by: str
    idempotency_key: str = Field(min_length=1, max_length=256)
    request_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("intended_uses", "output_roles")
    @classmethod
    def request_lists_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("conversion request lists must contain unique non-empty entries")
        return normalized


class ProviderProgressContract(ContractModel):
    conversion_id: str
    sequence: int = Field(ge=1)
    stage: str = Field(min_length=1)
    completed_work_units: float = Field(ge=0)
    total_work_units: float | None = Field(default=None, gt=0)
    work_unit_name: str = Field(min_length=1)
    resource_use: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    last_durable_checkpoint_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    estimated_output_bytes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def enforce_objective_progress(self) -> "ProviderProgressContract":
        if self.total_work_units is not None and self.completed_work_units > self.total_work_units:
            raise ValueError("completed work units cannot exceed total work units")
        return self


class HybridWorkerLeaseRenewalContract(ContractModel):
    conversion_id: str
    requested_ttl_seconds: int = Field(ge=30, le=900)
    last_durable_checkpoint_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ProviderCleanupConfirmationContract(ContractModel):
    attempted: bool
    completed: bool
    method: str = Field(min_length=1, max_length=128)
    workspace_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    deleted_object_count: int = Field(ge=0)
    retained_quarantine_asset_ids: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    verified_at: datetime
    verifier_id: str = Field(min_length=1, max_length=128)
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    cleanup_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("retained_quarantine_asset_ids", "residual_risks")
    @classmethod
    def cleanup_lists_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("cleanup list entries must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("cleanup list entries must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_cleanup_result(self) -> "ProviderCleanupConfirmationContract":
        if self.completed and not self.attempted:
            raise ValueError("completed cleanup requires an attempted cleanup")
        if self.completed and self.residual_risks:
            raise ValueError("completed cleanup cannot retain unresolved residual risks")
        from .canonical import canonical_sha256

        body = self.model_dump(mode="json", exclude={"cleanup_hash"})
        if self.cleanup_hash != canonical_sha256(body):
            raise ValueError("cleanup_hash does not match canonical cleanup evidence")
        return self


class ProviderFailureContract(ContractModel):
    conversion_id: str
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    safe_message: str = Field(min_length=1, max_length=512)
    retryable: bool
    last_durable_checkpoint_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    resource_use: dict[str, Any] = Field(default_factory=dict)
    cleanup: ProviderCleanupConfirmationContract
    failure_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def verify_failure_hash(self) -> "ProviderFailureContract":
        from .canonical import canonical_sha256

        body = self.model_dump(mode="json", exclude={"failure_hash"})
        if self.failure_hash != canonical_sha256(body):
            raise ValueError("failure_hash does not match canonical provider failure evidence")
        return self


class InteractionProfileManifestContract(ContractModel):
    profile_id: str = Field(min_length=1, max_length=128)
    profile_type: Literal["collision", "navigation", "occlusion", "spatial_audio", "picking"]
    version: str = Field(min_length=1, max_length=64)
    actor: dict[str, Any] = Field(min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    limits: dict[str, Any] = Field(min_length=1)
    behavior: dict[str, Any] = Field(min_length=1)
    validation: dict[str, Any] = Field(min_length=1)
    safety_claims: list[str] = Field(default_factory=list)
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("intended_uses", "safety_claims")
    @classmethod
    def profile_lists_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("interaction profile entries must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("interaction profile entries must be unique")
        return normalized

    @model_validator(mode="after")
    def verify_manifest_hash(self) -> "InteractionProfileManifestContract":
        from .canonical import canonical_sha256

        body = self.model_dump(mode="json", exclude={"manifest_hash", "manifest_signature"})
        if self.manifest_hash != canonical_sha256(body):
            raise ValueError("manifest_hash does not match canonical interaction profile")
        return self


class IntendedUseValidationContract(ContractModel):
    validation_id: str
    conversion_id: str
    representation_id: str
    intended_use: str
    profile_id: str
    profile_version: str
    validator_id: str
    validator_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    metrics: dict[str, Any] = Field(min_length=1)
    thresholds: dict[str, Any] = Field(min_length=1)
    coverage: dict[str, Any] = Field(min_length=1)
    topology: dict[str, Any] = Field(min_length=1)
    coordinate_validation: dict[str, Any] = Field(min_length=1)
    behavior_validation: dict[str, Any] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    passed: bool
    candidate_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ManualExternalReceiptContract(ContractModel):
    transfer_id: str
    conversion_id: str
    tool: str
    tool_version: str
    account_or_environment: str
    operator_id: str
    executed_at: datetime
    input_hashes: list[str] = Field(min_length=1)
    output_hashes: list[str] = Field(min_length=1)
    options: dict[str, Any]
    processing_location: Literal["uploaded_external", "local_operator_device", "approved_private_environment"]
    retention_statement: str
    cleanup_actions: list[str]
    manual_edits: list[dict[str, Any]] = Field(default_factory=list)
    evidence_asset_ids: list[str] = Field(min_length=1)
    receipt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class HybridSceneViewManifestContract(ContractModel):
    schema_name: Literal["sip.hybrid-scene-view/1.1"] = Field(
        default="sip.hybrid-scene-view/1.1", alias="schema", serialization_alias="schema"
    )
    view_id: str
    tenant_id: str
    project_id: str
    scene_id: str
    scene_revision_id: str
    principal_id: str
    purpose: str
    audience: str
    device_profile: str
    time_context: dict[str, Any]
    bindings: dict[str, list[str]]
    interaction_policy: dict[str, Any]
    truth_labels: dict[str, Any]
    streaming: dict[str, Any]
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime

    @model_validator(mode="after")
    def prohibit_raw_asset_references(self) -> "HybridSceneViewManifestContract":
        for role, identifiers in self.bindings.items():
            if any(not isinstance(identifier, str) or not identifier.strip() for identifier in identifiers):
                raise ValueError(f"hybrid view role {role} must reference non-empty binding identifiers")
        return self


class ManifestRestrictionContract(ContractModel):
    mode: Literal["unrestricted", "allowlist", "denylist"]
    values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_values(self) -> "ManifestRestrictionContract":
        normalized = [value.strip() for value in self.values]
        if any(not value for value in normalized):
            raise ValueError("restriction values must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("restriction values must be unique")
        if self.mode == "unrestricted" and normalized:
            raise ValueError("unrestricted restrictions cannot contain values")
        if self.mode in {"allowlist", "denylist"} and not normalized:
            raise ValueError(f"{self.mode} restrictions require at least one value")
        self.values = normalized
        return self


class ModelManifestContract(ContractModel):
    schema_name: Literal["sip.model-manifest/v1.1"] = Field(
        default="sip.model-manifest/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    model_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=256)
    model_name: str = Field(min_length=1, max_length=256)
    version: str = Field(min_length=1, max_length=64)
    revision: str = Field(min_length=1, max_length=128)
    checkpoint_hash: str = Field(min_length=1, max_length=128)
    source_urls: list[str] = Field(min_length=1)
    license_documents: list[LicenseDocumentContract] = Field(min_length=1)
    code_revision: str = Field(min_length=1, max_length=128)
    code_license: str = Field(min_length=1, max_length=128)
    weights_license: str = Field(min_length=1, max_length=128)
    dataset_terms: list[str] = Field(min_length=1)
    output_terms: str = Field(min_length=1)
    approval_state: Literal["approved", "denied", "expired", "revoked", "research_only", "pending"]
    commercial_use: bool
    allowed_classifications: list[Classification] = Field(min_length=1)
    permitted_uses: list[str] = Field(min_length=1)
    prohibited_uses: list[str] = Field(min_length=1)
    geographic_restrictions: ManifestRestrictionContract
    customer_restrictions: ManifestRestrictionContract
    allowed_deployments: list[Literal["development", "test", "staging", "production"]] = Field(min_length=1)
    approved_by: str = Field(min_length=1, max_length=128)
    reviewed_at: datetime
    review_due_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    signed_by: str = Field(min_length=1, max_length=128)

    @field_validator(
        "source_urls", "dataset_terms", "permitted_uses", "prohibited_uses", "allowed_deployments"
    )
    @classmethod
    def lists_are_nonempty_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("manifest list entries must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("manifest list entries must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_policy_dates_and_uses(self) -> "ModelManifestContract":
        if set(self.permitted_uses) & set(self.prohibited_uses):
            raise ValueError("permitted and prohibited uses cannot overlap")
        if self.review_due_at <= self.reviewed_at:
            raise ValueError("review_due_at must be after reviewed_at")
        if self.expires_at is not None and self.expires_at <= self.reviewed_at:
            raise ValueError("expires_at must be after reviewed_at")
        if self.approval_state == "revoked" and self.revoked_at is None:
            raise ValueError("revoked manifests require revoked_at")
        if self.approval_state != "revoked" and self.revoked_at is not None:
            raise ValueError("revoked_at is only valid for revoked manifests")
        return self


class RepresentationAssetContract(ContractModel):
    representation_id: str
    scene_id: str
    asset_id: str
    kind: RepresentationKind
    provider_id: str
    provider_version: str
    coordinate_frame_id: str
    source_class: SourceClass
    authority_class: AuthorityClass
    authority_ceiling: AuthorityClass
    disposable: bool
    lossy: bool
    intended_uses: list[str]
    prohibited_uses: list[str]
    quality: dict[str, Any]
    provenance: dict[str, Any]
    support_map: dict[str, Any]
    format_metadata: dict[str, Any] = Field(default_factory=dict)
    derivation_policy: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    information_losses: list[str] = Field(default_factory=list)
    privacy_inheritance: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    fallback_representation_id: str | None = None
    state: Literal["quarantined", "quality_failed", "approved", "published", "superseded", "invalidated", "deprecated"]

    @model_validator(mode="after")
    def enforce_representation_authority(self) -> "RepresentationAssetContract":
        if self.kind == RepresentationKind.INTERACTION:
            if self.authority_class != AuthorityClass.DERIVED_NON_AUTHORITATIVE:
                raise ValueError("interaction representations require derived_non_authoritative authority")
            if self.authority_ceiling != AuthorityClass.DERIVED_NON_AUTHORITATIVE:
                raise ValueError("interaction representations require a derived_non_authoritative authority ceiling")
            if not self.disposable:
                raise ValueError("interaction representations must be disposable")
        if self.kind == RepresentationKind.VISUAL and self.authority_ceiling in {
            AuthorityClass.METRIC,
            AuthorityClass.FIELD_VERIFIED,
        }:
            raise ValueError("visual representations cannot have metric or field-verified authority ceilings")
        return self


class SceneEntityContract(ContractModel):
    entity_id: str
    scene_id: str
    entity_type: str
    name: str
    source_class: SourceClass
    authority_class: AuthorityClass
    confidence: float = Field(ge=0, le=1)
    attributes: dict[str, Any]
    provenance: dict[str, Any]
    policy: dict[str, Any]
    stable_support: dict[str, Any]


class MeasurementContract(ContractModel):
    measurement_id: str
    scene_id: str
    entity_id: str | None = None
    measurement_type: str = Field(min_length=1)
    geometry: dict[str, Any] = Field(min_length=1)
    value: float
    unit: str
    uncertainty: float = Field(ge=0)
    source_method: str = Field(min_length=1)
    measured_at: datetime
    coordinate_frame_id: str
    source_commit_id: str
    permitted_uses: list[str] = Field(min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)
    calibration: dict[str, Any] = Field(min_length=1)
    creator_id: str
    verifier_id: str | None = None
    verification_date: datetime | None = None
    verification_status: Literal["observed", "measured", "verified", "disputed", "superseded"]
    authority_class: AuthorityClass
    originating_representation_id: str | None = None
    interaction_hit: dict[str, Any] | None = None
    resolved_metric_evidence: dict[str, Any] | None = None
    supersedes_measurement_id: str | None = None
    warning: str = "Phone-derived geometry is not survey-grade or contract-authoritative without independent verification."

    @model_validator(mode="after")
    def validate_measurement_verification(self) -> "MeasurementContract":
        if self.interaction_hit is not None:
            required_hit = {"representation_id", "world_point"}
            if not required_hit.issubset(self.interaction_hit):
                raise ValueError("interaction_hit requires representation_id and world_point")
            point = self.interaction_hit.get("world_point")
            if not isinstance(point, list) or len(point) != 3 or any(
                not math.isfinite(float(value)) for value in point
            ):
                raise ValueError("interaction_hit world_point must contain three finite values")
        if self.resolved_metric_evidence is not None:
            required_resolution = {
                "metric_representation_id",
                "metric_source_asset_ids",
                "estimated_residual_m",
                "acceptance_threshold_m",
            }
            if not required_resolution.issubset(self.resolved_metric_evidence):
                raise ValueError(
                    "resolved_metric_evidence requires metric representation, source assets, and residual"
                )
            residual = float(self.resolved_metric_evidence["estimated_residual_m"])
            threshold = float(self.resolved_metric_evidence["acceptance_threshold_m"])
            if not math.isfinite(residual) or residual < 0:
                raise ValueError("resolved metric residual must be finite and non-negative")
            if not math.isfinite(threshold) or threshold < 0:
                raise ValueError("resolved metric acceptance threshold must be finite and non-negative")
            if residual > threshold:
                raise ValueError("resolved metric residual exceeds the accepted support tolerance")
            source_ids = self.resolved_metric_evidence.get("metric_source_asset_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise ValueError("resolved metric evidence requires source asset identifiers")
        if self.interaction_hit is not None and self.originating_representation_id is None:
            raise ValueError("interaction-hit measurements require originating_representation_id")
        if self.verification_status == "verified":
            if not self.verifier_id or self.verification_date is None:
                raise ValueError("verified measurements require verifier and verification date")
            if self.authority_class != AuthorityClass.FIELD_VERIFIED:
                raise ValueError("verified measurements require field_verified authority")
            if self.uncertainty <= 0:
                raise ValueError("verified measurements require explicit non-zero uncertainty")
        return self


class ViewerLayerContract(ContractModel):
    role: Literal["metric", "visual", "interaction", "design", "evidence", "semantic", "collision", "navigation", "occlusion", "spatial_audio"]
    binding_ids: list[str] = Field(default_factory=list)
    visible: bool = True
    interactive: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    authority_label: str = Field(min_length=1)

    @field_validator("binding_ids")
    @classmethod
    def binding_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("viewer layer binding identifiers must be unique")
        return value


class ViewerSessionContract(ContractModel):
    schema_name: Literal["sip.viewer-session/v1.1"] = Field(
        default="sip.viewer-session/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    session_id: str
    tenant_id: str
    project_id: str
    scene_id: str
    principal_id: str
    purpose: str = Field(min_length=1)
    audience: Audience
    publication_class: Literal["working", "audit", "report"] = "working"
    scene_commit_ids: list[str] = Field(min_length=1, max_length=2)
    saved_hybrid_views: list[dict[str, Any]] = Field(default_factory=list)
    device_profile: str = Field(min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    spatial_region_ids: list[str] = Field(default_factory=list)
    camera: dict[str, Any] = Field(min_length=1)
    navigation_mode: Literal["orbit", "walk", "fly", "teleport", "guided"]
    layers: list[ViewerLayerContract] = Field(min_length=1)
    clipping_planes: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    section_box: dict[str, Any] | None = None
    selected_entity_ids: list[str] = Field(default_factory=list)
    timeline: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    redaction: dict[str, Any] = Field(default_factory=dict)
    accessibility: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=256)
    immutable: Literal[True] = True
    supersedes_session_id: str | None = None
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def validate_reproducible_viewer_session(self) -> "ViewerSessionContract":
        for name, values in {
            "scene_commit_ids": self.scene_commit_ids,
            "intended_uses": self.intended_uses,
            "spatial_region_ids": self.spatial_region_ids,
            "selected_entity_ids": self.selected_entity_ids,
        }.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} entries must be unique")
        if len({layer.role for layer in self.layers}) != len(self.layers):
            raise ValueError("viewer session can declare each layer role only once")
        if len(self.scene_commit_ids) == 2 and not self.comparison:
            raise ValueError("two-commit viewer sessions require comparison state")
        if len(self.scene_commit_ids) == 1 and self.comparison.get("secondary_commit_id"):
            raise ValueError("comparison state cannot reference a secondary commit not retained by the session")
        if self.redaction.get("server_enforced") is not True:
            raise ValueError("viewer session redaction state must be server-enforced")
        required_accessibility = {"reduced_motion", "high_contrast", "captions"}
        if not required_accessibility.issubset(self.accessibility):
            raise ValueError("viewer session accessibility state must retain reduced_motion, high_contrast, and captions")
        _reject_capability_material(self.model_dump(mode="json"))
        return self


class ViewerSessionReplayContract(ContractModel):
    schema_name: Literal["sip.viewer-session-replay/v1.1"] = Field(
        default="sip.viewer-session-replay/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    replay_id: str
    session_id: str
    tenant_id: str
    project_id: str
    principal_id: str
    issued_views: list[dict[str, Any]] = Field(default_factory=list)
    exact: bool
    degraded_reasons: list[str] = Field(default_factory=list)
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    replay_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def prevent_persisted_capabilities(self) -> "ViewerSessionReplayContract":
        # issued_views contain identifiers and expiry metadata only. Reusable bearer
        # material is returned to the caller separately and is never persisted.
        _reject_capability_material(self.model_dump(mode="json"))
        return self


class ChangeCandidateContract(ContractModel):
    candidate_id: str
    change_class: Literal["added", "removed", "moved", "modified", "occluded", "unobserved", "uncertain"]
    entity_id: str | None = None
    region: dict[str, Any] = Field(min_length=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    coverage_status: Literal["observed", "partially_observed", "unobserved"]
    difference_causes: list[Literal["geometry", "lod", "lighting", "exposure", "dynamic_object", "missing_coverage", "registration", "unknown"]] = Field(default_factory=list)
    state: Literal["active", "suppressed", "accepted", "rejected", "disputed"]
    suppression_reason: str | None = None
    candidate_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def enforce_change_suppression(self) -> "ChangeCandidateContract":
        nuisance = {"lod", "lighting", "exposure", "dynamic_object", "missing_coverage"}
        if self.change_class == "removed" and self.coverage_status != "observed":
            raise ValueError("unobserved or partially observed regions cannot be classified as removed")
        if set(self.difference_causes) & nuisance and self.state != "suppressed":
            raise ValueError("known nuisance differences must be suppressed")
        if self.state == "suppressed" and not self.suppression_reason:
            raise ValueError("suppressed change candidates require a reason")
        if self.state != "suppressed" and self.suppression_reason:
            raise ValueError("suppression_reason is valid only for suppressed candidates")
        return self


class TemporalComparisonContract(ContractModel):
    schema_name: Literal["sip.temporal-comparison/v1.1"] = Field(
        default="sip.temporal-comparison/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    comparison_id: str
    tenant_id: str
    project_id: str
    scene_id: str
    baseline_commit_id: str
    candidate_commit_id: str
    viewer_session_id: str | None = None
    comparable_region: dict[str, Any] = Field(min_length=1)
    registration_quality: dict[str, Any] = Field(min_length=1)
    thresholds: dict[str, Any] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    algorithm_id: str = Field(min_length=1)
    algorithm_version: str = Field(min_length=1)
    executable_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_coverage: dict[str, Any] = Field(min_length=1)
    candidates: list[ChangeCandidateContract]
    state: Literal["pending_review", "reviewed", "partially_applied", "applied", "superseded"]
    comparison_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=256)
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def validate_comparison_identity(self) -> "TemporalComparisonContract":
        if self.baseline_commit_id == self.candidate_commit_id:
            raise ValueError("temporal comparison requires distinct scene commits")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("temporal comparison evidence identifiers must be unique")
        if len({candidate.candidate_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("change candidate identifiers must be unique")
        quality = self.registration_quality
        if quality.get("accepted") is not True:
            raise ValueError("temporal comparison requires accepted registration quality")
        if float(quality.get("overlap_fraction", 0.0)) <= 0.0:
            raise ValueError("temporal comparison requires positive registered overlap")
        return self


class ChangeReviewContract(ContractModel):
    schema_name: Literal["sip.change-review/v1.1"] = Field(
        default="sip.change-review/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    review_id: str
    comparison_id: str
    candidate_id: str
    tenant_id: str
    project_id: str
    reviewer_id: str
    outcome: Literal["accepted", "rejected", "disputed"]
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    policy_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=256)
    review_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_at: datetime


class ChangeBenchmarkContract(ContractModel):
    schema_name: Literal["sip.change-benchmark/v1.1"] = Field(
        default="sip.change-benchmark/v1.1", alias="schema", serialization_alias="schema"
    )
    schema_version: Literal["1.1.0"] = "1.1.0"
    benchmark_id: str
    tenant_id: str
    project_id: str
    algorithm_id: str
    algorithm_version: str
    executable_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    benchmark_profile: str
    fixture_root_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    metrics_by_class: dict[str, dict[str, float]] = Field(min_length=1)
    environment: dict[str, Any] = Field(min_length=1)
    benchmark_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def require_quantitative_change_metrics(self) -> "ChangeBenchmarkContract":
        required = {"precision", "recall", "localization_error_m", "false_action_rate"}
        for change_class, metrics in self.metrics_by_class.items():
            if not required.issubset(metrics):
                raise ValueError(f"benchmark class {change_class!r} lacks required metrics")
            for name, value in metrics.items():
                numeric = float(value)
                if not math.isfinite(numeric) or numeric < 0:
                    raise ValueError(f"benchmark metric {change_class}.{name} must be finite and non-negative")
                if name in {"precision", "recall", "false_action_rate"} and numeric > 1:
                    raise ValueError(f"benchmark metric {change_class}.{name} must be between zero and one")
        return self


def _reject_capability_material(value: Any, path: str = "root") -> None:
    forbidden = {
        "token", "access_token", "refresh_token", "authorization", "bearer", "signed_url",
        "presigned_url", "credential", "secret", "password", "storage_key", "provider_key",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in forbidden or normalized.endswith("_token") or normalized.endswith("_secret"):
                raise ValueError(f"viewer session may not persist reusable capability material at {path}.{key}")
            _reject_capability_material(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_capability_material(item, f"{path}[{index}]")


class ThreatManifestContract(ContractModel):
    threat_manifest_id: str
    version: int = Field(ge=1)
    scope: str = Field(min_length=1)
    threats: list[dict[str, Any]] = Field(min_length=1)
    misuse_cases: list[dict[str, Any]] = Field(min_length=1)
    public_viewer_analysis: dict[str, Any] = Field(min_length=1)
    residual_risks: list[dict[str, Any]]
    owner: str = Field(min_length=1)
    review_trigger: str = Field(min_length=1)
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: Literal["active", "superseded"] = "active"


class PrivilegedAccessGrantContract(ContractModel):
    grant_id: str
    tenant_id: str
    project_id: str | None = None
    subject_id: str
    actions: list[str] = Field(min_length=1)
    resource_scope: dict[str, Any] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    mfa_method: str
    requested_by: str
    approved_by: str
    issued_at: datetime
    expires_at: datetime
    state: Literal["active", "revoked", "expired"]
    grant_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_grant(self) -> "PrivilegedAccessGrantContract":
        if self.requested_by == self.approved_by:
            raise ValueError("privileged access requires independent approval")
        if self.expires_at <= self.issued_at:
            raise ValueError("privileged access must expire after issuance")
        return self


class WorkloadIdentityGrantContract(ContractModel):
    grant_id: str
    tenant_id: str
    project_id: str | None = None
    workload_id: str
    audience: str
    scopes: list[str] = Field(min_length=1)
    purpose: str
    issued_at: datetime
    expires_at: datetime
    state: Literal["active", "revoked", "expired"]
    token_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class KeyScopeContract(ContractModel):
    key_scope_id: str
    tenant_id: str
    project_id: str | None = None
    person_id: str | None = None
    key_id: str
    backend: Literal["managed_kms", "governed_local", "hardware_backed"]
    recovery_policy: dict[str, Any] = Field(min_length=1)
    state: Literal["active", "rotated", "revoked", "erased"]
    rotated_from_key_id: str | None = None
    scope_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class PrivacyInventoryContract(ContractModel):
    inventory_id: str
    tenant_id: str
    project_id: str | None = None
    data_category: str
    purpose: str
    legal_basis: str
    consent_basis: str | None = None
    processors: list[dict[str, Any]]
    residency: dict[str, Any] = Field(min_length=1)
    retention: dict[str, Any] = Field(min_length=1)
    security_controls: list[str] = Field(min_length=1)
    rights_workflow: dict[str, Any] = Field(min_length=1)
    classification: str
    inventory_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class PrivacyRightsRequestContract(ContractModel):
    rights_request_id: str
    tenant_id: str
    project_id: str | None = None
    subject_id: str
    request_type: Literal["access", "deletion", "correction", "restriction", "portability"]
    scope: dict[str, Any] = Field(min_length=1)
    requested_by: str
    verified_by: str
    state: Literal["open", "completed", "denied", "expired"]
    due_at: datetime
    outcomes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class SecurityIncidentContract(ContractModel):
    incident_id: str
    tenant_id: str
    project_id: str | None = None
    incident_type: str
    severity: Literal["low", "moderate", "high", "critical"]
    affected_subjects: list[str]
    affected_resources: list[dict[str, Any]]
    containment: list[dict[str, Any]]
    notification_decision: dict[str, Any]
    evidence: list[dict[str, Any]]
    state: Literal["open", "contained", "resolved"]
    incident_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class AuditVerificationContract(ContractModel):
    verification_id: str
    tenant_id: str
    project_id: str | None = None
    status: Literal["passed", "failed"]
    record_count: int = Field(ge=0)
    findings: list[dict[str, Any]]
    referenced_manifests: list[dict[str, Any]]
    verification_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class SupplyChainReleaseContract(ContractModel):
    release_record_id: str
    version: str
    source_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    source_root: str = Field(pattern=r"^[a-f0-9]{64}$")
    component_manifests: dict[str, Any] = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    rollback_plan: dict[str, Any] = Field(min_length=1)
    environment_policy: dict[str, Any] = Field(min_length=1)
    signed_by: str
    signature: str
    state: Literal["candidate", "promoted", "revoked"]
    release_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    emergency_patch: bool = False


class ProviderOutputValidationContract(ContractModel):
    validation_id: str
    tenant_id: str
    project_id: str
    provider_id: str
    operation_id: str
    output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str
    byte_count: int = Field(ge=0)
    validations: dict[str, Any] = Field(min_length=1)
    state: Literal["quarantined", "approved", "rejected"]
    validation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class TransportVerificationContract(ContractModel):
    verification_id: str
    endpoint: str
    protocol: str
    minimum_tls_version: str
    certificate_validated: bool
    channel_authentication: str
    evidence: dict[str, Any] = Field(min_length=1)
    result: Literal["passed", "failed"]
    verification_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CaptureFinalizationContract(ContractModel):
    finalization_id: str
    tenant_id: str
    project_id: str
    capture_id: str
    package_root_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    archive_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    device: dict[str, Any] = Field(min_length=1)
    app: dict[str, Any] = Field(min_length=1)
    signer_id: str
    verification_result: Literal["passed", "failed"]
    finalization_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ImmersiveSafetyDecisionContract(ContractModel):
    decision_id: str
    tenant_id: str
    project_id: str
    scene_id: str
    checks: dict[str, Any] = Field(min_length=1)
    requested_modes: list[str] = Field(min_length=1)
    allowed_modes: list[str]
    fallback_mode: str
    state: Literal["allowed", "degraded", "denied"]
    decision_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProviderGovernanceExceptionContract(ContractModel):
    exception_id: str
    tenant_id: str
    project_id: str | None = None
    provider_id: str
    scope: dict[str, Any] = Field(min_length=1)
    purpose: str
    requested_waivers: list[str] = Field(min_length=1)
    approved_by: str
    expires_at: datetime
    state: Literal["active", "expired", "revoked"]
    exception_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CacheInvalidationContract(ContractModel):
    invalidation_id: str
    tenant_id: str
    project_id: str | None = None
    resource_id: str
    reason: str
    targets: list[str] = Field(min_length=1)
    state: Literal["pending", "completed", "failed"]
    invalidation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ConsentGrantContract(ContractModel):
    grant_id: str
    subject_id: str
    granted_by: str
    purposes: list[str]
    audiences: list[Audience]
    scopes: list[str]
    derivative_policy: dict[str, Any]
    expires_at: datetime | None
    state: Literal["active", "revoked", "expired"]
    revocation_propagation_required: bool = True


class PreservationManifestContract(ContractModel):
    format: Literal["sip-open-preservation"] = "sip-open-preservation"
    format_version: str = "1.1.0"
    tenant_id: str
    project_id: str
    assets: list[dict[str, Any]]
    tables: dict[str, list[dict[str, Any]]]
    semantic_identity: dict[str, Any]
    files: list[HashRef]
    root_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
