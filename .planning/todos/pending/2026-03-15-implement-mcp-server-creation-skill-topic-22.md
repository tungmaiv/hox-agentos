---
created: 2026-03-15T06:51:58.504Z
title: "Implement MCP Server Creation Skill (Topic #22)"
area: tooling
priority: medium
target: v1.6-architecture
effort: 10 weeks
existing_code: 0%
depends_on: ["topic-21-universal-integration"]
design_doc: docs/enhancement/topics/22-mcp-server-creation-skill/00-specification.md
---

## Problem

MCP servers are created manually. No automated generation exists. Users must hand-write MCP server code from scratch, even when an OpenAPI spec or GraphQL schema is available.

## What Exists (0%)

Zero code — specification only.

## What's Needed

- **Natural language → MCP server generation** — describe what you want, get a working MCP server
- **OpenAPI 3.x parser** — auto-detect and parse OpenAPI specs to extract tools
- **GraphQL introspection parser** — parse GraphQL schemas for tool extraction
- **AI semantic enrichment** — LLM-powered enrichment of parsed tools (better descriptions, parameter validation)
- **External prompt files** — Markdown prompts for maintainability and hot-reload
- **Jinja2 code generation templates** — Python MCP server template with proper structure
- **Interactive UI** — tool selection, refinement, preview before generation
- **Dual output modes:**
  - Downloadable code package (standalone MCP server)
  - Immediate runtime adapter (register directly in AgentOS)
- **Three deployment modes:** local runtime, Docker container, external hosting
- **Integration with Topic #21** — uses IntegrationRegistry for adapter registration

## Solution

Follow specification at `docs/enhancement/topics/22-mcp-server-creation-skill/00-specification.md`. 10-week implementation in 7 phases.
