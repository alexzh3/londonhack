# CafeTwin / SimCafe — Overview Plan

## One-Line Pitch

CafeTwin turns overhead cafe video into spatial operations intelligence: it surfaces repeated bottlenecks and recommends layout changes with evidence and predicted KPI impact.

> POS tells you what sold. CafeTwin shows why throughput stalled.

## Build Philosophy (locked)

```
MVP    = real intelligence (two typed Pydantic AI agents in sequence + traced reasoning + memory),
         mocked spectacle (existing Babel-in-browser JSX demo, fixture-backed perception)
Tier 1 = realer perception (live KPI engine + offline YOLO/ByteTrack tracks; PatternAgent already shipped in MVP)
Tier 2 = richer spectacle (R3F twin, scene-builder agent, chat, scenario rail, hero asset)
```

Time remaining: **~18h**. Two- or three-person team. MVP must ship by hour 14 with 4h reserved for polish, deploy, and pitch rehearsal. Tier 1 and Tier 2 only land if MVP is green and stable.

If only MVP ships, the project is still defensible: real typed agent, real evidence chain, real memory write, real Logfire trace, real before/after delta. Spectacle is honestly framed as "operations console," not "tycoon game."

## Frontend strategy (locked)

The MVP **does not port** the demo to Vite/TS/Tailwind. The existing `frontend/cafetwin.html` + JSX bundle (Babel-in-browser, UMD React) is the shell as-is. We bind backend data into it additively. This preserves all the visual work already done (iso twin, agent flow, KPI cards, scenario rail, chat, modals, tweaks panel) while plugging real intelligence underneath.

The rule: **what is mock stays mock; what is real (or could be real with a small additive binding) gets wired in MVP.** Tier 1 / Tier 2 add the rest. No existing JSX file is rewritten.

- The demo's hand-authored scenarios (`baseline`, `10x.size`, `brooklyn`, `+2.baristas`, `tokyo`) stay as decorative what-ifs. They are never claimed to be agent-generated.
- The agent contributes **one** scenario: a `recommended` chip materialised from the real `LayoutChange` returned by `OptimizationAgent`. That is the chip whose KPI deltas, rationale, evidence IDs, and confidence come from the live agent.
- All other binding is additive: a small `frontend/api.js` exposes `fetch` wrappers, including `listSessions`; `app-state.jsx` gains a `useBackend()` hook; existing components grow optional props (`stages`, `layoutChange`, `logfireUrl`, `memories`) and render real data when present, synthesized data when absent.

### What's real vs mock in the MVP UI

| Surface | Status | Source |
|---|---|---|
| `PatternAgent` → `OperationalPattern` | **REAL** | Pydantic AI + Claude, typed `output_type=OperationalPattern`, `PatternEvidenceBundle` deps, semantic `output_validator` retry, `pattern.id` normalized to canonical for stable recall, fixture fallback |
| `OptimizationAgent` → `LayoutChange` | **REAL** | Pydantic AI + Claude, typed `output_type=LayoutChange`, consumes the live PatternAgent's pattern, semantic `output_validator` retry, per-session cached fallback |
| Logfire trace + top-bar link | **REAL** | `RunResponse.logfire_trace_url` |
| Memory writes + recall (MuBit + jsonl) | **REAL** | Raw recommendation/feedback events are stored durably; `/api/run` derives decision-aware prior memory for the optimizer |
| Memories modal (new) | **REAL** | `GET /api/memories` |
| `recommended` scenario chip | **REAL** | `scenarioFromLayoutChange()` — chip name, KPI deltas, rationale, evidence IDs, confidence, risk |
| `ChatPanel` `optimize.layout` ToolCall | **REAL** (replaces existing fake) | `LayoutChange` rendering |
| `AgentFlow` 5-node animation | **REAL timings** | `RunResponse.stages[]` (`evidence_pack` → vision/kpi/pattern; `optimization_agent` → optimize; `memory_write` → simulate) |
| Baseline operational KPI cards | **REAL** | `kpi_windows[0]` from `GET /api/state` (crossings, queue obstruction, table detour, congestion, walk distance) |
| Apply-time iso asset shift | **HYBRID** | Real coordinates from `simulation.from_position`/`to_position`, projected onto the procedural iso scene |
| Decorative scenarios (`baseline`/`10x`/`brooklyn`/`+2.baristas`/`tokyo`) | **MOCK** | `SCENARIO_PRESETS` + `computeKpis()` — untouched |
| Decorative POS-style KPIs (throughput / wait / revenue / NPS) | **MOCK** | Different metric *kind* than ours; live alongside as "the POS layer the pitch positions us against" |
| Iso twin procedural rendering | **MOCK** | Synthesised from `seats/baristas/style/footfall` |
| Time scrubber, speed buttons, play/pause | **MOCK** | Animate the existing iso scene only |
| Tweaks panel | **MOCK** | Existing settings; not bound |
| Free-form chat input | **MOCK** (disabled in MVP) | Activated in Tier 2 with regex routing |
| Session selector | **Tier 1A URL param** | `cafetwin.html?session=real_cafe` selects the real-video session; default URL still uses `ai_cafe_a` |

