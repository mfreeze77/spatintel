# Deployment Guide

## Release input requirements

Deploy only a release record whose readiness is `ready`, whose `SHA256SUMS` verify, and whose Ed25519 signature matches the approved public key. A candidate with blockers is useful for review but is not deployable production material.

Verify locally:

```bash
sha256sum -c build/release/<candidate>/SHA256SUMS
python tools/release.py --mode release
```

## Local Compose profile

1. Copy `.env.example` to `.env`.
2. Generate development-only secrets:

```bash
make bootstrap
```

3. Review image digests and local-only components.
4. Start:

```bash
docker compose -f infrastructure/compose/docker-compose.yml up --build
```

5. Verify health, migrations, object writes, queue operations, worker leases, and all logical service routes.
6. Run the foundation export/restore demonstration against the running dependencies.

MinIO in this repository is a local compatibility fixture and is not an approved production object-store baseline.

## Kubernetes profile

The base manifests are generated from service and worker manifests. Before applying:

- replace all image sentinels with built immutable digests;
- verify image signatures and vulnerability reports;
- bind service accounts to workload identities;
- bind secrets through the approved secret manager or CSI driver;
- apply network policies before workloads;
- validate resource limits, disruption budgets, storage classes, and topology;
- server-side dry-run against the target cluster version;
- run migration as a controlled job with backup and rollback evidence.

Example validation sequence:

```bash
kubectl kustomize infrastructure/kubernetes/base > /tmp/sip.yaml
kubectl apply --server-side --dry-run=server -f /tmp/sip.yaml
```

Do not apply generated image sentinels.

## Terraform AWS reference profile

The AWS profile is a reference implementation, not an account-neutral promise. Use a dedicated environment/account boundary and remote state with encryption and locking.

```bash
cd infrastructure/terraform/environments/aws
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=sip.tfplan
terraform show -json sip.tfplan > sip.tfplan.json
```

Review identity trust policies, KMS grants, S3 public-access blocks, database networking, backup retention, logs, egress, quotas, and deletion protection before apply. Retain the plan hash and apply output in the deployment record.

## Deployment verification

At minimum, retain evidence for:

- release record and signature;
- built image digests and signatures;
- SBOM and vulnerability results;
- migration and backup IDs;
- health and readiness probes;
- cross-tenant authorization probes;
- object encryption and signed-read behavior;
- worker identity and egress denial;
- telemetry collection without sensitive labels;
- export and clean restore;
- rollback procedure.
