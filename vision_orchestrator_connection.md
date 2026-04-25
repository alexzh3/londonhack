# Vision ↔ Agents Connection

## Purpose

This document defines the handshake between the **vision pipeline** (OpenCV + Ultralytics YOLO + tracker) and the **agent pipeline** (Pydantic AI agents writing to MuBit memory). It exists so the vision and agent tracks can be built in parallel without coordination, and so the mock data in `demo_data/` has a clear real-world counterpart.

The short version:

```text
video frames
  -> YOLO detections (per frame)
  -> ByteTrack track IDs (across frames)
  -> ZoneCalibrationAgent drafts operational zones once per video
  -> deterministic zone assignment (geometric overlay)
  -> KPI engine (deterministic window stats)
  -> KPIReport (+ SceneObservation) -> Pydantic AI agents -> MuBit
```

Mock data in `demo_data/` is a frozen snapshot of the right side of that pipeline (`tracks.cached.json`, `kpi_windows.json`). Replace the mock data with real vision output and the agents keep working unchanged.

---

## What the vision layer must produce

The pipeline boundary is **five structured artifacts**. The vision layer produces detections/tracks; the zone calibration agent produces zones; the KPI engine consumes those artifacts and emits window summaries:


| Output                   | Pydantic schema | File it lands in                   | Produced by                                        |
| ------------------------ | --------------- | ---------------------------------- | -------------------------------------------------- |
| Per-frame detections     | `Detection`     | `demo_data/detections.cached.json` | YOLO                                               |
| Per-frame track points   | `TrackPoint`    | `demo_data/tracks.cached.json`     | YOLO + ByteTrack                                   |
| Zone draft metadata      | `ZoneDraft`     | `demo_data/zone_draft.cached.json` | ZoneCalibrationAgent                               |
| Spatial zones            | `Zone`          | `demo_data/zones.json`             | ZoneCalibrationAgent, with fixture/manual fallback |
| Per-window KPI snapshots | `KPIReport`     | `demo_data/kpi_windows.json`       | KPI engine (derived from the above)                |


Everything downstream (observations, patterns, recommendations) is generated from these artifacts. If a field isn't in one of these schemas, downstream code cannot depend on it, so vision should not waste time producing it.

---

## Stage-by-stage: what to ingest and why

### 1. Frame sampling — `cv2.VideoCapture`

**What:** Decode the overhead cafe video at a fixed sample rate (target 2 fps for MVP; the demo video is ~60 s → ~120 frames).

**Why this rate:** Staff walking speed in a cafe is ~1 m/s. At 2 fps and ~60 px/m, a person moves ~30 px between frames — large enough for tracker association, small enough that a queue-zone crossing can't happen between samples without showing up in at least one frame.

**What the agents use this for:** Nothing directly. But `KPIReport.frames_sampled` and the 20 s window boundaries depend on it, so the sample rate must be stable across the whole run.

### 2. Detection — Ultralytics YOLO

**What:** Run a YOLO model on each sampled frame. Map COCO classes to our cafe taxonomy:


| Our class                   | YOLO source                                             | Purpose in agents                                 |
| --------------------------- | ------------------------------------------------------- | ------------------------------------------------- |
| `person_staff`              | `person` + heuristic (apron color / near-counter dwell) | Who generates walking distance and crossings      |
| `person_customer`           | `person` (default)                                      | Who forms the queue                               |
| `table`                     | `dining table`                                          | Obstacle map for detours; target of layout change |
| `chair`                     | `chair`                                                 | Obstacle map; seating cluster assignment          |
| `counter`                   | static polygon (not detected)                           | Zone anchor                                       |
| `pickup_area`, `queue_area` | static polygons                                         | Zone anchors                                      |


**Why staff vs. customer matters:** The whole thesis — "staff detours cost throughput" — depends on distinguishing the two. Every KPI that matters (crossings, walking distance, table detour) is a function of *staff* tracks against *customer* tracks or zones. If we can't split the two roles, the recommendation collapses into generic "it's busy."

**MVP heuristic for role assignment:** A `person` track is labeled `staff` if ≥60% of its points fall inside the counter zone in the first 10 s; otherwise `customer`. Stored once per `track_id` in `TrackPoint.role`.

