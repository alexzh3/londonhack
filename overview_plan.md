# CafeTwin / SimCafe — Overview Plan

## One-Line Pitch

CafeTwin turns overhead cafe video into spatial operations intelligence: it surfaces repeated bottlenecks and recommends layout changes with evidence and predicted KPI impact.

> POS tells you what sold. CafeTwin shows why throughput stalled.

## Build Philosophy (locked)

```
MVP    = real intelligence (one typed Pydantic AI agent + traced reasoning + memory),
         mocked spectacle (existing Babel-in-browser JSX demo, fixture-backed perception)
Tier 1 = realer perception (live KPI engine + offline YOLO + PatternAgent or typed pattern builder)
Tier 2 = richer spectacle (R3F twin, scene-builder agent, chat, scenario rail, hero asset)
```

Time remaining: **~18h**. Two- or three-person team. MVP must ship by hour 14 with 4h reserved for polish, deploy, and pitch rehearsal. Tier 1 and Tier 2 only land if MVP is green and stable.

If only MVP ships, the project is still defensible: real typed agent, real evidence chain, real memory write, real Logfire trace, real before/after delta. Spectacle is honestly framed as "operations console," not "tycoon game."

## Frontend strategy (locked)

The MVP **does not port** the demo to Vite/TS/Tailwind. The existing `frontend/cafetwin.html` + JSX bundle (Babel-in-browser, UMD React) is the shell as-is. We bind backend data into it additively. This preserves all the visual work already done (iso twin, agent flow, KPI cards, scenario rail, chat, modals, tweaks panel) while plugging real intelligence underneath.

- The demo's hand-authored scenarios (`baseline`, `10x.size`, `brooklyn`, `+2.baristas`, `tokyo`) stay as decorative what-ifs. They are never claimed to be agent-generated.
- The agent contributes **one** scenario: a `recommended` chip materialised from the real `LayoutChange` returned by `OptimizationAgent`. That is the chip whose KPI deltas, rationale, evidence IDs, and confidence come from the live agent.
- All other binding is additive: a small `frontend/api.js` exposes `fetch` wrappers; `app-state.jsx` gains a `useBackend()` hook; existing components grow optional props (`stages`, `layoutChange`, `logfireUrl`, `memories`) and render real data when present, synthesized data when absent.

## Visual Architecture (MVP)

