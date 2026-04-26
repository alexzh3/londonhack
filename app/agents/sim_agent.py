"""SimAgent: natural-language scenario prompt -> validated ScenarioCommand.

The frontend's `scenario.chat` input (bottom-right of cafetwin.html) used
to run a brittle regex against the user's prompt to guess seats / baristas
/ footfall. This agent replaces that with a real Pydantic AI run: the
active scenario is passed in as context, the LLM returns a structured
`ScenarioCommand`, and the output validator clamps the numeric fields to
the ranges the iso scene + procedural layout can actually render.

Falls back to a deterministic heuristic (the same one the frontend used
to do client-side) when no API key is configured or the LLM run raises.
"""

from __future__ import annotations

import os
import re

from app import config as _config  # noqa: F401  # load .env before agent construction
from app.schemas import ScenarioCommand, ScenarioParams


INSTRUCTIONS = """
You are a cafe operations simulation agent. The user describes a "what-if"
scenario in plain English (e.g. "cut staff by half on weekday mornings",
"we want to handle a 200/hr rush", "brooklyn vibe, bigger").

Given the active scenario's current parameters, emit exactly one
ScenarioCommand:
- `scenario.name`: a short slug (lowercase, dots/digits) the user will see
  on the scenario rail. Max 22 chars. Derive it from the prompt's intent,
  not a restatement (e.g. "rush.hour", "half.staff", "brooklyn.scale").
- `scenario.seats`, `scenario.baristas`, `scenario.footfall`, `scenario.hours`:
  integer values within the schema's bounds. Keep them realistic for a
  cafe — most prompts move one or two axes, not all four.
- `scenario.style`: one of "default", "brooklyn", "tokyo". Only change
  from the active style when the prompt explicitly references a vibe.
- `rationale`: 1-2 sentences explaining *why* you chose those numbers,
  framed as simulation constraints (not marketing copy).
- `change_summary`: one short line, max 200 chars, suitable for the chat
  message above the tool-call card. Mention the deltas vs active, e.g.
  "+24 seats, +2 baristas, 2x footfall".

Rules:
- If the prompt says "half X" or "double Y", compute from the active
  scenario's current value — not from the baseline.
- Never return the exact active scenario unchanged; at minimum move one
  axis to reflect the prompt's intent.
- Do not invent fields outside ScenarioParams. The schema is strict.
"""


def _default_model_name() -> str:
    if os.getenv("PYDANTIC_AI_GATEWAY_API_KEY") or os.getenv("PAIG_API_KEY"):
        return "gateway/anthropic:claude-sonnet-4-6"
    return "anthropic:claude-sonnet-4-6"


def _agent_model_spec():
    model_name = os.getenv("CAFETWIN_SIM_MODEL") or _default_model_name()
    route = os.getenv("CAFETWIN_GATEWAY_ROUTE") or os.getenv("PYDANTIC_AI_GATEWAY_ROUTE")
    if not route or not model_name.startswith("gateway/"):
        return model_name

    provider_format, upstream_model = model_name.removeprefix("gateway/").split(":", 1)
    if provider_format == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.gateway import gateway_provider

        return AnthropicModel(upstream_model, provider=gateway_provider("anthropic", route=route))
    if provider_format in {"openai", "openai-chat", "chat"}:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.gateway import gateway_provider

        return OpenAIChatModel(upstream_model, provider=gateway_provider("openai", route=route))

    return model_name


try:
    from pydantic_ai import Agent

    sim_agent: Agent[None, ScenarioCommand] | None = Agent(
        _agent_model_spec(),
        output_type=ScenarioCommand,
        instructions=INSTRUCTIONS,
        retries=1,
        output_retries=1,
        defer_model_check=True,
    )
except Exception:
    sim_agent = None


async def run_sim_prompt(
    prompt: str, active: ScenarioParams
) -> tuple[ScenarioCommand, bool]:
    """Return (command, used_fallback).

    Runs the live agent when configured + the environment has an API key;
    otherwise returns the deterministic regex heuristic so the demo still
    produces *something* when offline.
    """
    if sim_agent is None or not _live_agent_enabled():
        return _heuristic_command(prompt, active), True
    try:
        result = await sim_agent.run(_sim_prompt(prompt, active))
        return _slugify_name(result.output), False
    except Exception:
        return _heuristic_command(prompt, active), True