**Why MVP ignores segmentation masks:** Bounding box centers plus agent-drafted or fixture zone polygons are sufficient for all six KPIs. Segmentation is only worth the latency if we later need precise obstacle maps for the simulator. Not blocking.

### 3. Tracking — Ultralytics ByteTrack (`model.track(persist=True)`)

**What:** Assign a persistent `track_id` to each detection across frames, emit a `TrackPoint` per (track_id, frame). Each TrackPoint has `(x, y)` = bbox center.

**Why tracking is non-negotiable:** Without stable track IDs, you cannot compute:

- **walking distance** (needs ordered points per track),
- **path crossings** (needs segments, which need consecutive points),
- **dwell / queue length over time** (needs the same person to stay the same ID while in a zone).

Single-frame detections alone tell you *how many people* are in the cafe. Tracking tells you *how they move*, which is the whole product.

**Why ByteTrack specifically:** It's the default Ultralytics tracker, handles short occlusions (customers walking behind tables), and requires zero extra setup. If it loses a track for 1–2 frames we can interpolate in the KPI engine; anything more is a new track ID and that's fine for aggregate KPIs.

### 4. Zone calibration — agent-assisted, then frozen

**What:** A `ZoneCalibrationAgent` runs once per video/session. It looks at a representative frame, static detections/furniture, track heatmaps, and any existing fixture zones, then drafts operational polygons:

- `counter`
- `queue`
- `pickup`
- `seating`
- `staff_path`
- `entrance`

It outputs `ZoneDraft`, which contains `list[Zone]`, confidence, rationale, assumptions, and `needs_review`.

**Why an agent helps:** Zones are operational concepts ("where the queue forms," "where staff should walk"), not pure visual classes. YOLO can detect people/tables/chairs, but it will not know which empty corridor is the ideal staff path. An agent can use the spatial layout + track density to propose a semantic map quickly.

**What stays deterministic:** Once zones are drafted/approved, every `TrackPoint` is assigned by geometry, not by the LLM:

```text
zone_id = first Zone whose polygon contains (x, y)
```

Implementation can use `cv2.pointPolygonTest`. The KPI engine must never ask an agent whether an individual point is "in the queue"; that would be slow, expensive, and non-reproducible.

**Fallback:** For the live demo, keep `demo_data/zones.json` as a frozen fixture. If the agent draft is bad or slow, use the fixture. The UI can still show the agent-assisted calibration as a staged step.

**Agent-side relevance:** `SceneObservation.affected_zones` and `OperationalPattern.affected_zones` both derive from zone assignment. Without zones, the agent can only say "something was bad"; with zones, it can say "staff crossed the queue zone 18 times," which is evidence.

### 5. KPI engine — deterministic Python

**What:** Aggregate detections + tracks + zones into a `KPIReport` per time window (default 20 s). Six deterministic metrics, no ML:


| KPI                         | How it's computed                                                                           | Why a cafe operator cares                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `staff_walk_distance_px`    | Σ Euclidean distance between consecutive TrackPoints for staff                              | Staff labor is the #1 cost line. Wasted motion = wasted payroll.                      |
| `staff_customer_crossings`  | Count of (staff segment) × (customer segment) intersections in same window                  | Crossings are physical friction: dropped orders, spilled drinks, longer service time. |
| `queue_length_peak` / `avg` | Count of customer TrackPoints inside `queue` zone per frame; peak/avg over window           | Queue length is the classic throughput bottleneck; directly predicts abandonment.     |
| `queue_obstruction_seconds` | Seconds where a staff segment enters the queue zone OR a table mask overlaps queue corridor | Blocked queues are invisible to POS but visible to customers — and they leave.        |
| `congestion_score`          | Normalized density in the counter+queue+pickup region (0..1)                                | Compact single number for the KPI card; drives the heatmap.                           |
| `table_detour_score`        | actual staff path length / straight-line counter→seating distance                           | Detects layout friction. Score >1.3 is the signal that furniture is in the way.       |


