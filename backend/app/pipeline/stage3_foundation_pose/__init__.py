"""Stage 3 Foundation Vision Pose and Pointmap Estimation Package."""

from backend.app.pipeline.stage3_foundation_pose.kabsch_svd import solve_kabsch_rigid
from backend.app.pipeline.stage3_foundation_pose.pointmap_regressor import (
    PointmapRegressor,
    RelativePoseResult,
)
from backend.app.pipeline.stage3_foundation_pose.view_graph import (
    RelativeCameraPose,
    RelativeReconstruction,
    ViewGraphBuilder,
)
from backend.app.pipeline.stage3_foundation_pose.vit_model import (
    PointmapOutput,
    ViTPointmapModel,
)

__all__ = [
    "solve_kabsch_rigid",
    "PointmapRegressor",
    "RelativePoseResult",
    "RelativeCameraPose",
    "RelativeReconstruction",
    "ViewGraphBuilder",
    "PointmapOutput",
    "ViTPointmapModel",
]
