export type UUID = string;
export type Sha256 = string;
export type Classification =
  | "public"
  | "internal"
  | "confidential"
  | "restricted"
  | "critical_infrastructure"
  | "biometric"
  | "minor";
export type SourceClass =
  | "direct_capture" | "observed" | "measured" | "verified" | "design" | "proposed"
  | "inferred" | "generated" | "recalled" | "corroborated" | "disputed" | "superseded";
export type AuthorityClass =
  | "none" | "evidence" | "metric" | "design" | "visual"
  | "derived_non_authoritative" | "field_verified" | "historical_assertion";
export type RepresentationKind = "metric" | "visual" | "interaction" | "design" | "evidence";
export type Audience = "private" | "family" | "project" | "owner" | "public";

export interface ProvenanceRef {
  source_ids: string[];
  run_id?: string;
  code_commit?: string;
  container_digest?: string;
  model_manifest_id?: string;
  model_checkpoint_hash?: string;
  parameters_hash?: Sha256;
  environment_hash?: Sha256;
  output_hash?: Sha256;
  validation_result_id?: string;
  notes?: string;
}

export interface CoordinateFrame {
  frame_id: string;
  parent_frame_id?: string;
  convention: "right_handed_y_up_meters" | "right_handed_z_up_meters" | "source_native";
  units: "meter" | "millimeter";
  transform_to_parent?: number[][];
  uncertainty_m?: number;
}

export interface RepresentationAsset {
  representation_id: UUID;
  scene_id: UUID;
  asset_id: UUID;
  kind: RepresentationKind;
  provider_id: string;
  provider_version: string;
  coordinate_frame_id: string;
  source_class: SourceClass;
  authority_class: AuthorityClass;
  authority_ceiling: AuthorityClass;
  disposable: boolean;
  lossy: boolean;
  intended_uses: string[];
  prohibited_uses: string[];
  quality: Record<string, unknown>;
  provenance: ProvenanceRef;
  support_map: Record<string, unknown>;
  state: "quarantined" | "quality_failed" | "approved" | "published" | "superseded";
}

export interface SceneEntity {
  entity_id: UUID;
  scene_id: UUID;
  entity_type: string;
  name: string;
  source_class: SourceClass;
  authority_class: AuthorityClass;
  confidence: number;
  attributes: Record<string, unknown>;
  provenance: ProvenanceRef;
  policy: Record<string, unknown>;
  stable_support: Record<string, unknown>;
}

export interface Measurement {
  measurement_id: UUID;
  entity_id?: UUID;
  value: number;
  unit: string;
  uncertainty: number;
  source_asset_ids: UUID[];
  calibration: Record<string, unknown>;
  verifier_id?: string;
  verification_date?: string;
  authority_class: AuthorityClass;
  warning: string;
}

export interface EventEnvelope<T extends Record<string, unknown> = Record<string, unknown>> {
  event_id: UUID;
  event_type: string;
  schema_version: string;
  tenant_id: string;
  project_id: string | null;
  aggregate_type: string;
  aggregate_id: string;
  occurred_at: string;
  recorded_at: string;
  actor_id: string | null;
  workload_identity: string | null;
  producer: string;
  classification: string;
  trace_id: string | null;
  causation_id: string | null;
  correlation_id: string | null;
  payload: T;
  payload_hash: Sha256;
}

