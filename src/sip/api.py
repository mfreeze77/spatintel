from __future__ import annotations
import base64
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .auth import authenticate_request
from .canonical import new_uuid, sha256_bytes
from .config import Settings
from .context import PlatformContext
from .contracts import (
    ManualExternalReceiptContract,
    ProviderCapabilityDescriptorContract,
    ProviderProgressContract,
    SpatialConversionRequestContract,
)
from .errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, SIPError, ValidationError
from .models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SignedPrincipal, SourceClass
from .observability import (
    BoundTelemetryContext,
    PlatformObservability,
    RequestTimer,
    bind_telemetry_context,
    configure_logging,
    configure_tracing,
    current_trace_id,
    current_traceparent,
    pseudonymize_identifier,
    server_span,
)
from .scene import ProxyHit
from .spatial_query import SearchQueryInput, SearchQuerySpec
API_VERSION = '1.1.0'
Principal = Annotated[SignedPrincipal, Depends(authenticate_request)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class TenantCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    tenant_id: str | None = None

class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    vertical: Literal['platform', 'construction', 'liveforever'] = 'platform'
    classification: Classification = Classification.INTERNAL
    project_id: str | None = None

class IdentityCreate(StrictModel):
    identity_id: str
    display_name: str
    identity_type: Literal['user', 'service'] = 'user'

class RoleBind(StrictModel):
    binding_id: str | None = None
    project_id: str | None = None
    identity_id: str
    role: str
    purposes: list[str] = Field(min_length=1)
    spatial_restrictions: list[dict[str, Any]] = []
    expires_at: datetime | None = None

class PolicyEvaluate(StrictModel):
    action: str
    tenant_id: str
    project_id: str | None = None
    purpose: str | None = None
    classification: Classification = Classification.INTERNAL
    required_audience: Audience | None = None
    spatial_region_id: str | None = None

class AssetIngest(StrictModel):
    content_base64: str
    media_type: str
    original_name: str
    classification: Classification = Classification.INTERNAL
    retention_class: str = 'standard'
    source_class: SourceClass = SourceClass.DIRECT_CAPTURE
    authority_class: AuthorityClass = AuthorityClass.EVIDENCE
    provenance: ProvenanceRef

class MultipartBegin(StrictModel):
    expected_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_bytes: int = Field(ge=0)
    media_type: str
    metadata: dict[str, Any] = {}

class MultipartPart(StrictModel):
    content_base64: str
    expected_sha256: str = Field(pattern='^[a-f0-9]{64}$')

class MultipartComplete(StrictModel):
    original_name: str
    classification: Classification
    retention_class: str
    source_class: SourceClass
    authority_class: AuthorityClass
    provenance: ProvenanceRef

class OperationCreate(StrictModel):
    operation_type: str
    idempotency_key: str
    input_manifest: dict[str, Any]
    max_attempts: int = Field(default=3, ge=1, le=20)

class WorkerLease(StrictModel):
    worker_id: str
    lease_seconds: int = Field(default=60, ge=10, le=3600)

class WorkerCheckpoint(StrictModel):
    worker_id: str
    progress: float = Field(ge=0, le=1)
    checkpoint: dict[str, Any]

class WorkerComplete(StrictModel):
    worker_id: str
    output: dict[str, Any]

class WorkerFail(StrictModel):
    worker_id: str
    code: str
    message: str
    retryable: bool = True

class SceneCreate(StrictModel):
    name: str

class EntityCreate(StrictModel):
    entity_type: str
    name: str
    attributes: dict[str, Any] = {}
    source_class: SourceClass
    authority_class: AuthorityClass
    confidence: float = Field(ge=0, le=1)
    provenance: ProvenanceRef
    policy: dict[str, Any] = {}
    stable_support: dict[str, Any] = {}
    entity_id: str | None = None

class CommitCreate(StrictModel):
    branch: str = 'main'
    expected_head: str
    message: str
    field_visit_id: str | None = None
    workflow_event_id: str | None = None
    change_evidence_ids: list[str] = Field(default_factory=list)
    policy_checks: dict[str, Any] = Field(default_factory=dict)
    signatures: list[dict[str, Any]] = Field(default_factory=list)
    review_state: str = 'unreviewed'
    valid_from: datetime | None = None
    valid_to: datetime | None = None

class BranchCreate(StrictModel):
    name: str
    from_commit_id: str
    protected: bool = False

class RollbackRequest(StrictModel):
    target_commit_id: str

class MeasurementCreate(StrictModel):
    entity_id: str | None = None
    value: float
    unit: str
    uncertainty: float = Field(ge=0)
    source_asset_ids: list[str] = Field(min_length=1)
    calibration: dict[str, Any] = Field(min_length=1)
    verifier_id: str | None = None
    verified: bool = False
    originating_representation_id: str | None = None
    interaction_hit: dict[str, Any] | None = None
    measurement_type: str = 'scalar'
    geometry: dict[str, Any] = Field(min_length=1)
    source_method: str = 'direct'
    measured_at: datetime | None = None
    coordinate_frame_id: str
    source_commit_id: str | None = None
    permitted_uses: list[str] = Field(default_factory=lambda: ['reference'], min_length=1)
    state: Literal['observed', 'measured', 'disputed'] = 'measured'
    supersedes_measurement_id: str | None = None
    proxy_tolerance_m: float = Field(default=0.03, gt=0, le=5)


class CoordinateFrameCreate(StrictModel):
    frame_id: str | None = None
    name: str = Field(min_length=1, max_length=256)
    parent_frame_id: str | None = None
    semantic_type: str = Field(default='local_cartesian', min_length=1, max_length=128)
    convention: Literal['right_handed_y_up_meters', 'right_handed_z_up_meters', 'source_native']
    units: Literal['meter', 'millimeter'] = 'meter'
    unit_scale_to_meters: float | None = Field(default=None, gt=0)
    original_units: str = 'meter'
    original_unit_scale_to_meters: float | None = Field(default=None, gt=0)
    axis_convention: str = 'right_handed_y_up'
    axis_directions: dict[str, str] = Field(min_length=3)
    handedness: Literal['right', 'left'] = 'right'
    origin_description: str = 'capture_session_origin'
    gravity_alignment: str | None = None
    source: str = 'platform'
    crs_identifier: str | None = None
    vertical_datum: str | None = None
    geodetic: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    transform_to_parent: list[list[float]] | None = None
    uncertainty_m: float | None = Field(default=None, ge=0)
    supersedes_frame_id: str | None = None


class SpatialTransformCreate(StrictModel):
    transform_id: str | None = None
    source_frame_id: str
    target_frame_id: str
    transform_type: Literal['SE3', 'SIM3']
    matrix: list[list[float]]
    matrix_layout: Literal['row_major', 'column_major'] = 'row_major'
    multiplication_convention: Literal['column_vector_pre_multiply', 'row_vector_post_multiply'] = 'column_vector_pre_multiply'
    direction: Literal['source_to_target', 'target_to_source'] = 'source_to_target'
    translation_units: Literal['meter', 'millimeter'] = 'meter'
    scale: float = Field(default=1.0, gt=0)
    covariance: list[list[float]] | None = None
    residual_summary: dict[str, float] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(min_length=1)
    source_type: Literal['calibration', 'registration', 'control', 'manual', 'geodetic', 'import']
    authority_class: AuthorityClass
    calibration_id: str | None = None
    solver_run_id: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    crs_pipeline: str | None = None
    grid_resources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    supersedes_transform_id: str | None = None


class GeometryManifestCreate(StrictModel):
    asset_id: str
    representation_id: str | None = None
    media_type: str
    format: str
    profile: str
    format_version: str
    coordinate_frame_id: str
    units: Literal['meter', 'millimeter']
    bounds: dict[str, list[float]]
    classification: Classification = Classification.INTERNAL
    counts: dict[str, int] = Field(min_length=1)
    compression: dict[str, Any] = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    quality: dict[str, Any] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    visual_content_classes: list[Literal['captured', 'corrected', 'reconstructed', 'inpainted', 'relit', 'generated', 'mixed']] = Field(default_factory=list)
    audience_policy: dict[str, Any] = Field(default_factory=dict)
    viewer_compatibility: list[str] = Field(default_factory=list)
    exporter_compatibility: list[str] = Field(default_factory=list)
    validation_state: Literal['pending', 'valid', 'invalid', 'deprecated'] = 'pending'
    rebuild_recipe: dict[str, Any] = Field(default_factory=dict)
    truth_label: str | None = None
    supersedes_manifest_id: str | None = None


class EvidenceCreate(StrictModel):
    asset_id: str
    source_type: str
    collected_at: datetime
    collected_by: str
    device_or_tool: str
    location_context: dict[str, Any] = Field(min_length=1)
    relevant_region: dict[str, Any] = Field(min_length=1)
    relevant_time_start: datetime
    relevant_time_end: datetime
    retention_class: str
    chain_of_custody: list[dict[str, Any]] | None = None
    legal_hold: bool = False
    consent_scope: dict[str, Any] = Field(min_length=1)
    access_policy: dict[str, Any] = Field(min_length=1)
    policy: dict[str, Any] = Field(default_factory=dict)


class AssertionCreate(StrictModel):
    subject_id: str
    predicate: str
    object_value: Any
    source_class: SourceClass
    authority_class: AuthorityClass
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    asserted_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    producer_id: str | None = None
    conflicts_with_assertion_ids: list[str] = Field(default_factory=list)
    supersedes_assertion_id: str | None = None
    state: Literal['active', 'disputed', 'superseded', 'withdrawn'] = 'active'


class DerivationCreate(StrictModel):
    activity_type: str = Field(min_length=1)
    input_ids: list[str] = Field(min_length=1)
    input_hashes: list[str] = Field(min_length=1)
    algorithm_id: str
    algorithm_version: str
    model_manifest_id: str | None = None
    parameters_hash: str = Field(pattern='^[a-f0-9]{64}$')
    environment_hash: str = Field(pattern='^[a-f0-9]{64}$')
    code_commit: str
    container_digest: str | None = None
    output_ids: list[str] = Field(min_length=1)
    output_hashes: list[str] = Field(min_length=1)
    software: dict[str, Any] = Field(min_length=1)
    quality: dict[str, Any] = Field(min_length=1)
    validation: dict[str, Any] = Field(min_length=1)
    started_at: datetime
    completed_at: datetime


class AnnotationCreate(StrictModel):
    coordinate_frame_id: str
    support_type: Literal['world_point', 'semantic_entity', 'surface_coordinate', 'plane', 'line', 'volume', 'document_region']
    support: dict[str, Any]
    uncertainty_m: float = Field(ge=0)
    source_class: SourceClass
    authority_class: AuthorityClass
    entity_id: str | None = None
    position: list[float] | None = None
    orientation: list[float] | None = None
    normal: list[float] | None = None
    policy: dict[str, Any] = Field(default_factory=dict)
    authored_from_representation_id: str | None = None


class AnnotationRemap(StrictModel):
    source_representation_id: str
    target_representation_id: str
    max_residual_m: float = Field(default=0.05, ge=0)
    min_confidence: float = Field(default=0.8, ge=0, le=1)


class CoordinateUnitConversion(StrictModel):
    values: list[float] = Field(min_length=1)
    from_units: str
    to_units: str = 'meter'
    from_scale_to_meters: float | None = Field(default=None, gt=0)
    to_scale_to_meters: float | None = Field(default=None, gt=0)


class SceneTagCreate(StrictModel):
    commit_id: str
    name: str = Field(min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneMerge(StrictModel):
    target_branch: str
    source_branch: str
    base_commit_id: str
    message: str
    approved_review_categories: list[str] = Field(default_factory=list)

class ProxyResolve(StrictModel):
    representation_id: str
    point: list[float] = Field(min_length=3, max_length=3)
    semantic_entity_id: str | None = None
    tolerance_m: float = Field(default=0.05, gt=0, le=5)

class ProviderRegister(StrictModel):
    manifest: dict[str, Any]

class ProviderAuthorize(StrictModel):
    classification: Classification
    purpose: str
    region: str
    external: bool = False

class RepresentationCreate(StrictModel):
    scene_id: str
    asset_id: str
    kind: RepresentationKind
    provider_id: str
    coordinate_frame_id: str
    source_class: SourceClass
    authority_class: AuthorityClass
    lossy: bool
    intended_uses: list[str]
    prohibited_uses: list[str] = []
    quality: dict[str, Any] = {}
    provenance: dict[str, Any]
    support_map: dict[str, Any] = {}
    operation_id: str | None = None
    representation_id: str | None = None
    format_metadata: dict[str, Any] = Field(default_factory=dict)
    derivation_policy: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    information_losses: list[str] = Field(default_factory=list)
    privacy_inheritance: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    fallback_representation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class RepresentationReview(StrictModel):
    approved_uses: list[str]
    metrics: dict[str, Any]
    passed: bool

class RepresentationPublish(StrictModel):
    commit_id: str
    role: str
    transform: list[list[float]] | None = None
    intended_uses: list[str] | None = None
    review_decision: dict[str, Any] | None = None
    audience_policy: dict[str, Any] | None = None
    client_profile: dict[str, Any] | None = None


class RepresentationInvalidate(StrictModel):
    changed_resource_id: str
    reason: str = Field(min_length=1)
    queue_regeneration: bool = True


class HybridViewSelect(StrictModel):
    scene_id: str
    intended_use: str
    audience: str
    role: str | None = None
    client_profile: dict[str, Any] = Field(default_factory=dict)

class SearchIndex(StrictModel):
    text: str
    entity_id: str | None = None
    entity_type: str | None = None
    asset_id: str | None = None
    embedding: list[float] | None = None
    embedding_model_manifest_id: str | None = None
    embedding_source_region: dict[str, Any] | None = None
    spatial_bounds: dict[str, Any] | None = None
    spatial_frame_id: str | None = None
    floor_id: str | None = None
    room_id: str | None = None
    temporal_start: datetime | None = None
    temporal_end: datetime | None = None
    source_class: SourceClass = SourceClass.OBSERVED
    authority_class: AuthorityClass = AuthorityClass.EVIDENCE
    confidence: float = Field(default=1.0, ge=0, le=1)
    tags: list[str] = []
    workflow_status: str | None = None
    relationships: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    source_sequence: int = Field(default=0, ge=0)
    index_sequence: int = Field(default=0, ge=0)
    scene_commit_id: str | None = None
    classification: Classification = Classification.INTERNAL
    policy: dict[str, Any] = {}

class SearchQuery(SearchQueryInput):
    """Public query body; tenant, project, and authorization scope are server-controlled."""


class SavedQueryCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    query: SearchQuery
    permissions: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    expected_result_contract: dict[str, Any] = {}
    supersedes_saved_query_id: str | None = None

class SavedQueryExecute(StrictModel):
    parameters: dict[str, Any] = {}

class AgentToolExecute(StrictModel):
    arguments: dict[str, Any]

class AgentClaimsValidate(StrictModel):
    claims: list[dict[str, Any]]

class AgentRequestCheck(StrictModel):
    request_kind: str
    simulation_enabled: bool = False
    consent_verified: bool = False


class ConstructionHierarchy(StrictModel):
    record_type: str
    name: str
    parent_id: str | None = None
    state: str = 'observed'
    attributes: dict[str, Any] = {}

class ConstructionSystem(StrictModel):
    system_type: str
    parent_id: str | None = None
    entity_id: str | None = None
    state: str
    data: dict[str, Any]
    evidence_asset_ids: list[str] = []

class ConstructionSystemVerification(StrictModel):
    method: str = Field(min_length=1, max_length=256)
    scope: dict[str, Any]
    exclusions: list[str] = Field(default_factory=list)
    evidence_asset_ids: list[str] = Field(min_length=1)
    signature_asset_id: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=256)

class ConstructionDocument(StrictModel):
    document_type: str
    asset_id: str
    parent_id: str | None = None
    page_region: dict[str, Any] | None = None
    spatial_anchor: dict[str, Any] | None = None
    data: dict[str, Any] = {}

class DeficiencyCreate(StrictModel):
    entity_id: str
    description: str
    severity: str
    evidence_asset_ids: list[str] = []

class DeficiencyRetest(StrictModel):
    correction: str
    correction_asset_ids: list[str]
    test_result: Literal['pass', 'fail']
    test_asset_ids: list[str]

class ConsentGrantCreate(StrictModel):
    subject_id: str
    purposes: list[str] = Field(min_length=1)
    audiences: list[Audience] = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    derivative_policy: dict[str, Any]
    expires_at: datetime | None = None

class ConsentRevoke(StrictModel):
    reason: str

class MemoryCreate(StrictModel):
    record_type: str
    subject_id: str | None = None
    subject_scope: dict[str, Any] | None = None
    related_ids: list[str] = []
    data: dict[str, Any]
    source_class: SourceClass
    confidence: float = Field(ge=0, le=1)
    evidence_asset_ids: list[str] = []
    audience: Audience
    purpose: str
    generated_lineage: dict[str, Any] | None = None

class LiveForeverRecordReview(StrictModel):
    target_source_class: Literal['corroborated', 'verified']
    rationale: str = Field(min_length=1)
    evidence_asset_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    idempotency_key: str = Field(min_length=1, max_length=256)

class ConflictingRecollections(StrictModel):
    subject_id: str
    event_key: str
    recollections: list[dict[str, Any]] = Field(min_length=2)
    audience: Audience

class ExperienceRequest(StrictModel):
    subject_id: str
    requested_features: dict[str, bool]
    audience: Audience


class ConstructionSurveyCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    objectives: list[str] = Field(min_length=1)
    required_place_ids: list[str] = Field(min_length=1)
    required_system_types: list[str] = Field(default_factory=list)
    sensitive_regions: list[dict[str, Any]] = Field(default_factory=list)
    control_requirements: dict[str, Any] = Field(default_factory=dict)
    measurement_requirements: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    deliverables: list[dict[str, Any]] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    baseline_commit_id: str | None = None
    return_visit_of_id: str | None = None


class ConstructionFieldVisitCreate(StrictModel):
    scope: dict[str, Any] = Field(default_factory=dict)
    capture_ids: list[str] = Field(min_length=1)
    checklist: list[dict[str, Any]] = Field(min_length=1)
    detail_evidence: list[dict[str, Any]] = Field(default_factory=list)
    inaccessible_regions: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    tracking: dict[str, Any] = Field(default_factory=dict)
    registration: dict[str, Any] = Field(default_factory=dict)
    controls: dict[str, Any] = Field(default_factory=dict)
    inventory: dict[str, Any] = Field(default_factory=dict)
    unresolved_questions: list[dict[str, Any]] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    exact_prior_commit_id: str | None = None
    complete: bool = True


class ConstructionSurveyReview(StrictModel):
    decision: Literal['accept', 'reject', 'request_changes']
    checklist: dict[str, Any] = Field(default_factory=dict)
    accepted_commit_id: str | None = None
    limitations: list[str] = Field(default_factory=list)


class ConstructionDocumentRevisionCreate(StrictModel):
    stable_document_id: str | None = None
    document_type: str
    title: str = Field(min_length=1, max_length=512)
    revision: str = Field(min_length=1, max_length=64)
    issue_date: str
    issuer: str
    status: str
    asset_id: str
    source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    page_count: int = Field(ge=1)
    permissions: dict[str, Any] = Field(default_factory=dict)
    page_regions: list[dict[str, Any]] = Field(default_factory=list)
    spatial_links: list[dict[str, Any]] = Field(default_factory=list)
    extraction: dict[str, Any] = Field(default_factory=dict)
    review: dict[str, Any] = Field(default_factory=dict)
    supersedes_revision_id: str | None = None


class ConstructionIssueCreate(StrictModel):
    issue_type: str
    description: str = Field(min_length=1)
    evidence: list[dict[str, Any]] = Field(min_length=1)
    severity: str
    idempotency_key: str = Field(min_length=1, max_length=256)
    entity_id: str | None = None
    place_id: str | None = None
    observed_commit_id: str | None = None
    responsible_party: str | None = None
    due_at: datetime | None = None
    permissions: dict[str, Any] = Field(default_factory=dict)


class ConstructionIssueTransition(StrictModel):
    target_state: str
    evidence: list[dict[str, Any]] = Field(min_length=1)
    note: str = Field(min_length=1)
    residual_limitations: list[str] = Field(default_factory=list)


class ConstructionCommissioningCreate(StrictModel):
    system_type: str
    entity_ids: list[str] = Field(min_length=1)
    procedure: dict[str, Any] = Field(min_length=1)
    prerequisites: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(min_length=1)
    participants: list[dict[str, Any]] = Field(min_length=1)
    instruments: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    issue_id: str | None = None
    retest_of_id: str | None = None
    accept: bool = False


class ConstructionInterchangeCreate(StrictModel):
    format: str
    direction: Literal['import', 'export']
    source_asset_id: str = Field(min_length=1, max_length=64)
    source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    schema_version: str
    units: str
    crs: dict[str, Any] = Field(default_factory=dict)
    owner_history: dict[str, Any] = Field(default_factory=dict)
    global_ids: list[str] = Field(default_factory=list)
    classifications: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    geometry_conversion_report: dict[str, Any] = Field(default_factory=dict)
    unsupported_constructs: list[dict[str, Any]] = Field(default_factory=list)
    alignment: dict[str, Any] = Field(default_factory=dict)
    mappings: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    truth_labels: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)


