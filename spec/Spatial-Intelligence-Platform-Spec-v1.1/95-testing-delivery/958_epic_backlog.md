---
spec_id: DEL-BACK
title: "Sequenced Epic Backlog"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: true
---

# Sequenced Epic Backlog

This backlog is ordered by dependency and risk retirement. Each task must also satisfy the cross-cutting Definition of Done. `Physical` means iPhone/field hardware is required; `GPU` means approved GPU access is required; `Legal` means license/terms review is a hard dependency; `Consent` means data cannot be acquired or used without documented participant permission.

## FND-001 — Monorepo and toolchain foundation

**Dependencies:** None  
**Special inputs:** Physical

### Tasks

- [ ] FND-001-01: Create repository layout, code owners, protected branches, commit/release conventions, and ADR directory.
- [ ] FND-001-02: Pin Swift/Xcode, Python, Node/pnpm, Docker, database, and infrastructure toolchains.
- [ ] FND-001-03: Add formatting, linting, type checking, unit tests, schema lint, secret scan, dependency scan, and signed CI artifacts.
- [ ] FND-001-04: Create synthetic small-room fixtures and a zero-customer-data developer seed.
- [ ] FND-001-05: Implement spec/requirements link validation and generated-code drift checks.
- [ ] FND-001-06: Produce initial SBOM and third-party manifest lock.

### Acceptance

A clean developer machine can run checks, ingest a synthetic fixture, and build signed artifacts without private data or checkpoints.
## GOV-001 — License, model, and dataset gate

**Dependencies:** FND-001  
**Special inputs:** GPU, Legal, Consent

### Tasks

- [ ] GOV-001-01: Implement dependency/model/dataset manifest schemas and approval state machine.
- [ ] GOV-001-02: Add CI gate for missing, expired, research-only, prohibited, or revoked artifacts.
- [ ] GOV-001-03: Mirror approved model assets by hash and block runtime downloads.
- [ ] GOV-001-04: Document LingBot checkpoint HOLD and create evidence request checklist.
- [ ] GOV-001-05: Add SBOM/license notices to release artifacts and worker images.
- [ ] GOV-001-06: Create dataset consent/license manifests and withdrawal procedure.

### Acceptance

A production job using an unapproved checkpoint is rejected before data access; an approved synthetic model fixture succeeds.
## GOV-002 — External spatial provider and derivative-governance gate

**Dependencies:** GOV-001  
**Special inputs:** Legal, Consent

### Tasks

- [ ] GOV-002-01: Implement provider/version approval schema for code, models, hosted terms, output rights, processing locality, retention, security, data classes, purposes, regions, deployments, and expiration.
- [ ] GOV-002-02: Implement provider classes `local_open_source`, `private_managed`, `external_api`, `manual_external`, and `research_shadow` with fail-closed admission.
- [ ] GOV-002-03: Implement purpose-limited manual export/import receipt, expiry, hash, operator, destination, deletion attestation, and quarantine workflow.
- [ ] GOV-002-04: Add SplatEdit as a disabled-by-default public/synthetic manual fixture and prove confidential/private data denial.
- [ ] GOV-002-05: Implement provider terms/license/security change monitoring, revocation, in-flight quarantine, and impact reporting.
- [ ] GOV-002-06: Add data-minimization/redaction profiles for external spatial processing.

### Acceptance

A synthetic scene can use the manual fixture; a confidential mechanical room and private family scene are denied before export; provider revocation blocks new work and reports every affected derivative without exposing raw scene data.
## FND-002 — Local reference environment

**Dependencies:** FND-001  
**Special inputs:** GPU

### Tasks

- [ ] FND-002-01: Create Docker Compose for PostgreSQL/PostGIS, object storage, queue/cache, API, workflow, and web.
- [ ] FND-002-02: Provide GPU-optional mock workers and one real GPU profile.
- [ ] FND-002-03: Add health/readiness, migrations, seed data, and one-command reset.
- [ ] FND-002-04: Document local-only network mode and disable external egress in tests.
- [ ] FND-002-05: Add local TLS/development identity or clearly isolated dev-only behavior.

### Acceptance

The complete control plane and mock pipeline run offline; the GPU profile can be enabled without changing contracts.
## DATA-001 — Content-addressed asset service

**Dependencies:** FND-002  
**Special inputs:** Physical, Legal

### Tasks

- [ ] DATA-001-01: Implement asset manifest, SHA-256 identity, multipart/chunk upload, verification, and dedup-safe tenant references.
- [ ] DATA-001-02: Implement encrypted storage metadata, classification, retention, and legal-hold fields.
- [ ] DATA-001-03: Create signed upload/download authorization with narrow scope and expiry.
- [ ] DATA-001-04: Add corruption detection, quarantine, restore hooks, and audit events.
- [ ] DATA-001-05: Build fixture uploader and hash-mismatch/adversarial tests.

### Acceptance

Large fixture uploads resume, verify, deduplicate logically, and cannot be accessed by another tenant or stale signed URL.
## DATA-002 — Transactional and spatial schema

**Dependencies:** FND-002  
**Special inputs:** Physical

### Tasks

- [ ] DATA-002-01: Implement tenant, user, project, place, capture, asset, operation, audit, and policy tables.
- [ ] DATA-002-02: Add PostGIS frame-aware spatial indexes and prohibit mixed-frame queries without transforms.
- [ ] DATA-002-03: Implement outbox, optimistic concurrency, immutable creation fields, and revision state.
- [ ] DATA-002-04: Add forward/upgrade/recovery migration rehearsals with production-scale generated data.
- [ ] DATA-002-05: Create database ownership and row-level/tenant policy tests.

