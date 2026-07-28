# Incident Response

## Severity triggers

Treat these as high-severity until scoped:

- suspected cross-tenant access;
- leaked signed URL or privileged credential;
- consent, audience, or redaction failure;
- object corruption or audit-chain break;
- unauthorized provider/model execution;
- destructive deletion without matching approvals;
- false verified measurement or authority escalation;
- immersive collision/navigation safety failure;
- backup or restore integrity failure.

## First actions

1. Preserve clocks, logs, release IDs, trace IDs, operation IDs, audit roots, and relevant object hashes.
2. Disable affected provider, model, route, key, link class, or worker identity with the narrowest effective kill switch.
3. Stop publication and destructive automation when truth, consent, or custody may be affected.
4. Do not copy raw private media into tickets or chat systems.
5. Open a legal/privacy escalation when living people, minors, biometrics, critical infrastructure, or preservation obligations are involved.

## Containment patterns

- Revoke provider/model manifest approval.
- Rotate signed-read and workload credentials.
- Quarantine affected candidates and supersede scene commits without deleting history.
- Invalidate search/vector/cache derivatives.
- Place assets under legal hold before forensic work when required.
- Disable generated voice, likeness, dialogue, or first-person experience globally through kill switches.

## Recovery and closure

Recovery must use a reviewed release and verified backup/export. Before closure, record root cause, affected tenants/projects/assets/derivatives, containment times, disclosure decisions, restoration evidence, and corrective requirements/tests.

The detailed telemetry-specific procedure is in `docs/runbooks/OBSERVABILITY_INCIDENTS.md`.
