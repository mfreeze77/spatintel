---
spec_id: CON-SURV
title: "Existing-Condition Survey and As-Built Workflow"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: construction
normative: true
---
# Existing-Condition Survey and As-Built Workflow

    ## 1. Purpose

    Defines pre-planning, field capture, detail evidence, verification, review, publication, and limitations for building reference scans.

    This document is normative for the construction layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - The workflow has rapid context, detail, and verification passes.
- As-built status is granted only by project-defined accountable review, not by scan completion.
- Coverage gaps and inaccessible areas remain explicit.
- Measurements used for bid or installation can be flagged for field confirmation.

    ## 3. Governing principles

    - The platform distinguishes design intent, observed condition, verified as-built condition, and proposed work.
- A scan-derived dimension is never promoted to a contract dimension without field verification and an accountable verifier.
- Every device, panel, door, room, deficiency, RFI, test, and drawing reference can be spatially anchored and temporally versioned.
- Exports preserve open AEC interoperability rather than trapping owners in a proprietary viewer.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                                                  | Verification            |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------- |
| CONSURV-001 | P0       | The survey plan shall identify objectives, required rooms/systems, sensitive areas, control/measurement requirements, safety, permissions, and deliverables. | Controlled verification |
| CONSURV-002 | P0       | The app shall support room/area checklists and detail evidence for labels, panel interiors, ceiling conditions, pathways, and interfaces.                    | Controlled verification |
| CONSURV-003 | P0       | A survey review shall inspect coverage, tracking, registration, controls, object inventory, unanswered questions, and privacy restrictions.                  | Controlled verification |
| CONSURV-004 | P1       | Publishing as `verified_as_built` shall require named verifier, scope, date, method, exclusions, and signature/approval evidence.                            | Controlled verification |
| CONSURV-005 | P1       | The viewer shall visually distinguish inaccessible, unobserved, inferred, and verified regions.                                                              | Controlled verification |
| CONSURV-006 | P1       | A return visit shall compare against the exact prior accepted commit and preserve both visits.                                                               | Controlled verification |

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

    - A versioned `con_surv_manifest` recording identity, timestamps, ownership, state, and provenance.
- An immutable input reference set using content hashes rather than mutable storage paths.
- A result summary carrying status, warnings, confidence, metrics, and links to detailed artifacts.

    Every contract includes `schema_version`, `tenant_id`, `project_id`, `created_at`, `created_by`, a globally unique identifier, and a provenance reference. Coordinates include frame identifier, axis convention, handedness, units, and transform direction. Timestamps state their clock domain and synchronization quality. Numeric confidence values are accompanied by a definition and calibration version; an unexplained number between zero and one is not acceptable evidence.

    ## 7. Primary workflow

    1. Create survey plan and import available drawings/BIM/asset lists.
2. Perform safety, permission, device, profile, and calibration preflight.
3. Capture context loops with overlap and named room/area segments.
4. Perform detail passes for systems, labels, equipment, doors, ceilings, pathways, and anomalies.
5. Record verified dimensions/control, inaccessible areas, and unresolved questions.
6. Process preview, review quality, request recapture where practical, then process final.
7. Map entities, review measurements and source labels, and publish a scoped field-observation commit.
8. Optionally conduct accountable as-built verification and publish a separate verified commit.

    Each transition emits a durable domain event after the corresponding state change commits. Consumers are idempotent and tolerate redelivery. Large binary assets are transferred through signed, resumable object-storage operations; APIs exchange manifests and references rather than embedding multi-gigabyte payloads.

    ## 8. Provenance, confidence, and authority

    The capability must preserve a minimum lineage chain of: source capture or record → normalized input → algorithm/model and exact version → parameters → output hash → validation result → reviewer or automated publication decision. If any link is absent, the result is marked `provenance_incomplete` and is not eligible for verified or authoritative status.

    Authority is orthogonal to confidence. A high-confidence AI prediction remains inferred. A manually verified field measurement may be authoritative even when the scanner's confidence was low. The user interface must expose source class, verifier, verification time, and superseding revisions.

    ## 9. Security and privacy

    Sensitive building systems, security devices, network rooms, and access-control details receive elevated classification and scoped sharing.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: field revisit reduction, verified-object coverage, change detection precision, RFI cycle time, handoff completeness. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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
