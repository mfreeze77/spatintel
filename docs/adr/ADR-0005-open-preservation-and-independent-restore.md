# ADR-0005: Open preservation export and independent restore

- Status: Accepted
- Date: 2026-07-27
- Decision owners: preservation, evidence-trust, privacy

## Context

Long-lived construction records and family memories must remain usable after a provider, deployment, viewer, or company disappears. Backup alone is not an open preservation strategy.

## Decision

SIP exports content-addressed source and derivative assets, canonical JSON manifests, coordinate frames, semantic identities, provenance, consent/audience policy, revisions, and integrity roots in an openly documented package. Restore occurs into a clean store, re-encrypts for the target, verifies every hash, and proves semantic identity without requiring proprietary services.

## Consequences

Exports may be larger and policy-aware restore is more complex. The package remains independently verifiable and supports cryptographic erasure and derivative invalidation rules.

## Traceability

- Requirements: DATEXP-001, DATEXP-004, OPSBKP-004, ARCADR-002, GOVPRIN-005
- Risks: RISK-PROVIDER-LOCK-IN, RISK-DERIVATIVE-REDACTION
- Benchmarks: `build/evidence/demos/foundation/evidence.json`
- Source evidence: `src/sip/exporting.py`, `src/sip/lifecycle.py`, `tests/integration/test_export_restore.py`, `docs/operator/BACKUP_RESTORE.md`
- Exit/export strategy: this ADR is the exit strategy; formats, hashes, policy, and identity are included in the package and validated by a clean restore.
- Security/privacy review: exports preserve policy and require authorization/encryption. Recipient governance and independent privacy assessment remain deployment-specific.
