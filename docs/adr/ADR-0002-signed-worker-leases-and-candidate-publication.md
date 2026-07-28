# ADR-0002: Signed worker leases and candidate-only completion

- Status: Accepted
- Date: 2026-07-27
- Decision owners: platform-runtime, security-assurance, hybrid-representations

## Context

GPU and geometry workers process hostile or sensitive inputs and may fail, retry, or be revoked. A worker must not gain broad database authority or attach its own output to an authoritative scene.

## Decision

Every worker runs under an immutable capability manifest and a signed lease bound to operation, attempt, input hash, deadline, resource envelope, cancellation token, output staging scope, and workload identity. Compute code has no shell or network permission. Completion creates a deterministic quarantined candidate and receipt; only the representation publisher may later attach an independently validated candidate.

## Consequences

Workers are independently replaceable and safely retryable. Control-plane gateways and staging receipts add protocol complexity, but publication remains exactly once and outside provider authority.

## Traceability

- Requirements: PLTGRPC-001, PLTGRPC-004, PLTSDK-003, HYBAPI-003, HYBAPI-004, REPOHYB-001, REPOHYB-003
- Risks: RISK-PROVIDER-DATA-EGRESS, RISK-PROTECTED-GEOMETRY-LOSS
- Benchmarks: `build/reports/benchmark-report.json`
- Source evidence: `src/sip/worker_protocol.py`, `src/sip/worker_runtime.py`, `src/sip/worker_sandbox.py`, `tests/integration/test_worker_runtime.py`, `tests/security/test_worker_protocol_security.py`
- Exit/export strategy: the worker protocol is versioned in Protobuf, JSON Schema, Python, and TypeScript; providers can be replaced without changing scene contracts.
- Security/privacy review: least-privilege design review completed internally; container escape, cloud identity, and external penetration validation remain release-blocking external evidence.
