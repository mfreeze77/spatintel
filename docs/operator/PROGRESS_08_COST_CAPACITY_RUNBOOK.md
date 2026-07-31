# Progress 08 Cost, Capacity, Quota, and Admission Runbook

Cost records use immutable price-catalog versions. Historical actuals and reconciliations never change when a later catalog is registered.

## Estimate before admission

A pre-run estimate binds tenant, project, capture, run, stage, model/checkpoint, compute profile, input class, all resource quantities, catalog version/hash, stage estimates, total, currency, expiry, and evidence class. Optional expensive final reconstruction must display the processing tier and fresh estimate before acknowledgement; server-side admission remains authoritative.

## Usage and allocation

Account for CPU seconds, GPU seconds by profile, memory-byte seconds, object bytes by tier, database/vector growth, requests, vector/search usage, CDN/egress, transcription/OCR/model-provider use, and support overhead. Rollups may group by tenant, project, capture, run, stage, model, and calendar period, but ordinary callers never receive another tenant's identifiers or usage.

## Reconciliation

Actual usage retains its catalog hash and complete quantities. Reconciliation compares all estimates and actuals for the run, records variance, and never mutates input records. Retry uses idempotency keys and returns the same governed result.

## Admission and reservations

Admission is one transaction that checks active policy, hard/soft budgets, concurrency, storage, retention, anomalies, overrides, and estimate freshness. A successful reservation has an expiry and is released on completion, cancellation, or failure. A denial commits stable audit/outbox evidence before returning. Concurrent admission must permit only the allowed number of reservations, never double-count, and never leak capacity.

## Overrides and anomalies

Overrides require an independent approver, exact scope, reason, amount/currency, expiry, request hash, and audit history. Self-approval and expired overrides fail closed. Anomaly suppression requires an actor independent from the detector, has an expiry, and never removes original alert evidence.

## Capacity plans

Plans use measured scene minutes, frames, area, peak concurrency, retention, storage, profile and headroom. Synthetic plans are labeled synthetic/local. Deployed capacity planning remains external until infrastructure measurements exist.
