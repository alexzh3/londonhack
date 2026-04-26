# Fixture Contract

The MVP starts with fixture-backed perception. The backend should fail clearly
when required files are missing.

## Runtime Inputs

Primary MVP session:

- `demo_data/sessions/ai_cafe_a/session.json`
- `demo_data/sessions/ai_cafe_a/zones.json`
- `demo_data/sessions/ai_cafe_a/object_inventory.json`
- `demo_data/sessions/ai_cafe_a/kpi_windows.json`
- `demo_data/sessions/ai_cafe_a/pattern_fixture.json`
- `demo_data/sessions/ai_cafe_a/recommendation.cached.json`

## Presentation Assets

- `cafe_videos/ai_generated_cctv.mp4`
- `demo_data/sessions/ai_cafe_a/frame.jpg` (optional representative frame)
- The MVP twin is rendered by `frontend/cafe-iso.jsx`; no PNG twin assets are required.

## Credibility / Tier 1 Assets

- `cafe_videos/real_cctv.mp4`
- `cafe_videos/ai_generated_cctv_round.mp4`
- `demo_data/sessions/<slug>/tracks.cached.json`
- `demo_data/sessions/<slug>/twin_observed.json`
- `demo_data/sessions/<slug>/twin_recommended.json`

## Runtime Output

- `mubit_fallback.jsonl`

The runtime output is local-only and ignored by git.
