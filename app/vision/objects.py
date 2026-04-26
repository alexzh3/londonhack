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


def write_object_detector_benchmark(path: Path, report: ObjectDetectorBenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
