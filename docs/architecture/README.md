# Architecture Notes

This folder holds short implementation notes that translate the plans into
buildable boundaries.

- `mvp_spine.md` defines the real backend path we build first.
- `project_structure.md` explains what each folder owns.
- `fixture_contract.md` summarizes the demo-data files the MVP expects.
- `vision_orchestrator_connection.md` describes the vision ↔ agent handshake — the typed contract Tier 1 perception hands the agent (relevant once live YOLO + KPI engine come online).

## Tier 1 architecture

This Mermaid diagram is the source-of-truth architecture visual for docs and the
README. It replaces the generated architecture PNG/HTML artifact.

```mermaid
flowchart LR
    video["Existing CCTV video files<br/>(real_cafe, ai_cafe_a)"]

    subgraph perception["Offline Tier 1 perception"]
        tracks["YOLOv8n + ByteTrack<br/>people tracks + annotated video"]
        objects["YOLOv8x static objects<br/>reviewed by ObjectReviewAgent"]
        kpi["KPI engine<br/>queue, detours, crossings, walk distance"]
    end

    evidence["Typed CafeEvidencePack<br/>zones + inventory + KPIs + pattern + prior memories"]

    subgraph agents["Pydantic AI reasoning"]
        pattern["PatternAgent<br/>OperationalPattern"]
        optimize["OptimizationAgent<br/>validated LayoutChange"]
    end

    ui["CafeTwin UI<br/>CCTV overlay + digital twin + recommendation card"]
    memory["MuBit + local jsonl<br/>recommendations and feedback memory"]
    trace["Logfire<br/>run trace and audit trail"]

    video --> tracks
    video --> objects
    tracks --> kpi
    objects --> evidence
    kpi --> evidence
    evidence --> pattern --> optimize --> ui
    ui -->|accept / reject| memory
    memory -->|prior decisions| evidence
    evidence -. spans .-> trace
    pattern -. spans .-> trace
    optimize -. spans .-> trace
```
