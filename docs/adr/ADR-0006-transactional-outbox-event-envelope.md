# ADR-0006: Transactional outbox and complete event envelopes

- Status: Accepted
- Date: 2026-07-27
- Decision owners: platform-runtime, security-assurance

## Context

A database commit without its event, or an event without its committed state, corrupts workflows and auditability. At-least-once delivery also requires stable deduplication and safe replay.

## Decision

Events asserting committed state are written in the same transaction through the outbox. Every event carries identity, type/version, aggregate, tenant/project scope, occurrence time, trace/correlation/causation context, producer, classification, and payload hash. Consumers deduplicate by event ID and hash; dead-letter replay requires remediation and authorization.

## Consequences

Outbox publishing and schema compatibility must be operated as first-class services. Event payloads remain bounded summaries and never transport raw geometry, media, transcripts, or restricted coordinates.

## Traceability

- Requirements: ARCEVT-001, ARCEVT-002, ARCEVT-003, ARCEVT-005, HYBAPI-005, HYBAPI-007
- Risks: RISK-DERIVATIVE-REDACTION, RISK-PROVIDER-DATA-EGRESS
- Benchmarks: `build/reports/test-matrix.json`
- Source evidence: `src/sip/events.py`, `src/sip/operations.py`, `schemas/events/event-catalog.json`, `tests/contract/test_event_architecture.py`
- Exit/export strategy: event schemas are JSON Schema documents with stable versions and payload hashes; consumers do not depend on a proprietary broker.
- Security/privacy review: data-minimized envelope approved as baseline; external broker/cloud telemetry review remains environment-specific.
