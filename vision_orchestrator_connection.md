# Vision ↔ Agents Connection

## Purpose

Defines the handshake between the **vision/perception layer** (whatever produces the upstream artifacts) and the **agent layer** (Pydantic AI agents writing to memory). This document is tier-aware: the contract is the same in all tiers; only the producer changes.

```
MVP    : producer = hand-authored or precomputed fixtures
Tier 1 : producer = real YOLO + ByteTrack + KPI engine + (optional) PatternAgent
Tier 2 : producer = same as Tier 1; UI consumes additional twin layout JSON
```

The agent layer (`OptimizationAgent`, optional `EvidenceSummarizerAgent`, future `PatternAgent`) does **not change** between tiers. It only consumes a single typed Pydantic input: `CafeEvidencePack`.

## Build philosophy reminder

> MVP = real intelligence (typed agent + traced reasoning + memory),
>       mocked spectacle (prebaked twin images, fixture-backed perception).
> Tier 1 = realer perception. Tier 2 = richer spectacle.

In MVP, **vision is a stack of JSON files on disk**. There is no live YOLO at demo time. Tier 1 swaps the JSON for live output without touching any agent code.

## The handoff contract — `CafeEvidencePack`

The boundary is exactly one typed Pydantic model. Everything upstream produces the parts; everything downstream consumes the bundle:

```python
class CafeEvidencePack(BaseModel):
    session_id: UUID
    run_id: UUID
    zones: list[Zone]
    object_inventory: ObjectInventory
    kpi_windows: list[KPIReport]
    pattern: OperationalPattern
    org_rules: list[str]
```

`evidence_pack.build()` constructs it. In MVP it loads from `demo_data/`. In Tier 1 it loads from running pipelines plus `demo_data/zones.json` (zones stay fixture-authored — see §Zones below).

This is the **whole** vision↔agents contract. If a field isn't here, agents can't depend on it.

## Files in `demo_data/` (MVP source-of-truth)

| File | Schema | Used by MVP runtime? | Producer (MVP) | Producer (Tier 1) |
|---|---|---|---|---|
| `source_video.mp4` | binary | No (pitch only) | seeded clip | seeded clip |
| `annotated_before.mp4` | binary | Yes (UI plays it) | hand-rendered or scripted | ffmpeg + cached YOLO overlays |
| `tracks.cached.json` | `list[TrackPoint]` | No (shipped for credibility; consumed by Tier 1 KPI engine) | hand-authored | `scripts/run_yolo_offline.py` |
| `zones.json` | `list[Zone]` | Yes (loaded into pack) | hand-drawn polygons | hand-drawn polygons (no zone agent in MVP/Tier 1) |
| `object_inventory.json` | `ObjectInventory` | Yes (loaded into pack) | hand-authored | YOLO static-detection collapse + manual review |
| `kpi_windows.json` | `list[KPIReport]` | Yes (loaded into pack) | precomputed plausible numbers | live KPI engine output |
| `pattern_fixture.json` | `OperationalPattern` | Yes (loaded into pack as `pack.pattern`) | hand-authored, with stable `evidence_ids` | `PatternAgent` output OR deterministic builder |
| `recommendation.cached.json` | `LayoutChange` | Fallback path | hand-authored | hand-authored |
| `twin_observed.png` | image | Yes (UI image) | matplotlib/Figma | re-rendered from real layout |
| `twin_recommended.png` | image | Yes (UI image) | matplotlib/Figma | re-rendered from real layout |
| `twin_observed.json` | `TwinLayout` | No (Tier 2 only) | hand-authored | derived from inventory + zones |
| `twin_recommended.json` | `TwinLayout` | No (Tier 2 only) | hand-authored | apply `LayoutChange.simulation` to baseline |
| `mubit_fallback.jsonl` | append-only memory log | Yes (UI reads it) | created at runtime | created at runtime |

## Tier-by-tier production rules

### MVP (the only thing being built first)

