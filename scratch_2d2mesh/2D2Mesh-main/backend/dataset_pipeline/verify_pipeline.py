#!/usr/bin/env python3
"""Pipeline Verification Suite.

Generates a mock raw dataset containing valid, invalid, and duplicate assets,
and executes the pipeline scripts sequentially to verify correct execution,
rejection criteria, duplication detection, and stratified splitting.
"""

import json
import os
import shutil
import sys
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

pipeline_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(pipeline_dir))


def create_dummy_mesh(file_path: Path) -> None:
    """Create a simple valid 3D sphere and save it as GLB."""
    import trimesh
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    # Give it dummy UV coordinates
    import numpy as np
    uvs = np.random.rand(len(mesh.vertices), 2)
    
    # Create simple solid texture
    img = Image.new("RGB", (256, 256), (180, 100, 80))
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs, image=img)
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(file_path), file_type="glb")


def create_dummy_image(file_path: Path, blur: bool = False, low_contrast: bool = False) -> None:
    """Create a test image, optionally applying blur or low contrast."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if low_contrast:
        # A flat, gray image has very low contrast
        img = Image.new("RGB", (512, 512), (128, 128, 128))
    else:
        # Bright background, dark shape to allow simple thresholding
        img = Image.new("RGB", (512, 512), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 100, 412, 412], fill=(40, 40, 40))
    
    if blur:
        from PIL import ImageFilter
        img = img.filter(ImageFilter.GaussianBlur(radius=15))
        
    img.save(file_path)


def setup_mock_raw_dataset(raw_dir: Path) -> None:
    """Populate raw_dir with valid, invalid, and duplicate objects."""
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Object A: VALID (category: chair)
    a_dir = raw_dir / "obj_A_valid"
    create_dummy_mesh(a_dir / "model" / "mesh.glb")
    create_dummy_image(a_dir / "images" / "view_1.png")
    (a_dir / "metadata.json").write_text(json.dumps({
        "object_id": "obj_A_valid",
        "category": "chair",
        "source": "mock_generator",
    }))

    # 2. Object B: INVALID (blurry image, category: chair)
    b_dir = raw_dir / "obj_B_blur"
    create_dummy_mesh(b_dir / "model" / "mesh.glb")
    create_dummy_image(b_dir / "images" / "view_1.png", blur=True)
    (b_dir / "metadata.json").write_text(json.dumps({
        "object_id": "obj_B_blur",
        "category": "chair",
        "source": "mock_generator",
    }))

    # 3. Object C: INVALID (missing metadata, category: table)
    c_dir = raw_dir / "obj_C_no_meta"
    create_dummy_mesh(c_dir / "model" / "mesh.glb")
    create_dummy_image(c_dir / "images" / "view_1.png")
    # intentionally missing metadata.json

    # 4. Object D: VALID (category: chair)
    d_dir = raw_dir / "obj_D_valid"
    create_dummy_mesh(d_dir / "model" / "mesh.glb")
    create_dummy_image(d_dir / "images" / "view_1.png")
    (d_dir / "metadata.json").write_text(json.dumps({
        "object_id": "obj_D_valid",
        "category": "chair",
        "source": "mock_generator",
    }))

    # 5. Object E: VALID DUPLICATE of Object A (category: chair)
    e_dir = raw_dir / "obj_E_duplicate"
    # Copy exact same mesh as A
    create_dummy_mesh(e_dir / "model" / "mesh.glb")
    create_dummy_image(e_dir / "images" / "view_1.png")
    (e_dir / "metadata.json").write_text(json.dumps({
        "object_id": "obj_E_duplicate",
        "category": "chair",
        "source": "mock_generator",
    }))


def run_script(script_name: str, args: list) -> None:
    """Run a pipeline script with arguments."""
    cmd = [sys.executable, str(pipeline_dir / script_name)] + args
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    temp_dir = pipeline_dir / "temp_verification"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = temp_dir / "raw_data"
    validated_dir = temp_dir / "validated_data"
    split_dir = temp_dir / "split_dataset"
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=== [1. Setting up Mock Raw Dataset] ===")
    setup_mock_raw_dataset(raw_dir)

    print("\n=== [2. Running Dataset Validator] ===")
    val_report = reports_dir / "audit_report.json"
    run_script("dataset_validator.py", [
        "--src-dir", str(raw_dir),
        "--report-file", str(val_report)
    ])

    # Parse validator report to assert correct rejections
    report_data = json.loads(val_report.read_text())
    valid_list = report_data.get("valid_objects", [])
    rejected_dict = report_data.get("rejected_objects", {})

    print(f"Valid objects: {valid_list}")
    print(f"Rejected objects: {list(rejected_dict.keys())}")

    assert "obj_A_valid" in valid_list, "Error: obj_A_valid should be valid!"
    assert "obj_D_valid" in valid_list, "Error: obj_D_valid should be valid!"
    assert "obj_E_duplicate" in valid_list, "Error: obj_E_duplicate is valid at validation step!"
    assert "obj_B_blur" in rejected_dict, "Error: obj_B_blur should have been rejected!"
    assert "obj_C_no_meta" in rejected_dict, "Error: obj_C_no_meta should have been rejected!"
    print("PASS: Validation rejections verified successfully.")

    # Populate validated_dir containing only validated objects
    validated_dir.mkdir(parents=True, exist_ok=True)
    for obj_name in valid_list:
        shutil.copytree(raw_dir / obj_name, validated_dir / obj_name)

    print("\n=== [3. Running Duplicate Detector] ===")
    dup_report = reports_dir / "duplicate_report.json"
    run_script("duplicate_detector.py", [
        "--dataset-dir", str(validated_dir),
        "--report-file", str(dup_report)
    ])

    dup_data = json.loads(dup_report.read_text())
    dup_objs = dup_data.get("duplicate_objects", [])
    print(f"Duplicate objects found: {dup_objs}")
    
    # Assert Object A and Object E are identified as duplicates
    has_ae_dup = False
    for pair in dup_objs:
        if ("obj_A_valid" in pair and "obj_E_duplicate" in pair):
            has_ae_dup = True
    assert has_ae_dup, "Error: Duplicate detector failed to identify obj_A_valid and obj_E_duplicate as duplicates!"
    print("PASS: Duplication detection verified successfully.")

    # Remove the duplicate object from validated directory before splitting
    shutil.rmtree(validated_dir / "obj_E_duplicate")
    print("Removed duplicate object 'obj_E_duplicate' from validated staging directory.")

    print("\n=== [4. Running Dataset Splitter] ===")
    # With only 2 unique valid objects (A and D), splitting will distribute them
    run_script("dataset_splitter.py", [
        "--src-dir", str(validated_dir),
        "--dest-dir", str(split_dir),
        "--train-ratio", "0.5",
        "--val-ratio", "0.5",
        "--test-ratio", "0.0",
        "--seed", "42"
    ])

    # Check that A and D were distributed to train/validation
    train_objs = [d.name for d in (split_dir / "train").iterdir() if d.is_dir()]
    val_objs = [d.name for d in (split_dir / "validation").iterdir() if d.is_dir()]
    print(f"Train split: {train_objs}")
    print(f"Validation split: {val_objs}")
    assert len(train_objs) == 1, "Train split should contain 1 object"
    assert len(val_objs) == 1, "Validation split should contain 1 object"
    print("PASS: Dataset splitter verified successfully.")

    print("\n=== [5. Running Statistics Compiler] ===")
    run_script("dataset_statistics.py", [
        "--dataset-dir", str(split_dir),
        "--version", "v1",
        "--validation-report", str(val_report)
    ])

    # Verify manifest file structure
    manifest_path = split_dir / "metadata" / "manifest_v1.json"
    assert manifest_path.exists(), "Manifest file should be created!"
    manifest_data = json.loads(manifest_path.read_text())
    
    assert manifest_data["summary"]["object_count"] == 2, "Manifest should report 2 valid objects"
    assert manifest_data["rejections"]["count"] == 2, "Manifest should record 2 rejected objects"
    print("PASS: Dataset statistics manifest compiled and verified.")

    # Clean up verification files
    shutil.rmtree(temp_dir)
    print("\n==========================================")
    print(" ALL PIPELINE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    main()
