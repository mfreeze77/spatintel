# Progress 06 Vertical MVP Architecture

## Scope and authority

Progress 06 composes the existing SIP control plane, evidence model, scene graph, policy engine, audit chain, preservation services, and hybrid representations into two bounded verticals: Construction Spatial Reference and LiveForever. The vertical services do not create a second identity, policy, asset, scene, or audit system. They retain vertical workflow state while delegating canonical identity, authorization, evidence, spatial truth, assets, and scene revisions to the shared platform.

This checkpoint is a development MVP. It does not make phone-derived geometry survey-grade, design geometry observed, generated memories factual, or consent revocable only in the UI. Production remains fail-closed.

## Logical service boundaries

`services/construction` owns vertical workflow records for surveys, field visits, document revisions, issues, commissioning, interchange, and owner handoff. `services/liveforever` owns governance, interviews, transcript layers, narrative editions, generated derivatives, and preservation releases. Both expose service-scoped OpenAPI documents and share only explicit platform records through typed identifiers.

The vertical tables introduced by migration `0014_vertical_mvp` are append-only schema additions. The migration does not alter revisions `0012` or `0013`. Recovery-only downgrade requires explicit enablement plus hash-addressed backup, dry-run, audit, and rehearsal evidence.

## Construction data flow

1. A survey plan binds objectives, places, systems, safety, permissions, measurement requirements, deliverables, and a baseline scene commit.
2. Each field visit binds source captures, checklist results, detail evidence, inaccessible regions, coverage, registration, controls, inventory, unresolved questions, privacy state, and the exact prior commit.
3. Review accepts or rejects the survey without rewriting visits. Inaccessible or unobserved regions remain limitations, never implicit absence.
4. System records represent fire alarm, access control, mechanical, electrical, and BAS entities using stable semantic IDs. Restricted topology and programming fields are server-side redacted.
5. Documents retain immutable source hashes and revisions. Page regions and spatial links identify exact evidence locations. Extracted values remain proposals until reviewed.
6. Issues retain evidence and state history. Correction, retest, and independently verified closure append history rather than erase the deficiency.
7. Commissioning retains procedures, prerequisites, steps, expected and actual results, participants, calibrated instruments, attachments, and acceptance. Credential material is rejected.
8. Interchange records retain IFC/BCF source identity, schema, units, CRS, owner history, GlobalIds, unsupported constructs, alignment residuals, mappings, and truth labels.
9. Owner handoff creates an open, checksummed, offline-readable package with inventory, reports, documents, tests, warranties, training, exclusions, limitations, and representation manifests.

## LiveForever data flow

1. Consent and governance records bind authority basis, subject/data scope, purpose, modality, audience, provider, geography, expiration, posthumous rules, evidence, successors, disputes, and high-risk freezes.
2. Stable graph records represent people, relationships, places, objects, events, memories, media, and stories. Approximate time and place use bounded or qualitative uncertainty.
3. Interviews retain participants, consent context, recording state, exact media and time ranges, environment, interruptions, pacing, and question lineage.
4. Transcript corrections add an edited reading layer and retain the original media and transcript. Family corrections create new memory revisions with provenance and never overwrite testimony.
5. Conflicting recollections remain parallel, source-labeled records. Majority vote is not treated as factual proof.
6. Narrative editions bind exact record revisions, scene commits, policy snapshots, truth legends, and presentation choices.
7. Generated derivatives remain denied by default for voice, likeness, dialogue, first-person simulation, and autonomous persona. Approved visual reconstruction remains generated and lineage-labeled.
8. Revocation freezes new processing and marks affected derivatives and records for access restriction or deletion review.
9. Preservation releases include originals, technical metadata, rights and consent, transcripts, graph data, scene manifests, open assets, fixity, replicas, migration history, succession, shutdown policy, and a static offline viewer.

## Archive and export safety

Construction handoff and LiveForever preservation use `src/sip/archive_safety.py`. ZIP validation rejects traversal, absolute or drive paths, backslashes, duplicate entries, symlinks, nonregular members, oversized members, aggregate expansion abuse, and suspicious compression ratios before extraction or trust.

## Determinism and idempotency

Mutating vertical workflows use tenant/project-scoped idempotency keys where a retry could otherwise duplicate durable state. Requests are hashed canonically. Reusing a key with different input is rejected. Deterministic reports and package manifests derive stable identity from retained source records rather than wall-clock generation time.

## External validation boundaries

The local reference implementation does not claim physical iPhone/LiDAR acceptance, complete IFC/BCF vendor interoperability, approved LingBot model execution, CUDA/GPU performance, browser accessibility certification, cloud deployment, independent penetration testing, privacy/legal approval, customer pilots, construction code compliance, or survey certification.