### Acceptance

Core resources transact correctly under concurrency; migration and restore tests preserve IDs, hashes, and tenant isolation.
## IAM-001 — Identity, tenant, project, and policy engine

**Dependencies:** DATA-002  
**Special inputs:** Consent

### Tasks

- [ ] IAM-001-01: Integrate OIDC/SSO-ready identity and service workload identities.
- [ ] IAM-001-02: Implement tenant/project roles, resource classifications, purposes, spatial restrictions, and consent hooks.
- [ ] IAM-001-03: Separate view, download/export, modify, review, and administrative privileges.
- [ ] IAM-001-04: Create short-lived share presentation tokens with revocation and audit.
- [ ] IAM-001-05: Add cross-tenant, count, search, cache, and object-reference leakage tests.

### Acceptance

Policy tests prove restricted entities and assets are undiscoverable through all current APIs and signed URLs.
## CAP-001 — Canonical Spatial Capture Package schema and validator

**Dependencies:** DATA-001, DATA-002  
**Special inputs:** Physical

### Tasks

- [ ] CAP-001-01: Define versioned root, asset, frame, sensor, mesh, event, policy, and signature schemas.
- [ ] CAP-001-02: Implement deterministic canonical serialization and root hash calculation.
- [ ] CAP-001-03: Implement streaming validator with decompression and resource limits.
- [ ] CAP-001-04: Create valid, partial, corrupt, malicious, previous-minor, and unknown-extension fixtures.
- [ ] CAP-001-05: Generate Swift/Python/TypeScript types and compatibility tests.
- [ ] CAP-001-06: Build CLI inspect/validate/repair-report tools without modifying sources.

### Acceptance

Identical logical packages hash identically; corrupt/malicious inputs fail safely; compatible unknown fields round-trip.
## CAP-002 — Polycam raw-export adapter

**Dependencies:** CAP-001  
**Special inputs:** Legal

### Tasks

- [ ] CAP-002-01: Pin and review the polyform format/tooling revision and license notices.
- [ ] CAP-002-02: Map raw GLB/video/images/cameras/depth/confidence/corrected variants into CSCP.
- [ ] CAP-002-03: Implement source coordinate-frame record and transform conformance tests.
- [ ] CAP-002-04: Detect optimized versus ARKit-only pose streams without guessing.
- [ ] CAP-002-05: Generate conversion report and retain native archive hash.
- [ ] CAP-002-06: Test small, large, missing-depth, malformed, partial, and future-extra-file exports.

### Acceptance

Representative Polycam captures normalize reproducibly, preserving native/optimized distinctions and source assets.
## CAP-003 — iOS capture state machine and durable journal

**Dependencies:** CAP-001, IAM-001  
**Special inputs:** Physical

### Tasks

- [ ] CAP-003-01: Create Swift modules and persisted state machine for setup through finalization/upload.
- [ ] CAP-003-02: Implement append-only journal, asset finalization, crash recovery, and partial export.
- [ ] CAP-003-03: Add project/profile/policy bootstrap and local encryption.
- [ ] CAP-003-04: Handle backgrounding, interruption, termination, low storage, and device restart.
- [ ] CAP-003-05: Build simulator/unit tests and device chaos test harness.
- [ ] CAP-003-06: Implement local package inspector and safe purge after verified receipt.

### Acceptance

A device capture survives forced termination at randomized points with no accepted-frame loss or corrupt final package.
## CAP-004 — Synchronized ARKit/RGB/LiDAR/IMU acquisition

**Dependencies:** CAP-003  
**Special inputs:** Physical

### Tasks

- [ ] CAP-004-01: Capture ARFrame image references, depth/confidence, camera transforms, intrinsics, tracking, exposure, and mesh-anchor operations.
- [ ] CAP-004-02: Capture CoreMotion streams and clock mappings with dropped-sample records.
- [ ] CAP-004-03: Implement bounded queues, backpressure, asset encoding, and performance telemetry.
- [ ] CAP-004-04: Persist coordinate conventions and camera calibration identity.
- [ ] CAP-004-05: Create synthetic/conformance tests for axes, intrinsics, timestamps, and depth invalids.
- [ ] CAP-004-06: Run supported-device thermal, memory, battery, and long-session tests.

### Acceptance

Physical-device packages preserve synchronized interpretable streams and stay within declared capture performance budgets.
## CAP-005 — Live quality, coverage, calibration, and privacy guidance

**Dependencies:** CAP-004  
**Special inputs:** Physical

### Tasks

- [ ] CAP-005-01: Implement blur, exposure, motion, tracking, depth-validity, distance, and viewpoint-diversity signals.
- [ ] CAP-005-02: Implement segment coverage map and recapture recommendations.
- [ ] CAP-005-03: Add calibration-check and known-scale/fiducial workflows.
- [ ] CAP-005-04: Add manual restricted object/region/spatial volume marks and automatic review suggestions.
- [ ] CAP-005-05: Version thresholds by profile/device and record operator overrides.
- [ ] CAP-005-06: Run field usability tests for construction and memory capture paths.

### Acceptance

Operators can correct common failures during capture and finalization accurately reports weak/unobserved/restricted regions.
## CAP-006 — Resumable transfer and server ingest

**Dependencies:** CAP-003, DATA-001  
**Special inputs:** None

### Tasks

