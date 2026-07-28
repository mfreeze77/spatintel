---
spec_id: PLT-REST
title: "REST Resource API"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: platform
normative: true
---
# REST Resource API

    ## 1. Purpose

    Defines the initial external API for tenants, projects, captures, assets, jobs, scenes, entities, evidence, search, reviews, exports, and consent.

    This document is normative for the platform layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - REST is the primary client/control API; worker streaming uses separate internal protocols.
- Binary upload/download uses signed URLs or local transfer endpoints after authorization.
- Scene publication and destructive operations use explicit commands and operation resources.
- OpenAPI is generated and checked against implementation.

    ## 3. Governing principles

    - Public APIs are resource-oriented, idempotent where possible, and carry explicit schema versions.
- Long-running work is asynchronous, observable, cancellable, retryable, and safe to resume.
- Agents may propose changes but only constrained tools can commit authoritative scene mutations.
- Viewer behavior is deterministic enough to reproduce what an auditor or family member saw at a recorded time.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                                                           | Verification            |
| ----------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| PLTREST-001 | P0       | The API shall provide create/read/list/update operations for projects, places, captures, entities, assertions, evidence, tasks, and consent where policy permits.     | Automated test          |
| PLTREST-002 | P0       | The API shall provide operations for finalize capture, start pipeline, cancel job, publish scene commit, compare commits, request review, export, redact, and delete. | Automated test          |
| PLTREST-003 | P0       | Search shall accept structured spatial/temporal/source filters and return explanation/provenance summaries.                                                           | Controlled verification |
| PLTREST-004 | P1       | Asset URLs shall be short-lived, scoped to exact object/action, and audited for sensitive classes.                                                                    | Controlled verification |
| PLTREST-005 | P1       | The API shall expose operation progress, warnings, outputs, quality, cost attribution, and terminal errors.                                                           | Automated test          |
| PLTREST-006 | P1       | Bulk endpoints shall be bounded, transactional where promised, and return per-item outcomes.                                                                          | Controlled verification |

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

    - `POST /v1/projects/{project_id}/capture-sessions` and `POST .../{session_id}:finalize`.
- `POST /v1/projects/{project_id}/pipeline-runs` with profile and immutable input manifest.
- `GET /v1/scenes/{scene_id}/commits/{commit_id}` and `POST ...:publish`.
- `POST /v1/search` for permission-aware multimodal/spatial retrieval.
- `POST /v1/exports` and `GET /v1/operations/{operation_id}`.

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

    API authorization combines tenant role, project role, asset classification, consent, and spatial scope.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: API error budget, queue age, viewer frame time, search relevance, tool-call rejection rate. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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

## Version 1.1 API surface

Representation operation, candidate review, validation, publication, supersession, retirement, provider promotion, support-map reattachment, and audience-filtered hybrid scene-view endpoints are defined in [`614_splat_surface_api_and_events.md`](614_splat_surface_api_and_events.md). They inherit the platform's authorization, idempotency, audit, error, and compatibility rules.
