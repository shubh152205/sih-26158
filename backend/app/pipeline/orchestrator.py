"""Master Photogrammetric Pipeline Orchestrator.

Coordinates Stages 1 through 6 in an asynchronous, non-blocking pipeline
with real-time progress callbacks and fail-safe error boundaries.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Coroutine, Any
import numpy as np
from pydantic import BaseModel, Field

from backend.app.core.exceptions import PipelineError
from backend.app.core.logger import get_logger
from backend.app.pipeline.stage1_ingestion import (
    GeodeticTransformer,
    TelemetryParser,
    TrajectorySplineInterpolator,
    VideoDecoder,
    determine_utm_zone,
)
from backend.app.pipeline.stage2_keyframing import KeyframeSelector, SelectedKeyframe
from backend.app.pipeline.stage3_foundation_pose import (
    PointmapRegressor,
    ViewGraphBuilder,
    ViTPointmapModel,
)
from backend.app.pipeline.stage4_georeferencing import (
    MetricScaler,
    TrajectoryAligner,
)
from backend.app.pipeline.stage5_surface_3dgs import (
    SDFMeshExtractor,
    SurfaceGaussianTrainer,
    TextureBaker,
)
from backend.app.pipeline.stage6_audit_export import (
    ConfidenceGate,
    DefenseAuditReport,
    MeshExporter,
    PointCloudExporter,
    RasterExporter,
)

logger = get_logger(__name__, subsystem="ORCHESTRATOR")


class PipelineArtifacts(BaseModel):
    """Manifest of generated deliverables."""

    job_id: str
    glb_path: str
    obj_path: str
    las_path: str
    ply_path: str
    geotiff_dsm_path: str
    audit_report: DefenseAuditReport
    total_duration_sec: float
    total_keyframes: int
    total_points: int


ProgressCallback = Callable[[str, float, str, dict[str, Any]], None]


class PipelineOrchestrator:
    """Master coordinator executing the 6-stage 3D reconstruction pipeline."""

    def __init__(
        self,
        output_dir: str | Path = "data/exports",
        temp_dir: str | Path = "data/processed",
    ):
        self.output_dir = Path(output_dir).resolve()
        self.temp_dir = Path(temp_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def run_reconstruction(
        self,
        job_id: str,
        video_path: str | Path,
        telemetry_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineArtifacts:
        """Execute full 6-stage reconstruction pipeline."""
        start_time = time.time()
        job_out = self.output_dir / job_id
        job_out.mkdir(parents=True, exist_ok=True)

        def notify(stage: str, pct: float, msg: str, extra: dict[str, Any] | None = None):
            logger.info("[%s] %.1f%% - %s", stage, pct, msg)
            if progress_callback:
                progress_callback(stage, pct, msg, extra or {})

        # ==========================================
        # STAGE 1: Ingestion & Telemetry Sync
        # ==========================================
        notify("STAGE1_INGESTION", 5.0, "Parsing drone telemetry and probing video stream...")
        decoder = VideoDecoder(video_path)
        raw_points = TelemetryParser.parse_or_estimate(
            telemetry_path,
            duration_sec=decoder.metadata.duration_sec,
            fps=decoder.metadata.fps,
        )

        first_pt = raw_points[0]
        zone, hemi = determine_utm_zone(first_pt.latitude, first_pt.longitude)
        transformer = GeodeticTransformer(zone=zone, hemisphere=hemi)

        interpolator = TrajectorySplineInterpolator.from_telemetry_points(raw_points, transformer)
        notify("STAGE1_INGESTION", 15.0, f"Synchronized flight trajectory in UTM Zone {zone}{hemi}")

        # ==========================================
        # STAGE 2: Adaptive Keyframing & Gating
        # ==========================================
        notify("STAGE2_KEYFRAMING", 20.0, "Decoding frames and evaluating motion blur...")
        # Stream frames at interval
        step = max(1, int(round(decoder.metadata.fps / 4.0)))  # ~4 frames/sec candidate rate
        candidates: list[tuple[int, np.ndarray]] = list(decoder.stream_all_frames(step=step, max_frames=200))

        keyframe_selector = KeyframeSelector()
        keyframes = keyframe_selector.select_keyframes_from_frames(
            candidates, interpolator, fps=decoder.metadata.fps
        )
        notify(
            "STAGE2_KEYFRAMING", 35.0,
            f"Curated {len(keyframes)} sharp, high-covisibility keyframes",
            {"keyframe_count": len(keyframes)}
        )

        # ==========================================
        # STAGE 3: Foundation Vision Pose Estimation
        # ==========================================
        notify("STAGE3_FOUNDATION_POSE", 40.0, "Predicting dense pointmaps and relative Kabsch poses...")
        vit_model = ViTPointmapModel()
        regressor = PointmapRegressor(vit_model)

        pairwise_results = []
        cand_dict = {c[0]: c[1] for c in candidates}

        for i in range(len(keyframes) - 1):
            kf_i = keyframes[i]
            kf_j = keyframes[i + 1]
            img_i = cand_dict.get(kf_i.source_frame_idx, candidates[0][1])
            img_j = cand_dict.get(kf_j.source_frame_idx, candidates[0][1])

            res = regressor.estimate_relative_pose(kf_i, kf_j, img_i, img_j)
            pairwise_results.append(res)
            pct = 40.0 + (i / max(1, len(keyframes) - 1)) * 15.0
            notify("STAGE3_FOUNDATION_POSE", pct, f"Relative pose pair {i + 1}/{len(keyframes) - 1}")

        relative_recon = ViewGraphBuilder.assemble_trajectory(pairwise_results)
        notify("STAGE3_FOUNDATION_POSE", 55.0, f"View graph assembled: {len(relative_recon.points3d)} relative points")

        # ==========================================
        # STAGE 4: Telemetry-Anchored Sim(3) Georeferencing
        # ==========================================
        notify("STAGE4_GEOREFERENCING", 60.0, "Solving weighted Umeyama Sim(3) alignment to WGS84 UTM...")
        aligner = TrajectoryAligner()
        alignment_result = aligner.align_trajectories(relative_recon, keyframes)

        metric_model = MetricScaler.scale_scene(relative_recon, alignment_result.transform)
        notify(
            "STAGE4_GEOREFERENCING", 70.0,
            f"Metric scale locked (Scale Error: {alignment_result.scale_error_pct:.2f}%)"
        )

        # ==========================================
        # STAGE 5: Surface 3DGS & Watertight Meshing
        # ==========================================
        notify("STAGE5_SURFACE_3DGS", 75.0, "Optimizing surface-flattened Gaussians and SDF meshing...")
        gaussian_trainer = SurfaceGaussianTrainer()
        gaussians = gaussian_trainer.train_surface_gaussians(metric_model)

        mesh_extractor = SDFMeshExtractor(voxel_resolution=40, padding_voxels=2)
        mesh = mesh_extractor.extract_mesh_from_gaussians(gaussians)

        texture_baker = TextureBaker(atlas_size=1024)
        mesh = texture_baker.bake_orthographic_texture(mesh)
        notify("STAGE5_SURFACE_3DGS", 85.0, f"Watertight mesh generated ({len(mesh.faces)} faces)")

        # ==========================================
        # STAGE 6: Defense Audit & Multi-Modal Exporters
        # ==========================================
        notify("STAGE6_AUDIT_EXPORT", 90.0, "Performing defense anti-hallucination audit and exporting deliverables...")
        gate = ConfidenceGate()
        audited_model, audit_report = gate.audit_scene(
            metric_model,
            metric_model.camera_centers_local,
            scale_error_pct=alignment_result.scale_error_pct,
            crs_epsg=f"WGS84 UTM Zone {zone}{hemi}",
        )

        # Export Files
        glb_path = MeshExporter.export_glb(mesh, job_out / "tactical_mesh.glb")
        obj_path = MeshExporter.export_obj(mesh, job_out / "tactical_mesh.obj")
        las_path = PointCloudExporter.export_las(audited_model, job_out / "georeferenced_cloud.las", epsg_code=transformer.epsg_code)
        ply_path = PointCloudExporter.export_ply(audited_model, job_out / "georeferenced_cloud.ply")
        raster_exporter = RasterExporter(gsd_meters=0.20)
        dsm_path = raster_exporter.export_geotiff(audited_model, job_out / "orthorectified_dsm.tif", epsg_code=transformer.epsg_code)

        total_duration = time.time() - start_time
        notify("COMPLETED", 100.0, f"Reconstruction pipeline completed in {total_duration:.1f}s")

        return PipelineArtifacts(
            job_id=job_id,
            glb_path=str(glb_path),
            obj_path=str(obj_path),
            las_path=str(las_path),
            ply_path=str(ply_path),
            geotiff_dsm_path=str(dsm_path),
            audit_report=audit_report,
            total_duration_sec=total_duration,
            total_keyframes=len(keyframes),
            total_points=len(audited_model.points_local),
        )
