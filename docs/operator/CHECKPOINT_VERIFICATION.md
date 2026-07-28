# Checkpoint verification

Progress checkpoints are evidence overlays around an exact committed source tree. Generated test reports and status documents are intentionally outside the `source/` namespace so they can identify the commit without creating an impossible self-referential Git hash.

Run:

```bash
python tools/verify_checkpoint.py \
  Spatial-Intelligence-Platform-v1.1.0-progress-04-r1.zip
```

The command exits nonzero for unsafe ZIP paths, duplicate or encrypted members, size/compression-limit violations, missing or unlisted files, hash/size/mode mismatches, a non-reproducible aggregate content root, a specification hash mismatch, a source-root mismatch, Git bundle/commit/tree/parent failure, a source archive mismatch, stale status files, contradictory checkpoint facts, duplicate or missing authoritative evidence categories, or evidence not bound to the packaged source.

The verifier needs only Python 3.11+ and Git. It does not trust the sidecar checksum or the checkpoint’s own success claim.

## Source identity

`governance/source-root-policy.json` is the single canonical exclusion policy used by tests, traceability, release tooling, checkpoint packaging, and checkpoint verification. Git tree identity binds the complete commit. The canonical source root separately binds executable and configuration inputs while excluding generated evidence, runtime state, dependency caches, and packaging metadata.

## Package structure

- `source/` — exact files from `git archive <commit>`;
- `artifacts/*.tar.gz` — exact source archive generated from the same commit;
- `artifacts/*.bundle` — Git bundle containing the milestone branch, parent, commit, and tree;
- `SOURCE_COMMIT.json` — full provenance and clean-worktree attestation;
- `build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json` — exactly one current artifact per required evidence category;
- `CHECKPOINT_CONTENT_MANIFEST.json` — every other package file’s size, mode, SHA-256, and aggregate content root.

The content manifest excludes only itself from the aggregate root to avoid a cryptographic self-reference. Its own bytes remain covered by the outer ZIP SHA-256 sidecar.
