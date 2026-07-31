# Progress 08 operations incident runbook

This runbook applies only to the bounded OPS-002 development profile. Production remains fail-closed.

## Budget admission denials

1. Correlate the denial with the immutable estimate, policy revision, price-catalog hash, and audit event.
2. Confirm that no retry double-counted a reservation.
3. Require an independent, unexpired override approval before exceeding a hard budget.
4. Do not change pricing inputs or delete denial evidence to admit work.

## Queue backlog

1. Inspect queue class, latest depth, in-flight work, retries, and oldest age without tenant identifiers in ordinary dashboards.
2. Identify OOM, provider, or downstream dependency signals by correlation ID.
3. Pause new admissions when bounded capacity is exhausted; do not bypass tenant quotas.
4. Record remediation and any approved capacity change.

## Queue age

Validate lease health, retry checkpoints, cancellations, and stalled workers. Preserve idempotency and do not discard an operation to make the dashboard green.

## Anomalies

A detector cannot suppress its own alert. Suppression requires an independent actor, bounded expiration, retained evidence, and an immutable audit event.

## Support access

Support access is customer-approved, named-personnel, purpose- and resource-scoped, time-bound, revocable, and metadata-first. Raw assets, unrestricted signed URLs, transcripts, biometrics, secrets, and restricted construction content are excluded from ordinary support bundles.
