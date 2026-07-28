# Controlled Deletion Runbook

1. Identify tenant/project/assets and the requesting authority.
2. Evaluate legal holds, preservation obligations, shared references, derivatives, indexes, exports, and backups.
3. Generate a dry-run dependency snapshot and retain its hash.
4. Create or verify a recovery backup and record its manifest/root.
5. Obtain two distinct authorized approvals.
6. Recheck that the dependency snapshot is unchanged.
7. Tombstone references and revoke access.
8. Remove eligible ciphertext and invalidate derivatives/caches.
9. Destroy eligible wrapped keys and retain key-version evidence.
10. Record residual backup copies and their expiry dates.
11. Verify normal reads, signed links, search, exports, and derivatives are denied.
12. Close only after audit-chain and recovery-state checks pass.

Never bypass dry run, backup, approval, or dependency recheck for convenience.
