"""Deliverable Export and Download Endpoints."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.config import config

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/{job_id}/mesh")
@router.get("/{job_id}/glb")
async def download_glb(job_id: str):
    """Download watertight .glb 3D mesh model."""
    path = config.exports_dir / job_id / "tactical_mesh.glb"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GLB model not found")
    return FileResponse(str(path), media_type="model/gltf-binary", filename=f"{job_id}.glb")


@router.get("/{job_id}/obj")
async def download_obj(job_id: str):
    """Download Wavefront .obj mesh model."""
    path = config.exports_dir / job_id / "tactical_mesh.obj"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OBJ model not found")
    return FileResponse(str(path), media_type="text/plain", filename=f"{job_id}.obj")


@router.get("/{job_id}/pointcloud")
@router.get("/{job_id}/las")
async def download_las(job_id: str):
    """Download georeferenced ASPRS LAS 1.4 point cloud."""
    path = config.exports_dir / job_id / "georeferenced_cloud.las"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LAS point cloud not found")
    return FileResponse(str(path), media_type="application/octet-stream", filename=f"{job_id}.las")


@router.get("/{job_id}/dsm")
async def download_dsm(job_id: str):
    """Download orthorectified GeoTIFF Digital Surface Model."""
    path = config.exports_dir / job_id / "orthorectified_dsm.tif"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GeoTIFF DSM not found")
    return FileResponse(str(path), media_type="image/tiff", filename=f"{job_id}_dsm.tif")
