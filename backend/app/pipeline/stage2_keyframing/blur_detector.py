"""Adaptive Motion Blur and Sharpness Detection Subsystem.

Computes the variance of the 2D Laplacian operator (sigma_L^2) across candidate
video frames to eliminate jittered, rolling-shutter distorted, and blurred images.
Supports dynamic threshold relaxation to guarantee minimal reconstruction continuity.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import convolve2d

from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="BLUR-DETECTOR")

# Discrete 3x3 Laplacian discrete kernel
LAPLACIAN_KERNEL = np.array(
    [[0.0, 1.0, 0.0],
     [1.0, -4.0, 1.0],
     [0.0, 1.0, 0.0]],
    dtype=np.float32,
)


class BlurDetector:
    """Laplacian variance sharpness estimator with adaptive thresholding."""

    def __init__(self, base_sharpness_threshold: float = 100.0, min_retained_frames: int = 60):
        self.base_threshold = base_sharpness_threshold
        self.min_retained_frames = min_retained_frames

    @staticmethod
    def rgb_to_grayscale(frame_rgb: np.ndarray) -> np.ndarray:
        """Convert RGB image (H, W, 3) to single-channel luminance (H, W) in float32."""
        if frame_rgb.ndim == 2:
            return frame_rgb.astype(np.float32)
        # Rec. 709 ITU luminance coefficients
        return (
            0.2126 * frame_rgb[:, :, 0]
            + 0.7152 * frame_rgb[:, :, 1]
            + 0.0722 * frame_rgb[:, :, 2]
        ).astype(np.float32)

    def compute_sharpness(self, frame_rgb: np.ndarray) -> float:
        """Compute the variance of the Laplacian over the frame.
        
        A higher variance indicates sharp edges; low variance indicates blur.
        """
        gray = self.rgb_to_grayscale(frame_rgb)

        # For speed on large 4K images, subsample center patch (e.g. 1024x1024)
        h, w = gray.shape
        if h > 1080 or w > 1920:
            ch, cw = h // 2, w // 2
            h_crop = min(h, 1024) // 2
            w_crop = min(w, 1024) // 2
            patch = gray[ch - h_crop : ch + h_crop, cw - w_crop : cw + w_crop]
        else:
            patch = gray

        # Fast 2D discrete Laplacian convolution
        laplacian = convolve2d(patch, LAPLACIAN_KERNEL, mode="valid", boundary="symm")
        var_l = float(np.var(laplacian))
        return var_l

    def filter_sharp_frames(
        self, frame_indices: list[int], sharpness_scores: list[float]
    ) -> tuple[list[int], float]:
        """Filter frame indices against threshold with fail-safe relaxation.

        If the base threshold eliminates > 90% of frames or drops below min_retained_frames,
        the threshold is iteratively relaxed by 20% until adequate continuity is preserved.

        Returns:
            Tuple of (retained_indices, effective_threshold).
        """
        if not frame_indices:
            return [], self.base_threshold

        total_input = len(frame_indices)
        threshold = self.base_threshold
        scores_arr = np.array(sharpness_scores, dtype=np.float32)
        indices_arr = np.array(frame_indices, dtype=np.int32)

        # Relaxation loop
        for attempt in range(15):
            mask = scores_arr >= threshold
            retained_count = int(np.sum(mask))

            target_min = min(self.min_retained_frames, max(2, int(total_input * 0.2)))
            if retained_count >= target_min or threshold < 5.0:
                logger.info(
                    "Retained %d / %d frames (effective blur threshold: %.1f, attempts: %d)",
                    retained_count, total_input, threshold, attempt
                )
                return indices_arr[mask].tolist(), threshold

            # Relax threshold by 20%
            threshold *= 0.80

        # Fallback: top N sharpest frames
        k = min(len(frame_indices), self.min_retained_frames)
        top_k_indices = np.argsort(-scores_arr)[:k]
        sorted_k = np.sort(indices_arr[top_k_indices]).tolist()
        logger.warning(
            "Forced fallback to top %d sharpest frames (min score: %.1f)",
            len(sorted_k), float(np.min(scores_arr[top_k_indices]))
        )
        return sorted_k, float(threshold)
