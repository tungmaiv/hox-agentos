# Blitz AgentOS – Implementation Guide

This document defines the end-to-end implementation workflow for Blitz AgentOS using two complementary tool systems: **GSD** (project management and phase tracking) and **Superpowers** (coding discipline and quality). Each step specifies which tool to use and the exact command/skill to invoke.

> **GSD version this guide is based on:** v1.20.6

---

## Tool Overview

| Tool | Purpose | Persistence |
|------|---------|-------------|
| **GSD** | Project roadmap, phase planning, progress tracking | Across sessions (writes `.planning/` files) |
| **Superpowers** | Coding discipline: brainstorming, TDD, parallel agents, verification | Within session only |

> GSD internally invokes Superpowers skills during execution. They are complementary, not competing.

---

## High-Level Workflow

```
Project Init (GSD)
      ↓
Phase 1: Identity & Skeleton
      ↓
Phase 2: Agents, Tools & Memory
      ↓
Phase 3: Canvas & Workflows
      ↓
Phase 4: Scheduler & Channels
      ↓
Phase 5: Hardening & Sandboxing
      ↓
Final Review & Handoff
```

Each phase follows the same inner loop:
```
Brainstorm → Discuss → Assumptions → Plan → Execute → UAT → Verify → Review → Complete
```

---

## Stage 0 – Project Initialization

### Step 0.1 – Initialize Project with GSD

**Tool:** GSD
**Command:** `/gsd:new-project`

**What it does:**
- Reads `docs/design/blueprint.md` and `docs/design/module-breakdown.md`
- Asks clarifying questions about goals, constraints, and team
- Creates `PROJECT.md` with goals, milestones, success criteria
- Generates a phased roadmap aligned to the 5 blueprint phases

**Input:** Point GSD at your docs:
> "Initialize a new project. The solution blueprint is in `docs/design/blueprint.md` and the module breakdown is in `docs/design/module-breakdown.md`."

**`--auto` flag (optional):** Runs research → requirements → roadmap automatically without stopping after each step. Requires passing the idea document via `@` reference:
> `/gsd:new-project --auto @docs/design/blueprint.md`

**Output:** `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`

---

### Step 0.2 – Configure GSD Settings

**Tool:** GSD
**Command:** `/gsd:settings`

**What it does:**
- Set model profile (quality/balanced/budget)
- Toggle optional agents (verification, code review, etc.)
- Configure per-agent model overrides (e.g., use `quality` only for security-critical agents)
- Set git branching strategy: `none` (default), `phase`, or `milestone`

**Recommended settings for Blitz AgentOS:**
- Profile: `balanced` for feature work, `quality` for security-critical phases
- Enable verification agent: `true`
- Git branching: `phase` (creates `gsd/phase-{N}-{slug}` branches per phase)
- Brave Search: set `BRAVE_API_KEY` env var to enable web search in researcher agents

**User-level defaults (optional):** Create `~/.gsd/defaults.json` to apply settings across all projects:
```json
{
  "profile": "balanced",
  "verification": true,
  "branching": "phase"
}
```

---

### Step 0.3 – Map the Codebase (if starting from existing code)

**Tool:** GSD
**Command:** `/gsd:map-codebase`

**What it does:**
- Runs parallel mapper agents across the repo
- Produces structured analysis documents in `.planning/codebase/`
- Covers architecture, tech stack, quality, and concerns

> Skip this step if starting from scratch (no existing code).

---

### Step 0.4 – Validate Planning Directory Health

**Tool:** GSD
**Command:** `/gsd:health`

**What it does:**
- Validates `.planning/` directory integrity (ROADMAP.md, REQUIREMENTS.md, STATE.md, config.json)
- Detects missing files, malformed frontmatter, phase numbering inconsistencies
- `--repair` flag auto-fixes config.json and STATE.md with timestamped backups

**Run after init and after any GSD update** to catch any setup issues before work begins.

```
/gsd:health --repair
```

---

## Stage 1 – Phase 1: Identity & Skeleton

**Goal:** Deploy Keycloak, Postgres, Redis. Implement FastAPI runtime with JWT middleware. Set up Next.js with CopilotKit provider and AG-UI chat.

