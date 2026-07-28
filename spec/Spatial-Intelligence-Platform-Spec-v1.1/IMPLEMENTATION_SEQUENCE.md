---
spec_id: SIP-SEQ
title: "Implementation Sequence"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: testing
normative: true
---
# Implementation Sequence

| Phase | Focus | Epics | Exit outcome |
|---:|---|---|---|
| 0 | Governance and foundation | FND-001, GOV-001, GOV-002, FND-002 | Repo, CI, manifests, provider/data gates, local environment |
| 1 | Canonical data and control plane | DATA-001, DATA-002, IAM-001, CAP-001, PLT-001 | Secure immutable ingest and durable jobs |
| 2 | Capture | CAP-002 through CAP-006 | Polycam and first-party iOS packages |
| 3 | Metric and visual reconstruction | REC-001 through REC-006 | Aligned metric and visual scene assets |
| 4 | Scene core and hybrid data | SCN-001, DATA-003, REC-007 through REC-009, QA-003 scaffold | Stable entities, hybrid asset contracts, provider pipeline, benchmark fixtures |
| 5 | Scene intelligence and runtime | SCN-002, SCN-003, PLT-002 through PLT-004 | Searchable versioned scenes and hybrid interaction runtime |
| 6 | Vertical MVPs | CON-001 through CON-005, LIF-001 through LIF-004 | Construction and LiveForever hybrid experiences |
| 7 | Production readiness | OPS-001 through OPS-004, QA-001, QA-002 | Secure, recoverable, benchmarked release |
| 8 | Pilots | PILOT-001 | Evidence-based product launch decision |

## Critical-path principles

- Do not begin customer capture before canonical packages, retention, consent/policy, and safe export exist.
- Do not use LingBot output commercially before checkpoint approval; develop against research/synthetic fixtures behind a hard gate.
- Do not build automated semantic detection before stable entity/evidence contracts and manual review workflows exist.
- Do not call scans as-built until the authority/verification workflow exists.
- Do not add simulated LiveForever presence before preservation, consent, evidence labels, kill switch, and quiet mode exist.
- Do not launch before open export, backup restore, rollback, and both acceptance scenarios are demonstrated.
- Do not expose proxy geometry as a measurement or historical evidence surface.
- Do not send confidential building or private-family scenes to a manual/hosted provider until approval explicitly covers that data and purpose.
- Do not approve collision, navigation, occlusion, or audio use merely because a render proxy looks acceptable.
- Do not make SplatEdit or any one research extractor a mandatory dependency; preserve native hybrid and local fallback paths.

