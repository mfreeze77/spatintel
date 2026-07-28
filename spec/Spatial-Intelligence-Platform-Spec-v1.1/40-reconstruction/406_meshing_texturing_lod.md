---
spec_id: REC-MESH
title: "Meshing, Texturing, and Level of Detail"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: reconstruction
normative: true
---
# Meshing, Texturing, and Level of Detail

    ## 1. Purpose

    Defines metric and visual mesh products, UV/texturing, semantic boundaries, decimation, tiles, and browser delivery.

    This document is normative for the reconstruction layer. It defines behavior that must remain stable even when implementation libraries, models, cloud providers, or user interfaces change. The design favors explicit evidence and reversible decisions over hidden automation.

    ## 2. Outcomes

    - Metric mesh and presentation mesh are separate assets.
- Texture selection can use original frames, exposure correction, occlusion checks, and privacy masks while preserving source references.
- LOD generation is spatially stable and does not alter entity anchors.
- Large scenes are tiled for streaming and can export to glTF/GLB, OpenUSD, and 3D Tiles profiles.

    ## 3. Governing principles

    - Learned geometry is a hypothesis with confidence, not a measurement by default.
- Metric scale is anchored by calibrated sensors, control points, fiducials, or verified dimensions.
- Long-sequence drift is corrected outside LingBot-Map through cross-session registration, loop constraints, and factor-graph optimization.
- Metric, visual, interaction, and evidence representations are generated separately but registered to common coordinate frames.

    ## 4. Normative requirements

    | ID          | Priority | Requirement                                                                                                                   | Verification            |
| ----------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| RECMESH-001 | P0       | Every mesh shall declare source volume/point set, coordinate frame, units, topology metrics, processing operations, and hash. | Automated test          |
| RECMESH-002 | P0       | Decimation shall be evaluated for surface error and preservation of protected semantic edges and anchor regions.              | Controlled verification |
| RECMESH-003 | P0       | Texturing shall avoid using redacted or unauthorized frames for broader-access derivatives.                                   | Controlled verification |
| RECMESH-004 | P1       | Viewer LOD switches shall not change measurement results, which are computed from approved metric geometry.                   | Controlled verification |
| RECMESH-005 | P1       | Tiling shall preserve stable global coordinates and entity-to-tile mappings.                                                  | Controlled verification |
| RECMESH-006 | P1       | Exports shall include provenance sidecars when the target format cannot carry SIP metadata.                                   | Controlled verification |

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

    - A versioned `rec_mesh_manifest` recording identity, timestamps, ownership, state, and provenance.
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

    Workers execute untrusted captures in isolated jobs with bounded resources and immutable input mounts.

    Data is minimized for the task, encrypted in transit and at rest, and separated by tenant. Sensitive scene regions may have more restrictive permissions than the surrounding project. Logs contain identifiers and outcomes but not raw photographs, transcripts, biometric templates, secrets, or precise security-system details unless an approved diagnostic mode is active.

    ## 10. Failure handling

    - Invalid or incomplete inputs are rejected before expensive work starts.
- Recoverable interruptions resume from a verified checkpoint rather than replaying accepted work.
- Low-confidence output is quarantined for review and cannot silently become authoritative.
- Partial writes are rolled back or marked incomplete; they are never returned as successful revisions.

    Every failure has a stable machine-readable code, user-safe explanation, operator diagnostic context, retry classification, and remediation link. Retries use exponential backoff and bounded attempts. Non-deterministic model failures preserve the failed run manifest to support investigation without falsely presenting the run as reproducible.

    ## 11. Observability and performance

    Required operational measures include: absolute trajectory error, surface distance error, completeness, cross-window seam error, pipeline reproducibility. Metrics are segmented by tenant, project, capture source, hardware profile, algorithm/model version, and software release when cardinality is safe. Traces carry a correlation identifier from API request through events, worker jobs, storage operations, and publication.

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

## 15. Version 1.1 interaction derivatives

Mesh production now distinguishes metric surfaces, visual meshes, interaction proxies, collision volumes, navigation surfaces, occlusion hulls, and preservation fallbacks. A render mesh is not automatically suitable for physics or navigation. Each derivative has a role, authority ceiling, intended-use validation, support map, and limitations statement.

Protected semantic regions—including doors, stairs, rails, panels, devices, thin conduit/piping, meaningful LiveForever objects, and privacy regions—participate in repair, decimation, and LOD tests. Remeshing that cannot preserve an anchor produces an unresolved-anchor report rather than silently moving the annotation.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| RECMESH-007 | P0 | Metric, visual, interaction, collision, navigation, occlusion, and preservation meshes shall use distinct roles and authority ceilings. | Schema/policy test |
| RECMESH-008 | P0 | A render mesh shall not be approved for collision or navigation without separate profile-specific validation. | Acceptance test |
| RECMESH-009 | P0 | Repair, decimation, and LOD shall test protected construction, memory, safety, and privacy regions. | Benchmark test |
| RECMESH-010 | P1 | Every remesh shall generate support-map results and identify unresolved semantic anchors. | Remesh regression test |
| RECMESH-011 | P1 | Collision/navigation derivatives shall be replaceable without replacing the visual or metric source. | Component test |
| RECMESH-012 | P1 | Mesh exports shall include role, authority, intended-use, limitations, transform, and derivation sidecars. | Export/import test |

## Version 1.1 role separation

Meshing now produces typed derivatives rather than a generic final mesh. Metric, visual, interaction, collision, navigation, occlusion, and preservation outputs are independently versioned and validated. Splat-derived surfaces follow [`415_splat_surface_hybrid_representation.md`](415_splat_surface_hybrid_representation.md), provider execution follows [`416_splat_surface_provider_contract.md`](416_splat_surface_provider_contract.md), and cleanup/LOD behavior follows [`418_splat_editing_cleanup.md`](418_splat_editing_cleanup.md).