### Step 1.1 – Brainstorm Before Building

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`

**What it does:**
- Explores design decisions before writing any code
- Surfaces ambiguities in auth flow, JWT strategy, and project structure
- Produces a clear intent summary

**Invoke before** touching any code in this phase.

---

### Step 1.2 – Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase`

**What it does:**
- Asks adaptive questions to capture your design decisions and constraints for this phase
- Writes a `CONTEXT.md` file that flows downstream into the researcher, planner, and plan checker
- Ensures the planner honors your decisions rather than making assumptions

**This step is critical:** without CONTEXT.md, `/gsd:plan-phase` will warn you that no context exists. Always run `/gsd:discuss-phase` first.

---

### Step 1.3 – Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions`

**What it does:**
- Shows what GSD assumes about the implementation approach before committing to a plan
- Lets you correct any wrong assumptions before the plan is written
- Prevents the planner from going in the wrong direction silently

Run this after `/gsd:discuss-phase` and before `/gsd:plan-phase`.

---

### Step 1.4 – Plan Phase 1

**Tool:** GSD
**Command:** `/gsd:plan-phase`

**What it does:**
- Reads the Phase 1 roadmap entry and your `CONTEXT.md`
- Researches implementation approach (Keycloak, FastAPI, CopilotKit)
- Creates `PLAN.md` with atomic, ordered tasks
- Runs **Nyquist validation** — catches quality issues before execution
- **Blocks execution** if any REQUIREMENTS.md entries for this phase are absent from the plan

**Key tasks it should produce:**
- Docker Compose setup (Keycloak, Postgres, Redis)
- `core/config.py` – Pydantic settings
- `core/db.py` – SQLAlchemy session factory
- `security/keycloak_client.py` – JWKS fetch and cache
- `security/jwt.py` – decode and verify JWT
- `security/deps.py` – FastAPI `get_current_user()` dependency
- `gateway/runtime.py` – Copilot Runtime init
- `frontend/` skeleton – Next.js + CopilotKit provider + AG-UI chat

---

### Step 1.5 – Execute Phase 1 with Parallel Agents

**Tool:** GSD + Superpowers
**Command:** `/gsd:execute-phase`

**What it does:**
- Reads `PLAN.md` and groups tasks into independent waves
- Spawns parallel subagents for non-dependent tasks:
  - Agent A: Docker Compose + infra setup
  - Agent B: FastAPI skeleton + security module
  - Agent C: Next.js frontend skeleton
- Uses `superpowers:dispatching-parallel-agents` internally
- Each agent uses `superpowers:test-driven-development` for their tasks
- Updates ROADMAP.md and REQUIREMENTS.md automatically after each plan completes

---

### Step 1.6 – UAT: Validate Built Features

**Tool:** GSD
**Command:** `/gsd:verify-work`

**What it does:**
- Conversational UAT session — describes what was built and asks you to confirm it meets intent
- Surfaces gaps between what was planned and what was implemented
- Creates UAT issues that auto-resolve after gap-closure if needed

---

### Step 1.7 – Verify Phase 1

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`

**What it does:**
- Runs verification commands (health checks, JWT validation tests)
- Confirms evidence before declaring Phase 1 done
- Must pass: Keycloak reachable, JWT validated, `/api/agents/chat` returns 200 with valid token

---

### Step 1.8 – Mark Phase 1 Complete

**Tool:** GSD
**Command:** `/gsd:progress`

Shows current phase status and routes to the next action.

---

## Stage 2 – Phase 2: Agents, Tools & Memory

**Goal:** Implement master agent, sub-agents (email, calendar, project), backend tools, Pydantic schemas, and hierarchical memory with per-user isolation.

### Step 2.1 – Brainstorm Agent Architecture

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`

Focus areas:
- LangGraph StateGraph design for master agent
- Sub-agent communication patterns
- Memory tier boundaries (short/medium/long term)
- PydanticAI tool schema conventions

---

### Step 2.2 – Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase`

Key decisions to capture:
- Which sub-agents are in scope for Phase 2
- Memory summarization trigger strategy (token threshold vs. session boundary)
- Tool registration metadata conventions

---

### Step 2.3 – Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions`

---

### Step 2.4 – Plan Phase 2

**Tool:** GSD
**Command:** `/gsd:plan-phase`

