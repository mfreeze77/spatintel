# Progress 09 AWS Reference Architecture Runbook

The AWS profile is an infrastructure-as-code reference, not evidence of an applied account. It is intentionally marked `synthetic_structural` and `production_approved: false`.

## Required pre-apply evidence

Before any credentialed plan or apply, retain:

- approved account and environment boundary;
- approved region and data-residency policy;
- final image digests, signatures, SBOMs, and vulnerability reports;
- secret-manager and KMS references;
- private networking and endpoint design;
- database/object-store backup and retention design;
- tenant quota, budget, and dead-letter policy;
- GPU egress and model-source controls;
- provider replacement and data-exit procedures;
- migration, rollback, queue, object-store, and graceful-shutdown test plans.

## Structural validation

```bash
python tools/generate_deployment_profiles.py --check
python tools/validate_infrastructure.py
terraform fmt -check -recursive infrastructure/terraform
```

When Terraform providers and credentials are available, run `init`, `validate`, and a reviewed `plan` in the target environment. Structural validation in this repository must not be labeled as an executed plan or applied deployment.

## Production stop line

Production remains denied until the release and deployment-control services can verify every required external evidence record. A caller-supplied Boolean, local profile, synthetic manifest, or structural test cannot grant production approval.
