"""API v1 Master Router Assembly."""

from fastapi import APIRouter

from backend.app.api.v1.endpoints.analytics import router as analytics_router
from backend.app.api.v1.endpoints.export import router as export_router
from backend.app.api.v1.endpoints.recon import router as recon_router
from backend.app.api.v1.endpoints.telemetry import router as telemetry_router
from backend.app.api.v1.endpoints.viewer import router as viewer_router
from backend.app.api.v1.websocket import router as ws_router

api_v1_router = APIRouter()

api_v1_router.include_router(recon_router)
api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(viewer_router)
api_v1_router.include_router(export_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(ws_router)
