# Construction Vertical Operations

## Safe operating profile

Use only synthetic or approved non-sensitive project data for the Progress 06 reference profile. Do not load critical-infrastructure topology, live credentials, access-control credential databases, programming passwords, biometric identifiers, or confidential facility data without an approved tenant classification, purpose, retention rule, and operator authorization.

## Survey lifecycle

1. Create a survey with explicit objectives, places, system types, sensitive regions, controls, measurement requirements, safety conditions, permissions, deliverables, and baseline commit.
2. Record each visit separately. Preserve capture IDs, checklist, detail evidence, coverage, registration, controls, inventory, inaccessible areas, unresolved questions, privacy state, and exact prior commit.
3. Mark visits complete only when the visit record is durably written. A completed visit is not automatically an accepted survey.
4. Review the aggregate against coverage, limitations, inventory, and unresolved questions. Acceptance records a separate reviewer decision and accepted scene commit.
5. A return visit references the prior survey/commit and does not overwrite earlier observations.

## Authority and measurement controls

- `design` remains design intent.
- `observed` is direct evidence, not independent verification.
- `inferred` must remain labeled.
- `measured` requires source and uncertainty but is not automatically verified.
- `verified` requires configured calibration, verifier identity, verification date, source, units, uncertainty/tolerance, and intended-use limitations.
- Interaction-proxy hits must re-resolve to eligible metric evidence before an authoritative measurement can be created.
- Inaccessible and unobserved regions cannot be reported as removed or complete.

## System records

Fire alarm, access control, BAS, mechanical, and electrical records use stable IDs and explicit evidence. Network paths, addresses, controller-security fields, programming data, credential context, and restricted annexes require elevated authorization and are omitted from broad reports and owner exports unless expressly permitted.

## Documents and RFIs

Every document revision retains the source asset ID, SHA-256, type, title, revision, issue date, issuer, status, page count, permissions, supersession, page-region anchors, spatial links, extraction proposal, and review state. Never silently replace a revision. AI extraction must cite exact page/region and remain review-required.

## Issues and commissioning

Issues move through append-only history. Correction and retest require new evidence. Closure requires the configured verifier, date, result, and residual limitations. Commissioning records reject secrets and retain procedure, prerequisites, steps, expected/actual results, participants, instruments/calibration, attachments, result, retest linkage, and acceptance.

## Incident handling

On authorization or policy uncertainty, deny the operation and retain safe audit context. On package verification failure, quarantine the package and preserve the original bytes. On partial handoff failure, retain the prior verified handoff and do not publish the incomplete replacement. Follow `docs/operator/INCIDENT_RESPONSE.md` and `docs/runbooks/OPERATIONS_INCIDENTS.md`.

## Reference commands

```bash
make demo-construction
make migrations
make security
make export-demo
make restore-demo
```

These commands validate the deterministic local profile only. They do not replace field, device, customer, cloud, accessibility, or legal acceptance.
