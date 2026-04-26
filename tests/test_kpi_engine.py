"""Tier 1C: deterministic live KPI engine."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.evidence_pack import _maybe_live_kpi_windows, build, state
from app.schemas import KPIReport, Zone
from app.vision.kpi import (
    CROSSING_DISTANCE_PX,
    QUEUE_OBSTRUCTION_MIN,
    compute_kpi_windows,
)
from app.vision.tracks import (
    PersonTrack,
    TrackDetection,
    TrackSummary,
    TrackVideoMetadata,
    TracksCache,
)


# --- Helpers --------------------------------------------------------------


def _det(frame_idx: int, ts: float, x: float, y: float, zone_id: str | None = None) -> TrackDetection:
    return TrackDetection(
        frame_idx=frame_idx,
        timestamp_s=ts,
        bbox_xyxy=(x - 5, y - 5, x + 5, y + 5),
        center_xy=(x, y),
        confidence=0.9,
        zone_id=zone_id,
    )


def _track(
    track_id: int,
    role: str,
    detections: list[TrackDetection],
    role_confidence: float = 0.9,
) -> PersonTrack:
    return PersonTrack(
        track_id=track_id,
        role=role,
        role_confidence=role_confidence,
        class_name="person",
        detections=detections,
    )


def _make_cache(
    tracks: list[PersonTrack],
    *,
    fps: float = 30.0,
    vid_stride: int = 3,
    duration_s: float = 15.0,
) -> TracksCache:
    frame_count = int(duration_s * fps)
    processed = sum(1 for t in tracks for _ in t.detections)
    return TracksCache(
        session_id="synthetic",
        source_video="synthetic.mp4",
        source="ultralytics_yolo_bytetrack",
        model="yolov8n.pt",
        tracker="bytetrack.yaml",
        generated_at=datetime(2026, 4, 26, 0, 0, 0, tzinfo=timezone.utc),
        video=TrackVideoMetadata(
            width=1280,
            height=720,
            fps=fps,
            frame_count=frame_count,
            duration_s=duration_s,
            processed_frame_count=processed,
            vid_stride=vid_stride,
        ),
        zone_ids=["counter", "pickup", "queue", "staff_path", "seating", "entrance"],
        summary=TrackSummary(
            track_count=len(tracks),
            detection_count=sum(len(t.detections) for t in tracks),
            frames_with_detections=processed,
            role_counts={
                "staff": sum(1 for t in tracks if t.role == "staff"),
                "customer": sum(1 for t in tracks if t.role == "customer"),
                "unknown": sum(1 for t in tracks if t.role == "unknown"),
            },
        ),
        tracks=tracks,
    )


def _fixture_window(memory_id: str, start: float, end: float) -> KPIReport:
    return KPIReport(
        window_start_s=start,
        window_end_s=end,
        frames_sampled=1,
        staff_walk_distance_px=0.0,
        staff_customer_crossings=0,
        queue_length_peak=0,
        queue_obstruction_seconds=0.0,
        congestion_score=0.0,
        table_detour_score=0.0,
        session_id="synthetic",
        run_id=uuid4(),
        memory_id=memory_id,
    )


def _zone(id_: str, kind: str = "queue") -> Zone:
    return Zone(
        id=id_,
        name=id_,
        kind=kind,
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        color_hex="#000000",
        source="manual",
        confidence=0.5,
    )


# --- Engine unit tests ----------------------------------------------------


def test_empty_window_keeps_schema_valid():
    """Empty windows fall back to fixture frames_sampled to keep schema constraint
    (frames_sampled >= 1)."""
    cache = _make_cache([])
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    assert len(windows) == 1
    w = windows[0]
    assert w.queue_length_peak == 0
    assert w.staff_customer_crossings == 0
    assert w.queue_obstruction_seconds == 0.0
    assert w.congestion_score == 0.0
    assert w.frames_sampled >= 1


def test_queue_peak_counts_distinct_customers_per_frame():
    """3 customer tracks all in queue zone on the same frame → peak=3."""
    customers = [
        _track(
            i + 1,
            "customer",
            [_det(0, 0.0, 100.0 + i, 100.0, zone_id="queue")],
        )
        for i in range(3)
    ]
    cache = _make_cache(customers)
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    assert windows[0].queue_length_peak == 3


def test_obstruction_seconds_uses_sampling_cadence():
    """Threshold engages when ≥ QUEUE_OBSTRUCTION_MIN customers are in queue.
    Each frame contributes vid_stride/fps seconds."""
    customers = [
        _track(
            i + 1,
            "customer",
            [
                _det(0, 0.0, 100.0 + i, 100.0, zone_id="queue"),
                _det(3, 0.1, 100.0 + i, 100.0, zone_id="queue"),
            ],
        )
        for i in range(QUEUE_OBSTRUCTION_MIN)
    ]
    cache = _make_cache(customers, fps=30.0, vid_stride=3)
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    # 2 frames × (3/30) = 0.2 s
    assert windows[0].queue_obstruction_seconds == pytest.approx(0.2)


def test_crossings_count_distinct_pairs_within_threshold():
    """Two staff and two customers, only one staff×customer pair within threshold."""
    staff = [
        _track(10, "staff", [_det(0, 0.0, 100.0, 100.0, zone_id="counter")]),
        _track(11, "staff", [_det(0, 0.0, 800.0, 100.0, zone_id="counter")]),
    ]
    customers = [
        _track(20, "customer", [_det(0, 0.0, 110.0, 100.0, zone_id="queue")]),
        _track(21, "customer", [_det(0, 0.0, 800.0 + CROSSING_DISTANCE_PX + 1, 100.0, zone_id="queue")]),
    ]
    cache = _make_cache(staff + customers)
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    # Only (staff=10, customer=20) within threshold; (10, 21), (11, 20), (11, 21) all > threshold
    assert windows[0].staff_customer_crossings == 1


def test_staff_walk_distance_sums_consecutive_centers():
    """Staff track with three detections at known coords → distance is 3+4=7."""
    staff = _track(
        1,
        "staff",
        [
            _det(0, 0.0, 0.0, 0.0, zone_id="counter"),
            _det(3, 0.1, 3.0, 0.0, zone_id="counter"),  # +3
            _det(6, 0.2, 3.0, 4.0, zone_id="counter"),  # +4
        ],
    )
    cache = _make_cache([staff])
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    assert windows[0].staff_walk_distance_px == pytest.approx(7.0)


def test_window_schedule_preserved_from_fixture():
    """Output windows mirror fixture timing + memory_id 1:1 for citation stability."""
    cache = _make_cache(
        [_track(1, "customer", [_det(0, 0.0, 100.0, 100.0, zone_id="queue")])]
    )
    fixture = [
        _fixture_window("kpi_w1", 0.0, 5.0),
        _fixture_window("kpi_w2", 5.0, 10.0),
        _fixture_window("kpi_w3", 10.0, 15.0),
    ]
    run_id = uuid4()
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=run_id,
        fixture_windows=fixture,
        zones=[_zone("queue")],
    )
    assert [w.memory_id for w in windows] == ["kpi_w1", "kpi_w2", "kpi_w3"]
    assert [(w.window_start_s, w.window_end_s) for w in windows] == [
        (0.0, 5.0),
        (5.0, 10.0),
        (10.0, 15.0),
    ]
    assert all(w.session_id == "synthetic" and w.run_id == run_id for w in windows)


def test_only_in_window_detections_counted():
    """Detections outside window time bounds shouldn't bleed across windows."""
    track = _track(
        1,
        "customer",
        [
            _det(0, 0.0, 100.0, 100.0, zone_id="queue"),
            _det(150, 5.0, 200.0, 200.0, zone_id="queue"),
        ],
    )
    cache = _make_cache([track], duration_s=10.0)
    fixture = [
        _fixture_window("kpi_w1", 0.0, 5.0),
        _fixture_window("kpi_w2", 5.0, 10.0),
    ]
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=fixture,
        zones=[_zone("queue")],
    )
    # Each window has exactly one detection
    assert windows[0].queue_length_peak == 1
    assert windows[1].queue_length_peak == 1


