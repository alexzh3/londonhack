"""Build the typed CafeEvidencePack from per-session demo fixtures."""

from __future__ import annotations

import json
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from app import config
from app.schemas import (
    CafeEvidencePack,
    KPIReport,
    ObjectInventory,
    OperationalPattern,
    PatternEvidenceBundle,
    PriorRecommendationMemory,
    StateResponse,
    Zone,
)
from app.sessions import fixture_statuses, missing_required, session_dir


class FixtureLoadError(RuntimeError):
    def __init__(self, session_id: str, missing: list[str]) -> None:
        super().__init__(f"Missing required fixtures for session {session_id}: {missing}")
        self.session_id = session_id
        self.missing = missing


def _load_json(session_id: str, filename: str) -> object:
    path = session_dir(session_id) / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture(session_id: str, filename: str, adapter: TypeAdapter):
    try:
        return adapter.validate_python(_load_json(session_id, filename))
    except (OSError, ValueError, ValidationError) as exc:
        raise FixtureLoadError(session_id, [filename]) from exc


def state(session_id: str = config.DEFAULT_SESSION_ID) -> StateResponse:
    """Return fixture status and parsed data where available."""
    missing = missing_required(session_id)

    if missing:
        return StateResponse(
            session_id=session_id,
            run_id=uuid4(),
            fixtures=fixture_statuses(session_id),
            missing_required=missing,
            assets=_assets(session_id),
        )

    inventory = _load_fixture(session_id, "object_inventory.json", TypeAdapter(ObjectInventory))
    kpi_windows = _load_fixture(session_id, "kpi_windows.json", TypeAdapter(list[KPIReport]))
    pattern = _load_fixture(session_id, "pattern_fixture.json", TypeAdapter(OperationalPattern))
    zones = _load_fixture(session_id, "zones.json", TypeAdapter(list[Zone]))

    # Normalise the slug across all fixtures regardless of what's stored in
    # them — the input arg is the source of truth.
    inventory = inventory.model_copy(update={"session_id": session_id})
    kpi_windows = [w.model_copy(update={"session_id": session_id}) for w in kpi_windows]

    return StateResponse(
        session_id=session_id,
        run_id=inventory.run_id,
        fixtures=fixture_statuses(session_id),
        zones=zones,
        object_inventory=inventory,
        kpi_windows=kpi_windows,
        pattern=pattern,
        assets=_assets(session_id),
    )


def build(
    session_id: str = config.DEFAULT_SESSION_ID,
    prior_recommendation_memories: list[PriorRecommendationMemory] | None = None,
    pattern: OperationalPattern | None = None,
) -> CafeEvidencePack:
    """Load and validate the session fixture bundle for the OptimizationAgent.

    When ``pattern`` is provided (e.g. from a live PatternAgent run), it is
    used directly; otherwise ``pattern_fixture.json`` is loaded as the
    canonical fallback. This keeps backward compatibility for any caller
    that still treats build() as the pattern source of truth."""
    missing = missing_required(session_id)
    if missing:
        raise FixtureLoadError(session_id, missing)

    run_id = uuid4()
    inventory = _load_fixture(session_id, "object_inventory.json", TypeAdapter(ObjectInventory))
    kpi_windows = _load_fixture(session_id, "kpi_windows.json", TypeAdapter(list[KPIReport]))
    if pattern is None:
        pattern = _load_fixture(session_id, "pattern_fixture.json", TypeAdapter(OperationalPattern))
    zones = _load_fixture(session_id, "zones.json", TypeAdapter(list[Zone]))

    # Stamp the slug + run_id consistently across nested models. The input
    # session_id is the source of truth; whatever the fixture stored is
    # informational and overridden here.
    inventory = inventory.model_copy(update={"session_id": session_id, "run_id": run_id})
    kpi_windows = [
        window.model_copy(update={"session_id": session_id, "run_id": run_id})
        for window in kpi_windows
    ]

    return CafeEvidencePack(
        session_id=session_id,
        run_id=run_id,
        zones=zones,
        object_inventory=inventory,
        kpi_windows=kpi_windows,
        pattern=pattern,
        org_rules=[
            "Prefer layout changes that preserve seating capacity.",
            "Do not move fixed counters, walls, or entrance paths.",
            "Cite only evidence IDs present in the operational pattern.",
        ],
        prior_recommendation_memories=prior_recommendation_memories or [],
    )


def build_pattern_evidence_bundle(state_response: StateResponse) -> PatternEvidenceBundle:
    """Construct the PatternAgent input from a populated StateResponse.

    State is the source of truth for the perception fixtures; this just
    repackages the subset PatternAgent needs without duplicating the slug
    normalization logic from build()."""
    if state_response.object_inventory is None:
        raise FixtureLoadError(state_response.session_id, ["object_inventory.json"])
    return PatternEvidenceBundle(
        session_id=state_response.session_id,
        zones=state_response.zones,
        object_inventory=state_response.object_inventory.model_copy(
            update={"session_id": state_response.session_id}
        ),
        kpi_windows=[
            window.model_copy(update={"session_id": state_response.session_id})
            for window in state_response.kpi_windows
        ],
    )


def _assets(session_id: str) -> dict[str, str]:
    base = session_dir(session_id)
    assets: dict[str, str] = {}
    frame_path = base / "frame.jpg"
    if frame_path.exists():
        assets["frame"] = str(frame_path.relative_to(config.ROOT_DIR))

    try:
        manifest = _load_json(session_id, "session.json")
    except (OSError, ValueError):
        return assets

    video_path = manifest.get("video_path") if isinstance(manifest, dict) else None
    if isinstance(video_path, str):
        assets["video"] = video_path
    return assets
