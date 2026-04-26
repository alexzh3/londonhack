## Hackathon Build Context

This project is for a 24-hour hackathon. The goal is to build a working, demoable product quickly.

The project should prioritize:
- a complete end-to-end MVP,
- a deployed or locally runnable demo,
- clear use of Pydantic schemas,
- at least one Pydantic AI agent,
- structured/validated agent outputs,
- simple memory/storage for observations and recommendations,
- a clear UI showing the input, extracted KPIs, and optimization recommendations.

# Agent Instructions

- Do not commit, stage, push, print, summarize, or upload local secret files.
- Treat `.env`, `.env.*`, private keys, certificates, and `secrets/` as off-limits.
- Commit only placeholder files such as `.env.example` or `.env.sample`.
- Before preparing a commit or PR, check that no secret file is tracked or staged.
- agent_plan.md contains the detailed architecture and overview_plan.md contains the general overview
- for every change also edit the agent_plan.md and overview_plan.md to keep progress 
- mubit documentation, if writing mubit code: https://docs.mubit.ai/
- pydantic documentation if writing pydantic code: https://pydantic.dev/docs/ai/overview/

## Multi-Agent Handoff (optional)

When `.agents/handoff.md` exists, the user is running multiple coding agents in parallel (e.g. Codex + Devin for Terminal) and uses that file to share context across sessions. If you see it:

- Read `.agents/handoff.md` at session start, after `AGENTS.md` and the plan files.
- Update its **Current State** block when you finish a meaningful chunk of work, and append to its **Decision Log** for non-obvious choices. Identify yourself (e.g. `codex`, `devin`).
- Keep entries short — it's a sticky note, not documentation. Substantive design changes still belong in `agent_plan.md` / `overview_plan.md`.

If the file does not exist, ignore this section — single-agent sessions don't need it and you should not create it unprompted.

## Installed Skills

Local skills live under `.agents/skills/`. Invoke them via the `skill` tool before writing code in the matching domain.

- **`building-pydantic-ai-agents`** (`.agents/skills/building-pydantic-ai-agents/`) — invoke before writing or editing any Pydantic AI agent (`OptimizationAgent`, future `PatternAgent` / `SceneBuilderAgent`). Covers `Agent` setup, structured output, tools, streaming, hooks, retries, and testing patterns. Required reading before touching `app/agents/`.
- **`instrumentation`** (`.agents/skills/instrumentation/`) — invoke before adding or editing Logfire spans, including `app/logfire_setup.py`, the `/api/run` span tree, and any `logfire.span(...)` / `logfire.instrument_pydantic_ai()` call. Catches subtle ordering/config mistakes that silently drop traces.

Discover all available skills with `skill list .` from the repo root.
