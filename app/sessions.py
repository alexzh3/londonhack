"""Session discovery and fixture status helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app import config
from app.schemas import FixtureStatus, SessionManifest


REQUIRED_FIXTURES = (
    "session.json",
    "zones.json",
    "object_inventory.json",
    "kpi_windows.json",
    "pattern_fixture.json",
    "recommendation.cached.json",
)


def session_dir(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id


def fixture_statuses(session_id: str) -> list[FixtureStatus]:
    base = session_dir(session_id)
    return [
        FixtureStatus(filename=filename, exists=(base / filename).exists())
        for filename in REQUIRED_FIXTURES
    ]


def missing_required(session_id: str) -> list[str]:
    return [status.filename for status in fixture_statuses(session_id) if not status.exists]


def load_manifest(session_id: str) -> SessionManifest:
    path = session_dir(session_id) / "session.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return SessionManifest.model_validate(data)


def list_session_manifests() -> list[SessionManifest]:
    sessions_root = config.SESSIONS_DIR
    if not sessions_root.exists():
        return []

    manifests: list[SessionManifest] = []
    adapter = TypeAdapter(SessionManifest)
    for path in sorted(sessions_root.glob("*/session.json")):
        try:
            manifests.append(adapter.validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError, ValueError):
            continue
    return manifests
