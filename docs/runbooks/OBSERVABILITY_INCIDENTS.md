# Observability and SLO incident runbook

## Service objectives and truth limits

The initial production service objective is **99.9% successful request availability over 30 days**, excluding explicitly classified client errors, and a **p95 API latency below one second** for control-plane requests. Geometry/GPU operation latency is measured separately by operation type and benchmark profile; HTTP acceptance of a durable job is not evidence that reconstruction completed.

Telemetry must never contain raw evidence bytes, credentials, private transcript text, biometric media, consent content, unrestricted spatial coordinates, raw tenant IDs, or raw project IDs. `src/sip/observability.py` redacts protected fields before JSON serialization, pseudonymizes tenant/project context, restricts metric labels to governed bounded values, and propagates only validated W3C `traceparent` context. Trace baggage is not propagated and trace context is never authorization data.

Local Compose telemetry stays local. Production routing, paging delivery, backend retention, and access controls require account-backed validation and retained evidence.

## First-response evidence

For every incident, retain:

1. alert name, start/end time, severity, and affected service or worker;
2. release identifier, container digest, configuration hash, provider/model manifest identifiers when applicable, and deployment revision;
3. request ID, trace ID, durable operation ID, signed worker-receipt hash, and stable error code where applicable;
4. readiness, queue depth, active-work, retry, cost-admission, and dependency signals;
5. audit-chain verification result and the incident decision timeline.

Never paste authorization headers, request bodies, captured media, transcript text, secret values, raw tenant/project identifiers, or unrestricted coordinates into an incident channel.

## High API error-budget burn

1. Confirm the alert is not caused by a telemetry-label or scrape failure.
2. Identify the affected `service`, route template, deployment revision, and first failing request ID.
3. Check readiness failures, database saturation, object-store errors, outbox growth, durable queue depth, and dependency status.
4. Stop a damaging rollout with the documented Kubernetes rollback command. Do not roll back a database migration independently of its tested application compatibility window.
5. If tenant isolation, consent, evidence integrity, deletion, or authority labeling may be affected, declare a security/privacy incident and disable the relevant provider or feature gate.
6. Add or retain a regression test before resolution.

## High control-plane latency

Separate control-plane latency from queued geometry work. Check database query latency, connection-pool exhaustion, object-store response time, CPU/memory throttling, queue admission, and high-cardinality search. Scale only after confirming idempotency, signed leases, cancellation, and cost-budget admission remain active.

## Worker failure ratio

Use `worker`, governed `model`, checkpoint prefix, capture profile, outcome, and stable error code to scope the event. Then:

1. Confirm the worker manifest source hash still matches the executable source and entry point.
2. Inspect the durable operation’s signed lease, latest monotonic checkpoint, attempt count, cancellation state, staged candidate, and receipt hash.
3. Distinguish deterministic input rejection from transient dependency failure, resource exhaustion, sandbox denial, provider revocation, and implementation defects.
4. Never bypass the sandbox, broaden the manifest capability, change a candidate to approved, or publish an output manually.
5. Requeue only through the durable operation service. Preserve the idempotency key and trace parent so a retry cannot create a second authoritative publication.
6. For OOM/resource-limit events, quarantine the input and compare it against the approved benchmark profile before changing limits.
7. If a provider/model was revoked or its approval expired, leave the operation blocked. Reauthorization requires a new current governance decision; an old receipt is not sufficient.

## Excessive worker queue delay

1. Compare queue depth, active operations, queue wait, retry count, and cost/GPU admission signals by capability.
2. Verify workers are healthy and scraped; a zero run rate plus a growing queue is not normal low traffic.
3. Check expired leases and run the normal reconciliation path. Do not edit lease timestamps or operation rows directly.
4. Scale only the affected immutable worker identity. Do not collapse workers into a shared over-privileged process.
5. Preserve per-tenant fairness, quotas, purpose limits, regional controls, and priority policy while draining the queue.
6. When capacity is unavailable, return a durable queued or policy-blocked state rather than claiming completion.

## Reconstruction-quality regression

A photorealistic result is not evidence of metric accuracy. Treat drift, coverage, residual, confidence, failed-region count, and prior-version delta together.

1. Identify the exact input root hash, coordinate-frame registry revision, source streams, worker manifest, solver profile, model/checkpoint manifest, seed, and output hash.
2. Compare the current run against the retained approved benchmark or prior scene revision using the same fixture/profile.
3. Reject or quarantine non-finite transforms, pose collapse, implausible motion, bad seams, low-overlap registration, low valid-depth coverage, or degraded confidence.
4. Confirm ICP ran only after accepted coarse alignment and that source-aware masks/uncertainty were retained.
5. Do not promote learned, splat-derived, proxy, or design geometry to verified measurement authority.
6. If only the interaction proxy regressed, retain the prior scene commit, regenerate the proxy, reproject stable semantic anchors, and report every unresolved anchor.
7. Reopen quality review and require an independent publisher decision for a replacement candidate. Never overwrite the prior published representation.

## Readiness failures

A database failure increments the `database` readiness counter; an object-store failure increments `object_store`. Keep the pod out of service until required dependencies pass. Never bypass readiness to restore traffic. A metrics endpoint being healthy does not prove the application is ready.

## Unhandled errors

Use the request ID and trace ID to locate the structured event. Client responses contain only a stable code, safe message, retryability, and correlation identifiers; raw exception text is not returned. If the error occurred during a durable operation, inspect its retained checkpoint and retry classification rather than replaying it manually.

## Telemetry pipeline failure

1. Confirm application health independently of telemetry health.
2. Check collector configuration hash, scrape target health, queue/backpressure, disk pressure, and backend credentials.
3. Do not disable privacy processors, protected-attribute deletion, pseudonymization, or TLS to restore telemetry.
4. If export is unavailable, retain bounded local telemetry according to policy and record the evidence gap. Do not permit unbounded buffering.
5. The local collector may export only to its debug sink. Any external endpoint in the local profile is a configuration defect.

## Security and privacy escalation

Immediately disable the affected provider/feature gate and invoke the security/privacy incident procedure when there is possible cross-tenant access, consent bypass, restricted-region disclosure, evidence-byte leakage, audit-chain failure, provider policy bypass, model/checkpoint mismatch, unauthorized publication, or deletion/retention failure. Client-side hiding is never accepted as containment.

## Resolution criteria

An incident is resolved only after service restoration, evidence retention, root cause, a regression test or controlled verification, audit-chain verification, affected-policy review, and explicit follow-up ownership. A transient disappearance of the alert is not resolution.

## External validation

Production alert routing, paging delivery, long-term telemetry retention, backend access controls, collector high availability, production TLS, capacity thresholds, and recovery of the telemetry backend remain `EXTERNAL_VALIDATION_REQUIRED` until tested with the actual accounts and retained evidence.
