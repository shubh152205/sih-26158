"""Unit tests for Stage 3 (Foundation Pose & Kabsch) and Stage 4 (Umeyama Sim(3) Georeferencing)."""

import math
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from backend.app.pipeline.stage3_foundation_pose.kabsch_svd import solve_kabsch_rigid
from backend.app.pipeline.stage3_foundation_pose.view_graph import (
    RelativeCameraPose,
    RelativePoseResult,
    ViewGraphBuilder,
)
from backend.app.pipeline.stage3_foundation_pose.vit_model import ViTPointmapModel
from backend.app.pipeline.stage4_georeferencing.metric_scaler import MetricScaler
from backend.app.pipeline.stage4_georeferencing.umeyama_solver import solve_weighted_umeyama_sim3


class TestKabschSVD:
    def test_exact_rigid_recovery(self):
        # 10 random 3D points
        np.random.seed(42)
        p_src = np.random.uniform(-10.0, 10.0, (10, 3))

        # Ground truth rotation (35 deg around [1, 2, 3] axis)
        rot_axis = np.array([1.0, 2.0, 3.0])
        rot_axis = rot_axis / np.linalg.norm(rot_axis)
        r_gt = Rotation.from_rotvec(rot_axis * math.radians(35.0)).as_matrix()
        t_gt = np.array([15.5, -8.2, 4.3])

        # Target points
        q_tgt = (r_gt @ p_src.T).T + t_gt

        # Solve Kabsch
        r_rec, t_rec, rmse = solve_kabsch_rigid(p_src, q_tgt)

        # Verify exact recovery
        assert math.isclose(rmse, 0.0, abs_tol=1e-6)
        assert math.isclose(np.linalg.det(r_rec), 1.0, abs_tol=1e-6)
        np.testing.assert_allclose(r_rec, r_gt, atol=1e-5)
        np.testing.assert_allclose(t_rec, t_gt, atol=1e-5)

    def test_reflection_prevention(self):
        # Enforce that det(R) is always +1, never -1 (no mirroring)
        p_src = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 1.0, 1.0]])
        # Mirror along Z
        q_tgt = p_src.copy()
        q_tgt[:, 2] = -q_tgt[:, 2]

        r_rec, t_rec, rmse = solve_kabsch_rigid(p_src, q_tgt)
        assert math.isclose(np.linalg.det(r_rec), 1.0, abs_tol=1e-6)


class TestUmeyamaSim3:
    def test_exact_sim3_recovery(self):
        # Generate flight path in relative coordinates
        np.random.seed(123)
        source_pts = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.2, 0.1],
            [2.0, 0.5, 0.3],
            [3.0, 0.8, 0.4],
            [4.0, 1.2, 0.6],
        ], dtype=np.float64)

        scale_gt = 25.4  # Metric scale factor
        r_gt = Rotation.from_euler("z", 45.0, degrees=True).as_matrix()
        t_gt = np.array([717000.0, 3166000.0, 200.0])  # UTM coordinates

        # Transform to target UTM coordinates
        target_pts = scale_gt * (r_gt @ source_pts.T).T + t_gt

        # Solve Umeyama
        transform = solve_weighted_umeyama_sim3(source_pts, target_pts)

        assert math.isclose(transform.scale, scale_gt, rel_tol=1e-4)
        assert math.isclose(transform.rmse_meters, 0.0, abs_tol=1e-4)
        np.testing.assert_allclose(transform.rotation, r_gt, atol=1e-4)
        np.testing.assert_allclose(transform.translation, t_gt, atol=1e-3)

    def test_dop_weighting(self):
        source_pts = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=np.float64)
        target_pts = 10.0 * source_pts.copy()

        # Inject huge outlier into point 2
        target_pts[2] += np.array([0.0, 100.0, 0.0])

        # Assign high DOP (poor accuracy -> low weight) to point 2
        dops = np.array([1.0, 1.0, 100.0, 1.0])
        weights = 1.0 / (dops**2)

        transform = solve_weighted_umeyama_sim3(source_pts, target_pts, weights=weights)
        # Scale should still be close to 10.0 because the outlier was downweighted by 10,000x
        assert 9.0 < transform.scale < 11.0


class TestMetricScaler:
    def test_metric_scene_scaling(self):
        cam_poses = [
            RelativeCameraPose(frame_idx=0, r_c2w=np.eye(3), center=np.array([0.0, 0.0, 0.0])),
            RelativeCameraPose(frame_idx=1, r_c2w=np.eye(3), center=np.array([1.0, 0.0, 0.0])),
            RelativeCameraPose(frame_idx=2, r_c2w=np.eye(3), center=np.array([2.0, 0.0, 0.0])),
        ]
        pts3d = np.array([[0.0, 0.0, 5.0], [1.0, 0.0, 5.0], [2.0, 0.0, 5.0]])
        colors = np.ones((3, 3), dtype=np.float32)
        confs = np.array([0.9, 0.9, 0.9], dtype=np.float32)

        from backend.app.pipeline.stage3_foundation_pose.view_graph import RelativeReconstruction
        recon = RelativeReconstruction(cam_poses, pts3d, colors, confs)

        from backend.app.pipeline.stage4_georeferencing.umeyama_solver import Sim3Transform
        sim3 = Sim3Transform(
            scale=10.0,
            rotation=np.eye(3),
            translation=np.array([500000.0, 3000000.0, 100.0]),
            rmse_meters=0.01,
        )

        model = MetricScaler.scale_scene(recon, sim3)
        assert len(model.points_local) == 3
        # Anchor origin is near the center of cameras
        assert model.anchor_origin[0] > 499990.0
        # Local coordinates should be small numbers in meters centered near 0
        assert np.max(np.abs(model.points_local)) < 100.0
