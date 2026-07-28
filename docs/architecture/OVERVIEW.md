# SIP Architecture Overview

## Product boundary

The Spatial Intelligence Platform is an evidence-aware control plane for spatial captures, derived representations, stable semantic entities, policy, and preservation. The architecture deliberately separates five concerns that must not be collapsed:

1. **Evidence** — immutable original captures and source records.
2. **Metric** — geometry eligible for metric reasoning under an explicit uncertainty and authority policy.
3. **Visual** — photorealistic representations such as Gaussian splats.
4. **Interaction** — disposable collision, navigation, picking, occlusion, and audio proxies.
5. **Design** — BIM or authored intent that does not become observed fact merely because it aligns visually.

A representation may reference another representation, but it cannot silently inherit authority. Stable scene identities are UUIDs and semantic support references; they never depend on triangle, voxel, Gaussian, tile, or LOD indices.

## Logical services

The local profile may colocate code, while the contracts retain independent logical boundaries:

| Service | Authoritative responsibility |
|---|---|
| `control-api` | Coherent public control-plane surface and health probes |
| `identity-policy` | Identity, tenant/project access, purpose, audience, consent, classification, and restricted-region decisions |
| `capture-service` | Capture-package admission, validation, resumable upload, immutable source registration |
| `workflow-service` | Durable operations, leases, retries, checkpoints, cancellation, progress, and outbox events |
| `scene-service` | Stable entities, anchors, measurements, scene commits, branches, diffs, and rollback |
| `evidence-service` | Asset and provenance access subject to current policy |
| `search-service` | Scoped text/spatial/index queries and index invalidation |
| `export-service` | Policy-aware open export, integrity manifests, import, and preservation restore |
| `notification-service` | Alerts that never function as authorization grants |
| `audit-service` | Append-only, hash-chained security and domain audit records |
| `representation-api` | Candidate inspection and use-specific quality state |
| `provider-registry` | Signed provider/model capability and governance manifests |
| `representation-publisher` | Sole authority for atomically attaching accepted representations to scene commits |

Each service entry point is under `services/<service>/`; its `service.json` is compared to the generated OpenAPI contract in tests.

## Durable worker plane

Every worker has:

- one `worker-manifest.json` with immutable code/protocol/sandbox digests;
- one capability-scoped workload identity;
- a signed, expiring lease that binds operation, input asset, resource envelope, output staging scope, and identity;
- no scene-publication permission;
- no shell or network access in the deterministic compute sandbox;
- a private writable staging volume and read-only source/configuration mounts;
- bounded summaries through the operation protocol and full output through encrypted content-addressed storage;
- a receipt linking input, parameters, environment, model/provider manifests, checkpoints, output, and candidate hashes.

Worker completion creates a quarantined candidate. Independent quality review and the publisher transaction are separate operations.

## Data stores

- **PostgreSQL/PostGIS** is the production transactional and spatial metadata system.
- **SQLite** is the deterministic local/test profile and is exercised through the same append-only Alembic chain.
- **S3-compatible object storage** holds encrypted content-addressed blobs. Local filesystem storage provides a reference implementation; MinIO is a local-only compatibility fixture.
- **Valkey/Redis-compatible coordination** supports queues, caching, and idempotency behind an abstraction.
- **Open export packages** provide independent preservation and restore without requiring the running service stack.

Object identity is the plaintext SHA-256. Ciphertext and wrapped keys can rotate without changing evidence identity.

## Principal flows

### Capture and reconstruction

1. The client journals observations locally and finalizes an immutable capture package.
2. Multipart upload validates chunks and the final root hash.
3. Policy authorizes decrypted access for an approved operation and provider.
4. Normalization preserves coordinate, timestamp, calibration, pose-stream, depth, and source distinctions.
5. Reconstruction workers emit quarantined metric, visual, and interaction candidates.
6. Independent quality review assigns intended-use approval.
7. The publisher atomically attaches accepted assets to a scene commit.

### Proxy pick to measurement

1. The renderer returns an interaction-proxy hit.
2. The scene service follows the proxy support map to eligible metric evidence.
3. The metric representation resolves a coordinate and uncertainty.
4. A verified measurement additionally requires source assets, calibration, verifier identity, and verification time.
5. Failure to resolve metric evidence returns a non-authoritative observation, never a verified value.

### Consent revocation

1. A consent grant scopes subject, purpose, audience, derivatives, and expiration.
2. Current authorization is reevaluated at every service boundary and historical-link open.
3. Revocation updates affected source and derivative policy state.
4. Indices, caches, editions, generated derivatives, and exports are invalidated or denied.
5. Audit and preservation records retain that revocation occurred without exposing revoked content.

## Deployment profiles

- **Local:** Docker Compose with local database, object store, queue/cache, logical services, workers, and optional observability.
- **Hybrid:** local capture and sensitive storage with approved remote compute providers constrained by data class, purpose, region, and retention.
- **AWS reference:** Terraform modules for network, identities, encryption, object storage, database, queue/cache, backup, logging, and Kubernetes integration.

Static manifests are not deployment evidence. Production readiness requires image replacement with built digests, signature verification, vulnerability results, secret-manager bindings, server-side Kubernetes validation, Terraform plan/apply evidence, restore rehearsal, and environment acceptance.

## Repository invariants

Run these before review:

```bash
make lint
make spec-check
make test
make infrastructure
make security
make license-check
```

Release promotion is controlled by `tools/release.py --mode release`; a candidate bundle can be generated while blocked, but a blocked candidate cannot be represented as a release.
