---
spec_id: PLT-HYBRID-RUNTIME
title: "Hybrid Scene Runtime"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: platform
normative: true
---

# Hybrid Scene Runtime

## 1. Purpose

The hybrid scene runtime presents a registered combination of Gaussian splats, metric meshes and point clouds, design/BIM geometry, interaction proxies, collision/navigation structures, semantic overlays, and evidence. It provides one spatial experience without collapsing these sources into one truth class.

The runtime applies consistently across the browser viewer, desktop reviewer, VR/AR clients, report renderers, and future native clients. Rendering engines are adapters; scene meaning comes from the canonical asset and view contracts.

## 2. Runtime layer stack

```text
Evidence and truth-label layer
Semantic entities, annotations, issues, memories, and measurements
Design/proposed geometry layer
Metric reference layer
Interaction layer: proxy, collision, nav, occlusion, audio
Visual layer: splats, textures, visual meshes, source imagery
Coordinate-frame and policy kernel
```

Layers can be rendered in a different visual order, but authority checks always follow the canonical order. Hidden layers can still participate in raycast, occlusion, or metric snapping only when the view manifest and user permission allow it.

## 3. Hybrid scene-view manifest

A client never receives a raw list of every project asset. The server creates a purpose- and audience-scoped view:

```json
{
  "schema_version": "sip.hybrid-scene-view/1.1",
  "view_id": "view_01K1RUNTIME8C",
  "scene_revision_id": "scene_rev_0027",
  "principal_id": "principal_01",
  "purpose": "construction_field_reference",
  "device_profile": "web_desktop_high",
  "time_context": {"observed_at": "2026-07-27T12:00:00Z"},
  "bindings": {
    "visual": ["binding_visual_splat_floor1"],
    "metric": ["binding_metric_mesh_floor1"],
    "design": ["binding_design_est4_panel"],
    "interaction": ["binding_proxy_floor1"],
    "collision": ["binding_collision_floor1"],
    "navigation": [],
    "semantic": ["binding_semantic_project"],
    "evidence": ["binding_evidence_authorized"]
  },
  "interaction_policy": {
    "selection_order": ["semantic", "design", "metric", "proxy", "visual"],
    "measurement_sources": ["metric"],
    "allow_approximate_visual_reference": true,
    "allow_public_navigation": false
  },
  "truth_labels": {"mode": "always_available", "audit_mode": true},
  "streaming": {"tile_manifest_id": "tiles_01", "bandwidth_budget_mbps": 30},
  "expires_at": "2026-07-27T13:00:00Z",
  "signature": "sig:..."
}
```

The server excludes unauthorized buildings, rooms, spatial volumes, source images, security devices, people, memories, and historical revisions before manifest generation. Client-side invisibility is not authorization.

## 4. Renderer abstraction

The runtime adapter must support, directly or through graceful fallback:

- Gaussian splat rendering;
- conventional glTF/GLB meshes;
- point clouds and optional metric overlays;
- transparent and x-ray design geometry;
- depth-aware semantic markers and labels;
- tiled/LOD streaming;
- world-origin rebasing for large coordinates;
- section boxes and clipping planes;
- picking and region selection;
- source-evidence camera views;
- device-specific performance tiers.

A candidate such as a Three.js-compatible splat renderer can be used behind the adapter, but canonical manifests must not embed renderer-specific object identities as durable scene identity.

## 5. Depth and occlusion composition

Splats and meshes must agree on camera, projection, depth convention, clipping, coordinate frame, color space, and temporal state. Preferred composition uses a shared or interoperable depth path so:

- a proposed mesh can appear correctly inside an observed splat;
- labels can be hidden by walls without disappearing behind translucent artifacts;
- proxy or metric geometry can provide a conservative depth prepass;
- source-image evidence can be projected from recorded camera poses;
- visual and interaction layers remain registered while tiles stream.

When exact depth interoperability is unavailable, the client selects a declared fallback such as ordered composition, proxy-depth approximation, cutaway mode, or side-by-side comparison. The fallback is surfaced in diagnostics and cannot be used for occlusion-sensitive review without warning.

## 6. Typed selection pipeline

A pointer, gaze, touch, controller, or agent query produces candidates from multiple layers. Resolution is typed:

1. semantic overlay candidates within screen/world tolerance;
2. design object candidates with stable model/entity GUIDs;
3. metric-surface hits where the user has access;
4. interaction-proxy hits;
5. visual-splat depth or Gaussian-region hits;
6. source-image observations projected near the hit.

