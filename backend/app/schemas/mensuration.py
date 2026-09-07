"""Pydantic schemas for tactical mensuration and spatial intelligence queries."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class DistanceQuery(BaseModel):
    point_a: Point3D
    point_b: Point3D


class DistanceResult(BaseModel):
    distance_3d_meters: float
    horizontal_distance_meters: float
    vertical_delta_meters: float
    slope_angle_deg: float


class PolygonAreaQuery(BaseModel):
    vertices: List[Point3D] = Field(..., min_length=3)


class PolygonAreaResult(BaseModel):
    horizontal_area_sq_meters: float
    estimated_surface_area_sq_meters: float
    perimeter_meters: float


class LineOfSightQuery(BaseModel):
    observer: Point3D
    target: Point3D
    observer_height_offset_meters: float = Field(default=1.8, ge=0.0)
    target_height_offset_meters: float = Field(default=0.0, ge=0.0)
    job_id: Optional[str] = None


class LineOfSightResult(BaseModel):
    is_visible: bool
    distance_to_target_meters: float
    elevation_angle_deg: float
    obstruction_point: Optional[Point3D] = None
    clearance_margin_meters: float


class ElevationProfileQuery(BaseModel):
    start_point: Point3D
    end_point: Point3D
    num_samples: int = Field(default=50, ge=5, le=500)
    job_id: Optional[str] = None


class ProfileSample(BaseModel):
    distance_from_start_meters: float
    elevation_meters: float
    x: float
    y: float


class ElevationProfileResult(BaseModel):
    samples: List[ProfileSample]
    min_elevation_meters: float
    max_elevation_meters: float
    elevation_gain_meters: float
    max_slope_deg: float
