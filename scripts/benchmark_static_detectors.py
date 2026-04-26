#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "opencv-python-headless>=4.9.0",
#   "pydantic>=2.7.0",
#   "ultralytics>=8.3.0",
# ]
# ///
"""Benchmark static layout detectors on the same CafeTwin session frames."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.vision.objects import (  # noqa: E402
    ObjectDetectorBenchmarkEntry,
    ObjectDetectorBenchmarkReport,
    load_object_detections_cache,
    write_object_detector_benchmark,
)


DETECT_SCRIPT = ROOT_DIR / "scripts" / "detect_layout_objects.py"


def main() -> int:
    args = _parse_args()
    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    output_dir = Path(args.output_dir) if args.output_dir else (
        session_dir / "object_detector_benchmark"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    models = [model.strip() for model in args.models.split(",") if model.strip()]
    if not models:
        raise SystemExit("--models must include at least one model")

    entries = []
    for model in models:
        slug = _model_slug(model)
        output_path = output_dir / f"{slug}.cached.json"
        annotated_path = None if args.no_annotated else output_dir / f"{slug}.annotated.jpg"
        _run_detector(args, model, output_path, annotated_path)
        cache = load_object_detections_cache(output_path)
        entries.append(
            ObjectDetectorBenchmarkEntry(
                model=model,
                output_path=_display_path(output_path),
                annotated_path=_display_path(annotated_path) if annotated_path else None,
                detection_count=cache.summary.detection_count,
                raw_detection_count=cache.summary.raw_detection_count,
                class_counts=cache.summary.class_counts,
            )
        )

    report = ObjectDetectorBenchmarkReport(
        session_id=args.session,
        generated_at=datetime.now(timezone.utc),
        models=models,
        entries=entries,
    )
    report_path = Path(args.report) if args.report else output_dir / "benchmark.json"
    write_object_detector_benchmark(report_path, report)

    print(f"[benchmark] wrote {_display_path(report_path)}")
    for entry in entries:
        counts = ", ".join(f"{key}={value}" for key, value in entry.class_counts.items())
        print(
            f"[benchmark] {entry.model}: "
            f"{entry.detection_count} objects from {entry.raw_detection_count} raw · {counts}"
        )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a")
    parser.add_argument("--models", default="yolov8x.pt,rtdetr-x.pt,yolo11x.pt")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--report", default=None)
    parser.add_argument("--no-annotated", action="store_true")
    parser.add_argument("--classes", default="chair,dining table,couch,potted plant")
    parser.add_argument("--conf", type=float, default=0.12)
    parser.add_argument("--iou", type=float, default=0.60)
    parser.add_argument("--aggregate-iou", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--sample-video-frames", type=int, default=8)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--keep-single-conf", type=float, default=0.35)
    return parser.parse_args()


def _run_detector(
    args: argparse.Namespace,
    model: str,
    output_path: Path,
    annotated_path: Path | None,
) -> None:
    command = [
        sys.executable,
        str(DETECT_SCRIPT),
        "--session",
        args.session,
        "--model",
        model,
        "--classes",
        args.classes,
        "--conf",
        str(args.conf),
        "--iou",
        str(args.iou),
        "--aggregate-iou",
        str(args.aggregate_iou),
        "--imgsz",
        str(args.imgsz),
        "--device",
        args.device,
        "--sample-video-frames",
        str(args.sample_video_frames),
        "--min-support",
        str(args.min_support),
        "--keep-single-conf",
        str(args.keep_single_conf),
        "--output",
        str(output_path),
    ]
    if annotated_path:
        command.extend(["--annotated", str(annotated_path)])
    else:
        command.append("--no-annotated")
    print(f"[benchmark] running {model} ...")
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def _model_slug(model: str) -> str:
    return (
        model.replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
