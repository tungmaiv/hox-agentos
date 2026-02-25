# Project Context Creation Guide

> How to establish a centralized project context that works with GSD, Superpowers, and raw Claude sessions.
> Follow this guide at the start of every new project to ensure consistency across sessions and agents.

---

## Why This Matters

AI coding agents (Claude, GSD agents, Superpowers skills) start each session with zero memory of
previous sessions. Without centralized context files, agents will:

- Guess URLs, ports, and endpoint paths (often wrong)
- Re-ask the same clarifying questions every session
- Invent package manager commands (`npm` instead of `pnpm`, `pip` instead of `uv`)
- Violate project conventions (wrong logging library, wrong LLM access pattern)
- Make architectural decisions that contradict ones already settled

The solution is a small set of files — created once, updated continuously — that every agent reads
at session start. This guide explains exactly what to create and why.

---

## How Context Reaches Agents — The Loading Mechanism

Understanding exactly how each file gets loaded prevents false confidence.

### Three Reliability Tiers

```
TIER 1 — GUARANTEED (Claude Code auto-injects at every session start)
  CLAUDE.md
    ✓ Your main session
    ✓ Every GSD sub-agent (researcher, planner, executor, verifier)
    ✓ Every Superpowers skill
    ✓ Any Claude Code subprocess — no exceptions

TIER 2 — STRONGLY INSTRUCTED (agents are told to read these in CLAUDE.md)
  docs/dev-context.md
  .dev-secrets
    ✓ Main session (follows AGENT INSTRUCTIONS reliably)
    ~ GSD sub-agents (may skip when narrowly focused on a task)
    → Mitigation: self-verifying AGENT INSTRUCTIONS (see below)

TIER 3 — GSD-MANAGED (GSD passes these explicitly into sub-agent prompts)
  .planning/PROJECT.md, ROADMAP.md, STATE.md, CONTEXT.md, PLAN.md
    ✓ Reliable for all GSD-spawned agents — GSD owns this layer
```

### Why CLAUDE.md is Tier 1

Claude Code reads `CLAUDE.md` from the project root (and parent directories) at startup and
injects the full content into every conversation before the first message. When GSD spawns a
sub-agent via the Task tool, that sub-agent also runs Claude Code in the same project directory
and gets the same injection. There is no way for a session to start without `CLAUDE.md`.

### The Tier 2 Gap and How to Close It

`docs/dev-context.md` is loaded by instruction, not automatically. A GSD executor sub-agent
focused on writing a specific module might read `CLAUDE.md`, see the instruction, and proceed
without reading `dev-context.md` if it judges the file unnecessary for its narrow task.

**Two mechanisms close this gap:**

**1. Self-verifying AGENT INSTRUCTIONS (in CLAUDE.md)**
Instead of just "read dev-context.md", the instruction requires the agent to *prove* it was read
by stating specific values from it:
> "Confirm by stating: the backend URL from inside a container is `http://backend:8000`
>  and Ollama is at `http://host.docker.internal:11434`."
An agent cannot fake this without reading the file.

**2. Critical items duplicated in CLAUDE.md's DO/DON'T table**
The most-guessed-wrong items (URL routing, package manager commands, LLM access pattern)
live in `CLAUDE.md` directly — in the DO/DON'T section. Even if `dev-context.md` is skipped,
these rules are in the guaranteed Tier 1 file. `dev-context.md` is the full reference;
`CLAUDE.md` is the safety net for the most critical rules.

### Validation Test

After setting up context files, verify they work correctly by starting a fresh session and asking:

```
1. "What URL should you use to call the backend from inside a Docker container?"
   Expected: http://backend:8000 (from dev-context.md or CLAUDE.md DO/DON'T)

2. "What URL does the LiteLLM proxy use to reach Ollama?"
   Expected: http://host.docker.internal:11434

3. "What package manager do you use for Python in this project?"
   Expected: uv

4. "How do you get an LLM client in the backend?"
   Expected: from core.config import get_llm; llm = get_llm("blitz/master")

5. "What is the current implementation phase?"
   Expected: reads from .planning/STATE.md via GSD
```

