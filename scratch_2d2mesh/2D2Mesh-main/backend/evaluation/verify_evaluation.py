#!/usr/bin/env python3
"""Evaluation Verification Suite.

Generates a mock test split dataset and executes the evaluation runner
to verify that mesh metrics (Chamfer distance, F-score, watertightness, etc.),
CSV/JSON logs, and markdown comparison reports are compiled correctly.
"""

import json
import os
import shutil
import sys
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

eval_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(eval_dir))


def create_dummy_mesh(file_path: Path) -> None:
    """Create a simple valid 3D sphere and save it as GLB."""
    import trimesh
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    import numpy as np
    uvs = np.random.rand(len(mesh.vertices), 2)
    img = Image.new("RGB", (256, 256), (180, 100, 80))
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs, image=img)
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(file_path), file_type="glb")


def create_dummy_image(file_path: Path) -> None:
    """Create a standard test image."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (512, 512), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 412, 412], fill=(40, 40, 40))
    img.save(file_path)


def setup_mock_test_split(test_dir: Path) -> None:
    """Populate test_dir with mock objects containing images, models, and metadata."""
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. Object 1 (category: chair)
    o1_dir = test_dir / "test_obj_1"
    create_dummy_mesh(o1_dir / "model" / "gt_mesh.glb")
    create_dummy_image(o1_dir / "images" / "view_1.png")
    (o1_dir / "metadata.json").write_text(json.dumps({
        "object_id": "test_obj_1",
        "category": "chair",
        "source": "test_dataset",
    }))

    # 2. Object 2 (category: table)
    o2_dir = test_dir / "test_obj_2"
    create_dummy_mesh(o2_dir / "model" / "gt_mesh.glb")
    create_dummy_image(o2_dir / "images" / "view_1.png")
    (o2_dir / "metadata.json").write_text(json.dumps({
        "object_id": "test_obj_2",
        "category": "table",
        "source": "test_dataset",
    }))


def run_script(script_name: str, args: list) -> None:
    """Run a Python script with arguments."""
    cmd = [sys.executable, str(eval_dir / script_name)] + args
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    temp_dir = eval_dir / "temp_verification"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    test_dir = temp_dir / "test_split"
    results_dir = temp_dir / "results"

    print("=== [1. Setting up Mock Test Split Dataset] ===")
    setup_mock_test_split(test_dir)

    print("\n=== [2. Running Model Evaluation Suite] ===")
    run_script("run_evaluation.py", [
        "--test-dir", str(test_dir),
        "--output-dir", str(results_dir),
        "--model", "mock"
    ])

    # 3. Assert outputs are created and look correct
    json_report = results_dir / "evaluation_report.json"
    csv_report = results_dir / "evaluation_report.csv"
    summary_md = results_dir / "summary.md"
    per_sample_md = results_dir / "per_sample_report.md"

    assert json_report.exists(), "Error: evaluation_report.json not found!"
    assert csv_report.exists(), "Error: evaluation_report.csv not found!"
    assert summary_md.exists(), "Error: summary.md not found!"
    assert per_sample_md.exists(), "Error: per_sample_report.md not found!"

    # Validate JSON content
    data = json.loads(json_report.read_text())
    assert data["model_name"] == "mock", "Error: model_name should be 'mock'"
    assert len(data["results"]) == 2, "Error: should evaluate exactly 2 objects"
    
    # Check that geometry comparisons are calculated
    for res in data["results"]:
        assert res["success"] is True, f"Error: object {res['object_id']} failed"
        assert "chamfer_distance" in res["geometry"], "Error: missing Chamfer distance!"
        assert "f_score" in res["geometry"], "Error: missing F-score!"
        assert "normal_consistency" in res["geometry"], "Error: missing Normal consistency!"
        assert res["mesh_quality"]["vertices"] > 0, "Error: vertices count should be > 0"
        assert res["textures"]["texture_presence"] is True, "Error: texture should be present"

    print("PASS: Evaluation outputs verified successfully.")

    # Clean up verification files
    shutil.rmtree(temp_dir)
    print("\n==========================================")
    print(" ALL EVALUATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    main()
