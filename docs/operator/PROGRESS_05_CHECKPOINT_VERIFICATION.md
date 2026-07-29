# Progress 05-R2 checkpoint verification

Progress 05-R2 must be built only after committing source and running acceptance from a clean detached worktree. Production promotion remains fail-closed.

## Verify the project ZIP

```bash
PYTHONPATH=src:. python tools/verify_progress05_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-05-r2.zip \
  --output progress-05-r2.verification.json
```

The verifier rejects unsafe paths, symlinks, duplicate members, file or mode drift, aggregate-root drift, specification drift, source/Git mismatch, stale evidence, contradictory status documents, unbound test results, a missing predecessor mapping, an incomplete milestone partition, or any production-ready claim.

## Restore the Git repository from the bundle

The branch must be named explicitly because a bundle is not required to advertise a default HEAD:

```bash
git clone \
  -b progress-05-r2-remediation \
  artifacts/Spatial-Intelligence-Platform-v1.1.0-progress-05-r2-<commit>.bundle \
  sip-progress-05-r2
```

## Evidence interpretation

- Linux Swift fixture results are not Xcode, iOS, LiDAR, camera, thermal, or physical-device acceptance.
- Dependency-free web tests are not a complete Next.js production build or independent browser accessibility audit.
- Structural Compose, Kubernetes, and Terraform checks are not runtime deployment validation.
- Passing command execution and complete control validation are separate facts.
- Production deployment and release remain NO-GO.
