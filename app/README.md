# Backend App

This package owns the real MVP intelligence spine:

```text
demo_data fixtures
  -> evidence_pack.build()
  -> OptimizationAgent
  -> validate/fallback LayoutChange
  -> memory.write()
  -> FastAPI response
```

Keep the backend honest and small. If a feature does not help that path, it is
Tier 1 or Tier 2.
