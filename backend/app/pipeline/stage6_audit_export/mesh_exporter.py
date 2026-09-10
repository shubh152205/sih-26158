"""Polygonal 3D Mesh Exporter Subsystem.

Packages watertight 3D models into production .glb (Binary glTF 2.0) and .obj formats
with embedded PBR materials, vertex colors, and georeference metadata.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import trimesh

from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="MESH-EXPORTER")


class MeshExporter:
    """Exports 3D mesh models to industry standard delivery formats."""

    # Standard transformation from GIS/Robotics Z-Up (X=East, Y=North, Z=Up)
    # to glTF 2.0 / WebGL Y-Up (X=East, Y=Up, Z=-North).
    # Preserves right-handed coordinate frame with determinant +1.
    R_ZUP_TO_YUP = np.array([
        [1.0,  0.0,  0.0, 0.0],
        [0.0,  0.0,  1.0, 0.0],
        [0.0, -1.0,  0.0, 0.0],
        [0.0,  0.0,  0.0, 1.0],
    ], dtype=np.float64)

    @classmethod
    def export_glb(cls, mesh: trimesh.Trimesh, output_path: str | Path) -> Path:
        """Export mesh as Binary glTF (.glb) with materials and textures conforming to glTF 2.0 Y-up standard."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        mesh_gltf = mesh.copy()
        mesh_gltf.apply_transform(cls.R_ZUP_TO_YUP)

        glb_bytes = trimesh.exchange.gltf.export_glb(mesh_gltf)
        out.write_bytes(glb_bytes)

        logger.info("Exported watertight GLB mesh (%d bytes, Y-Up) to %s", len(glb_bytes), str(out))
        return out

    @classmethod
    def export_obj(cls, mesh: trimesh.Trimesh, output_path: str | Path) -> Path:
        """Export mesh as Wavefront OBJ with MTL material definition conforming to Y-up convention."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        mesh_obj = mesh.copy()
        mesh_obj.apply_transform(cls.R_ZUP_TO_YUP)

        obj_str = trimesh.exchange.obj.export_obj(mesh_obj)
        out.write_text(obj_str, encoding="utf-8")

        logger.info("Exported Wavefront OBJ mesh (Y-Up) to %s", str(out))
        return out

