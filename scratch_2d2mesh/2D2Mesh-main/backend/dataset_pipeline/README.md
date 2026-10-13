# Paired 2D-to-3D Dataset Pipeline

This directory contains a reproducible pipeline for preprocessing, validating, de-duplicating, rendering, and partitioning paired 2D-image and ground-truth 3D-model assets to improve 3D reconstruction models.

---

## Dataset Directory Layout

The dataset is organized at the **object level** rather than the image level to ensure that all multi-view renders, textures, and geometry belong to a single entity and are grouped together during splits.

```text
dataset/
├── train/                  # 70% of objects
│   └── <object_id>/
│       ├── images/         # Multi-view images (original & synthetic)
│       ├── model/          # 3D files (GLB, GLTF, OBJ)
│       ├── textures/       # Optional explicit texture maps
│       └── metadata.json   # Object attributes
├── validation/             # 15% of objects
│   └── <object_id>/
│       └── ...
├── test/                   # 15% of objects
│   └── <object_id>/
│       └── ...
└── metadata/               # Manifest files
    ├── manifest_v1.json
    └── manifest_v2.json
```

---

## Metadata Schema (`metadata.json`)

Each object directory contains a `metadata.json` mapping its attributes:

```json
{
  "object_id": "unique-uuid-or-id",
  "category": "chair",
  "source": "shapenet",
  "image_path": "images/render_000_yaw0_pitch15.png",
  "model_path": "model/mesh.glb",
  "view_angle": "8_multi_view",
  "resolution": "512x512",
  "lighting": "three_point_studio",
  "background": "transparent",
  "material": "textured-pbr",
  "quality": "high"
}
```

---

## Pipeline Components

### 1. Dataset Validator (`dataset_validator.py`)
Audit raw folders to check compliance with quality benchmarks. Invalid folders are rejected with explicit logging.
* **3D Checks:** Vertex and face counts, watertightness, normal health (removes NaN/Inf or zero-length normal vectors), bounding-box sanity.
* **2D Checks:** Resolving resolution, contrast, brightness, blur score (using Laplacian variance), transparency, and object visibility.
```bash
python dataset_validator.py --src-dir /path/to/raw_data --report-file audit_report.json
```

### 2. Duplicate Detector (`duplicate_detector.py`)
Identify duplicate assets to prevent test data leakage and dataset bloat.
* **Images:** Uses difference hashing (dHash) with a default Hamming distance threshold of $\le 4$ bits.
* **Meshes:** Uses translation- and scale-invariant geometric signature hashing (sorted rounded vertex coordinates + topology signature).
```bash
python duplicate_detector.py --dataset-dir /path/to/dataset --report-file duplicate_report.json
```

### 3. Dataset Splitter (`dataset_splitter.py`)
Partition assets into Train (70%), Validation (15%), and Test (15%) splits.
* **Object-Level Boundaries:** Moves or copies the *entire* object folder to prevent visual leakage across sets.
* **Stratification:** Splits are balanced proportionally based on the `category` attribute in `metadata.json`.
* **Reproducibility:** Seeded random distribution (`--seed 42`).
```bash
python dataset_splitter.py --src-dir /path/to/validated --dest-dir /path/to/dataset_v1 --mode copy
```

### 4. Dataset Statistics Compiler (`dataset_statistics.py`)
Compiles versioned dataset manifests (e.g. `manifest_v1.json`) containing total object counts, image counts, category distribution histograms, split counts, and rejections history.
```bash
python dataset_statistics.py --dataset-dir /path/to/dataset_v1 --version v1 --validation-report audit_report.json
```

### 5. Synthetic Renderer (`synthetic_renderer.py`)
An optional Blender-based renderer wrapper. Renders multiple random viewpoints of a 3D model using three-point studio lighting, transparent backgrounds, and variable cameras.
* **Usage:**
```bash
python synthetic_renderer.py --dataset-dir /path/to/dataset_v1 --views 8 --resolution 512
```
* **Requirement:** Blender installed locally. On Windows, the script automatically searches standard directories. Or, supply `--blender-path "C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"`.