- [ ] CAP-006-01: Implement content/chunk manifest authorization, parallel upload, retry, pause, resume, and network-change behavior.
- [ ] CAP-006-02: Verify server asset hashes and package root before acceptance.
- [ ] CAP-006-03: Emit ingest events and reconcile orphan/duplicate uploads safely.
- [ ] CAP-006-04: Support Files/local-network/cable-style export for local-only environments.
- [ ] CAP-006-05: Add bandwidth, background, offline, expired-token, and interrupted-upload tests.

### Acceptance

A multi-gigabyte package resumes after device/network restarts and is not purge-eligible until server/root verification succeeds.
## PLT-001 — Control API, operations, events, and durable workflows

**Dependencies:** DATA-001, DATA-002, IAM-001  
**Special inputs:** Legal

### Tasks

- [ ] PLT-001-01: Implement REST resource patterns, idempotency, optimistic concurrency, pagination, and stable errors.
- [ ] PLT-001-02: Implement operation/job resources, workflow state, activity leases, cancellation, retries, and review waits.
- [ ] PLT-001-03: Implement transactional outbox and versioned event catalog/registry.
- [ ] PLT-001-04: Implement worker capability/lease/progress/checkpoint/result protocol.
- [ ] PLT-001-05: Add OpenAPI/Protobuf generated clients and contract tests.
- [ ] PLT-001-06: Add dead-letter, safe replay, and operator queue controls.

### Acceptance

A full mock pipeline survives process restarts and duplicate delivery without duplicate assets, publication, or charges.
## REC-001 — LingBot-Map research adapter

**Dependencies:** CAP-001, PLT-001, GOV-001  
**Special inputs:** GPU, Legal, Consent

### Tasks

- [ ] REC-001-01: Pin upstream source at `1f480aeb8a47a24656090d46d053115b7fe60435` in a dedicated build context and retain license/notice.
- [ ] REC-001-02: Build locked Python/PyTorch/CUDA/FlashInfer and SDPA profiles with container digests.
- [ ] REC-001-03: Convert CSCP images/frame map into deterministic LingBot inputs.
- [ ] REC-001-04: Persist per-frame predictions, window membership, diagnostics, timings, and normalized pose/depth observations.
- [ ] REC-001-05: Implement cancellation/resume by completed window and explicit OOM profiles.
- [ ] REC-001-06: Implement research-only production gate and synthetic/consented benchmark fixtures.
- [ ] REC-001-07: Add pose-collapse, nonfinite, implausible motion, scale discontinuity, and window-seam validation.

### Acceptance

The adapter reproduces a fixed benchmark within tolerance, retains complete manifests, and is impossible to schedule commercially while HOLD is active.
## REC-002 — Metric observation lane

**Dependencies:** CAP-001, PLT-001  
**Special inputs:** GPU

### Tasks

- [ ] REC-002-01: Decode and normalize ARKit/Polycam depth, confidence, poses, intrinsics, mesh anchors, controls, and known dimensions.
- [ ] REC-002-02: Implement source-aware validity masks and covariance/weight models.
- [ ] REC-002-03: Create camera/depth synthetic conformance and known-plane tests.
- [ ] REC-002-04: Produce frame/trajectory/depth quality reports and reusable normalized observation assets.
- [ ] REC-002-05: Add policy to exclude bad calibration, tracking-limited, dynamic, or restricted observations.

### Acceptance

Metric observations reproduce synthetic ground truth and preserve source/quality for every accepted or rejected sample.
## REC-003 — Pose alignment and registration service

**Dependencies:** REC-001, REC-002  
**Special inputs:** GPU

### Tasks

- [ ] REC-003-01: Implement timestamp/frame correspondences and camera-center Sim(3) initialization.
- [ ] REC-003-02: Implement RANSAC/robust refinement, optional feature/geometry correspondences, and overlap checks.
- [ ] REC-003-03: Implement ICP only after accepted coarse alignment.
- [ ] REC-003-04: Persist transform graph, residuals, inliers, uncertainty, and review state.
- [ ] REC-003-05: Add manual point/plane/line/semantic correspondence tools and tests.
- [ ] REC-003-06: Benchmark ARKit-LingBot, Polycam-LingBot, and session-to-session registration.

### Acceptance

Known transformed fixtures recover the correct transform within tolerance and reject confidently wrong low-overlap alignments.
## REC-004 — Global factor graph and loop closure

**Dependencies:** REC-003  
**Special inputs:** GPU

### Tasks

- [ ] REC-004-01: Define solver interface and implement GTSAM or Ceres reference backend.
- [ ] REC-004-02: Add pose, visual-inertial, LingBot, loop, gravity, plane, control, dimension, and cross-session factors.
- [ ] REC-004-03: Implement place retrieval plus geometric verification for loop candidates.
- [ ] REC-004-04: Use robust/switchable constraints and produce residual/convergence reports.
- [ ] REC-004-05: Add incremental/batch comparison and large-change review gate.
- [ ] REC-004-06: Benchmark repeated corridors, loops, stairs, long floors, and false-loop adversaries.

### Acceptance

Global solutions reduce drift against ground truth without accepting false closures or mutating raw observations.
## REC-005 — Depth fusion, TSDF, and metric mesh

**Dependencies:** REC-002, REC-004  
**Special inputs:** None

### Tasks

