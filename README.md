# Spatial Intelligence Platform (SIP) v1.1.0

SIP is an open, self-hostable spatial-intelligence platform that keeps **metric truth, visual appearance, interaction geometry, design intent, and source evidence separate**. The repository contains a deterministic CPU reference implementation, versioned API/contracts, iOS capture core, web hybrid-viewer runtime, durable worker protocol, Construction Spatial Reference and LiveForever domain implementations, preservation export/restore, governance controls, tests, and deployment profiles.

This checkout is configured as a private, local-first internal tool. Hosted processing and implicit model downloads remain disabled unless explicitly configured later.

> **Release posture:** this repository is production-shaped, but it is not represented as production-complete until the generated requirements ledger and release gates say so. Hardware, GPU/model, cloud-account, legal, customer-pilot, and human-subject validations remain explicitly external unless retained evidence exists.

## Authoritative specification

The unmodified specification archive is preserved at:

```text
spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip
```

Expected and verified SHA-256:

```text
84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8
```

All 164 Markdown files are extracted under `spec/Spatial-Intelligence-Platform-Spec-v1.1/`. The generated ledger contains 1,028 unique normative requirements and is available as JSON, CSV, and SQLite in `requirements/`.

## Repository map

```text
apps/ios-capture                 Swift capture core and conditional ARKit application
apps/web                         Next.js/React hybrid spatial review application
services/*                       Least-privilege FastAPI service boundaries
workers/*                        Isolated durable worker entry points
src/sip                          Shared domain/control-plane implementation
schemas                          OpenAPI, JSON Schema, Protobuf, events, SQL
packages/contracts               Generated Swift, Python, and TypeScript contracts
adapters                         Provider and import adapter boundaries
verticals/construction           Construction contracts, demos, and guidance
verticals/liveforever            LiveForever contracts, demos, and safety guidance
infrastructure                   Compose, Kubernetes, Terraform, observability, policies
requirements                     Requirements ledger, coverage, blockers, waivers
build/evidence                   Retained test and demonstration evidence
spec                             Immutable specification source and index
```

## Local CPU reference path

Prerequisites are Python 3.11–3.13 and Git. Docker, Node/pnpm, Swift/Xcode, Terraform, and Kubernetes tooling are required only for their corresponding profiles.

```bash
make bootstrap
make doctor
make test-all
make demo-foundation
make demo-hybrid
make demo-construction
make demo-liveforever
```

Start the co-located control API:

```bash
make dev
# API: http://127.0.0.1:8080
# OpenAPI: http://127.0.0.1:8080/docs
```

The equivalent `just` commands are provided when `just` is installed.

## Container profile

```bash
cp .env.example .env
# Replace all generated-development values before any non-local deployment.
docker compose -f infrastructure/compose/docker-compose.yml up --build
```

The Compose profile uses PostGIS, MinIO, Redis, separate API service boundaries, and the web application. Production profiles use Kubernetes/Terraform and external secret/key management; no production secret is committed.

## Core truth and safety rules

SIP enforces these invariants in domain code and tests:

- Original capture bytes are immutable, content-addressed evidence.
- Visual splats and interaction proxies cannot certify measurements.
- A proxy pick must resolve against eligible metric evidence before a measurement can be authoritative.
- Stable entity and anchor identity does not depend on triangles, splats, voxels, tiles, or LOD identifiers.
- Construction measurements retain units, uncertainty, calibration, verifier, and verification date.
- LiveForever recollection, corroborated fact, inference, and generated reconstruction remain separate labels.
- Consent and audience policy are server-side and reevaluated when opening historical links.
- Hosted providers and unknown checkpoints stay disabled. Local checkpoints run only when a hash-locked internal manifest matches the purpose, classification, region, and model bytes.
- Long operations are durable, idempotent, observable, cancellable, and auditable.
- Preservation export and clean restore are first-class acceptance paths.

## Development gates

```bash
make lint           # Python compilation and specification lint
make typecheck      # generated-contract and service-boundary checks
make security       # source secret/dangerous-pattern scan
make license-check  # third-party/model fail-closed governance
make spec-check     # regenerate and validate requirements ledger
make benchmark      # deterministic reference-profile benchmarks
make release        # manifests, SBOM, reports, source archives, checksums
```

## iOS capture

The Swift package can be tested on any Swift 6.2 host:

```bash
cd apps/ios-capture
swift test
```

The ARKit/AVFoundation/CoreMotion implementation is compiled only on supported Apple platforms. Physical LiDAR, thermal, battery, interruption, cable transfer, and background-task acceptance are tracked as external validation rather than claimed from Linux fixtures.

## Web viewer

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/web build
pnpm --dir apps/web test
```

The renderer-independent runtime has deterministic verification that can run without WebGL or third-party rendering packages. The application keeps metric, visual, design, interaction, and evidence layers distinct and displays authority/confidence labels.

## Local models and third-party components

LingBot-Map source is pinned to commit `1f480aeb8a47a24656090d46d053115b7fe60435` behind an isolated adapter. No model weights are bundled. A local checkpoint can be added by recording its exact hash, source, input/output terms, supported purposes, and quality profile. Until a checkpoint is configured, the deterministic local reconstruction lane remains available and the LingBot worker stays inactive.

The Polyform-compatible importer independently implements the documented user-export format. It preserves the original archive and separately records native ARKit and corrected pose streams; SIP does not copy proprietary Polycam application code or depend on the Polycam application.

See `third_party/manifest.lock.json`, `NOTICE.md`, and `docs/operator/PROVIDER_GOVERNANCE.md`.

The recommended internal capture-to-output pipeline and its current implementation limits are documented in `docs/developer/INTERNAL_MESH_QUALITY.md`.

## Evidence and status

- `IMPLEMENTATION_STATUS.md` — generated status and production claim
- `requirements/coverage-report.md` — priority/status matrix
- `requirements/external-validation.md` — evidence that must come from hardware, legal, cloud, or human review
- `build/evidence/` — machine-readable test/demo evidence
- `build/reports/` — security, privacy, benchmark, migration, coverage, and release reports
- `RESUME_IMPLEMENTATION.md` — exact remaining work at the current repository commit

## License

SIP source is licensed under Apache-2.0. Third-party components retain their own notices and recorded compatibility status. See `LICENSE`, `NOTICE.md`, `LICENSES/`, and `third_party/manifest.lock.json`.
