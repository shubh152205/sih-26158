"""Stage 5 Surface-Regularized 3DGS and Watertight SDF Meshing Package."""

from backend.app.pipeline.stage5_surface_3dgs.gaussian_trainer import (
    GaussianModel,
    SurfaceGaussianTrainer,
)
from backend.app.pipeline.stage5_surface_3dgs.sdf_extractor import (
    SDFMeshExtractor,
)
from backend.app.pipeline.stage5_surface_3dgs.texture_baker import (
    TextureBaker,
)

__all__ = [
    "GaussianModel",
    "SurfaceGaussianTrainer",
    "SDFMeshExtractor",
    "TextureBaker",
]
