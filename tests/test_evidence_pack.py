from app.evidence_pack import build, state
from app.fallback import load_cached_recommendation, validate_layout_change
from app.sessions import list_session_manifests


def test_ai_cafe_session_manifest_is_discovered():
    manifests = list_session_manifests()

    slugs = {manifest.slug for manifest in manifests}
    assert "ai_cafe_a" in slugs


def test_state_loads_ai_cafe_fixtures():
    response = state("ai_cafe_a")

    assert response.missing_required == []
    assert response.object_inventory is not None
    assert response.pattern is not None
    assert response.assets["video"] == "cafe_videos/ai_generated_cctv.mp4"
    assert response.assets["frame"] == "demo_data/sessions/ai_cafe_a/frame.jpg"


def test_build_pack_and_cached_recommendation_are_consistent():
    pack = build("ai_cafe_a")
    recommendation = load_cached_recommendation("ai_cafe_a")

    assert pack.pattern.id == "pattern_queue_counter_crossing"
    assert pack.object_inventory.objects
    assert validate_layout_change(recommendation, pack) == []
