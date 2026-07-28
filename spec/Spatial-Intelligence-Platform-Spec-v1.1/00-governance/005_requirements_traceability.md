---
spec_id: SIP-RTM
title: "Requirements Traceability Matrix"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---

# Requirements Traceability Matrix

This matrix is generated from requirement tables in the specification modules. A requirement is not complete until its implementation evidence, verification result, release, responsible owner, and any waiver or supersession are recorded in the delivery system. Requirement identifiers are immutable.

## Summary

| Category | P0 | P1 | Total |
|---|---:|---:|---:|
| appendix | 5 | 5 | 10 |
| architecture | 32 | 43 | 75 |
| capture | 31 | 36 | 67 |
| construction | 53 | 53 | 106 |
| data | 59 | 59 | 118 |
| governance | 35 | 39 | 74 |
| liveforever | 53 | 53 | 106 |
| operations | 50 | 50 | 100 |
| platform | 61 | 61 | 122 |
| reconstruction | 81 | 81 | 162 |
| testing | 44 | 44 | 88 |

**Total normative requirements:** 1,028

## Required delivery fields

Each implementation record shall add: owner, status, design/ADR link, implementation change, test or field-procedure ID, exact input/configuration/model/provider manifest, evidence artifact hash, first passing release, last regression result, waiver (if any), and supersession link (if any).

## Catalog

### APPFAIL-001 — Failure Mode and Recovery Catalog

- **Priority:** P0
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** The catalog shall cover mobile interruption, tracking loss, corrupt package, hash mismatch, clock error, bad calibration, pose collapse, misalignment, false loop, depth-scale error, dynamic contamination, mesh defect, model/license block, queue/provider outage, index staleness, permission leak, redaction failure, and deletion error.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-002 — Failure Mode and Recovery Catalog

- **Priority:** P0
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Each failure shall have severity, retryability, safe checkpoint, operator action, customer message, audit requirement, and test reference.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-003 — Failure Mode and Recovery Catalog

- **Priority:** P0
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Fatal failures shall preserve diagnostic manifests without exposing sensitive raw data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-004 — Failure Mode and Recovery Catalog

- **Priority:** P1
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** A failure classified as unsafe shall prevent publication even when partial outputs exist.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-005 — Failure Mode and Recovery Catalog

- **Priority:** P1
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Recovery shall create new run/commit lineage rather than rewriting the failed record.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-006 — Failure Mode and Recovery Catalog

- **Priority:** P1
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Failure-code compatibility shall be maintained for API clients and support analytics.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-007 — Failure Mode and Recovery Catalog

- **Priority:** P0
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** The failure catalog shall cover provider denial/revocation, malformed outputs, transform error, false geometry, anchor failure, redaction propagation, authority misuse, and immersive safety.
- **Minimum verification:** Failure-catalog audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-008 — Failure Mode and Recovery Catalog

- **Priority:** P0
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Hybrid failure shall preserve source, metric, visual, evidence, and prior accepted assets without partial publication.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-009 — Failure Mode and Recovery Catalog

- **Priority:** P1
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Picking, collision, navigation, occlusion, audio, and visual rendering shall fail independently with explicit fallbacks.
- **Minimum verification:** Component failure test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### APPFAIL-010 — Failure Mode and Recovery Catalog

- **Priority:** P1
- **Category:** appendix
- **Source:** [`99-appendices/995_failure_mode_catalog.md`](../99-appendices/995_failure_mode_catalog.md)
- **Requirement:** Recovery shall create new operation/revision lineage and shall not erase failed provider evidence.
- **Minimum verification:** Recovery audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCADR-001 — Architecture Decision Record Process

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/210_architecture_decisions.md`](../20-architecture/210_architecture_decisions.md)
- **Requirement:** An ADR shall link to requirements, risks, benchmarks, and source evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCADR-002 — Architecture Decision Record Process

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/210_architecture_decisions.md`](../20-architecture/210_architecture_decisions.md)
- **Requirement:** A vendor choice shall include an exit and export strategy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCADR-003 — Architecture Decision Record Process

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/210_architecture_decisions.md`](../20-architecture/210_architecture_decisions.md)
- **Requirement:** A model ADR shall include license, checkpoint, hardware, benchmark, operating envelope, and fallback.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCADR-004 — Architecture Decision Record Process

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/210_architecture_decisions.md`](../20-architecture/210_architecture_decisions.md)
- **Requirement:** Security and privacy reviewers shall approve decisions that expand data use or trust boundaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCADR-005 — Architecture Decision Record Process

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/210_architecture_decisions.md`](../20-architecture/210_architecture_decisions.md)
- **Requirement:** CI shall validate ADR identifiers and links referenced by schemas or code ownership files.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCCTX-001 — System Context and External Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/200_system_context.md`](../20-architecture/200_system_context.md)
- **Requirement:** The context model shall identify data controller/processor responsibility for each deployment profile.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCCTX-002 — System Context and External Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/200_system_context.md`](../20-architecture/200_system_context.md)
- **Requirement:** Every inbound source shall pass schema, malware, decompression-bomb, and content-policy checks before processing.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCCTX-003 — System Context and External Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/200_system_context.md`](../20-architecture/200_system_context.md)
- **Requirement:** Every outbound export shall apply permissions, consent, redaction, watermarking policy, and audit logging.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCCTX-004 — System Context and External Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/200_system_context.md`](../20-architecture/200_system_context.md)
- **Requirement:** External service outages shall degrade bounded capabilities without corrupting canonical data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCCTX-005 — System Context and External Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/200_system_context.md`](../20-architecture/200_system_context.md)
- **Requirement:** Trust-boundary changes shall require threat-model review.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCDEP-001 — Deployment Profiles and Topology

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/202_deployment_architecture.md`](../20-architecture/202_deployment_architecture.md)
- **Requirement:** Each profile shall declare which features require cloud connectivity and what happens when unavailable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCDEP-002 — Deployment Profiles and Topology

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/202_deployment_architecture.md`](../20-architecture/202_deployment_architecture.md)
- **Requirement:** Deployment manifests shall pin service images, infrastructure versions, secrets references, network policies, and resource limits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCDEP-003 — Deployment Profiles and Topology

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/202_deployment_architecture.md`](../20-architecture/202_deployment_architecture.md)
- **Requirement:** Data residency policy shall be enforceable before asset upload or worker scheduling.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCDEP-004 — Deployment Profiles and Topology

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/202_deployment_architecture.md`](../20-architecture/202_deployment_architecture.md)
- **Requirement:** Local upgrades shall be reversible and preserve compatible export paths.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCDEP-005 — Deployment Profiles and Topology

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/202_deployment_architecture.md`](../20-architecture/202_deployment_architecture.md)
- **Requirement:** Cloud autoscaling shall enforce tenant quotas and global budget limits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCEVT-001 — Event-Driven Workflows and State Machines

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/205_event_driven_workflows.md`](../20-architecture/205_event_driven_workflows.md)
- **Requirement:** Every event shall include event ID, type, schema version, aggregate ID, tenant/project context, occurrence time, trace ID, producer, and payload hash.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCEVT-002 — Event-Driven Workflows and State Machines

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/205_event_driven_workflows.md`](../20-architecture/205_event_driven_workflows.md)
- **Requirement:** Outbox or equivalent atomic publication shall prevent database commit/event divergence.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCEVT-003 — Event-Driven Workflows and State Machines

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/205_event_driven_workflows.md`](../20-architecture/205_event_driven_workflows.md)
- **Requirement:** Retries shall distinguish transient, capacity, policy, invalid-input, and deterministic-algorithm failures.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCEVT-004 — Event-Driven Workflows and State Machines

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/205_event_driven_workflows.md`](../20-architecture/205_event_driven_workflows.md)
- **Requirement:** Workflow state shall survive process restart and orchestrator failover.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCEVT-005 — Event-Driven Workflows and State Machines

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/205_event_driven_workflows.md`](../20-architecture/205_event_driven_workflows.md)
- **Requirement:** Dead-letter items shall expose remediation and safe replay controls.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-001 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** SIP shall implement hybrid representation through isolated control, provider, quarantine, validation, publication, and runtime boundaries.
- **Minimum verification:** Architecture and deployment test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-002 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Only the representation publisher shall attach an accepted derivative to a scene commit, and publication shall be atomic.
- **Minimum verification:** Authorization and transaction test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-003 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Provider workers shall have no permission to modify source evidence, assertions, consent, authority labels, or accepted scene revisions.
- **Minimum verification:** Least-privilege test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-004 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Unknown, expired, or incompatible provider policy shall fail closed before source asset access.
- **Minimum verification:** Negative policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-005 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Generated outputs shall enter a quarantine store and shall not be served to customer runtimes before validation.
- **Minimum verification:** Security integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-006 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Sensitive construction and LiveForever data shall remain within an approved deployment and egress boundary.
- **Minimum verification:** Data-flow and egress test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-007 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** A provider or compiler failure shall not mutate canonical source assets or the last accepted representation.
- **Minimum verification:** Fault-injection and rollback test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-008 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** The runtime shall select assets by role, branch, audience, device capability, and intended use rather than file extension.
- **Minimum verification:** Runtime selection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-009 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Collision, navigation, occlusion, and display derivatives shall be independently replaceable and versioned.
- **Minimum verification:** Component replacement test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-010 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Provider adapters shall remain outside domain schemas and shall conform to a stable provider SDK.
- **Minimum verification:** Adapter conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-011 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Local-only, hybrid, managed-cloud, and manual-external modes shall share the same operation and provenance contracts.
- **Minimum verification:** Cross-profile contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-012 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** Hybrid-representation events shall avoid embedding unrestricted source geometry and shall use separately authorized asset references.
- **Minimum verification:** Event privacy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-013 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** The platform shall expose operational metrics for queueing, compute, validation, publication, cache behavior, and runtime performance without requiring raw-scene inspection.
- **Minimum verification:** Observability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCHHYB-014 — Hybrid Representation Services and Trust Boundaries

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/211_hybrid_representation_services.md`](../20-architecture/211_hybrid_representation_services.md)
- **Requirement:** A provider replacement or deprecation shall not require migration of semantic entities, evidence, consent, or stable public APIs.
- **Minimum verification:** Provider substitution test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCIAM-001 — Identity, Tenancy, Authorization, and Sharing

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/206_identity_tenancy_permissions.md`](../20-architecture/206_identity_tenancy_permissions.md)
- **Requirement:** Every request shall be authorized using authenticated principal, tenant, project, action, resource classification, purpose, and relevant consent.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCIAM-002 — Identity, Tenancy, Authorization, and Sharing

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/206_identity_tenancy_permissions.md`](../20-architecture/206_identity_tenancy_permissions.md)
- **Requirement:** Service identities shall use short-lived credentials and cannot impersonate users without explicit delegated context.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCIAM-003 — Identity, Tenancy, Authorization, and Sharing

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/206_identity_tenancy_permissions.md`](../20-architecture/206_identity_tenancy_permissions.md)
- **Requirement:** Tenant isolation tests shall cover database, object storage, queues, caches, search, logs, and GPU scratch.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCIAM-004 — Identity, Tenancy, Authorization, and Sharing

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/206_identity_tenancy_permissions.md`](../20-architecture/206_identity_tenancy_permissions.md)
- **Requirement:** Share links shall have scope, expiry, revocation, watermark policy, and access logs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCIAM-005 — Identity, Tenancy, Authorization, and Sharing

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/206_identity_tenancy_permissions.md`](../20-architecture/206_identity_tenancy_permissions.md)
- **Requirement:** Permission changes shall invalidate cached access decisions within a bounded interval.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCLOG-001 — Logical Architecture

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/201_logical_architecture.md`](../20-architecture/201_logical_architecture.md)
- **Requirement:** A compute worker shall not receive direct database-owner credentials.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCLOG-002 — Logical Architecture

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/201_logical_architecture.md`](../20-architecture/201_logical_architecture.md)
- **Requirement:** Publication of a scene revision shall be atomic with its manifest and audit event.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCLOG-003 — Logical Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/201_logical_architecture.md`](../20-architecture/201_logical_architecture.md)
- **Requirement:** Derived indexes shall be rebuildable from canonical transactional records and object assets.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCLOG-004 — Logical Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/201_logical_architecture.md`](../20-architecture/201_logical_architecture.md)
- **Requirement:** Services shall expose health, readiness, version, and dependency status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCLOG-005 — Logical Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/201_logical_architecture.md`](../20-architecture/201_logical_architecture.md)
- **Requirement:** The architecture shall support replacing a model or storage vendor without changing stable domain identifiers.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCOBS-001 — Observability, Quality Telemetry, and Audit Correlation

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/208_observability.md`](../20-architecture/208_observability.md)
- **Requirement:** Logs shall be structured and include release, service, tenant-safe context, trace, operation, outcome, and stable error code.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCOBS-002 — Observability, Quality Telemetry, and Audit Correlation

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/208_observability.md`](../20-architecture/208_observability.md)
- **Requirement:** Metrics shall identify model/checkpoint and capture profile without leaking personal or facility-identifying values.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCOBS-003 — Observability, Quality Telemetry, and Audit Correlation

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/208_observability.md`](../20-architecture/208_observability.md)
- **Requirement:** Distributed traces shall connect ingest, orchestration, worker, storage, validation, and publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCOBS-004 — Observability, Quality Telemetry, and Audit Correlation

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/208_observability.md`](../20-architecture/208_observability.md)
- **Requirement:** Quality dashboards shall show drift, coverage, residuals, confidence distribution, failed regions, and comparison to prior versions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCOBS-005 — Observability, Quality Telemetry, and Audit Correlation

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/208_observability.md`](../20-architecture/208_observability.md)
- **Requirement:** Audit events shall be append-only and protected from ordinary support modification.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCREPO-001 — Implementation Repository Architecture

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/203_repository_architecture.md`](../20-architecture/203_repository_architecture.md)
- **Requirement:** The repository shall separate apps, services, workers, packages, schemas, infrastructure, tests, fixtures, benchmarks, and third-party notices.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCREPO-002 — Implementation Repository Architecture

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/203_repository_architecture.md`](../20-architecture/203_repository_architecture.md)
- **Requirement:** Generated code shall be reproducible and CI shall reject uncommitted generated diffs.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCREPO-003 — Implementation Repository Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/203_repository_architecture.md`](../20-architecture/203_repository_architecture.md)
- **Requirement:** Third-party source and patches shall record exact upstream revision and license files.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCREPO-004 — Implementation Repository Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/203_repository_architecture.md`](../20-architecture/203_repository_architecture.md)
- **Requirement:** Every deployable component shall have an owner, threat surface, health contract, and release artifact.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCREPO-005 — Implementation Repository Architecture

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/203_repository_architecture.md`](../20-architecture/203_repository_architecture.md)
- **Requirement:** Sample data shall contain no real customer, family, biometric, or sensitive-building information.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCRES-001 — Failure Domains, Resilience, and Degraded Modes

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/209_failure_domains_and_resilience.md`](../20-architecture/209_failure_domains_and_resilience.md)
- **Requirement:** Each component shall declare blast radius, retry safety, recovery point, recovery time, and degraded behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCRES-002 — Failure Domains, Resilience, and Degraded Modes

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/209_failure_domains_and_resilience.md`](../20-architecture/209_failure_domains_and_resilience.md)
- **Requirement:** Worker resource exhaustion shall terminate the job without terminating shared control-plane services.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCRES-003 — Failure Domains, Resilience, and Degraded Modes

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/209_failure_domains_and_resilience.md`](../20-architecture/209_failure_domains_and_resilience.md)
- **Requirement:** Object-store write success shall be followed by hash verification before database publication.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCRES-004 — Failure Domains, Resilience, and Degraded Modes

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/209_failure_domains_and_resilience.md`](../20-architecture/209_failure_domains_and_resilience.md)
- **Requirement:** Index outage shall fall back to bounded metadata navigation rather than returning unauthorized or stale results.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCRES-005 — Failure Domains, Resilience, and Degraded Modes

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/209_failure_domains_and_resilience.md`](../20-architecture/209_failure_domains_and_resilience.md)
- **Requirement:** Provider-region failure shall not trigger unapproved cross-region data movement.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSVC-001 — Service Catalog and Ownership

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/204_service_catalog.md`](../20-architecture/204_service_catalog.md)
- **Requirement:** The catalog shall list service owner, repository path, data stores, inbound/outbound APIs, events, secrets, SLO, and recovery strategy.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSVC-002 — Service Catalog and Ownership

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/204_service_catalog.md`](../20-architecture/204_service_catalog.md)
- **Requirement:** A service shall not write tables owned by another service except through an approved shared-kernel exception.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSVC-003 — Service Catalog and Ownership

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/204_service_catalog.md`](../20-architecture/204_service_catalog.md)
- **Requirement:** Worker callbacks shall be idempotent and authenticated as workload identities.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSVC-004 — Service Catalog and Ownership

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/204_service_catalog.md`](../20-architecture/204_service_catalog.md)
- **Requirement:** Service shutdown shall drain or safely requeue in-flight work.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSVC-005 — Service Catalog and Ownership

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/204_service_catalog.md`](../20-architecture/204_service_catalog.md)
- **Requirement:** Critical service dependencies shall have explicit timeout, circuit-breaker, and degradation behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSYNC-001 — Offline-First Operation and Synchronization

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/207_offline_first_sync.md`](../20-architecture/207_offline_first_sync.md)
- **Requirement:** The mobile app shall survive termination after every finalized frame/segment boundary without losing accepted data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSYNC-002 — Offline-First Operation and Synchronization

- **Priority:** P0
- **Category:** architecture
- **Source:** [`20-architecture/207_offline_first_sync.md`](../20-architecture/207_offline_first_sync.md)
- **Requirement:** Upload shall resume without retransmitting verified chunks.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSYNC-003 — Offline-First Operation and Synchronization

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/207_offline_first_sync.md`](../20-architecture/207_offline_first_sync.md)
- **Requirement:** The server shall deduplicate identical assets without exposing cross-tenant existence information.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSYNC-004 — Offline-First Operation and Synchronization

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/207_offline_first_sync.md`](../20-architecture/207_offline_first_sync.md)
- **Requirement:** A device shall verify server receipt and root-manifest integrity before offering local purge.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### ARCSYNC-005 — Offline-First Operation and Synchronization