The decorative POS-style KPIs and the real operational KPIs are different metric kinds, which is fine for the pitch: *"POS tells you what sold (those decorative chips); CafeTwin shows why throughput stalled (these operational signals)."*

## Visual Architecture (MVP)

```text
   PERCEPTION (mocked)            INTELLIGENCE (real · one agent)            PRESENTATION (existing JSX demo)
 ┌─────────────────────┐       ┌───────────────────────────────────┐       ┌──────────────────────────────┐
 │   demo_data/        │       │                                   │       │  cafetwin.html (Babel-in-     │
 │                     │       │   OptimizationAgent               │       │  browser, UMD React)         │
 │ • zones.json        │──────▶│   (Pydantic AI · Claude)          │─────▶ │                              │
 │ • object_inventory  │ pack  │     ↳ output_validator retry      │Layout │ • TopBar (Logfire link wired)│
 │ • kpi_windows       │       │     ↳ semantic evidence checks    │Change │ • AgentFlow (5 nodes,        │
 │ • pattern_fixture   │       │     ↳ cached fallback             │       │   driven by stages[])        │
 │ • recommendation    │       │                                   │       │ • KPI cards (real numbers    │
 │   .cached.json      │       │                                   │       │   from kpi_windows)          │
 └──────────┬──────────┘       └────┬───────────▲──────────────────┘       │ • ChatPanel ToolCall renders │
            │                       │           │                          │   real LayoutChange          │
            │                       │ remember  │ recall                   │ • Iso twin + split compare   │
            │                       ▼           │ accepted/rejected memory │   (existing cafe-iso.jsx,    │
            │                  ┌─────────────────────────┐                 │    optionally shifts target  │
            │                  │      MEMORY             │                 │    asset on Apply)           │
            │                  │   MuBit (primary)       │                 │ • ScenarioRail (presets stay │
            └─────────────────▶│   jsonl  (fallback)     │  /api/memories  │   synthesized; recommended   │
                               └────────────┬────────────┘ ──────────────▶ │   chip is agent-driven)      │
                                            │                              │ • Memories modal             │
                                            ▼ all spans                    └──────────────▲───────────────┘
                                   ┌──────────────────┐                                   │
                                   │     Logfire      │   one trace per /api/run          │
                                   │   (audit trail)  │ ──────────────────────────────────┘
                                   └──────────────────┘
```

**Three layers, three roles:**

| Layer | Role | What's real / mocked |
|---|---|---|
| **Perception** (`demo_data/`) | Provide a typed `CafeEvidencePack` to the agent | Mocked: hand-authored or precomputed fixtures |
| **Intelligence** (`PatternAgent` → `OptimizationAgent` + Memory) | PatternAgent detects the dominant operational pattern from the bundle; OptimizationAgent reasons over the pattern + recalled prior decisions, emits a validated `LayoutChange`, writes back to memory | **Real**: Pydantic AI + Anthropic + MuBit + Logfire |
| **Presentation** (existing `frontend/cafetwin.html` + JSX) | Render the typed outputs into the existing Babel-in-browser demo via additive bindings; iso twin remains the spectacle surface | Real bindings (KPI numbers, recommendation card, agent-flow timings, Logfire link, memories) over the unchanged JSX shell; decorative scenarios stay synthesized |

**One-line read:** fixtures feed two real Pydantic AI agents in sequence — `PatternAgent` emits a typed `OperationalPattern`, then `OptimizationAgent` emits a typed `LayoutChange` informed by that pattern + decision-aware prior memory; the existing JSX demo binds that output (plus stage timings, Logfire URL, and memory records) into its already-built panels. Memory (MuBit + jsonl) stores raw recommendation/feedback events and derives accepted/rejected prior lessons for the next run. Logfire wraps the pipeline. No SceneBuilderAgent, no `/api/apply`, no Vite port for MVP.

See `agent_plan.md §Visual Architecture` for module-level detail and the per-call sequence diagram.

## What MVP Must Ship

A single linear demo flow: **Load demo (auto-runs `/api/run`) → click `recommended` chip / Apply → Accept / Reject**.

The recommendation runs in the background as part of `/api/run` when the page loads. The user's decision click is **Apply** (or selecting the `recommended` chip in the existing scenario rail), which switches the iso twin into split-compare mode. **Accept** / **Reject** posts feedback to `/api/feedback`.

### Demo artifacts (fixture-backed)

MVP ships **one session**: `ai_cafe_a`, hand-derived from `cafe_videos/ai_generated_cctv.mp4` (controlled AI-generated CCTV mock; fastest path to a clean fixture pack). Each session lives at `demo_data/sessions/<slug>/` and contains six JSON files: `session.json`, `zones.json`, `object_inventory.json`, `kpi_windows.json`, `pattern_fixture.json`, `recommendation.cached.json`. See `agent_plan.md §Demo data contract` for the per-file schema.

`real_cafe` (from `real_cctv.mp4`) is **Tier 1A** — now authored as a real-video fixture session with manual zones/inventory/KPI windows/pattern and a valid cached recommendation. Full live YOLO+ByteTrack remains the next Tier 1 perception step. The third video `ai_generated_cctv_round.mp4` is held in repo but no session is authored for it.