- [ ] REC-005-01: Implement normalized depth unprojection and source-aware weighting.
- [ ] REC-005-02: Implement spatially chunked TSDF preview/final profiles with contribution tracking.
- [ ] REC-005-03: Implement incremental invalidation/rebuild for excluded sources.
- [ ] REC-005-04: Extract meshes and calculate topology/quality metrics; label repairs/fill.
- [ ] REC-005-05: Generate stable chunks/LODs and metric asset manifests.
- [ ] REC-005-06: Benchmark surface accuracy, completeness, seams, repeatability, RAM/VRAM, runtime, and cost.

### Acceptance

A controlled room meets declared metric/completeness thresholds and rebuilds affected chunks after source revocation.
## REC-006 — Texturing, visual mesh, splat lane, and tiling

**Dependencies:** REC-004, REC-005, GOV-001  
**Special inputs:** GPU

### Tasks

- [ ] REC-006-01: Implement source-frame texturing with occlusion, exposure, dynamic, and privacy masks.
- [ ] REC-006-02: Implement approved gsplat-based visual profile with full run manifests.
- [ ] REC-006-03: Generate browser LOD/tiles and optional OpenUSD/3D Tiles assets.
- [ ] REC-006-04: Implement evidence overlay and visual-source-class metadata by region where practical.
- [ ] REC-006-05: Evaluate held-out view quality, floaters, thin structures, restricted frame exclusion, and browser performance.
- [ ] REC-006-06: Ensure metric measurement tools never use visual-only assets by accident.

### Acceptance

Visual scenes improve presence while the UI and APIs preserve their non-authoritative status and evidence toggles.
## REC-007 — Splat normalization, cleanup, and edit journal

**Dependencies:** REC-005, GOV-002, DATA-001  
**Special inputs:** GPU, Legal

### Tasks

- [ ] REC-007-01: Implement immutable visual-splat source records, non-destructive transforms/crops, and replayable edit journal.
- [ ] REC-007-02: Implement approved local format normalization, compression, tiling, and LOD adapters with exact extension/version manifests.
- [ ] REC-007-03: Implement protected construction and LiveForever semantic regions across filtering, cleanup, and decimation.
- [ ] REC-007-04: Implement privacy redaction propagation to derivatives, previews, indexes, exports, and caches.
- [ ] REC-007-05: Build synchronized source/derivative, difference, semantic-impact, metric, interaction, and privacy review modes.
- [ ] REC-007-06: Add cleanup rollback, stage metrics, and unresolved-anchor reports.

### Acceptance

The fixture removes floaters while preserving a doorway, life-safety device, thin conduit, and memory-linked object; redacts a person in the approved derivative; and retains immutable originals, edit journal, support maps, and rollback.
## REC-008 — Splat-surface provider host and interaction-asset pipeline

**Dependencies:** REC-007, REC-005, GOV-002, PLT-001  
**Special inputs:** GPU, Legal

### Tasks

- [ ] REC-008-01: Implement provider SDK, signed capability manifest, admission, isolated execution, bounded resources, restricted egress, cancellation, stable errors, and result quarantine.
- [ ] REC-008-02: Implement deterministic local baseline providers for metric-derived proxy/collision and one approved splat-derived candidate.
- [ ] REC-008-03: Implement output roles for interaction proxy, collision volume, navigation surface, occlusion hull, spatial-audio volume, and preservation fallback.
- [ ] REC-008-04: Implement transform/scale/bounds/topology validation and comparison with accepted metric geometry.
- [ ] REC-008-05: Implement partitioning, overlap, seam validation, independent regeneration, and recomposition for building-scale scenes.
- [ ] REC-008-06: Implement per-use validation and candidate publication handoff without provider authority to publish.

### Acceptance

Two providers conform to one contract; each returns quarantined candidates; the publisher accepts only specific intended uses; failure leaves source, metric scene, and prior proxy byte-identical.
## SCN-001 — Scene graph, assertions, evidence, anchors, and measurements

**Dependencies:** DATA-002, REC-005  
**Special inputs:** Consent

### Tasks

- [ ] SCN-001-01: Implement stable entities/revisions, typed relationships, assertions, evidence links, provenance activities, and source/authority classes.
- [ ] SCN-001-02: Implement point/line/area/volume/surface/camera anchors and remapping records.
- [ ] SCN-001-03: Implement measurement classes, uncertainty, verification, permitted use, and evidence.
- [ ] SCN-001-04: Implement ontology registry and construction/LiveForever namespaces.
- [ ] SCN-001-05: Add authorization, history, merge/split identity, and provenance completeness validation.
- [ ] SCN-001-06: Create import/export sidecar schemas and fixture graph.

### Acceptance

Entities survive remeshing; all displayed facts and measurements expose evidence, source class, authority, and history.
## DATA-003 — Hybrid representation, derivation, family, and support-map schema
**Dependencies:** DATA-001, DATA-002, SCN-001  
**Special inputs:** None

### Tasks

- [ ] DATA-003-01: Implement representation assets, core roles, authority classes, intended/prohibited uses, publication states, limitations, spatial partitions, and representation families.
- [ ] DATA-003-02: Implement immutable derivation graph, provider/execution receipts, conversion-loss reports, validation reports, and source/output hashes.
- [ ] DATA-003-03: Implement support maps linking stable entities/anchors to world coordinates, evidence, source geometry neighborhoods, metric surfaces, semantic regions, and derived candidates.
- [ ] DATA-003-04: Add database constraints that make proxy/collision/navigation/occlusion assets ineligible for verified measurement and prevent authority inheritance through conversion.
- [ ] DATA-003-05: Implement LOD/tile membership, overlap, seams, recomposition, supersession, retirement, and branch-aware publication.
- [ ] DATA-003-06: Build explicit v1.0 role-assignment migration, quarantine ambiguous legacy assets, rollback, and independent export/import fixtures.

