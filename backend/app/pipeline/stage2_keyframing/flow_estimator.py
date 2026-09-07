"""Optical Flow and Parallax Covisibility Estimation Subsystem.

Computes visual parallax displacement between frame candidates to maintain
optimal baseline-to-height ratio (b/H in [0.10, 0.25]) and 60%-80% covisibility.
Supports OpenCV DIS Optical Flow with an analytical 2D spatial gradient fallback.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="FLOW-ESTIMATOR")


class OpticalFlowEstimator:
    """Displacement and visual overlap tracker between sequential video frames."""

    def __init__(self, target_downscale: tuple[int, int] = (256, 144)):
        self.downscale_w, self.downscale_h = target_downscale
        self._has_cv2 = False
        try:
            import cv2
            self._cv2 = cv2
            self._dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
            self._has_cv2 = True
        except ImportError:
            self._has_cv2 = False

    def downscale_luminance(self, frame_rgb: np.ndarray) -> np.ndarray:
        """Fast bilinear downscale and luminance extraction to fixed low-res grid."""
        h, w = frame_rgb.shape[:2]
        # Luminance
        if frame_rgb.ndim == 3:
            gray = 0.2126 * frame_rgb[:, :, 0] + 0.7152 * frame_rgb[:, :, 1] + 0.0722 * frame_rgb[:, :, 2]
        else:
            gray = frame_rgb.astype(np.float32)

        # Vectorized block sampling
        step_y = max(1, h // self.downscale_h)
        step_x = max(1, w // self.downscale_w)
        sampled = gray[::step_y, ::step_x][: self.downscale_h, : self.downscale_w]
        return sampled.astype(np.float32)

    def compute_flow_and_covisibility(
        self, frame1_rgb: np.ndarray, frame2_rgb: np.ndarray
    ) -> tuple[float, float]:
        """Compute mean pixel displacement magnitude and estimated visual covisibility ratio.

        Returns:
            Tuple of (mean_displacement_pixels, covisibility_ratio in [0, 1]).
        """
        if self._has_cv2:
            try:
                gray1 = self._cv2.cvtColor(frame1_rgb, self._cv2.COLOR_RGB2GRAY)
                gray2 = self._cv2.cvtColor(frame2_rgb, self._cv2.COLOR_RGB2GRAY)
                g1_small = self._cv2.resize(gray1, (self.downscale_w, self.downscale_h))
                g2_small = self._cv2.resize(gray2, (self.downscale_w, self.downscale_h))

                flow = self._dis.calc(g1_small, g2_small, None)
                mag = np.linalg.norm(flow, axis=-1)
                mean_disp = float(np.mean(mag))

                # Normalize displacement against frame diagonal
                diag = np.hypot(self.downscale_w, self.downscale_h)
                covisibility = float(max(0.0, min(1.0, 1.0 - (mean_disp / (0.6 * diag)))))
                return mean_disp, covisibility
            except Exception as e:
                logger.debug("OpenCV DIS flow failed (%s); falling back to analytical gradient", str(e))

        # Analytical Lucas-Kanade with Tikhonov regularization & Phase Correlation
        return self._analytical_flow(frame1_rgb, frame2_rgb)

    def _analytical_flow(
        self, frame1_rgb: np.ndarray, frame2_rgb: np.ndarray
    ) -> tuple[float, float]:
        """Vectorized spatial-temporal gradient optical flow with Tikhonov regularization."""
        i1 = self.downscale_luminance(frame1_rgb)
        i2 = self.downscale_luminance(frame2_rgb)

        # 1. Fourier Phase Correlation for global translational shift
        f1 = np.fft.fft2(i1)
        f2 = np.fft.fft2(i2)
        cross_power = (f1 * np.conj(f2)) / (np.abs(f1 * np.conj(f2)) + 1e-7)
        corr = np.fft.ifft2(cross_power).real
        corr = np.fft.fftshift(corr)

        cy, cx = np.unravel_index(np.argmax(corr), corr.shape)
        shift_y = cy - (corr.shape[0] // 2)
        shift_x = cx - (corr.shape[1] // 2)
        phase_disp = float(np.hypot(shift_x, shift_y))

        # 2. Local Lucas-Kanade gradients
        ix = 0.5 * (np.roll(i1, -1, axis=1) - np.roll(i1, 1, axis=1))
        iy = 0.5 * (np.roll(i1, -1, axis=0) - np.roll(i1, 1, axis=0))
        it = i2 - i1

        win_size = 7
        ixx = uniform_filter(ix * ix, size=win_size)
        iyy = uniform_filter(iy * iy, size=win_size)
        ixy = uniform_filter(ix * iy, size=win_size)
        ixt = uniform_filter(ix * it, size=win_size)
        iyt = uniform_filter(iy * it, size=win_size)

        # Tikhonov regularized 2x2 matrix inversion: (J^T J + lambda * I)^-1
        reg = 1.0
        det = (ixx + reg) * (iyy + reg) - ixy * ixy
        inv_00 = (iyy + reg) / det
        inv_11 = (ixx + reg) / det
        inv_01 = -ixy / det

        u = -(inv_00 * ixt + inv_01 * iyt)
        v = -(inv_01 * ixt + inv_11 * iyt)

        mag = np.hypot(u, v)
        grad_disp = float(np.mean(np.clip(mag, 0.0, 50.0)))

        # Fuse phase correlation and gradient magnitude
        mean_disp = max(phase_disp, grad_disp)

        diag = np.hypot(self.downscale_w, self.downscale_h)
        covisibility = float(max(0.0, min(1.0, 1.0 - (mean_disp / (0.4 * diag)))))
        return mean_disp, covisibility
