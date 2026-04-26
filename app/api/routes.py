"""MVP API routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse

from app import config
from app.agents.optimization_agent import run_optimization
from app.agents.pattern_agent import run_pattern_detection
from app.agents.sim_agent import run_sim_prompt
from app.evidence_pack import FixtureLoadError, build, build_pattern_evidence_bundle, state
from app.fallback import validate_layout_change
from app.logfire_setup import get_last_trace_url, set_last_trace_url, span, trace_url_from_span
from app.memory import list_memories, new_memory_record, recall_prior_memory, write_memory
from app.schemas import (
    FeedbackMemoryPayload,
    FeedbackRequest,
    FeedbackResponse,
    LogfireURLResponse,
    MemoriesResponse,
    RecommendationMemoryPayload,
    RunRequest,
    RunResponse,
    SessionManifest,
    SimPromptRequest,
    SimPromptResponse,
    StageTiming,
    StateResponse,
)
from app.sessions import list_session_manifests


router = APIRouter()


@router.get("/api/sessions")
async def sessions() -> list[SessionManifest]:
    return list_session_manifests()


@router.get("/api/state")
async def get_state(session_id: str = config.DEFAULT_SESSION_ID) -> StateResponse:
    return state(session_id)


@router.post("/api/run")
async def run(
    body: RunRequest | None = Body(default=None),
    session_id: str | None = None,
) -> RunResponse:
    active_session_id = session_id or (body.session_id if body else config.DEFAULT_SESSION_ID)
    response: RunResponse | None = None

    async for event in _run_event_stream(active_session_id):
        if event["event"] == "run_completed":
            response = RunResponse.model_validate(event["data"]["response"])

    if response is None:
        raise HTTPException(status_code=500, detail="run did not complete")
    return response


@router.post("/api/run/stream")
async def run_stream(
    body: RunRequest | None = Body(default=None),
    session_id: str | None = None,
) -> StreamingResponse:
    active_session_id = session_id or (body.session_id if body else config.DEFAULT_SESSION_ID)

    async def event_source() -> AsyncIterator[str]:
        try:
            async for event in _run_event_stream(active_session_id):
                yield _sse(event["event"], event["data"])
        except HTTPException as exc:
            yield _sse("error", {"status_code": exc.status_code, "detail": exc.detail})
        except Exception as exc:
            yield _sse("error", {"status_code": 500, "detail": str(exc)})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_event_stream(active_session_id: str) -> AsyncIterator[dict[str, Any]]:
    stages: list[StageTiming] = []

    yield _event("run_started", {"session_id": active_session_id})
    with span("api.run", session_id=active_session_id) as run_span:
        try:
            start = _now()
            yield _event("stage_started", {"name": "evidence_pack"})
            with span("evidence_pack.build", session_id=active_session_id):
                state_response = state(active_session_id)
                if state_response.missing_required:
                    raise FixtureLoadError(active_session_id, state_response.missing_required)
                pattern_bundle = build_pattern_evidence_bundle(state_response)
            stages.append(_stage("evidence_pack", start))
            yield _event(
                "stage_completed",
                {
                    "stage": stages[-1].model_dump(mode="json"),
                    "message": "Loaded fixture/live perception bundle",
                    "object_count": len(pattern_bundle.object_inventory.objects),
                    "kpi_windows": len(pattern_bundle.kpi_windows),
                },
            )

            start = _now()
            yield _event("stage_started", {"name": "pattern_agent"})
            with span("pattern_agent.run", session_id=active_session_id):
                pattern, pattern_used_fallback = await run_pattern_detection(
                    pattern_bundle, active_session_id
                )
            prior_memories = await recall_prior_memory(active_session_id, pattern.id)
            pack = build(
                active_session_id,
                prior_recommendation_memories=prior_memories,
                pattern=pattern,
            )
            stages.append(
                _stage("pattern_agent", start, "fallback" if pattern_used_fallback else "done")
            )
            yield _event(
                "stage_completed",
                {
                    "stage": stages[-1].model_dump(mode="json"),
                    "message": pattern.title,
                    "pattern_id": pattern.id,
                    "prior_recommendation_count": len(prior_memories),
                },
            )

            start = _now()
            yield _event("stage_started", {"name": "optimization_agent"})
            with span("optimization_agent.run", session_id=active_session_id):
                layout_change, used_fallback = await run_optimization(pack, active_session_id)
            with span("layout_change.validate", session_id=active_session_id):
                errors = validate_layout_change(layout_change, pack)
            if errors:
                raise HTTPException(status_code=502, detail={"validation_errors": errors})
            stages.append(_stage("optimization_agent", start, "fallback" if used_fallback else "done"))
            yield _event(
                "recommendation_ready",
                {
                    "title": layout_change.title,
                    "target_id": layout_change.target_id,
                    "action": layout_change.simulation.action,
                    "expected_kpi_delta": layout_change.expected_kpi_delta,
                    "used_fallback": used_fallback,
                },
            )
            yield _event(
                "stage_completed",
                {
                    "stage": stages[-1].model_dump(mode="json"),
                    "message": layout_change.title,
                    "fingerprint": layout_change.fingerprint,
                    "used_fallback": used_fallback,
                },
            )

            start = _now()
            yield _event("stage_started", {"name": "memory_write"})
            recommendation_payload = RecommendationMemoryPayload(
                session_id=active_session_id,
                pattern_id=pack.pattern.id,
                layout_change=layout_change,
            )
            record = new_memory_record(
                lane="location:demo:recommendations",
                intent="lesson",
                payload={
                    **recommendation_payload.model_dump(mode="json"),
                    "used_fallback": used_fallback,
                },
            )
            with span("memory.write", session_id=active_session_id):
                record = await write_memory(record)
            stages.append(_stage("memory_write", start))
            yield _event(
                "stage_completed",
                {
                    "stage": stages[-1].model_dump(mode="json"),
                    "message": "Stored recommendation memory",
                    "mubit_id": record.mubit_id,
                    "fallback_only": record.fallback_only,
                },
            )
        except FixtureLoadError as exc:
            raise HTTPException(
                status_code=400,
                detail={"session_id": exc.session_id, "missing_required": exc.missing},
            ) from exc

        trace_url = trace_url_from_span(run_span)

    set_last_trace_url(trace_url)
    response = RunResponse(
        stages=stages,
        layout_change=layout_change,
        memory_record=record,
        prior_recommendation_count=len(prior_memories),
        used_fallback=used_fallback,
        logfire_trace_url=trace_url,
    )
    yield _event("run_completed", {"response": response.model_dump(mode="json")})


@router.post("/api/sim/prompt")
async def sim_prompt(body: SimPromptRequest) -> SimPromptResponse:
    """Natural-language prompt -> ScenarioCommand via SimAgent.

    The frontend's chat input posts `{session_id, prompt, active_scenario}`
    and gets back a ScenarioCommand that the client materialises onto the
    scenario rail. Falls back to a deterministic heuristic when the live
    agent is disabled (no API key / CAFETWIN_FORCE_FALLBACK=1); the
    `used_fallback` flag lets the UI badge that distinction.
    """
    with span(
        "sim_agent.run",
        session_id=body.session_id,
        prompt_len=len(body.prompt),
    ) as sim_span:
        command, used_fallback = await run_sim_prompt(body.prompt, body.active_scenario)
        trace_url = trace_url_from_span(sim_span)
    set_last_trace_url(trace_url)
    return SimPromptResponse(
        command=command,
        used_fallback=used_fallback,
        logfire_trace_url=trace_url,
    )


@router.post("/api/feedback")
async def feedback(body: FeedbackRequest) -> FeedbackResponse:
    feedback_payload = FeedbackMemoryPayload(
        session_id=body.session_id,
        pattern_id=body.pattern_id,
        proposal_fingerprint=body.proposal_fingerprint,
        decision=body.decision,
    )
    record = new_memory_record(
        lane="location:demo:feedback",
        intent="feedback",
        payload={
            **feedback_payload.model_dump(mode="json"),
            "reason": body.reason,
        },
    )
    with span("feedback.write", session_id=body.session_id, pattern_id=body.pattern_id):
        record = await write_memory(record)
    return FeedbackResponse(decision=body.decision, memory_record=record)


@router.get("/api/memories")
async def memories(session_id: str | None = None) -> MemoriesResponse:
    records, source = await list_memories(session_id=session_id)
    return MemoriesResponse(records=records, source=source)


@router.get("/api/logfire_url")
async def logfire_url() -> LogfireURLResponse:
    return LogfireURLResponse(url=get_last_trace_url())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stage(name, started_at: datetime, status: str = "done") -> StageTiming:
    return StageTiming(name=name, started_at=started_at, ended_at=_now(), status=status)


def _event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "data": data}


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
