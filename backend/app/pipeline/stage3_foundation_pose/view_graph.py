"""View Graph Trajectory Assembly and Gauge Fixing Subsystem.

Chains pairwise relative camera transformations along the sequential UAV flight path
in linear time O(N), assembling a unified relative 3D point cloud without bundle adjustment.
"""

from __future__ import annotations

from typing import List, Sequence
import numpy as np

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage3_foundation_pose.pointmap_regressor import RelativePoseResult

logger = get_logger(__name__, subsystem="VIEW-GRAPH")


class RelativeCameraPose:
    """Relative camera pose in camera 0's reference frame."""

    def __init__(self, frame_idx: int, r_c2w: np.ndarray, center: np.ndarray):
        self.frame_idx = frame_idx
        self.r_c2w = r_c2w  # (3, 3) rotation from camera frame to relative world frame
        self.center = center  # (3,) camera position in relative world frame


class RelativeReconstruction:
    """Complete relative trajectory and unified sparse/dense point cloud."""

    def __init__(
        self,
        camera_poses: list[RelativeCameraPose],
        points3d: np.ndarray,
        colors: np.ndarray,
        confidences: np.ndarray,
    ):
        self.camera_poses = camera_poses
        self.points3d = points3d  # (M, 3) float64
        self.colors = colors      # (M, 3) float32 in [0, 1]
        self.confidences = confidences  # (M,) float32 in [0, 1]

    @property
    def camera_centers(self) -> np.ndarray:
        """Return (N, 3) array of relative camera center positions."""
        return np.array([pose.center for pose in self.camera_poses], dtype=np.float64)


class ViewGraphBuilder:
    """Chains relative pairwise poses into a unified unscaled trajectory."""

    @classmethod
    def assemble_trajectory(
        cls, pairwise_results: Sequence[RelativePoseResult]
    ) -> RelativeReconstruction:
        """Chain sequential pairwise transformations along the drone flight line."""
        if not pairwise_results:
            raise ValueError("Cannot build trajectory from empty pairwise results")

        camera_poses: list[RelativeCameraPose] = []
        all_pts: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        all_confs: list[np.ndarray] = []

        # Anchor Keyframe 0 at origin: R = Identity, Center = (0, 0, 0)
        curr_r = np.eye(3, dtype=np.float64)
        curr_t = np.zeros(3, dtype=np.float64)

        first_pair = pairwise_results[0]
        camera_poses.append(
            RelativeCameraPose(frame_idx=first_pair.frame_idx_i, r_c2w=curr_r.copy(), center=curr_t.copy())
        )

        # Transform keyframe 0 points
        all_pts.append(first_pair.pts3d_cam_i)
        all_colors.append(first_pair.colors)
        all_confs.append(first_pair.confidences)

        # Incrementally chain each sequential pair
        for pair in pairwise_results:
            # R_{k} = R_{k-1} * R_{rel}
            # t_{k} = t_{k-1} + R_{k-1} * t_{rel}
            next_t = curr_t + curr_r @ pair.t_rel
            next_r = curr_r @ pair.r_rel

            camera_poses.append(
                RelativeCameraPose(frame_idx=pair.frame_idx_j, r_c2w=next_r.copy(), center=next_t.copy())
            )

            # Transform points into global relative frame
            pts_world = (next_r @ pair.pts3d_cam_i.T).T + next_t
            all_pts.append(pts_world)
            all_colors.append(pair.colors)
            all_confs.append(pair.confidences)

            curr_r = next_r
            curr_t = next_t

        combined_pts = np.vstack(all_pts)
        combined_colors = np.vstack(all_colors)
        combined_confs = np.concatenate(all_confs)

        logger.info(
            "Assembled relative trajectory: %d cameras, %d total 3D points",
            len(camera_poses), len(combined_pts)
        )

        return RelativeReconstruction(
            camera_poses=camera_poses,
            points3d=combined_pts,
            colors=combined_colors,
            confidences=combined_confs,
        )
