# Progress 06 checkpoint verification

Progress 06 must be built from a clean detached worktree at the committed `progress-06-vertical-mvps` branch tip. Post-commit evidence is packaged outside the canonical `source/` namespace and is bound to the same commit, Git tree, source root, and clean-source attestation.

Verify the inner project checkpoint:

```bash
PYTHONPATH=src:. python tools/verify_progress06_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06.zip
```

Verify the consolidated outer envelope:

```bash
PYTHONPATH=src:. python tools/verify_progress06_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-delivery-package.zip
```

The inner verifier rejects unsafe or duplicate members, symlinks, compression abuse, file or mode drift, aggregate-content-root drift, specification drift, Git/source mismatch, incomplete evidence, scope or ledger drift, stale status records, migration-lock drift, test-result drift, and authorization overclaims.

The outer verifier rejects missing or unexpected payloads, index self-inclusion errors, path or mode drift, content-root drift, stale sidecars, and any nested checkpoint that fails fresh independent verification.

A successful verifier result does not authorize production. Progress 07 and production remain fail-closed pending separate True North decisions.
