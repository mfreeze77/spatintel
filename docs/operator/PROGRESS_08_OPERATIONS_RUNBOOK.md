# Progress 08 Operations and Incident Runbook

This runbook governs the bounded OPS-002 development milestone. It does not authorize production, Progress 09, raw-data support browsing, or safety-critical control. Every action uses an authenticated tenant/project context, a stable incident reference, a trace or operation identifier, and immutable audit/outbox evidence. Raw media, unrestricted transcript content, secrets, biometric material, private-family content, and restricted construction details are prohibited from ordinary incident notes.

## Common incident workflow

1. **Declare and classify.** Create an incident reference, severity, affected tenant/project scope, start time, correlation IDs, and the relevant resilience profile. Never infer an unauthorized tenant's existence from counts or errors.
2. **Contain.** Revoke affected grants or workload identities, stop unsafe publication, quarantine partial outputs, preserve immutable inputs, and activate the declared degraded behavior.
3. **Diagnose safely.** Use privacy-safe telemetry and customer-approved support bundles. Do not copy raw assets to unmanaged systems.
4. **Recover.** Resume only from verified checkpoints, validate object hashes and policy state, and reconcile reservations and actual cost.
5. **Validate.** Confirm authorization, data integrity, semantic identity, queue state, SLO recovery, and absence of leaked reservations.
6. **Communicate.** Use approved templates and audience scopes. Do not disclose another tenant, restricted resource, or sensitive value.
7. **Review.** Record an after-action review with findings, owners, due dates, requirement IDs, and executable regression tests.

Each incident action must retain the runbook reference, controlled command or operation, decision, evidence references, validation, rollback, communication, actor, and timestamp.

## Database outage

- **Trigger:** readiness failure, transaction errors, or failed database SLO.
- **Severity:** page when canonical writes are unavailable; ticket for bounded read-only degradation.
- **Containment:** fail closed for writes and authorization-sensitive reads. Do not switch to stale replicas for consent, policy, legal hold, or authority decisions.
- **Recovery:** restore connectivity or promote an approved database profile. Replay only idempotent operations and transactional outbox records.
- **Validation:** migration head, tenant isolation, audit chain, outbox drain, and SLO measurement.
- **Rollback:** return to the prior approved database endpoint and quarantine writes produced during an ambiguous interval.

## Object corruption or unavailable object store

- **Trigger:** post-write readback mismatch, missing immutable object, or checksum failure.
- **Severity:** page for evidence or source corruption; ticket for unavailable non-authoritative derivatives.
- **Containment:** quarantine affected outputs and prevent publication or export.
- **Recovery:** restore a verified immutable replica or regenerate a disposable derivative from verified inputs.
- **Validation:** plaintext hash, object metadata, tenant/project reference, derivation lineage, and preservation/export verification.
- **Rollback:** retain the prior published representation and supersession history.

## Queue backlog or broker failure

- **Trigger:** queue depth, p95 wait, retry, or dead-letter threshold.
- **Severity:** page for durable-job loss suspicion; ticket for bounded delay.
- **Containment:** stop nonessential admission, preserve reservations, and activate bounded metadata or viewer fallback.
- **Recovery:** restore the queue, rebalance approved workers, and resume from durable checkpoints.
- **Validation:** no duplicate execution, no reservation leakage, expected queue age, and operation/audit correlation.
- **Rollback:** cancel queued optional work and release its reservations.

## GPU failure, OOM, or preemption

- **Trigger:** compatibility denial, OOM disposition, worker heartbeat loss, or GPU health alert.
- **Severity:** ticket unless evidence integrity or cross-tenant isolation is implicated.
- **Containment:** terminate the isolated job; never silently reduce quality parameters.
- **Recovery:** resume from a verified checkpoint under a compatible pinned compute profile or explicitly select an approved fallback.
- **Validation:** checkpoint hash, model/checkpoint, container digest, tenant isolation, stage weights, and actual cost.
- **Rollback:** cancel and quarantine partial outputs while retaining immutable inputs.

## Model or reconstruction-quality regression

- **Trigger:** drift, coverage, residual, confidence, failed-region, or prior-version comparison alert.
- **Containment:** stop promotion, quarantine outputs, and retain the previous approved representation.
- **Recovery:** revert to an approved manifest/checkpoint or rerun with reviewed parameters.
- **Validation:** benchmark profile, quality thresholds, uncertainty, authority labels, and intended-use review.

## Cross-tenant access suspicion

- **Trigger:** tenant mismatch, unexpected authorization denial pattern, correlation spoof, or audit anomaly.
- **Severity:** page.
- **Containment:** revoke implicated grants and workload identities, stop exports and support access, and preserve evidence without broadening access.
- **Recovery:** only after independent security review confirms isolation.
- **Validation:** tenant/project policy checks, audit chain, access logs, object references, indexes, caches, exports, and support bundles.

## Leaked share link or support grant

- **Trigger:** reported link exposure, unexpected use, or scope mismatch.
- **Containment:** revoke immediately, invalidate cached capabilities, and deny bundle replay.
- **Recovery:** issue a new short-lived grant only after customer approval.
- **Validation:** old capability denied, new scope exact, audit and notification retained.

## Consent or audience-policy failure

- **Trigger:** derivative accessible after revocation, wrong audience, or policy dependency unavailable.
- **Containment:** fail closed across records, derivatives, indexes, caches, exports, and representations.
- **Recovery:** recompute policy and revoke stale derivatives.
- **Validation:** server-side authorization for every surface and a complete dependency scan.

## Bad redaction or sensitive telemetry

- **Trigger:** raw secret, transcript, biometric, restricted-facility detail, or unsafe high-cardinality field detected.
- **Containment:** stop export, revoke support bundle, and quarantine the telemetry record.
- **Recovery:** regenerate from approved low-cardinality metadata only.
- **Validation:** scrubber tests, archive manifest, no unchecked members, and timing/count non-disclosure.

## Deletion or retention error

- **Trigger:** deletion dependency mismatch, legal-hold conflict, residual derivative, or key-erasure failure.
- **Containment:** stop destructive action and preserve current evidence.
- **Recovery:** rerun the dry run against an unchanged dependency snapshot with verified backup and approval evidence.
- **Validation:** records, derivatives, indexes, caches, exports, backups, and cryptographic-erasure evidence.

## Backup or restore failure

- **Trigger:** restore rehearsal mismatch, missing object, audit-chain failure, or semantic identity drift.
- **Containment:** keep the active environment unchanged and mark the candidate restore invalid.
- **Recovery:** use the last verified backup or open preservation package.
- **Validation:** root hashes, database integrity, object decrypt/hash checks, audit chain, operations requiring reconciliation, and policy state.

## Game days and reviews

Synthetic game days shall exercise at least queue backlog, provider-region denial, GPU preemption, consent failure, and restore verification. An exercise is complete only when observations, participants, corrective requirements, owners, due dates, and executable tests are retained. A real staffed exercise remains external evidence.
