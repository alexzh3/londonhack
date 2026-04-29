#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "opencv-python-headless>=4.9.0",
#   "pydantic>=2.7.0",
#   "ultralytics>=8.3.0",
# ]
# ///
"""Detect static layout objects for a CafeTwin session frame/video."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
ULTRALYTICS_MODEL_DIR = ROOT_DIR / "models" / "ultralytics"
IMAGE_OUTPUT_DIR = ROOT_DIR / "images" / "static_layout_objects"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.vision.objects import (  # noqa: E402
    LayoutObjectClass,
    LayoutObjectDetection,
    ObjectDetectionsCache,
    ObjectFrame,
    ObjectImageMetadata,
    build_object_summary,
    write_object_detections_cache,
)
from app.vision.tracks import load_zones, zone_for_point  # noqa: E402


COCO_CLASS_IDS: dict[LayoutObjectClass, int] = {
    "person": 0,
    "chair": 56,
    "couch": 57,
    "potted plant": 58,
    "dining table": 60,
}
CLASS_ORDER: tuple[LayoutObjectClass, ...] = (
    "chair",
    "dining table",
    "couch",
    "potted plant",
    "person",
)
COLORS: dict[LayoutObjectClass, tuple[int, int, int]] = {
    "chair": (36, 99, 235),
    "dining table": (16, 185, 129),
    "couch": (147, 51, 234),
    "potted plant": (22, 163, 74),
    "person": (245, 158, 11),
}


@dataclass(frozen=True)
class FrameInput:
    frame: ObjectFrame
    image: Any


@dataclass(frozen=True)
class RawDetection:
    class_id: int
    class_name: LayoutObjectClass
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    center_xy: tuple[float, float]
    zone_id: str | None
    frame_id: str


def main() -> int:
    args = _parse_args()

    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Missing detection dependencies. Run with: "
            "uv run scripts/vision/detect_layout_objects.py --session ai_cafe_a"
        ) from exc

    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    output_path = Path(args.output) if args.output else session_dir / "object_detections.cached.json"
    annotated_path = None if args.no_annotated else (
        Path(args.annotated) if args.annotated else IMAGE_OUTPUT_DIR / f"{args.session}.jpg"
    )
    zones = load_zones(session_dir / "zones.json")
    target_classes = _parse_classes(args.classes, include_person=args.include_person)
    target_class_ids = [COCO_CLASS_IDS[class_name] for class_name in target_classes]

    frames = _load_frames(cv2, session_dir, args)
    if not frames:
        raise SystemExit("No frames loaded for object detection")

    session_frame = frames[0]
    model = YOLO(_resolve_model_path(args.model))
    raw_detections: list[RawDetection] = []
    frame_detection_counts: dict[str, int] = {}

    for frame_input in frames:
        results = model.predict(
            source=frame_input.image,
            classes=target_class_ids,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            augment=args.augment,
            max_det=args.max_det,
            verbose=False,
        )
        detections = _detections_from_result(
            results[0],
            frame_input.frame.frame_id,
            zones,
            include_video_person=args.include_video_person,
            frame_source=frame_input.frame.source,
        )
        raw_detections.extend(detections)
        frame_detection_counts[frame_input.frame.frame_id] = len(detections)

    frames_out = [
        frame_input.frame.model_copy(
            update={"raw_detection_count": frame_detection_counts.get(frame_input.frame.frame_id, 0)}
        )
        for frame_input in frames
    ]
    detections = _cluster_detections(raw_detections, args, zones)

    cache = ObjectDetectionsCache(
        session_id=args.session,
        model=args.model,
        generated_at=datetime.now(timezone.utc),
        image=ObjectImageMetadata(width=session_frame.frame.width, height=session_frame.frame.height),
        target_classes=target_classes,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        aggregate_iou_threshold=args.aggregate_iou,
        zone_ids=[str(zone["id"]) for zone in zones if "id" in zone],
        frames=frames_out,
        summary=build_object_summary(frames_out, detections),
        detections=detections,
    )
    write_object_detections_cache(output_path, cache)

    if annotated_path:
        _write_annotated(cv2, annotated_path, session_frame.image.copy(), detections)

    print(f"[objects] wrote {_display_path(output_path)}")
    print(
        "[objects] "
        f"{cache.summary.detection_count} objects from "
        f"{cache.summary.raw_detection_count} raw detections over {cache.summary.frame_count} frame(s)"
    )
    print(
        "[objects] classes: "
        + ", ".join(f"{name}={cache.summary.class_counts[name]}" for name in CLASS_ORDER)
    )
    if annotated_path:
        print(f"[objects] wrote {_display_path(annotated_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a")
    parser.add_argument("--frame", default=None)
    parser.add_argument("--video", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--annotated", default=None)
    parser.add_argument("--no-annotated", action="store_true")
    parser.add_argument("--model", default="yolov8x.pt")
    parser.add_argument("--classes", default="chair,dining table,couch,potted plant")
    parser.add_argument("--include-person", action="store_true")
    parser.add_argument("--include-video-person", action="store_true")
    parser.add_argument("--conf", type=float, default=0.12)
    parser.add_argument("--iou", type=float, default=0.60)
    parser.add_argument("--aggregate-iou", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--augment", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--sample-video-frames", type=int, default=8)
    parser.add_argument("--max-det", type=int, default=300)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--keep-single-conf", type=float, default=0.35)
    return parser.parse_args()


def _parse_classes(classes_csv: str, *, include_person: bool) -> list[LayoutObjectClass]:
    parsed = []
    for raw in classes_csv.split(","):
        name = raw.strip()
        if not name:
            continue
        if name not in COCO_CLASS_IDS:
            valid = ", ".join(COCO_CLASS_IDS)
            raise SystemExit(f"Unknown class {name!r}. Valid classes: {valid}")
        parsed.append(name)
    if include_person and "person" not in parsed:
        parsed.append("person")
    ordered = [name for name in CLASS_ORDER if name in parsed]
    if not ordered:
        raise SystemExit("No target classes selected")
    return ordered


def _load_frames(cv2, session_dir: Path, args: argparse.Namespace) -> list[FrameInput]:
    frame_path = Path(args.frame) if args.frame else session_dir / "frame.jpg"
    image = cv2.imread(str(frame_path))
    if image is None:
        raise SystemExit(f"Could not read frame: {frame_path}")
    height, width = image.shape[:2]
    frames = [
        FrameInput(
            frame=ObjectFrame(
                frame_id="session_frame",
                source="session_frame",
                image_path=str(frame_path.relative_to(ROOT_DIR)),
                width=width,
                height=height,
            ),
            image=image,
        )
    ]

    if args.sample_video_frames <= 0:
        return frames

    video_path = (ROOT_DIR / args.video).resolve() if args.video else _video_from_manifest(session_dir)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        cap.release()
        return frames

    indices = _sample_indices(frame_count, args.sample_video_frames)
    for sample_idx, frame_idx in enumerate(indices, start=1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, sample = cap.read()
        if not ok or sample is None:
            continue
        sample_h, sample_w = sample.shape[:2]
        if (sample_w, sample_h) != (width, height):
            sample = cv2.resize(sample, (width, height), interpolation=cv2.INTER_AREA)
        frames.append(
            FrameInput(
                frame=ObjectFrame(
                    frame_id=f"video_{sample_idx:02d}",
                    source="video_frame",
                    frame_idx=frame_idx,
                    timestamp_s=frame_idx / fps,
                    width=width,
                    height=height,
                ),
                image=sample,
            )
        )
    cap.release()
    return frames


def _sample_indices(frame_count: int, count: int) -> list[int]:
    if count <= 0:
        return []
    return sorted(
        {
            min(frame_count - 1, max(0, round((idx + 1) * frame_count / (count + 1))))
            for idx in range(count)
        }
    )


def _detections_from_result(
    result,
    frame_id: str,
    zones: list[dict],
    *,
    include_video_person: bool,
    frame_source: str,
) -> list[RawDetection]:
    boxes = result.boxes
    if boxes is None:
        return []
    xyxy = boxes.xyxy.cpu().tolist()
    confs = boxes.conf.cpu().tolist()
    classes = boxes.cls.int().cpu().tolist()
    detections: list[RawDetection] = []
    id_to_name = {class_id: name for name, class_id in COCO_CLASS_IDS.items()}
    for bbox, confidence, class_id in zip(xyxy, confs, classes, strict=False):
        class_name = id_to_name.get(int(class_id))
        if class_name is None:
            continue
        if class_name == "person" and frame_source == "video_frame" and not include_video_person:
            continue
        x1, y1, x2, y2 = [float(v) for v in bbox]
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        detections.append(
            RawDetection(
                class_id=int(class_id),
                class_name=class_name,
                confidence=float(confidence),
                bbox_xyxy=(x1, y1, x2, y2),
                center_xy=center,
                zone_id=zone_for_point(center[0], center[1], zones),
                frame_id=frame_id,
            )
        )
    return detections


def _cluster_detections(
    raw_detections: list[RawDetection],
    args: argparse.Namespace,
    zones: list[dict],
) -> list[LayoutObjectDetection]:
    clusters: list[list[RawDetection]] = []
    for detection in sorted(raw_detections, key=lambda item: item.confidence, reverse=True):
        best_index = None
        best_iou = 0.0
        for idx, cluster in enumerate(clusters):
            if cluster[0].class_name != detection.class_name:
                continue
            iou = _bbox_iou(_weighted_bbox(cluster), detection.bbox_xyxy)
            if iou > best_iou:
                best_iou = iou
                best_index = idx
        if best_index is not None and best_iou >= args.aggregate_iou:
            clusters[best_index].append(detection)
        else:
            clusters.append([detection])

    kept = [
        _cluster_to_detection(cluster, zones)
        for cluster in clusters
        if _keep_cluster(cluster, args)
    ]
    kept.sort(key=lambda item: (_class_sort_key(item.class_name), item.bbox_xyxy[1], item.bbox_xyxy[0]))
    return [
        detection.model_copy(update={"detection_id": f"{_slug(detection.class_name)}_{idx:03d}"})
        for idx, detection in enumerate(kept, start=1)
    ]


def _keep_cluster(cluster: list[RawDetection], args: argparse.Namespace) -> bool:
    support_count = len({detection.frame_id for detection in cluster})
    confidence = max(detection.confidence for detection in cluster)
    has_session_frame = any(detection.frame_id == "session_frame" for detection in cluster)
    return (
        support_count >= args.min_support
        or has_session_frame
        or confidence >= args.keep_single_conf
    )


def _cluster_to_detection(
    cluster: list[RawDetection],
    zones: list[dict],
) -> LayoutObjectDetection:
    bbox = _weighted_bbox(cluster)
    x1, y1, x2, y2 = bbox
    center = ((x1 + x2) / 2, (y1 + y2) / 2)
    source_frame_ids = sorted({detection.frame_id for detection in cluster})
    confidences = [detection.confidence for detection in cluster]
    return LayoutObjectDetection(
        detection_id="pending",
        class_id=cluster[0].class_id,
        class_name=cluster[0].class_name,
        confidence=max(confidences),
        confidence_mean=sum(confidences) / len(confidences),
        support_count=len(source_frame_ids),
        source_frame_ids=source_frame_ids,
        bbox_xyxy=bbox,
        center_xy=center,
        area_px=max(0.0, x2 - x1) * max(0.0, y2 - y1),
        zone_id=zone_for_point(center[0], center[1], zones),
    )


def _weighted_bbox(cluster: list[RawDetection]) -> tuple[float, float, float, float]:
    total = sum(max(detection.confidence, 1e-6) for detection in cluster)
    return tuple(
        sum(detection.bbox_xyxy[idx] * max(detection.confidence, 1e-6) for detection in cluster)
        / total
        for idx in range(4)
    )


def _bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / ((area_a + area_b - inter) or 1e-9)


def _write_annotated(cv2, path: Path, image, detections: list[LayoutObjectDetection]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for detection in detections:
        x1, y1, x2, y2 = [int(v) for v in detection.bbox_xyxy]
        color = COLORS[detection.class_name]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = (
            f"{detection.class_name} {detection.confidence:.2f}"
            f" x{detection.support_count}"
        )
        if detection.zone_id:
            label += f" {detection.zone_id}"
        cv2.putText(
            image,
            label,
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), image)


def _video_from_manifest(session_dir: Path) -> Path:
    manifest = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    return ROOT_DIR / manifest["video_path"]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _resolve_model_path(model: str) -> str:
    path = Path(model)
    if path.is_absolute():
        return str(path)
    if len(path.parts) > 1:
        rooted = ROOT_DIR / path
        return str(rooted if rooted.exists() else path)
    local_model = ULTRALYTICS_MODEL_DIR / model
    return str(local_model if local_model.exists() else model)


def _class_sort_key(class_name: LayoutObjectClass) -> int:
    return CLASS_ORDER.index(class_name)


def _slug(class_name: str) -> str:
    return class_name.replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