- **Priority:** P1
- **Category:** architecture
- **Source:** [`20-architecture/207_offline_first_sync.md`](../20-architecture/207_offline_first_sync.md)
- **Requirement:** Clock drift and time-zone ambiguity shall be recorded rather than silently normalized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-001 — Calibration and Known-Scale Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** A calibration record shall state method, equipment/target, environment, operator, date, software, residuals, units, and validity criteria.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-002 — Calibration and Known-Scale Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** The app shall reject or warn when a required calibration check fails.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-003 — Calibration and Known-Scale Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** Control points shall include coordinate frame, uncertainty, method, verifier, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-004 — Calibration and Known-Scale Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** Verified dimensions used as optimization constraints shall retain endpoints, measurement tool, uncertainty, and responsible person.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-005 — Calibration and Known-Scale Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** Calibration expiry or device/OS/camera changes shall trigger revalidation according to profile policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCAL-006 — Calibration and Known-Scale Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/305_calibration.md`](../30-capture/305_calibration.md)
- **Requirement:** The optimizer shall report how strongly control constraints changed the unconstrained solution.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-001 — Canonical Spatial Capture Package

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** The root manifest shall include schema version, session ID, tenant/project when known, source adapter, device, time range, coordinate frames, segments, asset index, root hash, and signature status.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-002 — Canonical Spatial Capture Package

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** Every asset entry shall include path/reference, media type, byte size, SHA-256, creation source, encryption status, and retention class.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-003 — Canonical Spatial Capture Package

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** Every frame shall reference an image and may reference depth, confidence, pose, intrinsics, mesh observations, audio time range, quality events, and privacy regions.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-004 — Canonical Spatial Capture Package

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** The validator shall detect missing assets, duplicate identifiers, hash mismatch, transform cycles, non-monotonic timestamps, impossible dimensions, and unsupported major versions.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-005 — Canonical Spatial Capture Package

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** Package normalization shall be deterministic so identical logical manifests produce identical canonical hashes.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPCSCP-006 — Canonical Spatial Capture Package

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/304_canonical_capture_package.md`](../30-capture/304_canonical_capture_package.md)
- **Requirement:** Unknown optional fields shall be retained when re-serializing a compatible package.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPFUT-001 — Future Sensor and Platform Extensions

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/310_multi_sensor_future.md`](../30-capture/310_multi_sensor_future.md)
- **Requirement:** A sensor adapter shall document units, axes, timestamp semantics, calibration, uncertainty, invalid values, and operating envelope.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPFUT-002 — Future Sensor and Platform Extensions

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/310_multi_sensor_future.md`](../30-capture/310_multi_sensor_future.md)
- **Requirement:** The fusion pipeline shall be able to exclude a source without rebuilding unrelated derivatives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPFUT-003 — Future Sensor and Platform Extensions

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/310_multi_sensor_future.md`](../30-capture/310_multi_sensor_future.md)
- **Requirement:** External survey imports shall preserve source coordinate reference systems and transformation evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPFUT-004 — Future Sensor and Platform Extensions

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/310_multi_sensor_future.md`](../30-capture/310_multi_sensor_future.md)
- **Requirement:** Thermal and other non-visible imagery shall be stored as registered observations, not painted into RGB truth by default.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPFUT-005 — Future Sensor and Platform Extensions

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/310_multi_sensor_future.md`](../30-capture/310_multi_sensor_future.md)
- **Requirement:** Drone and robotics integrations shall remain read-only with respect to actuation in the initial platform.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-001 — First-Party iOS Capture Application

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** The app shall implement states for setup, calibration check, ready, capturing, paused, tracking recovery, segment finalization, session finalization, upload, verified, and failed-recoverable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-002 — First-Party iOS Capture Application

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** The app shall capture RGB/depth/pose/intrinsics/IMU timestamps without blocking the AR session render loop.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-003 — First-Party iOS Capture Application

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** The app shall persist an append-only journal sufficient to recover after crash or device restart.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-004 — First-Party iOS Capture Application

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** Thermal, storage, battery, and memory pressure shall trigger controlled quality degradation or pause with user explanation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-005 — First-Party iOS Capture Application

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** The app shall support project policy bundles that disable audio, location, cloud transfer, or particular sensors.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPIOS-006 — First-Party iOS Capture Application

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/301_ios_app.md`](../30-capture/301_ios_app.md)
- **Requirement:** The app shall never delete local originals until package integrity and destination receipt are verified and the user or policy authorizes purge.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-001 — Polycam Raw Export Adapter

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** The adapter shall validate `raw.glb`, media, `mesh_info.json`, camera JSON, depth, confidence, and corrected variants independently.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-002 — Polycam Raw Export Adapter

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** Missing corrected poses shall not be synthesized or mislabeled as Polycam optimization output.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-003 — Polycam Raw Export Adapter

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** The adapter shall map Polycam's right-handed gravity-aligned coordinate convention into a named source frame before any SIP transform.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-004 — Polycam Raw Export Adapter

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** Depth resolution, units, invalid encoding, and confidence interpretation shall be recorded from the export metadata or marked unknown.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-005 — Polycam Raw Export Adapter

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** The adapter shall produce a conversion report listing accepted, skipped, malformed, and unmatched files.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPOLY-006 — Polycam Raw Export Adapter

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/303_polycam_adapter.md`](../30-capture/303_polycam_adapter.md)
- **Requirement:** Regression fixtures shall cover small optimized captures, large ARKit-only captures, missing depth, partial exports, and corrupted archives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-001 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** The app shall display capture/recording status and consent context appropriate to the project.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-002 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** Operators shall be able to mark faces, screens, documents, license plates, security equipment, rooms, or arbitrary regions as restricted.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-003 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** Automatic detectors shall create reviewable suggestions, not irreversible deletions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-004 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** Derived redacted media shall link to the source and exact redaction operations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-005 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** A public or broad-share export shall fail closed when required redactions are unresolved.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPPRIV-006 — Capture-Time Privacy and Sensitive-Region Controls

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/309_privacy_redaction_at_capture.md`](../30-capture/309_privacy_redaction_at_capture.md)
- **Requirement:** Private audio notes shall not be included in ordinary scene playback without explicit publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-001 — Live Capture Guidance and Coverage Quality

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** The app shall compute lightweight blur, exposure, motion, tracking, depth-coverage, and viewpoint-diversity signals during capture.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-002 — Live Capture Guidance and Coverage Quality

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** The app shall identify unvisited or weakly observed surfaces in the local map when feasible.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-003 — Live Capture Guidance and Coverage Quality

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** A quality warning shall state cause, consequence, and corrective action.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-004 — Live Capture Guidance and Coverage Quality

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** Operator overrides shall be recorded with reason and cannot relabel degraded data as passing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-005 — Live Capture Guidance and Coverage Quality

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** Finalization shall generate a room/segment quality summary and recommended recapture list.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPQUAL-006 — Live Capture Guidance and Coverage Quality

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/307_capture_guidance_quality.md`](../30-capture/307_capture_guidance_quality.md)
- **Requirement:** Quality thresholds shall be versioned by capture profile and device class.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPREC-001 — Capture Persistence, Resume, and Recovery

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/308_session_resume_recovery.md`](../30-capture/308_session_resume_recovery.md)
- **Requirement:** The app shall fsync or otherwise durably commit finalized asset and journal records at bounded intervals.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPREC-002 — Capture Persistence, Resume, and Recovery

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/308_session_resume_recovery.md`](../30-capture/308_session_resume_recovery.md)
- **Requirement:** On restart, the app shall verify recent hashes and offer resume, finalize-partial, export-for-repair, or discard with confirmation.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPREC-003 — Capture Persistence, Resume, and Recovery

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/308_session_resume_recovery.md`](../30-capture/308_session_resume_recovery.md)
- **Requirement:** Tracking loss shall not append poses as if they were valid world observations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPREC-004 — Capture Persistence, Resume, and Recovery

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/308_session_resume_recovery.md`](../30-capture/308_session_resume_recovery.md)
- **Requirement:** Low storage shall stop before filesystem exhaustion and preserve an exportable package.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPREC-005 — Capture Persistence, Resume, and Recovery

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/308_session_resume_recovery.md`](../30-capture/308_session_resume_recovery.md)
- **Requirement:** Repair tools shall create a new package revision with explicit lineage to the original.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-001 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** Each frame record shall include timestamps, image asset, depth asset when present, confidence asset, camera transform, intrinsics, image resolution, tracking state, exposure, and orientation metadata.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-002 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** The capture layer shall preserve invalid depth and confidence values without converting them into zero-distance surfaces.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-003 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** ARKit relocalization, world-origin changes, interruptions, and limited-tracking reasons shall create explicit events.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-004 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** Mesh-anchor add/update/remove operations shall be journaled with identifiers and transforms.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-005 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** Sensor sampling shall use bounded queues and record dropped frames with cause.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSENS-006 — ARKit, LiDAR, RGB, Mesh, and IMU Acquisition

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/302_arkit_lidar_rgb_imu.md`](../30-capture/302_arkit_lidar_rgb_imu.md)
- **Requirement:** Device model, OS, app build, sensor availability, and calibration-relevant camera identity shall be stored in the package manifest.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSOP-001 — Field Capture Standard Operating Procedures

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/311_field_capture_sops.md`](../30-capture/311_field_capture_sops.md)
- **Requirement:** The preflight shall verify device readiness, profile, project, permissions, storage, calibration requirement, safety, and consent.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSOP-002 — Field Capture Standard Operating Procedures

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/311_field_capture_sops.md`](../30-capture/311_field_capture_sops.md)
- **Requirement:** Every segment shall begin and end with adequate overlap or explicit control for later registration.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSOP-003 — Field Capture Standard Operating Procedures

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/311_field_capture_sops.md`](../30-capture/311_field_capture_sops.md)
- **Requirement:** Operators shall avoid unsafe walking, ladders, restricted zones, active work, and viewing the screen while moving through hazards.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSOP-004 — Field Capture Standard Operating Procedures

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/311_field_capture_sops.md`](../30-capture/311_field_capture_sops.md)
- **Requirement:** The closeout checklist shall review tracking events, coverage, details, privacy marks, notes, and package finalization.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSOP-005 — Field Capture Standard Operating Procedures

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/311_field_capture_sops.md`](../30-capture/311_field_capture_sops.md)
- **Requirement:** Training shall include failure examples such as mirrors, glass, featureless walls, repeated corridors, darkness, crowds, and moving machinery.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSTRAT-001 — Capture Strategy and Source Abstraction

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/300_capture_strategy.md`](../30-capture/300_capture_strategy.md)
- **Requirement:** Every adapter shall output the same minimum manifest or declare unsupported fields explicitly.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSTRAT-002 — Capture Strategy and Source Abstraction

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/300_capture_strategy.md`](../30-capture/300_capture_strategy.md)
- **Requirement:** The ingest service shall retain the source-native package alongside normalized data when policy permits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSTRAT-003 — Capture Strategy and Source Abstraction

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/300_capture_strategy.md`](../30-capture/300_capture_strategy.md)
- **Requirement:** Capture profiles shall specify required sensors, resolution, frame rate, operator pattern, expected range, quality thresholds, and storage budget.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSTRAT-004 — Capture Strategy and Source Abstraction

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/300_capture_strategy.md`](../30-capture/300_capture_strategy.md)
- **Requirement:** The app shall not claim a profile's target accuracy until calibration and field validation demonstrate it.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPSTRAT-005 — Capture Strategy and Source Abstraction

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/300_capture_strategy.md`](../30-capture/300_capture_strategy.md)
- **Requirement:** A source adapter shall be testable against fixed fixtures without access to the original application.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPTIME-001 — Timestamping and Sensor Synchronization

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/306_time_sync.md`](../30-capture/306_time_sync.md)
- **Requirement:** Every timestamped stream shall declare clock identifier, units, epoch/zero, monotonicity, and conversion to session time.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPTIME-002 — Timestamping and Sensor Synchronization

- **Priority:** P0
- **Category:** capture
- **Source:** [`30-capture/306_time_sync.md`](../30-capture/306_time_sync.md)
- **Requirement:** Interpolated poses or IMU values shall be labeled and include maximum temporal gap.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPTIME-003 — Timestamping and Sensor Synchronization

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/306_time_sync.md`](../30-capture/306_time_sync.md)
- **Requirement:** The pipeline shall reject synchronization gaps beyond profile limits for tightly coupled fusion.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPTIME-004 — Timestamping and Sensor Synchronization

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/306_time_sync.md`](../30-capture/306_time_sync.md)
- **Requirement:** Audio and transcript anchors shall preserve sample-accurate or bounded time mapping to source media.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CAPTIME-005 — Timestamping and Sensor Synchronization

- **Priority:** P1
- **Category:** capture
- **Source:** [`30-capture/306_time_sync.md`](../30-capture/306_time_sync.md)
- **Requirement:** Cross-device offset and drift estimates shall include residual and confidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-001 — Access Control and Door Intelligence

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** A door survey shall capture opening ID, side/handing, frame/door condition, hardware, power transfer, lock, reader, contact, REX, egress hardware, controller association, pathway, dimensions with source, and photographs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-002 — Access Control and Door Intelligence

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** Sequence-of-operation records shall be versioned documents/assertions with author and approval.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-003 — Access Control and Door Intelligence

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** Controller panels, network paths, addresses, and security zones shall require elevated access.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-004 — Access Control and Door Intelligence

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** The platform shall flag inconsistent or incomplete associations for review without automatically changing access policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-005 — Access Control and Door Intelligence

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** Commissioning tests shall record state transitions, expected/actual result, actor, time, and evidence without retaining unnecessary credential identifiers.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONAC-006 — Access Control and Door Intelligence

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/704_access_control.md`](../70-construction/704_access_control.md)
- **Requirement:** Exports for installers shall omit restricted owner security data unless expressly authorized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-001 — Construction Demonstration Scenario

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** The operator shall create a project, import a plan/drawing, capture the room, recover from a pause, and finalize locally.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-002 — Construction Demonstration Scenario

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** The platform shall ingest, process preview/final, align LingBot and metric lanes, publish a reviewed scene, and show quality.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-003 — Construction Demonstration Scenario

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** The reviewer shall anchor a panel, devices, door hardware, equipment, label photos, drawing regions, and one RFI.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-004 — Construction Demonstration Scenario

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** A measurement shall be shown first as scan estimate and later as field verified with history.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-005 — Construction Demonstration Scenario

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** A second capture shall identify a changed object and produce a reviewable semantic diff.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDEMO-006 — Construction Demonstration Scenario

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/713_construction_demo_scenario.md`](../70-construction/713_construction_demo_scenario.md)
- **Requirement:** The demo shall export a report and open-format project bundle while hiding restricted details from a broad-share viewer.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-001 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** Documents shall retain source file hash, title, type, revision, issue date, issuer, status, pages, permissions, and supersession links.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-002 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** Sheet anchors shall store page coordinate system, polygon/region, label, entity/space links, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-003 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** RFI records shall support question, context, responsible parties, due dates, responses, attachments, status, and affected scene/entities.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-004 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** Submittal records shall support specification section, product/equipment mappings, review status, exceptions, and approved documents.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-005 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** The viewer shall open the exact referenced document revision and region from a spatial entity.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONDOC-006 — Drawings, Specifications, RFIs, Submittals, and Spatial Linking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/706_drawings_specs_rfis_submittals.md`](../70-construction/706_drawings_specs_rfis_submittals.md)
- **Requirement:** AI extraction shall cite page/region and confidence and require review before authoritative mappings.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-001 — Fire Alarm Spatial Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** Fire-alarm entities shall support control units, power supplies, annunciators, amplifiers, network interfaces, initiating devices, notification appliances, modules, circuits/loops, interfaces, zones, and related equipment.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-002 — Fire Alarm Spatial Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** A device record shall support manufacturer/model, address/label, panel/loop/circuit, location, mount/condition, drawing reference, photograph, source class, and verification/test status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-003 — Fire Alarm Spatial Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** The system shall allow spatial comparison of observed devices against design drawings without automatically declaring code deficiency.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-004 — Fire Alarm Spatial Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** Test records shall include procedure, result, witnesses, instrument where relevant, time, device association, and supporting media/document.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-005 — Fire Alarm Spatial Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** Programming files and credentials shall be stored through restricted asset policies and never rendered in ordinary reports.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONFA-006 — Fire Alarm Spatial Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/703_fire_alarm.md`](../70-construction/703_fire_alarm.md)
- **Requirement:** Migration planning shall preserve existing-system evidence, interfaces, affected areas, temporary protection notes, and phased changes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-001 — BIM Handoff and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** A handoff package shall include scope, accepted scene commit, asset inventory, verified attributes, documents, tests, warranties, training, open issues, exclusions, exports, and checksums.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-002 — BIM Handoff and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** The system shall validate required owner fields and documents by equipment/system type.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-003 — BIM Handoff and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** IFC/CSV/API exports shall state which values are verified, design-derived, observed, or inferred.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-004 — BIM Handoff and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** Facility users shall search by location, tag, manufacturer/model, system, document, and issue history.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-005 — BIM Handoff and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** Operations changes shall retain continuity to construction entities and IDs where possible.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHAND-006 — BIM Handoff and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/710_bim_handoff_facility_operations.md`](../70-construction/710_bim_handoff_facility_operations.md)
- **Requirement:** A portability test shall confirm the owner can access core records without the production SIP service.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-001 — Construction Project and Spatial Hierarchy

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** Every place shall have stable ID, type, names/aliases, parent, validity, source, geometry/volume when known, access classification, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-002 — Construction Project and Spatial Hierarchy

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** The system shall support multiple building coordinate frames and a site/global frame with explicit transforms.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-003 — Construction Project and Spatial Hierarchy

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** Room number conflicts across drawings, signage, and owner systems shall be reviewable mappings.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-004 — Construction Project and Spatial Hierarchy

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** System zones such as fire-alarm notification, access-control areas, HVAC zones, and security partitions shall not be forced into geometric containment.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-005 — Construction Project and Spatial Hierarchy

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** Bulk import from IFC, room schedules, CSV, and owner systems shall produce mapping/conflict reports.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHIER-006 — Construction Project and Spatial Hierarchy

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/701_project_building_floor_room.md`](../70-construction/701_project_building_floor_room.md)
- **Requirement:** Reports shall use the project naming view selected for the audience while retaining stable IDs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-001 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Construction scenes shall maintain observed, inferred, verified, design/proposed, and generated states independently at entity and assertion level.
- **Minimum verification:** Domain schema test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-002 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** An interaction proxy or visual splat shall not independently establish field dimensions, code compliance, as-built status, payment progress, issue closure, or commissioning acceptance.
- **Minimum verification:** Policy and workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-003 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** A measurement begun on a proxy shall record the display hit and shall resolve to eligible metric evidence or remain approximate and unverified.
- **Minimum verification:** Measurement acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-004 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Proposed or design geometry shall retain a visible and machine-readable design label even when photorealistically blended with observed context.
- **Minimum verification:** Viewer/export test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-005 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Construction entities, tests, issues, and documents shall use stable IDs and source evidence rather than depending on a proxy triangle or visual Gaussian identity.
- **Minimum verification:** Remeshing regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-006 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Sensitive building, life-safety, and security representations shall be denied to unapproved external providers before data export or source access.
- **Minimum verification:** Security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-007 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Issue closure and commissioning acceptance shall require the configured evidence, test, retest, and accountable reviewer rather than visual disappearance alone.
- **Minimum verification:** Workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-008 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Handoff exports shall declare every representation role, authority ceiling, accuracy/validation report, coordinate frame, and limitation.
- **Minimum verification:** Handoff round-trip test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-009 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Progress comparison shall report capture gaps and review candidate geometric/visual changes before changing semantic state.
- **Minimum verification:** Change-detection scenario
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-010 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Fire-alarm, access-control, BAS, mechanical, and electrical verticals shall declare which attributes require documents, calculations, tests, or field verification beyond spatial appearance.
- **Minimum verification:** Vertical review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-011 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Field clients shall expose metric snap source, residual, uncertainty, truth state, and recapture/verification options at the point of work.
- **Minimum verification:** Field UX test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-012 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** BIM/IFC identity and properties shall remain linked to any visual-splat or proxy derivative without making the derivative the authoritative BIM deliverable.
- **Minimum verification:** IFC interoperability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-013 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Offline construction packages shall apply the same spatial permissions, truth rules, expiry, audit, and measurement constraints as hosted use.
- **Minimum verification:** Offline field test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-014 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Reports and screenshots shall identify source scene revision, design revision, representations used, excluded areas, and measurement authority.
- **Minimum verification:** Reporting acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-015 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** A proxy alignment failure beyond the purpose threshold shall disable affected selection, collision, navigation, or metric snapping and create a review task.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONHYB-016 — Hybrid Representation for Construction and Facility Operations

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/714_hybrid_representation_construction.md`](../70-construction/714_hybrid_representation_construction.md)
- **Requirement:** Owner handoff shall include an open path to inspect or reconstruct semantic/provenance data without dependence on a single proprietary viewer.
- **Minimum verification:** Portability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-001 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Every measurement shall store value, units, geometry/endpoints, class, uncertainty/tolerance, method/tool, calibration/control, author, verifier, time, source commit, and permitted use.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-002 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Scan estimates shall display a visible unverified label and configurable warning in exports.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-003 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** A verified measurement shall retain the original estimate for comparison and audit.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-004 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** The system shall prevent an agent or report template from dropping measurement class or uncertainty.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-005 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Field verification workflows shall support replacement, confirmation, or rejection with evidence.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-006 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Precision formatting shall be derived from source uncertainty and project standards.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-007 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** An interaction proxy shall never satisfy the source requirement for a verified construction measurement.
- **Minimum verification:** Policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-008 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Proxy-assisted measurements shall record interaction source, resolved metric/field source, snap distance, uncertainty, and resolution result.
- **Minimum verification:** Measurement test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-009 — Measurement Authority and Field Verification

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Proxy-only quantities, routes, clearances, and dimensions shall carry estimate language and required verification.
- **Minimum verification:** Report/export test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-010 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** The UI shall visually distinguish proxy hit, metric snap, design geometry, and field-verified point.
- **Minimum verification:** UI acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-011 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Proxy replacement shall not silently change saved measurement values or verification status.
- **Minimum verification:** Revision regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEAS-012 — Measurement Authority and Field Verification

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/708_measurements_truth_hierarchy.md`](../70-construction/708_measurements_truth_hierarchy.md)
- **Requirement:** Code, fabrication, and life-safety decisions shall require their independent evidence and qualified review regardless of proxy quality.
- **Minimum verification:** Workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-001 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** Equipment records shall support tag/aliases, type, manufacturer/model/serial, capacities, serving/served relationships, power/control connections, clearances, nameplate media, documents, and status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-002 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** BAS points shall link to equipment and sensor/actuator entities with source and verification.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-003 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** The platform shall represent fire-alarm shutdown/monitoring, access-control interfaces, elevator interfaces, and other cross-system dependencies.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-004 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** Spatial pathway or clearance measurements shall show scan/verified/design origin.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-005 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** Trend or operational data imports shall retain source system, units, timestamps, quality flags, and retention separate from static scene commits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONMEP-006 — BAS, Mechanical, Electrical, and Equipment Documentation

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/705_bas_mechanical_electrical.md`](../70-construction/705_bas_mechanical_electrical.md)
- **Requirement:** Sensitive network and controller configuration shall use restricted access and redacted exports.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-001 — Construction Spatial Reference Overview

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** A project shall organize site, building, level, zone, room, system, entity, document, visit, capture, task, and scene history.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-002 — Construction Spatial Reference Overview

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** Users shall be able to navigate from a spatial object to photographs, nameplates, drawings, specifications, RFIs, submittals, tests, deficiencies, and prior versions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-003 — Construction Spatial Reference Overview

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** The platform shall display measurement origin and verification state everywhere a quantity can affect estimating or installation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-004 — Construction Spatial Reference Overview

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** A field visit shall produce a completeness and unresolved-question report.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-005 — Construction Spatial Reference Overview

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** Owner handoff shall export open data and a read-only experience independent of a proprietary subscription where contractually required.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONOVR-006 — Construction Spatial Reference Overview

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/700_vertical_overview.md`](../70-construction/700_vertical_overview.md)
- **Requirement:** Construction reports shall identify scene commit, capture date, author, limitations, and evidence links.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-001 — Construction Progress and Change Tracking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** A progress visit shall reference baseline commit, scope, planned areas, comparable coverage, and capture quality.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-002 — Construction Progress and Change Tracking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** Change detection shall classify installed, removed, moved, modified, occluded, unobserved, and uncertain.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-003 — Construction Progress and Change Tracking

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** Progress states shall be defined per work item/system and linked to evidence and responsible reviewer.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-004 — Construction Progress and Change Tracking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** The system shall not infer payment entitlement from visual progress.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-005 — Construction Progress and Change Tracking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** Reports shall include comparable-region coverage and limitations to prevent false completeness.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONPROG-006 — Construction Progress and Change Tracking

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/709_progress_change_tracking.md`](../70-construction/709_progress_change_tracking.md)
- **Requirement:** Time-lapse views shall preserve restricted-area and worker-privacy policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-001 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** An issue shall include type, description, location/entity, observed commit/time, evidence, reporter, severity, responsible party, due date, status, and permissions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-002 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** Corrective action shall link new evidence and changed scene/entity revision.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-003 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** Closure shall require configured verification, verifier, date, result, and residual limitations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-004 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** Commissioning tests shall support procedures, prerequisites, steps, expected/actual results, participants, instruments, attachments, and retest history.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-005 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** Reports shall show open, overdue, disputed, corrected-awaiting-test, and closed issues with spatial summaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONQC-006 — Deficiencies, Punch, Testing, and Commissioning

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/707_punch_deficiency_commissioning.md`](../70-construction/707_punch_deficiency_commissioning.md)
- **Requirement:** Restricted system details shall remain protected in notifications and broad reports.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-001 — Construction Reports, Views, and Deliverables

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** A report shall identify project, scope, visit/commit, author, generation time, template version, query/filters, data cutoff, limitations, and integrity hash.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-002 — Construction Reports, Views, and Deliverables

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** Reports shall distinguish observed, verified, design, inferred, proposed, disputed, and unresolved items.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-003 — Construction Reports, Views, and Deliverables

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** Images and views shall retain source scene/view identifiers and redaction state.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-004 — Construction Reports, Views, and Deliverables

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** Audience profiles shall control inclusion of security topology, credentials context, personal information, and restricted rooms.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-005 — Construction Reports, Views, and Deliverables

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** Re-running the same report against the same inputs and version shall produce equivalent content within documented rendering variance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONREP-006 — Construction Reports, Views, and Deliverables

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/711_construction_reporting.md`](../70-construction/711_construction_reporting.md)
- **Requirement:** A report correction shall create a new revision and link the superseded version.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-001 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** The survey plan shall identify objectives, required rooms/systems, sensitive areas, control/measurement requirements, safety, permissions, and deliverables.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-002 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** The app shall support room/area checklists and detail evidence for labels, panel interiors, ceiling conditions, pathways, and interfaces.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-003 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** A survey review shall inspect coverage, tracking, registration, controls, object inventory, unanswered questions, and privacy restrictions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-004 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** Publishing as `verified_as_built` shall require named verifier, scope, date, method, exclusions, and signature/approval evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-005 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** The viewer shall visually distinguish inaccessible, unobserved, inferred, and verified regions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONSURV-006 — Existing-Condition Survey and As-Built Workflow

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/702_field_survey_as_built.md`](../70-construction/702_field_survey_as_built.md)
- **Requirement:** A return visit shall compare against the exact prior accepted commit and preserve both visits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-001 — Construction Vertical Acceptance Tests

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** The pilot shall capture at least one mechanical/electrical room, corridor, controlled door, and fire-alarm device set using the same platform.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-002 — Construction Vertical Acceptance Tests

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** Independent ground truth shall measure selected dimensions, device locations, and inventory.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-003 — Construction Vertical Acceptance Tests

