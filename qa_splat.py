#!/usr/bin/env python3
"""qa_splat.py

Post-Training Quality Assurance & Sanity Check Script for 3D Gaussian Splats.
Loads the exported PLY (using plyfile, Open3D, or native fallback) and verifies:
1. Total number of Gaussians
2. Spatial 3D Bounding Box and scene span (meters)
3. Centroid and floater / sky outlier ratio (Z-score analysis)
4. Scale and opacity distribution
5. Total file size on disk

Usage:
    python backend/qa_splat.py --input ./exports/splat.ply
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SPLAT-QA] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SPLAT-QA")


def format_size(bytes_size: int) -> str:
    """Formats raw byte count into human-readable string."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


def load_gaussian_ply(ply_path: Path) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """Loads 3D positions (N, 3), opacities (N,), and scales (N, 3) from a Gaussian Splat PLY.

    Tries plyfile -> Open3D -> native parser.
    """
    # 1. Attempt plyfile (Standard for 3DGS attributes)
    try:
        from plyfile import PlyData
        logger.info("Loading PLY via plyfile...")
        plydata = PlyData.read(str(ply_path))
        vertex = plydata["vertex"]
        x = np.asarray(vertex["x"])
        y = np.asarray(vertex["y"])
        z = np.asarray(vertex["z"])
        positions = np.column_stack([x, y, z])

        # Opacities
        opacities = None
        if "opacity" in vertex:
            raw_opacity = np.asarray(vertex["opacity"])
            # In 3DGS PLY, opacity is stored as logit: sigmoid(raw) = 1 / (1 + exp(-raw))
            opacities = 1.0 / (1.0 + np.exp(-np.clip(raw_opacity, -20.0, 20.0)))

        # Scales
        scales = None
        if "scale_0" in vertex and "scale_1" in vertex and "scale_2" in vertex:
            raw_s0 = np.asarray(vertex["scale_0"])
            raw_s1 = np.asarray(vertex["scale_1"])
            raw_s2 = np.asarray(vertex["scale_2"])
            # Scales stored as log(scale): exp(raw)
            scales = np.exp(np.column_stack([raw_s0, raw_s1, raw_s2]))

        return positions, opacities, scales
    except ImportError:
        pass
    except Exception as err:
        logger.debug("plyfile failed (%s); trying alternative loaders.", err)

    # 2. Attempt Open3D
    try:
        import open3d as o3d
        logger.info("Loading PLY via Open3D...")
        pcd = o3d.io.read_point_cloud(str(ply_path))
        positions = np.asarray(pcd.points)
        if len(positions) > 0:
            return positions, None, None
    except ImportError:
        pass
    except Exception as err:
        logger.debug("Open3D failed (%s); trying fallback parser.", err)

    # 3. Fallback binary/ascii header scanner
    logger.info("Using native binary PLY reader fallback...")
    positions = read_ply_positions_fallback(ply_path)
    return positions, None, None


def read_ply_positions_fallback(ply_path: Path) -> np.ndarray:
    """Reads XYZ positions directly from standard binary PLY vertex elements."""
    with open(ply_path, "rb") as f:
        # Read header
        header_lines = []
        num_vertices = 0
        properties = []
        is_binary = False

        while True:
            line = f.readline().decode("ascii", errors="ignore").strip()
            header_lines.append(line)
            if line.startswith("format binary"):
                is_binary = True
            elif line.startswith("element vertex"):
                num_vertices = int(line.split()[-1])
            elif line.startswith("property"):
                parts = line.split()
                properties.append((parts[1], parts[2]))
            elif line == "end_header":
                break

        if not is_binary or num_vertices == 0:
            raise ValueError(f"Could not parse binary vertices from PLY header in {ply_path}")

        # Build numpy dtype for structured vertex record
        type_map = {
            "float": "f4", "float32": "f4", "double": "f8", "float64": "f8",
            "uchar": "u1", "uint8": "u1", "int": "i4", "int32": "i4"
        }
        dt_list = []
        for ptype, pname in properties:
            dt_list.append((pname, type_map.get(ptype, "f4")))

        dt = np.dtype(dt_list)
        vertex_data = np.fromfile(f, dtype=dt, count=num_vertices)
        return np.column_stack([vertex_data["x"], vertex_data["y"], vertex_data["z"]])


