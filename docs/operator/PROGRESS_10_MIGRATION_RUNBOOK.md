# Progress 10 Legacy Migration Runbook

Progress 10 provides a conservative v1.0-to-v1.1 migration evidence path.

- Preserve every original asset byte and SHA-256.
- Create additive records; never rewrite source geometry in place.
- Assign role and authority from provenance and verification evidence, not extension or appearance.
- Classify splats and photogrammetry as visual-only unless independent metric evidence exists.
- Keep proxy/design/generated measurements non-authoritative.
- Quarantine unknown roles, transforms, frames, anchors, providers, and authority claims.
- Preserve or strengthen permissions, classification, consent, retention, holds, and deletion dependencies.
- Require a verified restorable source recovery point.
- Retain unresolved anchors and down-level omissions.
- Generate a signed mapping, quarantine, policy-diff, validation, compatibility, and rollback report.

Dry runs are deterministic by canonical input hash. Re-execution returns the prior report. A policy relaxation or mismatched source hash is denied.
