# CafeTwin: Overview Plan

## One-Line Pitch

CafeTwin turns overhead cafe video into spatial operations intelligence: it detects movement, remembers repeated bottlenecks, and recommends layout changes with evidence and predicted KPI impact.

> POS tells you what sold. CafeTwin shows why throughput stalled.

## What We Are Building

For the hackathon, build a polished demo that analyzes one overhead cafe video and produces one credible recommendation:

> Move table cluster B 0.8m left to reduce staff/customer crossings, lower queue obstruction, and shorten staff walking paths.

The proof is not "AI says so." The proof is an evidence chain:

```text
video frame -> detections/tracks -> zones/KPIs -> MuBit memories
-> Pydantic AI recommendation -> before/after simulation -> Logfire trace
```

## Core Demo Loop

```mermaid
flowchart TD
    A[Overhead cafe video] --> B[Frame sampler]
    B --> C[Detection + segmentation + tracking]
    C --> D[Zone + KPI engine]
    D --> E[Observation compressor agent]
    E --> F[(MuBit memory)]
    F --> G[Pattern agent]
    G --> H[Optimization agent]
    H --> I[Recommendation with evidence]
    I --> J[2D before/after simulation]
    J --> K[Manager feedback]
    K --> F

    C --> L[(Postgres or JSON cache)]
    D --> L
    I --> L
    J --> L

    B -. spans .-> M[Logfire]
    C -. spans .-> M
    E -. Pydantic AI .-> M
    F -. memory calls .-> M
    H -. Pydantic AI .-> M
    J -. simulation .-> M
```

## Recommended API Stack

Use hosted APIs first where they save setup time. Keep local/cached fallback paths for the live demo.

| Need | Default | Fallback | Why |
|---|---|---|---|
| Detection | Roboflow Workflows object detection | Ultralytics YOLO locally | Fastest path to a working video pipeline. |
| Segmentation | Roboflow instance segmentation / SAM block | YOLO segmentation locally | Useful for table/chair masks and after-image edits. |
| Tracking | Roboflow ByteTrack / Byte Tracker | Ultralytics `model.track(..., tracker="bytetrack.yaml")` | Needed for trails, dwell, path crossings. |
| Zones | Hardcoded/manual polygons in app | Roboflow Polygon Zone / Time in Zone blocks | Hardcoded zones are fastest and most controllable. |
| KPIs | Custom deterministic Python | Roboflow Time in Zone / Line Counter blocks | KPI math should be explainable and reproducible. |
| Memory | MuBit SDK | Local JSON fallback | MuBit stores compressed operational observations. |
| Agents | Pydantic AI | Cached proposal fallback | Typed outputs make the recommendation trustworthy. |
| Simulation | Deterministic 2D map | Pre-rendered fallback image | This is the proof mechanism. |
| Inpainted after image | Replicate / Roboflow Stability AI Inpainting | Skip | Stretch polish, not core proof. |

## Sponsor Stack Fit

```mermaid
flowchart LR
    A[Roboflow / Vision API] --> B[Spatial KPIs]
    B --> C[Pydantic AI typed agents]
    C --> D[MuBit memory lanes]
    D --> E[Recommendation]
    E --> F[Simulation]
    A -. observability .-> G[Logfire]
    C -. observability .-> G
    D -. observability .-> G
    F -. observability .-> G
    H[Render] --> I[Hosted demo]
```

- **Pydantic AI:** typed `SceneObservation`, `OperationalPattern`, and `LayoutChange` outputs.
- **Logfire:** one trace from video analysis to recommendation and simulation.
- **MuBit:** operational memory across video windows and feedback.
- **Render:** hosted demo.

## MVP Scope

Build only the path needed for a convincing 3-minute demo:

1. Load a seeded overhead cafe video.
2. Show detections, masks/tracks, zones, trails, and heatmap.
3. Compute spatial KPIs.
4. Compress KPI windows into MuBit memories.
5. Use Pydantic AI to generate one typed layout recommendation.
6. Show before/after 2D simulation with KPI deltas.
7. Record feedback back into memory.
8. Show Logfire trace.

Cut from MVP:

- Live camera feed.
- POS integration.
- Full restaurant table-service complexity.
- True predictive world model.
- Generated video as a required feature.
- Custom model training.
- Real staff/customer identity.

## Product Architecture

