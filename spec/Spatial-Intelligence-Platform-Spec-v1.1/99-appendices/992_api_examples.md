---
spec_id: APP-API
title: "API and Event Examples"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# API and Event Examples

The examples illustrate intended contracts. Normative schemas belong in generated OpenAPI/JSON Schema/Protobuf files in the implementation repository.

## Create a capture session

```http
POST /v1/projects/prj_01J.../capture-sessions
Authorization: Bearer <token>
Idempotency-Key: 0190d9b8-...
Content-Type: application/json

{
  "capture_profile": "construction_room_final_v1",
  "place_id": "plc_01J...",
  "source_type": "ios_first_party",
  "policy_bundle_id": "pol_01J...",
  "device": {
    "platform": "iOS",
    "device_class": "lidar_phone",
    "app_build": "1.0.0+102"
  }
}
```

```json
{
  "id": "cap_01J...",
  "project_id": "prj_01J...",
  "state": "setup",
  "upload": {
    "strategy": "content_addressed_multipart",
    "manifest_endpoint": "/v1/capture-sessions/cap_01J.../assets:authorize"
  },
  "version": 1
}
```

## Finalize a capture session

```http
POST /v1/capture-sessions/cap_01J...:finalize
Idempotency-Key: 0190d9c0-...
If-Match: "7"

{
  "package_manifest_asset_id": "ast_01J...",
  "package_root_sha256": "9f...",
  "device_signature": "base64...",
  "operator_summary": {
    "unobserved_areas": ["north ceiling above active equipment"],
    "notes": "Panel interior photographed under restricted classification."
  }
}
```

Finalization is asynchronous if deep validation or asset reconciliation is required:

```json
{
  "operation_id": "op_01J...",
  "state": "running",
  "links": {
    "self": "/v1/operations/op_01J..."
  }
}
```

## Start a processing run

```http
POST /v1/projects/prj_01J.../pipeline-runs
Idempotency-Key: 0190d9d0-...

{
  "input": {
    "capture_session_id": "cap_01J...",
    "package_root_sha256": "9f..."
  },
  "profile": "dual_reconstruction_preview_v1",
  "stages": [
    "validate",
    "metric_lane",
    "lingbot_lane",
    "pose_alignment",
    "tsdf_preview",
    "mesh_preview",
    "quality"
  ],
  "publication": "review_required",
  "budget": {
    "max_estimated_usd": 25.00
  }
}
```

Response includes estimate and blocked gates:

```json
{
  "run_id": "run_01J...",
  "state": "blocked",
  "gates": [
    {
      "code": "MODEL_RESEARCH_ONLY",
      "stage": "lingbot_lane",
      "model_manifest_id": "mdl_lingbot_long_2026_04",
      "allowed_actions": ["remove_stage", "use_research_environment"]
    }
  ],
  "cost_estimate": {
    "currency": "USD",
    "low": 3.40,
    "high": 7.80,
    "price_book_version": "aws-us-central-2026-07-26"
  }
}
```

## Operation resource

```json
{
  "id": "op_01J...",
  "type": "pipeline_run",
  "state": "running",
  "progress": {
    "stage": "pose_alignment",
    "completed_units": 5,
    "total_units": 8,
    "percent": 62.5,
    "message": "Optimizing 2,842 pose nodes and 17 loop candidates"
  },
  "warnings": [
    {
      "code": "COVERAGE_WEAK",
      "scope": {"segment_id": "seg_04", "region_id": "reg_91"},
      "message": "Ceiling region has insufficient high-confidence observations."
    }
  ],
  "cost_actual": {"currency": "USD", "amount": 2.18},
  "created_at": "2026-07-26T20:15:03Z",
  "updated_at": "2026-07-26T20:19:41Z"
}
```

## Publish a reviewed scene commit

```http
POST /v1/scenes/scn_01J.../commits/cmt_01J...:publish
Idempotency-Key: 0190d9e0-...

{
  "publication_class": "accepted_reference",
  "review": {
    "review_task_id": "rev_01J...",
    "limitations": [
      "North ceiling unobserved",
      "Door width remains scan-derived and unverified"
    ]
  }
}
```

The server rejects `verified_authoritative` unless project policy and verification evidence are satisfied.

## Spatial search

