# Automatic resume — SIP v1.1.0 Progress 05-R2

This branch is limited to the True North Progress 05-R2 remediation. No new user approval is required to resume an interrupted checkpoint-control step. Progress 06 must not begin from this record, and production remains **NO-GO**.

## Binding R2 disposition

Progress 05-R1 is accepted as a trustworthy development snapshot. Progress 05 closure and Progress 06 authorization remain withheld until R2 independently proves both of these corrections:

1. simultaneous accepted-change callers converge on one governed result without exposing a raw database integrity error; and
2. `PLTVIEW-007` is either supported by its specified mounted viewer integration test or conservatively retained as `IMPLEMENTED_UNVERIFIED`.

This implementation selects the conservative viewer disposition because the frozen Node 24.18.0/pnpm 10.28.2 React/Three.js toolchain is unavailable in the current environment.

## Required continuous sequence

1. regenerate controlled contracts, requirements ledgers, and the 30-requirement Progress 05 semantic traceability audit;
2. run the focused R2 concurrency, traceability, checkpoint-control, and viewer-reference tests;
3. commit the exact source bytes to `progress-05-r2-remediation`;
4. create a clean detached worktree at that commit;
5. create a source attestation and run the complete locally executable acceptance sequence against that exact commit;
6. repair any local failure in source, recommit, recreate the detached worktree, and rerun the complete affected acceptance sequence;
7. reach an evidence fixed point with no generated-source or traceability drift;
8. build `Spatial-Intelligence-Platform-v1.1.0-progress-05-r2.zip` only from the clean accepted commit;
9. independently verify the inner checkpoint with zero findings;
10. build the consolidated outer delivery envelope with the inner ZIP, Git bundle, exact source archive, hashes, manifests, provenance, scope, evidence, and acceptance reports;
11. independently verify the outer envelope with zero findings; and
12. publish both packages for True North milestone-closure review.

An interruption handler must inspect `/mnt/data/sip-progress-05-r2-auto-resume.json`, resume the first incomplete stage automatically, and never request another phase approval.
