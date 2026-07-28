---
spec_id: REC-SPLAT-CLEAN
title: "Splat and Surface Editing, Cleanup, and Derived LODs"
version: 1.1.0
status: "Build-ready engineering baseline — hybrid representation amendment"
last_updated: 2026-07-27
category: reconstruction
normative: true
---

# Splat and Surface Editing, Cleanup, and Derived LODs

## 1. Purpose

This module defines controlled cleanup of Gaussian splats and their derived surfaces. Cleanup improves usability and performance but must remain reproducible, attributable, reversible, and unable to rewrite source evidence.

## 2. Immutable-source rule

The canonical captured media, canonical splat checkpoint, imported native splat, metric mesh, and authored design model are immutable. Filtering, cropping, component removal, hole filling, decimation, retexturing, voxelization, and manual editing create new assets connected by derivation records.

An edited scene may become the default presentation asset, but the unedited source remains available to authorized reviewers subject to retention and consent policy.

## 3. Cleanup stages

### 3.1 Input normalization

- validate finite values and required attributes;
- preserve original units and coordinate-frame transform;
- detect unsupported spherical-harmonic bands or materials;
- compute bounds, statistics, and content hash;
- reject malformed or decompression-bomb inputs.

### 3.2 Splat cleanup

- remove or quarantine NaN/Inf records;
- filter low-opacity or low-contribution floaters under a versioned policy;
- select connected spatial clusters using recorded seeds and thresholds;
- crop by reviewed spatial volumes;
- preserve protected regions and subject masks;
- reorder for spatial locality without changing semantic identity;
- decimate with quality and appearance checks;
- generate streamed or device-specific LODs.

### 3.3 Surface cleanup

- remove unsupported disconnected components;
- orient normals and record ambiguous regions;
- detect non-manifold edges, self-intersections, zero-area faces, and duplicate vertices;
- apply hole policy by purpose rather than automatically sealing every opening;
- simplify while preserving doors, stairs, rails, panel faces, and protected semantic regions;
- split large assets into deterministic tiles with overlap and seam metadata;
- create render, collision, navigation, and occlusion derivatives independently.

### 3.4 Manual edits

Manual edits are captured as an edit journal whenever the tool supports it. Each entry records operator, time, tool/version, action, target region, before/after hashes, reason, and review. When replay is impossible, the output is classified `authored_derived`, and the receipt states that byte-for-byte reproduction is unavailable.

## 4. Protected regions

Protected regions prevent automated cleanup from deleting thin or unusual but important features. They can be created from:

- semantic entities;
- construction systems and equipment;
- doors, stairs, railings, piping, cabling, detectors, readers, panels, and labels;
- people, faces, keepsakes, handwriting, and meaningful memory objects;
- privacy masks and legal-hold regions;
- manually reviewed bounding volumes.

A protected region is not a claim that the geometry is correct. It only changes cleanup behavior.

## 5. Hole and bridge policy

For visual rendering, small holes may be patched where the patch is labeled generated. For collision, a floor may be filled conservatively to prevent falls. For construction review, doors, penetrations, access panels, and equipment clearances must not be closed merely to make a watertight model. False bridges between nearby surfaces are a critical defect.

Each derivative declares one of:

- `preserve_observed_openings`;
- `visual_fill_non_evidentiary`;
- `collision_conservative_fill`;
- `navigation_walkable_fill`;
- `manual_reviewed_fill`.

## 6. Level-of-detail families

A representation family can contain:

- source splat;
- cleaned splat;
- desktop splat LODs;
- mobile/headset streamed LODs;
- full proxy mesh;
- render proxy LODs;
- collision volume levels;
- navigation tiles;
- occlusion hulls;
- preservation fallback.

Every member has explicit parentage and cannot silently replace another role. Runtime switching preserves world transform, semantic identity, permissions, and authority labels.

## 7. Anchor preservation

Cleanup and LOD generation produce support maps that relate stable anchors to world coordinates, source geometry neighborhoods, semantic regions, and optional barycentric or splat-local coordinates. After regeneration, anchors are reattached using a confidence-ranked process and are sent for review when displacement, normal change, semantic mismatch, or occlusion exceeds thresholds.

## 8. Privacy-aware cleanup

Cleanup may remove bystanders, faces, license plates, documents, screens, family photographs, or security-sensitive equipment from a presentation derivative. Redaction masks and transformations remain auditable. A visual deletion does not delete the underlying source; source deletion follows the separate retention and subject-rights workflow.

## 9. Determinism and reproducibility

Automated cleanup uses pinned packages/containers, canonical parameter serialization, seeded randomness, bounded parallelism where needed, and content-addressed output. Nondeterministic GPU behavior is measured and given tolerances. The system distinguishes deterministic reproduction, bounded-equivalent reproduction, and non-reproducible manual editing.

## 10. Review views

Reviewers can compare:

- source versus cleaned splat;
- raw versus repaired surface;
- metric-reference distance heatmap;
- removed components and filled regions;
- protected regions;
- anchor displacement;
- triangle/splat counts and memory;
- collision and navigation overlays;
- privacy redactions;
- LOD transitions.

## 11. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| RECCLEAN-001 | P0 | Cleanup shall create derivatives and shall never overwrite canonical captures, splats, metric geometry, or design models. | Immutability test |
| RECCLEAN-002 | P0 | Every automated cleanup output shall record exact inputs, tool/container digest, parameters, seed, output hashes, and validation. | Reproducibility test |
| RECCLEAN-003 | P0 | Manual edits shall use a replayable journal or be classified as non-reproducible authored derivatives with complete receipts. | Workflow audit |
| RECCLEAN-004 | P0 | Hole filling and bridge creation shall be governed by declared purpose and shall not conceal openings relevant to construction or evidence. | Geometry and review test |
| RECCLEAN-005 | P0 | Protected semantic and privacy regions shall be honored by automated removal, decimation, and fill operations. | Adversarial cleanup test |
| RECCLEAN-006 | P0 | Generated collision, navigation, display, and occlusion products shall remain separate assets with separate quality gates. | Asset contract test |
| RECCLEAN-007 | P0 | A cleaned or decimated derivative shall retain source lineage, coordinate-frame identity, authority, and limitations. | Lineage test |
| RECCLEAN-008 | P1 | The system shall support connected-component filtering, spatial cropping, invalid-value removal, decimation, reordering, tiling, and LOD generation through provider capabilities. | Capability test |
| RECCLEAN-009 | P1 | Large scenes shall be partitioned deterministically and shall record overlap, seams, recomposition order, and tile hashes. | Building-scale test |
| RECCLEAN-010 | P1 | LOD switching shall preserve stable semantic anchors or create an explicit reattachment review task. | Anchor regression test |
| RECCLEAN-011 | P1 | Review tooling shall expose removed, filled, repaired, redacted, and manually authored regions. | Reviewer UI test |
| RECCLEAN-012 | P1 | Privacy presentation derivatives shall not be treated as fulfillment of source deletion, retention, or legal-hold obligations. | Privacy workflow test |
| RECCLEAN-013 | P1 | The system shall classify reproducibility as deterministic, bounded-equivalent, or manual/non-reproducible and expose the classification. | Provenance UI test |
| RECCLEAN-014 | P1 | Cleanup acceptance thresholds shall be profile- and purpose-specific and shall be regression tested against protected features. | Benchmark policy test |

## 12. Acceptance

The reference pipeline shall clean and tile a room-scale splat, generate visual and collision derivatives, preserve protected door/panel/memory-object regions, replay automated edits, retain a manual-edit receipt, and demonstrate stable anchors across at least three LODs.
