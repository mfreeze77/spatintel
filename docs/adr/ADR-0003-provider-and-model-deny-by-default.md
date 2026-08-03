# ADR-0003: Deny providers and models by default

- Status: Accepted
- Date: 2026-07-27
- Decision owners: model-provider-governance, security-privacy, legal-review

## Context

A repository checkout does not establish the checkpoint, dataset, hosted-service behavior, output terms, region, retention, or quality envelope. Runtime downloads also make an audited run non-reproducible.

## Decision

Provider and model execution requires a reviewed manifest with exact source revision, checkpoint hash when applicable, code/weights/data/output rights, permitted classifications/purposes/regions, retention, approver, and expiry. Unknown, expired, research-only, prohibited, or unscanned paths fail before source access. Runtime downloads are forbidden. LingBot source is pinned while its checkpoint remains denied.

## Consequences

Some visually impressive providers remain unavailable until their rights and operational envelope are proven. Deterministic local baselines and native hybrid rendering preserve functionality.

## Traceability

- Requirements: GOVLIC-001, GOVLIC-004, GOVLIC-008, PLTMODEL-002, RECLING-004, REPOHYB-006
- Risks: RISK-PROVIDER-DATA-EGRESS, RISK-PROVIDER-LOCK-IN
- Benchmarks: `build/reports/license-gate.json`, `build/reports/benchmark-report.json`
- Source evidence: `src/sip/model_governance.py`, `tools/check_governance.py`, `third_party/sources/source-lock.json`, `adapters/lingbot-map/source.lock.json`
- Exit/export strategy: provider-independent contracts, deterministic local providers, native mesh+splat rendering, and open preservation export prevent provider lock-in.
- Security/privacy review: restrictive policy approved as the internal baseline. Any expansion of data use or trust boundary requires named security/privacy/legal approvers and new evidence.
