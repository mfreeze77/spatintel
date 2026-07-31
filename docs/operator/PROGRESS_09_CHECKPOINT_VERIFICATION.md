# Progress 09 checkpoint verification

Progress 09 is a bounded `OPS-003` development checkpoint. It does not authorize Progress 10 or production.

## Verify the inner project checkpoint

```bash
PYTHONPATH=src:. python tools/verify_progress09_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-09.zip
```

The command must return `passed_complete` with zero findings. It verifies safe ZIP paths, complete hashes and modes, the aggregate content root, specification identity, Git/source provenance, accepted Progress 08 ancestry, migration `0019`, exact milestone scope, requirements evidence, clean-source acceptance, explicit external gaps, Progress 10 denial, and production denial.

## Verify the consolidated envelope

```bash
PYTHONPATH=src:. python tools/verify_progress09_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-09-delivery-package.zip
```

The outer verifier rejects missing or unexpected payloads, unsafe archive members, checksum drift, incorrect index self-exclusion, stale nested reports, and any nested project checkpoint that cannot pass a fresh independent verification.

## Evidence posture

A zero command exit does not imply that unavailable external controls ran. Node/pnpm production builds, Apple-device validation, GPU execution, deployed infrastructure, and external security/privacy/legal reviews remain explicit gaps unless separately evidenced.
