"""Static object detection cache contract for Tier 1 layout perception."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


LayoutObjectClass = Literal["chair", "dining table", "couch", "potted plant", "person"]


class ObjectFrame(StrictModel):
    frame_id: str
    source: Literal["session_frame", "video_frame"]
    image_path: str | None = None
    frame_idx: int | None = Field(default=None, ge=0)
    timestamp_s: float | None = Field(default=None, ge=0.0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    raw_detection_count: int = Field(default=0, ge=0)


class LayoutObjectDetection(StrictModel):
    detection_id: str
    class_id: int = Field(ge=0)
    class_name: LayoutObjectClass
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_mean: float = Field(ge=0.0, le=1.0)
    support_count: int = Field(ge=1)
    source_frame_ids: list[str] = Field(min_length=1)
    bbox_xyxy: tuple[float, float, float, float]
    center_xy: tuple[float, float]
    area_px: float = Field(ge=0.0)
    zone_id: str | None = None

    @model_validator(mode="after")
    def _validate_geometry(self) -> "LayoutObjectDetection":
        x1, y1, x2, y2 = self.bbox_xyxy
        cx, cy = self.center_xy
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox_xyxy must have positive width and height")
        if not (x1 <= cx <= x2 and y1 <= cy <= y2):
            raise ValueError("center_xy must be inside bbox_xyxy")
        return self


class ObjectImageMetadata(StrictModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ObjectDetectionSummary(StrictModel):
    detection_count: int = Field(ge=0)
    raw_detection_count: int = Field(ge=0)
    frame_count: int = Field(ge=1)
    class_counts: dict[LayoutObjectClass, int]
    zone_counts: dict[str, int]


class ObjectDetectionsCache(StrictModel):
    schema_version: Literal["cafetwin.objects.v1"] = "cafetwin.objects.v1"
    session_id: str
    source: Literal[
        "ultralytics_yolo_static_objects",
        "moondream_static_objects",
        "hybrid_vlm_static_objects",
    ] = "ultralytics_yolo_static_objects"
    model: str
    generated_at: datetime
    image: ObjectImageMetadata
    target_classes: list[LayoutObjectClass]
    conf_threshold: float = Field(ge=0.0, le=1.0)
    iou_threshold: float = Field(ge=0.0, le=1.0)
    aggregate_iou_threshold: float = Field(ge=0.0, le=1.0)
    zone_ids: list[str]
    frames: list[ObjectFrame] = Field(min_length=1)
    summary: ObjectDetectionSummary
    detections: list[LayoutObjectDetection]


class ObjectDetectorBenchmarkEntry(StrictModel):
    model: str
    output_path: str
    annotated_path: str | None = None
    detection_count: int = Field(ge=0)
    raw_detection_count: int = Field(ge=0)
    class_counts: dict[LayoutObjectClass, int]


class ObjectDetectorBenchmarkReport(StrictModel):
    schema_version: Literal["cafetwin.object_detector_benchmark.v1"] = (
        "cafetwin.object_detector_benchmark.v1"
    )
    session_id: str
    generated_at: datetime
    models: list[str] = Field(min_length=1)
    entries: list[ObjectDetectorBenchmarkEntry] = Field(min_length=1)


class ObjectReviewBundle(StrictModel):
    session_id: str
    detector_cache: ObjectDetectionsCache
    vlm_cache: ObjectDetectionsCache | None = None


class ObjectReviewDecision(StrictModel):
    detection_id: str
    action: Literal["keep", "drop"]
    reason: str = Field(min_length=1)


class ObjectReviewResult(StrictModel):
    schema_version: Literal["cafetwin.object_review.v1"] = "cafetwin.object_review.v1"
    session_id: str
    decisions: list[ObjectReviewDecision]
    notes: list[str] = Field(default_factory=list)


def build_object_summary(
    frames: list[ObjectFrame],
    detections: list[LayoutObjectDetection],
) -> ObjectDetectionSummary:
    class_counts: dict[LayoutObjectClass, int] = {
        "chair": 0,
        "dining table": 0,
        "couch": 0,
        "potted plant": 0,
        "person": 0,
    }
    zone_counts: dict[str, int] = {}
    for detection in detections:
        class_counts[detection.class_name] += 1
        if detection.zone_id:
            zone_counts[detection.zone_id] = zone_counts.get(detection.zone_id, 0) + 1
    return ObjectDetectionSummary(
        detection_count=len(detections),
        raw_detection_count=sum(frame.raw_detection_count for frame in frames),
        frame_count=len(frames),
        class_counts=class_counts,
        zone_counts=zone_counts,
    )


def load_object_detections_cache(path: Path) -> ObjectDetectionsCache:
    return ObjectDetectionsCache.model_validate_json(path.read_text(encoding="utf-8"))


def write_object_detections_cache(path: Path, cache: ObjectDetectionsCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_object_review_result(path: Path) -> ObjectReviewResult:
    return ObjectReviewResult.model_validate_json(path.read_text(encoding="utf-8"))


def write_object_review_result(path: Path, review: ObjectReviewResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2) + "\n", encoding="utf-8")


def reviewed_object_cache(
    detector_cache: ObjectDetectionsCache,
    review: ObjectReviewResult,
    *,
    model: str,
    generated_at: datetime,
    source: Literal[
        "ultralytics_yolo_static_objects",
        "moondream_static_objects",
        "hybrid_vlm_static_objects",
    ] = "hybrid_vlm_static_objects",
) -> ObjectDetectionsCache:
    keep_ids = {
        decision.detection_id
        for decision in review.decisions
        if decision.action == "keep"
    }
    detections = [
        detection
        for detection in detector_cache.detections
        if detection.detection_id in keep_ids
    ]
    return detector_cache.model_copy(
        update={
            "source": source,
            "model": model,
            "generated_at": generated_at,
            "summary": build_object_summary(detector_cache.frames, detections),
            "detections": detections,
        },
        deep=True,
    )


# ---------- Tier 1F: live → fixture inventory bridge ---------------------
#
# Convert YOLO/VLM `LayoutObjectDetection`s (from
# `object_detections.reviewed.cached.json` or the unreviewed sibling) into
# agent-facing `SceneObject`s, then *augment* (not replace) the fixture
# `ObjectInventory` so the cached recommendation's `target_id` stays
# valid. The agent gets a richer object set to reason over while the
# fallback path keeps working.

# YOLO COCO classes → agent's narrower ObjectKind enum. `person` is
# intentionally skipped — those land in the tracks pipeline, not the
# scene-object inventory. `couch` maps to `chair` because the agent's
# layout reasoning treats them as seating.
LAYOUT_CLASS_TO_OBJECT_KIND: dict[LayoutObjectClass, str] = {
    "chair": "chair",
    "dining table": "table",
    "couch": "chair",
    "potted plant": "plant",
    # "person": skipped
}


def _bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    """Standard axis-aligned IoU. Returns 0.0 on degenerate boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = a_area + b_area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def detection_to_scene_object_dict(
    detection: LayoutObjectDetection,
) -> dict | None:
    """Map a YOLO/VLM detection to a `SceneObject`-shaped dict.

    Returns None for classes that don't translate to the agent's
    scene-object inventory (e.g. ``person``).

    The dict shape avoids importing `app.schemas.SceneObject` directly so
    this module stays free of `app.*` dependencies — callers in
    `evidence_pack.py` validate via Pydantic when they hand the dict to
    `ObjectInventory`.
    """
    kind = LAYOUT_CLASS_TO_OBJECT_KIND.get(detection.class_name)
    if kind is None:
        return None
    x1, y1, x2, y2 = detection.bbox_xyxy
    cx, cy = detection.center_xy
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    label_class = detection.class_name.replace("_", " ").title()
    return {
        "id": f"vision_{detection.detection_id}",
        "kind": kind,
        "label": (
            f"Detected {label_class.lower()} (YOLO+VLM, "
            f"{detection.support_count}f, conf={detection.confidence_mean:.2f})"
        ),
        "bbox_xyxy": (x1, y1, x2, y2),
        "center_xy": (cx, cy),
        "size_xy": (width, height),
        "rotation_degrees": 0.0,
        "zone_id": detection.zone_id,
        "movable": kind in ("chair", "table", "plant"),
        "confidence": float(detection.confidence_mean),
        "source": "vision",
    }


def select_live_detections_for_inventory(
    detections: list[LayoutObjectDetection],
    fixture_bboxes: list[tuple[float, float, float, float]],
    *,
    iou_overlap_threshold: float = 0.5,
) -> list[dict]:
    """Pick the subset of detections worth appending to a fixture
    inventory. Drops detections that are likely re-discoveries of an
    already-named fixture object (IoU > threshold) and drops classes
    that don't map to ObjectKind."""
    selected: list[dict] = []
    for detection in detections:
        candidate = detection_to_scene_object_dict(detection)
        if candidate is None:
            continue
        if any(
            _bbox_iou(candidate["bbox_xyxy"], fixture_bbox) > iou_overlap_threshold
            for fixture_bbox in fixture_bboxes
        ):
            continue
        selected.append(candidate)
    return selected


def write_object_detector_benchmark(path: Path, report: ObjectDetectorBenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
