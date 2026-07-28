---
spec_id: APP-SPLAT-SURFACE-AUDIT
title: "Splat-Surface Research and Dependency Audit"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---

# Splat-Surface Research and Dependency Audit

## 1. Scope and caution

This appendix records candidate technologies reviewed for SIP v1.1. It is an engineering research inventory, not a legal opinion, procurement approval, security certification, or automatic permission to ship. Before implementation, pin the exact revision, retrieve every license file and submodule, inspect model/checkpoint and dataset terms, build an SBOM, scan the source and artifacts, benchmark the intended use, and complete the provider approval process.

Review date: **2026-07-27**.

## 2. Architectural conclusion

No reviewed component should become the canonical scene database. SIP uses replaceable adapters and keeps:

1. metric representations for eligible geometry and measurements;
2. visual splats/meshes for appearance;
3. non-authoritative interaction proxies, collision, navigation, and occlusion;
4. design/BIM geometry for intended state;
5. semantic and evidence models for meaning and truth.

Native hybrid rendering is preferable when it avoids unnecessary conversion. Splat-to-surface is most valuable for interaction; it does not automatically produce construction-authoritative geometry.

## 3. SplatEdit manual proxy tool

- Reference post: https://www.reddit.com/r/GaussianSplatting/comments/1uoy2e3/simple_splat_to_mesh_tool/
- Described workflow: use SplatEdit, choose `Tools > Create proxy`, select among three options, and export a GLB.
- Public post characterization: free and no login; large/high-resolution splats can be processor-heavy, with splitting suggested for large scenes.
- Positive fit: fast manual experiments; useful comparison of extraction approaches; GLB proxy output; validates demand for a simple interaction surface.
- Missing production evidence in this review: public source for the service, documented automation/API, self-hosting, data-processing/retention details, enterprise/security controls, and commercial integration terms.
- SIP posture: `manual_external_tool`, `research_isolated`; synthetic/public-cleared fixtures only until reviewed and approved.

## 4. PlayCanvas SplatTransform

- Repository: https://github.com/playcanvas/splat-transform
- Observed capabilities: open-source CLI/library; reads and writes numerous splat formats; transforms, filters, merges, decimates, and generates statistics; outputs GLB using Gaussian-splatting glTF support, streamed LOD, and voxel/collision data; supports programmatic and backend/Docker usage.
- License observed at review: MIT in the repository license file.
- Positive fit:
  - local/self-hosted deterministic preprocessing;
  - format normalization and open export;
  - floaters/cluster filtering and decimation;
  - large-scene LOD pipeline;
  - sparse voxel/collision generation that can avoid a full triangle surface;
  - strong candidate for the first permissive local provider adapter.
- Caveats: exact glTF extension and format interoperability must be pinned; collision output requires independent validation; dependencies and generated-format licensing still require inventory.
- SIP posture: high-priority candidate for `active` local preprocessing/voxel provider after SBOM, security, and benchmark gates.

## 5. Spark

- Repository: https://github.com/sparkjsdev/spark
- Observed capabilities: advanced Three.js Gaussian-splat renderer; integrates splat and mesh-based objects; supports multiple splat formats and dynamic transformations.
- License observed at review: MIT.
- Positive fit:
  - validates native hybrid splat-plus-mesh runtime architecture;
  - web/mobile device reach;
  - renderer-adapter candidate for visual splats alongside conventional Three.js meshes and semantic overlays.
- Caveats: SIP still requires its own typed selection, authority, depth/occlusion, tiling, policy, evidence, accessibility, and performance layers; renderer object IDs cannot become durable entity IDs.
- SIP posture: preferred renderer candidate for benchmark, not a canonical data dependency.

## 6. MILo

- Repository: https://github.com/Anttwo/MILo
- Project description: mesh-in-the-loop Gaussian splatting with differentiable surface extraction during optimization, intended to improve consistency between Gaussian and surface representations and produce more practical meshes.
- Positive fit:
  - research reference for jointly improving splat and mesh rather than converting only at the end;
  - potentially valuable for detailed object/room reconstruction and future editable LiveForever scenes;
  - provides multiple extraction approaches and mesh editing/animation research paths.
- License posture observed in the repository: the project states that portions build on original 3D Gaussian Splatting and use the Gaussian-Splatting License, with additional submodule licenses such as Nvdiffrast requiring separate review.
- Operational caveats: GPU-heavy training/extraction; complex transitive stack; model/checkpoint/dataset review; not a simple drop-in proxy generator.
- SIP posture: `research_isolated`; benchmark on public/consented fixtures; no commercial production assumption until full legal and dependency approval.

## 7. FastGS and Fast-PGSR

- Repository: https://github.com/fastgs/FastGS
- Observed project status: FastGS describes accelerated 3D Gaussian Splatting training; the repository states that the Fast-PGSR surface-reconstruction module was released in March 2026 and is based on PGSR.
- Repository license display: MIT for the top-level repository, while the README explicitly instructs users to adhere to licenses of 3DGS, Taming-3DGS, and Speedy-Splat.
- Positive fit:
  - research candidate where reconstruction speed is important;
  - surface-reconstruction comparison against MILo, TSDF, and deterministic local paths;
  - useful shadow benchmark for GPU cost and turnaround.
