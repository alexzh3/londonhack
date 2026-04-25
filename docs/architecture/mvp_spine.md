# MVP Spine

The MVP is not a simulator first. It is a real reasoning loop over fixture-backed
evidence.

```text
fixtures
  -> CafeEvidencePack
  -> OptimizationAgent
  -> LayoutChange validation
  -> memory write
  -> React presentation
```

## Must Be Real

- Pydantic schemas for evidence and outputs.
- At least one live Pydantic AI agent.
- Post-validation of agent output.
- Local JSONL memory write.
- Best-effort MuBit recall/write.
- Logfire spans around the backend path.

## Can Be Mocked

- Annotated video.
- KPI and object-count inputs.
- Twin before/after imagery.
- Flow-node animation.
- Recommendation fallback.

## First Implementation Slice

1. Make `demo_data/` validate.
2. Build `CafeEvidencePack`.
3. Return cached `LayoutChange`.
4. Replace cached path with live `OptimizationAgent`.
5. Add memory and Logfire.
