"""OptimizationAgent: CafeEvidencePack -> validated LayoutChange."""

from __future__ import annotations

import os
import json

from app import config as _config  # noqa: F401  # load .env before agent construction
from app.fallback import load_cached_recommendation
from app.layout_candidates import (
    generate_layout_candidates,
    materialize_layout_change,
    validate_optimization_choice,
)
from app.schemas import CafeEvidencePack, LayoutCandidate, LayoutChange, OptimizationChoice


INSTRUCTIONS = """
You are a cafe layout optimization agent.

Return exactly one OptimizationChoice selecting a deterministic layout candidate.
Constraints:
- selected_candidate_id must be one of candidate_shifts[*].candidate_id.
- evidence_ids must be a non-empty subset of pattern.evidence[*].memory_id.
- Prefer the highest-scoring single move that reduces the pattern's worst KPI without reducing seating.
- Use prior_recommendation_memories: favor compatible accepted proposals, avoid rejected repeats unless the current evidence materially changed, and treat unknown decisions as weak signals only.
- Be concrete: title, rationale, confidence, and risk must be demo-ready.
- Keep rationale to 2-3 sentences. Do not quote candidate scores or numeric KPI deltas; the backend materializes those from the selected candidate.
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
    from pydantic_ai import Agent, ModelRetry, RunContext

    optimization_agent: Agent[CafeEvidencePack, OptimizationChoice] | None = Agent(
        _agent_model_spec(),
        deps_type=CafeEvidencePack,
        output_type=OptimizationChoice,
        instructions=INSTRUCTIONS,
        retries=1,
        output_retries=1,
        defer_model_check=True,
    )

    @optimization_agent.output_validator
    async def validate_agent_output(
        ctx: RunContext[CafeEvidencePack],
        output: OptimizationChoice,
    ) -> OptimizationChoice:
        errors = validate_optimization_choice(output, ctx.deps)
        if errors:
            raise ModelRetry("Fix these OptimizationChoice validation errors:\n- " + "\n- ".join(errors))
        return output
except Exception:
    optimization_agent = None


async def run_optimization(pack: CafeEvidencePack, session_id: str) -> tuple[LayoutChange, bool]:
    """Run the live agent when configured; otherwise return the cached safe recommendation."""
    fallback = load_cached_recommendation(session_id)
    candidates = generate_layout_candidates(pack)
    if optimization_agent is None or not _live_agent_enabled():
        return fallback, True
    if not candidates:
        return fallback, True

    try:
        result = await optimization_agent.run(_optimization_prompt(pack, candidates), deps=pack)
        return materialize_layout_change(result.output, pack, candidates), False
    except Exception:
        return fallback, True


def _optimization_prompt(
    pack: CafeEvidencePack,
    candidates: list[LayoutCandidate] | None = None,
) -> str:
    candidates = candidates if candidates is not None else generate_layout_candidates(pack)
    return (
        "Optimize this cafe layout from the evidence pack. "
        "Select exactly one candidate shift; do not invent coordinates. "
        "Use only cited evidence IDs.\n\n"
        "Prior recommendation memory:\n"
        f"{_prior_memory_summary(pack)}\n\n"
        "Candidate shifts JSON:\n"
        f"{_candidate_summary(candidates)}\n\n"
        "Evidence pack JSON:\n"
        f"{pack.model_dump_json()}"
    )


def _prior_memory_summary(pack: CafeEvidencePack) -> str:
    if not pack.prior_recommendation_memories:
        return "No prior recommendation memory for this session and pattern."
    lines = []
    for memory in pack.prior_recommendation_memories:
        reason = f" reason={memory.reason}" if memory.reason else ""
        lines.append(
            f"- decision={memory.decision} fingerprint={memory.fingerprint} "
            f"target={memory.target_id} title={memory.title!r}{reason}"
        )
    return "\n".join(lines)


def _candidate_summary(candidates: list[LayoutCandidate]) -> str:
    return json.dumps(
        [candidate.model_dump(mode="json") for candidate in candidates],
        separators=(",", ":"),
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
