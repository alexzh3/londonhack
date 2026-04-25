# CafeTwin / SimCafe — Engineering Plan

## Purpose

Detailed implementation plan for engineers. Aligns with `overview_plan.md`. Time horizon is **~18h**. Build philosophy is locked:

```
MVP    = real intelligence, mocked spectacle
Tier 1 = realer perception
Tier 2 = richer spectacle
```

This document specifies **MVP** in full and gives upgrade contracts for Tier 1 / Tier 2. Anything not in MVP is a non-goal until MVP is green.

## Visual Architecture — module-level, per tier

Three views of the same system. Each tier strictly adds to the previous one — boxes marked `(NEW)` are the additions vs the prior tier. Tiers are gated on the previous tier being green and stable.

Legend: `[REAL]` = live code at demo time. `[mock]` = fixture or prebaked artifact. `(NEW)` = added in this tier.

### MVP — real intelligence, mocked spectacle

```text
  ── PERCEPTION (mocked) ───────────  ── INTELLIGENCE (REAL) ──────────────  ── PRESENTATION (mocked shell) ──

  demo_data/                          app/                                   frontend/
  ┌───────────────────────────┐       ┌────────────────────────────────┐     ┌─────────────────────────────┐
  │ zones.json           [mock]│      │ evidence_pack.py        [REAL] │     │ Video panel  (plays mp4)    │
  │ object_inventory.json[mock]│      │   build() → CafeEvidencePack   │     │ KPI / object cards (Tremor) │
  │ kpi_windows.json     [mock]│ ───▶ │                                │     │ Flow canvas (3 nodes)       │
  │ pattern_fixture.json [mock]│      │ agents/optimization_agent.py   │     │ Recommendation card         │
  │ recommendation.cached[mock]│      │   Pydantic AI · Claude  [REAL] │ ──▶ │   + "Seen before" chip      │
  └────────────┬──────────────┘       │   ↳ retry-once + validate      │     │ Twin: PNG crossfade         │
               │                      │   ↳ fallback to .cached.json   │     │ Memories expander           │
  ┌────────────┴──────────────┐       │                                │     │ Logfire link (top bar)      │
  │ annotated_before.mp4 [mock]│ ───────────────────────────────────────────▶│                             │
  │ twin_observed.png    [mock]│ ───────────────────────────────────────────▶└─────────────▲───────────────┘
  │ twin_recommended.png [mock]│       │ memory.py               [REAL] │                   │
  └───────────────────────────┘       │   write_memory()   ┐           │                   │
                                      │   recall_prior_…() │           │                   │
                                      └────────┬───────────┴──┬────────┘                   │
                                               │              │                            │
                                               ▼              ▼                            │
                                      ┌──────────────┐  ┌──────────────────┐                │
                                      │ MuBit        │  │ mubit_fallback   │   /api/memories│
                                      │  (primary)   │  │  .jsonl          │ ───────────────┘
                                      └──────┬───────┘  └─────────┬────────┘
                                             │                    │
                                             └─────────┬──────────┘
                                                       ▼
                                            ┌──────────────────────┐
                                            │ Logfire   one trace  │
                                            │   (4 spans + recall) │
                                            └──────────────────────┘
                                            
  Routes used: GET /api/state, POST /api/run, POST /api/feedback, GET /api/memories, GET /api/logfire_url
```

### Tier 1 — realer perception (only if MVP green)

Perception layer becomes live. Intelligence and presentation layers untouched. **Adds 3 memory lanes and 3 Logfire spans.**

```text
  ── PERCEPTION (now REAL) ─────────  ── INTELLIGENCE (REAL, unchanged) ──   ── PRESENTATION (still mocked shell)

  ┌─────────────────────────────┐
  │ scripts/run_yolo_offline.py │     (same app/ as MVP)                    (same frontend/ as MVP)
  │   YOLO + ByteTrack    (NEW) │
  │   → tracks.cached.json[REAL]│ ─┐
  └─────────────────────────────┘  │
                                   │
  ┌─────────────────────────────┐  │  ┌────────────────────────────────┐
  │ scripts/render_annotated.py │  │  │ evidence_pack.py        [REAL] │
  │   ffmpeg overlays     (NEW) │  ├─▶│   build() → CafeEvidencePack   │
  │   → annotated_before.mp4    │  │  │                                │
  └─────────────────────────────┘  │  │ kpi_engine.py           (NEW)  │
                                   │  │   compute_window()      [REAL] │
  ┌─────────────────────────────┐  │  │   → list[KPIReport]            │
  │ zones.json (still hand-drawn,│ ─┤  │                                │
  │  no zone agent in any tier) │  │  │ agents/pattern_agent.py (NEW)  │
  └─────────────────────────────┘  │  │   Pydantic AI           [REAL] │
                                   │  │   → OperationalPattern         │
  ┌─────────────────────────────┐  │  │   (or deterministic builder)   │
  │ object_inventory.json [mock]│ ─┘  │                                │
  │  (manual review of YOLO)    │     │ agents/optimization_agent.py   │
  └─────────────────────────────┘     │   (unchanged)           [REAL] │
                                      └─────────────┬──────────────────┘
  pattern_fixture.json — REMOVED                    │
  (replaced by live PatternAgent)                   ▼
                                          ┌────────────────────┐
                                          │ memory.py  (NEW writes:
                                          │   kpi · inventory · pattern)
                                          │   on top of MVP writes
                                          └─────┬──────────┬───┘
                                                ▼          ▼
                                          MuBit (+ lanes:    jsonl
                                          location:demo:kpi
                                          location:demo:inventory
                                          location:demo:patterns)
                                                │
                                                ▼
                                         Logfire (NEW spans:
                                          kpi_engine.compute_window × N
                                          pattern_agent.run
                                          memory.write × 3)
```

