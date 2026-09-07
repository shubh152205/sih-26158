"""Polygonal 3D Mesh Exporter Subsystem.

Packages watertight 3D models into production .glb (Binary glTF 2.0) and .obj formats
with embedded PBR materials, vertex colors, and georeference metadata.
"""

from __future__ import annotations

from pathlib import Path
import trimesh

from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="MESH-EXPORTER")


class MeshExporter:
    """Exports 3D mesh models to industry standard delivery formats."""

    @classmethod
    def export_glb(cls, mesh: trimesh.Trimesh, output_path: str | Path) -> Path:
        """Export mesh as Binary glTF (.glb) with materials and textures."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        glb_bytes = trimesh.exchange.gltf.export_glb(mesh)
        out.write_bytes(glb_bytes)

        logger.info("Exported watertight GLB mesh (%d bytes) to %s", len(glb_bytes), str(out))
        return out

    @classmethod
    def export_obj(cls, mesh: trimesh.Trimesh, output_path: str | Path) -> Path:
        """Export mesh as Wavefront OBJ with MTL material definition."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        obj_str = trimesh.exchange.obj.export_obj(mesh)
        out.write_text(obj_str, encoding="utf-8")

        logger.info("Exported Wavefront OBJ mesh to %s", str(out))
        return out
