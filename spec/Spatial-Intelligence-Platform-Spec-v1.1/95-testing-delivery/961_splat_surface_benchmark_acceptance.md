---
spec_id: DEL-HYBRID-BENCHMARK
title: "Splat-Surface Benchmark and Acceptance Plan"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: true
---

# Splat-Surface Benchmark and Acceptance Plan

## 1. Purpose

This plan defines how SIP evaluates splat-to-surface, metric-to-proxy, mesh-to-splat, cleanup, tiling, rendering, collision, navigation, semantic remapping, security, and production-readiness claims. A screenshot or compelling walk-through is useful evidence of appearance, but cannot replace independent geometry, authority, policy, or failure-mode tests.

Results are scoped by provider version, source type, scene class, intended use, hardware, parameters, and deployment mode. A provider may pass raycasting and fail navigation, or pass a small room and fail a multilevel building.

## 2. Test corpus

### 2.1 Synthetic canonical room

A reproducible open fixture with exact ground truth:

- two connected rooms;
- one door opening and threshold;
- stairs and a ramp;
- thin rail and pipes;
- wall-mounted panel, detector-sized object, reader-sized object, chair, and picture frame;
- reflective surface, glass-like surface, textureless wall, repeated texture, and clutter;
- removable transient person/object masks;
- privacy region;
- known camera paths and held-out views;
- exact metric mesh and semantic object IDs.

The fixture is generated from source code and produces RGB, depth, poses, LiDAR-like samples, splat input, metric mesh, design mesh, and expected navigation/collision records.

### 2.2 Construction room

A consented, noncritical mechanical/electrical or training room with independent control measurements. It includes doors, panels, equipment, labels, conduit/piping, overhead content, occlusion, and a proposed design object. Sensitive identifiers are removed or controlled.

### 2.3 LiveForever room

A consented family-like room or staged set containing furniture, photos, keepsakes, soft surfaces, reflective objects, narrow paths, and three story anchors. It includes audience-restricted content, a generated historical object, and an alternate-recollection branch.

### 2.4 Large tiled scene

A synthetic or cleared floor/building with repeated corridors, multiple rooms, stairs, tile overlap, loop paths, and intentionally incomplete capture zones. It tests memory, streaming, seam behavior, cross-tile selection, collision, and independent tile regeneration.

### 2.5 Adversarial corpus

- mirrors and glossy metal;
- glass and open doorways;
- dark and overexposed regions;
- sparse views and fast motion;
- large empty walls and repeated corridors;
- thin wires, rails, piping, vegetation, and hair-like material;
- moving people and equipment;
- scale/unit/handedness errors;
- corrupted or malicious geometry;
- disconnected floaters and false bridges;
- source-policy and consent changes during processing;
- provider crashes, retries, cancellation, and version drift.

## 3. Ground truth and reference hierarchy

Ground truth is independent from the candidate provider. Depending on fixture it includes exact synthetic geometry, surveyed control, calibrated scanner/total-station points, manually verified dimensions, annotated walkable/blocked volumes, door/threshold/stair semantics, held-out source images, and known entity anchors.

A provider's own mesh, depth, confidence, or self-reported metric cannot serve as the sole ground truth for its approval.

## 4. Benchmark profiles

| Profile | Goal | Required evidence |
|---|---|---|
| `proxy.click-selection.v1` | stable selection and entity resolution | hit accuracy, false hit/miss, remap stability, latency |
| `proxy.section-occlusion.v1` | clipping and label/depth behavior | depth disagreement, leaks, visual review, performance |
| `proxy.camera-collision.v1` | prevent camera passage through principal walls/floors | false opening/barrier, correction rate, safe fallback |
| `proxy.avatar-navigation.v1` | guided non-safety-critical locomotion | path connectivity, doors/stairs, false traversability, comfort |
| `proxy.spatial-audio.v1` | room/zone triggers and boundaries | zone precision/recall, transition stability |
| `proxy.construction-reference.v1` | construction clicking and metric snapping | role/authority, snap residual, critical object recall |
| `proxy.liveforever-guided.v1` | family room guided experience | object trigger recall, comfort, privacy behavior |
| `interop.mesh-to-splat.v1` | visual derivative of design/authored mesh | transform, held-out render, truth labels, source preservation |
| `interop.round-trip.v1` | characterize conversion loss | scale, surface, silhouette, semantics, declared irreversible loss |
| `runtime.hybrid-web.v1` | splat+mesh runtime | frame time, load, depth composition, fallbacks, accessibility |
| `large-scene.tiled.v1` | building-scale partition and streaming | seams, memory, tile latency, anchor stability, regeneration |

Thresholds live in versioned profile files and are calibrated using user impact. They are not hidden in provider code.

## 5. Geometry metrics

Metrics are computed in explicit frames and units after independent registration:

- point-to-surface and symmetric surface distance distributions;
- Chamfer-like mean/median and p90/p95/p99 distances;
- thresholded precision, recall, and F-score at multiple distances;
- completeness by visible/reference region;
- false surface area and unsupported bridge area;
- normal agreement where meaningful;
- connected-component count and principal-component retention;
- watertightness where the intended use requires it;
- self-intersections, non-manifold edges, degenerate faces, inverted normals;
- doorway/stair/rail/thin-object recall;
- scale error and transform residual;
- tile seam position/normal and gap/overlap metrics.

Metrics are reported globally and by semantic region. A low average error cannot hide a missing door or false wall.

## 6. Visual metrics

Visual evaluation uses held-out views and source-aligned cameras:

- PSNR, SSIM, LPIPS or approved equivalents;
- depth and silhouette disagreement;
- temporal/view-dependent popping;
- splat/mesh occlusion disagreement;
- color/exposure artifacts;
- privacy-mask leakage;
- expert review for emotionally or operationally important regions.

Visual metrics do not confer metric authority. A visually better candidate can be rejected for interaction if its collision or registration is worse.

## 7. Selection and anchoring tests

The test harness generates pointer rays, touch samples, controller rays, gaze samples, and spatial queries across LODs and viewpoints. It measures:

- entity hit precision/recall;
- mean and tail hit-position error;
- incorrect layer/role resolution;
- metric snap availability and residual;
- stable selected entity during tile/LOD change;
- support-map remap success after proxy regeneration;
- anchor drift and review-threshold activation;
- no verified status from a proxy-only hit.

Critical construction entities and memory objects receive separate recall minimums.

## 8. Collision tests

Collision is evaluated with actor-profile sweeps and scripted paths:

- wall/floor/ceiling penetration;
- false barriers in doorways and open space;
- false openings through walls, glass policy, or missing regions;
- step and slope behavior;
- stairs, thresholds, furniture, and low obstacles;
- camera tunneling at frame-rate extremes;
- correction jitter and comfort;
- fallback to bounded/teleport/no-navigation mode;
- invalid tile or seam transition;
- safe exit from malformed geometry.

The test result is profile-specific. It cannot be reused as accessibility, egress, robotics, or worker-safety certification.

## 9. Navigation tests

Navigation evaluation checks:

- walkable-area precision/recall against annotated reference;
- path existence where expected and nonexistence where blocked;
- connected components and isolated islands;
- door, stair, ramp, elevator, and off-mesh link semantics;
- dynamic door state handling;
- uncertain-region closure;
- path cost stability across tile/LOD changes;
- accessibility profile segregation;
- public guided-route completion and fallback.

## 10. Runtime performance

Profiles specify device class, viewport, resolution, scene size, warm/cold state, bandwidth, and concurrency. Measures include:

- time to first meaningful view;
- visual/proxy/semantic tile latency;
- steady and p95 frame time;
- memory and GPU memory;
- network bytes and cache footprint;
- draw/sort/selection cost;
- section and evidence-reveal latency;
- LOD thrash and visible seams;
- recovery after context loss or device pressure;
- battery/thermal behavior for mobile/immersive clients.

A degraded mode is tested, labeled, and bounded. It cannot silently disable truth labels or metric-snap warnings.

## 11. Provider conformance suite

Every provider adapter passes:

- capability descriptor validation;
- exact input/output hash and manifest handling;
- coordinate/unit/axis preservation;
- deterministic/seeded repeatability where claimed;
- resource-bound enforcement;
- progress and checkpoint semantics;
- cancellation, crash, resume, and cleanup;
- network and file-system restrictions;
- malformed input handling;
- output package validation;
- independent publication separation;
- license/model manifest gate;
- policy denial before data mount;
- provenance completeness.

## 12. Security and privacy tests

Tests include:

- public versus confidential versus restricted provider selection;
- denial of unapproved external transfer;
- signed URL scope and expiry;
- wrong-tenant and wrong-spatial-volume access;
- outbound minimization and metadata stripping;
- private residential and LiveForever consent purpose;
- privacy edit invalidating old proxy, collision, nav, thumbnails, and cache;
- malicious GLB/PLY/splat input in isolated parser;
- archive/path traversal, decompression, count/size overflow, NaN/Inf, shader/material abuse;
- logs and events free of raw sensitive content;
- provider approval expiry and block during an in-flight operation;
- incident withdrawal and legal-hold preservation.

## 13. Authority tests

The test suite attempts prohibited promotions:

- proxy hit saved as verified measurement;
- splat-derived watertight mesh called as-built;
- design mesh presented as observed;
- generated historical object called captured;
- collision profile reused for accessibility or egress;
- external provider self-validation used as publication approval;
- high confidence used to override source authority;
- human proxy cleanup used to create metric authority.

Every attempt must fail with a stable code and audit event.

## 14. Reproducibility and drift

For deterministic modes, identical inputs and environment must produce matching outputs or documented byte-independent geometric equivalence. For nondeterministic modes, repeated runs establish a distribution and a tolerance. Provider updates run in shadow against the current active version and compare:

