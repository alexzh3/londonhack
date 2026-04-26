"""Tests for SimAgent + the /api/sim/prompt endpoint.

The live Pydantic AI agent requires a real API key and is exercised only
in smoke tests. These tests cover:

- The deterministic fallback heuristic so the chat always works offline.
- The FastAPI endpoint contract (request/response shapes, slug dedupe).
- Forcing the fallback path via CAFETWIN_FORCE_FALLBACK so CI doesn't
  need a real LLM.
"""

from __future__ import annotations

import os

import anyio
import pytest

from app.agents.sim_agent import (
    _heuristic_command,
    _live_agent_enabled,
    _slugify_name,
    run_sim_prompt,
)
from app.api import routes
from app.schemas import ScenarioCommand, ScenarioParams, SimPromptRequest


BASELINE = ScenarioParams(
    name="baseline",
    seats=12,
    baristas=1,
    footfall=32,
    style="default",
    hours=10,
)


# ---------- Heuristic fallback ----------


def test_heuristic_parses_seat_count():
    cmd = _heuristic_command("add 40 seats please", BASELINE)
    assert cmd.scenario.seats == 40
    assert cmd.scenario.baristas == BASELINE.baristas
    assert "seats" in cmd.change_summary


def test_heuristic_parses_barista_count():
    cmd = _heuristic_command("staff up to 5 baristas", BASELINE)
    assert cmd.scenario.baristas == 5


def test_heuristic_parses_half():
    active = ScenarioParams(name="busy", seats=40, baristas=4, footfall=120, style="default", hours=12)
    cmd = _heuristic_command("cut staff by half", active)
    # "half" without "seats" keyword doesn't touch seats
    assert cmd.scenario.seats == active.seats
    # "cut staff" path halves baristas
    assert cmd.scenario.baristas == 2


def test_heuristic_parses_style_keywords():
    for word, expected in [("brooklyn rush", "brooklyn"), ("tokyo vibe", "tokyo")]:
        cmd = _heuristic_command(word, BASELINE)
        assert cmd.scenario.style == expected


def test_heuristic_rush_doubles_footfall():
    cmd = _heuristic_command("morning rush please", BASELINE)
    assert cmd.scenario.footfall == BASELINE.footfall * 2
    assert cmd.change_summary  # non-empty


def test_heuristic_slugifies_name():
    cmd = _heuristic_command("Cut staff by HALF, Brooklyn rush!", BASELINE)
    # Lowercase, no special chars, dots as separators
    assert all(ch.islower() or ch.isdigit() or ch == "." for ch in cmd.scenario.name)
    assert len(cmd.scenario.name) <= 22


def test_heuristic_clamps_to_schema_bounds():
    # Large numbers in the prompt must not push the schema over its cap.
    cmd = _heuristic_command("set seats to 9999", BASELINE)
    # Schema validation bounds (seats <= 240); the heuristic returns raw
    # parsed value, so ensure pydantic construction still succeeds by
    # clamping it ourselves before validation. The test below verifies
    # the final ScenarioCommand is valid.
    assert cmd.scenario.seats <= 240


def test_heuristic_never_returns_fields_outside_schema():
    cmd = _heuristic_command("go brooklyn", BASELINE)
    # Should round-trip through the strict ScenarioCommand model
    dumped = cmd.model_dump()
    assert set(dumped["scenario"].keys()) == {
        "name", "seats", "baristas", "footfall", "style", "hours"
    }


# ---------- Live-vs-fallback gating ----------


def test_run_sim_prompt_uses_fallback_when_flag_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    cmd, used_fallback = anyio.run(run_sim_prompt, "double the staff", BASELINE)
    assert used_fallback is True
    assert cmd.scenario.baristas == BASELINE.baristas * 2


def test_live_agent_gate_reads_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    assert _live_agent_enabled() is False
    monkeypatch.delenv("CAFETWIN_FORCE_FALLBACK", raising=False)
    # At least one API key should be present in dev; test is informative only
    # (skip when none are set — typical CI).
    has_any = any(
        os.getenv(k)
        for k in (
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
            "PYDANTIC_AI_GATEWAY_API_KEY", "PAIG_API_KEY",
        )
    )
    assert _live_agent_enabled() == has_any


# ---------- Slug normalisation ----------


def test_slugify_name_replaces_special_chars():
    cmd = ScenarioCommand(
        scenario=ScenarioParams(
            name="Brooklyn Rush!", seats=12, baristas=1, footfall=32,
            style="default", hours=10,
        ),
        rationale="test",
        change_summary="x",
    )
    out = _slugify_name(cmd)
    assert out.scenario.name == "brooklyn.rush"


def test_slugify_name_idempotent_when_already_clean():
    cmd = ScenarioCommand(
        scenario=ScenarioParams(
            name="rush.hour", seats=12, baristas=1, footfall=32,
            style="default", hours=10,
        ),
        rationale="test",
        change_summary="x",
    )
    out = _slugify_name(cmd)
    assert out is cmd  # no-op path returns same object


# ---------- /api/sim/prompt endpoint ----------


def test_sim_prompt_endpoint_returns_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    body = SimPromptRequest(
        session_id="ai_cafe_a",
        prompt="double the baristas",
        active_scenario=BASELINE,
    )
    response = anyio.run(routes.sim_prompt, body)

    assert response.used_fallback is True
    assert response.command.scenario.baristas == BASELINE.baristas * 2
    # Rationale + change_summary populated
    assert response.command.rationale
    assert response.command.change_summary


def test_sim_prompt_endpoint_preserves_session_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    body = SimPromptRequest(
        session_id="real_cafe",
        prompt="brooklyn vibe, 60 seats",
        active_scenario=BASELINE,
    )
    response = anyio.run(routes.sim_prompt, body)
    # Style keyword extracted
    assert response.command.scenario.style == "brooklyn"
    # Seat count extracted
    assert response.command.scenario.seats == 60
