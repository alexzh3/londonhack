# Scripts

One-shot utilities for the CafeTwin / SimCafe Tier 1 build. All scripts assume
they are run from the repo root or from anywhere — they `cd` to the repo root
themselves.

## Local dev / testing

| Script | Purpose |
|---|---|
| `setup.sh` | First-time bootstrap: `uv venv`, `uv sync`, fail loudly if `.env` is missing. |
| `dev.sh` | Run backend (uvicorn :8000) + frontend (`python -m http.server` :5500) in parallel with a clean Ctrl-C teardown. |
| `test.sh` | Run `pytest` and `ruff check app tests`. |
| `smoke.sh` | Curl-validate `/api/sessions`, `/api/state`, `/api/run`, `/api/feedback`, `/api/memories` against a running backend. Default target `http://127.0.0.1:8000`; override with `SMOKE_BASE=...`. |

Typical first-time flow:

```bash
./scripts/setup.sh         # bootstrap venv + deps
./scripts/test.sh          # confirm backend is green
./scripts/dev.sh           # start backend + frontend, open the URL it prints
# ...in another terminal:
./scripts/smoke.sh         # verify response shapes
```

The cached perception artifacts under `demo_data/sessions/` are enough
for the dev server — you don't need to run any vision scripts to see
the live agent path. See **Rebuilding perception artifacts** below if
you want to regenerate them from the source video.

## Rebuilding perception artifacts

The five vision-pipeline scripts live under `scripts/vision/`. The cached
`tracks.cached.json`, `object_detections.cached.json`,
`object_review.cached.json`, `object_detections.reviewed.cached.json`,
`annotated_before.mp4`, and `annotated_before.web.mp4` files in
`demo_data/sessions/<slug>/` are committed so the demo runs out of the
box. To regenerate them from the source CCTV videos:

| Script | Stage | Outputs (per session) |
|---|---|---|
| `run_yolo_offline.py` | Tier 1B people-tracking pass — YOLOv8n + ByteTrack | `tracks.cached.json` (+ a basic `annotated_before.mp4` with person boxes only). |
| `detect_layout_objects.py` | Tier 1B static-furniture pass — YOLOv8x over the representative frame plus sampled video frames, with duplicate-detection clustering | `object_detections.cached.json`. |
| `review_layout_objects_agent.py` | Pydantic AI review/merge over the detector cache | `object_review.cached.json` plus the stricter `object_detections.reviewed.cached.json`. |
| `render_rich_annotated_video.py` | Tier 1D enrichment pass: re-render `annotated_before.mp4` with **both** person tracks and reviewed static-object boxes overlaid | `annotated_before.mp4` (overwritten). |
| `transcode_annotated_for_web.sh` | Tier 1D web transcode: Chromium's HTML5 `<video>` rejects the `cv2.VideoWriter` default `mp4v` codec, so this re-encodes to H.264 | `annotated_before.web.mp4`. |

Full rebuild from scratch (both shipped sessions):

```bash
uv run scripts/vision/run_yolo_offline.py --session ai_cafe_a --vid-stride 2
uv run scripts/vision/run_yolo_offline.py --session real_cafe --vid-stride 3
uv run scripts/vision/detect_layout_objects.py --session ai_cafe_a
uv run scripts/vision/detect_layout_objects.py --session real_cafe
uv run scripts/vision/review_layout_objects_agent.py --session ai_cafe_a
uv run scripts/vision/review_layout_objects_agent.py --session real_cafe
uv run scripts/vision/render_rich_annotated_video.py --session ai_cafe_a
uv run scripts/vision/render_rich_annotated_video.py --session real_cafe
./scripts/vision/transcode_annotated_for_web.sh        # all sessions
```

`./scripts/vision/transcode_annotated_for_web.sh <session>` re-encodes a
single session if you only changed one. Running the script with no args
walks every session.

### Local heavy artifacts (gitignored)

- `models/ultralytics/` — active YOLO `.pt` weights used by the tracking and static-detection scripts.
- `images/` — generated screenshots and annotated still-image outputs.
- `demo_data/sessions/<slug>/annotated_before.mp4` and `annotated_before.web.mp4` are gitignored alongside the smaller cached JSON.

Ad-hoc benchmark scripts, the optional Moondream generator, and
benchmark-only model weights were removed after archiving the results;
see [`docs/vision_benchmarks.md`](../docs/vision_benchmarks.md) for the
YOLO / RT-DETR / YOLO11x / Moondream comparisons.

## Deploy

| Script | Purpose |
|---|---|
| `deploy_render.sh` | Walk through Render Blueprint setup; trigger a redeploy via `RENDER_DEPLOY_HOOK` if set; smoke-test the live URL with `--smoke`. |
| `deploy_vercel.sh` | Generate `frontend/vercel.json` (rewrites `/api/*`, `/demo_data/*`, and `/cafe_videos/*` to `CAFETWIN_RENDER_URL`) and run `vercel deploy --prod` from `frontend/`. |

Typical first-time deploy:

```bash
# 1) Push to GitHub.
git push

# 2) Backend on Render.
./scripts/deploy_render.sh
# Follow the printed steps. After Render assigns a URL, set:
#   CAFETWIN_RENDER_URL=https://cafetwin-backend-tier1.onrender.com
# in your local .env.

# 3) Smoke-test the live backend.
./scripts/deploy_render.sh --smoke

# 4) Frontend on Vercel.
./scripts/deploy_vercel.sh

# 5) Copy the printed Vercel URL — that is the demo URL.
```

Current hosted split:

| Surface | URL |
|---|---|
| Frontend (Vercel project `frontend-tier1`) | <https://frontend-tier1.vercel.app/cafetwin.html> |
| Backend (Render service `cafetwin-backend-tier1`) | <https://cafetwin-backend-tier1.onrender.com> |

Subsequent redeploys:

```bash
git push                                # Render redeploys automatically (or:)
RENDER_DEPLOY_HOOK=... ./scripts/deploy_render.sh   # explicit deploy hook
./scripts/deploy_vercel.sh              # frontend re-push
```

Both deploy scripts read `CAFETWIN_RENDER_URL`, `RENDER_DEPLOY_HOOK`, etc.
from `.env` if not set in the calling shell. `deploy_vercel.sh` only needs
`CAFETWIN_RENDER_URL`; passing it inline keeps local backend/API secrets out of
the Vercel CLI environment:

```bash
CAFETWIN_RENDER_URL=https://cafetwin-backend-tier1.onrender.com ./scripts/deploy_vercel.sh
```
