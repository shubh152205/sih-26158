"""Stage 4 Telemetry-Anchored Sim(3) Georeferencing Package."""

from backend.app.pipeline.stage4_georeferencing.metric_scaler import (
    MetricScaler,
    MetricSceneModel,
)
from backend.app.pipeline.stage4_georeferencing.trajectory_aligner import (
    TrajectoryAligner,
    TrajectoryAlignmentResult,
)
from backend.app.pipeline.stage4_georeferencing.umeyama_solver import (
    Sim3Transform,
    solve_weighted_umeyama_sim3,
)

__all__ = [
    "MetricScaler",
    "MetricSceneModel",
    "TrajectoryAligner",
    "TrajectoryAlignmentResult",
    "Sim3Transform",
    "solve_weighted_umeyama_sim3",
]
