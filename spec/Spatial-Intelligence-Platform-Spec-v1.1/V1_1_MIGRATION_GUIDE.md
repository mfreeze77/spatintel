---
spec_id: SIP-MIGRATION-GUIDE-110
title: "SIP v1.1 Hybrid Representation Migration Operator Guide"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: false
---

# SIP v1.1 Hybrid Representation Migration Operator Guide

## 1. Purpose

This guide turns the normative migration contract in [`MIGRATION_FROM_1.0.md`](MIGRATION_FROM_1.0.md) into an executable operator sequence. It is intended for the engineering lead, data migration owner, security reviewer, product owner, and release manager responsible for introducing the SIP v1.1 hybrid-representation model into an existing v1.0 deployment.

The guide does not replace the normative specification. Where this guide and a normative module differ, the normative module controls. The principal normative references are:

- [`MIGRATION_FROM_1.0.md`](MIGRATION_FROM_1.0.md)
- [`40-reconstruction/415_splat_surface_hybrid_representation.md`](40-reconstruction/415_splat_surface_hybrid_representation.md)
- [`40-reconstruction/416_splat_surface_provider_contract.md`](40-reconstruction/416_splat_surface_provider_contract.md)
- [`50-data/514_hybrid_representation_asset_contract.md`](50-data/514_hybrid_representation_asset_contract.md)
- [`60-platform/613_hybrid_scene_runtime.md`](60-platform/613_hybrid_scene_runtime.md)
- [`90-security-ops/913_external_spatial_provider_governance.md`](90-security-ops/913_external_spatial_provider_governance.md)
- [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](95-testing-delivery/961_splat_surface_benchmark_acceptance.md)

## 2. Migration outcome

At completion, the deployment must be able to represent one place using several independently governed assets in a common coordinate system:

1. metric geometry for calibrated spatial reference and eligible measurements;
2. visual geometry or Gaussian splats for appearance;
3. interaction proxies for raycasting, collision, navigation, clipping, occlusion, and spatial audio;
4. evidence records for provenance, consent, assertions, review, and authority;
5. design geometry for BIM/CAD intent where applicable.

The migration must not reinterpret a visually convincing model as a verified as-built condition. It must not make a proxy mesh authoritative merely because it is polygonal. It must not transfer authority from a source asset to a derivative without the required validation and review.

## 3. Roles and approvals

Assign named owners before the first production change:

| Role | Minimum responsibility |
|---|---|
| Migration owner | coordinates sequence, evidence, rollback, and signoff |
| Data model owner | schema, backfill, compatibility views, and integrity checks |
| Reconstruction owner | provider adapters, coordinate frames, support maps, and quality results |
| Viewer/runtime owner | hybrid loading, selection, fallback behavior, and performance |
| Construction product owner | measurement and as-built authority safeguards |
| LiveForever product owner | historical truth, consent, protected-object, and immersive-safety safeguards |
| Security/privacy owner | data classification, provider approval, retention, and egress policy |
| Release owner | gates, canary progression, rollback decision, and production declaration |

No single operator should approve both an external provider exception and the production release that relies on that exception.

## 4. Pre-migration inventory

Create a machine-readable inventory before changing the schema. The inventory should include:

- every scene and revision;
- every asset hash, format, byte size, encryption scope, retention class, and storage location;
- coordinate-frame identifier, units, handedness, axis convention, transform lineage, and georeferencing status;
- source captures and reconstruction runs;
- point clouds, meshes, splats, BIM/CAD models, collision meshes, navigation assets, exports, and cached viewer derivatives;
- annotations, measurements, equipment entities, memory entities, and anchors;
- primitive-index references such as triangle, vertex, voxel, surfel, or Gaussian identifiers;
- model/checkpoint/provider manifests;
- consent, audience, legal-hold, and deletion dependencies;
- client and viewer versions that read the current data;
- active jobs, unpublished drafts, and temporary objects.

Produce counts and content hashes before and after migration. Store the inventory as an immutable release artifact.

## 5. Backup and rollback rehearsal

A backup is not considered sufficient until it has been restored into an isolated environment and used to open representative v1.0 scenes. The rehearsal must verify:

