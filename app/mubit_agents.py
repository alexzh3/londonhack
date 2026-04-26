"""MuBit Agent Card registration + prompt versioning (Tier 1E).

Registers `PatternAgent` and `OptimizationAgent` as first-class
`AgentDefinition`s in MuBit's Managed control plane so the Console
shows named agents with versioned system prompts. Memory writes get
tagged with the resolved `agent_id` for per-agent run aggregation.

Falls back gracefully (logs a warning, leaves the registry empty,
agents keep working with in-code prompts) when:

- ``CAFETWIN_MUBIT_AGENTS != "1"`` (default off — opt-in)
- ``MUBIT_API_KEY`` not set
- API key lacks Managed control plane access (401/403/404)
- Network / endpoint unreachable

Endpoints exercised (see https://docs.mubit.ai/api-reference/control-http):

- ``POST /v2/control/projects/list``
- ``POST /v2/control/projects``  (create)
- ``POST /v2/control/projects/agents``  (create AgentDefinition)
- ``POST /v2/control/projects/agents/get``
- ``POST /v2/control/prompt/get``
- ``POST /v2/control/prompt/set``  (activate=true → mints new active
  version, retires the previous)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass

import httpx

from app.logfire_setup import span

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_NAME = "cafetwin"
DEFAULT_PROJECT_DESCRIPTION = (
    "CafeTwin hackathon — operations console with two Pydantic AI agents."
)


@dataclass(frozen=True)
class AgentCardSpec:
    """Spec for a single agent we want registered in MuBit Managed."""

    local_name: str  # how Python code looks the agent up (e.g. "pattern_agent")
    agent_id: str  # the MuBit agent_id slug shown in the Console
    role: str  # human-readable role (e.g. "operational pattern detector")
    description: str  # one-line description for the Console
    system_prompt: str  # active prompt content (kept in sync with the in-code constant)


# Runtime registry: local_name -> {project_id, agent_id, prompt_hash, version_id}.
# Populated by `bootstrap_mubit_agents()`; consumed by `get_agent_id()` and the
# memory write path.
_REGISTRY: dict[str, dict[str, str]] = {}


def is_enabled() -> bool:
    """Tier 1E only engages when explicitly opted in AND MuBit reachable."""
    if os.getenv("CAFETWIN_MUBIT_AGENTS") != "1":
        return False
    return bool(os.getenv("MUBIT_API_KEY"))


def get_agent_id(local_name: str, fallback: str) -> str:
    """Return the registered MuBit agent_id for memory-write tagging.

    Falls back to ``fallback`` (typically the legacy single-agent slug)
    when bootstrap hasn't run, didn't succeed, or the local name wasn't
    in the spec list passed to bootstrap.
    """
    cached = _REGISTRY.get(local_name, {}).get("agent_id")
    return cached or fallback


def get_project_id() -> str | None:
    """Return the MuBit project_id once bootstrap has run, else None."""
    for entry in _REGISTRY.values():
        pid = entry.get("project_id")
        if pid:
            return pid
    return None


def is_registered(local_name: str) -> bool:
    """Has a particular agent been successfully registered?"""
    return local_name in _REGISTRY


async def bootstrap_mubit_agents(specs: list[AgentCardSpec]) -> None:
    """Idempotent registration of all agent cards.

    Runs at app startup via ``app/api/main.py``. Safe to call multiple
    times — the project is dedup'd by name and agents are dedup'd by
    agent_id within their project. Prompt content is diff'd against the
    active version; only mints a new version when the content actually
    changed.
    """
    if not is_enabled():
        return

    with span("mubit.bootstrap"):
        try:
            project_id = await _ensure_project()
        except Exception as exc:
            logger.warning("MuBit project bootstrap failed: %s", exc)
            return

        for spec in specs:
            try:
                await _ensure_agent(project_id, spec)
            except Exception as exc:
                logger.warning(
                    "MuBit agent bootstrap for %s failed: %s", spec.agent_id, exc
                )


async def _ensure_project() -> str:
    """Find or create the cafetwin project. Returns ``project_id``.

    Honours ``MUBIT_PROJECT_ID`` env override (skips the list/create
    round-trip when the operator has already provisioned a project and
    just wants the agent registration step to attach to it).
    """
    explicit_id = os.getenv("MUBIT_PROJECT_ID")
    if explicit_id:
        return explicit_id

    name = os.getenv("CAFETWIN_MUBIT_PROJECT_NAME") or DEFAULT_PROJECT_NAME

    response = await _post("/v2/control/projects/list", {})
    for project in response.get("projects") or []:
        if isinstance(project, dict) and project.get("name") == name:
            pid = project.get("project_id")
            if isinstance(pid, str) and pid:
                logger.info("MuBit: reusing project %s (%s)", name, pid)
                return pid

    response = await _post(
        "/v2/control/projects",
        {"name": name, "description": DEFAULT_PROJECT_DESCRIPTION},
    )
    project = response.get("project") or {}
    pid = project.get("project_id")
    if not isinstance(pid, str) or not pid:
        raise RuntimeError(
            f"MuBit project create returned no project_id: {response!r}"
        )
    logger.info("MuBit: created project %s (%s)", name, pid)
    return pid


async def _ensure_agent(project_id: str, spec: AgentCardSpec) -> None:
    """Create the agent if missing; update the active prompt if its content
    drifted from the spec's ``system_prompt``."""
    existing = await _get_agent_definition(project_id, spec.agent_id)

    if existing is None:
        # First-time create: this also mints v1 of the prompt.
        await _post(
            "/v2/control/projects/agents",
            {
                "project_id": project_id,
                "agent_id": spec.agent_id,
                "role": spec.role,
                "description": spec.description,
                "system_prompt_content": spec.system_prompt,
            },
        )
        logger.info("MuBit: created agent %s in %s", spec.agent_id, project_id)
        active_content = spec.system_prompt
        version_id = ""
    else:
        # Agent exists. Pull the active prompt version and diff.
        prompt_response = await _post(
            "/v2/control/prompt/get",
            {"project_id": project_id, "agent_id": spec.agent_id},
        )
        version = prompt_response.get("version") or {}
        active_content = version.get("content") or ""
        version_id = version.get("version_id") or ""

        if active_content.strip() != spec.system_prompt.strip():
            # Prompt drifted — mint a new version and activate it. The
            # control plane retires the previous active version.
            new_version_response = await _post(
                "/v2/control/prompt/set",
                {
                    "project_id": project_id,
                    "agent_id": spec.agent_id,
                    "content": spec.system_prompt,
                    "activate": True,
                },
            )
            new_version = new_version_response.get("version") or {}
            active_content = spec.system_prompt
            version_id = new_version.get("version_id") or version_id
            logger.info(
                "MuBit: updated %s prompt (v%s -> v%s)",
                spec.agent_id,
                version.get("version_number"),
                new_version.get("version_number"),
            )

    _REGISTRY[spec.local_name] = {
        "project_id": project_id,
        "agent_id": spec.agent_id,
        "prompt_hash": _hash(active_content),
        "version_id": version_id,
    }


