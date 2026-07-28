---
spec_id: GOV-RISK
title: "Program Risk Register"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---
# Program Risk Register

    ## 1. Purpose

    Defines risk categories, scoring, mitigations, triggers, contingencies, and review cadence for the platform program.

    This document is normative for the governance layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Risks are scored by probability, impact, detectability, and time-to-harm.
- Top risks include geometry overclaim, model licensing, privacy exposure, loss of original evidence, drift, cross-tenant access, generated-memory confusion, and unsustainable GPU cost.
- Mitigations must be observable controls, not statements of intent.
- Accepted risks include named executive and technical owners plus review dates.

    ## 3. Governing principles

    - Every decision must be traceable to a requirement, risk, experiment, or external constraint.
- No inferred geometry, generated memory, or AI label may silently replace source evidence.
- Commercial release is blocked when code, model-weight, dataset, or transitive-license evidence is incomplete.
- Normative requirements use deterministic identifiers and measurable verification methods.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                               | Verification            |
| ----------- | -------- | --------------------------------------------------------------------------------------------------------- | ----------------------- |
| GOVRISK-001 | P0       | The risk register shall link each critical risk to requirements, tests, monitors, and incident playbooks. | Controlled verification |
| GOVRISK-002 | P0       | A risk score increase into the critical band shall trigger release review within one business day.        | Controlled verification |
| GOVRISK-003 | P1       | Known safety or consent failures shall not be reclassified as ordinary quality defects.                   | Controlled verification |
| GOVRISK-004 | P1       | Risk acceptance shall expire and require renewal based on current evidence.                               | Controlled verification |
| GOVRISK-005 | P1       | Closed risks shall retain closure evidence and residual-risk assessment.                                  | Controlled verification |

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

    - A versioned `gov_risk_manifest` recording identity, timestamps, ownership, state, and provenance.
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

## 15. Version 1.1 hybrid-representation risks

New critical risks include false confidence from photorealism, proxy geometry being mistaken for metric truth, missing doors/stairs/thin systems, unsafe immersive collision/navigation, semantic anchor loss after remeshing, external-provider egress or retention, transitive research-license exposure, privacy redaction failing to propagate, and dependence on an unavailable proprietary/manual tool.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| GOVRISK-006 | P0 | The risk register shall track proxy-authority confusion, provider data egress, protected-geometry loss, anchor drift, immersive safety, derivative redaction, and provider lock-in. | Risk review |
| GOVRISK-007 | P0 | Critical hybrid risks shall have automated gates or explicit fail-safe modes rather than relying only on user training. | Control audit |
| GOVRISK-008 | P1 | Provider and algorithm risks shall be stratified by scene class and intended use, not represented by one global quality rating. | Benchmark/risk audit |
| GOVRISK-009 | P1 | A provider revocation or failure shall have a tested local/native-hybrid fallback and impact-analysis procedure. | Game-day test |