`mubit_fallback.jsonl` is created at runtime under `demo_data/`. Payloads include `session_id` so the Memories modal can scope to the active session. The file mirrors the same raw event model as MuBit: recommendation records and feedback records are stored separately, then joined at recall time by proposal fingerprint.

Tier 2 twin JSON (`twin_observed.json` / `twin_recommended.json`) is **not** required for MVP — the existing iso renderer in `cafe-iso.jsx` synthesises its scene from `seats/baristas/style/footfall`. The agent's `LayoutChange.simulation` (`from_position` → `to_position`) optionally shifts one asset on the recommended pane to make Apply visually meaningful.

### Real backend workflow (MVP)

Six routes; details + Logfire span tree in `agent_plan.md §FastAPI routes` and `§Logfire`.

```
GET  /api/sessions                         → list of SessionManifest
GET  /api/state?session_id=ai_cafe_a       → fixtures + KPIs + zones + inventory + pattern
POST /api/run         { session_id }       → 3 stages + LayoutChange + MemoryRecord + logfire_trace_url
POST /api/feedback    { session_id, pattern_id, proposal_fingerprint, decision } → MemoryRecord
GET  /api/memories?session_id=...          → merged MuBit + jsonl, scoped to session
GET  /api/logfire_url                      → cached trace URL for top-bar
```

`/api/run` calls: load fixtures for `session_id` → build `PatternEvidenceBundle` → `PatternAgent` → typed `OperationalPattern` (canonical id-normalized) → recall raw recommendation + feedback records from MuBit/jsonl scoped to `(session_id, pattern_id)` → derive decision-aware prior memory by joining feedback to recommendations by fingerprint → build `CafeEvidencePack` (with the live pattern + prior memory) → `OptimizationAgent` → typed `LayoutChange` → memory write (payload wraps `LayoutChange` with `session_id` + `pattern_id`).

Stages (mirror `app/schemas.py::StageName`): `evidence_pack`, `pattern_agent`, `optimization_agent`, `memory_write`.

**Two live Pydantic AI agents** in MVP, sequenced on every `/api/run`:

1. **`PatternAgent`** (`PatternEvidenceBundle → OperationalPattern`) — detects the dominant operational pattern from KPI windows + scene inventory + zones. Uses typed structured output, `@agent.output_validator` raising `ModelRetry` when `evidence[*].memory_id` ⊄ `kpi_windows[*].memory_id` or `affected_zones` ⊄ `zones[*].id`. `pattern.id` is normalized post-run to the canonical session fixture ID so `PriorRecommendationMemory` recall stays scoped consistently. Falls back to `demo_data/sessions/<slug>/pattern_fixture.json` on live failure.
2. **`OptimizationAgent`** (`CafeEvidencePack → LayoutChange`) — reasons over the live pattern + decision-aware prior memory + perception fixtures. Same Pydantic AI pattern: typed structured output, `output_validator` + `ModelRetry`, cached fallback under `recommendation.cached.json`.

`SceneBuilderAgent` is deferred to Tier 2. MVP defaults to `session_id = "ai_cafe_a"`; Tier 1A can select the real session with `cafetwin.html?session=real_cafe`.

### UI binding map (existing components ← backend fields)

The demo's panels stay. Each gains a backend hookup:

