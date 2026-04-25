# SimCafe — UI/UX Design Spec

**Date:** 2026-04-25
**Project:** CafeTwin / SimCafe (London 24h hackathon)
**Status:** Approved design, pre-implementation
**Repo:** `/Users/samydev/londonhack/londonhack/`

## 1. Pitch

**SimCafe** turns an overhead cafe video into an editable, gamified 3D digital twin. A natural-language chat panel drives a Pydantic AI agent stack that proposes, simulates, and compares cafe layout scenarios. Users can ask "what if we 10x the cafe?" or "make it Brooklyn-style with communal seating" and watch the simulation morph in real time.

> POS tells you what sold. SimCafe shows why throughput stalled — and lets you redesign it by talking to it.

## 2. Product surface — three linked canvases

The UI is a single page with three coupled canvases plus a chat-driven command surface, all fed by one shared state store.

### 2.1 Layout (desktop, 1440+)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ TOP BAR: logo · video upload · session/run id · Logfire trace link      │
├──────────────┬─────────────────────────────────────┬────────────────────┤
│              │                                     │                    │
│ AGENT FLOW   │   3D SIMULATION CANVAS              │  💬 SCENARIO CHAT  │
│ (React Flow) │   (R3F · isometric tycoon)          │  (Vercel AI SDK)   │
│              │                                     │                    │
│ pipeline     │   active scenario rendered here     │  per-scenario      │
│ nodes glow   │   morphs / split-screen compare     │  thread; tool-call │
│ as data      │                                     │  cards, evidence   │
│ flows        │                                     │  chips             │
│              │                                     │                    │
│ ─────────    │                                     │                    │
│ CONTROLS     │                                     │                    │
│ (Tweakpane)  │                                     │                    │
│ sliders for  │                                     │                    │
│ seats, staff,│                                     │                    │
│ machines     │                                     │                    │
│              │                                     │  ───────────────   │
│ KPI CARDS    │                                     │  [prompt input ↵]  │
│ (Tremor)     │                                     │  📎 image attach   │
├──────────────┴─────────────────────────────────────┴────────────────────┤
│ 🌿 SCENARIO RAIL — [● baseline][○ 10x][○ Brooklyn][○ Tokyo][+]          │
│ click to switch · long-press 2 chips → split-screen compare             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Empty state (before video uploaded)

- 3D canvas shows a placeholder demo cafe (stock prefab arrangement) with a translucent overlay: *"Drop an overhead cafe video to start"*.
- Flow canvas shows nodes in dim/idle state.
- Chat shows a welcome message: *"Hi — upload a video and I'll reconstruct it as an editable 3D twin. Then ask me anything: 'what if we add 4 seats?', 'how do we shorten the queue?', 'make it Brooklyn-style.'"*.
- Scenario rail shows only the placeholder baseline.

### 2.3 Canvas roles

| Canvas | Purpose | Library |
|---|---|---|
| **Agent Flow** (left) | Visualize Pydantic AI pipeline. Nodes light up as the backend runs each stage. Edges animate when data flows. Click a node → opens right-side drawer with logs + Logfire span link. | `@xyflow/react` |
| **3D Simulation** (center) | The active scenario. Isometric tycoon camera. Drag furniture (raycaster + snap-to-grid), bloom + selection outlines. | `@react-three/fiber` + `drei` + `postprocessing` |
| **Scenario Chat** (right) | Per-scenario chat thread (switching chips switches threads). Streams responses, renders tool-call cards, evidence chips, recommendation cards. | `ai` (Vercel AI SDK) + `@ai-sdk/react` |
| **Controls + KPIs** (left lower) | Direct manipulation: sliders for seats/baristas/machines. Live KPI cards reflect current scenario. | Tweakpane + Tremor |
| **Scenario Rail** (bottom) | Tree of all scenarios. Switch, compare, fork. Horizontal scroll; collapses to grouped pills if >12. | Custom; chips + popover |

## 3. Scenarios — the central abstraction

### 3.1 Scenario tree

Every chat what-if forks a new branch from the current scenario. Backend Postgres is **source of truth**; frontend IndexedDB is an offline cache. On load the frontend hydrates from `GET /api/scenarios?session_id=...`. Last-write-wins on reconnect (not a 24h concern — single user).

