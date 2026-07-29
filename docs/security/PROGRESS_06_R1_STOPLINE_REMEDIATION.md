# Progress 06-R1 Stop-Line Remediation

Progress 06-R1 is a narrow security, privacy, provenance, package-integrity, and test-isolation correction to the accepted Progress 06 development snapshot. It introduces no Progress 07 functionality and does not authorize production.

## Scoped mutation controls

Consent revocation and Construction deficiency retesting require tenant and project scope in both the HTTP route and service method. The legacy unscoped routes remain non-schema compatibility traps that always fail with `PROJECT_SCOPE_REQUIRED`; they cannot mutate state. Cross-tenant lookups return the same non-disclosing not-found response as an unknown identifier.

Issue closure derives the verifier identity from the authenticated principal. Request bodies cannot supply or override a verifier. A reporter cannot independently verify the issue they reported.

## Restricted owner exports

A restricted annex requires the exact `construction:restricted_export` permission and an immutable approval record. The approval is bound to tenant, project, normalized scope, classification, audience, purpose, approver, expiry, and request hash. Project administrators cannot self-assert approval with request booleans, and the approver cannot also be the export requester.

## Portable package integrity

Construction owner handoff and LiveForever preservation packages use an exact package profile. Every required file must be present; every member other than `checksums.json` must be listed once with a lowercase SHA-256 digest; every listed member must exist; unexpected or unchecked members fail verification; duplicate JSON keys, empty/partial maps, unsupported algorithms, malformed digests, root mismatch, path abuse, duplicate ZIP members, symlinks, size abuse, and compression abuse fail closed.

Idempotent replay rereads and verifies the current archive. It compares the current ZIP SHA-256 and package Merkle root with the retained release identity. Missing, changed, or invalid package bytes return a stable conflict instead of a stale `verified` response.

## Immutable provenance

Construction document revisions and IFC/BCF interchange records require a live immutable source asset reference in the same tenant and project. Missing, tombstoned, cross-tenant, cross-project, or hash-mismatched assets are rejected before a vertical record is created.

## Hermetic test execution

Every isolated Python shard receives a process-private runtime root, SQLite database, object store, and multipart directory under the matrix writer token. Shards cannot initialize or mutate the repository-wide `runtime/sip.sqlite3` database.

## Retained external gaps

The frozen web-production toolchain, mounted viewer integration, Apple/LiDAR hardware, approved LingBot checkpoint and GPU, executable cloud/infrastructure deployment, penetration testing, formal privacy review, accessibility review, usability review, and legal approval remain external. Production remains NO-GO.
