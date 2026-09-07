"""Stage 1 Ingestion and Telemetry Synchronization Package."""

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
from backend.app.pipeline.stage1_ingestion.video_decoder import (
    VideoDecoder,
    VideoMetadata,
)

__all__ = [
    "GeodeticTransformer",
    "determine_utm_zone",
    "TrajectorySplineInterpolator",
    "euler_to_quaternion",
    "quaternion_to_euler",
    "TelemetryParser",
    "parse_srt_timestamp_ms",
    "VideoDecoder",
    "VideoMetadata",
]
