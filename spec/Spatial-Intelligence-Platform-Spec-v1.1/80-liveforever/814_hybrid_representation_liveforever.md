---
spec_id: LIF-HYBRID-REPRESENTATION
title: "Hybrid Representation for LiveForever Spatial Memories"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: liveforever
normative: true
---

# Hybrid Representation for LiveForever Spatial Memories

## 1. Purpose

LiveForever uses hybrid spatial representations to preserve the places in which a person's memories occurred and to let authorized family members explore stories in context. The visual splat provides presence, the interaction proxy provides touch and movement, metric geometry provides bounded spatial reference, semantic anchors provide meaning, and the evidence graph preserves what is known, remembered, disputed, generated, or private.

The product is not allowed to turn a compelling reconstruction into false historical certainty or to create a simulated person beyond the subject's and affected people's consent.

## 2. Memory-scene layers

| Layer | LiveForever role | Example |
|---|---|---|
| Visual | emotional and perceptual presence | grandparent's living room splat |
| Metric | registered spatial framework where available | LiDAR room shell, measured furniture location |
| Interaction | safe exploration and triggers | floor collision, chair proxy, doorway nav link |
| Reconstructed/design | historical or missing objects/conditions | 1987 Christmas tree, former workbench, demolished wall |
| Semantic | people, places, objects, events, relationships, memories | “Grandfather's chair,” “Christmas morning 1987” |
| Evidence | sources and governance | interviews, photos, VHS, letters, witnesses, consent |

Metric precision is often secondary to emotional fidelity, but source and uncertainty remain explicit. A current room scan may be metrically accurate while its 1987 reconstruction is interpretive.

## 3. Place capture and reconstruction

A meaningful place can be built from:

- a current first-party RGB/LiDAR capture;
- imported Polycam or other consented spatial exports;
- family photos and video with camera/pose reconstruction;
- floor plans, maps, diaries, letters, and interviews;
- manually authored geometry;
- generated visual completion under a labeled interpretation branch.

The canonical project preserves the current observed place separately from historical branches. Each historical change—furniture, wall color, room layout, objects, weather, lighting, people, or sounds—has source and confidence. The system can show multiple plausible versions when evidence conflicts.

## 4. Interaction proxy uses

The proxy may provide:

- walkable floors and solid walls;
- doorway, stair, and room transitions;
- raycast targets for objects and photos;
- trigger volumes for stories and ambient sound;
- avatar placement and non-safety-critical hand interaction;
- label and memory-card occlusion;
- accessible guided routes;
- fallback rendering on devices that cannot display splats.

The proxy is not presented as evidence that the historical room had exactly that geometry. A reconstructed chair proxy can trigger a true interview recording while still being only an approximate visual support.

## 5. Memory anchor model

A memory anchor links a story to place, time, entities, and evidence:

```json
{
  "memory_id": "memory_christmas_1987_01",
  "title": "Christmas morning at Grandma's house",
  "time": {"display": "Christmas 1987", "precision": "month"},
  "place_id": "place_grandparents_living_room",
  "world_anchor": {
    "frame_id": "frame_house_current",
    "position": [3.8, 2.1, 1.0],
    "uncertainty_m": 0.35
  },
  "object_ids": ["object_grandfather_chair", "object_christmas_tree"],
  "narrators": ["person_mary"],
  "truth_class": "remembered_first_person",
  "evidence_ids": ["interview_42_seg_118", "photo_1987_003", "vhs_07_clip_02"],
  "alternate_memory_ids": ["memory_christmas_1987_01_alt_susan"],
  "presentation_support": {
    "proxy_asset_id": "proxy_living_room_v4",
    "visual_asset_id": "splat_living_room_historical_v2"
  },
  "audience_policy_id": "aud_family_descendants"
}
```

The presentation support can be replaced without changing the memory's identity or sources.

## 6. Historical reconstruction branches

A place can contain branches such as:

- `observed_2026`;
- `reconstructed_2005`;
- `reconstructed_1987_mary_account`;
- `reconstructed_1987_susan_account`;
- `artist_interpretation_1952`.

Each branch declares which elements are directly captured, photo-supported, document-supported, witness-recalled, inferred, generated, or artistically authored. The viewer may transition between branches, but a generated morph is labeled as presentation and is never a record of how the room changed.

## 7. Objects and people

Objects receive stable IDs independent of their mesh or splat. An heirloom can link to photographs, scans, ownership history, stories, and family relationships. A reconstructed object can appear in the scene only with its reconstruction label.

People are not ordinary scene assets. A captured or generated likeness, voice, gesture, dialogue model, or first-person agent requires the separate consent and safety rules in the LiveForever specifications. A proxy mesh can establish where an archival video subject stood, but it cannot establish identity, thoughts, or words.

## 8. Evidence-first storytelling

Every story experience supports evidence reveal appropriate to the audience. A viewer can see:

- who told the memory and when;
- whether it is first-person, secondhand, documentary, inferred, or generated;
- source photo/video/audio/document excerpts;
- location and object support;
- other witnesses and conflicting accounts;
- editorial/reconstruction decisions;
- confidence and uncertainty expressed in human-readable terms;
- privacy limitations and why some content is unavailable.

A family may choose a streamlined presentation, but truth labels remain accessible and cannot be removed from exports or audit views.

## 9. Safe navigation and experience design

LiveForever may run on phone, browser, tablet, television, desktop, AR, or VR. The interaction layer supports:

- guided story paths;
- teleport and fade transitions;
- bounded walkable zones;
- seated mode;
- immediate safe exit;
- reduced motion;
- captioned and transcript-first alternatives;
- quiet mode with no generated voice or avatar;
- pause and emotional-content warnings;
- private curator mode;
- no-surprise defaults for sensitive memories.

