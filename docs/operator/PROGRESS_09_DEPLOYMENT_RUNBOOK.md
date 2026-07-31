# Progress 09 Deployment Profiles and Admission Runbook

## Scope and posture

This runbook covers the bounded `OPS-003` development milestone. It defines local-only, edge, hybrid, and AWS-reference deployment contracts. It does not authorize production traffic, production credentials, customer data, `OPS-004` recovery certification, `QA-002` final release gates, or Progress 10.

Every generated profile and AWS reference manifest is synthetic structural evidence. A structurally valid document is not proof that Docker, Kubernetes, an edge device, Terraform, or AWS was executed.

## Authoritative controls

The `deployment-control` logical service owns:

- deployment profile registration and immutable revision hashes;
- project-to-profile binding;
- residency and hybrid-transfer policy;
- asset-upload and worker-scheduling admission;
- edge enrollment, signed software identity, health, and revocation;
- signed offline update application and rollback;
- deployment-mode migration;
- local upgrade and graceful-shutdown rehearsals;
- autoscaling quota and budget admission;
- AWS reference manifests;
- CDN derivative admission;
- provider replacement paths;
- configuration drift and fail-closed production admission.

The service does not accept caller-computed allow decisions. Every admission result is recomputed server-side and retained with an audit/outbox record.

## Profile generation and validation

Generate deterministic non-production fixtures:

```bash
python tools/generate_deployment_profiles.py
python tools/generate_deployment_profiles.py --check
```

The profiles are stored in `infrastructure/deployment/profiles/`. They must retain:

- immutable image digests;
- explicit infrastructure versions;
- opaque secret references only;
- default-deny ingress and egress;
- explicit egress allowlists;
- positive CPU and memory limits;
- supported regions;
- feature-specific cloud-dependence and degraded behavior;
- open provider replacement paths;
- `production_authorized: false`.

A zero-filled image digest is a development sentinel. It must never be represented as a built or approved production image.

## Residency and transfer admission

Before asset upload or worker scheduling:

1. resolve the active project deployment binding;
2. require an explicit deployment region;
3. evaluate the tenant/project residency policy;
4. evaluate the asset class, worker class, purpose, and deployment mode;
5. evaluate hybrid-transfer stage and approval when applicable;
6. persist the allow or denial evidence;
7. proceed only after an allow decision.

Denials must not be rolled back with the rejected upload or scheduling transaction.

## Edge enrollment and updates

An edge node may enroll only when it presents:

- stable node identity;
- public-key hash;
- a signed software manifest;
- digest-pinned image;
- full source commit;
- release identity;
- disk-encryption attestation;
- supported region and capabilities.

Enrollment issues a short-lived workload identity scoped to the tenant, optional project, edge workload, audience, purpose, and exact runtime scope. Revocation must revoke both the edge record and workload identity.

Offline update manifests require signed forward and rollback bundles, pinned images, migration head, compatible export versions, and exact source commit. Rollback must be rehearsed without changing stable project or evidence identity.

## Upgrades, migration, and graceful shutdown

A local upgrade rehearsal is verified only when:

- pre-upgrade, post-upgrade, and rollback exports have matching semantic roots;
- object-store and queue continuity roots are retained;
- migration and rollback evidence is complete;
- jobs are checkpointed and resumable;
- no job is lost;
- no duplicate side effect is observed.

A project deployment-mode migration snapshots and compares stable IDs, scene history, permissions, consent, asset hashes, operation manifests, model manifests, and export roots before it changes the active binding.

Graceful worker shutdown requires checkpoint coverage for every in-flight operation, released leases, zero lost jobs, and zero duplicate side effects.

## Autoscaling and GPU queues

Autoscaling policy must define:

- minimum and maximum replicas;
- per-profile quotas;
- tenant concurrency limit;
- global budget limit and currency;
- dead-letter queue and retry limit;
- restricted egress.

Identical simultaneous requests resolve to one durable decision and governed idempotent replay. A raw database uniqueness error must never escape to a scheduler.

## AWS reference posture

The AWS reference manifest is accepted only when it declares:

- separate environment/account boundaries;
- private subnets and default-deny egress;
- private, encrypted, backed-up database and object storage;
- approved workload identities and endpoints;
- quota-, budget-, and dead-letter-aware queues;
- signed CDN authorization for immutable redacted derivatives only;
- no raw asset CDN origin;
- least-privilege audited KMS and secrets access;
- isolated GPU pools with restricted egress and approved pre-baked models;
- replacement/export paths for database, object store, queue, workflow, KMS, secrets, CDN, and GPU services.

Raw passwords, private keys, access tokens, or secret values are prohibited in manifests. Use only opaque secret references.

## Drift and production admission

`detect_drift` compares observed deployment controls to the immutable profile. Any image, network, region, secret-reference, resource, version, or canonical-contract mismatch is retained as drift.

Production admission remains fail-closed unless independent evidence exists for executed Compose, Kubernetes, Terraform, tenant isolation, default-deny networking, secret scanning, image signatures, migration and rollback rehearsal, queue and object-store continuity, graceful shutdown, externally approved AWS infrastructure, and externally approved profile evidence.

The Progress 09 checkpoint must report:

```text
Progress 09: delivered for independent True North review
Progress 10: unauthorized
Production: NO-GO
Production authorized: false
```