### Tier 2 — richer spectacle (only if Tier 1 green)

Presentation layer upgrades. Backend still Tier 1. **Adds R3F twin, chat, scenario rail.**

```text
  ── PERCEPTION (Tier 1, REAL) ────   ── INTELLIGENCE (Tier 1, REAL) ──     ── PRESENTATION (richer) ──────────

  (unchanged from Tier 1)              (unchanged from Tier 1)               frontend/
                                                                             ┌──────────────────────────────┐
                                                                             │ Video panel             [REAL]│
                                                                             │ KPI / object cards      [REAL]│
                                                                             │ Flow canvas             [REAL]│
                                                                             │   per-span animation   (NEW) │
                                                                             │ Recommendation card     [REAL]│
                                                                             │                              │
                                                                             │ Twin panel              (NEW) │
                                                                             │   R3F box prefabs       [REAL]│
                                                                             │   reads twin_*.json          │
                                                                             │                              │
                                                                             │ Scenario rail           (NEW) │
                                                                             │   2–3 prebaked concepts [mock]│
                                                                             │                              │
                                                                             │ Chat panel              (NEW) │
                                                                             │   supported prompts only      │
                                                                             │   (regex/keyword routing)     │
                                                                             │                              │
                                                                             │ Memory timeline         (NEW) │
                                                                             │   rich UI with previews [REAL]│
                                                                             │                              │
                                                                             │ Optional: Hyper3D hero asset  │
                                                                             │   (one prebaked GLB)    [mock]│
                                                                             └──────────────────────────────┘

  Backend additions in Tier 2: optional GET /api/twin/{scenario}, /api/chat for routed prompts.
  No new sponsor integrations.
```

### Cross-tier component status

| Component | MVP | Tier 1 | Tier 2 |
|---|---|---|---|
| `zones.json` | hand-drawn | hand-drawn (no zone agent ever) | hand-drawn |
| `tracks.cached.json` | hand-authored or skipped | live YOLO+ByteTrack offline | same as Tier 1 |
| `kpi_windows.json` | precomputed numbers | live `kpi_engine` per request | same as Tier 1 |
| `pattern_fixture.json` | hand-authored | replaced by `PatternAgent` (or builder) | same as Tier 1 |
| `OptimizationAgent` | live Pydantic AI | unchanged | unchanged |
| MuBit lanes | recommendations, feedback | + kpi, inventory, patterns | same as Tier 1 |
| Twin panel | PNG crossfade | PNG crossfade | R3F box prefabs |
| Chat | none | none | supported-prompts-only |
| Scenario rail | none | none | 2–3 prebaked |
| Logfire span count | 4 + recall | ~7 (+ KPI + pattern + extra writes) | same as Tier 1 |
| Sponsor services | Anthropic, MuBit, Logfire | + (none) | + (none) |

### Sponsor services used at demo time (all tiers)

- **Anthropic Claude** — drives `OptimizationAgent` (and `PatternAgent` in Tier 1+). Fallback to `recommendation.cached.json` on failure.
- **MuBit** — `remember()` for memory writes; `recall()` for prior recommendations. Degrades silently when `MUBIT_API_KEY` unset.
- **Logfire** — auto-instruments Pydantic AI; manual spans for evidence pack build, KPI compute (Tier 1), validation, memory write, MuBit recall.
- **Render** — backend hosting (configured at deploy time, not visible in the runtime diagrams above).

## Sequence — one `/api/run` call

What happens end-to-end when the user clicks **Generate recommendation**. Every arrow is a real function call or network hop at demo time.

