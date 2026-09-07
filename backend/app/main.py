"""FastAPI High-Performance Async Gateway Entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1 import api_v1_router
from backend.app.config import config
from backend.app.core.gpu_monitor import GPUMonitor
from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="GATEWAY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle handler."""
    logger.info("=================================================================")
    logger.info("Initializing SIH26158 Tactical 3D Reconstruction Gateway...")
    logger.info("Version: %s | API Prefix: %s", config.app_version, config.api_prefix)
    metrics = GPUMonitor.query_metrics()
    logger.info(
        "Hardware Active: %s (CUDA Available: %s, VRAM/Mem: %.1fMB / %.1fMB)",
        metrics.device_name, metrics.is_cuda_available, metrics.vram_used_mb, metrics.vram_total_mb
    )
    logger.info("Data Directories Verified: Exports=%s, Raw=%s", config.exports_dir, config.raw_dir)
    logger.info("=================================================================")
    yield
    logger.info("Shutting down Tactical 3D Reconstruction Gateway...")


app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="High-Speed Single-Pass UAV Video to Watertight 3D Metric Model Generation Engine (NTRO / SIH 2026)",
    lifespan=lifespan,
)

# Cross-Origin Resource Sharing (CORS) for Tactical Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 routes
app.include_router(api_v1_router, prefix=config.api_prefix)

# Mount local exports directory for direct asset serving
app.mount("/static/exports", StaticFiles(directory=str(config.exports_dir)), name="exports")


@app.get("/healthz", tags=["System"])
async def health_check():
    """System health check and live hardware utilization."""
    metrics = GPUMonitor.query_metrics()
    return {
        "status": "OPERATIONAL",
        "system": config.app_name,
        "version": config.app_version,
        "hardware": metrics.model_dump(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=config.host,
        port=config.port,
        reload=True,
    )
