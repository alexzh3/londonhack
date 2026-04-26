"""Runtime paths and environment helpers for the MVP backend."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

DEMO_DATA_DIR = Path(os.getenv("DEMO_DATA_DIR", ROOT_DIR / "demo_data"))
if not DEMO_DATA_DIR.is_absolute():
    DEMO_DATA_DIR = ROOT_DIR / DEMO_DATA_DIR

DEFAULT_SESSION_ID = os.getenv("DEFAULT_SESSION_ID", "ai_cafe_a")
SESSIONS_DIR = DEMO_DATA_DIR / "sessions"
MEMORY_JSONL_PATH = DEMO_DATA_DIR / "mubit_fallback.jsonl"


def demo_data_path(filename: str) -> Path:
    """Return an absolute path under the configured demo data directory."""
    return DEMO_DATA_DIR / filename