**Key tasks it should produce:**
- `agents/master_agent.py` – `run_conversation` and `run_workflow` entrypoints
- `agents/state/types.py` – `BlitzState` TypedDict
- `agents/subagents/email_agent.py`
- `agents/subagents/calendar_agent.py`
- `agents/subagents/project_agent.py`
- `agents/subagents/channel_agent.py`
- `tools/email_tools.py`, `tools/calendar_tools.py`, `tools/project_tools.py`, `tools/dataops_tools.py`
- `core/schemas/` – Pydantic input/output schemas for all tools
- `gateway/tool_registry.py` – register tools with metadata
- `memory/short_term.py`, `memory/medium_term.py`, `memory/long_term.py`
- `memory/summarizer.py` – LLM-based session summarization
- `core/models/memory.py` – SQLAlchemy memory models

---

### Step 2.5 – Dispatch Parallel Agents for Independent Modules

**Tool:** Superpowers
**Command:** `/superpowers:dispatching-parallel-agents`

Use directly when you want fine-grained control over parallelism within the session:

- Agent 1: Memory subsystem (`memory/`, `core/models/memory.py`)
- Agent 2: Master agent + state types (`agents/master_agent.py`, `agents/state/`)
- Agent 3: Sub-agents (`agents/subagents/`)
- Agent 4: Tool modules + schemas (`tools/`, `core/schemas/`)

> These modules have no shared write state — safe to parallelize.

---

### Step 2.6 – Build Each Component TDD

**Tool:** Superpowers
**Command:** `/superpowers:test-driven-development`

Apply for each component before writing implementation code:
1. Write test for tool Pydantic schema validation
2. Write test for memory isolation (cross-user read must fail)
3. Write test for master agent entrypoint
4. Implement to pass tests

---

### Step 2.7 – UAT: Validate Built Features

**Tool:** GSD
**Command:** `/gsd:verify-work`

---

### Step 2.8 – Verify Phase 2

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`

Must pass:
- All tool schema tests pass
- Memory queries filter by `user_id` (no cross-user reads)
- `POST /api/agents/chat` with a message returns an agent response
- Sub-agents invocable from master agent

---

## Stage 3 – Phase 3: Canvas & Workflows

**Goal:** Implement low-code canvas, persist `Workflow.definition_json`, compile canvas JSON to LangGraph StateGraph, add HITL nodes.

### Step 3.1 – Brainstorm Canvas Design

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`

Focus areas:
- Canvas JSON schema (node types: agent, tool, mcp, hitl)
- `useCoAgent` sync strategy between frontend and backend StateGraph
- `renderAndWait` semantics for HITL nodes
- A2UI JSONL envelope format for widget rendering

---

### Step 3.2 – Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase`

---

### Step 3.3 – Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions`

---

### Step 3.4 – Plan Phase 3

**Tool:** GSD
**Command:** `/gsd:plan-phase`

**Key tasks it should produce:**
- `core/models/workflow.py` – `Workflow` and `WorkflowRun` models
- `agents/graphs.py` – `compile_workflow_to_stategraph()`
- `api/routes/workflows.py` – CRUD and run endpoints
- `frontend/components/canvas/CanvasRoot.tsx`
- `frontend/components/canvas/NodePalette.tsx`
- `frontend/components/canvas/NodeRenderer.tsx`
- `frontend/hooks/use-co-agent.ts` – `useCoAgent` sync
- `frontend/hooks/use-frontend-tools.ts` – canvas tool registration
- `frontend/components/a2ui/A2UIMessageRenderer.tsx`
- `frontend/components/a2ui/widgets/` – Card, Table, Form, Progress

---

### Step 3.5 – Execute Phase 3

**Tool:** GSD
**Command:** `/gsd:execute-phase`

Parallel waves:
- Wave 1: Backend – workflow model + `compile_workflow_to_stategraph` + API routes
- Wave 2: Frontend – canvas components + `useCoAgent` + A2UI renderer

---

### Step 3.6 – UAT: Validate Built Features

**Tool:** GSD
**Command:** `/gsd:verify-work`

---

