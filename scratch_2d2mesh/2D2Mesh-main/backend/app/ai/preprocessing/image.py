"""Image preprocessing for the AI pipeline."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from app.config import get_settings


def preprocess_image(image_path: Path | str, max_side: Optional[int] = None) -> Image.Image:
    """Load an image, EXIF-rotate it, convert to RGB, and downscale to max_side."""
    max_side = max_side or get_settings().AI_MAX_IMAGE_SIZE
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return img.copy()


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def analyze_image(image: Image.Image) -> dict:
    """Return basic metadata for logging / diagnostics."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    has_alpha = alpha.getextrema() != (255, 255)
    return {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "aspect": round(image.width / max(1, image.height), 4),
        "has_alpha": bool(has_alpha),
    }
