---
spec_id: DAT-HYBRID-ASSET
title: "Hybrid Representation Asset Contract"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: data
normative: true
---

# Hybrid Representation Asset Contract

## 1. Purpose

This document extends the geometry and visual asset model with canonical types for visual splats, metric geometry, design geometry, interaction proxies, collision volumes, navigation surfaces, occlusion hulls, semantic support maps, conversion runs, and hybrid scene views.

The contract is designed so that storage format, rendering engine, reconstruction method, and provider can change without changing what an asset means. It also makes authority, intended use, provenance, and policy machine-enforceable.

## 2. Core distinction

A **representation asset** is immutable binary or structured content. A **representation binding** assigns that asset a role in a scene revision. A **hybrid scene view** selects approved bindings for a purpose, audience, device, and point in time.

This separation allows the same GLB to be:

- a non-authoritative interaction proxy in one scene;
- a design-intent model in another;
- a bounded-error metric LOD only when an approved derivation and verification establish that authority.

File extension never determines role or authority.

## 3. Representation role vocabulary

| Role | Description | Default authority | Disposable |
|---|---|---|---:|
| `metric_point_cloud` | calibrated or registered points carrying metric uncertainty | source-dependent | no |
| `metric_volume` | TSDF, SDF, occupancy, or voxel metric field | source-dependent | no |
| `metric_mesh` | surface derived from eligible metric evidence | source-dependent | no |
| `visual_splat` | Gaussian or related point-based visual reconstruction | visualization only | no |
| `visual_mesh` | textured visual mesh not approved for measurement | visualization only | no |
| `design_mesh` | BIM/CAD/authored intended or proposed geometry | design authority only | no |
| `interaction_proxy` | selection, clipping, basic physics, and fallback surface | derived non-authoritative | yes |
| `collision_volume` | collision-specific geometry or occupancy | derived non-authoritative | yes |
| `navigation_surface` | walkable polygons, links, costs, and exclusions | derived non-authoritative | yes |
| `occlusion_hull` | hidden depth or label-occlusion geometry | derived non-authoritative | yes |
| `spatial_audio_volume` | sound boundary or trigger representation | derived non-authoritative | yes |
| `semantic_overlay` | entity, label, issue, memory, or system visualization | assertion-dependent | yes |
| `source_evidence` | image, video, drawing, interview, document, or record | evidence-specific | no |

Custom roles require a registered namespace and a declared authority ceiling. Unknown roles are not eligible for measurement, collision, navigation, publication, or export until a policy adapter handles them.

## 4. Canonical representation asset

```json
{
  "$schema": "https://schemas.sip.local/representation-asset/1.1.json",
  "asset_id": "asset_01K1ASSET9P6",
  "tenant_id": "tenant_01",
  "project_id": "project_01",
  "content": {
    "sha256": "sha256:...",
    "bytes": 238492011,
    "media_type": "model/gltf-binary",
    "format_profile": "glb-2.0-sip-proxy-1",
    "storage_object_id": "object_01K1...",
    "encryption_scope_id": "keyscope_project_01"
  },
  "geometry": {
    "coordinate_frame_id": "frame_building_A",
    "units": "m",
    "axis": {"handedness": "right", "up": "+Z", "forward": "+Y"},
    "bounds": {
      "type": "oriented_box",
      "center": [12.3, 8.1, 1.8],
      "extents": [7.2, 5.3, 2.9],
      "orientation_xyzw": [0, 0, 0, 1]
    },
    "element_counts": {
      "vertices": 219842,
      "triangles": 421388,
      "gaussians": 0,
      "voxels": 0
    }
  },
  "derivation": {
    "source_asset_ids": ["asset_visual_splat_01", "asset_metric_mesh_01"],
    "operation_id": "op_01K1HYBRID6C42JQH7ZRZ",
    "provider_run_id": "run_01K1HYBRID6D1",
    "parameter_manifest_sha256": "sha256:...",
    "environment_manifest_sha256": "sha256:..."
  },
  "quality": {
    "validation_report_id": "hybval_01",
    "intended_use_approvals": ["raycast", "collision"],
    "intended_use_rejections": ["navigation"],
    "coverage_fraction": 0.91,
    "limitations_asset_id": "asset_limitations_01"
  },
  "policy": {
    "classification": "confidential_building",
    "retention_policy_id": "ret_project_7y",
    "legal_hold_ids": [],
    "consent_policy_ids": [],
    "export_policy_id": "export_internal_only"
  },
  "created_at": "2026-07-27T12:00:00Z",
  "created_by": "workload_hybrid_worker_01"
}
```

## 5. Scene representation binding

The binding gives an asset scene meaning:

```json
{
  "binding_id": "binding_01K1BIND7E2",
  "scene_revision_id": "scene_rev_0027",
  "asset_id": "asset_01K1ASSET9P6",
  "role": "interaction_proxy",
  "purpose_tags": ["raycast", "collision"],
  "authority_class": "derived_non_authoritative",
  "authority_ceiling": "derived_non_authoritative",
  "disposable": true,
  "coordinate_frame_id": "frame_building_A",
  "transform_chain_id": "xf_identity_building_A",
  "valid_time": {"from": "2026-07-27T12:00:00Z", "to": null},
  "publication_state": "published_limited",
  "audience_policy_id": "aud_project_members",
  "supersedes_binding_id": null,
  "review_decision_id": "review_01K1..."
}
```

An asset can have multiple bindings only when each role and authority is explicitly valid. A single visual file cannot acquire metric authority because it is simultaneously bound as a proxy.

## 6. Intended-use approvals

Approval is granular. The allowed uses include:

- `display_visual`;
- `raycast`;
- `label_occlusion`;
- `section_clip`;
- `camera_collision`;
- `avatar_collision`;
- `public_navigation`;
- `spatial_audio`;
- `approximate_reference`;
- `metric_measurement`;
- `verified_measurement`;
- `change_detection`;
- `export_presentation`;
- `export_engineering`.

A role supplies defaults, but the validation record and policy decide the final approval. `interaction_proxy` can never receive `metric_measurement`, `verified_measurement`, or `export_engineering` unless the asset is separately bound under a qualifying metric role with its own derivation and evidence.

## 7. Support-map contract

A semantic support map preserves stable entity and annotation behavior across representations.

```json
{
  "support_map_id": "support_01K1MAP9Q0",
  "entity_id": "equipment_panel_FA1",
  "world_anchor": {
    "coordinate_frame_id": "frame_building_A",
    "position": [12.72, 8.24, 1.44],
    "orientation_xyzw": [0, 0, 0.71, 0.71],
    "uncertainty": {"type": "ellipsoid", "radii_m": [0.01, 0.01, 0.02]}
  },
  "supports": [
    {
      "asset_id": "asset_metric_mesh_01",
      "kind": "mesh_barycentric",
      "primitive_id": 84021,
      "barycentric": [0.21, 0.33, 0.46],
      "residual_m": 0.004,
      "durability": "reprojectable"
    },
    {
      "asset_id": "asset_proxy_01",
      "kind": "mesh_barycentric_cache",
      "primitive_id": 14604,
      "barycentric": [0.15, 0.18, 0.67],
      "residual_m": 0.017,
      "durability": "cache_only"
    },
    {
      "asset_id": "asset_visual_splat_01",
      "kind": "gaussian_region",
      "region_asset_id": "asset_mask_04",
      "confidence": 0.88
    }
  ],
  "source_observation_ids": ["frame_4401", "photo_108"],
  "last_remapped_at": "2026-07-27T13:00:00Z",
  "remap_report_id": "remap_01K1..."
}
```

Provider-local primitive IDs are caches. The world anchor, entity ID, source observations, and reprojectable supports are durable. When a derivative is superseded, the remapping service creates a new support entry and retains the prior record for audit.

## 8. Collision profile

Collision geometry includes a profile declaring the actor and risk envelope:

```yaml
collision_profile_id: collision.avatar_guided.v1
actor:
  kind: guided_avatar
  radius_m: 0.28
  height_m: 1.70
  step_height_m: 0.18
  maximum_slope_deg: 35
behavior:
  allows_soft_correction: true
  allows_teleport_fallback: true
  safety_critical: false
validation:
  maximum_false_opening_m: 0.12
  maximum_false_barrier_m: 0.08
  minimum_door_recall: 0.98
```

A collision asset approved for a first-person family experience is not automatically suitable for a wheelchair path, construction clearance, robotic navigation, or emergency egress analysis.

## 9. Navigation-surface contract

A navigation surface stores polygons or cells, off-mesh links, allowed actor profiles, slope and step limits, blocked and uncertain regions, semantic costs, generation source, and validation. Stairs, ladders, elevators, doors, thresholds, ramps, and outdoor transitions require explicit semantic handling.

An uncertain or incomplete region is closed by default for autonomous path planning. A user-facing guided experience may instead offer teleport, fade transition, or bounded manual navigation with an explanation.

## 10. Tiled representation families

A representation family groups tiles and LODs:

```json
{
  "family_id": "family_floor_01_visual_proxy",
  "role": "interaction_proxy",
  "coordinate_frame_id": "frame_building_A",
  "tile_scheme_id": "tiles_octree_v2",
  "lods": [
    {"level": 0, "maximum_screen_error_px": 12, "asset_set_id": "set_lod0"},
    {"level": 1, "maximum_screen_error_px": 5, "asset_set_id": "set_lod1"},
    {"level": 2, "maximum_screen_error_px": 2, "asset_set_id": "set_lod2"}
  ],
  "seam_validation_report_id": "seam_01",
  "fallback_asset_id": "asset_proxy_floor_coarse"
}
```