If any answer is wrong or guessed, the context file that should have answered it needs
strengthening — either move the rule to CLAUDE.md or make the AGENT INSTRUCTIONS stronger.

---

## The File System

```
project-root/
├── CLAUDE.md                    ← Auto-loaded by Claude Code at every session start
├── .dev-secrets                 ← Local dev credentials (gitignored, never committed)
├── .dev-secrets.example         ← Template showing credential shape (committed)
├── .gitignore                   ← Must include .dev-secrets and .env
└── docs/
    └── dev-context.md           ← Service URLs, API endpoints, gotchas (committed)
```

| File | Committed? | Purpose |
|------|-----------|---------|
| `CLAUDE.md` | Yes | Master context: project identity, tech stack, philosophy, standards, DO/DON'T |
| `docs/dev-context.md` | Yes | Operational context: URLs, endpoints, DB tables, gotchas |
| `.dev-secrets` | **No** | Actual passwords, tokens, API keys for local dev |
| `.dev-secrets.example` | Yes | Template so agents know the shape of secrets |
| `.gitignore` | Yes | Prevents secrets from being committed |

---

## Step-by-Step Process

### Step 1 — Gather Source Material

Before writing any context file, collect the project's existing documentation:

- [ ] Architecture document (tech stack, system layers, component diagram)
- [ ] Solution blueprint or design doc (goals, constraints, MVP scope)
- [ ] Module breakdown (directory structure, module responsibilities)
- [ ] Implementation guide or roadmap (phases, milestones)
- [ ] Any ADRs (Architecture Decision Records) — decisions already made

If none of these exist, write a brief architecture document first. `CLAUDE.md` is a distillation of
these documents — you cannot fill it in without them.

**For Blitz AgentOS:** source docs were in `docs/architecture/`, `docs/design/`, `docs/implementation/`.

---

### Step 2 — Create `.gitignore`

Do this first, before anything else touches the repo.

**Minimum contents:**
```gitignore
# Secrets
.env
.dev-secrets

# Language artifacts
__pycache__/
*.py[cod]
.venv/
node_modules/
.next/

# Logs (often contain sensitive data)
logs/

# OS
.DS_Store
```

**Key rule:** `.env` and `.dev-secrets` must always be gitignored. Add them before any dev work begins.

---

### Step 3 — Create `CLAUDE.md`

This is the most important file. Claude Code reads it automatically at every session start.
GSD sub-agents and Superpowers skill sessions inherit it the same way.

**Structure — use this section order every time:**

#### 0. Header + AGENT INSTRUCTIONS (always first)
```markdown
# <Project Name> — Project Context for Claude

> This file is read automatically at every Claude Code session start.

## AGENT INSTRUCTIONS — Read Before Any Task

Before starting any implementation or testing task, you MUST read:
1. `docs/dev-context.md` — service URLs, API endpoints, gotchas. Never guess a URL.
2. `.dev-secrets` (if it exists) — actual credentials for local dev.

When you discover something new: update `docs/dev-context.md` immediately.
```

#### 1. Project Identity
Answer these questions:
- What does this system do in one sentence?
- Who uses it and at what scale? (affects YAGNI decisions)
- What is the deployment target? (Docker Compose, Kubernetes, serverless, etc.)
- What is the MVP scope vs. future scope?
- Where are the key docs? (link them here)

#### 2. Technology Stack
A table of every locked technology with exact version. Include:
- Frontend framework + version
- Backend framework + version
- Database(s) + version
- Auth/identity system
- Message queue / cache
- Any AI/LLM-specific tools
- Key libraries (ORM, validation, logging)
- LLM providers and routing strategy

