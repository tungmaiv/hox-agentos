# ScalyClaw Architecture Documentation

> **Repository:** https://github.com/scalyclaw/scalyclaw  
> **Tagline:** "The AI That Scales With You"  
> **Type:** Self-hosted AI assistant platform  
> **License:** MIT  
> **Researched:** March 2026

---

## Executive Summary

ScalyClaw is a **self-hosted AI assistant platform** written in TypeScript that connects to multiple messaging channels with a single shared mind. It emphasizes scalability through a Node-Worker architecture, multi-layer security, and hot-reload capabilities for all components.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCALYCLAW NODE (Orchestrator)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Channels   │  │   Guards    │  │   Memory    │  │   Agents    │    │
│  │  Manager    │  │  (4 layers) │  │  System     │  │   Manager   │    │
│  └──────┬──────┘  └─────────────┘  └──────┬──────┘  └─────────────┘    │
│         │                                  │                            │
│  ┌──────▼──────────────────────────────────▼──────────────────────┐    │
│  │                     Gateway Server (Fastify)                   │    │
│  │              - HTTP/SSE endpoints for channels                 │    │
│  │              - WebSocket for real-time comms                   │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Redis (Pub/Sub + Queue)
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                    SCALYCLAW WORKERS (Horizontally Scalable)           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    BullMQ Workers                                │  │
│  │  - Messages Queue    - Agents Queue    - Internal Queue         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Execution Engine                              │  │
│  │  - Command/Code execution  - Skill execution  - Dependency mgmt  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         DASHBOARD (React SPA)                          │
│  - Real-time monitoring  - Configuration  - Chat overlay  - Job viewer │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. ScalyClaw Node (Orchestrator)

**Role:** Singleton control plane managing all channels, security, memory, and agents.

**Key Modules:**

| Module | Responsibility | Location |
|--------|---------------|----------|
| `channels/` | Channel adapters for 7+ platforms | `scalyclaw/src/channels/` |
| `guards/` | Four-layer security system | `scalyclaw/src/guards/` |
| `memory/` | Hybrid vector + FTS5 memory | `scalyclaw/src/memory/` |
| `agents/` | Sub-agent management and delegation | `scalyclaw/src/agents/` |
| `orchestrator/` | Main message processing loop | `scalyclaw/src/orchestrator/` |
| `skills/` | Hot-reloadable skill system | `scalyclaw/src/skills/` |
| `mcp/` | MCP client integration | `scalyclaw/src/mcp/` |
| `scheduler/` | Cron-based proactive checks | `scalyclaw/src/scheduler/` |

**Entry Point:** `scalyclaw/src/index.ts`

**BullMQ Workers:**
- **Messages Queue:** Processes incoming messages
- **Agents Queue:** Runs delegated sub-agent tasks
- **Internal Queue:** System tasks (memory cleanup, consolidation)

### 2. ScalyClaw Worker (Scalable Execution)

**Role:** Stateless execution workers that can be deployed anywhere.

**Key Features:**
- Shares nothing with Node except Redis
- No shared filesystem required
- Hot-reload of skills via Redis pub/sub
- Auto-dependency installation

**Deployment Pattern:**
```bash
# Worker on same machine
bun run scalyclaw:worker start --name worker1

# Worker on remote machine (only needs Redis connection)
bun run scalyclaw:worker start --name worker2 --redis redis://remote:6379
```

### 3. Dashboard

**Tech Stack:** React 19, Vite 6, Tailwind CSS 4, shadcn/ui

