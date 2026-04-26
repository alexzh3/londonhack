from pathlib import Path

import pytest

from app.vision.tracks import load_tracks_cache


@pytest.mark.parametrize(
    ("session_id", "source_video", "width", "height"),
    [
        ("ai_cafe_a", "cafe_videos/ai_generated_cctv.mp4", 1924, 1076),
        ("real_cafe", "cafe_videos/real_cctv.mp4", 1280, 720),
    ],
)
def test_tracks_cache_validates(session_id, source_video, width, height):
    path = Path("demo_data/sessions") / session_id / "tracks.cached.json"

    cache = load_tracks_cache(path)

    assert cache.session_id == session_id
    assert cache.source_video == source_video
    assert cache.source == "ultralytics_yolo_bytetrack"
    assert cache.video.width == width
    assert cache.video.height == height
    assert cache.video.processed_frame_count > 0
    assert cache.summary.track_count == len(cache.tracks)
    assert cache.summary.detection_count == sum(len(track.detections) for track in cache.tracks)
    assert cache.summary.role_counts["staff"] + cache.summary.role_counts["customer"] > 0
    assert {"counter", "pickup", "queue", "staff_path", "seating", "entrance"} <= set(cache.zone_ids)
