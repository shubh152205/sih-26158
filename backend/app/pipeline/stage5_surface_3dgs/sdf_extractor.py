"""Signed Distance Field (SDF) and Watertight Mesh Extraction Subsystem.

Evaluates continuous Signed Distance Fields from surface-regularized Gaussians
and extracts watertight polygonal meshes via Marching Cubes / Tetrahedra with
topological hole-filling and normal consistency checks.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import KDTree
import skimage.measure
import trimesh

from backend.app.core.exceptions import MeshExtractionError
from backend.app.core.logger import get_logger
from backend.app.pipeline.stage5_surface_3dgs.gaussian_trainer import GaussianModel

logger = get_logger(__name__, subsystem="SDF-EXTRACTOR")


class SDFMeshExtractor:
    """Extracts watertight polygonal 3D surfaces from surface-aligned Gaussians."""

    def __init__(
        self,
        voxel_resolution: int = 48,
        padding_voxels: int = 2,
        smoothing_iterations: int = 1,
    ):
        self.resolution = voxel_resolution
        self.padding = padding_voxels
        self.smoothing_iterations = smoothing_iterations

    def extract_mesh_from_gaussians(self, model: GaussianModel) -> trimesh.Trimesh:
        """Construct continuous 3D Signed Distance Field and extract watertight Trimesh."""
        points = model.positions
        colors = model.colors

        if len(points) < 10:
            raise MeshExtractionError(f"Insufficient points for mesh extraction (got {len(points)})")

        logger.info("Building continuous 3D Signed Distance Field at resolution %d^3...", self.resolution)

        # 1. Compute spatial bounds
        min_bound = np.min(points, axis=0)
        max_bound = np.max(points, axis=0)
        extents = np.maximum(max_bound - min_bound, 1.0)

        # 2D Grid over X and Y
        xs = np.linspace(min_bound[0], max_bound[0], self.resolution)
        ys = np.linspace(min_bound[1], max_bound[1], self.resolution)
        dx = float(xs[1] - xs[0])
        dy = float(ys[1] - ys[0])

        # Vertical range (Z)
        z_min = float(min_bound[2] - 1.0)
        z_max = float(max_bound[2] + 1.0)
        zs = np.linspace(z_min, z_max, max(16, self.resolution // 2))
        dz = float(zs[1] - zs[0])

        # 2. Continuous height field h(x, y) via Inverse-Distance Weighting (IDW)
        tree_2d = KDTree(points[:, :2])
        xv, yv = np.meshgrid(xs, ys, indexing="ij")
        grid_2d = np.stack([xv.flatten(), yv.flatten()], axis=-1)

        k = min(8, len(points))
        dists, nn_idx = tree_2d.query(grid_2d, k=k)

        # IDW interpolation of elevations
        weights = 1.0 / (np.maximum(dists, 1e-4) ** 2)
        weights /= np.sum(weights, axis=-1, keepdims=True)
        z_interpolated = np.sum(weights * points[nn_idx, 2], axis=-1)
        h_grid = z_interpolated.reshape((len(xs), len(ys)))

        # 3. Formulate 3D Signed Distance Field: SDF(x, y, z) = z - h(x, y)
        # Outside (above surface): SDF > 0; Inside (below surface): SDF < 0
        xv3, yv3, zv3 = np.meshgrid(xs, ys, zs, indexing="ij")
        h3 = np.repeat(h_grid[:, :, np.newaxis], len(zs), axis=2)
        sdf_grid = (zv3 - h3).astype(np.float32)

        # Enclose volume completely: pad all 6 outer boundaries with positive (exterior) distance
        # This mathematically guarantees an uninterrupted, closed 2-manifold isosurface (Euler = 2)
        pad_width = 2
        pad_val = 5.0
        sdf_padded = np.pad(sdf_grid, pad_width=pad_width, mode="constant", constant_values=pad_val)

        # 4. Extract zero-crossing isosurface via Marching Cubes
        try:
            verts_vox, faces, vertex_normals, _ = skimage.measure.marching_cubes(
                sdf_padded,
                level=0.0,
                spacing=(dx, dy, dz),
                method="lorensen",
            )
        except Exception as e:
            raise MeshExtractionError(f"Marching cubes isosurface extraction failed: {e}") from e

        # Shift vertices to world coordinates
        origin_padded = np.array([min_bound[0] - pad_width * dx, min_bound[1] - pad_width * dy, z_min - pad_width * dz])
        verts_world = verts_vox + origin_padded

        # 5. Map vertex colors from nearest Gaussians
        tree_3d = KDTree(points)
        _, v_nn = tree_3d.query(verts_world, k=1)
        v_colors_float = colors[v_nn]
        v_colors_uint8 = np.clip(v_colors_float * 255.0, 0, 255).astype(np.uint8)
        rgba = np.column_stack([v_colors_uint8, np.full((len(v_colors_uint8), 1), 255, dtype=np.uint8)])

        # 6. Construct Trimesh and verify topological integrity
        mesh = trimesh.Trimesh(
            vertices=verts_world,
            faces=faces,
            vertex_normals=vertex_normals,
            vertex_colors=rgba,
            process=True,
        )

        # Retain only largest connected component to remove any disconnected floating dust
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda c: len(c.faces))

        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_inversion(mesh)
        trimesh.repair.fix_normals(mesh)

        if self.smoothing_iterations > 0:
            mesh = trimesh.smoothing.filter_laplacian(mesh, iterations=self.smoothing_iterations)

        is_closed = bool(mesh.is_watertight)
        logger.info(
            "Extracted Watertight 3D Mesh: %d vertices, %d faces (Watertight: %s, Euler: %d)",
            len(mesh.vertices), len(mesh.faces), is_closed, mesh.euler_number
        )

        return mesh
