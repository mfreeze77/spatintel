# Internal capture-to-mesh quality profile

This project is a private, local-first spatial-intelligence tool. Its best
result is a composed scene with separate metric, visual, and interaction
representations. Combining their presentation is useful; collapsing their
authority is not. Measurement must always resolve to the metric lane.

## Capture inputs

The target iPhone capture package carries RGB frames, depth, depth confidence,
camera pose, camera intrinsics, ARKit mesh geometry, motion, exposure, tracking
state, and coverage warnings when those signals are available. Original capture
bytes remain content-addressed so later reconstruction can be reproduced.

## Output lanes

- **Metric:** depth unprojection, confidence/uncertainty weighting, voxel fusion,
  and cleaned ARKit or derived metric geometry. Measurement resolves here and
  remains unverified until its supporting capture and quality evidence are
  reviewed.
- **Visual:** colored splats from the deterministic converter, or output from a
  locally configured GPU checkpoint. This lane supplies appearance, not metric
  authority.
- **Interaction:** bounded LOD, collision, navigation, picking, clipping,
  occlusion, and spatial-audio proxies. These disposable assets also resolve to
  metric geometry for measurement.
- **Quality:** vertex/face counts, surface area, boundary and non-manifold edge
  counts, watertight status, bounds, and vertex-color coverage. Real scenes also
  require residual, coverage, and visual review.

The `mesh.compose` worker creates these lanes together while retaining their
separate labels and measurement-resolution rules. Face cleanup preserves source
triangle winding, and duplicate-position colors are averaged before splat
sampling so input ordering does not change the appearance result.

## Recommended internal path

Use the cleaned ARKit/depth-derived mesh as the metric base. Add a locally
configured GPU reconstruction as the visual representation when its exact model
hash is recorded. Derive a bounded interaction LOD from the metric mesh. The
viewer can present all three as one scene, while every measurement resolves back
to the metric representation and its source evidence.

## Current implementation truth

- The deterministic local composite path is implemented and testable without a
  downloaded checkpoint.
- No GPU checkpoint is bundled or silently downloaded.
- Splat-to-surface conversion is a convex-hull fallback that can bridge
  unobserved space. It is only an interaction proxy and is not suitable for
  verified measurement.
- Vertex colors are supported, but texture-image and physically based material
  baking are not yet implemented.
- The conditional iOS capture path now serializes real camera, depth,
  confidence, motion, and ARKit mesh-anchor assets and can finalize a protected
  local directory. It still requires an Xcode build and physical verification
  on the configured iPhone/LiDAR device; repository fixtures do not substitute
  for that proof.

See `IPHONE_CAPTURE_PIPELINE.md` for the exact device output and workstation
commands.
