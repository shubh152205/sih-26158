#!/usr/bin/env python3
"""generate_mesh.py

Open3D-based Poisson Surface Reconstruction Pipeline for Drone Point Clouds.
1. Ingests cleaned 3D point cloud (PLY with XYZ, RGB, and optional confidence).
2. Robust normal estimation with consistent orientation (tangent plane / Z-up alignment).
3. Screened Poisson Surface Reconstruction with configurable octree depth.
4. Confidence-weighted density filtering to prune extrapolated Poisson bubbles.
5. Mesh post-processing:
   - Removes small disconnected cluster components below threshold.
   - Cleans degenerate/duplicated triangles and unreferenced vertices.
   - Applies Laplacian smoothing (configurable iterations).
   - Optional Quadric Decimation to target face count for real-time demo performance.
6. Exports as both .obj and .ply with material/vertex colors.
7. Prints detailed stats (vertices, faces before/after decimation).
8. Interactive visualization window via `--visualize`.

Usage:
    python generate_mesh.py \
        --input ./output/pointmap.ply \
        --output-dir ./output/mesh \
        --name drone_surface \
        --depth 9 \
        --smooth-iterations 5 \
        --target-faces 200000 \
        --visualize
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [MESH-GEN] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MESH-GEN")


def load_point_cloud_with_confidence(ply_path: Path) -> Tuple[Any, Optional[np.ndarray]]:
    """Loads point cloud and extracts per-point confidence if present in PLY properties."""
    import open3d as o3d

    logger.info("Loading point cloud from: %s", ply_path)
    pcd = o3d.io.read_point_cloud(str(ply_path))
    if len(pcd.points) == 0:
        raise ValueError(f"Point cloud at {ply_path} is empty or unreadable!")

    logger.info("Loaded %d points from PLY.", len(pcd.points))

    # Inspect for confidence attribute using plyfile if available
    confidences = None
    try:
        from plyfile import PlyData
        plydata = PlyData.read(str(ply_path))
        vertex = plydata["vertex"]
        # Look for standard confidence property names from ViT / MASt3R / COLMAP
        for prop in ["confidence", "conf", "scalar_confidence", "weight", "quality"]:
            if prop in vertex:
                confidences = np.asarray(vertex[prop], dtype=np.float32)
                logger.info(
                    "Found '%s' attribute: min=%.3f, max=%.3f, mean=%.3f",
                    prop, float(np.min(confidences)), float(np.max(confidences)), float(np.mean(confidences))
                )
                break
    except Exception as err:
        logger.debug("plyfile check for confidence skipped: %s", err)

    return pcd, confidences


def estimate_consistent_normals(
    pcd: Any,
    knn: int = 30,
    radius: Optional[float] = None,
    orient_up: bool = True,
) -> None:
    """Estimates surface normals and consistently orients them."""
    import open3d as o3d

    logger.info("Estimating point cloud normals (k=%d)...", knn)
    if radius is not None and radius > 0:
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=knn)
        )
    else:
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamKNN(knn=knn)
        )

    # Orient consistently along tangent planes
    logger.info("Orienting normals with consistent tangent planes...")
    pcd.orient_normals_consistent_tangent_plane(k=knn)

    # In aerial drone surveys, ensure dominant normal vector points upward (+Z >= 0)
    if orient_up:
        normals = np.asarray(pcd.normals)
        mean_normal_z = np.mean(normals[:, 2])
        if mean_normal_z < 0:
            logger.info("Inverting normals to consistently align with +Z sky orientation.")
            pcd.normals = o3d.utility.Vector3dVector(-normals)


def run_poisson_reconstruction(
    pcd: Any,
    depth: int = 9,
    linear_fit: bool = True,
) -> Tuple[Any, np.ndarray]:
    """Executes screened Poisson Surface Reconstruction, returning (mesh, densities)."""
    import open3d as o3d

    logger.info("Executing Screened Poisson Surface Reconstruction (octree depth=%d)...", depth)
    t0 = time.time()
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd,
        depth=depth,
        linear_fit=linear_fit,
        n_threads=os.cpu_count() or 4,
    )
    dt = time.time() - t0
    densities_np = np.asarray(densities)
    logger.info(
        "Poisson reconstruction completed in %.2fs: %d vertices, %d triangles.",
        dt, len(mesh.vertices), len(mesh.triangles)
    )
    return mesh, densities_np


def trim_poisson_envelope(mesh: Any, densities: np.ndarray, density_quantile: float = 0.05) -> Any:
    """Prunes extrapolated low-density Poisson bubbles and boundary artifacts."""
    import open3d as o3d

    if density_quantile <= 0:
        return mesh

    thresh = np.quantile(densities, density_quantile)
    logger.info(
        "Trimming low-density vertices (threshold = %.3f, quantile = %.1f%%)...",
        thresh, density_quantile * 100.0
    )
    vertices_to_remove = densities < thresh
    mesh.remove_vertices_by_mask(vertices_to_remove)
    mesh.remove_unreferenced_vertices()
    logger.info("After density trimming: %d vertices, %d triangles.", len(mesh.vertices), len(mesh.triangles))
    return mesh


def remove_small_components(mesh: Any, min_triangles: int = 200) -> Any:
    """Removes small disconnected floating triangle islands."""
    import open3d as o3d

    triangle_clusters, num_triangles, _ = mesh.cluster_connected_triangles()
    triangle_clusters = np.asarray(triangle_clusters)
    num_triangles = np.asarray(num_triangles)

    if len(num_triangles) <= 1:
        return mesh

    # Identify small clusters
    small_cluster_ids = np.where(num_triangles < min_triangles)[0]
    if len(small_cluster_ids) == 0:
        return mesh

    triangles_to_remove = np.isin(triangle_clusters, small_cluster_ids)
    mesh.remove_triangles_by_mask(triangles_to_remove)
    mesh.remove_unreferenced_vertices()
    logger.info(
        "Pruned %d small floating components (<%d triangles). Retained: %d triangles.",
        len(small_cluster_ids), min_triangles, len(mesh.triangles)
    )
    return mesh


def smooth_and_decimate(
    mesh: Any,
    smooth_iterations: int = 5,
    target_faces: Optional[int] = None,
) -> Any:
    """Cleans topology, applies Laplacian smoothing, and simplifies faces for real-time demo."""
    # Clean non-manifold and degenerate elements
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    # Laplacian smoothing
    if smooth_iterations > 0:
        logger.info("Applying %d iterations of Laplacian mesh smoothing...", smooth_iterations)
        mesh = mesh.filter_smooth_laplacian(number_of_iterations=smooth_iterations)
        mesh.compute_vertex_normals()

    # Quadric Decimation if target_faces specified
    if target_faces and target_faces > 0 and len(mesh.triangles) > target_faces:
        initial_faces = len(mesh.triangles)
        logger.info("Decimating mesh: %d -> %d target faces...", initial_faces, target_faces)
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_faces)
        mesh.remove_unreferenced_vertices()
        mesh.compute_vertex_normals()
        logger.info("Decimation complete. Retained: %d faces.", len(mesh.triangles))

    return mesh


def transfer_vertex_colors(pcd: Any, mesh: Any) -> None:
    """Interpolates RGB vertex colors from nearest point cloud points onto the mesh."""
    import open3d as o3d
    from scipy.spatial import KDTree

    if not pcd.has_colors():
        return

    logger.info("Mapping RGB colors from point cloud onto mesh vertices...")
    pcd_pts = np.asarray(pcd.points)
    pcd_colors = np.asarray(pcd.colors)
    mesh_pts = np.asarray(mesh.vertices)

    kdtree = KDTree(pcd_pts)
    _, idxs = kdtree.query(mesh_pts, k=1)
    mesh_colors = pcd_colors[idxs]
    mesh.vertex_colors = o3d.utility.Vector3dVector(mesh_colors)


def export_mesh_formats(
    mesh: Any,
    output_dir: Path,
    base_name: str,
    y_up: bool = False,
) -> Tuple[Path, Path]:
    """Exports reconstructed mesh to both .obj and .ply formats, optionally aligned to glTF 2.0 Y-Up convention."""
    import open3d as o3d

    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / f"{base_name}.obj"
    ply_path = output_dir / f"{base_name}.ply"

    export_mesh = mesh
    if y_up:
        # Standard transformation from GIS/Robotics Z-Up (X=East, Y=North, Z=Up)
        # to glTF 2.0 / WebGL Y-Up (X=East, Y=Up, Z=-North)
        r_zup_to_yup = np.array([
            [1.0,  0.0,  0.0, 0.0],
            [0.0,  0.0,  1.0, 0.0],
            [0.0, -1.0,  0.0, 0.0],
            [0.0,  0.0,  0.0, 1.0],
        ], dtype=np.float64)
        export_mesh = o3d.geometry.TriangleMesh(mesh)
        export_mesh.transform(r_zup_to_yup)
        logger.info("Transformed mesh to glTF 2.0 / WebGL Y-Up coordinate convention.")

    logger.info("Saving mesh to OBJ: %s", obj_path)
    o3d.io.write_triangle_mesh(str(obj_path), export_mesh, write_triangle_uvs=False)

    logger.info("Saving mesh to PLY: %s", ply_path)
    o3d.io.write_triangle_mesh(str(ply_path), export_mesh, write_ascii=False)

    return obj_path, ply_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screened Poisson 3D Surface Mesh Generator for Drone Point Clouds",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Input point cloud PLY file")
    parser.add_argument("--output-dir", "-o", type=str, default="./output/mesh", help="Destination folder for exported meshes")
    parser.add_argument("--name", type=str, default="drone_mesh", help="Base filename for exported OBJ and PLY")
    parser.add_argument("--depth", type=int, default=9, help="Poisson octree reconstruction depth (8-11)")
    parser.add_argument("--density-quantile", type=float, default=0.05, help="Trim lower quantile of low-density Poisson envelope")
    parser.add_argument("--min-cluster-triangles", type=int, default=300, help="Prune disconnected triangle islands smaller than this")
    parser.add_argument("--smooth-iterations", type=int, default=5, help="Number of Laplacian smoothing passes")
    parser.add_argument("--target-faces", type=int, default=None, help="Optional Quadric decimation target triangle count (e.g. 200000)")
    parser.add_argument("--knn-normals", type=int, default=30, help="KNN neighborhood for normal estimation")
    parser.add_argument("--y-up", action="store_true", help="Rotate exported mesh to glTF 2.0 / WebGL Y-Up coordinate convention")
    parser.add_argument("--visualize", action="store_true", help="Launch interactive Open3D window to inspect mesh")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        logger.error("Input point cloud file does not exist: %s", input_path)
        sys.exit(1)

    t_start = time.time()

    # 1. Load point cloud and extract optional confidence
    pcd, confidences = load_point_cloud_with_confidence(input_path)

    # 2. Filter low-confidence points if confidence exists
    if confidences is not None:
        valid_mask = confidences >= np.quantile(confidences, 0.10)
        pcd_pts = np.asarray(pcd.points)[valid_mask]
        pcd_colors = np.asarray(pcd.colors)[valid_mask] if pcd.has_colors() else None
        
        import open3d as o3d
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pcd_pts)
        if pcd_colors is not None:
            pcd.colors = o3d.utility.Vector3dVector(pcd_colors)
        logger.info("Filtered point cloud by confidence: %d high-confidence points retained.", len(pcd.points))

    # 3. Estimate consistent surface normals
    estimate_consistent_normals(pcd, knn=args.knn_normals)

    # 4. Screened Poisson Surface Reconstruction
    raw_mesh, densities = run_poisson_reconstruction(pcd, depth=args.depth)
    initial_vertices = len(raw_mesh.vertices)
    initial_faces = len(raw_mesh.triangles)

    # 5. Trim Poisson outer envelope
    trimmed_mesh = trim_poisson_envelope(raw_mesh, densities, density_quantile=args.density_quantile)

    # 6. Remove small disconnected floating islands
    filtered_mesh = remove_small_components(trimmed_mesh, min_triangles=args.min_cluster_triangles)

    # 7. Smoothing and Decimation
    final_mesh = smooth_and_decimate(
        filtered_mesh,
        smooth_iterations=args.smooth_iterations,
        target_faces=args.target_faces,
    )

    # 8. Transfer RGB vertex colors from point cloud
    transfer_vertex_colors(pcd, final_mesh)

    # 9. Export to OBJ and PLY
    out_dir = Path(args.output_dir)
    obj_path, ply_path = export_mesh_formats(final_mesh, out_dir, args.name, y_up=args.y_up)

    total_time = time.time() - t_start
    final_vertices = len(final_mesh.vertices)
    final_faces = len(final_mesh.triangles)

    # Print Summary Table
    print("\n" + "=" * 65)
    print("           POISSON SURFACE MESH RECONSTRUCTION STATS           ")
    print("=" * 65)
    print(f"Input Point Cloud:      {input_path.name} ({len(pcd.points):,} points)")
    print(f"Octree Depth:           {args.depth}")
    print(f"Laplacian Smoothing:    {args.smooth_iterations} iterations")
    print("-" * 65)
    print(f"Initial Poisson Mesh:   {initial_vertices:,} vertices | {initial_faces:,} faces")
    print(f"Final Cleaned Mesh:     {final_vertices:,} vertices | {final_faces:,} faces")
    if args.target_faces:
        reduction_pct = (1.0 - (final_faces / max(1, initial_faces))) * 100.0
        print(f"Decimation Reduction:   {reduction_pct:.1f}% faces reduced")
    print("-" * 65)
    print(f"Exported OBJ:           {obj_path.resolve()}")
    print(f"Exported PLY:           {ply_path.resolve()}")
    print(f"Total Processing Time:  {total_time:.2f} seconds")
    print("=" * 65 + "\n")

    # 10. Interactive Visualization
    if args.visualize:
        import open3d as o3d
        logger.info("Opening Open3D interactive visualization window...")
        final_mesh.compute_vertex_normals()
        o3d.visualization.draw_geometries(
            [final_mesh],
            window_name=f"SIH26158 3D Mesh - {args.name}",
            width=1280,
            height=720,
            mesh_show_wireframe=False,
            mesh_show_back_face=True,
        )


if __name__ == "__main__":
    main()
