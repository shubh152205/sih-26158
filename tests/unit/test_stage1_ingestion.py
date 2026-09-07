"""Unit tests for Stage 1: Telemetry Ingestion, Geodetic Transformation & Spline Interpolation."""

import math
import numpy as np
import pytest

from backend.app.pipeline.stage1_ingestion.geodetic import (
    GeodeticTransformer,
    determine_utm_zone,
)
from backend.app.pipeline.stage1_ingestion.spline_interpolator import (
    TrajectorySplineInterpolator,
    euler_to_quaternion,
    quaternion_to_euler,
)
from backend.app.pipeline.stage1_ingestion.telemetry_parser import (
    TelemetryParser,
    parse_srt_timestamp_ms,
)
from backend.app.schemas.telemetry import RawTelemetryPoint


class TestGeodeticTransformer:
    def test_utm_zone_determination(self):
        # New Delhi, India (approx 28.6139 N, 77.2090 E) -> Zone 43N
        zone, hemi = determine_utm_zone(28.6139, 77.2090)
        assert zone == 43
        assert hemi == "N"

        # Prime Meridian (0, 0) -> Zone 31N
        zone_pm, hemi_pm = determine_utm_zone(0.0, 0.0)
        assert zone_pm == 31
        assert hemi_pm == "N"

        # Southern Hemisphere (Sydney -33.8688, 151.2093) -> Zone 56S
        zone_syd, hemi_syd = determine_utm_zone(-33.8688, 151.2093)
        assert zone_syd == 56
        assert hemi_syd == "S"

    def test_wgs84_utm_roundtrip_precision(self):
        # Target: New Delhi India Gate
        lat_true, lon_true, alt_true = 28.6129, 77.2295, 215.0
        zone, hemi = determine_utm_zone(lat_true, lon_true)
        transformer = GeodeticTransformer(zone=zone, hemisphere=hemi)

        easting, northing, alt = transformer.wgs84_to_utm(lat_true, lon_true, alt_true)

        # Expected UTM 43N easting ~717750m, northing ~3166850m
        assert 700000.0 < easting < 730000.0
        assert 3150000.0 < northing < 3180000.0
        assert math.isclose(alt, alt_true, abs_tol=1e-5)

        # Inverse transform
        lat_inv, lon_inv, alt_inv = transformer.utm_to_wgs84(easting, northing, alt)
        assert math.isclose(lat_inv, lat_true, abs_tol=1e-6)  # Sub-millimeter accuracy
        assert math.isclose(lon_inv, lon_true, abs_tol=1e-6)
        assert math.isclose(alt_inv, alt_true, abs_tol=1e-5)

    def test_batch_transformation(self):
        zone = 43
        transformer = GeodeticTransformer(zone=zone, hemisphere="N")
        lats = np.array([28.61, 28.62, 28.63], dtype=np.float64)
        lons = np.array([77.20, 77.21, 77.22], dtype=np.float64)
        alts = np.array([100.0, 110.0, 120.0], dtype=np.float64)

        utm_pts = transformer.wgs84_to_utm_batch(lats, lons, alts)
        assert utm_pts.shape == (3, 3)
        for i in range(3):
            e_single, n_single, a_single = transformer.wgs84_to_utm(lats[i], lons[i], alts[i])
            assert math.isclose(utm_pts[i, 0], e_single, abs_tol=1e-4)
            assert math.isclose(utm_pts[i, 1], n_single, abs_tol=1e-4)
            assert math.isclose(utm_pts[i, 2], a_single, abs_tol=1e-4)


