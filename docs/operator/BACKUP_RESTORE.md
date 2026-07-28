# Backup, Restore, and Disaster Recovery

## Backup scope

A recoverable installation requires coordinated copies of:

- PostgreSQL transaction state and WAL/PITR data;
- encrypted object blobs and object-version metadata;
- encryption-key and key-version metadata in the approved KMS/HSM system;
- provider/model/source manifests;
- audit-chain state;
- release, schema, migration, and configuration manifests;
- search/index rebuild instructions rather than treating caches as evidence;
- legal holds and retention/deletion state.

## Local rehearsal

The reference implementation can create and verify an isolated SQLite plus content-addressed-store backup. Run the controlled tests:

```bash
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/integration/test_lifecycle_recovery.py \
  tests/integration/test_export_restore.py \
  tests/migration/test_migrations.py
```

## Restore procedure

1. Declare the incident and freeze destructive automation.
2. Select a backup by retained manifest and root hash, not filename alone.
3. Verify release, schema, migration, and key compatibility.
4. Restore into an isolated environment first.
5. Verify database integrity and migration head.
6. Verify every sampled object decrypts and its plaintext hash equals its content identity.
7. Verify the audit hash chain.
8. Reconcile operations that were leased or running at backup time.
9. Rebuild non-authoritative indexes and caches from policy-eligible source data.
10. Execute cross-tenant, consent, export/import, and application smoke tests.
11. Promote only with incident-owner approval and retained evidence.

## Preservation restore

The open preservation package is independent from installation backup. It contains project data, content hashes, semantic identity, scene history, evidence links, and policy summaries. It is the portability path when the original stack no longer exists.

```bash
make export-demo
make restore-demo
```

A matching archive hash alone is insufficient; the restore must also prove matching root hashes and semantic identities.

## Recovery limitations

Cloud PITR, object-version restore, KMS disaster recovery, multi-region failover, and target-account recovery require credentialed environment evidence. The local rehearsal does not substitute for them.
