# Progress 09 Edge and Hybrid Runbook

Edge enrollment requires a unique node identity, signed software manifest, encrypted-disk attestation, declared region, capabilities, and a short-lived workload identity. A revoked node cannot report health or apply updates.

Offline updates require a signed immutable manifest, exact source commit, digest-pinned images, compatible export versions, and a separately signed rollback bundle. Apply and rollback are idempotent and audited.

Hybrid transfer policy is deny-by-default and binds asset class, minimum processing stage, destination region, purpose, and independent approval. Raw or sensitive material cannot leave the site before the declared safe stage.

Project-mode migration preserves stable IDs, scene history, permissions, consent, content hashes, exports, operations, and model manifests. Compare source and target semantic snapshot hashes before declaring completion.
