---
spec_id: APP-SCHEMA
title: "Canonical Schema Examples"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Canonical Schema Examples

These compact examples show the required semantics. The implementation must split them into versioned JSON Schemas/OpenAPI/Protobuf definitions with validators and generated types.

## Canonical capture root manifest

```json
{
  "$schema": "https://sip.example/schemas/cscp/1.0/manifest.schema.json",
  "schema_version": "1.0.0",
  "package_id": "pkg_01J...",
  "session_id": "cap_01J...",
  "created_at": "2026-07-26T18:01:02.115Z",
  "finalized_at": "2026-07-26T19:02:10.432Z",
  "source": {
    "adapter": "ios_first_party",
    "adapter_version": "1.0.0",
    "native_package_asset_id": null
  },
  "device": {
    "platform": "iOS",
    "model_identifier": "REDACTABLE",
    "os_version": "26.x",
    "app_build": "1.0.0+102",
    "capabilities": ["rgb", "lidar_depth", "scene_depth_confidence", "arkit_pose", "mesh", "imu"]
  },
  "clock_domains": [
    {
      "id": "clk_arkit_monotonic",
      "kind": "monotonic",
      "unit": "seconds",
      "session_time_transform": {"scale": 1.0, "offset_seconds": 0.0, "estimated_error_ms": 0.3}
    }
  ],
  "coordinate_frames": [
    {
      "id": "frm_arkit_world_seg01",
      "kind": "session_local",
      "handedness": "right",
      "units": "m",
      "axes": {"x": "right", "y": "up_gravity_aligned", "z": "toward_initial_camera_back"}
    }
  ],
  "segments": [
    {
      "id": "seg_01",
      "frame_index_asset_id": "ast_frames_seg01",
      "events_asset_id": "ast_events_seg01",
      "local_frame_id": "frm_arkit_world_seg01",
      "start_session_ns": 0,
      "end_session_ns": 48822000000,
      "tracking_summary": {"normal_fraction": 0.982, "limited_fraction": 0.018}
    }
  ],
  "asset_index_id": "ast_asset_index",
  "policy": {
    "policy_bundle_id": "pol_01J...",
    "audio_enabled": false,
    "cloud_transfer_allowed": true,
    "default_classification": "confidential"
  },
  "root_hash": {"algorithm": "sha256-merkle-v1", "value": "9f..."},
  "signature": {"algorithm": "p256-sha256", "key_id": "devkey_01J...", "value": "base64..."}
}
```

## Frame record

```json
{
  "frame_id": "frm_00001842",
  "segment_id": "seg_01",
  "sequence": 1842,
  "timestamp": {"clock_id": "clk_arkit_monotonic", "value": 32.414992},
  "session_time_ns": 32414992000,
  "rgb_asset_id": "ast_rgb_1842",
  "depth_asset_id": "ast_depth_1842",
  "confidence_asset_id": "ast_conf_1842",
  "camera_model_id": "cam_wide_01",
  "camera_to_world": {
    "target_frame_id": "frm_arkit_world_seg01",
    "source_frame_id": "frm_camera_1842",
    "matrix_column_major": [1,0,0,0, 0,1,0,0, 0,0,1,0, 1.22,1.58,-3.04,1]
  },
  "tracking": {"state": "normal", "reason": null},
  "exposure": {"duration_s": 0.008, "iso": 160},
  "quality": {"blur": 0.12, "overexposure_fraction": 0.001, "depth_valid_fraction": 0.74},
  "privacy_region_ids": ["prv_04"]
}
```

## Pipeline run manifest

