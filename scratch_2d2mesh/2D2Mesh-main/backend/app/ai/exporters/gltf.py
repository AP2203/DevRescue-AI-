"""GLB / GLTF / OBJ export and container validation."""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Optional

try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None


def validate_glb_bytes(data: bytes) -> Optional[str]:
    """Return an error message if ``data`` is not a valid GLB, else None."""
    if not data:
        return "empty GLB payload"
    if len(data) < 12:
        return "GLB header truncated"
    try:
        magic, version, length = struct.unpack_from("<III", data, 0)
    except struct.error:
        return "GLB header unreadable"
    if magic != 0x46546C67:
        return "invalid GLB magic (missing 'glTF' header)"
    if version != 2:
        return f"unsupported GLB version {version}"
    if length != len(data):
        return f"GLB length mismatch (header says {length}, actual {len(data)})"
    return None


def glb_to_embedded_gltf(glb_bytes: bytes) -> bytes:
    """Convert a GLB file into a self-contained .gltf with a base64 data URI."""
    if validate_glb_bytes(glb_bytes):
        raise ValueError("Not a valid GLB")
    magic, _version, _length = struct.unpack_from("<III", glb_bytes, 0)
    if magic != 0x46546C67:
        raise ValueError("Invalid GLB magic")
    offset = 12
    json_chunk: bytes = b""
    bin_chunk: bytes = b""
    while offset < len(glb_bytes):
        chunk_length, chunk_type = struct.unpack_from("<II", glb_bytes, offset)
        offset += 8
        payload = glb_bytes[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:  # JSON
            json_chunk = payload
        elif chunk_type == 0x004E4942:  # BIN
            bin_chunk = payload

    gltf = json.loads(json_chunk.decode("utf-8"))
    if bin_chunk:
        encoded = base64.b64encode(bin_chunk).decode("ascii")
        if gltf.get("buffers"):
            gltf["buffers"][0]["uri"] = f"data:application/octet-stream;base64,{encoded}"
            gltf["buffers"][0].pop("byteLength", None)
    return json.dumps(gltf, separators=(",", ":")).encode("utf-8")


def export_glb(scene_or_mesh) -> bytes:
    """Export a trimesh scene/mesh to GLB bytes."""
    if trimesh is None:
        raise RuntimeError("trimesh is required for GLB export")
    return scene_or_mesh.export(file_type="glb")


def export_obj_bytes(mesh) -> bytes:
    """Export a mesh to .obj text bytes (geometry only; material referenced)."""
    if trimesh is None:
        raise RuntimeError("trimesh is required for OBJ export")
    data = mesh.export(file_type="obj")
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def export_obj(mesh, output_dir: Path, filename: str = "model.obj") -> Path:
    """Write a mesh to ``output_dir`` as .obj (with .mtl and texture files)."""
    if trimesh is None:
        raise RuntimeError("trimesh is required for OBJ export")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / filename
    mesh.export(obj_path, file_type="obj")
    return obj_path
