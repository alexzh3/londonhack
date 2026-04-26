import anyio

from app import config
from app.api import routes
from app.schemas import FeedbackRequest, RunRequest


def test_sessions_endpoint_lists_ai_cafe_a():
    response = anyio.run(routes.sessions)

    assert any(session.slug == "ai_cafe_a" for session in response)


def test_state_endpoint_returns_fixture_status():
    response = anyio.run(routes.get_state, "ai_cafe_a")

    assert response.missing_required == []
    assert response.pattern.id == "pattern_queue_counter_crossing"


def test_run_endpoint_returns_valid_fallback_response(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    response = anyio.run(routes.run, RunRequest(session_id="ai_cafe_a"))

    assert [stage.name for stage in response.stages] == [
        "evidence_pack",
        "optimization_agent",
        "memory_write",
    ]
    assert response.layout_change.fingerprint == "ai_cafe_a_open_pickup_lane_v1"
    assert response.used_fallback is True
    assert response.memory_record.fallback_only is True
    assert response.memory_record.payload["session_id"] == "ai_cafe_a"
    assert response.memory_record.payload["pattern_id"] == "pattern_queue_counter_crossing"
    assert config.MEMORY_JSONL_PATH.exists()


def test_feedback_endpoint_writes_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    response = anyio.run(
        routes.feedback,
        FeedbackRequest(
            session_id="ai_cafe_a",
            pattern_id="pattern_queue_counter_crossing",
            proposal_fingerprint="ai_cafe_a_open_pickup_lane_v1",
            decision="accept",
        ),
    )

    assert response.decision == "accept"
    assert response.memory_record.lane == "location:demo:feedback"


def test_memories_endpoint_filters_by_session(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    anyio.run(
        routes.feedback,
        FeedbackRequest(
            session_id="ai_cafe_a",
            pattern_id="pattern_queue_counter_crossing",
            proposal_fingerprint="ai_cafe_a_open_pickup_lane_v1",
            decision="accept",
        ),
    )
    anyio.run(
        routes.feedback,
        FeedbackRequest(
            session_id="other_cafe",
            pattern_id="pattern_queue_counter_crossing",
            proposal_fingerprint="other_proposal",
            decision="reject",
        ),
    )

    all_response = anyio.run(routes.memories)
    filtered_response = anyio.run(routes.memories, "ai_cafe_a")

    assert len(all_response.records) == 2
    assert len(filtered_response.records) == 1
    assert filtered_response.records[0].payload["session_id"] == "ai_cafe_a"


def test_run_endpoint_caches_logfire_trace_url(monkeypatch, tmp_path):
    trace_url = "https://logfire.example/demo/live?query=trace_id"
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")
    monkeypatch.setattr(routes, "trace_url_from_span", lambda _span: trace_url)

    response = anyio.run(routes.run, RunRequest(session_id="ai_cafe_a"))
    cached = anyio.run(routes.logfire_url)

    assert response.logfire_trace_url == trace_url
    assert cached.url == trace_url
