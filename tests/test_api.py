import anyio

from app import config
from app.api import routes
from app import memory
from app.evidence_pack import build
from app.fallback import load_cached_recommendation, validate_layout_change
from app.schemas import FeedbackRequest, RunRequest


def test_sessions_endpoint_lists_ai_cafe_a():
    response = anyio.run(routes.sessions)

    assert any(session.slug == "ai_cafe_a" for session in response)


def test_sessions_endpoint_lists_real_cafe():
    response = anyio.run(routes.sessions)

    assert any(session.slug == "real_cafe" and session.source_kind == "real" for session in response)


def test_state_endpoint_returns_fixture_status():
    response = anyio.run(routes.get_state, "ai_cafe_a")

    assert response.missing_required == []
    assert response.pattern.id == "pattern_queue_counter_crossing"


def test_real_cafe_fixture_pack_validates():
    response = anyio.run(routes.get_state, "real_cafe")
    cached = load_cached_recommendation("real_cafe")
    pack = build("real_cafe")

    assert response.missing_required == []
    assert response.assets["video"] == "cafe_videos/real_cctv.mp4"
    assert response.assets["frame"] == "demo_data/sessions/real_cafe/frame.jpg"
    assert response.pattern.id == "pattern_real_service_lane_choke"
    assert cached.fingerprint == "real_cafe_move_table_table_seating_1_m120_p0"
    assert validate_layout_change(cached, pack) == []


