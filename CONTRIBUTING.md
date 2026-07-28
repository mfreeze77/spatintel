# Contributing

## Ownership and review

Every change must identify its requirement IDs or ADR, its owning path from `CODEOWNERS`, and the reviewers needed for the trust boundary it changes. At least one code owner reviews ordinary changes. Security/privacy reviewers are required for authorization, consent, cryptography, secret handling, external providers, telemetry egress, destructive operations, or new data purposes. Geometry/quality reviewers are required for coordinate, reconstruction, measurement-authority, collision, or navigation changes.

Reviewers verify implementation, negative/failure behavior, tests, retained evidence, schemas, migrations, documentation, licensing, and rollback. A passing test alone does not authorize a production claim.

## ADR process

Create or update an ADR under `docs/adr/` for changes that alter architecture boundaries, durable contracts, authority/truth semantics, storage identity, encryption, tenancy, provider/model governance, deployment topology, migration policy, or irreversible operational behavior. ADRs state context, decision, alternatives, consequences, rollback/reversibility, affected requirement IDs, and required reviewers.

## Contracts and migrations

Public JSON Schema, OpenAPI, Protobuf, event, and generated-client changes must be versioned and pass compatibility/drift checks. Never reuse a Protobuf field number. Never modify an existing released migration; append a new migration and test clean install, supported upgrade, backup/restore, and rollback or explicit forward-fix behavior.

## Provider, model, data, and dependency governance

Provider/model additions fail closed until manifests record exact hashes, source/license rights, permitted data classifications, purposes, regions, retention, security/privacy review, benchmarks, and expiration/revocation. Source licensing does not imply model-weight or training-data permission. Preserve notices and update the SBOM/license inventory.

## Required change evidence

A completed change includes typed contracts where applicable, stable errors, authorization, audit, metrics, retention/deletion effects, user/operator/developer documentation, deterministic fixtures, tests carrying requirement IDs, and machine-readable results. Never commit private production data, credentials, generated secrets, unapproved checkpoints, or customer spatial content.

## Release gates

Pull-request CI must pass structural formatting/lint, compilation/type checks, unit/property/contract/integration/security/privacy/migration/acceptance tests, schema compatibility, specification traceability, secret and license gates, and applicable benchmarks. Release promotion additionally requires a clean exact tag, frozen dependency graph, signed artifacts, SBOM, vulnerability and container scans, backup/restore and migration evidence, all mandatory requirements resolved, and external validation evidence. `tools/release.py --mode release` is intentionally fail closed; do not bypass it or add a production-ready marker manually.
