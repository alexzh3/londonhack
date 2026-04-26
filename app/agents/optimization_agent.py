"""OptimizationAgent: CafeEvidencePack -> validated LayoutChange."""

from __future__ import annotations

import os

from app import config as _config  # noqa: F401  # load .env before agent construction
from app.fallback import load_cached_recommendation, validate_layout_change
from app.schemas import CafeEvidencePack, LayoutChange


INSTRUCTIONS = """
You are a cafe layout optimization agent.

Return exactly one LayoutChange. Constraints:
- The target_id must exist in object_inventory.objects.
- evidence_ids must be a non-empty subset of pattern.evidence[*].memory_id.
- Prefer a single move that reduces the pattern's worst KPI without reducing seating.
- Be concrete: title, rationale, expected_kpi_delta, confidence, and risk must be demo-ready.
"""


def _default_model_name() -> str:
    if os.getenv("PYDANTIC_AI_GATEWAY_API_KEY") or os.getenv("PAIG_API_KEY"):
        return "gateway/anthropic:claude-sonnet-4-6"
    return "anthropic:claude-sonnet-4-6"


def _agent_model_spec():
    model_name = os.getenv("CAFETWIN_OPTIMIZATION_MODEL") or _default_model_name()
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

    optimization_agent: Agent[CafeEvidencePack, LayoutChange] | None = Agent(
        _agent_model_spec(),
        deps_type=CafeEvidencePack,
        output_type=LayoutChange,
        instructions=INSTRUCTIONS,
        retries=1,
    )
except Exception:
    optimization_agent = None


async def run_optimization(pack: CafeEvidencePack, session_id: str) -> tuple[LayoutChange, bool]:
    """Run the live agent when configured; otherwise return the cached safe recommendation."""
    fallback = load_cached_recommendation(session_id)
    if optimization_agent is None or not _live_agent_enabled():
        return fallback, True

    try:
        result = await optimization_agent.run(_optimization_prompt(pack), deps=pack)
        change = result.output
        errors = validate_layout_change(change, pack)
        if not errors:
            return change, False

        result = await optimization_agent.run(_retry_prompt(pack, change, errors), deps=pack)
        retry_change = result.output
        if not validate_layout_change(retry_change, pack):
            return retry_change, False
    except Exception:
        return fallback, True

    return fallback, True


def _optimization_prompt(pack: CafeEvidencePack) -> str:
    return (
        "Optimize this cafe layout from the evidence pack. "
        "Use only cited evidence IDs.\n\n"
        f"{pack.model_dump_json()}"
    )


def _retry_prompt(pack: CafeEvidencePack, change: LayoutChange, errors: list[str]) -> str:
    error_lines = "\n- ".join(errors)
    return (
        "The previous LayoutChange failed semantic validation. "
        "Return one corrected LayoutChange only.\n\n"
        f"Validation errors:\n- {error_lines}\n\n"
        f"Previous output:\n{change.model_dump_json()}\n\n"
        f"Evidence pack:\n{pack.model_dump_json()}"
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
