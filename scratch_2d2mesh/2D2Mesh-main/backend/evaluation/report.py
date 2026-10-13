#!/usr/bin/env python3
"""Evaluation Reporting and Exporter.

Aggregates individual sample evaluations, flags rejections and failure cases,
identifies worst-performing assets, and generates CSV, JSON, and Markdown comparison reports.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

logger = logging.getLogger(__name__)


def export_json(data: Dict[str, Any], path: Path) -> None:
    """Save report dict to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    logger.info("Saved JSON report: %s", path)


def export_csv(results: List[Dict[str, Any]], path: Path) -> None:
    """Flatten results and write to a CSV file."""
    if not results:
        return
    path.parent.mkdir(parents=True, exist_ok=True)

    # Flatten nested dictionaries (e.g. mesh_quality, textures) for CSV writing
    flat_results = []
    for r in results:
        flat = {}
        for k, v in r.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat[f"{k}_{sub_k}"] = sub_v
            else:
                flat[k] = v
        flat_results.append(flat)

    headers = flat_results[0].keys()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(flat_results)
    logger.info("Saved CSV report: %s", path)


def generate_markdown_summary(
    report_data: Dict[str, Any],
    path: Path,
    comparison_reports: List[Dict[str, Any]] = None
) -> None:
    """Write a human-readable Markdown summary report of the baseline evaluation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    model_name = report_data["model_name"]
    device = report_data["device"]["name"]
    results = report_data["results"]
    
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0.0
    
    # Compute aggregates for successful runs
    successful_runs = [r for r in results if r["success"]]
    avg_time = np_mean([r["inference_time_seconds"] for r in successful_runs])
    avg_chamfer = np_mean([r["geometry"].get("chamfer_distance", 0) for r in successful_runs if "geometry" in r])
    avg_fscore = np_mean([r["geometry"].get("f_score", 0) for r in successful_runs if "geometry" in r])
    avg_nc = np_mean([r["geometry"].get("normal_consistency", 0) for r in successful_runs if "geometry" in r])
    
    avg_verts = np_mean([r["mesh_quality"].get("vertices", 0) for r in successful_runs if "mesh_quality" in r])
    avg_faces = np_mean([r["mesh_quality"].get("faces", 0) for r in successful_runs if "mesh_quality" in r])
    watertight_count = sum(1 for r in successful_runs if r.get("mesh_quality", {}).get("watertight", False))
    watertight_rate = (watertight_count / len(successful_runs) * 100) if len(successful_runs) > 0 else 0.0

    lines = []
    lines.append(f"# Model Evaluation Summary: `{model_name}`")
    lines.append("")
    lines.append("## System Context")
    lines.append(f"- **Evaluated Model:** {model_name}")
    lines.append(f"- **Evaluation Device:** {device} ({report_data['device']['type']})")
    lines.append(f"- **Timestamp:** {report_data['timestamp']}")
    lines.append(f"- **Total Test Samples:** {total_count}")
    lines.append("")
    lines.append("## Core Metrics Summary")
    lines.append("| Metric | Value | Description |")
    lines.append("|---|---|---|")
    lines.append(f"| **Success Rate** | {success_rate:.1f}% | Percentage of generations completed |")
    lines.append(f"| **Avg Inference Time** | {avg_time:.2f}s | Average wall-clock execution speed |")
    lines.append(f"| **Avg Chamfer Distance** | {avg_chamfer:.4f} | Bidirectional average surface distance (L1) |")
    lines.append(f"| **Avg F-score** | {avg_fscore:.4f} | Percent of points within threshold (5% bbox diag) |")
    lines.append(f"| **Normal Consistency** | {avg_nc:.4f} | Cosine similarity of surface normals |")
    lines.append(f"| **Avg Vertices / Faces** | {int(avg_verts):,} / {int(avg_faces):,} | Reconstructed mesh complexity |")
    lines.append(f"| **Watertight Mesh Rate** | {watertight_rate:.1f}% | Percentage of watertight models |")
    lines.append("")

    # Worst performing objects (by Chamfer distance descending)
    valid_geoms = [r for r in successful_runs if "geometry" in r and r["geometry"].get("chamfer_distance") is not None]
    worst = sorted(valid_geoms, key=lambda x: x["geometry"]["chamfer_distance"], reverse=True)[:5]
    if worst:
        lines.append("## Worst Performing Test Examples")
        lines.append("These objects returned the largest Chamfer Distance discrepancy compared to ground truth:")
        lines.append("")
        lines.append("| Object ID | Chamfer Distance | F-score | Vertices | Faces |")
        lines.append("|---|---|---|---|---|")
        for r in worst:
            lines.append(
                f"| `{r['object_id']}` "
                f"| {r['geometry']['chamfer_distance']:.4f} "
                f"| {r['geometry']['f_score']:.4f} "
                f"| {r['mesh_quality']['vertices']:,} "
                f"| {r['mesh_quality']['faces']:,} |"
            )
        lines.append("")

    # Failure Cases
    failed_runs = [r for r in results if not r["success"]]
    if failed_runs:
        lines.append("## Generation Failure Log")
        lines.append("")
        lines.append("| Object ID | Error Message | Inference Time |")
        lines.append("|---|---|---|")
        for r in failed_runs:
            lines.append(f"| `{r['object_id']}` | `{r['error']}` | {r['inference_time_seconds']:.2f}s |")
        lines.append("")

    # Comparison Matrix Section
    if comparison_reports:
        lines.append("## Cross-Model Comparison Matrix")
        lines.append("Comparison of baseline metrics across different model runs:")
        lines.append("")
        lines.append("| Model Version | Success Rate | Avg Inference Time | Avg Chamfer | Avg F-score | Avg Faces | Watertight % |")
        lines.append("|---|---|---|---|---|---|---|")
        
        # Add current model
        lines.append(
            f"| **{model_name} (Current)** "
            f"| {success_rate:.1f}% "
            f"| {avg_time:.2f}s "
            f"| {avg_chamfer:.4f} "
            f"| {avg_fscore:.4f} "
            f"| {int(avg_faces):,} "
            f"| {watertight_rate:.1f}% |"
        )
        
        for comp in comparison_reports:
            comp_results = comp["results"]
            c_success = [r for r in comp_results if r["success"]]
            c_total = len(comp_results)
            c_success_rate = (len(c_success) / c_total * 100) if c_total > 0 else 0.0
            
            c_time = np_mean([r["inference_time_seconds"] for r in c_success])
            c_chamfer = np_mean([r["geometry"].get("chamfer_distance", 0) for r in c_success if "geometry" in r])
            c_fscore = np_mean([r["geometry"].get("f_score", 0) for r in c_success if "geometry" in r])
            c_faces = np_mean([r["mesh_quality"].get("faces", 0) for r in c_success if "mesh_quality" in r])
            c_watertight = sum(1 for r in c_success if r.get("mesh_quality", {}).get("watertight", False))
            c_watertight_rate = (c_watertight / len(c_success) * 100) if len(c_success) > 0 else 0.0

            lines.append(
                f"| {comp['model_name']} "
                f"| {c_success_rate:.1f}% "
                f"| {c_time:.2f}s "
                f"| {c_chamfer:.4f} "
                f"| {c_fscore:.4f} "
                f"| {int(c_faces):,} "
                f"| {c_watertight_rate:.1f}% |"
            )

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved Markdown summary: %s", path)


def np_mean(vals: List[float]) -> float:
    """Utility to calculate average of a list, handling empty lists safely."""
    if not vals:
        return 0.0
    return float(np.mean(vals))


def generate_per_sample_markdown(report_data: Dict[str, Any], path: Path) -> None:
    """Write a human-readable detailed per-sample report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    model_name = report_data["model_name"]
    results = report_data["results"]

    lines = []
    lines.append(f"# Per-Sample Evaluation Report: `{model_name}`")
    lines.append("")
    lines.append(f"Detailed metric listings for all {len(results)} samples evaluated.")
    lines.append("")

    for r in sorted(results, key=lambda x: x["object_id"]):
        lines.append(f"## Sample: `{r['object_id']}`")
        if not r["success"]:
            lines.append(f"- **Status:** FAILED")
            lines.append(f"- **Error:** `{r['error']}`")
            lines.append(f"- **Inference Time:** {r['inference_time_seconds']:.2f}s")
            lines.append("")
            continue

        lines.append(f"- **Status:** SUCCESS")
        lines.append(f"- **Inference Time:** {r['inference_time_seconds']:.2f}s")
        lines.append(f"- **Output File Size:** {r['file_size_bytes'] / 1024.0 / 1024.0:.2f} MB")
        lines.append("")
        
        # Geometry
        geom = r.get("geometry", {})
        if geom:
            lines.append("### Geometry Metrics")
            lines.append(f"- **Chamfer Distance:** {geom.get('chamfer_distance', 'N/A')}")
            lines.append(f"- **F-score:** {geom.get('f_score', 'N/A')}")
            lines.append(f"- **Normal Consistency:** {geom.get('normal_consistency', 'N/A')}")
            lines.append("")

        # Quality
        qual = r.get("mesh_quality", {})
        if qual:
            lines.append("### Mesh Quality & Topology")
            lines.append(f"- **Vertices / Faces:** {qual.get('vertices', 0):,} / {qual.get('faces', 0):,}")
            lines.append(f"- **Watertight:** {'YES' if qual.get('watertight') else 'NO'}")
            lines.append(f"- **Non-Manifold Edges:** {qual.get('non_manifold_edges', 0)}")
            lines.append(f"- **Degenerate Faces:** {qual.get('degenerate_faces', 0)}")
            lines.append(f"- **Disconnected Components:** {qual.get('disconnected_components', 0)}")
            lines.append(f"- **Invalid Normals (NaN/Inf):** {'YES' if qual.get('invalid_normals') else 'NO'}")
            lines.append("")

        # Textures
        tex = r.get("textures", {})
        if tex:
            lines.append("### Material & Texturing")
            lines.append(f"- **Texture Present:** {'YES' if tex.get('texture_presence') else 'NO'}")
            lines.append(f"- **Texture Resolution:** {tex.get('texture_resolution', 'N/A')}")
            lines.append(f"- **UV Coordinates Completeness:** {tex.get('texture_completeness', 0.0)}%")
            lines.append(f"- **Texture Image Loadable:** {'YES' if tex.get('texture_loading_success') else 'NO'}")
            lines.append("")

        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved Per-Sample report: %s", path)

