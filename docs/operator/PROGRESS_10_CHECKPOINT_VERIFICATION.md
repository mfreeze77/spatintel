# Progress 10 checkpoint verification

Progress 10 is a bounded `OPS-004` development checkpoint for backup, restore, disaster-recovery controls, retention, deletion, preservation, and conservative migration. It does not authorize Progress 11 or production.

## Verify the inner project checkpoint

```bash
PYTHONPATH=src:. python tools/verify_progress10_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-10.zip
```

The command must return `passed_complete` with zero findings. It verifies safe ZIP paths, decompression limits, complete file hashes, file modes, aggregate content root, authoritative specification identity, Git bundle and source-archive provenance, ancestry from accepted Progress 09, migration `0020`, the exact 45-requirement OPS-004 scope, source-bound acceptance evidence, explicit external gaps, Progress 11 denial, and production denial.

## Verify the consolidated delivery envelope

```bash
PYTHONPATH=src:. python tools/verify_progress10_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-10-delivery-package.zip
```

The outer verifier checks its self-excluding delivery index, rejects missing or unexpected payloads, validates every payload hash/mode/size, reproduces the payload content root, checks the project ZIP checksum, and performs a fresh nested execution of the dedicated Progress 10 inner verifier.

## Recovery evidence classifications

The checkpoint keeps the following classes distinct:

- `local_executed`: an isolated local restore or migration rehearsal actually executed in the retained environment;
- `synthetic_executed`: a deterministic service/region-loss or dependency-failure exercise using synthetic/non-sensitive data;
- `structural_only`: configuration or infrastructure definitions were statically validated but not deployed;
- `external_validation_required`: credentialed cloud, KMS, queue/CDN, multi-region, physical edge, witnessed, or production evidence is absent.

No local or synthetic result is a production disaster-recovery certification.

## Git recovery

Clone the bundled repository by naming the Progress 10 branch explicitly:

```bash
git clone -b progress-10-recovery \
  Spatial-Intelligence-Platform-v1.1.0-progress-10-<commit>.bundle \
  sip-progress-10
```
