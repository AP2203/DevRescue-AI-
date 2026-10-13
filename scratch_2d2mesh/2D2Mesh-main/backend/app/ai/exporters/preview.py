"""Preview rendering for generated 3D models.

Produces a PNG preview using a dependency-free software triangle renderer
(Pillow + numpy, painter's algorithm). No GPU or offscreen GL context is
required, so previews work on any machine and in CI.
"""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None

_MAX_RENDER_FACES = 12_000
_LIGHT_DIR = np.array([0.5, 0.7, 0.9], dtype=np.float64)


def render_preview(
    mesh,
    size: Tuple[int, int] = (512, 512),
    background: Tuple[int, int, int] = (245, 247, 250),
) -> Optional[bytes]:
    """Render a PNG preview of a trimesh scene/mesh. Returns None on failure."""
    if trimesh is None or mesh is None:
        return None
    try:
        single = _as_single_mesh(mesh)
        if single is None or len(single.vertices) == 0 or len(single.faces) == 0:
            return None
        if len(single.faces) > _MAX_RENDER_FACES:
            with contextlib.suppress(Exception):
                single = single.simplify_quadric_decimation(_MAX_RENDER_FACES)
        image = _draw_mesh(single, size, background)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:  # pragma: no cover
        logger.warning("Preview render failed: %s", exc)
        return None


def _as_single_mesh(mesh):
    if isinstance(mesh, trimesh.Trimesh):
        return mesh
    if isinstance(mesh, trimesh.Scene):
        meshes = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            return None
        if len(meshes) == 1:
            return meshes[0]
        return trimesh.util.concatenate(meshes)
    return getattr(mesh, "mesh", None)


def _vertex_colors(mesh, count: int) -> np.ndarray:
    visual = getattr(mesh, "visual", None)
    if visual is not None:
        try:
            colors = np.asarray(visual.to_color().vertex_colors, dtype=np.float64)
            if colors.shape[0] == count:
                return np.clip(colors[:, :3], 0, 255).astype(np.uint8)
        except Exception:  # pragma: no cover
            pass
    return np.full((count, 3), 200, dtype=np.uint8)


def _rotation_matrix(yaw_deg: float, pitch_deg: float) -> np.ndarray:
    yaw = np.radians(yaw_deg)
    pitch = np.radians(pitch_deg)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cx, sx = np.cos(pitch), np.sin(pitch)
    ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    return rx @ ry


def _draw_mesh(mesh, size: Tuple[int, int], background: Tuple[int, int, int]) -> Image.Image:
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    width, height = size
    colors = _vertex_colors(mesh, len(verts))

    rotated = verts @ _rotation_matrix(30.0, -18.0).T
    rotated -= rotated.mean(axis=0)
    span = float(np.max(np.ptp(rotated, axis=0))) or 1.0
    rotated = rotated / span * 1.7

    scale = min(width, height) / 2.1
    sx = width / 2.0 + rotated[:, 0] * scale
    sy = height / 2.0 - rotated[:, 1] * scale
    depth = rotated[:, 2]

    # Painter's algorithm: draw far faces (smallest depth) first.
    face_depth = depth[faces].mean(axis=1)
    order = np.argsort(face_depth, kind="stable")

    face_normals = np.asarray(mesh.face_normals, dtype=np.float64)
    light = _LIGHT_DIR / (np.linalg.norm(_LIGHT_DIR) or 1.0)
    lambert = np.clip(face_normals @ light, 0.0, 1.0)
    shade = 0.45 + 0.55 * lambert

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    xs = sx[faces]
    ys = sy[faces]
    face_colors = colors[faces].mean(axis=1).astype(np.float64)
    intensity = shade[:, None]

    for face_index in order:
        pts = [
            (float(xs[face_index][0]), float(ys[face_index][0])),
            (float(xs[face_index][1]), float(ys[face_index][1])),
            (float(xs[face_index][2]), float(ys[face_index][2])),
        ]
        rgb = face_colors[face_index] * intensity[face_index]
        draw.polygon(pts, fill=tuple(int(np.clip(v, 0, 255)) for v in rgb))
    return image
