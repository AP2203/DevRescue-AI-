"""AI Mesh Repair Engine.

Deterministic repairs applied to a GLB mesh using trimesh.
Repairs:
- Fill holes (make watertight)
- Fix/recompute normals
- Remove duplicate vertices
- Remove degenerate faces
- Fix non-manifold geometry (split non-manifold edges)
- Merge disconnected components into a single mesh (optional)
- Remove unreferenced vertices

Returns repaired GLB bytes + before/after stats.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RepairResult:
    repaired_glb_bytes: bytes
    before_stats: Dict[str, Any]
    after_stats: Dict[str, Any]
    operations_applied: list


def repair_glb(
    glb_bytes: bytes,
    fill_holes: bool = True,
    fix_normals: bool = True,
    remove_duplicates: bool = True,
    remove_degenerate: bool = True,
    fix_winding: bool = True,
    merge_disconnected: bool = False,
    fix_non_manifold: bool = True,
    remove_disconnected: bool = True,
    reduce_geometry: bool = True,
    fix_textures: bool = True,
) -> RepairResult:
    """Load GLB, run all enabled repairs, return repaired GLB bytes."""
    try:
        import trimesh
    except ImportError:
        raise RuntimeError("trimesh is required for mesh repair.")

    scene = trimesh.load(io.BytesIO(glb_bytes), file_type="glb", force="scene")

    operations_applied = []

    # Collect meshes
    if remove_disconnected and hasattr(scene, "geometry") and len(scene.geometry) > 1:
        meshes = [g for g in scene.geometry.values() if hasattr(g, "faces")]
        if len(meshes) > 1:
            try:
                combined_mesh = trimesh.util.concatenate(meshes)
                # Re-create a single-mesh scene containing the combined mesh
                scene = trimesh.scene.Scene()
                scene.add_geometry(combined_mesh, geom_name="mesh")
                operations_applied.append("merged_disconnected_meshes")
            except Exception as e:
                logger.debug("Failed to concatenate scene meshes: %s", e)

    if hasattr(scene, "geometry"):
        mesh_items = list(scene.geometry.items())
    else:
        mesh_items = [("mesh", scene)]

    repaired_meshes = {}
    before_totals: Dict[str, Any] = {"vertices": 0, "faces": 0, "watertight_count": 0, "mesh_count": len(mesh_items)}
    after_totals: Dict[str, Any]  = {"vertices": 0, "faces": 0, "watertight_count": 0, "mesh_count": len(mesh_items)}

    for name, mesh in mesh_items:
        if not hasattr(mesh, "faces"):
            repaired_meshes[name] = mesh
            continue

        before_totals["vertices"] += len(mesh.vertices)
        before_totals["faces"] += len(mesh.faces)
        if hasattr(mesh, "is_watertight") and mesh.is_watertight:
            before_totals["watertight_count"] += 1

        m = mesh.copy()

        # Remove degenerate faces (zero-area)
        if remove_degenerate:
            try:
                orig_count = len(m.faces)
                areas = m.area_faces
                valid_mask = areas > 1e-10
                if not np.all(valid_mask):
                    m.update_faces(valid_mask)
                    removed = orig_count - int(np.sum(valid_mask))
                    logger.debug("Removed %d degenerate faces from %s", removed, name)
                    operations_applied.append(f"removed_degenerate:{removed}")
            except Exception as e:
                logger.debug("Degenerate face removal error: %s", e)

        # Remove unreferenced + duplicate vertices
        if remove_duplicates:
            try:
                m.remove_unreferenced_vertices()
                m.merge_vertices()
                operations_applied.append("merged_vertices")
            except Exception as e:
                logger.debug("Vertex merge error: %s", e)

        # Fill holes (make watertight)
        if fill_holes:
            try:
                trimesh.repair.fill_holes(m)
                operations_applied.append("fill_holes")
            except Exception as e:
                logger.debug("Fill holes error: %s", e)

        # Fix winding / face orientation
        if fix_winding:
            try:
                trimesh.repair.fix_winding(m)
                operations_applied.append("fix_winding")
            except Exception as e:
                logger.debug("Fix winding error: %s", e)

        # Fix normals (and inversions)
        if fix_normals:
            try:
                trimesh.repair.fix_inversion(m, multibody=True)
                trimesh.repair.fix_normals(m)
                m.vertex_normals  # trigger recompute
                operations_applied.append("fix_normals")
            except Exception as e:
                logger.debug("Fix normals error: %s", e)

        # Fix non-manifold geometry (split non-manifold edges)
        if fix_non_manifold:
            try:
                edges = m.edges_unique
                edges_inverse = m.edges_unique_inverse
                if edges is not None and len(edges) > 0 and edges_inverse is not None:
                    counts = np.bincount(edges_inverse, minlength=len(edges))
                    non_manifold_mask = counts > 2
                    if np.any(non_manifold_mask):
                        non_manifold_edges = edges[non_manifold_mask]
                        bad_edges = set(tuple(sorted(edge)) for edge in non_manifold_edges)
                        
                        faces_to_split = []
                        for face_idx, face in enumerate(m.faces):
                            face_edges = [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])]
                            for e in face_edges:
                                if tuple(sorted(e)) in bad_edges:
                                    faces_to_split.append(face_idx)
                                    break
                        
                        if faces_to_split:
                            new_vertices = list(m.vertices)
                            new_faces = list(m.faces)
                            for face_idx in faces_to_split:
                                face = new_faces[face_idx]
                                new_face = []
                                for v_idx in face:
                                    new_vertices.append(m.vertices[v_idx])
                                    new_face.append(len(new_vertices) - 1)
                                new_faces[face_idx] = new_face
                            
                            m = trimesh.Trimesh(
                                vertices=np.array(new_vertices),
                                faces=np.array(new_faces),
                                visual=m.visual.copy() if hasattr(m, "visual") else None,
                                process=False
                            )
                            operations_applied.append(f"split_non_manifold_edges:{len(non_manifold_edges)}")
            except Exception as e:
                logger.debug("Non-manifold split error: %s", e)

        # Remove tiny/broken disconnected components by keeping only the largest main shell
        if remove_disconnected:
            try:
                components = m.split(only_watertight=False)
                if len(components) > 1:
                    largest = max(components, key=lambda c: len(c.faces))
                    removed_count = len(components) - 1
                    m = largest
                    operations_applied.append(f"removed_disconnected_components:{removed_count}")
            except Exception as e:
                logger.debug("Disconnected components repair error: %s", e)

        # Reduce excessive geometry if it exceeds 100,000 faces
        if reduce_geometry:
            try:
                if len(m.faces) > 100_000:
                    from trimesh.simplify import simplify_quadric_decimation
                    simplified = simplify_quadric_decimation(m, 100_000)
                    reduced = len(m.faces) - len(simplified.faces)
                    m = simplified
                    operations_applied.append(f"reduced_polygons:{reduced}")
            except Exception as e:
                logger.debug("Excessive geometry reduction error: %s", e)

        # Repair missing or invalid texture references
        if fix_textures:
            try:
                from PIL import Image
                from trimesh.visual.texture import TextureVisuals
                from trimesh.visual.material import SimpleMaterial
                
                has_uv = hasattr(m, 'visual') and hasattr(m.visual, 'uv') and m.visual.uv is not None and len(m.visual.uv) > 0
                
                if has_uv:
                    is_texture_kind = getattr(m.visual, 'kind', None) == 'texture'
                    has_valid_img = False
                    if is_texture_kind:
                         try:
                             img = getattr(m.visual, 'image', None)
                             if img is not None and img.width > 0 and img.height > 0:
                                 has_valid_img = True
                         except Exception:
                             pass
                             
                    if not is_texture_kind or not has_valid_img:
                        # Create solid color fallback image (grey, RGB 200, 200, 200)
                        fallback_img = Image.new("RGB", (16, 16), (200, 200, 200))
                        m.visual = TextureVisuals(
                            uv=m.visual.uv,
                            image=fallback_img,
                            material=SimpleMaterial(image=fallback_img)
                        )
                        operations_applied.append("repaired_textures")
            except Exception as e:
                logger.debug("Texture repair error: %s", e)

        after_totals["vertices"] += len(m.vertices)
        after_totals["faces"] += len(m.faces)
        if hasattr(m, "is_watertight") and m.is_watertight:
            after_totals["watertight_count"] += 1

        repaired_meshes[name] = m

    # ── Reconstruct scene ───────────────────────────────────────────────────
    try:
        import trimesh
        new_scene = trimesh.scene.Scene()
        # Preserve original scene graph structure
        if hasattr(scene, "graph") and hasattr(scene, "geometry"):
            new_scene = scene.copy()
            for geom_name, repaired in repaired_meshes.items():
                if geom_name in new_scene.geometry:
                    new_scene.geometry[geom_name] = repaired
        else:
            for geom_name, repaired in repaired_meshes.items():
                new_scene.add_geometry(repaired, geom_name=geom_name)

        buf = io.BytesIO()
        new_scene.export(buf, file_type="glb")
        repaired_bytes = buf.getvalue()
    except Exception as exc:
        logger.error("Failed to export repaired scene: %s", exc)
        # Fall back to original bytes
        repaired_bytes = glb_bytes

    operations_applied = list(dict.fromkeys(operations_applied))

    return RepairResult(
        repaired_glb_bytes=repaired_bytes,
        before_stats=before_totals,
        after_stats=after_totals,
        operations_applied=operations_applied,
    )
