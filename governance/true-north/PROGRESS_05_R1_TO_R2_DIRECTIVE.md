# True North directive — Progress 05-R2 required

## Disposition

Progress 05-R1 is accepted as a trustworthy development snapshot. The outer package, inner checkpoint, and Git/source provenance are accepted. Progress 05 milestone closure and Progress 06 authorization are withheld. Production promotion remains **NO-GO**.

## Stop-line defect 1 — concurrent idempotency

Two simultaneous accepted-change calls may race on the project-scoped workflow-event uniqueness constraint. R2 must catch only that specific uniqueness conflict, allow the losing transaction to roll back, read the committed winner in a fresh transaction, and verify tenant, project, comparison, branch, expected parent, semantic-event links, outbox publications, and audit records. An equivalent result must be returned with `idempotent_replay: true`; an inconsistent state must return a stable SIP conflict rather than a raw SQLAlchemy exception.

A barrier-controlled, two-session test must prove:

- one persisted workflow commit;
- one committed branch-head advancement;
- no escaping `IntegrityError`;
- both callers resolve to the same commit;
- one caller is identified as an idempotent replay;
- semantic-event links, outbox events, and audit records remain consistent.

## Stop-line defect 2 — `PLTVIEW-007` evidence

The five-role renderer implementation is present, but its specified verification method is a mounted viewer integration test. Source invariants and a dependency-free directive test are insufficient. R2 must either run a genuine component/renderer integration test or demote the requirement to `IMPLEMENTED_UNVERIFIED` until the frozen web toolchain is available.

## Required delivery

R2 must remain a narrow remediation checkpoint. It must regenerate all ledgers, scope, traceability, evidence, status, and readiness records; commit before testing; run the complete matrix from a clean detached worktree; independently verify the inner ZIP and outer envelope; and retain production as NO-GO. Progress 06 must not begin.