**Views:**
- **Overview:** System health, active channels, recent activity
- **Mind:** Personality configuration (IDENTITY.md, SOUL.md, USER.md)
- **Channels:** Channel configuration and status
- **Models:** LLM configuration, budget control, load balancing
- **Agents:** Sub-agent management and monitoring
- **Skills:** Skill registry, deployment, hot-reload
- **Memory:** Search, view, delete memories
- **Vault:** Encrypted secrets management
- **MCP:** Connected MCP servers
- **Scheduler:** Cron jobs and scheduled tasks
- **Security:** Guard configuration
- **Workers:** Worker status and scaling

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Bun | Primary JavaScript runtime |
| **Queue** | BullMQ + Redis | Task queue and job distribution |
| **Database** | SQLite + sqlite-vec + FTS5 | Local-first storage with vector search |
| **LLM** | OpenAI-compatible API | Multi-provider model support |
| **Channels** | Various SDKs | Telegraf, discord.js, @slack/bolt, etc. |
| **MCP** | @modelcontextprotocol/sdk | Model Context Protocol integration |
| **HTTP** | Fastify | Gateway web server |
| **Dashboard** | React 19 + Vite 6 + Tailwind 4 | Web UI |
| **CLI** | Commander + @clack/prompts | Command-line interface |

---

## Security Architecture

### Four-Layer Guard System

All layers **fail closed** (deny by default):

| Guard | Purpose | Implementation |
|-------|---------|----------------|
| **Echo Guard** | Detect prompt injection via text repetition | Pattern matching |
| **Content Guard** | Block harmful content and social engineering | LLM-based classification |
| **Skill & Agent Guard** | Audit code/configs for malicious patterns | Static analysis |
| **Command Shield** | Block dangerous shell commands | Deterministic pattern matching |

### Vault System

- Secrets stored encrypted in Redis (AES-256)
- Injected as environment variables during skill execution
- Never exposed in conversations, logs, or dashboard
- Can be scoped to specific skills

---

## Memory System

### Hybrid Search Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Memory Types                           │
├─────────────────────────────────────────────────────────────┤
│  Facts        │ Stable facts, user preferences               │
│  Preferences  │ User likes/dislikes                          │
│  Events       │ Temporal events                              │
│  Relationships│ Entity connections                           │
└─────────────────────────────────────────────────────────────┘

Search Methods:
├── Vector Similarity (sqlite-vec) - semantic search
└── Full-Text Search (FTS5) - keyword search
```

**Auto-Extraction:**
- Facts extracted from conversations automatically
- Confidence scores for each memory
- Cross-channel memory (Telegram → Discord)

---

## Skills System

### Skill Structure

```
skills/
├── weather/
│   ├── SKILL.md      # Manifest (name, description, language, script)
│   └── main.py       # Entry point
└── deploy/
    ├── SKILL.md
    └── main.js