```text
   PERCEPTION (mocked)            INTELLIGENCE (real · one agent)            PRESENTATION (existing JSX demo)
 ┌─────────────────────┐       ┌───────────────────────────────────┐       ┌──────────────────────────────┐
 │   demo_data/        │       │                                   │       │  cafetwin.html (Babel-in-     │
 │                     │       │   OptimizationAgent               │       │  browser, UMD React)         │
 │ • zones.json        │──────▶│   (Pydantic AI · Claude)          │─────▶ │                              │
 │ • object_inventory  │ pack  │     ↳ retry-once                  │Layout │ • TopBar (Logfire link wired)│
 │ • kpi_windows       │       │     ↳ post-validate evidence_ids  │Change │ • AgentFlow (5 nodes,        │
 │ • pattern_fixture   │       │     ↳ cached fallback             │       │   driven by stages[])        │
 │ • recommendation    │       │                                   │       │ • KPI cards (real numbers    │
 │   .cached.json      │       │                                   │       │   from kpi_windows)          │
 └──────────┬──────────┘       └────┬───────────▲──────────────────┘       │ • ChatPanel ToolCall renders │
            │                       │           │                          │   real LayoutChange          │
            │                       │ remember  │ recall                   │ • Iso twin + split compare   │
            │                       ▼           │ prior recs               │   (existing cafe-iso.jsx,    │
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
| **Intelligence** (`OptimizationAgent` + Memory) | Reason over the pack, recall prior decisions, emit a validated `LayoutChange`, write back to memory | **Real**: Pydantic AI + Anthropic + MuBit + Logfire |
| **Presentation** (existing `frontend/cafetwin.html` + JSX) | Render the typed outputs into the existing Babel-in-browser demo via additive bindings; iso twin remains the spectacle surface | Real bindings (KPI numbers, recommendation card, agent-flow timings, Logfire link, memories) over the unchanged JSX shell; decorative scenarios stay synthesized |

**One-line read:** fixtures feed one real Pydantic AI agent (`OptimizationAgent`) that emits a typed `LayoutChange`; the existing JSX demo binds that output (plus stage timings, Logfire URL, and memory records) into its already-built panels. Memory (MuBit + jsonl) and Logfire wrap the pipeline. No SceneBuilderAgent, no `/api/apply`, no Vite port for MVP.

See `agent_plan.md §Visual Architecture` for module-level detail and the per-call sequence diagram.

## What MVP Must Ship

A single linear demo flow: **Load demo (auto-runs `/api/run`) → click `recommended` chip / Apply → Accept / Reject**.

The recommendation runs in the background as part of `/api/run` when the page loads. The user's decision click is **Apply** (or selecting the `recommended` chip in the existing scenario rail), which switches the iso twin into split-compare mode. **Accept** / **Reject** posts feedback to `/api/feedback`.

### Demo artifacts (fixture-backed)

```
demo_data/
  source_video.mp4                # original overhead clip (seeded; for the pitch, not loaded at runtime)
  annotated_before.mp4            # optional overlay video (only used if the canvas video tab is enabled)
  tracks.cached.json              # YOLO+ByteTrack output, generated offline (Tier 1; ship for credibility in MVP)
  zones.json                      # hand-drawn polygons (queue/pickup/seating/staff_path/counter)
  object_inventory.json           # chair/table/counter/pickup_shelf counts + xy
  kpi_windows.json                # KPI engine output (precomputed for MVP, live in Tier 1)
  pattern_fixture.json            # one OperationalPattern with evidence IDs
  recommendation.cached.json      # deterministic LayoutChange fallback (if OptimizationAgent retry fails)
  mubit_fallback.jsonl            # local-first memory lane, created at runtime
```

Twin layout JSON (`twin_observed.json` / `twin_recommended.json`) is **not** required for MVP — the existing iso renderer in `cafe-iso.jsx` synthesises its scene from `seats/baristas/style/footfall`. Optionally, `LayoutChange.simulation.target_id` + `from_position`/`to_position` is used to shift one asset on the recommended pane to make Apply visually meaningful.

### Real backend workflow (MVP)

One endpoint runs the full agentic chain. One Logfire trace.

```
POST /api/run                    (called once when the page loads)
  load fixtures
  → MuBit recall (prior recommendations for this pattern)
  → build CafeEvidencePack (typed Pydantic input bundle, includes prior_recommendations)
  → OptimizationAgent                               → typed LayoutChange
  → memory.write (lane=recommendations, intent=lesson)
  → return RunResponse { stages[3], layout_change, memory_record, logfire_trace_url } to UI

POST /api/feedback               (called on Accept / Reject)
  → memory.write (lane=feedback, intent=feedback)
  → return FeedbackResponse { decision, memory_record }
