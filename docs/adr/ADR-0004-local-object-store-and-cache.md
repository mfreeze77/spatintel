# ADR-0004: Local object-store fixture and queue/cache selection

- Status: Accepted
- Date: 2026-07-27
- Decision owners: platform-runtime, security-assurance

## Context

The specification names MinIO for local S3-compatible development and permits Redis or an abstracted equivalent for queue/cache use. The selected local MinIO image is retained only as a compatibility fixture, while Valkey supplies the Redis-compatible cache/queue boundary.

## Decision

1. Valkey is the default queue/cache implementation behind the SIP abstraction.
2. MinIO is digest-pinned, loopback-only, opt-in, and denied for production, hybrid, confidential, biometric, critical-infrastructure, and customer-data profiles.
3. Production object storage must provide versioning, retention, encryption, audit integration, and an approved provider manifest.
4. Release checks reject unpinned or ungoverned images and any denied image in a production profile.

## Consequences

Local S3 contract tests remain reproducible, but local MinIO results are not production-security evidence. The storage adapter and preservation format remain provider-independent.

## Traceability

- Requirements: ARCDEP-001, ARCDEP-004, DATOBJ-001, GOVLIC-008, ARCADR-002
- Risks: RISK-PROVIDER-LOCK-IN, RISK-PROVIDER-DATA-EGRESS
- Benchmarks: `build/reports/infrastructure-static-validation.json`
- Source evidence: `infrastructure/compose/docker-compose.yml`, `src/sip/assets.py`, `third_party/providers/minio-local-only.json`
- Exit/export strategy: S3-compatible and local CAS adapters share content hashes; preservation packages restore independently of MinIO or Valkey.
- Security/privacy review: production use remains denied until a supported service and target-environment review are complete.
