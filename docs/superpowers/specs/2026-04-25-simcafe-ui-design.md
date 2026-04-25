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
│ pipeline     │   active scenario rendered here     │  streaming msgs,   │
│ nodes glow   │   morphs / split-screen compare     │  tool-call cards,  │
│ as data      │                                     │  evidence chips    │
│ flows        │                                     │                    │
│              │                                     │                    │
│ ─────────    │                                     │                    │
│ CONTROLS     │                                     │                    │
│ (Tweakpane)  │                                     │                    │
│ sliders for  │                                     │                    │
│ seats, staff,│                                     │                    │
│ machines     │                                     │                    │
│              │                                     │  ───────────────   │
│ KPI CARDS    │                                     │  [prompt input ↵]  │
│ (Tremor)     │                                     │  📎 image · 🎤 mic │
├──────────────┴─────────────────────────────────────┴────────────────────┤
│ 🌿 SCENARIO RAIL — [● baseline][○ 10x][○ Brooklyn][○ Tokyo][+]          │
│ click to switch · long-press 2 chips → split-screen compare             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Canvas roles

| Canvas | Purpose | Library |
|---|---|---|
| **Agent Flow** (left) | Visualize Pydantic AI pipeline. Nodes light up as the backend runs each stage. Edges animate when data flows. Click a node → trace + logs. | `@xyflow/react` |
| **3D Simulation** (center) | The active scenario. Isometric tycoon camera. Drag furniture, see simulated agents walk, congestion particles, bloom + selection outlines. | `@react-three/fiber` + `drei` + `rapier` + `postprocessing` |
| **Scenario Chat** (right) | Natural-language command surface. Drives every other canvas via tool calls. Streams responses, renders tool-call cards, evidence chips, recommendation cards. | `ai` (Vercel AI SDK) + `@ai-sdk/react` |
| **Controls + KPIs** (left lower) | Direct manipulation: sliders for seats/baristas/machines. Live KPI cards reflect current scenario. | Tweakpane + Tremor |
| **Scenario Rail** (bottom) | Tree of all scenarios. Switch, compare, fork, merge. | Custom; chips + popover |

## 3. Scenarios — the central abstraction

### 3.1 Scenario tree

Every chat what-if forks a new branch from the current scenario. State is a tree, persisted to IndexedDB (frontend) and Postgres (backend).

```
baseline (reconstructed from video)
├── "10x cafe size"
├── "Brooklyn-style with communal seating"
│   └── "...and add 2 more baristas"
├── "Move counter to back wall"
└── "Tokyo minimalist redesign"
```

### 3.2 SimulationSpec — the LLM's DSL

The LLM never writes Three.js code. It emits a typed Pydantic `SimulationSpec` (a list of layout ops). The frontend deterministically renders from it. This is the safety boundary.

```python
class SimulationSpec(BaseModel):
    scenario_name: str
    parent_scenario_id: str | None = None
    ops: list[Op]

# Op is a discriminated union:
Op = (
    ScaleRoom              # factor
  | MoveAsset              # asset_id, to_xy, rotation
  | AddAssets              # asset_kind, count, placement_strategy
  | RemoveAssets           # selector
  | ReplaceAssets          # from_kind → to_kind
  | RestyleScene           # theme: brooklyn | tokyo_minimal | parisian | ...
  | SetStaffing            # baristas, runners
  | SetEquipment           # espresso_machines, ovens, fridges
  | RedrawRoomShape        # new floor polygon
  | RedistributeFurniture  # strategy
  | GenerateHeroAsset      # prompt → Hyper3D API
)
```

Validated by Pydantic, deterministically applied by `SceneBuilder` (TypeScript). Reproducible: replay any scenario by re-applying ops.

### 3.3 Scenario operations

| User intent | UI affordance | Backend |
|---|---|---|
| New scenario | Type "what if X" in chat | LLM emits `SimulationSpec`, store creates child node |
| Switch scenario | Click chip in rail | Frontend swaps active scenario; GSAP tweens furniture |
| Compare | Long-press 2 chips | Split-screen dual `<Canvas>` with synced cameras + KPI diff |
| Fork | Long-press chip → "Branch" | Creates child of selected (not just current) |
| Merge | Right-click → "Make baseline" | Confirmation, replaces baseline reference |
| Batch | "Show me 3 optimizations" | LLM emits 3 `SimulationSpec`s in parallel |

## 4. Chat as orchestration

Chat is not a sidebar — it's the **command layer**. Pydantic AI agents on the backend expose tools the LLM can call. Each tool-call renders an inline collapsible card in the chat thread.

### 4.1 Tools available to the LLM

