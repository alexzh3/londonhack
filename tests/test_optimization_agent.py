from types import SimpleNamespace

import anyio

from app.agents import optimization_agent as opt
from app.evidence_pack import build
from app.fallback import load_cached_recommendation


class FakeOptimizationAgent:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    async def run(self, prompt, *, deps):
        self.prompts.append(prompt)
        return SimpleNamespace(output=self.outputs.pop(0))


def test_optimization_agent_retries_semantic_validation_errors(monkeypatch):
    pack = build("ai_cafe_a")
    cached = load_cached_recommendation("ai_cafe_a")
    invalid = cached.model_copy(update={"evidence_ids": ["not_in_pattern"]})
    valid = cached.model_copy(update={"fingerprint": "live_retry_ok"})
    fake_agent = FakeOptimizationAgent([invalid, valid])
    monkeypatch.setattr(opt, "optimization_agent", fake_agent)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    change, used_fallback = anyio.run(opt.run_optimization, pack, "ai_cafe_a")

    assert change.fingerprint == "live_retry_ok"
    assert used_fallback is False
    assert len(fake_agent.prompts) == 2
    assert "failed semantic validation" in fake_agent.prompts[1]
    assert "evidence_ids must be a subset" in fake_agent.prompts[1]


def test_optimization_agent_uses_fallback_after_second_semantic_failure(monkeypatch):
    pack = build("ai_cafe_a")
    cached = load_cached_recommendation("ai_cafe_a")
    invalid = cached.model_copy(update={"evidence_ids": ["not_in_pattern"]})
    fake_agent = FakeOptimizationAgent([invalid, invalid])
    monkeypatch.setattr(opt, "optimization_agent", fake_agent)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)

    change, used_fallback = anyio.run(opt.run_optimization, pack, "ai_cafe_a")

    assert change.fingerprint == "ai_cafe_a_open_pickup_lane_v1"
    assert used_fallback is True
    assert len(fake_agent.prompts) == 2


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
