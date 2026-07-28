---
spec_id: SIP-MIGRATION-100-110
title: "Migration from SIP v1.0 to v1.1"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---

# Migration from SIP v1.0 to v1.1

For an operator-oriented rollout sequence, canary plan, and signoff checklist, use [`V1_1_MIGRATION_GUIDE.md`](V1_1_MIGRATION_GUIDE.md) together with this normative contract.

## 1. Purpose

SIP v1.1 adds splat-to-surface conversion, mesh-to-splat conversion, interaction proxies, collision/navigation derivatives, hybrid rendering, provider governance, and new vertical acceptance rules. This is an additive schema and architecture revision. It does not invalidate v1.0 captures, scenes, geometry, evidence, or consent records.

The migration must not infer role or authority from file names or extensions. Existing assets remain readable while they are explicitly classified and bound under the v1.1 representation model.

## 2. Main semantic change

Version 1.0 described three truth models:

1. metric scene;
2. visual scene;
3. evidence model.

Version 1.1 preserves those three truth models and adds a **disposable interaction layer**. The interaction layer is not a fourth truth source. It contains proxy meshes, collision volumes, navigation surfaces, occlusion hulls, and spatial-audio volumes optimized for runtime behavior.

The interaction layer may be regenerated or replaced without changing the source scene, semantic entity identity, evidence, or measurement authority.

## 3. Migration prerequisites

Before migration:

- verify the v1.0 package root hashes and database/object-store consistency;
- create a restorable backup and test restore;
- freeze writes or use a documented online migration boundary;
- inventory all geometry, visual, design, evidence, export, and viewer assets;
- inventory coordinate frames and missing unit/axis metadata;
- inventory existing measurements and anchors that reference mesh primitives;
- preserve the v1.0 application release for rollback;
- record the migration software/container digest and operator.

## 4. Data migration sequence

### 4.1 Add new tables and enums

Create representation assets, bindings, families, conversion operations, provider runs, intended-use validation, support maps, collision/navigation profiles, hybrid scene views, limitation/loss records, and dependency invalidation records.

Do not remove existing geometry/visual columns during the first migration phase.

### 4.2 Create asset records

For each existing binary asset:

1. verify or calculate its content hash;
2. retain its original storage object and encryption policy;
3. copy geometry metadata where trustworthy;
4. attach existing provenance and source-run references;
5. classify policy and retention dependencies;
6. create a v1.1 representation asset without assigning authority beyond the v1.0 record.

### 4.3 Assign roles conservatively

| Existing v1.0 description | Default v1.1 role | Authority ceiling |
|---|---|---|
| calibrated/verified point cloud | `metric_point_cloud` | source verification ceiling |
| TSDF or mesh with metric provenance | `metric_volume` or `metric_mesh` | source verification ceiling |
| Gaussian splat | `visual_splat` | visualization only |
| textured photogrammetry mesh without metric approval | `visual_mesh` | visualization only |
| IFC/BIM/CAD model | `design_mesh` | design intent only |
| generic GLB/OBJ with uncertain origin | `unknown_visual` quarantine role | none |
| existing collision/nav asset | interaction role only after purpose review | derived non-authoritative |
| source photo/video/document/interview | `source_evidence` | evidence-specific |

Unclear assets are not guessed. They enter a review queue with restricted uses.

### 4.4 Create scene bindings

For each scene commit, create bindings that preserve its published asset selection and time validity. Bindings declare role, authority class/ceiling, frame, transform, purpose, audience, and publication state. The legacy scene remains addressable for comparison.

### 4.5 Migrate anchors

Anchors that depend only on mesh triangle indices are vulnerable. For each:

- retain the historical primitive reference;
- derive a world-frame anchor and uncertainty when possible;
- link source observations and semantic entity;
- create reprojectable metric/visual supports;
- mark unresolved anchors for review;
- block critical measurement/entity publication when residual exceeds policy.

### 4.6 Migrate measurements

Every measurement is reviewed for method, source, uncertainty, calibration/control, verifier, and authority. A distance rendered on a visual mesh is imported as `approximate_reference` unless eligible evidence proves otherwise. Migration cannot turn a legacy viewer dimension into a verified field measurement.

