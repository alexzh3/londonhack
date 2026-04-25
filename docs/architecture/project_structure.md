# Project Structure

```text
app/                  Real Python backend code
app/api/              FastAPI routes
app/agents/           Pydantic AI agents
demo_data/            Fixture-backed perception artifacts
docs/architecture/    Short implementation notes
frontend/             React MVP shell
scripts/              Fixture generation and Tier 1 utilities
```

## Ownership Rules

- `demo_data/` produces facts, not recommendations.
- `app/evidence_pack.py` is the only bridge from fixtures into agent inputs.
- `app/agents/` owns recommendation reasoning.
- `app/memory.py` owns both MuBit and JSONL fallback behavior.
- `frontend/` renders backend state; it should not infer business logic from text.