class ConstructionHandoffCreate(StrictModel):
    scope: dict[str, Any] = Field(default_factory=dict)
    accepted_scene_commit_id: str
    warranties: list[dict[str, Any]] = Field(default_factory=list)
    training: list[dict[str, Any]] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    audience_profiles: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    classification: str = Field(default='internal', min_length=1, max_length=64)
    audience: str = Field(default='owner', min_length=1, max_length=64)
    purpose: str = Field(default='owner_handoff', min_length=1, max_length=128)
    restricted_export_approval_id: str | None = None


class ConstructionRestrictedExportApprovalCreate(StrictModel):
    scope: dict[str, Any] = Field(min_length=1)
    accepted_scene_commit_id: str
    warranties: list[dict[str, Any]] = Field(default_factory=list)
    training: list[dict[str, Any]] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    audience_profiles: dict[str, Any] = Field(default_factory=dict)
    handoff_idempotency_key: str = Field(min_length=1, max_length=256)
    classification: str = Field(min_length=1, max_length=64)
    audience: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=128)
    expires_at: datetime


class LiveForeverGovernanceCreate(StrictModel):
    record_type: str
    subject_id: str
    grantor_id: str
    authority_basis: str
    data_scope: dict[str, Any] = Field(default_factory=dict)
    purposes: list[str] = Field(min_length=1)
    modalities: list[str] = Field(default_factory=list)
    audiences: list[Audience] = Field(min_length=1)
    providers: list[str] = Field(default_factory=list)
    geography: dict[str, Any] = Field(default_factory=dict)
    effective_at: datetime
    expires_at: datetime | None = None
    posthumous_rules: dict[str, Any] = Field(default_factory=dict)
    evidence_asset_ids: list[str] = Field(default_factory=list)
    successor_ids: list[str] = Field(default_factory=list)
    dispute: dict[str, Any] = Field(default_factory=dict)
    freeze_high_risk: bool = False
    idempotency_key: str = Field(min_length=1, max_length=256)
    consent_grant_id: str | None = None


class LiveForeverInterviewCreate(StrictModel):
    subject_id: str
    participants: list[dict[str, Any]] = Field(min_length=1)
    consent_context: dict[str, Any] = Field(min_length=1)
    recording_state: str
    source_media_ids: list[str] = Field(min_length=1)
    timeline: dict[str, Any] = Field(min_length=1)
    device: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    interruptions: list[dict[str, Any]] = Field(default_factory=list)
    question_lineage: list[dict[str, Any]] = Field(default_factory=list)
    pacing_policy: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    complete: bool = False


class LiveForeverTranscriptSegmentCreate(StrictModel):
    segment_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    speaker_label: str
    speaker_confidence: float = Field(ge=0, le=1)
    original_text: str
    source_media_id: str
    spatial_anchor: dict[str, Any] | None = None
    private_marks: list[dict[str, Any]] = Field(default_factory=list)
    followup_suggestions: list[dict[str, Any]] = Field(default_factory=list)


class LiveForeverTranscriptCorrection(StrictModel):
    edited_text: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    review_state: str = 'reviewed'


class LiveForeverRecordRevision(StrictModel):
    correction_type: str
    reason: str = Field(min_length=1)
    changes: dict[str, Any] = Field(min_length=1)
    audience: Audience | None = None
    purpose: str = 'family_review'


class LiveForeverEditionCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    audience: Audience
    purpose: str
    presentation_choices: dict[str, Any] = Field(default_factory=dict)
    scene_commit_id: str | None = None
    narrative_path: list[dict[str, Any]] = Field(default_factory=list)
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    publish: bool = False
    supersedes_edition_id: str | None = None


class LiveForeverDerivativeCreate(StrictModel):
    derivative_type: str
    source_ids: list[str] = Field(min_length=1)
    subject_ids: list[str] = Field(min_length=1)
    consent_grant_ids: list[str] = Field(min_length=1)
    audience: Audience
    classification: str
    retention: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    generation_lineage: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)


class LiveForeverPreservationCreate(StrictModel):
    edition_id: str
    originals: list[dict[str, Any]] = Field(min_length=1)
    technical_metadata: dict[str, Any] = Field(default_factory=dict)
    rights_consent: list[dict[str, Any]] = Field(default_factory=list)
    memory_graph: dict[str, Any] = Field(default_factory=dict)
    scene_manifests: list[dict[str, Any]] = Field(default_factory=list)
    open_assets: list[dict[str, Any]] = Field(default_factory=list)
    human_guide: dict[str, Any] = Field(min_length=1)
    offline_fallback: dict[str, Any] = Field(min_length=1)
    replicas: list[dict[str, Any]] = Field(default_factory=list)
    format_migrations: list[dict[str, Any]] = Field(default_factory=list)
    succession: dict[str, Any] = Field(default_factory=dict)
    shutdown: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)


class NotificationCreate(StrictModel):
    recipient_id: str
    channel: Literal['in_app', 'email', 'sms', 'push']
    template_id: str
    payload: dict[str, Any]
    sensitive: bool = False

class CommentCreate(StrictModel):
    body: str
    scene_commit_id: str | None = None
    entity_id: str | None = None
    anchor: dict[str, Any] | None = None
    supersedes_comment_id: str | None = None

class TaskCreate(StrictModel):
    title: str
    description: str
    entity_id: str | None = None
    assignee_id: str | None = None
    priority: str = 'normal'
    due_at: datetime | None = None

class TaskTransition(StrictModel):
    state: str



class ProviderCapabilityCreate(ProviderCapabilityDescriptorContract):
    manifest_hash: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')
    manifest_signature: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')


class ProviderPromotionCreate(StrictModel):
    state: Literal['discovered', 'research_isolated', 'shadow', 'limited', 'active', 'deprecated', 'blocked']
    data_classifications: list[Classification] = Field(min_length=1)
    scene_classes: list[str] = Field(min_length=1)
    output_roles: list[str] = Field(min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    execution_zones: list[str] = Field(min_length=1)
    hardware_profiles: list[str] = Field(min_length=1)
    benchmark_evidence_hash: str = Field(pattern='^[a-f0-9]{64}$')
    policy_snapshot_hash: str = Field(pattern='^[a-f0-9]{64}$')
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    promotion_id: str | None = None


class HybridCandidateComplete(StrictModel):
    output_asset_id: str
    output_asset_sha256: str = Field(pattern='^(sha256:)?[a-f0-9]{64}$')
    output_role: str = Field(min_length=1)
    kind: RepresentationKind
    coordinate_frame_id: str
    source_class: SourceClass
    authority_class: AuthorityClass
    lossy: bool
    intended_uses: list[str] = Field(min_length=1)
    prohibited_uses: list[str] = Field(default_factory=list)
    quality: dict[str, Any] = Field(min_length=1)
    support_map: dict[str, Any] = Field(default_factory=dict)
    worker_receipt_hash: str = Field(pattern='^[a-f0-9]{64}$')
    candidate_core_hash: str = Field(pattern='^[a-f0-9]{64}$')
    format_metadata: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    information_losses: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridWorkerLeaseRenew(StrictModel):
    lease_ttl_seconds: int = Field(default=900, ge=30, le=900)


class HybridProviderFailureCreate(StrictModel):
    error_code: str = Field(pattern=r'^[A-Z][A-Z0-9_]{2,127}$')
    retryable: bool = False
    cleanup_receipt_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    cleanup_verified: bool
    last_durable_checkpoint_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    resource_use: dict[str, Any] = Field(default_factory=dict)


class HybridValidationCreate(StrictModel):
    intended_use: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    validator_manifest_hash: str = Field(pattern='^[a-f0-9]{64}$')
    metrics: dict[str, Any] = Field(min_length=1)
    thresholds: dict[str, Any] = Field(min_length=1)
    coverage: dict[str, Any] = Field(min_length=1)
    topology: dict[str, Any] = Field(min_length=1)
    coordinate_validation: dict[str, Any] = Field(min_length=1)
    behavior_validation: dict[str, Any] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class HybridManualExportCreate(StrictModel):
    approved_derivative_asset_ids: list[str] = Field(min_length=1)


class HybridManualReturnCreate(StrictModel):
    one_time_return_code: str = Field(min_length=1)
    receipt: ManualExternalReceiptContract
    returned_outputs: list[dict[str, str]] = Field(min_length=1)


class HybridViewCreate(StrictModel):
    scene_revision_id: str
    purpose: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    device_profile: str = Field(min_length=1)
    time_context: dict[str, Any] = Field(default_factory=dict)
    intended_uses: list[str] = Field(min_length=1)
    spatial_region_ids: list[str] = Field(default_factory=list)
    ttl_seconds: int = Field(default=300, ge=30, le=3600)


class ViewerSessionCreate(StrictModel):
    purpose: str = Field(min_length=1)
    audience: Audience = Audience.PROJECT
    publication_class: Literal['working', 'audit', 'report'] = 'working'
    scene_commit_ids: list[str] = Field(min_length=1, max_length=2)
    saved_hybrid_views: list[dict[str, Any]] = Field(default_factory=list)
    device_profile: str = Field(default='web_desktop_reference', min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    spatial_region_ids: list[str] = Field(default_factory=list)
    camera: dict[str, Any] = Field(min_length=1)
    navigation_mode: Literal['orbit', 'walk', 'fly', 'teleport', 'guided'] = 'orbit'
    layers: list[dict[str, Any]] = Field(min_length=1)
    clipping_planes: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    section_box: dict[str, Any] | None = None
    selected_entity_ids: list[str] = Field(default_factory=list)
    timeline: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    redaction: dict[str, Any] = Field(default_factory=dict)
    accessibility: dict[str, Any] = Field(default_factory=lambda: {
        'reduced_motion': False,
        'high_contrast': False,
        'captions': True,
    })
    comparison: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    supersedes_session_id: str | None = None


class ViewerSessionReplay(StrictModel):
    ttl_seconds: int = Field(default=300, ge=30, le=900)


class TemporalComparisonCreate(StrictModel):
    baseline_commit_id: str
    candidate_commit_id: str
    viewer_session_id: str | None = None
    comparable_region: dict[str, Any] = Field(min_length=1)
    registration_quality: dict[str, Any] = Field(min_length=1)
    thresholds: dict[str, Any] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    algorithm_id: str = Field(min_length=1)
    algorithm_version: str = Field(min_length=1)
    executable_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    parameters_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    observed_coverage: dict[str, Any] = Field(min_length=1)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=256)


class ChangeReviewCreate(StrictModel):
    outcome: Literal['accepted', 'rejected', 'disputed']
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    policy_snapshot_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=256)


class ApplySemanticChanges(StrictModel):
    branch: str = 'main'
    expected_head: str
    message: str = Field(min_length=1)


class ChangeBenchmarkCreate(StrictModel):
    algorithm_id: str = Field(min_length=1)
    algorithm_version: str = Field(min_length=1)
    executable_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    benchmark_profile: str = Field(min_length=1)
    fixture_root_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    metrics_by_class: dict[str, dict[str, float]] = Field(min_length=1)
    environment: dict[str, Any] = Field(min_length=1)


class InteractionProfileCreate(StrictModel):
    profile_id: str
    profile_type: Literal['collision', 'navigation', 'occlusion', 'spatial_audio', 'picking']
    version: str
    actor: dict[str, Any] = Field(min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    limits: dict[str, Any] = Field(min_length=1)
    behavior: dict[str, Any] = Field(min_length=1)
    validation: dict[str, Any] = Field(min_length=1)
    safety_claims: list[str] = Field(default_factory=list)
    validator_id: str = Field(min_length=1)
    validator_manifest_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    validation_evidence_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    validated_at: datetime
    review_due_at: datetime | None = None
    expires_at: datetime | None = None


class RepresentationFamilyCreate(StrictModel):
    family_id: str | None = None
    role: str = Field(min_length=1)
    coordinate_frame_id: str
    tile_scheme_id: str = Field(min_length=1)
    lods: list[dict[str, Any]] = Field(min_length=1)
    seam_validation_report_id: str | None = None
    fallback_representation_id: str | None = None

class ModelRegister(StrictModel):
    manifest: dict[str, Any]

class ModelAuthorize(StrictModel):
    checkpoint_hash: str
    purpose: str
    commercial: bool
    classification: Classification
    region: str = 'local'

class ThreatManifestCreate(StrictModel):
    scope: str
    threats: list[dict[str, Any]]
    misuse_cases: list[dict[str, Any]]
    public_viewer_analysis: dict[str, Any]
    residual_risks: list[dict[str, Any]]
    owner: str
    review_trigger: str


class PrivilegedAccessCreate(StrictModel):
    project_id: str | None = None
    subject_id: str
    actions: list[str]
    resource_scope: dict[str, Any]
    purpose: str
    mfa_method: str
    mfa_verified_at: datetime
    duration_seconds: int = Field(ge=60, le=3600)
    requested_by: str


class WorkloadIdentityCreate(StrictModel):
    project_id: str | None = None
    workload_id: str
    audience: str
    scopes: list[str]
    purpose: str
    ttl_seconds: int = Field(ge=30, le=3600)


class WorkloadIdentityValidate(StrictModel):
    token: str
    workload_id: str
    audience: str
    required_scope: str
    purpose: str
    project_id: str | None = None


class KeyScopeCreate(StrictModel):
    project_id: str | None = None
    person_id: str | None = None
    key_id: str
    backend: str
    recovery_policy: dict[str, Any]
    rotated_from_key_id: str | None = None


class KeyAccessCreate(StrictModel):
    project_id: str | None = None
    actor_or_workload: str
    purpose: str
    action: str
    resource_scope: dict[str, Any]
    outcome: str
    details: dict[str, Any] = Field(default_factory=dict)


class EmergencyKeyRevoke(StrictModel):
    project_id: str | None = None
    reason: str
    residual_timeline: list[dict[str, Any]]


class PrivacyInventoryCreate(StrictModel):
    project_id: str | None = None
    data_category: str
    purpose: str
    legal_basis: str
    consent_basis: str | None = None
    processors: list[dict[str, Any]]
    residency: dict[str, Any]
    retention: dict[str, Any]
    security_controls: list[str]
    rights_workflow: dict[str, Any]
    classification: str


class PrivacyImpactCreate(StrictModel):
    project_id: str | None = None
    change_type: str
    change_reference: str
    purpose: str
    data_categories: list[str]
    processors: list[str]
    risks: list[dict[str, Any]]
    controls: list[dict[str, Any]]
    residual_risk: str
    decision: str
    expires_at: datetime | None = None


class PrivacyRightsCreate(StrictModel):
    project_id: str | None = None
    subject_id: str
    request_type: str
    scope: dict[str, Any]
    requested_by: str
    due_days: int = Field(default=30, ge=1, le=365)


class PrivacyRightsComplete(StrictModel):
    project_id: str | None = None
    outcomes: dict[str, Any]
    evidence: list[dict[str, Any]] = Field(min_length=1)


class SecurityIncidentCreate(StrictModel):
    project_id: str | None = None
    incident_type: str
    severity: str
    affected_subjects: list[str] = Field(default_factory=list)
    affected_resources: list[dict[str, Any]] = Field(default_factory=list)
    containment: list[dict[str, Any]]
    notification_decision: dict[str, Any]
    evidence: list[dict[str, Any]]


class ProviderIncidentWithdrawalCreate(StrictModel):
    provider_id: str
    source_asset_ids: list[str] = Field(default_factory=list)
    derivative_asset_ids: list[str] = Field(default_factory=list)
    publication_ids: list[str] = Field(default_factory=list)
    cache_resource_ids: list[str] = Field(default_factory=list)
    export_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]]
    notification_decision: dict[str, Any]