```mermaid
sequenceDiagram
    autonumber
    participant FE as React UI
    participant API as FastAPI /api/run
    participant EP as evidence_pack.py
    participant MEM as memory.py
    participant MB as MuBit
    participant OPT as OptimizationAgent
    participant AN as Anthropic Claude
    participant VAL as validate_layout_change
    participant FB as fallback.py
    participant JL as mubit_fallback.jsonl
    participant LF as Logfire

    FE->>API: POST /api/run (JSON)
    API->>LF: span(run) begin

    API->>EP: build(CafeEvidencePack)
    EP->>MEM: recall_prior_recommendations(pattern_id)
    MEM->>MB: query(lane=recommendations, filters)
    MB-->>MEM: hits (or [] if unavailable)
    MEM-->>EP: prior_recommendations
    EP-->>API: CafeEvidencePack
    API-->>API: record stage evidence_pack done

    API->>OPT: run(pack)
    OPT->>AN: chat.completions (typed, output_type=LayoutChange)
    AN-->>OPT: LayoutChange
    OPT->>VAL: validate_layout_change(change, pack)
    alt validation passes
        VAL-->>OPT: ok
    else fails once
        OPT->>AN: retry with stricter prompt
        AN-->>OPT: LayoutChange v2
        OPT->>VAL: validate v2
        alt still fails
            OPT->>FB: load_fallback_recommendation()
            FB-->>OPT: cached LayoutChange
        end
    end
    OPT-->>API: LayoutChange, used_fallback
    API-->>API: record recommendation <LayoutChange>
    API-->>API: record stage optimization_agent done

    API->>MEM: write_memory(lesson, layout_change)
    MEM->>MB: remember()
    MB-->>MEM: mubit_id (or error → fallback_only=True)
    MEM->>JL: append jsonl line
    MEM-->>API: MemoryRecord
    API-->>API: record stage memory_write done

    API->>LF: span(run) end
    API-->>FE: 200 {stages, layout_change, memory_record}

    Note over FE,LF: Later: user clicks Accept/Reject<br/>→ POST /api/feedback → memory.write again
```

### Mapping: sequence steps → Logfire spans

| Steps in diagram | Logfire span |
|---|---|
| 4–7 (`build` + `recall_prior_recommendations`) | `evidence_pack.build` → child `mubit.recall` |
| 9–17 (`run` through `validate` + retry + fallback) | `optimization_agent.run` (auto) + `layout_change.validate` |
| 20–23 (write MuBit + jsonl) | `memory.write` → children `memory.write.mubit`, `memory.write.jsonl` |

### Frontend stage timestamps → flow canvas nodes

| Stage `name` value | Flow canvas node | What lights up |
|---|---|---|
| `evidence_pack` | Node 1 | From start of build until pack returned (covers MuBit recall) |
| `optimization_agent` | Node 2 | From agent start until the recommendation is recorded in the response (covers retry + fallback) |
| `memory_write` | Node 3 | From memory write start until final `done` event |

The `validate` step has no dedicated flow node — it's folded into the `optimization_agent` node so the UI stays three nodes wide. Logfire still shows it as a distinct span for engineers.

## Demo loop (MVP)

```
fixtures (loaded once)
  ↓
build CafeEvidencePack  (typed Pydantic input bundle)
  ↓
OptimizationAgent       (Pydantic AI, live)
  ↓
LayoutChange            (typed, post-validated, fallback to cache on failure)
  ↓
memory.write            (MuBit primary + jsonl fallback always)
  ↓
UI shows: recommendation card, before/after twin crossfade, KPI deltas
  ↓
user feedback           (Accept / Reject) → memory.write
```

Single Logfire trace, four spans:

1. `evidence_pack.build`
2. `optimization_agent.run`
3. `layout_change.validate`
4. `memory.write`

Plus `feedback.write` when user clicks Accept/Reject.

## File layout

```
app/
  schemas.py                    # all Pydantic models (see §Schemas)
  evidence_pack.py              # build CafeEvidencePack from demo_data/
  agents/
    optimization_agent.py       # the one live Pydantic AI agent
    evidence_summarizer.py      # OPTIONAL second live agent (see §Optional second agent)
  memory.py                     # local jsonl writer + MuBit best-effort wrapper
  logfire_setup.py              # init + span helpers
  api/
    main.py                     # FastAPI app
    routes.py                   # /api/run, /api/feedback, /api/state, /api/logfire_url
    sse.py                      # stage event streaming
  fallback.py                   # load recommendation.cached.json if agent fails
  config.py                     # env vars, demo_data path
demo_data/                      # see §Demo data contract
frontend/                       # Vite+React shell — see overview_plan.md §UI
scripts/
  build_fixtures.py             # one-shot: render annotated_before.mp4 + twin PNGs
  run_yolo_offline.py           # Tier 1 hook: produce real tracks.cached.json
```

