"""Tier 1F: live object_inventory augmentation from detector caches."""

from __future__ import annotations

import json

from app.evidence_pack import _maybe_augment_inventory_with_live, build, state
from app.fallback import load_cached_recommendation
from app.schemas import ObjectInventory
from app.vision.objects import (
    LAYOUT_CLASS_TO_OBJECT_KIND,
    LayoutObjectDetection,
    detection_to_scene_object_dict,
    select_live_detections_for_inventory,
)


# --- Pure conversion helpers -------------------------------------------


def _det(
    detection_id: str = "x",
    class_name: str = "chair",
    bbox: tuple[float, float, float, float] = (10.0, 20.0, 30.0, 50.0),
    zone: str | None = "seating",
    conf_mean: float = 0.7,
) -> LayoutObjectDetection:
    x1, y1, x2, y2 = bbox
    return LayoutObjectDetection(
        detection_id=detection_id,
        class_id=0,
        class_name=class_name,
        confidence=conf_mean,
        confidence_mean=conf_mean,
        support_count=3,
        source_frame_ids=["video_01"],
        bbox_xyxy=bbox,
        center_xy=((x1 + x2) / 2, (y1 + y2) / 2),
        area_px=(x2 - x1) * (y2 - y1),
        zone_id=zone,
    )


def test_class_mapping_covers_all_supported_yolo_classes():
    """Person is intentionally absent — those land in tracks, not inventory."""
    assert set(LAYOUT_CLASS_TO_OBJECT_KIND) == {
        "chair",
        "dining table",
        "couch",
        "potted plant",
    }
    # Couches map to chair so the agent's seating reasoning treats them right.
    assert LAYOUT_CLASS_TO_OBJECT_KIND["couch"] == "chair"


def test_detection_to_scene_object_returns_none_for_person():
    person = _det(class_name="person")
    assert detection_to_scene_object_dict(person) is None


def test_detection_to_scene_object_dict_has_agent_required_fields():
    chair = _det("chair_007", class_name="chair", bbox=(100.0, 200.0, 140.0, 280.0))
    out = detection_to_scene_object_dict(chair)
    assert out is not None
    assert out["id"] == "vision_chair_007"
    assert out["kind"] == "chair"
    assert out["source"] == "vision"
    assert out["movable"] is True  # chairs/tables/plants are movable
    assert out["bbox_xyxy"] == (100.0, 200.0, 140.0, 280.0)
    assert out["size_xy"] == (40.0, 80.0)


def test_detection_to_scene_object_dict_couches_are_not_movable_walls():
    """`couch` → kind=chair → movable=True (treated as seating)."""
    couch = _det(class_name="couch")
    out = detection_to_scene_object_dict(couch)
    assert out["kind"] == "chair"
    assert out["movable"] is True


def test_select_live_detections_skips_overlap_with_fixture():
    """When a fixture object already covers the bbox region, drop the
    detection — the fixture's narrative metadata wins."""
    chair = _det("chair_001", bbox=(100.0, 100.0, 200.0, 200.0))
    fixture_bboxes = [(100.0, 100.0, 200.0, 200.0)]  # exact overlap
    selected = select_live_detections_for_inventory([chair], fixture_bboxes)
    assert selected == []


def test_select_live_detections_keeps_non_overlapping():
    chair_a = _det("chair_001", bbox=(100.0, 100.0, 200.0, 200.0))
    chair_b = _det("chair_002", bbox=(500.0, 500.0, 600.0, 600.0))
    fixture_bboxes = [(100.0, 100.0, 200.0, 200.0)]  # only chair_a overlaps
    selected = select_live_detections_for_inventory([chair_a, chair_b], fixture_bboxes)
    assert len(selected) == 1
    assert selected[0]["id"] == "vision_chair_002"


def test_select_live_detections_drops_unmapped_classes():
    person = _det("person_001", class_name="person")
    selected = select_live_detections_for_inventory([person], fixture_bboxes=[])
    assert selected == []


# --- Augmentation against real demo_data caches ------------------------