def test_congestion_score_is_clamped_to_unit_interval():
    """Even with extreme inputs the schema bound 0 ≤ score ≤ 1 must hold."""
    customers = [
        _track(
            i + 1,
            "customer",
            [_det(0, 0.0, 100.0 + i * 0.1, 100.0, zone_id="queue")],
        )
        for i in range(20)
    ]
    cache = _make_cache(customers)
    windows = compute_kpi_windows(
        tracks_cache=cache,
        session_id="synthetic",
        run_id=uuid4(),
        fixture_windows=[_fixture_window("kpi_w1", 0.0, 5.0)],
        zones=[_zone("queue")],
    )
    assert 0.0 <= windows[0].congestion_score <= 1.0


# --- Integration tests with real demo_data ------------------------------


def test_state_uses_live_kpis_for_real_cafe(monkeypatch):
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_KPI", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_LIVE_KPI", raising=False)
    s = state("real_cafe")
    # Live obstruction (≥2 customer threshold over only ~150 sampled frames at
    # vid_stride=3) is much lower than the narratively-tuned fixture (8/17/12s).
    assert all(w.queue_obstruction_seconds < 8.0 for w in s.kpi_windows)
    # But peaks come from the same crowd → match fixture's (2, 3, 2) exactly.
    assert [w.queue_length_peak for w in s.kpi_windows] == [2, 3, 2]


