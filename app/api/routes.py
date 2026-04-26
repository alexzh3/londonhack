"""MVP API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException

from app import config
from app.agents.optimization_agent import run_optimization
from app.evidence_pack import FixtureLoadError, build, state
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
    stages: list[StageTiming] = []

    with span("api.run", session_id=active_session_id) as run_span:
        try:
            start = _now()
            with span("evidence_pack.build", session_id=active_session_id):
                state_response = state(active_session_id)
                if state_response.missing_required:
                    raise FixtureLoadError(active_session_id, state_response.missing_required)
                prior_memories = await recall_prior_memory(active_session_id, state_response.pattern.id)
                pack = build(active_session_id, prior_recommendation_memories=prior_memories)
            stages.append(_stage("evidence_pack", start))

            start = _now()
            with span("optimization_agent.run", session_id=active_session_id):
                layout_change, used_fallback = await run_optimization(pack, active_session_id)
            with span("layout_change.validate", session_id=active_session_id):
                errors = validate_layout_change(layout_change, pack)
            if errors:
                raise HTTPException(status_code=502, detail={"validation_errors": errors})
            stages.append(_stage("optimization_agent", start, "fallback" if used_fallback else "done"))

            start = _now()
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
        except FixtureLoadError as exc:
            raise HTTPException(
                status_code=400,
                detail={"session_id": exc.session_id, "missing_required": exc.missing},
            ) from exc

        trace_url = trace_url_from_span(run_span)

    set_last_trace_url(trace_url)
    return RunResponse(
        stages=stages,
        layout_change=layout_change,
        memory_record=record,
        prior_recommendation_count=len(prior_memories),
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
