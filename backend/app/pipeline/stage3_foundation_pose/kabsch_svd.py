"""Closed-Form Weighted Kabsch SVD Algorithm.

Computes the optimal rigid body transformation (Rotation R in SO(3) and Translation t)
aligning source 3D points P to target 3D points Q with per-point confidence weights.
Guarantees det(R) = +1 to eliminate improper reflections.
"""

from __future__ import annotations

import numpy as np

from backend.app.core.exceptions import PoseEstimationError
from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="KABSCH-SVD")


def solve_kabsch_rigid(
    p_source: np.ndarray,
    q_target: np.ndarray,
    weights: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Solve optimal rigid transformation: Q ~= R * P + t.

    Args:
        p_source: (N, 3) float array of source 3D coordinates.
        q_target: (N, 3) float array of target 3D coordinates.
        weights: Optional (N,) non-negative confidence weights.

    Returns:
        Tuple of:
            - R: (3, 3) rotation matrix in SO(3), det(R) == +1.0
            - t: (3,) translation vector
            - rmse: Root mean square alignment error in meters/units
    """
    if len(p_source) < 3 or len(q_target) < 3:
        raise PoseEstimationError(
            f"Kabsch SVD requires at least 3 non-collinear point correspondences (got {len(p_source)})"
        )

    if p_source.shape != q_target.shape:
        raise PoseEstimationError(
            f"Shape mismatch: source {p_source.shape} vs target {q_target.shape}"
        )

    n_pts = len(p_source)

    # Normalize weights
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
    p_bar = np.sum(p_source * w[:, None], axis=0)
    q_bar = np.sum(q_target * w[:, None], axis=0)

    # 2. Centered coordinates
    x = p_source - p_bar
    y = q_target - q_bar

    # 3. Weighted Cross-Covariance Matrix H = X^T * W * Y
    # Shape: (3, 3)
    h = (x * w[:, None]).T @ y

    # 4. Singular Value Decomposition
    u, s, vt = np.linalg.svd(h)
    v = vt.T

    # 5. Optimal Rotation matrix with reflection correction
    # R = V * diag(1, 1, det(V * U^T)) * U^T
    d = np.linalg.det(v @ u.T)
    s_matrix = np.eye(3, dtype=np.float64)
    s_matrix[2, 2] = 1.0 if d >= 0 else -1.0

    r = v @ s_matrix @ u.T

    # Ensure valid SO(3)
    if np.abs(np.linalg.det(r) - 1.0) > 1e-4:
        raise PoseEstimationError(f"Kabsch rotation failed SO(3) check: det(R) = {np.linalg.det(r):.4f}")

    # 6. Optimal Translation vector
    t = q_bar - r @ p_bar

    # 7. Alignment Residual & RMSE
    p_transformed = (r @ p_source.T).T + t
    residuals = np.linalg.norm(p_transformed - q_target, axis=1)
    weighted_mse = float(np.sum(w * (residuals**2)))
    rmse = float(np.sqrt(max(0.0, weighted_mse)))

    return r, t, rmse
