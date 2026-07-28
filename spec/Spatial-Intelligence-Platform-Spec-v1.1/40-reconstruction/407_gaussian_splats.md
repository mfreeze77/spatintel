---
spec_id: REC-SPLAT
title: "Gaussian Splat Visual Reconstruction"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: reconstruction
normative: true
---
# Gaussian Splat Visual Reconstruction

    ## 1. Purpose

    Defines a permissively licensed, independently versioned photoreal visual lane for presence and contextual review.

    This document is normative for the reconstruction layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - The commercial reference path prefers `gsplat` or an equivalently approved engine; restrictive research implementations are not default dependencies.
- Splats are visual assets and cannot be used as authoritative measurement surfaces without a separately validated method.
- Training camera poses come from an accepted pose solution and are referenced by hash.
- Construction and LiveForever use different optimization and artifact policies.

    ## 3. Governing principles

    - Learned geometry is a hypothesis with confidence, not a measurement by default.
- Metric scale is anchored by calibrated sensors, control points, fiducials, or verified dimensions.
- Long-sequence drift is corrected outside LingBot-Map through cross-session registration, loop constraints, and factor-graph optimization.
- Metric, visual, interaction, and evidence representations are generated separately but registered to common coordinate frames.

    ## 4. Normative requirements

    | ID           | Priority | Requirement                                                                                                                                                                           | Verification            |
| ------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| RECSPLAT-001 | P0       | A splat run shall record engine commit/package, license approval, input images, masks, pose solution, calibration, training parameters, seed, hardware, checkpoints, and output hash. | Automated test          |
| RECSPLAT-002 | P0       | The pipeline shall support excluding sensitive frames and regions before training.                                                                                                    | Controlled verification |
| RECSPLAT-003 | P0       | The viewer shall display a visual-reconstruction label and provide an evidence/geometry toggle.                                                                                       | Controlled verification |
| RECSPLAT-004 | P1       | Splat quality tests shall include held-out views, floaters, temporal artifacts, thin structures, and browser/device performance.                                                      | Controlled verification |
| RECSPLAT-005 | P1       | Generated inpainting or relighting shall be separate transformations with persistent labels.                                                                                          | Automated test          |
| RECSPLAT-006 | P1       | Export shall use approved open or documented formats and retain a fallback rendered archive for preservation.                                                                         | Controlled verification |

    Requirements marked **P0** block the first production release of this capability. P1 requirements may be delivered in a subsequent milestone only when the release plan identifies the temporary control, owner, expiration date, and migration path. A waiver cannot change an evidence or consent label into a more certain category.

    ## 5. Architecture and responsibilities

    The capability is implemented behind a versioned boundary. User-facing applications initiate intent, domain services enforce policy and state transitions, workers perform bounded computation, and the data plane stores immutable inputs and derivatives. No worker may directly grant itself authority to publish an authoritative scene revision. Publication is performed by the owning domain service after output validation.

    A production implementation must assign ownership for:

    - request validation and authorization;
    - deterministic identity and idempotency;
    - data-plane reads and writes;
    - model or algorithm execution;
    - confidence and quality calculation;
    - audit events and operational metrics;
    - human review and exception handling;
    - retention, deletion, legal hold, and export.

    ## 6. Data contracts

    - A versioned `rec_splat_manifest` recording identity, timestamps, ownership, state, and provenance.
- An immutable input reference set using content hashes rather than mutable storage paths.
- A result summary carrying status, warnings, confidence, metrics, and links to detailed artifacts.

    Every contract includes `schema_version`, `tenant_id`, `project_id`, `created_at`, `created_by`, a globally unique identifier, and a provenance reference. Coordinates include frame identifier, axis convention, handedness, units, and transform direction. Timestamps state their clock domain and synchronization quality. Numeric confidence values are accompanied by a definition and calibration version; an unexplained number between zero and one is not acceptable evidence.

    ## 7. Primary workflow

    1. Validate identity, authorization, schema version, and prerequisites.
