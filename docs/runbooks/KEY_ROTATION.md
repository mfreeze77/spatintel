# Encryption Key Rotation Runbook

## Envelope-key rewrap

1. Confirm the new key version is active and recoverable.
2. Select a bounded asset batch.
3. Verify existing metadata and plaintext content identity on a sample.
4. Rewrap data keys under the new key without changing ciphertext or plaintext SHA-256 identity.
5. Atomically update key-version metadata.
6. Verify decrypt and content hash after rotation.
7. Retain audit records, counts, failures, and rollback information.
8. Retire the prior key only after all dependent objects, backups, and restore paths are reconciled.

A rotation that cannot demonstrate successful restore under the new key is incomplete.
