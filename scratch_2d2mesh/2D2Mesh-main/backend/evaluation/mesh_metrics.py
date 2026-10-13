#!/usr/bin/env python3
"""Mesh metrics calculation for model evaluation.

Computes geometric distance metrics (Chamfer Distance, F-score, Normal Consistency)
and topological quality metrics (watertightness, manifoldness, degenerate elements)
between a generated mesh and a ground truth mesh.
"""

import logging
from typing import Dict, Any, Tuple

import numpy as np
from scipy.spatial import KDTree

logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:
    trimesh = None
    logger.warning("trimesh is not installed; mesh metrics will be unavailable.")


def sample_mesh(mesh: Any, num_samples: int = 2000) -> Tuple[np.ndarray, np.ndarray]:
    """Sample points and their corresponding face normals from the mesh surface."""
    points, face_indices = trimesh.sample.sample_surface(mesh, num_samples)
    normals = mesh.face_normals[face_indices]
    return points, normals


def compute_chamfer_and_fscore(
    gen_mesh: Any,
    gt_mesh: Any,
    num_samples: int = 2000,
    tau_multiplier: float = 0.05
) -> Tuple[float, float, float]:
    """Calculate Chamfer Distance, F-score, and Normal Consistency between two meshes."""
    if trimesh is None:
        return 0.0, 0.0, 0.0

    # 1. Sample points from both meshes
    gen_pts, gen_normals = sample_mesh(gen_mesh, num_samples)
    gt_pts, gt_normals = sample_mesh(gt_mesh, num_samples)

    # 2. Build KDTrees
    gen_tree = KDTree(gen_pts)
    gt_tree = KDTree(gt_pts)

    # 3. Query closest points
    # For every generated point, find closest ground truth point
    dist_gen_to_gt, idx_gen_to_gt = gt_tree.query(gen_pts)
    # For every ground truth point, find closest generated point
    dist_gt_to_gen, idx_gt_to_gen = gen_tree.query(gt_pts)

    # 4. Chamfer Distance (Average Euclidean Distance)
    # CD = mean(dist(gen -> gt)) + mean(dist(gt -> gen))
    chamfer_dist = float(dist_gen_to_gt.mean() + dist_gt_to_gen.mean())

    # 5. F-score Calculation
    # Threshold tau is defined relative to the ground truth bounding box diagonal
    bbox = gt_mesh.bounds
    diagonal = float(np.linalg.norm(bbox[1] - bbox[0]))
    tau = max(1e-4, diagonal * tau_multiplier)

    # Precision: percent of generated points within tau of ground truth
    precision = float((dist_gen_to_gt < tau).sum() / num_samples)
    # Recall: percent of ground truth points within tau of generated
    recall = float((dist_gt_to_gen < tau).sum() / num_samples)

    # F-score (harmonic mean of precision and recall)
    if precision + recall > 1e-8:
        f_score = 2.0 * (precision * recall) / (precision + recall)
    else:
        f_score = 0.0

    # 6. Normal Consistency (Average Cosine Similarity of normals of closest points)
    # Cosine similarity of gen normal i and its closest gt normal index
    cos_sim_gen = np.abs(np.sum(gen_normals * gt_normals[idx_gen_to_gt], axis=1))
    # Cosine similarity of gt normal i and its closest gen normal index
    cos_sim_gt = np.abs(np.sum(gt_normals * gen_normals[idx_gt_to_gen], axis=1))
    
    normal_consistency = float(0.5 * (cos_sim_gen.mean() + cos_sim_gt.mean()))

    return chamfer_dist, f_score, normal_consistency


def analyze_mesh_quality(mesh: Any) -> Dict[str, Any]:
    """Inspect topological and validation metrics of a mesh."""
    quality: Dict[str, Any] = {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "polygons": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "non_manifold_edges": 0,
        "degenerate_faces": 0,
        "disconnected_components": 1,
        "invalid_normals": False,
        "bbox_volume": 0.0,
    }

    # 1. Non-manifold edges
    try:
        non_manifold = trimesh.repair.non_manifold_edges(mesh)
        quality["non_manifold_edges"] = len(non_manifold)
    except Exception:
        pass

    # 2. Degenerate faces (zero-area or repeated vertices)
    try:
        faces = np.asarray(mesh.faces)
        dup_verts = (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
        areas = getattr(mesh, "area_faces", None)
        if areas is not None:
            zero_area = np.asarray(areas) <= 1e-12
            quality["degenerate_faces"] = int(np.sum(dup_verts | zero_area))
        else:
            quality["degenerate_faces"] = int(np.sum(dup_verts))
    except Exception:
        pass

    # 3. Disconnected components
    try:
        quality["disconnected_components"] = len(mesh.split())
    except Exception:
        pass

    # 4. Invalid normals (NaNs/Infs check)
    try:
        normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
        has_nan = np.isnan(normals).any() or np.isinf(normals).any()
        quality["invalid_normals"] = bool(has_nan)
    except Exception:
        quality["invalid_normals"] = True

    # 5. Bounding box volume
    try:
        bbox = mesh.bounds
        extents = bbox[1] - bbox[0]
        quality["bbox_volume"] = float(np.prod(extents))
    except Exception:
        pass

    return quality
