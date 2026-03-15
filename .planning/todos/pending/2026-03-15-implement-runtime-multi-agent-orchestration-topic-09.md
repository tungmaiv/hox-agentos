---
created: 2026-03-15T06:51:58.504Z
title: "Implement Runtime Multi-Agent Orchestration (Topic #09)"
area: agents
priority: medium
target: v1.5-foundation
effort: 10 weeks
existing_code: 10%
depends_on: ["topic-16-multi-agent-tab-architecture"]
design_doc: docs/enhancement/topics/09-runtime-multi-agent-orchestration/00-specification.md
---

## Problem

AgentOS uses a single master_agent with basic sub-agent routing (email_agent, calendar_agent, project_agent). All agents share a single `BlitzState` context — no context isolation, no dynamic spawning, no multi-agent coordination patterns.

## What Exists (10%)

- `master_agent.py` with `_pre_route()` conditional intent detection
- Sub-agents: email_agent, calendar_agent, project_agent (basic, shared state)
- Memory nodes for loading/saving conversation history (pgvector semantic search)
- Single CopilotKit instance

## What's Needed

- **Session Spawning** (Approach B) — independent checkpointers per agent, true context isolation
- **`agent_sessions` table** — DB model for agent lifecycle management
- **Optional Supervisor Agent** — pattern-first auto-enable with 5 coordination patterns:
  - Sequential, parallel-join, fan-out/fan-in, dynamic spawning, hierarchical
- **Event-driven coordination:**
  - Hybrid Redis (real-time) + PostgreSQL (durability) event delivery
  - Configurable event granularity (coarse/medium/fine)
- **Workspace state sharing** — JSONB in agent_sessions table for cross-agent data
- **4 error handling strategies** — retry, notify-and-wait, alternative, custom (per-dependency)
- **Circuit breaker** — disabled by default, opt-in only for v1.5
- **Recursive spawning** — unlimited depth (practical limit 3), depth tracking
- **DAG-only constraint** — no cycles in v1.5

## Solution

Follow specification at `docs/enhancement/topics/09-runtime-multi-agent-orchestration/00-specification.md`. 10-week implementation in 5 phases.