Current scaffold exists for these boundaries: `pyproject.toml`, `app/`,
`app/api/`, `app/agents/`, `demo_data/`, `frontend/`, `scripts/`, and
`docs/architecture/`. The next implementation step is filling `app/schemas.py`
and `demo_data/*.json`.

## Demo data contract (MVP fixtures)

All hand-authored or precomputed offline. Loaded once at startup.

| File | Schema | Notes |
|---|---|---|
| `demo_data/source_video.mp4` | binary | The original overhead clip. Not loaded by code; available for the pitch ("here's the raw input"). |
| `demo_data/annotated_before.mp4` | binary | Plays in the observed video panel. Generated by `scripts/build_fixtures.py` (Tier 1: real ffmpeg+YOLO; MVP: can be hand-edited). |
| `demo_data/tracks.cached.json` | `list[TrackPoint]` | Used by Tier 1 KPI engine. In MVP: shipped for credibility ("here's the data") but not consumed at runtime. |
| `demo_data/zones.json` | `list[Zone]` | Hand-drawn polygons. Loaded into `CafeEvidencePack`. |
| `demo_data/object_inventory.json` | `ObjectInventory` | Hand-authored counts + xy. Loaded into `CafeEvidencePack`. |
| `demo_data/kpi_windows.json` | `list[KPIReport]` | Precomputed in MVP, reflecting plausible numbers. Loaded into `CafeEvidencePack`. |
| `demo_data/pattern_fixture.json` | `OperationalPattern` | One pattern with `evidence_ids` (e.g. `mem_kpi_w1`, `mem_kpi_w2`, `mem_kpi_w3`). The agent **must** cite these IDs. |
| `demo_data/recommendation.cached.json` | `LayoutChange` | Deterministic fallback used if the agent retries fail validation. |
| `demo_data/twin_observed.png` | image | Used by MVP twin panel. |
| `demo_data/twin_recommended.png` | image | Used by MVP twin panel. |
| `demo_data/twin_observed.json` | `TwinLayout` (Tier 2 schema) | Shipped for Tier 2 R3F. Not used in MVP. |
| `demo_data/twin_recommended.json` | `TwinLayout` (Tier 2 schema) | Shipped for Tier 2 R3F. Not used in MVP. |
| `demo_data/mubit_fallback.jsonl` | append-only | Created at runtime. Source of truth for the "Memories" expander. |

**Failure rule:** if any required fixture is missing at startup, `/api/state` returns a clear error with the missing filename. Don't paper over it.

## Schemas

```python
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ---------- Vision-shaped (used as fixture inputs in MVP) ----------

ObjectKind = Literal[
    "table", "chair", "counter", "pickup_shelf",
    "queue_marker", "menu_board", "plant", "barrier",
]


class SceneObject(BaseModel):
    id: str
    kind: ObjectKind
    label: str
    bbox_xyxy: tuple[float, float, float, float]
    center_xy: tuple[float, float]
    size_xy: tuple[float, float]
    rotation_degrees: float = 0
    zone_id: str | None = None
    movable: bool = True
    confidence: float
    source: Literal["vision", "manual", "fixture"] = "fixture"


class ObjectInventory(BaseModel):
    session_id: UUID
    run_id: UUID
    source_frame_idx: int
    source_timestamp_s: float
    objects: list[SceneObject]
    counts_by_kind: dict[ObjectKind, int]
    count_confidence: float
    notes: list[str] = Field(default_factory=list)


class TrackPoint(BaseModel):
    track_id: int
    role: Literal["staff", "customer", "unknown"] = "unknown"
    timestamp_s: float
    x: float
    y: float
    zone_id: str | None = None


class Zone(BaseModel):
    id: str
    name: str
    kind: Literal["counter", "queue", "pickup", "seating", "staff_path", "entrance"]
    polygon: list[tuple[float, float]]
    color_hex: str = "#64748b"
    source: Literal["agent_drafted", "manual", "fixture"] = "fixture"
    confidence: float | None = None


# ---------- KPI ----------

KPIField = Literal[
    "staff_walk_distance_px",
    "staff_customer_crossings",
    "queue_obstruction_seconds",
    "congestion_score",
    "table_detour_score",
]


class KPIReport(BaseModel):
    window_start_s: float
    window_end_s: float
    frames_sampled: int
    staff_walk_distance_px: float
    staff_customer_crossings: int
    queue_length_peak: int
    queue_obstruction_seconds: float
    congestion_score: float
    table_detour_score: float
    session_id: UUID
    run_id: UUID
    memory_id: str  # e.g. "mem_kpi_w1"; cited by patterns


# ---------- Pattern (fixture in MVP, agent in Tier 1) ----------

class EvidenceRef(BaseModel):
    memory_id: str
    lane: str
    summary: str
    kpi_field: KPIField | None = None


class OperationalPattern(BaseModel):
    id: str  # e.g. "pat_queue_crossing_001"
    title: str
    summary: str
    pattern_type: Literal[
        "queue_crossing", "staff_detour", "table_blockage", "pickup_congestion"
    ]
    evidence: list[EvidenceRef] = Field(min_length=1)
    severity: Literal["low", "medium", "high"]
    affected_zones: list[str]


# ---------- Agent input bundle ----------

class CafeEvidencePack(BaseModel):
    """Single typed input to OptimizationAgent.
    Built by `evidence_pack.build()` from demo_data fixtures (MVP)
    or live KPI engine output (Tier 1).
    """
    session_id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(default_factory=uuid4)
    zones: list[Zone]
    object_inventory: ObjectInventory
    kpi_windows: list[KPIReport]
    pattern: OperationalPattern  # MVP: the fixture pattern. Tier 1: PatternAgent output.
    org_rules: list[str] = Field(default_factory=list)
    prior_recommendations: list["LayoutChange"] = Field(default_factory=list)
    # Populated by mubit.recall() on the pattern fingerprint. Empty list if
    # MuBit unavailable or no prior runs — agent handles both cases.


# ---------- Agent output ----------

class SimulationSpec(BaseModel):
    action: Literal["move_table", "move_chair", "move_station", "change_queue_boundary"]
    target_id: str
    from_position: tuple[float, float]
    to_position: tuple[float, float]
    rotation_degrees: float = 0


class LayoutChange(BaseModel):
    title: str
    rationale: str
    target_id: str
    simulation: SimulationSpec
    evidence_ids: list[str] = Field(min_length=1)  # MUST be subset of pattern.evidence ids
    expected_kpi_delta: dict[KPIField, float] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    risk: Literal["low", "medium", "high"]
    fingerprint: str


# ---------- Memory write payloads ----------

class MemoryRecord(BaseModel):
    lane: Literal[
        "location:demo:recommendations",
        "location:demo:feedback",
        # Tier 1 lanes:
        "location:demo:kpi",
        "location:demo:inventory",
        "location:demo:patterns",
    ]
    intent: Literal["fact", "lesson", "feedback", "rule", "trace"]
    payload: dict
    written_at: datetime
    mubit_id: str | None = None
    fallback_only: bool = False
```

