# Progress 10 Recovery Operations Runbook

## Scope

This runbook covers the bounded OPS-004 development implementation for local recovery points, isolated restores, recovery objectives, key-recovery exercises, portability fallbacks, fixity checks, and synthetic recovery game days. It does not certify production, cloud, multi-region, physical-edge, or customer-data recovery.

## Evidence classes

Every recovery record declares one of `synthetic`, `local_controlled`, `local_executed`, `cloud_executed`, or `external_witnessed`. The reference implementation creates only `local_executed` recovery points. Cloud and external classes require independently retained evidence and cannot be asserted by callers.

## Recovery point procedure

1. Confirm the active deployment profile and residency policy.
2. Register data/service-class RPO, RTO, degraded behavior, and recovery method.
3. Create a recovery point with an immutable idempotency key and positive immutability period.
4. Verify the preservation package SHA-256 and root hash, SQLite snapshot SHA-256 and integrity, object manifest root, configuration hash, audit head, queue manifest, and key references.
5. Do not treat a point as restorable until state is `verified`.

## Restore procedure

1. Select the latest verified point at or before the requested time.
2. Use an isolated platform-generated target tenant and project for clone and portability rehearsals.
3. Enforce the active residency policy before opening the package.
4. Verify the recovery point again immediately before import.
5. Reconcile package root, database references, object bytes, audit chronology, queue state, configuration, and unresolved references.
6. Reopen writes only when `blocking_findings` is empty.
7. Retain measured RPO/RTO and exact output identities.

Ordinary restore fails closed when the chosen recovery point predates an executed purge, preventing deleted information from being resurrected.

## Key recovery

Key recovery requires an opaque `vault://`, `kms://`, or governed recovery-asset reference, at least two approved guardians meeting the registered quorum, and evidence that the ordinary operator did not receive the root key. Root-key exposure is prohibited.

## Recovery game days

Synthetic/local game days must retain affected services, region, timeline, measured RPO/RTO, findings, exact recovery point, and a verified complete portability package. Local evidence must not be represented as cloud or production certification.

## External gaps

Credentialed database PITR, object-version restore, multi-region loss, KMS ceremony, physical edge recovery, external witnessing, and production certification remain external validation requirements.