async def _get_agent_definition(project_id: str, agent_id: str) -> dict | None:
    """Return the agent definition dict, or None if it doesn't exist."""
    try:
        response = await _post(
            "/v2/control/projects/agents/get",
            {"project_id": project_id, "agent_id": agent_id},
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    agent = response.get("agent")
    return agent if isinstance(agent, dict) else None


async def _post(path: str, body: dict) -> dict:
    """HTTP POST against the MuBit control plane.

    Mirrors ``app/memory.py``'s style for endpoint resolution + headers
    so all MuBit env knobs apply consistently. Raises on non-2xx so
    callers can branch on 404 / auth failures.
    """
    endpoint = (
        os.getenv("MUBIT_HTTP_ENDPOINT")
        or os.getenv("MUBIT_ENDPOINT")
        or "https://api.mubit.ai"
    )
    url = f"{endpoint.rstrip('/')}{path}"
    timeout = float(os.getenv("MUBIT_TIMEOUT_S", "8"))
    headers = {"Authorization": f"Bearer {os.getenv('MUBIT_API_KEY', '')}"}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        if not response.content:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError:
            return {}


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def reset_registry_for_tests() -> None:
    """Clear the runtime registry — only used in tests."""
    _REGISTRY.clear()


# ---------- Default agent spec catalogue ----------
#
# These are the two agents that ship in MVP/Tier 1. SceneBuilderAgent
# (Tier 2) will add a third entry here when it lands.

PATTERN_AGENT_LOCAL = "pattern_agent"
OPTIMIZATION_AGENT_LOCAL = "optimization_agent"

# Default MuBit agent_id slugs (kebab-case, stable across deploys).
PATTERN_AGENT_ID = "cafetwin-pattern-agent"
OPTIMIZATION_AGENT_ID = "cafetwin-optimization-agent"


def default_specs() -> list[AgentCardSpec]:
    """Build the default spec list from the in-code agent prompts.

    Imported lazily inside the function so this module doesn't pull in
    Pydantic AI / agent dependencies at module import time (relevant
    when the bootstrap is called from the FastAPI app factory).
    """
    from app.agents.optimization_agent import INSTRUCTIONS as OPT_PROMPT
    from app.agents.pattern_agent import INSTRUCTIONS as PATTERN_PROMPT

    return [
        AgentCardSpec(
            local_name=PATTERN_AGENT_LOCAL,
            agent_id=PATTERN_AGENT_ID,
            role="operational pattern detector",
            description=(
                "Tier 1 PatternAgent — detects the dominant operational "
                "friction (queue crossing, staff detour, table blockage, "
                "pickup congestion) from KPI windows + scene inventory + zones."
            ),
            system_prompt=PATTERN_PROMPT,
        ),
        AgentCardSpec(
            local_name=OPTIMIZATION_AGENT_LOCAL,
            agent_id=OPTIMIZATION_AGENT_ID,
            role="cafe layout optimization agent",
            description=(
                "MVP OptimizationAgent — proposes a single LayoutChange to "
                "reduce the worst pattern KPI without losing seating, using "
                "decision-aware prior recommendation memory."
            ),
            system_prompt=OPT_PROMPT,
        ),
    ]
