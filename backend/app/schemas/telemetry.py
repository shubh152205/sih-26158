"""Pydantic data models for drone telemetry and camera trajectories."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class RawTelemetryPoint(BaseModel):
    """Raw parsed record from subtitle (.srt), KLV, or CSV flight log."""

    frame_idx: int = Field(..., description="0-indexed or 1-indexed video frame counter")
    timestamp_ms: float = Field(..., description="Timestamp in milliseconds from video start or epoch")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude in decimal degrees")
    altitude_msl: float = Field(..., description="Altitude above Mean Sea Level in meters")
    altitude_rel: float = Field(default=0.0, description="Relative altitude above ground/takeoff point in meters")
    roll: float = Field(default=0.0, description="UAV roll angle in degrees")
    pitch: float = Field(default=0.0, description="UAV pitch angle in degrees")
    yaw: float = Field(default=0.0, description="UAV yaw/heading angle in degrees")
    dop: float = Field(default=1.0, ge=0.01, description="Dilution of Precision (lower is better; weights Umeyama)")
    focal_length_mm: float | None = Field(default=None, description="Equivalent focal length in millimeters if provided")
    shutter_speed: str | None = Field(default=None, description="Camera shutter speed string")
    iso: int | None = Field(default=None, description="Camera ISO setting")


class SynchronizedPose(BaseModel):
    """Spatially and temporally synchronized camera pose in local metric UTM coordinates.
    
    Coordinate Conventions:
    - UTM Cartesian Frame: +X = East (meters), +Y = North (meters), +Z = Altitude Up (meters)
    - Camera Frame (OpenCV convention): +X = Right, +Y = Down, +Z = Optical Axis (Forward)
    - Camera Rotation: 3x3 rotation matrix R_c2w aligning camera optical frame to world frame
    """

    frame_idx: int
    timestamp_sec: float
    utm_easting: float = Field(..., description="Local or global UTM Easting in meters")
    utm_northing: float = Field(..., description="Local or global UTM Northing in meters")
    utm_altitude: float = Field(..., description="Metric altitude (Z-up) in meters")
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    dop_weight: float = Field(default=1.0, description="Normalized Umeyama SVD weight w_i = 1 / (dop_i^2)")
    is_interpolated: bool = Field(default=False, description="True if pose was computed via cubic B-spline")


class TelemetryTrack(BaseModel):
    """Complete flight trajectory sequence with spatial boundary metadata."""

    drone_model: str = Field(default="Generic UAV", description="Identified UAV hardware model")
    total_records: int
    duration_sec: float
    sampling_rate_hz: float
    utm_zone: int
    utm_hemisphere: str = Field(..., pattern="^[NS]$")
    origin_easting: float = Field(..., description="Anchor Easting subtracted for local numeric stability")
    origin_northing: float = Field(..., description="Anchor Northing subtracted for local numeric stability")
    origin_altitude: float = Field(..., description="Anchor Altitude subtracted for local numeric stability")
    bounding_box_meters: dict[str, float] = Field(
        ...,
        description="Bounding extents in meters: min_x, max_x, min_y, max_y, min_z, max_z"
    )
    poses: list[SynchronizedPose] = Field(default_factory=list)
    has_degraded_gps: bool = Field(default=False, description="Flagged if mean DOP > 4.0 or signal dropouts detected")
