"""Local JSONL memory plus best-effort MuBit integration."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app import config
from app.logfire_setup import span
from app.schemas import MemoryIntent, MemoryLane, MemoryRecord


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
    """Write to local JSONL; MuBit is intentionally a best-effort later hook."""
    record = record.model_copy(update={"fallback_only": record.mubit_id is None})
    with span("memory.write.jsonl", lane=record.lane):
        config.MEMORY_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.MEMORY_JSONL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
    return record


async def recall_recommendations(session_id: str, pattern_id: str) -> list:
    """Return prior local recommendation payloads for this session and pattern."""
    with span("memory.recall.jsonl", session_id=session_id, pattern_id=pattern_id):
        if not config.MEMORY_JSONL_PATH.exists():
            return []

        hits = []
        with config.MEMORY_JSONL_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = MemoryRecord.model_validate_json(line)
                except ValueError:
                    continue
                payload = record.payload
                if (
                    record.lane == "location:demo:recommendations"
                    and payload.get("session_id") == session_id
                    and payload.get("pattern_id") == pattern_id
                ):
                    layout_change = payload.get("layout_change")
                    if isinstance(layout_change, dict):
                        hits.append(layout_change)
        return hits


async def list_memories(session_id: str | None = None) -> list[MemoryRecord]:
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
