---
spec_id: SIP-DEC
title: "Binding Decision Summary"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: true
---

# Binding Decision Summary

This document provides the shortest authoritative reading of the platform. Detailed rationale and acceptance criteria live in the linked specifications.

## Product decisions

1. SIP is a shared spatial platform with Construction and LiveForever as vertical applications, not two unrelated codebases.
2. Polycam is an optional ingestion source. The platform will not depend on Polycam's proprietary application or cloud.
3. A first-party iOS capture application is required for synchronized RGB, LiDAR depth, confidence, ARKit pose, intrinsics, mesh anchors, IMU, and resumable raw export.
4. The primary user value is not scanning alone; it is a persistent scene graph connecting place, time, objects, evidence, documents, people, workflows, and permissions.

## Truth and representation decisions

5. SIP maintains separate metric, visual, interaction, and evidence representations in shared coordinate frames. Design/BIM assets retain design authority and do not become observed conditions by display or conversion.
6. Source class and authority are explicit: observed, measured, verified, design, proposed, inferred, generated, recalled, corroborated, disputed, and superseded.
7. AI confidence never changes source class. A confident inference remains an inference.
8. Every generated or reconstructed LiveForever element is visibly labeled and linked to model/prompt lineage and supporting evidence.
9. Construction measurements display origin, uncertainty, calibration, verifier, and verification date.

## Reconstruction and hybrid-scene decisions

10. LingBot-Map is a replaceable worker adapter. Its output is never the sole authoritative geometry source.
11. ARKit/LiDAR supplies metric scale and short-range depth when valid; LingBot-Map supplies learned geometry and long visual context; external optimization reconciles poses and loop constraints.
12. Long-sequence processing uses segment/window manifests, overlap, explicit resets, and cross-window registration. Pose collapse is detected and quarantined.
13. Factor-graph or nonlinear optimization is owned by SIP, not delegated exclusively to a learned model.
14. TSDF or equivalent volumetric fusion creates metric surfaces; Gaussian splats are a parallel visual representation, not a measurement substrate.
15. A splat-derived proxy is disposable, non-authoritative geometry for picking, collision, navigation, clipping, occlusion, spatial audio, and compatible rendering.
16. Native splat-and-mesh composition is preferred when conversion would discard useful information. Mesh-to-splat and splat-to-mesh operations always create labeled derivatives.
17. Surface generation is provider-based. Providers return quarantined candidates and cannot publish, assign authority, or alter source evidence.
18. Semantic identity uses stable entities and world-frame supports; triangle, Gaussian, voxel, tile, and LOD identifiers are caches, not durable identity.
19. Dynamic people and movable objects are modeled separately from static structure.

## Data decisions

20. All original assets are immutable and content-addressed.
21. Scene entities use stable UUIDs independent of geometry file revisions.
22. Every pipeline run is reproducible from a run manifest containing input hashes, container image, code commit, model checkpoint hash, parameters, and environment.
23. Spatial Git uses append-only scene commits, parent references, semantic diffs, branches, review, and merge policies; raw binary files are not naively line-merged.
24. PostgreSQL/PostGIS is the reference transactional/spatial metadata store; large geometry and media live in object storage; derived search indexes are rebuildable.
25. Open interchange is mandatory. No customer data is considered safely stored if it can only be viewed by SIP.

## Security and privacy decisions

26. Tenant, project, scene, entity, asset, spatial-volume, provider, purpose, and consent permissions may all affect access.
27. Highly sensitive building-system details and intimate/biometric LiveForever data are restricted by default.
28. Local-only and hybrid deployments are first-class modes, not afterthoughts.
29. Destructive deletion uses tombstones, dependency analysis, retention/legal-hold checks, cryptographic erasure where appropriate, and auditable completion.
30. Administrative access is just-in-time, strongly authenticated, and fully logged.

## Licensing and provider decisions

31. Code license, model-weight license, dataset terms, generated-output terms, hosted-service terms, and transitive dependencies are reviewed separately.
32. LingBot-Map code may be evaluated under its published repository license, but production use of a checkpoint is blocked until the checkpoint's license and provenance are documented.
33. The original noncommercial VGGT checkpoint is excluded from commercial production; only an explicitly approved checkpoint and permitted use may be deployed.
34. GPL, noncommercial, research-only, or otherwise incompatible components are excluded from the default commercial distribution unless isolated and approved under a separate model.
35. Manual or hosted spatial tools are denied confidential construction, private-residence, biometric, minor, and restricted LiveForever data until evidence-backed approval covers source, license, processing, retention, security, and commercial use.
36. SplatEdit is an experimental manual provider, not a mandatory or approved production dependency in this baseline.
37. Collision, navigation, occlusion, audio, raycast, and render suitability are approved independently; one successful use does not imply another.

## Vertical and delivery decisions

38. Construction measurements begun on a proxy must resolve to eligible metric or field evidence; proxy geometry cannot establish code, quantity, clearance, fabrication, or as-built claims.
39. LiveForever claims must resolve to evidence and testimony rather than visual realism; an interaction proxy has no historical authority.
40. Every immersive experience has accessibility alternatives and a persistent safe exit; unsafe free locomotion is disabled.
41. The first milestone is a single-room dual demonstration: one construction room and one memory room, both using the same capture package, scene graph, hybrid runtime, and provenance system.
42. Production release requires quantitative geometry/interaction tests, security and privacy gates, license/provider evidence, reproducibility, backup restoration, rollback, open export, and field acceptance.
43. New models and providers are introduced through shadow evaluation and signed manifests, never through an untracked checkpoint, website, or dependency replacement.