### 4.7 Create fallback interaction behavior

A v1.0 scene need not have a new proxy immediately. The v1.1 runtime can use:

- an eligible existing metric mesh for picking under policy;
- a coarse local collision structure generated from approved metric/visual inputs;
- visual-only selection with approximate labels;
- bounded navigation or no locomotion.

The fallback does not change the source asset's role.

## 5. API compatibility

During the compatibility window:

- v1.0 scene endpoints remain read-only or translate to a v1.1 hybrid view with conservative defaults;
- new writes use v1.1 contracts;
- v1.0 clients cannot publish new hybrid derivatives;
- a compatibility response includes deprecation and migration status;
- no client receives more access because of translation;
- measurement and truth-label behavior follows v1.1 even for migrated v1.0 scenes.

## 6. Export compatibility

A migrated scene can be exported in the v1.0 preservation layout when no new representation is required, but v1.1 exports are preferred because they preserve explicit roles and authority. A down-level export must not strip truth labels or make a proxy look metric. Unsupported v1.1 assets are omitted with a machine-readable report, not silently substituted.

## 7. Rollback

Rollback restores the v1.0 application/database snapshot and original object store references. Because migration creates new rows/assets rather than modifying canonical binaries, rollback does not require reversing geometry. Any v1.1-only captures or scene commits created after migration must be exported and preserved before rollback or the system must remain in read-only dual-version mode.

## 8. Verification checklist

- every v1.0 asset has exactly one migration record;
- content hashes match originals;
- all explicit v1.0 authority is preserved or conservatively reduced with review, never increased;
- coordinate frames and transforms resolve or are quarantined;
- existing scene revisions render comparably within documented runtime differences;
- entity and annotation identity remains stable;
- measurements retain method and authority;
- permissions, consent, retention, legal hold, and deletion dependencies are unchanged or stricter;
- v1.0 export and v1.1 export both pass independent integrity checks;
- rollback and restore are demonstrated;
- unresolved assets/anchors are visible to operators and excluded from privileged uses.

## 9. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| SIPMIG-001 | P0 | Migration shall preserve every canonical v1.0 source asset and shall create additive v1.1 records rather than rewriting geometry bytes in place. | Hash and migration test |
| SIPMIG-002 | P0 | Role and authority assignment shall be based on provenance and verification evidence, never file extension or visual appearance. | Migration policy test |
| SIPMIG-003 | P0 | Ambiguous assets, frames, anchors, or measurements shall be quarantined or conservatively classified and shall not receive privileged intended uses. | Negative migration test |
| SIPMIG-004 | P0 | Existing permissions, classification, consent, retention, legal hold, and deletion dependencies shall remain equivalent or more restrictive after migration. | Policy-diff test |
| SIPMIG-005 | P0 | Legacy proxy-like or visual measurements shall remain approximate unless eligible metric/field evidence supports a higher status. | Measurement migration test |
| SIPMIG-006 | P0 | Entity identity and source evidence shall survive migration independently of mesh primitive IDs and renderer objects. | Anchor/entity regression test |
| SIPMIG-007 | P0 | Rollback shall be demonstrated from a restorable v1.0 backup without loss or mutation of original assets. | Recovery exercise |
| SIPMIG-008 | P1 | Compatibility APIs shall translate read behavior conservatively and shall prevent v1.0 clients from bypassing v1.1 authority or publication rules. | API compatibility test |
| SIPMIG-009 | P1 | Down-level exports shall report omitted or degraded v1.1 content and shall not relabel proxy/design/generated assets as metric or observed. | Export compatibility test |
| SIPMIG-010 | P1 | Migration shall produce a signed report of asset mappings, quarantines, unresolved anchors, policy diffs, validation results, and rollback evidence. | Audit report review |

## 10. Completion criterion

Migration is complete when every v1.0 project is either fully represented by v1.1 bindings or explicitly retained in read-only legacy mode; every unresolved item has an owner and restricted state; independent export/import and rollback pass; and no user workflow can mistake an interaction proxy, visual splat, or design mesh for verified construction truth or historical evidence.