Notes:

- `LayoutChange.evidence_ids` is a flat `list[str]` rather than `list[EvidenceRef]` to make the Pydantic AI prompt simpler and the post-validation trivial.
- `expected_kpi_delta` keys are typed via `KPIField` literal, so the agent cannot hallucinate field names.
- `confidence` is bounded `[0,1]` by `Field`.

## OptimizationAgent (live, MVP)

**Input:** `CafeEvidencePack`. **Output:** `LayoutChange`.

### Pydantic AI setup

```python
from pydantic_ai import Agent
from app.schemas import CafeEvidencePack, LayoutChange

optimization_agent: Agent[CafeEvidencePack, LayoutChange] = Agent(
    "anthropic:claude-sonnet-4-latest",  # exact model id per Pydantic AI docs
    output_type=LayoutChange,
    system_prompt=OPTIMIZATION_SYSTEM_PROMPT,
)
```

### System prompt (contract)

```text
You are a cafe layout optimization agent. You receive a CafeEvidencePack
describing zones, an object inventory, KPI windows, and one OperationalPattern
identifying a spatial bottleneck. Your job is to emit a single typed
LayoutChange that addresses the pattern.

HARD RULES — you will be rejected if you violate any of these:

1. evidence_ids MUST be a non-empty subset of the memory_ids appearing in
   the input pattern.evidence[*].memory_id. Do not invent IDs.
2. expected_kpi_delta MUST contain at least one key from this set:
   {staff_walk_distance_px, staff_customer_crossings,
    queue_obstruction_seconds, congestion_score, table_detour_score}.
   Values are signed floats representing expected change (negative = improvement
   for distance/crossings/obstruction/congestion; lower table_detour_score is also
   better).
3. simulation.target_id MUST refer to an existing object in
   object_inventory.objects[*].id, or a zone id from zones[*].id for
   change_queue_boundary actions.
4. simulation.from_position MUST equal the current center_xy of that object
   (within 1px tolerance) when target is movable furniture.
5. confidence MUST be in [0.0, 1.0] and risk MUST be one of {low, medium, high}.
6. fingerprint MUST be a short stable hash-like string of (target_id, action,
   to_position) so duplicates can be detected.

Prefer ONE high-confidence move. Keep rationale to 2-3 sentences citing the
specific pattern. Do not propose multiple changes.

If prior_recommendations is non-empty, briefly acknowledge in the rationale
that this pattern has been seen before (e.g. "Repeats a prior recommendation
that was accepted"). If empty, do not mention prior memory.
```

### Post-validation + fallback

After the agent returns, we run a second-pass validator before returning to the UI:

