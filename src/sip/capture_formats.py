from __future__ import annotations

import struct
from typing import Any

import numpy as np

from .errors import ValidationError

MESH_MAGIC = b"SIPMSH1\0"
MESH_HEADER = struct.Struct("<8sII")


def encode_mesh_anchor(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    normals: np.ndarray | None = None,
    classifications: np.ndarray | None = None,
) -> bytes:
    """Encode one ARKit mesh-anchor snapshot in the open SIPMSH1 format."""
    verts = np.asarray(vertices, dtype="<f4")
    tri = np.asarray(faces, dtype="<u4")
    if verts.ndim != 2 or verts.shape[1] != 3 or not np.isfinite(verts).all():
        raise ValidationError("CAPTURE_MESH_VERTICES_INVALID", "mesh vertices must be finite Nx3 values")
    if tri.ndim != 2 or tri.shape[1] != 3 or (len(tri) and int(tri.max()) >= len(verts)):
        raise ValidationError("CAPTURE_MESH_FACES_INVALID", "mesh faces must be valid Nx3 indices")
    vertex_normals = np.zeros_like(verts) if normals is None else np.asarray(normals, dtype="<f4")
    if vertex_normals.shape != verts.shape or not np.isfinite(vertex_normals).all():
        raise ValidationError("CAPTURE_MESH_NORMALS_INVALID", "mesh normals must align with vertices")
    face_classes = (
        np.full(len(tri), 255, dtype=np.uint8)
        if classifications is None
        else np.asarray(classifications, dtype=np.uint8)
    )
    if face_classes.shape != (len(tri),):
        raise ValidationError("CAPTURE_MESH_CLASSIFICATIONS_INVALID", "mesh classifications must align with faces")
    return b"".join(
        [
            MESH_HEADER.pack(MESH_MAGIC, len(verts), len(tri)),
            verts.tobytes(order="C"),
            vertex_normals.tobytes(order="C"),
            tri.tobytes(order="C"),
            face_classes.tobytes(order="C"),
        ]
    )


def decode_mesh_anchor(payload: bytes) -> dict[str, Any]:
    if len(payload) < MESH_HEADER.size:
        raise ValidationError("CAPTURE_MESH_TRUNCATED", "mesh-anchor asset is shorter than its header")
    magic, vertex_count, face_count = MESH_HEADER.unpack_from(payload)
    if magic != MESH_MAGIC:
        raise ValidationError("CAPTURE_MESH_ENCODING", "mesh-anchor asset has an unsupported encoding")
    expected = MESH_HEADER.size + vertex_count * 3 * 4 * 2 + face_count * 3 * 4 + face_count
    if len(payload) != expected:
        raise ValidationError(
            "CAPTURE_MESH_SIZE",
            "mesh-anchor byte count does not match its declared element counts",
            {"expected": expected, "actual": len(payload)},
        )
    offset = MESH_HEADER.size
    vertices = (
        np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape((-1, 3)).astype(np.float64)
    )
    offset += vertex_count * 3 * 4
    normals = (
        np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape((-1, 3)).astype(np.float64)
    )
    offset += vertex_count * 3 * 4
    faces = np.frombuffer(payload, dtype="<u4", count=face_count * 3, offset=offset).reshape((-1, 3)).astype(np.int64)
    offset += face_count * 3 * 4
    classifications = np.frombuffer(payload, dtype=np.uint8, count=face_count, offset=offset).copy()
    if len(faces) and int(faces.max()) >= len(vertices):
        raise ValidationError("CAPTURE_MESH_FACES_INVALID", "mesh-anchor face index exceeds the vertex count")
    if not np.isfinite(vertices).all() or not np.isfinite(normals).all():
        raise ValidationError("CAPTURE_MESH_NONFINITE", "mesh-anchor geometry contains non-finite values")
    return {
        "vertices": vertices,
        "normals": normals,
        "faces": faces,
        "classifications": classifications,
        "encoding": "sip_mesh_anchor_v1_little_endian",
    }
