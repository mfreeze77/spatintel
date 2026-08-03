from __future__ import annotations

import json
import math
import re
import struct
import tempfile
import zipfile
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from .canonical import canonical_sha256, merkle_root, new_uuid, sha256_bytes, sha256_file
from .capture_formats import encode_mesh_anchor
from .errors import ValidationError
from .temporal import db_now

CAPTURE_SCHEMA_VERSION = "1.1.0"
MAX_ARCHIVE_FILES = 200_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class CapturePackage:
    @staticmethod
    def write(destination: Path, manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
        normalized: dict[str, bytes] = {}
        for path, payload in files.items():
            safe = _safe_relative_path(path)
            if safe in normalized:
                raise ValidationError(
                    "CAPTURE_DUPLICATE_PATH", "capture package contains a duplicate path", {"path": safe}
                )
            normalized[safe] = payload
        assets = [
            {
                "path": path,
                "sha256": sha256_bytes(payload),
                "byte_count": len(payload),
                "media_type": _media_type(path),
            }
            for path, payload in sorted(normalized.items())
        ]
        body = {
            **manifest,
            "schema_version": CAPTURE_SCHEMA_VERSION,
            "assets": assets,
        }
        semantic_hash = canonical_sha256(body)
        asset_merkle = merkle_root((str(item["path"]), str(item["sha256"])) for item in assets)
        root_manifest = {**body, "semantic_hash": semantic_hash, "asset_merkle_root": asset_merkle}
        root_manifest["root_hash"] = canonical_sha256(root_manifest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", json.dumps(root_manifest, indent=2, sort_keys=True) + "\n")
            for path, payload in sorted(normalized.items()):
                archive.writestr(path, payload)
        result = CapturePackage.validate(destination)
        return {**result, "manifest": root_manifest, "path": str(destination)}

    @staticmethod
    def validate(path: Path) -> dict[str, Any]:
        if not zipfile.is_zipfile(path):
            raise ValidationError("CAPTURE_ARCHIVE_INVALID", "canonical capture package must be a ZIP archive")
        with zipfile.ZipFile(path) as archive:
            _validate_archive_metadata(archive)
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValidationError("CAPTURE_DUPLICATE_ENTRY", "archive contains duplicate entries")
            for name in names:
                _safe_relative_path(name)
            if "manifest.json" not in names:
                raise ValidationError("CAPTURE_MANIFEST_MISSING", "capture package is missing manifest.json")
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except Exception as exc:
                raise ValidationError("CAPTURE_MANIFEST_INVALID", "capture manifest is not valid JSON") from exc
            _validate_manifest_shape(manifest)
            declared_paths = [str(item.get("path", "")) for item in manifest["assets"]]
            if len(declared_paths) != len(set(declared_paths)):
                raise ValidationError("CAPTURE_ASSET_DUPLICATE", "capture asset paths must be unique")
            checks: list[dict[str, Any]] = []
            for asset in manifest["assets"]:
                asset_path = _safe_relative_path(asset["path"])
                if asset_path not in names:
                    raise ValidationError("CAPTURE_ASSET_MISSING", "manifest asset is absent", {"path": asset_path})
                payload = archive.read(asset_path)
                actual = sha256_bytes(payload)
                valid = actual == asset["sha256"] and len(payload) == asset["byte_count"]
                checks.append({"path": asset_path, "valid": valid, "sha256": actual, "byte_count": len(payload)})
                if not valid:
                    raise ValidationError(
                        "CAPTURE_ASSET_INTEGRITY", "capture asset failed size/hash verification", checks[-1]
                    )
            body = {
                key: value
                for key, value in manifest.items()
                if key not in {"semantic_hash", "asset_merkle_root", "root_hash"}
            }
            semantic_hash = canonical_sha256(body)
            if semantic_hash != manifest["semantic_hash"]:
                raise ValidationError("CAPTURE_SEMANTIC_HASH", "capture semantic manifest hash does not match")
            asset_merkle = merkle_root((item["path"], item["sha256"]) for item in manifest["assets"])
            if asset_merkle != manifest["asset_merkle_root"]:
                raise ValidationError("CAPTURE_ASSET_MERKLE", "capture asset Merkle root does not match")
            root_body = {key: value for key, value in manifest.items() if key != "root_hash"}
            if canonical_sha256(root_body) != manifest["root_hash"]:
                raise ValidationError("CAPTURE_ROOT_HASH", "capture root hash does not match")
            _validate_frames(manifest.get("frames", []), {item["path"] for item in manifest["assets"]})
            _validate_coordinate_frames(manifest.get("coordinate_frames", []))
            _validate_iphone_contract(manifest)
            return {
                "valid": True,
                "capture_id": manifest["capture_id"],
                "schema_version": manifest["schema_version"],
                "root_hash": manifest["root_hash"],
                "asset_count": len(checks),
                "frame_count": len(manifest.get("frames", [])),
                "archive_sha256": sha256_file(path),
                "checks": checks,
            }

    @staticmethod
    def inspect(path: Path) -> dict[str, Any]:
        validation = CapturePackage.validate(path)
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        return {**validation, "manifest": manifest}


def create_synthetic_room_capture(
    destination: Path,
    *,
    seed: int = 7,
    frame_count: int = 12,
    capture_source: str = "deterministic_synthetic_fixture",
    device_model: str = "synthetic-room",
) -> dict[str, Any]:
    if frame_count < 4:
        raise ValidationError("FIXTURE_FRAME_COUNT", "synthetic room fixture requires at least four frames")
    capture_id = f"synthetic-room-{seed}-{frame_count}"
    files: dict[str, bytes] = {}
    frames: list[dict[str, Any]] = []
    width, height = 16, 12
    intrinsics = [[14.0, 0.0, width / 2], [0.0, 14.0, height / 2], [0.0, 0.0, 1.0]]
    for index in range(frame_count):
        angle = 2 * math.pi * index / frame_count
        image_path = f"frames/{index:06d}/rgb.bin"
        depth_path = f"frames/{index:06d}/depth.f32"
        confidence_path = f"frames/{index:06d}/confidence.u8"
        image = bytes((index * 17 + pixel * 13 + seed) % 256 for pixel in range(width * height * 3))
        depths = [2.0 + 0.1 * math.sin(angle + pixel / 17) for pixel in range(width * height)]
        depth = b"".join(struct.pack("<f", value) for value in depths)
        confidence = bytes([2 if pixel % 7 else 1 for pixel in range(width * height)])
        files[image_path] = image
        files[depth_path] = depth
        files[confidence_path] = confidence
        pose = [
            [math.cos(angle), 0.0, math.sin(angle), 1.2 * math.sin(angle)],
            [0.0, 1.0, 0.0, 1.5],
            [-math.sin(angle), 0.0, math.cos(angle), 1.2 * math.cos(angle)],
            [0.0, 0.0, 0.0, 1.0],
        ]
        frames.append(
            {
                "frame_id": f"frame-{index:06d}",
                "timestamp_ns": 1_000_000_000 + index * 100_000_000,
                "rgb_asset": image_path,
                "rgb_encoding": "rgb8",
                "depth_asset": depth_path,
                "confidence_asset": confidence_path,
                "image_size": [width, height],
                "depth_size": [width, height],
                "depth_encoding": "float32_little_endian_meters",
                "confidence_encoding": "arkit_0_low_1_medium_2_high",
                "intrinsics": intrinsics,
                "camera_to_world": pose,
                "pose_stream": "synthetic_metric",
                "transform_convention": "row_major_camera_to_world_column_vector",
                "tracking_state": "normal",
                "limited_tracking_reason": None,
                "exposure": {"duration_s": 1 / 120, "iso": 100},
                "orientation": "landscape_right",
                "motion": {"angular_velocity_rad_s": [0.0, 0.1, 0.0], "acceleration_m_s2": [0.0, 9.80665, 0.0]},
                "quality": {"blur_score": 0.02, "coverage_hint": index / frame_count},
                "invalid_depth_preserved": True,
            }
        )
    mesh_vertices = np.asarray(
        [
            [-1.0, 0.0, -1.0],
            [1.0, 0.0, -1.0],
            [1.0, 2.5, -1.0],
            [-1.0, 2.5, -1.0],
            [-1.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 2.5, 1.0],
            [-1.0, 2.5, 1.0],
        ],
        dtype=np.float32,
    )
    mesh_faces = np.asarray(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [3, 7, 6],
            [3, 6, 2],
            [0, 4, 7],
            [0, 7, 3],
            [1, 2, 6],
            [1, 6, 5],
        ],
        dtype=np.uint32,
    )
    mesh_path = "meshes/room-anchor.sipmesh"
    files[mesh_path] = encode_mesh_anchor(mesh_vertices, mesh_faces)
    manifest = {
        "capture_id": capture_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "capture_source": capture_source,
        "device": {
            "model": device_model,
            "operating_system": "fixture",
            "app_build": "fixture-v1",
            "available_sensors": ["rgb", "lidar_depth", "confidence", "mesh", "motion"],
            "calibration_camera_identity": "fixture-camera",
        },
        "coordinate_frames": [
            {"frame_id": "world", "name": "fixture world", "convention": "right_handed_y_up_meters", "units": "meter"}
        ],
        "frames": frames,
        "motion_samples": [],
        "mesh_anchors": [
            {
                "anchor_id": "fixture-room-anchor",
                "timestamp_ns": 1_000_000_000,
                "change": "added",
                "anchor_to_world": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "geometry_asset": mesh_path,
                "geometry_encoding": "sip_mesh_anchor_v1_little_endian",
            }
        ],
        "segments": [
            {
                "segment_id": "segment-1",
                "started_at_ns": frames[0]["timestamp_ns"],
                "ended_at_ns": frames[-1]["timestamp_ns"],
                "frame_ids": [frame["frame_id"] for frame in frames],
                "overlap_control": "closed synthetic loop",
            }
        ],
        "events": [],
        "restricted_regions": [],
        "calibration": {"known_scale": True, "scale_source": "fixture_definition", "uncertainty_m": 0.001},
        "privacy": {"contains_people": False, "redactions": []},
        "provenance": {
            "generator": "sip.capture.create_synthetic_room_capture",
            "seed": seed,
            "physical_device_capture": False,
        },
    }
    return CapturePackage.write(destination, manifest, files)


def create_synthetic_iphone_capture(destination: Path, *, seed: int = 7, frame_count: int = 12) -> dict[str, Any]:
    """Create a deterministic fixture with the exact first-party iPhone contract."""
    return create_synthetic_room_capture(
        destination,
        seed=seed,
        frame_count=frame_count,
        capture_source="first_party_arkit_lidar",
        device_model="fixture-iphone-lidar",
    )


class PolyformImporter:
    """Independent adapter for the documented Polycam/polyform user-export layout."""

    def convert(self, source: Path, destination: Path) -> dict[str, Any]:
        source_archive_sha: str | None = None
        with tempfile.TemporaryDirectory(prefix="sip-polyform-") as temporary:
            root = Path(temporary) / "source"
            if source.is_file():
                if not zipfile.is_zipfile(source):
                    raise ValidationError("POLYFORM_ARCHIVE_INVALID", "raw export file is not a ZIP archive")
                source_archive_sha = sha256_file(source)
                root.mkdir(parents=True)
                with zipfile.ZipFile(source) as archive:
                    _validate_archive_metadata(archive)
                    for name in archive.namelist():
                        _safe_relative_path(name)
                    archive.extractall(root)
                root = _single_directory_root(root)
            elif source.is_dir():
                root = source
            else:
                raise ValidationError("POLYFORM_SOURCE_MISSING", "raw export source does not exist")
            camera_dir = root / "keyframes" / "cameras"
            corrected_camera_dir = root / "keyframes" / "corrected_cameras"
            image_dir = root / "keyframes" / "images"
            corrected_image_dir = root / "keyframes" / "corrected_images"
            depth_dir = root / "keyframes" / "depth"
            confidence_dir = root / "keyframes" / "confidence"
            if not camera_dir.is_dir() or not image_dir.is_dir() or not depth_dir.is_dir():
                raise ValidationError("POLYFORM_LAYOUT_INVALID", "raw export lacks cameras, images, or depth folders")
            timestamps = sorted(int(path.stem) for path in camera_dir.glob("*.json") if path.stem.isdigit())
            if not timestamps:
                raise ValidationError("POLYFORM_NO_KEYFRAMES", "raw export has no camera keyframes")
            has_corrected_cameras = corrected_camera_dir.is_dir()
            has_corrected_images = corrected_image_dir.is_dir()
            if has_corrected_cameras != has_corrected_images:
                raise ValidationError(
                    "POLYFORM_CORRECTED_STREAM_AMBIGUOUS",
                    "corrected cameras and corrected images must either both exist or both be absent",
                )
            files: dict[str, bytes] = {}
            frames: list[dict[str, Any]] = []
            warnings: list[str] = []
            optimized_count = 0
            for index, timestamp in enumerate(timestamps):
                native_camera_path = camera_dir / f"{timestamp}.json"
                native_image_path = _find_image(image_dir, timestamp)
                depth_path = depth_dir / f"{timestamp}.png"
                confidence_path = confidence_dir / f"{timestamp}.png"
                if not native_image_path or not depth_path.is_file():
                    warnings.append(f"skipped:{timestamp}:missing_image_or_depth")
                    continue
                native_camera = _load_camera(native_camera_path)
                selected_camera = native_camera
                selected_image = native_image_path
                pose_stream = "arkit_native"
                corrected_camera_path = corrected_camera_dir / f"{timestamp}.json"
                corrected_image_path = _find_image(corrected_image_dir, timestamp) if has_corrected_images else None
                if has_corrected_cameras and corrected_camera_path.is_file() and corrected_image_path:
                    selected_camera = _load_camera(corrected_camera_path)
                    selected_image = corrected_image_path
                    pose_stream = "polycam_corrected_optimized"
                    optimized_count += 1
                prefix = f"frames/{index:06d}"
                native_rgb_name = f"{prefix}/rgb_native{native_image_path.suffix.lower()}"
                files[native_rgb_name] = native_image_path.read_bytes()
                selected_rgb_name = native_rgb_name
                if selected_image != native_image_path:
                    selected_rgb_name = f"{prefix}/rgb_corrected{selected_image.suffix.lower()}"
                    files[selected_rgb_name] = selected_image.read_bytes()
                depth_name = f"{prefix}/depth.png"
                files[depth_name] = depth_path.read_bytes()
                confidence_name: str | None = None
                if confidence_path.is_file():
                    confidence_name = f"{prefix}/confidence.png"
                    files[confidence_name] = confidence_path.read_bytes()
                native_camera_name = f"{prefix}/camera_native.json"
                files[native_camera_name] = json.dumps(native_camera, sort_keys=True).encode()
                selected_camera_name = native_camera_name
                if pose_stream != "arkit_native":
                    selected_camera_name = f"{prefix}/camera_corrected.json"
                    files[selected_camera_name] = json.dumps(selected_camera, sort_keys=True).encode()
                frames.append(
                    {
                        "frame_id": f"polyform-{timestamp}",
                        "timestamp_ns": timestamp * 1_000,
                        "rgb_asset": selected_rgb_name,
                        "native_rgb_asset": native_rgb_name,
                        "depth_asset": depth_name,
                        "confidence_asset": confidence_name,
                        "camera_metadata_asset": selected_camera_name,
                        "native_camera_metadata_asset": native_camera_name,
                        "image_size": [int(selected_camera["width"]), int(selected_camera["height"])],
                        "depth_encoding": "uint16_png_millimeters",
                        "confidence_encoding": "polyform_0_low_127_medium_255_high" if confidence_name else None,
                        "intrinsics": [
                            [selected_camera["fx"], 0.0, selected_camera["cx"]],
                            [0.0, selected_camera["fy"], selected_camera["cy"]],
                            [0.0, 0.0, 1.0],
                        ],
                        "camera_to_world": selected_camera["camera_to_world"],
                        "native_camera_to_world": native_camera["camera_to_world"],
                        "pose_stream": pose_stream,
                        "tracking_state": "not_exported",
                        "quality": {"blur_score": selected_camera.get("blur_score")},
                    }
                )
            if not frames:
                raise ValidationError(
                    "POLYFORM_NO_VALID_FRAMES", "raw export contains no complete image/camera/depth frame"
                )
            for optional in [
                "raw.glb",
                "raw.gltf",
                "mesh.obj",
                "mesh_info.json",
                "anchors.json",
                "thumbnail.jpg",
                "polycam.mp4",
            ]:
                path = root / optional
                if path.is_file():
                    files[f"source/{optional}"] = path.read_bytes()
            manifest = {
                "capture_id": new_uuid(),
                "created_at": db_now().isoformat(),
                "capture_source": "polycam_polyform_compatible_raw_export",
                "coordinate_frames": [
                    {
                        "frame_id": "arkit-gravity",
                        "name": "Polyform ARKit gravity-aligned frame",
                        "convention": "right_handed_y_up_minus_z_initial_view",
                        "units": "meter",
                    }
                ],
                "frames": frames,
                "motion_samples": [],
                "mesh_anchors": [],
                "restricted_regions": [],
                "calibration": {"known_scale": True, "scale_source": "arkit_lidar", "uncertainty_m": None},
                "privacy": {"review_required": True, "redactions": []},
                "provenance": {
                    "adapter": "sip.PolyformImporter",
                    "source_archive_sha256": source_archive_sha,
                    "proprietary_application_dependency": False,
                    "format_reference_only": True,
                },
            }
            package = CapturePackage.write(destination, manifest, files)
            report = {
                "source_archive_sha256": source_archive_sha,
                "frames_discovered": len(timestamps),
                "frames_converted": len(frames),
                "optimized_frames": optimized_count,
                "native_frames": len(frames) - optimized_count,
                "selected_pose_policy": "corrected_when_complete_else_native_arkit",
                "warnings": warnings,
                "package_root_hash": package["root_hash"],
            }
            report_path = destination.with_suffix(destination.suffix + ".conversion-report.json")
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            return {**package, "conversion_report": report, "conversion_report_path": str(report_path)}


class IPhoneCaptureDirectoryImporter:
    """Convert the first-party iOS capture directory into canonical `.sipcapture`."""

    def convert(self, source: Path, destination: Path) -> dict[str, Any]:
        root = source.resolve()
        manifest_path = root / "manifest.json"
        if not root.is_dir() or not manifest_path.is_file():
            raise ValidationError("IPHONE_CAPTURE_DIRECTORY", "iPhone capture directory or manifest.json is missing")
        manifest_bytes = manifest_path.read_bytes()
        try:
            source_manifest = json.loads(manifest_bytes)
        except Exception as exc:
            raise ValidationError("IPHONE_CAPTURE_MANIFEST", "iPhone manifest is not valid JSON") from exc
        if source_manifest.get("schema") != "sip.cscp":
            raise ValidationError("IPHONE_CAPTURE_SCHEMA", "iPhone directory has an unsupported package schema")
        source_root_hash = source_manifest.get("rootHash")
        source_rootless = {key: value for key, value in source_manifest.items() if key != "rootHash"}
        if not isinstance(source_root_hash, str) or not _iphone_root_hash_valid(
            manifest_bytes,
            source_rootless,
            source_root_hash,
        ):
            raise ValidationError("IPHONE_CAPTURE_ROOT_HASH", "iPhone directory manifest root hash does not verify")
        asset_records = source_manifest.get("assets")
        frame_records = source_manifest.get("frames")
        if not isinstance(asset_records, list) or not isinstance(frame_records, list):
            raise ValidationError("IPHONE_CAPTURE_RECORDS", "iPhone manifest assets and frames must be arrays")
        assets_by_id: dict[str, dict[str, Any]] = {}
        files: dict[str, bytes] = {"source/iphone-manifest.json": manifest_path.read_bytes()}
        for record in asset_records:
            asset_id = str(record.get("assetID", ""))
            relative = _safe_relative_path(str(record.get("relativePath", "")))
            if not asset_id or asset_id in assets_by_id:
                raise ValidationError("IPHONE_CAPTURE_ASSET_ID", "iPhone asset identifiers must be present and unique")
            path = (root / relative).resolve()
            if root not in path.parents or not path.is_file():
                raise ValidationError(
                    "IPHONE_CAPTURE_ASSET_MISSING", "iPhone asset is missing or outside the package", {"path": relative}
                )
            payload = path.read_bytes()
            if len(payload) != int(record.get("byteCount", -1)) or sha256_bytes(payload) != record.get("sha256"):
                raise ValidationError(
                    "IPHONE_CAPTURE_ASSET_INTEGRITY",
                    "iPhone asset failed byte-count or hash validation",
                    {"path": relative},
                )
            assets_by_id[asset_id] = record
            files[relative] = payload

        frames: list[dict[str, Any]] = []
        mesh_anchors: list[dict[str, Any]] = []
        motion_by_timestamp: dict[int, dict[str, Any]] = {}
        for raw in frame_records:
            image = _iphone_asset_path(assets_by_id, raw.get("imageAssetID"), "image")
            depth = _iphone_optional_asset_path(assets_by_id, raw.get("depthAssetID"), "depth")
            confidence = _iphone_optional_asset_path(assets_by_id, raw.get("confidenceAssetID"), "confidence")
            resolution = raw.get("resolution", {})
            depth_resolution = raw.get("depthResolution")
            motion_samples = raw.get("motionSamples", [])
            for sample in motion_samples:
                timestamp = int(sample["timestampNanoseconds"])
                motion_by_timestamp[timestamp] = {
                    "timestamp_ns": timestamp,
                    "clock_domain": "system_uptime_monotonic",
                    "acceleration_m_s2": sample["acceleration"],
                    "angular_velocity_rad_s": sample["rotationRate"],
                    "attitude_quaternion_xyzw": sample["attitudeQuaternion"],
                }
            latest_motion = motion_samples[-1] if motion_samples else {}
            frame = {
                "frame_id": str(raw["frameID"]),
                "timestamp_ns": int(raw["timestampNanoseconds"]),
                "rgb_asset": image,
                "rgb_encoding": str(raw.get("imageEncoding", "bgra8")),
                "depth_asset": depth,
                "confidence_asset": confidence,
                "image_size": [int(resolution["width"]), int(resolution["height"])],
                "depth_size": (
                    [int(depth_resolution["width"]), int(depth_resolution["height"])]
                    if depth_resolution is not None
                    else None
                ),
                "depth_encoding": raw.get("depthEncoding"),
                "confidence_encoding": raw.get("confidenceEncoding"),
                "intrinsics": _column_major_matrix(raw["intrinsics"], 3),
                "camera_to_world": _column_major_matrix(raw["cameraTransform"], 4),
                "pose_stream": "arkit_native",
                "transform_convention": "row_major_camera_to_world_column_vector",
                "tracking_state": _swift_enum(raw["trackingState"]),
                "limited_tracking_reason": _swift_optional_enum(raw.get("limitedTrackingReason")),
                "exposure": {
                    "duration_s": float(raw["exposure"]["durationSeconds"]),
                    "iso": float(raw["exposure"]["iso"]),
                    "target_offset": float(raw["exposure"]["exposureTargetOffset"]),
                },
                "orientation": _snake_case(str(raw.get("orientation", "unknown"))),
                "motion": {
                    "angular_velocity_rad_s": latest_motion.get("rotationRate", [0.0, 0.0, 0.0]),
                    "acceleration_m_s2": latest_motion.get("acceleration", [0.0, 0.0, 0.0]),
                },
                "quality": _iphone_quality(raw.get("qualitySignals")),
                "privacy_region_ids": raw.get("privacyRegionIDs", []),
                "invalid_depth_preserved": bool(raw.get("invalidDepthPreserved", False)),
                "maximum_depth_m": 5.0,
            }
            frames.append(frame)
            for observation in raw.get("meshObservations", []):
                geometry = _iphone_optional_asset_path(
                    assets_by_id,
                    observation.get("geometryAssetID"),
                    "mesh geometry",
                )
                mesh_anchors.append(
                    {
                        "anchor_id": str(observation["anchorID"]),
                        "timestamp_ns": frame["timestamp_ns"],
                        "change": _swift_enum(observation["change"]),
                        "anchor_to_world": _column_major_matrix(observation["transform"], 4),
                        "geometry_asset": geometry,
                        "geometry_encoding": None if geometry is None else "sip_mesh_anchor_v1_little_endian",
                    }
                )
        for observation in source_manifest.get("meshObservations", []):
            geometry = _iphone_optional_asset_path(
                assets_by_id,
                observation.get("geometryAssetID"),
                "mesh geometry",
            )
            mesh_anchors.append(
                {
                    "anchor_id": str(observation["anchorID"]),
                        "timestamp_ns": int(
                            observation.get("timestampNanoseconds", source_manifest["endTimeNanoseconds"])
                        ),
                    "change": _swift_enum(observation["change"]),
                    "anchor_to_world": _column_major_matrix(observation["transform"], 4),
                    "geometry_asset": geometry,
                    "geometry_encoding": None if geometry is None else "sip_mesh_anchor_v1_little_endian",
                }
            )
        mesh_anchors = list(
            {
                (item["anchor_id"], item["timestamp_ns"], item["change"], item["geometry_asset"]): item
                for item in mesh_anchors
            }.values()
        )
        device = source_manifest.get("device", {})
        coordinate_frames = [
            {
                "frame_id": str(item["frameID"]),
                "parent_frame_id": item.get("parentFrameID"),
                "name": str(item["frameID"]),
                "convention": str(item["convention"]),
                "units": str(item["units"]),
                "transform_to_parent": (
                    _column_major_matrix(item["transformToParent"], 4)
                    if item.get("transformToParent") is not None
                    else None
                ),
            }
            for item in source_manifest.get("coordinateFrames", [])
        ]
        segments = [
            {
                "segment_id": str(item["segmentID"]),
                "started_at_ns": int(item["startedAtNanoseconds"]),
                "ended_at_ns": int(item["endedAtNanoseconds"]),
                "frame_ids": [str(value) for value in item["frameIDs"]],
                "overlap_control": str(item["overlapControl"]),
            }
            for item in source_manifest.get("segments", [])
        ]
        manifest = {
            "capture_id": str(source_manifest["sessionID"]),
            "created_at": db_now().isoformat(),
            "capture_source": "first_party_arkit_lidar",
            "device": {
                "model": str(device["model"]),
                "operating_system": str(device["operatingSystem"]),
                "app_build": str(device["appBuild"]),
                "available_sensors": [_snake_case(str(value)) for value in device["availableSensors"]],
                "calibration_camera_identity": str(device["calibrationCameraIdentity"]),
            },
            "tenant_id": source_manifest.get("tenantID"),
            "project_id": source_manifest.get("projectID"),
            "coordinate_frames": coordinate_frames,
            "segments": segments,
            "frames": frames,
            "motion_samples": [motion_by_timestamp[key] for key in sorted(motion_by_timestamp)],
            "mesh_anchors": mesh_anchors,
            "events": [
                {
                    "timestamp_ns": int(item["timestampNanoseconds"]),
                    "event": str(item["event"]),
                    "details": item.get("details", {}),
                }
                for item in source_manifest.get("events", [])
            ],
            "restricted_regions": [],
            "calibration": {
                "known_scale": True,
                "scale_source": "arkit_lidar",
                "camera_identity": str(device["calibrationCameraIdentity"]),
                "uncertainty_m": None,
            },
            "privacy": {
                "review_required": any(frame["privacy_region_ids"] for frame in frames),
                "redactions": [],
                "consent_context": source_manifest.get("policy", {}).get("consentContext"),
            },
            "source_asset_records": asset_records,
            "provenance": {
                "adapter": "sip.IPhoneCaptureDirectoryImporter/v1",
                "source_adapter": source_manifest.get("sourceAdapter"),
                "source_manifest_sha256": sha256_file(manifest_path),
                "source_root_hash": source_manifest.get("rootHash"),
                "journal_root_hash": source_manifest.get("journalRootHash"),
                "signature_status": source_manifest.get("signatureStatus"),
                "capture_origin_claim": "first_party_ios_directory",
                "physical_device_evidence": "unverified",
            },
        }
        result = CapturePackage.write(destination, manifest, files)
        return {**result, "source_directory": str(root), "source_manifest_sha256": sha256_file(manifest_path)}


def _iphone_asset_path(records: dict[str, dict[str, Any]], asset_id: Any, role: str) -> str:
    value = str(asset_id or "")
    if value not in records:
        raise ValidationError(
            "IPHONE_CAPTURE_ASSET_REFERENCE", f"iPhone {role} references an unknown asset", {"asset_id": value}
        )
    return _safe_relative_path(str(records[value]["relativePath"]))


def _iphone_root_hash_valid(raw_manifest: bytes, rootless: dict[str, Any], expected: str) -> bool:
    if canonical_sha256(rootless) == expected:
        return True
    # Foundation's sorted JSON is already the byte stream Swift hashed. Removing
    # the one top-level rootHash member avoids cross-runtime float rendering drift.
    fragment = b',"rootHash":"' + expected.encode("ascii", errors="ignore") + b'"'
    if raw_manifest.count(fragment) != 1:
        return False
    return bool(sha256_bytes(raw_manifest.replace(fragment, b"", 1)) == expected)


def _iphone_optional_asset_path(records: dict[str, dict[str, Any]], asset_id: Any, role: str) -> str | None:
    return None if asset_id is None else _iphone_asset_path(records, asset_id, role)


def _column_major_matrix(value: Any, size: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != size * size:
        raise ValidationError("IPHONE_CAPTURE_MATRIX", f"matrix must contain {size * size} column-major values")
    matrix = [[float(value[column * size + row]) for column in range(size)] for row in range(size)]
    if not all(math.isfinite(item) for row in matrix for item in row):
        raise ValidationError("IPHONE_CAPTURE_MATRIX", "matrix contains non-finite values")
    return matrix


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _swift_enum(value: Any) -> str:
    return _snake_case(str(value))


def _swift_optional_enum(value: Any) -> str | None:
    return None if value is None else _swift_enum(value)


def _iphone_quality(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "not_recorded"}
    return {
        "blur_score": float(value["blur"]),
        "exposure_clipping_fraction": float(value["exposureClippingFraction"]),
        "angular_velocity_rad_s": float(value["angularVelocityRadiansPerSecond"]),
        "depth_coverage": float(value["depthCoverage"]),
        "viewpoint_diversity": float(value["viewpointDiversity"]),
        "weak_surface_fraction": float(value["weakSurfaceFraction"]),
        "calculation_version": value.get("calculationVersion", "sip.iphone-frame-quality/v1"),
        "known_blind_spots": value.get("knownBlindSpots", []),
    }


def _validate_manifest_shape(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "capture_id",
        "capture_source",
        "frames",
        "assets",
        "semantic_hash",
        "asset_merkle_root",
        "root_hash",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValidationError("CAPTURE_MANIFEST_FIELDS", "capture manifest lacks required fields", {"missing": missing})
    version = str(manifest["schema_version"])
    try:
        major = int(version.split(".")[0])
    except Exception as exc:
        raise ValidationError("CAPTURE_SCHEMA_VERSION", "capture schema version is invalid") from exc
    if major > int(CAPTURE_SCHEMA_VERSION.split(".")[0]):
        raise ValidationError("CAPTURE_FUTURE_SCHEMA", "capture package uses an unsupported future major schema")
    if not isinstance(manifest["assets"], list) or not isinstance(manifest["frames"], list):
        raise ValidationError("CAPTURE_MANIFEST_TYPES", "capture assets and frames must be arrays")


def _validate_frames(frames: list[dict[str, Any]], asset_paths: set[str]) -> None:
    timestamps: list[int] = []
    frame_ids: set[str] = set()
    for frame in frames:
        required = {"frame_id", "timestamp_ns", "rgb_asset", "intrinsics", "camera_to_world", "pose_stream"}
        missing = sorted(required - frame.keys())
        if missing:
            raise ValidationError(
                "CAPTURE_FRAME_FIELDS",
                "capture frame lacks required fields",
                {"frame": frame.get("frame_id"), "missing": missing},
            )
        if frame["frame_id"] in frame_ids:
            raise ValidationError("CAPTURE_FRAME_DUPLICATE", "capture frame identifiers must be unique")
        frame_ids.add(frame["frame_id"])
        timestamp = int(frame["timestamp_ns"])
        timestamps.append(timestamp)
        for key in ["rgb_asset", "depth_asset", "confidence_asset", "camera_metadata_asset"]:
            value = frame.get(key)
            if value and value not in asset_paths:
                raise ValidationError(
                    "CAPTURE_FRAME_ASSET_REFERENCE",
                    "capture frame references an undeclared asset",
                    {"frame": frame["frame_id"], "path": value},
                )
        intrinsics = frame["intrinsics"]
        if len(intrinsics) != 3 or any(len(row) != 3 for row in intrinsics):
            raise ValidationError("CAPTURE_INTRINSICS", "camera intrinsics must be a 3x3 matrix")
        transform = frame["camera_to_world"]
        if len(transform) != 4 or any(len(row) != 4 for row in transform) or transform[3] != [0.0, 0.0, 0.0, 1.0]:
            raise ValidationError("CAPTURE_EXTRINSICS", "camera pose must be a homogeneous 4x4 matrix")
        flat = [float(item) for row in transform for item in row]
        if not all(math.isfinite(item) for item in flat):
            raise ValidationError("CAPTURE_NONFINITE", "camera pose contains a non-finite value")
        for key in ["image_size", "depth_size"]:
            if key in frame and frame[key] is not None:
                dimensions = frame[key]
                if (
                    not isinstance(dimensions, list)
                    or len(dimensions) != 2
                    or any(int(value) <= 0 for value in dimensions)
                ):
                    raise ValidationError("CAPTURE_DIMENSIONS", f"{key} must contain positive width and height")
    if any(current <= previous for previous, current in pairwise(timestamps)):
        raise ValidationError("CAPTURE_TIMESTAMPS", "capture frame timestamps must be strictly increasing")


def _validate_coordinate_frames(frames: list[dict[str, Any]]) -> None:
    identifiers = [str(frame.get("frame_id", "")) for frame in frames]
    if not identifiers or any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValidationError("CAPTURE_COORDINATE_FRAMES", "coordinate frame identifiers must be present and unique")
    parents = {str(frame["frame_id"]): frame.get("parent_frame_id") for frame in frames}
    for frame_id, parent in parents.items():
        if parent is not None and parent not in parents:
            raise ValidationError(
                "CAPTURE_COORDINATE_PARENT", "coordinate frame references an unknown parent", {"frame_id": frame_id}
            )
        visited: set[str] = set()
        current: str | None = frame_id
        while current is not None:
            if current in visited:
                raise ValidationError("CAPTURE_COORDINATE_CYCLE", "coordinate frame graph contains a cycle")
            visited.add(current)
            current = parents[current]


def _validate_iphone_contract(manifest: dict[str, Any]) -> None:
    if manifest.get("capture_source") != "first_party_arkit_lidar":
        return
    required = {
        "device",
        "segments",
        "motion_samples",
        "mesh_anchors",
        "events",
        "calibration",
        "privacy",
        "provenance",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValidationError(
            "CAPTURE_IPHONE_FIELDS", "iPhone package lacks required synchronized records", {"missing": missing}
        )
    device_required = {"model", "operating_system", "app_build", "available_sensors", "calibration_camera_identity"}
    device_missing = sorted(device_required - set(manifest["device"]))
    if device_missing:
        raise ValidationError(
            "CAPTURE_IPHONE_DEVICE", "iPhone device record is incomplete", {"missing": device_missing}
        )
    frame_required = {
        "rgb_encoding",
        "image_size",
        "tracking_state",
        "limited_tracking_reason",
        "exposure",
        "orientation",
        "transform_convention",
        "invalid_depth_preserved",
    }
    for frame in manifest["frames"]:
        missing_frame = sorted(frame_required - set(frame))
        if missing_frame:
            raise ValidationError(
                "CAPTURE_IPHONE_FRAME_FIELDS",
                "iPhone frame lacks required sensor interpretation metadata",
                {"frame": frame.get("frame_id"), "missing": missing_frame},
            )
        if frame.get("depth_asset"):
            depth_required = {"depth_size", "depth_encoding", "confidence_encoding"}
            missing_depth = sorted(depth_required - set(frame))
            if missing_depth:
                raise ValidationError(
                    "CAPTURE_IPHONE_DEPTH_FIELDS", "iPhone depth metadata is incomplete", {"missing": missing_depth}
                )
        if frame.get("invalid_depth_preserved") is not True:
            raise ValidationError("CAPTURE_IPHONE_DEPTH_SEMANTICS", "iPhone depth must preserve invalid values")


def _validate_archive_metadata(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_FILES:
        raise ValidationError("ARCHIVE_FILE_COUNT", "archive contains too many files")
    total = 0
    for info in infos:
        total += info.file_size
        if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValidationError("ARCHIVE_UNCOMPRESSED_SIZE", "archive expands beyond the configured safety limit")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ValidationError(
                "ARCHIVE_COMPRESSION_RATIO", "archive entry has a suspicious compression ratio", {"path": info.filename}
            )


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts or any(part in {"", "."} for part in path.parts):
        raise ValidationError("ARCHIVE_PATH_UNSAFE", "archive path is unsafe", {"path": value})
    return str(path)


def _single_directory_root(root: Path) -> Path:
    entries = [item for item in root.iterdir() if item.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


def _load_camera(path: Path) -> dict[str, Any]:
    try:
        camera = json.loads(path.read_text())
    except Exception as exc:
        raise ValidationError(
            "POLYFORM_CAMERA_INVALID", "camera metadata is invalid JSON", {"path": str(path)}
        ) from exc
    required = ["fx", "fy", "cx", "cy", "width", "height"] + [
        f"t_{row}{column}" for row in range(3) for column in range(4)
    ]
    missing = [key for key in required if key not in camera]
    if missing:
        raise ValidationError(
            "POLYFORM_CAMERA_FIELDS", "camera metadata lacks required values", {"path": str(path), "missing": missing}
        )
    transform = [[float(camera[f"t_{row}{column}"]) for column in range(4)] for row in range(3)] + [
        [0.0, 0.0, 0.0, 1.0]
    ]
    return {
        "fx": float(camera["fx"]),
        "fy": float(camera["fy"]),
        "cx": float(camera["cx"]),
        "cy": float(camera["cy"]),
        "width": int(camera["width"]),
        "height": int(camera["height"]),
        "blur_score": float(camera["blur_score"]) if camera.get("blur_score") is not None else None,
        "camera_to_world": transform,
    }


def _find_image(folder: Path, timestamp: int) -> Path | None:
    for suffix in [".jpg", ".jpeg", ".png", ".heic"]:
        candidate = folder / f"{timestamp}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _media_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".json": "application/json",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".mp4": "video/mp4",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".obj": "model/obj",
        ".f32": "application/vnd.sip.depth-f32",
        ".u8": "application/vnd.sip.confidence-u8",
        ".sipmesh": "application/vnd.sip.mesh-anchor-v1",
        ".bin": "application/octet-stream",
    }.get(suffix, "application/octet-stream")
