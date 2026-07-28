---
spec_id: REC-SURFACE-PROVIDER
title: "Splat-Surface Provider Contract"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: reconstruction
normative: true
---

# Splat-Surface Provider Contract

## 1. Purpose

This document defines the stable boundary between SIP and any implementation that derives interaction geometry, collision structures, navigation surfaces, occlusion hulls, or visual splats from another spatial representation. The contract prevents a provider's file formats, license, coordinate conventions, or confidence model from leaking into the canonical scene graph.

The provider boundary is intentionally broader than “splat to mesh.” It supports:

- visual splat to triangle or polygon proxy;
- visual splat to voxel, sparse voxel octree, occupancy field, or signed-distance proxy;
- metric mesh or point cloud to simplified interaction proxy;
- joint splat-and-surface optimization;
- authored or BIM mesh to visual splat;
- manual external conversion with controlled export and re-import;
- a no-conversion result when the native hybrid runtime can use an existing metric or design surface.

The governing representation rules are defined in [`415_splat_surface_hybrid_representation.md`](415_splat_surface_hybrid_representation.md).

## 2. Provider capability model

A provider registers a signed capability descriptor. Provider names are not business logic; orchestration selects capabilities and policy eligibility.

```yaml
provider_id: local.open3d.metric_proxy
provider_version: 1.4.2
execution_modes:
  - local_process
  - isolated_container
input_roles:
  - metric_point_cloud
  - metric_mesh
output_roles:
  - interaction_proxy
  - collision_volume
supported_formats:
  input: [ply, las, laz, obj, glb]
  output: [glb, ply, navmesh, occupancy_grid]
coordinate_contract:
  units: meters
  handedness: right
  up_axes: [y, z]
  preserves_input_frame: true
reproducibility:
  deterministic_modes: [cpu_reference]
  seedable: true
security:
  network_required: false
  writes_outside_job_workspace: false
license_manifest_id: lm-7f4d
benchmark_profile_ids:
  - proxy.click-selection.v1
  - proxy.collision-room.v1
```

Capabilities shall describe facts the provider can demonstrate, not marketing claims. The registry stores the exact executable/container digest, source revision where available, model/checkpoint hashes, transitive dependency inventory, license evidence, supported data classifications, and benchmark approvals.

## 3. Operation request

Every operation is immutable after admission. Retrying the same operation uses the same request hash and either returns the prior accepted result or creates a new attempt under the same operation identity.

```json
{
  "schema_version": "sip.spatial-conversion.request/1.1",
  "operation_id": "op_01K1HYBRID6C42JQH7ZRZ",
  "tenant_id": "tenant_example",
  "project_id": "project_example",
  "scene_revision_id": "scene_rev_0027",
  "purpose": "interaction_proxy",
  "intended_uses": ["raycast", "collision", "navigation", "occlusion"],
  "source_assets": [
    {
      "asset_id": "asset_visual_splat_01",
      "role": "visual_splat",
      "sha256": "sha256:...",
      "coordinate_frame_id": "frame_building_A"
    }
  ],
  "reference_assets": [
    {
      "asset_id": "asset_metric_mesh_01",
      "role": "metric_mesh",
      "use": "registration_and_validation",
      "sha256": "sha256:..."
    }
  ],
  "constraints": {
    "maximum_triangles": 500000,
    "maximum_bytes": 250000000,
    "preserve_components": true,
    "target_error_meters": 0.025,
    "tile_scheme_id": "tile_floor_01_v2",
    "protected_regions": ["region_panel_face", "region_stair_edges"]
  },
  "policy_context": {
    "data_classification": "confidential_building",
    "allowed_execution_zones": ["project_private_gpu"],
    "external_transfer_allowed": false,
    "retention_policy_id": "ret_7y_project",
    "legal_hold_ids": []
  },
  "provider_selector": {
    "required_capabilities": ["offline", "metric_reference_constraint", "glb_output"],
    "forbidden_capabilities": ["external_hosted"],
    "preferred_provider_ids": []
  },
  "requested_by": "principal_01",
  "idempotency_key": "01K1HYBRID6C42JQH7ZRZ"
}
```

## 4. Admission sequence

The orchestrator performs these checks before any provider can read source bytes:

1. Authenticate the calling workload and authorize the requested project and purpose.
2. Validate every asset hash and ensure the referenced scene revision is immutable.
3. Evaluate classification, consent, regional, retention, legal-hold, and external-transfer policies.
4. Resolve a provider whose code, model, weight, dataset, dependency, and commercial-use records are current.
5. Verify the provider benchmark approval covers the requested intended uses and scene class.
6. Resolve coordinate frames and reject ambiguous units, handedness, scale, or transforms.
7. Estimate resource and cost bounds and enforce project quotas.
8. Create an append-only admission decision before mounting source data.
9. Provision an isolated workspace with read-only source mounts and a write-only staging destination.
10. Issue short-lived workload credentials scoped to this operation.

