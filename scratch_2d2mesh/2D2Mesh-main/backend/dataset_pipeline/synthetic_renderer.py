#!/usr/bin/env python3
"""Synthetic View Renderer.

Uses Blender (headless) to render multi-view images of a 3D model.
Supports randomized camera positions, lighting intensity/colors, materials,
and backgrounds.

Usage:
  # To run as a wrapper that spawns Blender:
  python synthetic_renderer.py --dataset-dir ./dataset --views 8

  # Note: The script searches for blender.exe in default Windows locations.
  # You can also supply the path explicitly using --blender-path
"""

import argparse
import glob
import json
import os
import random
import subprocess
import sys
from pathlib import Path

# Check if we are running inside Blender's python interpreter
try:
    import bpy
    import mathutils
    IS_INSIDE_BLENDER = True
except ImportError:
    IS_INSIDE_BLENDER = False


def find_blender_windows() -> str | None:
    """Attempt to locate blender.exe in default Windows installation paths."""
    common_roots = [
        Path("C:/Program Files/Blender Foundation"),
        Path("C:/Program Files (x86)/Blender Foundation"),
    ]
    for root in common_roots:
        if root.exists():
            # Search for blender.exe in subdirs
            paths = list(root.glob("**/blender.exe"))
            if paths:
                # Return the latest version found (sorted alphabetically)
                paths.sort()
                return str(paths[-1])
    return None


# ==============================================================================
# BLENDER IN-PROCESS RENDERING LOGIC
# ==============================================================================