- **Priority:** P0
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** The pilot shall demonstrate an RFI/document link, issue lifecycle, return-visit change, and commissioning/test evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-004 — Construction Vertical Acceptance Tests

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** Unauthorized roles shall be unable to discover restricted security-system entities through search, viewer, exports, counts, or URLs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-005 — Construction Vertical Acceptance Tests

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** A full project export shall open in the reference offline viewer and validated third-party format consumers.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### CONTEST-006 — Construction Vertical Acceptance Tests

- **Priority:** P1
- **Category:** construction
- **Source:** [`70-construction/712_construction_acceptance_tests.md`](../70-construction/712_construction_acceptance_tests.md)
- **Requirement:** Operators shall complete capture recovery after an intentional app interruption without source loss.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-001 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** A measurement shall include type, endpoints/geometry, value, units, source method, uncertainty, calibration/control, creator, time, evidence, and verification status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-002 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** The system shall distinguish a user click on a visual mesh from a snap to accepted metric geometry.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-003 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Anchor remapping shall report residual/error and require review beyond threshold.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-004 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** A task annotation shall include assignee, status, due date, related entity/assertion/evidence, and scene revision.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-005 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Spatial-volume annotations shall support privacy, issue, safety, and processing-exclusion policies.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-006 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Exports shall retain measurement provenance even when target formats only support text labels.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-007 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Proxy-local primitive identifiers shall not be the sole persistent anchor identity.
- **Minimum verification:** Remesh test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-008 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Measurement save shall record both the initial interaction hit and the eligible metric/field evidence used for the value.
- **Minimum verification:** End-to-end test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-009 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** A proxy-only result shall remain unverified and shall not be exported as a verified dimension.
- **Minimum verification:** Policy/export test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-010 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Support maps shall report reprojection residual, uncertainty, failed anchors, and review state.
- **Minimum verification:** Contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-011 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Ambiguous overlapping semantic candidates shall be preserved and presented for resolution rather than silently selecting one.
- **Minimum verification:** UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATANCH-012 — Annotations, Spatial Anchors, and Measurements

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/505_annotations_anchors_measurements.md`](../50-data/505_annotations_anchors_measurements.md)
- **Requirement:** Anchors shall survive representation LOD and partition changes within the accepted support tolerance.
- **Minimum verification:** Streaming regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-001 — Immutable Asset Storage and Content Addressing

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** Assets shall be hashed before or during upload and verified after durable storage.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-002 — Immutable Asset Storage and Content Addressing

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** Multipart uploads shall record chunk hashes and be safely resumable.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-003 — Immutable Asset Storage and Content Addressing

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** An asset shall not be published until size and hash match the manifest.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-004 — Immutable Asset Storage and Content Addressing

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** Storage-class transitions shall preserve integrity and retrieval guarantees required by retention policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-005 — Immutable Asset Storage and Content Addressing

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** Corruption detection shall trigger quarantine, replica comparison, restore, and incident/audit records.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATASSET-006 — Immutable Asset Storage and Content Addressing

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/508_asset_storage_content_addressing.md`](../50-data/508_asset_storage_content_addressing.md)
- **Requirement:** Garbage collection shall produce a dry-run report and auditable deletion result.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-001 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** IFC imports shall retain source file hash, schema/version, units, CRS, owner history, GlobalIds, classifications, properties, relationships, and geometry conversion report.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-002 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** Alignment between BIM and field scene shall be an explicit transform solution with residuals and controls.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-003 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** Field objects shall link to design objects through proposed/accepted mappings rather than ID replacement.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-004 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** BCF import/export shall preserve issue ID, status, author, comments, snapshots, viewpoints, selected components, and coordinate semantics.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-005 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** Unsupported IFC constructs shall be listed rather than silently flattened.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATBIM-006 — BIM, IFC 4.3, BCF, and Design/As-Built Mapping

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/511_bim_ifc_bcf.md`](../50-data/511_bim_ifc_bcf.md)
- **Requirement:** As-built export shall identify which properties are verified, observed, inferred, or carried from design.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-001 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Primary tables shall use tenant-aware keys, immutable creation fields, revision/version columns, and audited state transitions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-002 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Spatial indexes shall use declared SRID/frame semantics and shall not mix local frames as if they shared one CRS.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-003 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Object references shall include hash, size, media type, encryption/key scope, storage class, retention, and verification time.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-004 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Database migrations shall be forward-tested, rollback/recovery-tested, and rehearsed against production-sized copies.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-005 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Derived indexes shall include source sequence/checkpoint so freshness can be measured.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATDB-006 — Transactional, Spatial, Search, and Graph Storage

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/507_storage_database_schema.md`](../50-data/507_storage_database_schema.md)
- **Requirement:** Deletion and legal-hold logic shall traverse assets, derivatives, indexes, exports, and backups according to policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-001 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** Every assertion shall include subject, predicate, value/object, time/validity, source class, author/producer, and status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-002 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** Every evidence record shall identify immutable source asset or record, relevant region/time range, contributor, consent/access, and integrity hash.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-003 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** A derivation event shall identify activity, agent, inputs, outputs, software/model, parameters, time, and validation.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-004 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** The UI shall allow users to inspect evidence behind a displayed assertion when authorized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-005 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** Disputed assertions shall remain retrievable and cannot be silently replaced by a favored narrative.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATEVID-006 — Evidence, Assertions, Provenance, and Chain of Derivation

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/503_evidence_provenance.md`](../50-data/503_evidence_provenance.md)
- **Requirement:** A provenance gap shall prevent verified or corroborated status.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-001 — Open Interchange and Export Format Profiles

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** Each export profile shall state units, axes, CRS/frame, supported semantics, loss behavior, texture/media handling, and validation tools.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-002 — Open Interchange and Export Format Profiles

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** The platform shall support at minimum GLB, PLY, OBJ, and a documented point-cloud exchange in the MVP; later profiles include E57, LAS/LAZ, USD/USDZ, 3D Tiles, IFC, and BCF.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-003 — Open Interchange and Export Format Profiles

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** Exports shall never silently drop restricted content or truth labels; they shall fail, redact, or create a limitation report.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-004 — Open Interchange and Export Format Profiles

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** Round-trip tests shall verify coordinates, scale, stable IDs where possible, and critical metadata.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-005 — Open Interchange and Export Format Profiles

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** Export manifests shall record source commit, filters, redactions, transforms, exporter version, output hashes, and authorization.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFMT-006 — Open Interchange and Export Format Profiles

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/510_interchange_formats.md`](../50-data/510_interchange_formats.md)
- **Requirement:** Long-term archival profiles shall avoid undocumented proprietary-only encoding.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-001 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** A coordinate frame shall declare ID, semantic type, handedness, axis directions, units, origin, parent when applicable, and CRS/vertical datum when applicable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-002 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** A transform shall declare source, target, matrix layout, multiplication convention, direction, timestamp/validity, solver/source, and uncertainty.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-003 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** Adapters shall include conformance tests using known basis vectors, camera rays, and round trips.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-004 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** Unit conversion shall occur at explicit boundaries and retain source units.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-005 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** Viewer coordinate conversions shall not modify stored authoritative geometry.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATFRAME-006 — Coordinate Frames, Units, and Transform Semantics

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/500_coordinate_frames_units.md`](../50-data/500_coordinate_frames_units.md)
- **Requirement:** Geospatial transforms shall record the exact CRS pipeline and grid resources used.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-001 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Every geometry asset shall declare format/profile, coordinate frame, units, bounds, element counts, compression, hash, source run, quality, and access classification.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-002 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Every visual asset shall declare whether pixels are captured, corrected, reconstructed, inpainted, relit, generated, or mixed.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-003 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Asset manifests shall include compatible viewers/exporters and validation status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-004 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** The system shall support deprecating an asset without deleting its historical references.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-005 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Entity anchors shall reference stable local primitives or barycentric/surface coordinates where possible, with fallback behavior after remeshing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-006 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** A corrupt or missing derivative shall be rebuildable or clearly reported without hiding the original scene commit.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-007 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Geometry asset bytes shall be separate from scene bindings that assign role, authority, intended use, and publication state.
- **Minimum verification:** Schema/migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-008 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** File extension, provider, renderer, or appearance shall not determine authority or intended use.
- **Minimum verification:** Policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-009 — Geometry and Visual Asset Model

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Derived geometry shall inherit applicable classification, consent, retention, legal-hold, export, and deletion dependencies.
- **Minimum verification:** Policy graph test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-010 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Geometry families shall support independent display, collision, navigation, occlusion, and preservation assets.
- **Minimum verification:** Contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-011 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Every irreversible conversion loss shall be captured in a machine-readable loss declaration.
- **Minimum verification:** Round-trip test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGEOM-012 — Geometry and Visual Asset Model

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/502_geometry_asset_model.md`](../50-data/502_geometry_asset_model.md)
- **Requirement:** Unknown roles shall default to non-privileged use until a registered policy adapter approves them.
- **Minimum verification:** Forward-compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-001 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** A scene commit shall include ID, parents, author, time, message, branch, root manifest hash, policy checks, signatures, and review status.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-002 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Diff shall classify additions, removals, modifications, moves, reclassification, authority changes, consent changes, and uncertain geometry changes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-003 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Automatic merge shall be prohibited for conflicting verified measurements, consent revocation, identity, deletion, or authoritative system associations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-004 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Tags shall identify releases, field visits, milestones, accepted as-builts, and memory editions without mutating commits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-005 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Rollback shall create a new commit referencing prior state rather than deleting intervening history.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-006 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Exported history bundles shall verify parent links and asset hashes offline.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-007 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Representation publication/replacement shall create a scene commit and shall not mutate an existing commit.
- **Minimum verification:** Revision test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-008 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Diffs shall separately report role, authority, provider, intended-use, quality, support-map, policy, and limitation changes.
- **Minimum verification:** Diff test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-009 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** A proxy replacement shall preserve the prior asset and record anchor reprojection and unresolved impacts.
- **Minimum verification:** Remesh history test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-010 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Merge rules shall block conflicting authority promotions or provider-policy changes from automatic merge.
- **Minimum verification:** Merge-policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-011 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Rollback shall restore the prior binding set while preserving later conversion and review history.
- **Minimum verification:** Rollback test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATGIT-012 — Spatial Git: Commits, Branches, Diffs, and Merges

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/504_temporal_spatial_git.md`](../50-data/504_temporal_spatial_git.md)
- **Requirement:** Offline history export shall verify all representation and support-map hashes.
- **Minimum verification:** Portability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-001 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** SIP shall model immutable representation assets separately from scene bindings that assign role, purpose, authority, and publication state.
- **Minimum verification:** Schema and migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-002 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** File extension, renderer support, visual similarity, or provider name shall never determine an asset's role or authority.
- **Minimum verification:** Policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-003 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Every binding shall declare coordinate frame, transform, role, authority class, authority ceiling, intended uses, review decision, and audience policy.
- **Minimum verification:** Contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-004 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** An interaction, collision, navigation, occlusion, or audio derivative shall default to `derived_non_authoritative` and `disposable=true`.
- **Minimum verification:** Defaulting and rejection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-005 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Intended-use approval shall be granular and shall prevent proxy assets from satisfying metric or verified-measurement policy by role alone.
- **Minimum verification:** Authorization test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-006 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Semantic identity shall use stable entity and world-frame references with reprojectable support; provider-local primitive IDs shall be cache-only.
- **Minimum verification:** Remeshing regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-007 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Every derivative shall inherit applicable classification, consent, retention, legal-hold, export, and deletion dependencies from all source assets.
- **Minimum verification:** Policy graph test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-008 — Hybrid Representation Asset Contract

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Collision and navigation assets shall declare an actor/profile and shall not be reused for unapproved safety or accessibility purposes.
- **Minimum verification:** Profile-enforcement test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-009 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Representation families shall support tiled and LOD assets with stable frames, seam validation, fallback assets, and runtime selection metadata.
- **Minimum verification:** Large-scene schema test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-010 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** A support-map remap shall report residual, confidence, failed anchors, and review thresholds while retaining historical supports.
- **Minimum verification:** Remap test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-011 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** A visual or interaction derivative shall include machine-readable limitations and irreversible-loss declarations.
- **Minimum verification:** Export and UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-012 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** The dependency graph shall support selective invalidation and regeneration after privacy, cleanup, transform, provider, or source changes.
- **Minimum verification:** Invalidation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-013 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Unknown representation roles or profiles shall be denied privileged uses until a registered policy adapter handles them.
- **Minimum verification:** Forward-compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-014 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Hybrid scene views shall reference approved bindings rather than raw storage objects.
- **Minimum verification:** API security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-015 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Database and export contracts shall preserve source hashes, coordinate transforms, authority ceilings, intended-use decisions, and policy dependencies.
- **Minimum verification:** Round-trip test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATHYB-016 — Hybrid Representation Asset Contract

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/514_hybrid_representation_asset_contract.md`](../50-data/514_hybrid_representation_asset_contract.md)
- **Requirement:** Asset deprecation shall not erase historical scene commits or prevent independent reproduction when retention policy permits.
- **Minimum verification:** Spatial Git test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-001 — Ontology, Taxonomy, and Extensibility

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** Every type shall define required properties, allowed relationships, authority rules, sensitivity defaults, and export mappings.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-002 — Ontology, Taxonomy, and Extensibility

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** Vocabulary changes shall provide migration for stored type identifiers and search indexes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-003 — Ontology, Taxonomy, and Extensibility

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** Aliases and multilingual labels shall not change stable type IDs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-004 — Ontology, Taxonomy, and Extensibility

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** The system shall support an unknown/unclassified state rather than forcing low-confidence classification.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-005 — Ontology, Taxonomy, and Extensibility

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** Object detection labels shall map through a versioned model-label-to-ontology table and retain original labels.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATONTO-006 — Ontology, Taxonomy, and Extensibility

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/506_ontology_taxonomy.md`](../50-data/506_ontology_taxonomy.md)
- **Requirement:** Ontology constraints shall be validated at commit time with reviewable warnings or errors.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-001 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** Every stored asset and record shall have retention class, policy source, hold status, and deletion eligibility.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-002 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** A deletion request shall produce impact analysis, authorization, execution plan, completion evidence, and unresolved exceptions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-003 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** Consent revocation shall stop future processing immediately and trigger policy-defined handling of prior derivatives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-004 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** Backups shall expire deleted data within a documented bounded period while preventing ordinary restoration from resurrecting access.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-005 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** Tenant offboarding shall provide a verified export and deletion/retention report.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATRET-006 — Retention, Legal Hold, Deletion, and Portability

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/513_data_retention_deletion.md`](../50-data/513_data_retention_deletion.md)
- **Requirement:** Deletion shall propagate to derived search/vector indexes and cached viewer assets.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-001 — Persistent Semantic Scene Graph

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** Every entity shall have a stable UUID, tenant/project scope, type, lifecycle status, and creation provenance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-002 — Persistent Semantic Scene Graph

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** An entity revision shall identify the scene commit or temporal validity, labels, properties, geometry references, anchors, permissions, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-003 — Persistent Semantic Scene Graph

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** Relationships shall include type, endpoints, validity, confidence/source class, and provenance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-004 — Persistent Semantic Scene Graph

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** Entity identity merges and splits shall be reversible and audited.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-005 — Persistent Semantic Scene Graph

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** Unknown or user-defined types shall use namespaced extensions without losing base behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSCENE-006 — Persistent Semantic Scene Graph

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/501_scene_graph.md`](../50-data/501_scene_graph.md)
- **Requirement:** Graph queries shall apply authorization before returning neighboring nodes or counts.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-001 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** Queries shall support tenant/project, entity type, spatial region, floor/room, time interval, source class, authority, confidence, tags, workflow status, and full text.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-002 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** Semantic search shall retain embedding model manifest and source text/media region.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-003 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** Authorization shall be enforced before returning result content, snippets, counts, or embeddings.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-004 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** A stale index shall expose freshness and fall back to canonical lookup for critical workflows.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-005 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** Search evaluation shall include relevance, permission leakage, multilingual names, OCR/transcript errors, and ambiguous room labels.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATSEARC-006 — Spatial, Temporal, Text, Vector, and Graph Search

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/509_search_indexing.md`](../50-data/509_search_indexing.md)
- **Requirement:** Users shall be able to navigate from a result to its scene view and underlying evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-001 — Digital Twin Timeline and State Projection

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** The platform shall query scene/entity state as of a commit, valid date, or field visit.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-002 — Digital Twin Timeline and State Projection

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** Changes shall reference causing evidence or workflow event when known.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-003 — Digital Twin Timeline and State Projection