The resolver returns the visible selected entity plus all support evidence the caller may access. It does not silently convert a proxy triangle into a verified point.

```json
{
  "selection_id": "sel_01",
  "entity_id": "door_127",
  "display_hit": {
    "source_role": "interaction_proxy",
    "position": [4.12, 7.44, 1.02],
    "residual_to_world_anchor_m": 0.018
  },
  "metric_support": {
    "available": true,
    "asset_id": "metric_mesh_01",
    "position": [4.11, 7.45, 1.01],
    "snap_distance_m": 0.024,
    "authority": "calibrated_scan_reference"
  },
  "truth_label": "observed_unverified",
  "evidence_count": 6
}
```

## 7. Measurement mode

Measurement is a dedicated workflow, not a generic distance between display hits.

For each endpoint the client:

1. records the raw input and visible representation hit;
2. requests eligible metric supports from the server or local authorized cache;
3. snaps only within a method-specific threshold;
4. displays snap residual, metric source, calibration/control, and uncertainty;
5. allows an approximate reference when policy permits, but prevents verification;
6. creates a measurement record with method and evidence;
7. requires accountable field verification for authoritative construction use.

When no eligible metric support exists, the runtime must not fall back to using a visual splat or proxy while retaining a metric-looking user interface. It states `approximate visual reference` and offers recapture or field-verification actions.

## 8. Collision and navigation

Collision and navigation are loaded by actor profile and purpose. They can differ from display geometry.

- Camera collision may use coarse conservative hulls.
- An avatar may use a room-scale collision mesh and explicit stair/door links.
- A wheelchair-accessible path requires a separately validated profile and cannot be inferred from ordinary avatar navigation.
- Construction path planning cannot claim egress, accessibility, or safe robotic clearance without a purpose-specific verified model.
- LiveForever can use teleport or guided transitions across uncertain areas.

The runtime supports a safe-exit gesture and never traps a user inside invalid geometry. Collision failure degrades to bounded navigation, teleport, or no locomotion rather than unsafe autonomous movement.

## 9. Tiling, streaming, and LOD

The client chooses tiles and LOD by view, device, bandwidth, memory, and semantic priority. It may prioritize a selected panel, doorway, photograph, or memory object over an unimportant wall region.

Requirements include:

- deterministic tile coordinate frames;
- hysteresis to avoid LOD thrashing;
- prefetch along authorized camera or guided paths;
- cancellation of obsolete requests;
- stable entity selection while LOD changes;
- proxy/visual tile synchronization;
- seam-aware collision/navigation loading;
- signed URLs or stream tokens with short expiry;
- local cache encryption and eviction under policy;
- explicit degraded modes.

## 10. Temporal and Spatial Git views

A runtime view selects one or more scene commits. Comparison modes include:

- side-by-side synchronized cameras;
- wipe or reveal;
- ghosted design versus observed;
- semantic change list with click-to-navigate;
- metric change overlay;
- visual time slider;
- LiveForever historical branches and alternate recollections.

The runtime never morphs between revisions in a way that hides uncertainty. Generated interpolation is a labeled visual aid, not evidence of an intermediate condition.

## 11. Evidence reveal

From any visible object or memory anchor, an authorized user can open an evidence panel showing:

- current assertion and truth label;
- source images/video frames and capture poses;
- drawings, documents, tests, interviews, or witnesses;
- metric and visual support;
- provider and conversion lineage;
- review decisions and disputes;
- superseded revisions;
- privacy and audience limitations.

The viewer records which scene revision, view manifest, truth labels, and evidence were shown when an audit snapshot is requested.

## 12. Construction modes

Construction runtime modes include:

- field reference;
- measurement and verification;
- design overlay;
- existing/proposed comparison;
- RFI, punch, and commissioning review;
- progress/time comparison;
- facility-operations handoff;
- restricted life-safety/security review.

A proposed EST4 panel rendered inside a captured room retains a proposed/design label. The user can click it to view submittals and planned connections, while the existing EST3 panel remains an observed entity with its own evidence and history.

## 13. LiveForever modes

LiveForever runtime modes include:

- guided memory walk;
- room/object story discovery;
- evidence and family-history review;
- alternate recollection branches;
- quiet mode with no generated presence;
- accessible 2D/desktop mode;
- VR/AR presence with safe locomotion;
- private curator mode for sensitive or disputed content.

A photoreal splat supplies place presence; proxy/collision/nav assets supply interaction; the semantic/evidence graph supplies meaning. Generated objects, voices, likeness, dialogue, or environmental completion remain visibly and programmatically labeled.