```
baseline (reconstructed from real video)
├── "10x cafe size"
├── "Brooklyn-style with communal seating"
│   └── "...and add 2 more baristas"
├── "Move counter to back wall"
└── "Tokyo minimalist redesign"
```

### 3.2 Scenario states

| Status | Meaning | Where it appears |
|---|---|---|
| `baseline` | The real-video reconstruction. KPIs come from actual tracks. | Always pinned first chip |
| `pending` | Agent-emitted proposal. Awaiting user "Apply". | Dotted-outline chip + recommendation card in chat |
| `active` | Promoted by user (Apply) or created from chat what-if. KPIs from simulation. | Solid chip |
| `archived` | Soft-deleted. | Hidden by default; surfaced via "Show archived" |

A `LayoutChange` from the optimization agent creates a `pending` scenario. Clicking **Apply** in the recommendation card promotes it to `active` (and switches to it).

### 3.3 KPI source of truth

| Scenario type | KPI source |
|---|---|
| `baseline` | Real video tracks via the existing CafeTwin vision/KPI pipeline. **Authoritative ground truth.** |
| `active` / `pending` (non-baseline) | Simulated KPIs computed deterministically from the modified layout (no live agent walking in 24h scope — see §11 cuts). KPIs are estimates from a path-graph approximation: rebuild walkable graph after layout change, recompute walking distance / crossings / queue obstruction estimates against the same person tracks projected onto the new layout. |

This distinction is **explicit in the UI**: baseline KPI cards are styled "from video" with a camera icon; scenario KPI cards are styled "estimated" with a sparkles icon.

### 3.4 Chat thread per scenario

Each scenario has its own chat thread. Switching the active scenario chip switches the visible chat history. Forking a scenario forks the chat (child thread starts with a synthetic system message: *"Forked from <parent name>"*). The baseline thread is the only thread that exists on first load.

### 3.5 SimulationSpec — the LLM's DSL

The LLM never writes Three.js code. It emits a typed Pydantic `SimulationSpec` (a list of layout ops). The frontend deterministically renders from it. This is the safety boundary.

```python
class SimulationSpec(BaseModel):
    scenario_name: str
    parent_scenario_id: str | None = None
    ops: list[Op]

# Op is a discriminated union (Pydantic tag = "type"):
Op = (
    ScaleRoom              # type, factor: float
  | MoveAsset              # type, asset_id, to_xy: tuple[float, float], rotation_deg
  | AddAssets              # type, asset_kind, count, placement_strategy
  | RemoveAssets           # type, selector: AssetSelector
  | ReplaceAssets          # type, from_kind, to_kind
  | RestyleScene           # type, theme: Literal["brooklyn"|"tokyo_minimal"|"parisian"|...]
  | SetStaffing            # type, baristas: int, runners: int
  | SetEquipment           # type, espresso_machines: int, ovens: int, fridges: int
  | RedrawRoomShape        # type, polygon: list[tuple[float, float]]
  | RedistributeFurniture  # type, strategy: Literal["preserve_ratios"|"max_capacity"|"max_flow"]
  | GenerateHeroAsset      # type, prompt: str, target_position: tuple[float, float]
)

class AssetSelector(BaseModel):
    asset_kind: Literal["table", "chair", "counter", "machine", ...] | None = None
    asset_ids: list[str] | None = None
    fraction: float | None = None  # e.g. 0.5 → "half of"
```

Validated by Pydantic, deterministically applied by `SceneBuilder` (TypeScript). Reproducible: replay any scenario by re-applying ops to the baseline.

### 3.6 Scenario operations

| User intent | UI affordance | Backend |
|---|---|---|
| New scenario | Type "what if X" in chat | LLM emits `SimulationSpec`, `POST /api/scenarios` creates child node |
| Switch scenario | Click chip in rail | Frontend swaps active scenario; GSAP tweens furniture |
| Compare (2-way) | Long-press 2 chips | Split-screen dual `<Canvas>` with synced cameras + KPI diff. **2-way only for 24h** |
| Fork | Long-press chip → "Branch" | Creates child of selected (not just current) |
| Promote pending | Click "Apply" on recommendation card | `POST /api/scenarios/{id}/promote` — status pending → active, switches to it |

