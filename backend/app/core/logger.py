"""Structured Defense Logging Subsystem.

Provides millisecond-precise, contextual logging for military and intelligence
photogrammetric pipeline operations.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


class TacticalLogFormatter(logging.Formatter):
    """Military HUD styled ANSI console formatter."""

    COLOR_MAP = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        time_str = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        subsystem = getattr(record, "subsystem", record.name)
        msg = record.getMessage()

        header = f"[{time_str}] [{color}{record.levelname:^8}{self.RESET}] [{self.BOLD}{subsystem}{self.RESET}]"
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            return f"{header} {msg}\n{exc_text}"
        return f"{header} {msg}"


def get_logger(name: str, subsystem: str | None = None) -> logging.Logger:
    """Instantiate or retrieve a configured structured logger.

    Args:
        name: The module or component name.
        subsystem: Optional operational identifier (e.g. 'STAGE1-INGESTION', 'SIM3-SOLVER').

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(TacticalLogFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    if subsystem:
        # Wrap or attach subsystem context
        extra = {"subsystem": subsystem}
        return logging.LoggerAdapter(logger, extra)  # type: ignore[return-value]

    return logger