A rejected request records a deterministic policy reason without exposing sensitive policy internals to an unauthorized caller.

## 5. Provider lifecycle

Providers implement the following logical lifecycle even when a specific runtime uses command-line, Python, gRPC, or batch-file adapters:

```text
inspect()        -> normalized source inventory and warnings
plan()           -> stages, resources, estimated bounds, deterministic plan hash
prepare()        -> local normalized assets and coordinate conversion manifest
execute()        -> raw candidate outputs, logs, progress, and checkpoints
validate_self()  -> provider-native metrics and limitations
finalize()       -> immutable candidate package and operation receipt
cancel()         -> bounded cancellation and cleanup
resume()         -> restart from verified checkpoint
```

`validate_self()` never publishes the result. Independent SIP validators determine whether the candidate is acceptable for the declared use.

## 6. Progress, cancellation, and recovery

A provider emits monotonically increasing stage progress rather than fabricated global percentages. Required progress fields include stage, completed work units, total work units when known, current resource use, warnings, last durable checkpoint, and estimated output footprint.

Cancellation shall:

- stop new GPU/CPU work within the provider's declared bound;
- preserve immutable inputs and accepted prior outputs;
- retain enough signed state to explain the attempt;
- securely erase transient decrypted material according to policy;
- mark incomplete output objects as quarantined, never publishable;
- allow a later restart when the algorithm supports checkpoints.

A worker crash must not create two published results for one operation. Publication is a separate transactional step after validation.

## 7. Candidate result contract

```json
{
  "schema_version": "sip.spatial-conversion.result/1.1",
  "operation_id": "op_01K1HYBRID6C42JQH7ZRZ",
  "attempt_id": "attempt_03",
  "status": "candidate_complete",
  "provider": {
    "provider_id": "local.open3d.metric_proxy",
    "provider_version": "1.4.2",
    "executable_digest": "sha256:...",
    "model_manifest_ids": [],
    "license_manifest_id": "lm-7f4d"
  },
  "inputs": [{"asset_id": "asset_visual_splat_01", "sha256": "sha256:..."}],
  "parameters_sha256": "sha256:...",
  "environment_manifest_sha256": "sha256:...",
  "outputs": [
    {
      "asset_id": "candidate_proxy_01",
      "role": "interaction_proxy",
      "media_type": "model/gltf-binary",
      "sha256": "sha256:...",
      "coordinate_frame_id": "frame_building_A",
      "authority_class": "derived_non_authoritative",
      "disposable": true
    }
  ],
  "provider_metrics": {
    "triangles": 421388,
    "vertices": 219842,
    "components": 71,
    "watertight_components": 3,
    "duration_seconds": 842.6
  },
  "limitations": [
    "thin handrails may be incomplete",
    "no measurement authority"
  ],
  "logs_asset_id": "asset_logs_01",
  "receipt_signature": "sig:..."
}
```

## 8. Coordinate and scale contract

The provider shall never silently guess scale. Every input and output declares:

- coordinate frame ID;
- units;
- axis orientation and handedness;
- transform to the operation's working frame;
- transform source and uncertainty;
- whether scale was fixed, estimated, or inherited;
- registration residuals and inlier distribution;
- any provider-local normalization and its exact inverse.

If an external tool strips coordinates, the manual adapter requires at least three non-collinear correspondences or an approved registration workflow before the output can enter a scene. A result with unresolved scale is quarantined as visualization-only and may not support collision, navigation, or measurement snapping.

## 9. Manual external provider adapter

A manual provider is never integrated by copying an output file into object storage. SIP generates an outbound package containing only approved derivatives, a conversion brief, a one-time operation ID, coordinate witnesses, prohibited-use notice, and expected output types. On return, an authorized operator records:

- tool and version;
- account and execution environment when known;
- time and operator;
- exact input and output hashes;
- options selected;
- whether data was uploaded, retained, or processed locally;
- screenshots or receipts sufficient for reproducibility review;
- cleanup performed after export;
- any manual editing.

The result remains `manual_external_unverified` until independent registration and quality checks pass. Manual providers are disabled for classifications not explicitly approved under [`913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md).

## 10. Provider promotion states

| State | Permitted use |
|---|---|
| `discovered` | metadata review only; no source data |
| `research_isolated` | synthetic or public fixtures in a segregated environment |
| `shadow` | approved consented data; output cannot affect customer scenes |
| `limited` | named projects, classifications, and intended uses under monitoring |
| `active` | normal selection within approved capability and policy envelope |
| `deprecated` | no new jobs; retained for reproducibility and rollback |
| `blocked` | execution and data access denied |

Promotion requires the benchmark and release evidence in [`961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md). A provider can be active for raycasting but blocked for collision, navigation, construction, or private family scenes.