- database point-in-time recovery;
- object-store version recovery;
- encryption-key availability under emergency procedure;
- v1.0 application deployment availability;
- reconstruction manifests and source captures;
- consent and policy records;
- ability to disable v1.1 writes while retaining v1.0 read access.

Record the restoration duration, missing dependencies, operator steps, and hashes of restored artifacts. A failed rehearsal blocks migration.

## 6. Schema rollout strategy

Use an expand–migrate–validate–contract sequence.

### 6.1 Expand

Add the v1.1 structures without removing v1.0 fields. Introduce:

- representation assets and representation families;
- scene bindings and hybrid scene views;
- explicit roles and authority classes;
- conversion operations and provider runs;
- intended-use approvals;
- support maps and anchor reprojection records;
- collision, navigation, occlusion, and spatial-audio derivatives;
- limitation, loss, uncertainty, and validation records;
- dependency and invalidation edges;
- publication and quarantine states.

All new fields that affect truth, authority, frame, or provenance must fail closed. An absent value may not be replaced with an optimistic default.

### 6.2 Dual read

Deploy readers that understand both v1.0 and v1.1. During this stage:

- v1.0 assets are translated into conservative v1.1 views;
- unknown assets remain quarantined or visual-only;
- no client receives broader access than before;
- no legacy measurement gains authority;
- v1.1 viewers expose source and limitation labels.

### 6.3 Dual write or controlled freeze

Choose one documented strategy:

- briefly freeze writes while migrating all mutable records; or
- dual-write v1.0 compatibility fields and v1.1 records until cutover.

Dual writing requires reconciliation metrics, idempotency keys, and a procedure for resolving partial writes. A write freeze requires a communicated maintenance boundary and a verified queue for deferred field uploads.

### 6.4 Backfill

Create v1.1 records from existing assets. Backfill must be deterministic and restartable. Each operation records:

- source record identifier and source hash;
- migration software/container digest;
- assigned role and authority ceiling;
- coordinate frame and transform decision;
- operator or automated policy identity;
- warnings and unresolved questions;
- created record identifiers;
- start, completion, and retry information.

### 6.5 Validate

Compare pre- and post-migration inventories. Validate database constraints, object hashes, referential integrity, access decisions, scene rendering, anchors, measurements, and exports. Do not contract the old schema until all blocking discrepancies are resolved.

### 6.6 Contract

Remove or stop writing legacy fields only after the compatibility window and rollback threshold have passed. Preserve read-only historical representations where required for audit or legal hold.

## 7. Conservative role classification

Use explicit evidence rather than file extension. A `.glb` may be a design model, visual mesh, proxy mesh, or export container. A `.ply` may contain a calibrated point cloud or a visual-only derivative. Classify each asset using provenance and intended use.

Recommended migration defaults:

| Existing asset | v1.1 default | Initial publication posture |
|---|---|---|
| Calibrated point cloud with traceable control | `metric_point_cloud` | eligible only up to its prior verification ceiling |
| TSDF/mesh derived from calibrated depth | `metric_volume` or `metric_mesh` | conditional on preserved uncertainty and validation |
| Gaussian splat | `visual_splat` | visual use only |
| Photogrammetry mesh without metric approval | `visual_mesh` | visual use only |
| IFC/BIM/CAD source | `design_mesh` | design intent only |
| Existing runtime collision geometry | interaction role | quarantine until source and purpose review |
| Unknown OBJ/GLB/PLY | `unknown_visual` | quarantine |
| Source media/document/interview | evidence role | existing policy and consent remain controlling |

A bulk classifier may propose roles, but a policy engine and reviewer must approve assets that affect measurements, construction truth, historical claims, identity, or sensitive navigation.

## 8. Coordinate-frame migration

Every published representation requires a named coordinate frame and transform lineage. For each migrated asset:

1. identify its native frame, units, axes, and handedness;
2. verify the transform into the scene frame;
3. preserve the original transform and calibration evidence;
4. calculate alignment residuals where correspondence exists;
5. record uncertainty and validity region;
6. reject or quarantine ambiguous transforms;
7. test round-trip serialization and viewer placement.

A visual alignment that appears correct is insufficient for metric publication. Construction assets require quantitative residual checks appropriate to the declared use. LiveForever assets may accept looser visual registration, but the uncertainty must remain visible to editors and must not support fabricated historical precision.

## 9. Anchor and identity migration