```
analyze_video(video_id)            → triggers vision pipeline, lights flow nodes
get_kpis(window_s, scenario_id)    → returns KPIReport for a scenario
propose_layout(prompt)             → emits SimulationSpec, creates scenario
apply_recommendation(proposal_id)  → mutates active scenario
adjust_slider(name, value)         → drives controls panel
query_mubit(lane, query)           → recall memories, render evidence chips
generate_hero_asset(prompt)        → calls Hyper3D, streams mesh into scene
explain_pattern(pattern_id)        → returns OperationalPattern with evidence
compare_scenarios(ids)             → opens split-screen, returns KPI diff
```

### 4.2 Message types rendered in chat

- **text** (markdown, streaming)
- **tool-call card** (collapsible, with status: running / done / error)
- **tool-result card** (e.g. KPI table, scenario chip)
- **layout-diff card** (visual: before vs after asset positions)
- **recommendation-card** (full `LayoutChange` proposal with Apply button)
- **evidence-chip** (links to MuBit memory, hover → preview)

### 4.3 Multimodal

- Paste/drop image of a cafe → vision-aware reply
- Optional Whisper voice input (stretch)

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
    ├─ hero items (1–2 per cafe, e.g. espresso machine): Hyper3D / Rodin API
    └─ floor / wall textures: Poly Haven PBR or solid colors
    ↓
[R3F scene assembly]
    walls    = extruded mesh from detected polygon
    floor    = textured plane
    furniture = prefabs at detected coordinates
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

### 5.4 Live agent simulation

Once a scenario is active, simulated customers and baristas walk around (instanced meshes). Walking paths are recomputed when furniture moves. Path crossings, queue length, walking distance update KPIs live.

## 6. Stack

| Concern | Library | Notes |
|---|---|---|
| Build | Vite + React 18 + TypeScript | Fastest hackathon setup |
| 3D core | `@react-three/fiber` + `@react-three/drei` | Declarative Three.js |
| 3D physics / drag | `@react-three/rapier` | Drag tables, snap-to-grid, collision |
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
| State | Zustand + IndexedDB persist | Single source of truth |
| Markdown rendering | `react-markdown` | Chat |
| Backend | FastAPI + Pydantic AI + Logfire | Existing stack |
| Memory | MuBit | Existing stack |
| Storage | Postgres (scenarios, KPIs) + JSON cache | Existing stack |

## 7. Component boundaries

```
src/
  app/
    App.tsx                       # Layout shell
    routes.tsx                    # If multi-page later

  components/
    SceneCanvas/                  # 3D simulation canvas
      SceneCanvas.tsx
      Walls.tsx
      Floor.tsx
      FurnitureInstance.tsx       # Wraps a GLTF prefab
      HeroAsset.tsx               # Streamed Hyper3D mesh
      SimulatedAgents.tsx         # Walking customers/staff
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
    ChatPanel/                    # LLM chat
      ChatPanel.tsx
      Message.tsx
      ToolCallCard.tsx
      RecommendationCard.tsx
      EvidenceChip.tsx
      PromptInput.tsx
    Controls/
      ControlsPanel.tsx           # Tweakpane sliders
      KPICards.tsx                # Tremor cards
    ScenarioRail/
      ScenarioRail.tsx
      ScenarioChip.tsx
      CompareView.tsx             # Split-screen
    TopBar.tsx
    Timeline.tsx                  # Bottom time scrubber + before/after toggle

  state/
    useSimStore.ts                # Zustand: layout, scenarios, KPIs, flow state, chat
    persist.ts                    # IndexedDB middleware

  lib/
    sceneBuilder.ts               # Applies SimulationSpec ops to layout
    assetResolver.ts              # Maps detection → prefab/Hyper3D
    api.ts                        # Backend REST + SSE client
    chatClient.ts                 # Vercel AI SDK setup

  schemas/
    simulationSpec.ts             # Mirrors backend Pydantic SimulationSpec
    kpi.ts
    scenario.ts
```

Each component owns one concern. State flows through Zustand. The backend speaks Pydantic; the frontend mirrors those schemas in TS for type safety.

## 8. Data flow

```
User types in ChatPanel
   ↓ Vercel AI SDK
Backend FastAPI /chat (SSE stream)
   ↓ Pydantic AI agent (Claude Sonnet 4.6)
LLM emits tool calls (e.g. propose_layout)
   ↓
Backend executes tool, returns SimulationSpec
   ↓ streamed to frontend
chatClient receives tool-call event
   ↓
useSimStore.applyScenario(spec)
   ↓
sceneBuilder applies ops → new layout JSON
   ↓
SceneCanvas re-renders (GSAP tweens for moved assets)
KPI engine recomputes for new layout
ScenarioRail adds new chip
ChatPanel renders tool-call card with result
```

