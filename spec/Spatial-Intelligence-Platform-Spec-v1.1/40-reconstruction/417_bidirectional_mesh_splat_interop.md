---
spec_id: REC-BIDIRECTIONAL-INTEROP
title: "Bidirectional Mesh-Splat Interoperability"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: reconstruction
normative: true
---

# Bidirectional Mesh-Splat Interoperability

## 1. Purpose

SIP must move information between conventional geometry and Gaussian visual representations without pretending that either conversion is lossless. This specification governs:

- splat-to-proxy-surface conversion for selection, collision, navigation, occlusion, and fallback rendering;
- metric-mesh-to-visual-splat conversion for combining BIM, proposed equipment, reconstructed objects, and authored scenes with captured splats;
- native hybrid composition where conversion is unnecessary;
- conversion provenance, coordinate preservation, uncertainty, and authority inheritance.

The canonical scene graph remains the source of entity identity and truth. File conversion creates a derivative asset, not a new authoritative observation.

## 2. Conversion classes

### 2.1 Splat to interaction surface

The operation estimates a useful surface from a view-dependent density/radiance representation. It may use Gaussian centers, opacity, covariance, normals, depth renderings, masks, density fields, metric constraints, or joint optimization. The result can be a triangle mesh, voxel structure, signed-distance representation, collision hull, or navigation-specific surface.

Expected losses include thin geometry, topology, obscured surfaces, true material boundaries, sharp corners, and regions unsupported by views.

### 2.2 Mesh to visual splat

The operation samples authored or reconstructed geometry and material appearance into a splat representation. It may preserve visible texture and render efficiently with captured splats, but it can lose exact topology, UV semantics, material graphs, parametric/BIM properties, layers, object identity, and manufacturing precision.

The canonical design mesh remains available and authoritative for design intent. Its splat derivative is presentation-only.

### 2.3 Native hybrid composition

When the viewer can render splats and meshes together, SIP should prefer preserving native forms. Conversion is justified only by a documented capability, performance, portability, or experience requirement. “One file is easier” is not sufficient reason to destroy source structure.

## 3. Authority inheritance

Conversion does not increase authority.

| Source | Derived representation | Maximum authority |
|---|---|---|
| visual splat | proxy mesh or collision volume | `derived_non_authoritative` |
| metric mesh | visual splat | `visualization_only` |
| design/BIM mesh | visual splat | `design_visualization_only` |
| verified metric mesh | simplified metric LOD | may retain metric authority only if bounded-error simplification is validated and recorded |
| unverified point cloud | mesh | no higher than source |
| AI-generated historical object | mesh or splat | `generated_interpretation` |

A provider cannot promote authority through registration, cleanup, watertight repair, photorealism, or human aesthetic approval.

## 4. Canonical transformation ledger

Every conversion writes an immutable ledger entry:

```json
{
  "conversion_id": "conv_01K1BIDIR4M8",
  "source_asset_ids": ["asset_ifc_panel_03"],
  "source_roles": ["design_mesh"],
  "target_asset_ids": ["asset_panel_splat_03"],
  "target_roles": ["visual_splat"],
  "provider_run_id": "run_01K1BIDIR4N1",
  "coordinate_frame_id": "frame_room_112",
  "transform_chain_ids": ["xf_ifc_to_building_04"],
  "authority_before": "design_authority",
  "authority_after": "design_visualization_only",
  "loss_declarations": [
    "IFC properties not encoded in visual derivative",
    "surface topology not recoverable from target alone"
  ],
  "round_trip_test_id": "rt_01K1BIDIR4PX",
  "created_at": "2026-07-27T12:00:00Z"
}
```

## 5. Mesh-to-splat uses

Permitted uses include:

- placing proposed fire-alarm panels, doors, equipment, cable routes, or furniture into a captured visual scene;
- showing historical objects reconstructed from photographs in a LiveForever environment;
- converting low-complexity proxy or design geometry into a renderer-compatible visual asset;
- rendering consistent visual previews on clients optimized for splats;
- packaging a presentation copy while preserving the source design model separately.

Prohibited uses include replacing IFC/BIM deliverables, discarding semantic properties, presenting proposed work as existing condition, using a generated visual derivative for measurement, or embedding restricted model properties in a public visual scene.

## 6. Splat-to-surface uses

Permitted and prohibited uses follow [`415_splat_surface_hybrid_representation.md`](415_splat_surface_hybrid_representation.md). When both a metric surface and splat exist, the orchestrator may use the metric surface to constrain or validate proxy extraction. It shall not warp an accepted metric surface merely to improve visual alignment without creating a separate derivative and review record.

## 7. Semantic identity preservation

Conversion files do not own persistent entity identity. The scene graph stores stable entity IDs and maps them to one or more support representations:

- world-space point, orientation, and uncertainty ellipsoid;
- semantic region or volume;
- source image observations;
- metric-surface barycentric support;
- proxy-surface support map;
- visual-splat Gaussian-set or rendered-view support;
- design-model object GUID.

