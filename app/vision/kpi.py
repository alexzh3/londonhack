"""Deterministic live KPI engine (Tier 1C).

Computes KPI windows from cached YOLO+ByteTrack detections so the
`PatternAgent` reasons over numbers derived from real video instead of
static fixtures. Uses the fixture's window schedule (start/end/memory_id)
as a template so pattern evidence citations (`kpi_*_w1` etc.) remain
valid subsets of the emitted `kpi_windows[*].memory_id` set.
"""

from __future__ import annotations

import math
from collections import defaultdict
from uuid import UUID

from app.schemas import KPIReport, Zone
from app.vision.tracks import PersonTrack, TrackDetection, TracksCache

# Pairwise staff/customer proximity threshold (pixels). At 1280-wide video a
# staff and customer within ~150 px share the same service interaction
# bubble; this mirrors the conservative fixture-era assumption that the
# service counter handoff area is ~1/8 of the frame width.
CROSSING_DISTANCE_PX = 150.0

# Queue obstruction triggers when ≥ this many distinct customer tracks sit
# inside the `queue` polygon on the same frame.
QUEUE_OBSTRUCTION_MIN = 2

STAFF_ZONE_IDS = frozenset({"counter", "staff_path", "pickup"})


def compute_kpi_windows(
    tracks_cache: TracksCache,
    session_id: str,
    run_id: UUID,
    fixture_windows: list[KPIReport],
    zones: list[Zone],
) -> list[KPIReport]:
    """Compute live KPIReports keyed to the fixture window schedule.

    The fixture provides the cadence (start/end seconds) and the stable
    ``memory_id`` PatternAgent evidence cites against; we overwrite the
    numeric KPI fields with values derived from ``tracks_cache``. Session
    / run stamps are overwritten from the function args so callers don't
    need to re-normalise downstream.
    """
    video = tracks_cache.video
    frame_duration_s = video.vid_stride / video.fps if video.fps > 0 else 0.0

    results: list[KPIReport] = []
    for fixture in fixture_windows:
        stats = _compute_window_stats(
            tracks=tracks_cache.tracks,
            start_s=fixture.window_start_s,
            end_s=fixture.window_end_s,
            frame_duration_s=frame_duration_s,
        )
        # Schema requires frames_sampled >= 1; fall back to the fixture's
        # declared count (or a safe default) when the window had no
        # detections at all — this keeps the evidence pack valid even on
        # dead windows instead of crashing the whole run.
        frames_sampled = stats["frames_sampled"] or fixture.frames_sampled or 1

        results.append(
            KPIReport(
                window_start_s=fixture.window_start_s,
                window_end_s=fixture.window_end_s,
                frames_sampled=frames_sampled,
                staff_walk_distance_px=stats["staff_walk_distance_px"],
                staff_customer_crossings=stats["staff_customer_crossings"],
                queue_length_peak=stats["queue_length_peak"],
                queue_obstruction_seconds=stats["queue_obstruction_seconds"],
                congestion_score=stats["congestion_score"],
                table_detour_score=stats["table_detour_score"],
                session_id=session_id,
                run_id=run_id,
                memory_id=fixture.memory_id,
            )
        )
    return results


