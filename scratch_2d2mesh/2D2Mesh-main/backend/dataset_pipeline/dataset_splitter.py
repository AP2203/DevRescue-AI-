#!/usr/bin/env python3
"""Dataset Splitter.

Splits a dataset of 3D objects into train, validation, and test subsets.
Enforces object-level splitting: all images/views of the same object are placed
into the same split to prevent data leakage. Shuffles reproducibly using a seed.
Supports category-stratified splitting.
"""

import argparse
import json
import logging
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class DatasetSplitter:
    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> None:
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

        # Normalize ratios
        total = train_ratio + val_ratio + test_ratio
        if abs(total - 1.0) > 1e-5:
            self.train_ratio /= total
            self.val_ratio /= total
            self.test_ratio /= total

    def read_category(self, obj_dir: Path) -> str:
        """Read the category of an object from its metadata.json file."""
        meta_path = obj_dir / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                category = meta.get("category", "").strip().lower()
                if category:
                    return category
            except Exception as exc:
                logger.warning("Could not read category from metadata in %s: %s", obj_dir.name, exc)
        return "unclassified"

    def split_dataset(
        self,
        src_dir: Path,
        dest_dir: Path,
        mode: str = "copy"
    ) -> Dict[str, List[str]]:
        """Perform category-stratified splitting of the dataset folders."""
        # Locate all subdirectories in the source folder
        obj_dirs = [d for d in src_dir.iterdir() if d.is_dir()]
        logger.info("Found %d objects in source directory '%s'", len(obj_dirs), src_dir)

        # 1. Group objects by category
        category_map = defaultdict(list)
        for obj_dir in obj_dirs:
            cat = self.read_category(obj_dir)
            category_map[cat].append(obj_dir)

        logger.info("Category distribution in raw dataset:")
        for cat, items in category_map.items():
            logger.info("  - %s: %d", cat, len(items))

        # Seed random for reproducibility
        random.seed(self.seed)

        splits: Dict[str, List[Path]] = {
            "train": [],
            "validation": [],
            "test": [],
        }

        # 2. Split each category independently
        for cat, items in category_map.items():
            # Shuffle items within this category reproducibly
            shuffled = sorted(items, key=lambda x: x.name)  # sort first to neutralize OS directory listing order
            random.shuffle(shuffled)

            n_total = len(shuffled)
            n_train = max(1 if n_total >= 3 else 0, int(round(n_total * self.train_ratio)))
            n_val = max(1 if n_total >= 3 else 0, int(round(n_total * self.val_ratio)))
            
            # Put remainder in test
            n_test = n_total - n_train - n_val
            
            # Corner cases adjustment
            if n_train + n_val + n_test != n_total:
                n_train = n_total - n_val - n_test

            cat_train = shuffled[:n_train]
            cat_val = shuffled[n_train : n_train + n_val]
            cat_test = shuffled[n_train + n_val :]

            splits["train"].extend(cat_train)
            splits["validation"].extend(cat_val)
            splits["test"].extend(cat_test)

            logger.debug(
                "Category '%s' split: Train %d, Val %d, Test %d",
                cat, len(cat_train), len(cat_val), len(cat_test)
            )

        # 3. Create destination folders
        for split_name in splits:
            (dest_dir / split_name).mkdir(parents=True, exist_ok=True)

        # 4. Copy/Move directories to their splits
        results: Dict[str, List[str]] = {
            "train": [],
            "validation": [],
            "test": [],
        }

        for split_name, paths in splits.items():
            split_dest = dest_dir / split_name
            for path in paths:
                target_path = split_dest / path.name
                
                # Clean existing target
                if target_path.exists():
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()

                try:
                    if mode == "move":
                        shutil.move(str(path), str(target_path))
                    else:
                        shutil.copytree(str(path), str(target_path))
                    results[split_name].append(path.name)
                except Exception as exc:
                    logger.error("Failed to copy/move %s to %s split: %s", path.name, split_name, exc)

        logger.info("Split execution completed:")
        logger.info("  - Train: %d objects", len(results["train"]))
        logger.info("  - Validation: %d objects", len(results["validation"]))
        logger.info("  - Test: %d objects", len(results["test"]))

        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Dataset Pipeline - Stratified Splitter")
    parser.add_argument("--src-dir", type=str, required=True, help="Source directory containing validated object folders")
    parser.add_argument("--dest-dir", type=str, required=True, help="Destination directory to output splits")
    parser.add_argument("--mode", type=str, choices=["copy", "move"], default="copy", help="File operation mode: copy or move")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Ratio for training split")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Ratio for validation split")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Ratio for test split")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible shuffling")
    args = parser.parse_args()

    src_dir = Path(args.src_dir)
    dest_dir = Path(args.dest_dir)

    if not src_dir.exists():
        logger.error("Source directory '%s' does not exist.", src_dir)
        sys.exit(1)

    splitter = DatasetSplitter(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed
    )
    splitter.split_dataset(src_dir, dest_dir, mode=args.mode)


if __name__ == "__main__":
    main()
