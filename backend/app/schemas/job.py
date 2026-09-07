"""Pydantic schemas for reconstruction jobs and progress streaming."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class DefenseAuditReport(BaseModel):
    """Formal spatial intelligence accuracy and anti-hallucination audit certificate."""

    total_candidate_points: int
    verified_points: int
    pruned_hallucinations: int
    mean_confidence_score: float = Field(..., ge=0.0, le=1.0)
    observation_coverage_pct: float = Field(..., ge=0.0, le=100.0)
    unobserved_void_pct: float = Field(..., ge=0.0, le=100.0)
    min_ray_coverage: int
    metric_scale_confirmed: bool
    scale_error_percentage: float
    geodetic_crs: str
    anti_hallucination_compliant: bool


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineStage(str, Enum):
    QUEUED = "QUEUED"
    STAGE1_INGESTION = "STAGE1_INGESTION"
    STAGE2_KEYFRAMING = "STAGE2_KEYFRAMING"
    STAGE3_FOUNDATION_POSE = "STAGE3_FOUNDATION_POSE"
    STAGE4_GEOREFERENCING = "STAGE4_GEOREFERENCING"
    STAGE5_SURFACE_3DGS = "STAGE5_SURFACE_3DGS"
    STAGE6_AUDIT_EXPORT = "STAGE6_AUDIT_EXPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobProgressUpdate(BaseModel):
    """Real-time progress broadcast over WebSockets."""

    job_id: str
    stage: str
    percentage: float = Field(..., ge=0.0, le=100.0)
    message: str
    vram_used_mb: float = 0.0
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobCreateRequest(BaseModel):
    """Configuration to start a reconstruction job."""

    mission_name: str = Field(default="Tactical Drone Recon")
    video_filename: str
    telemetry_filename: str
    voxel_resolution: int = Field(default=48, ge=16, le=128)
    min_confidence: float = Field(default=0.35, ge=0.1, le=0.9)


class JobSummary(BaseModel):
    """Concise representation of a reconstruction job."""

    job_id: str
    mission_name: str
    status: JobStatus
    stage: str
    progress_pct: float
    created_at: str
    completed_at: Optional[str] = None
    duration_sec: Optional[float] = None
    keyframe_count: int = 0
    points_count: int = 0
    glb_url: Optional[str] = None
    las_url: Optional[str] = None
    dsm_url: Optional[str] = None
    audit_report: Optional[DefenseAuditReport] = None
    error_message: Optional[str] = None
