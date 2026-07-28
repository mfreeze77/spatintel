---
spec_id: SIP-REPO
title: "Repository Blueprint"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: architecture
normative: true
---
# Repository Blueprint

The implementation should begin as a monorepo so schemas, adapters, clients, services, infrastructure, and acceptance fixtures evolve together. Logical boundaries are preserved so components can later split without changing contracts.

```text
spatial-intelligence-platform/
├── README.md
├── LICENSES/
├── NOTICE.md
├── SECURITY.md
├── CODEOWNERS
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
├── mise.toml / .tool-versions
├── justfile
├── apps/
│   ├── ios-capture/
│   │   ├── App/
│   │   ├── CaptureCore/
│   │   ├── SensorAdapters/
│   │   ├── QualityGuidance/
│   │   ├── PackageWriter/
│   │   ├── Transfer/
│   │   ├── Policy/
│   │   └── Tests/
│   ├── web/
│   │   ├── app/
│   │   ├── components/viewer/
│   │   ├── components/evidence/
│   │   ├── components/construction/
│   │   ├── components/liveforever/
│   │   ├── lib/api/
│   │   └── tests/
│   └── desktop-review/                 # optional after web/local-worker MVP
├── services/
│   ├── control-api/
│   ├── identity-policy/
│   ├── capture-service/
│   ├── workflow-service/
│   ├── scene-service/
│   ├── evidence-service/
│   ├── search-service/
│   ├── export-service/
│   ├── notification-service/
│   └── audit-service/
├── workers/
│   ├── capture-normalizer/
│   ├── lingbot-adapter/
│   ├── pose-optimizer/
│   ├── depth-normalizer/
│   ├── fusion-tsdf/
│   ├── mesh-lod/
│   ├── splat/
│   ├── semantics/
│   ├── document-media/
│   ├── change-detection/
│   └── report-export/
├── packages/
│   ├── contracts/
│   ├── capture-schema/
│   ├── coordinate-frames/
│   ├── scene-graph/
│   ├── provenance/
│   ├── authority-confidence/
│   ├── policy-engine/
│   ├── spatial-query/
│   ├── model-manifest/
│   ├── job-sdk/
│   ├── plugin-sdk/
│   └── test-fixtures/
├── schemas/
│   ├── jsonschema/
│   ├── openapi/
│   ├── protobuf/
│   ├── events/
│   ├── sql/
│   └── ontology/
├── verticals/
│   ├── construction/
│   │   ├── ontology/
│   │   ├── workflows/
│   │   ├── reports/
│   │   └── tests/
│   └── liveforever/
│       ├── ontology/
│       ├── consent/
│       ├── experiences/
│       └── tests/
├── infrastructure/
│   ├── compose/
│   ├── terraform/
│   ├── kubernetes/
│   ├── edge/
│   ├── observability/
│   └── policies/
├── benchmarks/
│   ├── manifests/
│   ├── geometry/
│   ├── capture/
│   ├── change/
│   ├── agents/
│   └── reports/
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   ├── privacy/
│   ├── migration/
│   └── acceptance/
├── third_party/
│   ├── manifest.lock
│   ├── patches/
│   ├── licenses/
│   └── lingbot-map/                    # submodule/source pin or build-context fetch
├── docs/
│   ├── adr/
│   ├── runbooks/
│   ├── developer/
│   ├── operator/
│   └── user/
└── tools/
    ├── spec-lint/
    ├── schema-codegen/
    ├── package-validator/
    ├── license-gate/
    ├── fixture-builder/
    ├── benchmark-runner/
    └── portability-viewer/
```


## Version 1.1 hybrid-representation additions

The implementation tree additionally includes:

```text
services/
  representation-api/
  provider-registry/
  representation-publisher/
workers/
  splat-normalizer/
  splat-surface/
  geometry-cleanup/
  collision-navigation/
  representation-quality/
packages/
  representation-contracts/
  provider-sdk/
  support-maps/
  geometry-policy/
adapters/
  spatial-providers/
    local-baseline/
    splat-transform/
    spark-runtime/
    mesh2splat/
    research-shadow/
    manual-fixture/
apps/web/components/viewer/hybrid-runtime/
benchmarks/
  splat-surface/
  interaction/
  protected-geometry/
  construction-hybrid/
  liveforever-hybrid/
```

