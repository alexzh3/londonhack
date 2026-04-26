# CafeTwin / SimCafe

Hackathon MVP that turns overhead cafe video evidence into typed layout
recommendations. One real Pydantic AI agent emits a validated `LayoutChange`,
memory recall surfaces a "seen before" chip, Logfire records the trace, and
an existing Babel-in-browser JSX demo binds it all into a clickable UI.

> POS tells operators what sold. CafeTwin shows why throughput stalled.

For architecture detail see [`overview_plan.md`](overview_plan.md) (high
level) and [`agent_plan.md`](agent_plan.md) (engineering). Current build
state is summarised in `overview_plan.md` § Implementation Status.

## Quick start (local)

```bash
git clone <this-repo>
cd <this-repo>

cp .env.example .env       # then edit .env (see "Environment" below)

./scripts/setup.sh         # uv venv + uv sync + .env sanity check
./scripts/test.sh          # pytest + ruff
./scripts/dev.sh           # backend on :8000 + frontend on :5500
```

Open <http://127.0.0.1:5500/cafetwin.html>. The page calls `/api/state` then
`/api/run` on mount; the agent flow lights up from real backend stages, the
recommendation card renders the live `LayoutChange`, and the Logfire button
opens the trace for that run.

To open the Tier 1A real-video fixture session, use
<http://127.0.0.1:5500/cafetwin.html?session=real_cafe>.

Tier 1B real-video tracking artifacts are generated offline:

```bash
uv run scripts/run_yolo_offline.py --session ai_cafe_a --vid-stride 2
uv run scripts/run_yolo_offline.py --session real_cafe --vid-stride 3
```

This writes `tracks.cached.json` and `annotated_before.mp4` under each session.
The fake `ai_cafe_a` video currently gives the cleanest detection overlay.

## Prerequisites

- Python 3.10+ (3.12 recommended; 3.13 pinned in `.python-version`).
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) for venv +
  dependency management.
- Optional for the live agent path:
  - A Pydantic AI Gateway API key (`PYDANTIC_AI_GATEWAY_API_KEY`) **or** an
    `ANTHROPIC_API_KEY`.
  - A Logfire write token (`LOGFIRE_TOKEN`) + project URL
    (`LOGFIRE_PROJECT_URL`) for trace links.

The cached-fallback demo path needs none of those — it ships fully offline
on the demo fixtures.

## Environment

`.env.example` is the template. Real values go in `.env` (gitignored).

| Var | Purpose |
|---|---|
| `PYDANTIC_AI_GATEWAY_API_KEY` | Live `OptimizationAgent` via Pydantic AI Gateway (preferred). |
| `ANTHROPIC_API_KEY` | Live `OptimizationAgent` via direct Anthropic. Used if Gateway key is absent. |
| `CAFETWIN_OPTIMIZATION_MODEL` | e.g. `gateway/anthropic:claude-sonnet-4-6` (default) or `anthropic:claude-sonnet-4-5`. |
| `CAFETWIN_FORCE_FALLBACK=1` | Skip the live agent; always return the cached recommendation. Useful for offline demos. |
| `LOGFIRE_TOKEN` + `LOGFIRE_PROJECT_URL` | Real Logfire spans + clickable trace URL on the top bar. |
| `MUBIT_API_KEY` | Enables MuBit primary memory writes/recall; jsonl remains the always-on fallback. |
| `CAFETWIN_RENDER_URL` | Set after Render deploy; consumed by `scripts/deploy_vercel.sh`. |
| `RENDER_DEPLOY_HOOK` | Optional; lets `scripts/deploy_render.sh` trigger redeploys without the dashboard. |

## Demo modes

The page works in three honest modes depending on which keys are populated:

| Mode | What's live | When to use |
|---|---|---|
| **Cached fallback** (`CAFETWIN_FORCE_FALLBACK=1`) | Stages, KPIs, `LayoutChange`, memory writes — all real, but the LLM is not called. | Offline demos. Works without any external service. |
| **Live agent, no Logfire** (set `*_API_KEY`, leave `LOGFIRE_TOKEN` empty) | Full pipeline + real Pydantic AI call. Top-bar Logfire button is greyed. | Local dev when you have an LLM key but don't want to send traces. |
| **Full** (all keys set) | Full pipeline + live agent + clickable Logfire trace per `/api/run`. | Pitch demo. |

