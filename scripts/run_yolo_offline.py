#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "lap>=0.5.12",
#   "opencv-python-headless>=4.9.0",
#   "pydantic>=2.7.0",
#   "ultralytics>=8.3.0",
# ]
# ///
"""Run YOLO + ByteTrack on a CafeTwin session video."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.vision.tracks import (  # noqa: E402
    PersonTrack,
    TrackDetection,
    TracksCache,
    TrackVideoMetadata,
    build_summary,
    classify_track_role,
    load_zones,
    write_tracks_cache,
    zone_for_point,
)


def main() -> int:
    args = _parse_args()

    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Missing tracking dependencies. Run with: "
            "uv run scripts/run_yolo_offline.py --session real_cafe"
        ) from exc

    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    video_path = (ROOT_DIR / args.video).resolve() if args.video else _video_from_manifest(session_dir)
    zones_path = session_dir / "zones.json"
    output_path = Path(args.output) if args.output else session_dir / "tracks.cached.json"
    annotated_path = None if args.no_annotated else (
        Path(args.annotated) if args.annotated else session_dir / "annotated_before.mp4"
    )

    zones = load_zones(zones_path)
    metadata = _video_metadata(cv2, video_path, args.vid_stride)
    raw_tracks: dict[int, list[TrackDetection]] = defaultdict(list)

    writer = None
    model = YOLO(args.model)
    results = model.track(
        source=str(video_path),
        stream=True,
        persist=True,
        tracker=args.tracker,
        classes=[0],
        conf=args.conf,
        iou=args.iou,
        vid_stride=args.vid_stride,
        device=args.device,
        verbose=False,
    )

    processed_frames = 0
    frames_with_detections: set[int] = set()
    for result in results:
        frame_idx = processed_frames * args.vid_stride
        timestamp_s = frame_idx / metadata.fps
        frame = result.orig_img.copy()
        detections_for_frame = []

        boxes = result.boxes
        if boxes is not None and boxes.id is not None:
            xyxy = boxes.xyxy.cpu().tolist()
            ids = boxes.id.int().cpu().tolist()
            confs = boxes.conf.cpu().tolist()
            for track_id, bbox, confidence in zip(ids, xyxy, confs, strict=False):
                x1, y1, x2, y2 = [float(v) for v in bbox]
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                zone_id = zone_for_point(center[0], center[1], zones)
                detection = TrackDetection(
                    frame_idx=frame_idx,
                    timestamp_s=timestamp_s,
                    bbox_xyxy=(x1, y1, x2, y2),
                    center_xy=center,
                    confidence=float(confidence),
                    zone_id=zone_id,
                )
                raw_tracks[int(track_id)].append(detection)
                detections_for_frame.append((int(track_id), detection))
                frames_with_detections.add(frame_idx)

        if annotated_path:
            writer = writer or _open_writer(cv2, annotated_path, metadata, args.vid_stride)
            _draw_frame(cv2, frame, detections_for_frame)
            writer.write(frame)

        processed_frames += 1
        if args.max_processed_frames and processed_frames >= args.max_processed_frames:
            break

    if writer is not None:
        writer.release()

    tracks = []
    for track_id, detections in sorted(raw_tracks.items()):
        if len(detections) < args.min_detections:
            continue
        role, role_confidence = classify_track_role(detections)
        tracks.append(
            PersonTrack(
                track_id=track_id,
                role=role,
                role_confidence=role_confidence,
                detections=detections,
            )
        )

    cache = TracksCache(
        session_id=args.session,
        source_video=str(video_path.relative_to(ROOT_DIR)),
        model=args.model,
        tracker=args.tracker,
        generated_at=datetime.now(timezone.utc),
        video=TrackVideoMetadata(
            width=metadata.width,
            height=metadata.height,
            fps=metadata.fps,
            frame_count=metadata.frame_count,
            duration_s=metadata.duration_s,
            processed_frame_count=processed_frames,
            vid_stride=args.vid_stride,
        ),
        zone_ids=[str(zone["id"]) for zone in zones if "id" in zone],
        summary=build_summary(tracks),
        tracks=tracks,
    )
    write_tracks_cache(output_path, cache)

    print(f"[track] wrote {_display_path(output_path)}")
    print(
        "[track] "
        f"{cache.summary.track_count} tracks · "
        f"{cache.summary.detection_count} detections · "
        f"{cache.summary.frames_with_detections}/{processed_frames} frames with detections"
    )
    if annotated_path:
        print(f"[track] wrote {_display_path(annotated_path)}")
    return 0


class _Metadata:
    def __init__(self, width: int, height: int, fps: float, frame_count: int, duration_s: float):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = frame_count
        self.duration_s = duration_s


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="real_cafe")
    parser.add_argument("--video", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--annotated", default=None)
    parser.add_argument("--no-annotated", action="store_true")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--conf", type=float, default=0.20)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--vid-stride", type=int, default=3)
    parser.add_argument("--min-detections", type=int, default=3)
    parser.add_argument("--max-processed-frames", type=int, default=0)
    return parser.parse_args()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _video_from_manifest(session_dir: Path) -> Path:
    import json

    manifest = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    return ROOT_DIR / manifest["video_path"]


def _video_metadata(cv2, video_path: Path, vid_stride: int) -> _Metadata:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    duration_s = frame_count / fps if fps else 0.0
    if vid_stride < 1:
        raise SystemExit("--vid-stride must be >= 1")
    return _Metadata(width, height, fps, frame_count, duration_s)


def _open_writer(cv2, annotated_path: Path, metadata: _Metadata, vid_stride: int):
    annotated_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(
        str(annotated_path),
        fourcc,
        max(1.0, metadata.fps / vid_stride),
        (metadata.width, metadata.height),
    )


def _draw_frame(cv2, frame, detections: list[tuple[int, TrackDetection]]) -> None:
    for track_id, detection in detections:
        x1, y1, x2, y2 = [int(v) for v in detection.bbox_xyxy]
        color = (36, 99, 235)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"id:{track_id} {detection.confidence:.2f}"
        if detection.zone_id:
            label += f" {detection.zone_id}"
        cv2.putText(
            frame,
            label,
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )


if __name__ == "__main__":
    raise SystemExit(main())