## 11. Error taxonomy

| Code | Meaning | Required handling |
|---|---|---|
| `HYB_PROVIDER_NO_ELIGIBLE_MATCH` | No approved provider meets capability and policy constraints | Return blocked decision and remediation options |
| `HYB_SOURCE_HASH_MISMATCH` | Source bytes differ from admitted manifest | Stop before execution and raise integrity incident |
| `HYB_COORDINATE_AMBIGUOUS` | Units, handedness, frame, or inverse transform cannot be proven | Quarantine; require registration evidence |
| `HYB_LICENSE_GATE_CLOSED` | License/model/dependency approval missing or expired | Prevent source data mount |
| `HYB_POLICY_EXTERNAL_TRANSFER_DENIED` | Classification or consent blocks external processing | Select local provider or stop |
| `HYB_RESOURCE_LIMIT_EXCEEDED` | Job exceeded admitted CPU/GPU/RAM/storage/time bounds | Cancel safely and retain diagnostic manifest |
| `HYB_PROVIDER_NONDETERMINISTIC_DRIFT` | Repeat output exceeds benchmark tolerance | Quarantine provider version |
| `HYB_OUTPUT_MALFORMED` | Candidate package or media is invalid | Reject output and preserve logs |
| `HYB_OUTPUT_MISREGISTERED` | Output transform or scale fails independent checks | Quarantine candidate |
| `HYB_OUTPUT_UNFIT_FOR_USE` | Geometry passes syntax but fails intended-use tests | Retain as rejected benchmark artifact |

## 12. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| RECPROV-001 | P0 | Every provider shall register a signed capability, execution, coordinate, security, license, and benchmark descriptor before source-data access. | Registry schema and admission test |
| RECPROV-002 | P0 | Orchestration shall select providers by approved capabilities and policy envelope rather than by hard-coded product name. | Policy-selection test |
| RECPROV-003 | P0 | The immutable operation request shall identify source hashes, roles, coordinate frames, intended uses, constraints, classification, and idempotency key. | Contract test |
| RECPROV-004 | P0 | License, model, data-rights, consent, and transfer gates shall execute before provider access to decrypted source bytes. | Security and policy test |
| RECPROV-005 | P0 | Provider-native validation shall not publish an output without independent SIP registration and intended-use validation. | End-to-end publication test |
| RECPROV-006 | P0 | A provider shall not infer or discard scale, units, handedness, coordinate transforms, or authority class without an explicit machine-readable record. | Coordinate conformance test |
| RECPROV-007 | P0 | Publication shall be atomic and separate from execution so retries and worker failures cannot create competing accepted outputs. | Fault-injection and transaction test |
| RECPROV-008 | P0 | Manual external conversion shall use controlled export, return receipt, hash verification, policy review, and independent validation. | Manual-provider procedure test |
| RECPROV-009 | P1 | Providers shall expose bounded cancellation, checkpoint, cleanup, and recovery behavior in the capability descriptor. | Recovery conformance test |
| RECPROV-010 | P1 | Progress shall report objective stage work units and last durable checkpoint rather than an unsupported global percentage. | Event-contract test |
| RECPROV-011 | P1 | Provider promotion shall be scoped independently by data classification, scene class, output role, and intended use. | Promotion-policy test |
| RECPROV-012 | P1 | Deprecated provider versions shall remain addressable for reproducibility but shall receive no new production work. | Registry lifecycle test |
| RECPROV-013 | P1 | Every candidate result shall include exact input, parameter, environment, provider, model, output, metric, limitation, and receipt records. | Provenance completeness test |
| RECPROV-014 | P1 | Error responses shall use stable machine-readable codes and shall not leak restricted policy or scene information. | API and security test |
| RECPROV-015 | P1 | Resource and cost admission shall occur before execution and enforce tenant and project quotas throughout the job. | Capacity and cost test |
| RECPROV-016 | P1 | A provider upgrade shall enter shadow benchmarking and shall not replace an active version solely because it is newer. | Upgrade-promotion test |

## 13. Acceptance evidence

The provider subsystem is accepted when two independently implemented adapters—one local deterministic provider and one isolated research or manual provider—can process the same public fixture through the common request/result contract. The test shall demonstrate policy denial before data mount, retry without duplicate publication, cancellation and cleanup, coordinate registration, rejected-output quarantine, promotion scoped by intended use, and complete exportable provenance.
