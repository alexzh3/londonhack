#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "opencv-python-headless>=4.9.0",
#   "pydantic>=2.7.0",
# ]
# ///
"""Overlay everything we know about a CafeTwin session on its CCTV.

Where `run_yolo_offline.py` only draws *person* boxes (the YOLOv8n + ByteTrack
output), this script renders a single rich annotated video that overlays
**all** the perception caches we have for a session:

  - Zone polygons from `zones.json` (semi-transparent fills).
  - Static layout objects from `object_detections.reviewed.cached.json`
    (or the unreviewed sibling) — chairs, tables, couches, plants — drawn
    at fixed positions on every frame, since these are stationary.
  - Person tracks from `tracks.cached.json` — coloured by track id, with
    the ByteTrack id and zone label.

The output overwrites `demo_data/sessions/<slug>/annotated_before.mp4`.
After running this, re-run `scripts/transcode_annotated_for_web.sh` to
produce the H.264 `.web.mp4` the frontend prefers.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# Class colour palette in BGR order (OpenCV default). Picked from a warm
# cafe palette so the overlay reads as "annotation" not "alert".
CLASS_COLORS = {
    "person": (235, 99, 36),         # blue-ish
    "chair": (96, 200, 96),          # green
    "dining table": (40, 130, 220),  # orange
    "table": (40, 130, 220),
    "couch": (180, 90, 180),         # purple
    "potted plant": (96, 180, 144),  # teal
    "plant": (96, 180, 144),
}
DEFAULT_CLASS_COLOR = (200, 200, 200)


def main() -> int:
    args = _parse_args()
    try:
        import cv2
    except ImportError as exc:
        raise SystemExit(
            "Missing opencv. Run with: uv run scripts/render_rich_annotated_video.py --session ai_cafe_a"
        ) from exc

    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    if not session_dir.is_dir():
        raise SystemExit(f"Session not found: {session_dir}")

    tracks_cache = _load_json(session_dir / "tracks.cached.json", required=True)
    objects_cache = _load_objects_cache(session_dir)
    zones = _load_json(session_dir / "zones.json", required=False) or []

    video_rel = tracks_cache["source_video"]
    video_path = (ROOT_DIR / video_rel).resolve()
    if not video_path.is_file():
        raise SystemExit(f"Source video not found: {video_path}")

    out_path = Path(args.output) if args.output else session_dir / "annotated_before.mp4"
    vid_meta = tracks_cache["video"]
    vid_stride = int(vid_meta["vid_stride"])
    fps = float(vid_meta["fps"])
    width = int(vid_meta["width"])
    height = int(vid_meta["height"])

    # Build per-frame person detections indexed by raw frame_idx.
    per_frame_persons: dict[int, list[dict]] = defaultdict(list)
    for track in tracks_cache.get("tracks", []):
        track_id = track["track_id"]
        role = track.get("role", "person")
        for det in track.get("detections", []):
            per_frame_persons[int(det["frame_idx"])].append(
                {
                    "track_id": track_id,
                    "role": role,
                    "bbox": det["bbox_xyxy"],
                    "confidence": det.get("confidence", 0.0),
                    "zone_id": det.get("zone_id"),
                }
            )

    static_objects = objects_cache.get("detections", []) if objects_cache else []
    print(
        f"[render] {args.session}: {len(tracks_cache.get('tracks', []))} tracks · "
        f"{sum(len(v) for v in per_frame_persons.values())} person detections · "
        f"{len(static_objects)} static objects · {len(zones)} zones"
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_fps = max(1.0, fps / vid_stride)
    writer = cv2.VideoWriter(str(out_path), fourcc, out_fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise SystemExit(f"Could not open writer: {out_path}")

    # Pre-render the static-object overlay once — they're stationary, so
    # we'll just `cv2.add` it onto every frame instead of redrawing per
    # frame (saves ~40% wall time on the 15s ai_cafe video).
    static_layer = _build_static_layer(cv2, height, width, static_objects, zones)

    written = 0
    frame_idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        # Skip frames not covered by tracks (they used vid_stride=2 or 3).
        if frame_idx % vid_stride != 0:
            continue

        # Composite: alpha-blend the static overlay (zones + objects) under
        # the live person boxes so persons are always on top and readable.
        cv2.addWeighted(static_layer, 1.0, frame, 1.0, 0, dst=frame)
        _draw_persons(cv2, frame, per_frame_persons.get(frame_idx, []))
        writer.write(frame)
        written += 1

    cap.release()
    writer.release()
    print(f"[render] wrote {_display_path(out_path)} · {written} frames @ {out_fps:.1f} fps")
    return 0


def _build_static_layer(cv2, height: int, width: int, static_objects: list[dict],
                         zones: list[dict]):
    """Build a transparent BGR layer with zones + static objects pre-drawn.

    Returns a frame-shaped np.ndarray we can `addWeighted` against each
    incoming raw frame. Zones get a 12% fill so they tint the floor without
    obscuring detail; static-object rectangles + labels are fully opaque.
    """
    import numpy as np

    layer = np.zeros((height, width, 3), dtype="uint8")

    # Zones — semi-transparent fills with a brighter outline. Each zone
    # carries a `color_hex` from the manual fixture; we fall back to a
    # neutral cool grey when missing.
    for zone in zones:
        polygon = zone.get("polygon") or []
        if len(polygon) < 3:
            continue
        pts = np.array([[int(p[0]), int(p[1])] for p in polygon], dtype="int32")
        color = _hex_to_bgr(zone.get("color_hex"), default=(180, 180, 180))
        # Soft fill via overlay scaled later in the alpha blend.
        fill = np.zeros_like(layer)
        cv2.fillPoly(fill, [pts], color)
        layer = cv2.addWeighted(fill, 0.18, layer, 1.0, 0)
        cv2.polylines(layer, [pts], isClosed=True, color=color, thickness=2)
        # Zone label near the polygon centroid.
        cx = int(sum(p[0] for p in polygon) / len(polygon))
        cy = int(sum(p[1] for p in polygon) / len(polygon))
        label = zone.get("id") or zone.get("name") or ""
        if label:
            _draw_label(cv2, layer, label, (cx - 30, cy), color)

    # Static objects — boxes + class labels with confidence.
    for det in static_objects:
        bbox = det.get("bbox_xyxy")
        if not bbox or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = (int(v) for v in bbox)
        cls = det.get("class_name") or "object"
        color = CLASS_COLORS.get(cls, DEFAULT_CLASS_COLOR)
        cv2.rectangle(layer, (x1, y1), (x2, y2), color, 2)
        conf = det.get("confidence", det.get("confidence_mean", 0.0)) or 0.0
        _draw_label(cv2, layer, f"{cls} {conf:.2f}", (x1, max(18, y1 - 6)), color)

    return layer


def _draw_persons(cv2, frame, detections: list[dict]) -> None:
    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        color = CLASS_COLORS["person"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"id:{det['track_id']}"
        zone = det.get("zone_id")
        if zone:
            label += f" · {zone}"
        _draw_label(cv2, frame, label, (x1, max(18, y1 - 6)), color)


def _draw_label(cv2, img, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    """Filled background pill with white text — readable on busy CCTV."""
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    x, y = origin
    pad = 3
    bg_x1, bg_y1 = x, y - th - pad
    bg_x2, bg_y2 = x + tw + 2 * pad, y + baseline
    cv2.rectangle(img, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)
    cv2.putText(img, text, (x + pad, y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)


def _hex_to_bgr(hex_color: str | None, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if not hex_color:
        return default
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return default
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return (b, g, r)
    except ValueError:
        return default


def _load_objects_cache(session_dir: Path) -> dict | None:
    """Prefer the agent-reviewed object cache, fall back to the raw one."""
    reviewed = session_dir / "object_detections.reviewed.cached.json"
    raw = session_dir / "object_detections.cached.json"
    return _load_json(reviewed, required=False) or _load_json(raw, required=False)


def _load_json(path: Path, required: bool) -> dict | list | None:
    if not path.is_file():
        if required:
            raise SystemExit(f"Required cache missing: {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a",
                        help="Session slug under demo_data/sessions/")
    parser.add_argument("--output", default=None,
                        help="Override output path (defaults to <session>/annotated_before.mp4)")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