class TransportVerificationCreate(StrictModel):
    endpoint: str
    protocol: str
    minimum_tls_version: str
    certificate_validated: bool
    channel_authentication: str
    evidence: dict[str, Any]


class CaptureFinalizationCreate(StrictModel):
    capture_id: str
    package_root_hash: str
    archive_sha256: str
    device: dict[str, Any]
    app: dict[str, Any]
    signer_id: str
    verification_result: str
    verification: dict[str, Any]


class ProviderOutputValidationCreate(StrictModel):
    provider_id: str
    operation_id: str
    output_sha256: str
    media_type: str
    byte_count: int = Field(ge=0)
    validations: dict[str, Any]


class ImmersiveSafetyCreate(StrictModel):
    scene_id: str
    checks: dict[str, Any]
    requested_modes: list[str]


class AuditSecurityVerify(StrictModel):
    project_id: str | None = None
    referenced_manifests: list[dict[str, Any]] = Field(default_factory=list)


class ProviderExecutionAuthorize(StrictModel):
    classification: str
    purpose: str
    region: str
    external: bool = False
    audience: str = "private"
    retention_days: int = Field(default=0, ge=0)
    telemetry: dict[str, Any] = Field(default_factory=dict)


class ProviderExceptionCreate(StrictModel):
    scope: dict[str, Any]
    purpose: str
    requested_waivers: list[str] = Field(default_factory=list)
    duration_seconds: int = Field(ge=60, le=2592000)


class CacheInvalidationCreate(StrictModel):
    resource_id: str
    reason: str
    targets: list[str]


class SupplyChainReleaseCreate(StrictModel):
    version: str
    source_commit: str
    source_root: str
    component_manifests: dict[str, Any]
    evidence: dict[str, Any]
    rollback_plan: dict[str, Any]
    environment_policy: dict[str, Any]
    emergency_patch: bool = False
    retrospective_review_due_at: datetime | None = None


def _context(request: Request) -> PlatformContext:
    return request.app.state.platform

def _require(request: Request, principal: SignedPrincipal, *, action: str, tenant_id: str, project_id: str | None=None, purpose: str | None=None, classification: Classification | str=Classification.INTERNAL, audience: Audience | None=None) -> None:
    value = classification.value if isinstance(classification, Classification) else classification
    _context(request).policy.require(principal, action=action, tenant_id=tenant_id, project_id=project_id, purpose=purpose, classification=value, required_audience=audience)

