---
spec_id: CAP-CSCP
title: "Canonical Spatial Capture Package"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: capture
normative: true
---
# Canonical Spatial Capture Package

    ## 1. Purpose

    Defines the immutable, source-neutral package consumed by every reconstruction and evidence pipeline.

    This document is normative for the capture layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Packages are manifests plus content-addressed assets and may be directory, ZIP64, or object-store collections.
- A package has session, segment, frame, sensor, coordinate-frame, calibration, quality, privacy, and provenance records.
- Finalization creates a Merkle-style root over asset hashes and normalized manifests.
- Extensions are namespaced and cannot redefine normative fields.

    ## 3. Governing principles

    - Capture quality is judged while the operator can still correct it, not only after upload.
- RGB, depth, confidence, pose, intrinsics, mesh anchors, IMU, timestamps, and device metadata remain synchronized and exportable.
- The operator can pause, resume, segment, and recover a session without corrupting accepted frames.
- Privacy zones and sensitive content can be marked at capture time while preserving controlled originals when policy permits.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                                                                                           | Verification            |
| ----------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| CAPCSCP-001 | P0       | The root manifest shall include schema version, session ID, tenant/project when known, source adapter, device, time range, coordinate frames, segments, asset index, root hash, and signature status. | Automated test          |
| CAPCSCP-002 | P0       | Every asset entry shall include path/reference, media type, byte size, SHA-256, creation source, encryption status, and retention class.                                                              | Automated test          |
| CAPCSCP-003 | P0       | Every frame shall reference an image and may reference depth, confidence, pose, intrinsics, mesh observations, audio time range, quality events, and privacy regions.                                 | Automated test          |
| CAPCSCP-004 | P1       | The validator shall detect missing assets, duplicate identifiers, hash mismatch, transform cycles, non-monotonic timestamps, impossible dimensions, and unsupported major versions.                   | Automated test          |
| CAPCSCP-005 | P1       | Package normalization shall be deterministic so identical logical manifests produce identical canonical hashes.                                                                                       | Automated test          |
| CAPCSCP-006 | P1       | Unknown optional fields shall be retained when re-serializing a compatible package.                                                                                                                   | Controlled verification |

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

    - `manifest.json` — package identity, schema, source, roots, segments, coordinate frames, policy, and signatures.
- `assets.jsonl` — one content record per immutable asset.
- `frames/*.jsonl` — ordered frame records partitioned by segment.
- `sensors/*.jsonl` — IMU, GNSS, barometer, thermal, or future streams with clock definitions.
- `meshes/*.jsonl` — mesh-anchor operations and references.
- `events/*.jsonl` — tracking, quality, privacy, user annotation, interruption, and recovery events.

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

    Capture packages are encrypted at rest, signed at finalization, and uploaded through resumable authenticated transfer.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: accepted-frame ratio, pose tracking loss, coverage score, blur/glare rate, upload retry volume. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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