- **Priority:** P0
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** Late-arriving historical evidence shall be added without rewriting when it was received.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-004 — Digital Twin Timeline and State Projection

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** A timeline view shall distinguish capture date, event date, document date, interview date, and publication date.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-005 — Digital Twin Timeline and State Projection

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** Future/proposed states shall not appear in current as-built views by default.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DATTWIN-006 — Digital Twin Timeline and State Projection

- **Priority:** P1
- **Category:** data
- **Source:** [`50-data/512_digital_twin_versioning.md`](../50-data/512_digital_twin_versioning.md)
- **Requirement:** Retention/deletion shall preserve required audit chronology while honoring privacy policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-001 — Developer Onboarding and Local Environment

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** The repository shall provide version-managed toolchains, containerized dependencies, seed fixtures, one-command checks, and troubleshooting.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-002 — Developer Onboarding and Local Environment

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** Local data shall be synthetic and clearly isolated from production.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-003 — Developer Onboarding and Local Environment

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** Developers shall complete secure-coding, data classification, truth/provenance, and model-license orientation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-004 — Developer Onboarding and Local Environment

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** The onboarding path shall validate schemas, run tests, ingest a fixture, execute mock metric/learned stages, and open the viewer.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-005 — Developer Onboarding and Local Environment

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** GPU setup shall verify driver/runtime compatibility and use approved local checkpoints only.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDEV-006 — Developer Onboarding and Local Environment

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/959_developer_onboarding.md`](../95-testing-delivery/959_developer_onboarding.md)
- **Requirement:** Contributor documentation shall state code owners, review expectations, ADR process, and release gates.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-001 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed feature shall satisfy linked requirements and acceptance tests, include typed contracts, errors, audit, metrics, authorization, retention, and user documentation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-002 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed schema change shall include compatibility, migration, rollback/recovery, fixtures, and generated clients.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-003 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed model integration shall include approval manifest, adapter isolation, benchmarks, failure detection, cost, monitoring, rollback, and reproducibility.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-004 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed UI shall include loading/error/empty/restricted states, accessibility, source labels, analytics/telemetry policy, and end-to-end tests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-005 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed operational service shall include SLO, alerts, runbooks, backup/recovery, capacity, and ownership.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-006 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** Acceptance evidence shall be linked to the release or epic record.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-007 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed provider adapter shall include signed manifest, isolation, contract tests, quarantine, stable errors, cost/resource limits, cancellation, and rollback.
- **Minimum verification:** Definition-of-done audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-008 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed proxy pipeline shall include per-use validation, limitations, protected regions, support maps, authority restrictions, and replacement.
- **Minimum verification:** Acceptance audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-009 — Definition of Done

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed hybrid viewer shall prove semantic stability, measurement re-resolution, security, safe locomotion, accessibility, and fallback.
- **Minimum verification:** End-to-end test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-010 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed conversion path shall include loss declaration, open export/import, provenance, policy inheritance, and preservation behavior.
- **Minimum verification:** Portability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-011 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** A completed external/manual workflow shall include minimization, receipt, expiry, quarantine, provider status, and data-class denial tests.
- **Minimum verification:** Security audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELDOD-012 — Definition of Done

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/960_definition_of_done.md`](../95-testing-delivery/960_definition_of_done.md)
- **Requirement:** Acceptance evidence shall be linked to requirement, provider version, benchmark profile, scene class, and release.
- **Minimum verification:** Traceability audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-001 — MVP Definition and Build Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** MVP shall ingest first-party iPhone and Polycam raw capture fixtures.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-002 — MVP Definition and Build Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** MVP shall run ARKit/LiDAR metric processing, a gated LingBot research adapter, alignment, TSDF/mesh, quality summary, and browser publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-003 — MVP Definition and Build Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** MVP shall create stable entities, anchors, evidence, assertions, tasks, scene commits, diff, search, and open export.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-004 — MVP Definition and Build Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** Construction demo shall include a systems room, devices/door/equipment, drawing link, issue, measurement verification, and report.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-005 — MVP Definition and Build Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** LiveForever demo shall include a room, object, interview stories, old media, uncertainty/conflict, evidence view, consent, and preservation export.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELMVP-006 — MVP Definition and Build Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/956_mvp_plan.md`](../95-testing-delivery/956_mvp_plan.md)
- **Requirement:** MVP shall run local workstation or hybrid and document production blockers.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-001 — Product and Research Roadmap

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** Every roadmap item shall name prerequisites, customer outcome, architecture impact, risk, acceptance, and deprecation/migration implications.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-002 — Product and Research Roadmap

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** Quarter labels shall not substitute for dependency-based sequencing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-003 — Product and Research Roadmap

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** Research spikes shall have time bounds and decisions, not become unowned permanent forks.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-004 — Product and Research Roadmap

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** Commercial dependencies shall have fallback/exit paths.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-005 — Product and Research Roadmap

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** Roadmap review shall use pilot evidence, benchmark results, cost, support burden, and consent/security incidents.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### DELROAD-006 — Product and Research Roadmap

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/957_roadmap.md`](../95-testing-delivery/957_roadmap.md)
- **Requirement:** The roadmap shall preserve local-only and open-export commitments as capabilities expand.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVDOC-001 — Document Control and Authority

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/000_document_control.md`](../00-governance/000_document_control.md)
- **Requirement:** Every normative document shall carry a unique specification identifier, version, status, update date, category, and normative flag.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVDOC-002 — Document Control and Authority

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/000_document_control.md`](../00-governance/000_document_control.md)
- **Requirement:** The release process shall produce a manifest containing every file path, byte count, word count, and SHA-256 digest.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVDOC-003 — Document Control and Authority

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/000_document_control.md`](../00-governance/000_document_control.md)
- **Requirement:** A breaking change shall identify affected schemas, APIs, stored data, exports, clients, tests, and migration steps.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVDOC-004 — Document Control and Authority

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/000_document_control.md`](../00-governance/000_document_control.md)
- **Requirement:** A waiver shall be rejected when it would cause unlicensed model use, unconsented biometric use, or presentation of generated content as verified fact.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVDOC-005 — Document Control and Authority

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/000_document_control.md`](../00-governance/000_document_control.md)
- **Requirement:** Superseded bundles shall remain retrievable for audit and migration testing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-001 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** Every assertion shall identify source class and may identify confidence, corroboration, dispute, and authority independently.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-002 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** Generated voice, likeness, dialogue, or first-person narration shall require a specific consent basis and persistent label.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-003 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** The platform shall provide an evidence-view mode for reconstructed memories and edited visual scenes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-004 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** Sensitive captures shall support subject access, correction, restriction, export, and deletion workflows subject to legal hold and shared-rights policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-005 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** The product shall not use grief, urgency, or family conflict to pressure users into broader consent or paid retention.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-006 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** Interaction smoothness or photorealism shall not suppress source, uncertainty, generation, dispute, redaction, or authority labels.
- **Minimum verification:** UX truthfulness test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-007 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** An interaction proxy shall not be cited as evidence for a construction condition, person's identity, object history, or remembered event.
- **Minimum verification:** Assertion policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-008 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** The experience shall expose unknown/occluded/uncertain regions instead of silently completing them for navigability or beauty.
- **Minimum verification:** Scenario test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVETH-009 — Data Ethics, Truthfulness, and Human Dignity

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/009_data_ethics_and_truthfulness.md`](../00-governance/009_data_ethics_and_truthfulness.md)
- **Requirement:** A user shall be able to reach source/evidence and limitations views from a photoreal or immersive scene without privileged tools.
- **Minimum verification:** Accessibility/UX test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-001 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Each model manifest shall record provider, model name, revision, checkpoint hash, source URLs, license documents, permitted uses, prohibited uses, geographic or customer restrictions, approver, and expiry/review date.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-002 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** The scheduler shall reject production jobs whose model manifest is research-only, expired, revoked, or incomplete.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-003 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Container builds shall produce an SBOM and license inventory including optional runtime downloads.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-004 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** The system shall prevent an adapter from downloading an unapproved checkpoint or segmentation model at first run.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-005 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Dataset manifests shall document consent/provenance, license, transformations, retention, and whether outputs may be commercialized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-006 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** A model replacement shall run shadow benchmarks and cannot inherit the prior model's approval automatically.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-007 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Every surface/conversion provider shall record exact code/service version, dependencies, models, datasets, terms, output rights, deployment, data classes, purposes, and expiration.
- **Minimum verification:** Manifest test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-008 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** A top-level license shall not automatically approve submodules, checkpoints, datasets, binaries, samples, hosted processing, or outputs.
- **Minimum verification:** License audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-009 — Dependency, Dataset, and Model Governance

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Manual/hosted provider admission shall fail closed when processing locality, retention, training use, security, or commercial permission is unknown for non-public data.
- **Minimum verification:** Governance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-010 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Provider replacement shall require new technical and legal approval and shall not inherit the predecessor's production status.
- **Minimum verification:** Replacement test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-011 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Runtime and build systems shall prohibit undeclared provider/model/dependency downloads.
- **Minimum verification:** Supply-chain test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVLIC-012 — Dependency, Dataset, and Model Governance

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/008_license_and_model_governance.md`](../00-governance/008_license_and_model_governance.md)
- **Requirement:** Historical derivatives shall retain the exact approval evidence and terms snapshot applicable at creation.
- **Minimum verification:** Provenance audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVNORM-001 — Normative Language and Requirement IDs

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/001_normative_language.md`](../00-governance/001_normative_language.md)
- **Requirement:** Requirement identifiers shall remain stable after publication even when wording is clarified.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVNORM-002 — Normative Language and Requirement IDs

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/001_normative_language.md`](../00-governance/001_normative_language.md)
- **Requirement:** A requirement shall have exactly one primary verification method and may list supplemental evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVNORM-003 — Normative Language and Requirement IDs

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/001_normative_language.md`](../00-governance/001_normative_language.md)
- **Requirement:** Undefined terms shall be linked to the glossary or defined in the owning document.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVNORM-004 — Normative Language and Requirement IDs

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/001_normative_language.md`](../00-governance/001_normative_language.md)
- **Requirement:** Words such as accurate, real-time, secure, reliable, and high-quality shall not appear in acceptance criteria without a measurable definition.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVNORM-005 — Normative Language and Requirement IDs

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/001_normative_language.md`](../00-governance/001_normative_language.md)
- **Requirement:** Conflicting requirements shall be resolved through an architecture decision record rather than implementation guesswork.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVOPEN-001 — Assumptions, Open Questions, and Experiment Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/006_open_questions_and_assumptions.md`](../00-governance/006_open_questions_and_assumptions.md)
- **Requirement:** The register shall include LingBot checkpoint licensing, supported hardware envelope, long-building drift, dynamic-scene behavior, and cross-session repeatability.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVOPEN-002 — Assumptions, Open Questions, and Experiment Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/006_open_questions_and_assumptions.md`](../00-governance/006_open_questions_and_assumptions.md)
- **Requirement:** Each high-risk assumption shall have a falsifiable experiment and acceptance threshold.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVOPEN-003 — Assumptions, Open Questions, and Experiment Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/006_open_questions_and_assumptions.md`](../00-governance/006_open_questions_and_assumptions.md)
- **Requirement:** An experiment shall retain input hashes, environment, exact model, output, analysis, and conclusion.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVOPEN-004 — Assumptions, Open Questions, and Experiment Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/006_open_questions_and_assumptions.md`](../00-governance/006_open_questions_and_assumptions.md)
- **Requirement:** Decisions that depend on customer policy shall identify the policy owner and default-safe behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVOPEN-005 — Assumptions, Open Questions, and Experiment Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/006_open_questions_and_assumptions.md`](../00-governance/006_open_questions_and_assumptions.md)
- **Requirement:** Unresolved P0 assumptions shall block release promotion.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPERS-001 — Stakeholders, Personas, and Responsibilities

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/004_stakeholders_and_personas.md`](../00-governance/004_stakeholders_and_personas.md)
- **Requirement:** Every privileged workflow shall name the accountable human role even when automation performs the work.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPERS-002 — Stakeholders, Personas, and Responsibilities

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/004_stakeholders_and_personas.md`](../00-governance/004_stakeholders_and_personas.md)
- **Requirement:** The user interface shall present task-focused capabilities instead of exposing infrastructure roles to ordinary users.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPERS-003 — Stakeholders, Personas, and Responsibilities

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/004_stakeholders_and_personas.md`](../00-governance/004_stakeholders_and_personas.md)
- **Requirement:** Consent and family governance roles shall remain separate from technical tenant administration.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPERS-004 — Stakeholders, Personas, and Responsibilities

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/004_stakeholders_and_personas.md`](../00-governance/004_stakeholders_and_personas.md)
- **Requirement:** A construction subcontractor shall not gain access to unrelated rooms or sensitive systems merely because they can access the project.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPERS-005 — Stakeholders, Personas, and Responsibilities

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/004_stakeholders_and_personas.md`](../00-governance/004_stakeholders_and_personas.md)
- **Requirement:** Personas with accessibility needs shall be included in capture and viewer usability tests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPRIN-001 — Product and Engineering Principles

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/003_product_principles.md`](../00-governance/003_product_principles.md)
- **Requirement:** Every automated transformation shall preserve a route back to source evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPRIN-002 — Product and Engineering Principles

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/003_product_principles.md`](../00-governance/003_product_principles.md)
- **Requirement:** A user shall be able to export their original assets, canonical manifests, scene metadata, and open-format derivatives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPRIN-003 — Product and Engineering Principles

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/003_product_principles.md`](../00-governance/003_product_principles.md)
- **Requirement:** Irreversible operations shall require explicit authority, impact preview, and auditable confirmation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPRIN-004 — Product and Engineering Principles

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/003_product_principles.md`](../00-governance/003_product_principles.md)
- **Requirement:** The implementation shall expose uncertainty and disagreement rather than compressing them into one unlabeled score.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVPRIN-005 — Product and Engineering Principles

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/003_product_principles.md`](../00-governance/003_product_principles.md)
- **Requirement:** New verticals shall reuse the canonical scene and evidence model unless an approved architecture decision demonstrates a necessary extension.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-001 — Program Risk Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** The risk register shall link each critical risk to requirements, tests, monitors, and incident playbooks.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-002 — Program Risk Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** A risk score increase into the critical band shall trigger release review within one business day.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-003 — Program Risk Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** Known safety or consent failures shall not be reclassified as ordinary quality defects.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-004 — Program Risk Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** Risk acceptance shall expire and require renewal based on current evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-005 — Program Risk Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** Closed risks shall retain closure evidence and residual-risk assessment.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-006 — Program Risk Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** The risk register shall track proxy-authority confusion, provider data egress, protected-geometry loss, anchor drift, immersive safety, derivative redaction, and provider lock-in.
- **Minimum verification:** Risk review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-007 — Program Risk Register

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** Critical hybrid risks shall have automated gates or explicit fail-safe modes rather than relying only on user training.
- **Minimum verification:** Control audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-008 — Program Risk Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** Provider and algorithm risks shall be stratified by scene class and intended use, not represented by one global quality rating.
- **Minimum verification:** Benchmark/risk audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVRISK-009 — Program Risk Register

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/007_risk_register.md`](../00-governance/007_risk_register.md)
- **Requirement:** A provider revocation or failure shall have a tested local/native-hybrid fallback and impact-analysis procedure.
- **Minimum verification:** Game-day test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-001 — Scope, Boundaries, and Non-Goals

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** Product interfaces shall display operating-envelope limitations wherever users can create or export measurements.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-002 — Scope, Boundaries, and Non-Goals

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** Marketing and generated reports shall not describe unverified phone scans as survey grade, code compliant, or as-built certified.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-003 — Scope, Boundaries, and Non-Goals

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** The platform shall prevent an AI agent from issuing a life-safety control command through spatial tools.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-004 — Scope, Boundaries, and Non-Goals

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** LiveForever experiences shall identify simulated voice, face, dialogue, and scene completion before or at first presentation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-005 — Scope, Boundaries, and Non-Goals

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** Out-of-scope requests shall generate a safe handoff or export rather than silent approximation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-006 — Scope, Boundaries, and Non-Goals

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** Product messaging shall describe splat-derived surfaces as interaction/visual derivatives unless independently promoted through an eligible metric workflow.
- **Minimum verification:** Marketing/UI review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-007 — Scope, Boundaries, and Non-Goals

- **Priority:** P0
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** Proxy, collision, and navigation assets shall not be marketed as survey, code, fabrication, robotic-safety, or historical-proof products.
- **Minimum verification:** Policy/content test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-008 — Scope, Boundaries, and Non-Goals

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** The platform shall remain useful through native hybrid rendering and open fallbacks when no splat-to-surface provider is available.
- **Minimum verification:** Portability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### GOVSCOPE-009 — Scope, Boundaries, and Non-Goals