```

**SKILL.md Example:**
```yaml
---
name: Weather
description: Get current weather for a city
script: main.py
language: python
---
Optional instructions for the AI on when and how to use this skill.
```

**Supported Languages:**
| Language | Runtime |
|----------|---------|
| JavaScript | `bun run` |
| Python | `uv run` |
| Rust | `cargo run --release` |
| Bash | `bash` |

**Deployment:**
- Hot-reload via Redis pub/sub
- Zip archive deployment
- Auto-dependency installation
- Scoped secrets injection

---

## Agents System

### Sub-Agent Architecture

Agents are autonomous workers with:
- **Custom Prompt:** Role definition
- **Dedicated Model:** Can use different LLM than main orchestrator
- **Restricted Skills:** Subset of available skills
- **Permissions:** Fine-grained capability control

**Execution:**
- Delegated tasks run on BullMQ agents queue
- Independent from main conversation
- Can spawn other agents (nested delegation)

---

## MCP Integration

### Supported Transports

- **stdio:** Local process communication
- **HTTP:** Direct HTTP requests
- **SSE:** Server-Sent Events (persistent connection)

### Auto-Discovery

- Tools from MCP servers automatically available to AI
- Dashboard-based configuration
- Hot-reload without restart

---

## Channels

### Supported Platforms (7+)

| Channel | Library | Notes |
|---------|---------|-------|
| Discord | discord.js | Full bot capabilities |
| Telegram | Telegraf | Bot API |
| Slack | @slack/bolt | Bolt framework |
| WhatsApp | WhatsApp Cloud API | Business API |
| Signal | signal-cli | CLI wrapper |
| Teams | botbuilder | Bot Framework |
| Web | Custom | Built-in gateway |

### Channel Architecture

All channels share the same memory and personality — one mind across all platforms.

---

## Model Management

### Multi-Model Configuration

- Different models for different tasks (chat, agents, guards, embeddings)
- **Priority + Weight Load Balancing:**
  - Lower priority = tried first
  - Within same priority: weighted-random distribution
  - Automatic fallback to next priority group

### Budget Control

- Monthly/daily spending limits
- Per-model cost tracking
- Soft or hard limit enforcement
- Configurable alerts

---

## Key Design Decisions

### 1. Bun Runtime
**Decision:** Use Bun instead of Node.js  
**Rationale:** Faster startup, built-in TypeScript support, better performance  
**Trade-off:** Less mature ecosystem than Node.js

### 2. SQLite + Vector Extension
**Decision:** Use sqlite-vec instead of PostgreSQL/pgvector  
**Rationale:** Local-first, zero configuration, single file  
**Trade-off:** Less suitable for multi-node deployments

### 3. Redis-Centric Architecture
**Decision:** Workers share only Redis, no shared filesystem  
**Rationale:** True horizontal scalability, simple deployment  
**Trade-off:** Redis becomes a single point of failure

### 4. Hot-Reload Everything
**Decision:** Skills, agents, config, MCP servers all reloadable  
**Rationale:** Zero-downtime updates, faster iteration  
**Trade-off:** Requires careful state management

---

## Comparison with OpenClaw

| Aspect | ScalyClaw | OpenClaw |
|--------|-----------|----------|
| **Scale** | Multi-user, horizontally scalable | Personal/single-user |
| **Runtime** | Bun | Node.js |
| **Database** | SQLite | SQLite |
| **Queue** | BullMQ + Redis | In-process |
| **Workers** | Separate scalable workers | Single process |
| **Channels** | 7+ platforms | 20+ platforms |
| **Memory** | Hybrid (vec + FTS5) | Hybrid (vec + FTS5) |
| **Skills** | Hot-reload, zip deploy | File-based, auto-discover |
| **Agents** | Sub-workers with queues | Session-based |
| **Target** | Small teams, self-hosted | Personal use |

---

## Strengths

1. **True Scalability:** Workers can be distributed across machines
2. **Production-Ready Security:** 4-layer guards with fail-closed design
3. **Excellent Developer Experience:** Hot-reload everything
4. **Budget Control:** Built-in cost tracking and limits
5. **Clean Architecture:** Well-separated concerns (Node/Worker/Dashboard)

## Limitations

1. **Early Stage:** Only 4 stars on GitHub, limited community
2. **Bun Dependency:** Smaller ecosystem than Node.js
3. **Single Redis:** Potential SPOF for queue system
4. **No Kubernetes:** Designed for simple deployments

---

## Files Reference

**Source Code Structure:**
```
scalyclaw/
├── src/
│   ├── index.ts              # Main entry point
│   ├── agents/               # Sub-agent management
│   ├── api/                  # REST API
│   ├── channels/             # Channel adapters
│   ├── commands/             # Command handlers
│   ├── const/                # Constants
│   ├── core/                 # Bootstrap, config, paths
│   ├── gateway/              # HTTP gateway server
│   ├── guards/               # Security guards
│   ├── mcp/                  # MCP integration
│   ├── memory/               # Memory subsystem
│   ├── models/               # LLM configuration
│   ├── orchestrator/         # Main message loop
│   ├── proactive/            # Proactive behavior
│   ├── processors/           # Queue processors
│   ├── prompt/               # Prompt engineering
│   ├── queue/                # Queue management
│   ├── scheduler/            # Cron scheduling
│   ├── skills/               # Skills system
│   └── tools/                # Built-in tools
```

---

## Sources

- https://github.com/scalyclaw/scalyclaw
- https://github.com/scalyclaw/scalyclaw/blob/main/README.md
- https://github.com/scalyclaw/scalyclaw/blob/main/scalyclaw/src/index.ts
- ScalyClaw architecture diagram (screenshots/architecture.png)

---

*Document generated: March 2026*
