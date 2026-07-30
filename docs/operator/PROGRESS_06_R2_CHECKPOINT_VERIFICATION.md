# Progress 06-R2 checkpoint verification

Progress 06-R2 is a narrow remediation checkpoint descended from accepted Progress 06-R1 commit `118ac917a6c35e007d9f2158d5495e1a69883748`. Progress 07 is unauthorized and production remains NO-GO.

## Verify the inner project checkpoint

```bash
PYTHONPATH=src:. python tools/verify_progress06_r2_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-r2.zip
```

A valid result has `status: passed_complete` and `finding_count: 0`. The verifier independently checks ZIP safety, exact manifest coverage, aggregate content root, authoritative specification hash, source root, Git bundle and source archive provenance, accepted-base ancestry, migration 0016 byte identity, milestone scope, semantic traceability, clean-source test evidence, status consistency, and fail-closed release posture.

## Verify the consolidated delivery envelope

```bash
PYTHONPATH=src:. python tools/verify_progress06_r2_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-r2-delivery-package.zip
```

The outer verifier rejects listed-but-missing files, unexpected files, unsafe paths, duplicate members, symlinks, mode/size/hash drift, incorrect payload roots, an implicit index self-exclusion, stale nested verification, or any nested checkpoint that fails a fresh independent verification.

## Clone the Git bundle

```bash
git clone \
  -b progress-06-r2-remediation \
  Spatial-Intelligence-Platform-v1.1.0-progress-06-r2-<commit>.bundle \
  sip-progress-06-r2
```

Compare `SOURCE_COMMIT.json`, `SOURCE_FILE_MANIFEST.json`, the exact source archive, and the verifier facts before accepting a checkpoint.
