import anyio
from datetime import datetime, timezone
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.agents import optimization_agent as opt
from app.evidence_pack import build
from app.fallback import load_cached_recommendation
from app.layout_candidates import generate_layout_candidates
from app.schemas import OptimizationChoice, PriorRecommendationMemory


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


def test_optimization_agent_retries_semantic_validation_errors(monkeypatch):
    pack = build("ai_cafe_a")
    candidate = generate_layout_candidates(pack)[0]
    invalid = OptimizationChoice(
        selected_candidate_id=candidate.candidate_id,
        title="Open the pickup lane",
        rationale="The selected candidate shifts the obstruction away from the bottleneck.",
        evidence_ids=["not_in_pattern"],
        confidence=0.8,
        risk="low",
    )
    valid = invalid.model_copy(update={"evidence_ids": ["kpi_ai_a_w2"]})
    model, calls = function_model_for_outputs([invalid, valid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with opt.optimization_agent.override(model=model):
        change, used_fallback = anyio.run(opt.run_optimization, pack, "ai_cafe_a")

    assert change.fingerprint == candidate.fingerprint
    assert change.target_id == candidate.target_id
    assert change.simulation.to_position == candidate.to_position
    assert used_fallback is False
    assert len(calls) == 2
    assert "evidence_ids must be a subset" in repr(calls[1])


def test_optimization_agent_uses_fallback_after_second_semantic_failure(monkeypatch):
    pack = build("ai_cafe_a")
    candidate = generate_layout_candidates(pack)[0]
    invalid = OptimizationChoice(
        selected_candidate_id=candidate.candidate_id,
        title="Open the pickup lane",
        rationale="The selected candidate shifts the obstruction away from the bottleneck.",
        evidence_ids=["not_in_pattern"],
        confidence=0.8,
        risk="low",
    )
    model, calls = function_model_for_outputs([invalid, invalid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with opt.optimization_agent.override(model=model):
        change, used_fallback = anyio.run(opt.run_optimization, pack, "ai_cafe_a")

    assert change.fingerprint == "ai_cafe_a_open_pickup_lane_v1"
    assert used_fallback is True
    assert len(calls) == 2


def test_pydantic_ai_gateway_key_enables_live_agent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "test-key")

    assert opt._live_agent_enabled() is True
    assert opt._default_model_name() == "gateway/anthropic:claude-sonnet-4-6"


def test_pydantic_ai_gateway_route_builds_provider_model(monkeypatch):
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_ROUTE", "builtin-anthropic")
    monkeypatch.delenv("CAFETWIN_OPTIMIZATION_MODEL", raising=False)

    model = opt._agent_model_spec()

    assert model.system == "anthropic"
    assert model.model_name == "claude-sonnet-4-6"


def test_optimization_prompt_includes_decision_aware_memory():
    cached = load_cached_recommendation("ai_cafe_a")
    pack = build(
        "ai_cafe_a",
        prior_recommendation_memories=[
            PriorRecommendationMemory(
                session_id="ai_cafe_a",
                pattern_id="pattern_queue_counter_crossing",
                fingerprint=cached.fingerprint,
                title=cached.title,
                target_id=cached.target_id,
                layout_change=cached,
                decision="reject",
                reason="blocked the service lane",
                last_seen_at=datetime.now(timezone.utc),
                source="jsonl",
            )
        ],
    )

    prompt = opt._optimization_prompt(pack)

    assert "decision=reject" in prompt
    assert cached.fingerprint in prompt
    assert "blocked the service lane" in prompt
    assert "Candidate shifts JSON" in prompt
    assert "selected_candidate_id" in opt.INSTRUCTIONS