| Existing component | File | Bound to |
|---|---|---|
| `TopBar` Logfire button | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `RunResponse.logfire_trace_url` → `window.open(url)` |
| `AgentFlow` 5 visual nodes (vision / kpi / pattern / optimize / simulate) | [frontend/app-panels.jsx](frontend/app-panels.jsx) | Mapped from `RunResponse.stages[]`: `evidence_pack` → vision+kpi+pattern; `optimization_agent` → optimize; `memory_write` → simulate (relabel to `memory` for honesty). Latency badges read `ended_at - started_at` |
| KPI card grid for `baseline` chip | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `kpi_windows[0]` from `GET /api/state` (operational KPIs shown alongside the demo's invented ones, or replacing them — TBD during build) |
| `recommended` scenario chip in `ScenarioRail` (delivered) | [frontend/app-panels.jsx](frontend/app-panels.jsx), [frontend/app-state.jsx](frontend/app-state.jsx) | `scenarioFromLayoutChange(lc, base)` in `app-state.jsx` shapes the `LayoutChange` into a Scenario object inheriting baseline's seats/baristas/footfall/style. `<Scenario>` in `app-panels.jsx` branches on `scn.isRecommended`: violet `<span class="scn-ai-badge">AI</span>` instead of a status dot, two largest-magnitude `expected_kpi_delta` entries (sorted by `Math.abs`) shown as the chip's meta rows with `good`/`bad` color classes by sign. Clicking activates with `scn-active scn-recommended` styling (violet glow). `simulation` is already applied to the iso scene independently via `recInfoFromLayout` regardless of which chip is active. |
| `ChatPanel` `optimize.layout` ToolCall | [frontend/app-panels.jsx](frontend/app-panels.jsx) | Real `LayoutChange.title / rationale / evidence_ids / expected_kpi_delta / confidence / risk`. Apply / Accept / Reject buttons render below it |
| Iso twin (split compare) | [frontend/app-canvas.jsx](frontend/app-canvas.jsx), [frontend/cafe-iso.jsx](frontend/cafe-iso.jsx) | Optional: shift `target_id` asset by `to_position - from_position` on the recommended pane |
| Memories modal (clone of `session.replay` modal pattern) | [frontend/cafetwin.html](frontend/cafetwin.html) | `GET /api/memories` |
| "Seen before" chip on the recommendation card | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `RunResponse.prior_recommendation_count > 0` |

What is **cut from MVP** even though it's in the demo:
- The fake `scenario.spawn` ToolCall narrative (the spawn motion is real on the `recommended` chip; chat input box may stay disabled or hidden for MVP).
- The other scenarios' KPI deltas remain synthesized by `computeKpis()` — never claimed to be agent output.
- Time scrubber, speed buttons, and play/pause: kept visually but not wired to backend; they animate the existing iso scene only.

### Interaction (3 clicks)

1. **Page load** — `GET /api/sessions` → `GET /api/state?session_id=ai_cafe_a` → `POST /api/run`. KPI cards populate from `kpi_windows`; AgentFlow nodes light up sequentially from `stages[]`; `ChatPanel` ToolCall renders the real `LayoutChange`; `recommended` chip materialises in the rail; "Seen before" chip if `prior_recommendation_count > 0`. If prior feedback exists, the optimizer sees whether similar recommendations were accepted or rejected and adapts rather than blindly repeating an old proposal.
2. **Click `recommended` chip / Apply** — frontend-only. Iso twin enters split-compare; if a movable target is named in `simulation`, that asset shifts on the right pane.
3. **Accept** — `POST /api/feedback {decision: 'accept'}`. Three things happen in lockstep on the right pane: the target table + chairs + seated customers translate to `simulation.to_position` over 700ms (cubic ease-out); a **`KPIDeltaStrip`** fades in at the bottom-right corner of the active CanvasPane and counts each `expected_kpi_delta` up from `0 → delta` over the same 700ms with matching ease-out (top-4 by magnitude, color-coded green/red by sign); the rec-card switches to its accepted state with the `mubit_id` chip if MuBit succeeded.
4. **Reject** — `POST /api/feedback {decision: 'reject'}`. Table stays put; rec-card switches to rejected state. Memory entry written either way.

Then click the Logfire link in the top bar to show the real trace.

## Tier 1 — Realer Perception (only if MVP is green)

Upgrade the upstream layer; UI mostly unchanged.

- **Tier 1A landed:** `demo_data/sessions/real_cafe/` exists for `cafe_videos/real_cctv.mp4` with a representative 20s frame, manual zones/inventory, fixture KPI windows, `pattern_real_service_lane_choke`, and cached fallback `real_cafe_open_right_service_lane_v1`. This makes the backend real-video path work before the heavier perception stack.
- **Tier 1B landed:** `scripts/run_yolo_offline.py` runs YOLOv8n + ByteTrack offline. The primary clean detection demo is now the fake CCTV session: `demo_data/sessions/ai_cafe_a/tracks.cached.json` + `annotated_before.mp4` contain 11 person tracks / 1275 detections over 180 processed frames (`vid_stride=2`). The real CCTV session also has a cache: 48 tracks / 1856 detections over 490 processed frames (`vid_stride=3`), but the fake camera is visually cleaner for pitch screenshots and downstream KPI work.
- **Tier 1B static layout landed:** `scripts/detect_layout_objects.py` runs high-accuracy YOLOv8x over the representative frame plus sampled video frames, aggregates duplicate furniture detections, and writes validated `object_detections.cached.json` artifacts. Current caches: `ai_cafe_a` has 31 aggregated objects (`chair=15`, `dining table=7`, `couch=1`, `potted plant=8`) from 345 raw detections; `real_cafe` has 12 (`chair=11`, `dining table=1`) from 84 raw detections. Archived benchmark results in `docs/vision_benchmarks.md` compare YOLOv8x, RT-DETR-x, YOLO11x, local Moondream Photon/Kestrel, and legacy Moondream 0.5B `.mf` ONNX. RT-DETR-x has higher recall but visibly noisier duplicate/oversized boxes, so YOLOv8x remains the base cache. Optional Moondream VLM detections (`MOONDREAM_API_KEY` or local `--local` Photon/Kestrel mode) and a Pydantic AI `ObjectReviewAgent` now form the AI-review workflow; reviewed caches currently keep 23/31 candidates for `ai_cafe_a` and 9/12 for `real_cafe`.
- **Tier 1B artifact hygiene:** local heavy files are grouped under ignored folders instead of the repo root: active YOLO weights in `models/ultralytics/` and generated screenshots/annotated still images in `images/`. Unused or benchmark-only model weights (`yolo11n.pt`, `yolo12n.pt`, `yolov8m.pt`, `rtdetr-x.pt`, `yolo11x.pt`) plus legacy Moondream `.mf`/ONNX files were removed after benchmark archival.
- **Tier 1C landed:** `app/vision/kpi.py` is a deterministic KPI engine that consumes cached YOLO/ByteTrack tracks and emits live `KPIReport` windows keyed to the fixture's window schedule + memory_ids (so PatternAgent's `evidence[*].memory_id` citations stay valid against live data). `evidence_pack.state()` and `build()` invoke it through `_maybe_live_kpi_windows()`; live KPIs engage when `session.source_kind == "real"` and `tracks.cached.json` exists. AI-generated mock sessions keep their narrative fixture KPIs (their synthetic people don't actually queue). Escape hatches: `CAFETWIN_FORCE_FIXTURE_KPI=1` (always fixture) and `CAFETWIN_FORCE_LIVE_KPI=1` (force live even on synthetic). Logfire span `kpi_engine.compute_window` joins the trace tree. Verified live: `real_cafe` /api/run shows the OptimizationAgent rationale citing the live numbers (e.g. `staff_walk_distance_px 487 → 617 → 1622 px (3.3× surge)`, `table_detour_score 0.6 → 1.0 → 2.4`) instead of fixture values.
- **Tier 1D landed (visible perception):** Backend mounts `StaticFiles` for `/cafe_videos` and `/demo_data` so the frontend can fetch real CCTV assets straight from FastAPI (CORS allowed, HTTP Range supported for video scrubbing). `evidence_pack._assets()` now surfaces `assets.annotated_video` (preferring the H.264 `annotated_before.web.mp4` variant transcoded by `scripts/transcode_annotated_for_web.sh`). The frontend canvas gains a `<RealCCTVPane>` — looping `<video>` element with a "● YOLOv8n · ByteTrack · zone polygons" badge — that swaps in for the iso pane on demand. New "cctv" toolbar toggle next to "compare". For **any session whose `assets.annotated_video` exists** (both `real_cafe` and `ai_cafe_a` after gpt-5.5's Tier 1B ran on the synthetic CCTV), the demo auto-engages split-compare on first load: **left pane = looping annotated CCTV with YOLO/ByteTrack overlays, right pane = iso twin** (responding to the OptimizationAgent's recommendation). Hardcoded "real CCTV" labels neutralised to "CCTV" / "annotated CCTV" since the same pane handles both real and AI-generated sources. Closes the "perception is real, not a cartoon" gap that previously made the demo feel fixture-driven.
- **Tier 1E landed (MuBit Agent Cards):** `app/mubit_agents.py` registers `PatternAgent` and `OptimizationAgent` as first-class `AgentDefinition` resources in MuBit Managed (control plane endpoints `/v2/control/projects`, `/v2/control/projects/agents`, `/v2/control/prompt/set`). On startup the FastAPI app calls `bootstrap_mubit_agents(default_specs())`, which creates/finds the `cafetwin` project, registers each agent with its in-code system prompt as PromptVersion v1, and mints a new active version when the prompt drifts. Memory writes now route to per-agent slugs via `_resolve_agent_id(record.lane)`: `recommendations` + `feedback` → `cafetwin-optimization-agent`, `patterns` → `cafetwin-pattern-agent`. Falls back to the legacy single-agent slug when `CAFETWIN_MUBIT_AGENTS != "1"` or MuBit is unreachable. MuBit Console at console.mubit.ai now shows two named agents with versioned prompts under the `cafetwin` project — sponsor-pitch asset.
- **Tier 1F landed (live object_inventory):** `evidence_pack._maybe_augment_inventory_with_live()` appends vision-detected scene objects from `object_detections.reviewed.cached.json` (preferred) or the unreviewed sibling to the fixture `ObjectInventory`. Augmentation, not replacement: fixture objects stay so the cached recommendation's `target_id` remains valid for the fallback path. `app/vision/objects.py` adds `LAYOUT_CLASS_TO_OBJECT_KIND`, `detection_to_scene_object_dict`, `select_live_detections_for_inventory` (drops detections with IoU > 0.5 against any fixture object). Live numbers: `ai_cafe_a` 16 → 37 objects (+21 chairs/tables/plants), `real_cafe` 10 → 19 (+9). Counts_by_kind and count_confidence both update; provenance tracked via per-object `source="vision"` + an inventory-level `Tier 1F:` note. Logfire span `object_inventory.augment_live` joins the trace tree. Escape hatch: `CAFETWIN_FORCE_FIXTURE_INVENTORY=1`.
- Add a richer session selector (TopBar dropdown or Tweaks panel control) if time allows. The fast path is already available via `?session=real_cafe`.
- Add 3 more memory writes: KPI summary, object inventory, pattern.
- Logfire trace already at 6 spans on `/api/run` (`api.run`, `evidence_pack.build`, `kpi_engine.compute_window`, `pattern_agent.run` + nested, `optimization_agent.run` + nested, `memory.write`).

The MVP pitch becomes "the perception layer is also real, on real footage."

## Tier 2 — Richer Spectacle (only if Tier 1 is green)

Upgrade the UI; backend gains a second agent.

- Add `SceneBuilderAgent` (Pydantic AI) emitting a typed `TwinLayout`. Add `POST /api/apply` returning the recommended layout. Wire a fourth and fifth flow node: `scene_build.observed`, `scene_build.recommended`.
- Optional: replace the iso renderer with R3F/box prefabs, same `TwinLayout` schema. The existing iso renderer stays as a low-end fallback (`?lowend=1`).
- Activate the chat input with **supported prompts only** (regex/keyword routing): "reduce crossings," "show Brooklyn concept," "compare baseline and recommendation." Anything else returns a canned reply.
- Wire flow-node animation to real backend stage events for every span.
- Richer memory timeline UI with hover previews and lane labels.
- Optional: Hyper3D / prebaked GLB hero asset (single object).
- Optional: live YOLO upload path.
- Optional: port to Vite + TS + Tailwind once the design is locked.

## Non-Goals (will not be built in 18h)

- Live camera feed.
- POS integration.
- Photorealistic 3D reconstruction.
- Drag-and-drop on the twin.
- Scenario forking / archiving / N-way compare.
- Multimodal chat (image paste, voice).
- Custom model training.
- Real staff/customer identity tracking.
- Whole-scene generative 3D.
- Vite/TS/Tailwind port (Tier 2 optional).

## Stack

| Concern | Choice |
|---|---|
| Backend | FastAPI + Pydantic AI (Anthropic Claude Sonnet 4.x) + Logfire |
| Memory | MuBit primary + local jsonl mirror as raw event store; derived decision-aware recall view for the optimizer |
| Vision (offline only in MVP) | Ultralytics YOLO + ByteTrack + OpenCV + ffmpeg |
| KPI engine | Deterministic Python (numpy + shapely or `cv2.pointPolygonTest`) |
| Frontend (MVP) | **Existing `frontend/cafetwin.html` + JSX** (Babel-standalone in-browser, UMD React 18). No build step. New `frontend/api.js` adds `fetch` wrappers |
| Frontend (Tier 2 optional) | Vite + React 18 + TypeScript + Tailwind + shadcn/ui |
| Twin (MVP) | Existing SVG iso renderer in `frontend/cafe-iso.jsx` |
| Twin (Tier 2) | `@react-three/fiber` + `drei`, driven by typed `TwinLayout` |
| Hosting | Render backend (`cafetwin-backend-tier1`, pinned to `tier_1`) + static frontend served as flat HTML |

## Sponsor-tool fit

- **Pydantic AI:** two typed agents in MVP, sequenced on every `/api/run` — `PatternAgent` (typed `OperationalPattern`) feeds `OptimizationAgent` (typed `LayoutChange`). Both use `output_validator` + `ModelRetry` + cached fixture fallback. Tier 2 adds `SceneBuilderAgent`.
- **Logfire:** one trace per `/api/run` covering evidence pack + recall, optimization agent, validation, and memory write. Plus a smaller `/api/feedback` trace.
- **MuBit:** primary memory store. MVP uses writes for raw recommendation + feedback events, then recall derives a decision-aware view of prior recommendations on the same pattern so the optimizer can favor accepted ideas and avoid rejected repeats. The UI surfaces this as a "Seen before" chip and the Memories modal. Tier 1 adds KPI/inventory/pattern lanes. Local jsonl is a hot fallback always written in parallel per AGENTS.md.
- **Render:** hosted Tier 1 backend demo URL from the `cafetwin-backend-tier1` service.

## 18h Build Plan (2-person split: A=backend, B=frontend bindings)

| Hours | Track A — backend | Track B — frontend bindings |
|---|---|---|
| 0–3 | Pull one representative frame from `cafe_videos/ai_generated_cctv.mp4` (`ffmpeg -ss 5 -i ... -frames:v 1`). Hand-author `demo_data/sessions/ai_cafe_a/{session,zones,object_inventory,kpi_windows,pattern_fixture,recommendation.cached}.json` against that frame. Stand up `evidence_pack.build(session_id)` reading these into `CafeEvidencePack`. | Add `frontend/api.js` (~40 lines, `fetch` wrappers for the 6 MVP routes). Verify `cafetwin.html` still loads with the new `<script>` tag. Stub `useBackend(session_id)` hook returning fixture data for now. |
| 3–7 | `OptimizationAgent` live with strict prompt requiring `evidence_ids` ⊆ pattern fixture IDs. Pydantic AI structured output + semantic `output_validator`/`ModelRetry` + cached fallback. CORS middleware + the 6 MVP routes wired (`/api/sessions`, `/api/state`, `/api/run`, `/api/feedback`, `/api/memories`, `/api/logfire_url`). | Wire `useBackend()` to `/api/state` then `/api/run` on mount. Drive `AgentFlow` node states from `stages[]`. Replace one `ToolCall` in `ChatPanel` with the real `LayoutChange` rendering. Wire Logfire button URL. |
| 7–11 | MuBit writer + jsonl fallback (always-write). Recall on pattern_id for raw recommendation + feedback events; derive decision-aware prior memory before the optimizer prompt. Logfire setup + manual spans. End-to-end smoke against the demo HTML running locally. | Build the `recommended` scenario chip from `LayoutChange` (preserving existing rail UX). Add Apply / Accept / Reject buttons under the recommendation; Accept/Reject hits `/api/feedback`. Add the Memories modal pulling from `/api/memories`. |
| 11–14 | End-to-end smoke. Prompt-tune until agent reliably cites real evidence IDs. Confirm fallback path on key-unset and on validation failure. | "Seen before" chip from `prior_recommendation_count`. **Done:** iso-scene asset shift on the recommended pane using `simulation.from_position/to_position` — `recInfoFromLayout` hashes `target_id` to a `tablePositions` index; `useScalarTween` drives the apply animation. Loading and error toasts. |
| 14–16 | Render deploy backend, env wiring, fallback recording of full flow as a video. | Polish: copy, loading skeletons, demo seeding script. Fallback recording. |
| 16–18 | Pitch rehearsal. **Cut anything still risky.** Final push. | Same. |

If MVP is green by hour 12, A starts Tier 1 (offline YOLO on `real_cctv.mp4` → live KPI engine → `PatternAgent`/builder → author `demo_data/sessions/real_cafe/`); B starts Tier 2 prep (`SceneBuilderAgent` integration, optional R3F scaffold) and wires the session selector. Don't merge Tier 1/2 work into the demo branch unless it's stable and green by hour 16.

## Implementation Status

Current status (2026-04-26):

- `pyproject.toml` defines the uv-managed Python backend project.
- `demo_data/sessions/ai_cafe_a/` now contains the extracted 5s frame plus the six required JSON fixtures for the controlled mock CCTV session.
- `demo_data/sessions/real_cafe/` now contains a Tier 1A real-video fixture pack from `cafe_videos/real_cctv.mp4`: extracted 20s frame, six required JSON fixtures, real-video service-lane choke pattern, and cached `LayoutChange` targeting `service_lane_marker_1`.
- `app/vision/tracks.py` defines the Tier 1 track-cache contract. `scripts/run_yolo_offline.py` uses PEP 723 inline dependencies (`ultralytics`, `opencv-python-headless`, `lap`) and defaults to CPU so it works on the local MX330 laptop where current PyTorch wheels cannot execute CUDA kernels. The generated `ai_cafe_a` cache is the preferred fake-session detection path (`schema_version="cafetwin.tracks.v1"`, 11 tracks, 1275 detections, role counts `staff=1`, `customer=10`, `unknown=0`); `real_cafe` also has a cache (48 tracks, 1856 detections, role counts `staff=15`, `customer=24`, `unknown=9`).
- `app/vision/objects.py` defines the Tier 1 static-object cache contract. `scripts/detect_layout_objects.py` defaults to YOLOv8x for accuracy, samples each session video in addition to the representative frame, clusters duplicate detections by class + IoU, and writes `object_detections.cached.json` for `ai_cafe_a` and `real_cafe`.
- `scripts/review_layout_objects_moondream.py` supports Moondream cloud and local Photon/Kestrel mode. Historical local Photon/Kestrel and legacy `.mf` Moondream benchmark results are archived in `docs/vision_benchmarks.md`; the ad-hoc benchmark scripts and benchmark-only weights were removed after capture.
- `app/agents/object_review_agent.py` adds a Pydantic AI review layer for object detections. It consumes detector candidates plus optional `object_detections.moondream.cached.json`, emits keep/drop decisions in `object_review.cached.json`, and writes a stricter `object_detections.reviewed.cached.json`.
- `app/` now has the first backend spine implemented: session discovery, fixture status, `CafeEvidencePack` build, `.env` loading, `OptimizationAgent` typed structured output with semantic retry/fallback via Pydantic AI `output_validator` + `ModelRetry`, decision-aware `PriorRecommendationMemory` recall derived from recommendation+feedback records, Logfire/Pydantic AI instrumentation, safe Logfire scrubbing for public fixture `session_id` values, MuBit primary memory writes/recall with always-on jsonl mirror fallback, CORS, and the six MVP routes.
- `app/schemas.py` defines the strict Pydantic evidence, agent-output, memory, and API contracts. `RunResponse` includes `stages`, `layout_change`, `memory_record`, `prior_recommendation_count`, `used_fallback`, and `logfire_trace_url` — frontend can bind against the locked shapes immediately.
- `GET /api/memories?session_id=...` queries MuBit when configured, merges/dedupes with local jsonl records, and reports `source` as `mubit`, `jsonl`, or `merged`.
- Live `/api/run` smoke with local Logfire + Pydantic AI Gateway env returns `used_fallback=false`, a validated `LayoutChange`, `logfire_trace_url`, and a jsonl memory write. The latest observed live fingerprint is `move_table_center_1_reduce_pickup_pinch_v1`.
- Forced-fallback validation for `real_cafe` passes: `/api/sessions` discovers it, `/api/state?session_id=real_cafe` returns all fixtures/assets, `validate_layout_change(load_cached_recommendation("real_cafe"), build("real_cafe"))` has no errors, and `/api/run {"session_id":"real_cafe"}` returns the cached `real_cafe_open_right_service_lane_v1` with the standard 3-stage response shape.
- `tests/` covers session discovery, fixture parsing, cached recommendation validation, `/api/state`, `/api/run`, `/api/feedback`, `/api/memories` filtering and MuBit merge behavior, derived accept/reject/unknown prior recommendation memory, Logfire trace URL construction/caching, Logfire `session_id` scrub allowlisting, `OptimizationAgent` `output_validator`/`ModelRetry` semantic retry/fallback, and MuBit-backed memory writes/recall without hitting the real service. Current verification: `pytest` 27 passed; `ruff check app tests` passed.
- `frontend/` is the Babel-in-browser demo: `cafetwin.html`, `app-state.jsx`, `app-canvas.jsx`, `app-panels.jsx`, `cafe-iso.jsx`, `cafetwin.css`, plus `api.js`. `tweaks-panel.jsx` is loaded only for its `useTweaks` hook (state container); the floating Tweaks panel itself is removed. **Wired in-app:** `useBackend(SESSION_ID)` drives `/api/state` + `/api/run` on mount and exposes `submitFeedback`; `SESSION_ID` defaults to `ai_cafe_a` and can be overridden with `?session=real_cafe`. `TopBar` surfaces: the Logfire button (opens `RunResponse.logfire_trace_url` in a new tab when present), a backend-status dot (loading / ready / error) showing the active session, and a **dark-theme toggle** between the tokens status and share button (sun/moon icons, flips `<html data-theme>` via a `useEffect` so the full warm-dark palette in `cafetwin.css` engages). `AgentFlow` 5 visual nodes light up from `RunResponse.stages[]` with real latencies; the 5th node is relabelled `memory` to match `memory_write`. `ChatPanel` renders the real `LayoutChange` via `LiveRecommendation` (title, rationale, KPI deltas, evidence + risk + confidence pills, "seen before" chip when `prior_recommendation_count > 0`, "cached fallback" pill when `used_fallback`, the `accept + apply` / `reject` controls directly under the recommendation title call `/api/feedback`), and its stream uses `minmax(0, 1fr)` + `min-height: 0` + `.chat-stream > * { flex: 0 0 auto }` (locks intrinsic size of `tool-call`/`chat-msg` so the rec-card isn't squashed and clipped by `.tool-call { overflow: hidden }`). `ChatPanel` auto-scrolls the rec-card's top into view whenever a fresh `fingerprint` arrives, so the user always sees title + accept/reject buttons without manual scrolling. The default active scenario is `baseline` so decorative scenario chat no longer pushes the recommendation down on first load. On Accept the iso scene's `CafeScene` now visibly translates the recommended target table (and its chairs + seated customers) along the agent's `simulation.from_position → to_position` vector via `recInfoFromLayout` + `useScalarTween` — pre-Apply a pulsing halo + dashed destination ghost + arrow flag the proposal; the right (active) pane animates while the left (baseline) pane stays clean for split-compare. `CanvasToolbar` stubs (`plan` / `3d` view modes, `geom` / `people` / `paths` layer chips) are visually marked as preview-only so they don't look broken. Decorative scenario presets remain untouched per "what is mock stays mock."
- `docs/architecture/` contains short build notes for the MVP spine, project structure, and fixture contract.
- `.venv/` and `.agents/` are local ignored artifacts. `.agents/handoff.md` is for multi-agent coordination only and should stay out of git. `.env.example` is the only env template that may be tracked.

Still open: the frontend Memories modal pulling `/api/memories`. Known cosmetic caveat: the iso SVG in `cafe-iso.jsx` uses hardcoded paint colours and stays bright in dark mode.

## Demo Script (90 seconds)

1. *"POS tells operators what sold. CafeTwin shows why throughput stalled — this is a controlled CCTV-style cafe mock."* — page loads with `ai_cafe_a` selected.
2. *"Fixture-backed KPIs from this overhead clip: 18 staff/customer crossings, queue obstructed for 41s, table detour score 1.6."* — KPI cards from `kpi_windows.json`.
3. *"Same cafe rendered as an isometric twin so we can preview changes."* — iso twin renders for the baseline chip.
4. *"A Pydantic AI agent read the evidence pack and proposed one layout change — cited evidence IDs, expected KPI deltas, confidence, risk."* — `ChatPanel` ToolCall renders the real `LayoutChange`. "Seen before" chip if prior runs exist.
5. **Click Apply.** *"Same twin, recommended layout — table cluster B shifts left."* — split-compare engages, target asset shifts, KPI deltas animate.
6. **Click Accept.** *"Feedback writes to MuBit; jsonl mirrors it as a hot fallback."* — Memories modal shows the new entry with a `mubit_id` chip.
7. **Reload the demo.** *"The agent recalls the prior recommendation from MuBit — see the 'Seen before' chip."* — memory loop visible.
8. **Click Logfire.** *"One trace per run — evidence pack, optimization agent, validation, memory write, all spans visible."* — opens in a new tab.
9. *"Perception is fixture-backed; the agent, its typed output, validation, memory recall + write, and the trace are all real."*

## Why This Wins The Room

- **Real intelligence:** typed Pydantic AI agent + semantic output validation/retry + evidence chain + memory + Logfire trace are all genuinely live and observable.
- **Honest framing:** we explicitly say what's fixture-backed vs live. No fake-AI demo theater. Decorative scenarios are decorative; the recommendation is real.
- **Sponsor-tool depth:** Pydantic AI is the spine, MuBit is the memory, Logfire is the audit trail, Render hosts it. Every sponsor tool is on the critical demo path.
- **Graceful degradation:** if Tier 1 doesn't land, MVP still ships. If the agent fails or keys are unset, the cached `LayoutChange` renders identically. The frontend never depends on a build step that could break at demo time.

## References

- Pydantic AI docs: https://pydantic.dev/docs/ai/overview/
- MuBit docs: https://docs.mubit.ai/
- Ultralytics tracking (Tier 1): https://docs.ultralytics.com/modes/track/
