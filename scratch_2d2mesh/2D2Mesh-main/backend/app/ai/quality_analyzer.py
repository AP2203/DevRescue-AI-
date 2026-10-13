"""AI 3D Quality Analyzer.

Analyzes a GLB/mesh for quality across 7 dimensions using trimesh and returns
a rich quality report with scores, detected issues (with severity), and
recommendations. No GPU or ML model required — deterministic geometric analysis
only.

Analyzed aspects:
- Geometry quality (watertightness, holes / open boundaries)
- Topology (non-manifold edges, degenerate faces, duplicate vertices,
  disconnected components)
- Texture quality (material map + UV coordinates)
- Completeness (empty / near-empty scenes, overall content)
- Polygon count budget
- Vertex normals
"""

from __future__ import annotations

import contextlib
import io
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ── Dimension weights (must sum to 1.0) ────────────────────────────────────

_WEIGHTS: Dict[str, float] = {
    "geometry": 0.20,
    "topology": 0.20,
    "texture": 0.15,
    "completeness": 0.15,
    "polygon_count": 0.10,
    "mesh_errors": 0.10,
    "normals": 0.10,
}


@dataclass
class DimensionResult:
    name: str
    score: float  # 0-100
    weight: float
    details: str


@dataclass
class Problem:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    value: Optional[Any] = None


@dataclass
class AnalysisResult:
    overall_score: float
    dimensions: List[DimensionResult]
    problems: List[Problem]
    recommendations: List[str]
    stats_snapshot: Dict[str, Any]


@dataclass
class _MeshMetrics:
    """Per-mesh metrics gathered by the analyzer."""

    vertices: int = 0
    faces: int = 0
    unique_edges: int = 0
    watertight: bool = False
    boundary_edges: int = 0  # edges used by exactly one face (holes)
    non_manifold_edges: int = 0  # edges used by more than two faces
    degenerate_faces: int = 0  # zero-area faces
    duplicate_vertices: int = 0
    has_texture: bool = False
    has_uvs: bool = False
    has_normals: bool = False
    components: int = 1  # number of disconnected pieces in the mesh


def analyze_glb(glb_bytes: bytes) -> AnalysisResult:
    """Analyze a GLB file and return a quality report."""
    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError(
            "trimesh is required for quality analysis. Install it with: pip install trimesh"
        ) from exc

    problems: List[Problem] = []
    recommendations: List[str] = []

    # ── Load scene ──────────────────────────────────────────────────────────
    try:
        scene = trimesh.load(io.BytesIO(glb_bytes), file_type="glb", force="scene")
    except Exception as exc:
        logger.warning("Failed to load GLB: %s", exc)
        return AnalysisResult(
            overall_score=0.0,
            dimensions=[],
            problems=[Problem("error", "load_failed", f"Cannot parse GLB: {exc}")],
            recommendations=["Re-generate the model or check the file format."],
            stats_snapshot={},
        )

    meshes: List[Any] = []
    if hasattr(scene, "geometry"):
        meshes = [g for g in scene.geometry.values() if hasattr(g, "faces")]
    elif hasattr(scene, "faces"):
        meshes = [scene]

    # ── Per-mesh metrics ────────────────────────────────────────────────────
    metrics = [_analyze_mesh(m) for m in meshes]

    stats: Dict[str, Any] = _aggregate(metrics)

    # ── Score each dimension ────────────────────────────────────────────────
    geometry_score = _score_geometry(stats, problems, recommendations)
    topology_score = _score_topology(stats, problems, recommendations)
    texture_score = _score_texture(stats, problems, recommendations)
    completeness_score = _score_completeness(stats, problems, recommendations)
    polygon_score = _score_polygon_count(stats, problems, recommendations)
    error_score = _score_mesh_errors(stats, problems, recommendations)
    normals_score = _score_normals(stats, problems, recommendations)

    # ── Weighted overall score ──────────────────────────────────────────────
    dim_scores = {
        "geometry": geometry_score,
        "topology": topology_score,
        "texture": texture_score,
        "completeness": completeness_score,
        "polygon_count": polygon_score,
        "mesh_errors": error_score,
        "normals": normals_score,
    }

    overall = sum(dim_scores[k] * _WEIGHTS[k] for k in dim_scores)
    overall = round(min(100.0, max(0.0, overall)), 1)

    dimensions = [
        DimensionResult(
            name=k,
            score=round(v, 1),
            weight=_WEIGHTS[k],
            details=_dim_details(k, v, stats),
        )
        for k, v in dim_scores.items()
    ]

    return AnalysisResult(
        overall_score=overall,
        dimensions=dimensions,
        problems=problems,
        recommendations=list(dict.fromkeys(recommendations)),  # dedupe preserving order
        stats_snapshot=stats,
    )