## 4. Chat as orchestration

Chat is not a sidebar — it's the **command layer**. Pydantic AI agents on the backend expose tools the LLM can call. Each tool-call renders an inline collapsible card in the chat thread.

### 4.1 Tools available to the LLM

```
analyze_video(video_id)            → triggers vision pipeline, lights flow nodes
get_kpis(scenario_id, window_s?)   → returns KPIReport for a scenario
propose_layout(prompt)             → emits SimulationSpec, creates scenario (status=active)
suggest_optimization()             → emits LayoutChange proposal (status=pending)
query_mubit(lane, query)           → recall memories, render evidence chips
generate_hero_asset(prompt, xy)    → calls Hyper3D, streams mesh into scene
explain_pattern(pattern_id)        → returns OperationalPattern with evidence
compare_scenarios(id_a, id_b)      → opens split-screen, returns KPI diff
```

(`adjust_slider` was cut — redundant with `propose_layout`.)

### 4.2 Hyper3D entry points

Hyper3D is invoked in **two places**:

1. **During baseline ingest** — backend identifies 1–2 hero candidates from detection (highest-confidence "espresso machine", "signage") and calls Hyper3D with a cropped image. Mesh streams in async; placeholder prefab is used until ready.
2. **From chat** via `generate_hero_asset(prompt, xy)` — user asks for a custom object ("a vintage La Marzocco at the counter"); Hyper3D generates, mesh streams in.

Both entry points emit the same `hero_asset_ready` SSE event so the frontend handles them uniformly.

### 4.3 Message types rendered in chat

- **text** (markdown, streaming)
- **tool-call card** (collapsible, with status: running / done / error)
- **tool-result card** (e.g. KPI table, scenario chip)
- **layout-diff card** (visual: before vs after asset positions)
- **recommendation-card** (full `LayoutChange` proposal with Apply button → promotes pending scenario)
- **evidence-chip** (links to MuBit memory, hover → preview)

### 4.4 Multimodal

- Paste/drop image of a cafe in chat → vision-aware reply (sent as a chat attachment, distinct from the top-bar video upload which is the analysis target).
- Voice input: **cut from 24h scope.**

## 5. The 3D scene — building the digital twin

### 5.1 Composite pipeline (no single magic API does this in 24h)

```
overhead video frame
    ↓
[vision pipeline]   detects: tables, chairs, counter, staff, customers, room outline
    ↓
[layout extractor]  converts bbox → floor coords + room polygon
    ↓
[asset resolver]
    ├─ common items (table, chair, wall): Quaternius Cafe Kit GLTF prefabs
    ├─ hero items (1–2 per cafe, e.g. espresso machine): Hyper3D / Rodin API (async stream)
    └─ floor / wall textures: Poly Haven PBR or solid colors
    ↓
[R3F scene assembly]
    walls    = extruded mesh from detected polygon
    floor    = textured plane
    furniture = prefabs at detected coordinates (placeholder until hero assets stream in)
    lighting = drei <Environment preset="city"> + soft shadows
    polish   = bloom + outline postprocessing
    ↓
editable, simulation-ready 3D twin
```

### 5.2 Why this approach

- Hyper3D / Meshy / Rodin generate single objects in 30–60s — not whole rooms.
- Whole-scene gen APIs (Worldlabs, CSM) are either closed beta or quality-inconsistent.
- Photogrammetry (Luma, Polycam) produces non-editable point clouds.
- Detection + prefab placement is how every shipped product (Planner 5D, IKEA Kreativ) actually does this. It's reliable, editable, and demo-perfect for 24h.

The honest demo angle: "We don't fake a generic cafe — we reconstruct *your* cafe. Hyper3D generates the unique objects, prefabs fill the rest, and you can drag everything around."

### 5.3 Camera and feel

- **Isometric tycoon** (Two Point Hospital / Theme Hospital vibe) — fixed angle, very readable, gamey
- `<MapControls>` from drei, locked rotation
- GSAP camera tweens on scenario switch (focus on changed assets)
- Bloom + selection outline on click
- Soft contact shadows
- Particles (`drei <Sparkles>`) on congestion zones
- `use-sound` for click/place/hover SFX — sells game feel

