# Progress 10 Recovery Incident Runbook

1. Freeze writes and new destructive operations for the affected scope.
2. Record stable incident and correlation identifiers.
3. Preserve audit heads, deployment profile, residency policy, key references, queue state, and object manifests.
4. Select a verified point at or before the approved target time.
5. Use an isolated target unless an independently approved in-place procedure exists.
6. Reconcile all hashes and references before reopening writes.
7. If recovery is impractical, produce and independently verify the complete open portability package.
8. Record RPO/RTO, gaps, unresolved references, rollback actions, and corrective requirements.
9. Do not cross regions, expose root keys, weaken holds/consent, or resurrect deleted data.
10. Keep production admission denied until separately authorized external evidence exists.
