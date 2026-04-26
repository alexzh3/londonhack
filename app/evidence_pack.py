"""Build the typed CafeEvidencePack from per-session demo fixtures."""

from __future__ import annotations

import json
import logging
import os
from uuid import UUID, uuid4

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
from app.logfire_setup import span as logfire_span
from app.sessions import fixture_statuses, load_manifest, missing_required, session_dir
from app.vision.kpi import compute_kpi_windows
from app.vision.objects import (
    load_object_detections_cache,
    select_live_detections_for_inventory,
)
from app.vision.tracks import load_tracks_cache

logger = logging.getLogger(__name__)


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


def _maybe_live_kpi_windows(
    session_id: str,
    run_id: UUID,
    fixture_windows: list[KPIReport],
    zones: list[Zone],
) -> list[KPIReport] | None:
    """Compute Tier 1C live KPIs from ``tracks.cached.json`` when available.

    Returns the live list keyed to the fixture's window schedule/memory_ids,
    or ``None`` to signal callers to keep the fixture windows as-is.

    Live KPIs engage when all of these hold:
    - Session manifest marks ``source_kind == "real"`` (AI-generated mock
      scenes keep their narrative fixture numbers so the demo story stays
      coherent — their synthetic people don't actually queue).
      ``CAFETWIN_FORCE_LIVE_KPI=1`` overrides this for testing.
    - ``tracks.cached.json`` is present on disk.
    - ``CAFETWIN_FORCE_FIXTURE_KPI != "1"`` (demo escape hatch).
    """
    if os.getenv("CAFETWIN_FORCE_FIXTURE_KPI") == "1":
        return None

    tracks_path = session_dir(session_id) / "tracks.cached.json"
    if not tracks_path.exists():
        return None

    force_live = os.getenv("CAFETWIN_FORCE_LIVE_KPI") == "1"
    if not force_live:
        try:
            manifest = load_manifest(session_id)
        except (OSError, ValueError, ValidationError):
            return None
        if manifest.source_kind != "real":
            return None

    try:
        tracks_cache = load_tracks_cache(tracks_path)
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("Failed to load %s for live KPIs: %s", tracks_path, exc)
        return None

    with logfire_span(
        "kpi_engine.compute_window",
        session_id=session_id,
        window_count=len(fixture_windows),
        track_count=len(tracks_cache.tracks),
    ):
        return compute_kpi_windows(
            tracks_cache=tracks_cache,
            session_id=session_id,
            run_id=run_id,
            fixture_windows=fixture_windows,
            zones=zones,
        )


