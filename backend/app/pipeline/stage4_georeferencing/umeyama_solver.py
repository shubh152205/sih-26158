"""Closed-Form Weighted Umeyama Sim(3) Alignment Algorithm.

Solves the optimal 7-DoF Similarity Transformation (Scale s, Rotation R in SO(3),
and Translation t in R^3) aligning relative photogrammetric camera centers to absolute
metric WGS84 UTM coordinates, weighted by GNSS Dilution of Precision (DOP).
"""

from __future__ import annotations

import numpy as np

from backend.app.core.exceptions import GeoreferencingError
from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="UMEYAMA-SIM3")


class Sim3Transform:
    """7-DoF Similarity Transformation parameters."""

    def __init__(
        self,
        scale: float,
        rotation: np.ndarray,
        translation: np.ndarray,
        rmse_meters: float,
    ):
        self.scale = float(scale)
        self.rotation = rotation  # (3, 3) in SO(3)
        self.translation = translation  # (3,)
        self.rmse_meters = float(rmse_meters)

    def transform_points(self, points: np.ndarray) -> np.ndarray:
        """Apply Sim(3) transformation: P_target = s * R * P_source + t."""
        # points: (N, 3)
        return self.scale * (self.rotation @ points.T).T + self.translation

    def inverse(self) -> "Sim3Transform":
        """Compute the inverse Sim(3) transformation."""
        inv_scale = 1.0 / self.scale
        inv_rot = self.rotation.T
        inv_trans = -inv_scale * (inv_rot @ self.translation)
        return Sim3Transform(inv_scale, inv_rot, inv_trans, self.rmse_meters * inv_scale)


def solve_weighted_umeyama_sim3(
    source_pts: np.ndarray,
    target_pts: np.ndarray,
    weights: np.ndarray | None = None,
) -> Sim3Transform:
    """Compute closed-form weighted Umeyama Sim(3) alignment.

    Args:
        source_pts: (N, 3) relative photogrammetric camera centers.
        target_pts: (N, 3) absolute metric UTM camera coordinates.
        weights: Optional (N,) weights w_i = 1 / (DOP_i^2).

    Returns:
        Sim3Transform object containing optimal (s, R, t, rmse).
    """
    n_pts = len(source_pts)
    if n_pts < 3:
        raise GeoreferencingError(
            f"Umeyama Sim(3) solver requires at least 3 camera correspondences (got {n_pts})"
        )

    if source_pts.shape != target_pts.shape:
        raise GeoreferencingError(
            f"Dimension mismatch: source {source_pts.shape} vs target {target_pts.shape}"
        )

    # Normalize weights: sum(w_i) = 1.0
    if weights is None:
        w = np.ones(n_pts, dtype=np.float64) / n_pts
    else:
        w_raw = np.asarray(weights, dtype=np.float64).flatten()
        w_sum = np.sum(w_raw)
        if w_sum <= 1e-9:
            w = np.ones(n_pts, dtype=np.float64) / n_pts
        else:
            w = w_raw / w_sum

    # 1. Weighted Centroids
    mu_x = np.sum(source_pts * w[:, None], axis=0)
    mu_y = np.sum(target_pts * w[:, None], axis=0)

    # 2. Centered coordinates
    x_centered = source_pts - mu_x
    y_centered = target_pts - mu_y

    # 3. Variance of source points: sigma_x^2 = sum(w_i * ||x_i||^2)
    var_x = float(np.sum(w * np.sum(x_centered**2, axis=1)))
    if var_x < 1e-7:
        raise GeoreferencingError("Degenerate source trajectory: points are collinear or identical")

    # 4. Weighted Cross-Covariance Matrix: Sigma_xy = sum(w_i * y_i * x_i^T)
    # Shape: (3, 3)
    sigma_xy = (y_centered * w[:, None]).T @ x_centered

    # 5. Singular Value Decomposition: Sigma_xy = U * D * V^T
    u, d, vt = np.linalg.svd(sigma_xy)
    v = vt.T

    # Reflection check: det(U * V^T)
    det_uv = np.linalg.det(u @ v.T)
    s_matrix = np.eye(3, dtype=np.float64)
    s_matrix[2, 2] = 1.0 if det_uv >= 0 else -1.0

    # 6. Optimal Rotation matrix in SO(3)
    r = u @ s_matrix @ v.T

    # 7. Optimal Scale factor: s = Tr(D * S) / sigma_x^2
    scale = float(np.sum(d * np.diag(s_matrix)) / var_x)
    if scale <= 1e-6:
        raise GeoreferencingError(f"Estimated Sim(3) scale factor is non-positive or near-zero: {scale:.6f}")

    # 8. Optimal Translation vector: t = mu_y - s * R * mu_x
    t = mu_y - scale * (r @ mu_x)

    # 9. Alignment residuals and weighted RMSE
    target_pred = scale * (r @ source_pts.T).T + t
    residuals = np.linalg.norm(target_pred - target_pts, axis=1)
    rmse = float(np.sqrt(np.sum(w * (residuals**2))))

    logger.info(
        "Sim(3) Solved: Scale = %.4f, RMSE = %.3fm across %d cameras",
        scale, rmse, n_pts
    )

    return Sim3Transform(scale=scale, rotation=r, translation=t, rmse_meters=rmse)
