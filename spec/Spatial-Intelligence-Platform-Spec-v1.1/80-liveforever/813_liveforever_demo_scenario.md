---
spec_id: LIF-DEMO
title: "LiveForever Demonstration Scenario"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: liveforever
normative: true
---
# LiveForever Demonstration Scenario

    ## 1. Purpose

    Provides an end-to-end demonstration centered on a reconstructed family room and evidence-backed stories.

    This document is normative for the liveforever layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - The demo begins with preservation, not generation.
- The viewer can switch between direct current scan, historical reconstruction, and evidence view.
- One account has uncertainty and one has a respectful contradiction.
- Any optional voice/likeness simulation is isolated behind explicit consent and disclosure.

    ## 3. Governing principles

    - The person and family control consent, audience, inheritance, and posthumous use.
- Source memories, witness recollections, factual records, and generated reconstructions remain visibly distinct.
- Conflicting memories may coexist; the system does not force a false single narrative.
- Emotionally compelling presentation must never erase uncertainty, source limitations, or a person's right to remain private.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                              | Verification            |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------ | ----------------------- |
| LIFDEMO-001 | P0       | The subject shall create consent/audience settings, capture the room, scan a meaningful object, and record an interview. | Controlled verification |
| LIFDEMO-002 | P0       | The platform shall transcribe and anchor stories to the room/object while preserving source time ranges.                 | Controlled verification |
| LIFDEMO-003 | P0       | Old photographs shall be placed with method/uncertainty and shown in evidence view.                                      | Controlled verification |
| LIFDEMO-004 | P1       | A historical room element shall be reconstructed with visible source coverage and generated-gap labeling.                | Controlled verification |
| LIFDEMO-005 | P1       | A family contributor shall add an alternate recollection and the edition shall present both without overwriting either.  | Controlled verification |
| LIFDEMO-006 | P1       | The demo shall produce a private family share and an offline preservation export with different permissions.             | Controlled verification |

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

    - A versioned `lif_demo_manifest` recording identity, timestamps, ownership, state, and provenance.
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

    Biometric, voice, family, health, location, and intimate-memory data are treated as highly sensitive by default.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: source attribution coverage, consent completeness, unlabeled generation rate, family access incidents, preservation verification. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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

## Version 1.1 demonstration extension

The demo now includes a present-day splat and metric shell, hidden proxy/collision/navigation, stable story anchors, one historical reconstruction, one alternate recollection, truth/evidence view, quiet and reduced-motion modes, audience filtering, consent revocation, proxy regeneration, and offline preservation.