- **Priority:** P1
- **Category:** governance
- **Source:** [`00-governance/002_scope_and_non_goals.md`](../00-governance/002_scope_and_non_goals.md)
- **Requirement:** A conversion capability shall not broaden the permitted use of its source data or representation.
- **Minimum verification:** Policy propagation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-001 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Public APIs shall represent spatial conversion, validation, publication, support remap, provider promotion, manual export/return, and hybrid scene views as versioned resources and explicit commands.
- **Minimum verification:** OpenAPI contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-002 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Creating, retrying, cancelling, validating, reviewing, and publishing shall be idempotent within their documented keys and state preconditions.
- **Minimum verification:** Concurrency and retry test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-003 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Worker completion shall create a candidate only; scene publication shall occur in a separate authoritative transaction after independent validation.
- **Minimum verification:** End-to-end state test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-004 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** The control plane shall issue least-privilege, short-lived, read-only input and write-only staging credentials to workers.
- **Minimum verification:** Security integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-005 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Events that assert publication, approval, cancellation, or invalidation shall be emitted only after the corresponding transaction commits.
- **Minimum verification:** Outbox consistency test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-006 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** A publication command shall reject stale candidate, policy, consent, provider, benchmark, transform, scene, or support-remap state.
- **Minimum verification:** Optimistic-concurrency test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-007 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** API and event payloads shall avoid raw geometry, media, transcripts, and restricted coordinates and shall return only authorized references and bounded summaries.
- **Minimum verification:** Data-leakage test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-008 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Manual external provider return shall require a conversion receipt and shall enter validation rather than publication.
- **Minimum verification:** Manual workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-009 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Durable jobs shall support leases, verified checkpoints, cancellation, reconciliation, bounded retries, and exactly-once publication effect.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-010 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Progress shall use stage work units and durable checkpoints with sequence numbers.
- **Minimum verification:** Event ordering test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-011 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Provider promotion APIs shall scope approval by data class, scene class, role, intended use, execution zone, hardware profile, and validity period.
- **Minimum verification:** Governance authorization test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-012 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Hybrid scene-view manifests shall be signed, short-lived, purpose-scoped, and generated after server-side spatial and content authorization.
- **Minimum verification:** Manifest security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-013 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Error responses shall use stable machine codes, safe user explanations, retry classification, and remediation without leaking restricted policy details.
- **Minimum verification:** Error-contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-014 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Agents shall use constrained tools that cannot approve their own outputs, increase authority, widen audience, or bypass consent/license policy.
- **Minimum verification:** Agent safety test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-015 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Cost, resource, and quota records shall be available before and after execution and attributable by operation and project.
- **Minimum verification:** Billing attribution test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBAPI-016 — Splat-Surface APIs, Jobs, and Domain Events

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/614_splat_surface_api_and_events.md`](../60-platform/614_splat_surface_api_and_events.md)
- **Requirement:** Schema compatibility for requests, results, events, and scene-view manifests shall be validated in CI and at publication boundaries.
- **Minimum verification:** Schema registry test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-001 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** The server shall generate an authorized hybrid scene-view manifest selecting typed bindings by scene revision, purpose, principal, audience, device, time, and policy.
- **Minimum verification:** API authorization test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-002 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Unauthorized assets and spatial volumes shall be excluded server-side rather than hidden only by the client.
- **Minimum verification:** Security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-003 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Runtime selection shall preserve the source role of each hit and shall not silently convert a proxy or visual hit into verified metric evidence.
- **Minimum verification:** Typed-selection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-004 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Measurement endpoints shall resolve to eligible metric support or be saved only as explicitly approximate and unverified.
- **Minimum verification:** End-to-end measurement test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-005 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Design, generated, inferred, observed, and verified truth labels shall remain available in every client and export profile.
- **Minimum verification:** Cross-client truth-label test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-006 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Collision and navigation shall use declared actor and intended-use profiles and shall not imply egress, accessibility, safety, or robotic suitability without matching verification.
- **Minimum verification:** Profile-policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-007 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** A missing or invalid proxy shall not cause measurement fallback to the visual splat or change metric authority.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-008 — Hybrid Scene Runtime

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Evidence reveal shall expose accessible source, lineage, limitations, and revision context for a selected entity or memory.
- **Minimum verification:** Evidence UX and authorization test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-009 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** The renderer adapter shall support registered splats and meshes in a common frame with depth-aware composition or an explicit declared fallback.
- **Minimum verification:** Renderer conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-010 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Tile and LOD transitions shall preserve world registration, semantic identity, and stable selection within benchmark thresholds.
- **Minimum verification:** Streaming regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-011 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** The runtime shall provide independent fallbacks for display, picking, collision, navigation, occlusion, and evidence.
- **Minimum verification:** Degradation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-012 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Temporal comparison shall identify source revisions and shall label any generated interpolation as non-evidentiary.
- **Minimum verification:** Spatial Git viewer test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-013 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Offline and local-only clients shall enforce the same authority, truth, consent, and measurement contracts as hosted clients.
- **Minimum verification:** Offline parity test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-014 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Runtime telemetry shall measure performance and failure without collecting restricted source content or unnecessary precise spatial details.
- **Minimum verification:** Privacy telemetry review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-015 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** LiveForever clients shall provide quiet mode, safe exit, accessible non-immersive alternatives, and audience controls.
- **Minimum verification:** Accessibility and safety test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBRUN-016 — Hybrid Scene Runtime

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/613_hybrid_scene_runtime.md`](../60-platform/613_hybrid_scene_runtime.md)
- **Requirement:** Construction clients shall surface design/observed/verified state and prohibit a visually blended design object from appearing as existing condition.
- **Minimum verification:** Construction acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-001 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Provider and runtime claims shall be evaluated by versioned intended-use profiles rather than a single visual quality score.
- **Minimum verification:** Benchmark framework test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-002 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Ground truth shall be independent of the candidate provider and shall include exact/surveyed geometry, semantic regions, held-out views, or annotated behavior appropriate to the claim.
- **Minimum verification:** Dataset review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-003 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Geometry metrics shall be reported globally and by critical semantic region so averages cannot hide missing doors, stairs, devices, objects, or false walls.
- **Minimum verification:** Metrics test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-004 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Authority tests shall prove that proxy, visual, design, generated, and provider-self-validated outputs cannot receive prohibited status.
- **Minimum verification:** Negative policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-005 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Provider conformance shall cover policy admission, hashes, coordinates, resources, progress, cancellation, recovery, isolation, outputs, provenance, and publication separation.
- **Minimum verification:** Conformance suite
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-006 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Security tests shall prove unapproved external-provider denial before data mount and complete derivative invalidation after privacy or consent change.
- **Minimum verification:** Security integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-007 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Construction and LiveForever acceptance scenarios shall pass with retained source, operation, validation, viewer, review, and export evidence.
- **Minimum verification:** Vertical E2E tests
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-008 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Production release shall include at least one approved local or project-private conversion/proxy path and shall not depend solely on a public manual web tool.
- **Minimum verification:** Release review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-009 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Selection tests shall measure role resolution, entity precision/recall, hit error, metric snap residual, LOD stability, and remap behavior.
- **Minimum verification:** Automated interaction test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-010 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Collision and navigation shall be benchmarked separately for declared actor profiles and shall not imply safety, accessibility, egress, or robotics approval.
- **Minimum verification:** Profile benchmark
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-011 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Large-scene tests shall cover tiling, seams, streaming, independent regeneration, cross-tile identity, memory, and degraded modes.
- **Minimum verification:** Building-scale test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-012 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Provider upgrades shall run in shadow and compare quality, behavior, performance, cost, security, license, and reproducibility against the active version.
- **Minimum verification:** Upgrade gate
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-013 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Human evaluation shall be task-based and shall test recognition of authority/truth labels, evidence access, comfort, accessibility, and failure communication.
- **Minimum verification:** Controlled user study
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-014 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** All benchmark evidence shall be machine-readable, content-addressed, reproducible where claimed, and attached to provider and release records.
- **Minimum verification:** Evidence audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-015 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Mesh-to-splat and splat-to-surface round trips shall report information loss and shall not claim representation equivalence.
- **Minimum verification:** Interoperability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### HYBTEST-016 — Splat-Surface Benchmark and Acceptance Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/961_splat_surface_benchmark_acceptance.md`](../95-testing-delivery/961_splat_surface_benchmark_acceptance.md)
- **Requirement:** Malformed and adversarial spatial files shall be parsed in isolation with bounded resources and no publication side effect.
- **Minimum verification:** Fuzz and abuse test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-001 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** Consent records shall include grantor, authority basis, subject/data scope, processing purposes, modalities, audiences, providers, geography, effective/expiry, revocation, posthumous rules, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-002 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** The policy engine shall evaluate all applicable subject, contributor, third-party, minor, and audience restrictions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-003 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** A guardian/executor transition shall require documented authority and cannot enable prohibited generated presence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-004 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** The system shall support sealed/private, family, named-invite, memorial-event, and public editions with separate assets if needed.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-005 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** Revocation shall stop new processing immediately and initiate derivative review/deletion/restriction according to policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFCONS-006 — Consent, Privacy, Family Governance, and Posthumous Administration

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/808_consent_privacy_family_governance.md`](../80-liveforever/808_consent_privacy_family_governance.md)
- **Requirement:** Disputed authority shall freeze high-risk changes while preserving access needed for due process and safety.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-001 — LiveForever Demonstration Scenario

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** The subject shall create consent/audience settings, capture the room, scan a meaningful object, and record an interview.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-002 — LiveForever Demonstration Scenario

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** The platform shall transcribe and anchor stories to the room/object while preserving source time ranges.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-003 — LiveForever Demonstration Scenario

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** Old photographs shall be placed with method/uncertainty and shown in evidence view.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-004 — LiveForever Demonstration Scenario

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** A historical room element shall be reconstructed with visible source coverage and generated-gap labeling.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-005 — LiveForever Demonstration Scenario

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** A family contributor shall add an alternate recollection and the edition shall present both without overwriting either.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDEMO-006 — LiveForever Demonstration Scenario

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/813_liveforever_demo_scenario.md`](../80-liveforever/813_liveforever_demo_scenario.md)
- **Requirement:** The demo shall produce a private family share and an offline preservation export with different permissions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-001 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** A dispute record shall identify assertions, contributors, issue, evidence, visibility, status, and resolution/edition decision.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-002 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** Corrections shall distinguish transcription correction, factual correction, contributor retraction, consent restriction, and alternate interpretation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-003 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** A contributor shall be able to restrict their own account subject to agreed shared/preservation policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-004 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** The system shall not use majority vote as proof of factual certainty.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-005 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** Agents shall present conflicts neutrally and cite sources rather than choosing a favorite account without policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFDISP-006 — Conflicting Memories, Corrections, and Family Disputes

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/807_conflicting_memories.md`](../80-liveforever/807_conflicting_memories.md)
- **Requirement:** Public editions shall disclose material unresolved disputes when omission would create a misleading narrative.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-007 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Free locomotion shall require accepted scale, walkability, opening, stair/fall, spawn, and safe-exit checks.
- **Minimum verification:** Immersive safety test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-008 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Spatial triggers shall not bypass consent, audience, truth-label, quiet-mode, synthetic-presence, or stop controls.
- **Minimum verification:** End-to-end policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-009 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** An interaction proxy shall not be presented as evidence that an object or event historically existed at a location.
- **Minimum verification:** Truth-label test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-010 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Guided, seated, teleport, 2D/source, transcript/audio, and evidence alternatives shall be available as appropriate.
- **Minimum verification:** Accessibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-011 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Proxy replacement shall preserve story/object/person/media anchors or route unresolved anchors to family review.
- **Minimum verification:** Remesh test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFEXP-012 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** A non-splat preservation experience shall remain usable when the preferred renderer is unavailable.
- **Minimum verification:** Preservation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-001 — Memory Graph and Narrative Data Model

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** A memory record shall include stable ID, title/working label, contributor, source class, time expression, place/object/person relationships, themes, emotional sensitivity, assertions, evidence, consent, and status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-002 — Memory Graph and Narrative Data Model

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** Approximate dates/locations shall use bounded or qualitative uncertainty rather than fabricated precision.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-003 — Memory Graph and Narrative Data Model

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** A narrative edition shall reference exact memory/assertion revisions and presentation choices.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-004 — Memory Graph and Narrative Data Model

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** Family corrections shall create new assertions or revisions with provenance, not overwrite original testimony.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-005 — Memory Graph and Narrative Data Model

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** The graph shall support private, family, invited, memorial, and public audience scopes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFGRAPH-006 — Memory Graph and Narrative Data Model

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/801_memory_graph.md`](../80-liveforever/801_memory_graph.md)
- **Requirement:** Search and agents shall respect contributor-specific and subject-specific consent attached to graph elements.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-001 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** LiveForever shall keep captured place, historical reconstruction, generated interpretation, semantic memory, and evidence roles separately identifiable.
- **Minimum verification:** Schema and viewer test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-002 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** A proxy or visual reconstruction shall not establish historical certainty, identity, speech, intent, relationship, or event occurrence without supporting evidence.
- **Minimum verification:** Truth-policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-003 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Memory identity and evidence shall survive proxy regeneration, splat retraining, tiling, and renderer replacement.
- **Minimum verification:** Remapping and migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-004 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Every visual, proxy, collision, navigation, screenshot, and export derivative shall inherit applicable consent, audience, retention, and deletion dependencies.
- **Minimum verification:** Consent propagation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-005 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Generated or artistically reconstructed regions and objects shall remain machine-readable and visibly labeled and shall never be reused as source evidence.
- **Minimum verification:** Generation-lineage test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-006 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Conflicting or alternate reconstructions shall be able to coexist without forcing one branch to appear as settled fact.
- **Minimum verification:** Alternate-memory scenario
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-007 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** A person likeness, voice, gesture, dialogue, or first-person agent shall remain disabled unless the separate consent and safety gates authorize it.
- **Minimum verification:** Safety policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-008 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Sensitive private-place data shall not be sent to an unapproved hosted conversion or editing provider.
- **Minimum verification:** External-provider security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-009 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** The experience shall support evidence reveal from a spatial memory or object within the current audience policy.
- **Minimum verification:** Evidence UX test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-010 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Collision/navigation shall be non-safety-critical and shall provide teleport, guided transition, bounded navigation, or no-entry fallback for uncertain geometry.
- **Minimum verification:** VR/desktop navigation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-011 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Quiet mode, immediate safe exit, reduced motion, captions/transcripts, and non-immersive alternatives shall be available.
- **Minimum verification:** Accessibility and emotional-safety test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-012 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Spatialized archival, restored, reenacted, ambient, and synthesized audio shall retain distinct provenance labels.
- **Minimum verification:** Audio provenance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-013 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** A historical branch shall declare the source class of each material element or region at the granularity supported by the reconstruction.
- **Minimum verification:** Branch manifest test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-014 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** Preservation export shall include open or documented assets, semantic graph, truth labels, consent policies, source hashes, and accessible fallbacks.
- **Minimum verification:** Independent restore test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-015 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** A consent or audience change shall trigger deterministic withdrawal, redaction, regeneration, or erasure of affected derived representations.
- **Minimum verification:** Revocation drill
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFHYB-016 — Hybrid Representation for LiveForever Spatial Memories

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/814_hybrid_representation_liveforever.md`](../80-liveforever/814_hybrid_representation_liveforever.md)
- **Requirement:** The system shall permit a source-only or evidence-first experience that does not require generated content, splats, avatars, or immersive navigation.
- **Minimum verification:** Minimal preservation scenario
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-001 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** Each session shall record participants, consent context, recording state, source media, timestamps, device, environment notes, and interruptions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-002 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** Transcript segments shall link to exact audio/video time ranges and preserve speaker uncertainty.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-003 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** Agent-generated questions shall be stored with model/prompt lineage when they materially shape the interview.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-004 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** The interface shall support private markers and review before broader publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-005 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** Sensitive topics and distress signals shall trigger configured pacing, pause, skip, or human handoff behavior without diagnosis.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFINT-006 — Interview Agent, Recording, and Conversational Capture

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/802_interview_agent.md`](../80-liveforever/802_interview_agent.md)
- **Requirement:** Corrections shall preserve original transcript/audio and create an edited reading layer with attribution.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-001 — AI Truth Labels and Evidence View

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** The platform shall support at minimum: direct_capture, source_document, first_person_recollection, witness_recollection, corroborated_synthesis, inferred, reconstructed, restored, generated, artistic, disputed, and unknown.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-002 — AI Truth Labels and Evidence View

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** Generated or reconstructed content shall retain model, prompt/instructions, inputs, operator decisions, and output hash where policy permits.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-003 — AI Truth Labels and Evidence View

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** The viewer shall show labels at first meaningful presentation and on demand at region/entity/assertion detail.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-004 — AI Truth Labels and Evidence View

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** Static exports shall include legends and source labels that cannot be cropped away without altering the export artifact.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-005 — AI Truth Labels and Evidence View

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** Agents shall include source labels in factual answers and cannot paraphrase generated dialogue as a quote.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFLABEL-006 — AI Truth Labels and Evidence View

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/809_ai_truth_labels.md`](../80-liveforever/809_ai_truth_labels.md)
- **Requirement:** Automated tests shall verify labels survive scene commits, reports, share links, exports, and offline bundles.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-001 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** Media assets shall store hash, technical metadata, source/custody, date uncertainty, people/place/object annotations, rights/consent, sensitivity, and derivative lineage.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-002 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** OCR and captions shall cite page/image regions and confidence and allow correction.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-003 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** Spatial placement shall record method, transform/anchor, uncertainty, and supporting correspondences.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-004 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** Restoration shall never overwrite the preservation master.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-005 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** The experience shall allow switching between original and restored/generated variants.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFMEDIA-006 — Photographs, Video, Letters, Documents, and Archives

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/804_photos_video_documents.md`](../80-liveforever/804_photos_video_documents.md)
- **Requirement:** Public editions shall enforce rights and consent, not merely project membership.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-001 — LiveForever Spatial Memory Overview

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** A LiveForever project shall represent subject, contributors, family/relationships, places, objects, events, memories, media, interviews, assertions, evidence, consent, audiences, and editions.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-002 — LiveForever Spatial Memory Overview

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** Every presented factual claim shall link to source evidence or be labeled as unsourced recollection/inference/generation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-003 — LiveForever Spatial Memory Overview

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** Generated first-person dialogue, voice, likeness, or behavior shall require purpose-specific consent and persistent disclosure.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-004 — LiveForever Spatial Memory Overview

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** A guardian/executor workflow shall define posthumous administration without silently expanding the subject's permissions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-005 — LiveForever Spatial Memory Overview

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** Users shall be able to export original media, transcripts, memory graph, consent record, and open spatial assets.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFOVR-006 — LiveForever Spatial Memory Overview

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/800_vertical_overview.md`](../80-liveforever/800_vertical_overview.md)
- **Requirement:** The experience shall avoid claims of consciousness, certainty, or direct communication with the deceased.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-001 — Places, Objects, People, and Relationships

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** Place records shall support address/region with privacy controls, names/aliases, time validity, scenes, maps, stories, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-002 — Places, Objects, People, and Relationships

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** Object records shall support physical description, ownership/custody history, spatial anchors, photographs, documents, stories, and preservation status.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-003 — Places, Objects, People, and Relationships

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** Person records shall support names/aliases, relationships, audience/privacy, media consent, and identity evidence without requiring biometric templates.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-004 — Places, Objects, People, and Relationships

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** Face or voice recognition suggestions shall remain private review items and use approved models/consent.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-005 — Places, Objects, People, and Relationships

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** A memory shall be able to refer to an unidentified person or object without forced classification.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPLACE-006 — Places, Objects, People, and Relationships

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/803_places_objects_people.md`](../80-liveforever/803_places_objects_people.md)
- **Requirement:** Deceased, living, minor, and public-figure subjects shall support different default consent/risk policies.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-001 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** A generated-presence consent shall define modality, purpose, audience, training data, providers, duration, posthumous behavior, prohibited topics/actions, and revocation/guardian process.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-002 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** Every generated interaction shall disclose simulation in the interface and retained session record.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-003 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** The persona shall not make legal, financial, medical, consent, inheritance, or relationship decisions on behalf of the subject.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-004 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** Outputs shall cite or expose grounding evidence and label imaginative synthesis.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-005 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** Model training artifacts and biometric embeddings shall use highly restricted storage and deletion controls.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRES-006 — Voice, Likeness, Avatar, and Simulated Presence

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/805_voice_avatar_presence.md`](../80-liveforever/805_voice_avatar_presence.md)
- **Requirement:** A kill switch shall immediately disable future generation while preserving authorized audit and source records.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-001 — Long-Term Preservation and Digital Legacy

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** Preservation packages shall include originals, technical metadata, rights/consent, transcripts, memory graph, scene/evidence manifests, open spatial assets, checksums, and human-readable guides.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-002 — Long-Term Preservation and Digital Legacy

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** The system shall perform scheduled fixity checks and repair from independent replicas when authorized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-003 — Long-Term Preservation and Digital Legacy

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** Format migration shall preserve originals and create documented derivatives with validation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-004 — Long-Term Preservation and Digital Legacy

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** At least one edition shall be viewable without a proprietary cloud API.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-005 — Long-Term Preservation and Digital Legacy

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** Succession plans shall define administrators, recovery methods, keys, billing/retention choices, and prohibited uses.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFPRESV-006 — Long-Term Preservation and Digital Legacy

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/811_long_term_preservation.md`](../80-liveforever/811_long_term_preservation.md)
- **Requirement:** Service shutdown planning shall include bulk export, key handoff or cryptographic deletion, and clear family notice.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-001 — Spatial and Temporal Memory Reconstruction

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** A reconstruction plan shall list target time/place, source assets, testimonies, known controls, gaps, assumptions, models, human decisions, and intended audience.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-002 — Spatial and Temporal Memory Reconstruction

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** Every reconstructed region/entity shall carry source class, supporting evidence, confidence/uncertainty, and creator/model lineage.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-003 — Spatial and Temporal Memory Reconstruction

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** Generated fill shall be togglable or visually inspectable separately from direct/source-constrained content.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-004 — Spatial and Temporal Memory Reconstruction

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** Conflicting evidence shall create alternatives or disputed attributes rather than arbitrary hidden selection.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-005 — Spatial and Temporal Memory Reconstruction

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** The platform shall preserve current capture and historical reconstruction as distinct states.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFREC-006 — Spatial and Temporal Memory Reconstruction

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/806_memory_reconstruction.md`](../80-liveforever/806_memory_reconstruction.md)
- **Requirement:** A reconstruction edition shall include a limitations statement understandable to family viewers.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-001 — LiveForever Vertical Acceptance Tests

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** The pilot shall capture one meaningful room, at least three spatially anchored interview stories, photographs/documents, one object, and a timeline.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-002 — LiveForever Vertical Acceptance Tests

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** The pilot shall demonstrate direct evidence, uncertain date, conflicting recollection, source-constrained reconstruction, and clearly labeled generated fill.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-003 — LiveForever Vertical Acceptance Tests

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** A contributor shall restrict one segment and the restriction shall propagate to search, viewer, agent, reports, share links, and export.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-004 — LiveForever Vertical Acceptance Tests

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** A family reviewer shall propose a correction without altering the original recording/transcript.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-005 — LiveForever Vertical Acceptance Tests

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** The system shall export an offline package with originals, transcript, graph, scene, labels, consent summary, and checksums.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFTEST-006 — LiveForever Vertical Acceptance Tests

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/812_liveforever_acceptance_tests.md`](../80-liveforever/812_liveforever_acceptance_tests.md)
- **Requirement:** Accessibility tests shall cover captions, keyboard navigation, screen-reader metadata, reduced motion, and non-voice experience.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-001 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Users shall control autoplay, voice, generated presence, ambient sound, animation, and content sensitivity.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-002 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Every story shall have transcript/captions and source/evidence access when authorized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-003 — LiveForever Experience and Narrative Design

- **Priority:** P0
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** The interface shall warn before highly sensitive or potentially distressing content according to contributor labeling and user preference.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-004 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** Family contributions shall enter review without modifying a published edition automatically.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-005 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** The experience shall provide clear exit, pause, and return-to-neutral-space controls.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### LIFUX-006 — LiveForever Experience and Narrative Design

