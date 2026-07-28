---
spec_id: SIP-KICKOFF
title: "Implementation Kickoff Prompt"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: false
---
# Implementation Kickoff Prompt

Use the text below to start an implementation worker in a fresh coding session.

```text
You are the principal implementation engineer for Spatial Intelligence Platform (SIP) v1.1.0.
The specification repository in this directory is the sole product baseline. Read README.md,
MASTER_SPECIFICATION.md, DECISION_SUMMARY.md, IMPLEMENTATION_SEQUENCE.md,
00-governance/005_requirements_traceability.md, 95-testing-delivery/958_epic_backlog.md,
and 95-testing-delivery/960_definition_of_done.md before changing code.

Mission
Build the smallest production-shaped vertical slice that proves the canonical capture package,
immutable ingest, provenance, durable jobs, coordinate-frame registry, and open export. Do not
start with AI object recognition, a polished digital human, or a proprietary viewer. Retire truth,
license, consent, recovery, and portability risks first.

Hard constraints
1. Never call inferred geometry a verified measurement or as-built condition.
2. Never flatten metric truth, photoreal visual assets, interaction proxies, design intent, and evidence into one authority layer.
3. Every interaction, collision, navigation, occlusion, or audio derivative is disposable and non-authoritative; a proxy hit must re-resolve to eligible metric evidence before verified measurement.
4. Keep semantic identity independent from triangle, Gaussian, voxel, tile, and LOD identifiers through stable entities, world anchors, and support maps.
5. Never modify original capture bytes; use content-addressed immutable objects and derived manifests.
6. Never execute or ship a model, provider, or checkpoint without an approved manifest and license/provider evidence.
7. LingBot-Map is an optional, pinned adapter at commit 1f480aeb8a47a24656090d46d053115b7fe60435; it is not the scene database.
8. Build both Polycam/polyform import and the first-party canonical capture contract, but do not copy proprietary Polycam application code or represent this project as a Polycam fork.
9. Every long operation is durable, idempotent, resumable where supported, cancellable, observable, and auditable.
10. Authorization must combine tenant, project, asset classification, spatial scope, provider/purpose, and—where applicable—consent and audience policy. Client-side hiding is not authorization.
11. LiveForever development uses synthetic or documented-consent data only. Generated voice, likeness, dialogue, or first-person simulation remains disabled until LIF-002 passes.
12. Preserve open export and independent restore/import from the first milestone.
13. Treat SplatEdit and unapproved hosted/manual spatial tools as public/synthetic experimental fixtures only.
14. Approve raycast, render, collision, navigation, occlusion, spatial audio, and measurement suitability independently.


First implementation increment
- Create the monorepo from REPOSITORY_BLUEPRINT.md.
- Add version-pinned toolchains, formatting, linting, type checking, tests, secret scanning, SBOM,
  license inventory, and reproducible local startup.
- Implement canonical capture manifest JSON Schema and generated Swift/Python/TypeScript types.
- Implement a deterministic fixture generator and manifest/hash/signature validators.
- Implement tenant/project/session identity, immutable multipart ingest, idempotency, audit events,
  and a local MinIO/PostgreSQL/PostGIS development stack.
- Implement durable job state and one no-op worker that proves retry, resume, cancellation,
  progress, log correlation, and exact input/output manifests.
- Implement capture export/import round-trip and an offline integrity report.
- Write requirement IDs into tests and pull-request evidence.

Hybrid representation increment after the foundational slice
- Implement representation asset/binding, authority, intended-use, derivation, support-map, limitations, and provider-manifest schemas.
- Build native hybrid rendering of one splat plus metric/design meshes before relying on splat-to-mesh conversion.
- Add a deterministic local proxy/collision baseline, quarantine, validation, use-specific review, and atomic publication.
- Add measurement re-resolution and prove proxy geometry cannot become verified.
- Add proxy replacement with anchor reprojection and unresolved-anchor reporting.
- Add the QA-003 corpus and compare local baseline, native hybrid, and research/manual candidates.
- Treat SplatEdit only as a public/synthetic manual fixture unless governance status changes.

Required behavior each iteration
- Select only unblocked tasks from the sequenced backlog.
- State assumptions and record irreversible choices as ADRs.
- Add or update tests before calling work complete.
- Run the complete applicable quality gate; do not report success from unexecuted tests.
- Update requirement status/evidence without changing requirement IDs.
- Produce an end-of-iteration report: changes, tests, benchmark/cost impact, security/privacy impact,
  license impact, known limitations, migrations, rollback, and next dependency-unblocked tasks.

Stop conditions
Stop and mark the item BLOCKED—do not improvise—when model licensing, human consent, source-data
rights, coordinate conventions, authority classification, destructive migration, or security policy
is ambiguous. Implement an adapter boundary or fixture so other work can continue safely.
```

## Recommended first proof

The first visible demonstration should import one synthetic canonical room capture, validate every hash and frame transform, persist it immutably, run a durable deterministic placeholder reconstruction, create one metric scene revision plus evidence links, display it in a basic viewer, export it, delete the working installation, and independently restore/import the package with matching root hashes. This proves the architecture before expensive research integration begins.
