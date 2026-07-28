---
spec_id: APP-CHECK
title: "Specification and Release Readiness Checklist"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Specification and Release Readiness Checklist

A checkbox is complete only when its evidence link is attached to the implementation release record.

## Governance and scope

- [ ] Specification version, manifest, checksums, approvals, and change log exist.
- [ ] All P0 requirements have verification evidence.
- [ ] Open P0 assumptions and critical risks are resolved or release is blocked.
- [ ] Product claims match the validated operating envelope.
- [ ] Non-goals and limitations appear in user-facing measurement/reconstruction flows.

## Licensing and models

- [ ] SBOM contains every runtime/build dependency and optional download.
- [ ] LingBot code revision and notices are pinned.
- [ ] LingBot checkpoint hash, license, upstream provenance, and commercial-purpose approval are complete—or the production adapter is disabled.
- [ ] VGGT or other inherited checkpoints use the explicitly permitted artifact, not a noncommercial original.
- [ ] Auxiliary sky/segmentation/OCR/embedding/voice models have manifests.
- [ ] Dataset rights and service-provider terms permit the actual use, region, customer, and outputs.
- [ ] Production workers cannot download undeclared models.

## Capture

- [ ] First-party iOS state machine persists and recovers from termination.
- [ ] RGB, depth, confidence, poses, intrinsics, mesh anchors, IMU, and timestamps remain synchronized.
- [ ] CSCP package validates, hashes, signs, exports, resumes, and preserves unknown compatible extensions.
- [ ] Polycam adapter handles optimized and non-optimized raw exports.
- [ ] Tracking loss, low storage, thermal pressure, and no-network scenarios are tested.
- [ ] Capture quality and coverage warnings are actionable and versioned.
- [ ] Privacy marks and restricted spatial volumes survive processing and export.

## Reconstruction

- [ ] LingBot adapter records exact commit/container/checkpoint/backend/parameters and per-frame outputs.
- [ ] Long-sequence keyframe/window policy and pose-collapse detection are tested.
- [ ] ARKit/LiDAR, LingBot, controls, and optional sources normalize into explicit frames.
- [ ] Sim(3)/SE(3) alignment has convention and synthetic conformance tests.
- [ ] Loop closures are geometrically verified and robustly weighted.
- [ ] Factor-graph/global optimization reports residuals and rejected factors.
- [ ] Depth fusion preserves source contribution and uncertainty.
- [ ] TSDF/chunking/mesh extraction is reproducible within tolerance.
- [ ] Metric and visual assets are separately classified.
- [ ] Dynamic objects and unobserved regions are not mistaken for structural change.
- [ ] Quantitative benchmark thresholds pass by scene class.

## Data and provenance

- [ ] Stable entities survive remeshing and rescans.
- [ ] Coordinate frames, units, transform direction, and CRS semantics are explicit.
- [ ] Assertions link to immutable evidence and provenance.
- [ ] Authority, confidence, source class, and corroboration are separate.
- [ ] Scene commits, semantic diff, merge conflicts, tags, and rollback work.
- [ ] Content hashes are verified after storage and on restore.
- [ ] Search is permission-aware before ranking and snippets.
- [ ] Open exports include provenance/limitation sidecars.
- [ ] Retention, legal hold, revocation, deletion, and portability are implemented.

## Viewer and APIs

- [ ] REST/OpenAPI and worker contracts pass compatibility tests.
- [ ] Idempotency, optimistic concurrency, pagination, cancellation, and retry behavior are tested.
- [ ] Viewer supports metric/visual/evidence/design/uncertainty/privacy layers.
- [ ] Measurements show class, uncertainty, and permitted use.
- [ ] Restricted content is filtered server-side.
- [ ] Accessibility requirements pass.
- [ ] Saved views/reports are reproducible from commit/layers/camera/filter state.
- [ ] Agent tools cannot bypass policy or silently commit authoritative facts.
- [ ] Prompt-injection and evidence-fabrication evaluations pass.

## Construction

- [ ] Project/building/level/room/system hierarchy supports aliases and revisions.
- [ ] Design intent is separate from field observation and verified as-built.
- [ ] Fire alarm, access control, and MEP records support required entities and restricted details.
- [ ] Drawings/specs/RFIs/submittals link to exact revisions and spatial regions.
- [ ] Deficiency/punch/commissioning lifecycle retains evidence and retest.
- [ ] Scan estimates cannot be exported without source/verification warning.
- [ ] Return-visit change detection passes controlled tests.
- [ ] Owner handoff exports open data and validates in independent consumers.
- [ ] Construction acceptance scenario passes.

## LiveForever

- [ ] Original interviews/media are immutable and derivatives link to exact ranges/regions.
- [ ] Memory graph supports uncertainty, witnesses, conflict, and editions.
- [ ] Consent is purpose/modality/audience/provider/time specific.
- [ ] Living third-party and minor policy is enforced.
- [ ] Generated voice/likeness/dialogue requires explicit consent and persistent disclosure.
- [ ] Evidence view reveals direct, reconstructed, restored, inferred, generated, and disputed content.
- [ ] Revocation propagates to search, viewer, agents, exports, and future processing.
- [ ] Experience has quiet/non-avatar mode, captions, reduced motion, and safe exit.
- [ ] Offline preservation package verifies.
- [ ] LiveForever acceptance scenario passes.

## Security and operations

- [ ] Threat model covers cross-tenant, spatial leakage, parser, GPU, agent, insider, and destructive abuse.
- [ ] MFA/JIT administration, workload identity, egress controls, secrets, and signing are implemented.
- [ ] Encryption/key rotation/recovery/erasure are tested.
- [ ] Audit is append-only and links capture-to-output lineage.
- [ ] Backup restoration and disaster recovery are demonstrated.
- [ ] Local-only and hybrid deployments pass policy tests.
- [ ] Cost estimates and actual attribution are operational.
- [ ] Load, noisy-neighbor, quota, and budget tests pass.
- [ ] CI/CD produces signed artifacts, SBOM, license gate, migrations, benchmark evidence, and rollback.
- [ ] Support access is scoped, approved, logged, and privacy-safe.

## Final release evidence

- [ ] Construction and LiveForever pilot reports are attached.
- [ ] Known limitations and operating envelopes are published.
- [ ] Rollback has been rehearsed.
- [ ] Portability/offline access has been demonstrated from a clean environment.
- [ ] Release owner signs the evidence record.

## Version 1.1 completion additions

- [ ] hybrid service/trust-boundary module implemented;
- [ ] representation asset/authority/support-map schemas implemented;
- [ ] provider SDK, registry, quarantine, validation, publication, and revocation implemented;
- [ ] local baseline proxy/collision provider implemented;
- [ ] native splat-plus-mesh runtime and capability resolver implemented;
- [ ] stable anchors survive remesh/LOD/tile changes;
- [ ] proxy measurement and historical-authority abuse tests pass;
- [ ] construction and LiveForever hybrid pilots pass;
- [ ] provider/license/privacy/security evidence passes;
- [ ] v1.0 migration, rollback, and independent export/import pass.
