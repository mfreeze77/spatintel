# Progress 05-R2 remediation contract

True North conditionally accepted Progress 05-R1 as a trustworthy development snapshot but withheld Progress 05 milestone closure, Progress 06 authorization, and production promotion.

This is a narrow remediation checkpoint. It does not begin Progress 06.

## Binding stop-line corrections

1. Concurrent accepted-change application must not expose a raw database uniqueness exception. The losing transaction must roll back, resolve the winner in a fresh transaction, verify tenant, project, comparison, branch, semantic-event, outbox, and audit equivalence, and return the existing result with `idempotent_replay: true`.
2. A barrier-controlled two-session test must prove exactly one commit, one branch-head advancement, no escaping `IntegrityError`, one governed result for both callers, and consistent event, outbox, and audit records.
3. `PLTVIEW-007` may remain `VERIFIED` only with the specified mounted viewer integration test. Because the frozen React/Three.js toolchain is unavailable here, R2 must demote it to `IMPLEMENTED_UNVERIFIED` and retain the exact verification gap.
4. Every ledger, scope, traceability, evidence, status, readiness, and packaging record must reflect those facts.
5. Source must be committed before acceptance; acceptance must run from a clean detached worktree at that exact commit.
6. The inner checkpoint and consolidated outer envelope must each pass independent verification with zero findings.

Production remains **NO-GO**.