```python
def validate_layout_change(change: LayoutChange, pack: CafeEvidencePack) -> bool:
    pattern_ids = {ref.memory_id for ref in pack.pattern.evidence}
    if not change.evidence_ids:
        return False
    if not set(change.evidence_ids).issubset(pattern_ids):
        return False
    if not change.expected_kpi_delta:
        return False
    object_ids = {o.id for o in pack.object_inventory.objects}
    zone_ids = {z.id for z in pack.zones}
    if change.simulation.target_id not in object_ids | zone_ids:
        return False
    return True


async def run_optimization(pack: CafeEvidencePack) -> tuple[LayoutChange, bool]:
    """Returns (layout_change, used_fallback)."""
    with logfire.span("optimization_agent.run"):
        try:
            result = await optimization_agent.run(pack)
            change = result.output
        except Exception as e:
            logfire.warn("optimization_agent failed", error=str(e))
            return load_fallback_recommendation(), True

    with logfire.span("layout_change.validate"):
        if validate_layout_change(change, pack):
            return change, False
        # Retry once with a stricter reminder
        retry = await optimization_agent.run(
            pack,
            message_history=[...],  # include the original failure as a user message
        )
        if validate_layout_change(retry.output, pack):
            return retry.output, False
        logfire.warn("optimization_agent validation failed twice, using fallback")
        return load_fallback_recommendation(), True
```

`load_fallback_recommendation()` reads `demo_data/recommendation.cached.json` and returns it parsed as `LayoutChange`.

## Optional second agent (recommended)

To honestly say "agentic workflow" (plural), add `EvidenceSummarizerAgent`:

**Input:** `CafeEvidencePack`. **Output:** a small typed model:

```python
class EvidenceSummary(BaseModel):
    headline: str  # one sentence
    bullets: list[str] = Field(min_length=2, max_length=4)  # 2-4 bullets citing KPIs
```

Run it before `OptimizationAgent`. Show its output above the recommendation card. Cost: ~30 minutes of code, one extra Logfire span (`evidence_summarizer.run`), one extra `MemoryRecord`. Two real Pydantic AI agents in a chain.

If time-constrained, skip and frame the demo as "typed Pydantic AI agent with structured output and traced reasoning" (singular). Both framings are honest.

## Memory layer

MuBit is the **primary** memory store in MVP. The local jsonl is a hot fallback that is always written so a MuBit outage at demo time degrades gracefully (no demo break). The UI reads from MuBit when available, jsonl when not.

```python
# app/memory.py
import json
from pathlib import Path
from datetime import datetime, timezone

JSONL_PATH = Path("demo_data/mubit_fallback.jsonl")


async def write_memory(record: MemoryRecord) -> MemoryRecord:
    record.written_at = datetime.now(timezone.utc)

    # 1) MuBit (primary)
    with logfire.span("memory.write.mubit"):
        try:
            record.mubit_id = await _mubit_remember(record)
        except Exception as e:
            logfire.warn("mubit write failed; jsonl-only", error=str(e))
            record.fallback_only = True

    # 2) Local jsonl (always, as fallback + audit log)
    with logfire.span("memory.write.jsonl"):
        with JSONL_PATH.open("a") as f:
            f.write(record.model_dump_json() + "\n")

    return record


async def recall_prior_recommendations(
    fingerprint: str | None = None,
    pattern_id: str | None = None,
    limit: int = 3,
) -> list[LayoutChange]:
    """Recall prior LayoutChange recommendations for the same pattern or
    layout fingerprint. Used by evidence_pack.build() to give the agent
    operational memory.

    Returns [] if MuBit unavailable, key unset, or no matches.
    """
    with logfire.span("mubit.recall"):
        if not _mubit_available():
            return []
        try:
            hits = await _mubit_query(
                lane="location:demo:recommendations",
                filters={"fingerprint": fingerprint} if fingerprint else {"pattern_id": pattern_id},
                limit=limit,
            )
            return [LayoutChange.model_validate(h.payload) for h in hits]
        except Exception as e:
            logfire.warn("mubit recall failed; returning empty", error=str(e))
            return []
```

If `MUBIT_API_KEY` is unset, both `_mubit_remember` and `_mubit_query` no-op cleanly: writes still hit jsonl, recalls return `[]`, demo still works. This is what `MemoryRecord.fallback_only` flags.

### MVP writes

- After successful recommendation: 1 record on lane `location:demo:recommendations`, intent `lesson`. Payload includes the `LayoutChange` JSON and its `fingerprint`.
- After Accept/Reject feedback: 1 record on lane `location:demo:feedback`, intent `feedback`. Payload includes the proposal `fingerprint` and the decision.

### MVP reads

