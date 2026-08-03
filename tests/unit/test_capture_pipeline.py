from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from sip.canonical import canonical_sha256
from sip.capture import CapturePackage, IPhoneCaptureDirectoryImporter, create_synthetic_iphone_capture
from sip.capture_formats import decode_mesh_anchor, encode_mesh_anchor
from sip.capture_pipeline import reconstruct_capture_package, reconstruct_to_scene_bundle
from sip.errors import ValidationError


@pytest.mark.unit
def test_iphone_mesh_anchor_binary_round_trip_is_exact() -> None:
    vertices = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    normals = np.asarray([[0, 0, 1]] * 3, dtype=np.float32)
    faces = np.asarray([[0, 1, 2]], dtype=np.uint32)
    classifications = np.asarray([3], dtype=np.uint8)
    decoded = decode_mesh_anchor(encode_mesh_anchor(vertices, faces, normals=normals, classifications=classifications))
    assert np.array_equal(decoded["vertices"], vertices)
    assert np.array_equal(decoded["normals"], normals)
    assert np.array_equal(decoded["faces"], faces)
    assert np.array_equal(decoded["classifications"], classifications)


@pytest.mark.unit
def test_first_party_iphone_fixture_satisfies_complete_capture_contract(tmp_path: Path) -> None:
    path = tmp_path / "iphone.sipcapture"
    created = create_synthetic_iphone_capture(path, frame_count=8)
    validated = CapturePackage.validate(path)
    manifest = CapturePackage.inspect(path)["manifest"]
    assert validated["root_hash"] == created["root_hash"]
    assert manifest["capture_source"] == "first_party_arkit_lidar"
    assert manifest["device"]["model"] == "fixture-iphone-lidar"
    assert manifest["frames"][0]["depth_encoding"] == "float32_little_endian_meters"
    assert manifest["frames"][0]["confidence_encoding"] == "arkit_0_low_1_medium_2_high"
    assert manifest["frames"][0]["invalid_depth_preserved"] is True
    assert manifest["mesh_anchors"][0]["geometry_encoding"] == "sip_mesh_anchor_v1_little_endian"


@pytest.mark.unit
def test_iphone_capture_reconstructs_all_authority_lanes_and_open_exports(tmp_path: Path) -> None:
    capture_path = tmp_path / "iphone.sipcapture"
    create_synthetic_iphone_capture(capture_path, frame_count=8)
    result = reconstruct_capture_package(
        capture_path,
        pixel_stride=2,
        splat_samples=128,
        lod_target_faces=12,
        seed=11,
    )
    assert result["metric"]["source"] == "arkit_mesh_anchors"
    assert result["metric"]["authority"] == "metric_unverified"
    assert result["visual"]["authority"] == "visual_non_metric"
    assert result["interaction"]["authoritative"] is False
    assert result["quality"]["watertight"] is True
    assert result["quality"]["accepted_depth_frames"] == 8
    assert result["quality"]["acceptance_state"] == "preview"
    assert result["composition"]["authority_lanes_preserved"] is True

    bundle = reconstruct_to_scene_bundle(
        capture_path,
        tmp_path / "scene",
        pixel_stride=2,
        splat_samples=128,
        lod_target_faces=12,
        seed=11,
    )
    assert bundle["roles_separate"] is True
    assert bundle["measurement_resolves_to"] == "metric.ply"
    for record in bundle["files"]:
        assert (tmp_path / "scene" / record["path"]).stat().st_size == record["byte_count"]
    viewer = json.loads((tmp_path / "scene/viewer-bundle.json").read_text(encoding="utf-8"))
    assert viewer["metric"]["authority"] == "metric_unverified"
    assert len(viewer["visual"]["positions"]) == 128


