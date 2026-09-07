"""Adaptive Keyframe Selector Subsystem.

Balances baseline progress, motion sharpness, and visual covisibility (60%-80%)
to curate optimal keyframe sequences from raw UAV video.
"""

from __future__ import annotations

import math
from typing import List, Sequence
import numpy as np
from pydantic import BaseModel, Field

from backend.app.core.exceptions import KeyframingError
from backend.app.core.logger import get_logger
from backend.app.pipeline.stage1_ingestion.spline_interpolator import TrajectorySplineInterpolator
from backend.app.pipeline.stage1_ingestion.video_decoder import VideoDecoder
from backend.app.pipeline.stage2_keyframing.blur_detector import BlurDetector
from backend.app.pipeline.stage2_keyframing.flow_estimator import OpticalFlowEstimator
from backend.app.schemas.telemetry import SynchronizedPose

logger = get_logger(__name__, subsystem="KEYFRAME-SELECTOR")


class SelectedKeyframe(BaseModel):
    """Metadata and telemetry record for a curated reconstruction keyframe."""

    keyframe_idx: int = Field(..., description="0-indexed keyframe order in selected sequence")
    source_frame_idx: int = Field(..., description="Original raw video frame index")
    timestamp_sec: float
    sharpness_score: float
    flow_displacement: float
    covisibility_with_prev: float
    pose: SynchronizedPose


class KeyframeSelector:
    """Intelligent adaptive keyframe selection controller."""

    def __init__(
        self,
        min_covisibility: float = 0.55,
        max_covisibility: float = 0.85,
        target_keyframes: int = 150,
        base_sharpness_threshold: float = 80.0,
    ):
        self.min_covisibility = min_covisibility
        self.max_covisibility = max_covisibility
        self.target_keyframes = target_keyframes
        self.blur_detector = BlurDetector(base_sharpness_threshold=base_sharpness_threshold)
        self.flow_estimator = OpticalFlowEstimator()

    def select_keyframes_from_frames(
        self,
        frames: Sequence[tuple[int, np.ndarray]],
        spline_interp: TrajectorySplineInterpolator,
        fps: float,
    ) -> list[SelectedKeyframe]:
        """Curate keyframes given in-memory sequence of (frame_idx, rgb_array)."""
        if len(frames) < 2:
            raise KeyframingError(f"Insufficient frames for keyframing (got {len(frames)})")

        logger.info("Evaluating sharpness across %d candidate frames...", len(frames))
        frame_indices = [f[0] for f in frames]
        sharpness_scores = [self.blur_detector.compute_sharpness(f[1]) for f in frames]

        # Filter sharp frames with adaptive relaxation
        sharp_indices, eff_thresh = self.blur_detector.filter_sharp_frames(
            frame_indices, sharpness_scores
        )
        sharp_indices_set = set(sharp_indices)

        # Filter candidate list to sharp frames only
        sharp_frames = [f for f in frames if f[0] in sharp_indices_set]
        if not sharp_frames:
            raise KeyframingError("All candidate frames rejected by sharpness filter")

        # Covisibility and baseline gating
        selected: list[SelectedKeyframe] = []
        # Anchor the very first sharp frame
        first_idx, first_img = sharp_frames[0]
        first_pose = spline_interp.evaluate_at_time(first_idx / fps, frame_idx=first_idx)
        first_score = sharpness_scores[frame_indices.index(first_idx)]

        selected.append(
            SelectedKeyframe(
                keyframe_idx=0,
                source_frame_idx=first_idx,
                timestamp_sec=first_idx / fps,
                sharpness_score=first_score,
                flow_displacement=0.0,
                covisibility_with_prev=1.0,
                pose=first_pose,
            )
        )

        last_img = first_img
        last_idx = first_idx

        # Iterate through candidate sharp frames
        for f_idx, f_img in sharp_frames[1:]:
            disp, covis = self.flow_estimator.compute_flow_and_covisibility(last_img, f_img)
            t_sec = f_idx / fps

            # Compute metric baseline distance using interpolated poses
            curr_pose = spline_interp.evaluate_at_time(t_sec, frame_idx=f_idx)
            prev_pose = selected[-1].pose
            baseline_dist = math.sqrt(
                (curr_pose.utm_easting - prev_pose.utm_easting) ** 2
                + (curr_pose.utm_northing - prev_pose.utm_northing) ** 2
                + (curr_pose.utm_altitude - prev_pose.utm_altitude) ** 2
            )

            # Keyframe acceptance criteria:
            # 1. Parallax is sufficient (covisibility dropped below max_covisibility OR baseline > 2.0 meters)
            # 2. Covisibility has NOT collapsed completely (covisibility > min_covisibility OR frame delta > 60)
            should_select = (
                (covis <= self.max_covisibility and covis >= self.min_covisibility)
                or (baseline_dist >= 3.0 and covis >= 0.40)
                or (f_idx - last_idx >= 45)  # Enforce maximum frame spacing gap
            )

            if should_select:
                score = sharpness_scores[frame_indices.index(f_idx)]
                selected.append(
                    SelectedKeyframe(
                        keyframe_idx=len(selected),
                        source_frame_idx=f_idx,
                        timestamp_sec=t_sec,
                        sharpness_score=score,
                        flow_displacement=disp,
                        covisibility_with_prev=covis,
                        pose=curr_pose,
                    )
                )
                last_img = f_img
                last_idx = f_idx

        # Ensure last frame is included for loop / endpoint closure
        last_cand_idx, last_cand_img = sharp_frames[-1]
        if selected[-1].source_frame_idx != last_cand_idx:
            t_sec = last_cand_idx / fps
            pose = spline_interp.evaluate_at_time(t_sec, frame_idx=last_cand_idx)
            disp, covis = self.flow_estimator.compute_flow_and_covisibility(last_img, last_cand_img)
            score = sharpness_scores[frame_indices.index(last_cand_idx)]
            selected.append(
                SelectedKeyframe(
                    keyframe_idx=len(selected),
                    source_frame_idx=last_cand_idx,
                    timestamp_sec=t_sec,
                    sharpness_score=score,
                    flow_displacement=disp,
                    covisibility_with_prev=covis,
                    pose=pose,
                )
            )

        logger.info(
            "Selected %d high-quality keyframes from %d raw candidates (retention: %.1f%%)",
            len(selected), len(frames), (len(selected) / len(frames)) * 100.0
        )
        return selected