export interface ApiError {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export interface WorkerResourceLimits {
  max_wall_seconds: number;
  max_cpu_seconds: number;
  max_memory_bytes: number;
  max_input_bytes: number;
  max_output_bytes: number;
  gpu_count: number;
}

export interface WorkerManifest {
  schema: "sip.worker-manifest/v1";
  name: string;
  version: string;
  entrypoint: string;
  entrypoint_sha256: Sha256;
  runtime_module: string;
  runtime_sha256: Sha256;
  protocol_module: string;
  protocol_sha256: Sha256;
  sandbox_module: string;
  sandbox_sha256: Sha256;
  workload_identity: string;
  capabilities: string[];
  input_contract: string;
  output_contract: string;
  compatibility: string;
  governance: string;
  durable: true;
  idempotent: true;
  cancellable: true;
  checkpointed: true;
  audited: true;
  least_privilege: true;
  shell_access: false;
  network_access: false;
  publication_permission: false;
  output_mode: "quarantine_candidate";
  filesystem_read_scopes: string[];
  filesystem_write_scopes: string[];
  resource_limits: WorkerResourceLimits;
  requirement_ids: string[];
  manifest_sha256: Sha256;
}

export interface WorkerOutputStagingScope {
  scope_id: string;
  mode: "write_only_quarantine";
  tenant_id: string;
  project_id: string;
  operation_id: string;
  maximum_bytes: number;
  expires_at: string;
}

export interface WorkerLease {
  schema_version: "sip.worker-lease/v1";
  lease_id: string;
  run_id: string;
  operation_id: string;
  attempt: number;
  operation_type: string;
  adapter_profile: string;
  input_manifest: Record<string, unknown>;
  input_manifest_hash: Sha256;
  input_byte_count: number;
  resume_checkpoint: Record<string, unknown>;
  resume_progress: number;
  output_staging_scope: WorkerOutputStagingScope;
  resource_limits: WorkerResourceLimits;
  deadline_at: string;
  cancellation_token: string;
  workload_identity: string;
  capabilities: string[];
  worker_manifest_sha256: Sha256;
  issued_at: string;
  expires_at: string;
}

export interface SignedWorkerLease {
  lease: WorkerLease;
  token: string;
}

export interface WorkerProgressRecord {
  sequence: number;
  stage: string;
  progress: number;
  completed_units?: number;
  total_units?: number;
  unit?: string;
  warnings: string[];
  quality: Record<string, unknown>;
  resource_use: Record<string, number>;
  safe_to_resume: boolean;
  payload: Record<string, unknown>;
  checkpoint_hash: Sha256;
}

export interface RepresentationCandidatePackage {
  schema_version: "sip.representation-candidate/v1";
  candidate_id: string;
  representation_id: UUID;
  asset_id: UUID;
  asset_sha256: Sha256;
  media_type: string;
  operation_id: string;
  operation_type: string;
  state: "quarantined";
  output_role: string;
  representation_kind: RepresentationKind;
  coordinate_frame_id: string;
  source_scene_revision_id?: string;
  source_asset_ids: UUID[];
  payload_hash: Sha256;
  source_manifest_hash: Sha256;
  parameters_hash: Sha256;
  environment_manifest_hash: Sha256;
  provider_id: string;
  provider_version: string;
  provider_executable_digest: string;
  worker_receipt_hash?: Sha256;
  authority_ceiling: string;
  disposable: boolean;
  lossy: boolean;
  intended_uses: string[];
  prohibited_uses: string[];
  provider_metrics: Record<string, unknown>;
  limitations: string[];
  publication_permission: false;
  independent_validation_required: true;
  human_review_required: true;
}

export interface WorkerReceipt {
  schema_version: "sip.worker-receipt/v1";
  lease_id: string;
  run_id: string;
  operation_id: string;
  operation_type: string;
  adapter_profile: string;
  attempt: number;
  worker_name: string;
  workload_identity: string;
  lease_hash: Sha256;
  worker_manifest_sha256: Sha256;
  runtime_sha256: Sha256;
  protocol_sha256: Sha256;
  sandbox_sha256: Sha256;
  input_manifest_hash: Sha256;
  parameters_hash: Sha256;
  handler_output_hash: Sha256;
  candidate_core_hash?: Sha256;
  resume_checkpoint_hash?: Sha256;
  checkpoints: WorkerProgressRecord[];
  execution_environment: Record<string, unknown>;
  model_artifacts: Record<string, unknown>;
  started_at: string;
  completed_at: string;
  elapsed_wall_seconds: number;
  elapsed_cpu_seconds: number;
  maximum_rss_bytes: number;
  input_byte_count: number;
  handler_output_byte_count: number;
  software_version: string;
  code_commit: string;
  container_digest: string;
  python_version: string;
  platform_profile: string;
  environment_hash: Sha256;
  shell_access_allowed: false;
  network_access_allowed: false;
  publication_permission: false;
  receipt_sha256: Sha256;
}

export interface Bounds3D {
  min: [number, number, number];
  max: [number, number, number];
}

export interface SpatialPredicate {
  operator: "within" | "intersects" | "near" | "visible_from" | "on_level";
  frame_id?: string;
  bounds?: Bounds3D;
  point?: [number, number, number];
  distance_m?: number;
  observer_entity_id?: string;
  level_id?: string;
}

export interface TemporalInterval {
  start: string;
  end: string;
}

export interface GraphTraversal {
  start_entity_ids: string[];
  relationship_types: string[];
  direction: "outbound" | "inbound" | "either";
  max_depth: number;
}

/** Public query input. Tenant/project and authorization scope are injected server-side. */
export interface SpatialQueryInput {
  schema_version: "sip.spatial-query/v1";
  full_text?: string;
  embedding?: number[];
  embedding_model_manifest_id?: string;
  entity_types: string[];
  floor_ids: string[];
  room_ids: string[];
  spatial: SpatialPredicate[];
  temporal_interval?: TemporalInterval;
  changed_between?: TemporalInterval;
  graph?: GraphTraversal;
  source_classes: SourceClass[];
  authority_classes: AuthorityClass[];
  minimum_confidence?: number;
  tags: string[];
  workflow_statuses: string[];
  evidence_ids: string[];
  scene_commit_id?: string;
  purpose?: string;
  critical_workflow: boolean;
  include_snippets: boolean;
  limit: number;
  timeout_ms: number;
}

export interface AuthorizedSpatialQuery extends SpatialQueryInput {
  tenant_id: string;
  project_id: string;
}

export interface SavedQuery {
  saved_query_id: UUID;
  tenant_id: string;
  project_id: string;
  name: string;
  schema_version: "sip.spatial-query/v1";
  version: number;
  author_id: string;
  query: AuthorizedSpatialQuery;
  permissions: Record<string, unknown>;
  parameters: Record<string, unknown>;
  expected_result_contract: Record<string, unknown>;
  query_hash: Sha256;
  supersedes_saved_query_id?: UUID;
  created_at: string;
  immutable: true;
}

export interface AgentToolSpec {
  schema_version: "sip.agent-tool/v1";
  name: string;
  description: string;
  required_permissions: string[];
  side_effect: "none" | "review_proposal";
  idempotency: "read_only" | "idempotency_key_required";
  evidence_requirements: string[];
  allowed_source_classes: SourceClass[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  authority_ceiling: "none" | "inferred" | "metric_unverified";
  prohibited_actions: string[];
}

export interface GroundedClaim {
  text: string;
  claim_type: "fact" | "inference" | "proposal" | "unknown";
  entity_ids: UUID[];
  evidence_ids: UUID[];
  confidence?: number;
  source_class?: SourceClass;
}

export interface AgentAnswer {
  schema_version: "sip.agent-answer/v1";
  claims: GroundedClaim[];
  generated_content: true;
  persistent_label: "AI-generated; verify against cited evidence";
  refused: boolean;
  refusal_code?: string;
}

export interface AgentProposal {
  proposal_id: UUID;
  state: "review_required";
  rationale: string;
  affected_resource_ids: UUID[];
  evidence_ids: UUID[];
  confidence: number;
  required_reviewer: string;
  proposed_by: string;
  authority: "inferred";
  auto_committed: false;
  publication_permission: false;
}
