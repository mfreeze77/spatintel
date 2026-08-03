from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from typing import Any, cast

import numpy as np
from scipy.spatial import cKDTree

from .canonical import canonical_sha256, sha256_file
from .capture import CapturePackage
from .capture_formats import decode_mesh_anchor
from .errors import ValidationError
from .geometry import cleanup_mesh, compose_mesh_representations, convex_mesh, unproject_depth, voxel_fuse


def reconstruct_capture_package(
    package_path: Path,
    *,
    voxel_size_m: float = 0.03,
    frame_stride: int = 1,
    pixel_stride: int = 2,
    splat_samples: int = 20_000,
    lod_target_faces: int = 20_000,
    seed: int = 0,
) -> dict[str, Any]:
    """Reconstruct a validated local capture into separated output lanes."""
    if voxel_size_m <= 0 or frame_stride <= 0 or pixel_stride <= 0:
        raise ValidationError("CAPTURE_PIPELINE_CONFIGURATION", "voxel and stride settings must be positive")
    inspection = CapturePackage.inspect(package_path)
    manifest = inspection["manifest"]
    point_sets: list[np.ndarray] = []
    weight_sets: list[np.ndarray] = []
    color_sets: list[np.ndarray] = []
    accepted_frames = 0
    rejected_tracking_frames = 0
    depth_pixels = 0
    valid_depth_pixels = 0
    with zipfile.ZipFile(package_path) as archive:
        for frame in manifest["frames"][::frame_stride]:
            if frame.get("tracking_state") != "normal":
                rejected_tracking_frames += 1
                continue
            depth_path = frame.get("depth_asset")
            if not depth_path:
                continue
            depth = _decode_depth(archive.read(depth_path), frame)
            confidence = (
                _decode_confidence(archive.read(frame["confidence_asset"]), frame)
                if frame.get("confidence_asset")
                else None
            )
            depth = _preserve_depth_edges(depth)
            intrinsics = _matrix(frame["intrinsics"], 3, "intrinsics")
            image_width, image_height = _dimensions(frame.get("image_size"), "image_size")
            depth_width, depth_height = _dimensions(frame.get("depth_size"), "depth_size")
            intrinsics = intrinsics.copy()
            intrinsics[0, :] *= depth_width / image_width
            intrinsics[1, :] *= depth_height / image_height
            intrinsics[2, :] = [0.0, 0.0, 1.0]
            pose = _matrix(frame["camera_to_world"], 4, "camera_to_world")
            points, weights = unproject_depth(
                depth,
                intrinsics,
                pose,
                confidence=confidence,
                minimum_confidence=1,
                max_depth_m=float(frame.get("maximum_depth_m", 5.0)),
                stride=pixel_stride,
            )
            if not len(points):
                continue
            motion_scale = _motion_weight(frame)
            weights *= motion_scale
            colors = _colors_for_depth_samples(archive, frame, depth, confidence, pixel_stride=pixel_stride)
            if len(colors) != len(points):
                raise ValidationError(
                    "CAPTURE_COLOR_ALIGNMENT", "RGB samples do not align with unprojected depth observations"
                )
            point_sets.append(points)
            weight_sets.append(weights)
            color_sets.append(colors)
            accepted_frames += 1
            depth_pixels += int(depth.size)
            valid_depth_pixels += int(np.count_nonzero(np.isfinite(depth) & (depth > 0)))
        if not point_sets:
            raise ValidationError("CAPTURE_DEPTH_EMPTY", "capture has no usable normally tracked depth observations")
        fused = voxel_fuse(point_sets, weight_sets, voxel_size_m=voxel_size_m)
        source_points = np.vstack(point_sets)
        source_colors = np.vstack(color_sets)
        _, nearest = cKDTree(source_points).query(fused["points"], k=1)
        fused_colors = source_colors[np.asarray(nearest, dtype=np.int64)]
        anchor_mesh = _active_anchor_mesh(archive, manifest)

    limitations: list[str] = []
    if anchor_mesh is not None:
        metric_vertices = anchor_mesh["vertices"]
        metric_faces = anchor_mesh["faces"]
        _, color_indices = cKDTree(fused["points"]).query(metric_vertices, k=1)
        metric_colors = fused_colors[np.asarray(color_indices, dtype=np.int64)]
        metric_source = "arkit_mesh_anchors"
    else:
        hull_input = _bounded_hull_points(fused["points"])
        fallback = convex_mesh(hull_input)
        metric_vertices = fallback["vertices"]
        metric_faces = fallback["faces"]
        _, color_indices = cKDTree(fused["points"]).query(metric_vertices, k=1)
        metric_colors = fused_colors[np.asarray(color_indices, dtype=np.int64)]
        metric_source = "depth_convex_hull_fallback"
        limitations.append("No ARKit mesh anchors were present; the fallback hull may bridge unobserved space.")

    target_faces = max(4, min(lod_target_faces, max(len(metric_faces), 4)))
    composite = compose_mesh_representations(
        metric_vertices,
        metric_faces,
        vertex_colors=metric_colors,
        splat_samples=splat_samples,
        lod_target_faces=target_faces,
        seed=seed,
    )
    quality = {
        **composite["quality"],
        "capture_root_hash": inspection["root_hash"],
        "capture_frame_count": inspection["frame_count"],
        "accepted_depth_frames": accepted_frames,
        "rejected_tracking_frames": rejected_tracking_frames,
        "depth_valid_fraction": float(valid_depth_pixels / max(depth_pixels, 1)),
        "fused_voxel_count": len(fused["points"]),
        "mean_fused_uncertainty_m": float(np.mean(fused["uncertainty_m"])),
        "metric_source": metric_source,
        "acceptance_state": "preview",
        "physical_device_validation": "required",
        "limitations": limitations,
    }
    composite["quality"] = quality
    composite["metric"]["source"] = metric_source
    composite["metric"]["vertex_colors"] = metric_colors
    composite["metric"]["fused_observations"] = {
        "points": fused["points"],
        "uncertainty_m": fused["uncertainty_m"],
        "weights": fused["weights"],
    }
    composite["provenance"] = {
        "capture_sha256": inspection["archive_sha256"],
        "capture_root_hash": inspection["root_hash"],
        "pipeline": "sip.capture_pipeline.reconstruct_capture_package/v1",
        "parameters": {
            "voxel_size_m": voxel_size_m,
            "frame_stride": frame_stride,
            "pixel_stride": pixel_stride,
            "splat_samples": splat_samples,
            "lod_target_faces": lod_target_faces,
            "seed": seed,
        },
    }
    return cast(dict[str, Any], composite)


