---
spec_id: REC-ALIGN
title: "Pose Alignment, Scale, and Coordinate Registration"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: reconstruction
normative: true
---
# Pose Alignment, Scale, and Coordinate Registration

    ## 1. Purpose

    Defines coarse and fine registration between LingBot, ARKit, Polycam, survey, BIM, and prior-scene coordinate frames.

    This document is normative for the reconstruction layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Every registration creates a transform edge with method, correspondences, residuals, uncertainty, and validity interval.
- Similarity transforms are solved before rigid refinement when source scale is not guaranteed.
- Camera-center and orientation alignment is preferred before geometry ICP when synchronized poses are available.
- ICP is gated by overlap and initialization quality to avoid confident wrong minima.

    ## 3. Governing principles

    - Learned geometry is a hypothesis with confidence, not a measurement by default.
- Metric scale is anchored by calibrated sensors, control points, fiducials, or verified dimensions.
- Long-sequence drift is corrected outside LingBot-Map through cross-session registration, loop constraints, and factor-graph optimization.
- Metric, visual, interaction, and evidence representations are generated separately but registered to common coordinate frames.

    ## 4. Normative requirements

    | ID           | Priority | Requirement                                                                                                                             | Verification            |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| RECALIGN-001 | P0       | The alignment solver shall support SE(3) and Sim(3) and state which was used.                                                           | Controlled verification |
| RECALIGN-002 | P0       | At least three non-collinear constraints or an equivalent trajectory/geometry basis shall be required for free 3D similarity alignment. | Controlled verification |
| RECALIGN-003 | P0       | Robust estimation shall reject outliers and report inlier count, distribution, and residual statistics.                                 | Automated test          |
| RECALIGN-004 | P1       | Transform direction, source frame, target frame, units, handedness, and axis convention shall be machine-readable.                      | Controlled verification |
| RECALIGN-005 | P1       | Alignment acceptance thresholds shall depend on capture profile and intended use.                                                       | Controlled verification |
| RECALIGN-006 | P1       | A transform revision shall not mutate prior observation coordinates; it creates a new solution graph.                                   | Controlled verification |

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

    - `coordinate_frame` records with frame ID, parent, axis convention, units, origin, and CRS where applicable.
- `registration_constraint` records for camera pairs, points, planes, fiducials, dimensions, and semantic landmarks.
- `transform_solution` records with matrix, covariance/quality, solver, robust loss, residuals, input hashes, and approval.

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
