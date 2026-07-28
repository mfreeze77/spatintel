---
spec_id: GOV-SCOPE
title: "Scope, Boundaries, and Non-Goals"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---
# Scope, Boundaries, and Non-Goals

    ## 1. Purpose

    Prevents the platform from drifting into unsupported claims such as survey certification, automatic design approval, or recreation of consciousness.

    This document is normative for the governance layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - SIP records and reconstructs places; it does not certify survey-grade accuracy unless a separately governed workflow supplies qualified control and verification.
- SIP can assist BIM creation but does not autonomously issue contract documents or professional seals.
- LiveForever preserves and presents memories; it does not claim that a generated persona is the deceased person or is conscious.
- Robotics actuation, life-safety control, and autonomous security decisions are outside the initial product boundary.

    ## 3. Governing principles

    - Every decision must be traceable to a requirement, risk, experiment, or external constraint.
- No inferred geometry, generated memory, or AI label may silently replace source evidence.
- Commercial release is blocked when code, model-weight, dataset, or transitive-license evidence is incomplete.
- Normative requirements use deterministic identifiers and measurable verification methods.

    ## 4. Normative requirements

    | ID           | Priority | Requirement                                                                                                                       | Verification            |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| GOVSCOPE-001 | P0       | Product interfaces shall display operating-envelope limitations wherever users can create or export measurements.                 | Controlled verification |
| GOVSCOPE-002 | P0       | Marketing and generated reports shall not describe unverified phone scans as survey grade, code compliant, or as-built certified. | Controlled verification |
| GOVSCOPE-003 | P1       | The platform shall prevent an AI agent from issuing a life-safety control command through spatial tools.                          | Automated test          |
| GOVSCOPE-004 | P1       | LiveForever experiences shall identify simulated voice, face, dialogue, and scene completion before or at first presentation.     | Controlled verification |
| GOVSCOPE-005 | P1       | Out-of-scope requests shall generate a safe handoff or export rather than silent approximation.                                   | Controlled verification |

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

    - A versioned `gov_scope_manifest` recording identity, timestamps, ownership, state, and provenance.
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

    Governance records are append-only, signed where practical, and visible to authorized auditors.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: unresolved decision age, requirements without tests, license gates without evidence, waiver count and expiry. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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

## 15. Version 1.1 scope clarification

SIP now includes generation and runtime use of non-authoritative interaction proxies, collision volumes, navigation surfaces, occlusion hulls, spatial-audio volumes, and bidirectional mesh/splat derivatives. These capabilities improve interaction and presentation; they do not expand the platform's authority to certify dimensions, code compliance, as-built conditions, autonomous safety, identity, or historical fact.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| GOVSCOPE-006 | P0 | Product messaging shall describe splat-derived surfaces as interaction/visual derivatives unless independently promoted through an eligible metric workflow. | Marketing/UI review |
| GOVSCOPE-007 | P0 | Proxy, collision, and navigation assets shall not be marketed as survey, code, fabrication, robotic-safety, or historical-proof products. | Policy/content test |
| GOVSCOPE-008 | P1 | The platform shall remain useful through native hybrid rendering and open fallbacks when no splat-to-surface provider is available. | Portability test |
| GOVSCOPE-009 | P1 | A conversion capability shall not broaden the permitted use of its source data or representation. | Policy propagation test |
