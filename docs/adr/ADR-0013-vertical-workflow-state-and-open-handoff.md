# ADR-0013: Vertical workflow state and open handoff

## Status

Accepted for the Progress 06 development checkpoint.

## Context

Construction and LiveForever need domain-specific workflow state, but they must not create parallel authorities for identity, policy, evidence, scene history, or audit. Both verticals also require long-lived handoff and preservation outputs that remain usable without a proprietary hosted viewer.

## Decision

Construction and LiveForever retain their workflow-specific records in bounded logical services while canonical identity, policy, assets, evidence, spatial truth, scene history, and audit remain shared platform authorities. New schema is append-only in migration `0014_vertical_mvp`.

Both verticals produce open, independently verifiable handoff or preservation packages. Archive verification happens before trust or extraction. Vertical packages may not persist reusable credentials or broaden authority. Construction exports distinguish design, observed, inferred, measured, and verified state. LiveForever exports preserve truth labels, conflicts, consent, and generated-content lineage.

## Consequences

The first deployment may co-locate services, but ownership remains explicit in the service catalog. Full physical isolation, cloud deployment, field acceptance, and human-subject review remain external. No vertical may bypass server-side policy by hiding content in its client.

## Traceability

- Requirements: CONOVR-001, CONHAND-001, CONHAND-002, CONHAND-003, CONHAND-004, CONHAND-006, LIFOVR-001, LIFCONS-001, LIFPRESV-001, LIFPRESV-003, LIFPRESV-004, LIFPRESV-005, LIFPRESV-006
- Risks: confidential-facility disclosure, credential leakage, authority-label collapse, consent bypass, derivative revocation gaps, proprietary-viewer lock-in, malicious archive import
- Benchmarks: `build/evidence/demos/construction.json`; `build/evidence/demos/liveforever.json`; `build/evidence/demos/export.json`; `build/evidence/demos/restore.json`
- Source evidence: `src/sip/construction.py`; `src/sip/liveforever.py`; `src/sip/archive_safety.py`; `migrations/versions/0014_vertical_mvp.py`
- Exit/export strategy: Construction owner handoff and LiveForever preservation use open manifests, checksums, static offline viewers, and policy-scoped content without proprietary-service dependencies
- Security/privacy review: server-side tenant, project, purpose, audience, consent, classification, redaction, provider, retention, and archive-safety controls remain mandatory for every derivative and export
