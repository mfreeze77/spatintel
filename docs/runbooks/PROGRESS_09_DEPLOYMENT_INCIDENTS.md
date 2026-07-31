# Progress 09 Deployment Incident Runbook

For region, identity, update, drift, scaling, or secret-exposure incidents:

1. stop new admission and preserve the denial/audit evidence;
2. revoke affected edge/workload identities;
3. quarantine drifted nodes or workloads;
4. freeze profile and update promotion;
5. preserve image, release, configuration, queue, checkpoint, and object-store hashes;
6. restore the last approved signed release or deployment profile;
7. resume only from verified checkpoints;
8. verify no duplicate side effects and no cross-tenant leakage;
9. invalidate CDN authorizations and restricted derivatives when applicable;
10. issue an immutable incident and corrective-action record.

Never rotate or delete evidence before backup, legal-hold, retention, and chain-of-custody review.