def test_real_cafe_state_augments_with_live_detections(monkeypatch):
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", raising=False)
    s = state("real_cafe")
    inv = s.object_inventory

    fixture_objects = [o for o in inv.objects if o.source != "vision"]
    vision_objects = [o for o in inv.objects if o.source == "vision"]

    assert len(fixture_objects) == 10, "fixture has 10 hand-authored objects"
    assert len(vision_objects) >= 5, "reviewed cache should append several detections"
    # Notes capture the Tier 1F augmentation event (helps trace in the demo).
    assert any("Tier 1F" in note for note in inv.notes)


def test_force_fixture_inventory_env_disables_augmentation(monkeypatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", "1")
    s = state("real_cafe")
    fixture_only = [o for o in s.object_inventory.objects if o.source != "vision"]
    assert len(s.object_inventory.objects) == len(fixture_only)


def test_cached_recommendation_target_id_survives_augmentation(monkeypatch):
    """The whole reason augmentation never replaces the fixture: the
    cached recommendation's `target_id` must keep resolving for the
    fallback path."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", raising=False)
    pack = build("real_cafe")
    cached = load_cached_recommendation("real_cafe")
    inventory_ids = {obj.id for obj in pack.object_inventory.objects}
    assert cached.target_id in inventory_ids


def test_augmentation_no_op_when_cache_missing(tmp_path, monkeypatch):
    """Sessions without a detector cache get the fixture untouched."""
    fake_session = tmp_path / "sessions" / "ghost"
    fake_session.mkdir(parents=True)

    inv = ObjectInventory.model_validate(
        {
            "session_id": "ghost",
            "run_id": "00000000-0000-0000-0000-000000000000",
            "source_frame_idx": 0,
            "source_timestamp_s": 0.0,
            "objects": [
                {
                    "id": "table_main",
                    "kind": "table",
                    "label": "main table",
                    "bbox_xyxy": (0.0, 0.0, 10.0, 10.0),
                    "center_xy": (5.0, 5.0),
                    "size_xy": (10.0, 10.0),
                    "rotation_degrees": 0.0,
                    "zone_id": "seating",
                    "movable": True,
                    "confidence": 0.9,
                    "source": "manual",
                }
            ],
            "counts_by_kind": {
                "table": 1,
                "chair": 0,
                "counter": 0,
                "pickup_shelf": 0,
                "queue_marker": 0,
                "menu_board": 0,
                "plant": 0,
                "barrier": 0,
            },
            "count_confidence": 0.9,
            "notes": [],
        }
    )
    monkeypatch.setattr("app.evidence_pack.session_dir", lambda _: fake_session)

    augmented = _maybe_augment_inventory_with_live("ghost", inv)
    assert augmented.objects == inv.objects, "no cache → inventory passes through"
    assert augmented.notes == inv.notes


def test_augmentation_updates_counts_by_kind(monkeypatch):
    """Counts roll up the per-kind tally so the agent prompt sees the
    full inventory shape, not just the fixture's slice."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", raising=False)
    s = state("real_cafe")
    counts = s.object_inventory.counts_by_kind
    # Fixture has chair=2; reviewed cache adds ~8 chair detections.
    assert counts["chair"] >= 5
    # Plant/table totals should also reflect the new entries.
    assert sum(counts.values()) == len(s.object_inventory.objects)


def test_assets_field_is_unaffected(monkeypatch):
    """Tier 1F only touches inventory; static-file assets stay as-is."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", raising=False)
    s = state("real_cafe")
    # Sanity check that frame.jpg + annotated video URLs are still there.
    assert "frame" in s.assets


def test_real_cafe_reviewed_cache_path_is_preferred_over_raw(monkeypatch):
    """When both caches exist, augmentation reads the reviewed file. The
    reviewed file has fewer detections than raw (false positives dropped),
    so the augment count should match the reviewed file's keep-list."""
    monkeypatch.delenv("CAFETWIN_FORCE_FIXTURE_INVENTORY", raising=False)
    s = state("real_cafe")
    vision_count = sum(1 for o in s.object_inventory.objects if o.source == "vision")

    with open("demo_data/sessions/real_cafe/object_detections.reviewed.cached.json") as f:
        reviewed = json.load(f)
    reviewed_n = len(reviewed["detections"])

    # Some reviewed detections may overlap fixture objects and get filtered.
    assert vision_count <= reviewed_n
    assert vision_count >= 1
