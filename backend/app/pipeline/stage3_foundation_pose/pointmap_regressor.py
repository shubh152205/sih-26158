"""Dense Pointmap Regressor and Relative Pose Estimator.

Extracts dense 3D pointmaps, filters mutual correspondences by confidence,
and executes closed-form Kabsch SVD to determine pairwise relative camera extrinsics.
"""

from __future__ import annotations

from typing import Tuple
import numpy as np

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage2_keyframing.keyframe_selector import SelectedKeyframe
from backend.app.pipeline.stage3_foundation_pose.kabsch_svd import solve_kabsch_rigid
from backend.app.pipeline.stage3_foundation_pose.vit_model import PointmapOutput, ViTPointmapModel

logger = get_logger(__name__, subsystem="POINTMAP-REGRESSOR")


class RelativePoseResult:
    """Estimated relative pose and correspondence set between two keyframes."""

    def __init__(
        self,
        frame_idx_i: int,
        frame_idx_j: int,
        r_rel: np.ndarray,
        t_rel: np.ndarray,
        rmse: float,
        pts3d_cam_i: np.ndarray,
        colors: np.ndarray,
        confidences: np.ndarray,
    ):
        self.frame_idx_i = frame_idx_i
        self.frame_idx_j = frame_idx_j
        self.r_rel = r_rel  # (3, 3) SO(3)
        self.t_rel = t_rel  # (3,)
        self.rmse = rmse
        self.pts3d_cam_i = pts3d_cam_i  # (M, 3)
        self.colors = colors  # (M, 3) in [0, 1]
        self.confidences = confidences  # (M,) in [0, 1]


class PointmapRegressor:
    """Pairwise correspondence extractor and relative pose solver."""

    def __init__(self, vit_model: ViTPointmapModel, min_confidence: float = 0.35):
        self.vit = vit_model
        self.min_confidence = min_confidence

    def estimate_relative_pose(
        self,
        kf_i: SelectedKeyframe,
        kf_j: SelectedKeyframe,
        img_i: np.ndarray,
        img_j: np.ndarray,
    ) -> RelativePoseResult:
        """Estimate relative camera transform (R_ij, t_ij) mapping frame i to frame j."""
        # Baseline distance from synchronous telemetry
        dx = kf_j.pose.utm_easting - kf_i.pose.utm_easting
        dy = kf_j.pose.utm_northing - kf_i.pose.utm_northing
        dz = kf_j.pose.utm_altitude - kf_i.pose.utm_altitude
        baseline_m = float(np.hypot(np.hypot(dx, dy), dz))
        baseline_m = max(1.0, baseline_m)

        # Infer dense pointmaps
        output = self.vit.infer_pair(img_i, img_j, baseline_meters=baseline_m)

        # Mask high-confidence points in both views
        conf_mask = (output.conf1 >= self.min_confidence) & (output.conf2 >= self.min_confidence)
        if np.sum(conf_mask) < 20:
            # Relax confidence if scene has low texture
            conf_mask = output.conf1 >= (self.min_confidence * 0.5)

        # Subsample points for robust SVD (up to 2000 points)
        y_coords, x_coords = np.where(conf_mask)
        n_candidates = len(x_coords)

        if n_candidates > 2000:
            step = n_candidates // 2000
            y_coords = y_coords[::step]
            x_coords = x_coords[::step]

        p_source = output.pts1[y_coords, x_coords]
        q_target = output.pts2_in_cam1[y_coords, x_coords]
        weights = output.conf1[y_coords, x_coords]

        # Solve closed-form Kabsch SVD for relative rotation and translation
        r_rel, t_rel, rmse = solve_kabsch_rigid(p_source, q_target, weights=weights)

        # Extract RGB colors for 3D point cloud
        rgb_norm = img_i.astype(np.float32) / 255.0
        colors = rgb_norm[y_coords, x_coords]

        logger.debug(
            "Pair (%d, %d): Kabsch SVD aligned %d points with RMSE = %.3fm",
            kf_i.keyframe_idx, kf_j.keyframe_idx, len(p_source), rmse
        )

        return RelativePoseResult(
            frame_idx_i=kf_i.keyframe_idx,
            frame_idx_j=kf_j.keyframe_idx,
            r_rel=r_rel,
            t_rel=t_rel,
            rmse=rmse,
            pts3d_cam_i=p_source,
            colors=colors,
            confidences=weights,
        )