- geometry/visual metrics;
- intended-use pass/fail;
- semantic remap;
- performance and cost;
- security and dependency changes;
- output determinism;
- new failure modes.

No upgrade is promoted based only on a new version number or vendor claim.

## 15. Human evaluation

Human review is structured, blinded where practical, and task-based. Construction reviewers locate entities, understand proposed versus existing state, create measurements, and identify limitations. LiveForever reviewers navigate, find stories, understand truth labels, use quiet mode, and report comfort/emotional concerns. Review evidence includes scenario, user role, build/asset hashes, device, completion/errors, and qualitative notes.

## 16. Promotion decision

| State | Required benchmark posture |
|---|---|
| `research_isolated` | conformance on public/synthetic fixtures; no customer data |
| `shadow` | current corpus executed with outputs hidden from customer workflows |
| `limited` | named profiles/scenes/projects pass and monitored rollback exists |
| `active` | all required profiles, security, license, operations, and vertical scenarios pass |
| `deprecated` | reproducible for history; removed from selection |
| `blocked` | cannot execute or access source data |

Approval records exact profile versions and exclusions. A provider can be active for splat cleanup and voxel collision while remaining research-only for surface extraction.

## 17. Release gate

The first production hybrid release requires:

- at least one approved local or project-private provider path;
- canonical asset, support-map, API, event, and view contracts;
- construction and LiveForever end-to-end acceptance demonstrations;
- proxy/metric authority enforcement;
- provider denial before source data mount;
- privacy/consent invalidation of all derivatives;
- open export/import and independent restore;
- rollback to prior published representation;
- benchmark dashboard with retained machine-readable evidence;
- security review of parsers and hybrid runtime;
- license/model/dependency manifests for every shipped component.

## 18. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| HYBTEST-001 | P0 | Provider and runtime claims shall be evaluated by versioned intended-use profiles rather than a single visual quality score. | Benchmark framework test |
| HYBTEST-002 | P0 | Ground truth shall be independent of the candidate provider and shall include exact/surveyed geometry, semantic regions, held-out views, or annotated behavior appropriate to the claim. | Dataset review |
| HYBTEST-003 | P0 | Geometry metrics shall be reported globally and by critical semantic region so averages cannot hide missing doors, stairs, devices, objects, or false walls. | Metrics test |
| HYBTEST-004 | P0 | Authority tests shall prove that proxy, visual, design, generated, and provider-self-validated outputs cannot receive prohibited status. | Negative policy test |
| HYBTEST-005 | P0 | Provider conformance shall cover policy admission, hashes, coordinates, resources, progress, cancellation, recovery, isolation, outputs, provenance, and publication separation. | Conformance suite |
| HYBTEST-006 | P0 | Security tests shall prove unapproved external-provider denial before data mount and complete derivative invalidation after privacy or consent change. | Security integration test |
| HYBTEST-007 | P0 | Construction and LiveForever acceptance scenarios shall pass with retained source, operation, validation, viewer, review, and export evidence. | Vertical E2E tests |
| HYBTEST-008 | P0 | Production release shall include at least one approved local or project-private conversion/proxy path and shall not depend solely on a public manual web tool. | Release review |
| HYBTEST-009 | P1 | Selection tests shall measure role resolution, entity precision/recall, hit error, metric snap residual, LOD stability, and remap behavior. | Automated interaction test |
| HYBTEST-010 | P1 | Collision and navigation shall be benchmarked separately for declared actor profiles and shall not imply safety, accessibility, egress, or robotics approval. | Profile benchmark |
| HYBTEST-011 | P1 | Large-scene tests shall cover tiling, seams, streaming, independent regeneration, cross-tile identity, memory, and degraded modes. | Building-scale test |
| HYBTEST-012 | P1 | Provider upgrades shall run in shadow and compare quality, behavior, performance, cost, security, license, and reproducibility against the active version. | Upgrade gate |
| HYBTEST-013 | P1 | Human evaluation shall be task-based and shall test recognition of authority/truth labels, evidence access, comfort, accessibility, and failure communication. | Controlled user study |
| HYBTEST-014 | P1 | All benchmark evidence shall be machine-readable, content-addressed, reproducible where claimed, and attached to provider and release records. | Evidence audit |
| HYBTEST-015 | P1 | Mesh-to-splat and splat-to-surface round trips shall report information loss and shall not claim representation equivalence. | Interoperability test |
| HYBTEST-016 | P1 | Malformed and adversarial spatial files shall be parsed in isolation with bounded resources and no publication side effect. | Fuzz and abuse test |

## 19. Acceptance output

Each run produces a signed benchmark package containing fixture and source hashes, provider/model/environment manifests, parameters, coordinate transforms, raw metrics, semantic-region results, screenshots/previews, logs, resource/cost records, security/policy decisions, reviewer findings, pass/fail by intended use, limitations, and promotion recommendation. The package can be independently inspected without access to a private dashboard.