Reload after **Accept** in any mode to see the "seen N× before" chip — that's
the real memory recall path against MuBit when configured, with
`demo_data/mubit_fallback.jsonl` as the local mirror/fallback.

## Deploy

The recommended split is **Vercel for the static frontend + Render for the
FastAPI backend**. Vercel rewrites `/api/*` to the Render origin so the
deployed frontend stays same-origin (no CORS preflight, no hardcoded API
URL in `cafetwin.html`).

### 1. Backend on Render

`render.yaml` at the repo root declares the web service.

```bash
git push                          # Render auto-deploys when connected.
./scripts/deploy_render.sh        # one-time walkthrough; prints next steps.
```

First-time:

1. Push the repo (with `render.yaml`) to GitHub.
2. <https://dashboard.render.com> → **New** → **Blueprint** → connect repo.
3. In the service Environment tab, set the secrets listed in `render.yaml`
   (`LOGFIRE_TOKEN`, `LOGFIRE_PROJECT_URL`, `ANTHROPIC_API_KEY` /
   `PYDANTIC_AI_GATEWAY_API_KEY`, etc.).
4. After Render assigns a public URL, set it in your local `.env`:

   ```bash
   CAFETWIN_RENDER_URL=https://cafetwin-backend.onrender.com
   ```
5. Smoke-test:

   ```bash
   ./scripts/deploy_render.sh --smoke
   ```

Optional: copy the deploy hook from **Render → cafetwin-backend → Settings →
Deploy Hook** into `.env` as `RENDER_DEPLOY_HOOK=...` so subsequent runs of
`./scripts/deploy_render.sh` trigger a redeploy without the dashboard.

### 2. Frontend on Vercel

```bash
./scripts/deploy_vercel.sh
```

This generates `frontend/vercel.json` with a `/api/*` rewrite pointing at
`CAFETWIN_RENDER_URL`, then runs `vercel deploy --prod` from the `frontend/`
directory. Prereqs: a Vercel account, `vercel login` once. The script falls
back to `npx vercel@latest` if the CLI is not installed globally.

### Why this split

Vercel's CDN is built for flat HTML + assets (cafetwin.html loads
Babel-standalone in-browser, no build step). Render's long-lived web service
fits a uvicorn process that wants Logfire instrumented once at startup and
local file writes for the jsonl memory fallback. The plan's
[overview](overview_plan.md#stack) goes deeper on the trade-off.

#### Render-only alternative

Both pieces can run on Render — backend as a web service, frontend as a
static site. Single dashboard, slightly slower frontend cold load. Skip the
Vercel script and create a second Render service of type "Static Site"
serving the `frontend/` directory.

## Project layout

```
app/                  FastAPI backend (routes, agents, memory, logfire setup)
  schemas.py          Strict Pydantic models — the source of truth
  agents/             Pydantic AI agents (OptimizationAgent today)
  api/                FastAPI app + 6 MVP routes
demo_data/sessions/   Per-session fixture packs (ai_cafe_a is MVP)
cafe_videos/          Source CCTV-style clips
frontend/             Babel-in-browser JSX demo + api.js fetch wrappers
scripts/              setup / dev / test / smoke / deploy_*.sh
tests/                pytest suite + conftest blanking secret env
.agents/handoff.md    Multi-agent coordination sticky note (gitignored)
agent_plan.md         Engineering plan (deep)
overview_plan.md      Build philosophy + tier ladder + stack (high-level)
render.yaml           Render Blueprint config for the backend
```

## Verification

`scripts/test.sh` runs `pytest` and `ruff check app tests`. `scripts/smoke.sh`
hits a running backend (default `http://127.0.0.1:8000`; override with
`SMOKE_BASE`) and validates the response shape of every MVP route.

## See also

- [`overview_plan.md`](overview_plan.md) — build philosophy, tier ladder, deploy stack, demo script.
- [`agent_plan.md`](agent_plan.md) — module-level engineering plan, schemas, span tree.
- [`AGENTS.md`](AGENTS.md) — secrets policy and skill registry.
- `.agents/handoff.md` — current state across coding agents (local only, gitignored).
