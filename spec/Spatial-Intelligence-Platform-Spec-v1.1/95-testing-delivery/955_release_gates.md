---
spec_id: TST-GATE
title: "Release Gates and Promotion Evidence"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: true
---
# Release Gates and Promotion Evidence

    ## 1. Purpose

    Defines mandatory evidence for research, internal alpha, pilot, production, and enterprise release stages.

    This document is normative for the testing layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Each release stage has allowed data, users, claims, and operational controls.
- Production requires model/checkpoint license approval, not merely code build success.
- Quality, security, privacy, portability, backup, and rollback are equal release dimensions.
- A release record is signed and immutable.

    ## 3. Governing principles

    - Geometry claims are tested against independent ground truth rather than screenshots or subjective visual appeal.
- Every normative requirement maps to at least one automated test, controlled field procedure, review gate, or monitored production control.
- Test datasets include ordinary success cases and adversarial conditions such as mirrors, textureless walls, crowds, darkness, and repeated corridors.
- Release gates cover functionality, accuracy, privacy, licensing, reproducibility, security, and rollback.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                                                                                       | Verification            |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| TSTGATE-001 | P0       | Research release shall use authorized test data, explicit research labels, and no commercial/customer output from unapproved models.                                                              | Controlled verification |
| TSTGATE-002 | P0       | Pilot release shall define operating envelope, customer consent, support plan, measurement limitations, and rollback/export.                                                                      | Controlled verification |
| TSTGATE-003 | P0       | Production release shall pass all P0 requirements, vulnerability/SBOM/license review, benchmark thresholds, consent/truth-label tests, backup restore, migration, load, and acceptance scenarios. | Controlled verification |
| TSTGATE-004 | P1       | Enterprise release shall additionally pass tenant isolation, SSO/audit, retention/legal hold, DR, scale, and support controls.                                                                    | Controlled verification |
| TSTGATE-005 | P1       | Known limitations shall be included in release notes and UI where they affect use.                                                                                                                | Controlled verification |
| TSTGATE-006 | P1       | Rollback shall be rehearsed before production promotion.                                                                                                                                          | Controlled verification |

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

    - A versioned `tst_gate_manifest` recording identity, timestamps, ownership, state, and provenance.
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

## 15. Version 1.1 hybrid-representation release gate

A production hybrid capability requires a current provider/dependency approval, immutable provenance, use-specific geometry/interaction benchmarks, protected-region results, provider-policy tests, measurement and truth-label enforcement, vertical acceptance, open export, fallback, replacement, and rollback.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| TSTGATE-007 | P0 | A surface provider shall not enter production without current legal, privacy, security, reproducibility, and stratified benchmark approval. | Release review |
| TSTGATE-008 | P0 | Raycast, render, collision, navigation, occlusion, audio, and measurement suitability shall be gated independently. | Quality-profile test |
| TSTGATE-009 | P0 | Production promotion shall prove proxy authority restrictions in Construction and LiveForever end-to-end scenarios. | Acceptance test |
| TSTGATE-010 | P1 | Release evidence shall include native-hybrid comparison, open export/import, non-splat fallback, provider replacement, and rollback. | Release evidence audit |
| TSTGATE-011 | P1 | Known proxy gaps and prohibited uses shall appear in machine-readable limitations and applicable UI/report surfaces. | Documentation/UI test |
| TSTGATE-012 | P1 | A provider/license/terms change shall trigger re-review before subsequent production execution. | Governance test |

## Version 1.1 release gates

A provider, quality profile, or hybrid runtime cannot release until the purpose-specific tracks in [`961_splat_surface_benchmark_acceptance.md`](961_splat_surface_benchmark_acceptance.md) pass. Mandatory gates include provider/license/privacy approval, transform and geometry checks, anchor remapping, collision/navigation safety, truth/authority negative tests, hybrid rendering, malformed-input security, vertical scenarios, fallback, rollback, and independent export.