```json
{
  "run_id": "run_01J...",
  "run_schema_version": "1.0.0",
  "profile": "dual_reconstruction_final_v1",
  "input_roots": [{"kind": "cscp", "sha256": "9f..."}],
  "software": {
    "orchestrator_commit": "abc...",
    "containers": {
      "lingbot": "sha256:...",
      "optimizer": "sha256:...",
      "fusion": "sha256:..."
    }
  },
  "models": [
    {
      "model_manifest_id": "mdl_lingbot_long_2026_04",
      "checkpoint_sha256": "REQUIRED",
      "approval_snapshot_id": "map_01J..."
    }
  ],
  "parameters": {
    "lingbot": {"backend": "flashinfer", "dtype": "bf16", "mode": "windowed", "window_size": 128, "keyframe_interval": 4, "overlap_keyframes": 16},
    "fusion": {"voxel_size_m": 0.015, "truncation_m": 0.06}
  },
  "environment": {"gpu": "profile_l40s", "cuda": "12.8", "pytorch": "2.8.0"},
  "started_at": "2026-07-26T20:00:00Z",
  "completed_at": null,
  "outputs": [],
  "validation": null
}
```

## Coordinate transform edge

```json
{
  "transform_id": "trf_lingbot_to_arkit_01",
  "target_frame_id": "frm_arkit_world_seg01",
  "source_frame_id": "frm_lingbot_run01",
  "kind": "sim3",
  "target_from_source": {
    "scale": 1.0371,
    "rotation_quaternion_xyzw": [0.001, -0.012, 0.003, 0.9999],
    "translation_m": [0.118, -0.031, 0.404]
  },
  "method": "synchronized_camera_centers_ransac_then_robust_refine",
  "constraints": {"total": 402, "inliers": 377},
  "residuals": {"position_rmse_m": 0.041, "rotation_rmse_deg": 1.24},
  "uncertainty": {"status": "estimated", "covariance_asset_id": "ast_cov_01"},
  "provenance_id": "prov_01J...",
  "acceptance": "review_required"
}
```

## Scene commit

```json
{
  "commit_id": "cmt_01J...",
  "scene_id": "scn_01J...",
  "parents": ["cmt_01I..."],
  "branch": "field-observation/2026-07-26",
  "author_id": "usr_01J...",
  "message": "Publish reviewed mechanical-room field capture",
  "created_at": "2026-07-26T20:44:03Z",
  "root_manifest_asset_id": "ast_scene_manifest_01",
  "root_manifest_sha256": "af...",
  "publication_class": "accepted_reference",
  "quality_summary_id": "qlt_01J...",
  "review_id": "rev_01J...",
  "limitations": ["north ceiling unobserved", "door width unverified"],
  "signature": {"key_id": "releasekey_01", "value": "base64..."}
}
```

## Entity and revision

```json
{
  "entity": {
    "entity_id": "ent_panel_fa1",
    "project_id": "prj_01J...",
    "base_type": "physical_object",
    "type_id": "construction.fire_alarm.control_unit",
    "lifecycle": "active",
    "created_provenance_id": "prov_01J..."
  },
  "revision": {
    "entity_revision_id": "erv_01J...",
    "entity_id": "ent_panel_fa1",
    "scene_commit_id": "cmt_01J...",
    "labels": [{"value": "FA-1", "kind": "field_label"}],
    "properties": {
      "manufacturer": {"value": "Edwards", "source_class": "observed", "evidence_ids": ["evd_nameplate"]},
      "model": {"value": "EST4", "source_class": "observed", "evidence_ids": ["evd_nameplate"]}
    },
    "anchor_ids": ["anc_panel_fa1"],
    "classification": "restricted_building_system"
  }
}
```

## Assertion and evidence

```json
{
  "assertion": {
    "assertion_id": "astn_01J...",
    "subject_entity_id": "ent_panel_fa1",
    "predicate": "located_in",
    "object_entity_id": "plc_electrical_room_112",
    "source_class": "observed",
    "authority": "accepted_reference",
    "status": "active",
    "evidence_links": [
      {"evidence_id": "evd_frame_1842", "relationship": "supports"},
      {"evidence_id": "evd_drawing_fa201", "relationship": "contextualizes"}
    ]
  },
  "evidence": {
    "evidence_id": "evd_frame_1842",
    "kind": "capture_frame_region",
    "asset_id": "ast_rgb_1842",
    "region": {"type": "polygon", "normalized_xy": [[0.1,0.2],[0.4,0.2],[0.4,0.8],[0.1,0.8]]},
    "integrity_sha256": "...",
    "classification": "restricted_building_system",
    "provenance_id": "prov_..."
  }
}
```

