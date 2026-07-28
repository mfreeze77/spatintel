---
spec_id: CON-HYBRID-REPRESENTATION
title: "Hybrid Representation for Construction and Facility Operations"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: construction
normative: true
---

# Hybrid Representation for Construction and Facility Operations

## 1. Purpose

This specification applies the hybrid spatial architecture to construction surveys, estimating, design coordination, field reference, commissioning, progress documentation, owner handoff, and facility operations. It combines:

- photoreal captured context as a Gaussian splat or visual mesh;
- calibrated LiDAR, survey, TSDF, point-cloud, and verified measurement evidence;
- interaction proxies for clicking, clipping, collision, navigation, and label occlusion;
- BIM/CAD/design geometry for intended or proposed work;
- semantic construction entities and documents;
- an evidence ledger and temporal scene history.

The goal is not to make a visually convincing scan look contract-authoritative. The goal is to let a field user work inside a rich spatial reference while every click, dimension, proposal, and conclusion retains its real source and authority.

## 2. Construction representation stack

| Layer | Construction role | Example |
|---|---|---|
| Visual | rapid recognition and remote context | photoreal mechanical room or corridor splat |
| Metric | eligible dimensional reference | survey control, calibrated LiDAR/TSDF mesh, verified field points |
| Interaction | user and viewer behavior | invisible click/collision mesh, nav surface, section hull |
| Design | intended/proposed state | IFC model, proposed EST4 panel, cable route, access-control hardware |
| Semantic | construction meaning | rooms, devices, panels, doors, systems, issues, RFIs, tests |
| Evidence | factual support | source frames, drawings, specs, submittals, field measurements, witness/reviewer |

A facility can have incomplete layers. The UI and export state what is available and which functions degrade.

## 3. Typical workflows

### 3.1 Existing-condition survey

1. Define scope, sensitive zones, coordinate/control plan, and capture completeness criteria.
2. Capture synchronized RGB/LiDAR/pose and preserve raw evidence.
3. Produce metric and visual representations independently.
4. Generate a non-authoritative proxy or use the metric mesh for bounded interaction.
5. Create rooms, systems, panels, doors, equipment, and device entities through human or reviewed AI annotation.
6. Link each entity to source views and spatial supports.
7. Record measurements separately with method and uncertainty.
8. Publish a field-reference revision labeled observed, inferred, or verified at the entity/assertion level.

### 3.2 Design overlay and estimating

A proposed panel, detector layout, door package, conduit route, or equipment replacement enters as design geometry and design assertions. The runtime can render it inside the existing visual scene for coordination. It remains proposed even when material, lighting, and occlusion make it appear physically present.

An estimator can use the scene to understand access, routing, congestion, room relationships, and likely scope. Quantities or lengths inferred from non-authoritative geometry are labeled estimating assumptions and require field verification before contractual reliance.

### 3.3 Progress capture and spatial diff

Each visit creates a new observed revision. Change detection compares eligible metric surfaces, visual evidence, semantic entities, and known design intent. The system identifies candidate changes such as:

- panel or device installed, removed, moved, or obstructed;
- wall, ceiling, door, or equipment change;
- conduit/cable route appearance;
- access-control hardware state;
- deficiency corrected or still visible;
- area inaccessible or insufficiently captured.

AI or geometric differences create review tasks, not automatic payment certification or acceptance.

### 3.4 Commissioning and closeout

Tests attach to stable equipment/device entities, not mesh triangles. A technician can navigate to an item, open required procedures, record observations, attach photos/video, and sign test results. The final handoff can include visual context, verified geometry where available, current design/as-built documents, test history, programming backups, warranties, and open limitations.

## 4. Measurement truth hierarchy

The platform follows the authority hierarchy in [`708_measurements_truth_hierarchy.md`](708_measurements_truth_hierarchy.md). Hybrid interactions add these rules:

1. A click may originate on the proxy for usability.
2. The measurement service attempts to resolve it to eligible metric evidence.
3. The UI displays the raw click, snapped point, snap residual, source class, calibration/control, and uncertainty.
4. A visual/proxy-only point can create an `approximate_reference` but not a verified dimension.
5. Field verification records the instrument/method, responsible person, date, and evidence.
6. Contract/design dimensions remain separate from field-observed dimensions and conflicts are shown.