def run_quality_check(
    ply_path: Path,
    max_expected_span_meters: float = 1000.0,
    min_expected_gaussians: int = 10000,
) -> bool:
    """Performs comprehensive drone 3DGS quality assurance check."""
    if not ply_path.is_file():
        logger.error("PLY file does not exist: %s", ply_path)
        return False

    file_size_bytes = ply_path.stat().st_size
    file_size_str = format_size(file_size_bytes)

    # Load geometry
    try:
        positions, opacities, scales = load_gaussian_ply(ply_path)
    except Exception as err:
        logger.error("Failed to parse PLY file: %s", err)
        return False

    num_gaussians = len(positions)
    if num_gaussians == 0:
        logger.error("PLY contains 0 Gaussian elements! Training likely failed or produced degenerate output.")
        return False

    # Bounding Box
    min_xyz = np.min(positions, axis=0)
    max_xyz = np.max(positions, axis=0)
    spans = max_xyz - min_xyz
    diag_span = float(np.linalg.norm(spans))
    centroid = np.mean(positions, axis=0)

    # Floater / Outlier Analysis (Z-score test)
    dists_from_center = np.linalg.norm(positions - centroid, axis=1)
    mean_dist = float(np.mean(dists_from_center))
    std_dist = float(np.std(dists_from_center))
    outlier_threshold = mean_dist + 3.5 * std_dist
    outlier_count = int(np.sum(dists_from_center > outlier_threshold))
    outlier_pct = (outlier_count / num_gaussians) * 100.0

    # Output Clean QA Report
    print("\n" + "=" * 65)
    print("        SIH26158 3D GAUSSIAN SPLATTING QA AUDIT REPORT        ")
    print("=" * 65)
    print(f"File Path:              {ply_path.resolve()}")
    print(f"File Size on Disk:      {file_size_str} ({file_size_bytes:,} bytes)")
    print(f"Total Gaussian Splats:  {num_gaussians:,}")
    print("-" * 65)
    print("SPATIAL BOUNDS & COORDINATE EXTENTS:")
    print(f"  X Range:              [{min_xyz[0]:+9.3f} m  -->  {max_xyz[0]:+9.3f} m] (Span: {spans[0]:7.2f} m)")
    print(f"  Y Range:              [{min_xyz[1]:+9.3f} m  -->  {max_xyz[1]:+9.3f} m] (Span: {spans[1]:7.2f} m)")
    print(f"  Z Range (Height):     [{min_xyz[2]:+9.3f} m  -->  {max_xyz[2]:+9.3f} m] (Span: {spans[2]:7.2f} m)")
    print(f"  Bounding Box Diagonal:{diag_span:8.2f} meters")
    print(f"  Scene Centroid:       [{centroid[0]:+7.2f}, {centroid[1]:+7.2f}, {centroid[2]:+7.2f}]")
    print("-" * 65)
    print("ANOMALY & FLOATER DETECTION:")
    print(f"  Mean Point Distance:  {mean_dist:7.2f} m  (Std Dev: {std_dist:7.2f} m)")
    print(f"  Floaters (>3.5 std):  {outlier_count:,} Gaussians ({outlier_pct:.2f}%)")

    if opacities is not None:
        mean_opacity = float(np.mean(opacities))
        dense_splats = int(np.sum(opacities > 0.5))
        print(f"  Mean Opacity:         {mean_opacity:.3f}")
        print(f"  Solid Splats (α>0.5): {dense_splats:,} ({(dense_splats / num_gaussians) * 100.0:.1f}%)")

    if scales is not None:
        mean_scale = np.mean(scales, axis=0)
        print(f"  Mean Scales [s1,s2,s3]: [{mean_scale[0]:.3f}, {mean_scale[1]:.3f}, {mean_scale[2]:.3f}] m")

    print("-" * 65)

    # Sanity checks & Verdict
    warnings = []
    if num_gaussians < min_expected_gaussians:
        warnings.append(f"Low Gaussian count ({num_gaussians:,} < {min_expected_gaussians:,}). Scene may be sparse.")
    if diag_span > max_expected_span_meters:
        warnings.append(f"Extremely large bounding box ({diag_span:.1f}m > {max_expected_span_meters:.1f}m). Probable sky floaters.")
    if outlier_pct > 2.0:
        warnings.append(f"High floater percentage ({outlier_pct:.2f}%). Recommend pruning floaters or tightening cull-alpha-thresh.")

    if not warnings:
        print("FINAL SANITY CHECK:  \033[92m[PASSED - READY FOR DEMO DAY]\033[0m")
        print("=" * 65 + "\n")
        return True
    else:
        print("FINAL SANITY CHECK:  \033[93m[WARNINGS DETECTED]\033[0m")
        for w in warnings:
            print(f"  ! {w}")
        print("=" * 65 + "\n")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="3D Gaussian Splatting Quality Assurance (QA) Sanity Checker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to exported Gaussian Splat .ply file")
    parser.add_argument("--max-span", type=float, default=800.0, help="Maximum expected scene diagonal in meters")
    parser.add_argument("--min-gaussians", type=int, default=15000, help="Minimum expected Gaussian count")
    args = parser.parse_args()

    run_quality_check(
        ply_path=Path(args.input),
        max_expected_span_meters=args.max_span,
        min_expected_gaussians=args.min_gaussians,
    )


if __name__ == "__main__":
    main()