### Acceptance

One room registers visual, metric, proxy, collision, navigation, design, and evidence assets; invalid authority promotions fail; all source/derivation/validation links export; and proxy regeneration retains stable entities through support maps.
## REC-009 — Bidirectional mesh-splat interop and support maps

**Dependencies:** REC-008, SCN-001, DATA-003  
**Special inputs:** GPU, Legal

### Tasks

- [ ] REC-009-01: Implement representation asset/binding, authority ceiling, derivation, loss declaration, intended-use, partition/LOD family, and support-map schemas.
- [ ] REC-009-02: Implement splat-to-proxy and mesh-to-splat adapters as derivative operations without source overwrite or authority transfer.
- [ ] REC-009-03: Implement stable world/entity supports with optional primitive caches and anchor reprojection after remeshing.
- [ ] REC-009-04: Implement design/BIM object ID and revision preservation through mesh-to-splat visual conversion.
- [ ] REC-009-05: Implement open export/import sidecars, non-splat preservation fallback, and independent reference importer.
- [ ] REC-009-06: Implement Spatial Git diffs for representation, authority, provider, quality, limitations, support maps, policies, and affected entities.

### Acceptance

A scene round-trips through splat-to-proxy and mesh-to-splat derivatives, preserves coordinate and design/entity lineage, survives proxy replacement with bounded anchor residuals, reports unresolved anchors, and never transfers metric/as-built authority.
## SCN-002 — Scene commits, branches, semantic diff, and merge

**Dependencies:** SCN-001  
**Special inputs:** Consent

### Tasks

- [ ] SCN-002-01: Implement immutable scene root manifests, parent links, branches, tags, signatures, and publication classes.
- [ ] SCN-002-02: Implement semantic diff for entities, properties, relationships, anchors, measurements, permissions, consent, and geometry regions.
- [ ] SCN-002-03: Implement automatic safe merges and manual conflict records for high-impact classes.
- [ ] SCN-002-04: Implement rollback-as-new-commit and history export verification.
- [ ] SCN-002-05: Add two-visit building and conflicting-memory fixtures.

### Acceptance

A return visit and family alternate account produce reviewable diffs/merges without source loss or history rewrite.
## SCN-003 — Search, indexing, and spatial query

**Dependencies:** SCN-001, IAM-001  
**Special inputs:** GPU

### Tasks

- [ ] SCN-003-01: Implement metadata/full-text search and permission-filtered spatial/temporal predicates.
- [ ] SCN-003-02: Add vector embeddings behind model manifests and source-region lineage.
- [ ] SCN-003-03: Implement query DSL, saved queries/views, explanations, freshness, and canonical fallback.
- [ ] SCN-003-04: Add entity-to-view navigation and evidence summaries.
- [ ] SCN-003-05: Evaluate relevance, OCR/transcript noise, multilingual aliases, and permission leakage.

### Acceptance

Representative construction and memory questions return relevant authorized results with explanations and evidence links.
## PLT-002 — Web viewer and evidence interface

**Dependencies:** REC-005, SCN-001, IAM-001  
**Special inputs:** Physical

### Tasks

- [ ] PLT-002-01: Implement streaming point cloud/mesh/tiles and named coordinate conversion.
- [ ] PLT-002-02: Implement orbit/walk, floor/room navigation, clipping/sections, saved views, layers, and timeline.
- [ ] PLT-002-03: Implement entity/evidence/history/task panels and metric measurement controls.
- [ ] PLT-002-04: Implement metric/visual/design/source-photo/uncertainty/privacy/evidence toggles.
- [ ] PLT-002-05: Implement server-side restricted content filtering and immutable share presentations.
- [ ] PLT-002-06: Meet accessibility and device-tier performance budgets.

### Acceptance

Users can inspect one room on supported devices, understand source/authority, reproduce a saved view, and cannot retrieve restricted assets.
## PLT-003 — Spatial agent and typed tool layer

**Dependencies:** SCN-003, PLT-002, GOV-001  
**Special inputs:** Consent

### Tasks

- [ ] PLT-003-01: Define read tools for search, entity/evidence, scene history, measurements, and views.
- [ ] PLT-003-02: Define proposal tools for annotations, mappings, review tasks, and reports with idempotency.
- [ ] PLT-003-03: Implement context builder, citations, source labels, permission checks, and prompt-injection isolation.
- [ ] PLT-003-04: Block authoritative measurement, consent, deletion, life-safety control, or persona impersonation outside explicit tools/policy.
- [ ] PLT-003-05: Create construction and LiveForever evaluation suites with adversarial content.
- [ ] PLT-003-06: Add provider adapters and no-training/data-residency policy enforcement.

### Acceptance

The agent answers grounded questions with entity/evidence citations and fails closed on prohibited or injected actions.
## PLT-004 — Hybrid scene runtime, picking, interaction, and fallback

**Dependencies:** REC-008, REC-009, PLT-002  
**Special inputs:** GPU, Physical

### Tasks

