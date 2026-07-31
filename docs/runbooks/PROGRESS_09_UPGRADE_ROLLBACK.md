# Progress 09 Upgrade and Rollback

1. Freeze new admissions and drain workers through graceful shutdown.
2. Retain operation checkpoints, lease release, queue state, object-store root, and pre-upgrade preservation export root.
3. Apply the append-only migration and digest-pinned release.
4. Verify post-upgrade export semantic identity, object-store continuity, queue continuity, checkpoint resume, and duplicate-side-effect count of zero.
5. On failure, verify the signed rollback bundle, restore the previous release, rehearse schema recovery or forward-fix, and compare rollback export identity.
6. Record the rehearsal with exact release/schema versions, roots, parameters, environment, and evidence.

A failed or incomplete rehearsal blocks production admission.
