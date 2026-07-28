---
spec_id: TST-LAY
title: "Unit, Contract, Integration, and End-to-End Tests"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: true
---
# Unit, Contract, Integration, and End-to-End Tests

    ## 1. Purpose

    Defines deterministic automated tests for core state, schemas, adapters, APIs, events, workers, and user journeys.

    This document is normative for the testing layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Contract tests validate both producer and consumer against canonical schemas.
- Integration tests use real databases/object stores/queues where behavior matters.
- End-to-end tests use small deterministic fixtures and do not replace field benchmarks.
- Golden artifacts are versioned with intentional update review.

    ## 3. Governing principles

    - Geometry claims are tested against independent ground truth rather than screenshots or subjective visual appeal.
- Every normative requirement maps to at least one automated test, controlled field procedure, review gate, or monitored production control.
- Test datasets include ordinary success cases and adversarial conditions such as mirrors, textureless walls, crowds, darkness, and repeated corridors.
- Release gates cover functionality, accuracy, privacy, licensing, reproducibility, security, and rollback.

    ## 4. Normative requirements

    | ID         | Priority | Requirement                                                                                                                           | Verification            |
| ---------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| TSTLAY-001 | P0       | Coordinate math shall have property tests for identity, inverse, composition, units, and camera ray round trips.                      | Controlled verification |
| TSTLAY-002 | P0       | CSCP validators shall have malformed, adversarial, backward-compatible, and forward-unknown-field fixtures.                           | Controlled verification |
| TSTLAY-003 | P0       | API/event tests shall cover idempotency, retries, concurrency, authorization, pagination, and schema compatibility.                   | Automated test          |
| TSTLAY-004 | P1       | Worker tests shall verify resource limits, cancellation, checkpoints, hash validation, and unapproved-model rejection.                | Automated test          |
| TSTLAY-005 | P1       | End-to-end tests shall cover capture ingest through scene publication, review, search, viewer metadata, export, and deletion request. | Controlled verification |
| TSTLAY-006 | P1       | Golden updates shall include comparison reports and reviewer approval.                                                                | Controlled verification |

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

    - A versioned `tst_lay_manifest` recording identity, timestamps, ownership, state, and provenance.
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

    Test data is synthetic or consented, minimized, access-controlled, and destroyed according to its retention class.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: requirements covered, regression escape rate, benchmark variance, flaky test rate, release rollback frequency. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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
