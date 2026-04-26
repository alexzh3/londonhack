"""Local JSONL memory plus best-effort MuBit integration."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

import httpx

from app import config
from app.logfire_setup import span
from app.schemas import LayoutChange, MemoryIntent, MemoryLane, MemoryRecord, PriorRecommendationMemory

MUBIT_DEFAULT_ENDPOINT = "https://api.mubit.ai"
# Legacy single-agent slug. Kept as the fallback for memory records whose
# lane doesn't map cleanly to a registered MuBit AgentDefinition (and as
# the default when Tier 1E `bootstrap_mubit_agents` hasn't run / opted in).
MUBIT_AGENT_ID = "cafetwin-optimization-agent"
RECOMMENDATION_LANE = "location:demo:recommendations"
FEEDBACK_LANE = "location:demo:feedback"
PATTERN_LANE = "location:demo:patterns"
MemorySource = Literal["mubit", "jsonl"]


def _resolve_agent_id(record: "MemoryRecord") -> str:
    """Pick the MuBit agent_id for a memory record's MuBit ingest payload.

    When Tier 1E (`CAFETWIN_MUBIT_AGENTS=1`) has registered AgentDefinitions
    for both PatternAgent and OptimizationAgent, the per-lane mapping below
    routes recommendations + feedback to the OptimizationAgent's slug and
    pattern records to the PatternAgent's slug. Falls back to the legacy
    single-agent slug when bootstrap hasn't run or the lane doesn't map.
    """
    from app.mubit_agents import (
        OPTIMIZATION_AGENT_LOCAL,
        PATTERN_AGENT_LOCAL,
        get_agent_id,
    )

    if record.lane == PATTERN_LANE:
        return get_agent_id(PATTERN_AGENT_LOCAL, MUBIT_AGENT_ID)
    # Recommendations + feedback both flow through the OptimizationAgent's
    # decision surface: the agent emits the LayoutChange, the user accepts
    # or rejects it, and either way the feedback teaches the same agent.
    return get_agent_id(OPTIMIZATION_AGENT_LOCAL, MUBIT_AGENT_ID)


def new_memory_record(
    *,
    lane: MemoryLane,
    intent: MemoryIntent,
    payload: dict,
    fallback_only: bool = True,
) -> MemoryRecord:
    return MemoryRecord(
        lane=lane,
        intent=intent,
        payload=payload,
        written_at=datetime.now(timezone.utc),
        mubit_id=None,
        fallback_only=fallback_only,
    )


async def write_memory(record: MemoryRecord) -> MemoryRecord:
    """Write to MuBit when configured and always mirror to local JSONL."""
    record = record.model_copy(update={"fallback_only": True})
    if _mubit_available():
        with span("memory.write.mubit", lane=record.lane):
            try:
                mubit_id = await _mubit_remember(record)
            except Exception:
                mubit_id = None
            if mubit_id:
                record = record.model_copy(update={"mubit_id": mubit_id, "fallback_only": False})

    with span("memory.write.jsonl", lane=record.lane):
        config.MEMORY_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.MEMORY_JSONL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
    return record


async def recall_prior_memory(
    session_id: str,
    pattern_id: str,
    limit: int = 3,
) -> list[PriorRecommendationMemory]:
    records: list[tuple[MemoryRecord, MemorySource]] = []
    query_limit = max(limit * 4, 12)
    if _mubit_available():
        with span("memory.recall.mubit", session_id=session_id, pattern_id=pattern_id):
            for lane in (RECOMMENDATION_LANE, FEEDBACK_LANE):
                try:
                    mubit_records = await _mubit_query(
                        lane=lane,
                        filters={"session_id": session_id, "pattern_id": pattern_id},
                        limit=query_limit,
                    )
                except Exception:
                    mubit_records = []
                records.extend((record, "mubit") for record in mubit_records)

    with span("memory.recall.jsonl", session_id=session_id, pattern_id=pattern_id):
        records.extend(
            (record, "jsonl")
            for record in _list_jsonl_memories(session_id=session_id)
            if record.lane in {RECOMMENDATION_LANE, FEEDBACK_LANE}
            and record.payload.get("pattern_id") == pattern_id
        )

    return _build_prior_memory_view(records, session_id=session_id, pattern_id=pattern_id)[:limit]


async def recall_recommendations(session_id: str, pattern_id: str) -> list:
    memories = await recall_prior_memory(session_id, pattern_id)
    return [memory.layout_change.model_dump(mode="json") for memory in memories]


async def list_memories(session_id: str | None = None) -> tuple[list[MemoryRecord], str]:
    mubit_records: list[MemoryRecord] = []
    if _mubit_available() and session_id is not None:
        with span("memory.list.mubit", session_id=session_id):
            try:
                mubit_records = await _mubit_query(
                    lane=None,
                    filters={"session_id": session_id},
                    limit=50,
                    semantic_fallback=False,
                )
            except Exception:
                mubit_records = []

    jsonl_records = _list_jsonl_memories(session_id=session_id)
    records = _merge_memory_records([*mubit_records, *jsonl_records])
    source = "merged" if mubit_records and jsonl_records else "mubit" if mubit_records else "jsonl"
    return records, source


def _list_jsonl_memories(session_id: str | None = None) -> list[MemoryRecord]:
    if not config.MEMORY_JSONL_PATH.exists():
        return []

    records: list[MemoryRecord] = []
    with config.MEMORY_JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = MemoryRecord.model_validate_json(line)
            except ValueError:
                continue
            if session_id is not None and record.payload.get("session_id") != session_id:
                continue
            records.append(record)
    return records


def memory_id(prefix: str = "local") -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _mubit_available() -> bool:
    return bool(os.getenv("MUBIT_API_KEY"))


async def _mubit_remember(record: MemoryRecord) -> str | None:
    payload = record.payload
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    # MuBit's /v2/control/ingest requires `item_id` (caller-supplied dedupe
    # key) and `content_type` (e.g. "text") on every item — without them the
    # endpoint 422s with "missing field". The agent-supplied LayoutChange
    # `fingerprint` makes a stable item_id when present so re-running the
    # same recommendation hits MuBit's own dedup; otherwise fall back to a
    # uuid so each call lands as a fresh row.
    layout = payload.get("layout_change") if isinstance(payload, dict) else None
    fingerprint = layout.get("fingerprint") if isinstance(layout, dict) else None
    proposal_fp = payload.get("proposal_fingerprint") if isinstance(payload, dict) else None
    stable_seed = fingerprint or proposal_fp
    item_id = (
        f"cafetwin_{record.lane.replace(':', '_')}_{stable_seed}"
        if isinstance(stable_seed, str) and stable_seed
        else f"cafetwin_{uuid4().hex[:16]}"
    )
    agent_id = _resolve_agent_id(record)
    body = {
        "run_id": session_id or "cafetwin-demo",
        "agent_id": agent_id,
        "items": [
            {
                "item_id": item_id,
                "content_type": "text",
                "text": _mubit_content(record, agent_id=agent_id),
                "intent": record.intent,
                "lane": record.lane,
                "agent_id": agent_id,
                "metadata_json": json.dumps(
                    _mubit_metadata(record, agent_id=agent_id), separators=(",", ":")
                ),
                "occurrence_time": int(record.written_at.timestamp()),
            }
        ],
    }
    response = await _mubit_post("/v2/control/ingest", body)
    mubit_id = _mubit_id_from_response(response)
    job_id = _dig(response, "job_id")
    if isinstance(job_id, str) and job_id:
        await _mubit_wait_for_ingest(job_id)
    return mubit_id or (job_id if isinstance(job_id, str) and job_id else None)


async def _mubit_query(
    *,
    lane: str | None,
    filters: dict[str, str],
    limit: int,
    semantic_fallback: bool = True,
) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    session_id = filters.get("session_id")
    if session_id:
        activity = await _mubit_post(
            "/v2/control/activity",
            {"run_id": session_id, "limit": max(limit * 4, 25)},
        )
        records.extend(_records_from_mubit_items(_mubit_items(activity), lane=lane, filters=filters))

    if semantic_fallback and lane and len(records) < limit and session_id:
        result = await _mubit_post(
            "/v2/control/query",
            {
                "run_id": session_id,
                "query": (
                    "Return CafeTwin MemoryRecord entries whose payload JSON has "
                    f"session_id={filters.get('session_id')} and "
                    f"pattern_id={filters.get('pattern_id')}."
                ),
                "include_working_memory": False,
                "mode": "agent_routed",
                "lane_filter": lane,
                "budget": "low",
            },
        )
        records.extend(_records_from_mubit_items(_mubit_items(result), lane=lane, filters=filters))

    return _merge_memory_records(records)[:limit]


async def _mubit_wait_for_ingest(job_id: str) -> None:
    attempts = int(os.getenv("MUBIT_INGEST_POLL_ATTEMPTS", "4"))
    delay = float(os.getenv("MUBIT_INGEST_POLL_INTERVAL_S", "0.15"))
    for _ in range(max(0, attempts)):
        try:
            status = await _mubit_get(f"/v2/control/ingest/jobs/{job_id}")
        except Exception:
            return
        state = status.get("status") if isinstance(status, dict) else None
        if status.get("done") or state in {"completed", "done"}:
            return
        if state == "failed":
            raise RuntimeError("mubit ingest failed")
        await asyncio.sleep(delay)


async def _mubit_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_mubit_timeout(), follow_redirects=True) as client:
        response = await client.post(_mubit_url(path), json=body, headers=_mubit_headers())
        response.raise_for_status()
        return response.json() if response.content else {}


async def _mubit_get(path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_mubit_timeout(), follow_redirects=True) as client:
        response = await client.get(_mubit_url(path), headers=_mubit_headers())
        response.raise_for_status()
        return response.json() if response.content else {}


def _mubit_url(path: str) -> str:
    endpoint = os.getenv("MUBIT_HTTP_ENDPOINT") or os.getenv("MUBIT_ENDPOINT") or MUBIT_DEFAULT_ENDPOINT
    return f"{endpoint.rstrip('/')}/{path.lstrip('/')}"


def _mubit_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.getenv('MUBIT_API_KEY', '')}"}


def _mubit_timeout() -> float:
    return float(os.getenv("MUBIT_TIMEOUT_S", "8"))


def _mubit_content(record: MemoryRecord, *, agent_id: str = MUBIT_AGENT_ID) -> str:
    return (
        f"CafeTwin {record.intent} memory on {record.lane} by {agent_id}.\n"
        f"CAFETWIN_MEMORY_RECORD_JSON={record.model_dump_json()}"
    )


def _mubit_metadata(
    record: MemoryRecord, *, agent_id: str = MUBIT_AGENT_ID
) -> dict[str, Any]:
    payload = record.payload if isinstance(record.payload, dict) else {}
    return {
        "app": "cafetwin",
        "agent_id": agent_id,
        "schema": "MemoryRecord",
        "lane": record.lane,
        "intent": record.intent,
        "session_id": payload.get("session_id"),
        "pattern_id": payload.get("pattern_id"),
        "record": record.model_dump(mode="json"),
    }


def _mubit_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    items: list[Any] = []
    for key in ("entries", "evidence", "results", "items", "records", "memories"):
        value = data.get(key)
        if isinstance(value, list):
            items.extend(value)
    nested = data.get("data")
    if isinstance(nested, (dict, list)):
        items.extend(_mubit_items(nested))
    return items


def _records_from_mubit_items(
    items: Iterable[Any],
    *,
    lane: str | None,
    filters: dict[str, str],
) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for item in items:
        record = _record_from_mubit_item(item)
        if record is not None and _record_matches(record, lane=lane, filters=filters):
            records.append(record)
    return records


def _record_from_mubit_item(item: Any) -> MemoryRecord | None:
    candidates = list(_candidate_records(item))
    if isinstance(item, dict):
        for value in item.values():
            if isinstance(value, (dict, str)):
                candidates.extend(_candidate_records(value))
    for candidate in candidates:
        try:
            record = MemoryRecord.model_validate(candidate)
        except (TypeError, ValueError):
            continue
        mubit_id = _mubit_id_from_response(item)
        updates: dict[str, Any] = {"fallback_only": False}
        if mubit_id and record.mubit_id is None:
            updates["mubit_id"] = mubit_id
        return record.model_copy(update=updates)
    return None


def _candidate_records(value: Any) -> Iterable[Any]:
    if isinstance(value, MemoryRecord):
        yield value.model_dump(mode="json")
        return
    if isinstance(value, dict):
        for key in ("record", "memory_record", "payload_record"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                yield candidate
        for key in ("metadata", "metadata_json", "entry_json"):
            parsed = _maybe_json(value.get(key))
            if isinstance(parsed, dict):
                yield from _candidate_records(parsed)
        for key in ("content", "text", "body"):
            yield from _candidate_records(value.get(key))
        return
    if isinstance(value, str):
        parsed = _maybe_json(value)
        if isinstance(parsed, dict):
            yield parsed


def _maybe_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if "CAFETWIN_MEMORY_RECORD_JSON=" in text:
        text = text.split("CAFETWIN_MEMORY_RECORD_JSON=", 1)[1].strip()
    if not text.startswith("{"):
        start = text.find("{")
        if start == -1:
            return None
        text = text[start:]
    try:
        return json.loads(text)
    except ValueError:
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(text)
        except ValueError:
            return None
        return obj


def _record_matches(record: MemoryRecord, *, lane: str | None, filters: dict[str, str]) -> bool:
    if lane and record.lane != lane:
        return False
    for key, value in filters.items():
        if record.payload.get(key) != value:
            return False
    return True


def _build_prior_memory_view(
    records: Iterable[tuple[MemoryRecord, MemorySource]],
    *,
    session_id: str,
    pattern_id: str,
) -> list[PriorRecommendationMemory]:
    recommendations: dict[str, dict[str, Any]] = {}
    feedback: dict[str, dict[str, Any]] = {}

    for record, source in records:
        payload = record.payload if isinstance(record.payload, dict) else {}
        if payload.get("session_id") != session_id or payload.get("pattern_id") != pattern_id:
            continue

        if record.lane == RECOMMENDATION_LANE:
            layout_change = _layout_change_from_payload(payload)
            if layout_change is None:
                continue
            current = recommendations.get(layout_change.fingerprint)
            if current is None:
                recommendations[layout_change.fingerprint] = {
                    "layout_change": layout_change,
                    "last_seen_at": record.written_at,
                    "sources": {source},
                }
                continue
            current["sources"].add(source)
            if record.written_at > current["last_seen_at"]:
                current["layout_change"] = layout_change
                current["last_seen_at"] = record.written_at

        if record.lane == FEEDBACK_LANE:
            fingerprint = payload.get("proposal_fingerprint")
            decision = payload.get("decision")
            if not isinstance(fingerprint, str) or decision not in {"accept", "reject"}:
                continue
            current = feedback.get(fingerprint)
            if current is None:
                feedback[fingerprint] = {
                    "decision": decision,
                    "reason": payload.get("reason") if isinstance(payload.get("reason"), str) else None,
                    "last_seen_at": record.written_at,
                    "sources": {source},
                }
                continue
            current["sources"].add(source)
            if record.written_at > current["last_seen_at"]:
                current["decision"] = decision
                current["reason"] = payload.get("reason") if isinstance(payload.get("reason"), str) else None
                current["last_seen_at"] = record.written_at

    memories: list[PriorRecommendationMemory] = []
    for fingerprint, recommendation in recommendations.items():
        layout_change = recommendation["layout_change"]
        matched_feedback = feedback.get(fingerprint)
        decision = "unknown"
        reason = None
        sources = set(recommendation["sources"])
        last_seen_at = recommendation["last_seen_at"]
        if matched_feedback is not None:
            decision = matched_feedback["decision"]
            reason = matched_feedback["reason"]
            sources.update(matched_feedback["sources"])
            last_seen_at = max(last_seen_at, matched_feedback["last_seen_at"])
        memories.append(
            PriorRecommendationMemory(
                session_id=session_id,
                pattern_id=pattern_id,
                fingerprint=fingerprint,
                title=layout_change.title,
                target_id=layout_change.target_id,
                layout_change=layout_change,
                decision=decision,
                reason=reason,
                last_seen_at=last_seen_at,
                source=_prior_memory_source(sources),
            )
        )
    return sorted(memories, key=lambda memory: memory.last_seen_at, reverse=True)


def _layout_change_from_payload(payload: dict[str, Any]) -> LayoutChange | None:
    layout_change = payload.get("layout_change")
    if not isinstance(layout_change, dict):
        return None
    try:
        return LayoutChange.model_validate(layout_change)
    except ValueError:
        return None


def _prior_memory_source(sources: set[MemorySource]) -> Literal["mubit", "jsonl", "merged"]:
    if len(sources) > 1:
        return "merged"
    return next(iter(sources), "jsonl")


def _layout_changes_from_records(records: Iterable[MemoryRecord]) -> list[dict]:
    changes: list[dict] = []
    for record in records:
        layout_change = record.payload.get("layout_change")
        if isinstance(layout_change, dict):
            changes.append(layout_change)
    return changes


def _dedupe_layout_changes(items: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    changes: list[dict] = []
    for item in items:
        fingerprint = item.get("fingerprint") if isinstance(item, dict) else None
        key = fingerprint or json.dumps(item, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        changes.append(item)
    return changes


def _merge_memory_records(records: Iterable[MemoryRecord]) -> list[MemoryRecord]:
    merged: dict[tuple[Any, ...], MemoryRecord] = {}
    for record in records:
        key = _memory_record_key(record)
        existing = merged.get(key)
        if existing is None or (existing.fallback_only and not record.fallback_only):
            merged[key] = record
    return sorted(merged.values(), key=lambda record: record.written_at, reverse=True)


def _memory_record_key(record: MemoryRecord) -> tuple[Any, ...]:
    payload = record.payload if isinstance(record.payload, dict) else {}
    layout = payload.get("layout_change") if isinstance(payload.get("layout_change"), dict) else {}
    return (
        record.lane,
        payload.get("session_id"),
        payload.get("pattern_id"),
        payload.get("proposal_fingerprint") or layout.get("fingerprint"),
        payload.get("decision"),
        record.written_at.isoformat(),
    )


def _mubit_id_from_response(data: Any) -> str | None:
    for key in ("mubit_id", "memory_id", "record_id", "entry_id", "node_id", "id", "reference_id", "job_id"):
        value = _dig(data, key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
    return None


def _dig(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = _dig(value, key)
            if found is not None:
                return found
    if isinstance(data, list):
        for value in data:
            found = _dig(value, key)
            if found is not None:
                return found
    return None
