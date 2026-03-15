---
created: 2026-03-15T06:51:58.504Z
title: "Implement Multi-Agent Tab Architecture (Topic #16)"
area: ui
priority: high
target: v1.4-foundation
effort: 10-13 hours
existing_code: 5%
depends_on: []
blocks: ["topic-09-multi-agent-orchestration"]
design_doc: docs/enhancement/topics/16-multi-agent-tab-architecture/00-specification.md
files:
  - backend/agents/artifact_builder.py
  - frontend/src/components/admin/artifact-wizard.tsx
---

## Problem

The artifact builder uses a single CopilotKit instance and a single `artifact_builder` agent for creating all artifact types (skills, tools, MCP servers, agents). This limits complex artifact creation that requires multi-step, multi-agent workflows. No multi-tab support exists. This is a prerequisite for Topic #09 (Multi-Agent Orchestration).

## What Exists (5%)

- Single `artifact_builder` agent at `backend/agents/artifact_builder.py`
- Basic artifact form at `frontend/src/components/admin/artifact-wizard.tsx`
- Single CopilotKit instance at `/admin/create`

## What's Needed

- **`tool_builder` agent** — separate agent for tool creation with tool-specific context
- **`mcp_builder` agent** — separate agent for MCP server creation
- **`agent_dependencies` table** — DB schema for tracking cross-agent dependencies
- **Multi-tab UI** — tabbed interface to switch between specialized builder agents
- **Tab state management** — `use-agent-tabs.ts` hook for managing tab state
- **Multiple CopilotKit instances** — support running tool_builder and skill_builder in parallel
- **Refactor artifact wizard** — from single-agent to multi-agent tabbed architecture

## Solution

Follow specification at `docs/enhancement/topics/16-multi-agent-tab-architecture/00-specification.md`.