## 9. Five canonical user flows

1. **Ingest**: drop video → vision detects → flow nodes light up sequentially → 3D scene materializes (prefabs spawn, walls extrude, hero asset streams in from Hyper3D).
2. **Optimize**: click "Optimize" or ask in chat → agent emits `LayoutChange` → 3D scene morphs → KPI deltas count up → recommendation card with Apply button.
3. **Tune**: drag sliders → scene rebuilds → simulated agents re-route → KPIs update live.
4. **Prompt-to-scenario**: "Brooklyn-style with communal seating" → LLM emits `SimulationSpec` → new scenario chip → scene morphs → chat narrates tradeoffs.
5. **Compare**: long-press 2 chips → split-screen → KPI diff table → pick a winner.

## 10. Demo moments

### Primary — the orchestrated narrative
> User: *"Why is the queue so long around 11am?"*
> AI streams: *"Let me check"* → tool-card `get_kpis(window=11:00–11:15)` → tool-card `query_mubit("location:demo:patterns")` → 3D scene auto-pans to queue zone, highlights it red.
> AI: *"Found it — staff cross the queue 18× in 12 min because table cluster B forces detours. Want me to fix it?"*
> User: *"yes"* → tool-card `propose_layout` → tables tween to new positions → KPIs count down → recommendation card with evidence + Apply button.

### Stretch — the parallel scenario flex
> *"Show me 3 different optimizations side-by-side."*
> AI streams 3 tool calls in parallel → 3 chips materialize → 3-way split-screen → KPI diff overlay → AI narrates tradeoffs → user picks one → it tweens to fullscreen.

## 11. Risk controls

- **Hyper3D fails**: fall back to a curated prefab for the hero asset. Demo is unaffected.
- **LLM emits invalid `SimulationSpec`**: Pydantic validation rejects it; chat shows "I couldn't parse that — try rewording." No scene corruption.
- **Vision pipeline slow**: pre-cache detections for the demo video; live mode behind a toggle.
- **MuBit unavailable**: local JSON memory fallback with identical UI contract.
- **3D perf bad on judges' laptop**: drop postprocessing, drop simulated agents, fall back to static scene with morphs.
- **Backend chat stream stalls**: 30s timeout, retry once, surface error in chat.

## 12. Out of scope (explicit cuts)

- Live camera feed (only seeded video)
- POS integration
- True NeRF / gaussian splat reconstruction
- Custom model training
- Multi-user collaboration
- Mobile / responsive layout (desktop demo only)
- Auth / user accounts
- Generated VIDEO previews (only generated 3D + image inpainting as stretch)

## 13. Build sequence (mapped to 24h gates)

| Time | Gate | Frontend deliverable | Backend deliverable |
|---|---|---|---|
| 0–4h | Visual proof | Vite + R3F skeleton, isometric scene, prefab loaded, walls/floor, mock data | Vision pipeline cached output |
| 4–8h | KPI proof | KPI cards (Tremor) bound to mock data, FlowCanvas with static nodes | KPI engine endpoint |
| 8–12h | Memory proof | Evidence chips, MuBit timeline panel | MuBit reads/writes |
| 12–16h | Agent proof | ChatPanel streaming, tool-call cards, ScenarioRail with branching | Pydantic AI agent emitting `SimulationSpec` |
| 16–20h | Simulation proof | Scene morph on scenario switch, before/after toggle, sliders driving scene | KPI recompute per scenario |
| 20–24h | Demo proof | Polish: bloom, outlines, SFX, scenario compare split-screen, Logfire link | Render deploy, fallback recording |

## 14. Acceptance checks

- [ ] Drop video → 3D scene reconstructed within 60s
- [ ] At least one Hyper3D hero asset visible
- [ ] Chat streams responses with tool-call cards
- [ ] Type "what if 10x" → new scenario chip appears, scene morphs
- [ ] Slider drag rebuilds scene + updates KPIs in <500ms
- [ ] Scenario rail supports switch, compare, fork
- [ ] At least one typed `LayoutChange` recommendation card with ≥3 evidence chips
- [ ] Logfire trace visible from top bar
- [ ] All flow nodes light up during a full pipeline run
- [ ] Frontend deploys to Render

## 15. Open questions

None blocking. Specifics resolved during implementation:

- Exact Tweakpane vs Leva choice (will spike both in 30 min)
- Whether to ship voice input (stretch)
- Whether `compare_scenarios` is 2-way or N-way (start 2-way)