> **Why exact versions matter:** agents often use different API patterns across major versions.
> Specifying `Pydantic v2` vs `v1` or `Next.js 15 App Router` vs `Pages Router` prevents
> entire classes of wrong code.

For AI projects, also add a **Model Aliases table** explaining what alias maps to what provider
model, and the single function to call to get an LLM client.

#### 3. Development Environment
Three subsections:

**Package Management table** — explicit tool for each ecosystem. Example:
| Ecosystem | Tool | Rule |
|-----------|------|------|
| Python | uv | Never use pip directly |
| Node.js | pnpm | Never use npm or yarn |
| GitHub | gh CLI | Use for PRs and issues |

**Service Port Map** — every service with its port. Critical: annotate which services run
on the host vs. inside Docker if they differ.

**Common Commands** — the 6–10 commands a developer uses every day (start services, run
tests, apply migrations, etc.). Using the correct package manager (uv/pnpm) from the start.

#### 4. Coding Philosophy
Cover: DRY, YAGNI, KISS, and any domain-specific principles (Security-First, Async-First, etc.).

For each principle, write **concrete project-specific rules**, not just abstract definitions:
- DRY → "Extract shared logic only when used in 3+ places; `core/config.py` is the single config source"
- YAGNI → "Design for 100 users, not millions; no Kubernetes until post-MVP"
- KISS → "Each module does one thing; prefer flat structure over deep nesting"

#### 5. Language-Specific Standards
One section per language used. Cover:
- Type annotation rules
- Error handling patterns
- Logging library and forbidden alternatives
- Import style
- Key patterns (async DB session, Pydantic models, etc.)

Include short **correct vs. wrong** code snippets for the most commonly violated rules.

#### 6. Architecture Invariants
The non-negotiables — rules that, if broken, cause security holes or data corruption.
Write these as absolute statements:

- Memory isolation: all queries parameterized on `user_id` from JWT, never from request body
- Credential containment: never log tokens, never pass to LLMs
- Single registries: one place to register tools, one function to get an LLM client
- Schema versioning: any persisted JSON schema must have a version field

#### 7. Directory Structure (annotated)
A tree of the project's directory layout with a one-line comment on each key directory/file.
Agents use this to know where to put new code and where to find existing code.

#### 8. Key Constraints
A table of hard constraints and the reason behind each. Example:
| Constraint | Reason |
|-----------|--------|
| PostgreSQL is the sole database | Operational simplicity at 100-user scale |
| No Kubernetes for MVP | YAGNI — Docker Compose is sufficient |

Constraints prevent agents from "improving" things by adding complexity that violates
architectural decisions already made.

#### 9. Implementation Phases
If the project has a phased roadmap (common with GSD), list phases and their gate criteria.
Agents use this to understand what phase is current and what should/shouldn't exist yet.

#### 10. ADR Summary
A condensed table of Architecture Decision Records. For each ADR: the decision and its
key consequence. This prevents agents from reopening settled debates.

