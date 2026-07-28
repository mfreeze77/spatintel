# Automatic resume — SIP v1.1.0 Progress 05-R1

This branch is limited to the True North Progress 05-R1 remediation. No user approval is required to continue any interrupted checkpoint-control step, and Progress 06 must not begin from this record.

The required continuous sequence is:

1. regenerate controlled contracts, requirements ledgers, and the 30-requirement Progress 05 semantic traceability audit;
2. run focused remediation tests and source-drift checks;
3. commit the exact source bytes to `progress-05-r1-remediation`;
4. create a clean detached worktree at that commit;
5. create a source attestation and run the complete locally executable acceptance sequence against that exact commit;
6. repair any local failure in source, recommit, recreate the detached worktree, and rerun the complete affected acceptance sequence;
7. build the inner `Spatial-Intelligence-Platform-v1.1.0-progress-05-r1.zip` only from the clean accepted commit;
8. independently verify the inner checkpoint;
9. build the consolidated outer delivery envelope with the inner ZIP, Git bundle, exact source archive, hashes, manifests, provenance, milestone scope, evidence, and acceptance reports;
10. independently verify the outer envelope and publish both packages for True North review.

An interruption handler must inspect the machine-readable resume state at `/mnt/data/sip-progress-05-r1-auto-resume.json`, resume the first incomplete stage automatically, and never ask the user to type “continue.”

Production remains **NO-GO**. Progress 06 remains unauthorized until True North accepts Progress 05-R1.
