"""3D Model and Asset Streaming Endpoints for WebGL Clients."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.config import config

router = APIRouter(prefix="/viewer", tags=["Viewer"])


@router.get("/{job_id}/mesh.glb")
async def get_mesh_glb(job_id: str):
    """Stream watertight Binary glTF (.glb) 3D mesh model."""
    glb_path = config.exports_dir / job_id / "tactical_mesh.glb"
    if not glb_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"3D Mesh not found for mission {job_id}",
        )
    return FileResponse(
        path=str(glb_path),
        media_type="model/gltf-binary",
        filename=f"{job_id}_mesh.glb",
    )


@router.get("/{job_id}/pointcloud.ply")
async def get_pointcloud_ply(job_id: str):
    """Stream binary Stanford PLY point cloud."""
    ply_path = config.exports_dir / job_id / "georeferenced_cloud.ply"
    if not ply_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Point cloud not found for mission {job_id}",
        )
    return FileResponse(
        path=str(ply_path),
        media_type="application/octet-stream",
        filename=f"{job_id}_cloud.ply",
    )