Primitive identifiers are unstable across remeshing, splat pruning, decimation, tiling, and provider changes. Migrate anchors toward stable semantic identity and world-space support.

For each anchor:

- preserve the historical primitive reference as evidence;
- derive or verify world position and orientation;
- associate a semantic entity where possible;
- attach source observations;
- calculate support against metric, visual, interaction, and design representations;
- store residual, confidence, and validity region;
- identify a fallback representation;
- flag unresolved or drifting anchors for review.

Critical construction equipment, life-safety devices, access-control components, memorial objects, faces, photographs, letters, and story activation points require protected-object tests. They must not disappear because a proxy was simplified.

## 10. Measurement migration

Measurements require method-specific review. The migration must preserve:

- source observations;
- calibration and control information;
- measurement method;
- units and uncertainty;
- responsible person or process;
- verification state;
- authority class;
- scene revision and validity interval.

Measurements that were made against an unverified visual mesh or splat-derived surface become `approximate_reference` unless independent evidence supports a stronger class. The viewer may use a proxy for the click interaction, but the measurement service must resolve the endpoints against eligible metric geometry or request field verification.

## 11. Provider onboarding sequence

Onboard each splat-to-surface or mesh-to-splat provider independently:

1. register provider identity and exact version;
2. document source, code license, model/weight license, dataset provenance, transitive dependencies, and commercial restrictions;
3. define supported inputs, outputs, coordinate behavior, and determinism;
4. classify execution as local, private managed, external API, manual external, or research shadow;
5. define data classes permitted to leave the trust boundary;
6. run synthetic and public-data fixtures;
7. record quality, performance, failure, and security results;
8. keep outputs quarantined until policy and quality gates pass;
9. publish only through the common asset contract;
10. establish expiration and re-review triggers.

SplatEdit remains a manual experimental provider under v1.1. Do not send private residences, customer construction data, restricted infrastructure, biometric imagery, or confidential LiveForever material to it without a later explicit approval record.

## 12. Hybrid runtime rollout

Release the viewer/runtime in stages:

### Stage A — visual coexistence

Render a splat and conventional meshes in one scene using registered coordinate frames. Validate depth behavior, clipping, camera controls, and access policy.

### Stage B — selection

Enable raycasting against an interaction proxy or eligible fallback. Display the representation used for selection and reproject hits to stable semantic anchors.

### Stage C — collision and navigation

Enable bounded collision and navigation only after detecting holes, floating components, invalid floors, blocked doorways, and unstable stairs. Provide teleport, reset, and safe-exit controls.

### Stage D — occlusion and spatial audio

Add occlusion hulls and audio zones with visible editor diagnostics and fallbacks. Do not allow a proxy defect to trap the user or hide required safety information.

### Stage E — immersive mode

Enable VR/AR only after frame-time, locomotion, accessibility, consent, and content-safety gates pass. LiveForever experiences must support quiet mode, pause, exit, and audience restrictions.

## 13. Construction pilot

Use a bounded, noncritical pilot such as one mechanical/electrical room and adjacent corridor. Include:

- a metric source from ARKit/LiDAR or better;
- a visual splat;
- a derived interaction proxy;
- several protected thin/small devices;
- one design/BIM object;
- semantic equipment records;
- one approximate measurement and one field-verified measurement;
- one annotation, issue, drawing reference, and change event.

Acceptance must prove that:

- the proxy improves selection/navigation;
- proxy-derived clicks cannot create verified measurements without eligible metric evidence;
- the source and authority label is visible;
- sensitive-system policy is enforced;
- proxy regeneration preserves entity anchors;
- visual/proxy failure falls back without losing the project record.

## 14. LiveForever pilot

Use a consented room with a small set of stories and objects. Include:

- a visual splat or visual mesh;
- a safe interaction proxy;
- interview evidence;
- photographs or documents;
- one disputed or alternate recollection;
- protected memory objects;
- private and family audience views;
- one regenerated proxy version.

Acceptance must prove that:

- historical claims remain tied to evidence rather than proxy geometry;
- uncertain reconstruction is labeled;
- alternate recollections remain separate;
- story/object anchors survive proxy replacement;
- consent and audience rules apply to every representation;
- locomotion and exit controls are safe and accessible;
- a preservation fallback remains usable without the interactive proxy.