def test_run_endpoint_returns_valid_fallback_response(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    response = anyio.run(routes.run, RunRequest(session_id="ai_cafe_a"))

    assert [stage.name for stage in response.stages] == [
        "evidence_pack",
        "pattern_agent",
        "optimization_agent",
        "memory_write",
    ]
    pattern_stage = next(s for s in response.stages if s.name == "pattern_agent")
    assert pattern_stage.status == "fallback"
    assert response.layout_change.fingerprint == "ai_cafe_a_open_pickup_lane_v1"
    assert response.used_fallback is True
    assert response.memory_record.fallback_only is True
    assert response.memory_record.payload["session_id"] == "ai_cafe_a"
    assert response.memory_record.payload["pattern_id"] == "pattern_queue_counter_crossing"
    assert config.MEMORY_JSONL_PATH.exists()


def test_run_event_stream_yields_progress_and_final_response(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    async def collect():
        return [event async for event in routes._run_event_stream("ai_cafe_a")]

    events = anyio.run(collect)
    names = [event["event"] for event in events]
    final = events[-1]["data"]["response"]

    assert names[:2] == ["run_started", "stage_started"]
    assert "recommendation_ready" in names
    assert names[-1] == "run_completed"
    assert final["layout_change"]["fingerprint"] == "ai_cafe_a_open_pickup_lane_v1"
    assert [stage["name"] for stage in final["stages"]] == [
        "evidence_pack",
        "pattern_agent",
        "optimization_agent",
        "memory_write",
    ]


def test_run_endpoint_returns_real_cafe_fallback_response(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    response = anyio.run(routes.run, RunRequest(session_id="real_cafe"))

    assert [stage.name for stage in response.stages] == [
        "evidence_pack",
        "pattern_agent",
        "optimization_agent",
        "memory_write",
    ]
    pattern_stage = next(s for s in response.stages if s.name == "pattern_agent")
    assert pattern_stage.status == "fallback"
    assert response.layout_change.fingerprint == "real_cafe_move_table_table_seating_1_m120_p0"
    assert response.used_fallback is True
    assert response.memory_record.payload["session_id"] == "real_cafe"
    assert response.memory_record.payload["pattern_id"] == "pattern_real_service_lane_choke"


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


def test_run_endpoint_marks_memory_as_mubit_backed(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setenv("MUBIT_API_KEY", "test-mubit-key")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    async def fake_remember(record):
        return "mem_test_123"

    async def fake_query(*, lane, filters, limit, semantic_fallback=True):
        return []

    monkeypatch.setattr(memory, "_mubit_remember", fake_remember)
    monkeypatch.setattr(memory, "_mubit_query", fake_query)

    response = anyio.run(routes.run, RunRequest(session_id="ai_cafe_a"))

    assert response.memory_record.mubit_id == "mem_test_123"
    assert response.memory_record.fallback_only is False
    assert "mem_test_123" in config.MEMORY_JSONL_PATH.read_text(encoding="utf-8")


def test_recall_recommendations_merges_mubit_and_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("MUBIT_API_KEY", "test-mubit-key")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")
    change = load_cached_recommendation("ai_cafe_a")
    record = memory.new_memory_record(
        lane="location:demo:recommendations",
        intent="lesson",
        payload={
            "session_id": "ai_cafe_a",
            "pattern_id": "pattern_queue_counter_crossing",
            "layout_change": change.model_dump(mode="json"),
        },
    )

    async def fake_query(*, lane, filters, limit, semantic_fallback=True):
        assert filters == {
            "session_id": "ai_cafe_a",
            "pattern_id": "pattern_queue_counter_crossing",
        }
        assert limit == 12
        if lane == "location:demo:recommendations":
            return [record]
        if lane == "location:demo:feedback":
            return []
        raise AssertionError(f"unexpected lane {lane}")

    monkeypatch.setattr(memory, "_mubit_query", fake_query)

    hits = anyio.run(
        memory.recall_recommendations,
        "ai_cafe_a",
        "pattern_queue_counter_crossing",
    )

    assert [hit["fingerprint"] for hit in hits] == ["ai_cafe_a_open_pickup_lane_v1"]


def test_recall_prior_memory_derives_decisions_from_jsonl(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")
    accepted = load_cached_recommendation("ai_cafe_a")
    unknown = accepted.model_copy(
        update={
            "title": "Try a smaller pickup tweak",
            "fingerprint": "ai_cafe_a_unknown_pickup_tweak",
        }
    )
    rejected = accepted.model_copy(
        update={
            "title": "Move the queue marker instead",
            "fingerprint": "ai_cafe_a_rejected_queue_marker",
        }
    )

    for change in (accepted, unknown, rejected):
        anyio.run(
            memory.write_memory,
            memory.new_memory_record(
                lane="location:demo:recommendations",
                intent="lesson",
                payload={
                    "session_id": "ai_cafe_a",
                    "pattern_id": "pattern_queue_counter_crossing",
                    "layout_change": change.model_dump(mode="json"),
                },
            ),
        )
    anyio.run(
        memory.write_memory,
        memory.new_memory_record(
            lane="location:demo:feedback",
            intent="feedback",
            payload={
                "session_id": "ai_cafe_a",
                "pattern_id": "pattern_queue_counter_crossing",
                "proposal_fingerprint": accepted.fingerprint,
                "decision": "accept",
                "reason": "operator approved the pickup lane change",
            },
        ),
    )
    anyio.run(
        memory.write_memory,
        memory.new_memory_record(
            lane="location:demo:feedback",
            intent="feedback",
            payload={
                "session_id": "ai_cafe_a",
                "pattern_id": "pattern_queue_counter_crossing",
                "proposal_fingerprint": rejected.fingerprint,
                "decision": "reject",
                "reason": "queue marker confused guests",
            },
        ),
    )

    hits = anyio.run(
        memory.recall_prior_memory,
        "ai_cafe_a",
        "pattern_queue_counter_crossing",
    )
    by_fingerprint = {hit.fingerprint: hit for hit in hits}

    assert by_fingerprint[accepted.fingerprint].decision == "accept"
    assert by_fingerprint[accepted.fingerprint].reason == "operator approved the pickup lane change"
    assert by_fingerprint[accepted.fingerprint].source == "jsonl"
    assert by_fingerprint[rejected.fingerprint].decision == "reject"
    assert by_fingerprint[rejected.fingerprint].reason == "queue marker confused guests"
    assert by_fingerprint[unknown.fingerprint].decision == "unknown"
    assert by_fingerprint[unknown.fingerprint].reason is None


def test_run_endpoint_passes_prior_memories_to_evidence_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")
    change = load_cached_recommendation("ai_cafe_a")

    anyio.run(
        memory.write_memory,
        memory.new_memory_record(
            lane="location:demo:recommendations",
            intent="lesson",
            payload={
                "session_id": "ai_cafe_a",
                "pattern_id": "pattern_queue_counter_crossing",
                "layout_change": change.model_dump(mode="json"),
            },
        ),
    )
    anyio.run(
        routes.feedback,
        FeedbackRequest(
            session_id="ai_cafe_a",
            pattern_id="pattern_queue_counter_crossing",
            proposal_fingerprint=change.fingerprint,
            decision="reject",
            reason="created too much visual clutter",
        ),
    )

    response = anyio.run(routes.run, RunRequest(session_id="ai_cafe_a"))

    assert response.prior_recommendation_count == 1


def test_memories_endpoint_returns_merged_mubit_and_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("MUBIT_API_KEY", "test-mubit-key")
    monkeypatch.setattr(config, "MEMORY_JSONL_PATH", tmp_path / "mubit_fallback.jsonl")

    async def fake_remember(record):
        return None

    monkeypatch.setattr(memory, "_mubit_remember", fake_remember)

    local = anyio.run(
        routes.feedback,
        FeedbackRequest(
            session_id="ai_cafe_a",
            pattern_id="pattern_queue_counter_crossing",
            proposal_fingerprint="local_feedback",
            decision="accept",
        ),
    ).memory_record
    remote = local.model_copy(
        update={
            "mubit_id": "mem_remote_456",
            "fallback_only": False,
            "payload": {**local.payload, "proposal_fingerprint": "remote_feedback"},
        }
    )

    async def fake_query(*, lane, filters, limit, semantic_fallback=True):
        assert lane is None
        assert filters == {"session_id": "ai_cafe_a"}
        assert semantic_fallback is False
        return [remote]

    monkeypatch.setattr(memory, "_mubit_query", fake_query)

    response = anyio.run(routes.memories, "ai_cafe_a")

    assert response.source == "merged"
    assert {record.payload["proposal_fingerprint"] for record in response.records} == {
        "local_feedback",
        "remote_feedback",
    }
    assert any(record.mubit_id == "mem_remote_456" for record in response.records)
