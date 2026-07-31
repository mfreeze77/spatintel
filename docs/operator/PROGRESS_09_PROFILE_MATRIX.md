# Progress 09 Deployment Profile Matrix

| Profile | Offline/local operation | Cloud dependency | External validation required |
|---|---|---|---|
| local-only | Yes | None for core capture, scene, evidence, and export | Host hardening, executable Compose, upgrade/rollback |
| edge | Yes | Optional synchronization | Physical disk encryption, device identity, signed update and rollback |
| hybrid | Yes with queued/degraded modes | Approved transfer/GPU/provider operations | Transfer boundary, network, residency, cloud worker execution |
| AWS reference | Degraded local/export paths | Private AWS data plane and workload services | Terraform plan/apply, EKS, IAM, KMS, RDS, S3, queues, CDN, GPU |

All profiles expose the same canonical package, scene, evidence, and export contracts. Profile selection must not change truth, authority, consent, or stable semantic identity.
