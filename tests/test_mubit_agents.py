"""Tier 1E: MuBit agent card registration + per-agent memory tagging."""

from __future__ import annotations

from typing import Any

import anyio
import pytest

import app.mubit_agents as ma
from app.mubit_agents import (
    AgentCardSpec,
    bootstrap_mubit_agents,
    default_specs,
    get_agent_id,
    is_enabled,
    reset_registry_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


def _spec(agent_id: str = "test-agent", prompt: str = "p1") -> AgentCardSpec:
    return AgentCardSpec(
        local_name=agent_id,
        agent_id=agent_id,
        role="role",
        description="desc",
        system_prompt=prompt,
    )


# --- Gating ---------------------------------------------------------------


def test_is_enabled_requires_env_flag(monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "abc")
    monkeypatch.delenv("CAFETWIN_MUBIT_AGENTS", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    assert is_enabled() is True
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    monkeypatch.delenv("MUBIT_API_KEY", raising=False)
    assert is_enabled() is False


def test_bootstrap_no_op_when_disabled(monkeypatch):
    monkeypatch.delenv("CAFETWIN_MUBIT_AGENTS", raising=False)
    monkeypatch.setenv("MUBIT_API_KEY", "abc")

    calls: list[tuple[str, dict]] = []

    async def fake_post(path: str, body: dict) -> dict:
        calls.append((path, body))
        return {}

    monkeypatch.setattr(ma, "_post", fake_post)
    anyio.run(bootstrap_mubit_agents, [_spec()])

    assert calls == [], "bootstrap must not contact MuBit when feature flag is off"
    assert get_agent_id("test-agent", "fallback") == "fallback"


# --- Idempotent registration ---------------------------------------------


def test_bootstrap_creates_project_and_agent_first_run(monkeypatch):
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    monkeypatch.setenv("MUBIT_API_KEY", "abc")
    monkeypatch.delenv("MUBIT_PROJECT_ID", raising=False)

    calls: list[tuple[str, dict]] = []

    import httpx

    async def fake_post(path: str, body: dict) -> dict:
        calls.append((path, body))
        if path == "/v2/control/projects/list":
            return {"projects": []}
        if path == "/v2/control/projects":
            return {"project": {"project_id": "proj-XYZ", "name": body["name"]}}
        if path == "/v2/control/projects/agents/get":
            # Simulate "agent doesn't exist yet" — 404 mapped to None
            request = httpx.Request("POST", "https://api.mubit.ai" + path)
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        if path == "/v2/control/projects/agents":
            return {"agent": {"project_id": body["project_id"], "agent_id": body["agent_id"]}}
        return {}

    monkeypatch.setattr(ma, "_post", fake_post)
    anyio.run(bootstrap_mubit_agents, [_spec("agent-a", "first version")])

    paths = [path for path, _ in calls]
    assert paths == [
        "/v2/control/projects/list",
        "/v2/control/projects",
        "/v2/control/projects/agents/get",
        "/v2/control/projects/agents",
    ]
    assert get_agent_id("agent-a", "fallback") == "agent-a"


def test_bootstrap_reuses_existing_project_and_agent(monkeypatch):
    """Second deploy: project + agent + active prompt all already exist
    with matching content. Bootstrap should NOT mint a new prompt version."""
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    monkeypatch.setenv("MUBIT_API_KEY", "abc")
    monkeypatch.delenv("MUBIT_PROJECT_ID", raising=False)

    paths: list[str] = []
    prompt = "stable prompt"

    async def fake_post(path: str, body: dict) -> dict:
        paths.append(path)
        if path == "/v2/control/projects/list":
            return {"projects": [{"project_id": "proj-EXIST", "name": "cafetwin"}]}
        if path == "/v2/control/projects/agents/get":
            return {"agent": {"agent_id": body["agent_id"]}}
        if path == "/v2/control/prompt/get":
            return {"version": {"content": prompt, "version_id": "pv-1"}}
        if path == "/v2/control/prompt/set":
            raise AssertionError("must not mint a new version when prompt unchanged")
        return {}

    monkeypatch.setattr(ma, "_post", fake_post)
    anyio.run(bootstrap_mubit_agents, [_spec("agent-a", prompt)])

    assert "/v2/control/projects" not in paths, "must not re-create the project"
    assert "/v2/control/projects/agents" not in paths, "must not re-create the agent"
    assert "/v2/control/prompt/set" not in paths
    assert get_agent_id("agent-a", "fallback") == "agent-a"


def test_bootstrap_mints_new_prompt_version_when_content_drifts(monkeypatch):
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    monkeypatch.setenv("MUBIT_API_KEY", "abc")
    monkeypatch.delenv("MUBIT_PROJECT_ID", raising=False)

    set_calls: list[dict[str, Any]] = []

    async def fake_post(path: str, body: dict) -> dict:
        if path == "/v2/control/projects/list":
            return {"projects": [{"project_id": "p", "name": "cafetwin"}]}
        if path == "/v2/control/projects/agents/get":
            return {"agent": {"agent_id": "agent-a"}}
        if path == "/v2/control/prompt/get":
            return {"version": {"content": "old prompt", "version_id": "pv-1"}}
        if path == "/v2/control/prompt/set":
            set_calls.append(body)
            return {"version": {"content": body["content"], "version_id": "pv-2"}}
        return {}

    monkeypatch.setattr(ma, "_post", fake_post)
    anyio.run(bootstrap_mubit_agents, [_spec("agent-a", "new prompt")])

    assert len(set_calls) == 1
    assert set_calls[0]["content"] == "new prompt"
    assert set_calls[0]["activate"] is True


def test_bootstrap_swallows_per_agent_errors(monkeypatch):
    monkeypatch.setenv("CAFETWIN_MUBIT_AGENTS", "1")
    monkeypatch.setenv("MUBIT_API_KEY", "abc")

    async def fake_post(path: str, body: dict) -> dict:
        if path == "/v2/control/projects/list":
            return {"projects": [{"project_id": "p", "name": "cafetwin"}]}
        if path == "/v2/control/projects/agents/get":
            raise RuntimeError("simulated outage")
        return {}

    monkeypatch.setattr(ma, "_post", fake_post)
    # Bootstrap must not raise — caller relies on it being safe in startup hooks.
    anyio.run(bootstrap_mubit_agents, [_spec("agent-a")])
    assert get_agent_id("agent-a", "fallback") == "fallback"


# --- default_specs sanity --------------------------------------------------


def test_default_specs_returns_pattern_optimization_and_sim_agents():
    specs = default_specs()
    assert {spec.local_name for spec in specs} == {
        "pattern_agent",
        "optimization_agent",
        "sim_agent",
    }
    for spec in specs:
        assert spec.system_prompt.strip(), f"{spec.agent_id} must have a non-empty prompt"
        assert spec.role
        assert spec.description


# --- memory.py per-agent dispatch ----------------------------------------


def test_memory_resolve_agent_id_uses_lane(monkeypatch):
    """Once Tier 1E populates the registry, lane → agent_id dispatches:
    recommendations + feedback to optimization_agent, patterns to pattern_agent."""
    from datetime import datetime, timezone

    from app.memory import _resolve_agent_id
    from app.schemas import MemoryRecord

    # Seed the registry as if bootstrap had succeeded.
    ma._REGISTRY["pattern_agent"] = {"agent_id": "pa-id"}
    ma._REGISTRY["optimization_agent"] = {"agent_id": "oa-id"}

    rec = MemoryRecord(
        lane="location:demo:recommendations",
        intent="lesson",
        payload={},
        written_at=datetime.now(timezone.utc),
    )
    assert _resolve_agent_id(rec) == "oa-id"

    fb = rec.model_copy(update={"lane": "location:demo:feedback"})
    assert _resolve_agent_id(fb) == "oa-id"

    pat = rec.model_copy(update={"lane": "location:demo:patterns"})
    assert _resolve_agent_id(pat) == "pa-id"


def test_memory_resolve_agent_id_falls_back_when_registry_empty():
    from datetime import datetime, timezone

    from app.memory import _resolve_agent_id, MUBIT_AGENT_ID
    from app.schemas import MemoryRecord

    rec = MemoryRecord(
        lane="location:demo:recommendations",
        intent="lesson",
        payload={},
        written_at=datetime.now(timezone.utc),
    )
    assert _resolve_agent_id(rec) == MUBIT_AGENT_ID