The tile scheme and world frame remain stable across LODs. Semantic supports may point to the family and be resolved to loaded tiles at runtime.

## 11. Policy inheritance and deletion graph

Every derivative inherits the most restrictive applicable policy from its sources unless a documented policy transformation lawfully reduces sensitivity. Examples:

- a proxy derived from a private home splat remains private even if it contains no texture;
- a collision volume can still reveal room layout and security-sensitive paths;
- a mesh-to-splat derivative of a proposed access-control design inherits design confidentiality;
- removing a face texture does not remove biometric or relationship sensitivity from source-linked evidence;
- an audience-specific redaction creates a separate derivative and does not change the original's policy.

Deletion planning traverses source, derivative, preview, cache, support-map, export, and publication dependencies. A legal hold can block physical deletion while requiring immediate audience withdrawal and cryptographic access revocation.

## 12. Database entities

Reference relational entities:

- `representation_asset` — immutable content and geometry metadata;
- `representation_binding` — scene role, authority, purpose, and publication;
- `representation_family` — tile/LOD organization;
- `conversion_operation` and `provider_run` — execution lineage;
- `intended_use_validation` — metrics and approval per use;
- `support_map` and `support_entry` — stable semantic anchoring;
- `collision_profile` and `navigation_profile` — actor-specific behavior;
- `loss_declaration` and `limitations_statement` — machine-readable caveats;
- `representation_dependency` — provenance, invalidation, retention, and deletion graph;
- `hybrid_scene_view` — authorized runtime selection.

Spatial indexes apply to world bounds and support anchors. Object storage remains the binary source of truth; database rows hold hashes and manifests, not multi-gigabyte payloads.

## 13. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| DATHYB-001 | P0 | SIP shall model immutable representation assets separately from scene bindings that assign role, purpose, authority, and publication state. | Schema and migration test |
| DATHYB-002 | P0 | File extension, renderer support, visual similarity, or provider name shall never determine an asset's role or authority. | Policy test |
| DATHYB-003 | P0 | Every binding shall declare coordinate frame, transform, role, authority class, authority ceiling, intended uses, review decision, and audience policy. | Contract test |
| DATHYB-004 | P0 | An interaction, collision, navigation, occlusion, or audio derivative shall default to `derived_non_authoritative` and `disposable=true`. | Defaulting and rejection test |
| DATHYB-005 | P0 | Intended-use approval shall be granular and shall prevent proxy assets from satisfying metric or verified-measurement policy by role alone. | Authorization test |
| DATHYB-006 | P0 | Semantic identity shall use stable entity and world-frame references with reprojectable support; provider-local primitive IDs shall be cache-only. | Remeshing regression test |
| DATHYB-007 | P0 | Every derivative shall inherit applicable classification, consent, retention, legal-hold, export, and deletion dependencies from all source assets. | Policy graph test |
| DATHYB-008 | P0 | Collision and navigation assets shall declare an actor/profile and shall not be reused for unapproved safety or accessibility purposes. | Profile-enforcement test |
| DATHYB-009 | P1 | Representation families shall support tiled and LOD assets with stable frames, seam validation, fallback assets, and runtime selection metadata. | Large-scene schema test |
| DATHYB-010 | P1 | A support-map remap shall report residual, confidence, failed anchors, and review thresholds while retaining historical supports. | Remap test |
| DATHYB-011 | P1 | A visual or interaction derivative shall include machine-readable limitations and irreversible-loss declarations. | Export and UI test |
| DATHYB-012 | P1 | The dependency graph shall support selective invalidation and regeneration after privacy, cleanup, transform, provider, or source changes. | Invalidation test |
| DATHYB-013 | P1 | Unknown representation roles or profiles shall be denied privileged uses until a registered policy adapter handles them. | Forward-compatibility test |
| DATHYB-014 | P1 | Hybrid scene views shall reference approved bindings rather than raw storage objects. | API security test |
| DATHYB-015 | P1 | Database and export contracts shall preserve source hashes, coordinate transforms, authority ceilings, intended-use decisions, and policy dependencies. | Round-trip test |
| DATHYB-016 | P1 | Asset deprecation shall not erase historical scene commits or prevent independent reproduction when retention policy permits. | Spatial Git test |

## 14. Migration from v1.0

Existing v1.0 geometry assets are not automatically reclassified. A migration operation assigns an explicit role and authority ceiling, verifies coordinate metadata, links source lineage, sets policy dependencies, and records a review decision. When evidence is insufficient, the asset is imported as `visual_mesh` or `unknown_visual` with no measurement privileges.

## 15. Acceptance

The schema is accepted when one metric mesh, visual splat, design mesh, interaction proxy, collision volume, and navigation surface can be bound to a scene revision; selected through an authorized hybrid view; exported and re-imported without authority loss; remapped after proxy regeneration; invalidated after a privacy edit; and independently queried for provenance, intended use, limitations, and policy dependencies.
