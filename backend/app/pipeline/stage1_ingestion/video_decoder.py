"""High-Throughput Video Decoding and Metadata Ingestion Subsystem.

Provides zero-copy / streaming frame decoding using FFmpeg with optional
NVIDIA NVDEC hardware acceleration, extracting raw RGB24 frames and precise
temporal metadata without frame dropping.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Generator, Sequence
import numpy as np
from PIL import Image

from backend.app.core.exceptions import PipelineError
from backend.app.core.logger import get_logger

logger = get_logger(__name__, subsystem="VIDEO-DECODER")


class VideoMetadata:
    """Detailed video stream parameters."""

    def __init__(
        self,
        width: int,
        height: int,
        fps: float,
        total_frames: int,
        duration_sec: float,
        codec_name: str,
        file_size_bytes: int,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.total_frames = total_frames
        self.duration_sec = duration_sec
        self.codec_name = codec_name
        self.file_size_bytes = file_size_bytes

    def to_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 3),
            "total_frames": self.total_frames,
            "duration_sec": round(self.duration_sec, 3),
            "codec_name": self.codec_name,
            "file_size_mb": round(self.file_size_bytes / (1024 * 1024), 2),
        }


class VideoDecoder:
    """High-speed frame extractor and video stream inspector."""

    def __init__(self, video_path: str | Path, use_nvdec: bool = False):
        self.path = Path(video_path).resolve()
        if not self.path.is_file():
            raise PipelineError(f"Video file not found: {self.path}", stage="STAGE1_INGESTION")

        self.use_nvdec = use_nvdec
        self.metadata = self._probe_metadata()

    def _probe_metadata(self) -> VideoMetadata:
        """Query stream parameters via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration,codec_name",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(self.path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            stream = data["streams"][0]
            fmt = data.get("format", {})

            width = int(stream["width"])
            height = int(stream["height"])

            # Compute precise FPS from fractional representation (e.g., "30000/1001" or "30/1")
            r_fps = stream.get("r_frame_rate", "30/1")
            num, den = map(float, r_fps.split("/"))
            fps = num / den if den > 0 else 30.0

            # Duration
            duration_sec = float(stream.get("duration") or fmt.get("duration") or 0.0)

            # Total frames
            nb_frames = stream.get("nb_frames")
            if nb_frames and nb_frames.isdigit():
                total_frames = int(nb_frames)
            elif duration_sec > 0:
                total_frames = int(round(duration_sec * fps))
            else:
                total_frames = 0

            codec = stream.get("codec_name", "unknown")
            file_size = int(fmt.get("size", self.path.stat().st_size))

            logger.info(
                "Probed video: %dx%d @ %.2f fps, %d frames (%.1fs), codec=%s",
                width, height, fps, total_frames, duration_sec, codec
            )

            return VideoMetadata(
                width=width,
                height=height,
                fps=fps,
                total_frames=total_frames,
                duration_sec=duration_sec,
                codec_name=codec,
                file_size_bytes=file_size,
            )
        except Exception as e:
            raise PipelineError(f"Failed to probe video {self.path}: {e}", stage="STAGE1_INGESTION") from e

    def extract_frame_at_index(self, frame_idx: int) -> np.ndarray:
        """Extract a single frame by exact index as an RGB numpy array (H, W, 3)."""
        pts_sec = frame_idx / self.metadata.fps
        cmd = ["ffmpeg", "-ss", f"{pts_sec:.4f}", "-i", str(self.path)]
        if self.use_nvdec:
            cmd = ["ffmpeg", "-hwaccel", "nvdec", "-ss", f"{pts_sec:.4f}", "-i", str(self.path)]

        cmd.extend([
            "-frames:v", "1",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-v", "error",
            "pipe:1",
        ])

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        expected_bytes = self.metadata.width * self.metadata.height * 3
        if len(proc.stdout) < expected_bytes:
            raise PipelineError(
                f"Failed to extract frame {frame_idx}: expected {expected_bytes} bytes, received {len(proc.stdout)}",
                stage="STAGE1_INGESTION",
            )

        frame = np.frombuffer(proc.stdout[:expected_bytes], dtype=np.uint8)
        return frame.reshape((self.metadata.height, self.metadata.width, 3))

    def stream_all_frames(
        self, step: int = 1, max_frames: int | None = None
    ) -> Generator[tuple[int, np.ndarray], None, None]:
        """Stream sequential frames with step downsampling.

        Yields:
            Tuple of (frame_index, rgb_array).
        """
        cmd = ["ffmpeg"]
        if self.use_nvdec:
            cmd.extend(["-hwaccel", "nvdec"])
        cmd.extend(["-i", str(self.path)])

        if step > 1:
            cmd.extend(["-vf", f"select=not(mod(n\\,{step}))", "-fps_mode", "passthrough"])

        if max_frames:
            cmd.extend(["-vframes", str(max_frames)])

        cmd.extend([
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-v", "error",
            "pipe:1",
        ])

        expected_frame_bytes = self.metadata.width * self.metadata.height * 3
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**7)

        count = 0
        current_idx = 0
        try:
            while True:
                raw_bytes = proc.stdout.read(expected_frame_bytes)  # type: ignore[union-attr]
                if len(raw_bytes) < expected_frame_bytes:
                    break

                arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(
                    (self.metadata.height, self.metadata.width, 3)
                )
                yield current_idx, arr
                count += 1
                current_idx += step
                if max_frames and count >= max_frames:
                    break
        finally:
            proc.terminate()
            proc.wait()

    def extract_keyframes_to_disk(
        self, indices: Sequence[int], output_dir: str | Path, format: str = "png"
    ) -> list[Path]:
        """Extract given frame indices and write to disk in output_dir."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        saved_paths: list[Path] = []

        for idx in indices:
            arr = self.extract_frame_at_index(idx)
            img = Image.fromarray(arr)
            dest = out_path / f"frame_{idx:06d}.{format}"
            img.save(dest)
            saved_paths.append(dest)

        logger.info("Extracted %d keyframes to disk at %s", len(saved_paths), str(out_path))
        return saved_paths
