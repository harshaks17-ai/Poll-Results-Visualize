"""Shared helpers: directories, logging and light styling for matplotlib."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import config


def ensure_directories() -> None:
    """Create every output folder the project writes to (idempotent)."""
    for folder in (
        config.RAW_DATA_DIR,
        config.PROCESSED_DATA_DIR,
        config.CHARTS_DIR,
        config.REPORTS_DIR,
        config.NOTEBOOK_DIR,
        config.IMAGE_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)


def get_logger(name: str = "poll_visualizer") -> logging.Logger:
    """Return a logger that writes clean, timestamped lines to stdout."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def apply_matplotlib_theme() -> None:
    """Apply the light theme to matplotlib so saved charts look consistent."""
    import matplotlib

    matplotlib.use("Agg")  # headless-safe backend (no display required)
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": config.THEME["surface"],
            "axes.facecolor": config.THEME["surface"],
            "axes.edgecolor": config.THEME["border"],
            "axes.labelcolor": config.THEME["text"],
            "axes.titlecolor": config.THEME["text"],
            "text.color": config.THEME["text"],
            "xtick.color": config.THEME["muted"],
            "ytick.color": config.THEME["muted"],
            "grid.color": config.THEME["border"],
            "font.family": "DejaVu Sans",
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "figure.dpi": 100,
            "savefig.dpi": config.FIG_DPI,
            "savefig.bbox": "tight",
        },
    )


def banner(title: str = "", width: int = 78) -> str:
    """Return a pretty ASCII banner used by the CLI pipeline."""
    line = "=" * width
    return f"{line}\n{title.center(width)}\n{line}"
