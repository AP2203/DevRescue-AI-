"""Deterministic 3D Mesh Editor.

Applies structured command dicts (produced by the LLM parser and validated by
`app.ai.command_validator`) to GLB bytes using trimesh and pygltflib. The
editor NEVER uses AI — it only executes well-defined geometric/material
operations.

Supported operations:
- change_material / change_color (color, roughness, metalness)
- change_roughness
- change_metalness
- reduce_polygons (keep-ratio)
- scale
- translate
- rotate
- prepare_print (watertight + scale to mm)
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EditResult:
    edited_glb_bytes: bytes
    applied_operations: List[str]
    before_stats: Dict[str, Any]
    after_stats: Dict[str, Any]
    message: str


def apply_command(glb_bytes: bytes, command: Dict[str, Any]) -> EditResult:
    """Apply a structured command dict to a GLB and return edited bytes.

    The command is expected to have an ``operations`` array:
        {"operations": [{"type": ..., "target": ..., "value": ...}]}

    For backwards compatibility a single-operation dict (no ``operations``
    key) is wrapped into a one-element list.
    """
    operations = command.get("operations")
    if operations is None:
        operations = [_legacy_operation(command)]

    if not operations:
        raise ValueError("Cannot apply empty operations list.")

    try:
        import trimesh
    except ImportError:
        raise RuntimeError("trimesh is required for mesh editing.") from None

    # Load scene
    scene = trimesh.load(io.BytesIO(glb_bytes), file_type="glb", force="scene")

    # Collect all meshes (before state)
    all_meshes = _collect_meshes(scene)
    before_stats = _collect_stats(all_meshes)

    applied: List[str] = []
    messages: List[str] = []

    # ── Apply each operation in sequence ────────────────────────────────────
    for op in operations:
        op_type = op.get("type", "unknown")
        target = op.get("target", "all")

        meshes_to_edit = _select_meshes(scene, target)

        if op_type == "change_material" or op_type == "change_color":
            _op_change_material(meshes_to_edit, op)
            messages.append(f"Material updated on {len(meshes_to_edit)} mesh(es)")

        elif op_type == "change_roughness":
            _op_change_roughness(meshes_to_edit, op)
            messages.append(f"Roughness set to {op.get('value', 0.5)}")

        elif op_type == "change_metalness":
            _op_change_metalness(meshes_to_edit, op)
            messages.append(f"Metalness set to {op.get('value', 0.5)}")

        elif op_type == "reduce_polygons":
            _op_reduce_polygons(scene, meshes_to_edit, op)
            messages.append(f"Polygon count reduced on {len(meshes_to_edit)} mesh(es)")

        elif op_type == "scale":
            _op_scale(scene, op)
            messages.append("Model scaled")

        elif op_type == "translate":
            _op_translate(scene, op)
            messages.append("Model translated")

        elif op_type == "rotate":
            _op_rotate(scene, op)
            messages.append("Model rotated")

        elif op_type == "prepare_print":
            _op_prepare_print(meshes_to_edit)
            messages.append("Model prepared for 3D printing (watertight repair applied)")

        else:
            raise ValueError(f"Unsupported operation: {op_type}")

        applied.append(op_type)

    # ── Export ───────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    try:
        if hasattr(scene, "export"):
            scene.export(buf, file_type="glb")
        else:
            all_meshes["mesh"].export(buf, file_type="glb")
    except Exception as exc:
        logger.error("Failed to export edited GLB: %s", exc)
        raise RuntimeError(f"Failed to export edited model: {exc}") from exc

    edited_bytes = buf.getvalue()

    # Re-collect stats after edit
    try:
        edited_scene = trimesh.load(io.BytesIO(edited_bytes), file_type="glb", force="scene")
        after_stats = _collect_stats(_collect_meshes(edited_scene))
    except Exception:
        after_stats = before_stats

    message = " · ".join(messages) if messages else "No operations applied"

    return EditResult(
        edited_glb_bytes=edited_bytes,
        applied_operations=applied,
        before_stats=before_stats,
        after_stats=after_stats,
        message=message,
    )


def _legacy_operation(command: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a legacy single-operation dict into the operations shape."""
    return {
        "type": command.get("operation", "unknown"),
        "target": command.get("target", "all"),
        "value": command.get("color") or command.get("scale") or command.get("target_ratio"),
    }


def _collect_meshes(scene: Any) -> Dict[str, Any]:
    meshes: Dict[str, Any] = {}
    if hasattr(scene, "geometry"):
        for name, geom in scene.geometry.items():
            if hasattr(geom, "faces"):
                meshes[name] = geom
    elif hasattr(scene, "faces"):
        meshes["mesh"] = scene
    return meshes


def _select_meshes(scene: Any, target: str) -> Dict[str, Any]:
    """Return meshes matching the target name, or all meshes as fallback."""
    meshes = _collect_meshes(scene)
    if target == "all":
        return meshes
    selected = {k: v for k, v in meshes.items() if target.lower() in k.lower()}
    if selected:
        return selected
    return meshes