if IS_INSIDE_BLENDER:
    import math

    def clean_scene() -> None:
        """Clear all default objects, cameras, and lights from the scene."""
        bpy.ops.wm.read_factory_settings(use_empty=True)
        # Remove any lingering objects
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    def import_model(model_path: Path) -> bpy.types.Object:
        """Import GLB, GLTF, or OBJ into the scene and return the loaded mesh object."""
        ext = model_path.suffix.lower()
        
        # Keep track of objects before import
        existing_objs = set(bpy.data.objects)
        
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=str(model_path))
        elif ext == ".obj":
            try:
                # Newer Blender versions (4.0+)
                bpy.ops.wm.obj_import(filepath=str(model_path))
            except AttributeError:
                # Older Blender versions
                bpy.ops.import_scene.obj(filepath=str(model_path))
        else:
            raise ValueError(f"Unsupported model extension: {ext}")

        # Identify newly imported objects
        new_objs = set(bpy.data.objects) - existing_objs
        if not new_objs:
            raise RuntimeError("Import failed: no objects loaded.")

        # Find the primary mesh or group it
        meshes = [o for o in new_objs if o.type == 'MESH']
        if not meshes:
            # Check if there is an empty containing meshes
            empties = [o for o in new_objs if o.type == 'EMPTY']
            if empties:
                return empties[0]
            return list(new_objs)[0]
        
        # Center mesh origin and scale it
        # For simplicity, return the first mesh object or join them
        return meshes[0]

    def setup_render_engine(resolution: int = 512, transparent: bool = True) -> None:
        """Configure EEVEE rendering engine parameters."""
        scene = bpy.context.scene
        # EEVEE is fast and adequate for synthetic dataset views
        scene.render.engine = 'BLENDER_EEVEE'
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
        
        if transparent:
            scene.render.film_transparent = True

    def setup_camera_and_lighting(target_obj: bpy.types.Object) -> Tuple[bpy.types.Object, List[bpy.types.Object]]:
        """Add a camera track-constrained to target object, and multiple point lights."""
        scene = bpy.context.scene

        # 1. Create a target empty at the object center to point camera at
        target_empty = bpy.data.objects.new("CameraTarget", None)
        scene.collection.objects.link(target_empty)
        
        # Center empty at bounding box center
        if target_obj.type == 'MESH':
            local_bbox = [target_obj.matrix_world @ mathutils.Vector(corner) for corner in target_obj.bound_box]
            bbox_center = sum(local_bbox, mathutils.Vector()) / 8.0
            target_empty.location = bbox_center
        else:
            target_empty.location = target_obj.location

        # 2. Setup Camera
        camera_data = bpy.data.cameras.new("SyntheticCamera")
        # Lower focal length for wider field of view
        camera_data.lens = 35
        camera_obj = bpy.data.objects.new("SyntheticCamera", camera_data)
        scene.collection.objects.link(camera_obj)
        scene.camera = camera_obj

        # Add Track To constraint pointing to center empty
        track_to = camera_obj.constraints.new(type='TRACK_TO')
        track_to.target = target_empty
        track_to.track_axis = 'TRACK_NEGATIVE_Z'
        track_to.up_axis = 'UP_Y'

        # 3. Setup Lights (Three-point lighting setup)
        lights = []
        light_positions = [
            ("KeyLight", (5.0, 5.0, 6.0), 1200.0, (1.0, 0.95, 0.9)),
            ("FillLight", (-5.0, 3.0, 4.0), 600.0, (0.9, 0.95, 1.0)),
            ("RimLight", (0.0, -6.0, 5.0), 800.0, (1.0, 1.0, 1.0)),
        ]
        for name, pos, energy, color in light_positions:
            l_data = bpy.data.lights.new(name, type='POINT')
            l_data.energy = energy
            l_data.color = color
            l_obj = bpy.data.objects.new(name, l_data)
            scene.collection.objects.link(l_obj)
            l_obj.location = pos
            lights.append(l_obj)

        return camera_obj, lights

    def render_views(
        model_path: Path,
        output_dir: Path,
        num_views: int,
        resolution: int,
        randomize: bool
    ) -> None:
        """Load model and render multiple views sequentially."""
        clean_scene()
        setup_render_engine(resolution=resolution)
        
        # Import target mesh
        target = import_model(model_path)
        camera, lights = setup_camera_and_lighting(target)
        
        # Determine camera distance based on bounding box size
        if target.type == 'MESH':
            extents = [target.bound_box[i] for i in range(8)]
            max_dim = max(max(e) - min(e) for e in zip(*extents))
            distance_base = max(1.5, max_dim * 1.8)
        else:
            distance_base = 3.0

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting rendering of %d views...", num_views)

        for i in range(num_views):
            # 1. Spherical coordinates setup
            # Distribute yaw angles evenly, add random jitter if requested
            base_yaw = (360.0 / num_views) * i
            yaw = base_yaw + (random.uniform(-10, 10) if randomize else 0.0)
            pitch = 15.0 + (random.uniform(-10, 25) if randomize else 15.0)
            distance = distance_base + (random.uniform(-0.2, 0.5) if randomize else 0.0)

            # 2. Calculate position
            phi = math.radians(yaw)
            theta = math.radians(90.0 - pitch)
            
            x = distance * math.sin(theta) * math.cos(phi)
            y = distance * math.sin(theta) * math.sin(phi)
            z = distance * math.cos(theta)
            
            camera.location = (x, y, z)

            # 3. Randomize lights slightly if requested
            if randomize:
                for light in lights:
                    light.data.energy *= random.uniform(0.8, 1.2)

            # 4. Render and save
            filename = f"render_{i:03d}_yaw{int(yaw)}_pitch{int(pitch)}.png"
            dest_img_path = output_dir / filename
            
            bpy.context.scene.render.filepath = str(dest_img_path)
            bpy.ops.render.render(write_still=True)
            logger.info("Rendered view %d/%d -> %s", i+1, num_views, filename)


# ==============================================================================
# SUBPROCESS LAUNCHER/WRAPPER (STANDARD PYTHON)
# ==============================================================================

