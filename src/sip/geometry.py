from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.spatial import ConvexHull, cKDTree

from .errors import ValidationError


@dataclass(frozen=True)
class SimilarityTransform:
    scale: float
    rotation: np.ndarray
    translation: np.ndarray
    rmse: float
    inlier_count: int

    def matrix(self) -> np.ndarray:
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = self.scale * self.rotation
        matrix[:3, 3] = self.translation
        return matrix

    def apply(self, points: np.ndarray) -> np.ndarray:
        values = _points(points)
        return (self.scale * (self.rotation @ values.T)).T + self.translation


def validate_transform(matrix: np.ndarray, *, similarity: bool = False) -> None:
    value = np.asarray(matrix, dtype=np.float64)
    if value.shape != (4, 4) or not np.isfinite(value).all():
        raise ValidationError("TRANSFORM_INVALID", "transform must be a finite 4x4 matrix")
    if not np.allclose(value[3], [0, 0, 0, 1], atol=1e-8):
        raise ValidationError("TRANSFORM_HOMOGENEOUS_ROW", "transform final row is invalid")
    linear = value[:3, :3]
    determinant = np.linalg.det(linear)
    if determinant <= 0:
        raise ValidationError("TRANSFORM_HANDEDNESS", "transform must preserve right-handed orientation")
    scale = np.cbrt(determinant) if similarity else 1.0
    rotation = linear / scale
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5):
        raise ValidationError("TRANSFORM_ROTATION_INVALID", "transform linear component is not orthonormal")
    if not similarity and not np.isclose(determinant, 1.0, atol=1e-5):
        raise ValidationError("TRANSFORM_SCALE_NOT_ALLOWED", "SE(3) transform cannot contain scale")