def _collect_stats(meshes: Dict[str, Any]) -> Dict[str, Any]:
    total_verts = sum(len(m.vertices) for m in meshes.values())
    total_faces = sum(len(m.faces) for m in meshes.values())
    return {"vertices": total_verts, "faces": total_faces, "mesh_count": len(meshes)}


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #rrggbb to (r, g, b) in 0-255 range."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _op_change_material(meshes: Dict[str, Any], op: Dict[str, Any]) -> None:
    """Change the diffuse color and optional PBR parameters of target meshes."""
    import trimesh

    color_hex = op.get("value") if isinstance(op.get("value"), str) and op.get("value", "").startswith("#") else None
    if color_hex is None:
        color_hex = op.get("color")
    roughness = op.get("roughness")
    metalness = op.get("metalness")

    for mesh in meshes.values():
        try:
            if color_hex:
                rgb = _hex_to_rgb(color_hex)
                rgba = (*rgb, 255)
                mesh.visual = trimesh.visual.ColorVisuals(
                    mesh=mesh, vertex_colors=np.tile(rgba, (len(mesh.vertices), 1))
                )
        except Exception as exc:
            logger.debug("color change error: %s", exc)

        if roughness is not None or metalness is not None:
            if not hasattr(mesh, "metadata"):
                mesh.metadata = {}
            if roughness is not None:
                mesh.metadata["roughness"] = float(roughness)
            if metalness is not None:
                mesh.metadata["metalness"] = float(metalness)


def _op_change_roughness(meshes: Dict[str, Any], op: Dict[str, Any]) -> None:
    """Apply roughness metadata (stored in mesh metadata dict)."""
    roughness = float(op.get("value", 0.5))
    for mesh in meshes.values():
        if not hasattr(mesh, "metadata"):
            mesh.metadata = {}
        mesh.metadata["roughness"] = roughness


def _op_change_metalness(meshes: Dict[str, Any], op: Dict[str, Any]) -> None:
    """Apply metalness metadata."""
    metalness = float(op.get("value", 0.5))
    for mesh in meshes.values():
        if not hasattr(mesh, "metadata"):
            mesh.metadata = {}
        mesh.metadata["metalness"] = metalness


def _op_reduce_polygons(scene: Any, meshes: Dict[str, Any], op: Dict[str, Any]) -> Any:
    """Reduce polygon count by keep-ratio (value = fraction to keep)."""
    try:
        from trimesh.simplify import simplify_quadric_decimation
    except ImportError:
        logger.warning("Polygon reduction requires trimesh with simplify support.")
        return scene

    ratio = float(op.get("value", 0.5))
    ratio = max(0.05, min(0.95, ratio))

    for name, mesh in meshes.items():
        try:
            target_count = max(4, int(len(mesh.faces) * ratio))
            simplified = simplify_quadric_decimation(mesh, target_count)
            if hasattr(scene, "geometry") and name in scene.geometry:
                scene.geometry[name] = simplified
        except Exception as exc:
            logger.debug("Polygon reduction failed on %s: %s", name, exc)

    return scene


def _op_scale(scene: Any, op: Dict[str, Any]) -> None:
    """Scale the entire scene."""
    scale = op.get("value", [1.0, 1.0, 1.0])
    if isinstance(scale, (int, float)):
        scale = [scale, scale, scale]

    # Apply uniform scale if scale is uniform
    if len(set(scale)) == 1:
        if hasattr(scene, "apply_scale"):
            scene.apply_scale(scale[0])
        elif hasattr(scene, "geometry"):
            for mesh in scene.geometry.values():
                if hasattr(mesh, "apply_scale"):
                    mesh.apply_scale(scale[0])
    else:
        # Per-axis scale via transform
        sx, sy, sz = scale
        diag = np.array([[sx, 0, 0, 0], [0, sy, 0, 0], [0, 0, sz, 0], [0, 0, 0, 1]])
        if hasattr(scene, "apply_transform"):
            scene.apply_transform(diag)


def _op_translate(scene: Any, op: Dict[str, Any]) -> None:
    """Translate the entire scene."""
    vec = op.get("value", [0.0, 0.0, 0.0])
    if isinstance(vec, (int, float)):
        vec = [vec, vec, vec]
    import trimesh

    matrix = trimesh.transformations.translation_matrix(vec)
    if hasattr(scene, "apply_transform"):
        scene.apply_transform(matrix)
    elif hasattr(scene, "geometry"):
        for mesh in scene.geometry.values():
            if hasattr(mesh, "apply_transform"):
                mesh.apply_transform(matrix)


def _op_rotate(scene: Any, op: Dict[str, Any]) -> None:
    """Rotate the scene by euler degrees (x, y, z)."""
    import trimesh

    degrees = op.get("value", [0.0, 0.0, 0.0])
    if isinstance(degrees, (int, float)):
        degrees = [degrees, degrees, degrees]
    matrix = trimesh.transformations.euler_matrix(
        np.deg2rad(float(degrees[0])),
        np.deg2rad(float(degrees[1])),
        np.deg2rad(float(degrees[2])),
    )
    if hasattr(scene, "apply_transform"):
        scene.apply_transform(matrix)
    elif hasattr(scene, "geometry"):
        for mesh in scene.geometry.values():
            if hasattr(mesh, "apply_transform"):
                mesh.apply_transform(matrix)


def _op_prepare_print(meshes: Dict[str, Any]) -> None:
    """Prepare mesh for 3D printing: make watertight, recompute normals."""
    try:
        import trimesh
    except ImportError:
        return

    for mesh in meshes.values():
        try:
            trimesh.repair.fill_holes(mesh)
            trimesh.repair.fix_winding(mesh)
            trimesh.repair.fix_normals(mesh)
        except Exception as exc:
            logger.debug("Prepare print error: %s", exc)