No photorealism, watertight repair, surface cleanup, or human confidence in the picture changes this hierarchy.

## 5. Fire-alarm application

The hybrid scene may spatially organize:

- fire-alarm control panels, annunciators, network nodes, power supplies, amplifiers, communicators, and batteries;
- initiating, notification, monitor, control, relay, and interface devices;
- elevators, smoke control, dampers, door release, suppression, and other monitored/controlled systems;
- circuits, loops, risers, network paths, and programming relationships;
- equipment labels, model/serial information, firmware, backups, drawings, point lists, tests, deficiencies, and replacement plans.

A proxy can make devices easy to click and provide occlusion. It cannot establish code-required spacing, exact mounting height, circuit routing, survivability, sequence, candela/audibility, or compliance. Those facts require drawings, calculations, tests, verified field evidence, and accountable review.

For an EST3-to-EST4 project, the existing panel can be an observed entity linked to photos and backups; the proposed EST4 assembly can be a design entity rendered in place; interfaces can be modeled as planned connections; and closeout can supersede the proposal with verified installed evidence without erasing history.

## 6. Access-control application

The scene graph can represent openings, frames, leaves, readers, credentials, controllers, locks, strikes, maglocks, request-to-exit, door contacts, power, interfaces, cable paths, and sequences. Proxy geometry supports selecting the correct door leaf and walking the building. It does not prove fire-rating, egress compliance, mounting dimensions, hardware compatibility, power-transfer route, or accessibility clearance.

Sensitive access-control geometry and system relationships receive elevated classification. Public or broad owner views may show a door entity while withholding controller locations, cable routes, network addresses, credentials, and security sequences.

## 7. BAS, mechanical, and electrical application

The visual scene can provide room and equipment context; design meshes can show proposed panels, sensors, piping, ducts, and equipment; semantic entities carry points, sequences, nameplates, tests, and maintenance. Thin piping, wire, conduit, grilles, and reflective metal are known reconstruction risks and receive protected-region or manual-review rules.

A visual splat or proxy does not establish airflow, pressure, electrical capacity, breaker size, control sequence, load, clearance, or operability. Operational truth comes from sensors, records, tests, and responsible verification.

## 8. RFI, submittal, and document anchoring

A document anchor records drawing/specification/submittal ID, revision, page, region, extracted text where lawful, entity relationships, scene revision, world location, author, and review state. The viewer can navigate from an RFI to the affected room and from a panel to its drawing details.

Design overlays are revision-specific. When an addendum or ASI changes the design, the prior design representation remains in Spatial Git and the viewer can compare it to the new design and observed condition.

## 9. Punch lists and deficiencies

A deficiency includes stable entity, world anchor/volume, description, classification, responsible party, due date, source evidence, applicable drawing/spec/test, status, correction evidence, retest, and closure decision. The proxy can provide the visible selection point, but closure requires the defined evidence and reviewer. A new clean visual scene alone does not close an issue.

## 10. BIM and open handoff

The platform preserves native IFC/BIM object GUIDs and properties. Visual or splat derivatives of BIM are presentation assets. Handoff packages can include:

- authoritative or approved BIM/IFC where contractually required;
- point clouds/metric meshes and their accuracy reports;
- visual splats and supported open viewer formats;
- proxies/collision/nav assets labeled non-authoritative;
- scene graph/entities and stable IDs;
- BCF issues, RFIs, submittals, tests, and commissioning records;
- source evidence and provenance manifests;
- representation roles, authority ceilings, limitations, and viewer instructions.

An owner shall be able to distinguish what can be measured, what is visual reference, what is design intent, and what was verified.

## 11. Restricted and critical facilities

For security-sensitive, life-safety, government, healthcare, laboratory, SCIF, critical infrastructure, or similar work:

- prefer local-only or approved private processing;
- minimize outbound derivatives;
- apply spatial-volume permissions;
- classify panel/controller/network/cable-route details;
- block unapproved hosted conversion tools;
- control screenshots and public links;
- watermark or audit exports where required;
- preserve chain of custody;
- define deletion and retention before capture;
- use synthetic/public fixtures for provider research.

A textureless proxy can still reveal floor plan, routes, protected room locations, and security architecture and therefore remains sensitive.

