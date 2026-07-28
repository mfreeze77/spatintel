# Operations Incident Runbooks

These runbooks are executable control procedures for SIP incidents. They supplement the first-response rules in `docs/operator/INCIDENT_RESPONSE.md` and the telemetry-specific procedure in `docs/runbooks/OBSERVABILITY_INCIDENTS.md`.

## Common incident record

Every invocation must record the trigger and detection source, severity, incident commander, security/privacy/legal/communications roles, exact release and deployment revision, affected tenant-safe scope, start and containment times, commands or control-plane actions used, decision points, retained evidence hashes, validation results, rollback or recovery result, communications, and follow-up owner. Never copy raw evidence, credentials, transcripts, biometric media, restricted coordinates, or unrestricted tenant/project identifiers into an incident record.

The following controls apply to every runbook:

1. Preserve audit roots, trace and operation identifiers, relevant object hashes, clocks, and configuration hashes before changing state.
2. Stop publication and destructive automation whenever authority, consent, custody, or tenant isolation may be affected.
3. Use supported kill switches, revocations, quarantine, rollback, restore, and reconciliation paths; never edit durable state directly.
4. Validate recovery with a negative test and an integrity check, not only disappearance of an alert.
5. Retain the reviewed decision, evidence, and communications record before closure.

## Database outage

**Trigger and severity:** failed readiness, connection exhaustion, corruption signal, replication/PITR alarm, or elevated database error rate. Treat possible corruption or cross-tenant query behavior as critical.

**Roles:** incident commander, database operator, service owner, security lead when integrity or isolation is uncertain, and communications owner.

**Controls and decisions:** remove unhealthy workloads from service; pause publication and deletion; inspect connection saturation and migration state; select retry, failover, point-in-time recovery, or isolated restore according to the verified recovery point; never downgrade a released migration ad hoc.

**Evidence and validation:** retain database logs without sensitive row data, migration head, backup identifiers and hashes, restore transcript, integrity check, outbox reconciliation, audit-chain verification, and representative tenant-isolation queries.

**Rollback and communications:** roll back application only within its tested schema compatibility window. Communicate data-loss bounds and unavailable functions plainly.

## Object corruption or loss

**Trigger and severity:** ciphertext hash mismatch, missing object, decryption/authentication failure, root-manifest mismatch, or replication alarm. Treat evidence loss as critical.

**Roles:** incident commander, object-storage operator, evidence/custody owner, security lead, and communications owner.

**Controls and decisions:** quarantine the affected object/reference; stop derivative publication; identify all dependency edges; restore from an independently verified backup or preservation package; do not replace bytes under an existing content identity.

**Evidence and validation:** retain expected and actual hashes, storage-version identifiers, key version, dependency graph, restore source and root, independent decrypt/hash verification, and derivative invalidation/rebuild record.

**Rollback and communications:** preserve the corrupted version for forensics where lawful. Report any unresolved evidence gap and affected derivative set.

## Queue backlog or stuck workflow

**Trigger and severity:** queue delay or depth over policy, zero completion with active demand, repeated lease expiry, or reconciliation lag.

**Roles:** workflow owner, worker owner, cost-capacity owner, and incident commander.

**Controls and decisions:** inspect durable operation state, leases, checkpoints, retry classes, cancellation, tenant fairness, quotas, and provider/model admission; scale only the affected immutable worker identity; never bypass cost, purpose, region, or consent policy.

**Evidence and validation:** retain queue and inflight metrics, operation/lease IDs, checkpoint sequence, resource pressure, scaling decision, and proof that retries did not create competing publication effects.

**Rollback and communications:** return durable queued or policy-blocked status instead of fabricated progress. Reconcile expired leases through the supported command.

## GPU or reconstruction-worker failure

**Trigger and severity:** GPU OOM/reset, device loss, sandbox denial, non-finite output, pose collapse, model mismatch, or repeated worker failure.

**Roles:** worker owner, reconstruction quality owner, security lead for sandbox/model violations, and incident commander.

**Controls and decisions:** quarantine input and staged output; verify signed lease, manifest digest, model/checkpoint hash, driver/runtime profile, resource envelope, and latest safe checkpoint; use an approved CPU/reference fallback where supported; do not increase privileges or publish manually.

**Evidence and validation:** retain input/output hashes, worker receipt, model/provider dossier identifiers, environment and container digest, failure class, quality metrics, and rerun comparison against the approved benchmark profile.

**Rollback and communications:** retain the prior scene commit and representation. State explicitly when no metric or visual output is available.

## Model or quality regression

**Trigger and severity:** drift, coverage, residual, confidence, seam, benchmark, hallucination, truth-label, or safety metric crosses its approved threshold.

**Roles:** quality reviewer, model owner, product safety/privacy owner as applicable, and incident commander.

**Controls and decisions:** revoke or suspend the exact model/checkpoint/provider manifest; stop publication; compare the same fixture/profile against the prior approved version; separate metric, visual, interaction, and design impacts; never promote visually convincing output to verified authority.

**Evidence and validation:** retain model lineage, seed, parameters, inputs, outputs, benchmark threshold and result, source coverage, reviewer decision, and replacement-candidate receipt.

**Rollback and communications:** restore the last approved representation/scene commit and disclose any unresolved anchors or degraded capabilities.

## Suspected cross-tenant access

**Trigger and severity:** any object, search result, signed URL, cache, log, worker input, export, or notification appears accessible outside its authorized tenant/project scope. Always critical.

**Roles:** security incident commander, privacy/legal owners, affected service owner, evidence custodian, and communications owner.

**Controls and decisions:** disable the affected route/provider/share mechanism; rotate relevant credentials and signing keys; preserve audit and access logs; quarantine caches, indexes, exports, and staged derivatives; do not rely on client-side hiding.