Provider adapters may translate provider-specific contracts only at the boundary. They cannot add provider-specific fields to scene entities, evidence, construction, LiveForever, or public client contracts. The publisher is the sole service permitted to attach accepted representation bindings to a scene commit.

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| REPOHYB-001 | P0 | Provider registry, provider worker, quarantine/quality, publisher, and hybrid runtime shall be separate least-privilege boundaries. | Architecture test |
| REPOHYB-002 | P0 | Provider-specific code and fields shall remain inside adapters/SDK extensions and shall not leak into domain schemas. | Dependency and contract test |
| REPOHYB-003 | P0 | The representation publisher shall be the only component permitted to attach accepted derived assets to scene commits. | Authorization test |
| REPOHYB-004 | P1 | Local, research-shadow, private managed, and manual fixture providers shall conform to the same core contract suite. | Adapter conformance test |
| REPOHYB-005 | P1 | Benchmark fixtures and reports shall be versioned independently from production customer data. | Repository/CI test |
| REPOHYB-006 | P1 | Third-party provider source, patches, licenses, models, build images, and approvals shall be locked in the third-party manifest. | Supply-chain test |

## Build boundaries

### iOS capture

`CaptureCore` owns the state machine and never imports network/UI implementation details. `SensorAdapters` converts ARKit/AVFoundation/CoreMotion callbacks into immutable internal observations. `PackageWriter` persists assets and journal entries. `QualityGuidance` consumes a bounded stream of summaries and cannot block raw recording. `Transfer` uploads finalized immutable chunks. `Policy` decides sensor and destination permissions before acquisition.

### Control plane

The control API validates intent, delegates domain operations, and returns operation resources. It does not perform GPU work. Domain services own tables and publish events through an outbox. The workflow service schedules workers using content-addressed manifests and workload identity.

### Workers

Each worker image contains one bounded capability and no customer-facing web server. Inputs mount read-only; outputs write to a staging scope. The control plane verifies hashes and quality before publication. The LingBot image pins upstream source, patches, checkpoint, PyTorch/CUDA, and backend. Alternative learned models implement the same normalized observation contract.

### Shared packages

Shared packages are small, versioned, and deterministic. They may define schemas, coordinate math, authority labels, and policy evaluation. They may not become a hidden shared database access layer that defeats service ownership.

## Initial branch strategy

- `main` is releasable and protected.
- Short feature branches merge through reviewed pull requests.
- Release tags identify coordinated mobile/web/service/worker/schema/model manifests.
- Research model experiments live behind adapters and feature flags; they do not fork the canonical data model.
- Schema changes include compatibility fixtures and generated-code updates in the same change.

## Required CI jobs

1. lint, formatting, type and Swift concurrency checks;
2. unit/property tests;
3. JSON Schema/OpenAPI/Protobuf compatibility and code generation;
4. database migration build/upgrade/rollback-recovery rehearsal;
5. contract and integration tests using real service dependencies;
6. mobile fixture package generation/recovery tests;
7. security, secret, container, dependency, and SBOM scans;
8. license/model-manifest gate;
9. deterministic small-scene end-to-end pipeline;
10. benchmark smoke and viewer screenshot/interaction tests;
11. signed release artifact and provenance attestations.

## Third-party policy

Third-party source is not copied casually into application directories. Every component has an entry in `third_party/manifest.lock` with source, revision, license files, patches, build image, model/dataset relationship, and approval. Runtime downloads are disabled in production unless the exact hash and destination are part of the approved manifest.

## Version 1.1 hybrid-representation repository extension

```text
services/
  representation-api/
  provider-registry/
  representation-publisher/
workers/
  splat-surface/
  geometry-cleanup/
  collision-navigation/
  representation-quality/
packages/
  representation-contracts/
  provider-sdk/
  support-maps/
  geometry-policy/
adapters/spatial-providers/
  local-baseline/
  playcanvas-splat-transform/
  spark-runtime/
  research-milo/
  research-fast-pgsr/
  research-mesh2splat/
  manual-external-fixture/
apps/web-viewer/src/hybrid-runtime/
benchmarks/hybrid-representation/
tests/hybrid-representation/
```

Provider adapters have no authority to publish, edit evidence, or assign authority. Candidate outputs land in quarantine and pass independent validation. The local baseline and fixture adapter must work before research adapters are promoted.
