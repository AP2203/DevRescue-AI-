"""Texture and material helpers for the AI pipeline."""

from __future__ import annotations

from typing import Optional, Tuple

from PIL import Image

try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None


def material_has_texture(mesh) -> bool:
    """True when a mesh exposes an image-based material."""
    if mesh is None:
        return False
    material = getattr(getattr(mesh, "visual", None), "material", None)
    if material is None:
        return False
    image = getattr(material, "image", None) or getattr(material, "baseColorTexture", None)
    return image is not None


def texture_dimensions(mesh) -> Optional[Tuple[int, int]]:
    """Return ``(width, height)`` of the mesh's texture, or None."""
    if not material_has_texture(mesh):
        return None
    material = getattr(getattr(mesh, "visual", None), "material", None)
    image = getattr(material, "image", None) or getattr(material, "baseColorTexture", None)
    try:
        return (image.size[0], image.size[1])
    except Exception:  # pragma: no cover
        return None


def validate_texture(image: Optional[Image.Image]) -> Tuple[bool, str]:
    """Check an image is usable as a GPU texture."""
    if image is None:
        return False, "no texture image provided"
    if image.width < 1 or image.height < 1:
        return False, "texture has zero dimensions"
    if image.width > 8192 or image.height > 8192:
        return False, "texture exceeds 8192px (hardware limit)"
    if image.width & (image.width - 1) or image.height & (image.height - 1):
        return True, "non-power-of-two dimensions (compatible, may cost performance)"
    return True, "texture is valid"


def build_simple_material(image: Optional[Image.Image], base_color=(0.8, 0.8, 0.8, 1.0)):
    """Build a trimesh SimpleMaterial from an image or a flat color."""
    if trimesh is None:  # pragma: no cover
        return None
    from trimesh.visual.material import SimpleMaterial

    if image is not None:
        return SimpleMaterial(image=image)
    return SimpleMaterial(diffuse=list(base_color))


def color_hex_to_rgb_tuple(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
