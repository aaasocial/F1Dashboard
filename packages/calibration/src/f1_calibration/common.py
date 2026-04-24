"""Shared constants + logging for calibration pipeline.

Per CONTEXT D-03: training window 2022-2024 (constant, not CLI flag).
Per CONTEXT D-04: chronological 80/20 split.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

TRAINING_YEARS: tuple[int, ...] = (2022, 2023)
VALIDATION_YEARS: tuple[int, ...] = (2024,)
YEAR_RANGE: str = "2022-2024"

WORKSPACE_ROOT: Path = Path(__file__).resolve().parents[4]  # repo root
DEFAULT_POSTERIORS_DIR: Path = WORKSPACE_ROOT / ".data" / "posteriors"
DEFAULT_VALIDATION_DIR: Path = WORKSPACE_ROOT / ".data" / "validation"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("F1_LOG_LEVEL", "INFO"))
    return logger


__all__ = [
    "TRAINING_YEARS",
    "VALIDATION_YEARS",
    "YEAR_RANGE",
    "WORKSPACE_ROOT",
    "DEFAULT_POSTERIORS_DIR",
    "DEFAULT_VALIDATION_DIR",
    "get_logger",
]
