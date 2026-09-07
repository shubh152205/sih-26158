"""Unit tests for Stage 2: Adaptive Keyframing, Blur Gating, and Covisibility Flow."""

import math
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from backend.app.pipeline.stage1_ingestion.spline_interpolator import TrajectorySplineInterpolator
from backend.app.pipeline.stage2_keyframing.blur_detector import BlurDetector
from backend.app.pipeline.stage2_keyframing.flow_estimator import OpticalFlowEstimator
from backend.app.pipeline.stage2_keyframing.keyframe_selector import KeyframeSelector


class TestBlurDetector:
    def test_sharp_vs_blurred_discrimination(self):
        # Create high-contrast checkerboard image
        h, w = 128, 128
        y, x = np.ogrid[:h, :w]
        checker = ((x // 16) + (y // 16)) % 2
        sharp_img = (checker * 255).astype(np.uint8)
        sharp_rgb = np.stack([sharp_img, sharp_img, sharp_img], axis=-1)

        # Create heavily blurred version
        blurred_img = gaussian_filter(sharp_img.astype(np.float32), sigma=4.0).astype(np.uint8)
        blurred_rgb = np.stack([blurred_img, blurred_img, blurred_img], axis=-1)

        detector = BlurDetector(base_sharpness_threshold=50.0)
        score_sharp = detector.compute_sharpness(sharp_rgb)
        score_blurred = detector.compute_sharpness(blurred_rgb)

        assert score_sharp > score_blurred * 5.0
        assert score_sharp > 50.0

    def test_threshold_relaxation(self):
        detector = BlurDetector(base_sharpness_threshold=1000.0, min_retained_frames=5)
        # Low scores that would fail a strict 1000 threshold
        scores = [120.0, 110.0, 130.0, 105.0, 125.0, 115.0, 40.0, 30.0]
        indices = list(range(len(scores)))

        retained, eff_thresh = detector.filter_sharp_frames(indices, scores)
        assert len(retained) >= 5
        assert eff_thresh < 1000.0


class TestFlowEstimator:
    def test_flow_zero_for_identical_frames(self):
        estimator = OpticalFlowEstimator()
        img = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)

        disp, covis = estimator.compute_flow_and_covisibility(img, img)
        assert math.isclose(disp, 0.0, abs_tol=1e-2)
        assert math.isclose(covis, 1.0, abs_tol=1e-2)

    def test_flow_magnitude_on_translation(self):
        estimator = OpticalFlowEstimator()
        # Textured image translated horizontally by 8 pixels
        img1 = np.zeros((128, 128, 3), dtype=np.uint8)
        img1[32:96, 32:96] = 200

        img2 = np.zeros((128, 128, 3), dtype=np.uint8)
        img2[32:96, 40:104] = 200  # Shifted 8 pixels right

        disp, covis = estimator.compute_flow_and_covisibility(img1, img2)
        assert disp > 0.5
        assert covis < 1.0


class TestKeyframeSelector:
    def test_keyframe_selection_pipeline(self):
        times = np.linspace(0.0, 5.0, 20)
        eastings = 500000.0 + 10.0 * times
        northings = 3000000.0 + np.zeros_like(times)
        altitudes = 100.0 + np.zeros_like(times)

        interp = TrajectorySplineInterpolator(
            timestamps_sec=times,
            eastings=eastings,
            northings=northings,
            altitudes=altitudes,
            rolls_deg=np.zeros_like(times),
            pitches_deg=-15.0 * np.ones_like(times),
            yaws_deg=90.0 * np.ones_like(times),
        )

        # Generate 20 test frames with gentle horizontal shift
        frames = []
        for i in range(20):
            frame = np.zeros((128, 128, 3), dtype=np.uint8)
            col_start = (i * 4) % 80
            frame[30:90, col_start : col_start + 40] = 220
            frames.append((i, frame))

        selector = KeyframeSelector(base_sharpness_threshold=10.0, target_keyframes=5)
        selected = selector.select_keyframes_from_frames(frames, interp, fps=4.0)

        assert len(selected) >= 2
        # First keyframe should be index 0
        assert selected[0].source_frame_idx == 0
        # Poses should be populated with UTM coordinates
        assert selected[0].pose.utm_easting >= 500000.0
