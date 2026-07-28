---
spec_id: APP-GLOSS
title: "Glossary"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Glossary

**Accepted reference** — reviewed information suitable for the declared reference use but not necessarily professionally verified or authoritative.

**Anchor** — a spatial association between an entity/evidence/annotation and a coordinate frame, surface, point, line, volume, camera view, or semantic place.

**Assertion** — a statement about a subject, value, relationship, event, location, identity, or property with source, time, provenance, and status.

**Authority** — the approved status and permitted use of information. Authority is separate from model confidence.

**Canonical Spatial Capture Package (CSCP)** — the source-neutral immutable package containing synchronized capture assets, manifests, frames, coordinate frames, sensor streams, quality events, privacy marks, hashes, and signatures.

**Capture profile** — a versioned specification of sensors, operator pattern, thresholds, expected environment, processing path, intended use, and budget.

**Confidence** — a defined measure of model belief, sensor validity, or estimate uncertainty. It has no meaning without method and calibration.

**Control point** — a point with known coordinates and uncertainty in a defined frame, established by a documented method.

**Coordinate frame** — an explicitly defined origin, axes, handedness, units, and optional CRS in which coordinates are expressed.

**Derivative** — any transformed asset or record produced from source inputs, including transcript, depth normalization, mesh, splat, summary, redaction, restoration, or report.

**Design intent** — information from drawings, BIM, specifications, or approved design records describing what should be built, separate from observed condition.

**Evidence** — immutable or versioned material supporting, contradicting, or contextualizing an assertion, including media regions, transcript ranges, documents, measurements, and records.

**Evidence view** — a user experience showing source class, supporting material, uncertainty, generation, and provenance behind a scene or story.

**Generated** — content created by a generative model or artistic process that is not direct capture or solely source-constrained reconstruction.

**Inferred** — content predicted from observations or patterns but not directly observed or verified.

**LingBot adapter** — the isolated SIP worker/service that executes an approved LingBot-Map revision/checkpoint and converts outputs into canonical observations.

**Measurement class** — survey/control, verified field, calibrated sensor, scan estimate, design, learned estimate, or generated placeholder.

**Metric scene** — the representation intended for geometry, spatial queries, navigation, comparison, and measurements, with source and uncertainty.

**Model manifest** — an immutable record of model/checkpoint identity, hash, code, preprocessors, license evidence, approved uses, container, benchmark, and deployment status.

**Observed condition** — a condition supported by field capture or human observation, not necessarily verified as exact or complete.

**Operating envelope** — the validated input, environment, hardware, scene, scale, motion, quality, and use range within which a capability's claims apply.

**Original** — the unmodified bytes acquired from a device, person, document source, or external system.

**Place** — a persistent spatial concept such as site, building, level, room, route, home, landscape, or meaningful location.

**Pose** — a transform between explicitly named camera/device/world frames. Canonical schemas avoid ambiguous direction.

**Provenance** — the chain of entities, activities, agents, software/models, parameters, inputs, outputs, and reviews explaining how information was produced.

**Reconstructed** — content assembled from evidence to represent a place/object/time not directly captured in its entirety.

**Restored** — a derivative intended to repair damage or improve legibility while preserving the original.

**Scene** — a persistent spatial representation of a place with commits, assets, entities, evidence, and policies.

**Scene commit** — an immutable root manifest and metadata referencing one version of scene state and zero or more parents.

**Semantic diff** — a domain-aware comparison of entities, relationships, assertions, geometry regions, permissions, and evidence between commits.

**Source class** — direct capture, measurement, design record, first-person recollection, witness recollection, documented fact, inference, reconstruction, restoration, generation, artistic interpretation, dispute, or unknown.

**Spatial Git** — SIP's immutable commit/branch/diff/merge model for scene manifests and semantics; not a claim that large meshes are line-merged by Git.

**Spatial privacy volume** — a point/area/volume policy object restricting visibility, processing, search, export, or generation within part of a scene.

**Transform edge** — a versioned transformation from a source frame to a target frame with method, uncertainty, residuals, provenance, and validity.

**Verified authoritative** — information approved through a defined accountable verification workflow for specified uses; it is never assigned from AI confidence alone.

**Visual scene** — photoreal or presentation-oriented assets such as textured meshes or Gaussian splats, registered to the scene but not inherently authoritative for measurement.

## Version 1.1 terms

- **Hybrid scene:** registered composition of visual, metric, interaction, design, semantic, and evidence representations.
- **Interaction proxy:** derived non-authoritative geometry for picking, clipping, occlusion, approximate physics, or compatibility.
- **Support map:** versioned mapping from stable anchors/semantic regions to source and derived geometry references.
- **Representation family:** related but non-equivalent assets for roles, LODs, devices, partitions, or revisions.
- **Surface provider:** isolated adapter that produces quarantined candidate geometry or collision/navigation assets.
- **Authority laundering:** improper elevation of truth or measurement status through conversion or appearance.
