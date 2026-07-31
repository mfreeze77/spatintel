# Progress 10 Recovery API

The `recovery-control` logical service exposes authenticated routes for recovery objectives, local recovery points, verification, isolated restore, key-recovery exercises, retention inventory, deletion graphs, purge request/approval/execution, backup expiry, fixity, format migration, tenant offboarding, synthetic game days, legacy migration reports, and fail-closed production admission.

All project routes derive tenant scope from the authenticated principal. Destructive actions require exact `deletion:approve` or `deletion:execute` authority. The service stores no reusable credentials in request or response bodies.

Important stable errors include:

- `RECOVERY_POINT_PACKAGE_MISMATCH`
- `RECOVERY_POINT_DATABASE_MISMATCH`
- `RECOVERY_POINT_BYTES_MISSING`
- `RESTORE_TARGET_SCOPE_DENIED`
- `RESTORE_RESIDENCY_DENIED`
- `RESTORE_WOULD_RESURRECT_DELETED_DATA`
- `KEY_RECOVERY_QUORUM_NOT_MET`
- `ROOT_KEY_EXPOSURE_PROHIBITED`
- `LEGAL_HOLD_ACTIVE`
- `DELETION_GRAPH_CHANGED`
- `CRYPTOGRAPHIC_ERASURE_EVIDENCE_INCOMPLETE`
- `MIGRATION_POLICY_RELAXATION_DENIED`
- `RECOVERY_SCOPE_LOCKED`

Idempotency keys are immutable within tenant/project scope. Reuse with different canonical request content is a conflict; exact replay returns the original governed result.
