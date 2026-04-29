"""ObjectReviewAgent: detector + VLM object candidates -> keep/drop decisions."""

from __future__ import annotations

import os

from app import config as _config  # noqa: F401  # load .env before agent construction
from app.vision.objects import ObjectReviewBundle, ObjectReviewDecision, ObjectReviewResult


INSTRUCTIONS = """
You are a cafe scene object detection reviewer.

Return keep/drop decisions for detector candidates. Constraints:
- Review only detector_cache.detections[*].detection_id values; do not invent IDs.
- Keep objects supported by multiple frames, high confidence, or matching VLM detections of the same class.
- Drop likely false positives: giant counter regions mislabeled as dining table, tiny edge fragments, duplicate boxes for the same physical object, or low-confidence chair/table guesses with no VLM or multi-frame support.
- Be conservative: if unsure and the object could be useful for layout reasoning, keep it and explain why.
"""


def _default_model_name() -> str:
    if os.getenv("PYDANTIC_AI_GATEWAY_API_KEY") or os.getenv("PAIG_API_KEY"):
        return "gateway/anthropic:claude-sonnet-4-6"
    return "anthropic:claude-sonnet-4-6"


def _agent_model_spec():
    model_name = os.getenv("CAFETWIN_OBJECT_REVIEW_MODEL") or _default_model_name()
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

    object_review_agent: Agent[ObjectReviewBundle, ObjectReviewResult] | None = Agent(
        _agent_model_spec(),
        deps_type=ObjectReviewBundle,
        output_type=ObjectReviewResult,
        instructions=INSTRUCTIONS,
        retries=1,
        output_retries=1,
        defer_model_check=True,
    )

    @object_review_agent.output_validator
    async def validate_agent_output(
        ctx: RunContext[ObjectReviewBundle],
        output: ObjectReviewResult,
    ) -> ObjectReviewResult:
        errors = validate_object_review(output, ctx.deps)
        if errors:
            raise ModelRetry("Fix these ObjectReviewResult validation errors:\n- " + "\n- ".join(errors))
        return output
except Exception:
    object_review_agent = None


async def run_object_review(bundle: ObjectReviewBundle) -> tuple[ObjectReviewResult, bool]:
    fallback = heuristic_object_review(bundle)
    if object_review_agent is None or not _live_agent_enabled():
        return fallback, True

    try:
        result = await object_review_agent.run(_review_prompt(bundle), deps=bundle)
        return result.output, False
    except Exception:
        return fallback, True


def heuristic_object_review(bundle: ObjectReviewBundle) -> ObjectReviewResult:
    vlm_matches = _vlm_match_ids(bundle) if bundle.vlm_cache else set()
    decisions = []
    for detection in bundle.detector_cache.detections:
        keep = (
            detection.support_count >= 2
            or detection.confidence >= 0.35
            or detection.detection_id in vlm_matches
        )
        reason = (
            "multi-frame/high-confidence detector evidence or VLM agreement"
            if keep
            else "low-confidence single-frame detector candidate without VLM agreement"
        )
        decisions.append(
            ObjectReviewDecision(
                detection_id=detection.detection_id,
                action="keep" if keep else "drop",
                reason=reason,
            )
        )
    return ObjectReviewResult(
        session_id=bundle.session_id,
        decisions=decisions,
        notes=["deterministic fallback review; live agent disabled or unavailable"],
    )


def validate_object_review(output: ObjectReviewResult, bundle: ObjectReviewBundle) -> list[str]:
    errors = []
    if output.session_id != bundle.session_id:
        errors.append("session_id must match review bundle")
    valid_ids = {detection.detection_id for detection in bundle.detector_cache.detections}
    seen = set()
    for decision in output.decisions:
        if decision.detection_id not in valid_ids:
            errors.append(f"unknown detection_id: {decision.detection_id}")
        if decision.detection_id in seen:
            errors.append(f"duplicate decision for detection_id: {decision.detection_id}")
        seen.add(decision.detection_id)
    missing = valid_ids - seen
    if missing:
        errors.append("missing decisions for detection_id(s): " + ", ".join(sorted(missing)))
    return errors


def _review_prompt(bundle: ObjectReviewBundle) -> str:
    return (
        "Review the static layout object detections. "
        "Return one keep/drop decision for every detector candidate.\n\n"
        "Detector/VLM review bundle JSON:\n"
        f"{bundle.model_dump_json()}"
    )


def _vlm_match_ids(bundle: ObjectReviewBundle) -> set[str]:
    if bundle.vlm_cache is None:
        return set()
    matches = set()
    for detector in bundle.detector_cache.detections:
        for vlm in bundle.vlm_cache.detections:
            if detector.class_name == vlm.class_name and _bbox_iou(detector.bbox_xyxy, vlm.bbox_xyxy) >= 0.25:
                matches.add(detector.detection_id)
                break
    return matches


def _bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / ((area_a + area_b - inter) or 1e-9)


def _live_agent_enabled() -> bool:
    from app._runtime_overrides import force_fallback_active

    if force_fallback_active():
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