## 15. Observability and reconciliation

Monitor at least:

- migration records attempted, completed, retried, quarantined, and failed;
- assets by role, authority class, and missing metadata;
- unresolved coordinate frames;
- anchor reprojection residuals and failures;
- measurements downgraded or blocked;
- provider runs by data class and approval state;
- output validation failures;
- viewer fallback rate;
- collision/navigation safety failures;
- policy denials and unexpected egress attempts;
- orphaned storage objects and dangling references;
- v1.0 compatibility reads after cutover.

Reconciliation should be repeatable and produce signed or content-addressed evidence suitable for the release record.

## 16. Canary progression

Use progressive exposure:

1. local developer fixtures;
2. automated benchmark corpus;
3. internal public/synthetic scenes;
4. one non-sensitive internal pilot;
5. one consented LiveForever pilot and one bounded construction pilot;
6. limited customer canary with rollback enabled;
7. broader production after release review.

Stop progression when any P0 requirement fails, an authority label is incorrect, a policy boundary is crossed, an anchor materially drifts, a verified measurement changes unexpectedly, or the rollback path is no longer demonstrably available.

## 17. Rollback triggers

Rollback or disable v1.1 writes when:

- source assets or provenance cannot be reconciled;
- roles or authority classes are misassigned;
- access or consent becomes broader than v1.0;
- viewer selection presents proxy geometry as metric truth;
- measurements are promoted incorrectly;
- provider data leaves an approved boundary;
- coordinate transforms produce material scene displacement;
- critical construction or memory anchors are lost;
- repeated runtime crashes prevent safe access;
- migration cannot resume idempotently;
- backup restoration is unavailable.

A rollback may disable hybrid derivatives while preserving valid v1.1 metadata. Never delete source captures or evidence merely to return the application to v1.0 behavior.

## 18. Production signoff packet

The release packet should contain:

- approved migration plan and owner list;
- pre- and post-migration inventories;
- backup and restore rehearsal evidence;
- schema and compatibility test results;
- asset-role classification report;
- coordinate-frame and anchor residual report;
- measurement migration report;
- provider approval records and dependency manifests;
- construction and LiveForever pilot results;
- security, privacy, consent, and egress test results;
- performance and runtime fallback results;
- unresolved risks and accepted waivers;
- release, canary, and rollback records;
- hashes for code, containers, models, configuration, and specification version.

## 19. Completion checklist

The migration is complete only when all of the following are true:

- v1.0 source assets and evidence remain intact and addressable;
- v1.1 representation roles and authority classes are explicit;
- coordinate frames and transforms are traceable;
- hybrid scene bindings are revisioned;
- interaction proxies are marked derived and non-authoritative;
- stable anchors survive proxy regeneration within accepted residuals;
- measurements retain or reduce authority according to evidence and never gain authority by migration alone;
- external-provider policy is enforced before data access;
- construction and LiveForever pilots pass their respective gates;
- compatible export and preservation fallbacks work;
- observability and reconciliation show no blocking discrepancy;
- rollback remains tested through the end of the canary period;
- the release owner records a final production decision.

## 20. Recommended reading order for implementers

1. Read [`V1_1_HYBRID_REPRESENTATION_CHANGESET.md`](V1_1_HYBRID_REPRESENTATION_CHANGESET.md).
2. Apply the normative contract in [`MIGRATION_FROM_1.0.md`](MIGRATION_FROM_1.0.md).
3. Implement the asset schema in [`50-data/514_hybrid_representation_asset_contract.md`](50-data/514_hybrid_representation_asset_contract.md).
4. Implement the provider boundary in [`40-reconstruction/416_splat_surface_provider_contract.md`](40-reconstruction/416_splat_surface_provider_contract.md).
5. Implement runtime behavior in [`60-platform/613_hybrid_scene_runtime.md`](60-platform/613_hybrid_scene_runtime.md).
6. Enforce external-provider policy in [`90-security-ops/913_external_spatial_provider_governance.md`](90-security-ops/913_external_spatial_provider_governance.md).
7. Run the benchmark and acceptance program in [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](95-testing-delivery/961_splat_surface_benchmark_acceptance.md).
8. Execute the sequenced epics in [`95-testing-delivery/958_epic_backlog.md`](95-testing-delivery/958_epic_backlog.md).
