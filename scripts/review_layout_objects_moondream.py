#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "moondream>=1.1.0",
#   "opencv-python-headless>=4.9.0",
#   "pillow>=10.0.0",
#   "pydantic>=2.7.0",
# ]
# ///
"""Run Moondream open-vocabulary static object detection for a CafeTwin session."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
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
PROMPTS: dict[LayoutObjectClass, str] = {
    "chair": "chair",
    "dining table": "dining table or cafe table",
    "couch": "couch or sofa",
    "potted plant": "potted plant",
    "person": "person",
}
COLORS: dict[LayoutObjectClass, tuple[int, int, int]] = {
    "chair": (36, 99, 235),
    "dining table": (16, 185, 129),
    "couch": (147, 51, 234),
    "potted plant": (22, 163, 74),
    "person": (245, 158, 11),
}


def main() -> int:
    args = _parse_args()
    api_key = os.getenv(args.api_key_env)
    use_local = args.local or args.backend == "photon"
    if not use_local and not api_key:
        raise SystemExit(
            f"{args.api_key_env} is not set; Moondream cloud detection needs an API key. "
            "Run the detector benchmark now, then rerun this once the key is available."
        )

    try:
        import cv2
        import moondream
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Missing Moondream dependencies. Run with: "
            "uv run scripts/review_layout_objects_moondream.py --session ai_cafe_a"
        ) from exc

    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    frame_path = Path(args.frame) if args.frame else session_dir / "frame.jpg"
    output_path = Path(args.output) if args.output else (
        session_dir / "object_detections.moondream.cached.json"
    )
    annotated_path = None if args.no_annotated else (
        Path(args.annotated) if args.annotated else session_dir / "object_detections.moondream.jpg"
    )

    image = Image.open(frame_path).convert("RGB")
    width, height = image.size
    zones = load_zones(session_dir / "zones.json")
    target_classes = _parse_classes(args.classes)
    model = _load_moondream_model(moondream, args, api_key=api_key, local=use_local)
    model_label = _model_label(args, local=use_local)

    detections = []
    for class_name in target_classes:
        result = model.detect(image, object=PROMPTS[class_name])
        for idx, region in enumerate(result.get("objects", []), start=1):
            bbox = _region_to_bbox(region, width, height)
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            detections.append(
                LayoutObjectDetection(
                    detection_id=f"moondream_{_slug(class_name)}_{idx:03d}",
                    class_id=COCO_CLASS_IDS[class_name],
                    class_name=class_name,
                    confidence=args.vlm_confidence,
                    confidence_mean=args.vlm_confidence,
                    support_count=1,
                    source_frame_ids=["session_frame"],
                    bbox_xyxy=bbox,
                    center_xy=center,
                    area_px=max(0.0, x2 - x1) * max(0.0, y2 - y1),
                    zone_id=zone_for_point(center[0], center[1], zones),
                )
            )

    frame = ObjectFrame(
        frame_id="session_frame",
        source="session_frame",
        image_path=str(frame_path.relative_to(ROOT_DIR)),
        width=width,
        height=height,
        raw_detection_count=len(detections),
    )
    cache = ObjectDetectionsCache(
        session_id=args.session,
        source="moondream_static_objects",
        model=model_label,
        generated_at=datetime.now(timezone.utc),
        image=ObjectImageMetadata(width=width, height=height),
        target_classes=target_classes,
        conf_threshold=args.vlm_confidence,
        iou_threshold=0.0,
        aggregate_iou_threshold=0.0,
        zone_ids=[str(zone["id"]) for zone in zones if "id" in zone],
        frames=[frame],
        summary=build_object_summary([frame], detections),
        detections=detections,
    )
    write_object_detections_cache(output_path, cache)

    if annotated_path:
        bgr = cv2.imread(str(frame_path))
        if bgr is not None:
            _write_annotated(cv2, annotated_path, bgr, detections)

    print(f"[moondream] wrote {_display_path(output_path)}")
    print(
        "[moondream] "
        f"{cache.summary.detection_count} objects · "
        + ", ".join(f"{name}={cache.summary.class_counts[name]}" for name in target_classes)
    )
    if annotated_path:
        print(f"[moondream] wrote {_display_path(annotated_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a")
    parser.add_argument("--frame", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--annotated", default=None)
    parser.add_argument("--no-annotated", action="store_true")
    parser.add_argument("--classes", default="chair,dining table,couch,potted plant")
    parser.add_argument("--api-key-env", default="MOONDREAM_API_KEY")
    parser.add_argument("--model", default=None)
    parser.add_argument("--backend", choices=["cloud", "photon"], default="cloud")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-batch-size", type=int, default=1)
    parser.add_argument("--kv-cache-pages", type=int, default=2048)
    parser.add_argument("--vlm-confidence", type=float, default=0.55)
    return parser.parse_args()


def _load_moondream_model(moondream, args: argparse.Namespace, *, api_key: str | None, local: bool):
    if local:
        local_model = args.model or "moondream2"
        return moondream.vl(
            local=True,
            api_key=api_key,
            model=local_model,
            device=args.device,
            max_batch_size=args.max_batch_size,
            kv_cache_pages=args.kv_cache_pages,
        )
    return moondream.CloudVL(api_key=api_key, model=args.model)


def _model_label(args: argparse.Namespace, *, local: bool) -> str:
    if local:
        return f"moondream-local-photon:{args.model or 'moondream2'}:{args.device}"
    return f"moondream-cloud:{args.model or 'default'}"


def _parse_classes(classes_csv: str) -> list[LayoutObjectClass]:
    classes = []
    for raw in classes_csv.split(","):
        name = raw.strip()
        if not name:
            continue
        if name not in COCO_CLASS_IDS:
            valid = ", ".join(COCO_CLASS_IDS)
            raise SystemExit(f"Unknown class {name!r}. Valid classes: {valid}")
        classes.append(name)
    if not classes:
        raise SystemExit("No target classes selected")
    return classes


def _region_to_bbox(region: dict, width: int, height: int) -> tuple[float, float, float, float] | None:
    try:
        x1 = float(region["x_min"])
        y1 = float(region["y_min"])
        x2 = float(region["x_max"])
        y2 = float(region["y_max"])
    except (KeyError, TypeError, ValueError):
        return None
    if max(x1, y1, x2, y2) <= 1.5:
        x1 *= width
        x2 *= width
        y1 *= height
        y2 *= height
    x1 = min(max(0.0, x1), width)
    x2 = min(max(0.0, x2), width)
    y1 = min(max(0.0, y1), height)
    y2 = min(max(0.0, y2), height)
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _write_annotated(cv2, path: Path, image, detections: list[LayoutObjectDetection]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for detection in detections:
        x1, y1, x2, y2 = [int(v) for v in detection.bbox_xyxy]
        color = COLORS[detection.class_name]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"moondream {detection.class_name}"
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


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _slug(class_name: str) -> str:
    return class_name.replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
