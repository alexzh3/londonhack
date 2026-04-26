# Demo Data

This folder is the MVP perception source of truth.

Required MVP artifacts:

- `sessions/ai_cafe_a/session.json`
- `sessions/ai_cafe_a/zones.json`
- `sessions/ai_cafe_a/object_inventory.json`
- `sessions/ai_cafe_a/kpi_windows.json`
- `sessions/ai_cafe_a/pattern_fixture.json`
- `sessions/ai_cafe_a/recommendation.cached.json`
- `sessions/ai_cafe_a/frame.jpg`

Tier 1 / Tier 2 artifacts may add `tracks.cached.json`, `twin_observed.json`,
and `twin_recommended.json` under each session directory. They are not required
for the MVP backend contract.

Runtime memory is appended to `mubit_fallback.jsonl`; that file is intentionally
ignored by git.
