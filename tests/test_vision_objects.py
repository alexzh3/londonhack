from pathlib import Path

import pytest

from app.vision.objects import load_object_detections_cache, load_object_review_result


@pytest.mark.parametrize(
    ("session_id", "width", "height", "min_counts"),
    [
        (
            "ai_cafe_a",
            1924,
            1076,
            {"chair": 10, "dining table": 5, "couch": 1, "potted plant": 5},
        ),
        (
            "real_cafe",
            1280,
            720,
            {"chair": 5, "dining table": 1, "couch": 0, "potted plant": 0},
        ),
    ],
)
def test_object_detections_cache_validates(session_id, width, height, min_counts):
    path = Path("demo_data/sessions") / session_id / "object_detections.cached.json"

    cache = load_object_detections_cache(path)

    assert cache.session_id == session_id
    assert cache.source in {
        "ultralytics_yolo_static_objects",
        "moondream_static_objects",
        "hybrid_vlm_static_objects",
    }
    assert cache.schema_version == "cafetwin.objects.v1"
    assert cache.model == "yolov8x.pt"
    assert cache.image.width == width
    assert cache.image.height == height
    assert cache.summary.frame_count == len(cache.frames)
    assert cache.summary.frame_count >= 1
    assert cache.summary.detection_count == len(cache.detections)
    assert cache.summary.raw_detection_count == sum(frame.raw_detection_count for frame in cache.frames)
    assert {"chair", "dining table", "couch", "potted plant"} <= set(cache.target_classes)
    assert {"counter", "pickup", "queue", "staff_path", "seating", "entrance"} <= set(cache.zone_ids)
    for class_name, minimum in min_counts.items():
        assert cache.summary.class_counts[class_name] >= minimum


@pytest.mark.parametrize("session_id", ["ai_cafe_a", "real_cafe"])
def test_object_detections_have_valid_geometry_and_sources(session_id):
    path = Path("demo_data/sessions") / session_id / "object_detections.cached.json"
    cache = load_object_detections_cache(path)
    frame_ids = {frame.frame_id for frame in cache.frames}
    zone_ids = set(cache.zone_ids)

    for detection in cache.detections:
        x1, y1, x2, y2 = detection.bbox_xyxy
        cx, cy = detection.center_xy
        assert 0 <= x1 < x2 <= cache.image.width
        assert 0 <= y1 < y2 <= cache.image.height
        assert x1 <= cx <= x2
        assert y1 <= cy <= y2
        assert detection.area_px > 0
        assert detection.support_count == len(set(detection.source_frame_ids))
        assert set(detection.source_frame_ids) <= frame_ids
        if detection.zone_id is not None:
            assert detection.zone_id in zone_ids


@pytest.mark.parametrize("session_id", ["ai_cafe_a", "real_cafe"])
def test_reviewed_object_detections_are_valid_subset(session_id):
    session_dir = Path("demo_data/sessions") / session_id
    base = load_object_detections_cache(session_dir / "object_detections.cached.json")
    reviewed = load_object_detections_cache(session_dir / "object_detections.reviewed.cached.json")
    review = load_object_review_result(session_dir / "object_review.cached.json")
    keep_ids = {
        decision.detection_id
        for decision in review.decisions
        if decision.action == "keep"
    }

    assert reviewed.session_id == session_id
    assert reviewed.source == "hybrid_vlm_static_objects"
    assert reviewed.summary.detection_count == len(keep_ids)
    assert reviewed.summary.detection_count <= base.summary.detection_count
    assert {detection.detection_id for detection in reviewed.detections} == keep_ids
    assert len(review.decisions) == base.summary.detection_count
