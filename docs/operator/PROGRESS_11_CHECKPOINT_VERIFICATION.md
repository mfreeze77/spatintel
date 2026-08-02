# Progress 11 Checkpoint Verification

Use only the dedicated Progress 11 verifiers.

```bash
PYTHONPATH=src:. python tools/verify_progress11_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-11.zip

PYTHONPATH=src:. python tools/verify_progress11_delivery_envelope.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-11-delivery-package.zip
```

Both commands must return `passed_complete` with zero findings. The outer verifier performs a fresh nested verification. The checkpoint remains a development artifact with production authorization false.
