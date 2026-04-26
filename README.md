# CafeTwin / SimCafe

Hackathon MVP for turning overhead cafe video evidence into typed layout
recommendations.

## Setup

```bash
uv venv
source .venv/bin/activate
uv sync
```

Real secrets belong in `.env`, which is ignored. Use `.env.example` only as a
placeholder template.

## MVP Build Order

1. Done: validate `demo_data/sessions/ai_cafe_a/` fixtures from `cafe_videos/ai_generated_cctv.mp4`.
2. Done: build the `CafeEvidencePack` loader.
3. Done: return and validate a cached `LayoutChange`.
4. In progress: wire the live `OptimizationAgent`.
5. In progress: add memory writes and Logfire spans.
6. Next: bind the existing `frontend/cafetwin.html` JSX shell to the backend flow.

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check app tests
```
