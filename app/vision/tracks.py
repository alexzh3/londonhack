"""Track cache contract for Tier 1 real CCTV perception."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TrackRole = Literal["staff", "customer", "unknown"]


class TrackDetection(StrictModel):
    frame_idx: int = Field(ge=0)
    timestamp_s: float = Field(ge=0.0)
    bbox_xyxy: tuple[float, float, float, float]
    center_xy: tuple[float, float]
    confidence: float = Field(ge=0.0, le=1.0)
    zone_id: str | None = None


class PersonTrack(StrictModel):
    track_id: int
    role: TrackRole = "unknown"
    role_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    class_name: Literal["person"] = "person"
    detections: list[TrackDetection] = Field(min_length=1)


class TrackVideoMetadata(StrictModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0.0)
    frame_count: int = Field(ge=0)
    duration_s: float = Field(ge=0.0)
    processed_frame_count: int = Field(ge=0)
    vid_stride: int = Field(ge=1)


class TrackSummary(StrictModel):
    track_count: int = Field(ge=0)
    detection_count: int = Field(ge=0)
    frames_with_detections: int = Field(ge=0)
    role_counts: dict[TrackRole, int]


class TracksCache(StrictModel):
    schema_version: Literal["cafetwin.tracks.v1"] = "cafetwin.tracks.v1"
    session_id: str
    source_video: str
    source: Literal["ultralytics_yolo_bytetrack"] = "ultralytics_yolo_bytetrack"
    model: str
    tracker: str
    generated_at: datetime
    video: TrackVideoMetadata
    zone_ids: list[str]
    summary: TrackSummary
    tracks: list[PersonTrack]


def load_tracks_cache(path: Path) -> TracksCache:
    return TracksCache.model_validate_json(path.read_text(encoding="utf-8"))


def write_tracks_cache(path: Path, cache: TracksCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.model_dump_json(indent=2) + "\n", encoding="utf-8")


def zone_for_point(x: float, y: float, zones: list[dict]) -> str | None:
    for zone in zones:
        polygon = zone.get("polygon")
        if isinstance(polygon, list) and _point_in_polygon(x, y, polygon):
            zone_id = zone.get("id")
            return zone_id if isinstance(zone_id, str) else None
    return None


def classify_track_role(detections: list[TrackDetection]) -> tuple[TrackRole, float]:
    if not detections:
        return "unknown", 0.0

    counts: dict[str, int] = {}
    for detection in detections:
        if detection.zone_id:
            counts[detection.zone_id] = counts.get(detection.zone_id, 0) + 1

    if not counts:
        return "unknown", 0.0

    staff_score = sum(counts.get(zone, 0) for zone in ("counter", "staff_path", "pickup"))
    customer_score = sum(counts.get(zone, 0) for zone in ("queue", "seating", "entrance"))
    total = len(detections)

    if staff_score > customer_score and staff_score / total >= 0.35:
        return "staff", staff_score / total
    if customer_score > staff_score and customer_score / total >= 0.35:
        return "customer", customer_score / total
    return "unknown", max(staff_score, customer_score) / total


def build_summary(tracks: list[PersonTrack]) -> TrackSummary:
    detection_count = sum(len(track.detections) for track in tracks)
    frames = {
        detection.frame_idx
        for track in tracks
        for detection in track.detections
    }
    role_counts: dict[TrackRole, int] = {"staff": 0, "customer": 0, "unknown": 0}
    for track in tracks:
        role_counts[track.role] += 1
    return TrackSummary(
        track_count=len(tracks),
        detection_count=detection_count,
        frames_with_detections=len(frames),
        role_counts=role_counts,
    )


def _point_in_polygon(x: float, y: float, polygon: list) -> bool:
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def load_zones(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
