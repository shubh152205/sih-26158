#!/usr/bin/env python3
"""view_assets.py

Quick 3D Asset Visualizer for SIH26158.
Opens an interactive Open3D window to inspect point clouds (.ply) and meshes (.obj / .ply).

Usage:
    python backend/view_assets.py --input ./output/pointmap.ply
    python backend/view_assets.py --input ./output/mesh/drone_surface.obj
    python backend/view_assets.py --input ./final_assets/mesh_demo.obj --wireframe
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive 3D Viewer for Point Clouds and Meshes")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to .ply or .obj file")
    parser.add_argument("--wireframe", "-w", action="store_true", help="Display mesh in wireframe mode")
    parser.add_argument("--point-size", type=float, default=2.0, help="Rendering point size for point clouds")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: File not found at {input_path}")
        sys.exit(1)

    try:
        import open3d as o3d
    except ImportError:
        print("Error: Open3D is not installed. Install via: pip install open3d")
        sys.exit(1)

    print(f"Loading 3D asset: {input_path.name}...")
    suffix = input_path.suffix.lower()

    # Try loading as mesh first if OBJ or if user wants mesh view
    if suffix in (".obj", ".stl", ".gltf", ".glb"):
        geometry = o3d.io.read_triangle_mesh(str(input_path))
        if len(geometry.vertices) == 0:
            print("Failed to load geometry or mesh is empty.")
            sys.exit(1)
        geometry.compute_vertex_normals()
        print(f"Mesh Loaded: {len(geometry.vertices):,} vertices | {len(geometry.triangles):,} triangles")
    else:
        # For .ply, attempt mesh first, then point cloud
        mesh_cand = o3d.io.read_triangle_mesh(str(input_path))
        if len(mesh_cand.triangles) > 0:
            geometry = mesh_cand
            geometry.compute_vertex_normals()
            print(f"Mesh Loaded: {len(geometry.vertices):,} vertices | {len(geometry.triangles):,} triangles")
        else:
            pcd = o3d.io.read_point_cloud(str(input_path))
            if len(pcd.points) == 0:
                print("Failed to load point cloud or file is empty.")
                sys.exit(1)
            geometry = pcd
            print(f"Point Cloud Loaded: {len(geometry.points):,} points")

    print("\nControls:")
    print("  - Left Click + Drag: Rotate")
    print("  - Shift + Left Click + Drag / Middle Click: Pan")
    print("  - Mouse Wheel: Zoom")
    print("  - Press [Q] or [ESC]: Close Window\n")

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=f"SIH26158 3D Viewer - {input_path.name}", width=1280, height=720)
    vis.add_geometry(geometry)

    opt = vis.get_render_option()
    opt.background_color = [0.1, 0.1, 0.1]
    opt.point_size = args.point_size
    if args.wireframe and isinstance(geometry, o3d.geometry.TriangleMesh):
        opt.mesh_show_wireframe = True

    vis.run()
    vis.destroy_window()


if __name__ == "__main__":
    main()
