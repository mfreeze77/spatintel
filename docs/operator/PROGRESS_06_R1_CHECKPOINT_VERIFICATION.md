# Progress 06-R1 Checkpoint Verification

Progress 06-R1 is built only from a clean detached worktree at a committed R1 source revision. Verification must use the dedicated R1 verifier:

```bash
PYTHONPATH=src:. python tools/verify_progress06_r1_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-r1.zip
```

The verifier checks ZIP safety, complete content manifests, aggregate content root, specification identity, exact Git commit/tree/source archive, accepted Progress 06 ancestry, migration `0015` identity, authoritative evidence bindings, the 1,028-requirement ledger, R1 milestone scope, R1 traceability audit, complete test results, external-gap posture, and the prohibition on Progress 07 and production authorization.

The consolidated envelope is independently checked with:

```bash
PYTHONPATH=src:. python tools/verify_progress06_r1_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-r1-delivery-package.zip
```