def main_launcher() -> None:
    parser = argparse.ArgumentParser(description="Vision3D Dataset Pipeline - Synthetic View Renderer")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Directory containing validated objects")
    parser.add_argument("--views", type=int, default=8, help="Number of synthetic views to render per object")
    parser.add_argument("--resolution", type=int, default=512, help="Resolution of rendered images")
    parser.add_argument("--randomize", action="store_true", default=True, help="Randomize camera offset, light intensity and pitch angles")
    parser.add_argument("--blender-path", type=str, default=None, help="Path to the blender.exe executable")
    parser.add_argument("--object-id", type=str, default=None, help="Limit rendering to a single object_id folder")
    args = parser.parse_args()

    # 1. Resolve Blender Path
    blender_bin = args.blender_path
    if not blender_bin:
        # Check environment or attempt autodetect
        blender_bin = os.environ.get("BLENDER_PATH")
        if not blender_bin and sys.platform.startswith("win"):
            blender_bin = find_blender_windows()

    if not blender_bin:
        print("Error: Could not find Blender automatically.")
        print("Please ensure Blender is installed and either:")
        print("  - Provide the path via --blender-path")
        print("  - Set the BLENDER_PATH environment variable")
        print("  - Add Blender folder to your PATH environment variable")
        sys.exit(1)

    print(f"Using Blender executable: {blender_bin}")

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.exists():
        print(f"Error: Dataset directory {dataset_dir} does not exist.")
        sys.exit(1)

    # 2. Gather object folders
    if args.object_id:
        obj_dirs = [dataset_dir / args.object_id]
        if not obj_dirs[0].exists():
            print(f"Error: Specified object folder {obj_dirs[0]} does not exist.")
            sys.exit(1)
    else:
        obj_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]

    print(f"Processing {len(obj_dirs)} objects...")

    for obj_dir in obj_dirs:
        model_dir = obj_dir / "model"
        if not model_dir.exists():
            print(f"Skipping {obj_dir.name}: missing 'model/' folder")
            continue

        models = list(model_dir.glob("*.glb")) + list(model_dir.glob("*.gltf")) + list(model_dir.glob("*.obj"))
        if not models:
            print(f"Skipping {obj_dir.name}: no GLB/GLTF/OBJ found in 'model/' folder")
            continue

        model_path = models[0]
        output_dir = obj_dir / "images"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--- Rendering {obj_dir.name} ---")
        print(f"Model:  {model_path.name}")
        print(f"Target: {output_dir}")

        # Spawn blender subprocess in background, passing arguments to ourself running inside Blender
        cmd = [
            blender_bin,
            "--background",
            "--python", __file__,
            "--",
            "--model-path", str(model_path),
            "--output-dir", str(output_dir),
            "--views", str(args.views),
            "--resolution", str(args.resolution),
            "--randomize", str(args.randomize)
        ]

        try:
            subprocess.run(cmd, check=True)
            # Update metadata.json with lighting/views details
            meta_path = obj_dir / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    meta["view_angle"] = f"{args.views}_multi_view"
                    meta["resolution"] = f"{args.resolution}x{args.resolution}"
                    meta["lighting"] = "three_point_studio"
                    meta["background"] = "transparent"
                    meta_path.write_text(json.dumps(meta, indent=2))
                except Exception as meta_exc:
                    print(f"Warning: Failed to update metadata.json: {meta_exc}")
        except subprocess.CalledProcessError as exc:
            print(f"Error rendering {obj_dir.name} views: {exc}")


if __name__ == "__main__":
    if IS_INSIDE_BLENDER:
        # Extract arguments after "--" when running inside Blender
        # E.g. blender -b -P script.py -- --model-path ...
        try:
            idx = sys.argv.index("--")
            inner_args = sys.argv[idx + 1:]
        except ValueError:
            inner_args = []

        parser = argparse.ArgumentParser()
        parser.add_argument("--model-path", type=str, required=True)
        parser.add_argument("--output-dir", type=str, required=True)
        parser.add_argument("--views", type=int, default=8)
        parser.add_argument("--resolution", type=int, default=512)
        parser.add_argument("--randomize", type=str, default="True")
        
        args = parser.parse_args(inner_args)
        
        render_views(
            model_path=Path(args.model_path),
            output_dir=Path(args.output_dir),
            num_views=args.views,
            resolution=args.resolution,
            randomize=args.randomize.lower() == "true"
        )
    else:
        main_launcher()