def _sim_prompt(prompt: str, active: ScenarioParams) -> str:
    return (
        "Apply this prompt to the active scenario. Respond with a single "
        "ScenarioCommand whose `scenario` fields are within the schema's "
        "integer ranges (seats 4-240, baristas 1-20, footfall 0-600, "
        "hours 4-24).\n\n"
        f"Active scenario (JSON):\n{active.model_dump_json()}\n\n"
        f"User prompt:\n{prompt!r}"
    )


def _slugify_name(command: ScenarioCommand) -> ScenarioCommand:
    """Force `scenario.name` to the rail-slug shape `[a-z0-9.]+`.

    The rest of the schema validates automatically via Pydantic, but the
    slug regex lives out-of-band (frontend assumes dots / digits only).
    """
    slug = re.sub(r"[^a-z0-9]+", ".", command.scenario.name.lower()).strip(".")
    slug = slug[:22] or "custom"
    if slug == command.scenario.name:
        return command
    return command.model_copy(
        update={"scenario": command.scenario.model_copy(update={"name": slug})}
    )


def _live_agent_enabled() -> bool:
    if os.getenv("CAFETWIN_FORCE_FALLBACK") == "1":
        return False
    return any(
        os.getenv(key)
        for key in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "PYDANTIC_AI_GATEWAY_API_KEY",
            "PAIG_API_KEY",
        )
    )


# ---------- Deterministic fallback heuristic ----------


_SEAT_RE = re.compile(r"(\d+)\s*seat", re.I)
_BAR_RE = re.compile(r"(\d+)\s*barista", re.I)
_FOOTFALL_RE = re.compile(r"(\d+)\s*(?:customer|guest|people|/?\s*hr|per\s*hour)", re.I)


def _heuristic_command(prompt: str, active: ScenarioParams) -> ScenarioCommand:
    """Mirrors the original client-side regex in cafetwin.html's onSendChat.

    Kept deliberately conservative — the goal is "something changes" when
    the LLM is offline, not "the heuristic is as good as an LLM". A user
    typing `brooklyn rush` here gets a sensible scenario chip rather than
    a blank response.
    """
    low = prompt.lower()
    # If the prompt mentions "staff"/"baristas", any "half" / "double"
    # keyword is about staff — we don't want to halve seats when the user
    # said "cut staff by half".
    is_staff_topic = any(w in low for w in ("staff", "barista"))

    baristas = active.baristas
    if m := _BAR_RE.search(low):
        baristas = int(m.group(1))
    elif "more staff" in low or "add staff" in low:
        baristas = min(20, active.baristas + 2)
    elif "cut staff" in low or "less staff" in low or ("half" in low and is_staff_topic):
        baristas = max(1, active.baristas // 2)
    elif (("double" in low or "twice" in low) and is_staff_topic):
        baristas = min(20, active.baristas * 2)

    seats = active.seats
    if m := _SEAT_RE.search(low):
        seats = min(240, int(m.group(1)))
    elif "half" in low and not is_staff_topic:
        seats = max(6, active.seats // 2)
    elif ("double" in low or "twice" in low) and not is_staff_topic:
        seats = min(240, active.seats * 2)

    footfall = active.footfall
    if m := _FOOTFALL_RE.search(low):
        footfall = int(m.group(1))
    elif "rush" in low or "busy" in low:
        footfall = min(600, active.footfall * 2)
    elif "quiet" in low or "slow" in low:
        footfall = max(0, active.footfall // 2)

    style = active.style
    if "brooklyn" in low:
        style = "brooklyn"
    elif "tokyo" in low:
        style = "tokyo"

    slug = re.sub(r"[^a-z0-9]+", ".", low).strip(".")[:22] or "custom"

    deltas = []
    if seats != active.seats:
        deltas.append(f"seats {active.seats}->{seats}")
    if baristas != active.baristas:
        deltas.append(f"baristas {active.baristas}->{baristas}")
    if footfall != active.footfall:
        deltas.append(f"footfall {active.footfall}->{footfall}/hr")
    if style != active.style:
        deltas.append(f"style {active.style}->{style}")
    change_summary = ", ".join(deltas) or "no numeric change inferred"

    return ScenarioCommand(
        scenario=ScenarioParams(
            name=slug,
            seats=seats,
            baristas=baristas,
            footfall=footfall,
            style=style,
            hours=active.hours,
        ),
        rationale=(
            "Heuristic fallback: scanned the prompt for seat/barista/"
            "footfall keywords and scaled from the active scenario. "
            "Live agent disabled (no API key or CAFETWIN_FORCE_FALLBACK=1)."
        ),
        change_summary=change_summary,
    )