# ── Per-mesh analysis ──────────────────────────────────────────────────────


def _analyze_mesh(mesh: Any) -> _MeshMetrics:
    m = _MeshMetrics()
    try:
        m.vertices = int(mesh.vertices.shape[0])
    except Exception:
        m.vertices = 0
    try:
        m.faces = int(mesh.faces.shape[0])
    except Exception:
        m.faces = 0

    with contextlib.suppress(Exception):
        m.watertight = bool(mesh.is_watertight)

    # Unique edge usage counts: how many faces reference each undirected edge.
    # count == 1 -> boundary/open edge (hole), count > 2 -> non-manifold edge.
    try:
        if m.faces > 0:
            inverse = getattr(mesh, "edges_unique_inverse", None)
            unique = getattr(mesh, "edges_unique", None)
            if inverse is not None and len(inverse) > 0 and unique is not None:
                counts = np.bincount(inverse, minlength=len(unique))
                m.unique_edges = len(unique)
                m.boundary_edges = int(np.sum(counts == 1))
                m.non_manifold_edges = int(np.sum(counts > 2))
    except Exception:
        pass

    try:
        areas = mesh.area_faces
        m.degenerate_faces = int(np.sum(np.asarray(areas) < 1e-10))
    except Exception:
        pass

    try:
        if m.vertices > 0:
            _unique, counts = np.unique(mesh.vertices, axis=0, return_counts=True)
            m.duplicate_vertices = int(np.sum(counts > 1))
    except Exception:
        pass

    vis = getattr(mesh, "visual", None)
    if vis is not None:
        kind = getattr(vis, "kind", None)
        if kind == "texture":
            m.has_texture = True
            uv = getattr(vis, "uv", None)
            m.has_uvs = uv is not None and len(uv) > 0
        elif kind is None:
            uv = getattr(vis, "uv", None)
            if uv is not None and len(uv) > 0:
                m.has_uvs = True

    try:
        normals = getattr(mesh, "vertex_normals", None)
        m.has_normals = normals is not None and len(normals) > 0
    except Exception:
        pass

    try:
        m.components = max(1, len(mesh.split(only_watertight=False)))
    except Exception:
        m.components = 1

    return m


def _aggregate(metrics: List[_MeshMetrics]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "vertices": 0,
        "faces": 0,
        "triangles": 0,
        "edges": 0,
        "mesh_count": len(metrics),
        "watertight_count": 0,
        "boundary_edges": 0,
        "non_manifold_edges": 0,
        "degenerate_faces": 0,
        "duplicate_vertices": 0,
        "has_texture": False,
        "has_uvs": False,
        "has_normals": False,
        "disconnected_components": 0,
    }
    for m in metrics:
        stats["vertices"] += m.vertices
        stats["faces"] += m.faces
        stats["triangles"] += m.faces
        stats["edges"] += m.unique_edges
        stats["watertight_count"] += int(m.watertight)
        stats["boundary_edges"] += m.boundary_edges
        stats["non_manifold_edges"] += m.non_manifold_edges
        stats["degenerate_faces"] += m.degenerate_faces
        stats["duplicate_vertices"] += m.duplicate_vertices
        stats["has_texture"] = stats["has_texture"] or m.has_texture
        stats["has_uvs"] = stats["has_uvs"] or m.has_uvs
        stats["has_normals"] = stats["has_normals"] or m.has_normals
        stats["disconnected_components"] += m.components
    return stats


