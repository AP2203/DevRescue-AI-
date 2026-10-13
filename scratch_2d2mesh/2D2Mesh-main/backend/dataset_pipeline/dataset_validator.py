#!/usr/bin/env python3
"""Dataset Validator.

Performs automated data quality checks on paired 2D images and 3D models.
Saves validation reports and filters out corrupted or invalid assets.
"""

import argparse
import json
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
from PIL import Image
from scipy.ndimage import laplace

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:
    trimesh = None
    logger.warning("trimesh is not installed; 3D model validation will be degraded.")


class DatasetValidator:
    def __init__(
        self,
        min_image_resolution: int = 256,
        min_blur_score: float = 10.0,
        min_brightness: float = 15.0,
        max_brightness: float = 240.0,
        min_contrast: float = 15.0,
        min_texture_resolution: int = 128,
        min_vertices: int = 10,
        min_faces: int = 10,
    ) -> None:
        self.min_image_resolution = min_image_resolution
        self.min_blur_score = min_blur_score
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_contrast = min_contrast
        self.min_texture_resolution = min_texture_resolution
        self.min_vertices = min_vertices
        self.min_faces = min_faces

    def validate_image(self, image_path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Perform quality checks on a 2D image."""
        metrics: Dict[str, Any] = {}
        errors: List[str] = []

        try:
            with Image.open(image_path) as img:
                width, height = img.size
                metrics["resolution"] = f"{width}x{height}"
                metrics["width"] = width
                metrics["height"] = height

                # Check minimum resolution
                if min(width, height) < self.min_image_resolution:
                    errors.append(
                        f"Low resolution: {width}x{height} (min: {self.min_image_resolution}px)"
                    )

                # Convert to grayscale for metrics
                gray_img = img.convert("L")
                gray_arr = np.array(gray_img, dtype=np.float64)

                # Brightness (mean)
                brightness = float(gray_arr.mean())
                metrics["brightness"] = round(brightness, 2)
                if brightness < self.min_brightness or brightness > self.max_brightness:
                    errors.append(f"Invalid brightness: {metrics['brightness']} (range: {self.min_brightness}-{self.max_brightness})")

                # Contrast (std dev)
                contrast = float(gray_arr.std())
                metrics["contrast"] = round(contrast, 2)
                if contrast < self.min_contrast:
                    errors.append(f"Low contrast: {metrics['contrast']} (min: {self.min_contrast})")

                # Blur Score using Laplacian variance
                laplacian_var = float(laplace(gray_arr).var())
                metrics["blur_score"] = round(laplacian_var, 2)
                if laplacian_var < self.min_blur_score:
                    errors.append(f"Blurry image: blur score {metrics['blur_score']} (min: {self.min_blur_score})")

                # Background and object visibility (rough bbox detection of foreground)
                # Background is assumed to be either transparent or solid (very low variance at corners)
                rgba_img = img.convert("RGBA")
                rgba_arr = np.array(rgba_img)
                alpha = rgba_arr[:, :, 3]
                
                has_alpha = alpha.min() < 255
                metrics["has_alpha"] = has_alpha

                if has_alpha:
                    # Bounding box of non-transparent pixels
                    nonzero = np.argwhere(alpha > 10)
                    if len(nonzero) > 0:
                        min_y, min_x = nonzero.min(axis=0)
                        max_y, max_x = nonzero.max(axis=0)
                        bbox_area_pct = ((max_y - min_y) * (max_x - min_x)) / (width * height)
                        metrics["object_visibility"] = round(bbox_area_pct * 100, 2)
                    else:
                        metrics["object_visibility"] = 0.0
                        errors.append("Empty transparent image (no object visible)")
                else:
                    # Sample corners to determine background luminance
                    corners = [gray_arr[0, 0], gray_arr[0, -1], gray_arr[-1, 0], gray_arr[-1, -1]]
                    bg_lum = np.mean(corners)
                    
                    if bg_lum > 128:
                        # Bright background: object is darker
                        foreground = gray_arr < (bg_lum - 30)
                    else:
                        # Dark background: object is brighter
                        foreground = gray_arr > (bg_lum + 30)
                        
                    bbox_area_pct = foreground.sum() / (width * height)
                    metrics["object_visibility"] = round(bbox_area_pct * 100, 2)

                # Check visibility
                if metrics.get("object_visibility", 100.0) < 1.0:
                    errors.append(f"Low object visibility: {metrics['object_visibility']}%")

                metrics["background_quality"] = "transparent" if has_alpha else "opaque"

        except Exception as exc:
            errors.append(f"Corrupted image file: {exc}")
            metrics["resolution"] = "0x0"
            metrics["blur_score"] = 0.0
            metrics["brightness"] = 0.0
            metrics["contrast"] = 0.0
            metrics["object_visibility"] = 0.0

        passed = len(errors) == 0
        return passed, metrics, errors

    def validate_mesh(self, mesh_path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Perform quality checks on a 3D model."""
        metrics: Dict[str, Any] = {
            "vertices": 0,
            "faces": 0,
            "polygons": 0,
            "bounding_box": None,
            "connected_components": 0,
            "watertight": False,
            "normal_validity": False,
            "texture_presence": False,
        }
        errors: List[str] = []

        if trimesh is None:
            errors.append("trimesh library missing, cannot validate 3D model")
            return False, metrics, errors

        try:
            # Suppress trimesh loading logs if verbose
            mesh = trimesh.load(mesh_path, force="mesh")
            
            # 1. Base counts
            verts_count = len(mesh.vertices)
            faces_count = len(mesh.faces)
            metrics["vertices"] = verts_count
            metrics["faces"] = faces_count
            metrics["polygons"] = faces_count

            if verts_count < self.min_vertices:
                errors.append(f"Mesh has too few vertices: {verts_count} (min: {self.min_vertices})")
            if faces_count < self.min_faces:
                errors.append(f"Mesh has too few faces: {faces_count} (min: {self.min_faces})")

            # 2. Bounding Box
            bbox = mesh.bounds
            metrics["bounding_box"] = bbox.tolist() if bbox is not None else None
            if bbox is not None:
                extents = bbox[1] - bbox[0]
                if np.min(extents) < 1e-6:
                    errors.append(f"Mesh is flat or degenerate on one axis: extents {extents.tolist()}")

            # 3. Connected Components
            try:
                bodies = len(mesh.split())
                metrics["connected_components"] = bodies
            except Exception:
                metrics["connected_components"] = 1

            # 4. Watertight status
            watertight = bool(mesh.is_watertight)
            metrics["watertight"] = watertight
            # We log watertight as warning/stat rather than rejection, unless strictly required

            # 5. Normal validity
            try:
                normals = mesh.vertex_normals
                has_nan_normals = np.isnan(normals).any() or np.isinf(normals).any()
                zero_len_normals = (np.linalg.norm(normals, axis=1) < 1e-6).sum()
                
                normals_valid = not has_nan_normals and zero_len_normals == 0
                metrics["normal_validity"] = bool(normals_valid)
                if has_nan_normals:
                    errors.append("Mesh normals contain NaN/Inf values")
                if zero_len_normals > 0:
                    errors.append(f"Mesh has {zero_len_normals} zero-length normals")
            except Exception as exc:
                errors.append(f"Invalid normals: {exc}")

            # 6. Texture presence & quality
            has_texture = False
            texture_res = None
            if hasattr(mesh, "visual") and mesh.visual is not None:
                # Check UV coords
                uvs = getattr(mesh.visual, "uv", None)
                if uvs is not None and len(uvs) == len(mesh.vertices):
                    # Check Texture Image
                    mat = getattr(mesh.visual, "material", None)
                    if mat is not None:
                        img = getattr(mat, "image", None) or getattr(mat, "baseColorTexture", None)
                        if img is not None:
                            has_texture = True
                            if hasattr(img, "size"):
                                texture_res = max(img.size)
                                if texture_res < self.min_texture_resolution:
                                    errors.append(
                                        f"Low resolution texture: {img.size[0]}x{img.size[1]} "
                                        f"(min side: {self.min_texture_resolution}px)"
                                    )

            metrics["texture_presence"] = has_texture
            metrics["texture_resolution"] = texture_res
            if not has_texture:
                # If mesh uses vertex colors instead
                has_colors = hasattr(mesh.visual, "vertex_colors") and len(mesh.visual.vertex_colors) > 0
                metrics["vertex_colors_presence"] = has_colors
                if not has_colors:
                    errors.append("Mesh has neither texture maps nor vertex colors")

        except Exception as exc:
            errors.append(f"Corrupted or empty 3D model file: {exc}")
            traceback.print_exc()

        passed = len(errors) == 0
        return passed, metrics, errors

    def validate_object_folder(self, obj_dir: Path) -> Dict[str, Any]:
        """Validate an object folder containing images/, model/, and textures/."""
        report: Dict[str, Any] = {
            "object_id": obj_dir.name,
            "passed": False,
            "errors": [],
            "image_metrics": {},
            "model_metrics": {},
        }

        # 1. Verify directory structure
        images_dir = obj_dir / "images"
        model_dir = obj_dir / "model"
        
        if not images_dir.exists() or not any(images_dir.iterdir()):
            report["errors"].append("Missing or empty 'images/' directory")
        if not model_dir.exists() or not any(model_dir.iterdir()):
            report["errors"].append("Missing or empty 'model/' directory")

        if report["errors"]:
            return report

        # 2. Find files
        img_files = [
            f for f in images_dir.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        ]
        model_files = [
            f for f in model_dir.iterdir()
            if f.suffix.lower() in (".glb", ".gltf", ".obj")
        ]

        if not img_files:
            report["errors"].append("No supported images (JPG, PNG, WEBP) in 'images/' folder")
        if not model_files:
            report["errors"].append("No supported 3D models (GLB, GLTF, OBJ) in 'model/' folder")

        if report["errors"]:
            return report

        # 3. Validate image files
        img_passed_count = 0
        for img_path in img_files:
            img_passed, img_metrics, img_errors = self.validate_image(img_path)
            report["image_metrics"][img_path.name] = {
                "passed": img_passed,
                "metrics": img_metrics,
                "errors": img_errors,
            }
            if img_passed:
                img_passed_count += 1
            else:
                report["errors"].extend([f"Image '{img_path.name}': {err}" for err in img_errors])

        # 4. Validate 3D model files
        model_passed_count = 0
        for model_path in model_files:
            model_passed, model_metrics, model_errors = self.validate_mesh(model_path)
            report["model_metrics"][model_path.name] = {
                "passed": model_passed,
                "metrics": model_metrics,
                "errors": model_errors,
            }
            if model_passed:
                model_passed_count += 1
            else:
                report["errors"].extend([f"Model '{model_path.name}': {err}" for err in model_errors])

        # 5. Metadata.json validation
        metadata_path = obj_dir / "metadata.json"
        if not metadata_path.exists():
            report["errors"].append("Missing required 'metadata.json'")
        else:
            try:
                meta = json.loads(metadata_path.read_text())
                required_fields = ["object_id", "category", "source"]
                for fld in required_fields:
                    if fld not in meta or not str(meta[fld]).strip():
                        report["errors"].append(f"Missing or empty metadata field: '{fld}'")
            except Exception as exc:
                report["errors"].append(f"Malformed 'metadata.json': {exc}")

        # Final decision
        report["passed"] = (
            img_passed_count > 0 
            and model_passed_count > 0 
            and len(report["errors"]) == 0
        )
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Dataset Pipeline - Validator")
    parser.add_argument("--src-dir", type=str, required=True, help="Raw dataset directory to audit")
    parser.add_argument("--report-file", type=str, default="validation_report.json", help="Path to write the audit JSON report")
    args = parser.parse_args()

    src_dir = Path(args.src_dir)
    if not src_dir.exists():
        logger.error("Source directory '%s' does not exist.", src_dir)
        sys.exit(1)

    validator = DatasetValidator()
    
    # Locate all object folders (subdirectories of src_dir)
    obj_dirs = [d for d in src_dir.iterdir() if d.is_dir()]
    logger.info("Found %d object directories to validate.", len(obj_dirs))

    report_summary: Dict[str, Any] = {
        "valid_objects": [],
        "rejected_objects": {},
    }

    for obj_dir in obj_dirs:
        logger.info("Validating object: %s", obj_dir.name)
        res = validator.validate_object_folder(obj_dir)
        if res["passed"]:
            report_summary["valid_objects"].append(obj_dir.name)
            logger.info("-> [VALID] %s", obj_dir.name)
        else:
            report_summary["rejected_objects"][obj_dir.name] = res["errors"]
            logger.warning("-> [REJECTED] %s | Reasons: %s", obj_dir.name, res["errors"])

    # Save validation report
    out_path = Path(args.report_file)
    out_path.write_text(json.dumps(report_summary, indent=2))
    logger.info("Validation report saved to: %s", out_path)
    logger.info("Valid: %d | Rejected: %d", len(report_summary["valid_objects"]), len(report_summary["rejected_objects"]))


if __name__ == "__main__":
    main()
