#!/usr/bin/env python3
"""export_splat.py

Wraps Nerfstudio's `ns-export gaussian-splat` CLI to export a final 3D Gaussian Splat PLY.
Includes robust configuration validation, automatic newest config discovery,
and output integrity verification.

Usage:
    python backend/export_splat.py --load-config ./outputs/drone_splat/splatfacto/2026-09-10_120000/config.yml --output-dir ./exports
    # Or auto-discover latest trained config:
    python backend/export_splat.py --search-dir ./outputs --output-dir ./exports
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SPLAT-EXPORT] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SPLAT-EXPORT")


def find_latest_config(search_dir: Path) -> Optional[Path]:
    """Finds the most recently modified config.yml recursively inside search_dir."""
    if not search_dir.is_dir():
        return None
    configs = list(search_dir.rglob("config.yml"))
    if not configs:
        return None
    configs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return configs[0]


def resolve_config_path(config_arg: Optional[str], search_dir: Path) -> Path:
    """Validates the explicit config path or resolves the latest available config."""
    if config_arg:
        config_path = Path(config_arg).resolve()
        if not config_path.is_file():
            # Check if user passed directory containing config.yml
            if config_path.is_dir() and (config_path / "config.yml").is_file():
                config_path = config_path / "config.yml"
            else:
                nearby = list(search_dir.rglob("config.yml")) if search_dir.exists() else []
                err_msg = [
                    f"Config file does not exist: {config_path}",
                    "Available configs found in search directory:",
                ]
                for c in nearby[:5]:
                    err_msg.append(f"  - {c}")
                logger.error("\n".join(err_msg))
                sys.exit(1)
        return config_path

    # Auto-discovery
    logger.info("No explicit --load-config provided. Searching in: %s", search_dir)
    auto_config = find_latest_config(search_dir)
    if not auto_config:
        logger.error(
            "Could not locate any config.yml inside '%s'.\n"
            "Please provide an explicit path using --load-config <path/to/config.yml>",
            search_dir,
        )
        sys.exit(1)

    logger.info("Auto-discovered latest trained config: %s", auto_config)
    return auto_config


def export_splat(
    config_path: Path,
    output_dir: Path,
    target_filename: str = "splat.ply",
    extra_args: Optional[str] = None,
) -> Path:
    """Executes ns-export gaussian-splat and verifies the exported PLY file."""
    ns_export_bin = shutil.which("ns-export")
    if not ns_export_bin:
        logger.warning(
            "ns-export not found in system PATH. Attempting invocation via environment..."
        )
        ns_export_bin = "ns-export"

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        ns_export_bin,
        "gaussian-splat",
        "--load-config", str(config_path),
        "--output-dir", str(output_dir),
    ]

    if extra_args:
        cmd.extend(extra_args.split())

    logger.info("Running export command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info("ns-export standard output:\n%s", result.stdout.strip())
    except subprocess.CalledProcessError as err:
        logger.error("ns-export failed with returncode %d!", err.returncode)
        logger.error("STDERR output:\n%s", err.stderr.strip())
        logger.error("STDOUT output:\n%s", err.stdout.strip())
        sys.exit(err.returncode)
    except FileNotFoundError:
        logger.error(
            "Execution failed: '%s' is not installed or not in PATH.\n"
            "Install Nerfstudio inside your active Python environment:\n"
            "  pip install nerfstudio",
            ns_export_bin,
        )
        sys.exit(1)

    # Nerfstudio outputs 'splat.ply' inside output_dir
    expected_ply = output_dir / "splat.ply"
    if not expected_ply.is_file():
        # Check if any .ply was created inside output_dir
        plys = list(output_dir.glob("*.ply"))
        if plys:
            expected_ply = plys[0]
        else:
            logger.error("Export completed but no .ply file was found in %s", output_dir)
            sys.exit(1)

    # Rename to target filename if requested
    final_ply = output_dir / target_filename
    if expected_ply != final_ply:
        expected_ply.replace(final_ply)

    size_mb = final_ply.stat().st_size / (1024 * 1024)
    logger.info("=================================================================")
    logger.info("Gaussian Splat Export Successful!")
    logger.info("Output PLY: %s (%.2f MB)", final_ply, size_mb)
    logger.info("Run QA Check:")
    logger.info("  python backend/qa_splat.py --input %s", final_ply)
    logger.info("=================================================================")

    return final_ply


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nerfstudio Gaussian Splat Exporter with Config Validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--load-config",
        type=str,
        default=None,
        help="Path to trained config.yml (if omitted, searches --search-dir)",
    )
    parser.add_argument(
        "--search-dir",
        type=str,
        default="./outputs",
        help="Directory to scan for latest config.yml if --load-config is omitted",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./exports",
        help="Directory where exported splat.ply will be written",
    )
    parser.add_argument(
        "--target-name",
        type=str,
        default="splat.ply",
        help="Filename for the exported Gaussian Splat PLY",
    )
    parser.add_argument(
        "--extra-args",
        type=str,
        default=None,
        help="Any additional raw arguments to pass to ns-export gaussian-splat",
    )

    args = parser.parse_args()

    config_path = resolve_config_path(args.load_config, Path(args.search_dir))
    output_dir = Path(args.output_dir).resolve()

    export_splat(
        config_path=config_path,
        output_dir=output_dir,
        target_filename=args.target_name,
        extra_args=args.extra_args,
    )


if __name__ == "__main__":
    main()
