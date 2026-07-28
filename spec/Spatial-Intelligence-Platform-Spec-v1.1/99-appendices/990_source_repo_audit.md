---
spec_id: APP-SOURCE
title: "Source Repository and Research Audit"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Source Repository and Research Audit

**Audit date:** 2026-07-27  
**Purpose:** establish the technical baseline and identify facts that must be rechecked before implementation or commercial release. This is an engineering inventory, not legal advice.

## LingBot-Map

| Item | Observed baseline | SIP decision |
|---|---|---|
| Repository | [Robbyant/lingbot-map](https://github.com/Robbyant/lingbot-map) | Pin exact source revision in the adapter image. |
| Audited commit | `1f480aeb8a47a24656090d46d053115b7fe60435` | Initial reference; upgrades require regression and license review. |
| Repository license | Repository states Apache License 2.0 | Code can enter evaluation subject to notice/dependency review. |
| Package version | `0.1.0` in `pyproject.toml` | Do not treat semantic version as production maturity. |
| Python | `>=3.10` | Reference adapter uses a locked Python 3.10 environment unless tested otherwise. |
| Recommended stack | README recommends PyTorch 2.8/CUDA 12.8; FlashInfer preferred; SDPA fallback | Treat backend and runtime as distinct benchmark profiles. |
| Claimed streaming behavior | README describes about 20 FPS at 518×378 and sequences beyond 10,000 frames | Verify on SIP hardware and input classes; do not copy the claim into product guarantees. |
| Long-sequence guidance | Keyframe interval beyond the 320-view training context; windowed mode for very long sequences; README warns of pose collapse outside range | Enforce keyframe/window policies and external global optimization. |
| Outputs | Interactive Viser point clouds; batch rendering; per-frame NPZ predictions via `--save_predictions` | Integrate predictions/manifests, not rendered videos. |
| Upstream acknowledgments | VGGT, DINOv2, FlashInfer | Review each transitive code/model/data obligation. |
| Checkpoint metadata | The Hugging Face model card observed during this audit did not clearly declare license metadata | **Commercial checkpoint use is HOLD** until written terms/provenance are attached to a model manifest. |

### Integration implications

LingBot-Map is a feed-forward learned reconstruction source. It is not the canonical scene database, metric verifier, loop-closure authority, or only pose source. SIP wraps it in a service that records every input/output and compares its trajectory and scale with independent evidence. The system can replace or disable the adapter without migrating scene entities.

## VGGT dependency context

The LingBot repository says it builds on VGGT. The official VGGT repository announced a license change permitting commercial code use subject to its terms and excluding military uses, while distinguishing a specifically approved `VGGT-1B-Commercial` checkpoint from the original checkpoint. The original `facebook/VGGT-1B` model card is marked CC BY-NC 4.0; the commercial checkpoint has a separate acceptable-use license and access process.

SIP rules:

1. Never infer LingBot checkpoint rights from VGGT code rights.
2. Never use the original noncommercial VGGT checkpoint in a commercial processing path.
3. Record whether a LingBot checkpoint contains, derives from, or was trained using weights/data with downstream restrictions.
4. Require written approval covering intended construction and LiveForever use, hosted processing, customer outputs, and model redistribution/deployment.

## Polycam raw export and `polyform`

| Item | Observed baseline | SIP decision |
|---|---|---|
| Repository | [PolyCam/polyform](https://github.com/PolyCam/polyform) | Use as a documented raw-export reference/adapter input. |
| License | MIT | Candidate for commercial adapter after dependency review. |
| Raw files | Mesh/GLB, video/thumbnail, mesh metadata, keyframe images, camera data, depth, confidence, and corrected variants when available | Preserve unmodified raw package and normalize each field. |
| Coordinate notes | Documentation describes ARKit gravity-aligned, right-handed coordinates and camera conventions | Create an explicit source coordinate frame and conformance tests. |
| Optimized poses | Availability depends on capture size/mode and whether optimization ran | Never synthesize or relabel missing corrected poses. |
| Depth limitations | Documentation notes lower resolution/artifacts and limited fine detail | Treat as source-aware observation with uncertainty, not guaranteed metric truth. |

Polycam remains useful immediately for field capture, but SIP's first-party capture application avoids product dependence and exposes all required synchronization and policy controls.

## Open iOS capture references

| Project | Observed role | License/status decision |
|---|---|---|
| [xiongyiheng/ARKit-Scanner](https://github.com/xiongyiheng/ARKit-Scanner) | RGB-D, depth, IMU, transforms; used for ScanNet++ capture workflows | Apache-2.0 candidate; study formats and architecture, do not blindly fork production UX. |
| [cedanmisquith/SwiftUI-LiDAR](https://github.com/cedanmisquith/SwiftUI-LiDAR) | Small SwiftUI/ARKit/RealityKit LiDAR mesh/OBJ scanner scaffold | MIT candidate; useful UI/export patterns, limited maturity. |
| [3dugc/Area-Target-Scanner](https://github.com/3dugc/Area-Target-Scanner) | Offline area capture, processing, feature database/localization patterns | Apache-2.0 candidate; evaluate support boundary and dependencies. |
| `ReScan` and other noncommercial examples | Useful research/UI ideas | Excluded from commercial source reuse when license is noncommercial. |
| Apple RoomPlan / ARKit / RealityKit | Room structure, LiDAR/camera APIs, native platform capture | Platform frameworks; comply with Apple SDK and distribution terms. |

## Reconstruction, optimization, and visualization candidates

| Component | Role | Observed license/status | Default policy |
|---|---|---|---|
| [Open3D](https://github.com/isl-org/Open3D) | registration, point clouds, RGB-D/TSDF, meshing, visualization | MIT | Preferred reference geometry library. |
| [GTSAM](https://github.com/borglab/gtsam) | factor graphs and incremental optimization | BSD family | Preferred solver candidate. |
| [Ceres Solver](https://github.com/ceres-solver/ceres-solver) | nonlinear least squares | Apache-2.0 | Alternative/companion solver candidate. |
| [RTAB-Map](https://github.com/introlab/rtabmap) | RGB-D/stereo/LiDAR graph SLAM and loop closure | BSD with build/dependency caveats | Optional loop/relocalization adapter after locked build audit. |
| [COLMAP](https://github.com/colmap/colmap) | SfM, feature matching, bundle adjustment | BSD; third-party components separate | Optional offline refinement/import/export. |
| [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) | SLAM reference | GPLv3/commercial licensing implications | Excluded from default proprietary distribution. |
| [gsplat](https://github.com/nerfstudio-project/gsplat) | Gaussian splat training/rendering primitives | Apache-2.0 | Preferred commercial-path candidate. |
| [Nerfstudio](https://github.com/nerfstudio-project/nerfstudio) | visual reconstruction tooling/ecosystem | Apache-2.0 | Optional tooling/reference after dependency audit. |
| Graphdeco reference implementation | Research implementation of Gaussian Splatting | restrictive/custom terms observed in ecosystem | Not default commercial dependency. |

## Standards and data infrastructure

| Standard/tool | Baseline | SIP use |
|---|---|---|
| IFC | IFC 4.3 is formalized as ISO 16739-1:2024 | Design/as-built semantics and open owner exchange. |
| IfcOpenShell | Official docs identify LGPL-3.0-or-later and IFC geometry/authoring support | Isolate behind service/library boundary and complete legal review. |
| glTF | glTF 2.0/2.0.1 ecosystem and ISO/IEC 12113:2022 | Runtime mesh/material interchange and browser delivery. |
| 3D Tiles | OGC standard with metadata support | Large-scene tiled streaming. |
| OpenUSD | Time-sampled, composable scene description; official repo supports desktop and embeddable builds | Rich scene interchange/composition; pin release and exact license/dependencies. |
| PostgreSQL/PostGIS | PostGIS 3.6 is the current stable documentation branch during this audit; 3.7 was beta | Transactional and spatial metadata; use stable release, not beta, unless separately approved. |

## Mandatory pre-build rechecks

- Verify each repository's exact commit/tag and license file.
- Verify every package's transitive dependencies and build options.
- Verify model checkpoint terms and hashes, not only model cards.
- Verify auxiliary models downloaded by scripts, including sky segmentation, embeddings, OCR, segmentation, and voice models.
- Verify training/evaluation dataset rights and whether commercial outputs are permitted.
- Verify hosted API terms, data retention, training use, region, and deletion.
- Record all results in model/dependency manifests checked by CI and the production scheduler.


## Version 1.1 hybrid-representation research

The detailed current audit for SplatEdit, SplatTransform, Spark, MILo, FastGS/Fast-PGSR, Mesh2Splat, SuGaR, 2DGS, PGSR, native hybrid rendering, and the provider boundary is maintained in [`989_splat_surface_research_and_dependency_audit.md`](989_splat_surface_research_and_dependency_audit.md).

The governing conclusions are:

- a visual splat and an interaction/metric mesh can coexist without conversion;
- splat-to-mesh and mesh-to-splat operations are derivative transformations, not lossless format changes;
- a top-level repository license does not settle model, dataset, submodule, binary, sample-asset, patent, hosted-service, or output-right questions;
- SplatEdit is a manual experimental provider for public/synthetic data until official evidence supports a broader approval;
- every candidate enters through a replaceable adapter, quarantine, benchmark, and publication boundary.