- [ ] PLT-004-01: Implement layer registry for visual, metric, interaction, collision, navigation, occlusion, audio, design, semantic, and evidence assets.
- [ ] PLT-004-02: Integrate one approved hybrid splat-plus-mesh web renderer behind a replaceable runtime boundary.
- [ ] PLT-004-03: Implement support-map picking, ambiguous-candidate cycling, source/evidence navigation, and proxy replacement without entity identity loss.
- [ ] PLT-004-04: Implement measurement re-resolution from interaction hit to eligible metric/field evidence and proxy-only denial.
- [ ] PLT-004-05: Implement use-specific collision/navigation, clipping/sectioning, occlusion, spatial-audio zones, safe exit, and locomotion fallbacks.
- [ ] PLT-004-06: Implement partition/LOD streaming, device budgets, non-splat fallback, accessibility, and privacy-safe telemetry.

### Acceptance

Desktop and immersive-capable clients render one mixed scene, select entities through a hidden proxy, resolve measurement to metric evidence, navigate with an accepted collision asset, retain truth labels and safe exit, survive proxy replacement, and fall back without splat support.
## QA-001 — Benchmark and regression laboratory

**Dependencies:** REC-005, CAP-005, GOV-001  
**Special inputs:** Physical, Consent

### Tasks

- [ ] QA-001-01: Create controlled room and route with reference scanner/measurements/trajectory as appropriate.
- [ ] QA-001-02: Curate public/synthetic/consented manifests and split policies.
- [ ] QA-001-03: Implement benchmark runner for ATE/RPE, scale drift, surface error, completeness, normal error, seams, change precision/recall, runtime/memory/cost.
- [ ] QA-001-04: Add adversarial scenes: mirrors, glass, featureless walls, repeated corridors, darkness, crowds, stairs, long loops.
- [ ] QA-001-05: Publish per-scene-class operating envelope and regression thresholds.

### Acceptance

Every model/pipeline release produces reproducible stratified benchmark results and blocks material regression.
## QA-003 — Splat-surface and hybrid-runtime benchmark laboratory

**Dependencies:** QA-001, REC-008, REC-009, PLT-004  
**Special inputs:** Physical, GPU, Legal, Consent

### Tasks

- [ ] QA-003-01: Extend corpus with furnished room, MEP room, corridor, stairs/rails/openings, glass/mirrors, dynamics, protected thin devices, named memory objects, multi-room tiles, and design overlays.
- [ ] QA-003-02: Implement geometry metrics for scale, surface distance, completeness, normals, seams, false bridges, holes, floaters, intersections, and protected-object retention.
- [ ] QA-003-03: Implement interaction metrics for picking, anchor reprojection, collision leakage/barriers, walkability, stairs/doors, occlusion, spatial audio, and safe spawn/exit.
- [ ] QA-003-04: Implement runtime/cost metrics across desktop, mobile, headset, conversion resources, loading, memory, bandwidth, frame time, cancellation, and tiling.
- [ ] QA-003-05: Compare native hybrid, deterministic local baseline, prior release, approved research candidates, and manual fixture by scene stratum and intended use.
- [ ] QA-003-06: Implement release profiles and signed evidence for visual review, annotation, desktop/immersive navigation, construction reference/handoff, LiveForever guided/free modes, and preservation.

### Acceptance

Every provider/runtime release produces reproducible stratified evidence, rejects critical failures hidden by averages, proves provider-policy and proxy-authority controls, and publishes an operating envelope and fallback.
## CON-001 — Construction project, places, systems, and survey workflow

**Dependencies:** SCN-001, PLT-002, CAP-005  
**Special inputs:** Physical

### Tasks

- [ ] CON-001-01: Implement site/building/level/zone/room hierarchy, aliases, drawing names, and access classification.
- [ ] CON-001-02: Implement survey plans, room/system checklists, detail-pass requirements, inaccessible regions, and field visit closeout.
- [ ] CON-001-03: Implement design/observed/verified/proposed branches and publication workflows.
- [ ] CON-001-04: Create construction capture profiles and SOP UI.
- [ ] CON-001-05: Implement return-visit comparison entry point.

### Acceptance

A field operator captures and publishes a scoped accepted-reference survey with completeness, exclusions, and source labels.
## CON-002 — Fire alarm, access control, and MEP entity packs

**Dependencies:** CON-001  
**Special inputs:** Physical, GPU

### Tasks

- [ ] CON-002-01: Define ontology/properties/relationships for fire-alarm panels/devices/circuits/interfaces.
- [ ] CON-002-02: Define door/opening/hardware/readers/locks/contacts/REX/controllers and sequence records.
- [ ] CON-002-03: Define equipment/nameplates/BAS points/power/control/connections/clearances and cross-system interfaces.
- [ ] CON-002-04: Implement restricted classifications and role-specific viewer/report fields.
- [ ] CON-002-05: Create manual mapping UX and optional model-assisted proposals under review.
- [ ] CON-002-06: Add realistic system inventory fixtures and exports.

### Acceptance

A reviewer can build evidence-backed system inventories without exposing restricted topology to general project roles.
## CON-003 — Construction documents, issues, tests, and commissioning

**Dependencies:** CON-001, SCN-003  
**Special inputs:** Physical

### Tasks

- [ ] CON-003-01: Ingest drawings/specs/RFIs/submittals with immutable revisions and page-region anchors.
- [ ] CON-003-02: Implement issue/punch lifecycle, assignments, severity, evidence, correction, retest, closure, and disputes.
- [ ] CON-003-03: Implement commissioning procedures/results/participants/instruments and device/equipment links.
- [ ] CON-003-04: Add report and notification audience controls.
- [ ] CON-003-05: Create one end-to-end RFI-to-field-condition and issue-to-retest scenario.