```

Stages (mirrors `app/schemas.py::StageName`): `evidence_pack`, `optimization_agent`, `memory_write`.

Logfire spans for `/api/run`:

1. `evidence_pack.build` → child: `mubit.recall`
2. `optimization_agent.run` (auto-instrumented by Pydantic AI)
3. `layout_change.validate`
4. `memory.write` → children: `memory.write.mubit`, `memory.write.jsonl`

For `/api/feedback`:

5. `feedback.write` → children: `memory.write.mubit`, `memory.write.jsonl`

**One live Pydantic AI agent** — `OptimizationAgent`. Validated, retry-once, cached fallback. SceneBuilderAgent is deferred to Tier 2.

### UI binding map (existing components ← backend fields)

The demo's panels stay. Each gains a backend hookup:

| Existing component | File | Bound to |
|---|---|---|
| `TopBar` Logfire button | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `RunResponse.logfire_trace_url` → `window.open(url)` |
| `AgentFlow` 5 visual nodes (vision / kpi / pattern / optimize / simulate) | [frontend/app-panels.jsx](frontend/app-panels.jsx) | Mapped from `RunResponse.stages[]`: `evidence_pack` → vision+kpi+pattern; `optimization_agent` → optimize; `memory_write` → simulate (relabel to `memory` for honesty). Latency badges read `ended_at - started_at` |
| KPI card grid for `baseline` chip | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `kpi_windows[0]` from `GET /api/state` (operational KPIs shown alongside the demo's invented ones, or replacing them — TBD during build) |
| `recommended` scenario chip in `ScenarioRail` | [frontend/app-panels.jsx](frontend/app-panels.jsx), [frontend/app-state.jsx](frontend/app-state.jsx) | Built client-side from `LayoutChange`: chip name=`recommended`, `expected_kpi_delta` shown on hover/inspect, `simulation` applied to iso scene |
| `ChatPanel` `optimize.layout` ToolCall | [frontend/app-panels.jsx](frontend/app-panels.jsx) | Real `LayoutChange.title / rationale / evidence_ids / expected_kpi_delta / confidence / risk`. Apply / Accept / Reject buttons render below it |
| Iso twin (split compare) | [frontend/app-canvas.jsx](frontend/app-canvas.jsx), [frontend/cafe-iso.jsx](frontend/cafe-iso.jsx) | Optional: shift `target_id` asset by `to_position - from_position` on the recommended pane |
| Memories modal (clone of `session.replay` modal pattern) | [frontend/cafetwin.html](frontend/cafetwin.html) | `GET /api/memories` |
| "Seen before" chip on the recommendation card | [frontend/app-panels.jsx](frontend/app-panels.jsx) | `RunResponse.prior_recommendation_count > 0` |

What is **cut from MVP** even though it's in the demo:
- The fake `scenario.spawn` ToolCall narrative (the spawn motion is real on the `recommended` chip; chat input box may stay disabled or hidden for MVP).
- The other scenarios' KPI deltas remain synthesized by `computeKpis()` — never claimed to be agent output.
- Time scrubber, speed buttons, and play/pause: kept visually but not wired to backend; they animate the existing iso scene only.

### Interaction (3 clicks)

1. **Page load** — calls `GET /api/state` then `POST /api/run`. KPI cards populate from `kpi_windows`. AgentFlow nodes light up sequentially using returned stage timestamps. The existing `recommended` chip materialises in the rail with real `LayoutChange` data; `ChatPanel` ToolCall renders the real recommendation. The "Seen before" chip appears if `prior_recommendation_count > 0`.
2. **Click `recommended` chip / Apply** — frontend-only. Switches iso twin to split-compare mode; if a movable target is named in `simulation`, that one asset visibly shifts on the right pane. KPI delta cards for the recommended chip animate from `expected_kpi_delta`.
3. **Accept / Reject** — calls `POST /api/feedback`. Toast confirms; the Memories modal (next time it's opened) shows the new entry with a fresh `mubit_id` chip.

Then click the Logfire link in the top bar to show the real trace.

## Tier 1 — Realer Perception (only if MVP is green)

Upgrade the upstream layer; UI mostly unchanged.

- Run YOLO + ByteTrack offline (or on demand) on the seeded video to produce real `tracks.cached.json` + `annotated_before.mp4` (replaces hand-authored fixtures).
- Run the deterministic KPI engine live on cached tracks + zones (replaces precomputed `kpi_windows.json`).
- Add a second live agent — either a real `PatternAgent` or a deterministic pattern builder — so the chain is `KPI engine → PatternAgent → OptimizationAgent`.
- Add 3 more memory writes: KPI summary, object inventory, pattern.
- Logfire trace grows to 6–7 spans.

No UI changes required. The demo looks identical; the pitch becomes "the perception layer is also real."

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
| Memory | local jsonl (always written) + MuBit (primary read/write, best-effort) |
| Vision (offline only in MVP) | Ultralytics YOLO + ByteTrack + OpenCV + ffmpeg |
| KPI engine | Deterministic Python (numpy + shapely or `cv2.pointPolygonTest`) |
| Frontend (MVP) | **Existing `frontend/cafetwin.html` + JSX** (Babel-standalone in-browser, UMD React 18). No build step. New `frontend/api.js` adds `fetch` wrappers |
| Frontend (Tier 2 optional) | Vite + React 18 + TypeScript + Tailwind + shadcn/ui |
| Twin (MVP) | Existing SVG iso renderer in `frontend/cafe-iso.jsx` |
| Twin (Tier 2) | `@react-three/fiber` + `drei`, driven by typed `TwinLayout` |
| Hosting | Render (backend) + static frontend served as flat HTML |

## Sponsor-tool fit

- **Pydantic AI:** one typed agent in MVP — `OptimizationAgent` emitting validated `LayoutChange`. Tier 2 adds `SceneBuilderAgent`.
- **Logfire:** one trace per `/api/run` covering evidence pack + recall, optimization agent, validation, and memory write. Plus a smaller `/api/feedback` trace.
- **MuBit:** primary memory store. MVP uses both `remember` (recommendations + feedback) and `recall` (prior recommendations on the same pattern, surfaced in the recommendation card as a "Seen before" chip). Tier 1 adds KPI/inventory/pattern lanes. Local jsonl is a hot fallback always written in parallel per AGENTS.md.
- **Render:** hosted demo URL.

## 18h Build Plan (2-person split: A=backend, B=frontend bindings)

| Hours | Track A — backend | Track B — frontend bindings |
|---|---|---|
| 0–3 | Hand-author or extract `tracks.cached.json`, `zones.json`, `object_inventory.json`, `kpi_windows.json`, `pattern_fixture.json`, `recommendation.cached.json`. Stand up `evidence_pack.build()` reading these into `CafeEvidencePack`. | Add `frontend/api.js` (~40 lines, `fetch` wrappers for the 5 routes). Verify `cafetwin.html` still loads with the new `<script>` tag. Stub `useBackend()` hook returning fixture data for now. |
| 3–7 | `OptimizationAgent` live with strict prompt requiring `evidence_ids` ⊆ pattern fixture IDs. Post-validation + retry-once + cached fallback. CORS middleware + the 5 routes wired (`/api/state`, `/api/run`, `/api/feedback`, `/api/memories`, `/api/logfire_url`). | Wire `useBackend()` to `/api/state` then `/api/run` on mount. Drive `AgentFlow` node states from `stages[]`. Replace one `ToolCall` in `ChatPanel` with the real `LayoutChange` rendering. Wire Logfire button URL. |
| 7–11 | MuBit writer + jsonl fallback (always-write). Recall on pattern_id for prior recommendations. Logfire setup + manual spans. End-to-end smoke against the demo HTML running locally. | Build the `recommended` scenario chip from `LayoutChange` (preserving existing rail UX). Add Apply / Accept / Reject buttons under the recommendation; Accept/Reject hits `/api/feedback`. Add the Memories modal pulling from `/api/memories`. |
| 11–14 | End-to-end smoke. Prompt-tune until agent reliably cites real evidence IDs. Confirm fallback path on key-unset and on validation failure. | "Seen before" chip from `prior_recommendation_count`. Optional: shift the iso scene's `target_id` asset on the recommended pane using `simulation.from_position/to_position`. Loading and error toasts. |
| 14–16 | Render deploy backend, env wiring, fallback recording of full flow as a video. | Polish: copy, loading skeletons, demo seeding script. Fallback recording. |
| 16–18 | Pitch rehearsal. **Cut anything still risky.** Final push. | Same. |

If MVP is green by hour 12, A starts Tier 1 (live KPI engine on cached tracks → live `pattern_builder` or `PatternAgent`); B starts Tier 2 prep (`SceneBuilderAgent` integration, optional R3F scaffold). Don't merge Tier 1/2 work into the demo branch unless it's stable and green by hour 16.

## Implementation Status

Current scaffold:

- `pyproject.toml` defines the uv-managed Python backend project.
- `app/` contains the initial FastAPI, agent, memory, fallback, and evidence-pack module boundaries (route bodies are stubs to be implemented in 0–7h Track A).
- `app/schemas.py` defines the strict Pydantic evidence, agent-output, memory, and API contracts. `RunResponse` already includes `stages`, `layout_change`, `memory_record`, `prior_recommendation_count`, `used_fallback`, and `logfire_trace_url` — frontend can bind against the locked shapes immediately.
- `frontend/` contains the working Babel-in-browser demo: `cafetwin.html`, `app-state.jsx`, `app-canvas.jsx`, `app-panels.jsx`, `cafe-iso.jsx`, `tweaks-panel.jsx`, `cafetwin.css`. **This is the MVP shell — keep it as-is and bind backend data into it.**
- `demo_data/` and `scripts/` have ownership READMEs.
- `docs/architecture/` contains short build notes for the MVP spine, project structure, and fixture contract.
- `.venv/` is a local ignored artifact; `.env.example` is the only env template that may be tracked.

## Demo Script (90 seconds)

1. *"POS tells operators what sold. CafeTwin shows why throughput stalled. Watch."* — page loads.
2. *"Real KPIs from the overhead video: 18 staff/customer crossings in this minute, queue obstructed for 41 seconds, table detour score 1.6."* — KPI cards populate from `kpi_windows.json`.
3. *"This is the existing cafe rendered as an isometric twin from the detected object inventory."* — iso twin renders for the baseline chip.
4. *"A Pydantic AI agent read the evidence pack and proposed one layout change — cited evidence IDs, expected KPI deltas, confidence, risk."* — recommendation ToolCall renders the real `LayoutChange`. Note the "Seen before" chip if prior runs exist.
5. **Click Apply.** *"Same twin, recommended layout — table cluster B shifts left. Estimated impact applies to the KPI cards on this chip."* — split-compare engages, target asset shifts, KPI deltas animate.
6. **Click Accept.** *"Feedback writes to MuBit; jsonl mirrors it as a hot fallback."* — Memories modal shows the new entry with a fresh `mubit_id` chip.
7. **Reload the demo.** *"The agent recalls the prior recommendation from MuBit — see the 'Seen before' chip."* — operational memory loop visible.
8. **Click Logfire.** *"One trace per run — evidence pack, optimization agent, validation, memory write, all spans visible."* — opens in a new tab.
9. *"Perception is fixture-backed for demo reliability. The agent, its typed output, validation, memory recall + write, and the trace are all real."*

## Why This Wins The Room

- **Real intelligence:** typed Pydantic AI agent + post-validation + evidence chain + memory + Logfire trace are all genuinely live and observable.
- **Honest framing:** we explicitly say what's fixture-backed vs live. No fake-AI demo theater. Decorative scenarios are decorative; the recommendation is real.
- **Sponsor-tool depth:** Pydantic AI is the spine, MuBit is the memory, Logfire is the audit trail, Render hosts it. Every sponsor tool is on the critical demo path.
- **Graceful degradation:** if Tier 1 doesn't land, MVP still ships. If the agent fails or keys are unset, the cached `LayoutChange` renders identically. The frontend never depends on a build step that could break at demo time.

## References

- Pydantic AI docs: https://pydantic.dev/docs/ai/overview/
- MuBit docs: https://docs.mubit.ai/
- Ultralytics tracking (Tier 1): https://docs.ultralytics.com/modes/track/
