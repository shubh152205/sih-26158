"""Continuous Cubic B-Spline Temporal Interpolation Subsystem.

Provides continuous, smooth trajectory evaluation over UAV flight timestamps.
Employs quaternion representation for attitude interpolation to eliminate
gimbal lock and boundary wrap-around discontinuities (e.g., crossing 0/360 degrees).
"""

from __future__ import annotations

import math
from typing import List, Sequence
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation, Slerp

from backend.app.core.exceptions import PipelineError
from backend.app.core.logger import get_logger
from backend.app.schemas.telemetry import RawTelemetryPoint, SynchronizedPose

logger = get_logger(__name__, subsystem="SPLINE-INTERP")


def euler_to_quaternion(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """Convert aerospace Euler angles (Roll, Pitch, Yaw in degrees) to unit quaternion [x, y, z, w].
    
    Convention: intrinsic Z-Y-X (Yaw-Pitch-Roll) rotation.
    """
    rot = Rotation.from_euler("zyx", [yaw_deg, pitch_deg, roll_deg], degrees=True)
    return rot.as_quat()  # returns [x, y, z, w]


def quaternion_to_euler(quat: np.ndarray) -> tuple[float, float, float]:
    """Convert unit quaternion [x, y, z, w] to aerospace Euler angles (Roll, Pitch, Yaw in degrees)."""
    norm = np.linalg.norm(quat)
    if norm > 1e-9:
        quat = quat / norm
    else:
        quat = np.array([0.0, 0.0, 0.0, 1.0])
    rot = Rotation.from_quat(quat)
    yaw, pitch, roll = rot.as_euler("zyx", degrees=True)
    return float(roll), float(pitch), float(yaw)


class TrajectorySplineInterpolator:
    """Cubic B-Spline and Spherical Linear Interpolator for drone 6-DoF trajectory."""

    def __init__(
        self,
        timestamps_sec: np.ndarray,
        eastings: np.ndarray,
        northings: np.ndarray,
        altitudes: np.ndarray,
        rolls_deg: np.ndarray,
        pitches_deg: np.ndarray,
        yaws_deg: np.ndarray,
        dops: np.ndarray | None = None,
    ):
        if len(timestamps_sec) < 2:
            raise PipelineError(
                f"Cannot construct spline with fewer than 2 points (got {len(timestamps_sec)})",
                stage="STAGE1_INGESTION",
            )

        # Sort strictly by timestamp and remove duplicate timestamps
        order = np.argsort(timestamps_sec)
        t_sorted = timestamps_sec[order]
        unique_mask = np.concatenate([[True], np.diff(t_sorted) > 1e-6])

        self.t = t_sorted[unique_mask]
        if len(self.t) < 2:
            raise PipelineError(
                "Degenerate timestamps: insufficient unique temporal samples after deduplication",
                stage="STAGE1_INGESTION",
            )

        self.e = eastings[order][unique_mask]
        self.n = northings[order][unique_mask]
        self.a = altitudes[order][unique_mask]
        r = rolls_deg[order][unique_mask]
        p = pitches_deg[order][unique_mask]
        y = yaws_deg[order][unique_mask]

        if dops is not None:
            self.dop = dops[order][unique_mask]
        else:
            self.dop = np.ones_like(self.t)

        self.t_min = float(self.t[0])
        self.t_max = float(self.t[-1])

        # Construct position cubic splines with natural boundary conditions
        self.spline_e = CubicSpline(self.t, self.e, bc_type="natural")
        self.spline_n = CubicSpline(self.t, self.n, bc_type="natural")
        self.spline_a = CubicSpline(self.t, self.a, bc_type="natural")
        self.spline_dop = CubicSpline(self.t, self.dop, bc_type="natural")

        # Convert orientations to continuous unit quaternions
        quats = []
        for i in range(len(self.t)):
            q = euler_to_quaternion(r[i], p[i], y[i])
            # Ensure shortest-path hemisphere continuity (q_i . q_{i-1} >= 0)
            if quats and np.dot(quats[-1], q) < 0.0:
                q = -q
            quats.append(q)
        self.quats = np.array(quats)

        # Slerp requires strictly increasing times
        try:
            self.rotations = Rotation.from_quat(self.quats)
            self.slerp = Slerp(self.t, self.rotations)
            self._has_slerp = True
        except Exception as e:
            logger.warning("Slerp initialization failed (%s); falling back to component splines", str(e))
            self._has_slerp = False
            self.spline_q = CubicSpline(self.t, self.quats, axis=0, bc_type="natural")

    @classmethod
    def from_telemetry_points(
        cls, points: Sequence[RawTelemetryPoint], transformer: Any
    ) -> "TrajectorySplineInterpolator":
        """Factory method constructing interpolator directly from raw telemetry records."""
        lats = np.array([pt.latitude for pt in points], dtype=np.float64)
        lons = np.array([pt.longitude for pt in points], dtype=np.float64)
        alts = np.array([pt.altitude_msl for pt in points], dtype=np.float64)
        ts = np.array([pt.timestamp_ms / 1000.0 for pt in points], dtype=np.float64)
        rolls = np.array([pt.roll for pt in points], dtype=np.float64)
        pitches = np.array([pt.pitch for pt in points], dtype=np.float64)
        yaws = np.array([pt.yaw for pt in points], dtype=np.float64)
        dops = np.array([pt.dop for pt in points], dtype=np.float64)

        # Convert to UTM
        utm_coords = transformer.wgs84_to_utm_batch(lats, lons, alts)
        return cls(
            timestamps_sec=ts,
            eastings=utm_coords[:, 0],
            northings=utm_coords[:, 1],
            altitudes=utm_coords[:, 2],
            rolls_deg=rolls,
            pitches_deg=pitches,
            yaws_deg=yaws,
            dops=dops,
        )

    def evaluate_at_time(self, t_query: float, frame_idx: int = 0) -> SynchronizedPose:
        """Evaluate continuous trajectory state at a specific query time in seconds."""
        # Clamp gracefully to valid time interval
        t_clamped = max(self.t_min, min(self.t_max, t_query))
        is_interp = abs(t_clamped - t_query) > 1e-4 or not any(np.isclose(self.t, t_query, atol=1e-3))

        e = float(self.spline_e(t_clamped))
        n = float(self.spline_n(t_clamped))
        a = float(self.spline_a(t_clamped))
        dop_val = max(0.1, float(self.spline_dop(t_clamped)))

        # SVD weight is inversely proportional to DOP variance
        dop_weight = float(1.0 / (dop_val**2))

        if self._has_slerp:
            rot = self.slerp([t_clamped])
            yaw, pitch, roll = rot.as_euler("zyx", degrees=True)[0]
        else:
            q_interp = self.spline_q(t_clamped)
            roll, pitch, yaw = quaternion_to_euler(q_interp)

        return SynchronizedPose(
            frame_idx=frame_idx,
            timestamp_sec=t_query,
            utm_easting=e,
            utm_northing=n,
            utm_altitude=a,
            roll_deg=float(roll),
            pitch_deg=float(pitch),
            yaw_deg=float(yaw),
            dop_weight=dop_weight,
            is_interpolated=is_interp,
        )

    def evaluate_frames(self, total_frames: int, fps: float) -> list[SynchronizedPose]:
        """Generate synchronized poses for every discrete video frame index."""
        poses: list[SynchronizedPose] = []
        for idx in range(total_frames):
            t_sec = idx / fps
            poses.append(self.evaluate_at_time(t_sec, frame_idx=idx))
        return poses
