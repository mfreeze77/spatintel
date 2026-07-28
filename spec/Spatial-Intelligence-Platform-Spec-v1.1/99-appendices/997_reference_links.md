---
spec_id: APP-REF
title: "External References"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# External References

**Accessed:** 2026-07-26. External material may change. The implementation must pin exact revisions and retain applicable licenses/notices.

## Primary LingBot sources

- [LingBot-Map repository](https://github.com/Robbyant/lingbot-map)
- [LingBot-Map commit used for this baseline](https://github.com/Robbyant/lingbot-map/commit/1f480aeb8a47a24656090d46d053115b7fe60435)
- [LingBot-Map paper, arXiv:2604.14141](https://arxiv.org/abs/2604.14141)
- [LingBot-Map model repository](https://huggingface.co/robbyant/lingbot-map)

## Capture and Apple spatial frameworks

- [PolyCam/polyform](https://github.com/PolyCam/polyform)
- [Apple RoomPlan documentation](https://developer.apple.com/documentation/roomplan)
- [Apple ARKit documentation](https://developer.apple.com/documentation/arkit)
- [ARKit-Scanner](https://github.com/xiongyiheng/ARKit-Scanner)
- [SwiftUI-LiDAR](https://github.com/cedanmisquith/SwiftUI-LiDAR)
- [Area-Target-Scanner](https://github.com/3dugc/Area-Target-Scanner)

## Geometry, SLAM, optimization, and visual reconstruction

- [Open3D](https://github.com/isl-org/Open3D)
- [GTSAM](https://github.com/borglab/gtsam)
- [Ceres Solver](https://github.com/ceres-solver/ceres-solver)
- [RTAB-Map](https://github.com/introlab/rtabmap)
- [COLMAP](https://github.com/colmap/colmap)
- [gsplat](https://github.com/nerfstudio-project/gsplat)
- [Nerfstudio](https://github.com/nerfstudio-project/nerfstudio)
- [VGGT repository](https://github.com/facebookresearch/vggt)
- [VGGT original checkpoint](https://huggingface.co/facebook/VGGT-1B)
- [VGGT commercial checkpoint](https://huggingface.co/facebook/VGGT-1B-Commercial)

## Formats, BIM, and scene standards

- [buildingSMART IFC 4.3 documentation](https://ifc43-docs.standards.buildingsmart.org/)
- [IfcOpenShell](https://ifcopenshell.org/)
- [Khronos glTF](https://www.khronos.org/gltf/)
- [OGC 3D Tiles standard](https://www.ogc.org/standard/3dtiles/)
- [OpenUSD](https://openusd.org/)
- [OpenUSD repository](https://github.com/PixarAnimationStudios/OpenUSD)

## Data and spatial infrastructure

- [PostgreSQL](https://www.postgresql.org/)
- [PostGIS](https://postgis.net/)
- [PostGIS official manual](https://postgis.net/documentation/manual/)

## Reference-use rules

1. A URL is not a dependency lock. Record commit/tag/package/checkpoint hash.
2. A repository license is not automatically a model-weight or dataset license.
3. A paper performance claim is not a SIP product guarantee.
4. An official format standard does not guarantee every tool round-trips every feature.
5. Cloud/API pricing and terms are runtime configuration inputs and must be rechecked before commercial planning.

## Version 1.1 research references

See [`989_splat_surface_research_and_dependency_audit.md`](989_splat_surface_research_and_dependency_audit.md) for version-sensitive links and provisional postures covering SplatTransform, Spark, MILo, FastGS/Fast-PGSR, Mesh2Splat, SuGaR, 2DGS, PGSR, and the user-supplied community concept.
