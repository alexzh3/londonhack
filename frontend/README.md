# Frontend

The MVP frontend is the existing `cafetwin.html` + JSX shell over the real backend spine.

Build only the locked MVP flow first:

1. Page load: `useBackend("ai_cafe_a")` calls `/api/sessions`, `/api/state`, then `/api/run`.
2. Click `recommended` / Apply: frontend-only split compare and KPI delta animation.
3. Accept / Reject: POST `/api/feedback`.

The twin is the existing SVG iso renderer in MVP. No PNG crossfade, no Vite port,
and no SceneBuilderAgent until Tier 2. The demo scenario rail stays visible; only
the `recommended` chip is agent-backed.
