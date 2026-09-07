"""Georeferenced Point Cloud Exporter Subsystem.

Exports dense 3D point clouds in ASPRS LAS 1.4 (.las) and Stanford PLY (.ply)
formats with UTM geospatial CRS coordinates, RGB radiometric colors, and confidence intensities.
"""

from __future__ import annotations

from pathlib import Path
import laspy
import numpy as np

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage4_georeferencing.metric_scaler import MetricSceneModel

logger = get_logger(__name__, subsystem="POINTCLOUD-EXPORTER")


class PointCloudExporter:
    """Exports metric 3D point clouds to ASPRS LAS and PLY formats."""

    @classmethod
    def export_las(
        cls,
        model: MetricSceneModel,
        output_path: str | Path,
        epsg_code: int = 32643,
    ) -> Path:
        """Export point cloud to ASPRS LAS 1.4 format with UTM coordinates."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        pts_utm = model.points_utm
        colors_rgb = model.colors
        confs = model.confidences

        # Create LAS 1.4 header (Point format 2: X, Y, Z, Intensity, Return, RGB)
        header = laspy.LasHeader(point_format=2, version="1.4")
        header.offsets = np.min(pts_utm, axis=0)
        header.scales = [0.001, 0.001, 0.001]  # Millimeter precision

        las = laspy.LasData(header)
        las.x = pts_utm[:, 0]
        las.y = pts_utm[:, 1]
        las.z = pts_utm[:, 2]

        # Map colors (16-bit uint)
        las.red = np.clip(colors_rgb[:, 0] * 65535.0, 0, 65535).astype(np.uint16)
        las.green = np.clip(colors_rgb[:, 1] * 65535.0, 0, 65535).astype(np.uint16)
        las.blue = np.clip(colors_rgb[:, 2] * 65535.0, 0, 65535).astype(np.uint16)

        # Map confidence to intensity (uint16)
        las.intensity = np.clip(confs * 65535.0, 0, 65535).astype(np.uint16)

        las.write(str(out))
        logger.info("Exported ASPRS LAS 1.4 point cloud (%d points) to %s", len(pts_utm), str(out))
        return out

    @classmethod
    def export_ply(cls, model: MetricSceneModel, output_path: str | Path) -> Path:
        """Export local point cloud in binary Stanford PLY format."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        pts = model.points_local
        colors = (np.clip(model.colors * 255.0, 0, 255)).astype(np.uint8)
        confs = model.confidences.astype(np.float32)

        header = (
            "ply\n"
            "format binary_little_endian 1.0\n"
            f"element vertex {len(pts)}\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
            "property uchar red\n"
            "property uchar green\n"
            "property uchar blue\n"
            "property float confidence\n"
            "end_header\n"
        )

        with open(out, "wb") as f:
            f.write(header.encode("ascii"))
            # Pack structured binary array
            dt = np.dtype([
                ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                ("red", "u1"), ("green", "u1"), ("blue", "u1"),
                ("confidence", "<f4"),
            ])
            data = np.empty(len(pts), dtype=dt)
            data["x"] = pts[:, 0]
            data["y"] = pts[:, 1]
            data["z"] = pts[:, 2]
            data["red"] = colors[:, 0]
            data["green"] = colors[:, 1]
            data["blue"] = colors[:, 2]
            data["confidence"] = confs

            f.write(data.tobytes())

        logger.info("Exported binary PLY point cloud (%d points) to %s", len(pts), str(out))
        return out
