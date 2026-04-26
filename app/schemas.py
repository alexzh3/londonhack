"""Pydantic schemas for the CafeTwin MVP evidence and API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that catches fixture typos instead of silently ignoring them."""

    model_config = ConfigDict(extra="forbid")


# ---------- Shared literals ----------

ObjectKind = Literal[
    "table",
    "chair",
    "counter",
    "pickup_shelf",
    "queue_marker",
    "menu_board",
    "plant",
    "barrier",
]

TrackRole = Literal["staff", "customer", "unknown"]

ZoneKind = Literal["counter", "queue", "pickup", "seating", "staff_path", "entrance"]

FixtureSource = Literal["vision", "manual", "fixture"]

SessionSourceKind = Literal["real", "ai_generated"]

KPIField = Literal[
    "staff_walk_distance_px",
    "staff_customer_crossings",
    "queue_obstruction_seconds",
    "congestion_score",
    "table_detour_score",
]

PatternType = Literal[
    "queue_crossing",
    "staff_detour",
    "table_blockage",
    "pickup_congestion",
]

Severity = Literal["low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]

SimulationAction = Literal[
    "move_table",
    "move_chair",
    "move_station",
    "change_queue_boundary",
]

MemoryLane = Literal[
    "location:demo:recommendations",
    "location:demo:feedback",
    "location:demo:kpi",
    "location:demo:inventory",
    "location:demo:patterns",
]

MemoryIntent = Literal["fact", "lesson", "feedback", "rule", "trace"]


# ---------- Vision-shaped fixture inputs ----------


class SceneObject(StrictModel):
    id: str
    kind: ObjectKind
    label: str
    bbox_xyxy: tuple[float, float, float, float]
    center_xy: tuple[float, float]
    size_xy: tuple[float, float]
    rotation_degrees: float = 0
    zone_id: str | None = None
    movable: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    source: FixtureSource = "fixture"


class ObjectInventory(StrictModel):
    session_id: str  # slug, e.g. "ai_cafe_a"
    run_id: UUID
    source_frame_idx: int = Field(ge=0)
    source_timestamp_s: float = Field(ge=0.0)
    objects: list[SceneObject] = Field(min_length=1)
    counts_by_kind: dict[ObjectKind, int]
    count_confidence: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class TrackPoint(StrictModel):
    track_id: int
    role: TrackRole = "unknown"
    timestamp_s: float = Field(ge=0.0)
    x: float
    y: float
    zone_id: str | None = None


class Zone(StrictModel):
    id: str
    name: str
    kind: ZoneKind
    polygon: list[tuple[float, float]] = Field(min_length=3)
    color_hex: str = "#64748b"
    source: Literal["agent_drafted", "manual", "fixture"] = "fixture"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# ---------- KPI ----------


class KPIReport(StrictModel):
    window_start_s: float = Field(ge=0.0)
    window_end_s: float = Field(ge=0.0)
    frames_sampled: int = Field(ge=1)
    staff_walk_distance_px: float = Field(ge=0.0)
    staff_customer_crossings: int = Field(ge=0)
    queue_length_peak: int = Field(ge=0)
    queue_obstruction_seconds: float = Field(ge=0.0)
    congestion_score: float = Field(ge=0.0, le=1.0)
    table_detour_score: float = Field(ge=0.0)
    session_id: str  # slug, e.g. "ai_cafe_a"
    run_id: UUID
    memory_id: str


# ---------- Pattern ----------


class EvidenceRef(StrictModel):
    memory_id: str
    lane: str
    summary: str
    kpi_field: KPIField | None = None


class OperationalPattern(StrictModel):
    id: str
    title: str
    summary: str
    pattern_type: PatternType
    evidence: list[EvidenceRef] = Field(min_length=1)
    severity: Severity
    affected_zones: list[str] = Field(min_length=1)


# ---------- Agent input bundle ----------


class CafeEvidencePack(StrictModel):
    """Single typed boundary between perception fixtures and agents."""

    session_id: str  # slug, e.g. "ai_cafe_a"
    run_id: UUID = Field(default_factory=uuid4)
    zones: list[Zone] = Field(min_length=1)
    object_inventory: ObjectInventory
    kpi_windows: list[KPIReport] = Field(min_length=1)
    pattern: OperationalPattern
    org_rules: list[str] = Field(default_factory=list)
    prior_recommendations: list["LayoutChange"] = Field(default_factory=list)
    # Populated by mubit.recall(session_id, pattern.id). Empty list if MuBit
    # unavailable or no prior runs. Recall is scoped to (session_id, pattern_id)
    # so cafes never see each other's recommendations.


# ---------- Agent output ----------


class LayoutSimulation(StrictModel):
    """Single-action MVP simulation spec.

    Renamed from ``SimulationSpec`` to avoid collision with the Tier-2 multi-op
    ``SimulationSpec`` defined in
    ``docs/superpowers/specs/2026-04-25-simcafe-ui-design.md`` §3.5.
    """

    action: SimulationAction
    target_id: str
    from_position: tuple[float, float]
    to_position: tuple[float, float]
    rotation_degrees: float = 0


class LayoutChange(StrictModel):
    """Pure agent output. Does NOT carry session_id / pattern_id; the
    orchestrator wraps it in :class:`RecommendationMemoryPayload` when
    persisting, so recall scoping stays out of the LLM's schema.
    """

    title: str
    rationale: str
    target_id: str
    simulation: LayoutSimulation
    evidence_ids: list[str] = Field(min_length=1)
    expected_kpi_delta: dict[KPIField, float] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    risk: RiskLevel
    fingerprint: str


# ---------- Memory ----------


class RecommendationMemoryPayload(StrictModel):
    """Stored as ``MemoryRecord.payload`` for lane=recommendations."""

    session_id: str
    pattern_id: str
    layout_change: LayoutChange


class FeedbackMemoryPayload(StrictModel):
    """Stored as ``MemoryRecord.payload`` for lane=feedback."""

    session_id: str
    pattern_id: str
    proposal_fingerprint: str
    decision: Literal["accept", "reject"]


class MemoryRecord(StrictModel):
    lane: MemoryLane
    intent: MemoryIntent
    payload: dict  # validated via the per-lane payload models above
    written_at: datetime
    mubit_id: str | None = None
    fallback_only: bool = False


# ---------- MVP API models ----------


class SessionManifest(StrictModel):
    slug: str
    label: str
    video_path: str
    source_kind: SessionSourceKind
    notes: str | None = None
    representative_frame_idx: int | None = None


StageName = Literal["evidence_pack", "optimization_agent", "memory_write"]


class StageTiming(StrictModel):
    name: StageName
    started_at: datetime
    ended_at: datetime
    status: Literal["done", "fallback"] = "done"


class FixtureStatus(StrictModel):
    filename: str
    exists: bool
    required: bool = True


class StateResponse(StrictModel):
    session_id: str  # slug, e.g. "ai_cafe_a"
    run_id: UUID
    fixtures: list[FixtureStatus]
    missing_required: list[str] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    object_inventory: ObjectInventory | None = None
    kpi_windows: list[KPIReport] = Field(default_factory=list)
    pattern: OperationalPattern | None = None
    assets: dict[str, str] = Field(default_factory=dict)


class RunResponse(StrictModel):
    stages: list[StageTiming]
    layout_change: LayoutChange
    memory_record: MemoryRecord | None = None
    prior_recommendation_count: int = 0
    used_fallback: bool = False
    logfire_trace_url: str | None = None


class RunRequest(StrictModel):
    session_id: str = "ai_cafe_a"


FeedbackDecision = Literal["accept", "reject"]


class FeedbackRequest(StrictModel):
    session_id: str
    pattern_id: str
    proposal_fingerprint: str
    decision: FeedbackDecision
    reason: str | None = None


class FeedbackResponse(StrictModel):
    decision: FeedbackDecision
    memory_record: MemoryRecord


class SessionsResponse(StrictModel):
    sessions: list[SessionManifest]


class MemoriesResponse(StrictModel):
    records: list[MemoryRecord]
    source: Literal["mubit", "jsonl", "merged"]


class LogfireURLResponse(StrictModel):
    url: str | None = None


# ---------- Tier 2 twin fixture hooks ----------


class TwinAsset(StrictModel):
    id: str
    kind: ObjectKind
    label: str
    position_xy: tuple[float, float]
    size_xy: tuple[float, float]
    rotation_degrees: float = 0
    zone_id: str | None = None
    movable: bool = True


class TwinLayout(StrictModel):
    id: str
    name: str
    source: Literal["observed", "recommended", "concept"]
    room_size_xy: tuple[float, float]
    assets: list[TwinAsset]
    zones: list[Zone] = Field(default_factory=list)
    applied_change_fingerprint: str | None = None
