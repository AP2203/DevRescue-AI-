"""Mesh validation and repair service.

Performs thorough geometry inspection, diagnostic logging, and automatic repair
of 3D meshes before export. Ensures output models have valid, non-corrupted
topology, vertex normals, UV coordinates, and materials.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None


class MeshDiagnosticReport:
    """Detailed diagnostics of a 3D mesh representation."""

    def __init__(self) -> None:
        self.vertices_count: int = 0
        self.faces_count: int = 0
        self.meshes_count: int = 0
        self.materials_count: int = 0
        self.has_normals: bool = False
        self.has_uvs: bool = False
        self.has_texture: bool = False
        self.texture_dimensions: Tuple[int, int] | None = None
        self.nan_vertex_count: int = 0
        self.inf_vertex_count: int = 0
        self.invalid_vertex_count: int = 0
        self.degenerate_face_count: int = 0
        self.duplicate_vertex_count: int = 0
        self.non_manifold_edge_count: int = 0
        self.bounding_box_min: List[float] = [0.0, 0.0, 0.0]
        self.bounding_box_max: List[float] = [0.0, 0.0, 0.0]
        self.bounding_sphere_radius: float = 0.0
        self.is_watertight: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vertices": self.vertices_count,
            "faces": self.faces_count,
            "triangles": self.faces_count,
            "meshes": self.meshes_count,
            "materials": self.materials_count,
            "has_normals": self.has_normals,
            "has_uvs": self.has_uvs,
            "has_texture": self.has_texture,
            "texture_dimensions": list(self.texture_dimensions) if self.texture_dimensions else None,
            "nan_vertices": self.nan_vertex_count,
            "inf_vertices": self.inf_vertex_count,
            "invalid_vertices": self.invalid_vertex_count,
            "degenerate_faces": self.degenerate_face_count,
            "duplicate_vertices": self.duplicate_vertex_count,
            "non_manifold_edges": self.non_manifold_edge_count,
            "bounding_box_min": [round(v, 4) for v in self.bounding_box_min],
            "bounding_box_max": [round(v, 4) for v in self.bounding_box_max],
            "bounding_sphere_radius": round(self.bounding_sphere_radius, 4),
            "is_watertight": self.is_watertight,
        }

    def log_summary(self, stage: str = "Mesh Inspection") -> None:
        logger.info("=== [%s Diagnostic Report] ===", stage)
        logger.info(
            "Vertices: %d | Faces: %d | Meshes: %d | Materials: %d",
            self.vertices_count,
            self.faces_count,
            self.meshes_count,
            self.materials_count,
        )
        logger.info(
            "Normals: %s | UVs: %s | Texture: %s (%s)",
            "YES" if self.has_normals else "NO",
            "YES" if self.has_uvs else "NO",
            "YES" if self.has_texture else "NO",
            f"{self.texture_dimensions[0]}x{self.texture_dimensions[1]}"
            if self.texture_dimensions
            else "N/A",
        )
        logger.info(
            "NaN/Inf Vertices: %d / %d | Degenerate Faces: %d | Duplicates: %d",
            self.nan_vertex_count,
            self.inf_vertex_count,
            self.degenerate_face_count,
            self.duplicate_vertex_count,
        )
        logger.info(
            "Bounding Box: Min %s Max %s | Sphere Radius: %.4f | Watertight: %s",
            [round(v, 3) for v in self.bounding_box_min],
            [round(v, 3) for v in self.bounding_box_max],
            self.bounding_sphere_radius,
            "YES" if self.is_watertight else "NO",
        )
        logger.info("===========================================")


class MeshValidator:
    """Service to inspect, validate, and repair 3D meshes."""

    @staticmethod
    def inspect(mesh_or_scene: Any) -> MeshDiagnosticReport:
        report = MeshDiagnosticReport()
        if trimesh is None:
            return report

        mesh = MeshValidator._to_single_mesh(mesh_or_scene)
        if mesh is None or not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            return report

        report.vertices_count = len(mesh.vertices)
        report.faces_count = len(mesh.faces) if hasattr(mesh, "faces") and mesh.faces is not None else 0
        report.meshes_count = (
            1 if isinstance(mesh, trimesh.Trimesh) else len(getattr(mesh_or_scene, "geometry", {}))
        )

        verts = np.asarray(mesh.vertices, dtype=np.float64)
        nans = np.isnan(verts).any(axis=1)
        infs = np.isinf(verts).any(axis=1)
        report.nan_vertex_count = int(np.sum(nans))
        report.inf_vertex_count = int(np.sum(infs))
        report.invalid_vertex_count = report.nan_vertex_count + report.inf_vertex_count

        if report.faces_count > 0:
            faces = np.asarray(mesh.faces)
            deg_indices = (
                (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
            )
            areas = getattr(mesh, "area_faces", None)
            if areas is not None:
                zero_area = areas <= 1e-12
                report.degenerate_face_count = int(np.sum(deg_indices | zero_area))
            else:
                report.degenerate_face_count = int(np.sum(deg_indices))

        if len(verts) > 0 and not report.invalid_vertex_count:
            _, unique_indices = np.unique(np.round(verts, 6), axis=0, return_index=True)
            report.duplicate_vertex_count = len(verts) - len(unique_indices)

        report.has_normals = bool(
            hasattr(mesh, "vertex_normals")
            and mesh.vertex_normals is not None
            and len(mesh.vertex_normals) == len(mesh.vertices)
            and not np.isnan(mesh.vertex_normals).any()
        )

        has_uv = False
        if hasattr(mesh, "visual") and mesh.visual is not None:
            uvs = getattr(mesh.visual, "uv", None)
            if uvs is not None and len(uvs) == len(mesh.vertices):
                has_uv = bool(not np.isnan(uvs).any() and not np.isinf(uvs).any())
        report.has_uvs = has_uv

        if hasattr(mesh, "visual") and getattr(mesh.visual, "material", None) is not None:
            mat = mesh.visual.material
            report.materials_count = 1
            img = getattr(mat, "image", None) or getattr(mat, "baseColorTexture", None)
            if img is not None:
                report.has_texture = True
                if hasattr(img, "size"):
                    report.texture_dimensions = (img.size[0], img.size[1])

        if len(verts) > 0 and not report.invalid_vertex_count:
            bbox = mesh.bounds
            report.bounding_box_min = bbox[0].tolist()
            report.bounding_box_max = bbox[1].tolist()
            center = mesh.centroid
            dists = np.linalg.norm(verts - center, axis=1)
            report.bounding_sphere_radius = float(np.max(dists)) if len(dists) > 0 else 0.0

        report.is_watertight = bool(getattr(mesh, "is_watertight", False))
        return report

    @staticmethod
    def repair(mesh_or_scene: Any) -> Any:
        """Thoroughly validate and repair a mesh / scene for export."""
        if trimesh is None:
            return mesh_or_scene

        report_before = MeshValidator.inspect(mesh_or_scene)
        report_before.log_summary("Pre-Repair Mesh")

        mesh = MeshValidator._to_single_mesh(mesh_or_scene)
        if mesh is None or len(mesh.vertices) == 0:
            logger.warning("Empty mesh provided to repair pipeline")
            return mesh_or_scene

        verts = np.asarray(mesh.vertices, dtype=np.float64)
        valid_mask = ~(np.isnan(verts).any(axis=1) | np.isinf(verts).any(axis=1))
        if not np.all(valid_mask):
            logger.info("Cleaning %d invalid vertices", np.sum(~valid_mask))
            mesh.update_vertices(valid_mask)

        if hasattr(mesh, "remove_infinite_values"):
            mesh.remove_infinite_values()
        if hasattr(mesh, "unique_faces"):
            mesh.update_faces(mesh.unique_faces())
        if hasattr(mesh, "remove_degenerate_faces"):
            mesh.remove_degenerate_faces()
        if hasattr(mesh, "remove_unreferenced_vertices"):
            mesh.remove_unreferenced_vertices()

        with contextlib.suppress(Exception):
            mesh.merge_vertices()

        if len(mesh.faces) > 0:
            try:
                trimesh.repair.fix_normals(mesh)
                trimesh.repair.fix_inversion(mesh)
            except Exception as exc:
                logger.warning("Trimesh normal fix warning: %s", exc)

        try:
            _ = mesh.vertex_normals
        except Exception as exc:
            logger.warning("Trimesh vertex normal evaluation warning: %s", exc)

        has_valid_uv = False
        if hasattr(mesh, "visual") and mesh.visual is not None:
            uvs = getattr(mesh.visual, "uv", None)
            if (
                uvs is not None
                and len(uvs) == len(mesh.vertices)
                and not np.isnan(uvs).any()
                and not np.isinf(uvs).any()
            ):
                has_valid_uv = True

        if not has_valid_uv:
            logger.info("Generating automatic planar/box UV coordinates")
            mesh = MeshValidator._generate_uv_coordinates(mesh)

        mesh = MeshValidator._normalize_mesh_transform(mesh)

        report_after = MeshValidator.inspect(mesh)
        report_after.log_summary("Post-Repair Mesh")
        return mesh

    @staticmethod
    def _to_single_mesh(mesh_or_scene: Any) -> Any:
        if trimesh is None:
            return None
        if isinstance(mesh_or_scene, trimesh.Trimesh):
            return mesh_or_scene
        if isinstance(mesh_or_scene, trimesh.Scene):
            if len(mesh_or_scene.geometry) == 0:
                return None
            meshes = [g for g in mesh_or_scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if len(meshes) == 1:
                return meshes[0]
            elif len(meshes) > 1:
                return trimesh.util.concatenate(meshes)
        return getattr(mesh_or_scene, "mesh", None)

    @staticmethod
    def _generate_uv_coordinates(mesh: Any) -> Any:
        """Generate projection UV coordinates if missing or invalid."""
        if trimesh is None or not hasattr(mesh, "vertices"):
            return mesh

        verts = np.asarray(mesh.vertices, dtype=np.float64)
        if len(verts) == 0:
            return mesh

        min_bounds = np.min(verts, axis=0)
        max_bounds = np.max(verts, axis=0)
        extent = np.maximum(max_bounds - min_bounds, 1e-6)

        u = (verts[:, 0] - min_bounds[0]) / extent[0]
        v = (verts[:, 1] - min_bounds[1]) / extent[1]
        uvs = np.column_stack([u, v])

        existing_material = getattr(mesh.visual, "material", None) if hasattr(mesh, "visual") else None
        existing_image = getattr(existing_material, "image", None) if existing_material else None

        from trimesh.visual.material import SimpleMaterial
        from trimesh.visual.texture import TextureVisuals

        if existing_image is not None:
            mat = SimpleMaterial(image=existing_image)
            mesh.visual = TextureVisuals(uv=uvs, image=existing_image, material=mat)
        else:
            mesh.visual = TextureVisuals(uv=uvs)
        return mesh

    @staticmethod
    def _normalize_mesh_transform(mesh: Any) -> Any:
        """Center the mesh at origin and scale the bounding box to a sane size."""
        if trimesh is None or not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            return mesh

        center = mesh.centroid
        mesh.vertices -= center

        extents = mesh.extents
        max_extent = np.max(extents)
        if max_extent > 1e-6 and (max_extent < 0.2 or max_extent > 20.0):
            scale_factor = 2.0 / max_extent
            mesh.vertices *= scale_factor
            logger.info("Normalized model scale by factor %.4f", scale_factor)

        return mesh


def repair_mesh(mesh_or_scene: Any) -> Any:
    """Convenience wrapper around :meth:`MeshValidator.repair`."""
    return MeshValidator.repair(mesh_or_scene)
