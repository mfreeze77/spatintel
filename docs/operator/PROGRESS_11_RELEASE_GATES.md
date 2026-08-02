# Progress 11 Dual-Vertical Release Gates

Progress 11 is the bounded `QA-002` development checkpoint. It evaluates Construction and LiveForever on one governed release campaign and never authorizes production by itself.

## Required local gates

The release-assurance service retains immutable results for requirements, Construction acceptance, LiveForever acceptance, hybrid authority, security/privacy, accessibility, load/performance, backup/restore, migration, rollback, open export, license/model rights, SBOM/vulnerability posture, support/recovery, and the release manifest. Command execution status and control completeness are recorded separately.

These critical P0, truth, consent, authority, tenant-isolation, evidence-integrity, security, rollback, migration, backup/restore, and release-manifest failures are non-waivable. Any permitted waiver requires an independent approver, compensating control, rationale, owner, and expiration.

## Evidence classes

- `local_executed`: executed in the retained local reference profile.
- `browser_independent`: dependency-free web/runtime verification.
- `synthetic_controlled`: deterministic synthetic acceptance evidence.
- `external_validation_required`: device, mounted browser, GPU/model-rights, credentialed cloud, customer/human-subject, legal, privacy, accessibility, penetration, or production evidence that did not execute.

A zero exit code cannot promote an external gap to `passed_complete`.

## Release posture

A signed candidate proves evidence integrity only. It always carries `production_authorized: false` and `progress_12_authorized: false` until a later independent True North decision. Production admission fails closed while any required external gate or independent authorization is absent.

Production posture: **NO-GO**. This bounded development checkpoint never authorizes production.