def write_scene_bundle(result: dict[str, Any], destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    metric_path = destination / "metric.ply"
    visual_path = destination / "visual.ply"
    interaction_path = destination / "interaction.ply"
    viewer_path = destination / "viewer-bundle.json"
    quality_path = destination / "quality.json"
    _write_mesh_ply(
        metric_path,
        np.asarray(result["metric"]["vertices"]),
        np.asarray(result["metric"]["faces"]),
        colors=np.asarray(result["metric"].get("vertex_colors", [])),
    )
    _write_points_ply(
        visual_path,
        np.asarray(result["visual"]["positions"]),
        colors=np.asarray(result["visual"].get("colors")) if "colors" in result["visual"] else None,
    )
    _write_mesh_ply(
        interaction_path,
        np.asarray(result["interaction"]["vertices"]),
        np.asarray(result["interaction"]["faces"]),
    )
    quality_path.write_text(
        json.dumps(_json_values(result["quality"]), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    viewer = {
        "schema": "spatintel.viewer-bundle/v1",
        "metric": {
            "vertices": _json_values(result["metric"]["vertices"]),
            "faces": _json_values(result["metric"]["faces"]),
            "colors": _json_values(result["metric"].get("vertex_colors", [])),
            "authority": result["metric"]["authority"],
        },
        "visual": {
            "positions": _json_values(result["visual"]["positions"]),
            "colors": _json_values(result["visual"].get("colors", [])),
            "authority": result["visual"]["authority"],
        },
        "interaction": {
            "vertices": _json_values(result["interaction"]["vertices"]),
            "faces": _json_values(result["interaction"]["faces"]),
            "authority": "derived_non_authoritative",
        },
        "quality": _json_values(result["quality"]),
        "provenance": _json_values(result["provenance"]),
    }
    viewer["bundle_hash"] = canonical_sha256(viewer)
    viewer_path.write_text(json.dumps(viewer, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    files = [metric_path, visual_path, interaction_path, viewer_path, quality_path]
    manifest = {
        "schema": "spatintel.scene-bundle/v1",
        "roles_separate": True,
        "measurement_resolves_to": "metric.ply",
        "files": [
            {"path": path.name, "sha256": sha256_file(path), "byte_count": path.stat().st_size} for path in files
        ],
        "quality": _json_values(result["quality"]),
        "provenance": _json_values(result["provenance"]),
    }
    manifest["root_hash"] = canonical_sha256(manifest)
    manifest_path = destination / "scene-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "output_directory": str(destination), "manifest_path": str(manifest_path)}


def reconstruct_to_scene_bundle(package_path: Path, destination: Path, **parameters: Any) -> dict[str, Any]:
    return write_scene_bundle(reconstruct_capture_package(package_path, **parameters), destination)


def _decode_depth(payload: bytes, frame: dict[str, Any]) -> np.ndarray:
    if frame.get("depth_encoding") != "float32_little_endian_meters":
        raise ValidationError(
            "CAPTURE_DEPTH_ENCODING", "the local reference path requires float32 little-endian meter depth"
        )
    width, height = _dimensions(frame.get("depth_size"), "depth_size")
    expected = width * height * 4
    if len(payload) != expected:
        raise ValidationError(
            "CAPTURE_DEPTH_SIZE",
            "depth bytes do not match depth dimensions",
            {"expected": expected, "actual": len(payload)},
        )
    return cast(np.ndarray, np.frombuffer(payload, dtype="<f4").reshape((height, width)).astype(np.float64))


def _decode_confidence(payload: bytes, frame: dict[str, Any]) -> np.ndarray:
    if frame.get("confidence_encoding") != "arkit_0_low_1_medium_2_high":
        raise ValidationError("CAPTURE_CONFIDENCE_ENCODING", "confidence encoding is not the ARKit 0/1/2 model")
    width, height = _dimensions(frame.get("depth_size"), "depth_size")
    if len(payload) != width * height:
        raise ValidationError("CAPTURE_CONFIDENCE_SIZE", "confidence bytes do not match depth dimensions")
    values = np.frombuffer(payload, dtype=np.uint8).reshape((height, width))
    if np.any(values > 2):
        raise ValidationError("CAPTURE_CONFIDENCE_VALUE", "ARKit confidence contains a value outside 0, 1, or 2")
    return cast(np.ndarray, values)


def _colors_for_depth_samples(
    archive: zipfile.ZipFile,
    frame: dict[str, Any],
    depth: np.ndarray,
    confidence: np.ndarray | None,
    *,
    pixel_stride: int,
) -> np.ndarray:
    width, height = _dimensions(frame.get("image_size"), "image_size")
    encoding = frame.get("rgb_encoding", "rgb8")
    payload = archive.read(frame["rgb_asset"])
    if encoding == "bgra8":
        expected = width * height * 4
        if len(payload) != expected:
            raise ValidationError("CAPTURE_RGB_SIZE", "BGRA bytes do not match image dimensions")
        image = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, 4))[:, :, [2, 1, 0]]
    elif encoding == "rgb8":
        expected = width * height * 3
        if len(payload) != expected:
            raise ValidationError("CAPTURE_RGB_SIZE", "RGB bytes do not match image dimensions")
        image = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, 3))
    else:
        raise ValidationError("CAPTURE_RGB_ENCODING", "the local reference path requires rgb8 or bgra8 input")
    rows, columns = np.indices(depth.shape)
    sample = np.zeros_like(depth, dtype=bool)
    sample[::pixel_stride, ::pixel_stride] = True
    valid = sample & np.isfinite(depth) & (depth > 0) & (depth <= float(frame.get("maximum_depth_m", 5.0)))
    if confidence is not None:
        valid &= confidence >= 1
    row_scale = (height - 1) / max(depth.shape[0] - 1, 1)
    column_scale = (width - 1) / max(depth.shape[1] - 1, 1)
    rgb_rows = np.rint(rows[valid] * row_scale).astype(np.int64)
    rgb_columns = np.rint(columns[valid] * column_scale).astype(np.int64)
    return cast(np.ndarray, image[rgb_rows, rgb_columns].astype(np.float64) / 255.0)


def _preserve_depth_edges(depth: np.ndarray, threshold_m: float = 0.15) -> np.ndarray:
    result = np.asarray(depth, dtype=np.float64).copy()
    horizontal = np.abs(np.diff(result, axis=1)) > threshold_m
    vertical = np.abs(np.diff(result, axis=0)) > threshold_m
    edge = np.zeros_like(result, dtype=bool)
    edge[:, 1:] |= horizontal
    edge[:, :-1] |= horizontal
    edge[1:, :] |= vertical
    edge[:-1, :] |= vertical
    result[edge] = np.nan
    return cast(np.ndarray, result)


def _motion_weight(frame: dict[str, Any]) -> float:
    motion = frame.get("motion", {})
    angular = motion.get("angular_velocity_rad_s", [0.0, 0.0, 0.0])
    try:
        magnitude = math.sqrt(sum(float(value) ** 2 for value in angular))
    except Exception as exc:
        raise ValidationError("CAPTURE_MOTION_INVALID", "frame motion metadata is invalid") from exc
    return 1.0 / (1.0 + magnitude**2)


def _active_anchor_mesh(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, np.ndarray] | None:
    active: dict[str, dict[str, Any]] = {}
    for observation in manifest.get("mesh_anchors", []):
        anchor_id = str(observation["anchor_id"])
        if observation.get("change") == "removed":
            active.pop(anchor_id, None)
        else:
            active[anchor_id] = observation
    vertices: list[np.ndarray] = []
    faces: list[np.ndarray] = []
    offset = 0
    for anchor_id in sorted(active):
        observation = active[anchor_id]
        decoded = decode_mesh_anchor(archive.read(observation["geometry_asset"]))
        transform = _matrix(observation["anchor_to_world"], 4, "anchor_to_world")
        local = decoded["vertices"]
        homogeneous = np.column_stack((local, np.ones(len(local))))
        world = (transform @ homogeneous.T).T[:, :3]
        vertices.append(world)
        faces.append(decoded["faces"] + offset)
        offset += len(world)
    if not vertices:
        return None
    return cast(dict[str, np.ndarray], cleanup_mesh(np.vstack(vertices), np.vstack(faces)))


def _bounded_hull_points(points: np.ndarray, maximum: int = 20_000) -> np.ndarray:
    if len(points) <= maximum:
        return points
    indices = np.linspace(0, len(points) - 1, maximum, dtype=np.int64)
    return cast(np.ndarray, points[indices])


def _matrix(value: Any, size: int, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (size, size) or not np.isfinite(matrix).all():
        raise ValidationError("CAPTURE_MATRIX_INVALID", f"{name} must be a finite {size}x{size} matrix")
    return cast(np.ndarray, matrix)


def _dimensions(value: Any, name: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValidationError("CAPTURE_DIMENSIONS", f"{name} must contain width and height")
    width, height = int(value[0]), int(value[1])
    if width <= 0 or height <= 0:
        raise ValidationError("CAPTURE_DIMENSIONS", f"{name} must be positive")
    return width, height


def _write_mesh_ply(path: Path, vertices: np.ndarray, faces: np.ndarray, *, colors: np.ndarray | None = None) -> None:
    verts = np.asarray(vertices, dtype=np.float32)
    tri = np.asarray(faces, dtype=np.int64)
    vertex_colors = _byte_colors(colors, len(verts))
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(verts)}",
        "property float x",
        "property float y",
        "property float z",
    ]
    if vertex_colors is not None:
        lines += ["property uchar red", "property uchar green", "property uchar blue"]
    lines += [f"element face {len(tri)}", "property list uchar int vertex_indices", "end_header"]
    for index, vertex in enumerate(verts):
        suffix = (
            ""
            if vertex_colors is None
            else f" {vertex_colors[index, 0]} {vertex_colors[index, 1]} {vertex_colors[index, 2]}"
        )
        lines.append(f"{vertex[0]:.7g} {vertex[1]:.7g} {vertex[2]:.7g}{suffix}")
    lines += [f"3 {face[0]} {face[1]} {face[2]}" for face in tri]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _write_points_ply(path: Path, points: np.ndarray, *, colors: np.ndarray | None = None) -> None:
    _write_mesh_ply(path, points, np.empty((0, 3), dtype=np.int64), colors=colors)


def _byte_colors(colors: np.ndarray | None, count: int) -> np.ndarray | None:
    if colors is None or np.asarray(colors).size == 0:
        return None
    values = np.asarray(colors, dtype=np.float64)
    if values.shape[0] != count or values.ndim != 2 or values.shape[1] < 3:
        return None
    return cast(np.ndarray, np.rint(np.clip(values[:, :3], 0, 1) * 255).astype(np.uint8))


def _json_values(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_values(item) for item in value]
    return value