### 5.4 Drag and drop

Furniture is draggable via raycaster + snap-to-grid (no physics engine). Dropping an asset emits a `MoveAsset` op into the active scenario, recomputes KPIs, and tweens neighbors out of overlap if needed.

### 5.5 Live agent simulation — **CUT from 24h scope**

Animated walking customers/baristas were considered but cut for time. Instead:
- Static path arrows show the most-trafficked routes from real video tracks (baseline) or path-graph estimates (scenarios).
- Heatmap overlay (`drei <Sparkles>` density) shows congestion zones.

This still sells the simulation feel without the perf/dev cost of agent pathfinding.

## 6. Stack

| Concern | Library | Notes |
|---|---|---|
| Build | Vite + React 18 + TypeScript | Fastest hackathon setup |
| 3D core | `@react-three/fiber` + `@react-three/drei` | Declarative Three.js |
| 3D postprocessing | `@react-three/postprocessing` | Bloom, outline |
| Camera helpers | `drei <MapControls>` | Isometric lock |
| Asset library | Quaternius Cafe Kit (GLTF, CC0) | Bulk furniture |
| Hero assets | Hyper3D / Rodin API | 1–2 per cafe |
| Floor/wall textures | Poly Haven PBR | Free, high quality |
| Animation | GSAP + react-spring | Scene morphs, asset tweens |
| Sound | `use-sound` | Click/place SFX |
| Flow canvas | `@xyflow/react` | Agent pipeline |
| Chat | `ai` + `@ai-sdk/react` | Streaming, tool calls |
| LLM (backend) | Anthropic Claude Sonnet 4.6 via Pydantic AI | Structured output |
| UI primitives | Tailwind + shadcn/ui | Cards, inputs, dialogs |
| Sliders | Tweakpane | Game-style HUD |
| Charts | Tremor | KPI sparklines |
| Particles | `drei <Sparkles>` | Congestion |
| State | Zustand + IndexedDB persist | Frontend cache |
| Markdown rendering | `react-markdown` | Chat |
| Backend | FastAPI + Pydantic AI + Logfire | Existing stack |
| Memory | MuBit | Existing stack |
| Storage | Postgres (scenarios, KPIs, chat threads) — **source of truth** | Existing stack |

(Cuts from earlier draft: `@react-three/rapier` physics, agent simulation pathfinding, voice input, N-way compare.)

## 7. Component boundaries

```
frontend/
  src/
    app/
      App.tsx                       # Layout shell

    components/
      SceneCanvas/                  # 3D simulation canvas
        SceneCanvas.tsx
        Walls.tsx
        Floor.tsx
        FurnitureInstance.tsx       # Wraps a GLTF prefab
        HeroAsset.tsx               # Streamed Hyper3D mesh
        PathArrows.tsx              # Static traffic arrows
        SelectionOutline.tsx
        Lighting.tsx
        Effects.tsx                 # Postprocessing
      FlowCanvas/                   # Agent pipeline graph
        FlowCanvas.tsx
        nodes/
          VisionNode.tsx
          KPINode.tsx
          PatternNode.tsx
          OptimizeNode.tsx
          SimulateNode.tsx
        FlowNodeDrawer.tsx          # Right-side drawer with logs + Logfire link
      ChatPanel/                    # LLM chat (per-scenario thread)
        ChatPanel.tsx
        Message.tsx
        ToolCallCard.tsx
        RecommendationCard.tsx
        EvidenceChip.tsx
        PromptInput.tsx
      Controls/
        ControlsPanel.tsx           # Tweakpane sliders
        KPICards.tsx                # Tremor cards (baseline-styled vs estimated-styled)
      ScenarioRail/
        ScenarioRail.tsx
        ScenarioChip.tsx
        CompareView.tsx             # Split-screen (2-way only)
      TopBar.tsx
      Timeline.tsx                  # Bottom time scrubber + before/after toggle
      EmptyState.tsx                # Pre-upload placeholder

    state/
      useSimStore.ts                # Zustand: layout, scenarios, KPIs, flow state, active threads
      persist.ts                    # IndexedDB middleware (cache only)

    lib/
      sceneBuilder.ts               # Applies SimulationSpec ops to layout
      assetResolver.ts              # Maps detection → prefab/Hyper3D
      api.ts                        # Backend REST + SSE client
      mockApi.ts                    # Canned responses for frontend-only dev
      chatClient.ts                 # Vercel AI SDK setup

    schemas/
      simulationSpec.ts             # Mirrors backend Pydantic SimulationSpec (zod)
      scenario.ts
      kpi.ts
      chatEvent.ts
```

