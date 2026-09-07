"""Unit tests for Stage 5 (Surface 3DGS & SDF Meshing) and Stage 6 (Defense Audit & Exporters)."""

import math
import os
import tempfile
from pathlib import Path
import numpy as np
import pytest

from backend.app.pipeline.stage4_georeferencing.metric_scaler import MetricSceneModel
from backend.app.pipeline.stage5_surface_3dgs.gaussian_trainer import SurfaceGaussianTrainer
from backend.app.pipeline.stage5_surface_3dgs.sdf_extractor import SDFMeshExtractor
from backend.app.pipeline.stage5_surface_3dgs.texture_baker import TextureBaker
from backend.app.pipeline.stage6_audit_export.confidence_gate import ConfidenceGate
from backend.app.pipeline.stage6_audit_export.mesh_exporter import MeshExporter
from backend.app.pipeline.stage6_audit_export.pointcloud_exporter import PointCloudExporter
from backend.app.pipeline.stage6_audit_export.raster_exporter import RasterExporter


@pytest.fixture
def sample_metric_model():
    """Generates synthetic planar terrain with a central structure."""
    np.random.seed(42)
    # 20x20 grid points
    xs, ys = np.meshgrid(np.linspace(-10, 10, 20), np.linspace(-10, 10, 20))
    pts_local = np.stack([xs.flatten(), ys.flatten(), np.zeros(400)], axis=-1).astype(np.float32)
    # Add a raised central mound
    dists = np.hypot(pts_local[:, 0], pts_local[:, 1])
    pts_local[:, 2] = np.maximum(0.0, 3.0 - 0.3 * dists)

    pts_utm = pts_local.astype(np.float64) + np.array([717000.0, 3166000.0, 200.0])
    colors = np.ones((400, 3), dtype=np.float32) * 0.6
    confs = np.random.uniform(0.7, 0.95, 400).astype(np.float32)

    cam_centers = np.array([
        [-5.0, -5.0, 20.0],
        [0.0, 0.0, 20.0],
        [5.0, 5.0, 20.0],
    ], dtype=np.float32)

    return MetricSceneModel(
        points_local=pts_local,
        points_utm=pts_utm,
        colors=colors,
        confidences=confs,
        anchor_origin=np.array([717000.0, 3166000.0, 200.0]),
        bounding_box_meters={"min_x": -10, "max_x": 10, "min_y": -10, "max_y": 10, "min_z": 0, "max_z": 3},
        camera_centers_local=cam_centers,
    )


class TestSurface3DGSAndMeshing:
    def test_surface_gaussian_trainer(self, sample_metric_model):
        trainer = SurfaceGaussianTrainer(flatness_ratio=0.08)
        gaussians = trainer.train_surface_gaussians(sample_metric_model)

        assert len(gaussians) == 400
        # Normal vectors should point upwards (+Z >= 0)
        assert np.all(gaussians.normals[:, 2] >= -1e-4)
        # Thickness s3 should be significantly smaller than principal axes
        mean_thickness = np.mean(gaussians.scales[:, 2])
        mean_span = np.mean(gaussians.scales[:, 0])
        assert mean_thickness < mean_span * 0.3

    def test_watertight_mesh_extraction(self, sample_metric_model):
        trainer = SurfaceGaussianTrainer()
        gaussians = trainer.train_surface_gaussians(sample_metric_model)

        extractor = SDFMeshExtractor(voxel_resolution=24, padding_voxels=2)
        mesh = extractor.extract_mesh_from_gaussians(gaussians)

        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0
        assert mesh.is_watertight

    def test_texture_baking(self, sample_metric_model):
        trainer = SurfaceGaussianTrainer()
        gaussians = trainer.train_surface_gaussians(sample_metric_model)
        extractor = SDFMeshExtractor(voxel_resolution=20, padding_voxels=2)
        mesh = extractor.extract_mesh_from_gaussians(gaussians)

        baker = TextureBaker(atlas_size=128)
        textured_mesh = baker.bake_orthographic_texture(mesh)

        assert textured_mesh.visual is not None
        assert textured_mesh.visual.uv is not None
        assert len(textured_mesh.visual.uv) == len(textured_mesh.vertices)


class TestDefenseAuditAndExporters:
    def test_confidence_gating_report(self, sample_metric_model):
        gate = ConfidenceGate(min_ray_observations=2, min_confidence_threshold=0.5)
        filtered_model, report = gate.audit_scene(
            sample_metric_model,
            sample_metric_model.camera_centers_local,
            scale_error_pct=1.8,
        )

        assert report.anti_hallucination_compliant
        assert report.metric_scale_confirmed
        assert report.observation_coverage_pct > 50.0
        assert len(filtered_model.points_local) > 0

    def test_export_all_deliverables(self, sample_metric_model):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 1. Mesh Export (.glb and .obj)
            trainer = SurfaceGaussianTrainer()
            gaussians = trainer.train_surface_gaussians(sample_metric_model)
            extractor = SDFMeshExtractor(voxel_resolution=20, padding_voxels=2)
            mesh = extractor.extract_mesh_from_gaussians(gaussians)

            glb_file = MeshExporter.export_glb(mesh, tmp_path / "model.glb")
            obj_file = MeshExporter.export_obj(mesh, tmp_path / "model.obj")
            assert glb_file.is_file()
            assert glb_file.stat().st_size > 100
            assert obj_file.is_file()

            # 2. Point Cloud Export (.las and .ply)
            las_file = PointCloudExporter.export_las(sample_metric_model, tmp_path / "cloud.las")
            ply_file = PointCloudExporter.export_ply(sample_metric_model, tmp_path / "cloud.ply")
            assert las_file.is_file()
            assert las_file.stat().st_size > 100
            assert ply_file.is_file()

            # 3. GeoTIFF Export (.tif)
            raster_exporter = RasterExporter(gsd_meters=1.0)
            tif_file = raster_exporter.export_geotiff(sample_metric_model, tmp_path / "dsm.tif")
            assert tif_file.is_file()
            assert tif_file.stat().st_size > 100
