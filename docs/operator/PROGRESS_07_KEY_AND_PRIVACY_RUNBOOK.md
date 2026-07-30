# Key, privacy, audit, and incident runbook

## Key operations

Keys are scoped to tenant/project/person policy and backed by an approved KMS, HSM, or offline-recovery control. Every unwrap/rewrap/revoke event records actor/workload, purpose, resource scope, and outcome. Recovery requires quorum and forbids one-person permanent control. Emergency revocation records bounded impact and residual replica/backup timelines.

## Privacy inventory and impact review

Inventory each data category with purpose, legal/consent basis, processors, residency, retention, security controls, classification, and rights workflow. A new provider or purpose requires an approved privacy-impact assessment before processing.

## Rights requests

Verify the requester; retain scope and due date; process canonical records, derivatives, indexes, caches, exports, and backups; attach SHA-256-addressed evidence; and complete only when every store has an explicit outcome. Replays with different evidence fail closed.

## Audit verification

Verify the hash/signature chain and every referenced manifest. A gap, mutation, invalid signature, missing manifest, or mismatched hash fails verification. Ordinary application roles have no audit update/delete permission in the production database role.