**Why these six, not others:** Every one of them (a) is deterministic and reproducible, (b) maps to a dollar-value operator concern, and (c) is supported by the agent schema's `KPIField` literal so the agent can emit `expected_kpi_delta` without hallucinating field names. Anything outside this set either costs money to measure (needs POS integration) or can't be justified from spatial data alone (e.g. "customer satisfaction").

**Why windows of 20 s:** Short enough that a single bottleneck event shows up as a peak rather than getting averaged out; long enough that three windows cover a minute, giving `PatternAgent` repetition to aggregate across. Pattern severity needs repetition — a one-window spike is anecdote, three-in-a-row is evidence.

---

## The handoff boundary

```text
┌─────────────── Vision pipeline ────────────────┐   ┌──── Agents pipeline ────┐
│ video → YOLO → ByteTrack → ZoneDraft → KPI     │ → │  Pydantic AI → MuBit    │
└────────────────────────────────────────────────┘   └─────────────────────────┘
                         │
                         ▼
                kpi_windows.json
                tracks.cached.json
                detections.cached.json
                zone_draft.cached.json
                zones.json
```

**The contract is the four JSON files.** That's the whole handshake.

- Vision team owns everything upstream of the JSON files.
- Agent team owns everything downstream.
- Neither team imports the other's modules.
- Swapping mock data for real data is `cp real_output.json demo_data/kpi_windows.json` — no code change.

This is also the fallback story: if live vision inference is slow or fails during the demo, we serve the cached JSON files and the agent loop is unaffected. The plan's `RUN_LIVE_VISION=1` env flag toggles live vs. cached.

---

## Why the mock data represents this faithfully

The files in `demo_data/` are fixtures that match what the real pipeline would produce:


| Mock file                          | Represents                                                            | Shape must match                                                                        |
| ---------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `demo_data/zone_draft.cached.json` | ZoneCalibrationAgent rationale and confidence                         | `ZoneDraft`                                                                             |
| `demo_data/zones.json`             | Agent-drafted or fixture polygons (one-time setup per camera/session) | `list[Zone]` — identical schema in prod                                                 |
| `demo_data/tracks.cached.json`     | ByteTrack output over 60 s at 2 fps                                   | `list[TrackPoint]`, ordered by `(track_id, timestamp_s)`                                |
| `demo_data/kpi_windows.json`       | KPI engine output for 3 × 20 s windows                                | `list[KPIReport]` with stable `session_id` across windows, distinct `run_id` per window |
| `demo_data/org_rules.json`         | Operator-configured constraints (not vision at all)                   | Loaded into MuBit `org:rules` lane on init                                              |


The scenario encoded in the mock data is also chosen to exercise every KPI at once:

- **Cluster B table placement** forces the staff runner into the queue zone → high `staff_customer_crossings` and `queue_obstruction_seconds`.
- **Six counter→seating trips in 60 s** make `staff_walk_distance_px` non-trivial and `table_detour_score` >1.4.
- **Five customers queueing during the same window** produce `queue_length_peak=6`.
- **Three repeated windows** (not one) give PatternAgent the repetition it needs to emit `severity="high"` honestly.

When real vision output replaces the mock data, the agents behave identically as long as the zone calibration and KPI engine hit roughly the same KPI magnitudes. The mock data is, in effect, the acceptance test for the vision layer: "produce zones and KPIs in this shape and range for the demo video, and the end-to-end loop works."

---

## What vision does **not** produce

To keep the boundary clean, the vision layer should not emit:

- Natural-language summaries (that's the ObservationCompressor agent's job).
- Pattern labels like "queue_crossing" (that's PatternAgent's job).
- Recommendations or confidence scores (that's OptimizationAgent).
- Furniture move suggestions (that's the simulator, fed by OptimizationAgent).
- MuBit writes (that's the memory adapter's job — agents write, vision doesn't).

If a vision engineer is tempted to add a field that isn't in `Detection`, `TrackPoint`, `Zone`, or `KPIReport`, that's a signal the work belongs on the agent side of the boundary instead. The exception is `ZoneDraft`, which is owned by the agent side but saved into the same JSON handoff so the KPI engine can stay decoupled.