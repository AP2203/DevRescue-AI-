#!/usr/bin/env python3
"""Performance and texturing metrics for model evaluation.

Measures memory usage (VRAM), processing speed, container file sizes,
and checks texture maps validity and coordinate completeness.
"""

import os
from pathlib import Path
from typing import Dict, Any

import numpy as np


def analyze_textures(mesh: Any) -> Dict[str, Any]:
    """Audit texture maps, UV completeness, and resolution in a mesh."""
    report = {
        "texture_presence": False,
        "texture_resolution": None,
        "texture_completeness": 0.0,  # percentage of vertices with valid UVs
        "texture_loading_success": False,
    }

    if mesh is None:
        return report

    # 1. Texture Presence & Load Check
    has_texture = False
    mat_loaded = False
    tex_res = None
    
    visual = getattr(mesh, "visual", None)
    if visual is not None:
        # Check if mesh visual has material with image texture
        mat = getattr(visual, "material", None)
        if mat is not None:
            img = getattr(mat, "image", None) or getattr(mat, "baseColorTexture", None)
            if img is not None:
                has_texture = True
                try:
                    # Test if the texture can be read/processed
                    _ = img.size
                    tex_res = max(img.size)
                    report["texture_resolution"] = f"{img.size[0]}x{img.size[1]}"
                    mat_loaded = True
                except Exception:
                    pass

        # 2. UV Completeness Check
        uvs = getattr(visual, "uv", None)
        if uvs is not None and len(uvs) == len(mesh.vertices):
            # Check for non-nan, non-inf coordinates
            valid_uvs = ~(np.isnan(uvs).any(axis=1) | np.isinf(uvs).any(axis=1))
            completeness = float(valid_uvs.sum() / len(mesh.vertices)) * 100.0
            report["texture_completeness"] = round(completeness, 2)
        else:
            report["texture_completeness"] = 0.0

    report["texture_presence"] = has_texture
    report["texture_loading_success"] = mat_loaded
    return report


def get_file_metrics(file_path: Path) -> Dict[str, Any]:
    """Record size of generated output file."""
    metrics = {
        "file_size_bytes": 0,
        "file_size_kb": 0.0,
    }
    if file_path.exists():
        size = file_path.stat().st_size
        metrics["file_size_bytes"] = size
        metrics["file_size_kb"] = round(size / 1024.0, 2)
    return metrics
