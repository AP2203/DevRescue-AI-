#!/usr/bin/env python3
"""Model Evaluation and Benchmarking Suite.

Orchestrates the baseline evaluation loop:
- Iterates over paired assets in the test split
- Executes model inference
- Measures geometry correctness, topological mesh quality, texture mappings, and speeds
- Exports detailed JSON, CSV, and Markdown comparison reports
"""

import argparse
import asyncio
import io
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

# Add backend directory to sys.path to allow importing backend app
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure environment defaults before importing app code
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")

try:
    from app.ai.factory import create_ai_model, ModelNotAvailableError
    from app.ai.types import GenerationSettings
    from app.ai.inference.device import get_device_info, vram_snapshot
except ImportError as exc:
    print(f"Error: Failed to import backend app modules: {exc}")
    sys.exit(1)

# Import local evaluation modules
from evaluation.mesh_metrics import compute_chamfer_and_fscore, analyze_mesh_quality
from evaluation.metrics import analyze_textures, get_file_metrics
from evaluation.report import export_json, export_csv, generate_markdown_summary, generate_per_sample_markdown

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:
    trimesh = None


def get_primary_mesh(loaded_obj: Any) -> Any:
    """Extract the primary mesh from a trimesh.Scene or return the mesh itself."""
    if trimesh is None:
        return loaded_obj
    if isinstance(loaded_obj, trimesh.Scene):
        if not loaded_obj.geometry:
            return trimesh.Trimesh()
        # Find the geometry with texture visuals
        for geom in loaded_obj.geometry.values():
            visual = getattr(geom, "visual", None)
            if visual is not None:
                mat = getattr(visual, "material", None)
                if mat is not None:
                    img = getattr(mat, "image", None) or getattr(mat, "baseColorTexture", None)
                    if img is not None:
                        return geom
        # Fall back to the geometry with the most vertices
        geoms = list(loaded_obj.geometry.values())
        geoms.sort(key=lambda m: len(m.vertices) if hasattr(m, "vertices") else 0, reverse=True)
        return geoms[0]
    return loaded_obj


