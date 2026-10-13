"""Backward-compatible import path for shared AI utilities."""

from app.ai.exporters.gltf import glb_to_embedded_gltf
from app.ai.geometry.stats import compute_mesh_stats
from app.ai.preprocessing.image import image_to_png_bytes, preprocess_image
from app.ai.textures.material import color_hex_to_rgb_tuple

__all__ = [
    "preprocess_image",
    "image_to_png_bytes",
    "glb_to_embedded_gltf",
    "compute_mesh_stats",
    "color_hex_to_rgb_tuple",
]
