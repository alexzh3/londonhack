# Scripts

One-shot utilities for the CafeTwin / SimCafe MVP. All scripts assume they are
run from the repo root or from anywhere — they `cd` to the repo root themselves.

## Local dev / testing

| Script | Purpose |
|---|---|
| `setup.sh` | First-time bootstrap: `uv venv`, `uv sync`, fail loudly if `.env` is missing. |
| `dev.sh` | Run backend (uvicorn :8000) + frontend (`python -m http.server` :5500) in parallel with a clean Ctrl-C teardown. |
| `test.sh` | Run `pytest` and `ruff check app tests`. |
| `smoke.sh` | Curl-validate `/api/sessions`, `/api/state`, `/api/run`, `/api/feedback`, `/api/memories` against a running backend. Default target `http://127.0.0.1:8000`; override with `SMOKE_BASE=...`. |

Typical first-time flow:

```bash
uv run scripts/run_yolo_offline.py --session ai_cafe_a --vid-stride 2
./scripts/setup.sh         # bootstrap venv + deps
./scripts/test.sh          # confirm backend is green
./scripts/dev.sh           # start backend + frontend, open the URL it prints
# ...in another terminal:
./scripts/smoke.sh         # verify response shapes
```

## Deploy

| Script | Purpose |
|---|---|
| `deploy_render.sh` | Walk through Render Blueprint setup; trigger a redeploy via `RENDER_DEPLOY_HOOK` if set; smoke-test the live URL with `--smoke`. |
| `deploy_vercel.sh` | Generate `frontend/vercel.json` (rewrites `/api/*` to `CAFETWIN_RENDER_URL`) and run `vercel deploy --prod` from `frontend/`. |

Typical first-time deploy:

```bash
# 1) Push to GitHub.
git push

# 2) Backend on Render.
./scripts/deploy_render.sh
# Follow the printed steps. After Render assigns a URL, set:
#   CAFETWIN_RENDER_URL=https://cafetwin-backend.onrender.com
# in your local .env.

# 3) Smoke-test the live backend.
./scripts/deploy_render.sh --smoke

# 4) Frontend on Vercel.
./scripts/deploy_vercel.sh

# 5) Copy the printed Vercel URL — that is the demo URL.
```

Subsequent redeploys:

```bash
git push                                # Render redeploys automatically (or:)
RENDER_DEPLOY_HOOK=... ./scripts/deploy_render.sh   # explicit deploy hook
./scripts/deploy_vercel.sh              # frontend re-push
```

Both deploy scripts read `CAFETWIN_RENDER_URL`, `RENDER_DEPLOY_HOOK`, etc.
from `.env` if not set in the calling shell.

## Tier 1 / Tier 2

MVP scripts generate or validate fixture artifacts. Tier 1 adds YOLO / ByteTrack
and KPI-engine scripts behind the same `demo_data/` contracts.

- `build_fixtures.py` — one-shot per session: ffmpeg representative-frame extract + hand-author scaffolding.
- `run_yolo_offline.py` — Tier 1B: run YOLOv8n + ByteTrack offline and produce `tracks.cached.json` plus `annotated_before.mp4` per session.
- `detect_layout_objects.py` — Tier 1B static layout pass: run high-accuracy YOLOv8x over the representative frame plus sampled video frames, aggregate duplicate furniture detections, and produce `object_detections.cached.json` per session.
- `transcode_annotated_for_web.sh` — Tier 1D: transcode `annotated_before.mp4` (cv2 default `mp4v` codec, browser-incompatible) to `annotated_before.web.mp4` (H.264) so the frontend's real CCTV pane can play it.

```bash
uv run scripts/run_yolo_offline.py --session real_cafe --vid-stride 3
uv run scripts/detect_layout_objects.py --session ai_cafe_a
uv run scripts/detect_layout_objects.py --session real_cafe
./scripts/transcode_annotated_for_web.sh
```
