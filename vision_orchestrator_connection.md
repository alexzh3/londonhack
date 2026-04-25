# Vision ↔ Agents — The Handshake

## What this document is for

CafeTwin has two halves:

1. A **perception** half that turns video into facts ("there's a queue here," "staff walked 12 meters").
2. An **agent** half that reasons about those facts and recommends a layout change.

Each half can be built independently as long as the **handshake between them is fixed**. This doc describes that handshake in plain terms so the two teams never have to coordinate beyond it.

## The big idea

> The two halves talk to each other through **one bundle of evidence**, called the `CafeEvidencePack`. Whoever produces the bundle can change. Whoever consumes it never has to.

That's the whole contract. The producer changes per tier; the consumer (the agent) stays the same.

```text
        WHO PRODUCES THE EVIDENCE                THE EVIDENCE BUNDLE         WHO USES IT
                                                  (CafeEvidencePack)
        (changes per tier)                                                   (never changes)

   ┌───────────────────────────┐
   │  MVP                      │
   │  Hand-authored JSON       │ ─┐
   │  in demo_data/            │  │
   └───────────────────────────┘  │
                                  │      ┌───────────────────────────┐    ┌──────────────────────┐
   ┌───────────────────────────┐  │      │                           │    │                      │
   │  Tier 1                   │  │      │  • zones                  │    │  Optimization Agent  │
   │  Real video analysis      │  │      │  • objects in the cafe    │    │  (Pydantic AI)       │
   │  (YOLO + tracking + KPI   │  ├────▶ │  • KPIs over time         │ ─▶ │                      │
   │   engine + Pattern agent) │  │      │  • the bottleneck pattern │    │  → Layout change     │
   └───────────────────────────┘  │      │  • prior recommendations  │    │    recommendation    │
                                  │      │                           │    │                      │
   ┌───────────────────────────┐  │      └───────────────────────────┘    └──────────────────────┘
   │  Tier 2                   │ ─┘
   │  Same as Tier 1 +         │
   │  3D twin layout files     │
   └───────────────────────────┘
```

## What's inside the evidence bundle

In words, the bundle gives the agent everything it needs to make a confident, evidence-backed recommendation:

| Piece | What it represents |
|---|---|
| **Zones** | Where the queue forms, where pickup happens, the staff path, etc. Hand-drawn polygons on the floor. |
| **Object inventory** | Counts and positions of tables, chairs, the counter, the pickup shelf. |
| **KPI windows** | Numeric snapshots of what happened in the cafe over time — crossings, walking distance, queue obstruction, congestion, table detours. |
| **Pattern** | A short summary of the spatial bottleneck the agent should address ("staff repeatedly cross the queue to reach pickup"). Includes the KPI evidence that supports it. |
| **Org rules** | Hard constraints like "minimum 1.2m walkway." |
| **Prior recommendations** | What the system has recommended for this same pattern before, recalled from MuBit. Lets the agent acknowledge memory. |

The exact field-by-field schema lives in `agent_plan.md §Schemas`. This doc only cares about the concepts.

## How the bundle gets built, per tier

### MVP — bundle is hand-authored

Everything in the bundle comes from JSON files in `demo_data/` that we wrote by hand. The agent has no idea this is the case. It validates and reasons over the bundle exactly the same way it would in production.

Why this is OK: judges grade the **reasoning loop** (typed agent, evidence chain, memory write, traced run), not whether the upstream KPIs came from live YOLO. Saying "the perception is fixture-backed for demo reliability" is honest.

### Tier 1 — bundle is computed live

We swap each fixture file for the real thing:

- A YOLO + tracking script runs offline and produces real movement tracks for the seeded video.
- A small KPI engine consumes those tracks plus the zones and computes real KPI windows.
- A `PatternAgent` (or a deterministic rule-based builder) reads the recent KPI windows and emits the operational pattern.

The agent layer doesn't change. The bundle has the same shape. The demo looks identical — but now we can also say "perception is live."

### Tier 2 — extra files for richer UI

Tier 2 doesn't change the agent contract at all. It just ships two extra layout files (`twin_observed.json`, `twin_recommended.json`) that the frontend uses to render a real 3D twin instead of pre-rendered PNGs. The agent still consumes the same bundle.

## What stays hand-drawn forever

**Zones.** Drawing operational zones (where the queue is, where pickup is, the staff corridor) takes 5 minutes by hand and judges won't watch the agent draft them live. We could add a `ZoneCalibrationAgent` later, but never in this hackathon. Zones are the one piece of "perception" that's deliberately hand-drawn in every tier.

## What perception layer does NOT produce

To keep the boundary clean, the perception layer only produces facts about the cafe — never opinions about the cafe. So no:

- Natural-language summaries (the agents do that).
- Bottleneck labels like "queue crossing problem" (the pattern step does that).
- Recommendations or suggestions (the optimization agent does that).
- Memory writes to MuBit (the memory layer does that).

If a contributor wants to add a field that doesn't fit the bundle, that's a signal the work belongs on the agent side or the UI side, not in perception.

## Demo-day fallback

The demo never depends on live perception. In any tier:

- The hand-authored fixtures from MVP are always on disk.
- An env flag opts into live YOLO when we want it (Tier 1).
- If anything in the perception layer fails, we serve the cached bundle and the agent can't tell the difference.

That's also the reason zones stay hand-drawn — one less thing that can break under stage lights.

## One-line take

> The vision team owns producing the evidence bundle. The agent team owns reasoning over it. The boundary is one Pydantic model, and we keep it that way across all three tiers.

For the field-by-field schema, see `agent_plan.md §Schemas`. For the architecture per tier, see `agent_plan.md §Visual Architecture`.
