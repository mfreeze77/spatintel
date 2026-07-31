# Progress 10 Retention and Deletion Runbook

## Retention inventory

Evaluate every project asset, memory record, scene commit, and export against its retention class, authoritative policy source, active legal holds, and deletion-eligibility time. Store an immutable assignment hash. A legal hold always overrides deletion eligibility.

## Deletion workflow

1. Build a dependency graph for an asset, subject, project, or tenant.
2. Review canonical, derivative, index, cache, export, replica, and backup dispositions.
3. Resolve every exception and legal hold.
4. Select and verify a recovery point for rollback/evidentiary continuity.
5. Request purge with an idempotency key.
6. Obtain independent approval; the requester cannot approve.
7. Recompute and compare the graph immediately before execution.
8. Execute canonical tombstone/redaction, index purge, cache invalidation, derivative withdrawal, export withdrawal, replica scheduling, and backup expiry scheduling.
9. Retain key IDs, cryptographic-erasure evidence hash, residual timelines, store results, unresolved exceptions, approver, executor, and completion evidence.

## Backup expiry

Backup expiry has an explicit deadline and residual-location record. Active legal holds block expiry. On execution, package and database snapshot bytes are removed and the recovery point becomes `expired`. Ordinary restores from a point preceding completed deletion are denied even before expiry.

## Tenant offboarding

Tenant offboarding creates and verifies an open preservation package per project, plus retention and deletion reports. It is preparation evidence only; destructive tenant deletion still requires the governed deletion workflow.

## Failure handling

A changed dependency graph, new legal hold, missing verified recovery point, incomplete erasure evidence, lost operation lock, or unresolved store result fails closed. Audit evidence for denials and failures is retained outside rejected transactions.