# ── Dimension scoring ──────────────────────────────────────────────────────


def _score_geometry(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    """Watertightness + open boundary (hole) closure."""
    mesh_count = stats["mesh_count"]
    watertight_count = stats["watertight_count"]
    boundary_edges = stats["boundary_edges"]
    edges = stats["edges"]

    score = 100.0
    if mesh_count == 0:
        return 0.0

    watertight_ratio = watertight_count / mesh_count
    # Surface closure: fraction of unique edges that are NOT open boundaries.
    closure_ratio = 1.0 if edges == 0 else (edges - boundary_edges) / max(edges, 1)
    score = 100.0 * (0.6 * watertight_ratio + 0.4 * closure_ratio)

    if boundary_edges > 0:
        problems.append(
            Problem(
                "warning" if watertight_ratio > 0 else "error",
                "open_boundary_holes",
                f"{boundary_edges:,} open boundary edge(s) detected — the surface has holes.",
                {"boundary_edges": boundary_edges},
            )
        )
        recommendations.append("Use Auto Repair to fill holes and make the mesh watertight.")
    if watertight_ratio < 0.5:
        problems.append(
            Problem(
                "error",
                "non_watertight",
                f"Only {watertight_count}/{mesh_count} mesh(es) are watertight (closed).",
                {"watertight": watertight_count, "total": mesh_count},
            )
        )

    return round(min(100.0, max(0.0, score)), 1)


def _score_topology(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    """Non-manifold edges, degenerate faces, duplicate vertices, components."""
    score = 100.0
    non_manifold = stats["non_manifold_edges"]
    degenerate = stats["degenerate_faces"]
    duplicate = stats["duplicate_vertices"]
    total_faces = stats["faces"]

    if non_manifold > 0:
        score -= min(60.0, non_manifold * 10.0)
        problems.append(
            Problem(
                "error",
                "non_manifold_edges",
                f"{non_manifold:,} non-manifold edge(s) detected (shared by more than 2 faces).",
                {"count": non_manifold},
            )
        )
        recommendations.append("Use Auto Repair to fix non-manifold geometry.")

    if total_faces > 0 and degenerate > 0:
        degenerate_ratio = degenerate / total_faces
        score -= min(40.0, degenerate_ratio * 500.0)
        problems.append(
            Problem(
                "warning",
                "degenerate_faces",
                f"{degenerate:,} degenerate (zero-area) face(s) detected.",
                {"count": degenerate},
            )
        )
        recommendations.append("Use Auto Repair to remove degenerate faces.")

    if duplicate > 100:
        score = min(score, 70.0)
        problems.append(
            Problem(
                "warning",
                "duplicate_vertices",
                f"{duplicate:,} duplicate vertex(es) detected.",
                {"count": duplicate},
            )
        )
        recommendations.append("Use Auto Repair to merge duplicate vertices.")

    if stats["disconnected_components"] > 1:
        score = min(score, 90.0)
        problems.append(
            Problem(
                "info",
                "disconnected_components",
                f"{stats['disconnected_components']} disconnected component(s) detected.",
                {"count": stats["disconnected_components"]},
            )
        )
        recommendations.append("Use Auto Repair to merge or clean up disconnected components.")

    return round(min(100.0, max(0.0, score)), 1)


def _score_texture(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    score = 100.0 if stats["has_texture"] else 40.0
    if not stats["has_texture"]:
        problems.append(
            Problem(
                "warning",
                "no_texture",
                "No texture map found. The model uses a solid/flat material.",
            )
        )
        recommendations.append("For richer visuals, consider adding a texture in a 3D editor.")
    elif not stats["has_uvs"]:
        score = 60.0
        problems.append(
            Problem(
                "warning",
                "no_uvs",
                "Texture present but UV coordinates are missing.",
            )
        )
    return score


def _score_completeness(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    total_faces = stats["faces"]
    total_vertices = stats["vertices"]
    mesh_count = stats["mesh_count"]

    if mesh_count == 0 or total_faces == 0:
        problems.append(Problem("error", "empty_scene", "The GLB contains no mesh geometry."))
        recommendations.append("Re-generate the model — the AI output was empty.")
        return 0.0

    if total_vertices < 3:
        problems.append(Problem("error", "degenerate_mesh", "The model has no meaningful geometry."))
        return 0.0

    if total_faces < 12:
        score = 40.0
        problems.append(
            Problem(
                "warning",
                "very_low_detail",
                f"Only {total_faces:,} face(s) — the model has very little geometric detail.",
                {"faces": total_faces},
            )
        )
    elif total_faces < 100:
        score = 70.0
        problems.append(
            Problem(
                "info",
                "low_detail",
                f"{total_faces:,} face(s) — the model is low-poly.",
                {"faces": total_faces},
            )
        )
    else:
        score = 100.0

    if stats["disconnected_components"] > 1:
        score = min(score, 85.0)

    return score


def _score_polygon_count(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    total_faces = stats["faces"]
    if total_faces < 100:
        score = 30.0
        problems.append(
            Problem(
                "warning",
                "too_few_polygons",
                f"Only {total_faces:,} face(s) — model lacks geometric detail.",
                {"faces": total_faces},
            )
        )
    elif total_faces < 1000:
        score = 60.0
    elif total_faces > 500_000:
        score = 40.0
        problems.append(
            Problem(
                "warning",
                "excessive_polygons",
                f"{total_faces:,} face(s) — may be too heavy for real-time use.",
                {"faces": total_faces},
            )
        )
        recommendations.append("Use Model Optimization (Web or Game profile) to reduce polygon count.")
    elif total_faces > 200_000:
        score = 75.0
        problems.append(
            Problem(
                "info",
                "high_polygon_count",
                f"{total_faces:,} face(s) — consider optimization for web/game use.",
                {"faces": total_faces},
            )
        )
    else:
        score = 100.0
    return score


def _score_mesh_errors(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    score = 100.0
    if stats["non_manifold_edges"] > 0:
        score -= min(50.0, stats["non_manifold_edges"] * 8.0)
        problems.append(
            Problem(
                "error",
                "non_manifold_geometry",
                f"{stats['non_manifold_edges']:,} non-manifold edge(s) make the mesh invalid for printing.",
                {"count": stats["non_manifold_edges"]},
            )
        )
        recommendations.append("Use Auto Repair to fix non-manifold geometry.")
    if stats["degenerate_faces"] > 0:
        score -= min(20.0, stats["degenerate_faces"] * 2.0)
    if not stats["has_normals"]:
        score = min(score, 70.0)
        problems.append(
            Problem(
                "warning",
                "missing_normals",
                "Vertex normals are missing or could not be detected.",
            )
        )
        recommendations.append("Use Auto Repair to recompute vertex normals.")
    return round(min(100.0, max(0.0, score)), 1)


def _score_normals(stats: Dict[str, Any], problems: List[Problem], recommendations: List[str]) -> float:
    return 100.0 if stats["has_normals"] else 30.0


# ── Dimension details ──────────────────────────────────────────────────────


def _dim_details(name: str, score: float, stats: Dict[str, Any]) -> str:
    labels = {
        "geometry": (
            f"Watertight: {stats.get('watertight_count', 0)}/{max(stats.get('mesh_count', 1), 1)} meshes"
            f" | Open edges: {stats.get('boundary_edges', 0):,}"
        ),
        "topology": (
            f"Non-manifold edges: {stats.get('non_manifold_edges', 0):,}"
            f" | Degenerate faces: {stats.get('degenerate_faces', 0):,}"
            f" | Components: {stats.get('disconnected_components', 0)}"
        ),
        "texture": "PBR texture detected" if stats.get("has_texture") else "No texture map",
        "completeness": f"{stats.get('vertices', 0):,} vertices, {stats.get('faces', 0):,} faces",
        "polygon_count": f"{stats.get('faces', 0):,} faces",
        "mesh_errors": "No critical errors" if score > 90 else f"Score: {score:.0f}/100",
        "normals": "Valid normals" if stats.get("has_normals") else "Missing vertex normals",
    }
    return labels.get(name, "")
