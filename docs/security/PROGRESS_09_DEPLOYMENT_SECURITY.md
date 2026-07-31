# Progress 09 Deployment Security Model

## Trust boundaries

The milestone treats local hosts, edge nodes, hybrid transfer channels, cluster workloads, cloud accounts, provider services, object stores, queues, CDNs, and GPU pools as separate trust boundaries. Tenant and project context is never inferred from a profile ID or caller-supplied decision.

## Mandatory controls

- default-deny ingress and egress;
- exact workload identity scope, audience, purpose, tenant, project, workload, expiry, signature, and revocation checks;
- immutable image digests and source commits;
- external secret references only;
- residency admission before persistence or scheduling;
- redaction and approval before sensitive transfer;
- private encrypted data planes;
- signed redacted immutable CDN delivery;
- quota and budget admission before scaling;
- drift detection and fail-closed promotion.

## Forbidden content

Deployment manifests, source, logs, generated infrastructure, support bundles, and exports may not contain raw passwords, tokens, passcodes, access keys, private keys, credential secrets, or biometric values. Opaque secret references are permitted only under approved URI schemes.

## Evidence limitations

The local control suite proves contract behavior and structural configuration. It does not prove an effective cloud security group, Kubernetes network plugin, KMS key policy, secret-store IAM boundary, image signature, runtime container isolation, or physical edge encryption. These remain external evidence requirements.