- `evidence_pack.build()` calls `recall_prior_recommendations(pattern_id=pack.pattern.id)` before building the pack and stores results in `pack.prior_recommendations`.
- `GET /api/memories` queries MuBit (lane: `location:demo:recommendations` + `location:demo:feedback`) and merges with jsonl entries, dedup by `mubit_id`. If MuBit unavailable, returns jsonl only.

### UI surface

- Memories expander row shows `[mubit_id]` chip when present (e.g. `mem_a1b2c3`), or `[local]` when fallback-only.
- Recommendation card shows a "Seen before" chip with count when `prior_recommendations` is non-empty.

### Tier 1 adds

KPI summary, object inventory, and pattern writes on their own lanes (see `MemoryRecord.lane` literal). Recall is also extended to `location:demo:patterns` for pattern history.

## FastAPI routes

```python
# app/api/routes.py

@router.get("/api/state")
async def get_state() -> StateResponse:
    """Returns precomputed KPIs, object counts, baseline twin URL."""

@router.post("/api/run")
async def run() -> RunResponse:
    """JSON response:
        {
          "stages": [
            {"name": "evidence_pack", "started_at": "...", "ended_at": "..."},
            {"name": "optimization_agent", "started_at": "...", "ended_at": "..."},
            {"name": "memory_write", "started_at": "...", "ended_at": "..."}
          ],
          "layout_change": <LayoutChange JSON>,
          "memory_record": <MemoryRecord JSON>,
          "used_fallback": false
        }
    """

@router.post("/api/feedback")
async def feedback(body: FeedbackRequest) -> FeedbackResponse:
    """Writes feedback memory. body has decision (accept/reject) and proposal_id."""

@router.get("/api/logfire_url")
async def logfire_url() -> dict:
    """Returns the current trace URL for the top-bar link."""

@router.get("/api/memories")
async def memories() -> list[MemoryRecord]:
    """Reads mubit_fallback.jsonl and returns parsed records."""
```

SSE is optional polish, not MVP. If we add it later, it should preserve the same
stage names and response shapes so the frontend can replay either live or after
the request completes.

## Logfire

```python
# app/logfire_setup.py
import logfire
logfire.configure(service_name="cafetwin-mvp")
logfire.instrument_pydantic_ai()  # auto-spans agent runs
```

Span hierarchy for one `/api/run` call:

```
run (root)
├── evidence_pack.build
│   └── mubit.recall                  (returns prior_recommendations)
├── optimization_agent.run            (auto-instrumented by Pydantic AI)
├── layout_change.validate
└── memory.write
    ├── memory.write.mubit
    └── memory.write.jsonl
```

The Logfire URL exposed at `/api/logfire_url` should be the URL of the most recent `run` span. Cache it in process state when the run finishes.

## Frontend contract

Frontend is described in `overview_plan.md` §UI. Key API touchpoints:

| User action | Frontend call |
|---|---|
| Page load | `GET /api/state` → populate KPI/object cards, set baseline twin image |
| Click "Generate recommendation" | `POST /api/run`; replay returned stage timestamps in flow canvas; render returned recommendation card |
| Click "Apply" | Frontend-only: crossfade twin PNG, animate KPI delta cards from `expected_kpi_delta` |
| Click "Accept" / "Reject" | `POST /api/feedback {decision, fingerprint}` |
| Click Logfire link | `GET /api/logfire_url` then `window.open` |
| Open "Memories" expander | `GET /api/memories` |

## KPI engine (Tier 1, NOT MVP)

Pre-compute in MVP, ship live in Tier 1. Implementation reference (lifted from old plan):

- `staff_walk_distance_px`: Σ Euclidean distance between consecutive staff TrackPoints.
- `staff_customer_crossings`: count of (staff segment) × (customer segment) intersections per window.
- `queue_length_peak`/`avg`: count of customer points inside `queue` zone per frame.
- `queue_obstruction_seconds`: seconds where a staff segment enters queue zone or a table mask overlaps queue corridor.
- `congestion_score`: normalized density in counter+queue+pickup region (0..1).
- `table_detour_score`: actual staff path length / straight-line counter→seating distance.

Window size: 20s. Run on cached `tracks.cached.json` + `zones.json`. Output overwrites `kpi_windows.json` (or returns from API directly).

## Vision (Tier 1, NOT MVP)

Run offline once, not at demo time. Script: `scripts/run_yolo_offline.py`:

```python
from ultralytics import YOLO
import cv2, json

model = YOLO("yolo11n.pt")
cap = cv2.VideoCapture("demo_data/source_video.mp4")
points = []
frame_idx = 0
while cap.isOpened():
    ok, frame = cap.read()
    if not ok: break
    if frame_idx % 15 == 0:  # ~2 fps from 30 fps source
        results = model.track(frame, tracker="bytetrack.yaml", persist=True)
        # Convert to TrackPoint records, append to `points`
        ...
    frame_idx += 1

# Heuristic role assignment: staff if >=60% of points in counter zone in first 10s
# Save to demo_data/tracks.cached.json
```

