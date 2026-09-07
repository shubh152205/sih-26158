"""Metric Scaling and Local Frame Anchoring Subsystem.

Transforms dense relative pointmaps to absolute metric WGS84 UTM space (1 unit = 1 meter)
and anchors coordinates to a local origin to maintain float32 numerical precision in WebGL.
"""

from __future__ import annotations

import numpy as np

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage3_foundation_pose.view_graph import RelativeReconstruction
from backend.app.pipeline.stage4_georeferencing.umeyama_solver import Sim3Transform

logger = get_logger(__name__, subsystem="METRIC-SCALER")


class MetricSceneModel:
    """Metric georeferenced point cloud with local visualization coordinates."""

    def __init__(
        self,
        points_local: np.ndarray,
        points_utm: np.ndarray,
        colors: np.ndarray,
        confidences: np.ndarray,
        anchor_origin: np.ndarray,
        bounding_box_meters: dict[str, float],
        camera_centers_local: np.ndarray,
    ):
        self.points_local = points_local  # (N, 3) float32 centered at anchor (meters)
        self.points_utm = points_utm      # (N, 3) float64 absolute UTM (meters)
        self.colors = colors              # (N, 3) float32 in [0, 1]
        self.confidences = confidences    # (N,) float32 in [0, 1]
        self.anchor_origin = anchor_origin  # (3,) [Easting, Northing, Altitude]
        self.bounding_box_meters = bounding_box_meters
        self.camera_centers_local = camera_centers_local  # (K, 3) float32


class MetricScaler:
    """Transforms and normalizes photogrammetric pointmaps into metric coordinates."""

    @classmethod
    def scale_scene(
        cls,
        relative_recon: RelativeReconstruction,
        sim3_transform: Sim3Transform,
    ) -> MetricSceneModel:
        """Apply Sim(3) transformation and compute local origin anchor."""
        # 1. Transform all relative points to absolute metric UTM coordinates
        # P_utm = s * R * P_rel + t
        pts_rel = relative_recon.points3d
        pts_utm = sim3_transform.transform_points(pts_rel)

        # 2. Transform camera centers to UTM
        cam_centers_utm = sim3_transform.transform_points(relative_recon.camera_centers)

        # 3. Establish anchor origin from centroid of camera trajectory
        anchor_origin = np.mean(cam_centers_utm, axis=0)

        # 4. Subtract anchor origin for numerical stability in WebGL (float32)
        pts_local = (pts_utm - anchor_origin).astype(np.float32)
        cam_centers_local = (cam_centers_utm - anchor_origin).astype(np.float32)

        # 5. Compute metric bounding box
        min_xyz = np.min(pts_local, axis=0)
        max_xyz = np.max(pts_local, axis=0)
        bbox = {
            "min_x": float(min_xyz[0]),
            "max_x": float(max_xyz[0]),
            "min_y": float(min_xyz[1]),
            "max_y": float(max_xyz[1]),
            "min_z": float(min_xyz[2]),
            "max_z": float(max_xyz[2]),
            "extent_x_m": float(max_xyz[0] - min_xyz[0]),
            "extent_y_m": float(max_xyz[1] - min_xyz[1]),
            "extent_z_m": float(max_xyz[2] - min_xyz[2]),
        }

        logger.info(
            "Metric Scene Scaled: %d points. Extents: X=%.1fm, Y=%.1fm, Z=%.1fm (Anchor: E=%.1f, N=%.1f)",
            len(pts_local), bbox["extent_x_m"], bbox["extent_y_m"], bbox["extent_z_m"],
            anchor_origin[0], anchor_origin[1]
        )

        return MetricSceneModel(
            points_local=pts_local,
            points_utm=pts_utm,
            colors=relative_recon.colors,
            confidences=relative_recon.confidences,
            anchor_origin=anchor_origin,
            bounding_box_meters=bbox,
            camera_centers_local=cam_centers_local,
        )
