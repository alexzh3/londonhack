"""Runtime paths and environment helpers for the MVP backend."""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_DATA_DIR = Path(os.getenv("DEMO_DATA_DIR", ROOT_DIR / "demo_data"))


def demo_data_path(filename: str) -> Path:
    """Return an absolute path under the configured demo data directory."""
    return DEMO_DATA_DIR / filename
