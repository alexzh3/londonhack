"""PatternAgent: PatternEvidenceBundle -> validated OperationalPattern.

Detects the dominant operational friction pattern from KPI windows + scene
inventory + zones. The OptimizationAgent then proposes a layout change to
reduce that pattern's worst KPI. Mirrors OptimizationAgent's structure:
defer_model_check + @output_validator + ModelRetry + cached fixture fallback.
"""

from __future__ import annotations

import os

from app import config as _config  # noqa: F401  # load .env before agent construction
from app.fallback import load_cached_pattern, validate_operational_pattern
from app.schemas import OperationalPattern, PatternEvidenceBundle


INSTRUCTIONS = """
You are a cafe operations pattern detector.

Return exactly one OperationalPattern. Constraints:
- evidence must be a non-empty subset of kpi_windows[*].memory_id; ground each evidence summary in the actual KPI numbers from the cited window.
- affected_zones must be a non-empty subset of zones[*].id (refer to real zones in the layout).
- pattern_type must match the dominant kind of friction in the KPI windows: queue_crossing for staff/customer crossings + queue obstruction, staff_detour for high staff_walk_distance + table_detour_score, table_blockage when seating layout creates table-side obstructions, pickup_congestion for pickup-area pinch points.
- severity is high if the worst KPI window has staff_customer_crossings >= 6 OR queue_obstruction_seconds >= 15 OR congestion_score >= 0.7; medium if any window crosses 3 / 8s / 0.5; otherwise low.
- title and summary must be operationally specific (cite zones and the worst KPI number, not vague descriptions).
"""


def _default_model_name() -> str:
    if os.getenv("PYDANTIC_AI_GATEWAY_API_KEY") or os.getenv("PAIG_API_KEY"):
        return "gateway/anthropic:claude-sonnet-4-6"
    return "anthropic:claude-sonnet-4-6"


def _agent_model_spec():
    model_name = os.getenv("CAFETWIN_PATTERN_MODEL") or _default_model_name()
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
    from pydantic_ai import Agent, ModelRetry, RunContext

    pattern_agent: Agent[PatternEvidenceBundle, OperationalPattern] | None = Agent(
        _agent_model_spec(),
        deps_type=PatternEvidenceBundle,
        output_type=OperationalPattern,
        instructions=INSTRUCTIONS,
        retries=1,
        output_retries=1,
        defer_model_check=True,
    )

    @pattern_agent.output_validator
    async def validate_agent_output(
        ctx: RunContext[PatternEvidenceBundle],
        output: OperationalPattern,
    ) -> OperationalPattern:
        errors = validate_operational_pattern(output, ctx.deps)
        if errors:
            raise ModelRetry(
                "Fix these OperationalPattern validation errors:\n- " + "\n- ".join(errors)
            )
        return output
except Exception:
    pattern_agent = None


async def run_pattern_detection(
    bundle: PatternEvidenceBundle,
    session_id: str,
) -> tuple[OperationalPattern, bool]:
    """Run the live agent when configured; otherwise return the cached fixture pattern.

    The live agent enriches title / summary / severity / evidence / pattern_type /
    affected_zones with reasoning over the actual KPI numbers. We normalize
    pattern.id to the canonical session fixture ID so PriorRecommendationMemory
    recall stays scoped to the same pattern across runs (otherwise the agent
    would pick a new ID each call and 'seen before' would always be 0).
    """
    fallback = load_cached_pattern(session_id)
    if pattern_agent is None or not _live_agent_enabled():
        return fallback, True

    try:
        result = await pattern_agent.run(
            _pattern_prompt(bundle, canonical_pattern_id=fallback.id),
            deps=bundle,
        )
        normalized = result.output.model_copy(update={"id": fallback.id})
        return normalized, False
    except Exception:
        return fallback, True


def _pattern_prompt(bundle: PatternEvidenceBundle, *, canonical_pattern_id: str) -> str:
    return (
        "Detect the dominant operational pattern from the evidence below. "
        "Cite kpi_windows[*].memory_id in evidence and use only zones[*].id values for affected_zones. "
        f"Use this stable pattern.id so prior decisions can be recalled: {canonical_pattern_id!r}.\n\n"
        "Evidence bundle JSON:\n"
        f"{bundle.model_dump_json()}"
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
