---
spec_id: OPS-COST
title: "Cost, Capacity, and Unit Economics Model"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: operations
normative: true
---
# Cost, Capacity, and Unit Economics Model

    ## 1. Purpose

    Defines measurable cost attribution, capacity planning, pricing inputs, budget enforcement, and optimization without relying on volatile hard-coded cloud prices.

    This document is normative for the operations layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Cost is modeled by units and current price inputs, not fixed values embedded in domain logic.
- Every pipeline run estimates cost before admission and records actual resource consumption.
- Preview, standard, and archival/final profiles have distinct quality and cost envelopes.
- Storage and egress over years are treated as product economics, not incidental infrastructure.

    ## 3. Governing principles

    - Production operations are reproducible from versioned infrastructure and signed artifacts.
- Backups are not considered valid until restoration is demonstrated.
- Cost is attributed per tenant, project, capture, pipeline stage, GPU minute, and retained byte.
- Security and privacy incidents have predefined containment, evidence preservation, and notification playbooks.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                                                                                                             | Verification            |
| ----------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| OPSCOST-001 | P0       | The model shall attribute CPU seconds, GPU seconds by profile, memory, object bytes by tier, database/storage growth, requests, search/vector usage, CDN/egress, transcription/OCR/model API use, and support overhead. | Automated test          |
| OPSCOST-002 | P0       | Costs shall roll up by tenant, project, capture, run, stage, model, and calendar period.                                                                                                                                | Controlled verification |
| OPSCOST-003 | P0       | Admission control shall enforce project budgets, tenant quotas, concurrency, and anomaly detection.                                                                                                                     | Controlled verification |
| OPSCOST-004 | P1       | The UI shall show estimated cost/processing tier before optional expensive final reconstruction.                                                                                                                        | Controlled verification |
| OPSCOST-005 | P1       | Capacity plans shall use measured scene minutes/frames/area and peak concurrency with headroom.                                                                                                                         | Controlled verification |
| OPSCOST-006 | P1       | A price-source update shall be versioned and not change historical actual-cost records.                                                                                                                                 | Controlled verification |

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

    - `CostEstimate { profile, input_units, assumptions, price_book_version, estimated_range, expiry }`
- `UsageRecord { tenant, project, run, stage, resource_type, quantity, unit, region/provider, observed_at }`
- `CostAllocation { usage_record, price_book_version, amount, currency, tags }`

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

    Administrative access is just-in-time, strongly authenticated, logged, reviewed, and unavailable from normal end-user sessions.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: availability, mean time to recovery, restore success, cost per processed minute, security patch age. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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