- Caveats: top-level license is not sufficient to clear inherited code, submodules, models, datasets, or output rights; exact Fast-PGSR revision and dependency tree must be audited independently.
- SIP posture: `research_isolated` pending complete component-level approval.

## 8. Electronic Arts Mesh2Splat

- Repository: https://github.com/electronicarts/mesh2splat
- Observed capabilities: directly converts GLB mesh geometry/material/texture information into a 3D Gaussian representation; includes a renderer and mesh-Gaussian depth-test support; intended for fast integration of synthetic mesh assets into 3DGS workflows.
- License observed at review: a permissive three-clause-style source/binary redistribution license with an additional condition restricting use of EA names/marks and demo logos; exact file must be retained and reviewed.
- Positive fit:
  - reverse direction for proposed BIM/CAD objects, historical reconstructed objects, and authored assets;
  - potential fast visual derivative when a client prefers a splat-only renderer;
  - useful round-trip and hybrid-occlusion benchmark.
- Caveats: current input support described as GLB; conversion does not preserve BIM semantics or metric authority in the splat; dependencies, sample assets, trademarks/logos, renderer requirements, and commercial packaging need audit.
- SIP posture: promising `mesh_to_visual_splat` provider candidate after legal/SBOM/security/benchmark review.

## 9. Open3D and metric-first paths

- Repository: https://github.com/isl-org/Open3D
- Role: point-cloud processing, registration, TSDF integration, meshing, simplification, geometry validation, and visualization support.
- Positive fit: first-party local metric-to-proxy and validation path; useful for RANSAC/ICP, surface comparison, point sampling, simplification, and deterministic fixtures.
- Caveats: each algorithm requires calibrated thresholds and cannot by itself assign construction authority; optional/native dependencies must be inventoried.
- SIP posture: preferred foundation for the deterministic local reference implementation.

## 10. LingBot-Map relationship

- Repository: https://github.com/Robbyant/lingbot-map
- SIP role: optional pinned streaming RGB reconstruction/pose/geometry worker, not a splat-to-mesh provider and not the scene database.
- Integration opportunity: LingBot geometry and camera context can complement ARKit/LiDAR, supply visual continuity, and contribute confidence-aware observations before metric fusion or visual reconstruction.
- Guardrail: learned geometry remains inferred until aligned, validated, and supported by eligible metric evidence.

## 11. Provider comparison

| Candidate | Primary role | Local/self-hosted path | Initial production posture | Key concern |
|---|---|---:|---|---|
| SplatEdit | manual splat-to-proxy experiment | not established in reviewed material | research/manual only | processing, automation, source, and terms unknown |
| SplatTransform | splat conversion, cleanup, LOD, voxel/collision | yes | high-priority local candidate | intended-use validation and dependency audit |
| Spark | hybrid web rendering | yes | high-priority renderer candidate | runtime semantics must remain in SIP |
| MILo | joint splat/mesh research | yes | research only | inherited licenses and complex dependencies |
| Fast-PGSR | fast surface research | yes | research only | inherited licenses/submodules/models |
| Mesh2Splat | mesh-to-visual-splat | yes | candidate after review | semantics/authority loss and license/package audit |
| Open3D | metric-first proxy and validation | yes | preferred reference foundation | algorithm limits and calibration |

## 12. Recommended implementation order

1. Implement canonical asset/provider/view contracts independent of all candidates.
2. Build a deterministic Open3D metric-to-proxy reference path.
3. Integrate SplatTransform locally for normalization, filtering, LOD, and voxel/collision experiments.
4. Integrate Spark behind the renderer abstraction for splat-plus-mesh composition.
5. Add manual SplatEdit comparison using public fixtures only.
6. Benchmark MILo and Fast-PGSR in isolated research workers.
7. Evaluate Mesh2Splat for proposed/historical object visualization.
8. Promote only the specific capabilities that pass license, security, quality, cost, and vertical acceptance.

## 13. Open research questions

- Which proxy representation—triangle mesh, voxel/SVO, SDF, or combined structure—best serves web selection, collision, navigation, and mobile budgets by scene class?
- Can ARKit/LiDAR metric geometry constrain splat surface extraction without degrading visual quality or hiding disagreement?
- How should support maps persist across splat retraining when Gaussian identity changes substantially?
- Which tile/overlap strategy minimizes seam artifacts while allowing room/floor-level regeneration?
- Can a hybrid depth prepass remain stable across browsers, mobile GPUs, WebXR, and multiple splat formats?
- What semantic protection masks are required to preserve life-safety devices, door openings, rails, thin conduit, photographs, and memory objects?
- How should generated historical completion be spatially labeled at sub-object or region granularity?
- What open preservation format best packages splats, metric geometry, proxies, semantic/evidence data, and viewer fallbacks over decades?

## 14. Required revalidation

Revisit this audit before implementation and at every material version upgrade. Repository activity, releases, license files, dependencies, hosted-service behavior, and terms can change. The provider registry—not this appendix—holds the binding production approval.