#### 11. DO / DON'T Quick Reference
A set of two-column tables (DO | DON'T) covering the most critical rules in scannable form.
Group by topic: package management, URLs, LLM access, credentials, memory, Python, TypeScript,
architecture.

> **Why a separate DO/DON'T section when the rules are already in sections 4–10?**
> Agents skim. Sections 4–10 are reference material for when an agent needs detail.
> The DO/DON'T section is a pre-flight checklist that catches 90% of violations
> before the agent writes a single line of code.

#### 12. GSD + Superpowers Workflow
If the project uses GSD and/or Superpowers, add a section explaining:
- What each tool does and its persistence model
- Key commands for each
- The recommended per-feature workflow

---

### Step 4 — Create `docs/dev-context.md`

This covers operational, environment-specific details that change between dev/staging/prod
and that agents frequently get wrong.

**Sections to include:**

#### 1. URL Reference — Docker-Internal vs Localhost
A table with every service showing:
- URL from the browser / host CLI
- URL from inside a container

If any service runs on the host (not Dockerized), call it out explicitly with a note on how
containers reach it (e.g., `host.docker.internal`).

#### 2. API Endpoints
One table per domain (auth, users, core features, admin, webhooks). Columns: method, path, description.
This eliminates endpoint guessing — the single most common agent error in API-heavy projects.

#### 3. Frontend Routes
All page routes with descriptions. Agents need this when writing redirect logic or integration tests.

#### 4. Auth / Identity
- Admin console URL
- Realm or tenant name
- OIDC/token endpoints
- Role definitions (name → what it can do)
- Test account names (actual passwords go in `.dev-secrets`)

#### 5. Database
- Connection strings (host vs. container)
- Key tables with one-line description each
- Any important indexes or constraints worth knowing

#### 6. External Services / Integrations
One subsection per external service: its URL (internal and external), auth method,
key endpoints used by this project.

#### 7. Common Gotchas Table
The most important section. Format:
| Situation | Wrong | Correct |
|-----------|-------|---------|

Populate from real mistakes observed during development. Every time an agent makes a
URL mistake or uses a wrong command, add it here.

#### 8. Update Log
A simple table at the bottom:
| Date | Change | Added by |

Agents append to this when they discover new information. It creates a lightweight
audit trail of what was learned and when.

---

### Step 5 — Create `.dev-secrets.example`

A template file showing the shape of every secret needed for local development.
All values are blank — this file is committed. The actual values live in `.dev-secrets`.

**Cover:**
- Database password
- Auth system admin password
- Test account usernames and passwords (one per role)
- LLM API keys (all providers used)
- External service tokens (Telegram bot token, webhook secrets, etc.)
- Encryption keys

```bash
# Example structure
POSTGRES_PASSWORD=
KEYCLOAK_ADMIN_PASSWORD=

# Test accounts
TEST_ADMIN_USER=admin@example.local
TEST_ADMIN_PASSWORD=
TEST_EMPLOYEE_USER=employee@example.local
TEST_EMPLOYEE_PASSWORD=

# LLM providers
ANTHROPIC_KEY=
OPENAI_KEY=
```

Then create `.dev-secrets` (gitignored) by copying this file and filling in real values:
```bash
cp .dev-secrets.example .dev-secrets
# Fill in .dev-secrets with real values
```

---

### Step 6 — Update GSD (if used)

If the project uses GSD for phase planning, initialize it after `CLAUDE.md` is in place:

```
/gsd:new-project --auto @docs/design/blueprint.md
```

GSD will create:
- `.planning/PROJECT.md` — goals, milestones, success criteria
- `.planning/ROADMAP.md` — phases
- `.planning/REQUIREMENTS.md` — detailed requirements

These complement `CLAUDE.md`: GSD files track *what to build next*; `CLAUDE.md` defines
*how to build it*.

---

## Maintenance Rules

Context files are only useful if they stay accurate. Establish these rules at project start:

| Trigger | Action |
|---------|--------|
| New API endpoint added | Update `docs/dev-context.md` endpoint table |
| New service added to Docker Compose | Update URL reference table in `docs/dev-context.md` |
| New package manager command discovered | Update Common Commands in `CLAUDE.md` |
| Agent makes a URL mistake | Add to Gotchas table in `docs/dev-context.md` |
| Architectural decision made | Add ADR summary row to `CLAUDE.md` |
| New secret required | Add key to `.dev-secrets.example` + update `.dev-secrets` |
| New technology added to stack | Update Technology Stack table in `CLAUDE.md` |
| Convention violated repeatedly | Add a DO/DON'T row to `CLAUDE.md` |


The `docs/dev-context.md` Update Log (section 8) serves as the running record of these changes.

---

## Checklist — New Project

Copy this checklist when starting a new project:

```
## Project Context Setup

### Prerequisites
- [ ] Architecture document exists (or written before starting context files)
- [ ] Tech stack decisions are made and recorded

### Files to Create
- [ ] .gitignore (with .env and .dev-secrets blocked)
- [ ] CLAUDE.md
  - [ ] AGENT INSTRUCTIONS block (top, before all sections)
  - [ ] DO / DON'T quick reference tables
  - [ ] 1. Project Identity (name, scale, scope, key docs)
  - [ ] 2. Technology Stack (exact versions, model aliases if AI project)
  - [ ] 3. Development Environment (package mgmt, port map, common commands)
  - [ ] 4. Coding Philosophy (DRY, YAGNI, KISS + project-specific principles)
  - [ ] 5. Language Standards (type rules, logging, imports, patterns)
  - [ ] 6. Architecture Invariants (security, isolation, single registries)
  - [ ] 7. Directory Structure (annotated tree)
  - [ ] 8. Key Constraints (with reasons)
  - [ ] 9. Implementation Phases (if phased roadmap)
  - [ ] 10. ADR Summary (if decisions already made)
  - [ ] 11. GSD + Superpowers workflow (if using these tools)
- [ ] docs/dev-context.md
  - [ ] URL reference (docker-internal vs localhost)
  - [ ] API endpoints (grouped by domain)
  - [ ] Frontend routes
  - [ ] Auth / identity (roles, OIDC endpoints, test account names)
  - [ ] Database (connection strings, key tables)
  - [ ] External service URLs
  - [ ] Common Gotchas table
  - [ ] Update Log (empty, ready for agents to append to)
- [ ] .dev-secrets.example (all keys, no values)
- [ ] .dev-secrets (copied from example, filled with real values, gitignored)

### GSD Initialization (if using GSD)
- [ ] /gsd:new-project run — .planning/ directory created
- [ ] PROJECT.md, ROADMAP.md, REQUIREMENTS.md verified

### Validation
- [ ] Start a new Claude Code session — CLAUDE.md loads without errors
- [ ] Ask Claude: "What URL should you use to call the backend from inside a container?"
      Expected: reads from dev-context.md, gives correct answer
- [ ] Ask Claude: "What package manager should you use for Python?"
      Expected: uv (or project-specific tool)
- [ ] Ask Claude: "How do you get an LLM client in this project?"
      Expected: get_llm() (or project-specific pattern)
```

---

## Anti-Patterns to Avoid

**Putting credentials in `CLAUDE.md`**
`CLAUDE.md` is committed to git. Credentials go in `.dev-secrets` (gitignored).
`CLAUDE.md` references the shape — `.dev-secrets` holds the values.

**Writing CLAUDE.md as abstract principles only**
"Use DRY" is useless. "Extract shared logic only when used in 3+ places; `core/config.py`
is the single config source — never read `os.environ` directly in business logic" is actionable.
Every principle needs at least one concrete, project-specific rule.

**One giant context file**
`CLAUDE.md` is read at every session start — keep it focused on *how to build*.
`docs/dev-context.md` covers *how the system is wired*. Separate concerns; agents can
then choose which to read based on the task.

**Treating context files as write-once**
Context files rot fast. The maintenance rules above (and the Update Log) must be followed.
An outdated `dev-context.md` is worse than none — it confidently misleads agents.

**Skipping the DO / DON'T section**
The detailed sections (philosophy, standards, invariants) are reference material.
Agents doing fast tasks skip them. The DO / DON'T tables are the safety net
for agents who skim — they must be present and placed near the top of `CLAUDE.md`.

---

## Reference — Files Created for Blitz AgentOS

| File | Location |
|------|----------|
| Master context | `CLAUDE.md` |
| Operational context | `docs/dev-context.md` |
| Secrets template | `.dev-secrets.example` |
| Git ignore rules | `.gitignore` |
| This guide | `docs/guideline/project-context-guide.md` |
