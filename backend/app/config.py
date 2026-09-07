"""Application Configuration and Environmental Settings."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Configuration parameters for the Tactical Reconstruction Engine."""

    app_name: str = "SIH26158 Tactical 3D Reconstruction Engine"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Base workspace directory
    base_dir: Path = Field(default_factory=lambda: Path(os.getenv("BASE_DIR", ".")).resolve())

    # Data Storage Directories
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")).resolve())
    raw_dir: Path = Field(default_factory=lambda: Path(os.getenv("RAW_DIR", "data/raw")).resolve())
    processed_dir: Path = Field(default_factory=lambda: Path(os.getenv("PROCESSED_DIR", "data/processed")).resolve())
    exports_dir: Path = Field(default_factory=lambda: Path(os.getenv("EXPORTS_DIR", "data/exports")).resolve())

    # Compute & GPU Settings
    prefer_cuda: bool = Field(default_factory=lambda: os.getenv("PREFER_CUDA", "true").lower() == "true")
    max_vram_gb: float = Field(default_factory=lambda: float(os.getenv("MAX_VRAM_GB", "22.0")))

    # Quality & Mesh Extraction Parameters
    default_voxel_res: int = 48
    default_gsd_meters: float = 0.15

    def setup_directories(self) -> None:
        """Ensure all runtime directories exist."""
        for d in [self.data_dir, self.raw_dir, self.processed_dir, self.exports_dir]:
            d.mkdir(parents=True, exist_ok=True)


config = AppConfig()
config.setup_directories()
