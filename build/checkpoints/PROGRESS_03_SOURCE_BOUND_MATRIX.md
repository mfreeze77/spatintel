# SIP v1.1.0 Progress Checkpoint 03 — Source-Bound Test Matrix

Generated: 2026-07-27
Branch: `hybrid-governed`
Worktree: `/mnt/data/sip-hybrid-work`
Base commit: `8af0aafa0425b3f190b14fa63701990f0bd6d343`

## Verification result

The isolated, resumable, source-bound Python matrix passed with the same source-tree root for every suite:

```text
Source-tree root SHA-256: 0062be01d0aca663d38894aca2506e8785965def12208479e4758961e5620345
Contract:      97 passed
Integration:   56 passed
Migration:      5 passed
Security:       3 passed
Unit:          20 passed
Property:       1 passed
Privacy:        1 passed
End-to-end:     5 passed
Acceptance:     2 passed
Specification:  1 passed
Total:        191 passed, 0 failed, 0 errors, 0 skipped
```

Every suite retains JUnit XML, logs, per-test-file shard results, shard manifests, input roots, output hashes, environment evidence, and the shared source-tree root.

## Additional implementation added before this matrix

- Deterministic 15-item synthetic fixture corpus with valid canonical capture, future schema, tampered capture, truncated archive, path traversal, compression bomb, embedded script metadata, coordinate/transform cases, proxy failure case, cross-tenant attempts, provider failures, Construction data, and conflicting LiveForever recollections.
- Deterministic fixture generator with drift-check mode.
- Construction and LiveForever vertical manifests and operating entry-point documentation.
- Regenerated service/worker ownership catalog.
- OpenAPI operation-count contract updated to the intentional 103-operation surface.

## Not yet claimed at this checkpoint

Swift/Xcode-platform validation, web production build/browser E2E, static/type/security/license gates, benchmarks, refreshed demonstration evidence, final traceability fixed point, release lint, release bundle, commit, and tag remain pending.