Plus a separate `scripts/render_annotated.py` that uses ffmpeg + the cached detections to produce `annotated_before.mp4`. Both run offline.

## Tier 2 hooks (NOT MVP)

The MVP explicitly ships `twin_observed.json` and `twin_recommended.json` so Tier 2 can be added without backend changes. Schema (use as-is in Tier 2):

```python
class TwinAsset(BaseModel):
    id: str
    kind: ObjectKind
    position: tuple[float, float]
    rotation_degrees: float = 0
    size_xy: tuple[float, float]


class TwinLayout(BaseModel):
    walls: list[tuple[float, float]]  # polygon
    floor_image: str | None  # optional reference texture path
    assets: list[TwinAsset]
    zone_overlays: list[Zone]
    track_trails: list[list[tuple[float, float]]] = Field(default_factory=list)
```

R3F renders this with box prefabs. A Tier 2 endpoint `/api/twin/{scenario}` returns the parsed layout. Twin panel can A/B between current MVP `<img>` rendering and R3F rendering behind a feature flag.

## Risk controls

| Risk | Mitigation |
|---|---|
| Pydantic AI agent returns invalid `LayoutChange` | Post-validate, retry once with stricter prompt, fall back to `recommendation.cached.json` |
| Anthropic API down/slow at demo time | Same fallback; keep the cached recommendation visually identical to a real one |
| MuBit unavailable | Writes still hit jsonl; recall returns `[]`; UI falls back to jsonl read; "Seen before" chip simply doesn't render |
| Logfire unavailable | Spans no-op gracefully; top-bar link disables if `/api/logfire_url` errors |
| Flow animation polish eats too much time | Return stages from `/api/run`; render static complete states client-side |
| Frontend twin panel buggy | PNG `<img>` crossfade has zero geometry; if even that breaks, single static "after" image is acceptable |
| Demo wifi flaky | Render-deployed backend has fallback recording (full screen capture of working flow) |

## Acceptance checks (MVP)

- [ ] `GET /api/state` returns plausible KPI numbers and object counts.
- [ ] `POST /api/run` returns 3 stage timestamps and a `layout_change` payload.
- [ ] `LayoutChange.evidence_ids` is non-empty and ⊆ pattern fixture's evidence IDs.
- [ ] `LayoutChange.expected_kpi_delta` has ≥ 1 entry, all keys are valid `KPIField`s.
- [ ] After clicking Generate, the recommendation card renders with rationale, evidence, deltas, confidence.
- [ ] Clicking Apply crossfades the twin and animates KPI deltas.
- [ ] Clicking Accept/Reject writes a `MemoryRecord` to MuBit AND to `mubit_fallback.jsonl`.
- [ ] When MuBit is up: Memories expander rows show `mubit_id` chips; `GET /api/memories` returns merged MuBit+jsonl data.
- [ ] When MuBit is up and a prior recommendation with the same `pattern_id` exists, the recommendation card shows a "Seen before" chip and the agent's rationale acknowledges it.
- [ ] Logfire trace shows the full span tree (`evidence_pack.build` → `mubit.recall`, `optimization_agent.run`, `layout_change.validate`, `memory.write` → `memory.write.mubit` + `memory.write.jsonl`).
- [ ] If `ANTHROPIC_API_KEY` is unset or invalid, the fallback path still produces a valid recommendation card.
- [ ] If `MUBIT_API_KEY` is unset, jsonl-only mode works end-to-end without errors and the UI degrades silently (no `mubit_id` chips, no "Seen before" chip).

## Pitch copy (best-case demo recommendation)

```
Move table cluster B 0.8m left.

Rationale:
Cluster B forces the staff runner across the queue zone every trip,
producing 18 crossings across three 20-second KPI windows and obstructing the queue for 41s.

Evidence: mem_kpi_w1, mem_kpi_w2, mem_kpi_w3

Expected impact:
- staff_customer_crossings: -38%
- queue_obstruction_seconds: -31%
- staff_walk_distance_px: -14%

Risk: low. Maintains 1.2m walkway clearance.
```

## Engineering defaults

- Cafe, not restaurant.
- One seeded video, no live camera.
- Fixture-backed perception; live agent reasoning.
- MuBit is the primary memory store; jsonl is a hot fallback always written in parallel.
- One Pydantic AI agent live (optionally two). All other agents are non-goals until Tier 1.
- 3D twin is a PNG crossfade. R3F is non-goal until Tier 2.
- Evidence chain is mandatory; recommendation must cite real fixture IDs.
- Logfire trace is mandatory.
- If anything is at risk past hour 14, cut it.