Each component owns one concern. State flows through Zustand. The backend speaks Pydantic; the frontend mirrors those schemas in TS via zod for type safety.

## 8. Data flow

```
User types in ChatPanel
   ↓ Vercel AI SDK (POST /api/chat with scenario_id + message)
Backend FastAPI /api/chat (SSE stream)
   ↓ Pydantic AI agent (Claude Sonnet 4.6) on the scenario's thread
LLM emits tool calls (e.g. propose_layout)
   ↓
Backend executes tool, persists scenario to Postgres, streams events
   ↓ SSE: tool_call_start → tool_call_result → text_delta → message_complete
chatClient routes events
   ├─ tool-call cards → ChatPanel
   └─ scenario.created → useSimStore.applyScenario(spec)
                           ↓
                         sceneBuilder applies ops → new layout
                           ↓
                         SceneCanvas re-renders (GSAP tweens)
                         KPI cards update (estimated)
                         ScenarioRail adds new chip
```

## 9. Five canonical user flows

1. **Ingest**: drop video → `POST /api/videos` → `POST /api/videos/{id}/analyze` → flow nodes light up sequentially via SSE → 3D scene materializes (prefabs at <10s, hero asset streams in <90s).
2. **Optimize**: ask "how do I improve flow?" or click Optimize → agent emits `LayoutChange` (pending scenario) → recommendation card with Apply → click Apply → promotes to active, scene morphs, KPI deltas count up.
3. **Tune**: drag sliders → emits a `propose_layout` op locally → scene rebuilds + KPIs update live (debounced 250ms).
4. **Prompt-to-scenario**: "Brooklyn-style with communal seating" → LLM emits `SimulationSpec` → new active scenario chip → scene morphs → chat narrates tradeoffs.
5. **Compare**: long-press 2 chips → split-screen → KPI diff table → pick a winner.

## 10. Demo moments

### Primary — the orchestrated narrative
> User: *"Why is the queue so long around 11am?"*
> AI streams: *"Let me check"* → tool-card `get_kpis(window=11:00–11:15)` → tool-card `query_mubit("location:demo:patterns")` → 3D scene auto-pans to queue zone, highlights it red.
> AI: *"Found it — staff cross the queue 18× in 12 min because table cluster B forces detours. Want me to fix it?"*
> User: *"yes"* → tool-card `suggest_optimization` → pending scenario chip + recommendation card → click Apply → tables tween to new positions → KPI deltas count down.

### Stretch — parallel scenarios
> *"Show me 2 different optimizations side-by-side."*
> AI streams 2 tool calls → 2 chips materialize → 2-way split-screen → KPI diff overlay → AI narrates tradeoffs → user picks one.

## 11. Risk controls and 24h cuts

**Cuts from initial design (kept the demo focused):**
- `@react-three/rapier` physics — replaced with raycaster + snap-to-grid
- Live walking agent simulation — replaced with static path arrows + heatmap
- Voice input — fully cut
- N-way compare — 2-way only
- `adjust_slider` LLM tool — redundant, cut

**Risk controls:**
- **Hyper3D fails / slow**: fall back to a curated prefab. Demo unaffected.
- **LLM emits invalid `SimulationSpec`**: Pydantic validation rejects; chat shows "I couldn't parse that — try rewording." No scene corruption.
- **Vision pipeline slow**: pre-cache detections for the demo video; live mode behind a toggle.
- **MuBit unavailable**: local JSON fallback with identical UI contract.
- **3D perf bad on judges' laptop**: `?lowend=1` URL flag drops postprocessing, drops particles, simplifies materials.
- **Chat stream stalls**: 30s timeout, retry once, surface error in chat.
- **Hero asset fails to stream**: keep placeholder prefab indefinitely; chat shows a non-blocking warning.

