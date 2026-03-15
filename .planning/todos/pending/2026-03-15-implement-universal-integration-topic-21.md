---
created: 2026-03-15T06:51:58.504Z
title: "Implement Universal Integration (Topic #21)"
area: infrastructure
priority: medium
target: v1.6-architecture
effort: 6 weeks
existing_code: 15%
depends_on: []
blocks: ["topic-22-mcp-server-creation", "topic-23-plugin-templates", "topic-24-third-party-apps-ui"]
design_doc: docs/enhancement/topics/21-universal-integration/00-specification.md
---

## Problem

Integrations are fragmented: MCP servers, REST/OpenAPI bridges, and channel adapters each have their own patterns. No unified adapter framework exists. The Universal Integration topic creates a single `IntegrationAdapter` protocol that all integration types implement, enabling consistent security, discovery, and management.

## What Exists (15%)

- `ChannelAdapter` Protocol (runtime_checkable) at `backend/channels/adapter.py`
- `SkillAdapter` ABC at `backend/skills/adapters/base.py` with GitHub, ClaudeMarket, SkillRepo implementations
- MCP client code at `backend/mcp/client.py`
- REST/OpenAPI bridge exists (basic)
- These are separate patterns — not unified

## What's Needed

- **Unified `IntegrationAdapter` base class** — abstract base that MCP, REST, Webhook, CLI-Anything all implement
- **`SecureAdapterWrapper`** — applies RBAC + ACL (3-gate security) to ALL adapters uniformly
- **REST/OpenAPI adapter** — hybrid BaseHTTPAdapter + OpenAPIAdapter + RESTAdapter
- **Webhook adapter** — HMAC-SHA256 primary, JWT optional
- **CLI-Anything adapter** — line-by-line streaming with `--stream-prefix` support
- **`IntegrationRegistry`** — lifecycle management for all adapter instances
- **Plugin SDK** — Python entry points for third-party adapter discovery
- **Separate `integrations/` module** — decouple from core AgentOS
- **MCP vs CLI-Anything resolution** — hybrid architecture (MCP for custom tools, CLI-Anything for existing software)

## Solution

Follow specification at `docs/enhancement/topics/21-universal-integration/00-specification.md`. Also see `docs/enhancement/mcp-vs-cli-anything-evaluation.md` for hybrid architecture rationale.