- All upstream artifacts are hand-authored or trivially scripted.
- Numbers in `kpi_windows.json` and `pattern_fixture.json` must be plausible and internally consistent: the pattern's `evidence` IDs must equal the `memory_id`s of the KPI windows, and the pattern's `pattern_type` must be supportable by those KPI numbers (e.g. don't claim `queue_crossing` if `staff_customer_crossings` is 0).
- `LayoutChange.evidence_ids` returned by `OptimizationAgent` must be a subset of `pattern_fixture.evidence[*].memory_id`. This is enforced by `validate_layout_change()` in the agent layer; the fixture-author must ensure those IDs exist.
- The annotated video doesn't need to be sync-linked to the JSON. Judges won't frame-step it. As long as overlays are visually credible, ship it.
- No live YOLO, no live KPI, no live pattern detection.

### Tier 1 (only if MVP green and stable)

Upgrade producers; do **not** touch the agent layer or schemas.

- **Frame sampling:** `cv2.VideoCapture` at 2 fps for ~60s.
- **Detection:** Ultralytics YOLO (`yolo11n.pt`) on each sampled frame. Map COCO classes to our taxonomy (see §Class mapping).
- **Tracking:** `model.track(..., tracker="bytetrack.yaml", persist=True)`. Each TrackPoint = bbox center.
- **Role assignment:** A track is `staff` if ≥60% of its first 10s of points fall inside the `counter` zone polygon; otherwise `customer`. Stored once per `track_id`.
- **Object inventory:** Collapse static detections (table/chair/counter) into `ObjectInventory` once per session. Hand-correct counts and positions if YOLO output is messy.
- **KPI engine:** Deterministic Python (numpy + shapely or `cv2.pointPolygonTest`). Six KPIs per 20s window — see §KPI math below.
- **Pattern:** Either a real `PatternAgent` (Pydantic AI, `output_type=OperationalPattern`) over recent KPI windows, or a deterministic rule-based builder. Either is fine; both produce the same typed output.

Tier 1 adds these spans to the Logfire trace:

```
run
├── evidence_pack.build
│   ├── kpi_engine.compute_window  (xN windows)
│   ├── pattern_agent.run          (or pattern_builder.run if deterministic)
│   └── memory.write (kpi)
│   └── memory.write (inventory)
│   └── memory.write (pattern)
├── optimization_agent.run
├── layout_change.validate
└── memory.write (recommendation)
```

### Tier 2 (only if Tier 1 green)

Vision contract unchanged. The frontend additionally consumes `twin_observed.json` and `twin_recommended.json` (`TwinLayout` schema in `agent_plan.md` §Tier 2 hooks) to render an R3F scene with box prefabs. No backend changes required.

## Zones (MVP and Tier 1: hand-drawn)

`ZoneCalibrationAgent` is **cut from MVP and Tier 1**. Zones are hand-drawn polygons in `zones.json` for:

- `counter`
- `queue`
- `pickup`
- `seating`
- `staff_path`
- `entrance`

Rationale: zones are operational concepts that judges won't watch the agent draft live. Hand-authoring takes 5 minutes; agentic drafting eats 2–4h and adds a failure mode. If we're showing off agent work, the work that matters to the demo is the recommendation, not the zone polygons.

A `ZoneCalibrationAgent` may be added in a future Tier 3, never in this hackathon.

## Class mapping (Tier 1 reference)

Used by `scripts/run_yolo_offline.py` to translate COCO outputs into our cafe taxonomy:

| Our class | YOLO source | Notes |
|---|---|---|
| `person_staff` | `person` + role heuristic (counter dwell) | role decided post-hoc per track |
| `person_customer` | `person` (default) | |
| `table` | `dining table` | |
| `chair` | `chair` | |
| `counter` zone, `pickup` zone, `queue` zone | not detected — read from `zones.json` polygons (`Zone.kind`) | |

Bounding-box centers are sufficient for KPIs. Segmentation masks are non-goals for all tiers in this build.

## KPI math (Tier 1 reference)

Per 20s window over cached tracks + zones:

| KPI | Computation |
|---|---|
| `staff_walk_distance_px` | Σ Euclidean distance between consecutive TrackPoints for `staff` tracks |
| `staff_customer_crossings` | count of (staff segment) × (customer segment) intersections in same window |
| `queue_length_peak` | max count of `customer` points inside `queue` polygon across frames in the window |
| `queue_obstruction_seconds` | seconds where a staff segment intersects the queue polygon (or table mask overlaps it, if Tier 1.5 segmentation is added) |
| `congestion_score` | normalized density in counter+queue+pickup region, 0..1 |
| `table_detour_score` | actual staff path length / straight-line counter→nearest-seating distance |

Window of 20s is chosen so a single bottleneck shows as a peak rather than averaging out, and three windows give a `PatternAgent` enough repetition to call `severity="high"` honestly.

## What the vision/perception layer does NOT produce

To keep the boundary clean, vision artifacts must not contain:

- Natural-language summaries (job of `EvidenceSummarizerAgent`).
- Pattern labels like `queue_crossing` (job of `PatternAgent` in Tier 1; fixture-authored in MVP).
- Recommendations or confidence scores (job of `OptimizationAgent`).
- Furniture move suggestions (job of `OptimizationAgent`; the simulator previews the selected suggestion).
- Business conclusions from object counts ("too many chairs"). Job of agents.
- MuBit writes (job of `app/memory.py`; agents trigger writes, vision does not).

If a contributor is tempted to add a field that isn't in `Detection`, `TrackPoint`, `SceneObject`, `ObjectInventory`, `Zone`, `KPIReport`, or `OperationalPattern`, that's a signal the work belongs on the agent side or the UI side — not in vision.

## Acceptance test for the vision layer

In any tier, the vision/perception layer is "done" when:

```python
pack: CafeEvidencePack = evidence_pack.build()
assert pack.zones                              # at least one zone of each operational kind
assert pack.object_inventory.counts_by_kind["table"] >= 1
assert len(pack.kpi_windows) >= 3
assert pack.pattern.evidence                   # has at least one EvidenceRef
ids = {ref.memory_id for ref in pack.pattern.evidence}
assert all(w.memory_id in ids for w in pack.kpi_windows[:3])  # IDs line up
```

If those assertions pass, `OptimizationAgent` will run successfully end-to-end. The mock data in MVP is constructed to pass these assertions; Tier 1 just produces a fresh pack that also passes them.

## Fallback story

The demo never depends on live vision. In any tier:

- Cached/fixture JSON is always on disk.
- An env var `RUN_LIVE_VISION=1` (Tier 1) opts into live YOLO; default behavior is to read fixtures.
- If anything in the perception layer fails, the cached files are served instead.
- The agent layer cannot tell the difference and behaves identically.

This is also the reason zones stay hand-drawn even in Tier 1: zone calibration would re-introduce a failure mode for no demo gain.

## References

- Ultralytics tracking: https://docs.ultralytics.com/modes/track/
- Ultralytics Python: https://docs.ultralytics.com/usage/python/
- OpenCV video I/O: https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html
- Pydantic AI: https://pydantic.dev/docs/ai/overview/
- MuBit: https://docs.mubit.ai/