Collision is conservative and non-safety-critical. Missing or uncertain geometry uses a visible boundary or guided transition rather than inventing a traversable space.

## 10. Privacy and consent propagation

Spatial derivatives can expose a private residence, room layout, valuables, people, family relationships, security details, and personal history even when textures are removed. Every visual, proxy, collision, nav, screenshot, and export inherits consent and audience policy.

When a person revokes consent, dies under a defined estate policy, reaches adulthood, or changes audience, the dependency graph identifies affected derivatives and publications. The platform can withdraw, redact, regenerate, or cryptographically erase them according to legal and governance rules. A family member's desire for realism never overrides a living person's rights.

## 11. Generated completion

Generated completion can repair a presentation gap or visualize a historical hypothesis only when:

- it is a separate derivative or branch;
- source and generated regions are machine-readable;
- the audience sees an appropriate label;
- the subject/family policy allows the purpose;
- the output is not fed back as source evidence;
- future training use is separately governed;
- alternate reconstructions can coexist;
- a non-generated evidence view remains available.

Examples include restoring a missing portion of a room for a guided experience or rendering a described workbench that no longer exists. The generated object must not be described as a recovered scan.

## 12. Spatial audio

Audio anchors can place archival voice, music, room ambience, or sound effects. The provenance distinguishes recorded audio, cleaned/restored audio, reenactment, generated ambience, and synthesized voice. Spatialization is a presentation transform and does not imply the audio was originally recorded at that exact position.

Synthetic voice and conversational agents remain subject to explicit consent and kill switches. Quiet mode can replace them with text or original recordings.

## 13. Preservation package

A long-term package includes:

- canonical source photos, video, audio, documents, and interviews as permitted;
- visual splats and open or documented decoders;
- metric and proxy assets with role/authority labels;
- semantic memory graph and stable IDs;
- coordinate frames and support maps;
- historical branches and reconstruction manifests;
- consent/audience policies and revocation instructions;
- truth labels and limitations;
- checksums, signatures, and migration instructions;
- accessible 2D media fallbacks.

The family's memories must remain intelligible even if a specific real-time splat renderer disappears.

## 14. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| LIFHYB-001 | P0 | LiveForever shall keep captured place, historical reconstruction, generated interpretation, semantic memory, and evidence roles separately identifiable. | Schema and viewer test |
| LIFHYB-002 | P0 | A proxy or visual reconstruction shall not establish historical certainty, identity, speech, intent, relationship, or event occurrence without supporting evidence. | Truth-policy test |
| LIFHYB-003 | P0 | Memory identity and evidence shall survive proxy regeneration, splat retraining, tiling, and renderer replacement. | Remapping and migration test |
| LIFHYB-004 | P0 | Every visual, proxy, collision, navigation, screenshot, and export derivative shall inherit applicable consent, audience, retention, and deletion dependencies. | Consent propagation test |
| LIFHYB-005 | P0 | Generated or artistically reconstructed regions and objects shall remain machine-readable and visibly labeled and shall never be reused as source evidence. | Generation-lineage test |
| LIFHYB-006 | P0 | Conflicting or alternate reconstructions shall be able to coexist without forcing one branch to appear as settled fact. | Alternate-memory scenario |
| LIFHYB-007 | P0 | A person likeness, voice, gesture, dialogue, or first-person agent shall remain disabled unless the separate consent and safety gates authorize it. | Safety policy test |
| LIFHYB-008 | P0 | Sensitive private-place data shall not be sent to an unapproved hosted conversion or editing provider. | External-provider security test |
| LIFHYB-009 | P1 | The experience shall support evidence reveal from a spatial memory or object within the current audience policy. | Evidence UX test |
| LIFHYB-010 | P1 | Collision/navigation shall be non-safety-critical and shall provide teleport, guided transition, bounded navigation, or no-entry fallback for uncertain geometry. | VR/desktop navigation test |
| LIFHYB-011 | P1 | Quiet mode, immediate safe exit, reduced motion, captions/transcripts, and non-immersive alternatives shall be available. | Accessibility and emotional-safety test |
| LIFHYB-012 | P1 | Spatialized archival, restored, reenacted, ambient, and synthesized audio shall retain distinct provenance labels. | Audio provenance test |
| LIFHYB-013 | P1 | A historical branch shall declare the source class of each material element or region at the granularity supported by the reconstruction. | Branch manifest test |
| LIFHYB-014 | P1 | Preservation export shall include open or documented assets, semantic graph, truth labels, consent policies, source hashes, and accessible fallbacks. | Independent restore test |
| LIFHYB-015 | P1 | A consent or audience change shall trigger deterministic withdrawal, redaction, regeneration, or erasure of affected derived representations. | Revocation drill |
| LIFHYB-016 | P1 | The system shall permit a source-only or evidence-first experience that does not require generated content, splats, avatars, or immersive navigation. | Minimal preservation scenario |

## 15. LiveForever acceptance demonstration

The release demonstration uses a consented family room and synthetic/cleared historical material. It shall:

1. capture or import the current room and create visual, metric, proxy, collision, and semantic layers;
2. anchor a chair, photograph, and three stories to stable entities;
3. create two evidence-backed alternate historical branches;
4. add one clearly labeled reconstructed object;
5. provide guided, teleport, and non-immersive access;
6. reveal source evidence and truth labels;
7. enforce audience restriction on one photo and story;
8. regenerate the proxy without losing memories;
9. revoke one asset's consent and prove complete derivative invalidation;
10. export and independently restore an accessible preservation package.
