# ADR-0001: Separate metric, visual, interaction, design, and evidence authority

- Status: Accepted
- Date: 2026-07-27
- Decision owners: scene-core, evidence-trust, product-safety

## Context

A photorealistic splat, simplified collision proxy, design model, and direct observation can occupy the same coordinates while carrying radically different evidentiary meaning. Stable scene identity cannot depend on triangles, Gaussians, voxels, tiles, or LOD identifiers.

## Decision

SIP stores metric, visual, interaction, design, and evidence representations as separate assets and bindings. Interaction geometry is disposable and capped at `derived_non_authoritative`. A proxy hit must re-resolve against eligible metric evidence before an authoritative measurement can be created. Stable semantic UUIDs and coordinate-aware anchors survive representation replacement.

## Consequences

Hybrid rendering is preferred over forced conversion. More storage and explicit review states are required, but visual plausibility cannot silently become metric authority.

## Traceability

- Requirements: ARCHHYB-001, ARCHHYB-006, ARCHHYB-014, DATHYB-004, RECHYB-002, CONMEAS-001
- Risks: RISK-PROXY-AUTHORITY-CONFUSION, RISK-PROTECTED-GEOMETRY-LOSS, RISK-ANCHOR-DRIFT
- Benchmarks: `build/reports/benchmark-report.json`
- Source evidence: `src/sip/representations.py`, `src/sip/scene.py`, `tests/integration/test_scene_representation.py`, `build/evidence/demos/hybrid/evidence.json`
- Exit/export strategy: representation contracts and preservation exports retain open asset types, coordinate frames, provenance, support maps, and historical commits; no proprietary viewer is required.
- Security/privacy review: this decision reduces authority and disclosure risk. Independent production security/privacy review remains external validation.
