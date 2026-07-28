---
spec_id: DAT-FRAME
title: "Coordinate Frames, Units, and Transform Semantics"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: data
normative: true
---
# Coordinate Frames, Units, and Transform Semantics

    ## 1. Purpose

    Defines unambiguous spatial math across ARKit, cameras, LingBot, BIM, GIS, meshes, splats, and viewer engines.

    This document is normative for the data layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Every transform is named as `target_from_source` and serialized with explicit convention.
- Internal metric geometry uses meters and right-handed frames unless an adapter boundary states otherwise.
- Camera models distinguish camera-to-world and world-to-camera; no field is named merely `pose` in canonical contracts.
- Local building frames, survey/CRS frames, device frames, session frames, and render frames remain explicit.

    ## 3. Governing principles

    - Entities have stable IDs independent of geometry revisions and file formats.
- Spatial relationships, temporal validity, provenance, confidence, permissions, and evidence are first-class fields.
- Content-addressed assets prevent accidental duplication and enable cryptographic integrity checks.
- Deletion, legal hold, retention, and inheritance policies propagate across derivatives without rewriting the historical ledger.

    ## 4. Normative requirements

    | ID           | Priority | Requirement                                                                                                                                                     | Verification            |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| DATFRAME-001 | P0       | A coordinate frame shall declare ID, semantic type, handedness, axis directions, units, origin, parent when applicable, and CRS/vertical datum when applicable. | Controlled verification |
| DATFRAME-002 | P0       | A transform shall declare source, target, matrix layout, multiplication convention, direction, timestamp/validity, solver/source, and uncertainty.              | Controlled verification |
| DATFRAME-003 | P0       | Adapters shall include conformance tests using known basis vectors, camera rays, and round trips.                                                               | Controlled verification |
| DATFRAME-004 | P1       | Unit conversion shall occur at explicit boundaries and retain source units.                                                                                     | Controlled verification |
| DATFRAME-005 | P1       | Viewer coordinate conversions shall not modify stored authoritative geometry.                                                                                   | Controlled verification |
| DATFRAME-006 | P1       | Geospatial transforms shall record the exact CRS pipeline and grid resources used.                                                                              | Controlled verification |

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

    - `CoordinateFrame { id, kind, handedness, axes, units, origin, crs, vertical_datum }`
- `TransformEdge { id, target_frame_id, source_frame_id, matrix4x4, convention, valid_time, covariance, provenance_id }`
- `CameraModel { model, intrinsics, distortion, image_size, calibration_id }`

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

    Row, object, scene, and spatial-volume permissions are evaluated consistently across APIs and viewers.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: orphaned asset count, index freshness, provenance completeness, hash verification failures, query selectivity. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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
