---
spec_id: SIP-CHANGE-110
title: "Version 1.1 Hybrid Representation Changeset"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---

# Version 1.1 Hybrid Representation Changeset

## 1. Release intent

Version 1.1 integrates splat-to-surface conversion, mesh-to-splat conversion, and native splat-plus-mesh rendering without weakening the platform's truth model. The release adds an **interaction proxy** as a first-class, registered representation. It is optimized for selection, collision, navigation, clipping, occlusion, spatial audio, and simulation support, while remaining disposable and non-authoritative.

The release does not redefine a Gaussian splat as a measured building model. It formalizes a hybrid scene in which visual appearance, metric geometry, interaction geometry, design geometry, and evidence may coexist in the same coordinate frame while retaining separate provenance, authority, and lifecycle.

## 2. Binding architectural change

The former three-representation description is replaced by four coordinated layers:

| Layer | Principal purpose | Typical assets | Authority rule |
|---|---|---|---|
| Metric representation | dimensions, topology, change analysis, verified navigation | calibrated point clouds, TSDFs, metric meshes, control points | may become authoritative only through the verification workflow |
| Visual representation | photoreal presence and human interpretation | Gaussian splats, textured meshes, source imagery | never authoritative by appearance alone |
| Interaction representation | picking, collision, locomotion, clipping, occlusion, spatial audio | proxy mesh, collision volume, navigation surface, occlusion hull | always derived and non-authoritative |
| Evidence representation | source truth, consent, provenance, reviews, disputes | captures, drawings, interviews, documents, manifests, approvals | authoritative only for the fact the evidence actually establishes |

Design/BIM geometry remains a typed asset within the scene graph and carries `design_authority`, not observed or verified-as-built authority.

## 3. New normative modules

- `20-architecture/211_hybrid_representation_services.md`
- `40-reconstruction/415_splat_surface_hybrid_representation.md`
- `40-reconstruction/416_splat_surface_provider_contract.md`
- `40-reconstruction/417_bidirectional_mesh_splat_interop.md`
- `40-reconstruction/418_splat_editing_cleanup.md`
- `50-data/514_hybrid_representation_asset_contract.md`
- `60-platform/613_hybrid_scene_runtime.md`
- `60-platform/614_splat_surface_api_and_events.md`
- `70-construction/714_hybrid_representation_construction.md`
- `80-liveforever/814_hybrid_representation_liveforever.md`
- `90-security-ops/913_external_spatial_provider_governance.md`
- `95-testing-delivery/961_splat_surface_benchmark_acceptance.md`
- `99-appendices/989_splat_surface_research_and_dependency_audit.md`
- `MIGRATION_FROM_1.0.md`
- `V1_1_MIGRATION_GUIDE.md`

## 4. Provider posture

The subsystem uses a provider boundary. Local permissively licensed tools, private managed services, research workers, and manual external tools can be benchmarked without becoming permanent data-model dependencies.

SplatEdit is classified as a manual experimental provider until source availability, automation surface, data-processing location, retention, commercial permission, and security posture are documented and approved. Sensitive construction scans, private residences, biometric imagery, and restricted LiveForever material cannot be sent to it under this baseline.

## 5. New delivery epics

The backlog gains governance, reconstruction, platform, vertical-pilot, and benchmark work for the hybrid representation. The implementation sequence requires the asset contract and provider gate before any external conversion, and requires quantitative comparison against metric geometry before a proxy can be published for a customer scene.

## 6. Compatibility

Version 1.0 scenes remain readable. When no interaction proxy exists, the runtime falls back to metric-mesh interaction where authorized, a coarse locally generated collision structure, or bounded camera navigation. Existing visual splats do not need to be retrained merely to adopt the v1.1 schema.

## 7. Migration rule

A v1.0 asset may be promoted to a v1.1 role only through an explicit migration operation that records the original asset hash, assigned role, coordinate frame, authority class, review decision, and any derived support map. File extension or visual resemblance must never determine authority.
