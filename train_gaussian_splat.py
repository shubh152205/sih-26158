#!/usr/bin/env python3
"""train_gaussian_splat.py

Wraps Nerfstudio's `ns-train splatfacto` as a robust subprocess with live stdout monitoring.
Streams and parses training telemetry (PSNR, SSIM, Loss, Iterations) in real-time,
applies drone-specific parameter presets, and returns the final config path.

Usage:
    python backend/train_gaussian_splat.py \
        --data ./data/drone_colmap \
        --output-dir ./outputs \
        --max-iterations 30000 \
        --experiment-name drone_flight_alpha
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SPLAT-TRAIN] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SPLAT-TRAIN")


# =====================================================================
# Telemetry Regex Matchers for ns-train splatfacto
# =====================================================================
STEP_REGEX = re.compile(r"(\d+)\s*/\s*(\d+)\s*\[", re.IGNORECASE)
LOSS_REGEX = re.compile(r"loss[:=]\s*([0-9\.]+)", re.IGNORECASE)
PSNR_REGEX = re.compile(r"psnr[:=]\s*([0-9\.]+)", re.IGNORECASE)
SSIM_REGEX = re.compile(r"ssim[:=]\s*([0-9\.]+)", re.IGNORECASE)
NUM_RAYS_REGEX = re.compile(r"([0-9\.]+[kM]?\s*(?:rays/s|it/s))", re.IGNORECASE)


def verify_nerfstudio_installation() -> str:
    """Verifies that ns-train is accessible in the current environment."""
    ns_train_bin = shutil.which("ns-train")
    if not ns_train_bin:
        logger.warning(
            "ns-train executable not found in PATH.\n"
            "Ensure Nerfstudio is installed: pip install nerfstudio\n"
            "The script will proceed assuming it can be invoked via Python environment."
        )
        return "ns-train"
    return ns_train_bin


def build_command(args: argparse.Namespace, ns_bin: str) -> List[str]:
    """Constructs the full ns-train splatfacto CLI command with drone optimizations."""
    cmd = [
        ns_bin,
        "splatfacto",
        "--data", str(Path(args.data).resolve()),
        "--output-dir", str(Path(args.output_dir).resolve()),
        "--experiment-name", args.experiment_name,
        "--max-num-iterations", str(args.max_iterations),
    ]

    # Nerfstudio evaluation mode (default 'all' evaluates train and val)
    if args.eval_mode:
        cmd.extend(["--pipeline.model.eval-mode", args.eval_mode])

    # Drone-specific floater reduction & optimization tuning
    cmd.extend([
        "--pipeline.model.cull-alpha-thresh", str(args.cull_alpha_thresh),
        "--pipeline.model.densify-grad-thresh", str(args.densify_grad_thresh),
        "--pipeline.model.reset-alpha-every", str(args.reset_alpha_every),
        "--pipeline.model.background-color", args.background_color,
        "--pipeline.model.sh-degree", str(args.sh_degree),
    ])

    # Viewer / logging options
    if args.vis:
        cmd.extend(["--vis", args.vis])
    else:
        cmd.extend(["--vis", "none"])

    # Forward any custom unhandled extra arguments
    if args.extra_args:
        cmd.extend(args.extra_args.split())

    return cmd


def stream_subprocess_output(proc: subprocess.Popen, log_file: Path, report_interval: int = 500) -> None:
    """Streams stdout line-by-line, writes to log_file, and extracts PSNR/SSIM."""
    last_reported_step = -1
    t0 = time.time()

    with open(log_file, "w", encoding="utf-8") as lf:
        for raw_line in iter(proc.stdout.readline, ""):
            if not raw_line:
                break

            lf.write(raw_line)
            lf.flush()
            line = raw_line.strip()

            # Parse Step
            step_match = STEP_REGEX.search(line)
            psnr_match = PSNR_REGEX.search(line)
            ssim_match = SSIM_REGEX.search(line)
            loss_match = LOSS_REGEX.search(line)
            speed_match = NUM_RAYS_REGEX.search(line)

            curr_step = int(step_match.group(1)) if step_match else None
            max_step = int(step_match.group(2)) if step_match else None
            curr_psnr = float(psnr_match.group(1)) if psnr_match else None
            curr_ssim = float(ssim_match.group(1)) if ssim_match else None
            curr_loss = float(loss_match.group(1)) if loss_match else None
            curr_speed = speed_match.group(1) if speed_match else ""

            # Check if PSNR/SSIM evaluation was printed
            if curr_psnr is not None or curr_ssim is not None:
                psnr_str = f"PSNR: {curr_psnr:.2f} dB" if curr_psnr is not None else ""
                ssim_str = f"SSIM: {curr_ssim:.4f}" if curr_ssim is not None else ""
                step_str = f"Step [{curr_step}/{max_step}]" if curr_step else "Eval"
                logger.info(">>> EVALUATION METRIC: %s | %s %s", step_str, psnr_str, ssim_str)

            # Periodic training progress report
            elif curr_step and (curr_step - last_reported_step >= report_interval or curr_step == max_step):
                last_reported_step = curr_step
                progress_pct = (curr_step / max_step) * 100.0 if max_step else 0.0
                elapsed = time.time() - t0
                loss_str = f"Loss: {curr_loss:.5f}" if curr_loss is not None else ""
                logger.info(
                    "Training Progress: %5.1f%% (%d/%d iters) | %s | %s | Elapsed: %.1fs",
                    progress_pct, curr_step, max_step, loss_str, curr_speed, elapsed
                )


def find_latest_config(output_dir: Path, experiment_name: str) -> Optional[Path]:
    """Locates the generated config.yml inside output_dir/experiment_name/splatfacto/<timestamp>/."""
    search_dir = output_dir / experiment_name
    if not search_dir.is_dir():
        search_dir = output_dir

    configs = list(search_dir.rglob("config.yml"))
    if not configs:
        return None
    # Return the most recently modified config
    configs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return configs[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nerfstudio splatfacto Training Wrapper with Live Metric Monitoring for Aerial Drones",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data", type=str, required=True, help="Path to Nerfstudio-compatible dataset directory")
    parser.add_argument("--output-dir", type=str, default="./outputs", help="Directory where trained models are saved")
    parser.add_argument("--experiment-name", type=str, default="drone_splat", help="Experiment identifier name")
    parser.add_argument("--max-iterations", type=int, default=30000, help="Maximum number of training iterations")
    parser.add_argument("--report-interval", type=int, default=500, help="Console progress reporting interval in steps")
    parser.add_argument("--vis", type=str, default="none", choices=["viewer", "wandb", "tensorboard", "none"], help="Visualizer backend")

    # Drone Floater / Sky Tuning Presets
    parser.add_argument("--cull-alpha-thresh", type=float, default=0.005, help="Prune Gaussians with opacity below this threshold")
    parser.add_argument("--densify-grad-thresh", type=float, default=0.0002, help="Position gradient threshold for Gaussian splitting/cloning")
    parser.add_argument("--reset-alpha-every", type=int, default=3000, help="Reset opacities to zero every N steps to destroy floaters")
    parser.add_argument("--background-color", type=str, default="random", choices=["random", "black", "white"], help="Background training color")
    parser.add_argument("--sh-degree", type=int, default=3, choices=[0, 1, 2, 3, 4], help="Spherical Harmonics order (3 = 16 coefficients per color)")
    parser.add_argument("--eval-mode", type=str, default="all", choices=["all", "train", "fraction", "filename"], help="Nerfstudio evaluation mode")
    parser.add_argument("--extra-args", type=str, default="", help="Additional raw flags to append to ns-train splatfacto")

    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("Dataset path does not exist: %s", data_path)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / f"{args.experiment_name}_train.log"

    ns_bin = verify_nerfstudio_installation()
    cmd = build_command(args, ns_bin)

    logger.info("=================================================================")
    logger.info("Starting Nerfstudio Splatfacto Training for Drone Reconstruction")
    logger.info("Command: %s", " ".join(cmd))
    logger.info("Logging raw output to: %s", log_file)
    logger.info("=================================================================")

    t_start = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        stream_subprocess_output(proc, log_file, report_interval=args.report_interval)
        return_code = proc.wait()

        if return_code != 0:
            logger.error("Training failed with exit code %d. Check logs: %s", return_code, log_file)
            sys.exit(return_code)

        elapsed = time.time() - t_start
        logger.info("Training successfully finished in %.2f minutes (%.1fs)!", elapsed / 60.0, elapsed)

        # Discover config
        config_path = find_latest_config(out_dir, args.experiment_name)
        if config_path:
            logger.info("=================================================================")
            logger.info("TRAINED CONFIG READY FOR EXPORT:")
            logger.info("Config Path: %s", config_path)
            logger.info("Export Command:")
            logger.info("  python backend/export_splat.py --load-config %s --output-dir ./exports", config_path)
            logger.info("=================================================================")
        else:
            logger.warning("Training finished but config.yml could not be automatically located under %s", out_dir)

    except KeyboardInterrupt:
        logger.warning("Training interrupted by user (Ctrl+C). Terminating subprocess...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("Subprocess safely terminated.")
        config_path = find_latest_config(out_dir, args.experiment_name)
        if config_path:
            logger.info("Latest saved checkpoint config found at: %s", config_path)
        sys.exit(130)


if __name__ == "__main__":
    main()
