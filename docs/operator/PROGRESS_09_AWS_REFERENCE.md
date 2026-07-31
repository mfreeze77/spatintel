# Progress 09 AWS Reference Profile

The AWS profile is an infrastructure-as-code reference, not a deployed environment. It requires separate environment/account boundaries, private subnets, default-deny egress, encrypted private database and object storage, approved identities, KMS and secrets audit, GPU isolation, quota- and budget-governed queues, dead-letter handling, and signed redacted CDN derivatives.

All credentials are opaque `secret://` or `vault://` references. Raw passwords, tokens, private keys, access keys, and biometric secrets are prohibited from manifests.

Provider-specific components retain documented open export and replacement paths. Production admission remains denied until executable Compose, Kubernetes, Terraform, isolation, migration, rollback, queue, object-store, graceful-shutdown, signature, and external approval evidence exists.
