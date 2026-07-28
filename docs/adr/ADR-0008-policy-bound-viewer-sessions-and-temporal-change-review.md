# ADR-0008: Policy-bound viewer sessions and governed temporal change review

- Status: Accepted
- Date: 2026-07-28
- Decision owners: Scene Platform, Security, Product, QA

## Context

A saved spatial view must be reproducible without becoming a reusable authorization capability. Temporal change detection must preserve the exact scene commits, evidence, registration quality, coverage, thresholds, algorithm lineage, and uncertainty that produced a candidate. A visual difference cannot become semantic truth merely because an automated detector or interaction proxy reported it.

## Decision

SIP persists immutable viewer-session state separately from short-lived view bindings. Saved sessions contain scene commits, camera and navigation state, representation roles, clipping and section state, selection, timeline, filters, redaction, and accessibility preferences, but reject bearer tokens, signed URLs, storage keys, and provider credentials. Replay always reauthorizes server-side and returns newly issued transient bindings.

Temporal comparisons are durable records. Unobserved regions cannot be classified as removed. LOD, lighting, exposure, dynamic-object, and missing-coverage differences are suppressed or retained explicitly for review. An independent reviewer must decide active candidates before an accepted candidate may create a semantic change event. Applying accepted events is a separate, optimistic-concurrency-controlled scene commit. Desktop review exports remain proposals and cannot directly publish authoritative state.

## Consequences

The platform can reproduce review context without turning a saved session into an authorization bypass. Change history remains explainable and reversible. More storage and workflow steps are required, and automated change detection cannot silently mutate the scene graph. Browser/GPU behavior, native desktop packaging, physical-device capture, and human accessibility/usability acceptance remain separate evidence gates.

## Traceability

- Requirements: PLTVIEW-001, PLTVIEW-003, PLTVIEW-005, RECCHANG-001, RECCHANG-002, RECCHANG-003, RECCHANG-004, PLTDESK-001, PLTDESK-003, PLTDESK-005, PLTDESK-006, DATGIT-004
- Risks: unauthorized replay, capability persistence, false removals from missing coverage, detector self-approval, silent semantic mutation, offline-review overwrite
- Benchmarks: `build/evidence/demos/scene-runtime.json`; `build/reports/benchmark-report.json`; per-class change benchmark records
- Source evidence: `src/sip/scene_runtime.py`; `src/sip/desktop_review.py`; `apps/web/components/HybridCanvas.tsx`; `migrations/versions/0012_scene_runtime_review.py`
- Exit/export strategy: viewer sessions are JSON-compatible state; desktop bundles and proposals are open JSON plus content-addressed inputs; semantic history remains in Spatial Git commits and open preservation exports
- Security/privacy review: server-side policy is re-evaluated on replay and evidence access; capability-shaped material is rejected; local HTTP is loopback, Host, Origin, JSON, and CSRF constrained
