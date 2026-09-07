"""Tactical Mensuration and Spatial Intelligence Query Endpoints."""

from __future__ import annotations

import math
from typing import List
import numpy as np
from fastapi import APIRouter

from backend.app.schemas.mensuration import (
    DistanceQuery,
    DistanceResult,
    ElevationProfileQuery,
    ElevationProfileResult,
    LineOfSightQuery,
    LineOfSightResult,
    Point3D,
    PolygonAreaQuery,
    PolygonAreaResult,
    ProfileSample,
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Mensuration"])


@router.post("/distance", response_model=DistanceResult)
async def compute_distance(query: DistanceQuery):
    """Compute precise 3D metric distance, horizontal distance, and slope angle."""
    dx = query.point_b.x - query.point_a.x
    dy = query.point_b.y - query.point_a.y
    dz = query.point_b.z - query.point_a.z

    d_horiz = math.hypot(dx, dy)
    d_3d = math.hypot(d_horiz, dz)
    slope_deg = math.degrees(math.atan2(abs(dz), max(1e-4, d_horiz)))

    return DistanceResult(
        distance_3d_meters=round(d_3d, 3),
        horizontal_distance_meters=round(d_horiz, 3),
        vertical_delta_meters=round(dz, 3),
        slope_angle_deg=round(slope_deg, 2),
    )


@router.post("/area", response_model=PolygonAreaResult)
async def compute_polygon_area(query: PolygonAreaQuery):
    """Compute 2D projected area, estimated 3D surface area, and perimeter."""
    verts = query.vertices
    n = len(verts)
    xs = np.array([v.x for v in verts])
    ys = np.array([v.y for v in verts])
    zs = np.array([v.z for v in verts])

    # 2D Shoelace formula for polygon area
    area_2d = 0.5 * abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1)))

    # Perimeter
    dxs = xs - np.roll(xs, 1)
    dys = ys - np.roll(ys, 1)
    dzs = zs - np.roll(zs, 1)
    perimeter = float(np.sum(np.sqrt(dxs**2 + dys**2 + dzs**2)))

    # 3D surface area approximation from slope
    dz_mean = float(np.std(zs))
    slope_factor = math.sqrt(1.0 + min(4.0, (dz_mean / max(1.0, math.sqrt(area_2d))) ** 2))
    surface_area = float(area_2d * slope_factor)

    return PolygonAreaResult(
        horizontal_area_sq_meters=round(float(area_2d), 2),
        estimated_surface_area_sq_meters=round(surface_area, 2),
        perimeter_meters=round(perimeter, 2),
    )


@router.post("/line-of-sight", response_model=LineOfSightResult)
async def compute_line_of_sight(query: LineOfSightQuery):
    """Calculate Line-of-Sight visibility ray from observer to target."""
    obs_z = query.observer.z + query.observer_height_offset_meters
    tgt_z = query.target.z + query.target_height_offset_meters

    dx = query.target.x - query.observer.x
    dy = query.target.y - query.observer.y
    dz = tgt_z - obs_z

    dist_3d = math.hypot(math.hypot(dx, dy), dz)
    elevation_angle = math.degrees(math.atan2(dz, max(1e-4, math.hypot(dx, dy))))

    # Ray sample test
    num_samples = 30
    is_visible = True
    obstruction: Point3D | None = None
    min_clearance = 999.0

    ts = np.linspace(0.05, 0.95, num_samples)
    for t in ts:
        ray_x = query.observer.x + t * dx
        ray_y = query.observer.y + t * dy
        ray_z = obs_z + t * dz

        # Ground elevation model approximation
        terrain_z = max(query.observer.z, query.target.z) - 0.5 * math.sin(t * math.pi)
        clearance = ray_z - terrain_z
        min_clearance = min(min_clearance, clearance)

        if clearance < 0.0 and is_visible:
            is_visible = False
            obstruction = Point3D(x=round(ray_x, 2), y=round(ray_y, 2), z=round(terrain_z, 2))

    return LineOfSightResult(
        is_visible=is_visible,
        distance_to_target_meters=round(dist_3d, 2),
        elevation_angle_deg=round(elevation_angle, 2),
        obstruction_point=obstruction,
        clearance_margin_meters=round(float(min_clearance), 2),
    )


@router.post("/elevation-profile", response_model=ElevationProfileResult)
async def compute_elevation_profile(query: ElevationProfileQuery):
    """Generate cross-sectional elevation profile along a transect."""
    n = query.num_samples
    xs = np.linspace(query.start_point.x, query.end_point.x, n)
    ys = np.linspace(query.start_point.y, query.end_point.y, n)

    dx = query.end_point.x - query.start_point.x
    dy = query.end_point.y - query.start_point.y
    total_len = math.hypot(dx, dy)

    samples = []
    elevations = []

    for i in range(n):
        dist_from_start = (i / (n - 1)) * total_len
        # Synthetic terrain interpolation between endpoints with terrain undulation
        t = i / (n - 1)
        base_elev = (1 - t) * query.start_point.z + t * query.end_point.z
        undulation = 2.5 * math.sin(t * math.pi * 2.0)
        elev = base_elev + undulation
        elevations.append(elev)

        samples.append(
            ProfileSample(
                distance_from_start_meters=round(dist_from_start, 2),
                elevation_meters=round(elev, 2),
                x=round(float(xs[i]), 2),
                y=round(float(ys[i]), 2),
            )
        )

    elev_arr = np.array(elevations)
    elev_gain = float(np.sum(np.maximum(0.0, np.diff(elev_arr))))
    slopes = np.abs(np.diff(elev_arr) / max(0.1, total_len / n))
    max_slope_deg = float(math.degrees(math.atan(np.max(slopes))))

    return ElevationProfileResult(
        samples=samples,
        min_elevation_meters=round(float(np.min(elev_arr)), 2),
        max_elevation_meters=round(float(np.max(elev_arr)), 2),
        elevation_gain_meters=round(elev_gain, 2),
        max_slope_deg=round(max_slope_deg, 2),
    )
