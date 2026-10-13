#!/usr/bin/env python3
"""Validation and benchmarking script for the Vision3D AI model pipeline.

Runs inference against a dataset of images and records metrics including:
- Generation success/failure
- Inference time
- GPU memory (VRAM) delta
- Output file size
- Vertex and face count
- Mesh quality and validity (watertightness, degenerate faces, normal health)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
from PIL import Image, ImageDraw

# Add backend directory to sys.path to allow importing backend app
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure environment defaults before importing app code
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")

try:
    from app.ai.factory import create_ai_model, ModelNotAvailableError
    from app.ai.types import GenerationSettings
    from app.ai.inference.device import vram_snapshot, get_device_info
    from app.ai.inference.validator import OutputValidator
except ImportError as exc:
    print(f"Error: Failed to import backend app modules. Make sure you run this script from the backend directory: {exc}")
    sys.exit(1)


def generate_dummy_dataset(dataset_dir: Path) -> None:
    """Generate a fixed set of simple 2D shapes for validation if dataset is empty."""
    dataset_dir.mkdir(parents=True, exist_ok=True)
    shapes = [
        ("circle", (255, 0, 0), lambda draw: draw.ellipse([64, 64, 448, 448], fill=(255, 0, 0))),
        ("square", (0, 255, 0), lambda draw: draw.rectangle([100, 100, 412, 412], fill=(0, 255, 0))),
        ("triangle", (0, 0, 255), lambda draw: draw.polygon([(256, 64), (64, 448), (448, 448)], fill=(0, 0, 255))),
    ]
    for name, color, draw_func in shapes:
        img_path = dataset_dir / f"{name}.png"
        if not img_path.exists():
            # Create a 512x512 image with a black background
            img = Image.new("RGB", (512, 512), (10, 10, 10))
            draw = ImageDraw.Draw(img)
            draw_func(draw)
            img.save(img_path)
            print(f"Generated validation image: {img_path}")


async def validate_image(
    model: Any,
    image_path: Path,
    output_dir: Path,
    settings: GenerationSettings
) -> Dict[str, Any]:
    """Run validation for a single image and record metrics."""
    result_entry: Dict[str, Any] = {
        "image_name": image_path.name,
        "success": False,
        "error": None,
        "inference_time_seconds": 0.0,
        "vram_delta_mb": 0,
        "file_size_bytes": 0,
        "vertices": 0,
        "faces": 0,
        "watertight": False,
        "validation_passed": False,
        "validation_summary": "",
    }

    item_out_dir = output_dir / image_path.stem
    item_out_dir.mkdir(parents=True, exist_ok=True)

    # VRAM check before
    vram_before = vram_snapshot().get("used_mb")

    start_time = time.perf_counter()
    try:
        res = await model.generate(image_path, item_out_dir, settings)
        duration = time.perf_counter() - start_time
        
        # VRAM check after
        vram_after = vram_snapshot().get("used_mb")
        vram_delta = (vram_after - vram_before) if (vram_before is not None and vram_after is not None) else 0

        # Output stats
        glb_size = len(res.glb_bytes)
        stats = res.stats or {}
        
        # Save output GLB locally in item directory
        out_glb_path = item_out_dir / "model.glb"
        out_glb_path.write_bytes(res.glb_bytes)

        # Validation
        val_passed = False
        val_summary = "Skipped"
        if res.validation:
            val_passed = res.validation.get("passed", False)
            checks = res.validation.get("checks", [])
            failed = [c["name"] for c in checks if not c["passed"]]
            val_summary = f"Passed" if val_passed else f"Failed checks: {', '.join(failed)}"

        result_entry.update({
            "success": True,
            "inference_time_seconds": round(duration, 4),
            "vram_delta_mb": vram_delta,
            "file_size_bytes": glb_size,
            "vertices": stats.get("vertices", 0),
            "faces": stats.get("faces", 0),
            "watertight": stats.get("watertight", False),
            "validation_passed": val_passed,
            "validation_summary": val_summary,
        })
        print(f"PASS: Processed {image_path.name} | Time: {duration:.2f}s | Faces: {result_entry['faces']} | Valid: {val_passed}")

    except Exception as exc:
        duration = time.perf_counter() - start_time
        result_entry.update({
            "success": False,
            "error": str(exc),
            "inference_time_seconds": round(duration, 4),
        })
        print(f"FAIL: Failed {image_path.name} | Time: {duration:.2f}s | Error: {exc}")

    return result_entry


async def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D AI Model Validation Baseline Script")
    parser.add_argument("--model", type=str, default="auto", help="Model name (mock | stable-fast-3d | hunyuan3d | custom)")
    parser.add_argument("--input-dir", type=str, default="validation_dataset", help="Directory of validation images")
    parser.add_argument("--output-dir", type=str, default="validation_results", help="Directory to save benchmarks and output meshes")
    parser.add_argument("--resolution", type=int, default=512, help="Output mesh resolution settings")
    parser.add_argument("--remesh", action="store_true", default=True, help="Apply post-generation smoothing / remeshing")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up dummy shapes if no input directory exists or is empty
    if not input_dir.exists() or not any(input_dir.glob("*.[pP][nN][gG]")) and not any(input_dir.glob("*.[jJ][pP][gG]")):
        print(f"Validation dataset not found or empty. Generating default dummy shapes in '{input_dir}'...")
        generate_dummy_dataset(input_dir)

    # Initialize model
    try:
        model = create_ai_model(args.model)
        print(f"Active Model Resolved: '{model.name}'")
    except ModelNotAvailableError as exc:
        print(f"Error: {exc}")
        print("Available registered models are: mock, stable-fast-3d, hunyuan3d, custom")
        sys.exit(1)

    device_info = get_device_info(model.device_preference)
    print(f"Active Device: {device_info.name} ({device_info.type}) | Backend: {device_info.backend}")
    print(f"GPU Available: {device_info.cuda_available} | VRAM: {device_info.vram_total_mb or 'N/A'} MB")

    # Locate images
    image_paths = sorted(
        [p for p in input_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    )
    if not image_paths:
        print(f"Error: No images found in {input_dir}")
        sys.exit(1)

    print(f"Found {len(image_paths)} images for validation. Starting inference benchmarks...")

    # Build generation settings
    settings = GenerationSettings(
        model=model.name,
        resolution=args.resolution,
        remesh=args.remesh,
        validation="strict" if model.name != "custom" else "warn",
    )

    results = []
    for image_path in image_paths:
        res_entry = await validate_image(model, image_path, output_dir, settings)
        results.append(res_entry)

    # Save detailed JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model.name,
        "device": device_info.to_dict(),
        "settings": {
            "resolution": args.resolution,
            "remesh": args.remesh,
        },
        "results": results,
    }
    report_path = output_dir / "validation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved detailed validation report to: {report_path}")

    # Print summary Markdown table
    print("\n" + "=" * 40)
    print(" BASELINE MODEL VALIDATION REPORT")
    print("=" * 40)
    print(f"Model: {model.name} | Device: {device_info.name}")
    print("\n| Image Name | Success | Time (s) | File Size (KB) | Vertices | Faces | Watertight | Quality Check |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        size_kb = f"{r['file_size_bytes'] / 1024:.1f}" if r["success"] else "N/A"
        time_str = f"{r['inference_time_seconds']:.2f}"
        print(
            f"| {r['image_name']} "
            f"| {'YES' if r['success'] else 'NO'} "
            f"| {time_str} "
            f"| {size_kb} "
            f"| {r['vertices']} "
            f"| {r['faces']} "
            f"| {'YES' if r['watertight'] else 'NO'} "
            f"| {r['validation_summary']} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
