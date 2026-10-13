"""Output validation and quality checks for generated 3D models.

Runs every generated model through a battery of checks (empty mesh, broken
geometry, invalid normals, missing texture, excessive polygons, invalid GLB,
bounding-box sanity) and produces a ``QualityReport`` the engine can enforce.
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional

import numpy as np

from app.ai.exporters.gltf import validate_glb_bytes
from app.ai.types import GenerationResult, GenerationSettings, QualityCheck, QualityReport

logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None

DEFAULT_MAX_POLYGONS = 500_000
MIN_BBOX_EXTENT = 1e-6
MAX_BBOX_EXTENT = 1000.0
MAX_DEGENERATE_FRACTION = 0.05


class QualityReportBuilder:
    """Collects checks into a :class:`QualityReport`."""

    def __init__(self) -> None:
        self.checks: List[QualityCheck] = []

    def check(self, name: str, passed: bool, severity: str, message: str) -> None:
        self.checks.append(QualityCheck(name=name, passed=passed, severity=severity, message=message))

    def error(self, name: str, passed: bool, message: str) -> None:
        self.check(name, passed, "error", message)

    def warning(self, name: str, passed: bool, message: str) -> None:
        self.check(name, passed, "warning", message)

    def build(self) -> QualityReport:
        failed = [c for c in self.checks if not c.passed and c.severity == "error"]
        report = QualityReport(checks=self.checks, passed=not failed)
        for check in self.checks:
            if not check.passed:
                logger.warning("[quality] %s %s: %s", check.severity, check.name, check.message)
        return report


class OutputValidator:
    """Runs quality checks against a generated model and its GLB bytes."""

    @staticmethod
    def load_mesh(result: GenerationResult):
        """Load the single-trimesh mesh from a result's GLB bytes (best effort).

        When the scene has several meshes the largest (primary object) is
        returned — concatenating a textured mesh with a colored one would
        discard the texture, so we avoid it.
        """
        if trimesh is None:
            return None
        err = validate_glb_bytes(result.glb_bytes)
        if err:
            return None
        try:
            loaded = trimesh.load(io.BytesIO(result.glb_bytes), file_type="glb", force="scene")
            if isinstance(loaded, trimesh.Scene):
                meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
            elif isinstance(loaded, trimesh.Trimesh):
                meshes = [loaded]
            else:
                return None
            if not meshes:
                return None
            if len(meshes) == 1:
                return meshes[0]
            return max(meshes, key=lambda g: len(getattr(g, "faces", [])))
        except Exception:  # pragma: no cover
            return None

    @staticmethod
    def validate(
        result: GenerationResult,
        settings: Optional[GenerationSettings] = None,
    ) -> QualityReport:
        settings = settings or GenerationSettings()
        builder = QualityReportBuilder()
        max_polygons = settings.max_polygons or DEFAULT_MAX_POLYGONS

        # 1. GLB container validity ----------------------------------------
        glb_err = validate_glb_bytes(result.glb_bytes)
        builder.error("glb_valid", glb_err is None, glb_err or "GLB container is valid")

        mesh = OutputValidator.load_mesh(result) if glb_err is None else None

        # 2. Empty mesh ----------------------------------------------------
        empty = mesh is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0
        builder.error(
            "mesh_not_empty",
            not empty,
            "mesh has no vertices/faces"
            if empty
            else f"mesh has {len(mesh.vertices)} vertices, {len(mesh.faces)} faces",
        )

        if mesh is not None and not empty:
            verts = np.asarray(mesh.vertices, dtype=np.float64)

            # 3. Broken geometry: NaN/Inf vertices + degenerate faces --------
            invalid_verts = int(np.isnan(verts).any(axis=1).sum() + np.isinf(verts).any(axis=1).sum())
            builder.error(
                "vertices_valid",
                invalid_verts == 0,
                f"{invalid_verts} NaN/Inf vertices found" if invalid_verts else "all vertices finite",
            )

            faces = np.asarray(mesh.faces)
            degenerate = 0
            if len(faces) > 0:
                dup = (
                    (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
                )
                areas = getattr(mesh, "area_faces", None)
                if areas is not None:
                    zero = np.asarray(areas) <= 1e-12
                    degenerate = int(np.sum(dup | zero))
                else:
                    degenerate = int(np.sum(dup))
            frac = degenerate / max(1, len(faces))
            builder.error(
                "geometry_not_broken",
                degenerate == 0 or frac <= MAX_DEGENERATE_FRACTION,
                f"{degenerate} degenerate faces ({frac:.1%})" if degenerate else "no degenerate faces",
            )

            # 4. Valid normals ----------------------------------------------
            normals_ok = True
            normals_msg = "normals are valid"
            try:
                normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
                if len(normals) != len(verts):
                    normals_ok = False
                    normals_msg = "normal count does not match vertex count"
                else:
                    bad = np.isnan(normals).any() or np.isinf(normals).any()
                    zero_len = (np.linalg.norm(normals, axis=1) <= 1e-12).sum()
                    if bad:
                        normals_ok = False
                        normals_msg = "normals contain NaN/Inf values"
                    elif zero_len:
                        normals_ok = False
                        normals_msg = f"{int(zero_len)} zero-length normals"
            except Exception:  # pragma: no cover
                normals_ok = False
                normals_msg = "normals could not be computed"
            builder.error("normals_valid", normals_ok, normals_msg)

            # 5. Texture presence -------------------------------------------
            material = getattr(getattr(mesh, "visual", None), "material", None)
            material_image = None
            if material is not None:
                material_image = getattr(material, "image", None) or getattr(
                    material, "baseColorTexture", None
                )
            has_texture = material_image is not None or bool(result.stats.get("has_texture"))
            if settings.texture_quality and settings.texture_quality.lower() != "none":
                builder.error(
                    "texture_present",
                    has_texture,
                    "model has no texture/material" if not has_texture else "model is textured",
                )

            # 6. Excessive polygon count -------------------------------------
            builder.warning(
                "polygon_budget",
                len(faces) <= max_polygons,
                f"{len(faces)} faces exceeds budget of {max_polygons}"
                if len(faces) > max_polygons
                else f"{len(faces)} faces within budget",
            )

            # 7. Bounding-box validation -------------------------------------
            extents = mesh.extents
            max_extent = float(np.max(extents)) if extents is not None and len(extents) else 0.0
            min_extent = float(np.min(extents)) if extents is not None and len(extents) else 0.0
            if (
                max_extent > MIN_BBOX_EXTENT
                and max_extent <= MAX_BBOX_EXTENT
                and min_extent > MIN_BBOX_EXTENT
            ):
                bbox_msg = f"bounding box within limits (max extent {max_extent:.4f})"
                bbox_ok = True
            elif max_extent <= MIN_BBOX_EXTENT:
                bbox_msg = "degenerate bounding box (extent near zero)"
                bbox_ok = False
            elif min_extent <= MIN_BBOX_EXTENT:
                bbox_msg = "flat/degenerate bounding box on at least one axis"
                bbox_ok = False
            else:
                bbox_msg = f"bounding box too large (max extent {max_extent:.4f})"
                bbox_ok = False
            builder.error("bounding_box_valid", bbox_ok, bbox_msg)

        return builder.build()
