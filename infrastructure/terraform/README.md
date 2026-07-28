# SIP Terraform profiles

The profiles are deliberately separate from the Kubernetes manifests:

- `state-bootstrap`: one-time encrypted and versioned remote-state bucket. Terraform 1.15 native S3 lockfiles are used; DynamoDB locking is not required.
- `profiles/local`: auditable manifest for the Docker Compose profile. It does not pretend to provision Docker when the Terraform Docker provider is absent.
- `profiles/hybrid`: hardens an existing Kubernetes namespace and records external PostgreSQL, Valkey, and object-storage endpoints without storing credentials in Terraform state.
- `profiles/aws`: three-AZ VPC, private EKS 1.34, PostgreSQL 18.4, Valkey 9.1, KMS, immutable evidence storage, audit trail, backups, budgets, ECR, and pod identities.

## Required validation

Provider lockfiles are **not fabricated**. From a networked operator workstation with Terraform 1.15.5:

```bash
cd infrastructure/terraform/state-bootstrap
terraform init
terraform validate
terraform plan -out bootstrap.tfplan

cd ../profiles/aws
terraform init -backend-config=backend.hcl
terraform validate
terraform plan -out sip.tfplan
terraform show -json sip.tfplan > ../../../build/evidence/terraform-plan.json
```

The AWS profile will not accept blank EKS add-on pins. Resolve exact versions in the target region before planning. Cloud credentials, deployment, and restore rehearsal remain `EXTERNAL_VALIDATION_REQUIRED` until evidence from the target account is retained.