## 14. Offline and local-only operation

An authorized offline package can contain a scoped scene view, assets, policy snapshot, revocation/expiry behavior, local search index, and audit queue. The client validates signatures and hashes without cloud access. Offline mode must preserve the same role, authority, measurement, truth-label, and evidence rules as hosted mode.

When an offline authorization expires or is revoked at next synchronization, restricted cached assets are withdrawn and erased according to policy. Safety and privacy cannot depend solely on continuous connectivity.

## 15. Accessibility and comfort

The runtime supports keyboard, screen reader, captions/transcripts, reduced motion, seated mode, adjustable movement, teleport, high contrast, scalable labels, narration controls, and non-immersive alternatives. LiveForever includes quiet mode and immediate safe exit. Construction views support field-friendly controls, gloves/stylus where practical, bright-light contrast, and low-bandwidth fallbacks.

## 16. Observability

Privacy-safe measures include frame time, tile latency, memory, representation fallback, selection failure, anchor residual, collision correction, navigation fallback, measurement snap source, and renderer errors. Telemetry shall not capture raw memory content, exact sensitive security-system geometry, faces, transcripts, or source media. Project- and tenant-level labels are pseudonymized when operationally sufficient.

## 17. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| HYBRUN-001 | P0 | The server shall generate an authorized hybrid scene-view manifest selecting typed bindings by scene revision, purpose, principal, audience, device, time, and policy. | API authorization test |
| HYBRUN-002 | P0 | Unauthorized assets and spatial volumes shall be excluded server-side rather than hidden only by the client. | Security test |
| HYBRUN-003 | P0 | Runtime selection shall preserve the source role of each hit and shall not silently convert a proxy or visual hit into verified metric evidence. | Typed-selection test |
| HYBRUN-004 | P0 | Measurement endpoints shall resolve to eligible metric support or be saved only as explicitly approximate and unverified. | End-to-end measurement test |
| HYBRUN-005 | P0 | Design, generated, inferred, observed, and verified truth labels shall remain available in every client and export profile. | Cross-client truth-label test |
| HYBRUN-006 | P0 | Collision and navigation shall use declared actor and intended-use profiles and shall not imply egress, accessibility, safety, or robotic suitability without matching verification. | Profile-policy test |
| HYBRUN-007 | P0 | A missing or invalid proxy shall not cause measurement fallback to the visual splat or change metric authority. | Fault-injection test |
| HYBRUN-008 | P0 | Evidence reveal shall expose accessible source, lineage, limitations, and revision context for a selected entity or memory. | Evidence UX and authorization test |
| HYBRUN-009 | P1 | The renderer adapter shall support registered splats and meshes in a common frame with depth-aware composition or an explicit declared fallback. | Renderer conformance test |
| HYBRUN-010 | P1 | Tile and LOD transitions shall preserve world registration, semantic identity, and stable selection within benchmark thresholds. | Streaming regression test |
| HYBRUN-011 | P1 | The runtime shall provide independent fallbacks for display, picking, collision, navigation, occlusion, and evidence. | Degradation test |
| HYBRUN-012 | P1 | Temporal comparison shall identify source revisions and shall label any generated interpolation as non-evidentiary. | Spatial Git viewer test |
| HYBRUN-013 | P1 | Offline and local-only clients shall enforce the same authority, truth, consent, and measurement contracts as hosted clients. | Offline parity test |
| HYBRUN-014 | P1 | Runtime telemetry shall measure performance and failure without collecting restricted source content or unnecessary precise spatial details. | Privacy telemetry review |
| HYBRUN-015 | P1 | LiveForever clients shall provide quiet mode, safe exit, accessible non-immersive alternatives, and audience controls. | Accessibility and safety test |
| HYBRUN-016 | P1 | Construction clients shall surface design/observed/verified state and prohibit a visually blended design object from appearing as existing condition. | Construction acceptance test |

## 18. Acceptance scenarios

### Construction

Load a mechanical/electrical room as a visual splat with a hidden metric mesh, proxy collision, semantic devices, and a proposed panel model. Select the existing and proposed panels, navigate through a doorway, clip the room, open evidence, create an approximate proxy click, snap a measurement to eligible metric geometry, and prove the approximate click cannot become verified.

### LiveForever

Load a family room splat with an invisible proxy, walkable floor, object anchors, source photographs, and three memories. Navigate with collision and teleport fallback, trigger a story at a chair, reveal its evidence, switch to an alternate recollection, enable quiet mode, and hide a restricted family photograph without leaving geometry or cache leakage.