async def evaluate_sample(
    model: Any,
    obj_dir: Path,
    output_dir: Path,
    settings: GenerationSettings
) -> Dict[str, Any]:
    """Run model inference and evaluate quality metrics against ground truth."""
    object_id = obj_dir.name
    report_entry = {
        "object_id": object_id,
        "success": False,
        "error": None,
        "inference_time_seconds": 0.0,
        "vram_delta_mb": 0,
        "file_size_bytes": 0,
        "geometry": {},
        "mesh_quality": {},
        "textures": {},
    }

    # 1. Locate inputs
    images_dir = obj_dir / "images"
    model_dir = obj_dir / "model"

    img_files = sorted(
        [f for f in images_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    ) if images_dir.exists() else []
    gt_files = sorted(
        [f for f in model_dir.iterdir() if f.suffix.lower() in (".glb", ".gltf", ".obj")]
    ) if model_dir.exists() else []

    if not img_files or not gt_files:
        report_entry["error"] = "Missing paired images or ground-truth models"
        logger.error("Skipping %s: %s", object_id, report_entry["error"])
        return report_entry

    image_path = img_files[0]
    gt_path = gt_files[0]

    # Staging area for this generated run
    item_out_dir = output_dir / "generated" / object_id
    item_out_dir.mkdir(parents=True, exist_ok=True)

    # VRAM check before
    vram_before = vram_snapshot().get("used_mb")

    start_time = time.perf_counter()
    try:
        # Run inference
        res = await model.generate(image_path, item_out_dir, settings)
        duration = time.perf_counter() - start_time
        
        # VRAM check after
        vram_after = vram_snapshot().get("used_mb")
        vram_delta = (vram_after - vram_before) if (vram_before is not None and vram_after is not None) else 0

        # Save output GLB locally in outputs folder
        out_glb_path = item_out_dir / "generated_model.glb"
        out_glb_path.write_bytes(res.glb_bytes)

        # Get file stats
        file_stats = get_file_metrics(out_glb_path)

        if trimesh is not None:
            # Load as Scene/Mesh and extract the main models
            loaded_gen = trimesh.load(io.BytesIO(res.glb_bytes), file_type="glb")
            loaded_gt = trimesh.load(gt_path)
            
            gen_mesh = get_primary_mesh(loaded_gen)
            gt_mesh = get_primary_mesh(loaded_gt)

            # Calculate geometric similarity (Chamfer distance, F-score, normals)
            chamfer, f_score, norm_sim = compute_chamfer_and_fscore(gen_mesh, gt_mesh)
            
            # Calculate mesh topology stats
            mesh_stats = analyze_mesh_quality(gen_mesh)
            
            # Calculate texture details
            tex_stats = analyze_textures(gen_mesh)

            report_entry["geometry"] = {
                "chamfer_distance": round(chamfer, 6),
                "f_score": round(f_score, 4),
                "normal_consistency": round(norm_sim, 4),
            }
            report_entry["mesh_quality"] = mesh_stats
            report_entry["textures"] = tex_stats

        report_entry.update({
            "success": True,
            "inference_time_seconds": round(duration, 4),
            "vram_delta_mb": vram_delta,
            "file_size_bytes": file_stats["file_size_bytes"],
        })
        logger.info("Successfully evaluated object: %s", object_id)

    except Exception as exc:
        duration = time.perf_counter() - start_time
        report_entry.update({
            "success": False,
            "error": str(exc),
            "inference_time_seconds": round(duration, 4),
        })
        logger.error("Failed evaluation for object %s: %s", object_id, exc)

    return report_entry


async def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Evaluation Suite")
    parser.add_argument("--test-dir", type=str, required=True, help="Directory containing the test split objects")
    parser.add_argument("--model", type=str, default="auto", help="Model name (mock | stable-fast-3d | hunyuan3d | custom)")
    parser.add_argument("--output-dir", type=str, default="evaluation/results", help="Directory to save evaluation reports and models")
    parser.add_argument("--resolution", type=int, default=512, help="Output mesh resolution settings")
    parser.add_argument("--compare", type=str, default=None, help="Comma-separated paths to other evaluation JSON reports to compile comparison tables")
    args = parser.parse_args()

    test_dir = Path(args.test_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not test_dir.exists():
        logger.error("Test directory '%s' does not exist.", test_dir)
        sys.exit(1)

    # Initialize model
    try:
        model = create_ai_model(args.model)
        logger.info("Initialized model for evaluation: '%s'", model.name)
    except ModelNotAvailableError as exc:
        logger.error("Model unavailable: %s", exc)
        sys.exit(1)

    device_info = get_device_info(model.device_preference)
    
    # Gather test object folders
    obj_dirs = sorted([d for d in test_dir.iterdir() if d.is_dir()])
    logger.info("Found %d test samples in split: '%s'", len(obj_dirs), test_dir)

    settings = GenerationSettings(
        model=model.name,
        resolution=args.resolution,
        remesh=True,
        validation="warn",  # do not crash on validation, log warnings and proceed
    )

    results = []
    for obj_dir in obj_dirs:
        logger.info("Evaluating sample: %s", obj_dir.name)
        res_entry = await evaluate_sample(model, obj_dir, output_dir, settings)
        results.append(res_entry)

    # Final report dictionary
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_name": model.name,
        "device": device_info.to_dict(),
        "settings": {
            "resolution": args.resolution,
        },
        "results": results,
    }

    # Load comparison files if provided
    comparison_reports = []
    if args.compare:
        for path_str in args.compare.split(","):
            comp_path = Path(path_str.strip())
            if comp_path.exists():
                try:
                    comparison_reports.append(json.loads(comp_path.read_text()))
                    logger.info("Loaded comparison report: %s", comp_path)
                except Exception as exc:
                    logger.error("Failed to load comparison report %s: %s", comp_path, exc)

    # Exporters
    export_json(report, output_dir / "evaluation_report.json")
    export_csv(results, output_dir / "evaluation_report.csv")
    generate_markdown_summary(report, output_dir / "summary.md", comparison_reports)
    generate_per_sample_markdown(report, output_dir / "per_sample_report.md")
    
    print("\n=======================================================")
    print(" EVALUATION BASRUN COMPLETED SUCCESSFULLY!")
    print(f" Reports saved to: {output_dir.resolve()}")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(main())
