"""Mesh statistics for generated 3D models."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _empty_stats() -> Dict[str, Any]:
    return {
        "vertices": 0,
        "faces": 0,
        "triangles": 0,
        "edges": 0,
        "bounds": None,
        "has_texture": False,
        "texture_size": None,
        "watertight": False,
        "volume": None,
        "surface_area": None,
        "extents": None,
        "center": None,
    }


def compute_mesh_stats(mesh) -> Dict[str, Any]:
    """Build a JSON-safe statistics dict from a trimesh object/scene root mesh."""
    if mesh is None:
        return _empty_stats()
    try:
        vertices = int(mesh.vertices.shape[0]) if getattr(mesh, "vertices", None) is not None else 0
        faces = int(mesh.faces.shape[0]) if getattr(mesh, "faces", None) is not None else 0
        bounds = mesh.bounds.tolist() if getattr(mesh, "bounds", None) is not None else None
        has_texture = bool(getattr(getattr(mesh, "visual", None), "material", None) is not None)
        texture_size = None
        if has_texture:
            mat = mesh.visual.material
            if getattr(mat, "image", None) is not None:
                texture_size = max(mat.image.size)

        stats: Dict[str, Any] = {
            "vertices": vertices,
            "faces": faces,
            "triangles": faces,
            "edges": int(faces * 3 / 2),
            "bounds": bounds,
            "has_texture": has_texture,
            "texture_size": texture_size,
            "watertight": bool(mesh.is_watertight),
        }
        with np.errstate(all="ignore"):
            volume = getattr(mesh, "volume", None)
            stats["volume"] = float(volume) if volume is not None else None
            area = getattr(mesh, "area", None)
            stats["surface_area"] = float(area) if area is not None else None
        extents = getattr(mesh, "extents", None)
        if extents is not None:
            stats["extents"] = [round(float(e), 6) for e in extents]
        centroid = getattr(mesh, "centroid", None)
        if centroid is not None:
            stats["center"] = [round(float(c), 6) for c in centroid]
        return stats
    except Exception:  # pragma: no cover
        return _empty_stats()
