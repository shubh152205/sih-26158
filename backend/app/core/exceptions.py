"""Domain-specific pipeline exception hierarchy.

Ensures fail-safe error boundaries and unambiguous tactical error reporting.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all reconstruction pipeline errors."""

    def __init__(self, message: str, stage: str = "GLOBAL", recoverable: bool = False):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.recoverable = recoverable

    def to_dict(self) -> dict[str, object]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "stage": self.stage,
            "recoverable": self.recoverable,
        }


class TelemetryParseError(PipelineError):
    """Raised when drone telemetry stream (.srt, KLV, CSV) cannot be parsed or is corrupted."""

    def __init__(self, message: str, file_path: str | None = None):
        super().__init__(message, stage="STAGE1_INGESTION", recoverable=True)
        self.file_path = file_path


class GeodeticConversionError(PipelineError):
    """Raised when WGS84 coordinates cannot be mapped to a valid UTM zone."""

    def __init__(self, message: str, lat: float | None = None, lon: float | None = None):
        super().__init__(message, stage="STAGE1_INGESTION", recoverable=False)
        self.lat = lat
        self.lon = lon


class KeyframingError(PipelineError):
    """Raised when adaptive keyframe gating rejects all candidate frames or fails flow calculation."""

    def __init__(self, message: str):
        super().__init__(message, stage="STAGE2_KEYFRAMING", recoverable=True)


class PoseEstimationError(PipelineError):
    """Raised when ViT pointmap regression or relative Kabsch SVD fails to converge."""

    def __init__(self, message: str):
        super().__init__(message, stage="STAGE3_FOUNDATION_POSE", recoverable=False)


class GeoreferencingError(PipelineError):
    """Raised when closed-form Umeyama Sim(3) solver encounters degenerate rank or insufficient correspondences."""

    def __init__(self, message: str):
        super().__init__(message, stage="STAGE4_GEOREFERENCING", recoverable=True)


class MeshExtractionError(PipelineError):
    """Raised when SDF Marching Tetrahedra generates non-manifold or empty triangular topology."""

    def __init__(self, message: str):
        super().__init__(message, stage="STAGE5_SURFACE_3DGS", recoverable=False)


class AntiHallucinationAuditError(PipelineError):
    """Raised when quality verification thresholds are violated."""

    def __init__(self, message: str):
        super().__init__(message, stage="STAGE6_AUDIT_EXPORT", recoverable=False)


class PipelineVRAMExceededError(PipelineError):
    """Raised when GPU memory limits are breached and dynamic downscaling cannot recover."""

    def __init__(self, message: str, required_bytes: int = 0, available_bytes: int = 0):
        super().__init__(message, stage="MEMORY_GUARD", recoverable=False)
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