class TestSplineInterpolator:
    def test_euler_quaternion_roundtrip(self):
        roll_orig, pitch_orig, yaw_orig = 12.5, -25.0, 145.2
        q = euler_to_quaternion(roll_orig, pitch_orig, yaw_orig)
        assert math.isclose(np.linalg.norm(q), 1.0, abs_tol=1e-6)

        roll_back, pitch_back, yaw_back = quaternion_to_euler(q)
        assert math.isclose(roll_back, roll_orig, abs_tol=1e-4)
        assert math.isclose(pitch_back, pitch_orig, abs_tol=1e-4)
        assert math.isclose(yaw_back, yaw_orig, abs_tol=1e-4)

    def test_trajectory_interpolation_accuracy(self):
        # 5 seconds flight path moving east at 10 m/s and rising at 2 m/s
        times = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        eastings = 500000.0 + 10.0 * times
        northings = 3000000.0 + np.zeros_like(times)
        altitudes = 100.0 + 2.0 * times
        rolls = np.zeros_like(times)
        pitches = -15.0 * np.ones_like(times)
        yaws = 90.0 * np.ones_like(times)
        dops = 1.0 * np.ones_like(times)

        interp = TrajectorySplineInterpolator(
            timestamps_sec=times,
            eastings=eastings,
            northings=northings,
            altitudes=altitudes,
            rolls_deg=rolls,
            pitches_deg=pitches,
            yaws_deg=yaws,
            dops=dops,
        )

        # Query midpoint at t = 2.5 seconds
        pose = interp.evaluate_at_time(2.5, frame_idx=75)
        assert math.isclose(pose.utm_easting, 500025.0, abs_tol=1e-2)
        assert math.isclose(pose.utm_northing, 3000000.0, abs_tol=1e-2)
        assert math.isclose(pose.utm_altitude, 105.0, abs_tol=1e-2)
        assert math.isclose(pose.pitch_deg, -15.0, abs_tol=0.5)
        assert math.isclose(pose.yaw_deg, 90.0, abs_tol=0.5)
        assert pose.dop_weight > 0.0


class TestTelemetryParser:
    def test_parse_srt_timestamp(self):
        ms = parse_srt_timestamp_ms("01:02:03,456")
        expected_ms = (1 * 3600 + 2 * 60 + 3) * 1000 + 456
        assert ms == expected_ms

    def test_parse_dji_srt_bracketed(self):
        sample_srt = """
1
00:00:00,000 --> 00:00:01,000
<font size="28">S转换: 100
[latitude: 28.613939] [longitude: 77.209021] [altitude: 125.40] [rel_altitude: 45.20]
[flight_yaw: 42.1] [gimbal_pitch: -30.0] [gimbal_roll: 0.0] [focal_len: 24.0]
</font>

2
00:00:01,000 --> 00:00:02,000
<font size="28">
[latitude: 28.614050] [longitude: 77.209150] [altitude: 126.10] [rel_altitude: 45.90]
[flight_yaw: 43.5] [gimbal_pitch: -30.0] [gimbal_roll: 0.0] [focal_len: 24.0]
</font>
"""
        points = TelemetryParser.parse_srt(sample_srt)
        assert len(points) == 2
        assert math.isclose(points[0].latitude, 28.613939, abs_tol=1e-6)
        assert math.isclose(points[0].longitude, 77.209021, abs_tol=1e-6)
        assert math.isclose(points[0].altitude_msl, 125.40, abs_tol=1e-2)
        assert math.isclose(points[0].pitch, -30.0, abs_tol=1e-2)
        assert math.isclose(points[0].yaw, 42.1, abs_tol=1e-2)
        assert points[0].focal_length_mm == 24.0

    def test_parse_csv_flight_log(self):
        sample_csv = """timestamp,latitude,longitude,altitude_msl,altitude_rel,roll,pitch,yaw,dop
0.0,28.613939,77.209021,125.4,45.2,0.0,-30.0,42.1,1.2
1000.0,28.614050,77.209150,126.1,45.9,0.0,-30.0,43.5,1.1
"""
        points = TelemetryParser.parse_csv(sample_csv)
        assert len(points) == 2
        assert points[1].frame_idx == 1
        assert math.isclose(points[1].latitude, 28.614050, abs_tol=1e-6)
        assert math.isclose(points[1].dop, 1.1, abs_tol=1e-2)
