#!/usr/bin/env python3
"""Dataset Statistics and Manifest Compiler.

Scans the final split dataset directory to calculate aggregate metrics,
category distribution, and compiles a comprehensive versioned manifest.
Integrates validation rejection logs to maintain auditability.
"""

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class DatasetStatistics:
    def __init__(self, dataset_dir: Path) -> None:
        self.dataset_dir = dataset_dir

    def read_category(self, obj_dir: Path) -> str:
        """Read category from object metadata."""
        meta_path = obj_dir / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                cat = meta.get("category", "").strip().lower()
                if cat:
                    return cat
            except Exception:
                pass
        return "unclassified"

    def compile_manifest(
        self,
        version: str,
        validation_report_path: Path | None = None
    ) -> Dict[str, Any]:
        """Compile a versioned manifest of the dataset."""
        manifest: Dict[str, Any] = {
            "dataset_version": version,
            "summary": {
                "object_count": 0,
                "image_count": 0,
                "split_counts": {},
                "category_distribution": {},
            },
            "splits": {
                "train": [],
                "validation": [],
                "test": [],
            },
            "rejections": {
                "count": 0,
                "rejection_reasons": {},
            }
        }

        # 1. Process splits
        total_objects = 0
        total_images = 0
        category_counter: Counter = Counter()
        split_counts: Dict[str, int] = {}

        for split_name in ["train", "validation", "test"]:
            split_dir = self.dataset_dir / split_name
            if not split_dir.exists():
                split_counts[split_name] = 0
                continue

            obj_dirs = [d for d in split_dir.iterdir() if d.is_dir()]
            split_counts[split_name] = len(obj_dirs)
            total_objects += len(obj_dirs)

            for obj_dir in obj_dirs:
                # Add to split list
                manifest["splits"][split_name].append(obj_dir.name)
                
                # Count images
                images_dir = obj_dir / "images"
                if images_dir.exists():
                    img_files = [
                        f for f in images_dir.iterdir()
                        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                    ]
                    total_images += len(img_files)

                # Get category
                cat = self.read_category(obj_dir)
                category_counter[cat] += 1

        manifest["summary"]["object_count"] = total_objects
        manifest["summary"]["image_count"] = total_images
        manifest["summary"]["split_counts"] = split_counts
        manifest["summary"]["category_distribution"] = dict(category_counter)

        # 2. Integrate validation rejections if report is provided
        if validation_report_path and validation_report_path.exists():
            try:
                report = json.loads(validation_report_path.read_text())
                rejected = report.get("rejected_objects", {})
                manifest["rejections"]["count"] = len(rejected)
                manifest["rejections"]["rejection_reasons"] = rejected
            except Exception as exc:
                logger.error("Failed to load validation report: %s", exc)

        return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Dataset Pipeline - Statistics & Manifest Compiler")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Path to the split dataset directory (containing train/val/test)")
    parser.add_argument("--version", type=str, required=True, help="Dataset version identifier (e.g. v1, v2)")
    parser.add_argument("--validation-report", type=str, default=None, help="Path to the JSON validation report to integrate rejections")
    parser.add_argument("--manifest-file", type=str, default=None, help="Optional output path for the manifest. Defaults to <dataset-dir>/metadata/manifest_<version>.json")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.exists():
        logger.error("Dataset directory '%s' does not exist.", dataset_dir)
        sys.exit(1)

    val_report = Path(args.validation_report) if args.validation_report else None

    compiler = DatasetStatistics(dataset_dir)
    manifest = compiler.compile_manifest(args.version, val_report)

    # Resolve manifest save location
    if args.manifest_file:
        out_path = Path(args.manifest_file)
    else:
        metadata_dir = dataset_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        out_path = metadata_dir / f"manifest_{args.version}.json"

    out_path.write_text(json.dumps(manifest, indent=2))
    
    logger.info("Dataset statistics compiled successfully.")
    logger.info("Manifest saved to: %s", out_path)
    logger.info("========================================")
    logger.info(" DATASET VERSION: %s", args.version.upper())
    logger.info("========================================")
    logger.info("Valid Objects: %d", manifest["summary"]["object_count"])
    logger.info("Valid Images:  %d", manifest["summary"]["image_count"])
    logger.info("Splits:")
    for split, count in manifest["summary"]["split_counts"].items():
        logger.info("  - %s: %d", split.capitalize(), count)
    logger.info("Rejections:    %d", manifest["rejections"]["count"])
    logger.info("Categories:")
    for cat, count in manifest["summary"]["category_distribution"].items():
        logger.info("  - %s: %d", cat, count)


if __name__ == "__main__":
    main()