@pytest.mark.unit
def test_ios_directory_imports_into_the_same_downstream_pipeline(tmp_path: Path) -> None:
    source = tmp_path / "ios-directory"
    source.mkdir()
    canonical_path = tmp_path / "fixture-source.sipcapture"
    create_synthetic_iphone_capture(canonical_path, frame_count=8)
    canonical = CapturePackage.inspect(canonical_path)["manifest"]
    import zipfile

    with zipfile.ZipFile(canonical_path) as archive:
        frame_source = canonical["frames"][0]
        selected_paths = [frame_source["rgb_asset"], frame_source["depth_asset"], frame_source["confidence_asset"]]
        asset_records = []
        asset_ids: dict[str, str] = {}
        for index, relative in enumerate(selected_paths):
            payload = archive.read(relative)
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            asset_id = f"asset-{index}"
            asset_ids[relative] = asset_id
            asset_records.append(
                {
                    "assetID": asset_id,
                    "relativePath": relative,
                    "mediaType": "application/octet-stream",
                    "byteCount": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "creationSource": "fixture",
                    "encrypted": True,
                    "retentionClass": "evidence",
                }
            )
    camera = [frame_source["camera_to_world"][row][column] for column in range(4) for row in range(4)]
    intrinsics = [frame_source["intrinsics"][row][column] for column in range(3) for row in range(3)]
    raw_frame = {
        "frameID": "frame-1",
        "timestampNanoseconds": 1_000_000_000,
        "imageAssetID": asset_ids[frame_source["rgb_asset"]],
        "depthAssetID": asset_ids[frame_source["depth_asset"]],
        "confidenceAssetID": asset_ids[frame_source["confidence_asset"]],
        "cameraTransform": camera,
        "intrinsics": intrinsics,
        "resolution": {"width": 16, "height": 12},
        "trackingState": "normal",
        "limitedTrackingReason": None,
        "exposure": {"durationSeconds": 0.01, "iso": 100.0, "exposureTargetOffset": 0.0},
        "orientation": "landscapeRight",
        "motionSamples": [],
        "meshObservations": [],
        "privacyRegionIDs": [],
        "invalidDepthPreserved": True,
        "imageEncoding": "rgb8",
        "depthResolution": {"width": 16, "height": 12},
        "depthEncoding": "float32_little_endian_meters",
        "confidenceEncoding": "arkit_0_low_1_medium_2_high",
        "transformConvention": "arkit_column_major_camera_to_world_column_vector",
        "qualitySignals": None,
    }
    rootless = {
        "schema": "sip.cscp",
        "schemaVersion": "1.1.0",
        "sessionID": "ios-session-1",
        "tenantID": None,
        "projectID": "project-1",
        "sourceAdapter": "first-party-arkit-v1",
        "device": {
            "model": "fixture-iphone",
            "operatingSystem": "iOS fixture",
            "appBuild": "1",
            "availableSensors": ["confidence", "lidarDepth", "rgb"],
            "calibrationCameraIdentity": "back-lidar-camera",
        },
        "startTimeNanoseconds": 1_000_000_000,
        "endTimeNanoseconds": 1_000_000_001,
        "coordinateFrames": [
            {
                "frameID": "world",
                "parentFrameID": None,
                "convention": "right_handed_y_up_meters",
                "units": "meter",
                "transformToParent": None,
            }
        ],
        "segments": [
            {
                "segmentID": "segment-1",
                "startedAtNanoseconds": 1_000_000_000,
                "endedAtNanoseconds": 1_000_000_001,
                "frameIDs": ["frame-1"],
                "overlapControl": "operator overlap",
            }
        ],
        "assets": asset_records,
        "frames": [raw_frame],
        "journalRootHash": "0" * 64,
        "signatureStatus": "device_protected_unsigned",
        "policy": {
            "projectID": "project-1",
            "permittedSensors": ["confidence", "lidarDepth", "rgb"],
            "cloudTransferAllowed": False,
            "cableExportAllowed": True,
            "purgeAfterVerifiedReceiptAllowed": False,
            "consentContext": "fixture",
        },
        "unknownOptionalFields": {},
    }
    (source / "manifest.json").write_text(
        json.dumps({**rootless, "rootHash": canonical_sha256(rootless)}, sort_keys=True),
        encoding="utf-8",
    )
    output = tmp_path / "imported.sipcapture"
    converted = IPhoneCaptureDirectoryImporter().convert(source, output)
    assert converted["frame_count"] == 1
    imported = CapturePackage.inspect(output)["manifest"]
    assert imported["capture_source"] == "first_party_arkit_lidar"
    assert imported["frames"][0]["camera_to_world"] == frame_source["camera_to_world"]

    tampered = source / asset_records[0]["relativePath"]
    tampered.write_bytes(tampered.read_bytes() + b"tampered")
    with pytest.raises(ValidationError) as error:
        IPhoneCaptureDirectoryImporter().convert(source, tmp_path / "tampered.sipcapture")
    assert error.value.code == "IPHONE_CAPTURE_ASSET_INTEGRITY"
