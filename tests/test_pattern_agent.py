import anyio
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.agents import pattern_agent as pat
from app.evidence_pack import build_pattern_evidence_bundle, state
from app.fallback import load_cached_pattern, validate_operational_pattern


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


def _bundle(session_id="ai_cafe_a"):
    return build_pattern_evidence_bundle(state(session_id))


def test_pattern_agent_falls_back_when_live_disabled(monkeypatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    bundle = _bundle()

    pattern, used_fallback = anyio.run(pat.run_pattern_detection, bundle, "ai_cafe_a")

    assert used_fallback is True
    assert pattern == load_cached_pattern("ai_cafe_a")


def test_pattern_agent_returns_live_output_when_valid(monkeypatch):
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")
    valid = cached.model_copy(
        update={"id": "agent_picked_id", "title": "Live agent saw congestion"}
    )
    model, calls = function_model_for_outputs([valid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with pat.pattern_agent.override(model=model):
        pattern, used_fallback = anyio.run(pat.run_pattern_detection, bundle, "ai_cafe_a")

    # ID is normalized to the canonical fixture ID so memory recall stays
    # scoped consistently; the live agent's title/severity/evidence flow through.
    assert pattern.id == cached.id
    assert pattern.title == "Live agent saw congestion"
    assert used_fallback is False
    assert len(calls) == 1


def test_pattern_agent_prompt_includes_canonical_pattern_id():
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")

    prompt = pat._pattern_prompt(bundle, canonical_pattern_id=cached.id)

    assert cached.id in prompt
    assert "stable pattern.id" in prompt


def test_pattern_agent_retries_semantic_validation_errors(monkeypatch):
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")
    invalid = cached.model_copy(
        update={"affected_zones": ["not_a_zone"]}
    )
    valid = cached.model_copy(update={"id": "agent_picked_retry", "severity": "medium"})
    model, calls = function_model_for_outputs([invalid, valid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with pat.pattern_agent.override(model=model):
        pattern, used_fallback = anyio.run(pat.run_pattern_detection, bundle, "ai_cafe_a")

    assert pattern.id == cached.id  # normalized
    assert pattern.severity == "medium"  # live content preserved
    assert used_fallback is False
    assert len(calls) == 2
    assert "affected_zones must be a subset" in repr(calls[1])


def test_pattern_agent_uses_fallback_after_repeated_semantic_failures(monkeypatch):
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")
    invalid = cached.model_copy(update={"affected_zones": ["not_a_zone"]})
    model, calls = function_model_for_outputs([invalid, invalid])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    with pat.pattern_agent.override(model=model):
        pattern, used_fallback = anyio.run(pat.run_pattern_detection, bundle, "ai_cafe_a")

    assert pattern == cached
    assert used_fallback is True
    assert len(calls) == 2


def test_validate_operational_pattern_flags_unknown_evidence_id():
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")
    bad_evidence = cached.evidence[0].model_copy(update={"memory_id": "kpi_does_not_exist"})
    bad = cached.model_copy(update={"evidence": [bad_evidence]})

    errors = validate_operational_pattern(bad, bundle)

    assert any("evidence[*].memory_id" in error for error in errors)


def test_validate_operational_pattern_flags_unknown_zone_id():
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")
    bad = cached.model_copy(update={"affected_zones": ["counter", "not_a_zone"]})

    errors = validate_operational_pattern(bad, bundle)

    assert any("affected_zones must be a subset" in error for error in errors)


def test_validate_operational_pattern_passes_for_fixture():
    bundle = _bundle()
    cached = load_cached_pattern("ai_cafe_a")

    errors = validate_operational_pattern(cached, bundle)

    assert errors == []


def test_pattern_agent_pydantic_ai_gateway_key_enables_live_agent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "test-key")

    assert pat._live_agent_enabled() is True
    assert pat._default_model_name() == "gateway/anthropic:claude-sonnet-4-6"


def test_pattern_agent_real_cafe_session_fallback(monkeypatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    bundle = _bundle("real_cafe")

    pattern, used_fallback = anyio.run(pat.run_pattern_detection, bundle, "real_cafe")

    assert used_fallback is True
    assert pattern == load_cached_pattern("real_cafe")