### Step 3.7 – Verify Phase 3

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`

Must pass:
- Canvas JSON can be persisted and retrieved via API
- `compile_workflow_to_stategraph` executes a simple 2-node workflow
- HITL node pauses execution and waits for user approval
- A2UI widgets render correctly from JSONL envelopes
- Canvas state syncs with backend StateGraph via `useCoAgent`

---

## Stage 4 – Phase 4: Scheduler & Channels

**Goal:** Implement Celery-based scheduler, REST APIs for jobs, at least one external channel (Telegram), wire outputs to web and channels.

### Step 4.1 – Brainstorm Scheduler and Channel Design

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`

Focus areas:
- Celery beat vs. custom periodic scanner for job triggering
- Channel gateway auth (HMAC vs. service account JWT)
- A2UI notification delivery vs. channel adapter delivery
- `ChannelAccount` resolution from external user IDs

---

### Step 4.2 – Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase`

---

### Step 4.3 – Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions`

---

### Step 4.4 – Plan Phase 4

**Tool:** GSD
**Command:** `/gsd:plan-phase`

**Key tasks it should produce:**
- `scheduler/celery_app.py` – Celery + Redis broker config
- `scheduler/jobs.py` – cron parsing, `next_run_at` computation
- `scheduler/worker.py` – `run_scheduled_job(job_id)` Celery task
- `core/models/job.py` – `ScheduledJob` model
- `api/routes/scheduler.py` – CRUD for scheduled jobs
- `core/models/channel.py` – `ChannelAccount`, `ChannelSession`
- `channels/dispatcher.py` – `send_message(user_id, channel, payload)`
- `channels/telegram_adapter.py` – Telegram outbound adapter
- `channel-gateways/telegram/` – inbound webhook microservice
- `api/routes/channels.py` – unified incoming message endpoint

---

### Step 4.5 – Execute Phase 4

**Tool:** GSD
**Command:** `/gsd:execute-phase`

Parallel waves:
- Wave 1: Scheduler subsystem (Celery, jobs, worker, API routes)
- Wave 2: Channel subsystem (dispatcher, adapters, gateway, models)

---

### Step 4.6 – UAT: Validate Built Features

**Tool:** GSD
**Command:** `/gsd:verify-work`

---

### Step 4.7 – Verify Phase 4

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`

Must pass:
- Scheduled job created via API, executes on cron trigger
- `WorkflowRun` record created after execution
- Telegram gateway receives webhook, resolves user, gets agent response
- Morning digest workflow runs and delivers result to web or Telegram

---

## Stage 5 – Phase 5: Hardening & Sandboxing

**Goal:** Docker sandbox for unsafe tools, ACL middleware for MCP tools, audit logging, role/permission refinement.

### Step 5.1 – Brainstorm Security Hardening

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`

Focus areas:
- Docker sandbox per-request vs. per-session container lifecycle
- ACL deny-list vs. allow-list strategy for tool registry
- Audit log schema (who called what tool, when, with what result)
- MCP tool ACL enforcement at AG-UI middleware layer

---

### Step 5.2 – Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase`

---

### Step 5.3 – Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions`

---

### Step 5.4 – Security Scan Before Implementation

**Tool:** dev-toolkit
**Command:** `/dev-toolkit:security-scan`

Run before implementing sandbox to understand attack surface and validate the design.

---

### Step 5.5 – Plan Phase 5

**Tool:** GSD
**Command:** `/gsd:plan-phase`

**Key tasks it should produce:**
- `sandbox/docker_client.py` – Docker SDK wrapper
- `sandbox/policies.py` – allowlist/denylist, base images
- `sandbox/executor.py` – container lifecycle + exec + cleanup
- `tools/sandbox_tools.py` – `bash.exec`, `python.exec` tools
- `gateway/agui_middleware.py` – TOOLCALL_START ACL enforcement
- `security/acl.py` – `check_acl(user, tool_name)` against `ToolAcl` table
- `core/models/acl.py` – `ToolAcl` model with `allow_roles`, `deny_roles`
- Audit logging middleware – structured logs per tool invocation

---

### Step 5.6 – Execute Phase 5

**Tool:** GSD
**Command:** `/gsd:execute-phase`

Parallel waves:
- Wave 1: Sandbox subsystem (docker_client, policies, executor)
- Wave 2: ACL enforcement (agui_middleware, security/acl.py, ToolAcl model)
- Wave 3: Audit logging