## 12. Field UX requirements

The field interface provides:

- mode and truth-state banner;
- quick layer toggles with explanations;
- click-to-object using proxy with evidence reveal;
- metric snap indicator and residual;
- approximate/verified measurement distinction;
- offline scoped packages;
- annotations and photos without losing scene context;
- capture gaps and recapture guidance;
- bright-light and low-bandwidth modes;
- change/time comparison;
- issue and test workflows;
- a visible warning when the proxy/visual alignment exceeds tolerance.

## 13. Reporting

Reports identify the exact scene revision and view manifest, representation roles, excluded or inaccessible zones, metric sources, measurement status, visual limitations, design revision, proxy limitations, source evidence, and reviewer. Rendered screenshots are supporting illustrations, not a substitute for the data/provenance package.

## 14. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| CONHYB-001 | P0 | Construction scenes shall maintain observed, inferred, verified, design/proposed, and generated states independently at entity and assertion level. | Domain schema test |
| CONHYB-002 | P0 | An interaction proxy or visual splat shall not independently establish field dimensions, code compliance, as-built status, payment progress, issue closure, or commissioning acceptance. | Policy and workflow test |
| CONHYB-003 | P0 | A measurement begun on a proxy shall record the display hit and shall resolve to eligible metric evidence or remain approximate and unverified. | Measurement acceptance test |
| CONHYB-004 | P0 | Proposed or design geometry shall retain a visible and machine-readable design label even when photorealistically blended with observed context. | Viewer/export test |
| CONHYB-005 | P0 | Construction entities, tests, issues, and documents shall use stable IDs and source evidence rather than depending on a proxy triangle or visual Gaussian identity. | Remeshing regression test |
| CONHYB-006 | P0 | Sensitive building, life-safety, and security representations shall be denied to unapproved external providers before data export or source access. | Security test |
| CONHYB-007 | P0 | Issue closure and commissioning acceptance shall require the configured evidence, test, retest, and accountable reviewer rather than visual disappearance alone. | Workflow test |
| CONHYB-008 | P0 | Handoff exports shall declare every representation role, authority ceiling, accuracy/validation report, coordinate frame, and limitation. | Handoff round-trip test |
| CONHYB-009 | P1 | Progress comparison shall report capture gaps and review candidate geometric/visual changes before changing semantic state. | Change-detection scenario |
| CONHYB-010 | P1 | Fire-alarm, access-control, BAS, mechanical, and electrical verticals shall declare which attributes require documents, calculations, tests, or field verification beyond spatial appearance. | Vertical review |
| CONHYB-011 | P1 | Field clients shall expose metric snap source, residual, uncertainty, truth state, and recapture/verification options at the point of work. | Field UX test |
| CONHYB-012 | P1 | BIM/IFC identity and properties shall remain linked to any visual-splat or proxy derivative without making the derivative the authoritative BIM deliverable. | IFC interoperability test |
| CONHYB-013 | P1 | Offline construction packages shall apply the same spatial permissions, truth rules, expiry, audit, and measurement constraints as hosted use. | Offline field test |
| CONHYB-014 | P1 | Reports and screenshots shall identify source scene revision, design revision, representations used, excluded areas, and measurement authority. | Reporting acceptance test |
| CONHYB-015 | P1 | A proxy alignment failure beyond the purpose threshold shall disable affected selection, collision, navigation, or metric snapping and create a review task. | Fault-injection test |
| CONHYB-016 | P1 | Owner handoff shall include an open path to inspect or reconstruct semantic/provenance data without dependence on a single proprietary viewer. | Portability test |

## 15. Construction acceptance demonstration

The release demonstration uses a consented noncritical room containing an existing fire-alarm or control panel, two doors, equipment, and a proposed replacement. It shall:

1. preserve RGB/LiDAR/source evidence;
2. render a visual splat and a hidden metric reference;
3. generate and validate a proxy/collision asset;
4. attach stable panel, door, and equipment entities;
5. overlay the proposed design model with truth labels;
6. perform one approximate proxy measurement and one metric-supported measurement;
7. create and close a deficiency with correction and retest evidence;
8. regenerate the proxy and preserve anchors;
9. compare two time revisions;
10. export an owner package and prove independent re-import with authority and provenance intact.