### Acceptance

Exact document revisions/regions and field evidence are navigable through issue and commissioning history.
## CON-004 — Construction reports, open handoff, and facility view

**Dependencies:** CON-002, CON-003, SCN-002  
**Special inputs:** Physical

### Tasks

- [ ] CON-004-01: Build reproducible survey, inventory, change, issue, and commissioning report templates.
- [ ] CON-004-02: Implement audience profiles and sensitive-field separation.
- [ ] CON-004-03: Implement IFC/BCF/CSV/GLB/point-cloud export profiles and limitation/provenance sidecars.
- [ ] CON-004-04: Build read-only owner/facility search and document retrieval view.
- [ ] CON-004-05: Create full handoff release/tag, checksums, offline viewer, and independent import validation.

### Acceptance

An owner receives an open, integrity-verified package and can find assets/documents without the production subscription.
## CON-005 — Construction hybrid spatial-reference pilot

**Dependencies:** CON-004, PLT-004, QA-003  
**Special inputs:** Physical, GPU

### Tasks

- [ ] CON-005-01: Capture and register one mechanical/electrical or fire-alarm room plus adjacent corridor/doors as visual, metric, interaction, and evidence representations.
- [ ] CON-005-02: Anchor at least ten panels/devices/doors/equipment entities with source frames, documents, issues, and tests.
- [ ] CON-005-03: Overlay proposed design equipment/routes and preserve proposed versus observed/verified states.
- [ ] CON-005-04: Exercise clipping, navigation, protected thin geometry, change view, and proxy replacement.
- [ ] CON-005-05: Prove a proxy-derived dimension/quantity/clearance cannot become verified; record one independent field-verified measurement.
- [ ] CON-005-06: Export an owner handoff with open assets, sidecars, checksums, limitations, sensitive-layer policy, and offline viewer.

### Acceptance

A construction reviewer can navigate, select equipment, retrieve exact evidence, compare observed/proposed conditions, create and close an issue, measure through the authority workflow, replace the proxy without losing links, and independently open the handoff package.
## LIF-001 — LiveForever people, places, objects, memory graph, and interviews

**Dependencies:** SCN-001, PLT-002  
**Special inputs:** GPU, Consent

### Tasks

- [ ] LIF-001-01: Implement subject/contributor/person/relationship, place, object, event, memory, theme, time uncertainty, and audience models.
- [ ] LIF-001-02: Implement interview sessions, recording records, time-linked transcript, speaker uncertainty, corrections, private marks, and follow-up suggestions.
- [ ] LIF-001-03: Implement source classes, evidence links, corroboration, disputes, and narrative editions.
- [ ] LIF-001-04: Build one-question-at-a-time interview UX and review workflow.
- [ ] LIF-001-05: Create consented/synthetic fixtures and data-retention controls.

### Acceptance

Three source-linked stories can be captured, corrected, spatially anchored, searched, and assembled into an edition without changing originals.
## LIF-002 — Consent, family governance, privacy, and generated-presence gate

**Dependencies:** IAM-001, LIF-001  
**Special inputs:** Consent

### Tasks

- [ ] LIF-002-01: Implement granular consent grants by subject/data/purpose/modality/audience/provider/time/posthumous scope.
- [ ] LIF-002-02: Implement guardians/executors, living third-party restrictions, minors, disputes, freeze, revocation, and succession.
- [ ] LIF-002-03: Implement generated voice/likeness/dialogue/first-person capability flags and kill switch.
- [ ] LIF-002-04: Propagate policy to processing, search, viewer, agents, notifications, shares, reports, exports, and training datasets.
- [ ] LIF-002-05: Add consent evidence, audit, subject-rights export, and revocation tests.

### Acceptance

A prohibited voice-clone request is denied across every path; a revocation stops future use and identifies affected derivatives.
## LIF-003 — Memory reconstruction, evidence view, and preservation experience

**Dependencies:** LIF-001, LIF-002, REC-006, SCN-002  
**Special inputs:** Consent

### Tasks

- [ ] LIF-003-01: Implement current-place scan plus historical reconstruction branches and region-level source labels.
- [ ] LIF-003-02: Implement photo/video/document spatial placement with method and uncertainty.
- [ ] LIF-003-03: Implement explore, guided story, timeline, person/place/object, quiet, and evidence modes.
- [ ] LIF-003-04: Implement conflicting memory presentation and family review.
- [ ] LIF-003-05: Implement private family share and offline preservation package with open assets/checksums.
- [ ] LIF-003-06: Meet captions, reduced motion, keyboard, screen-reader, and safe-exit requirements.

### Acceptance

A family can explore a reconstructed room, reveal evidence/generation, view alternate accounts, and retain an offline preservation edition.
## LIF-004 — LiveForever navigable memory-room pilot

**Dependencies:** LIF-003, PLT-004, QA-003  
**Special inputs:** Physical, GPU, Consent

### Tasks

- [ ] LIF-004-01: Build one consented/synthetic meaningful room with visual splat, metric shell, interaction/collision/navigation assets, and evidence graph.
- [ ] LIF-004-02: Anchor at least three stories, five source media items, one named object, one uncertain historical detail, and one conflicting recollection.
- [ ] LIF-004-03: Implement captured/reconstructed/authored/disputed/generated/redacted region and object labels with evidence view.
- [ ] LIF-004-04: Implement guided, seated, teleport/free-when-safe, 2D/source, transcript/audio, quiet, and safe-exit modes.
- [ ] LIF-004-05: Exercise spatial narration, consent/audience controls, protected memory objects, proxy replacement, and unresolved family review.
- [ ] LIF-004-06: Export private/family editions and a non-splat offline preservation package with checksums and policy metadata.

