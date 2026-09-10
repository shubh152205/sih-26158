#!/usr/bin/env python3
"""export_3d_assets.py

SIH26158 3D Asset Packager & Demo Optimizer.
--------------------------------------------
This script prepares the final 3D deliverables for presentation and archiving:
1. Gathers the 3 core pipeline outputs:
   - Dense Point Cloud (PLY) from MASt3R / ViT
   - 3D Gaussian Splat (PLY) from Nerfstudio
   - Watertight Surface Mesh (OBJ & PLY) from Open3D Poisson Reconstruction
2. Copies and standardizes them into a unified, clean output directory.
3. Generates lightweight "Demo-Optimized" assets (voxel-downsampled point cloud
   and simplified quadric decimation mesh) for smooth 60 FPS loading on demo laptops.
4. Generates a comprehensive `metadata.json` capturing point counts, face counts,
   bounding box spans in meters, file sizes, and model version metadata.
5. Prints an ASCII summary table formatted specifically for PPT slide screenshots.

Usage:
    python backend/export_3d_assets.py \
        --pointcloud ./output/pointmap.ply \
        --splat ./exports/splat.ply \
        --mesh ./output/mesh/drone_surface.obj \
        --output-dir ./final_assets \
        --model-version "MASt3R-ViT-L + Splatfacto-30k" \
        --pcd-voxel-size 0.08 \
        --mesh-target-faces 80000
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [ASSET-EXPORT] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ASSET-EXPORT")


# =====================================================================
# Helper: File Size & Formatting Utilities
# =====================================================================

def get_file_size_info(filepath: Path) -> Dict[str, Any]:
    """Returns file size in bytes and human-readable string (MB)."""
    if not filepath.is_file():
        return {"bytes": 0, "formatted": "0 MB"}
    size_bytes = filepath.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return {
        "bytes": size_bytes,
        "formatted": f"{size_mb:.2f} MB",
    }


def compute_bounding_box(points: np.ndarray) -> Dict[str, Any]:
    """Calculates spatial extents, spans, and diagonal in meters."""
    if len(points) == 0:
        return {"min": [0, 0, 0], "max": [0, 0, 0], "span": [0, 0, 0], "diagonal_meters": 0.0}

    min_xyz = np.min(points, axis=0)
    max_xyz = np.max(points, axis=0)
    spans = max_xyz - min_xyz
    diag = float(np.linalg.norm(spans))

    return {
        "min": [round(float(v), 3) for v in min_xyz],
        "max": [round(float(v), 3) for v in max_xyz],
        "span_meters": [round(float(v), 3) for v in spans],
        "diagonal_meters": round(diag, 2),
    }


# =====================================================================
# Point Cloud Processor (Full & Demo Optimization)
# =====================================================================

def process_point_cloud(
    input_ply: Path,
    out_dir: Path,
    voxel_size: float = 0.08,
) -> Dict[str, Any]:
    """Copies full point cloud and creates a lightweight downsampled demo version."""
    import open3d as o3d

    logger.info("Processing Point Cloud: %s", input_ply)
    pcd = o3d.io.read_point_cloud(str(input_ply))
    raw_pts = np.asarray(pcd.points)
    raw_count = len(raw_pts)

    # Standardized full asset
    full_target = out_dir / "pointmap_full.ply"
    shutil.copy2(input_ply, full_target)

    # Demo-optimized asset via voxel downsampling
    logger.info("Downsampling demo point cloud (voxel size = %.3fm)...", voxel_size)
    pcd_demo = pcd.voxel_down_sample(voxel_size=voxel_size)
    demo_count = len(pcd_demo.points)
    demo_target = out_dir / "pointmap_demo.ply"
    o3d.io.write_point_cloud(str(demo_target), pcd_demo, write_ascii=False)

    bbox_info = compute_bounding_box(raw_pts)

    return {
        "full_path": str(full_target.name),
        "full_points": raw_count,
        "full_size": get_file_size_info(full_target),
        "demo_path": str(demo_target.name),
        "demo_points": demo_count,
        "demo_size": get_file_size_info(demo_target),
        "point_reduction_pct": round((1.0 - (demo_count / max(1, raw_count))) * 100.0, 1),
        "bounding_box": bbox_info,
    }


# =====================================================================
# Gaussian Splat Processor
# =====================================================================

def process_gaussian_splat(input_ply: Path, out_dir: Path) -> Dict[str, Any]:
    """Standardizes Gaussian Splat PLY and extracts Gaussian element count."""
    logger.info("Processing Gaussian Splat: %s", input_ply)
    target_splat = out_dir / "splat.ply"
    shutil.copy2(input_ply, target_splat)

    gaussian_count = 0
    bbox_info = {}

    # Attempt parsing gaussian count and positions
    try:
        from plyfile import PlyData
        plydata = PlyData.read(str(input_ply))
        vertex = plydata["vertex"]
        gaussian_count = len(vertex)
        x = np.asarray(vertex["x"])
        y = np.asarray(vertex["y"])
        z = np.asarray(vertex["z"])
        bbox_info = compute_bounding_box(np.column_stack([x, y, z]))
    except Exception as err:
        logger.debug("plyfile inspection skipped: %s", err)
        # Fallback line counter for PLY header
        try:
            with open(input_ply, "r", encoding="ascii", errors="ignore") as f:
                for line in f:
                    if line.startswith("element vertex"):
                        gaussian_count = int(line.strip().split()[-1])
                    elif line.startswith("end_header"):
                        break
        except Exception:
            pass

    return {
        "path": str(target_splat.name),
        "gaussian_count": gaussian_count,
        "file_size": get_file_size_info(target_splat),
        "bounding_box": bbox_info,
    }


# =====================================================================
# Mesh Processor (Full & Demo Optimization)
# =====================================================================

def process_mesh(
    mesh_path: Path,
    out_dir: Path,
    target_faces: int = 80000,
) -> Dict[str, Any]:
    """Standardizes full mesh (OBJ/PLY) and creates a decimated demo version."""
    import open3d as o3d

    logger.info("Processing Surface Mesh: %s", mesh_path)
    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    mesh.compute_vertex_normals()

    raw_vertices = len(mesh.vertices)
    raw_faces = len(mesh.triangles)

    # Save full mesh in both formats
    full_obj = out_dir / "mesh_full.obj"
    full_ply = out_dir / "mesh_full.ply"
    o3d.io.write_triangle_mesh(str(full_obj), mesh, write_triangle_uvs=False)
    o3d.io.write_triangle_mesh(str(full_ply), mesh, write_ascii=False)

    # Demo-optimized simplified mesh
    logger.info("Decimating demo mesh: %d faces -> %d target faces...", raw_faces, target_faces)
    if raw_faces > target_faces:
        mesh_demo = mesh.simplify_quadric_decimation(target_number_of_triangles=target_faces)
        mesh_demo.remove_unreferenced_vertices()
        mesh_demo.compute_vertex_normals()
    else:
        mesh_demo = mesh

    demo_vertices = len(mesh_demo.vertices)
    demo_faces = len(mesh_demo.triangles)

    demo_obj = out_dir / "mesh_demo.obj"
    demo_ply = out_dir / "mesh_demo.ply"
    o3d.io.write_triangle_mesh(str(demo_obj), mesh_demo, write_triangle_uvs=False)
    o3d.io.write_triangle_mesh(str(demo_ply), mesh_demo, write_ascii=False)

    bbox_info = compute_bounding_box(np.asarray(mesh.vertices))

    return {
        "full_obj": str(full_obj.name),
        "full_ply": str(full_ply.name),
        "full_vertices": raw_vertices,
        "full_faces": raw_faces,
        "full_size_obj": get_file_size_info(full_obj),
        "demo_obj": str(demo_obj.name),
        "demo_ply": str(demo_ply.name),
        "demo_vertices": demo_vertices,
        "demo_faces": demo_faces,
        "demo_size_obj": get_file_size_info(demo_obj),
        "face_reduction_pct": round((1.0 - (demo_faces / max(1, raw_faces))) * 100.0, 1),
        "bounding_box": bbox_info,
    }


# =====================================================================
# Console Summary Table for PPT Screenshot
# =====================================================================

def print_presentation_summary(meta: Dict[str, Any], output_dir: Path) -> None:
    """Prints a clean ASCII summary table ready for PPT presentation screenshots."""
    pcd = meta.get("point_cloud", {})
    splat = meta.get("gaussian_splat", {})
    mesh = meta.get("mesh", {})
    config = meta.get("pipeline_configuration", {})

    print("\n" + "=" * 76)
    print("      SIH26158 DRONE 3D RECONSTRUCTION - FINAL ASSET EXPORT AUDIT      ")
    print("=" * 76)
    print(f"Timestamp:       {meta.get('export_timestamp')}")
    print(f"Pipeline Config: {config.get('model_version')}")
    print(f"Output Folder:   {output_dir.resolve()}")
    print("-" * 76)
    print(f"{'ASSET TYPE':<22} | {'PRIMITIVE COUNT':<20} | {'RAW SIZE':<11} | {'DEMO SIZE':<11}")
    print("-" * 76)

    # Point Cloud row
    pcd_str = f"{pcd.get('full_points', 0):,} pts -> {pcd.get('demo_points', 0):,} pts"
    print(f"{'1. Dense Point Cloud':<22} | {pcd_str:<20} | {pcd.get('full_size', {}).get('formatted', '-'):<11} | {pcd.get('demo_size', {}).get('formatted', '-'):<11}")

    # Gaussian Splat row
    splat_str = f"{splat.get('gaussian_count', 0):,} gaussians"
    print(f"{'2. Gaussian Splat':<22} | {splat_str:<20} | {splat.get('file_size', {}).get('formatted', '-'):<11} | {'-':<11}")

    # Mesh row
    mesh_str = f"{mesh.get('full_faces', 0):,} f -> {mesh.get('demo_faces', 0):,} f"
    print(f"{'3. Surface Mesh (OBJ)':<22} | {mesh_str:<20} | {mesh.get('full_size_obj', {}).get('formatted', '-'):<11} | {mesh.get('demo_size_obj', {}).get('formatted', '-'):<11}")

    print("-" * 76)
    # Metric extents
    bbox = pcd.get("bounding_box", {})
    span = bbox.get("span_meters", [0, 0, 0])
    diag = bbox.get("diagonal_meters", 0.0)
    print(f"Physical Scene Extents:  Length: {span[0]:.1f}m | Width: {span[1]:.1f}m | Height: {span[2]:.1f}m")
    print(f"Bounding Box Diagonal:   {diag:.2f} meters")
    print("-" * 76)
    print("STATUS: \033[92m[ALL 3D ASSETS EXPORTED & DEMO-OPTIMIZED FOR JUDGING DAY]\033[0m")
    print("=" * 76 + "\n")


# =====================================================================
# Main Orchestrator
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIH26158 3D Asset Packaging & Demo Optimization Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--pointcloud", "-p", type=str, required=True, help="Path to input point cloud PLY")
    parser.add_argument("--splat", "-s", type=str, required=True, help="Path to input Gaussian Splat PLY")
    parser.add_argument("--mesh", "-m", type=str, required=True, help="Path to input mesh (OBJ or PLY)")
    parser.add_argument("--output-dir", "-o", type=str, default="./output/final_assets", help="Target export folder")
    parser.add_argument("--model-version", type=str, default="MASt3R-ViT-Large + Splatfacto", help="Model descriptor")
    parser.add_argument("--pcd-voxel-size", type=float, default=0.08, help="Voxel size in meters for demo point cloud")
    parser.add_argument("--mesh-target-faces", type=int, default=80000, help="Target face count for demo mesh")
    parser.add_argument("--mission-id", type=str, default="mission-alpha", help="Mission or dataset identifier")

    args = parser.parse_args()

    pcd_path = Path(args.pointcloud).resolve()
    splat_path = Path(args.splat).resolve()
    mesh_path = Path(args.mesh).resolve()
    out_dir = Path(args.output_dir).resolve()

    # Validate inputs
    for name, p in [("Point cloud", pcd_path), ("Gaussian splat", splat_path), ("Mesh", mesh_path)]:
        if not p.is_file():
            logger.error("%s file not found at: %s", name, p)
            sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Exporting standardized 3D assets to: %s", out_dir)

    # 1. Process Point Cloud
    pcd_meta = process_point_cloud(pcd_path, out_dir, voxel_size=args.pcd_voxel_size)

    # 2. Process Gaussian Splat
    splat_meta = process_gaussian_splat(splat_path, out_dir)

    # 3. Process Surface Mesh
    mesh_meta = process_mesh(mesh_path, out_dir, target_faces=args.mesh_target_faces)

    # 4. Compile metadata.json
    metadata = {
        "mission_id": args.mission_id,
        "export_timestamp": datetime.datetime.now().isoformat(),
        "pipeline_configuration": {
            "model_version": args.model_version,
            "pcd_demo_voxel_size": args.pcd_voxel_size,
            "mesh_demo_target_faces": args.mesh_target_faces,
        },
        "point_cloud": pcd_meta,
        "gaussian_splat": splat_meta,
        "mesh": mesh_meta,
    }

    metadata_path = out_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Wrote audit metadata to: %s", metadata_path)

    # 5. Output presentation table
    print_presentation_summary(metadata, out_dir)


if __name__ == "__main__":
    main()
