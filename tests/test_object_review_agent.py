from pathlib import Path

import anyio
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.agents import object_review_agent as ora
from app.vision.objects import (
    ObjectReviewBundle,
    ObjectReviewDecision,
    ObjectReviewResult,
    load_object_detections_cache,
    reviewed_object_cache,
)


def function_model_for_outputs(outputs):
    calls = []
    queued = list(outputs)

    def model(_messages, info):
        calls.append(_messages)
        output = queued.pop(0)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args=output.model_dump(mode="json"),
                )
            ]
        )

    return FunctionModel(model), calls


def _bundle():
    cache = load_object_detections_cache(
        Path("demo_data/sessions/ai_cafe_a/object_detections.cached.json")
    )
    return ObjectReviewBundle(session_id="ai_cafe_a", detector_cache=cache)


def test_object_review_falls_back_when_live_disabled(monkeypatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    bundle = _bundle()

    review, used_fallback = anyio.run(ora.run_object_review, bundle)

    assert used_fallback is True
    assert review.session_id == "ai_cafe_a"
    assert len(review.decisions) == len(bundle.detector_cache.detections)
    assert all(decision.action in {"keep", "drop"} for decision in review.decisions)


def test_validate_object_review_flags_missing_and_unknown_ids():
    bundle = _bundle()
    known = bundle.detector_cache.detections[0].detection_id
    bad = ObjectReviewResult(
        session_id="ai_cafe_a",
        decisions=[
            ObjectReviewDecision(detection_id=known, action="keep", reason="ok"),
            ObjectReviewDecision(detection_id="not_real", action="drop", reason="bad"),
        ],
    )

    errors = ora.validate_object_review(bad, bundle)

    assert any("unknown detection_id" in error for error in errors)
    assert any("missing decisions" in error for error in errors)


def test_object_review_agent_returns_live_review_when_valid(monkeypatch):
    bundle = _bundle()
    decisions = [
        ObjectReviewDecision(
            detection_id=detection.detection_id,
            action="keep",
            reason="test model keeps all candidates",
        )
        for detection in bundle.detector_cache.detections
    ]
    valid = ObjectReviewResult(session_id="ai_cafe_a", decisions=decisions)
    model, calls = function_model_for_outputs([valid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with ora.object_review_agent.override(model=model):
        review, used_fallback = anyio.run(ora.run_object_review, bundle)

    assert used_fallback is False
    assert review == valid
    assert len(calls) == 1


def test_reviewed_object_cache_filters_dropped_detections():
    bundle = _bundle()
    keep_id = bundle.detector_cache.detections[0].detection_id
    decisions = [
        ObjectReviewDecision(
            detection_id=detection.detection_id,
            action="keep" if detection.detection_id == keep_id else "drop",
            reason="test filter",
        )
        for detection in bundle.detector_cache.detections
    ]
    review = ObjectReviewResult(session_id="ai_cafe_a", decisions=decisions)

    reviewed = reviewed_object_cache(
        bundle.detector_cache,
        review,
        model="test-review",
        generated_at=bundle.detector_cache.generated_at,
    )

    assert reviewed.source == "hybrid_vlm_static_objects"
    assert reviewed.model == "test-review"
    assert [detection.detection_id for detection in reviewed.detections] == [keep_id]
    assert reviewed.summary.detection_count == 1