### Acceptance

An authorized family member can explore and review the room without mistaking proxy or generated geometry for historical evidence; accessibility and safe-exit controls work; story anchors survive proxy replacement; alternate recollections and evidence remain visible; and the preservation edition opens offline.
## OPS-001 — Security, encryption, audit, and privacy controls

**Dependencies:** IAM-001, DATA-001, PLT-001  
**Special inputs:** Physical, GPU

### Tasks

- [ ] OPS-001-01: Implement envelope encryption/key scopes, rotation, access audit, local key option, and cryptographic-erasure workflow.
- [ ] OPS-001-02: Implement workload identity, network/egress policy, secret management, signed artifacts, and administrative JIT access.
- [ ] OPS-001-03: Implement append-only audit and capture/scene manifest signature verification.
- [ ] OPS-001-04: Implement privacy inventory, subject-rights workflows, redaction, and vendor/purpose policy.
- [ ] OPS-001-05: Run threat model and penetration/abuse tests including spatial leakage and prompt injection.

### Acceptance

Critical threat controls and cross-tenant/consent/redaction tests pass with retained evidence.
## OPS-002 — Observability, SLOs, cost, and support tooling

**Dependencies:** PLT-001, REC-001  
**Special inputs:** Physical, GPU

### Tasks

- [ ] OPS-002-01: Implement structured logs, distributed traces, metrics, quality dashboards, model segmentation, and audit correlation.
- [ ] OPS-002-02: Define SLOs/performance budgets by endpoint, viewer tier, capture device, and processing profile.
- [ ] OPS-002-03: Implement pre-run cost estimates and actual usage/cost allocation by tenant/project/run/stage.
- [ ] OPS-002-04: Implement quotas, budget admission, anomaly alerts, and queue dashboards.
- [ ] OPS-002-05: Implement privacy-safe support bundles and time-bound customer-approved access.

### Acceptance

Operators diagnose failures and cost without raw-data browsing; customers see estimates and budget controls.
## OPS-003 — Cloud, hybrid, local, and edge deployment

**Dependencies:** FND-002, OPS-001  
**Special inputs:** GPU

### Tasks

- [ ] OPS-003-01: Build infrastructure-as-code for small cloud reference deployment and isolated environments.
- [ ] OPS-003-02: Build local-only installer/upgrade/rollback and edge enrollment.
- [ ] OPS-003-03: Implement hybrid asset residency/transfer policy and approved-compute routing.
- [ ] OPS-003-04: Implement GPU pool capability discovery, quotas, pre-baked models, and restricted egress.
- [ ] OPS-003-05: Test migration of a project among deployment profiles preserving IDs/history/policy.

### Acceptance

One project processes local-only and hybrid using identical manifests, with no disallowed asset transfer.
## OPS-004 — Backup, restore, disaster recovery, retention, and deletion

**Dependencies:** OPS-001, OPS-003  
**Special inputs:** Legal

### Tasks

- [ ] OPS-004-01: Implement database PITR, object versioning/immutability, audit preservation, and configuration/key recovery.
- [ ] OPS-004-02: Automate isolated restore and root-hash reconciliation.
- [ ] OPS-004-03: Implement retention/legal hold/deletion dependency graph and dry-run reports.
- [ ] OPS-004-04: Implement cache/index purge and backup expiry handling.
- [ ] OPS-004-05: Run region/service-loss game day and portability-based contingency.

### Acceptance

A clean environment restores a selected point, verifies hashes/history, and deletion does not resurrect through indexes or routine restore.
## QA-002 — Dual vertical acceptance and release gates

**Dependencies:** CON-004, LIF-003, OPS-004, QA-001  
**Special inputs:** Legal, Consent

### Tasks

- [ ] QA-002-01: Run the construction hybrid-reference demo with independent dimensions, protected-device inventory, proxy replacement, design overlay, and measurement-authority checks.
- [ ] QA-002-02: Run the LiveForever navigable-memory demo with consented stories, conflict, generated labels, proxy replacement, safe locomotion, evidence view, and offline export.
- [ ] QA-002-03: Run license, security/privacy, accessibility, load, backup/restore, migration, and rollback gates.
- [ ] QA-002-04: Compile known limitations, operating envelope, support plan, and release evidence.
- [ ] QA-002-05: Sign and publish release manifest/checksums and recovery instructions.

### Acceptance

All P0 requirements and both end-to-end scenarios pass; release can roll back and customers can export independently.
## PILOT-001 — Controlled customer pilots

**Dependencies:** QA-002  
**Special inputs:** Physical, Consent

### Tasks

- [ ] PILOT-001-01: Select one construction pilot and one LiveForever pilot with explicit data/consent agreements.
- [ ] PILOT-001-02: Define success metrics, operating envelope, support, privacy, measurement claims, and exit/export.
- [ ] PILOT-001-03: Run capture/operator training and capture-quality review.
- [ ] PILOT-001-04: Collect field revisits avoided, retrieval speed, reconstruction quality, support burden, costs, and consent/trust feedback.
- [ ] PILOT-001-05: Resolve pilot findings through requirements, tests, and releases before broader launch.

### Acceptance

Pilots deliver customer value within declared limitations and produce evidence-based go/no-go decisions for production expansion.