def _compute_window_stats(
    tracks: list[PersonTrack],
    start_s: float,
    end_s: float,
    frame_duration_s: float,
) -> dict:
    """Aggregate per-window stats. All numbers are deterministic and
    derived purely from ``tracks`` + time bounds — no randomness."""

    # Per-frame groupings by role for crossings + queue peak.
    customers_per_frame: dict[int, set[int]] = defaultdict(set)
    staff_per_frame: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    customer_positions_per_frame: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    queue_customers_per_frame: dict[int, set[int]] = defaultdict(set)

    staff_walk_distance_px = 0.0
    staff_zone_transitions = 0

    frames_seen: set[int] = set()

    for track in tracks:
        in_window = [d for d in track.detections if start_s <= d.timestamp_s < end_s]
        if not in_window:
            continue

        for det in in_window:
            frames_seen.add(det.frame_idx)

        if track.role == "staff":
            staff_walk_distance_px += _track_walk_distance(in_window)
            staff_zone_transitions += _zone_transition_count(in_window)
            for det in in_window:
                staff_per_frame[det.frame_idx].append(
                    (track.track_id, det.center_xy[0], det.center_xy[1])
                )

        elif track.role == "customer":
            for det in in_window:
                customers_per_frame[det.frame_idx].add(track.track_id)
                customer_positions_per_frame[det.frame_idx].append(
                    (track.track_id, det.center_xy[0], det.center_xy[1])
                )
                if det.zone_id == "queue":
                    queue_customers_per_frame[det.frame_idx].add(track.track_id)

    # Crossings: distinct (staff, customer) track-id pairs that came
    # within CROSSING_DISTANCE_PX on any frame in the window.
    crossing_pairs: set[tuple[int, int]] = set()
    for frame_idx, staff_list in staff_per_frame.items():
        customers_here = customer_positions_per_frame.get(frame_idx)
        if not customers_here:
            continue
        for staff_id, sx, sy in staff_list:
            for cust_id, cx, cy in customers_here:
                if math.hypot(sx - cx, sy - cy) <= CROSSING_DISTANCE_PX:
                    crossing_pairs.add((staff_id, cust_id))

    # Queue length: max per-frame distinct customer count inside the
    # queue polygon.
    queue_length_peak = max(
        (len(ids) for ids in queue_customers_per_frame.values()),
        default=0,
    )

    # Obstruction: frames where ≥ N customers sit in the queue polygon
    # simultaneously, converted to seconds via the sampling cadence.
    obstruction_frames = sum(
        1 for ids in queue_customers_per_frame.values() if len(ids) >= QUEUE_OBSTRUCTION_MIN
    )
    queue_obstruction_seconds = obstruction_frames * frame_duration_s

    total_window_frames = len(frames_seen) or 1
    obstruction_ratio = obstruction_frames / total_window_frames

    # Blended congestion score: queue pressure + how long that pressure
    # lasted + staff-customer near-misses. Clamped to [0, 1].
    congestion_score = min(
        1.0,
        0.4 * min(1.0, queue_length_peak / 5.0)
        + 0.4 * obstruction_ratio
        + 0.2 * min(1.0, len(crossing_pairs) / 10.0),
    )

    # Detour proxy: more staff zone hops in a window = more back-and-forth
    # wandering. Normalised against a conservative "5 transitions = peak"
    # reference and clipped at the schema-meaningful 3.0 upper bound.
    table_detour_score = min(3.0, staff_zone_transitions / 5.0)

    return {
        "frames_sampled": len(frames_seen),
        "staff_walk_distance_px": float(staff_walk_distance_px),
        "staff_customer_crossings": len(crossing_pairs),
        "queue_length_peak": queue_length_peak,
        "queue_obstruction_seconds": float(queue_obstruction_seconds),
        "congestion_score": float(congestion_score),
        "table_detour_score": float(table_detour_score),
    }


def _track_walk_distance(detections: list[TrackDetection]) -> float:
    """Sum Euclidean distance between consecutive detection centers."""
    if len(detections) < 2:
        return 0.0
    ordered = sorted(detections, key=lambda d: d.frame_idx)
    total = 0.0
    prev_x, prev_y = ordered[0].center_xy
    for det in ordered[1:]:
        x, y = det.center_xy
        total += math.hypot(x - prev_x, y - prev_y)
        prev_x, prev_y = x, y
    return total


def _zone_transition_count(detections: list[TrackDetection]) -> int:
    """Count zone changes along a track's detection sequence."""
    if len(detections) < 2:
        return 0
    ordered = sorted(detections, key=lambda d: d.frame_idx)
    transitions = 0
    prev_zone = ordered[0].zone_id
    for det in ordered[1:]:
        if det.zone_id != prev_zone:
            transitions += 1
            prev_zone = det.zone_id
    return transitions


__all__ = [
    "compute_kpi_windows",
    "CROSSING_DISTANCE_PX",
    "QUEUE_OBSTRUCTION_MIN",
    "STAFF_ZONE_IDS",
]
