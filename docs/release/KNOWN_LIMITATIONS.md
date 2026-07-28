# Known Limitations and External Evidence Gaps

This repository currently provides a deterministic reference implementation and production-shaped controls. It is not production-complete while the release-readiness report is blocked.

## Environment gaps

- Docker/Compose build, startup, health, and dependency integration have not been executed in this workspace.
- Kubernetes server-side validation and cluster acceptance require a target cluster.
- Terraform init, provider resolution, plan, apply, and recovery require the target cloud account and credentials.
- PostgreSQL/PostGIS, object-store, Valkey, KMS, PITR, object-version, and multi-region recovery require real managed dependencies.
- Full web install/build/browser/accessibility testing requires a committed frozen dependency graph and supported Node toolchain.
- Xcode, simulator, Apple signing, background-task, camera, LiDAR, thermal, battery, and physical-device acceptance require Apple hardware/tooling.
- LingBot-Map learned weights remain denied until exact bytes, rights, image scan, GPU benchmark, and real-scene validation exist.

## Assurance gaps

- No customer or human-subject pilot has occurred.
- No independent penetration test, privacy assessment, legal approval, accessibility audit, or construction/survey certification has occurred.
- CPU synthetic benchmarks are not capacity, GPU, mobile, production-load, or field-accuracy claims.
- IFC/BCF support is a handoff/reference subset, not complete certification against every vendor implementation.
- OCR, transcription, hosted conversion, and semantic model providers remain governed adapters unless separately approved.

The authoritative current list is machine-readable in each release candidate's `release-readiness.json` and in the requirements ledger.
