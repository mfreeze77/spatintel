# ADR-0007: Versioned failure catalog and new-lineage recovery

- Status: Accepted
- Date: 2026-07-27
- Decision owners: reliability, product-safety, security-assurance

## Context

Unstructured exception strings cannot safely drive retries, publication, customer messaging, incident response, or compatibility analytics. Retrying by rewriting a failed record destroys evidence.

## Decision

SIP maintains an append-only, versioned failure catalog with stable codes, severity, retry class, safe checkpoint, operator action, customer-safe message, audit requirement, tests, publication action, diagnostic allowlist, recovery behavior, and explicit component fallback. Unsafe/fatal failures block or withdraw publication. Diagnostics retain bounded hashes/IDs/metrics, never raw sensitive content. Recovery creates a new operation/run/revision linked to the immutable failed record.

## Consequences

New failure modes require catalog and compatibility review. This improves deterministic remediation, safe customer messages, analytics, and evidence retention.

## Traceability

- Requirements: APPFAIL-001, APPFAIL-002, APPFAIL-003, APPFAIL-004, APPFAIL-005, APPFAIL-006, APPFAIL-007, APPFAIL-008, APPFAIL-009, APPFAIL-010
- Risks: RISK-PROXY-AUTHORITY-CONFUSION, RISK-IMMERSIVE-SAFETY, RISK-DERIVATIVE-REDACTION
- Benchmarks: `build/reports/test-matrix.json`
- Source evidence: `governance/failure-catalog.json`, `src/sip/failures.py`, `tests/unit/test_failure_catalog.py`
- Exit/export strategy: the catalog is plain JSON with stable aliases and can be consumed by any API, support, or analytics implementation.
- Security/privacy review: diagnostic minimization and fail-closed publication are baseline controls; independent incident-response review remains an external assurance item.