2. Create an immutable intent record and assign an idempotency key.
3. Execute the operation while emitting progress, warnings, metrics, and audit events.
4. Validate outputs and confidence before making them discoverable.
5. Commit the new revision atomically, preserving the prior authoritative state.

    Each transition emits a durable domain event after the corresponding state change commits. Consumers are idempotent and tolerate redelivery. Large binary assets are transferred through signed, resumable object-storage operations; APIs exchange manifests and references rather than embedding multi-gigabyte payloads.

    ## 8. Provenance, confidence, and authority

    The capability must preserve a minimum lineage chain of: source capture or record → normalized input → algorithm/model and exact version → parameters → output hash → validation result → reviewer or automated publication decision. If any link is absent, the result is marked `provenance_incomplete` and is not eligible for verified or authoritative status.

    Authority is orthogonal to confidence. A high-confidence AI prediction remains inferred. A manually verified field measurement may be authoritative even when the scanner's confidence was low. The user interface must expose source class, verifier, verification time, and superseding revisions.

    ## 9. Security and privacy

    Workers execute untrusted captures in isolated jobs with bounded resources and immutable input mounts.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: absolute trajectory error, surface distance error, completeness, cross-window seam error, pipeline reproducibility. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

    Performance objectives are recorded as budgets rather than vague aspirations. A budget defines input class, hardware profile, concurrency, percentile, warm/cold state, and degradation behavior. The system prefers an explicit lower-quality preview over an unexplained timeout.

    ## 12. Testing and acceptance

    - All P0 requirements have automated or repeatable controlled verification.
- The happy path and each listed failure mode are demonstrated with retained evidence.
- A second implementation can consume the documented contracts without private knowledge.
- Security, privacy, provenance, and rollback behavior are included in the acceptance demonstration.

    Tests retain machine-readable results, input hashes, environment information, and output metrics. Visual review may supplement but cannot replace quantitative tests for geometry, timing, authorization, lineage, or destructive operations.

    ## 13. Implementation sequence

    1. Freeze the contract and state machine behind feature flags.
    2. Implement a deterministic reference path with synthetic fixtures.
    3. Add production storage, queues, authorization, audit, and cancellation.
    4. Integrate algorithms or models through adapters with pinned manifests.
    5. Add quality gates, review queues, and observability.
    6. Run controlled field pilots and compare against independent ground truth.
    7. Promote only after acceptance evidence is attached to the release record.

    ## 14. Dependencies and related documents

    - See `SPEC_INDEX.md` for upstream and downstream specifications.
- See `00-governance/008_license_and_model_governance.md` before adding a dependency or model.
- See `95-testing-delivery/955_release_gates.md` for production promotion criteria.

## 15. Version 1.1 hybrid use

A visual splat may be displayed with hidden metric and interaction geometry. Splat-to-surface extraction creates a derivative; it never changes the source splat's visual role or grants measurement authority. The platform prefers native hybrid composition when conversion would discard view-dependent appearance or introduce topology errors.

Splat cleanup, compression, LOD, mesh extraction, and mesh-to-splat conversion retain immutable lineage, generation/redaction labels, protected regions, and policy dependencies. Hosted/manual tools use the external-provider gate.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| RECSPLAT-007 | P0 | A surface extracted from a splat shall be a separately versioned derivative with non-authoritative default authority. | Lineage/policy test |
| RECSPLAT-008 | P0 | Splat processing shall retain generation, redaction, consent, classification, and source-policy dependencies. | Policy propagation test |
| RECSPLAT-009 | P0 | Unapproved hosted/manual tools shall be denied sensitive scene assets before export. | Security test |
| RECSPLAT-010 | P1 | Native hybrid splat-plus-mesh rendering shall remain a supported path when extraction is unnecessary or rejected. | Viewer compatibility test |
| RECSPLAT-011 | P1 | Splat LOD or format conversion shall preserve coordinate alignment and semantic support within declared tolerances. | Interop test |
| RECSPLAT-012 | P1 | The preservation package shall include a documented non-splat fallback when long-term renderer support is uncertain. | Preservation test |

## Version 1.1 hybrid-scene integration

A Gaussian splat is retained as a first-class visual representation even when a proxy or collision asset is generated. Splat-to-mesh and mesh-to-splat are lossy derivations under [`417_bidirectional_mesh_splat_interop.md`](417_bidirectional_mesh_splat_interop.md); neither direction transfers measurement, as-built, design, or historical authority. Native splat-plus-mesh rendering is preferred when conversion is unnecessary.
