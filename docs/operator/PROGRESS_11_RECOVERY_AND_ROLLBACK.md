# Progress 11 Recovery and Rollback Instructions

1. Stop new release-candidate admission and quiesce long operations.
2. Verify the selected prior release, recovery point, manifests, signatures, and source root.
3. Rehearse or execute the append-only migration rollback path only with retained backup, dry-run, audit, and rehearsal evidence.
4. Restore the prior application release and compatible schema state in isolation.
5. Reconcile canonical assets, evidence, semantic identity, audit sequence, queues, exports, and root hashes.
6. Confirm no data loss, consent regression, authority promotion, or resurrection of deleted data.
7. Retain the failed candidate and all diagnostic evidence; create new operation and release lineage rather than rewriting history.
8. Reopen writes only after independent review.

Open export and independent restore are mandatory recovery paths. Local rehearsal evidence is not cloud or production disaster-recovery certification.