## 12. Out of scope (explicit cuts)

- Live camera feed (only seeded video)
- POS integration
- True NeRF / gaussian splat reconstruction
- Custom model training
- Multi-user collaboration
- Mobile / responsive layout (desktop demo only)
- Auth / user accounts
- Generated VIDEO previews (only generated 3D + image inpainting as stretch)
- Accessibility / keyboard shortcuts (post-hackathon)

## 13. Build sequence (mapped to 24h gates)

| Time | Gate | Frontend deliverable | Backend deliverable |
|---|---|---|---|
| 0–4h | Visual proof | Vite + R3F skeleton, isometric scene, prefab loaded, walls/floor, mock data via `mockApi.ts` | Vision pipeline cached output + `/api/videos`, `/api/videos/{id}/analyze` |
| 4–8h | KPI proof | KPI cards (Tremor) bound to mock data, FlowCanvas with static nodes lit by SSE | KPI engine endpoint + `/api/scenarios/{id}/kpis` |
| 8–12h | Memory proof | Evidence chips, MuBit timeline panel | MuBit reads/writes + `/api/mubit/recall` |
| 12–16h | Agent proof | ChatPanel streaming, tool-call cards, ScenarioRail with branching, per-scenario threads | Pydantic AI agent emitting `SimulationSpec` + full SSE event set |
| 16–20h | Simulation proof | Scene morph on scenario switch, before/after toggle, sliders driving scene | KPI estimator per scenario layout |
| 20–24h | Demo proof | Polish: bloom, outlines, SFX, scenario compare split-screen, Logfire links | Render deploy, fallback recording |

**Stretch (P2, only if ahead of schedule):** N-way compare, voice input, accessibility, generated image inpainting.

## 14. Acceptance checks

- [ ] Drop video → prefab scene visible <10s
- [ ] Hero asset streams in <90s (placeholder until ready)
- [ ] Chat streams responses with tool-call cards
- [ ] Type "what if 10x" → new scenario chip appears, scene morphs
- [ ] Slider drag rebuilds scene + updates KPIs in <500ms
- [ ] Scenario rail supports switch, fork, 2-way compare
- [ ] At least one typed `LayoutChange` recommendation card with ≥3 evidence chips
- [ ] Logfire trace visible from top bar
- [ ] All flow nodes light up during a full pipeline run
- [ ] Frontend deploys to Render
- [ ] Empty state visible before first video
- [ ] Baseline KPI cards visually distinct from estimated KPI cards

## 15. Open questions

None blocking. Specifics resolved during implementation:

- Tweakpane vs Leva (will spike both in 30 min)
- Exact Hyper3D hero candidate selection rule (top-2 by confidence among hero classes)

---

## 16. Backend interface contract (for the backend dev)

> **Goal:** the frontend builds against `mockApi.ts` from hour 0. The backend dev implements these endpoints to the same shapes; flipping `VITE_USE_MOCK=false` swaps to live. **Decoupled, parallelizable.**

### 16.1 Conventions

- Base URL: `/api`
- All requests/responses JSON unless noted
- Errors: `{ "error": { "code": str, "message": str, "details": object? } }`, HTTP 4xx/5xx
- Auth: **none** (single-user hackathon demo)
- IDs: UUID v4 strings
- Timestamps: ISO 8601 UTC strings
- All Pydantic models exported via FastAPI's OpenAPI schema → frontend generates zod types via `openapi-zod-client` (or by hand if faster)
- SSE event format: `event: <name>\ndata: <json>\n\n`

### 16.2 REST endpoints

