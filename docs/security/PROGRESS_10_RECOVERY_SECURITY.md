# Progress 10 Recovery Security Design

## Threats

The bounded implementation addresses tampered archives, missing versions, stale manifests, cross-tenant restore, residency bypass, unauthorized key recovery, deletion resurrection, legal-hold bypass, partial purge, concurrent restore/purge, replay ambiguity, and migration authority inflation.

## Controls

- Immutable content hashes and complete preservation-package verification.
- Isolated generated restore targets and exact tenant/project lookup.
- Residency evaluation before recovery work.
- Re-verification immediately before restore.
- Reconciliation before write reopening.
- Project recovery locks for restore and purge.
- Independent purge approval and graph revalidation.
- Cryptographic-erasure and bounded residual evidence.
- Restore denial after completed deletion.
- Quorum key recovery with opaque references and no root-key disclosure.
- Additive migration and conservative authority ceilings.
- Denial/failure audit and outbox evidence.
- Production admission permanently denied without executed cloud/external recovery and later release authorization.

## Nonclaims

Local SQLite/CAS recovery proves only the deterministic reference profile. It is not managed PITR, object-versioning, multi-region, KMS, edge, external-witness, customer-data, or production recovery evidence.