def _maybe_augment_inventory_with_live(
    session_id: str, inventory: ObjectInventory
) -> ObjectInventory:
    """Tier 1F. Append vision-detected scene objects to the fixture
    `ObjectInventory` when a reviewed (or unreviewed) detector cache is
    on disk for the session.

    Augmentation, not replacement: the fixture's narrative objects
    (counter, queue_marker, pickup_shelf...) stay in place so the cached
    `recommendation.cached.json`'s ``target_id`` remains valid. The
    detector-derived chairs/tables/plants land alongside with
    ``source="vision"`` IDs prefixed ``vision_`` so the agent can reason
    over real perception output without the fallback path breaking.

    Engages by default whenever a cache file exists; opt out per request
    with ``CAFETWIN_FORCE_FIXTURE_INVENTORY=1`` (mirrors the equivalent
    KPI escape hatch from Tier 1C).
    """
    if os.getenv("CAFETWIN_FORCE_FIXTURE_INVENTORY") == "1":
        return inventory

    base = session_dir(session_id)
    reviewed = base / "object_detections.reviewed.cached.json"
    raw = base / "object_detections.cached.json"
    cache_path = reviewed if reviewed.exists() else (raw if raw.exists() else None)
    if cache_path is None:
        return inventory

    try:
        cache = load_object_detections_cache(cache_path)
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("Failed to load %s for live inventory: %s", cache_path, exc)
        return inventory

    if not cache.detections:
        return inventory

    fixture_bboxes = [obj.bbox_xyxy for obj in inventory.objects]
    with logfire_span(
        "object_inventory.augment_live",
        session_id=session_id,
        cache_path=cache_path.name,
        candidate_count=len(cache.detections),
    ):
        live_dicts = select_live_detections_for_inventory(
            cache.detections, fixture_bboxes
        )

    if not live_dicts:
        return inventory

    # Validate the new objects through the SceneObject Pydantic model so any
    # mismatch with the agent-facing schema fails loudly here rather than
    # downstream. Use the schema TypeAdapter so we get clean error messages.
    from app.schemas import SceneObject

    new_objects = [SceneObject.model_validate(d) for d in live_dicts]

    # Update counts_by_kind to include the new vision-tagged objects.
    augmented_counts = dict(inventory.counts_by_kind)
    for obj in new_objects:
        augmented_counts[obj.kind] = augmented_counts.get(obj.kind, 0) + 1

    # Confidence drops slightly toward the detector's mean to honestly
    # reflect that some of the inventory is now derived rather than
    # hand-authored. Weighted average by object count.
    fixture_n = len(inventory.objects)
    live_n = len(new_objects)
    live_mean_conf = (
        sum(obj.confidence for obj in new_objects) / live_n if live_n else 0.0
    )
    augmented_conf = (
        (inventory.count_confidence * fixture_n + live_mean_conf * live_n)
        / max(1, fixture_n + live_n)
    )

    return inventory.model_copy(
        update={
            "objects": [*inventory.objects, *new_objects],
            "counts_by_kind": augmented_counts,
            "count_confidence": min(1.0, max(0.0, augmented_conf)),
            "notes": [
                *inventory.notes,
                (
                    f"Tier 1F: appended {live_n} vision-detected object(s) "
                    f"from {cache_path.name} ({cache.source})."
                ),
            ],
        }
    )


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

    # Tier 1F: append vision-detected objects to the fixture inventory
    # when a detector cache is on disk for the session. Augmentation is
    # safe even when no cache exists (returns inventory unchanged).
    inventory = _maybe_augment_inventory_with_live(session_id, inventory)

    live_windows = _maybe_live_kpi_windows(session_id, inventory.run_id, kpi_windows, zones)
    if live_windows is not None:
        kpi_windows = live_windows
    else:
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

    # Tier 1F: augment with live vision detections (safe no-op when no
    # cache file exists or CAFETWIN_FORCE_FIXTURE_INVENTORY=1).
    inventory = _maybe_augment_inventory_with_live(session_id, inventory)

    live_windows = _maybe_live_kpi_windows(session_id, run_id, kpi_windows, zones)
    if live_windows is not None:
        kpi_windows = live_windows
    else:
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

    # Tier 1D: surface the YOLO+ByteTrack annotated overlay video when the
    # offline vision script has produced one, so the frontend can play the
    # real-CCTV-with-detections asset side-by-side with the iso twin.
    # Prefer the H.264-encoded `.web.mp4` variant for browser playback
    # (cv2.VideoWriter's default `mp4v` fourcc is MPEG-4 part 2, which
    # Chromium's HTML5 video element rejects with MEDIA_ERR_SRC_NOT_SUPPORTED).
    annotated_web = base / "annotated_before.web.mp4"
    annotated_raw = base / "annotated_before.mp4"
    if annotated_web.exists():
        assets["annotated_video"] = str(annotated_web.relative_to(config.ROOT_DIR))
    elif annotated_raw.exists():
        assets["annotated_video"] = str(annotated_raw.relative_to(config.ROOT_DIR))

    try:
        manifest = _load_json(session_id, "session.json")
    except (OSError, ValueError):
        return assets

    video_path = manifest.get("video_path") if isinstance(manifest, dict) else None
    if isinstance(video_path, str):
        assets["video"] = video_path
    return assets
