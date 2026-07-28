---
spec_id: APP-DEC
title: "Initial Architecture Decision Log"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Initial Architecture Decision Log

| ADR | Status | Decision | Rationale | Revisit trigger |
|---|---|---|---|---|
| ADR-001 | Accepted | Use a Canonical Spatial Capture Package between all capture sources and reconstruction. | Prevent model/vendor lock-in and preserve synchronization/provenance. | A future standard fully covers required streams and policy semantics. |
| ADR-002 | Accepted | Treat LingBot-Map as a replaceable adapter. | Research model limitations and checkpoint licensing must not define the system of record. | LingBot becomes a stable, explicitly licensed library with canonical compatible contracts; adapter boundary may still remain. |
| ADR-003 | Accepted | Maintain metric, visual, and evidence representations separately. | Appearance, measurement, and truth have different quality and authority requirements. | No anticipated removal; extension only. |
| ADR-004 | Accepted | Store originals and derivatives immutably by content hash. | Integrity, deduplication, reproducibility, rollback, and preservation. | Cryptographic algorithm migration. |
| ADR-005 | Accepted | Use stable semantic entities independent of geometry assets. | Entities must survive rescans, remeshing, and format conversion. | No anticipated removal. |
| ADR-006 | Accepted | Implement Spatial Git as scene manifests and semantic diffs. | Binary meshes cannot be meaningfully line-merged; semantic history is essential. | A standardized scene-revision protocol supersedes it. |
| ADR-007 | Accepted | Use external factor-graph/nonlinear optimization for global consistency. | LingBot does not provide sufficient explicit global loop closure/control fusion for the product requirement. | A replacement model proves controlled global optimization while preserving observations and constraints. |
| ADR-008 | Accepted | Use TSDF/equivalent for metric fusion and splats for visual presence. | Separate measurement topology from photoreal rendering. | A new representation proves both with transparent uncertainty and open export. |
| ADR-009 | Accepted | PostgreSQL/PostGIS plus content-addressed object storage is the reference data plane. | Strong transactions, spatial indexing, mature operations, and open portability. | Scale/queries demonstrate an unresolvable limitation. |
| ADR-010 | Accepted | Derived search/vector/graph stores are rebuildable projections. | Avoid multiple conflicting systems of record. | No anticipated removal. |
| ADR-011 | Accepted | Enforce code/model/dataset/service licensing separately through manifests. | Repository badges do not establish commercial checkpoint or data rights. | No anticipated removal. |
| ADR-012 | Accepted | Support local-only, hybrid, and cloud profiles using identical canonical schemas. | Privacy-sensitive homes and facilities require deployment choice. | No anticipated removal. |
| ADR-013 | Accepted | Agents use typed constrained tools and proposals. | LLMs cannot be authoritative for measurements, consent, deletion, or restricted access. | Formal verification of specific narrow actions may permit auto-commit under policy. |
| ADR-014 | Accepted | Construction design, observation, verified as-built, and proposal are separate states. | Prevents contractual and field-truth confusion. | No anticipated removal. |
| ADR-015 | Accepted | LiveForever generated presence is optional and separately consented. | Preservation can provide value without impersonation; voice/likeness is high risk. | No anticipated removal; consent model may become more granular. |
| ADR-016 | Accepted | Open exports and offline preservation are production requirements. | Customer and family access must outlive one service. | No anticipated removal. |
| ADR-017 | Provisional | Use Open3D plus GTSAM or Ceres as initial geometry/optimization stack. | Permissive mature candidates; implementation benchmark required. | Benchmark, platform support, or license/dependency findings. |
| ADR-018 | Provisional | Prefer gsplat for commercial splat implementation. | Permissive license candidate and active ecosystem. | Quality, browser format, performance, or dependency review. |
| ADR-019 | Provisional | Use a FastAPI/TypeScript/Swift monorepo and durable workflow engine. | Matches existing skills and service boundaries; specific orchestrator remains open. | Scale and team ownership justify split or alternate language. |
| ADR-020 | Open | Select approved LingBot or alternate commercial checkpoint. | Checkpoint license/provenance remains a production gate. | Written evidence and benchmark review. |

## Version 1.1 decisions

| ID | Status | Decision | Rationale | Revisit condition |
|---|---|---|---|---|
| ADR-021 | Accepted | Add a distinct interaction representation registered with metric, visual, design, and evidence layers. | Conventional selection, collision, navigation, clipping, occlusion, and audio need geometry without confusing it with metric truth. | A future open representation transparently satisfies all roles and authority controls. |
| ADR-022 | Accepted | Treat splat-derived surfaces as disposable and non-authoritative by default. | Extraction quality depends on view coverage, method, cleanup, and decimation. | Independently verified promotion may create a separate metric asset, not mutate the proxy. |
| ADR-023 | Accepted | Use a provider contract, quarantine, use-specific validation, and separate publisher. | Research tools and hosted services change rapidly and must not own domain authority. | No anticipated removal. |
| ADR-024 | Accepted | Prefer native hybrid splat-plus-mesh rendering before converting everything. | Preserves appearance, metric geometry, design objects, and interaction behavior with less information loss. | Performance or interoperability evidence supports a different default. |
| ADR-025 | Accepted | Use support maps and stable entities rather than persistent triangle/Gaussian identifiers. | Remeshing, tiling, compression, and LOD change provider-local primitives. | No anticipated removal. |
| ADR-026 | Accepted | Approve render, raycast, collision, navigation, occlusion, audio, and measurement uses independently. | Quality for one use does not prove another, especially immersive safety and construction claims. | No anticipated removal. |
| ADR-027 | Accepted | Classify SplatEdit as an experimental manual provider for public/synthetic data pending official evidence. | Public availability does not establish source, automation, privacy, self-hosting, or commercial rights. | Official evidence and full governance/benchmark approval. |
| ADR-028 | Provisional | Evaluate SplatTransform for local conversion/LOD/collision tooling and Spark for hybrid web rendering. | Their official repositories present permissive candidates aligned with the architecture. | Exact-revision dependency, performance, security, format, and maintenance review. |
| ADR-029 | Provisional | Evaluate Mesh2Splat, MILo, Fast-PGSR, and surface-aware Gaussian methods behind research-shadow providers. | They may improve bidirectional composition or surface quality but require exact technical and transitive-license review. | Benchmarks and commercial approval. |