## Measurement

```json
{
  "measurement_id": "mea_01J...",
  "measurement_type": "distance",
  "frame_id": "frm_building_local",
  "geometry": {"points": [[1.0,1.2,0.0],[1.914,1.2,0.0]]},
  "value": 0.914,
  "unit": "m",
  "measurement_class": "verified_field",
  "uncertainty": {"kind": "plus_minus", "value": 0.003, "unit": "m"},
  "method": "laser_distance_meter",
  "instrument_id": "inst_01J...",
  "calibration_record_id": "cal_01J...",
  "verified_by": "usr_01J...",
  "verified_at": "2026-07-27T14:20:00Z",
  "permitted_uses": ["estimating", "installation_reference"],
  "evidence_ids": ["evd_measure_photo", "evd_field_note"]
}
```

## LiveForever memory and consent

```json
{
  "memory_id": "mem_01J...",
  "title": "Dad's chair by the fireplace",
  "source_class": "first_person_recollection",
  "contributor_person_id": "per_subject",
  "time_expression": {"kind": "interval_approximate", "start_year": 1985, "end_year": 1990},
  "relationships": [
    {"type": "occurred_at", "entity_id": "plc_living_room"},
    {"type": "features_object", "entity_id": "obj_grandfather_chair"},
    {"type": "features_person", "entity_id": "per_dad"}
  ],
  "anchor_ids": ["anc_chair"],
  "assertion_ids": ["astn_dad_always_sat_here"],
  "evidence_ids": ["evd_interview_segment", "evd_photo_1987_04"],
  "consent_policy_id": "cns_family_private"
}
```

```json
{
  "consent_id": "cns_01J...",
  "grantor_person_id": "per_subject",
  "authority_basis": "self",
  "data_scope": ["interviews/session_01", "voice_recordings"],
  "purposes": ["private_playback", "transcription", "family_memory_experience"],
  "prohibited_purposes": ["voice_clone_generation", "public_release", "model_training"],
  "audiences": ["family_named_group"],
  "effective_at": "2026-07-26T00:00:00Z",
  "expires_at": null,
  "posthumous": {"administrator_person_id": "per_executor", "may_expand_scope": false},
  "evidence_asset_id": "ast_signed_consent",
  "status": "active"
}
```

## Model manifest

```json
{
  "model_manifest_id": "mdl_lingbot_long_2026_04",
  "provider": "Robbyant",
  "model_name": "lingbot-map-long",
  "checkpoint_sha256": "REQUIRED",
  "source": {
    "repository": "https://github.com/Robbyant/lingbot-map",
    "commit": "1f480aeb8a47a24656090d46d053115b7fe60435"
  },
  "license": {
    "code_evidence_asset_id": "lic_apache2",
    "checkpoint_evidence_asset_id": null,
    "status": "incomplete"
  },
  "approval": {
    "state": "research_hold",
    "permitted_purposes": [],
    "prohibited_purposes": ["commercial_customer_processing"],
    "approved_data_classes": ["synthetic", "consented_internal_benchmark"]
  },
  "container_digest": "sha256:...",
  "benchmark_report_id": "bench_01J..."
}
```

## Version 1.1 examples

Examples shall include `representation_asset`, `representation_family`, `representation_derivation`, `support_map`, `representation_validation_report`, `provider_manifest`, `spatial_partition`, `representation_lod`, `SpatialHit`, conversion loss report, limitations, and manual export/import receipt.
