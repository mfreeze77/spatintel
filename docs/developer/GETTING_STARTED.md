# Developer Getting Started

## Supported profiles

The pinned toolchain is in `.tool-versions`. The Python reference implementation supports Python 3.11 through 3.13. Apple-platform capture development requires Swift 6.2 and Xcode on macOS. The complete web build requires Node 24.18 or newer and the committed pnpm lockfile.

Check the current machine without changing it:

```bash
make doctor
```

## Python reference environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,postgres,redis,telemetry]'
make bootstrap
make test
```

`make bootstrap` regenerates worker manifests, generated contracts, Kubernetes manifests, and local development secret files. It does not download model weights or grant provider approval.

## Reproducible acceptance toolchain

The acceptance image combines the digest-pinned Python 3.13.14, Swift 6.2.4,
and Node 24.18.0 official images used by the local checkpoint gates:

```bash
docker build -f infrastructure/containers/Dockerfile.acceptance \
  -t sip-progress11-acceptance:local .
docker run --rm -v "$PWD:/workspace" -w /workspace \
  sip-progress11-acceptance:local make test-all
```

This image proves the Linux Swift fixture and dependency-free web profiles. It
does not substitute for Xcode/physical-device, mounted-browser, GPU/model,
credentialed-cloud, independent-review, pilot, or production evidence.

## Run the API

```bash
make dev
```

Development authentication is explicitly enabled only by that command. Do not use `SIP_ALLOW_DEVELOPMENT_AUTH=true` in a shared or production environment.

## Swift capture fixture profile

```bash
cd apps/ios-capture
swift build
swift test
```

Linux/macOS package tests exercise the journal, state machine, package writer, sensor fixtures, quality rules, and resumable transfer logic. ARKit, LiDAR, AVFoundation, CoreMotion, thermal, battery, interruption, and BackgroundTasks acceptance require Xcode and physical devices.

## Web source profile

The renderer-independent runtime checks need no dependency install:

```bash
make web-test
```

The complete profile is release-gated:

```bash
corepack enable
corepack prepare pnpm@10.28.2 --activate
pnpm install --frozen-lockfile
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```

A missing lockfile is a release blocker, not permission to perform an unfrozen install in CI.

## Common commands

```bash
make lint
make typecheck
make test-all
make security
make license-check
make benchmark
make demo-foundation
make demo-hybrid
make demo-construction
make demo-liveforever
```

Reports are written under `build/reports/`; retained demonstration evidence is under `build/evidence/demos/`.

## Adding a worker

1. Add `workers/<name>/main.py` and `worker.json`.
2. Register only the operation types implemented by that worker.
3. Add deterministic handler tests and cancellation/checkpoint behavior.
4. Regenerate immutable manifests and deployment definitions:

```bash
PYTHONPATH=src:. python tools/generate_worker_manifests.py
PYTHONPATH=src:. python tools/sync_compose_workers.py
PYTHONPATH=src:. python tools/generate_kubernetes.py
```

5. Verify drift and identity isolation:

```bash
make contracts
make infrastructure
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/contract/test_worker_manifests.py \
  tests/contract/test_worker_protocol.py \
  tests/security/test_worker_sandbox.py
```

A worker may create candidates; it may not attach them to a scene commit.

## Adding a migration

Never modify a released migration. Create the next append-only revision, update `migrations/manifest.json` with exact bytes and SHA-256, and run:

```bash
make migrations
```

Destructive downgrade is denied by default. The explicit rehearsal flag is permitted only against an isolated copy after a verified backup.

## Evidence-backed requirement updates

Implementation status is overlaid through `requirements/implementation-map.json`. Do not edit the generated JSON/CSV/SQLite ledgers directly.

A `VERIFIED` overlay must name:

- implementation files;
- valid requirement-linked test IDs;
- retained machine-readable evidence paths;
- the reviewed release or commit;
- remaining limitations or external evidence boundaries.

Regenerate and validate:

```bash
PYTHONPATH=src:. python tools/update_requirements.py
make spec-check
make lint
```
