# ADR-0012: Post-commit checkpoint evidence overlays

## Status

Accepted for Progress 04-R1.

## Context

A Git commit cannot practically contain its own final SHA in a tracked report because changing the report changes the commit. Checkpoint reports must still identify the exact tested commit, tree, parent, and source root.

## Decision

The exact committed project is packaged under `source/` and is independently reproduced by a Git archive and Git bundle. Test reports, status documents, milestone scope, release pointers, and the authoritative evidence index are generated only after the clean commit is tested and are packaged outside `source/`.

The canonical source root excludes generated evidence and packaging metadata according to `governance/source-root-policy.json`. The Git tree ID binds the complete committed tree. The outer checkpoint content root binds all post-commit evidence and source artifacts.

## Consequences

- No report falsely claims to be both part of and evidence for its own Git commit.
- Checkpoint verification must validate both Git provenance and the outer content manifest.
- Source archives remain exact and independently restorable.
- Generated status documents cannot silently alter the tested source root.

## Traceability

- Requirements: DELDOD-001, DELDEV-004, TSTGATE-003, OPSCICD-002
- Risks: self-referential commit claims, dirty-worktree evidence, packaging-induced source-root drift, stale release pointers, unverifiable source continuity
- Benchmarks: checkpoint content-root reproduction; Git archive/source-manifest byte equivalence; independent inner and outer verifier execution
- Source evidence: `tools/build_checkpoint.py`; `tools/verify_checkpoint.py`; `tools/source_identity.py`; `governance/source-root-policy.json`
- Exit/export strategy: every checkpoint includes a Git bundle, exact source archive, source-file manifest, SHA-256 sidecars, and independently verifiable content manifests
- Security/privacy review: checkpoint archives reject unsafe paths, symlinks, duplicate members, compression abuse, stale evidence, and source or authorization contradictions