- **Priority:** P1
- **Category:** liveforever
- **Source:** [`80-liveforever/810_experience_design.md`](../80-liveforever/810_experience_design.md)
- **Requirement:** A saved narrative path shall record edition and scene commits so future updates do not silently change it.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-001 — Audit, Integrity, and Chain of Custody

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Audit events shall include actor/workload, action, resource, tenant/project, time, source IP/device context when appropriate, purpose, outcome, trace, and before/after references.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-002 — Audit, Integrity, and Chain of Custody

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Capture finalization shall record package root hash, device/app, signer, and verification result.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-003 — Audit, Integrity, and Chain of Custody

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Evidence access, model execution, authority changes, consent changes, exports, and deletion shall be audited.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-004 — Audit, Integrity, and Chain of Custody

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Audit storage shall prevent ordinary application roles from altering or deleting events.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-005 — Audit, Integrity, and Chain of Custody

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Verification tools shall detect gaps, broken chains, invalid signatures, and missing referenced manifests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAUDIT-006 — Audit, Integrity, and Chain of Custody

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/904_audit_chain_of_custody.md`](../90-security-ops/904_audit_chain_of_custody.md)
- **Requirement:** Legal/evidentiary claims shall require separate counsel and jurisdictional procedure.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-001 — AWS Reference Architecture

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** Infrastructure shall be defined as code with separate environments/accounts or equivalent strong boundaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-002 — AWS Reference Architecture

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** Databases and object stores shall be private, encrypted, backed up, and accessible only through approved identities/endpoints.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-003 — AWS Reference Architecture

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** GPU queues shall enforce tenant/profile quotas, cost budgets, and dead-letter handling.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-004 — AWS Reference Architecture

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** CloudFront/CDN delivery shall use signed authorization and redacted immutable derivatives; raw assets are not public origins.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-005 — AWS Reference Architecture

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** KMS/secrets access shall be least privilege and audited.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSAWS-006 — AWS Reference Architecture

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/908_aws_reference_architecture.md`](../90-security-ops/908_aws_reference_architecture.md)
- **Requirement:** Provider-specific services shall have documented export/replacement paths.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-001 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** CI shall run formatting, type checks, unit/integration tests, schema compatibility, license/SBOM, secret scan, vulnerability scan, and artifact signing.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-002 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** Mobile, web, service, worker, infrastructure, and model manifests shall share a release record.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-003 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** Production deployment shall verify signatures and environment policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-004 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** Release promotion shall require benchmark and acceptance evidence from `955_release_gates.md`.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-005 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** Emergency patches shall still produce traceable artifacts and retrospective review.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCICD-006 — CI/CD, Software Supply Chain, and Release Engineering

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/911_ci_cd_supply_chain.md`](../90-security-ops/911_ci_cd_supply_chain.md)
- **Requirement:** Rollback shall include service, worker routing/model, configuration, and database compatibility plans.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-001 — Cost, Capacity, and Unit Economics Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** The model shall attribute CPU seconds, GPU seconds by profile, memory, object bytes by tier, database/storage growth, requests, search/vector usage, CDN/egress, transcription/OCR/model API use, and support overhead.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-002 — Cost, Capacity, and Unit Economics Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** Costs shall roll up by tenant, project, capture, run, stage, model, and calendar period.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-003 — Cost, Capacity, and Unit Economics Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** Admission control shall enforce project budgets, tenant quotas, concurrency, and anomaly detection.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-004 — Cost, Capacity, and Unit Economics Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** The UI shall show estimated cost/processing tier before optional expensive final reconstruction.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-005 — Cost, Capacity, and Unit Economics Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** Capacity plans shall use measured scene minutes/frames/area and peak concurrency with headroom.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSCOST-006 — Cost, Capacity, and Unit Economics Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/909_cost_capacity_model.md`](../90-security-ops/909_cost_capacity_model.md)
- **Requirement:** A price-source update shall be versioned and not change historical actual-cost records.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-001 — Backup, Restore, and Disaster Recovery

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** Recovery objectives shall be declared by data/service class and deployment profile.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-002 — Backup, Restore, and Disaster Recovery

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** Database backups shall support point-in-time recovery and periodic isolated restore tests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-003 — Backup, Restore, and Disaster Recovery

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** Object storage shall use versioning/immutability or equivalent protections against accidental/malicious deletion.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-004 — Backup, Restore, and Disaster Recovery

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** Key recovery shall be tested without exposing root keys to ordinary operators.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-005 — Backup, Restore, and Disaster Recovery

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** A restore shall reconcile manifests/hashes, database references, object assets, audit chronology, and queued jobs before reopening writes.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSDR-006 — Backup, Restore, and Disaster Recovery

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/906_backup_restore_dr.md`](../90-security-ops/906_backup_restore_dr.md)
- **Requirement:** Disaster tests shall include a complete tenant/project portability export when service recovery is not practical.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-001 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** Every deployment shall expose the same canonical package, scene, evidence, and export contracts.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-002 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** Hybrid transfer policy shall specify which asset classes may leave the site and at what processing stage.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-003 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** Edge nodes shall enroll with unique identity, signed software, disk encryption, health reporting, and revocation.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-004 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** Offline updates shall be signed and rollback-capable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-005 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** A project migration between deployment modes shall preserve IDs, history, permissions, consent, hashes, and model/run manifests.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSHYB-006 — Cloud, Hybrid, Edge, and Local Deployment

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/907_cloud_hybrid_deployment.md`](../90-security-ops/907_cloud_hybrid_deployment.md)
- **Requirement:** Cloud dependence shall be visible to administrators before enabling a feature.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-001 — Encryption and Key Management

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** All network connections shall use current approved TLS with certificate validation; local transfer uses authenticated encrypted channels.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-002 — Encryption and Key Management

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** Data keys shall be generated securely, wrapped by managed or local key-encryption keys, and scoped by policy.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-003 — Encryption and Key Management

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** Key access shall be logged with actor/workload, purpose, resource scope, and outcome.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-004 — Encryption and Key Management

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** Rotation shall support rewrapping and emergency revocation with bounded impact.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-005 — Encryption and Key Management

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** Recovery mechanisms shall avoid one-person permanent loss while respecting local-only and family succession policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSKEY-006 — Encryption and Key Management

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/902_encryption_key_management.md`](../90-security-ops/902_encryption_key_management.md)
- **Requirement:** Cryptographic erasure shall include key deletion evidence and residual replica/backup timelines.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-001 — Performance and Scalability Budgets

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** The iOS app shall maintain capture responsiveness and bounded frame-drop behavior on supported devices under declared thermal conditions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-002 — Performance and Scalability Budgets

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** Upload shall saturate available policy-permitted bandwidth while preserving foreground responsiveness and resumability.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-003 — Performance and Scalability Budgets

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** API and search SLOs shall be defined by endpoint class and result size.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-004 — Performance and Scalability Budgets

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** The viewer shall define frame-time, first-meaningful-scene, memory, and network budgets by device tier and scene size.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-005 — Performance and Scalability Budgets

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** Pipeline profiles shall define expected runtime and peak VRAM/RAM per input class.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPERF-006 — Performance and Scalability Budgets

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/910_performance_budgets.md`](../90-security-ops/910_performance_budgets.md)
- **Requirement:** Load tests shall include noisy-neighbor and tenant-quota behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-001 — Privacy Engineering and Compliance Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** The platform shall maintain a data inventory linking category, purpose, legal/consent basis, processors, residency, retention, security, and rights workflow.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-002 — Privacy Engineering and Compliance Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** New data purposes or providers shall require privacy impact review before processing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-003 — Privacy Engineering and Compliance Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** Subject-access export shall explain source records, derivatives, sharing, consent, and automated processing in understandable form.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-004 — Privacy Engineering and Compliance Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** Correction/restriction/deletion requests shall be tracked and verified across canonical and derived stores.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-005 — Privacy Engineering and Compliance Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** Vendor agreements and settings shall prohibit training/use beyond approved purpose where required.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSPRIV-006 — Privacy Engineering and Compliance Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/903_privacy_compliance.md`](../90-security-ops/903_privacy_compliance.md)
- **Requirement:** Incident workflows shall identify affected people/projects and applicable notification decision without exposing additional data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-001 — Security Architecture and Zero-Trust Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Human privileged access shall require phishing-resistant MFA where available and just-in-time elevation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-002 — Security Architecture and Zero-Trust Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Service-to-service authentication shall use short-lived workload identities with audience and scope.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-003 — Security Architecture and Zero-Trust Controls

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Network policies shall restrict worker egress and prevent runtime model downloads in production.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-004 — Security Architecture and Zero-Trust Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Secrets shall live in an approved secret manager and never in repositories, images, logs, manifests, or mobile packages.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-005 — Security Architecture and Zero-Trust Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Containers and mobile builds shall be hardened, signed, scanned, and patched under defined SLAs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSEC-006 — Security Architecture and Zero-Trust Controls

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/901_security_architecture.md`](../90-security-ops/901_security_architecture.md)
- **Requirement:** Sensitive-access and administrative events shall be immutable and monitored.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-001 — SRE Runbooks and Incident Operations

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** Runbooks shall cover database outage, object corruption, queue backlog, GPU failure, model regression, cross-tenant suspicion, leaked share link, consent failure, bad redaction, deletion error, and backup restore.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-002 — SRE Runbooks and Incident Operations

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** Each runbook shall include trigger, severity, roles, commands/controls, decision points, evidence, validation, rollback, and communications.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-003 — SRE Runbooks and Incident Operations

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** Incident actions shall be audited and preserve forensic evidence without copying sensitive data unnecessarily.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-004 — SRE Runbooks and Incident Operations

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** After-action reviews shall create tracked corrective requirements and tests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-005 — SRE Runbooks and Incident Operations

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** Runbooks shall be exercised through game days.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSRE-006 — SRE Runbooks and Incident Operations

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/905_sre_runbooks.md`](../90-security-ops/905_sre_runbooks.md)
- **Requirement:** On-call access shall use just-in-time privileges and recorded sessions where appropriate.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-001 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** Support bundles shall contain versions, manifests, metrics, stable errors, hardware/profile, and selected redacted logs without raw media by default.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-002 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** Customer-approved scene access shall state scope, purpose, personnel, duration, and revocation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-003 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** Support engineers shall not copy raw assets to unmanaged systems.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-004 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** High-risk LiveForever or security-system issues shall route to specially authorized personnel.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-005 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** Resolved tickets shall link remediation and affected release without retaining unnecessary customer data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSSUP-006 — Support, Customer Operations, and Safe Diagnostics

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/912_support_operations.md`](../90-security-ops/912_support_operations.md)
- **Requirement:** Support tooling shall enforce tenant isolation and cannot generate unrestricted signed URLs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-007 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Threat modeling shall cover geometry/splat payload parsing, provider egress, topology disclosure, derivative redaction, authority spoofing, and immersive collision/navigation failure.
- **Minimum verification:** Threat-model review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-008 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Untrusted provider outputs shall remain quarantined with malware/resource/format/transform/content validation.
- **Minimum verification:** Security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-009 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Authorization shall apply to geometry derivatives even when texture or obvious personal data has been removed.
- **Minimum verification:** Policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-010 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Abuse tests shall attempt to elevate proxy/design assets to verified/observed authority through API, import, UI, and export paths.
- **Minimum verification:** Adversarial test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-011 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Client and CDN caches shall purge or invalidate superseded/redacted hybrid assets according to policy.
- **Minimum verification:** Cache/privacy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHR-012 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Immersive safety failures shall disable affected locomotion modes while preserving a safe fallback.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-001 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** The threat model shall enumerate capture-device compromise, upload tampering, archive bombs, parser exploits, GPU escape, cross-tenant access, signed-URL leakage, viewer scraping, model exfiltration, prompt injection, insider abuse, and destructive deletion.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-002 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Each critical threat shall map to preventative, detective, and recovery controls plus tests and owners.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-003 — Threat Model

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Sensitive facility and family data shall use misuse/abuse cases beyond ordinary confidentiality.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-004 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** The threat model shall be reviewed when adding a sensor, model provider, sharing mode, plugin, or new data purpose.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-005 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** Residual risks shall be visible to release decision makers.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### OPSTHREA-006 — Threat Model

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/900_threat_model.md`](../90-security-ops/900_threat_model.md)
- **Requirement:** A public viewer shall be analyzed as hostile client code with no trusted secrets.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-001 — Spatial LLM and Agent Tooling

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** Tool schemas shall state permissions, side effects, idempotency, evidence requirements, and allowed source classes.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-002 — Spatial LLM and Agent Tooling

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** The agent shall cite entity/evidence identifiers for factual answers and distinguish inference.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-003 — Spatial LLM and Agent Tooling

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** Measurement tools shall operate only on accepted metric geometry or verified points and return uncertainty/source.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-004 — Spatial LLM and Agent Tooling

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** The agent shall refuse to fabricate missing construction facts or speak as a deceased person without an enabled, consented simulation mode.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-005 — Spatial LLM and Agent Tooling

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** Mutating proposals shall include rationale, affected resources, source evidence, confidence, and required reviewer.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAGENT-006 — Spatial LLM and Agent Tooling

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/608_spatial_llm_agents.md`](../60-platform/608_spatial_llm_agents.md)
- **Requirement:** Agent evaluation shall test hallucination, permission leakage, prompt injection in documents/transcripts, destructive actions, and truth-label compliance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-001 — API Design, Versioning, and Error Semantics

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Every endpoint shall document authentication, authorization, request/response schema, idempotency, side effects, events, errors, limits, and examples.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-002 — API Design, Versioning, and Error Semantics

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Mutation requests shall include an idempotency key or be demonstrably naturally idempotent.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-003 — API Design, Versioning, and Error Semantics

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Conditional updates shall use version/ETag semantics and reject lost updates.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-004 — API Design, Versioning, and Error Semantics

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Pagination shall use opaque stable cursors and deterministic ordering.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-005 — API Design, Versioning, and Error Semantics

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Error responses shall include stable code, message, trace/correlation ID, retryability, and field details when safe.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTAPI-006 — API Design, Versioning, and Error Semantics

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/600_api_guidelines.md`](../60-platform/600_api_guidelines.md)
- **Requirement:** Breaking API changes shall use a new major version and migration period.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-001 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** Comments and tasks shall retain author, time, scope, referenced commit, anchor, edit history, and visibility.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-002 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** Review decisions shall include accepted/rejected/needs-information outcomes, rationale, evidence, and approver authority.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-003 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** Notification preferences shall support channel, urgency, digest, quiet hours, and sensitive-content suppression.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-004 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** Email/SMS/push payloads shall not include intimate memories or security-system details by default.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-005 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** A permission revocation shall prevent access through historical notification links.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTCOLLA-006 — Collaboration, Review, Tasks, and Notifications

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/612_notifications_collaboration.md`](../60-platform/612_notifications_collaboration.md)
- **Requirement:** Escalations shall be configurable and auditable without impersonating the responsible person.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-001 — Desktop Expert Review Application

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** The reviewer shall inspect synchronized frame/depth/trajectory/geometry and allow correspondence creation with undo and provenance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-002 — Desktop Expert Review Application

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** The reviewer shall visualize factor residuals, loop constraints, source weights, and region uncertainty.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-003 — Desktop Expert Review Application

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** Offline changes shall preserve local identity, author, base commit, and conflict information.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-004 — Desktop Expert Review Application

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** The application shall not require cloud login for authorized local-only projects.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-005 — Desktop Expert Review Application

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** GPU crashes shall not corrupt local project bundles.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTDESK-006 — Desktop Expert Review Application

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/606_desktop_review.md`](../60-platform/606_desktop_review.md)
- **Requirement:** Exports and publication shall still pass policy and license gates.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-001 — Domain Event Catalog

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** The catalog shall cover project, capture, asset, pipeline, quality, scene, entity, evidence, review, consent, export, deletion, security, and billing-attribution domains.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-002 — Domain Event Catalog

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** Each event shall define producer, consumers, partition/ordering key, retry policy, retention, personal-data classification, and example.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-003 — Domain Event Catalog

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** Consumers shall persist processed event IDs or use an equivalent idempotency mechanism.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-004 — Domain Event Catalog

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** Schema registry validation shall run in CI and at publication boundaries.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-005 — Domain Event Catalog

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** An event shall never assert success before its authoritative transaction commits.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTEVENT-006 — Domain Event Catalog

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/603_event_catalog.md`](../60-platform/603_event_catalog.md)
- **Requirement:** Replay tools shall support dry run, bounded ranges, tenant scope, and audit.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-001 — Internal Worker and Streaming Contracts

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** A job lease shall include job/run ID, adapter/profile, input manifest, output staging scope, resource limits, deadline, cancellation token, and workload identity.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-002 — Internal Worker and Streaming Contracts

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** Workers shall report startup, download, decode, stage progress, warnings, quality, checkpoints, resource use, and terminal result.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-003 — Internal Worker and Streaming Contracts

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** Heartbeat expiry shall release or quarantine the lease according to checkpoint safety.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-004 — Internal Worker and Streaming Contracts

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** The control plane shall verify output hashes and manifest before accepting completion.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-005 — Internal Worker and Streaming Contracts

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** Protocol mismatches shall fail before expensive work and never fall back to untyped execution.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTGRPC-006 — Internal Worker and Streaming Contracts

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/602_grpc_worker_api.md`](../60-platform/602_grpc_worker_api.md)
- **Requirement:** Workers shall support graceful cancellation at declared safe points.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-001 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** An import shall report accepted, transformed, skipped, duplicate, conflicting, unsupported, and quarantined items.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-002 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** An export shall include source commit, query/scope, permissions/consent decision, redactions, transformations, output hashes, and limitations.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-003 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Full-project export shall include originals when authorized, canonical manifests, scene graph, history, evidence, open-format geometry/media, and checksums.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-004 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** The system shall support dry-run migration and deterministic re-execution.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-005 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Password-protected or encrypted input shall never be weakened or logged without explicit authorized handling.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-006 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Portability verification shall run on a clean offline viewer/reference importer.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-007 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Hybrid export shall preserve role, authority, transform, derivation, use suitability, limitations, support maps, and policy labels.
- **Minimum verification:** Independent import test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-008 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** External/manual provider export shall be minimized, purpose-limited, hashed, expiring, and receipted.
- **Minimum verification:** Security workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-009 — Import, Export, Packaging, and Migration

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Import shall quarantine unknown providers, roles, extensions, transforms, and authority claims.
- **Minimum verification:** Adversarial import test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-010 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Full-project export shall include visual, metric, interaction, design, evidence, and non-splat fallback assets when authorized.
- **Minimum verification:** Portability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-011 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** Format conversion shall retain irreversible-loss declarations and source relationships.
- **Minimum verification:** Round-trip test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTIO-012 — Import, Export, Packaging, and Migration

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/611_import_export.md`](../60-platform/611_import_export.md)
- **Requirement:** A clean reference importer shall reconstruct the hybrid layer registry without vendor-specific private knowledge.
- **Minimum verification:** Independent verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-001 — Pipeline Job Orchestration and Review Gates

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** A workflow shall persist state, attempts, checkpoints, input/output manifests, costs, warnings, and cancellation.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-002 — Pipeline Job Orchestration and Review Gates

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** Activity retries shall not duplicate published assets or charges.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-003 — Pipeline Job Orchestration and Review Gates

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** Quality and license gates shall execute before publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-004 — Pipeline Job Orchestration and Review Gates

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** Manual-review tasks shall include scope, evidence, requested decision, possible outcomes, and impact.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-005 — Pipeline Job Orchestration and Review Gates

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** Workflow upgrades shall preserve running jobs or migrate them explicitly.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTJOB-006 — Pipeline Job Orchestration and Review Gates

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/604_job_orchestration.md`](../60-platform/604_job_orchestration.md)
- **Requirement:** Operators shall be able to pause queues or disable a model/profile without editing customer data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-001 — Model Registry and Deployment Control

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** A model version shall include architecture/source, checkpoint hash, tokenizer/preprocessor, license, data terms, container, hardware compatibility, benchmark results, limitations, and approvers.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-002 — Model Registry and Deployment Control

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** Production workers shall verify registry state and checkpoint hash at job start.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-003 — Model Registry and Deployment Control

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** Shadow/canary runs shall compare quality, cost, latency, safety, and failure modes before promotion.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-004 — Model Registry and Deployment Control

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** Rollback shall be one control-plane operation and preserve runs generated by the revoked model for audit/rebuild analysis.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-005 — Model Registry and Deployment Control

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** Monitoring shall segment quality and incident metrics by model version.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTMODEL-006 — Model Registry and Deployment Control

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/609_model_registry.md`](../60-platform/609_model_registry.md)
- **Requirement:** Auxiliary models such as sky masks, segmentation, OCR, embeddings, and voice models shall follow the same registry rules.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-001 — REST Resource API

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** The API shall provide create/read/list/update operations for projects, places, captures, entities, assertions, evidence, tasks, and consent where policy permits.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-002 — REST Resource API

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** The API shall provide operations for finalize capture, start pipeline, cancel job, publish scene commit, compare commits, request review, export, redact, and delete.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-003 — REST Resource API

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** Search shall accept structured spatial/temporal/source filters and return explanation/provenance summaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-004 — REST Resource API

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** Asset URLs shall be short-lived, scoped to exact object/action, and audited for sensitive classes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-005 — REST Resource API

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** The API shall expose operation progress, warnings, outputs, quality, cost attribution, and terminal errors.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTREST-006 — REST Resource API

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/601_rest_api.md`](../60-platform/601_rest_api.md)
- **Requirement:** Bulk endpoints shall be bounded, transactional where promised, and return per-item outcomes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-001 — Adapter and Plugin SDK

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** The SDK shall define contracts for source adapters, pipeline stages, quality metrics, entity extractors, exporters, viewer layers, and report generators.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-002 — Adapter and Plugin SDK

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** Plugin installation shall require signature verification, dependency scan, requested capabilities, and administrator approval.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-003 — Adapter and Plugin SDK

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** Runtime shall enforce CPU/GPU/memory/time/network/filesystem limits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-004 — Adapter and Plugin SDK

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** Plugin outputs shall pass schema, provenance, quality, and authorization validation before publication.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-005 — Adapter and Plugin SDK

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** A plugin failure shall not corrupt the parent workflow or leak another tenant's data.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSDK-006 — Adapter and Plugin SDK

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/610_plugin_sdk.md`](../60-platform/610_plugin_sdk.md)
- **Requirement:** Compatibility tests shall run against supported contract versions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-001 — Spatial Query Language and Saved Views

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** The language shall support `within`, `intersects`, `near`, `visible_from`, `on_level`, `changed_between`, temporal intervals, graph traversal, source/authority, and evidence filters.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-002 — Spatial Query Language and Saved Views

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** Query execution shall enforce complexity, result, time, and spatial-volume limits.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-003 — Spatial Query Language and Saved Views

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** Saved queries shall record schema version, author, permissions, parameters, and expected result contract.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-004 — Spatial Query Language and Saved Views

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** Natural-language translation shall not broaden scope beyond the user's authorization or stated intent.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-005 — Spatial Query Language and Saved Views

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** Reports shall record the exact query and scene commit used.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTSQL-006 — Spatial Query Language and Saved Views

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/607_spatial_query_language.md`](../60-platform/607_spatial_query_language.md)
- **Requirement:** Query explanations shall show filters and ranking factors in user-understandable form.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-001 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** The viewer shall support orbit, walk/fly, saved views, floor/room navigation, clipping, section boxes, entity selection, timeline, and synchronized comparison.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-002 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Rendering shall stream bounded LOD/tile assets and maintain interactive frame budgets on supported devices.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-003 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Selecting an entity shall show authority/source class, properties, history, evidence, tasks, permissions, and related documents when authorized.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-004 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** The viewer shall display generated/inferred/reconstructed labels persistently and offer evidence view.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-005 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Keyboard navigation, screen-reader metadata panels, captions/transcripts, reduced motion, and high-contrast controls shall be supported.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-006 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Viewer sessions used for audit or reports shall be reproducible from saved camera, layers, commit, filters, and redaction state.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-007 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Hybrid rendering shall keep visual, metric, interaction, design, and evidence roles independently selectable and labeled.
- **Minimum verification:** Viewer integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-008 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Proxy picking shall resolve to stable semantic entities and shall not expose primitive IDs as business identity.
- **Minimum verification:** Remesh test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-009 — Web Spatial Viewer and Evidence Interface

- **Priority:** P0
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** A measurement started on a proxy shall invoke metric re-resolution and display the resulting authority/verification class.
- **Minimum verification:** End-to-end test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-010 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Collision, navigation, occlusion, clipping, and spatial-audio sources shall be independently diagnosable.
- **Minimum verification:** UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-011 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** Performance degradation shall preserve permissions, truth labels, safe navigation, and evidence access before optional visual quality.
- **Minimum verification:** Device-tier test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### PLTVIEW-012 — Web Spatial Viewer and Evidence Interface

- **Priority:** P1
- **Category:** platform
- **Source:** [`60-platform/605_web_viewer.md`](../60-platform/605_web_viewer.md)
- **Requirement:** The viewer shall provide a non-splat fallback without changing semantic identity or evidence links.
- **Minimum verification:** Compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-001 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** The alignment solver shall support SE(3) and Sim(3) and state which was used.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-002 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** At least three non-collinear constraints or an equivalent trajectory/geometry basis shall be required for free 3D similarity alignment.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-003 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** Robust estimation shall reject outliers and report inlier count, distribution, and residual statistics.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-004 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** Transform direction, source frame, target frame, units, handedness, and axis convention shall be machine-readable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-005 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** Alignment acceptance thresholds shall depend on capture profile and intended use.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECALIGN-006 — Pose Alignment, Scale, and Coordinate Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/402_pose_alignment_scale.md`](../40-reconstruction/402_pose_alignment_scale.md)
- **Requirement:** A transform revision shall not mutate prior observation coordinates; it creates a new solution graph.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-001 — Geometry and Reconstruction Benchmark Program

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** The benchmark suite shall include trajectory ground truth, known dimensions, high-quality reference scans, semantic inventory, and change events where applicable.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-002 — Geometry and Reconstruction Benchmark Program

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** Every result shall record source code, model/checkpoint hash, environment, hardware, parameters, and input hashes.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-003 — Geometry and Reconstruction Benchmark Program

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** Metrics shall include ATE/RPE, point-to-surface distance, completeness, normal error, scale drift, loop residual, change precision/recall, runtime, peak memory, and cost.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-004 — Geometry and Reconstruction Benchmark Program

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** Regressions beyond declared tolerances shall block release or require an explicit scoped waiver.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-005 — Geometry and Reconstruction Benchmark Program

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** Benchmark datasets with people or homes shall document consent, access, retention, and publication restrictions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBENCH-006 — Geometry and Reconstruction Benchmark Program

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/412_benchmarking.md`](../40-reconstruction/412_benchmarking.md)
- **Requirement:** Results shall be stratified by scene type and not averaged into a misleading single number.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-001 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Mesh-splat and splat-surface conversions shall create new content-addressed derivatives and shall preserve every canonical source asset.
- **Minimum verification:** Asset-lineage test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-002 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** A conversion shall never assign an authority class higher than the source evidence permits.
- **Minimum verification:** Authority-policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-003 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Every conversion shall record exact provider, version, model, parameters, environment, source/output hashes, coordinate transforms, and declared information losses.
- **Minimum verification:** Provenance-schema test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-004 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Native hybrid composition shall be preferred when it meets the declared client and experience requirements without destructive conversion.
- **Minimum verification:** Architecture review and scenario test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-005 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Stable semantic entity identity shall remain in the scene graph and shall survive remeshing, decimation, retraining, and tiling.
- **Minimum verification:** Anchor-remapping regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-006 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** A visual derivative of design or generated content shall retain an inseparable design or generated truth label in all publishable manifests.
- **Minimum verification:** Viewer and export test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-007 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** A conversion shall not modify an accepted metric asset to improve visual alignment without creating and reviewing a separate derivative.
- **Minimum verification:** Immutability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-008 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** The platform shall support round-trip comparison that reports bounded intended-use metrics and irreversible information loss.
- **Minimum verification:** Benchmark test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-009 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Conversion packages shall include open or documented target formats, transforms, support maps, limitations, validation, and redistribution notes.
- **Minimum verification:** Export/import conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-010 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Spatial Git shall version conversion choices and semantic state without attempting binary line merges of meshes or splats.
- **Minimum verification:** Revision and merge test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-011 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Design-to-observed alignment shall record coordinate source, control correspondences, residuals, approver, and validity interval.
- **Minimum verification:** Alignment audit test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-012 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Client fallback behavior shall not discard or conceal authority and truth labels when a preferred representation is unsupported.
- **Minimum verification:** Cross-client test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-013 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** Provider-specific identifiers shall be normalized behind canonical asset, frame, and semantic-support contracts.
- **Minimum verification:** Adapter conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECBIDI-014 — Bidirectional Mesh-Splat Interoperability

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/417_bidirectional_mesh_splat_interop.md`](../40-reconstruction/417_bidirectional_mesh_splat_interop.md)
- **Requirement:** A target asset shall inherit applicable consent, privacy, retention, legal-hold, export, and deletion dependencies from all sources.
- **Minimum verification:** Policy-propagation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-001 — Temporal Change Detection and Semantic Diff

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** Every change result shall identify compared commits, comparable region, registration quality, thresholds, evidence frames, and algorithm version.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-002 — Temporal Change Detection and Semantic Diff

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** The detector shall suppress differences caused by LOD, lighting, exposure, dynamic objects, and missing coverage where possible.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-003 — Temporal Change Detection and Semantic Diff

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** Unobserved regions shall not be reported as removed.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-004 — Temporal Change Detection and Semantic Diff

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** A reviewer shall be able to inspect synchronized views and source evidence before accepting a change.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-005 — Temporal Change Detection and Semantic Diff

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** Accepted changes shall create semantic events and may update entity revisions through a controlled commit.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCHANG-006 — Temporal Change Detection and Semantic Diff

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/410_change_detection.md`](../40-reconstruction/410_change_detection.md)
- **Requirement:** Benchmarks shall report precision, recall, localization error, and false-action rate by change class.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-001 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Cleanup shall create derivatives and shall never overwrite canonical captures, splats, metric geometry, or design models.
- **Minimum verification:** Immutability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-002 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Every automated cleanup output shall record exact inputs, tool/container digest, parameters, seed, output hashes, and validation.
- **Minimum verification:** Reproducibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-003 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Manual edits shall use a replayable journal or be classified as non-reproducible authored derivatives with complete receipts.
- **Minimum verification:** Workflow audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-004 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Hole filling and bridge creation shall be governed by declared purpose and shall not conceal openings relevant to construction or evidence.
- **Minimum verification:** Geometry and review test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-005 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Protected semantic and privacy regions shall be honored by automated removal, decimation, and fill operations.
- **Minimum verification:** Adversarial cleanup test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-006 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Generated collision, navigation, display, and occlusion products shall remain separate assets with separate quality gates.
- **Minimum verification:** Asset contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-007 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** A cleaned or decimated derivative shall retain source lineage, coordinate-frame identity, authority, and limitations.
- **Minimum verification:** Lineage test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-008 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** The system shall support connected-component filtering, spatial cropping, invalid-value removal, decimation, reordering, tiling, and LOD generation through provider capabilities.
- **Minimum verification:** Capability test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-009 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Large scenes shall be partitioned deterministically and shall record overlap, seams, recomposition order, and tile hashes.
- **Minimum verification:** Building-scale test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-010 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** LOD switching shall preserve stable semantic anchors or create an explicit reattachment review task.
- **Minimum verification:** Anchor regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-011 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Review tooling shall expose removed, filled, repaired, redacted, and manually authored regions.
- **Minimum verification:** Reviewer UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-012 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Privacy presentation derivatives shall not be treated as fulfillment of source deletion, retention, or legal-hold obligations.
- **Minimum verification:** Privacy workflow test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-013 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** The system shall classify reproducibility as deterministic, bounded-equivalent, or manual/non-reproducible and expose the classification.
- **Minimum verification:** Provenance UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECCLEAN-014 — Splat and Surface Editing, Cleanup, and Derived LODs

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/418_splat_editing_cleanup.md`](../40-reconstruction/418_splat_editing_cleanup.md)
- **Requirement:** Cleanup acceptance thresholds shall be profile- and purpose-specific and shall be regression tested against protected features.
- **Minimum verification:** Benchmark policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-001 — Depth Observation Normalization and Fusion

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** Each depth map shall declare encoding, units/scale, camera model, intrinsics, pose, timestamp, valid mask, confidence model, and source manifest.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-002 — Depth Observation Normalization and Fusion

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** Unprojection shall be tested with synthetic cameras and known planes for every supported source convention.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-003 — Depth Observation Normalization and Fusion

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** Weights shall account for range, confidence, viewing angle, motion, temporal agreement, calibration, and source class.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-004 — Depth Observation Normalization and Fusion

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** The pipeline shall retain source-contribution statistics per voxel/surface region.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-005 — Depth Observation Normalization and Fusion

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** Depth discontinuities shall not be blurred across semantic or edge boundaries without explicit algorithm behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDEPTH-006 — Depth Observation Normalization and Fusion

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/404_depth_fusion.md`](../40-reconstruction/404_depth_fusion.md)
- **Requirement:** Fusion shall be repeatable from immutable normalized observations and a versioned policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-001 — Dynamic People, Objects, and Scene Layers

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** The pipeline shall preserve original frames before masking.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-002 — Dynamic People, Objects, and Scene Layers

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** Dynamic detections shall include model manifest, class, track, mask, confidence, and review state.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-003 — Dynamic People, Objects, and Scene Layers

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** Static fusion shall exclude accepted dynamic pixels and report excluded coverage.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-004 — Dynamic People, Objects, and Scene Layers

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** The system shall distinguish unknown motion from sensor/pose error.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-005 — Dynamic People, Objects, and Scene Layers

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** A person identity shall not be inferred or published solely from spatial track continuity.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECDYN-006 — Dynamic People, Objects, and Scene Layers

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/408_dynamic_objects.md`](../40-reconstruction/408_dynamic_objects.md)
- **Requirement:** Construction change detection shall not report ordinary temporary workers or equipment as structural changes by default.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-001 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** Each compute profile shall pin resolution, dtype, backend, model, window policy, memory limit, timeout, output class, and expected quality tier.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-002 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** The scheduler shall prevent incompatible CUDA/driver/container combinations.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-003 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** GPU workers shall run one tenant security context per isolated job or approved batch boundary.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-004 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** OOM fallback shall be explicit and recorded; silent parameter reduction is prohibited.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-005 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** Cost estimation shall include decode, inference, optimization, fusion, splat, semantic processing, storage, and egress.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGPU-006 — GPU Compute Profiles and Resource Scheduling

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/413_gpu_compute_profiles.md`](../40-reconstruction/413_gpu_compute_profiles.md)
- **Requirement:** Preempted jobs shall resume from verified checkpoints when supported.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-001 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** The graph shall represent pose nodes, optional landmarks/planes, priors, relative-pose factors, loop factors, gravity, scale, control, and cross-session constraints.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-002 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** Each factor shall identify source, covariance or weight rationale, timestamp/frame association, and evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-003 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** The optimizer shall report convergence, cost history, residual distributions by factor type, rejected/suppressed factors, and gauge fixing.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-004 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** Large changes from a prior accepted solution shall trigger review rather than automatic publication.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-005 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** Loop detection shall enforce temporal/spatial separation and geometric verification after descriptor retrieval.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECGRAPH-006 — Factor Graph, Loop Closure, and Global Optimization

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/403_factor_graph_loop_closure.md`](../40-reconstruction/403_factor_graph_loop_closure.md)
- **Requirement:** Incremental and batch optimization results shall be comparable on fixed regression scenes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-001 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** SIP shall store metric, visual, interaction, design, and evidence roles independently while registering them to explicit coordinate frames.
- **Minimum verification:** Schema and integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-002 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Every interaction proxy shall carry authority class `derived_non_authoritative` and shall be ineligible for verified measurement by itself.
- **Minimum verification:** Policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-003 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** A splat-to-surface operation shall preserve immutable source hashes, provider identity, exact version, parameters, environment, output hashes, validation, and publication decision.
- **Minimum verification:** Provenance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-004 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** The system shall validate transform, scale, coverage, topology, collision behavior, and intended-use suitability before proxy publication.
- **Minimum verification:** Benchmark gate
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-005 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Construction measurements initiated from a proxy shall resolve to eligible metric evidence or remain explicitly approximate and unverified.
- **Minimum verification:** End-to-end test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-006 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Sensitive scenes shall not leave an approved trust boundary through a manual or hosted provider without a matching policy approval.
- **Minimum verification:** Security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-007 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Semantic anchors shall not depend solely on provider-local triangle indices that may change after remeshing or decimation.
- **Minimum verification:** Remesh regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-008 — Splat-to-Surface and Hybrid Representation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Provider failure or rejection shall not modify the accepted metric scene, source splat, or prior published proxy.
- **Minimum verification:** Transaction and rollback test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-009 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** The pipeline shall support separate derivatives for display, collision, navigation, occlusion, and spatial audio when one mesh cannot satisfy all budgets.
- **Minimum verification:** Integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-010 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Building-scale scenes shall support tiled processing, overlap validation, seam checks, and independent partition regeneration.
- **Minimum verification:** Large-scene test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-011 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** The viewer shall provide an authorized diagnostic mode exposing layer roles, authority, provider, coverage, and limitations.
- **Minimum verification:** UI acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-012 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** The runtime shall provide component-level fallbacks when proxy picking, collision, navigation, or occlusion is unavailable.
- **Minimum verification:** Fault-injection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-013 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Surface quality gates shall be selected by intended use rather than a single global pass/fail score.
- **Minimum verification:** Policy and benchmark test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-014 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Manual cleanup shall be replayable or preserved as a separately versioned authored derivative with edit provenance.
- **Minimum verification:** Reproducibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-015 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** A visual splat shall remain independently viewable and exportable when surface extraction is disabled or unsuccessful.
- **Minimum verification:** Compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECHYB-016 — Splat-to-Surface and Hybrid Representation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/415_splat_surface_hybrid_representation.md`](../40-reconstruction/415_splat_surface_hybrid_representation.md)
- **Requirement:** Every published proxy shall retain a machine-readable limitations statement and support-map reference.
- **Minimum verification:** Schema test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-001 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** The scheduler shall select fixed-cache, keyframe, or windowed execution from a versioned policy based on frame count, scene length, motion, and hardware.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-002 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** The pipeline shall detect cache/window discontinuities through shared-frame residuals and geometry overlap.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-003 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** The validator shall compare learned trajectory to ARKit, IMU gravity, controls, and physical speed/acceleration bounds when available.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-004 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** A run shall be marked outside operating envelope when its input exceeds validated distance, resolution, device motion, dynamic occupancy, or scene category.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-005 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** Product UI shall not expose unsupported scenes as verified simply because a point cloud rendered successfully.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLIM-006 — LingBot-Map Operating Envelope and Guardrails

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/401_lingbot_limitations_guardrails.md`](../40-reconstruction/401_lingbot_limitations_guardrails.md)
- **Requirement:** Benchmarks shall include long repeated corridors, loops, stairs, elevators, glass, mirrors, low texture, outdoor sky, and moving people.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-001 — LingBot-Map Integration Adapter

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** Every run shall record source commit, container digest, Python/PyTorch/CUDA versions, attention backend, checkpoint hash, dtype, input resolution, frame selection, keyframe interval, mode, window size, overlap, camera iterations, masking models, and random seeds where relevant.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-002 — LingBot-Map Integration Adapter

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** The adapter shall normalize output transform direction and coordinate convention before exposing results downstream.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-003 — LingBot-Map Integration Adapter

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** The adapter shall persist per-frame output, confidence, frame mapping, window membership, scale phase, warnings, and timing.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-004 — LingBot-Map Integration Adapter

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** The adapter shall reject implicit network downloads in production; checkpoints and auxiliary models must be pre-approved and content-addressed.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-005 — LingBot-Map Integration Adapter

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** The adapter shall support cancellation and resume at completed window boundaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECLING-006 — LingBot-Map Integration Adapter

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/400_lingbot_integration.md`](../40-reconstruction/400_lingbot_integration.md)
- **Requirement:** An upstream upgrade shall run fixed regression scenes and compare trajectory, depth, completeness, runtime, memory, and failure behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-001 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Every mesh shall declare source volume/point set, coordinate frame, units, topology metrics, processing operations, and hash.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-002 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Decimation shall be evaluated for surface error and preservation of protected semantic edges and anchor regions.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-003 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Texturing shall avoid using redacted or unauthorized frames for broader-access derivatives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-004 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Viewer LOD switches shall not change measurement results, which are computed from approved metric geometry.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-005 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Tiling shall preserve stable global coordinates and entity-to-tile mappings.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-006 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Exports shall include provenance sidecars when the target format cannot carry SIP metadata.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-007 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Metric, visual, interaction, collision, navigation, occlusion, and preservation meshes shall use distinct roles and authority ceilings.
- **Minimum verification:** Schema/policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-008 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** A render mesh shall not be approved for collision or navigation without separate profile-specific validation.
- **Minimum verification:** Acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-009 — Meshing, Texturing, and Level of Detail

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Repair, decimation, and LOD shall test protected construction, memory, safety, and privacy regions.
- **Minimum verification:** Benchmark test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-010 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Every remesh shall generate support-map results and identify unresolved semantic anchors.
- **Minimum verification:** Remesh regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-011 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Collision/navigation derivatives shall be replaceable without replacing the visual or metric source.
- **Minimum verification:** Component test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECMESH-012 — Meshing, Texturing, and Level of Detail

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/406_meshing_texturing_lod.md`](../40-reconstruction/406_meshing_texturing_lod.md)
- **Requirement:** Mesh exports shall include role, authority, intended-use, limitations, transform, and derivation sidecars.
- **Minimum verification:** Export/import test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-001 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Every provider shall register a signed capability, execution, coordinate, security, license, and benchmark descriptor before source-data access.
- **Minimum verification:** Registry schema and admission test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-002 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Orchestration shall select providers by approved capabilities and policy envelope rather than by hard-coded product name.
- **Minimum verification:** Policy-selection test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-003 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** The immutable operation request shall identify source hashes, roles, coordinate frames, intended uses, constraints, classification, and idempotency key.
- **Minimum verification:** Contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-004 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** License, model, data-rights, consent, and transfer gates shall execute before provider access to decrypted source bytes.
- **Minimum verification:** Security and policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-005 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Provider-native validation shall not publish an output without independent SIP registration and intended-use validation.
- **Minimum verification:** End-to-end publication test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-006 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** A provider shall not infer or discard scale, units, handedness, coordinate transforms, or authority class without an explicit machine-readable record.
- **Minimum verification:** Coordinate conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-007 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Publication shall be atomic and separate from execution so retries and worker failures cannot create competing accepted outputs.
- **Minimum verification:** Fault-injection and transaction test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-008 — Splat-Surface Provider Contract

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Manual external conversion shall use controlled export, return receipt, hash verification, policy review, and independent validation.
- **Minimum verification:** Manual-provider procedure test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-009 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Providers shall expose bounded cancellation, checkpoint, cleanup, and recovery behavior in the capability descriptor.
- **Minimum verification:** Recovery conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-010 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Progress shall report objective stage work units and last durable checkpoint rather than an unsupported global percentage.
- **Minimum verification:** Event-contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-011 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Provider promotion shall be scoped independently by data classification, scene class, output role, and intended use.
- **Minimum verification:** Promotion-policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-012 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Deprecated provider versions shall remain addressable for reproducibility but shall receive no new production work.
- **Minimum verification:** Registry lifecycle test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-013 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Every candidate result shall include exact input, parameter, environment, provider, model, output, metric, limitation, and receipt records.
- **Minimum verification:** Provenance completeness test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-014 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Error responses shall use stable machine-readable codes and shall not leak restricted policy or scene information.
- **Minimum verification:** API and security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-015 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** Resource and cost admission shall occur before execution and enforce tenant and project quotas throughout the job.
- **Minimum verification:** Capacity and cost test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECPROV-016 — Splat-Surface Provider Contract

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/416_splat_surface_provider_contract.md`](../40-reconstruction/416_splat_surface_provider_contract.md)
- **Requirement:** A provider upgrade shall enter shadow benchmarking and shall not replace an active version solely because it is newer.
- **Minimum verification:** Upgrade-promotion test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-001 — Pipeline Reproducibility and Run Manifests

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** The run manifest shall include inputs, software commits, images, packages, container digest, hardware, driver/runtime, model manifests, parameters, seeds, locale/timezone, outputs, logs, metrics, and validation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-002 — Pipeline Reproducibility and Run Manifests

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** The platform shall verify every referenced hash before executing a reproducibility claim.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-003 — Pipeline Reproducibility and Run Manifests

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** A comparison report shall classify identical, within tolerance, materially different, and incomparable outputs.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-004 — Pipeline Reproducibility and Run Manifests

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** Non-deterministic algorithms shall document expected variance and benchmark it.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-005 — Pipeline Reproducibility and Run Manifests

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** Expired or revoked dependencies shall not prevent reading old manifests, but may prevent execution until isolated approval.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECREPRO-006 — Pipeline Reproducibility and Run Manifests

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/414_pipeline_reproducibility.md`](../40-reconstruction/414_pipeline_reproducibility.md)
- **Requirement:** Release acceptance shall reproduce representative runs in a clean environment.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-001 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** A splat run shall record engine commit/package, license approval, input images, masks, pose solution, calibration, training parameters, seed, hardware, checkpoints, and output hash.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-002 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** The pipeline shall support excluding sensitive frames and regions before training.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-003 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** The viewer shall display a visual-reconstruction label and provide an evidence/geometry toggle.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-004 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Splat quality tests shall include held-out views, floaters, temporal artifacts, thin structures, and browser/device performance.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-005 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Generated inpainting or relighting shall be separate transformations with persistent labels.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-006 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Export shall use approved open or documented formats and retain a fallback rendered archive for preservation.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-007 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** A surface extracted from a splat shall be a separately versioned derivative with non-authoritative default authority.
- **Minimum verification:** Lineage/policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-008 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Splat processing shall retain generation, redaction, consent, classification, and source-policy dependencies.
- **Minimum verification:** Policy propagation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-009 — Gaussian Splat Visual Reconstruction

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Unapproved hosted/manual tools shall be denied sensitive scene assets before export.
- **Minimum verification:** Security test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-010 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Native hybrid splat-plus-mesh rendering shall remain a supported path when extraction is unnecessary or rejected.
- **Minimum verification:** Viewer compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-011 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** Splat LOD or format conversion shall preserve coordinate alignment and semantic support within declared tolerances.
- **Minimum verification:** Interop test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECSPLAT-012 — Gaussian Splat Visual Reconstruction

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/407_gaussian_splats.md`](../40-reconstruction/407_gaussian_splats.md)
- **Requirement:** The preservation package shall include a documented non-splat fallback when long-term renderer support is uncertain.
- **Minimum verification:** Preservation test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-001 — Volumetric Integration and Metric Surface Generation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** The volume manifest shall record bounds, voxel/truncation parameters, coordinate frame, accepted observation set, weighting policy, and implementation version.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-002 — Volumetric Integration and Metric Surface Generation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** Spatial chunks shall have stable keys and boundary-overlap rules to avoid visible seams.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-003 — Volumetric Integration and Metric Surface Generation

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** Incremental fusion shall produce the same result within tolerance as full rebuild for the same accepted inputs and deterministic mode.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-004 — Volumetric Integration and Metric Surface Generation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** The system shall support invalidating contributions from a revoked, miscalibrated, or unlicensed source and rebuilding affected chunks.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-005 — Volumetric Integration and Metric Surface Generation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** Mesh extraction shall report watertightness, non-manifold elements, holes, component sizes, and repair operations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECTSDF-006 — Volumetric Integration and Metric Surface Generation

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/405_tsdf_voxel_fusion.md`](../40-reconstruction/405_tsdf_voxel_fusion.md)
- **Requirement:** No hole-filling operation shall be represented as directly observed geometry.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-001 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** A scene revision shall carry trajectory, alignment, coverage, surface, source-contribution, semantic, and provenance quality summaries.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-002 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** Quality metrics shall define units, calculation, calibration, thresholds, and known blind spots.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-003 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** A downstream workflow shall declare the minimum acceptance state it consumes.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-004 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** The UI shall reveal region-level uncertainty and source coverage rather than only a project-level badge.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-005 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** Human review shall record reviewer, evidence examined, decision, scope, and limitations.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECUNC-006 — Quality, Uncertainty, and Acceptance Classification

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/411_quality_uncertainty.md`](../40-reconstruction/411_quality_uncertainty.md)
- **Requirement:** Verification shall never be inferred from elapsed time, customer payment, or absence of complaints.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-001 — Cross-Session Relocalization and Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** The system shall generate candidate place matches using approved descriptors or manual selection and verify them geometrically.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-002 — Cross-Session Relocalization and Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** Cross-session transforms shall report overlap, inliers, residuals, scale, uncertainty, and changed-region masks.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-003 — Cross-Session Relocalization and Registration

- **Priority:** P0
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** The optimizer shall avoid using known changed objects as rigid constraints.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-004 — Cross-Session Relocalization and Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** Manual correspondence tools shall support points, planes, lines, semantic objects, and image-to-scene anchors.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-005 — Cross-Session Relocalization and Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** Registration failures shall leave sessions independently viewable and reviewable.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### RECXREG-006 — Cross-Session Relocalization and Registration

- **Priority:** P1
- **Category:** reconstruction
- **Source:** [`40-reconstruction/409_cross_session_registration.md`](../40-reconstruction/409_cross_session_registration.md)
- **Requirement:** A global-place revision shall preserve every contributing session and transform solution.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-001 — Repository Blueprint

- **Priority:** P0
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** Provider registry, provider worker, quarantine/quality, publisher, and hybrid runtime shall be separate least-privilege boundaries.
- **Minimum verification:** Architecture test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-002 — Repository Blueprint

- **Priority:** P0
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** Provider-specific code and fields shall remain inside adapters/SDK extensions and shall not leak into domain schemas.
- **Minimum verification:** Dependency and contract test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-003 — Repository Blueprint

- **Priority:** P0
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** The representation publisher shall be the only component permitted to attach accepted derived assets to scene commits.
- **Minimum verification:** Authorization test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-004 — Repository Blueprint

- **Priority:** P1
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** Local, research-shadow, private managed, and manual fixture providers shall conform to the same core contract suite.
- **Minimum verification:** Adapter conformance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-005 — Repository Blueprint

- **Priority:** P1
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** Benchmark fixtures and reports shall be versioned independently from production customer data.
- **Minimum verification:** Repository/CI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### REPOHYB-006 — Repository Blueprint

- **Priority:** P1
- **Category:** architecture
- **Source:** [`REPOSITORY_BLUEPRINT.md`](../REPOSITORY_BLUEPRINT.md)
- **Requirement:** Third-party provider source, patches, licenses, models, build images, and approvals shall be locked in the third-party manifest.
- **Minimum verification:** Supply-chain test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-001 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** An external or unknown provider shall not access source or derived scene bytes before an approved provider dossier and matching data/purpose policy exist.
- **Minimum verification:** Egress and admission test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-002 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Unknown data processing, retention, training, region, license, or security facts shall default to no production data access.
- **Minimum verification:** Governance policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-003 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Data classification shall account for geometry, layout, inference, relationships, and security context even when textures or obvious identifiers are removed.
- **Minimum verification:** Classification review test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-004 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Manual external use shall follow controlled minimization, export, custody, receipt, import validation, independent review, and deletion/cleanup recording.
- **Minimum verification:** Procedure and audit test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-005 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Private residential, restricted building-system, critical-infrastructure, biometric, intimate, and LiveForever-sensitive data shall be blocked from public hosted providers unless a specific higher-order approval permits it.
- **Minimum verification:** Negative security tests
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-006 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Provider approval shall separately cover source code, weights, datasets, dependencies, commercial rights, deployment mode, and execution artifact hashes.
- **Minimum verification:** License/model gate test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-007 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Provider credentials and object access shall be short-lived, least-privilege, operation-scoped, and revoked at completion or incident.
- **Minimum verification:** IAM integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-008 — External Spatial Provider Security and Governance

- **Priority:** P0
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** A consented preservation or construction purpose shall not be expanded to provider training, public demonstration, or unrelated retention without separate authorization.
- **Minimum verification:** Consent-purpose test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-009 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Approved external execution shall use destination controls, egress monitoring, content hashes, signed receipts, quarantine, and return validation appropriate to the data class.
- **Minimum verification:** Security integration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-010 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** A provider version or material terms/control change shall enter review or shadow state and shall not inherit approval automatically.
- **Minimum verification:** Change-management test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-011 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Provider exceptions shall be scoped, approved, audited, automatically expiring, and unable to waive truth, consent, legal-hold, or authority rules.
- **Minimum verification:** Exception lifecycle test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-012 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Incidents shall identify and withdraw affected source, derivative, publication, cache, and export assets while preserving investigation evidence.
- **Minimum verification:** Incident exercise
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-013 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Local-only deployments shall deny network-required providers by default and expose the attempted egress in audit.
- **Minimum verification:** Local deployment test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-014 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** SplatEdit shall remain limited to synthetic, public, or explicitly public-cleared fixtures until its production-relevant processing and permission posture is approved.
- **Minimum verification:** Provider registry test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-015 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Output from an external provider shall be treated as untrusted content and parsed, scanned, registered, and validated in isolation.
- **Minimum verification:** Malformed asset test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SECEXT-016 — External Spatial Provider Security and Governance

- **Priority:** P1
- **Category:** operations
- **Source:** [`90-security-ops/913_external_spatial_provider_governance.md`](../90-security-ops/913_external_spatial_provider_governance.md)
- **Requirement:** Operational telemetry about provider use shall not contain raw geometry, media, transcripts, secrets, or unnecessary precise locations.
- **Minimum verification:** Logging privacy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-001 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Migration shall preserve every canonical v1.0 source asset and shall create additive v1.1 records rather than rewriting geometry bytes in place.
- **Minimum verification:** Hash and migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-002 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Role and authority assignment shall be based on provenance and verification evidence, never file extension or visual appearance.
- **Minimum verification:** Migration policy test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-003 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Ambiguous assets, frames, anchors, or measurements shall be quarantined or conservatively classified and shall not receive privileged intended uses.
- **Minimum verification:** Negative migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-004 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Existing permissions, classification, consent, retention, legal hold, and deletion dependencies shall remain equivalent or more restrictive after migration.
- **Minimum verification:** Policy-diff test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-005 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Legacy proxy-like or visual measurements shall remain approximate unless eligible metric/field evidence supports a higher status.
- **Minimum verification:** Measurement migration test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-006 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Entity identity and source evidence shall survive migration independently of mesh primitive IDs and renderer objects.
- **Minimum verification:** Anchor/entity regression test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-007 — Migration from SIP v1.0 to v1.1

- **Priority:** P0
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Rollback shall be demonstrated from a restorable v1.0 backup without loss or mutation of original assets.
- **Minimum verification:** Recovery exercise
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-008 — Migration from SIP v1.0 to v1.1

- **Priority:** P1
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Compatibility APIs shall translate read behavior conservatively and shall prevent v1.0 clients from bypassing v1.1 authority or publication rules.
- **Minimum verification:** API compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-009 — Migration from SIP v1.0 to v1.1

- **Priority:** P1
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Down-level exports shall report omitted or degraded v1.1 content and shall not relabel proxy/design/generated assets as metric or observed.
- **Minimum verification:** Export compatibility test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### SIPMIG-010 — Migration from SIP v1.0 to v1.1

- **Priority:** P1
- **Category:** governance
- **Source:** [`MIGRATION_FROM_1.0.md`](../MIGRATION_FROM_1.0.md)
- **Requirement:** Migration shall produce a signed report of asset mappings, quarantines, unresolved anchors, policy diffs, validation results, and rollback evidence.
- **Minimum verification:** Audit report review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-001 — Dataset and Benchmark Curation Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Each dataset shall document purpose, source, consent/rights, license, subjects/locations, sensitivities, allowed uses, retention, splits, ground truth, known bias, and hash manifest.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-002 — Dataset and Benchmark Curation Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Train/tune/test leakage shall be assessed for any model adapted by the team.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-003 — Dataset and Benchmark Curation Plan

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Ground truth shall state equipment/method, calibration, uncertainty, alignment, and processing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-004 — Dataset and Benchmark Curation Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Field pilots shall use data agreements that separate service delivery from model improvement.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-005 — Dataset and Benchmark Curation Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Public result publication shall respect location/security and personal privacy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTDATA-006 — Dataset and Benchmark Curation Plan

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/954_dataset_benchmark_plan.md`](../95-testing-delivery/954_dataset_benchmark_plan.md)
- **Requirement:** Dataset withdrawal shall identify affected models/results and trigger governance review.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-001 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Research release shall use authorized test data, explicit research labels, and no commercial/customer output from unapproved models.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-002 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Pilot release shall define operating envelope, customer consent, support plan, measurement limitations, and rollback/export.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-003 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Production release shall pass all P0 requirements, vulnerability/SBOM/license review, benchmark thresholds, consent/truth-label tests, backup restore, migration, load, and acceptance scenarios.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-004 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Enterprise release shall additionally pass tenant isolation, SSO/audit, retention/legal hold, DR, scale, and support controls.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-005 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Known limitations shall be included in release notes and UI where they affect use.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-006 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Rollback shall be rehearsed before production promotion.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-007 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** A surface provider shall not enter production without current legal, privacy, security, reproducibility, and stratified benchmark approval.
- **Minimum verification:** Release review
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-008 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Raycast, render, collision, navigation, occlusion, audio, and measurement suitability shall be gated independently.
- **Minimum verification:** Quality-profile test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-009 — Release Gates and Promotion Evidence

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Production promotion shall prove proxy authority restrictions in Construction and LiveForever end-to-end scenarios.
- **Minimum verification:** Acceptance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-010 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Release evidence shall include native-hybrid comparison, open export/import, non-splat fallback, provider replacement, and rollback.
- **Minimum verification:** Release evidence audit
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-011 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** Known proxy gaps and prohibited uses shall appear in machine-readable limitations and applicable UI/report surfaces.
- **Minimum verification:** Documentation/UI test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGATE-012 — Release Gates and Promotion Evidence

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/955_release_gates.md`](../95-testing-delivery/955_release_gates.md)
- **Requirement:** A provider/license/terms change shall trigger re-review before subsequent production execution.
- **Minimum verification:** Governance test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-001 — Sensor, Calibration, and Geometry Validation

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** Synthetic fixtures shall validate intrinsics, distortion, unprojection, transform convention, interpolation, and scale.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-002 — Sensor, Calibration, and Geometry Validation

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** Physical rigs/rooms shall include known dimensions, planes, corners, thin structures, reflective surfaces, repeated texture, stairs, and loops.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-003 — Sensor, Calibration, and Geometry Validation

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** Cross-device and cross-session tests shall measure transform repeatability and change-detection false positives.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-004 — Sensor, Calibration, and Geometry Validation

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** Measurements shall be compared against calibrated independent tools and reported by range/orientation/surface type.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-005 — Sensor, Calibration, and Geometry Validation

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** LingBot and other learned outputs shall be evaluated independently and in fusion.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTGEO-006 — Sensor, Calibration, and Geometry Validation

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/952_sensor_geometry_tests.md`](../95-testing-delivery/952_sensor_geometry_tests.md)
- **Requirement:** A passing visual render shall not substitute for numeric trajectory/surface tests.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-001 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** Coordinate math shall have property tests for identity, inverse, composition, units, and camera ray round trips.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-002 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** CSCP validators shall have malformed, adversarial, backward-compatible, and forward-unknown-field fixtures.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-003 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** API/event tests shall cover idempotency, retries, concurrency, authorization, pagination, and schema compatibility.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-004 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** Worker tests shall verify resource limits, cancellation, checkpoints, hash validation, and unapproved-model rejection.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-005 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** End-to-end tests shall cover capture ingest through scene publication, review, search, viewer metadata, export, and deletion request.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTLAY-006 — Unit, Contract, Integration, and End-to-End Tests

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/951_unit_integration_e2e.md`](../95-testing-delivery/951_unit_integration_e2e.md)
- **Requirement:** Golden updates shall include comparison reports and reviewer approval.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-001 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** Tests shall attempt unauthorized discovery through IDs, counts, search snippets, vectors, thumbnails, tiles, caches, logs, share links, signed URLs, exports, and agent tools.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-002 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** Consent restriction/revocation shall propagate to processing, viewer, search, agents, reports, notifications, exports, and future model training.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-003 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** File ingestion shall test malicious archives, media parsers, oversized dimensions, embedded scripts, and metadata injection.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-004 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** Agent tests shall cover destructive requests, role confusion, evidence fabrication, source-label removal, and speaking as an unconsented person.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-005 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** Deletion tests shall verify canonical, derivatives, indexes, caches, links, and backup expiry behavior.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSEC-006 — Security, Privacy, Consent, and Abuse Testing

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/953_security_privacy_tests.md`](../95-testing-delivery/953_security_privacy_tests.md)
- **Requirement:** Incident and support access controls shall be exercised through realistic scenarios.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-001 — Master Test Strategy

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** Every P0 requirement shall map to an automated test, controlled field procedure, review artifact, or continuously monitored control.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-002 — Master Test Strategy

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** Test evidence shall include input hashes, environment, version, output, result, thresholds, and reviewer when manual.
- **Minimum verification:** Automated test
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-003 — Master Test Strategy

- **Priority:** P0
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** The strategy shall cover unit, property, contract, integration, end-to-end, field, benchmark, load, resilience, security, privacy, accessibility, migration, backup, and acceptance testing.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-004 — Master Test Strategy

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** Failed critical tests shall block release unless an allowed waiver with compensating control exists.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-005 — Master Test Strategy

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** Test data shall be synthetic or consented and follow retention/access policy.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None

### TSTSTRAT-006 — Master Test Strategy

- **Priority:** P1
- **Category:** testing
- **Source:** [`95-testing-delivery/950_test_strategy.md`](../95-testing-delivery/950_test_strategy.md)
- **Requirement:** Flaky tests shall be quarantined only with owner and expiry and cannot represent sole P0 evidence.
- **Minimum verification:** Controlled verification
- **Required evidence:** test/field-procedure result, exact software/model/provider/configuration manifest, input fixture or capture reference, output hash, reviewer, timestamp, and release identifier.
- **Implementation status:** Not started
- **Waiver:** None