def _json(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json')
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value

def _routers() -> dict[str, APIRouter]:
    control = APIRouter(tags=['control'])
    identity = APIRouter(tags=['identity-policy'])
    capture = APIRouter(tags=['capture'])
    workflow = APIRouter(tags=['workflow'])
    scene = APIRouter(tags=['scene'])
    evidence = APIRouter(tags=['evidence'])
    search = APIRouter(tags=['search'])
    export = APIRouter(tags=['export'])
    notification = APIRouter(tags=['notification'])
    audit = APIRouter(tags=['audit'])
    representation = APIRouter(tags=['representation'])
    providers = APIRouter(tags=['provider-registry'])
    publisher = APIRouter(tags=['representation-publisher'])
    construction = APIRouter(tags=['construction'])
    memory = APIRouter(tags=['liveforever'])
    collaboration = APIRouter(tags=['collaboration'])
    security_ops = APIRouter(tags=['security-ops'])

    @control.get('/version', operation_id='get_version')
    def version(request: Request) -> dict[str, Any]:
        return {'version': API_VERSION, 'environment': _context(request).settings.environment}

    @control.post('/v1/tenants', status_code=201, operation_id='create_tenant')
    def create_tenant(body: TenantCreate, request: Request, principal: Principal) -> dict[str, Any]:
        if 'bootstrap_admin' not in principal.roles and 'tenant_admin' not in principal.roles:
            raise AuthorizationError('TENANT_CREATE_DENIED', 'tenant creation requires bootstrap administration')
        tenant_id = _context(request).tenancy.create_tenant(body.name, tenant_id=body.tenant_id, actor_id=principal.subject_id)
        return {'tenant_id': tenant_id}

    @control.post('/v1/tenants/{tenant_id}/projects', status_code=201, operation_id='create_project')
    def create_project(tenant_id: str, body: ProjectCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:create', tenant_id=tenant_id)
        project_id = _context(request).tenancy.create_project(tenant_id, body.name, vertical=body.vertical, classification=body.classification.value, project_id=body.project_id, actor_id=principal.subject_id)
        return {'project_id': project_id}

    @identity.post('/v1/tenants/{tenant_id}/identities', status_code=201, operation_id='create_identity')
    def create_identity(tenant_id: str, body: IdentityCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=tenant_id)
        _context(request).policy.create_identity(tenant_id, body.identity_id, body.display_name, body.identity_type)
        return {'identity_id': body.identity_id}

    @identity.post('/v1/tenants/{tenant_id}/role-bindings', status_code=201, operation_id='bind_role')
    def bind_role(tenant_id: str, body: RoleBind, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=tenant_id, project_id=body.project_id)
        binding_id = body.binding_id or new_uuid()
        _context(request).policy.bind_role(binding_id=binding_id, tenant_id=tenant_id, project_id=body.project_id, identity_id=body.identity_id, role=body.role, purposes=body.purposes, spatial_restrictions=body.spatial_restrictions, expires_at=body.expires_at)
        return {'binding_id': binding_id}

    @identity.post('/v1/policy/evaluate', operation_id='evaluate_policy')
    def evaluate_policy(body: PolicyEvaluate, request: Request, principal: Principal) -> dict[str, Any]:
        decision = _context(request).policy.authorize(principal, action=body.action, tenant_id=body.tenant_id, project_id=body.project_id, purpose=body.purpose, classification=body.classification.value, required_audience=body.required_audience, spatial_region_id=body.spatial_region_id)
        return _json(decision)

    @capture.post('/v1/projects/{project_id}/assets', status_code=201, operation_id='ingest_asset')
    def ingest_asset(project_id: str, body: AssetIngest, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='asset:create', tenant_id=principal.tenant_id, project_id=project_id, classification=body.classification)
        try:
            payload = base64.b64decode(body.content_base64, validate=True)
        except Exception as exc:
            raise ValidationError('ASSET_BASE64_INVALID', 'asset content is not valid base64') from exc
        result = _context(request).assets.ingest_bytes(tenant_id=principal.tenant_id, project_id=project_id, data=payload, media_type=body.media_type, original_name=body.original_name, classification=body.classification, retention_class=body.retention_class, source_class=body.source_class, authority_class=body.authority_class, provenance=body.provenance, actor_id=principal.subject_id)
        return _json(result)

    @capture.get('/v1/projects/{project_id}/assets/{asset_id}', operation_id='get_asset')
    def get_asset(project_id: str, asset_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='asset:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _json(_context(request).assets.get(principal.tenant_id, project_id, asset_id))

    @capture.get('/v1/projects/{project_id}/assets/{asset_id}/content', operation_id='read_asset')
    def read_asset(project_id: str, asset_id: str, request: Request, principal: Principal) -> Response:
        _require(request, principal, action='asset:read', tenant_id=principal.tenant_id, project_id=project_id)
        ref = _context(request).assets.get(principal.tenant_id, project_id, asset_id)
        payload = _context(request).assets.read(principal.tenant_id, project_id, asset_id, actor_id=principal.subject_id)
        return Response(content=payload, media_type=ref.media_type, headers={'Digest': f'sha-256={ref.sha256}'})

    @capture.post('/v1/projects/{project_id}/assets/{asset_id}/read-token', operation_id='issue_asset_read_token')
    def issue_asset_token(project_id: str, asset_id: str, request: Request, principal: Principal, ttl_seconds: int=Query(default=300, ge=1, le=3600)) -> dict[str, Any]:
        _require(request, principal, action='asset:read', tenant_id=principal.tenant_id, project_id=project_id)
        token = _context(request).assets.issue_read_token(principal.tenant_id, project_id, asset_id, subject_id=principal.subject_id, ttl_seconds=ttl_seconds)
        return {'token': token, 'expires_in_seconds': ttl_seconds}

    @capture.post('/v1/projects/{project_id}/multipart', status_code=201, operation_id='begin_multipart')
    def begin_multipart(project_id: str, body: MultipartBegin, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='asset:create', tenant_id=principal.tenant_id, project_id=project_id)
        upload_id = _context(request).assets.begin_multipart(tenant_id=principal.tenant_id, project_id=project_id, expected_sha256=body.expected_sha256, expected_bytes=body.expected_bytes, media_type=body.media_type, metadata=body.metadata, actor_id=principal.subject_id)
        return {'upload_id': upload_id}

    @capture.put('/v1/multipart/{upload_id}/parts/{part_number}', operation_id='put_multipart_part')
    def put_multipart_part(upload_id: str, part_number: int, body: MultipartPart, request: Request, principal: Principal) -> dict[str, Any]:
        status = _context(request).assets.multipart_status(upload_id, tenant_id=principal.tenant_id)
        _require(request, principal, action='asset:create', tenant_id=principal.tenant_id, project_id=status['project_id'])
        try:
            payload = base64.b64decode(body.content_base64, validate=True)
        except Exception as exc:
            raise ValidationError('CHUNK_BASE64_INVALID', 'chunk content is not valid base64') from exc
        return _context(request).assets.put_part(upload_id, part_number, payload, body.expected_sha256, tenant_id=principal.tenant_id, project_id=status['project_id'])

    @capture.get('/v1/multipart/{upload_id}', operation_id='get_multipart_status')
    def get_multipart_status(upload_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        status = _context(request).assets.multipart_status(upload_id, tenant_id=principal.tenant_id)
        _require(request, principal, action='asset:create', tenant_id=principal.tenant_id, project_id=status['project_id'])
        return status

    @capture.post('/v1/multipart/{upload_id}/complete', operation_id='complete_multipart')
    def complete_multipart(upload_id: str, body: MultipartComplete, request: Request, principal: Principal) -> dict[str, Any]:
        status = _context(request).assets.multipart_status(upload_id, tenant_id=principal.tenant_id)
        _require(request, principal, action='asset:create', tenant_id=principal.tenant_id, project_id=status['project_id'])
        result = _context(request).assets.complete_multipart(upload_id, original_name=body.original_name, classification=body.classification, retention_class=body.retention_class, source_class=body.source_class, authority_class=body.authority_class, provenance=body.provenance, actor_id=principal.subject_id, tenant_id=principal.tenant_id, project_id=status['project_id'])
        return _json(result)

    @workflow.post('/v1/projects/{project_id}/operations', status_code=202, operation_id='create_operation')
    def create_operation(project_id: str, body: OperationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).operations.create(tenant_id=principal.tenant_id, project_id=project_id, operation_type=body.operation_type, idempotency_key=body.idempotency_key, input_manifest=body.input_manifest, actor_id=principal.subject_id, max_attempts=body.max_attempts, traceparent=current_traceparent())

    @workflow.get('/v1/operations/{operation_id}', operation_id='get_operation')
    def get_operation(operation_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        result = _context(request).operations.get(operation_id)
        _require(request, principal, action='project:*', tenant_id=result['tenant_id'], project_id=result['project_id'])
        return result

    @workflow.post('/v1/operations/{operation_id}/cancel', status_code=202, operation_id='cancel_operation')
    def cancel_operation(operation_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        result = _context(request).operations.get(operation_id)
        _require(request, principal, action='project:*', tenant_id=result['tenant_id'], project_id=result['project_id'])
        return _context(request).operations.request_cancel(operation_id, actor_id=principal.subject_id)

    @workflow.post('/v1/internal/operations/{operation_id}/lease', operation_id='lease_operation')
    def lease_operation(operation_id: str, body: WorkerLease, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='operation:lease', tenant_id=principal.tenant_id)
        return _context(request).operations.lease(operation_id, worker_id=body.worker_id, lease_seconds=body.lease_seconds)

    @workflow.post('/v1/internal/operations/{operation_id}/start', operation_id='start_operation')
    def start_operation(operation_id: str, body: WorkerLease, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='operation:lease', tenant_id=principal.tenant_id)
        return _context(request).operations.start(operation_id, worker_id=body.worker_id)

    @workflow.post('/v1/internal/operations/{operation_id}/checkpoint', operation_id='checkpoint_operation')
    def checkpoint_operation(operation_id: str, body: WorkerCheckpoint, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='operation:checkpoint', tenant_id=principal.tenant_id)
        return _context(request).operations.checkpoint(operation_id, worker_id=body.worker_id, progress=body.progress, checkpoint=body.checkpoint)

    @workflow.post('/v1/internal/operations/{operation_id}/complete', operation_id='complete_operation')
    def complete_operation(operation_id: str, body: WorkerComplete, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='operation:complete', tenant_id=principal.tenant_id)
        return _context(request).operations.complete(operation_id, worker_id=body.worker_id, output=body.output)

    @workflow.post('/v1/internal/operations/{operation_id}/fail', operation_id='fail_operation')
    def fail_operation(operation_id: str, body: WorkerFail, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='operation:complete', tenant_id=principal.tenant_id)
        return _context(request).operations.fail(operation_id, worker_id=body.worker_id, code=body.code, message=body.message, retryable=body.retryable)

    @scene.post('/v1/projects/{project_id}/scenes', status_code=201, operation_id='create_scene')
    def create_scene(project_id: str, body: SceneCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene.create_scene(principal.tenant_id, project_id, name=body.name, actor_id=principal.subject_id)

    @scene.post('/v1/projects/{project_id}/coordinate-frames', status_code=201, operation_id='register_coordinate_frame')
    def register_coordinate_frame(project_id: str, body: CoordinateFrameCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.register_frame(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            name=body.name,
            semantic_type=body.semantic_type,
            convention=body.convention,
            units=body.units,
            unit_scale_to_meters=body.unit_scale_to_meters,
            original_units=body.original_units,
            original_unit_scale_to_meters=body.original_unit_scale_to_meters,
            axis_convention=body.axis_convention,
            axis_directions=body.axis_directions,
            handedness=body.handedness,
            origin_description=body.origin_description,
            source=body.source,
            crs_identifier=body.crs_identifier,
            vertical_datum=body.vertical_datum,
            actor_id=principal.subject_id,
            frame_id=body.frame_id,
            parent_frame_id=body.parent_frame_id,
            transform_to_parent=body.transform_to_parent,
            uncertainty_m=body.uncertainty_m,
            gravity_alignment=body.gravity_alignment,
            geodetic=body.geodetic,
            metadata=body.metadata,
            supersedes_frame_id=body.supersedes_frame_id,
        )

    @scene.post('/v1/projects/{project_id}/spatial-transforms', status_code=201, operation_id='register_spatial_transform')
    def register_spatial_transform(project_id: str, body: SpatialTransformCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.register_transform(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            source_frame_id=body.source_frame_id,
            target_frame_id=body.target_frame_id,
            transform_type=body.transform_type,
            matrix=body.matrix,
            matrix_layout=body.matrix_layout,
            multiplication_convention=body.multiplication_convention,
            direction=body.direction,
            translation_units=body.translation_units,
            source_type=body.source_type,
            authority_class=body.authority_class,
            scale=body.scale,
            covariance=body.covariance,
            residual_summary=body.residual_summary,
            uncertainty=body.uncertainty,
            calibration_id=body.calibration_id,
            solver_run_id=body.solver_run_id,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
            observed_at=body.observed_at,
            crs_pipeline=body.crs_pipeline,
            grid_resources=body.grid_resources,
            metadata=body.metadata,
            supersedes_transform_id=body.supersedes_transform_id,
            transform_id=body.transform_id,
        )

    @scene.get('/v1/projects/{project_id}/spatial-transforms/resolve', operation_id='resolve_spatial_transform')
    def resolve_spatial_transform(
        project_id: str,
        request: Request,
        principal: Principal,
        source_frame_id: str = Query(...),
        target_frame_id: str = Query(...),
        at_time: datetime | None = Query(default=None),
    ) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.resolve_transform(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            source_frame_id=source_frame_id,
            target_frame_id=target_frame_id,
            at_time=at_time,
        )

    @scene.post('/v1/projects/{project_id}/coordinate-frames/{frame_id}:convert-units', operation_id='convert_coordinate_units')
    def convert_coordinate_units(project_id: str, frame_id: str, body: CoordinateUnitConversion, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.convert_units(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            frame_id=frame_id,
            values=body.values,
            from_units=body.from_units,
            to_units=body.to_units,
            from_scale_to_meters=body.from_scale_to_meters,
            to_scale_to_meters=body.to_scale_to_meters,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/entities', status_code=201, operation_id='create_scene_entity')
    def create_entity(project_id: str, scene_id: str, body: EntityCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        entity_id = _context(request).scene.create_entity(tenant_id=principal.tenant_id, project_id=project_id, scene_id=scene_id, entity_type=body.entity_type, name=body.name, attributes=body.attributes, source_class=body.source_class, authority_class=body.authority_class, confidence=body.confidence, provenance=body.provenance, policy=body.policy, stable_support=body.stable_support, actor_id=principal.subject_id, entity_id=body.entity_id)
        return {'entity_id': entity_id}

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/commits', status_code=201, operation_id='commit_scene')
    def commit_scene(project_id: str, scene_id: str, body: CommitCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene.commit(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            branch=body.branch,
            expected_head=body.expected_head,
            message=body.message,
            actor_id=principal.subject_id,
            field_visit_id=body.field_visit_id,
            workflow_event_id=body.workflow_event_id,
            change_evidence_ids=body.change_evidence_ids,
            policy_checks=body.policy_checks,
            signatures=body.signatures,
            review_state=body.review_state,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/branches', status_code=201, operation_id='create_scene_branch')
    def create_branch(project_id: str, scene_id: str, body: BranchCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        branch_id = _context(request).scene.create_branch(principal.tenant_id, project_id, scene_id, name=body.name, from_commit_id=body.from_commit_id, protected=body.protected)
        return {'branch_id': branch_id}

    @scene.get('/v1/scene-diffs', operation_id='diff_scene_commits')
    def diff_scene(left: str, right: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id)
        return _context(request).scene.diff(left, right)

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/branches/{branch}/rollback', operation_id='rollback_scene_branch')
    def rollback(project_id: str, scene_id: str, branch: str, body: RollbackRequest, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene.rollback_branch(principal.tenant_id, project_id, scene_id, branch, body.target_commit_id, actor_id=principal.subject_id)

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/annotations', status_code=201, operation_id='create_spatial_annotation')
    def create_spatial_annotation(project_id: str, scene_id: str, body: AnnotationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.create_annotation(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            coordinate_frame_id=body.coordinate_frame_id,
            support_type=body.support_type,
            support=body.support,
            uncertainty_m=body.uncertainty_m,
            source_class=body.source_class,
            authority_class=body.authority_class,
            actor_id=principal.subject_id,
            entity_id=body.entity_id,
            position=body.position,
            orientation=body.orientation,
            normal=body.normal,
            policy=body.policy,
            authored_from_representation_id=body.authored_from_representation_id,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/annotation-remaps', operation_id='remap_spatial_annotations')
    def remap_spatial_annotations(project_id: str, scene_id: str, body: AnnotationRemap, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.remap_annotations(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            source_representation_id=body.source_representation_id,
            target_representation_id=body.target_representation_id,
            max_residual_m=body.max_residual_m,
            min_confidence=body.min_confidence,
            actor_id=principal.subject_id,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/tags', status_code=201, operation_id='tag_scene_commit')
    def tag_scene_commit(project_id: str, scene_id: str, body: SceneTagCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.tag_commit(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            commit_id=body.commit_id,
            name=body.name,
            actor_id=principal.subject_id,
            metadata=body.metadata,
        )

    @scene.get('/v1/projects/{project_id}/scenes/{scene_id}/as-of', operation_id='get_scene_as_of')
    def get_scene_as_of(
        project_id: str,
        scene_id: str,
        request: Request,
        principal: Principal,
        commit_id: str | None = Query(default=None),
        tag: str | None = Query(default=None),
        recorded_at: datetime | None = Query(default=None),
        valid_at: datetime | None = Query(default=None),
        field_visit_id: str | None = Query(default=None),
        branch: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.query_scene_as_of(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            commit_id=commit_id,
            tag=tag,
            recorded_at=recorded_at,
            valid_at=valid_at,
            field_visit_id=field_visit_id,
            branch=branch,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/merges', operation_id='merge_scene_branches')
    def merge_scene_branches(project_id: str, scene_id: str, body: SceneMerge, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.merge_branches(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            target_branch=body.target_branch,
            source_branch=body.source_branch,
            base_commit_id=body.base_commit_id,
            actor_id=principal.subject_id,
            message=body.message,
            approved_review_categories=body.approved_review_categories,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/viewer-sessions', status_code=201, operation_id='create_viewer_session')
    def create_viewer_session(project_id: str, scene_id: str, body: ViewerSessionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(
            request,
            principal,
            action='scene:read',
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=body.purpose,
            audience=body.audience,
        )
        return _context(request).scene_runtime.create_viewer_session(
            principal=principal,
            project_id=project_id,
            scene_id=scene_id,
            purpose=body.purpose,
            audience=body.audience,
            publication_class=body.publication_class,
            scene_commit_ids=body.scene_commit_ids,
            saved_hybrid_views=body.saved_hybrid_views,
            device_profile=body.device_profile,
            intended_uses=body.intended_uses,
            spatial_region_ids=body.spatial_region_ids,
            camera=body.camera,
            navigation_mode=body.navigation_mode,
            layers=body.layers,
            clipping_planes=body.clipping_planes,
            section_box=body.section_box,
            selected_entity_ids=body.selected_entity_ids,
            timeline=body.timeline,
            filters=body.filters,
            redaction=body.redaction,
            accessibility=body.accessibility,
            comparison=body.comparison,
            idempotency_key=body.idempotency_key,
            supersedes_session_id=body.supersedes_session_id,
        )

    @scene.get('/v1/projects/{project_id}/scenes/{scene_id}/viewer-sessions/{session_id}', operation_id='get_viewer_session')
    def get_viewer_session(project_id: str, scene_id: str, session_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        retained = _context(request).scene_runtime.get_viewer_session(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            session_id=session_id,
        )
        if retained['scene_id'] != scene_id:
            raise NotFoundError('viewer_session', session_id)
        if principal.subject_id != retained['principal_id'] and not set(principal.roles).intersection({'tenant_admin', 'project_admin', 'reviewer'}):
            raise AuthorizationError('VIEWER_SESSION_PRINCIPAL_DENIED', 'viewer session is limited to its principal or a trusted reviewer')
        _require(
            request,
            principal,
            action='scene:read',
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=retained['purpose'],
            audience=Audience(retained['audience']),
        )
        return retained

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/viewer-sessions/{session_id}/replays', status_code=201, operation_id='replay_viewer_session')
    def replay_viewer_session(project_id: str, scene_id: str, session_id: str, body: ViewerSessionReplay, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        retained = _context(request).scene_runtime.get_viewer_session(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            session_id=session_id,
        )
        if retained['scene_id'] != scene_id:
            raise NotFoundError('viewer_session', session_id)
        return _context(request).scene_runtime.replay_viewer_session(
            principal=principal,
            project_id=project_id,
            session_id=session_id,
            ttl_seconds=body.ttl_seconds,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/temporal-comparisons', status_code=201, operation_id='create_temporal_comparison')
    def create_temporal_comparison(project_id: str, scene_id: str, body: TemporalComparisonCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene_runtime.create_temporal_comparison(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            baseline_commit_id=body.baseline_commit_id,
            candidate_commit_id=body.candidate_commit_id,
            viewer_session_id=body.viewer_session_id,
            comparable_region=body.comparable_region,
            registration_quality=body.registration_quality,
            thresholds=body.thresholds,
            evidence_ids=body.evidence_ids,
            algorithm_id=body.algorithm_id,
            algorithm_version=body.algorithm_version,
            executable_hash=body.executable_hash,
            parameters_hash=body.parameters_hash,
            observed_coverage=body.observed_coverage,
            candidates=body.candidates,
            idempotency_key=body.idempotency_key,
            actor_id=principal.subject_id,
        )

    @scene.get('/v1/projects/{project_id}/scenes/{scene_id}/temporal-comparisons/{comparison_id}', operation_id='get_temporal_comparison')
    def get_temporal_comparison(project_id: str, scene_id: str, comparison_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        trusted = bool(set(principal.roles).intersection({'tenant_admin', 'project_admin', 'reviewer'}))
        result = _context(request).scene_runtime.get_temporal_comparison(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            include_suppression_details=trusted,
        )
        if result['scene_id'] != scene_id:
            raise NotFoundError('temporal_comparison', comparison_id)
        return result

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/temporal-comparisons/{comparison_id}/candidates/{candidate_id}/reviews', status_code=201, operation_id='review_change_candidate')
    def review_change_candidate(project_id: str, scene_id: str, comparison_id: str, candidate_id: str, body: ChangeReviewCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id, project_id=project_id)
        comparison = _context(request).scene_runtime.get_temporal_comparison(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            include_suppression_details=True,
        )
        if comparison['scene_id'] != scene_id:
            raise NotFoundError('temporal_comparison', comparison_id)
        return _context(request).scene_runtime.review_change_candidate(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            candidate_id=candidate_id,
            reviewer_id=principal.subject_id,
            outcome=body.outcome,
            rationale=body.rationale,
            evidence_ids=body.evidence_ids,
            policy_snapshot_hash=body.policy_snapshot_hash,
            idempotency_key=body.idempotency_key,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/temporal-comparisons/{comparison_id}/apply', status_code=201, operation_id='apply_accepted_changes')
    def apply_accepted_changes(project_id: str, scene_id: str, comparison_id: str, body: ApplySemanticChanges, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        comparison = _context(request).scene_runtime.get_temporal_comparison(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            include_suppression_details=True,
        )
        if comparison['scene_id'] != scene_id:
            raise NotFoundError('temporal_comparison', comparison_id)
        return _context(request).scene_runtime.apply_accepted_changes(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            comparison_id=comparison_id,
            branch=body.branch,
            expected_head=body.expected_head,
            message=body.message,
            actor_id=principal.subject_id,
        )

    @scene.post('/v1/projects/{project_id}/change-benchmarks', status_code=201, operation_id='record_change_benchmark')
    def record_change_benchmark(project_id: str, body: ChangeBenchmarkCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene_runtime.record_change_benchmark(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            algorithm_id=body.algorithm_id,
            algorithm_version=body.algorithm_version,
            executable_hash=body.executable_hash,
            benchmark_profile=body.benchmark_profile,
            fixture_root_hash=body.fixture_root_hash,
            metrics_by_class=body.metrics_by_class,
            environment=body.environment,
            actor_id=principal.subject_id,
        )

    @scene.post('/v1/projects/{project_id}/scenes/{scene_id}/measurements', status_code=201, operation_id='create_measurement')
    def create_measurement(project_id: str, scene_id: str, body: MeasurementCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review' if body.verified else 'scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        measurement_id = _context(request).scene.create_measurement(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            entity_id=body.entity_id,
            value=body.value,
            unit=body.unit,
            uncertainty=body.uncertainty,
            source_asset_ids=body.source_asset_ids,
            calibration=body.calibration,
            verifier_id=body.verifier_id,
            verified=body.verified,
            actor_id=principal.subject_id,
            originating_representation_id=body.originating_representation_id,
            interaction_hit=body.interaction_hit,
            measurement_type=body.measurement_type,
            geometry=body.geometry,
            source_method=body.source_method,
            measured_at=body.measured_at,
            coordinate_frame_id=body.coordinate_frame_id,
            source_commit_id=body.source_commit_id,
            permitted_uses=body.permitted_uses,
            state=body.state,
            supersedes_measurement_id=body.supersedes_measurement_id,
            proxy_tolerance_m=body.proxy_tolerance_m,
        )
        return _context(request).scene.get_measurement(
            principal.tenant_id,
            project_id,
            scene_id,
            measurement_id,
        )

    @scene.get('/v1/projects/{project_id}/scenes/{scene_id}/measurements/{measurement_id}', operation_id='get_measurement')
    def get_measurement(project_id: str, scene_id: str, measurement_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).scene.get_measurement(
            principal.tenant_id,
            project_id,
            scene_id,
            measurement_id,
        )

    @scene.post('/v1/projects/{project_id}/proxy-hits/resolve', operation_id='resolve_proxy_hit')
    def resolve_proxy_hit(project_id: str, body: ProxyResolve, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        hit = ProxyHit(
            representation_id=body.representation_id,
            world_point=body.point,
            normal=None,
            support_hint={"semantic_entity_id": body.semantic_entity_id} if body.semantic_entity_id else {},
        )
        return _context(request).scene.resolve_proxy_hit(principal.tenant_id, project_id, hit, tolerance_m=body.tolerance_m)

    @providers.post('/v1/providers', status_code=201, operation_id='register_provider')
    def register_provider(body: ProviderRegister, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=principal.tenant_id)
        return _context(request).providers.register(body.manifest, actor_id=principal.subject_id)

    @providers.post('/v1/providers/capabilities', status_code=201, operation_id='register_provider_capability')
    def register_provider_capability(body: ProviderCapabilityCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=principal.tenant_id)
        return _context(request).providers.register(
            body.model_dump(mode='json', by_alias=True, exclude_none=True),
            actor_id=principal.subject_id,
        )

    @providers.get('/v1/providers/{provider_id}/capability', operation_id='get_provider_capability')
    def get_provider_capability(provider_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id)
        return _context(request).providers.get_descriptor(provider_id)

    @providers.post('/v1/providers/{provider_id}/promotions', status_code=201, operation_id='promote_provider_capability')
    def promote_provider_capability(provider_id: str, body: ProviderPromotionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=principal.tenant_id)
        return _context(request).providers.promote(
            provider_id,
            state=body.state,
            data_classifications=[item.value for item in body.data_classifications],
            scene_classes=body.scene_classes,
            output_roles=body.output_roles,
            intended_uses=body.intended_uses,
            execution_zones=body.execution_zones,
            hardware_profiles=body.hardware_profiles,
            benchmark_evidence_hash=body.benchmark_evidence_hash,
            policy_snapshot_hash=body.policy_snapshot_hash,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            actor_id=principal.subject_id,
            promotion_id=body.promotion_id,
        )

    @providers.post('/v1/providers/{provider_id}/authorize', operation_id='authorize_provider')
    def authorize_provider(provider_id: str, body: ProviderAuthorize, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, purpose=body.purpose, classification=body.classification)
        return _context(request).providers.authorize_execution(provider_id, classification=body.classification, purpose=body.purpose, region=body.region, external=body.external)

    @providers.post('/v1/models', status_code=201, operation_id='register_model')
    def register_model(body: ModelRegister, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=principal.tenant_id)
        return _context(request).models.register(body.manifest, actor_id=principal.subject_id)

    @providers.post('/v1/models/{model_id}/authorize', operation_id='authorize_model')
    def authorize_model(model_id: str, body: ModelAuthorize, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, purpose=body.purpose, classification=body.classification)
        return _context(request).models.authorize(
            model_id,
            checkpoint_hash=body.checkpoint_hash,
            purpose=body.purpose,
            commercial=body.commercial,
            classification=body.classification,
            deployment=_context(request).settings.environment,
            region=body.region,
            customer_id=principal.tenant_id,
        )

    @representation.post('/v1/projects/{project_id}/hybrid/conversions', status_code=201, operation_id='create_hybrid_conversion')
    def create_hybrid_conversion(project_id: str, body: SpatialConversionRequestContract, request: Request, principal: Principal) -> dict[str, Any]:
        _require(
            request,
            principal,
            action='representation:*',
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=body.purpose,
        )
        if body.tenant_id != principal.tenant_id or body.project_id != project_id:
            raise AuthorizationError('HYB_API_SCOPE_MISMATCH', 'conversion request scope must match authenticated route scope')
        if body.requested_by != principal.subject_id:
            raise AuthorizationError('HYB_REQUESTER_MISMATCH', 'conversion requester must match the authenticated actor')
        return _context(request).hybrid.create_conversion(
            body,
            actor_id=principal.subject_id,
            traceparent=current_traceparent(),
        )

    @representation.get('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}', operation_id='get_hybrid_conversion')
    def get_hybrid_conversion(project_id: str, conversion_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.get_conversion(
            conversion_id, tenant_id=principal.tenant_id, project_id=project_id
        )

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/cancel', operation_id='cancel_hybrid_conversion')
    def cancel_hybrid_conversion(project_id: str, conversion_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.cancel_conversion(
            conversion_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
        )

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/progress', operation_id='record_hybrid_provider_progress')
    def record_hybrid_provider_progress(
        project_id: str,
        conversion_id: str,
        body: ProviderProgressContract,
        request: Request,
        principal: Principal,
        worker_token: Annotated[str, Header(alias='X-SIP-Worker-Token')],
    ) -> dict[str, Any]:
        _require(request, principal, action='operation:checkpoint', tenant_id=principal.tenant_id, project_id=project_id)
        if body.conversion_id != conversion_id:
            raise ValidationError('HYB_PROGRESS_ROUTE_MISMATCH', 'progress conversion identifier must match route')
        return _context(request).hybrid.record_progress(worker_token, body)

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/worker-lease:renew', operation_id='renew_hybrid_worker_lease')
    def renew_hybrid_worker_lease(
        project_id: str,
        conversion_id: str,
        body: HybridWorkerLeaseRenew,
        request: Request,
        principal: Principal,
        worker_token: Annotated[str, Header(alias='X-SIP-Worker-Token')],
    ) -> dict[str, Any]:
        _require(request, principal, action='operation:checkpoint', tenant_id=principal.tenant_id, project_id=project_id)
        result = _context(request).hybrid.renew_worker_lease(
            worker_token,
            lease_ttl_seconds=body.lease_ttl_seconds,
        )
        if result.get('conversion_id') != conversion_id:
            raise AuthorizationError('HYB_WORKER_SCOPE_MISMATCH', 'worker token does not authorize the route conversion')
        return result

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/failure', operation_id='report_hybrid_provider_failure')
    def report_hybrid_provider_failure(
        project_id: str,
        conversion_id: str,
        body: HybridProviderFailureCreate,
        request: Request,
        principal: Principal,
        worker_token: Annotated[str, Header(alias='X-SIP-Worker-Token')],
    ) -> dict[str, Any]:
        _require(request, principal, action='operation:complete', tenant_id=principal.tenant_id, project_id=project_id)
        result = _context(request).hybrid.report_provider_failure(
            worker_token,
            error_code=body.error_code,
            retryable=body.retryable,
            cleanup_receipt_hash=body.cleanup_receipt_hash,
            cleanup_verified=body.cleanup_verified,
            last_durable_checkpoint_hash=body.last_durable_checkpoint_hash,
            resource_use=body.resource_use,
        )
        if result.get('conversion_id') != conversion_id:
            raise AuthorizationError('HYB_WORKER_SCOPE_MISMATCH', 'worker token does not authorize the route conversion')
        return result

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/candidate', status_code=201, operation_id='complete_hybrid_candidate')
    def complete_hybrid_candidate(
        project_id: str,
        conversion_id: str,
        body: HybridCandidateComplete,
        request: Request,
        principal: Principal,
        worker_token: Annotated[str, Header(alias='X-SIP-Worker-Token')],
    ) -> dict[str, Any]:
        _require(request, principal, action='operation:complete', tenant_id=principal.tenant_id, project_id=project_id)
        result = _context(request).hybrid.complete_candidate(
            worker_token,
            output_asset_id=body.output_asset_id,
            output_asset_sha256=body.output_asset_sha256,
            output_role=body.output_role,
            kind=body.kind,
            coordinate_frame_id=body.coordinate_frame_id,
            source_class=body.source_class,
            authority_class=body.authority_class,
            lossy=body.lossy,
            intended_uses=body.intended_uses,
            prohibited_uses=body.prohibited_uses,
            quality=body.quality,
            support_map=body.support_map,
            worker_receipt_hash=body.worker_receipt_hash,
            candidate_core_hash=body.candidate_core_hash,
            format_metadata=body.format_metadata,
            limitations=body.limitations,
            information_losses=body.information_losses,
            metadata=body.metadata,
        )
        if result.get('conversion_id') != conversion_id:
            raise AuthorizationError('HYB_WORKER_SCOPE_MISMATCH', 'worker token does not authorize the route conversion')
        return result

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/validations', status_code=201, operation_id='validate_hybrid_candidate')
    def validate_hybrid_candidate(project_id: str, conversion_id: str, body: HybridValidationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.validate_candidate(
            conversion_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            intended_use=body.intended_use,
            profile_id=body.profile_id,
            profile_version=body.profile_version,
            validator_id=principal.subject_id,
            validator_manifest_hash=body.validator_manifest_hash,
            metrics=body.metrics,
            thresholds=body.thresholds,
            coverage=body.coverage,
            topology=body.topology,
            coordinate_validation=body.coordinate_validation,
            behavior_validation=body.behavior_validation,
            limitations=body.limitations,
        )

    @representation.post('/v1/projects/{project_id}/hybrid/conversions/{conversion_id}/manual-export', status_code=201, operation_id='create_hybrid_manual_export')
    def create_hybrid_manual_export(project_id: str, conversion_id: str, body: HybridManualExportCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.create_manual_export(
            conversion_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            approved_derivative_asset_ids=body.approved_derivative_asset_ids,
            actor_id=principal.subject_id,
        )

    @representation.post('/v1/projects/{project_id}/hybrid/manual-transfers/{transfer_id}/return', operation_id='record_hybrid_manual_return')
    def record_hybrid_manual_return(project_id: str, transfer_id: str, body: HybridManualReturnCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        if body.receipt.transfer_id != transfer_id:
            raise ValidationError('HYB_MANUAL_RECEIPT_ROUTE_MISMATCH', 'manual receipt transfer identifier must match route')
        return _context(request).hybrid.record_manual_return(
            transfer_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            one_time_return_code=body.one_time_return_code,
            receipt=body.receipt,
            returned_outputs=body.returned_outputs,
            actor_id=principal.subject_id,
        )

    @representation.post('/v1/projects/{project_id}/scenes/{scene_id}/hybrid-view', status_code=201, operation_id='create_hybrid_scene_view')
    def create_hybrid_scene_view(project_id: str, scene_id: str, body: HybridViewCreate, request: Request, principal: Principal) -> dict[str, Any]:
        audience = Audience(body.audience)
        _require(
            request,
            principal,
            action='scene:read',
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=body.purpose,
            audience=audience,
        )
        return _context(request).hybrid.create_view_manifest(
            principal=principal,
            project_id=project_id,
            scene_id=scene_id,
            scene_revision_id=body.scene_revision_id,
            purpose=body.purpose,
            audience=body.audience,
            device_profile=body.device_profile,
            time_context=body.time_context,
            intended_uses=body.intended_uses,
            spatial_region_ids=body.spatial_region_ids,
            ttl_seconds=body.ttl_seconds,
        )

    @representation.post('/v1/projects/{project_id}/hybrid/interaction-profiles', status_code=201, operation_id='register_hybrid_interaction_profile')
    def register_hybrid_interaction_profile(project_id: str, body: InteractionProfileCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.register_interaction_profile(
            profile_id=body.profile_id,
            profile_type=body.profile_type,
            version=body.version,
            actor=body.actor,
            intended_uses=body.intended_uses,
            limits=body.limits,
            behavior=body.behavior,
            validation=body.validation,
            safety_claims=body.safety_claims,
            validator_id=body.validator_id,
            validator_manifest_hash=body.validator_manifest_hash,
            validation_evidence_hash=body.validation_evidence_hash,
            validated_at=body.validated_at,
            review_due_at=body.review_due_at,
            expires_at=body.expires_at,
            created_by=principal.subject_id,
        )

    @representation.post('/v1/projects/{project_id}/scenes/{scene_id}/representation-families', status_code=201, operation_id='register_representation_family')
    def register_representation_family(project_id: str, scene_id: str, body: RepresentationFamilyCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).hybrid.register_representation_family(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            role=body.role,
            coordinate_frame_id=body.coordinate_frame_id,
            tile_scheme_id=body.tile_scheme_id,
            lods=body.lods,
            seam_validation_report_id=body.seam_validation_report_id,
            fallback_representation_id=body.fallback_representation_id,
            actor_id=principal.subject_id,
            family_id=body.family_id,
        )

    @representation.post('/v1/projects/{project_id}/representations', status_code=201, operation_id='create_representation_candidate')
    def create_representation(project_id: str, body: RepresentationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).representations.create_candidate(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=body.scene_id,
            asset_id=body.asset_id,
            kind=body.kind,
            provider_id=body.provider_id,
            coordinate_frame_id=body.coordinate_frame_id,
            source_class=body.source_class,
            authority_class=body.authority_class,
            lossy=body.lossy,
            intended_uses=body.intended_uses,
            prohibited_uses=body.prohibited_uses,
            quality=body.quality,
            provenance=body.provenance,
            support_map=body.support_map,
            actor_id=principal.subject_id,
            operation_id=body.operation_id,
            representation_id=body.representation_id,
            format_metadata=body.format_metadata,
            derivation_policy=body.derivation_policy,
            limitations=body.limitations,
            information_losses=body.information_losses,
            privacy_inheritance=body.privacy_inheritance,
            dependencies=body.dependencies,
            fallback_representation_id=body.fallback_representation_id,
            metadata=body.metadata,
        )
        return {'representation_id': identifier, 'state': 'quarantined'}

    @representation.post('/v1/representations/{representation_id}/quality-review', operation_id='review_representation')
    def review_representation(representation_id: str, body: RepresentationReview, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:review', tenant_id=principal.tenant_id)
        return _context(request).representations.review_quality(representation_id, reviewer_id=principal.subject_id, approved_uses=body.approved_uses, metrics=body.metrics, passed=body.passed)

    @representation.post('/v1/representations/{old_id}/replace/{new_id}', operation_id='replace_interaction_proxy')
    def replace_proxy(old_id: str, new_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id)
        return _context(request).representations.replace_proxy(old_id, new_id)

    @representation.post('/v1/projects/{project_id}/representations/dependencies:invalidate', operation_id='invalidate_representation_dependencies')
    def invalidate_representation_dependencies(project_id: str, body: RepresentationInvalidate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).representations.invalidate_dependencies(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            changed_resource_id=body.changed_resource_id,
            reason=body.reason,
            actor_id=principal.subject_id,
            queue_regeneration=body.queue_regeneration,
        )

    @representation.post('/v1/projects/{project_id}/representations/view:select', operation_id='select_hybrid_representations')
    def select_hybrid_representations(project_id: str, body: HybridViewSelect, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).representations.select_for_view(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=body.scene_id,
            intended_use=body.intended_use,
            audience=body.audience,
            role=body.role,
            client_profile=body.client_profile,
        )

    @publisher.post('/v1/representations/{representation_id}/publish', operation_id='publish_representation')
    def publish_representation(representation_id: str, body: RepresentationPublish, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='representation:publish', tenant_id=principal.tenant_id)
        binding_id = _context(request).publisher.publish(
            representation_id,
            commit_id=body.commit_id,
            role=body.role,
            publisher_id=principal.subject_id,
            transform=body.transform,
            intended_uses=body.intended_uses,
            review_decision=body.review_decision,
            audience_policy=body.audience_policy,
            client_profile=body.client_profile,
        )
        return {'binding_id': binding_id}

    @search.post('/v1/projects/{project_id}/search/documents', status_code=201, operation_id='index_search_document')
    def index_search(project_id: str, body: SearchIndex, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).search.index(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            text=body.text,
            entity_id=body.entity_id,
            entity_type=body.entity_type,
            asset_id=body.asset_id,
            embedding=body.embedding,
            embedding_model_manifest_id=body.embedding_model_manifest_id,
            embedding_source_region=body.embedding_source_region,
            spatial_bounds=body.spatial_bounds,
            spatial_frame_id=body.spatial_frame_id,
            floor_id=body.floor_id,
            room_id=body.room_id,
            temporal_start=body.temporal_start,
            temporal_end=body.temporal_end,
            source_class=body.source_class.value,
            authority_class=body.authority_class.value,
            confidence=body.confidence,
            tags=body.tags,
            workflow_status=body.workflow_status,
            relationships=body.relationships,
            evidence_ids=body.evidence_ids,
            source_sequence=body.source_sequence,
            index_sequence=body.index_sequence,
            scene_commit_id=body.scene_commit_id,
            classification=body.classification.value,
            policy=body.policy,
            actor_id=principal.subject_id,
        )
        return {'document_id': identifier}

    @search.post('/v1/projects/{project_id}/search', operation_id='search_project')
    def query_search(project_id: str, body: SearchQuery, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        spec = SearchQuerySpec(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            **body.model_dump(mode='python'),
        )
        return _context(request).search.query(principal=principal, spec=spec)

    @search.post('/v1/projects/{project_id}/saved-queries', status_code=201, operation_id='create_saved_query')
    def create_saved_query(project_id: str, body: SavedQueryCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        spec = SearchQuerySpec(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            **body.query.model_dump(mode='python'),
        )
        return _context(request).search.save_query(
            principal=principal,
            name=body.name,
            spec=spec,
            permissions=body.permissions,
            parameters=body.parameters,
            expected_result_contract=body.expected_result_contract,
            supersedes_saved_query_id=body.supersedes_saved_query_id,
        )

    @search.get('/v1/projects/{project_id}/saved-queries/{saved_query_id}', operation_id='get_saved_query')
    def get_saved_query(project_id: str, saved_query_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).search.get_saved_query(principal=principal, saved_query_id=saved_query_id)

    @search.post('/v1/projects/{project_id}/saved-queries/{saved_query_id}:execute', operation_id='execute_saved_query')
    def execute_saved_query(project_id: str, saved_query_id: str, body: SavedQueryExecute, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).search.execute_saved_query(
            principal=principal,
            saved_query_id=saved_query_id,
            parameters=body.parameters,
        )

    @search.get('/v1/projects/{project_id}/agent-tools', operation_id='list_agent_tools')
    def list_agent_tools(project_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        return {'items': _context(request).agents.list_tools(principal=principal, project_id=project_id)}

    @search.post('/v1/projects/{project_id}/agent-tools/{tool_name}:execute', operation_id='execute_agent_tool')
    def execute_agent_tool(project_id: str, tool_name: str, body: AgentToolExecute, request: Request, principal: Principal) -> dict[str, Any]:
        return _context(request).agents.execute(
            principal=principal,
            project_id=project_id,
            tool_name=tool_name,
            arguments=body.arguments,
        )

    @search.post('/v1/projects/{project_id}/agent-answers:validate', operation_id='validate_agent_answer')
    def validate_agent_answer(project_id: str, body: AgentClaimsValidate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).agents.answer(body.claims)

    @search.post('/v1/projects/{project_id}/agent-requests:check', operation_id='check_agent_request')
    def check_agent_request(project_id: str, body: AgentRequestCheck, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).agents.evaluate_request(
            body.request_kind,
            simulation_enabled=body.simulation_enabled,
            consent_verified=body.consent_verified,
        )

    @evidence.post('/v1/projects/{project_id}/geometry-manifests', status_code=201, operation_id='register_geometry_manifest')
    def register_geometry_manifest(project_id: str, body: GeometryManifestCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id, classification=body.classification)
        return _context(request).spatial_data.register_geometry_manifest(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            asset_id=body.asset_id,
            media_type=body.media_type,
            format=body.format,
            profile=body.profile,
            format_version=body.format_version,
            coordinate_frame_id=body.coordinate_frame_id,
            units=body.units,
            bounds=body.bounds,
            classification=body.classification.value,
            counts=body.counts,
            compression=body.compression,
            source_run_id=body.source_run_id,
            quality=body.quality,
            limitations=body.limitations,
            visual_content_classes=body.visual_content_classes,
            audience_policy=body.audience_policy,
            viewer_compatibility=body.viewer_compatibility,
            exporter_compatibility=body.exporter_compatibility,
            validation_state=body.validation_state,
            rebuild_recipe=body.rebuild_recipe,
            truth_label=body.truth_label,
            representation_id=body.representation_id,
            supersedes_manifest_id=body.supersedes_manifest_id,
        )

    @evidence.post('/v1/projects/{project_id}/evidence', status_code=201, operation_id='record_evidence')
    def record_evidence(project_id: str, body: EvidenceCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.record_evidence(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            asset_id=body.asset_id,
            source_type=body.source_type,
            collected_at=body.collected_at,
            collected_by=body.collected_by,
            device_or_tool=body.device_or_tool,
            location_context=body.location_context,
            relevant_region=body.relevant_region,
            relevant_time_start=body.relevant_time_start,
            relevant_time_end=body.relevant_time_end,
            retention_class=body.retention_class,
            actor_id=principal.subject_id,
            chain_of_custody=body.chain_of_custody,
            legal_hold=body.legal_hold,
            consent_scope=body.consent_scope,
            access_policy=body.access_policy,
            policy=body.policy,
        )

    @evidence.get('/v1/projects/{project_id}/evidence/{evidence_id}', operation_id='get_evidence')
    def get_evidence(
        project_id: str,
        evidence_id: str,
        request: Request,
        principal: Principal,
        purpose: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return _context(request).spatial_data.get_evidence(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            evidence_id=evidence_id,
            principal=principal,
            purpose=purpose,
        )

    @evidence.post('/v1/projects/{project_id}/assertions', status_code=201, operation_id='record_assertion')
    def record_assertion(project_id: str, body: AssertionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.record_assertion(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            subject_id=body.subject_id,
            predicate=body.predicate,
            object_value=body.object_value,
            source_class=body.source_class,
            authority_class=body.authority_class,
            confidence=body.confidence,
            evidence_ids=body.evidence_ids,
            actor_id=principal.subject_id,
            asserted_at=body.asserted_at,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
            producer_id=body.producer_id,
            conflicts_with_assertion_ids=body.conflicts_with_assertion_ids,
            supersedes_assertion_id=body.supersedes_assertion_id,
            state=body.state,
        )

    @evidence.get('/v1/projects/{project_id}/assertions', operation_id='list_assertions')
    def list_assertions(
        project_id: str,
        request: Request,
        principal: Principal,
        purpose: str | None = Query(default=None),
        subject_id: str | None = Query(default=None),
        predicate: str | None = Query(default=None),
        states: list[str] | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        return _context(request).spatial_data.list_assertions(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            principal=principal,
            purpose=purpose,
            subject_id=subject_id,
            predicate=predicate,
            states=states,
            limit=limit,
        )

    @evidence.get('/v1/projects/{project_id}/assertions/{assertion_id}', operation_id='get_assertion')
    def get_assertion(
        project_id: str,
        assertion_id: str,
        request: Request,
        principal: Principal,
        purpose: str | None = Query(default=None),
        include_evidence: bool = Query(default=False),
    ) -> dict[str, Any]:
        return _context(request).spatial_data.get_assertion(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            assertion_id=assertion_id,
            principal=principal,
            purpose=purpose,
            include_evidence=include_evidence,
        )

    @evidence.get('/v1/projects/{project_id}/assertions/{assertion_id}/evidence', operation_id='get_assertion_evidence')
    def get_assertion_evidence(
        project_id: str,
        assertion_id: str,
        request: Request,
        principal: Principal,
        purpose: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return _context(request).spatial_data.get_assertion_evidence(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            assertion_id=assertion_id,
            principal=principal,
            purpose=purpose,
        )

    @evidence.post('/v1/projects/{project_id}/derivations', status_code=201, operation_id='record_derivation')
    def record_derivation(project_id: str, body: DerivationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:commit', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).spatial_data.record_derivation(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            activity_type=body.activity_type,
            input_ids=body.input_ids,
            input_hashes=body.input_hashes,
            algorithm_id=body.algorithm_id,
            algorithm_version=body.algorithm_version,
            parameters_hash=body.parameters_hash,
            environment_hash=body.environment_hash,
            code_commit=body.code_commit,
            output_ids=body.output_ids,
            output_hashes=body.output_hashes,
            software=body.software,
            validation=body.validation,
            started_at=body.started_at,
            completed_at=body.completed_at,
            quality=body.quality,
            actor_id=principal.subject_id,
            model_manifest_id=body.model_manifest_id,
            container_digest=body.container_digest,
        )

    @evidence.get('/v1/tenants/{tenant_id}/audit/verify', operation_id='verify_audit_chain')
    def verify_audit(tenant_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:admin', tenant_id=tenant_id)
        return _context(request).audit.verify(tenant_id)

    @export.post('/v1/projects/{project_id}/exports/preservation', status_code=202, operation_id='export_preservation')
    def export_preservation(project_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='export:*', tenant_id=principal.tenant_id, project_id=project_id)
        root = _context(request).settings.object_store_root.parent / 'exports'
        root.mkdir(parents=True, exist_ok=True)
        destination = root / f'{principal.tenant_id}-{project_id}-{new_uuid()}.sip-preservation.zip'
        return _context(request).preservation.export_project(principal.tenant_id, project_id, destination, actor_id=principal.subject_id)


    # Progress 06 Construction vertical -----------------------------------------------------
    @construction.post('/v1/projects/{project_id}/construction/surveys', status_code=201, operation_id='create_construction_survey')
    def create_construction_survey(project_id: str, body: ConstructionSurveyCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.create_survey_plan(
            tenant_id=principal.tenant_id, project_id=project_id, name=body.name,
            objectives=body.objectives, required_place_ids=body.required_place_ids,
            required_system_types=body.required_system_types, sensitive_regions=body.sensitive_regions,
            control_requirements=body.control_requirements,
            measurement_requirements=body.measurement_requirements, safety=body.safety,
            permissions=body.permissions, deliverables=body.deliverables,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
            baseline_commit_id=body.baseline_commit_id, return_visit_of_id=body.return_visit_of_id,
        )

    @construction.post('/v1/projects/{project_id}/construction/surveys/{survey_id}/visits', status_code=201, operation_id='record_construction_field_visit')
    def record_construction_field_visit(project_id: str, survey_id: str, body: ConstructionFieldVisitCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.record_field_visit(
            tenant_id=principal.tenant_id, project_id=project_id, survey_id=survey_id,
            scope=body.scope, capture_ids=body.capture_ids, checklist=body.checklist,
            detail_evidence=body.detail_evidence, inaccessible_regions=body.inaccessible_regions,
            coverage=body.coverage, tracking=body.tracking, registration=body.registration,
            controls=body.controls, inventory=body.inventory,
            unresolved_questions=body.unresolved_questions, privacy=body.privacy,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
            exact_prior_commit_id=body.exact_prior_commit_id, complete=body.complete,
        )

    @construction.get('/v1/projects/{project_id}/construction/surveys/{survey_id}', operation_id='get_construction_survey')
    def get_construction_survey(project_id: str, survey_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.survey(principal.tenant_id, project_id, survey_id)

    @construction.post('/v1/projects/{project_id}/construction/surveys/{survey_id}/review', operation_id='review_construction_survey')
    def review_construction_survey(project_id: str, survey_id: str, body: ConstructionSurveyReview, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.review_survey(
            survey_id, tenant_id=principal.tenant_id, project_id=project_id,
            reviewer_id=principal.subject_id, decision=body.decision, checklist=body.checklist,
            accepted_commit_id=body.accepted_commit_id, limitations=body.limitations,
        )

    @construction.post('/v1/projects/{project_id}/construction/document-revisions', status_code=201, operation_id='create_construction_document_revision')
    def create_construction_document_revision(project_id: str, body: ConstructionDocumentRevisionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.create_document_revision(
            tenant_id=principal.tenant_id, project_id=project_id,
            stable_document_id=body.stable_document_id, document_type=body.document_type,
            title=body.title, revision=body.revision, issue_date=body.issue_date,
            issuer=body.issuer, status=body.status, asset_id=body.asset_id,
            source_sha256=body.source_sha256, page_count=body.page_count,
            permissions=body.permissions, page_regions=body.page_regions,
            spatial_links=body.spatial_links, extraction=body.extraction, review=body.review,
            actor_id=principal.subject_id, supersedes_revision_id=body.supersedes_revision_id,
        )

    @construction.get('/v1/projects/{project_id}/construction/document-revisions/{revision_id}', operation_id='get_construction_document_revision')
    def get_construction_document_revision(
        project_id: str, revision_id: str, request: Request, principal: Principal,
        include_restricted: bool = Query(default=False),
    ) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        if include_restricted:
            _require(request, principal, action='construction:restricted_read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.document_revision(
            principal.tenant_id, project_id, revision_id, include_restricted=include_restricted,
        )

    @construction.post('/v1/projects/{project_id}/construction/issues', status_code=201, operation_id='create_construction_issue')
    def create_construction_issue(project_id: str, body: ConstructionIssueCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.create_issue(
            tenant_id=principal.tenant_id, project_id=project_id,
            issue_type=body.issue_type, description=body.description, evidence=body.evidence,
            reporter_id=principal.subject_id, severity=body.severity,
            idempotency_key=body.idempotency_key, entity_id=body.entity_id,
            place_id=body.place_id, observed_commit_id=body.observed_commit_id,
            responsible_party=body.responsible_party, due_at=body.due_at,
            permissions=body.permissions,
        )

    @construction.get('/v1/projects/{project_id}/construction/issues/{issue_id}', operation_id='get_construction_issue')
    def get_construction_issue(project_id: str, issue_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.issue(principal.tenant_id, project_id, issue_id)

    @construction.post('/v1/projects/{project_id}/construction/issues/{issue_id}/transition', operation_id='transition_construction_issue')
    def transition_construction_issue(project_id: str, issue_id: str, body: ConstructionIssueTransition, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.transition_issue(
            issue_id, tenant_id=principal.tenant_id, project_id=project_id,
            actor_id=principal.subject_id, target_state=body.target_state,
            evidence=body.evidence, note=body.note,
            residual_limitations=body.residual_limitations,
        )

    @construction.post('/v1/projects/{project_id}/construction/commissioning', status_code=201, operation_id='record_construction_commissioning')
    def record_construction_commissioning(project_id: str, body: ConstructionCommissioningCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.record_commissioning(
            tenant_id=principal.tenant_id, project_id=project_id,
            system_type=body.system_type, entity_ids=body.entity_ids, procedure=body.procedure,
            prerequisites=body.prerequisites, steps=body.steps, participants=body.participants,
            instruments=body.instruments, attachments=body.attachments, results=body.results,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
            issue_id=body.issue_id, retest_of_id=body.retest_of_id, accept=body.accept,
        )

    @construction.post('/v1/projects/{project_id}/construction/interchanges', status_code=201, operation_id='record_construction_interchange')
    def record_construction_interchange(project_id: str, body: ConstructionInterchangeCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.record_interchange(
            tenant_id=principal.tenant_id, project_id=project_id, format=body.format,
            direction=body.direction, source_asset_id=body.source_asset_id,
            source_sha256=body.source_sha256, schema_version=body.schema_version,
            units=body.units, crs=body.crs, owner_history=body.owner_history,
            global_ids=body.global_ids, classifications=body.classifications,
            properties=body.properties, relationships=body.relationships,
            geometry_conversion_report=body.geometry_conversion_report,
            unsupported_constructs=body.unsupported_constructs, alignment=body.alignment,
            mappings=body.mappings, issues=body.issues, truth_labels=body.truth_labels,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
        )

    @construction.post('/v1/projects/{project_id}/construction/handoffs', status_code=201, operation_id='create_construction_owner_handoff')
    def create_construction_owner_handoff(project_id: str, body: ConstructionHandoffCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        root = _context(request).settings.object_store_root.parent / 'vertical-exports'
        root.mkdir(parents=True, exist_ok=True)
        name_hash = sha256_bytes(f'{principal.tenant_id}:{project_id}:{body.idempotency_key}:construction'.encode())[:24]
        destination = root / f'construction-owner-handoff-{name_hash}.zip'
        return _context(request).construction.create_owner_handoff(
            tenant_id=principal.tenant_id, project_id=project_id, destination=destination,
            scope=body.scope, accepted_scene_commit_id=body.accepted_scene_commit_id,
            warranties=body.warranties, training=body.training, exclusions=body.exclusions,
            audience_profiles=body.audience_profiles, actor_id=principal.subject_id,
            idempotency_key=body.idempotency_key,
            classification=body.classification, audience=body.audience, purpose=body.purpose,
            restricted_export_approval_id=body.restricted_export_approval_id,
        )

    @construction.post(
        '/v1/projects/{project_id}/construction/restricted-export-approvals',
        status_code=201,
        operation_id='approve_construction_restricted_export',
    )
    def approve_construction_restricted_export(
        project_id: str,
        body: ConstructionRestrictedExportApprovalCreate,
        request: Request,
        principal: Principal,
    ) -> dict[str, Any]:
        _require(
            request,
            principal,
            action='construction:restricted_export',
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=body.purpose,
            classification=body.classification,
        )
        root = _context(request).settings.object_store_root.parent / 'vertical-exports'
        name_hash = sha256_bytes(
            f'{principal.tenant_id}:{project_id}:{body.handoff_idempotency_key}:construction'.encode()
        )[:24]
        destination_name = f'construction-owner-handoff-{name_hash}.zip'
        return _context(request).construction.approve_restricted_export(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scope=body.scope,
            accepted_scene_commit_id=body.accepted_scene_commit_id,
            warranties=body.warranties,
            training=body.training,
            exclusions=body.exclusions,
            audience_profiles=body.audience_profiles,
            destination_name=destination_name,
            classification=body.classification,
            audience=body.audience,
            purpose=body.purpose,
            approver_id=principal.subject_id,
            expires_at=body.expires_at,
        )

    @construction.get('/v1/projects/{project_id}/construction/handoffs/{handoff_id}', operation_id='get_construction_handoff')
    def get_construction_handoff(project_id: str, handoff_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.handoff(principal.tenant_id, project_id, handoff_id)

    @construction.get('/v1/projects/{project_id}/construction/search', operation_id='search_construction_facility')
    def search_construction_facility(
        project_id: str, request: Request, principal: Principal,
        query: str = Query(default=''), system_pack: str | None = Query(default=None),
        state: str | None = Query(default=None), include_restricted: bool = Query(default=False),
    ) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        if include_restricted:
            _require(request, principal, action='construction:restricted_read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.search_facility_records(
            principal.tenant_id, project_id, query=query, system_pack=system_pack,
            state=state, include_restricted=include_restricted,
        )

    @construction.get('/v1/projects/{project_id}/construction/system-packs/{pack}', operation_id='get_construction_system_pack')
    def get_construction_system_pack(
        project_id: str, pack: str, request: Request, principal: Principal,
        include_restricted: bool = Query(default=False),
    ) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        if include_restricted:
            _require(request, principal, action='construction:restricted_read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.export_system_pack(
            principal.tenant_id, project_id, pack=pack, include_restricted=include_restricted,
        )

    # Progress 06 LiveForever vertical ------------------------------------------------------
    @memory.post('/v1/projects/{project_id}/liveforever/governance', status_code=201, operation_id='create_liveforever_governance')
    def create_liveforever_governance(project_id: str, body: LiveForeverGovernanceCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.create_governance_record(
            tenant_id=principal.tenant_id, project_id=project_id, record_type=body.record_type,
            subject_id=body.subject_id, grantor_id=body.grantor_id,
            authority_basis=body.authority_basis, data_scope=body.data_scope,
            purposes=body.purposes, modalities=body.modalities, audiences=body.audiences,
            providers=body.providers, geography=body.geography, effective_at=body.effective_at,
            expires_at=body.expires_at, posthumous_rules=body.posthumous_rules,
            evidence_asset_ids=body.evidence_asset_ids, successor_ids=body.successor_ids,
            dispute=body.dispute, freeze_high_risk=body.freeze_high_risk,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
            consent_grant_id=body.consent_grant_id,
        )

    @memory.get('/v1/projects/{project_id}/liveforever/governance/{governance_id}', operation_id='get_liveforever_governance')
    def get_liveforever_governance(project_id: str, governance_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.governance_record(principal.tenant_id, project_id, governance_id)

    @memory.post('/v1/projects/{project_id}/liveforever/interviews', status_code=201, operation_id='create_liveforever_interview')
    def create_liveforever_interview(project_id: str, body: LiveForeverInterviewCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.create_interview(
            tenant_id=principal.tenant_id, project_id=project_id, subject_id=body.subject_id,
            participants=body.participants, consent_context=body.consent_context,
            recording_state=body.recording_state, source_media_ids=body.source_media_ids,
            timeline=body.timeline, device=body.device, environment=body.environment,
            interruptions=body.interruptions, question_lineage=body.question_lineage,
            pacing_policy=body.pacing_policy, actor_id=principal.subject_id,
            idempotency_key=body.idempotency_key, complete=body.complete,
        )

    @memory.get('/v1/projects/{project_id}/liveforever/interviews/{interview_id}', operation_id='get_liveforever_interview')
    def get_liveforever_interview(
        project_id: str, interview_id: str, request: Request, principal: Principal,
        include_private_marks: bool = Query(default=False),
    ) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id)
        if include_private_marks:
            _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.interview(
            principal.tenant_id, project_id, interview_id, include_private_marks=include_private_marks,
        )

    @memory.post('/v1/projects/{project_id}/liveforever/interviews/{interview_id}/segments', status_code=201, operation_id='create_liveforever_transcript_segment')
    def create_liveforever_transcript_segment(project_id: str, interview_id: str, body: LiveForeverTranscriptSegmentCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.add_transcript_segment(
            interview_id, tenant_id=principal.tenant_id, project_id=project_id,
            segment_index=body.segment_index, start_ms=body.start_ms, end_ms=body.end_ms,
            speaker_label=body.speaker_label, speaker_confidence=body.speaker_confidence,
            original_text=body.original_text, source_media_id=body.source_media_id,
            spatial_anchor=body.spatial_anchor, private_marks=body.private_marks,
            followup_suggestions=body.followup_suggestions, actor_id=principal.subject_id,
        )

    @memory.post('/v1/projects/{project_id}/liveforever/transcript-segments/{segment_id}/corrections', operation_id='correct_liveforever_transcript_segment')
    def correct_liveforever_transcript_segment(project_id: str, segment_id: str, body: LiveForeverTranscriptCorrection, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.correct_transcript_segment(
            segment_id, tenant_id=principal.tenant_id, project_id=project_id,
            editor_id=principal.subject_id, edited_text=body.edited_text,
            reason=body.reason, review_state=body.review_state,
        )

    @memory.post('/v1/projects/{project_id}/liveforever/records/{record_id}/revisions', status_code=201, operation_id='revise_liveforever_record')
    def revise_liveforever_record(project_id: str, record_id: str, body: LiveForeverRecordRevision, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        revised_id = _context(request).liveforever.revise_record(
            record_id, tenant_id=principal.tenant_id, project_id=project_id,
            editor_id=principal.subject_id, correction_type=body.correction_type,
            reason=body.reason, changes=body.changes, audience=body.audience,
            purpose=body.purpose,
        )
        return {"record_id": revised_id, "revises_record_id": record_id, "original_preserved": True}

    @memory.post('/v1/projects/{project_id}/liveforever/editions', status_code=201, operation_id='create_liveforever_edition')
    def create_liveforever_edition(project_id: str, body: LiveForeverEditionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.create_edition(
            tenant_id=principal.tenant_id, project_id=project_id, name=body.name,
            audience=body.audience, purpose=body.purpose,
            presentation_choices=body.presentation_choices, scene_commit_id=body.scene_commit_id,
            narrative_path=body.narrative_path, policy_snapshot=body.policy_snapshot,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
            publish=body.publish, supersedes_edition_id=body.supersedes_edition_id,
        )

    @memory.get('/v1/projects/{project_id}/liveforever/edition-revisions/{edition_id}', operation_id='get_liveforever_edition_revision')
    def get_liveforever_edition_revision(project_id: str, edition_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.edition_by_id(principal.tenant_id, project_id, edition_id)

    @memory.post('/v1/projects/{project_id}/liveforever/derivatives', status_code=201, operation_id='register_liveforever_derivative')
    def register_liveforever_derivative(project_id: str, body: LiveForeverDerivativeCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.register_derivative(
            tenant_id=principal.tenant_id, project_id=project_id,
            derivative_type=body.derivative_type, source_ids=body.source_ids,
            subject_ids=body.subject_ids, consent_grant_ids=body.consent_grant_ids,
            audience=body.audience, classification=body.classification,
            retention=body.retention, provider=body.provider,
            generation_lineage=body.generation_lineage, policy=body.policy,
            actor_id=principal.subject_id, idempotency_key=body.idempotency_key,
        )

    @memory.get('/v1/projects/{project_id}/liveforever/derivatives/{derivative_id}', operation_id='get_liveforever_derivative')
    def get_liveforever_derivative(project_id: str, derivative_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.derivative(principal.tenant_id, project_id, derivative_id)

    @memory.get('/v1/projects/{project_id}/liveforever/memory-room/{subject_id}', operation_id='get_liveforever_memory_room')
    def get_liveforever_memory_room(
        project_id: str, subject_id: str, request: Request, principal: Principal,
        audience: Audience = Query(...), purpose: str = Query(...),
        include_private_transcript_marks: bool = Query(default=False),
    ) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id, purpose=purpose, audience=audience)
        if include_private_transcript_marks:
            _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.memory_room(
            principal.tenant_id, project_id, subject_id=subject_id, audience=audience,
            purpose=purpose, include_private_transcript_marks=include_private_transcript_marks,
        )

    @memory.post('/v1/projects/{project_id}/liveforever/preservation-releases', status_code=201, operation_id='create_liveforever_preservation_release')
    def create_liveforever_preservation_release(project_id: str, body: LiveForeverPreservationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        root = _context(request).settings.object_store_root.parent / 'vertical-exports'
        root.mkdir(parents=True, exist_ok=True)
        name_hash = sha256_bytes(f'{principal.tenant_id}:{project_id}:{body.idempotency_key}:liveforever'.encode())[:24]
        destination = root / f'liveforever-preservation-{name_hash}.zip'
        return _context(request).liveforever.create_preservation_release(
            tenant_id=principal.tenant_id, project_id=project_id, edition_id=body.edition_id,
            destination=destination, originals=body.originals,
            technical_metadata=body.technical_metadata, rights_consent=body.rights_consent,
            memory_graph=body.memory_graph, scene_manifests=body.scene_manifests,
            open_assets=body.open_assets, human_guide=body.human_guide,
            offline_fallback=body.offline_fallback, replicas=body.replicas,
            format_migrations=body.format_migrations, succession=body.succession,
            shutdown=body.shutdown, actor_id=principal.subject_id,
            idempotency_key=body.idempotency_key,
        )

    @memory.get('/v1/projects/{project_id}/liveforever/preservation-releases/{release_id}', operation_id='get_liveforever_preservation_release')
    def get_liveforever_preservation_release(project_id: str, release_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.preservation_release(principal.tenant_id, project_id, release_id)

    @construction.post('/v1/projects/{project_id}/construction/hierarchy', status_code=201, operation_id='create_construction_hierarchy')
    def construction_hierarchy(project_id: str, body: ConstructionHierarchy, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).construction.create_hierarchy_item(tenant_id=principal.tenant_id, project_id=project_id, record_type=body.record_type, name=body.name, parent_id=body.parent_id, state=body.state, actor_id=principal.subject_id, attributes=body.attributes)
        return {'record_id': identifier}

    @construction.post('/v1/projects/{project_id}/construction/systems', status_code=201, operation_id='create_construction_system')
    def construction_system(project_id: str, body: ConstructionSystem, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).construction.create_system_record(tenant_id=principal.tenant_id, project_id=project_id, system_type=body.system_type, parent_id=body.parent_id, entity_id=body.entity_id, state=body.state, data=body.data, evidence_asset_ids=body.evidence_asset_ids, actor_id=principal.subject_id)
        return {'record_id': identifier}

    @construction.post('/v1/projects/{project_id}/construction/systems/{record_id}/verify', operation_id='verify_construction_system')
    def verify_construction_system(
        project_id: str, record_id: str, body: ConstructionSystemVerification,
        request: Request, principal: Principal,
    ) -> dict[str, Any]:
        _require(request, principal, action='construction:verify', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.verify_system_record(
            record_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            verifier_id=principal.subject_id,
            method=body.method,
            scope=body.scope,
            exclusions=body.exclusions,
            evidence_asset_ids=body.evidence_asset_ids,
            signature_asset_id=body.signature_asset_id,
            idempotency_key=body.idempotency_key,
        )

    @construction.post('/v1/projects/{project_id}/construction/documents', status_code=201, operation_id='attach_construction_document')
    def construction_document(project_id: str, body: ConstructionDocument, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).construction.attach_document(tenant_id=principal.tenant_id, project_id=project_id, document_type=body.document_type, asset_id=body.asset_id, parent_id=body.parent_id, page_region=body.page_region, spatial_anchor=body.spatial_anchor, data=body.data, actor_id=principal.subject_id)
        return {'record_id': identifier, 'revision_id': identifier, 'canonical_revision': True}

    @construction.post('/v1/projects/{project_id}/construction/deficiencies', status_code=201, operation_id='create_deficiency')
    def create_deficiency(project_id: str, body: DeficiencyCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        identifier = _context(request).construction.create_deficiency(tenant_id=principal.tenant_id, project_id=project_id, entity_id=body.entity_id, description=body.description, severity=body.severity, evidence_asset_ids=body.evidence_asset_ids, actor_id=principal.subject_id)
        return {'deficiency_id': identifier}

    @construction.post(
        '/v1/projects/{project_id}/construction/deficiencies/{deficiency_id}/retest',
        operation_id='retest_project_deficiency',
    )
    def retest_deficiency(
        project_id: str,
        deficiency_id: str,
        body: DeficiencyRetest,
        request: Request,
        principal: Principal,
    ) -> dict[str, Any]:
        _require(request, principal, action='construction:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).construction.correct_and_retest(
            deficiency_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            correction=body.correction,
            correction_asset_ids=body.correction_asset_ids,
            test_result=body.test_result,
            test_asset_ids=body.test_asset_ids,
            tester_id=principal.subject_id,
        )

    @construction.post(
        '/v1/construction/deficiencies/{deficiency_id}/retest',
        include_in_schema=False,
        operation_id='deny_unscoped_deficiency_retest',
    )
    def deny_unscoped_deficiency_retest(
        deficiency_id: str,
        body: DeficiencyRetest,
        request: Request,
        principal: Principal,
    ) -> dict[str, Any]:
        raise AuthorizationError(
            'PROJECT_SCOPE_REQUIRED',
            'deficiency retesting requires an authenticated tenant-and-project-scoped route',
        )

    @construction.get('/v1/projects/{project_id}/construction/reports/{report_type}', operation_id='get_construction_report')
    def construction_report(project_id: str, report_type: Literal['owner', 'technical'], request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='construction:read', tenant_id=principal.tenant_id, project_id=project_id)
        if report_type == 'owner':
            return _context(request).construction.owner_report(principal.tenant_id, project_id)
        return _context(request).construction.technical_report(principal.tenant_id, project_id)

    @memory.post('/v1/projects/{project_id}/liveforever/consents', status_code=201, operation_id='grant_consent')
    def grant_consent(project_id: str, body: ConsentGrantCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='consent:*', tenant_id=principal.tenant_id, project_id=project_id)
        grant_id = _context(request).liveforever.grant_consent(tenant_id=principal.tenant_id, project_id=project_id, subject_id=body.subject_id, granted_by=principal.subject_id, purposes=body.purposes, audiences=body.audiences, scopes=body.scopes, derivative_policy=body.derivative_policy, expires_at=body.expires_at)
        return {'grant_id': grant_id}

    @memory.post(
        '/v1/projects/{project_id}/liveforever/consents/{grant_id}/revoke',
        operation_id='revoke_project_consent',
    )
    def revoke_consent(
        project_id: str,
        grant_id: str,
        body: ConsentRevoke,
        request: Request,
        principal: Principal,
    ) -> dict[str, Any]:
        _require(request, principal, action='consent:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.revoke_consent(
            grant_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            reason=body.reason,
        )

    @memory.post(
        '/v1/liveforever/consents/{grant_id}/revoke',
        include_in_schema=False,
        operation_id='deny_unscoped_consent_revoke',
    )
    def deny_unscoped_consent_revoke(
        grant_id: str,
        body: ConsentRevoke,
        request: Request,
        principal: Principal,
    ) -> dict[str, Any]:
        raise AuthorizationError(
            'PROJECT_SCOPE_REQUIRED',
            'consent revocation requires an authenticated tenant-and-project-scoped route',
        )

    @memory.post('/v1/projects/{project_id}/liveforever/records', status_code=201, operation_id='create_memory_record')
    def create_memory(project_id: str, body: MemoryCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id, purpose=body.purpose, audience=body.audience)
        record_id = _context(request).liveforever.create_record(tenant_id=principal.tenant_id, project_id=project_id, record_type=body.record_type, subject_id=body.subject_id, subject_scope=body.subject_scope, related_ids=body.related_ids, data=body.data, source_class=body.source_class, confidence=body.confidence, evidence_asset_ids=body.evidence_asset_ids, audience=body.audience, actor_id=principal.subject_id, purpose=body.purpose, generated_lineage=body.generated_lineage)
        return {'record_id': record_id}

    @memory.post('/v1/projects/{project_id}/liveforever/records/{record_id}/review', status_code=201, operation_id='review_liveforever_record')
    def review_liveforever_record(
        project_id: str, record_id: str, body: LiveForeverRecordReview,
        request: Request, principal: Principal,
    ) -> dict[str, Any]:
        _require(request, principal, action='liveforever:review', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.review_record(
            record_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            reviewer_id=principal.subject_id,
            target_source_class=SourceClass(body.target_source_class),
            rationale=body.rationale,
            evidence_asset_ids=body.evidence_asset_ids,
            confidence=body.confidence,
            idempotency_key=body.idempotency_key,
        )

    @memory.post('/v1/projects/{project_id}/liveforever/conflicting-recollections', status_code=201, operation_id='create_conflicting_recollections')
    def create_conflicts(project_id: str, body: ConflictingRecollections, request: Request, principal: Principal) -> list[str]:
        _require(request, principal, action='liveforever:*', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).liveforever.conflicting_recollections(tenant_id=principal.tenant_id, project_id=project_id, subject_id=body.subject_id, event_key=body.event_key, recollections=body.recollections, audience=body.audience, actor_id=principal.subject_id)

    @memory.post('/v1/projects/{project_id}/liveforever/experience', operation_id='configure_liveforever_experience')
    def configure_experience(project_id: str, body: ExperienceRequest, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id, audience=body.audience)
        return _context(request).liveforever.experience_configuration(principal.tenant_id, project_id, body.subject_id, requested_features=body.requested_features, audience=body.audience)

    @memory.get('/v1/projects/{project_id}/liveforever/editions/{audience}', operation_id='get_liveforever_edition')
    def get_edition(project_id: str, audience: Audience, request: Request, principal: Principal, purpose: str=Query(...)) -> dict[str, Any]:
        _require(request, principal, action='liveforever:read', tenant_id=principal.tenant_id, project_id=project_id, purpose=purpose, audience=audience)
        return _context(request).liveforever.edition(principal.tenant_id, project_id, audience=audience, purpose=purpose)

    @collaboration.post('/v1/projects/{project_id}/comments', status_code=201, operation_id='create_comment')
    def create_comment(project_id: str, body: CommentCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        comment_id = _context(request).collaboration.comment(tenant_id=principal.tenant_id, project_id=project_id, body=body.body, author_id=principal.subject_id, scene_commit_id=body.scene_commit_id, entity_id=body.entity_id, anchor=body.anchor, supersedes_comment_id=body.supersedes_comment_id)
        return {'comment_id': comment_id}

    @collaboration.post('/v1/projects/{project_id}/tasks', status_code=201, operation_id='create_task')
    def create_task(project_id: str, body: TaskCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id, project_id=project_id)
        task_id = _context(request).collaboration.create_task(tenant_id=principal.tenant_id, project_id=project_id, title=body.title, description=body.description, created_by=principal.subject_id, entity_id=body.entity_id, assignee_id=body.assignee_id, priority=body.priority, due_at=body.due_at)
        return {'task_id': task_id}

    @collaboration.post('/v1/tasks/{task_id}/transition', operation_id='transition_task')
    def transition_task(task_id: str, body: TaskTransition, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='scene:read', tenant_id=principal.tenant_id)
        return _context(request).collaboration.transition_task(task_id, new_state=body.state, actor_id=principal.subject_id)

    @notification.post('/v1/projects/{project_id}/notifications', status_code=202, operation_id='queue_notification')
    def queue_notification(project_id: str, body: NotificationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='project:*', tenant_id=principal.tenant_id, project_id=project_id)
        notification_id = _context(request).notifications.queue(tenant_id=principal.tenant_id, project_id=project_id, recipient_id=body.recipient_id, channel=body.channel, template_id=body.template_id, payload=body.payload, sensitive=body.sensitive)
        return {'notification_id': notification_id}
    @security_ops.post('/v1/security/threat-manifests', status_code=201, operation_id='register_threat_manifest')
    def register_threat_manifest(body: ThreatManifestCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:threat_manage', tenant_id=principal.tenant_id)
        return _context(request).security_ops.register_threat_manifest(
            scope=body.scope,
            threats=body.threats,
            misuse_cases=body.misuse_cases,
            public_viewer_analysis=body.public_viewer_analysis,
            residual_risks=body.residual_risks,
            owner=body.owner,
            review_trigger=body.review_trigger,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/privileged-access', status_code=201, operation_id='grant_privileged_access')
    def grant_privileged_access(tenant_id: str, body: PrivilegedAccessCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privileged_access', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.grant_privileged_access(
            tenant_id=tenant_id,
            project_id=body.project_id,
            subject_id=body.subject_id,
            actions=body.actions,
            resource_scope=body.resource_scope,
            purpose=body.purpose,
            mfa_method=body.mfa_method,
            mfa_verified_at=body.mfa_verified_at,
            duration_seconds=body.duration_seconds,
            requested_by=body.requested_by,
            approved_by=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/privileged-access/{grant_id}/revoke', operation_id='revoke_privileged_access')
    def revoke_privileged_access(tenant_id: str, grant_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privileged_access', tenant_id=tenant_id)
        return _context(request).security_ops.revoke_privileged_access(grant_id=grant_id, tenant_id=tenant_id, actor_id=principal.subject_id)

    @security_ops.post('/v1/tenants/{tenant_id}/security/workload-identities', status_code=201, operation_id='issue_workload_identity')
    def issue_workload_identity(tenant_id: str, body: WorkloadIdentityCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:workload_identity', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.issue_workload_identity(
            tenant_id=tenant_id,
            project_id=body.project_id,
            workload_id=body.workload_id,
            audience=body.audience,
            scopes=body.scopes,
            purpose=body.purpose,
            ttl_seconds=body.ttl_seconds,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/workload-identities/validate', operation_id='validate_workload_identity')
    def validate_workload_identity(tenant_id: str, body: WorkloadIdentityValidate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:workload_identity', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.validate_workload_identity(
            body.token,
            audience=body.audience,
            required_scope=body.required_scope,
            purpose=body.purpose,
            tenant_id=tenant_id,
            project_id=body.project_id,
            workload_id=body.workload_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/workload-identities/{grant_id}/revoke', operation_id='revoke_workload_identity')
    def revoke_workload_identity(tenant_id: str, grant_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:workload_identity', tenant_id=tenant_id)
        _context(request).security_ops.revoke_workload_identity(grant_id=grant_id, tenant_id=tenant_id, actor_id=principal.subject_id)
        return {'grant_id': grant_id, 'state': 'revoked'}

    @security_ops.post('/v1/tenants/{tenant_id}/security/key-scopes', status_code=201, operation_id='register_key_scope')
    def register_key_scope(tenant_id: str, body: KeyScopeCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:key_manage', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.register_key_scope(
            tenant_id=tenant_id,
            project_id=body.project_id,
            person_id=body.person_id,
            key_id=body.key_id,
            backend=body.backend,
            recovery_policy=body.recovery_policy,
            actor_id=principal.subject_id,
            rotated_from_key_id=body.rotated_from_key_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/key-scopes/{key_scope_id}/access', status_code=201, operation_id='record_key_access')
    def record_key_access(tenant_id: str, key_scope_id: str, body: KeyAccessCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:key_manage', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.record_key_access(
            key_scope_id=key_scope_id,
            tenant_id=tenant_id,
            project_id=body.project_id,
            actor_or_workload=body.actor_or_workload,
            purpose=body.purpose,
            action=body.action,
            resource_scope=body.resource_scope,
            outcome=body.outcome,
            details=body.details,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/key-scopes/{key_scope_id}/emergency-revoke', operation_id='emergency_revoke_key')
    def emergency_revoke_key(tenant_id: str, key_scope_id: str, body: EmergencyKeyRevoke, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:key_manage', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.emergency_revoke_key(
            key_scope_id=key_scope_id,
            tenant_id=tenant_id,
            project_id=body.project_id,
            actor_id=principal.subject_id,
            reason=body.reason,
            residual_timeline=body.residual_timeline,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/privacy/inventory', status_code=201, operation_id='register_privacy_inventory')
    def register_privacy_inventory(tenant_id: str, body: PrivacyInventoryCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privacy_manage', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.register_privacy_inventory(
            tenant_id=tenant_id,
            project_id=body.project_id,
            data_category=body.data_category,
            purpose=body.purpose,
            legal_basis=body.legal_basis,
            consent_basis=body.consent_basis,
            processors=body.processors,
            residency=body.residency,
            retention=body.retention,
            security_controls=body.security_controls,
            rights_workflow=body.rights_workflow,
            classification=body.classification,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/privacy/impact-assessments', status_code=201, operation_id='assess_privacy_change')
    def assess_privacy_change(tenant_id: str, body: PrivacyImpactCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privacy_manage', tenant_id=tenant_id, project_id=body.project_id, purpose=body.purpose)
        return _context(request).security_ops.assess_privacy_change(
            tenant_id=tenant_id,
            project_id=body.project_id,
            change_type=body.change_type,
            change_reference=body.change_reference,
            purpose=body.purpose,
            data_categories=body.data_categories,
            processors=body.processors,
            risks=body.risks,
            controls=body.controls,
            residual_risk=body.residual_risk,
            decision=body.decision,
            reviewer_id=principal.subject_id,
            expires_at=body.expires_at,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/privacy/rights-requests', status_code=201, operation_id='create_privacy_rights_request')
    def create_privacy_rights_request(tenant_id: str, body: PrivacyRightsCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privacy_manage', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.create_rights_workflow(
            tenant_id=tenant_id,
            project_id=body.project_id,
            subject_id=body.subject_id,
            request_type=body.request_type,
            scope=body.scope,
            requested_by=body.requested_by,
            verified_by=principal.subject_id,
            due_days=body.due_days,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/privacy/rights-requests/{rights_request_id}/complete', operation_id='complete_privacy_rights_request')
    def complete_privacy_rights_request(tenant_id: str, rights_request_id: str, body: PrivacyRightsComplete, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:privacy_manage', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.complete_rights_workflow(
            rights_request_id=rights_request_id,
            tenant_id=tenant_id,
            project_id=body.project_id,
            outcomes=body.outcomes,
            evidence=body.evidence,
            completed_by=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/security/incidents', status_code=201, operation_id='record_security_incident')
    def record_security_incident(tenant_id: str, body: SecurityIncidentCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:incident_manage', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.record_incident(
            tenant_id=tenant_id,
            project_id=body.project_id,
            incident_type=body.incident_type,
            severity=body.severity,
            affected_subjects=body.affected_subjects,
            affected_resources=body.affected_resources,
            containment=body.containment,
            notification_decision=body.notification_decision,
            evidence=body.evidence,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/projects/{project_id}/security/provider-incidents', status_code=201, operation_id='record_provider_incident_withdrawal')
    def record_provider_incident_withdrawal(project_id: str, body: ProviderIncidentWithdrawalCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:incident_manage', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).security_ops.record_provider_incident_withdrawal(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            provider_id=body.provider_id,
            source_asset_ids=body.source_asset_ids,
            derivative_asset_ids=body.derivative_asset_ids,
            publication_ids=body.publication_ids,
            cache_resource_ids=body.cache_resource_ids,
            export_ids=body.export_ids,
            evidence=body.evidence,
            notification_decision=body.notification_decision,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/security/transport-verifications', status_code=201, operation_id='verify_transport_profile')
    def verify_transport_profile(body: TransportVerificationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:transport_verify', tenant_id=principal.tenant_id)
        return _context(request).security_ops.verify_transport_profile(
            endpoint=body.endpoint,
            protocol=body.protocol,
            minimum_tls_version=body.minimum_tls_version,
            certificate_validated=body.certificate_validated,
            channel_authentication=body.channel_authentication,
            evidence=body.evidence,
            verified_by=principal.subject_id,
        )

    @security_ops.post('/v1/projects/{project_id}/security/capture-finalizations', status_code=201, operation_id='record_capture_finalization')
    def record_capture_finalization(project_id: str, body: CaptureFinalizationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:capture_finalize', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).security_ops.record_capture_finalization(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            capture_id=body.capture_id,
            package_root_hash=body.package_root_hash,
            archive_sha256=body.archive_sha256,
            device=body.device,
            app=body.app,
            signer_id=body.signer_id,
            verification_result=body.verification_result,
            verification=body.verification,
        )

    @security_ops.post('/v1/projects/{project_id}/security/provider-outputs', status_code=201, operation_id='validate_provider_output')
    def validate_provider_output(project_id: str, body: ProviderOutputValidationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:provider_governance', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).security_ops.validate_provider_output(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            provider_id=body.provider_id,
            operation_id=body.operation_id,
            output_sha256=body.output_sha256,
            media_type=body.media_type,
            byte_count=body.byte_count,
            validations=body.validations,
            validated_by=principal.subject_id,
        )

    @security_ops.post('/v1/projects/{project_id}/security/immersive-safety', status_code=201, operation_id='evaluate_immersive_safety')
    def evaluate_immersive_safety(project_id: str, body: ImmersiveSafetyCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:immersive_safety', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).security_ops.evaluate_immersive_safety(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            scene_id=body.scene_id,
            checks=body.checks,
            requested_modes=body.requested_modes,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/tenants/{tenant_id}/audit/security-verify', operation_id='verify_security_audit_chain')
    def verify_security_audit_chain(tenant_id: str, body: AuditSecurityVerify, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:audit_verify', tenant_id=tenant_id, project_id=body.project_id)
        return _context(request).security_ops.verify_audit_chain(
            tenant_id=tenant_id,
            project_id=body.project_id,
            referenced_manifests=body.referenced_manifests,
            verifier_id=principal.subject_id,
        )

    @security_ops.post('/v1/projects/{project_id}/security/providers/{provider_id}/authorize', operation_id='authorize_security_provider_execution')
    def authorize_security_provider_execution(project_id: str, provider_id: str, body: ProviderExecutionAuthorize, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:provider_governance', tenant_id=principal.tenant_id, project_id=project_id, purpose=body.purpose)
        return _context(request).security_ops.authorize_provider_execution(
            provider_id=provider_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            classification=body.classification,
            purpose=body.purpose,
            region=body.region,
            external=body.external,
            audience=body.audience,
            retention_days=body.retention_days,
            telemetry=body.telemetry,
        )

    @security_ops.post('/v1/projects/{project_id}/security/providers/{provider_id}/exceptions', status_code=201, operation_id='create_provider_governance_exception')
    def create_provider_governance_exception(project_id: str, provider_id: str, body: ProviderExceptionCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:provider_governance', tenant_id=principal.tenant_id, project_id=project_id, purpose=body.purpose)
        return _context(request).security_ops.create_provider_exception(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            provider_id=provider_id,
            scope=body.scope,
            purpose=body.purpose,
            requested_waivers=body.requested_waivers,
            approved_by=principal.subject_id,
            duration_seconds=body.duration_seconds,
        )

    @security_ops.post('/v1/projects/{project_id}/security/cache-invalidations', status_code=201, operation_id='invalidate_security_caches')
    def invalidate_security_caches(project_id: str, body: CacheInvalidationCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:cache_invalidate', tenant_id=principal.tenant_id, project_id=project_id)
        return _context(request).security_ops.invalidate_caches(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            resource_id=body.resource_id,
            reason=body.reason,
            targets=body.targets,
            actor_id=principal.subject_id,
        )

    @security_ops.post('/v1/security/releases', status_code=201, operation_id='create_supply_chain_release')
    def create_supply_chain_release(body: SupplyChainReleaseCreate, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:release_manage', tenant_id=principal.tenant_id)
        return _context(request).security_ops.create_release_record(
            version=body.version,
            source_commit=body.source_commit,
            source_root=body.source_root,
            component_manifests=body.component_manifests,
            evidence=body.evidence,
            rollback_plan=body.rollback_plan,
            environment_policy=body.environment_policy,
            signed_by=principal.subject_id,
            emergency_patch=body.emergency_patch,
            retrospective_review_due_at=body.retrospective_review_due_at,
        )

    @security_ops.post('/v1/security/releases/{release_record_id}/promote', operation_id='promote_supply_chain_release')
    def promote_supply_chain_release(release_record_id: str, request: Request, principal: Principal) -> dict[str, Any]:
        _require(request, principal, action='security:release_manage', tenant_id=principal.tenant_id)
        return _context(request).security_ops.promote_release(release_record_id=release_record_id, actor_id=principal.subject_id)

    return {'control-api': control, 'identity-policy': identity, 'capture-service': capture, 'workflow-service': workflow, 'scene-service': scene, 'evidence-service': evidence, 'search-service': search, 'export-service': export, 'notification-service': notification, 'audit-service': audit, 'representation-api': representation, 'provider-registry': providers, 'representation-publisher': publisher, 'construction': construction, 'liveforever': memory, 'collaboration': collaboration, 'security-ops': security_ops}
SERVICE_DEPENDENCIES: dict[str, set[str]] = {'control-api': {'control-api', 'construction', 'liveforever', 'collaboration'}, 'all': set(_routers().keys())}

def create_app(*, context: PlatformContext | None=None, service_name: str | None=None) -> FastAPI:
    settings = context.settings if context else Settings.from_env()
    context = context or PlatformContext.create(settings)
    service_name = service_name or os.getenv('SIP_SERVICE_NAME', 'all')
    logger = configure_logging(service_name)
    telemetry = PlatformObservability.create(service_name)
    tracing_enabled = configure_tracing(service_name)
    app = FastAPI(title=f'Spatial Intelligence Platform — {service_name}', version=API_VERSION, openapi_version='3.1.0', docs_url='/docs' if settings.environment != 'production' else None, redoc_url=None)
    app.state.platform = context
    app.state.service_name = service_name
    app.state.observability = telemetry
    app.state.tracing_enabled = tracing_enabled
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'] if settings.environment != 'production' else [], allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key', 'X-Request-ID'])

    @app.middleware('http')
    async def request_integrity(request: Request, call_next):
        supplied_request_id = request.headers.get('x-request-id', '')
        request_id = (
            supplied_request_id
            if 0 < len(supplied_request_id) <= 128
            and supplied_request_id.replace('-', '').replace('_', '').isalnum()
            else new_uuid()
        )
        request.state.request_id = request_id
        content_length = request.headers.get('content-length')
        timer = RequestTimer()
        telemetry.in_flight.labels(service=service_name).inc()
        status = 500
        error_code = 'none'
        response: Response | None = None

        def correlated_error(code: str, message: str, status_code: int, *, retryable: bool=False) -> JSONResponse:
            nonlocal error_code
            error_code = code
            request.state.error_code = code
            trace_id = current_trace_id() or 'none'
            request.state.trace_id = trace_id
            return JSONResponse(
                status_code=status_code,
                content={
                    'error': {
                        'code': code,
                        'message': message,
                        'details': {},
                        'retryable': retryable,
                        'correlation': {'request_id': request_id, 'trace_id': trace_id},
                    }
                },
            )

        def secure_response(response_value: Response) -> Response:
            response_value.headers['X-Request-ID'] = request_id
            response_value.headers['X-Trace-ID'] = getattr(request.state, 'trace_id', 'none')
            response_value.headers['X-Content-Type-Options'] = 'nosniff'
            response_value.headers['Referrer-Policy'] = 'no-referrer'
            response_value.headers['X-Frame-Options'] = 'DENY'
            response_value.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
            response_value.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
            response_value.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/v1') else 'no-cache'
            if settings.environment == 'production':
                response_value.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response_value

        with server_span(service_name=service_name, method=request.method, carrier=dict(request.headers)) as span:
            trace_id = current_trace_id() or 'none'
            request.state.trace_id = trace_id
            with bind_telemetry_context(BoundTelemetryContext(request_id=request_id, trace_id=trace_id)):
                try:
                    if content_length:
                        try:
                            parsed_length = int(content_length)
                        except ValueError:
                            response = correlated_error(
                                'CONTENT_LENGTH_INVALID',
                                'content-length must be an integer',
                                400,
                            )
                        else:
                            if parsed_length < 0:
                                response = correlated_error(
                                    'CONTENT_LENGTH_INVALID',
                                    'content-length must be non-negative',
                                    400,
                                )
                            elif parsed_length > settings.max_api_body_bytes:
                                response = correlated_error(
                                    'BODY_TOO_LARGE',
                                    'request body exceeds configured limit',
                                    413,
                                )
                    if response is None:
                        response = await call_next(request)
                    status = response.status_code
                    return secure_response(response)
                except Exception as exc:
                    error_code = 'INTERNAL_ERROR'
                    status = 500
                    telemetry.observe_error(error_code=error_code, outcome='unhandled_error')
                    logger.exception(
                        'unhandled request failure',
                        extra={
                            'request_id': request_id,
                            'trace_id': current_trace_id() or 'none',
                            'event': 'http.request.unhandled_error',
                            'outcome': 'unhandled_error',
                            'error_code': error_code,
                            'fields': {
                                'method': request.method,
                                'route': getattr(request.scope.get('route'), 'path', '__unmatched__'),
                                'exception_type': type(exc).__name__,
                            },
                        },
                    )
                    return secure_response(
                        correlated_error(
                            'INTERNAL_ERROR',
                            'the request could not be completed',
                            500,
                            retryable=True,
                        )
                    )
                finally:
                    route_object = request.scope.get('route')
                    route = getattr(route_object, 'path', None) or '__unmatched__'
                    principal = getattr(request.state, 'principal', None)
                    tenant_context = pseudonymize_identifier(
                        getattr(principal, 'tenant_id', None),
                        namespace='tenant',
                        key=settings.signing_key,
                    )
                    project_id = request.path_params.get('project_id') if request.path_params else None
                    project_context = pseudonymize_identifier(
                        project_id,
                        namespace='project',
                        key=settings.signing_key,
                    )
                    error_code = getattr(request.state, 'error_code', error_code)
                    outcome = 'success' if status < 400 else ('client_error' if status < 500 else 'server_error')
                    telemetry.observe(method=request.method, route=route, status=status, duration_seconds=timer.elapsed)
                    telemetry.in_flight.labels(service=service_name).dec()
                    if span is not None:
                        try:
                            span.update_name(f'{request.method} {route}')
                            span.set_attribute('http.route', route)
                            span.set_attribute('http.response.status_code', status)
                            span.set_attribute('sip.outcome', outcome)
                            span.set_attribute('sip.error_code', error_code)
                        except Exception:
                            pass
                    with bind_telemetry_context(
                        BoundTelemetryContext(
                            request_id=request_id,
                            trace_id=current_trace_id() or trace_id,
                            tenant_context=tenant_context,
                            project_context=project_context,
                        )
                    ):
                        logger.info(
                            'http request complete',
                            extra={
                                'event': 'http.request.complete',
                                'outcome': outcome,
                                'error_code': error_code,
                                'fields': {
                                    'method': request.method,
                                    'route': route,
                                    'status': status,
                                    'duration_seconds': round(timer.elapsed, 6),
                                },
                            },
                        )

    @app.exception_handler(SIPError)
    async def sip_error_handler(request: Request, exc: SIPError) -> JSONResponse:
        request_id = getattr(request.state, 'request_id', 'none')
        trace_id = current_trace_id() or getattr(request.state, 'trace_id', 'none')
        request.state.trace_id = trace_id
        request.state.error_code = exc.code
        telemetry.observe_error(error_code=exc.code, outcome='handled_error')
        logger.warning(
            'request rejected',
            extra={
                'request_id': request_id,
                'trace_id': trace_id,
                'event': 'http.request.rejected',
                'outcome': 'handled_error',
                'error_code': exc.code,
                'fields': {'status': exc.status_code, 'retryable': exc.retryable},
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.as_dict(request_id=request_id, trace_id=trace_id),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, 'request_id', 'none')
        trace_id = current_trace_id() or getattr(request.state, 'trace_id', 'none')
        request.state.error_code = 'VALUE_INVALID'
        telemetry.observe_error(error_code='VALUE_INVALID', outcome='handled_error')
        issues = [
            {
                'path': '.'.join(str(item) for item in error.get('loc', []) if item != 'body'),
                'type': str(error.get('type', 'value_error')),
            }
            for error in exc.errors()[:20]
        ]
        return JSONResponse(
            status_code=422,
            content={
                'error': {
                    'code': 'VALUE_INVALID',
                    'message': 'request validation failed',
                    'details': {'issues': issues},
                    'retryable': False,
                    'correlation': {'request_id': request_id, 'trace_id': trace_id},
                }
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, _: ValueError) -> JSONResponse:
        request_id = getattr(request.state, 'request_id', 'none')
        trace_id = current_trace_id() or getattr(request.state, 'trace_id', 'none')
        request.state.error_code = 'VALUE_INVALID'
        telemetry.observe_error(error_code='VALUE_INVALID', outcome='handled_error')
        return JSONResponse(
            status_code=400,
            content={
                'error': {
                    'code': 'VALUE_INVALID',
                    'message': 'request value is invalid',
                    'details': {},
                    'retryable': False,
                    'correlation': {'request_id': request_id, 'trace_id': trace_id},
                }
            },
        )

    @app.get('/health/live', operation_id='health_live')
    def health_live() -> dict[str, Any]:
        return {'status': 'live', 'service': service_name, 'version': API_VERSION}

    @app.get('/health/ready', operation_id='health_ready')
    def health_ready() -> dict[str, Any]:
        try:
            with context.database.session() as session:
                session.execute(__import__('sqlalchemy').text('SELECT 1'))
        except Exception:
            telemetry.readiness_failures.labels(service=service_name, dependency='database').inc()
            raise
        try:
            context.store.probe()
        except Exception:
            telemetry.readiness_failures.labels(service=service_name, dependency='object_store').inc()
            raise
        return {'status': 'ready', 'service': service_name, 'database': 'ok', 'object_store': 'ok', 'tracing': tracing_enabled, 'version': API_VERSION}

    @app.get('/metrics', include_in_schema=False)
    def metrics() -> Response:
        telemetry.refresh_operation_depth(context.database)
        return Response(content=telemetry.render(), media_type='text/plain; version=0.0.4; charset=utf-8')

    routers = _routers()
    selected = SERVICE_DEPENDENCIES.get(service_name, {service_name})
    unknown = selected - routers.keys()
    if unknown:
        raise RuntimeError(f'unknown SIP service boundary: {sorted(unknown)}')
    for name in sorted(selected):
        app.include_router(routers[name])
    return app
app = create_app(service_name=os.getenv('SIP_SERVICE_NAME', 'all'))

def main() -> None:
    import uvicorn
    uvicorn.run('sip.api:app', host='0.0.0.0', port=int(os.getenv('PORT', '8080')), proxy_headers=True)