```http
POST /v1/search

{
  "project_id": "prj_01J...",
  "commit_id": "cmt_01J...",
  "query": "smoke detectors associated with AHU-3",
  "filters": {
    "entity_types": ["fire_alarm_smoke_detector"],
    "source_classes": ["observed", "verified"],
    "within": {"place_id": "lvl_02"},
    "relationships": [
      {"type": "monitors_or_controls", "target_entity_id": "eqp_ahu3"}
    ]
  },
  "include": ["evidence_summary", "saved_view"]
}
```

```json
{
  "results": [
    {
      "entity_id": "ent_01J...",
      "label": "SD-2-147",
      "source_class": "observed",
      "authority": "accepted_reference",
      "why": [
        "type matched",
        "located on Level 2",
        "accepted relationship to AHU-3",
        "supported by device photograph and FA-202 region"
      ],
      "evidence_ids": ["evd_01J...", "evd_01K..."],
      "saved_view": {"scene_id": "scn_01J...", "view_id": "view_01J..."}
    }
  ],
  "index_checkpoint": "cmt_01J..."
}
```

## Create a measurement proposal

```http
POST /v1/scenes/scn_01J.../measurements

{
  "commit_id": "cmt_01J...",
  "measurement_type": "distance",
  "geometry": {
    "frame_id": "frm_building_local",
    "points": [[12.118, 1.002, 4.550], [12.118, 1.002, 5.466]]
  },
  "source_method": "viewer_metric_mesh_pick",
  "intended_use": "estimating_reference"
}
```

```json
{
  "measurement_id": "mea_01J...",
  "value": 0.916,
  "unit": "m",
  "display": "3 ft 0.1 in",
  "class": "scan_estimate",
  "uncertainty": {"type": "estimated_95", "value": 0.022, "unit": "m"},
  "verification_state": "unverified",
  "warning": "Not approved for fabrication or installation."
}
```

## LiveForever memory assertion

```http
POST /v1/liveforever/projects/lfp_01J.../memories

{
  "title": "Christmas morning by the fireplace",
  "source_class": "first_person_recollection",
  "contributor_person_id": "per_subject",
  "time_expression": {
    "kind": "approximate_year",
    "year": 1987,
    "uncertainty_years": 1
  },
  "place_id": "plc_grandparents_living_room",
  "spatial_anchor_id": "anc_fireplace",
  "source_ranges": [
    {"evidence_id": "evd_interview_01", "start_ms": 114200, "end_ms": 168900}
  ],
  "audience_policy_id": "aud_family"
}
```

## Consent denial response

```json
{
  "error": {
    "code": "CONSENT_SCOPE_DENIED",
    "message": "This voice recording is not authorized for generated speech.",
    "trace_id": "trc_01J...",
    "retryable": false,
    "details": {
      "permitted_uses": ["private_playback", "transcription"],
      "requested_use": "voice_clone_generation"
    }
  }
}
```

## Event examples

### `CaptureSessionFinalized.v1`

```json
{
  "event_id": "evt_01J...",
  "event_type": "CaptureSessionFinalized.v1",
  "occurred_at": "2026-07-26T19:02:11Z",
  "tenant_id": "ten_01J...",
  "project_id": "prj_01J...",
  "aggregate_id": "cap_01J...",
  "trace_id": "trc_01J...",
  "producer": "capture-service@1.0.0",
  "payload": {
    "package_manifest_asset_id": "ast_01J...",
    "package_root_sha256": "9f...",
    "segment_count": 12,
    "frame_count": 2844,
    "validation_state": "accepted_with_warnings"
  }
}
```

### `SceneCommitPublished.v1`

```json
{
  "event_id": "evt_01K...",
  "event_type": "SceneCommitPublished.v1",
  "occurred_at": "2026-07-26T20:44:03Z",
  "tenant_id": "ten_01J...",
  "project_id": "prj_01J...",
  "aggregate_id": "scn_01J...",
  "payload": {
    "commit_id": "cmt_01J...",
    "parent_commit_ids": ["cmt_01I..."],
    "publication_class": "accepted_reference",
    "root_manifest_sha256": "af...",
    "review_id": "rev_01J...",
    "limitations_count": 2
  }
}
```

## Version 1.1 examples

Examples shall include creating a splat-to-proxy operation, requesting separate proxy/collision outputs, receiving a quarantined candidate, reading validation, approving/publishing, resolving a proxy hit to metric support, remapping an anchor, generating a hybrid scene-view manifest, and rejecting a prohibited external-provider request.