| Method | Path | Purpose | Body | Returns |
|---|---|---|---|---|
| `GET` | `/api/health` | Liveness | — | `{ "status": "ok" }` |
| `POST` | `/api/sessions` | Create demo session | — | `{ session_id, created_at }` |
| `POST` | `/api/videos` | Upload video (multipart) | `file`, `session_id` | `{ video_id, duration_s, frame_count }` |
| `POST` | `/api/videos/{video_id}/analyze` | Kick off vision pipeline | `{ session_id }` | `{ run_id }` |
| `GET` | `/api/runs/{run_id}` | Pipeline status | — | `RunStatus` (see schemas) |
| `GET` | `/api/runs/{run_id}/events` | **SSE** stream of pipeline events (for FlowCanvas) | — | SSE: `node_started`, `node_completed`, `node_error`, `run_completed` |
| `GET` | `/api/scenarios?session_id=...` | List all scenarios | — | `Scenario[]` |
| `GET` | `/api/scenarios/{id}` | Full scenario | — | `Scenario` |
| `POST` | `/api/scenarios` | Create scenario from spec | `SimulationSpec` | `Scenario` |
| `POST` | `/api/scenarios/{id}/promote` | Pending → active | — | `Scenario` |
| `DELETE` | `/api/scenarios/{id}` | Soft-delete (status=archived) | — | `204` |
| `GET` | `/api/scenarios/{id}/kpis` | KPI report | — | `KPIReport` |
| `POST` | `/api/scenarios/compare` | Diff two scenarios | `{ id_a, id_b }` | `{ kpi_diff, layout_diff }` |
| `POST` | `/api/chat` | **SSE** chat stream | `ChatRequest` | SSE events (see §16.4) |
| `POST` | `/api/hero-assets` | Generate via Hyper3D | `{ scenario_id, prompt, target_xy }` | `{ asset_id }` (mesh streams via SSE on `/api/runs/{run_id}/events`) |
| `GET` | `/api/mubit/recall` | Query MuBit lanes | `?lane=...&query=...` | `MemoryRef[]` |
| `GET` | `/api/logfire/trace/{session_id}` | Trace URL | — | `{ url }` |

### 16.3 Pydantic schemas (canonical, backend owns these)

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

# ─── Session ──────────────────────────────────────────────────────────
class Session(BaseModel):
    session_id: UUID
    created_at: datetime

# ─── Video / Run ──────────────────────────────────────────────────────
class Video(BaseModel):
    video_id: UUID
    duration_s: float
    frame_count: int

class RunStatus(BaseModel):
    run_id: UUID
    session_id: UUID
    state: Literal["queued", "running", "completed", "error"]
    nodes: list["NodeStatus"]
    started_at: datetime
    completed_at: datetime | None
    logfire_trace_id: str | None

class NodeStatus(BaseModel):
    name: Literal["vision", "kpi", "pattern", "optimize", "simulate"]
    state: Literal["idle", "running", "completed", "error"]
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None

# ─── Scenario ─────────────────────────────────────────────────────────
class Scenario(BaseModel):
    scenario_id: UUID
    session_id: UUID
    parent_scenario_id: UUID | None
    name: str
    status: Literal["baseline", "pending", "active", "archived"]
    spec: "SimulationSpec"        # the ops applied to parent
    layout_snapshot: "Layout"     # resolved layout after applying spec
    kpi_snapshot: "KPIReport"
    chat_thread_id: UUID
    created_at: datetime

class Layout(BaseModel):
    room_polygon: list[tuple[float, float]]
    assets: list["AssetInstance"]

class AssetInstance(BaseModel):
    asset_id: UUID
    asset_kind: Literal["table", "chair", "counter", "machine", "signage", "person", ...]
    position: tuple[float, float]
    rotation_deg: float
    source: Literal["prefab", "hyper3d"]
    asset_ref: str               # GLTF path or Hyper3D mesh URL

# ─── KPIs (mirrors agent_plan.md) ─────────────────────────────────────
class KPIReport(BaseModel):
    scenario_id: UUID
    source: Literal["video", "estimated"]    # ← UI distinguishes baseline vs sim
    window_start_s: float
    window_end_s: float
    staff_walk_distance_px: float
    staff_customer_crossings: int
    queue_length_peak: int
    queue_obstruction_seconds: float
    congestion_score: float
    table_detour_score: float

# ─── SimulationSpec / Ops ─────────────────────────────────────────────
# (see §3.5 for the discriminated union)

# ─── Chat ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    scenario_id: UUID
    message: str
    attachments: list["Attachment"] = []

