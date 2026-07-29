# LiveForever Preservation Operations

## Preservation objective

Create an open, fixity-verifiable release that preserves originals, provenance, transcript/media relationships, memory graph, conflicting recollections, truth labels, consent and rights state, narrative edition identity, scene manifests, and a static offline experience without depending on a proprietary cloud API.

## Release procedure

1. Select an exact narrative edition and current policy snapshot.
2. Reauthorize every source and derivative for the release purpose and audience.
3. Include originals and technical metadata without transforming the originals.
4. Include transcript layers while withholding private marks not authorized for the audience.
5. Preserve all alternate/conflicting recollections and source labels.
6. Include generated-content lineage and an unmistakable generated/reconstructed label.
7. Create open graph, timeline, transcript, and scene manifests.
8. Generate a static offline viewer with no network dependency.
9. Compute per-file hashes and a deterministic package root.
10. Verify archive safety and reopen the package in an isolated directory.
11. Record replicas, fixity schedule, format-migration history, succession, key recovery/deletion, billing/retention choices, and shutdown behavior.

## Revocation and disputes

Revocation stops new processing immediately and disables or queues deletion/restriction review for affected derivatives. It does not erase the fact that a revocation occurred from the immutable audit chain. Active authority disputes, minor-protection records, living-third-party restrictions, and explicit freezes block high-risk generated or visual reconstruction changes while preserving due-process access.

## Generated presence

Voice, likeness, dialogue, first-person simulation, and autonomous persona remain disabled by default. No preservation release may imply consciousness, factual certainty, or authorization beyond the current policy. Kill switches override earlier approvals and preserve only authorized audit and source records.

## Verification

Use `make demo-liveforever`, `make export-demo`, and `make restore-demo` in the deterministic reference profile. External review is still required for privacy, legal, accessibility, family governance, long-term format migration, independent repository custody, and human-subject use.

## Progress 06-R1 package identity

The preservation verifier uses an exact allowlist and complete SHA-256 manifest. Every package member other than `checksums.json` must be covered; required members must be present; unexpected, unchecked, duplicate, malformed, unsafe, or altered content fails closed. The root is computed from the complete declared member set.

Idempotent replay is a new verification, not a cached status read. The service reopens the current file, verifies all members, and compares its ZIP SHA-256 and Merkle root to the retained release record. Changed or missing bytes produce a stable conflict.
