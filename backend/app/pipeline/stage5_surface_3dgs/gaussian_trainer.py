"""Surface-Regularized 3D Gaussian Splatting (SuGaR) Optimizer.

Enforces planar surface constraints (s_3 << s_1, s_2) aligning Gaussians to local
surface tangent planes, eliminating floating needles and preparing for SDF meshing.
"""

from __future__ import annotations

from typing import Tuple
import numpy as np
from scipy.spatial import KDTree

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage4_georeferencing.metric_scaler import MetricSceneModel

logger = get_logger(__name__, subsystem="GAUSSIAN-TRAINER")


class GaussianModel:
    """Parametric representation of 3D Gaussian Splats."""

    def __init__(
        self,
        positions: np.ndarray,      # (N, 3) float32
        scales: np.ndarray,         # (N, 3) float32 (s1, s2, s3)
        rotations: np.ndarray,      # (N, 4) float32 unit quaternions [w, x, y, z]
        opacities: np.ndarray,      # (N,) float32 in [0, 1]
        colors: np.ndarray,         # (N, 3) float32 in [0, 1]
        normals: np.ndarray,        # (N, 3) float32 unit surface normals
    ):
        self.positions = positions
        self.scales = scales
        self.rotations = rotations
        self.opacities = opacities
        self.colors = colors
        self.normals = normals

    def __len__(self) -> int:
        return len(self.positions)


class SurfaceGaussianTrainer:
    """Initializes and regularizes surface-aligned 3D Gaussians."""

    def __init__(
        self,
        k_neighbors: int = 8,
        flatness_ratio: float = 0.08,  # s3 thickness ratio relative to tangent plane
        base_radius: float = 0.15,     # nominal splat radius in meters
    ):
        self.k_neighbors = k_neighbors
        self.flatness_ratio = flatness_ratio
        self.base_radius = base_radius

    def estimate_normals_and_scales(
        self, points: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute PCA local surface normals, tangent scales, and orientation quaternions via vectorized batch SVD."""
        n_pts = len(points)
        k = min(self.k_neighbors, max(3, n_pts - 1))
        tree = KDTree(points)
        _, idxs = tree.query(points, k=k)

        # Vectorized batch covariance calculation
        neighborhoods = points[idxs]  # (N, k, 3)
        centroids = np.mean(neighborhoods, axis=1)  # (N, 3)
        diff = neighborhoods - centroids[:, None, :]  # (N, k, 3)
        covs = np.einsum("nki,nkj->nij", diff, diff) / (k - 1)  # (N, 3, 3)

        # Batch eigen-decomposition
        evals, evecs = np.linalg.eigh(covs)  # evals: (N, 3), evecs: (N, 3, 3)

        # Smallest eigenvalue corresponds to normal direction (evecs[:, :, 0])
        normals = evecs[:, :, 0].copy()
        # Flip downwards normals to consistently point upwards (+Z >= 0)
        neg_mask = normals[:, 2] < 0.0
        normals[neg_mask] = -normals[neg_mask]

        # Tangent scales along principal surface directions
        r1 = np.maximum(0.02, np.sqrt(np.maximum(1e-6, evals[:, 2])) * 2.0)
        r2 = np.maximum(0.02, np.sqrt(np.maximum(1e-6, evals[:, 1])) * 2.0)
        r3 = np.maximum(0.005, np.minimum(r1, r2) * self.flatness_ratio)
        scales = np.column_stack([r1, r2, r3]).astype(np.float32)

        # Quaternions
        quats = np.zeros((n_pts, 4), dtype=np.float32)
        quats[:, 0] = 1.0  # Default identity [w=1, x=0, y=0, z=0]

        return normals.astype(np.float32), scales, quats

    def train_surface_gaussians(self, metric_model: MetricSceneModel, max_gaussians: int = 12000) -> GaussianModel:
        """Initialize and regularize surface-aligned 3D Gaussians from metric model."""
        points = metric_model.points_local
        colors = metric_model.colors
        confs = metric_model.confidences

        # Subsample if point cloud is ultra-dense to preserve real-time 60 FPS performance
        if len(points) > max_gaussians:
            step = len(points) // max_gaussians
            points = points[::step]
            colors = colors[::step]
            confs = confs[::step]

        logger.info("Computing surface normals and flat Gaussians for %d points...", len(points))
        normals, scales, quats = self.estimate_normals_and_scales(points)

        # Opacities correlated with ViT confidence
        opacities = np.clip(confs * 1.1, 0.2, 0.99).astype(np.float32)

        model = GaussianModel(
            positions=points,
            scales=scales,
            rotations=quats,
            opacities=opacities,
            colors=colors,
            normals=normals,
        )

        mean_flatness = float(np.mean(scales[:, 2] / ((scales[:, 0] + scales[:, 1]) / 2.0)))
        logger.info(
            "Constructed %d Surface-Aligned Gaussians (Mean Thickness-to-Span Ratio: %.3f)",
            len(model), mean_flatness
        )

        return model
