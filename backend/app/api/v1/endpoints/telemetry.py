"""Telemetry Parsing and Inspection Endpoints."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.app.pipeline.stage1_ingestion import (
    GeodeticTransformer,
    TelemetryParser,
    TrajectorySplineInterpolator,
    determine_utm_zone,
)
from backend.app.schemas.telemetry import TelemetryTrack

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/parse", response_model=TelemetryTrack)
async def parse_telemetry_file(file: UploadFile = File(...)):
    """Upload and inspect a drone telemetry stream (.srt, CSV, or KLV)."""
    try:
        content_bytes = await file.read()
        filename = file.filename or "telemetry.srt"

        if filename.lower().endswith(".srt"):
            raw_pts = TelemetryParser.parse_srt(content_bytes.decode("utf-8", errors="replace"))
        elif filename.lower().endswith(".csv") or filename.lower().endswith(".txt"):
            raw_pts = TelemetryParser.parse_csv(content_bytes.decode("utf-8", errors="replace"))
        else:
            raw_pts = TelemetryParser.parse_klv(content_bytes)

        first_pt = raw_pts[0]
        zone, hemi = determine_utm_zone(first_pt.latitude, first_pt.longitude)
        transformer = GeodeticTransformer(zone=zone, hemisphere=hemi)

        # Interpolate poses
        interp = TrajectorySplineInterpolator.from_telemetry_points(raw_pts, transformer)
        duration_sec = interp.t_max - interp.t_min

        # Generate sample poses (1 Hz)
        sample_times = np.linspace(interp.t_min, interp.t_max, min(200, len(raw_pts)))
        poses = [interp.evaluate_at_time(float(t), frame_idx=idx) for idx, t in enumerate(sample_times)]

        origin_e = float(np.mean([p.utm_easting for p in poses]))
        origin_n = float(np.mean([p.utm_northing for p in poses]))
        origin_a = float(np.mean([p.utm_altitude for p in poses]))

        min_x = float(min(p.utm_easting - origin_e for p in poses))
        max_x = float(max(p.utm_easting - origin_e for p in poses))
        min_y = float(min(p.utm_northing - origin_n for p in poses))
        max_y = float(max(p.utm_northing - origin_n for p in poses))
        min_z = float(min(p.utm_altitude - origin_a for p in poses))
        max_z = float(max(p.utm_altitude - origin_a for p in poses))

        mean_dop = float(np.mean([pt.dop for pt in raw_pts]))

        return TelemetryTrack(
            drone_model="UAV Recon Platform",
            total_records=len(raw_pts),
            duration_sec=round(duration_sec, 2),
            sampling_rate_hz=round(len(raw_pts) / max(0.1, duration_sec), 1),
            utm_zone=zone,
            utm_hemisphere=hemi,
            origin_easting=origin_e,
            origin_northing=origin_n,
            origin_altitude=origin_a,
            bounding_box_meters={
                "min_x": min_x, "max_x": max_x,
                "min_y": min_y, "max_y": max_y,
                "min_z": min_z, "max_z": max_z,
            },
            poses=poses,
            has_degraded_gps=(mean_dop > 4.0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse telemetry file: {str(e)}",
        )


@router.get("/track/{job_id}", response_model=TelemetryTrack)
async def get_job_telemetry_track(job_id: str):
    """Retrieve the georeferenced flight track and waypoints for a specific job."""
    from backend.app.config import config

    job_raw_dir = config.raw_dir / job_id
    telem_files = list(job_raw_dir.glob("*.srt")) + list(job_raw_dir.glob("*.csv")) if job_raw_dir.exists() else []

    if telem_files:
        raw_pts = TelemetryParser.parse_file(telem_files[0])
    else:
        raw_pts = TelemetryParser.generate_synthetic_telemetry(duration_sec=25.0)

    first_pt = raw_pts[0]
    zone, hemi = determine_utm_zone(first_pt.latitude, first_pt.longitude)
    transformer = GeodeticTransformer(zone=zone, hemisphere=hemi)

    interp = TrajectorySplineInterpolator.from_telemetry_points(raw_pts, transformer)
    duration_sec = interp.t_max - interp.t_min
    sample_times = np.linspace(interp.t_min, interp.t_max, min(200, len(raw_pts)))
    poses = [interp.evaluate_at_time(float(t), frame_idx=idx) for idx, t in enumerate(sample_times)]

    origin_e = float(np.mean([p.utm_easting for p in poses]))
    origin_n = float(np.mean([p.utm_northing for p in poses]))
    origin_a = float(np.mean([p.utm_altitude for p in poses]))

    return TelemetryTrack(
        drone_model="Tactical Drone Platform",
        total_records=len(raw_pts),
        duration_sec=round(duration_sec, 2),
        sampling_rate_hz=round(len(raw_pts) / max(0.1, duration_sec), 1),
        utm_zone=zone,
        utm_hemisphere=hemi,
        origin_easting=origin_e,
        origin_northing=origin_n,
        origin_altitude=origin_a,
        bounding_box_meters={
            "min_x": float(min(p.utm_easting - origin_e for p in poses)),
            "max_x": float(max(p.utm_easting - origin_e for p in poses)),
            "min_y": float(min(p.utm_northing - origin_n for p in poses)),
            "max_y": float(max(p.utm_northing - origin_n for p in poses)),
            "min_z": float(min(p.utm_altitude - origin_a for p in poses)),
            "max_z": float(max(p.utm_altitude - origin_a for p in poses)),
        },
        poses=poses,
        has_degraded_gps=False,
    )
