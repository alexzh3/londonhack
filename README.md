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

1. Validate `demo_data/` fixtures.
2. Build the `CafeEvidencePack` loader.
3. Return and validate a cached `LayoutChange`.
4. Wire the live `OptimizationAgent`.
5. Add memory writes and Logfire spans.
6. Add the React four-click demo shell.
