#!/usr/bin/env python3
"""Duplicate Detector.

Identifies duplicate 2D images and 3D meshes to prevent data leakage and redundancy.
Uses difference hashing (dHash) for images and geometric signature hashing for meshes.
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

import numpy as np
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import trimesh
except ImportError:
    trimesh = None
    logger.warning("trimesh is not installed; mesh duplicate detection will be unavailable.")


def compute_dhash(image_path: Path) -> str:
    """Calculate the difference hash (dHash) of an image for visual comparison."""
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale and resize to 9x8 (width x height)
            gray = img.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
            pixels = np.array(gray, dtype=np.float64)
            # Compare columns
            diff = pixels[:, 1:] > pixels[:, :-1]
            
            # Pack boolean values into a hex string
            flat = diff.flatten()
            decimal_val = 0
            for bit in flat:
                decimal_val = (decimal_val << 1) | int(bit)
            return f"{decimal_val:016x}"
    except Exception as exc:
        logger.error("Failed to compute dHash for image %s: %s", image_path, exc)
        return ""


def hamming_distance(hex_hash1: str, hex_hash2: str) -> int:
    """Calculate Hamming distance between two hex hashes (0 to 64)."""
    if not hex_hash1 or not hex_hash2 or len(hex_hash1) != len(hex_hash2):
        return 999
    val1 = int(hex_hash1, 16)
    val2 = int(hex_hash2, 16)
    # XOR to find differing bits, then count them
    return bin(val1 ^ val2).count("1")


def compute_mesh_signature(mesh_path: Path) -> str:
    """Compute a translation- and scale-invariant geometric hash of a 3D mesh."""
    if trimesh is None:
        return ""
    try:
        mesh = trimesh.load(mesh_path, force="mesh")
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        if len(verts) == 0:
            return ""

        # 1. Translate invariant: Center at centroid
        centroid = verts.mean(axis=0)
        centered = verts - centroid

        # 2. Scale invariant: Divide by maximum extent
        extents = centered.max(axis=0) - centered.min(axis=0)
        max_extent = float(extents.max())
        if max_extent > 1e-6:
            normalized = centered / max_extent
        else:
            normalized = centered

        # 3. Precision rounding (round to 4 decimal places to absorb floating point noise)
        rounded = np.round(normalized, 4)

        # 4. Lexicographical sorting to make it permutation invariant
        sorted_verts = rounded[np.lexsort((rounded[:, 2], rounded[:, 1], rounded[:, 0]))]

        # 5. Compute SHA-256 of sorted coordinates
        sha = hashlib.sha256()
        sha.update(sorted_verts.tobytes())
        # Also append vertex count and face count
        sha.update(f"|V:{len(mesh.vertices)}|F:{len(mesh.faces)}".encode("utf-8"))
        return sha.hexdigest()

    except Exception as exc:
        logger.error("Failed to compute mesh signature for %s: %s", mesh_path, exc)
        return ""


class DuplicateDetector:
    def __init__(self, image_threshold: int = 4) -> None:
        # A Hamming distance of 0-4 bits out of 64 indicates highly similar/identical images
        self.image_threshold = image_threshold

    def scan_dataset(self, dataset_dir: Path) -> Dict[str, Any]:
        """Scan a dataset folder to detect duplicate objects, images, and meshes."""
        # Locate all subdirectories
        obj_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
        
        image_hashes: Dict[str, Tuple[str, Path]] = {}  # dhash -> (object_id, image_path)
        mesh_signatures: Dict[str, Tuple[str, Path]] = {}  # signature -> (object_id, mesh_path)
        
        duplicate_images: List[Dict[str, Any]] = []
        duplicate_meshes: List[Dict[str, Any]] = []

        logger.info("Scanning dataset for duplicate assets...")

        for obj_dir in obj_dirs:
            object_id = obj_dir.name
            
            # Scan Images
            images_dir = obj_dir / "images"
            if images_dir.exists():
                for img_path in images_dir.iterdir():
                    if img_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        ihash = compute_dhash(img_path)
                        if not ihash:
                            continue
                        
                        # Compare against existing hashes with Hamming threshold
                        found_dup = False
                        for ref_hash, (ref_obj, ref_path) in image_hashes.items():
                            dist = hamming_distance(ihash, ref_hash)
                            if dist <= self.image_threshold:
                                duplicate_images.append({
                                    "object_1": object_id,
                                    "image_1": str(img_path.relative_to(dataset_dir)),
                                    "object_2": ref_obj,
                                    "image_2": str(ref_path.relative_to(dataset_dir)),
                                    "hamming_distance": dist,
                                })
                                found_dup = True
                                break
                        
                        if not found_dup:
                            image_hashes[ihash] = (object_id, img_path)

            # Scan Meshes
            model_dir = obj_dir / "model"
            if model_dir.exists() and trimesh is not None:
                for mesh_path in model_dir.iterdir():
                    if mesh_path.suffix.lower() in (".glb", ".gltf", ".obj"):
                        msig = compute_mesh_signature(mesh_path)
                        if not msig:
                            continue
                        
                        if msig in mesh_signatures:
                            ref_obj, ref_path = mesh_signatures[msig]
                            # Only flag if it's not the exact same folder (different objects)
                            if ref_obj != object_id:
                                duplicate_meshes.append({
                                    "object_1": object_id,
                                    "model_1": str(mesh_path.relative_to(dataset_dir)),
                                    "object_2": ref_obj,
                                    "model_2": str(ref_path.relative_to(dataset_dir)),
                                })
                        else:
                            mesh_signatures[msig] = (object_id, mesh_path)

        # Categorize duplicate objects
        # An object is a duplicate if its primary 3D mesh is identical to another
        dup_obj_pairs = set()
        for dm in duplicate_meshes:
            dup_obj_pairs.add((dm["object_1"], dm["object_2"]))

        report = {
            "duplicate_image_pairs_count": len(duplicate_images),
            "duplicate_mesh_pairs_count": len(duplicate_meshes),
            "duplicate_objects": [list(p) for p in dup_obj_pairs],
            "details": {
                "images": duplicate_images,
                "meshes": duplicate_meshes,
            }
        }
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Dataset Pipeline - Duplicate Detector")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Path to the dataset directory to inspect")
    parser.add_argument("--report-file", type=str, default="duplicate_report.json", help="Path to write the duplicate report JSON")
    parser.add_argument("--threshold", type=int, default=4, help="Hamming distance threshold for image similarity (0-64)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.exists():
        logger.error("Dataset directory '%s' does not exist.", dataset_dir)
        sys.exit(1)

    detector = DuplicateDetector(image_threshold=args.threshold)
    report = detector.scan_dataset(dataset_dir)

    out_path = Path(args.report_file)
    out_path.write_text(json.dumps(report, indent=2))
    
    logger.info("Scan completed. Duplicate report saved to: %s", out_path)
    logger.info("Found %d duplicate image pairs.", report["duplicate_image_pairs_count"])
    logger.info("Found %d duplicate mesh pairs.", report["duplicate_mesh_pairs_count"])
    logger.info("Identified duplicate objects: %s", report["duplicate_objects"])


if __name__ == "__main__":
    main()