**Evidence and validation:** retain authorization inputs and decisions in pseudonymous form, affected object/reference hashes, signed-token claims, cache/index invalidation evidence, cross-tenant negative tests, and forensic timeline.

**Rollback and communications:** restore only after independent object-authorization and leakage tests pass. Follow legal notification decisions without speculative claims.

## Leaked share link, credential, or workload identity

**Trigger and severity:** exposed signed URL, API credential, key material, refresh token, or workload credential.

**Roles:** security incident commander, identity/key owner, affected service owner, and communications owner.

**Controls and decisions:** revoke the link/credential and current sessions; rotate impacted key material; shorten or disable the affected share class; inspect audit usage and downstream downloads; reauthorize historical links against current policy.

**Evidence and validation:** retain token identifier and scope without secret material, issuance/revocation times, access timeline, rotation record, and denial test after revocation.

**Rollback and communications:** do not re-enable until the leakage source is fixed and dependent caches are invalidated.

## Consent, audience, or third-party protection failure

**Trigger and severity:** revoked/expired consent remains accessible, wrong edition exposure, minor/living-third-party protection failure, or generated voice/likeness/dialogue executes without approval. Treat exposure as critical.

**Roles:** privacy incident commander, consent/policy owner, legal owner, product safety owner, and communications owner.

**Controls and decisions:** activate relevant kill switches; block affected editions and exports; invalidate derivatives, indexes, caches, notifications, and representations; preserve source and policy history under legal/retention rules.

**Evidence and validation:** retain grant/revocation identifiers, purpose/scope/audience, policy decision traces, dependency graph, invalidation results, negative access tests for private/family/public editions, and generated-content lineage.

**Rollback and communications:** restore only with current valid consent and explicit review. Never rewrite conflicting recollections or consent history.

## Bad redaction or topology disclosure

**Trigger and severity:** sensitive building systems, restricted regions, people, documents, metadata, or topology remain visible in a derivative or export.

**Roles:** security/privacy lead, construction or LiveForever domain owner, export/search owner, and incident commander.

**Controls and decisions:** withdraw the derivative/export; invalidate all derived caches/indexes; determine whether source policy, transform, cleanup, tiling, viewer, or export omitted restrictions; do not treat presentation hiding as authorization.

**Evidence and validation:** retain source policy and region IDs, derivative lineage, before/after hashes, negative retrieval/render/export tests, and reviewer approval.

**Rollback and communications:** use a newly derived asset with a new identity; preserve the affected version for audit where lawful.

## Destructive deletion error

**Trigger and severity:** deletion without dry run/backup/two-person approval, wrong dependency set, legal-hold conflict, residual plaintext/ciphertext, or unverifiable cryptographic erasure. Critical.

**Roles:** incident commander, evidence/retention owner, security/privacy/legal owners, storage operator, and communications owner.

**Controls and decisions:** stop all deletion jobs; place affected scope under hold; preserve deletion plan, approvals, snapshot, backup, tombstones, and key-destruction records; restore only through the verified backup/preservation path where policy permits.

**Evidence and validation:** follow `docs/runbooks/CONTROLLED_DELETION.md`; retain dry-run graph, unchanged-snapshot check, approver identities, object/key results, residual-backup deadlines, restore test, and audit-chain verification.

**Rollback and communications:** state irrecoverable loss honestly; do not synthesize missing evidence or claim erasure without proof.

## Backup, restore, or disaster-recovery failure

**Trigger and severity:** backup missing/corrupt, restore root mismatch, RPO/RTO breach, unreconciled operations, or inability to restore independently.

**Roles:** recovery lead, database/object operators, service owner, security/evidence custodian, and communications owner.

**Controls and decisions:** isolate the restore environment; verify manifests before import; restore database and objects to a matched point; rewrap keys as required; reconcile outbox and durable operations; never overwrite the only surviving backup.

**Evidence and validation:** retain source backup/export identifiers, file/root hashes, environment, restore transcript, database integrity, object decrypt/hash checks, audit-chain result, semantic identity comparison, and measured RPO/RTO.

**Rollback and communications:** keep production read-only or unavailable until integrity and authorization checks pass.

## Malicious parser payload or archive bomb

**Trigger and severity:** path traversal, decompression ratio/entry-count/size limit, parser crash, future-schema ambiguity, geometry exploit, or unexpected network/filesystem activity. Treat sandbox escape evidence as critical.

**Roles:** security incident commander, parser/worker owner, and evidence custodian.

**Controls and decisions:** quarantine bytes immutably; deny publication; revoke affected parser image/provider version; run only in the bounded no-network sandbox; do not inspect private payload through consumer desktop tools.

**Evidence and validation:** retain input hash, rejection code, resource-limit evidence, sandbox receipt, parser/version/container digest, and adversarial regression fixture when lawful.

**Rollback and communications:** return a safe rejection without exposing parser internals or source contents.

## Immersive collision, navigation, or safe-exit failure

**Trigger and severity:** collision proxy misses unsafe geometry, navigation crosses restricted/unsafe space, motion/accessibility control fails, or quiet mode/safe exit does not work.

**Roles:** product safety owner, interaction/representation owner, accessibility reviewer, and incident commander.

**Controls and decisions:** disable the immersive experience or affected navigation mode; retain the last approved proxy; separate interaction failure from metric truth; do not substitute visual splats for collision authority.

**Evidence and validation:** retain scene/proxy versions, anchor and unresolved-anchor reports, collision/navigation tests, device/runtime profile, accessibility settings, and safe-exit verification.

**Rollback and communications:** provide a non-immersive accessible fallback and disclose the disabled capability.