---

### Step 5.7 – UAT: Validate Built Features

**Tool:** GSD
**Command:** `/gsd:verify-work`

---

### Step 5.8 – Verify Phase 5

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`

Must pass:
- `bash.exec` tool runs in Docker container, not on host
- Container destroyed after execution
- Unauthorized user cannot call restricted tool (returns 403)
- Audit log entry created for every tool invocation
- MCP tool ACL enforced via AG-UI middleware

---

## Stage 6 – Final Review & Handoff

### Step 6.1 – Audit Milestone Completion

**Tool:** GSD
**Command:** `/gsd:audit-milestone`

**What it does:**
- Reviews all 5 phases against the original `PROJECT.md` goals
- Cross-references three independent sources: VERIFICATION.md + SUMMARY frontmatter + REQUIREMENTS.md traceability
- Detects orphaned requirements (in traceability table but absent from all phase verifications)
- **Blocks archival** until all REQUIREMENTS.md entries are checked complete

---

### Step 6.2 – Full Code Review

**Tool:** Superpowers
**Command:** `/superpowers:requesting-code-review`

**What it does:**
- Runs a comprehensive review across all implemented modules
- Checks against requirements, security standards, and coding quality
- Flags issues before the system goes to users

---

### Step 6.3 – Plan Gap Closure (if needed)

**Tool:** GSD
**Command:** `/gsd:plan-milestone-gaps`

If the audit reveals missing coverage, this creates phases to close all gaps. Also updates REQUIREMENTS.md traceability table with new phase assignments.

---

### Step 6.4 – Complete Milestone

**Tool:** GSD
**Command:** `/gsd:complete-milestone`

Archives the completed milestone and prepares the project for the next version cycle. Completed phase directories are archived for a cleaner project structure.

---

### Step 6.5 – Cleanup Phase Directories

**Tool:** GSD
**Command:** `/gsd:cleanup`

**What it does:**
- Archives accumulated phase directories from the completed milestone
- Keeps the `.planning/` directory clean for the next milestone cycle

Run after `/gsd:complete-milestone`.

---

## Quick Reference: Steps vs. Tools

| Step | Description | Tool | Command |
|------|-------------|------|---------|
| 0.1 | Initialize project | GSD | `/gsd:new-project` |
| 0.2 | Configure settings | GSD | `/gsd:settings` |
| 0.3 | Map codebase | GSD | `/gsd:map-codebase` |
| 0.4 | Validate planning health | GSD | `/gsd:health --repair` |
| 1.1 | Brainstorm Phase 1 | Superpowers | `/superpowers:brainstorming` |
| 1.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| 1.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| 1.4 | Plan Phase 1 | GSD | `/gsd:plan-phase` |
| 1.5 | Execute Phase 1 | GSD + Superpowers | `/gsd:execute-phase` |
| 1.6 | UAT Phase 1 | GSD | `/gsd:verify-work` |
| 1.7 | Verify Phase 1 | Superpowers | `/superpowers:verification-before-completion` |
| 1.8 | Mark Phase 1 done | GSD | `/gsd:progress` |
| 2.1 | Brainstorm Phase 2 | Superpowers | `/superpowers:brainstorming` |
| 2.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| 2.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| 2.4 | Plan Phase 2 | GSD | `/gsd:plan-phase` |
| 2.5 | Parallel agents | Superpowers | `/superpowers:dispatching-parallel-agents` |
| 2.6 | TDD per component | Superpowers | `/superpowers:test-driven-development` |
| 2.7 | UAT Phase 2 | GSD | `/gsd:verify-work` |
| 2.8 | Verify Phase 2 | Superpowers | `/superpowers:verification-before-completion` |
| 3.1 | Brainstorm Phase 3 | Superpowers | `/superpowers:brainstorming` |
| 3.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| 3.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| 3.4 | Plan Phase 3 | GSD | `/gsd:plan-phase` |
| 3.5 | Execute Phase 3 | GSD | `/gsd:execute-phase` |
| 3.6 | UAT Phase 3 | GSD | `/gsd:verify-work` |
| 3.7 | Verify Phase 3 | Superpowers | `/superpowers:verification-before-completion` |
| 4.1 | Brainstorm Phase 4 | Superpowers | `/superpowers:brainstorming` |
| 4.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| 4.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| 4.4 | Plan Phase 4 | GSD | `/gsd:plan-phase` |
| 4.5 | Execute Phase 4 | GSD | `/gsd:execute-phase` |
| 4.6 | UAT Phase 4 | GSD | `/gsd:verify-work` |
| 4.7 | Verify Phase 4 | Superpowers | `/superpowers:verification-before-completion` |
| 5.1 | Brainstorm Phase 5 | Superpowers | `/superpowers:brainstorming` |
| 5.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| 5.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| 5.4 | Security scan | dev-toolkit | `/dev-toolkit:security-scan` |
| 5.5 | Plan Phase 5 | GSD | `/gsd:plan-phase` |
| 5.6 | Execute Phase 5 | GSD | `/gsd:execute-phase` |
| 5.7 | UAT Phase 5 | GSD | `/gsd:verify-work` |
| 5.8 | Verify Phase 5 | Superpowers | `/superpowers:verification-before-completion` |
| 6.1 | Audit milestone | GSD | `/gsd:audit-milestone` |
| 6.2 | Code review | Superpowers | `/superpowers:requesting-code-review` |
| 6.3 | Plan gaps | GSD | `/gsd:plan-milestone-gaps` |
| 6.4 | Complete milestone | GSD | `/gsd:complete-milestone` |
| 6.5 | Cleanup directories | GSD | `/gsd:cleanup` |

---

## Recurring Commands During Development

Use these anytime during the project, not just at phase boundaries:

| Situation | Tool | Command |
|-----------|------|---------|
| Something is broken or failing | Superpowers | `/superpowers:systematic-debugging` |
| About to implement a feature | Superpowers | `/superpowers:brainstorming` |
| Need to capture design decisions before planning | GSD | `/gsd:discuss-phase` |
| Want to see what GSD assumes before planning | GSD | `/gsd:list-phase-assumptions` |
| Implementation is done, before committing | Superpowers | `/superpowers:verification-before-completion` |
| Validate features meet original intent | GSD | `/gsd:verify-work` |
| Need to check what's next | GSD | `/gsd:progress` |
| Resuming after a break | GSD | `/gsd:resume-work` |
| Planning directory seems broken | GSD | `/gsd:health --repair` |
| Need isolated branch for risky work | Superpowers | `/superpowers:using-git-worktrees` |
| Received code review feedback | Superpowers | `/superpowers:receiving-code-review` |
| Have a spec, need a plan | Superpowers | `/superpowers:writing-plans` |
| Urgent unplanned work appears | GSD | `/gsd:insert-phase` |
| Want to add a new phase to roadmap | GSD | `/gsd:add-phase` |
| Quick task with GSD guarantees | GSD | `/gsd:quick` |
| Quick task with full verification | GSD | `/gsd:quick --full` |
| After completing a milestone | GSD | `/gsd:cleanup` |

---

## Key Principles

1. **Always brainstorm before coding** — invoke `/superpowers:brainstorming` at the start of every phase and every non-trivial feature.
2. **Always discuss before planning** — use `/gsd:discuss-phase` to write `CONTEXT.md` before `/gsd:plan-phase`. Without it, the planner makes assumptions you may not agree with.
3. **Surface assumptions early** — use `/gsd:list-phase-assumptions` after discuss and before plan to catch wrong directions before they're committed to a plan.
4. **Always plan before executing** — use `/gsd:plan-phase` to produce a `PLAN.md` before any `/gsd:execute-phase`. The Nyquist validation layer will block low-quality plans.
5. **Never claim done without evidence** — `/superpowers:verification-before-completion` is mandatory before marking any phase complete.
6. **UAT before verify** — use `/gsd:verify-work` conversationally to validate intent before running automated verification commands.
7. **Parallelize independent work** — use `/superpowers:dispatching-parallel-agents` when modules have no shared write state.
8. **Write tests first** — `/superpowers:test-driven-development` on every non-trivial component.
9. **Resume with context** — after any break, use `/gsd:resume-work` to restore full context before continuing.
10. **Keep planning directory healthy** — run `/gsd:health` after any GSD update or if something feels off with phase tracking.
