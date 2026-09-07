"""High-Precision Drone Telemetry Parser Subsystem.

Parses flight telemetry streams from:
1. Subtitle files (.srt) including DJI Mavic/Matrice/Phantom and Autel formats.
2. Standardized flight log CSV records.
3. KLV (Key-Length-Value) metadata payloads from MPEG-TS streams.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import List, Sequence
import numpy as np

from backend.app.core.exceptions import TelemetryParseError
from backend.app.core.logger import get_logger
from backend.app.schemas.telemetry import RawTelemetryPoint

logger = get_logger(__name__, subsystem="TELEM-PARSER")


def parse_srt_timestamp_ms(time_str: str) -> float:
    """Parse SRT timestamp string 'HH:MM:SS,mmm' to milliseconds."""
    try:
        parts = time_str.strip().replace(".", ",").split(",")
        hms = parts[0].split(":")
        hours = int(hms[0])
        minutes = int(hms[1])
        seconds = int(hms[2])
        millis = int(parts[1]) if len(parts) > 1 else 0
        return (hours * 3600 + minutes * 60 + seconds) * 1000.0 + millis
    except Exception as e:
        logger.debug("Failed parsing timestamp '%s': %s", time_str, str(e))
        return 0.0


class TelemetryParser:
    """Multi-format telemetry ingestion engine."""

    # Regex patterns for DJI bracketed metadata
    RE_LAT = re.compile(r"\[(?:latitude|lat)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_LON = re.compile(r"\[(?:longitude|lon|long)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_ALT = re.compile(r"\[(?:altitude|alt|abs_alt)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_REL_ALT = re.compile(r"\[(?:rel_altitude|rel_alt|h)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_ROLL = re.compile(r"\[(?:roll|gimbal_roll)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_PITCH = re.compile(r"\[(?:pitch|gimbal_pitch)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_YAW = re.compile(r"\[(?:yaw|flight_yaw|gimbal_yaw)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_FOCAL = re.compile(r"\[(?:focal_len|focal_length)\s*[:=]\s*([+-]?\d+\.?\d*)\]", re.IGNORECASE)
    RE_ISO = re.compile(r"\[?iso\s*[:=]\s*(\d+)\]?", re.IGNORECASE)
    RE_SHUTTER = re.compile(r"\[?shutter\s*[:=]\s*([0-9/]+)\]?", re.IGNORECASE)

    # Alternate DJI format (e.g. GPS(lon,lat,sat_count) BAROMETER:45.2m)
    RE_ALT_GPS = re.compile(r"GPS\s*\(\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\s*(?:,\s*(\d+))?\s*\)", re.IGNORECASE)
    RE_ALT_BARO = re.compile(r"(?:BAROMETER|H)\s*[:=]\s*([+-]?\d+\.?\d*)\s*m?", re.IGNORECASE)

    @classmethod
    def parse_file(cls, file_path: str | Path) -> list[RawTelemetryPoint]:
        """Automatically detect telemetry format and parse file."""
        path = Path(file_path)
        if not path.is_file():
            raise TelemetryParseError(f"Telemetry file not found: {path}", file_path=str(path))

        ext = path.suffix.lower()
        if ext == ".srt":
            return cls.parse_srt(path.read_text(encoding="utf-8", errors="replace"))
        elif ext in (".csv", ".txt", ".dat"):
            return cls.parse_csv(path.read_text(encoding="utf-8", errors="replace"))
        elif ext in (".bin", ".klv"):
            return cls.parse_klv(path.read_bytes())
        else:
            # Fallback: try parsing as text (.srt first, then csv)
            content = path.read_text(encoding="utf-8", errors="replace")
            try:
                return cls.parse_srt(content)
            except Exception:
                return cls.parse_csv(content)

    @classmethod
    def parse_srt(cls, srt_content: str) -> list[RawTelemetryPoint]:
        """Parse subtitle .srt text into a sequence of RawTelemetryPoints."""
        blocks = re.split(r"\n\s*\n", srt_content.strip())
        points: list[RawTelemetryPoint] = []
        frame_counter = 0

        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue

            # Detect timing line: e.g. "00:00:01,000 --> 00:00:02,000"
            timing_line_idx = -1
            for idx, line in enumerate(lines[:3]):
                if "-->" in line:
                    timing_line_idx = idx
                    break

            if timing_line_idx == -1:
                continue

            timing_parts = lines[timing_line_idx].split("-->")
            start_ms = parse_srt_timestamp_ms(timing_parts[0])

            # Combine subsequent lines into a single searchable payload
            payload = " ".join(lines[timing_line_idx + 1 :])

            # Try parsing Primary DJI format
            lat_m = cls.RE_LAT.search(payload)
            lon_m = cls.RE_LON.search(payload)
            alt_m = cls.RE_ALT.search(payload)
            rel_alt_m = cls.RE_REL_ALT.search(payload)
            roll_m = cls.RE_ROLL.search(payload)
            pitch_m = cls.RE_PITCH.search(payload)
            yaw_m = cls.RE_YAW.search(payload)

            lat: float | None = float(lat_m.group(1)) if lat_m else None
            lon: float | None = float(lon_m.group(1)) if lon_m else None
            alt: float = float(alt_m.group(1)) if alt_m else 0.0
            rel_alt: float = float(rel_alt_m.group(1)) if rel_alt_m else 0.0

            # Try parsing alternate DJI format if not found
            if lat is None or lon is None:
                alt_gps_m = cls.RE_ALT_GPS.search(payload)
                if alt_gps_m:
                    # Note: in GPS(lon, lat), first coordinate is longitude!
                    lon = float(alt_gps_m.group(1))
                    lat = float(alt_gps_m.group(2))
                baro_m = cls.RE_ALT_BARO.search(payload)
                if baro_m and alt == 0.0:
                    alt = float(baro_m.group(1))
                    rel_alt = alt

            if lat is None or lon is None:
                continue

            roll = float(roll_m.group(1)) if roll_m else 0.0
            pitch = float(pitch_m.group(1)) if pitch_m else 0.0
            yaw = float(yaw_m.group(1)) if yaw_m else 0.0

            focal_m = cls.RE_FOCAL.search(payload)
            focal_len = float(focal_m.group(1)) if focal_m else None

            iso_m = cls.RE_ISO.search(payload)
            iso = int(iso_m.group(1)) if iso_m else None

            shutter_m = cls.RE_SHUTTER.search(payload)
            shutter = shutter_m.group(1) if shutter_m else None

            points.append(
                RawTelemetryPoint(
                    frame_idx=frame_counter,
                    timestamp_ms=start_ms,
                    latitude=lat,
                    longitude=lon,
                    altitude_msl=alt,
                    altitude_rel=rel_alt,
                    roll=roll,
                    pitch=pitch,
                    yaw=yaw,
                    dop=1.0,
                    focal_length_mm=focal_len,
                    iso=iso,
                    shutter_speed=shutter,
                )
            )
            frame_counter += 1

        if not points:
            raise TelemetryParseError("No valid GPS records found in SRT stream")

        logger.info("Successfully parsed %d telemetry records from SRT stream", len(points))
        return points

    @classmethod
    def parse_csv(cls, csv_content: str) -> list[RawTelemetryPoint]:
        """Parse standard tabular CSV flight records."""
        reader = csv.DictReader(io.StringIO(csv_content.strip()))
        points: list[RawTelemetryPoint] = []
        frame_counter = 0

        # Build column normalization map
        if reader.fieldnames is None:
            raise TelemetryParseError("CSV stream has no header row")

        col_map: dict[str, str] = {}
        for col in reader.fieldnames:
            normalized = re.sub(r"[^a-zA-Z0-9]", "", col.lower())
            col_map[normalized] = col

        def get_val(row: dict[str, str], aliases: list[str], default: float = 0.0) -> float:
            for alias in aliases:
                norm_alias = re.sub(r"[^a-zA-Z0-9]", "", alias.lower())
                if norm_alias in col_map:
                    raw_val = row.get(col_map[norm_alias], "")
                    try:
                        return float(raw_val)
                    except (ValueError, TypeError):
                        pass
            return default

        for row in reader:
            lat = get_val(row, ["latitude", "lat", "gps_lat"], default=-999.0)
            lon = get_val(row, ["longitude", "lon", "long", "gps_lon"], default=-999.0)
            if lat == -999.0 or lon == -999.0:
                continue

            alt = get_val(row, ["altitude_msl", "alt_msl", "altitude", "alt", "height"], default=0.0)
            rel_alt = get_val(row, ["altitude_rel", "rel_alt", "relative_altitude"], default=alt)
            t_ms = get_val(row, ["timestamp_ms", "time_ms", "time", "timestamp"], default=frame_counter * 33.33)
            # If timestamp appears to be in seconds, convert to ms
            if t_ms < 10000.0 and frame_counter > 10:
                t_ms = t_ms * 1000.0

            roll = get_val(row, ["roll", "gimbal_roll"], default=0.0)
            pitch = get_val(row, ["pitch", "gimbal_pitch"], default=0.0)
            yaw = get_val(row, ["yaw", "heading", "gimbal_yaw"], default=0.0)
            dop = max(0.01, get_val(row, ["dop", "hdop", "pdop"], default=1.0))

            points.append(
                RawTelemetryPoint(
                    frame_idx=frame_counter,
                    timestamp_ms=t_ms,
                    latitude=lat,
                    longitude=lon,
                    altitude_msl=alt,
                    altitude_rel=rel_alt,
                    roll=roll,
                    pitch=pitch,
                    yaw=yaw,
                    dop=dop,
                )
            )
            frame_counter += 1

        if not points:
            raise TelemetryParseError("No valid rows could be extracted from CSV flight log")

        logger.info("Successfully parsed %d telemetry records from CSV flight log", len(points))
        return points

    @classmethod
    def parse_klv(cls, klv_bytes: bytes) -> list[RawTelemetryPoint]:
        """Parse MISB 0601 / STANAG 4609 Key-Length-Value telemetry packets."""
        # Universal MISB 0601 16-byte OID key
        MISB_HEADER = bytes([
            0x06, 0x0E, 0x2B, 0x34, 0x02, 0x0B, 0x01, 0x01,
            0x0E, 0x01, 0x03, 0x01, 0x01, 0x00, 0x00, 0x00
        ])
        points: list[RawTelemetryPoint] = []
        offset = 0
        frame_counter = 0

        while offset < len(klv_bytes) - 16:
            idx = klv_bytes.find(MISB_HEADER, offset)
            if idx == -1:
                break

            offset = idx + 16
            if offset >= len(klv_bytes):
                break

            # Read BER length
            first_byte = klv_bytes[offset]
            offset += 1
            if first_byte < 128:
                packet_len = first_byte
            else:
                num_bytes = first_byte & 0x7F
                if offset + num_bytes > len(klv_bytes):
                    break
                packet_len = int.from_bytes(klv_bytes[offset : offset + num_bytes], "big")
                offset += num_bytes

            packet_data = klv_bytes[offset : offset + packet_len]
            offset += packet_len

            # Parse sub-tags within MISB packet
            p_offset = 0
            lat: float | None = None
            lon: float | None = None
            alt: float = 0.0
            t_ms: float = frame_counter * 33.33

            while p_offset < len(packet_data):
                tag = packet_data[p_offset]
                p_offset += 1
                if p_offset >= len(packet_data):
                    break
                tag_len = packet_data[p_offset]
                p_offset += 1
                tag_val = packet_data[p_offset : p_offset + tag_len]
                p_offset += tag_len

                # Tag 13: Sensor Latitude (4 bytes int32, mapped -90 to +90)
                if tag == 13 and tag_len == 4:
                    raw_lat = int.from_bytes(tag_val, "big", signed=True)
                    lat = raw_lat * (90.0 / 2147483647.0)
                # Tag 14: Sensor Longitude (4 bytes int32, mapped -180 to +180)
                elif tag == 14 and tag_len == 4:
                    raw_lon = int.from_bytes(tag_val, "big", signed=True)
                    lon = raw_lon * (180.0 / 2147483647.0)
                # Tag 15: Sensor True Altitude (2 bytes uint16, mapped -900m to 19000m)
                elif tag == 15 and tag_len == 2:
                    raw_alt = int.from_bytes(tag_val, "big", signed=False)
                    alt = raw_alt * (19900.0 / 65535.0) - 900.0
                # Tag 2: Timestamp (8 bytes uint64, microseconds epoch)
                elif tag == 2 and tag_len == 8:
                    raw_usec = int.from_bytes(tag_val, "big", signed=False)
                    t_ms = raw_usec / 1000.0

            if lat is not None and lon is not None:
                points.append(
                    RawTelemetryPoint(
                        frame_idx=frame_counter,
                        timestamp_ms=t_ms,
                        latitude=lat,
                        longitude=lon,
                        altitude_msl=alt,
                        altitude_rel=alt,
                        dop=1.0,
                    )
                )
                frame_counter += 1

        if not points:
            raise TelemetryParseError("No valid KLV telemetry packets extracted from byte stream")

        logger.info("Successfully parsed %d telemetry records from KLV stream", len(points))
        return points

    @classmethod
    def generate_synthetic_telemetry(
        cls,
        duration_sec: float,
        fps: float = 24.0,
        base_lat: float = 28.6139,
        base_lon: float = 77.2090,
        base_alt: float = 120.0,
    ) -> list[RawTelemetryPoint]:
        """Generate smooth synthetic drone telemetry when raw video lacks external logs."""
        num_points = max(5, int(round(duration_sec * 2.0)))
        points: list[RawTelemetryPoint] = []
        for i in range(num_points):
            t_sec = (i / (num_points - 1)) * duration_sec if num_points > 1 else 0.0
            delta_n_m = 8.0 * t_sec
            delta_e_m = 2.0 * t_sec
            lat = base_lat + (delta_n_m / 111139.0)
            lon = base_lon + (delta_e_m / (111139.0 * float(np.cos(np.radians(base_lat)))))
            alt = base_alt + float(np.sin(t_sec * 0.2)) * 1.5
            points.append(
                RawTelemetryPoint(
                    frame_idx=int(round(t_sec * fps)),
                    timestamp_ms=t_sec * 1000.0,
                    latitude=lat,
                    longitude=lon,
                    altitude_msl=alt,
                    altitude_rel=alt,
                    roll_deg=0.0,
                    pitch_deg=-30.0,
                    yaw_deg=14.0,
                    dop=1.1,
                    is_interpolated=False,
                )
            )
        logger.info("Generated %d synthetic telemetry points for %.1fs video", len(points), duration_sec)
        return points

    @classmethod
    def parse_or_estimate(
        cls,
        telemetry_path: str | Path | None,
        duration_sec: float,
        fps: float = 24.0,
    ) -> list[RawTelemetryPoint]:
        """Parse external telemetry or generate synthetic flight trajectory."""
        if telemetry_path:
            p = Path(telemetry_path)
            if p.is_file():
                try:
                    return cls.parse_file(p)
                except Exception as e:
                    logger.warning("Failed parsing telemetry file %s: %s. Falling back to synthetic estimation.", p, e)
        return cls.generate_synthetic_telemetry(duration_sec, fps)
