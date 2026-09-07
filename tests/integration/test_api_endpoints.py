"""Integration tests for FastAPI endpoints."""

import io
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app

client = TestClient(app)


def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "hardware" in data
    assert "vram_total_mb" in data["hardware"]


def test_analytics_distance_endpoint():
    payload = {
        "point_a": {"x": 0.0, "y": 0.0, "z": 10.0},
        "point_b": {"x": 30.0, "y": 40.0, "z": 20.0},
    }
    response = client.post("/api/v1/analytics/distance", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["horizontal_distance_meters"] == 50.0
    assert abs(res["distance_3d_meters"] - 50.99) < 0.1
    assert res["vertical_delta_meters"] == 10.0
    assert res["slope_angle_deg"] > 0.0


def test_analytics_area_endpoint():
    # 10x10 square
    payload = {
        "vertices": [
            {"x": 0.0, "y": 0.0, "z": 0.0},
            {"x": 10.0, "y": 0.0, "z": 0.0},
            {"x": 10.0, "y": 10.0, "z": 0.0},
            {"x": 0.0, "y": 10.0, "z": 0.0},
        ]
    }
    response = client.post("/api/v1/analytics/area", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["horizontal_area_sq_meters"] == 100.0
    assert res["perimeter_meters"] == 40.0


def test_analytics_line_of_sight_endpoint():
    payload = {
        "observer": {"x": 0.0, "y": 0.0, "z": 10.0},
        "target": {"x": 100.0, "y": 100.0, "z": 10.0},
        "observer_height_offset_meters": 2.0,
        "target_height_offset_meters": 0.0,
    }
    response = client.post("/api/v1/analytics/line-of-sight", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "is_visible" in res
    assert res["distance_to_target_meters"] > 100.0


def test_analytics_elevation_profile_endpoint():
    payload = {
        "start_point": {"x": 0.0, "y": 0.0, "z": 10.0},
        "end_point": {"x": 100.0, "y": 0.0, "z": 25.0},
        "num_samples": 20,
    }
    response = client.post("/api/v1/analytics/elevation-profile", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert len(res["samples"]) == 20
    assert res["samples"][0]["distance_from_start_meters"] == 0.0
    assert res["max_elevation_meters"] >= 25.0


def test_telemetry_parse_endpoint():
    sample_srt = """1
00:00:00,000 --> 00:00:01,000
[latitude: 28.6139] [longitude: 77.2090] [altitude: 120.0] [flight_yaw: 45.0] [gimbal_pitch: -30.0] [gimbal_roll: 0.0]

2
00:00:01,000 --> 00:00:02,000
[latitude: 28.6140] [longitude: 77.2091] [altitude: 121.0] [flight_yaw: 45.0] [gimbal_pitch: -30.0] [gimbal_roll: 0.0]
"""
    files = {"file": ("flight.srt", io.BytesIO(sample_srt.encode("utf-8")), "text/plain")}
    response = client.post("/api/v1/telemetry/parse", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 2
    assert data["utm_zone"] == 43
    assert len(data["poses"]) > 0


def test_recon_demo_mission_endpoint():
    response = client.post("/api/v1/recon/jobs/demo")
    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == "demo-mission-alpha"
    assert data["status"] in ["QUEUED", "PROCESSING"]