def test_state_uses_fixture_kpis_for_ai_cafe_a(monkeypatch):
    """AI-generated session keeps narrative fixture (people are seated, no queue)."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_KPI", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_LIVE_KPI", raising=False)
    s = state("ai_cafe_a")
    # Fixture peaks: 2, 3, 3
    assert [w.queue_length_peak for w in s.kpi_windows] == [2, 3, 3]
    assert s.kpi_windows[0].queue_obstruction_seconds == 13.0


def test_force_fixture_kpi_env_overrides_live(monkeypatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FIXTURE_KPI", "1")
    pack = build("real_cafe")
    # Fixture obstruction values
    assert pack.kpi_windows[0].queue_obstruction_seconds == 8.0
    assert pack.kpi_windows[1].queue_obstruction_seconds == 17.0


def test_force_live_kpi_env_engages_on_synthetic_session(monkeypatch):
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_KPI", raising=False)
    monkeypatch.setenv("CAFETWIN_FORCE_LIVE_KPI", "1")
    pack = build("ai_cafe_a")
    # Live numbers on ai_cafe_a: customers all seated, no queue activity
    assert all(w.queue_length_peak == 0 for w in pack.kpi_windows)


def test_live_kpis_preserve_fixture_memory_ids(monkeypatch):
    """PatternAgent evidence cites kpi_*_w1 etc — those must survive the swap."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_KPI", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_LIVE_KPI", raising=False)
    pack = build("real_cafe")
    assert {w.memory_id for w in pack.kpi_windows} == {
        "kpi_real_cafe_w1",
        "kpi_real_cafe_w2",
        "kpi_real_cafe_w3",
    }


def test_maybe_live_returns_none_without_tracks_cache(monkeypatch, tmp_path):
    """Sessions without tracks.cached.json keep their fixture."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_KPI", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_LIVE_KPI", raising=False)
    # Hijack SESSIONS_DIR to point at an empty tmp dir
    fake_sessions = tmp_path / "sessions" / "ghost_session"
    fake_sessions.mkdir(parents=True)
    fake_manifest = fake_sessions / "session.json"
    fake_manifest.write_text(
        '{"slug": "ghost_session", "label": "g", "video_path": "x.mp4", "source_kind": "real"}'
    )
    monkeypatch.setattr("app.evidence_pack.session_dir", lambda _: fake_sessions)
    monkeypatch.setattr("app.sessions.session_dir", lambda _: fake_sessions)

    fixture = [_fixture_window("kpi_w1", 0.0, 5.0)]
    result = _maybe_live_kpi_windows("ghost_session", uuid4(), fixture, [_zone("queue")])
    assert result is None