def umeyama(
    source: np.ndarray,
    target: np.ndarray,
    *,
    weights: np.ndarray | None = None,
    estimate_scale: bool = True,
) -> SimilarityTransform:
    src, dst = _paired(source, target)
    n = len(src)
    if n < 3:
        raise ValidationError("REGISTRATION_CORRESPONDENCES_INSUFFICIENT", "at least three correspondences are required")
    if weights is None:
        w = np.ones(n, dtype=np.float64) / n
    else:
        w = np.asarray(weights, dtype=np.float64)
        if w.shape != (n,) or np.any(w < 0) or not np.isfinite(w).all() or w.sum() <= 0:
            raise ValidationError("REGISTRATION_WEIGHTS_INVALID", "weights must be finite, non-negative, and non-zero")
        w = w / w.sum()
    src_mean = np.sum(src * w[:, None], axis=0)
    dst_mean = np.sum(dst * w[:, None], axis=0)
    src_centered = src - src_mean
    dst_centered = dst - dst_mean
    covariance = (dst_centered * w[:, None]).T @ src_centered
    u, singular, vt = np.linalg.svd(covariance)
    sign = np.ones(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        sign[-1] = -1
    rotation = u @ np.diag(sign) @ vt
    source_variance = float(np.sum(w * np.sum(src_centered**2, axis=1)))
    if source_variance <= np.finfo(float).eps:
        raise ValidationError("REGISTRATION_DEGENERATE", "source correspondences have no usable spatial variance")
    scale = float(np.sum(singular * sign) / source_variance) if estimate_scale else 1.0
    if not np.isfinite(scale) or scale <= 0:
        raise ValidationError("REGISTRATION_SCALE_INVALID", "estimated scale is not positive and finite")
    translation = dst_mean - scale * rotation @ src_mean
    transformed = (scale * (rotation @ src.T)).T + translation
    errors = np.linalg.norm(transformed - dst, axis=1)
    rmse = float(np.sqrt(np.sum(w * errors**2)))
    return SimilarityTransform(scale, rotation, translation, rmse, n)


def ransac_similarity(
    source: np.ndarray,
    target: np.ndarray,
    *,
    threshold_m: float,
    iterations: int = 500,
    estimate_scale: bool = True,
    seed: int = 0,
) -> tuple[SimilarityTransform, np.ndarray]:
    src, dst = _paired(source, target)
    if threshold_m <= 0 or iterations < 1:
        raise ValidationError("RANSAC_CONFIGURATION_INVALID", "RANSAC threshold and iterations must be positive")
    rng = np.random.default_rng(seed)
    best_mask: np.ndarray | None = None
    best_score = (-1, float("inf"))
    for _ in range(iterations):
        indices = rng.choice(len(src), size=3, replace=False)
        try:
            candidate = umeyama(src[indices], dst[indices], estimate_scale=estimate_scale)
        except ValidationError:
            continue
        errors = np.linalg.norm(candidate.apply(src) - dst, axis=1)
        mask = errors <= threshold_m
        count = int(mask.sum())
        median = float(np.median(errors[mask])) if count else float("inf")
        score = (count, -median)
        if score > (best_score[0], -best_score[1]):
            best_mask = mask
            best_score = (count, median)
    if best_mask is None or int(best_mask.sum()) < 3:
        raise ValidationError("RANSAC_NO_MODEL", "no registration model met the inlier threshold")
    refined = umeyama(src[best_mask], dst[best_mask], estimate_scale=estimate_scale)
    return SimilarityTransform(refined.scale, refined.rotation, refined.translation, refined.rmse, int(best_mask.sum())), best_mask


def icp_point_to_point(
    source: np.ndarray,
    target: np.ndarray,
    initial: SimilarityTransform,
    *,
    max_correspondence_m: float,
    iterations: int = 20,
) -> SimilarityTransform:
    src = _points(source)
    dst = _points(target)
    if initial.inlier_count < 3 or initial.rmse > max_correspondence_m * 2:
        raise ValidationError("ICP_COARSE_ALIGNMENT_REJECTED", "ICP requires an accepted coarse alignment")
    current = initial
    tree = cKDTree(dst)
    for _ in range(iterations):
        transformed = current.apply(src)
        distances, indices = tree.query(transformed, k=1)
        mask = distances <= max_correspondence_m
        if int(mask.sum()) < 3:
            break
        delta = umeyama(transformed[mask], dst[indices[mask]], estimate_scale=False)
        composed_rotation = delta.rotation @ current.rotation
        composed_scale = current.scale
        composed_translation = delta.rotation @ current.translation + delta.translation
        current = SimilarityTransform(composed_scale, composed_rotation, composed_translation, float(np.sqrt(np.mean(distances[mask] ** 2))), int(mask.sum()))
        if current.rmse < 1e-7:
            break
    return current


def unproject_depth(
    depth_m: np.ndarray,
    intrinsics: np.ndarray,
    pose_camera_to_world: np.ndarray,
    *,
    confidence: np.ndarray | None = None,
    minimum_confidence: int = 1,
    max_depth_m: float = 5.0,
    stride: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    depth = np.asarray(depth_m, dtype=np.float64)
    k = np.asarray(intrinsics, dtype=np.float64)
    pose = np.asarray(pose_camera_to_world, dtype=np.float64)
    if depth.ndim != 2 or k.shape != (3, 3):
        raise ValidationError("DEPTH_INPUT_INVALID", "depth must be 2D and intrinsics 3x3")
    validate_transform(pose)
    if confidence is None:
        conf = np.full(depth.shape, 2, dtype=np.uint8)
    else:
        conf = np.asarray(confidence)
        if conf.shape != depth.shape:
            raise ValidationError("DEPTH_CONFIDENCE_SHAPE", "confidence map must match depth map")
    v, u = np.mgrid[0 : depth.shape[0] : stride, 0 : depth.shape[1] : stride]
    z = depth[::stride, ::stride]
    c = conf[::stride, ::stride]
    valid = np.isfinite(z) & (z > 0) & (z <= max_depth_m) & (c >= minimum_confidence)
    u = u[valid].astype(np.float64)
    v = v[valid].astype(np.float64)
    z = z[valid]
    x = (u - k[0, 2]) * z / k[0, 0]
    y = (v - k[1, 2]) * z / k[1, 1]
    camera = np.column_stack([x, y, z, np.ones_like(z)])
    world = (pose @ camera.T).T[:, :3]
    weights = (c[valid].astype(np.float64) + 1.0) / np.maximum(z**2, 1e-6)
    return world, weights


def voxel_fuse(point_sets: list[np.ndarray], weight_sets: list[np.ndarray], *, voxel_size_m: float) -> dict[str, np.ndarray]:
    if voxel_size_m <= 0 or len(point_sets) != len(weight_sets):
        raise ValidationError("FUSION_CONFIGURATION_INVALID", "voxel size must be positive and point/weight sets aligned")
    accum: dict[tuple[int, int, int], tuple[np.ndarray, float, float]] = {}
    for points, weights in zip(point_sets, weight_sets, strict=True):
        pts = _points(points)
        w = np.asarray(weights, dtype=np.float64)
        if w.shape != (len(pts),) or np.any(w <= 0):
            raise ValidationError("FUSION_WEIGHTS_INVALID", "fusion weights must be positive and aligned")
        keys = np.floor(pts / voxel_size_m).astype(np.int64)
        for key_array, point, weight in zip(keys, pts, w, strict=True):
            key = tuple(int(item) for item in key_array)
            weighted_sum, weight_sum, squared_sum = accum.get(key, (np.zeros(3), 0.0, 0.0))
            accum[key] = (weighted_sum + point * weight, weight_sum + float(weight), squared_sum + float(np.dot(point, point) * weight))
    centers: list[np.ndarray] = []
    uncertainties: list[float] = []
    weights_out: list[float] = []
    for key in sorted(accum):
        weighted_sum, weight_sum, squared_sum = accum[key]
        mean = weighted_sum / weight_sum
        variance = max(0.0, squared_sum / weight_sum - float(np.dot(mean, mean)))
        centers.append(mean)
        uncertainties.append(float(np.sqrt(variance + voxel_size_m**2 / 12)))
        weights_out.append(weight_sum)
    return {
        "points": np.asarray(centers, dtype=np.float64).reshape((-1, 3)),
        "uncertainty_m": np.asarray(uncertainties, dtype=np.float64),
        "weights": np.asarray(weights_out, dtype=np.float64),
    }


def convex_mesh(points: np.ndarray) -> dict[str, np.ndarray]:
    pts = _points(points)
    if len(pts) < 4:
        raise ValidationError("MESH_POINTS_INSUFFICIENT", "at least four non-coplanar points are required")
    try:
        hull = ConvexHull(pts)
    except Exception as exc:
        raise ValidationError("MESH_EXTRACTION_FAILED", "point set cannot form a stable surface") from exc
    used = np.unique(hull.simplices)
    remap = {int(old): index for index, old in enumerate(used)}
    vertices = pts[used]
    faces = np.vectorize(remap.get)(hull.simplices).astype(np.int64)
    return cleanup_mesh(vertices, faces)


def cleanup_mesh(vertices: np.ndarray, faces: np.ndarray) -> dict[str, np.ndarray]:
    verts = _points(vertices)
    tri = np.asarray(faces, dtype=np.int64)
    if tri.ndim != 2 or tri.shape[1] != 3:
        raise ValidationError("MESH_FACES_INVALID", "mesh faces must be Nx3 indices")
    if len(tri) and (tri.min() < 0 or tri.max() >= len(verts)):
        raise ValidationError("MESH_INDEX_INVALID", "mesh face index is out of range")
    rounded = np.round(verts, decimals=9)
    unique, inverse = np.unique(rounded, axis=0, return_inverse=True)
    remapped = inverse[tri]
    nondegenerate = np.all(np.sort(remapped, axis=1)[:, 1:] != np.sort(remapped, axis=1)[:, :-1], axis=1)
    remapped = remapped[nondegenerate]
    if len(remapped):
        a, b, c = unique[remapped[:, 0]], unique[remapped[:, 1]], unique[remapped[:, 2]]
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        remapped = remapped[area > 1e-12]
    if len(remapped):
        # Use orientation-independent keys to remove duplicate triangles, but
        # retain the first triangle's winding. Sorting the returned face itself
        # destroys the surface orientation and corrupts downstream normals.
        face_keys = np.sort(remapped, axis=1)
        _, first_indices = np.unique(face_keys, axis=0, return_index=True)
        canonical_faces = remapped[np.sort(first_indices)]
    else:
        canonical_faces = remapped
    return {"vertices": unique.astype(np.float64), "faces": canonical_faces.astype(np.int64)}


def mesh_quality_report(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    vertex_colors: np.ndarray | None = None,
) -> dict[str, Any]:
    """Return deterministic topology and appearance coverage facts for a mesh."""
    clean = cleanup_mesh(vertices, faces)
    verts = clean["vertices"]
    tri = clean["faces"]
    if len(tri):
        a, b, c = verts[tri[:, 0]], verts[tri[:, 1]], verts[tri[:, 2]]
        face_areas = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        edges = np.vstack((tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]))
        edge_keys = np.sort(edges, axis=1)
        _, edge_counts = np.unique(edge_keys, axis=0, return_counts=True)
        boundary_edges = int(np.count_nonzero(edge_counts == 1))
        nonmanifold_edges = int(np.count_nonzero(edge_counts > 2))
    else:
        face_areas = np.asarray([], dtype=np.float64)
        boundary_edges = 0
        nonmanifold_edges = 0
    bounds_min = verts.min(axis=0).tolist() if len(verts) else [0.0, 0.0, 0.0]
    bounds_max = verts.max(axis=0).tolist() if len(verts) else [0.0, 0.0, 0.0]
    color_coverage = 0.0
    if vertex_colors is not None:
        colors = np.asarray(vertex_colors, dtype=np.float64)
        if colors.ndim != 2 or colors.shape[0] != len(np.asarray(vertices)) or colors.shape[1] not in {3, 4}:
            raise ValidationError(
                "MESH_VERTEX_COLORS_INVALID",
                "vertex colors must be Nx3 or Nx4 and align with input vertices",
            )
        if not np.isfinite(colors).all():
            raise ValidationError("MESH_VERTEX_COLORS_INVALID", "vertex colors must be finite")
        color_coverage = (
            float(np.count_nonzero(np.any(colors[:, :3] != 0, axis=1)) / len(colors)) if len(colors) else 0.0
        )
    return {
        "vertex_count": len(verts),
        "face_count": len(tri),
        "surface_area_m2": float(face_areas.sum()),
        "boundary_edge_count": boundary_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "watertight": bool(len(tri) and boundary_edges == 0 and nonmanifold_edges == 0),
        "bounds_min_m": bounds_min,
        "bounds_max_m": bounds_max,
        "vertex_color_coverage": color_coverage,
    }


def interaction_proxy(vertices: np.ndarray, faces: np.ndarray, *, target_faces: int = 5000) -> dict[str, Any]:
    clean = cleanup_mesh(vertices, faces)
    tri = clean["faces"]
    if target_faces < 4:
        raise ValidationError("PROXY_TARGET_INVALID", "proxy target must allow at least four faces")
    if len(tri) > target_faces:
        indices = np.linspace(0, len(tri) - 1, target_faces, dtype=int)
        tri = tri[indices]
    verts = clean["vertices"]
    normals = np.zeros_like(verts)
    for face in tri:
        normal = np.cross(verts[face[1]] - verts[face[0]], verts[face[2]] - verts[face[0]])
        length = np.linalg.norm(normal)
        if length:
            normal /= length
        normals[face] += normal
    lengths = np.linalg.norm(normals, axis=1)
    normals[lengths > 0] /= lengths[lengths > 0, None]
    nav_faces = [int(index) for index, face in enumerate(tri) if abs(float(normals[face].mean(axis=0)[1])) >= 0.65]
    return {
        "vertices": verts,
        "faces": tri,
        "vertex_normals": normals,
        "navigation_face_indices": nav_faces,
        "authoritative": False,
        "intended_uses": ["picking", "collision", "navigation", "clipping", "occlusion", "spatial_audio"],
        "prohibited_uses": ["verified_measurement", "fabrication", "code_compliance", "survey", "as_built_certification"],
    }


def mesh_to_splats(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    samples: int = 1024,
    seed: int = 0,
    vertex_colors: np.ndarray | None = None,
) -> dict[str, Any]:
    if samples <= 0:
        raise ValidationError("SPLAT_SAMPLE_COUNT_INVALID", "splat sample count must be positive")
    mesh = cleanup_mesh(vertices, faces)
    verts, tri = mesh["vertices"], mesh["faces"]
    if len(tri) == 0:
        raise ValidationError("MESH_EMPTY", "mesh has no surface faces")
    a, b, c = verts[tri[:, 0]], verts[tri[:, 1]], verts[tri[:, 2]]
    areas = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    probabilities = areas / areas.sum()
    rng = np.random.default_rng(seed)
    selected = rng.choice(len(tri), size=samples, p=probabilities)
    uv = rng.random((samples, 2))
    flip = uv.sum(axis=1) > 1
    uv[flip] = 1 - uv[flip]
    positions = a[selected] + uv[:, :1] * (b[selected] - a[selected]) + uv[:, 1:] * (c[selected] - a[selected])
    normals = np.cross(b[selected] - a[selected], c[selected] - a[selected])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    radii = np.sqrt(np.maximum(areas[selected], 1e-12) / samples)
    covariance = np.stack([radii, radii, radii * 0.1], axis=1)
    result: dict[str, Any] = {
        "positions": positions,
        "normals": normals,
        "scales": covariance,
        "opacity": np.ones(samples),
        "lossy": True,
        "representation_equivalent": False,
        "information_loss": [
            "surface topology and exact triangle boundaries are not retained",
            "material and texture attributes are not represented by the deterministic reference converter",
            "sample density bounds recoverable geometric detail",
        ],
        "authority": "visual_non_metric",
    }
    if vertex_colors is not None:
        colors = np.asarray(vertex_colors, dtype=np.float64)
        if colors.ndim != 2 or colors.shape[0] != len(vertices) or colors.shape[1] not in {3, 4}:
            raise ValidationError(
                "MESH_VERTEX_COLORS_INVALID",
                "vertex colors must be Nx3 or Nx4 and align with input vertices",
            )
        if not np.isfinite(colors).all():
            raise ValidationError("MESH_VERTEX_COLORS_INVALID", "vertex colors must be finite")
        rounded = np.round(np.asarray(vertices, dtype=np.float64), decimals=9)
        unique_vertices, inverse = np.unique(rounded, axis=0, return_inverse=True)
        color_sums = np.zeros((len(unique_vertices), colors.shape[1]), dtype=np.float64)
        color_counts = np.zeros(len(unique_vertices), dtype=np.float64)
        np.add.at(color_sums, inverse, colors)
        np.add.at(color_counts, inverse, 1.0)
        clean_colors = color_sums / color_counts[:, None]
        if not np.array_equal(unique_vertices, verts):
            raise ValidationError("MESH_COLOR_ALIGNMENT_FAILED", "cleaned vertices do not align with vertex colors")
        w1 = uv[:, :1]
        w2 = uv[:, 1:]
        w0 = 1.0 - w1 - w2
        result["colors"] = (
            w0 * clean_colors[tri[selected, 0]]
            + w1 * clean_colors[tri[selected, 1]]
            + w2 * clean_colors[tri[selected, 2]]
        )
        result["information_loss"] = [
            item for item in result["information_loss"] if "material and texture" not in item
        ] + ["vertex colors are interpolated; texture images and material response are not retained"]
    return result


def compose_mesh_representations(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    vertex_colors: np.ndarray | None = None,
    splat_samples: int = 4096,
    lod_target_faces: int = 5000,
    seed: int = 0,
) -> dict[str, Any]:
    """Compose metric, visual, and interaction lanes without collapsing authority."""
    clean = cleanup_mesh(vertices, faces)
    visual = mesh_to_splats(
        vertices,
        faces,
        samples=splat_samples,
        seed=seed,
        vertex_colors=vertex_colors,
    )
    interaction = interaction_proxy(clean["vertices"], clean["faces"], target_faces=lod_target_faces)
    return {
        "metric": {
            "vertices": clean["vertices"],
            "faces": clean["faces"],
            "authority": "metric_unverified",
            "intended_uses": ["measurement_with_source_resolution", "alignment", "change_review"],
        },
        "visual": visual,
        "interaction": interaction,
        "quality": mesh_quality_report(vertices, faces, vertex_colors=vertex_colors),
        "composition": {
            "authority_lanes_preserved": True,
            "visual_resolves_to_metric_for_measurement": True,
            "interaction_resolves_to_metric_for_measurement": True,
        },
    }


def splats_to_surface(positions: np.ndarray, *, minimum_points: int = 4) -> dict[str, Any]:
    pts = _points(positions)
    if len(pts) < minimum_points:
        raise ValidationError("SPLAT_SURFACE_POINTS_INSUFFICIENT", "not enough splats to extract a proxy surface")
    mesh = convex_mesh(pts)
    return {
        **mesh,
        "lossy": True,
        "representation_equivalent": False,
        "information_loss": [
            "Gaussian appearance, opacity, covariance, and view-dependent color are not retained",
            "the convex reference surface may bridge unobserved space",
            "the output is unsuitable for verified measurement without independent metric evidence",
        ],
        "authoritative": False,
        "authority": "derived_non_authoritative",
        "source": "splat-derived-proxy",
        "prohibited_uses": ["verified_measurement", "fabrication", "survey", "code_compliance"],
    }


def change_detection(reference: np.ndarray, comparison: np.ndarray, *, threshold_m: float) -> dict[str, Any]:
    first, second = _points(reference), _points(comparison)
    if threshold_m <= 0:
        raise ValidationError("CHANGE_THRESHOLD_INVALID", "change threshold must be positive")
    tree_a, tree_b = cKDTree(first), cKDTree(second)
    distances_b_to_a, _ = tree_a.query(second)
    distances_a_to_b, _ = tree_b.query(first)
    added = np.where(distances_b_to_a > threshold_m)[0]
    removed = np.where(distances_a_to_b > threshold_m)[0]
    return {
        "added_indices": added.tolist(),
        "removed_indices": removed.tolist(),
        "added_fraction": float(len(added) / max(len(second), 1)),
        "removed_fraction": float(len(removed) / max(len(first), 1)),
        "threshold_m": threshold_m,
    }


def detect_pose_anomalies(poses: list[np.ndarray], *, max_step_m: float = 5.0, collapse_variance_m2: float = 1e-8) -> dict[str, Any]:
    if not poses:
        return {"valid": False, "reasons": ["empty_trajectory"]}
    translations: list[np.ndarray] = []
    reasons: list[str] = []
    for index, pose in enumerate(poses):
        try:
            validate_transform(pose)
        except ValidationError as exc:
            reasons.append(f"pose_{index}:{exc.code}")
            continue
        translations.append(np.asarray(pose)[:3, 3])
    if translations:
        values = np.asarray(translations)
        if len(values) > 2 and float(np.var(values, axis=0).sum()) < collapse_variance_m2:
            reasons.append("pose_collapse")
        steps = np.linalg.norm(np.diff(values, axis=0), axis=1) if len(values) > 1 else np.array([])
        if np.any(steps > max_step_m):
            reasons.append("implausible_motion")
    return {"valid": not reasons, "reasons": reasons, "poses_checked": len(poses)}


def _points(value: np.ndarray) -> np.ndarray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValidationError("POINTS_INVALID", "points must be a finite Nx3 array")
    return points


def _paired(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    src, dst = _points(source), _points(target)
    if src.shape != dst.shape:
        raise ValidationError("CORRESPONDENCE_SHAPE_MISMATCH", "source and target correspondences must have the same shape")
    return src, dst