```mermaid
flowchart TB
    subgraph UI[Dashboard]
        U1[Video with overlays]
        U2[KPI cards]
        U3[MuBit memory timeline]
        U4[Recommendation card]
        U5[Before/after simulation]
    end

    subgraph Vision[Vision Pipeline]
        V1[Frame sampler]
        V2[Roboflow Workflow API]
        V3[Cached detections JSON]
    end

    subgraph Reasoning[Reasoning Layer]
        R1[Deterministic KPI engine]
        R2[ObservationCompressorAgent]
        R3[PatternAgent]
        R4[OptimizationAgent]
    end

    subgraph Memory[Memory + Audit]
        M1[(Postgres / local cache)]
        M2[(MuBit)]
        M3[Logfire]
    end

    U1 --> V1 --> V2 --> V3 --> R1
    R1 --> R2 --> M2
    M2 --> R3 --> R4 --> U4
    R4 --> U5
    V3 --> M1
    R1 --> M1
    R4 --> M1
    V1 -. spans .-> M3
    R2 -. spans .-> M3
    R4 -. spans .-> M3
```

## MuBit Memory Lanes

| Lane | Contents |
|---|---|
| `location:demo:scene` | Compressed 10-second scene observations. |
| `location:demo:kpi` | Queue, walking, crossing, dwell, heatmap summaries. |
| `location:demo:patterns` | Repeated bottlenecks with evidence IDs. |
| `location:demo:recommendations` | Accepted/rejected recommendations and feedback. |
| `org:rules` | Hard constraints like minimum walkway width. |

MuBit should not store every raw frame or every raw bounding box. Store raw detections in Postgres/local JSON; store compressed operational memory in MuBit.

## Pydantic AI Agents

```mermaid
flowchart TD
    A[Detections + tracks + KPIs] --> B[ObservationCompressorAgent]
    B --> C[SceneObservation]
    C --> D[PatternAgent]
    D --> E[OperationalPattern]
    E --> F[OptimizationAgent]
    F --> G{Typed output}
    G --> H[LayoutChange]
    G --> I[StaffingAdjustment]
    G --> J[EquipmentRepositioning]
    G --> K[NoActionRecommended]
```

The main hackathon output should be `LayoutChange`.

Every recommendation must include:

- title
- rationale
- evidence IDs
- expected KPI deltas
- confidence
- risk
- simulation spec

## KPIs To Show

Use metrics judges can understand instantly:

- Staff walking distance.
- Staff/customer path crossings.
- Queue length proxy.
- Queue obstruction time.
- Congestion heatmap.
- Table cluster detour score.

Avoid "coffees served per staff member" in the MVP unless the video makes service events visually obvious. Use "service interactions completed" as a proxy instead.

## 24h Build Plan

| Time | Goal | Output |
|---|---|---|
| 0-4h | Visual proof | Video, zones, cached detections, trails. |
| 4-8h | KPI engine | Crossings, walking distance, queue proxy, heatmap. |
| 8-12h | Memory | MuBit observation writes and visible memory timeline. |
| 12-16h | Recommendation | Pydantic AI emits one typed `LayoutChange`. |
| 16-20h | Simulation | 2D before/after map and recomputed KPI deltas. |
| 20-24h | Polish | Logfire trace, Render deploy, fallback recording, pitch. |

## Demo Script

1. "Restaurants optimize from POS, but POS is blind to physics."
2. Show overhead video with tracks, zones, and heatmap.
3. Show KPI cards: crossings, walking distance, queue obstruction.
4. Show MuBit memory timeline.
5. Generate recommendation: "Move table cluster B 0.8m left."
6. Show evidence chain and expected deltas.
7. Click simulate and show before/after map.
8. Open Logfire trace: video -> KPI -> memory -> agent -> simulation.

## Why This Can Win

- **Build quality:** real visual pipeline plus typed agent output.
- **Insight:** spatial bottlenecks are invisible to POS analytics.
- **Viability:** cafes, QSR operators, franchisees, layout consultants, and ghost kitchens have clear ROI.
- **Execution:** the demo is visual, auditable, and sponsor tools are in the core path.

## References

- Roboflow object detection model block: https://docs.roboflow.com/workflow-blocks/run-a-model/object-detection-model
- Roboflow Byte Tracker: https://inference.roboflow.com/workflows/blocks/byte_tracker/
- Roboflow video workflows: https://inference.roboflow.com/workflows/video_processing/overview/
- Roboflow supported model types: https://docs.roboflow.com/deploy/supported-models
- Ultralytics tracking mode: https://docs.ultralytics.com/modes/track/