class Attachment(BaseModel):
    kind: Literal["image"]
    url: str

class ChatMessage(BaseModel):
    message_id: UUID
    thread_id: UUID
    role: Literal["user", "assistant", "tool"]
    content: list["ContentBlock"]
    created_at: datetime

ContentBlock = TextBlock | ToolCallBlock | ToolResultBlock

# ─── MuBit ────────────────────────────────────────────────────────────
class MemoryRef(BaseModel):
    memory_id: str
    lane: str
    intent: Literal["trace", "fact", "lesson", "rule", "feedback", "tool_artifact"]
    summary: str
    created_at: datetime
```

### 16.4 SSE event taxonomy

**`/api/runs/{run_id}/events`** (pipeline events, used by FlowCanvas):

| Event | Data |
|---|---|
| `node_started` | `{ node, started_at }` |
| `node_completed` | `{ node, completed_at, summary? }` |
| `node_error` | `{ node, error }` |
| `hero_asset_ready` | `{ asset_id, scenario_id, position, mesh_url }` |
| `run_completed` | `{ run_id, scenario_id }` |

**`/api/chat`** (chat stream):

| Event | Data |
|---|---|
| `text_delta` | `{ message_id, delta }` |
| `tool_call_start` | `{ message_id, tool_call_id, tool_name, args }` |
| `tool_call_result` | `{ tool_call_id, result }` |
| `tool_call_error` | `{ tool_call_id, error }` |
| `scenario_created` | `{ scenario: Scenario }` ← frontend adds chip + applies layout |
| `recommendation_ready` | `{ proposal: LayoutChange, scenario_id }` ← pending scenario |
| `evidence_attached` | `{ message_id, evidence: MemoryRef }` |
| `message_complete` | `{ message_id }` |
| `error` | `{ code, message }` |

### 16.5 Tool execution contract (server-side)

Tools are Pydantic AI tools defined on the backend. The frontend never calls tools directly — it submits a chat message; the LLM decides whether to call tools; the backend executes and streams events. This keeps the LLM->tool boundary single-sided and easy to audit.

Each tool returns a Pydantic model. The backend wraps the result in a `ToolResultBlock` and streams it as `tool_call_result`. If the tool's side effect creates a scenario, the backend ALSO streams `scenario_created` so the frontend updates state without needing to refetch.

### 16.6 Frontend mock contract

`frontend/src/lib/mockApi.ts` ships a complete mock implementation:

```ts
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
export const api = USE_MOCK ? mockApi : liveApi;
```

Mock returns canned responses with realistic timing (e.g. 2s vision pipeline, fake SSE stream of pre-recorded events). Same Pydantic-mirroring zod types. Backend dev implements liveApi to the same surface; flip the env var at any time.

### 16.7 Environment variables

| Var | Default | Used by | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | `/api` | frontend | Backend base URL |
| `VITE_USE_MOCK` | `true` (dev), `false` (prod) | frontend | Use `mockApi.ts` |
| `ANTHROPIC_API_KEY` | — | backend | Claude API |
| `HYPER3D_API_KEY` | — | backend | Hero assets |
| `MUBIT_API_KEY` | — | backend | Memory |
| `LOGFIRE_TOKEN` | — | backend | Tracing |
| `DATABASE_URL` | — | backend | Postgres |
| `ROBOFLOW_API_KEY` | — | backend | Vision (or fallback to local YOLO) |

### 16.8 Decoupling rules (the contract that keeps frontend and backend dev parallel)

1. **Frontend never calls Anthropic, Hyper3D, MuBit, or Roboflow directly.** All third-party calls go through the backend. Keys stay server-side.
2. **Frontend renders only what the backend tells it via Scenarios + SSE events.** It does not infer state from chat text.
3. **All scenario mutations flow through `POST /api/scenarios` or `/api/scenarios/{id}/promote`.** Frontend never invents scenarios; it only displays them.
4. **`mockApi.ts` is the spec.** If a mock response shape changes, the spec changes — keep them in sync. Backend dev implements to the mock.
5. **Schema drift = build failure.** Zod types are generated from OpenAPI; CI fails if frontend types diverge from backend.