When a mesh is decimated, tiled, retrained, or regenerated, a remapping job reprojects support to the new representation and records confidence. A triangle index may be cached for performance, but never be the only durable anchor.

## 8. Alignment of proposed and observed content

Design content is aligned through explicit transform chains. Each chain records source coordinate system, survey/site reference, units, axis mapping, georeferencing, operator or algorithm, control correspondences, residuals, date, and approval. The viewer shall label design content as proposed, intended, or historical even when it visually blends with the observed splat.

For construction, the default visual distinction is configurable but cannot be removed from audit/evidence mode. For LiveForever, generated or reconstructed objects retain truth labels and can be hidden by audience preference.

## 9. Round-trip validation

Round-trip tests measure information loss, not fidelity perfection:

```text
mesh A -> visual splat B -> proxy mesh C
```

Tests compare A and C for scale, registration, visible surface distance, silhouette, component preservation, semantic anchor reprojection, and intended-use behavior. Passing does not make C equivalent to A. The report lists which properties cannot round-trip, including topology, BIM attributes, material graphs, provenance, and hidden geometry.

A corresponding visual round trip:

```text
splat A -> proxy mesh B -> rendered or generated splat C
```

compares held-out views, depth, occlusion, and visual artifacts. It cannot prove factual or metric accuracy.

## 10. Packaging and interchange

Each conversion package contains:

- canonical source references, not duplicated originals unless an export policy requires it;
- target assets in open or documented formats;
- transform ledger;
- provider/model/environment manifests;
- semantic support map;
- loss and limitation declarations;
- validation report;
- preview assets;
- license and redistribution notes;
- deletion and retention dependencies.

GLB/glTF is the default portable triangle/scene derivative. PLY and relevant splat formats may be included for interchange. IFC/USD or original CAD formats remain separate authoritative design artifacts. A custom glTF extension must be accompanied by a fallback or documented open decoder path.

## 11. Versioning and Spatial Git

A conversion is a build artifact attached to a scene commit. Rebuilding it with a different algorithm creates a new asset and conversion record. Spatial Git diffs show:

- source and target role changes;
- provider/version/parameter changes;
- coordinate-transform changes;
- quality and performance changes;
- anchor remapping changes;
- authority/label changes;
- policy and redistribution changes.

Merging branches never line-merges binary splats or meshes. It selects, regenerates, or retains parallel derivatives while merging semantic scene state under explicit policy.

## 12. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| RECBIDI-001 | P0 | Mesh-splat and splat-surface conversions shall create new content-addressed derivatives and shall preserve every canonical source asset. | Asset-lineage test |
| RECBIDI-002 | P0 | A conversion shall never assign an authority class higher than the source evidence permits. | Authority-policy test |
| RECBIDI-003 | P0 | Every conversion shall record exact provider, version, model, parameters, environment, source/output hashes, coordinate transforms, and declared information losses. | Provenance-schema test |
| RECBIDI-004 | P0 | Native hybrid composition shall be preferred when it meets the declared client and experience requirements without destructive conversion. | Architecture review and scenario test |
| RECBIDI-005 | P0 | Stable semantic entity identity shall remain in the scene graph and shall survive remeshing, decimation, retraining, and tiling. | Anchor-remapping regression test |
| RECBIDI-006 | P0 | A visual derivative of design or generated content shall retain an inseparable design or generated truth label in all publishable manifests. | Viewer and export test |
| RECBIDI-007 | P0 | A conversion shall not modify an accepted metric asset to improve visual alignment without creating and reviewing a separate derivative. | Immutability test |
| RECBIDI-008 | P1 | The platform shall support round-trip comparison that reports bounded intended-use metrics and irreversible information loss. | Benchmark test |
| RECBIDI-009 | P1 | Conversion packages shall include open or documented target formats, transforms, support maps, limitations, validation, and redistribution notes. | Export/import conformance test |
| RECBIDI-010 | P1 | Spatial Git shall version conversion choices and semantic state without attempting binary line merges of meshes or splats. | Revision and merge test |
| RECBIDI-011 | P1 | Design-to-observed alignment shall record coordinate source, control correspondences, residuals, approver, and validity interval. | Alignment audit test |
| RECBIDI-012 | P1 | Client fallback behavior shall not discard or conceal authority and truth labels when a preferred representation is unsupported. | Cross-client test |
| RECBIDI-013 | P1 | Provider-specific identifiers shall be normalized behind canonical asset, frame, and semantic-support contracts. | Adapter conformance test |
| RECBIDI-014 | P1 | A target asset shall inherit applicable consent, privacy, retention, legal-hold, export, and deletion dependencies from all sources. | Policy-propagation test |

## 13. Acceptance

Acceptance requires a hybrid construction scene containing an observed splat, a verified metric reference, and a proposed BIM object rendered both natively and through a visual splat derivative. It also requires a LiveForever scene with a captured environment and a clearly labeled reconstructed object. The demonstration shall prove stable identity, coordinate alignment, source reveal, truth labels, export/import, anchor remapping after regeneration, and no authority promotion through either conversion direction.
