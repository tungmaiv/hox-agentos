# Project Implementation Workflow
## Using GSD + Superpowers for Any Project

> **Purpose:** A reusable, step-by-step implementation workflow that works for any software project.
> Adapt the phase goals and key tasks to your project — the workflow structure stays the same every time.
>
> **Based on:** GSD v1.20.6 + Superpowers (current installed version)
> **Reference implementation:** `docs/implementation/implementation-guide.md` (Blitz AgentOS)

---

## 1. Tool Overview

### Two Tools, Two Purposes

| Tool | What It Does | Persists? |
|------|-------------|-----------|
| **GSD** | Project initialization, roadmap, phase planning, progress tracking, milestone management | Yes — writes to `.planning/` directory, survives session resets |
| **Superpowers** | Coding discipline: brainstorming, TDD, parallel agents, verification, debugging, code review | No — session-only skills that read `CLAUDE.md` for project context |

> GSD internally calls Superpowers skills during execution (e.g., TDD inside `/gsd:execute-phase`).
> They are complementary, not competing. Think of GSD as the project manager and Superpowers as the engineering discipline layer.

### How Context Flows

```
CLAUDE.md (permanent)
    │
    ├── Read by every Claude session, every GSD sub-agent, every Superpowers skill
    │
    └── docs/dev-context.md (permanent)
            │
            └── Read when working with services, URLs, credentials

.planning/ (GSD-managed)
    ├── PROJECT.md     — goals, milestones, success criteria
    ├── ROADMAP.md     — phase list with gate criteria
    ├── REQUIREMENTS.md — traceable requirements
    └── phase-N/
        ├── CONTEXT.md  — your decisions for this phase (from /gsd:discuss-phase)
        ├── PLAN.md     — atomic task list (from /gsd:plan-phase)
        └── VERIFICATION.md — evidence of completion (from /gsd:verify-work)
```

---

## 2. The Universal Workflow

### High-Level Shape

Every project follows this macro structure:

```
Stage 0: Project Setup
    ↓
Stage 1: Phase 1
    ↓
Stage 2: Phase 2
    ↓
    ...
Stage N: Phase N
    ↓
Stage Final: Review & Milestone Close
```

### The Phase Inner Loop (repeat for EVERY phase)

```
  ┌─────────────────────────────────────────────────────────┐
  │                  PHASE INNER LOOP                        │
  │                                                          │
  │  1. Brainstorm          (Superpowers)                    │
  │       ↓                                                  │
  │  2. Discuss Phase       (GSD)        → CONTEXT.md        │
  │       ↓                                                  │
  │  3. List Assumptions    (GSD)        → correct if wrong  │
  │       ↓                                                  │
  │  4. Plan Phase          (GSD)        → PLAN.md           │
  │       ↓                                                  │
  │  5. Execute Phase       (GSD)        → code written      │
  │       ↓                                                  │
  │  6. UAT                 (GSD)        → intent validated   │
  │       ↓                                                  │
  │  7. Verify              (Superpowers) → evidence gathered │
  │       ↓                                                  │
  │  8. Code Review         (Superpowers) → quality checked  │
  │       ↓                                                  │
  │  9. Mark Complete       (GSD)        → progress updated  │
  └─────────────────────────────────────────────────────────┘
```

This loop is non-negotiable. Skipping steps causes downstream problems:
- Skip **Brainstorm** → implement the wrong thing
- Skip **Discuss** → planner makes assumptions you disagree with
- Skip **List Assumptions** → wrong direction committed to a plan
- Skip **UAT** → built the right code, wrong behavior
- Skip **Verify** → claim done without evidence
- Skip **Code Review** → quality and security issues ship

---

## 3. Stage 0 — Project Setup

Do this once at the start of every project, before writing any code.

---

### Step 0.1 — Create Project Context Files

**Before GSD can run, it needs context.** Create the project context files first.
Follow the full guide in `docs/guideline/project-context-guide.md`.

**Minimum required:**
- [ ] `CLAUDE.md` — project identity, tech stack, philosophy, standards, DO/DON'T
- [ ] `docs/dev-context.md` — service URLs, endpoints, gotchas
- [ ] `.dev-secrets.example` + `.dev-secrets` — credential shapes and values
- [ ] `.gitignore` — with `.env` and `.dev-secrets` blocked

**Why first:** GSD sub-agents and Superpowers skills read `CLAUDE.md` at session start.
Without it, every agent starts blind and makes up conventions.

---

### Step 0.2 — Initialize Project with GSD

**Tool:** GSD
**Command:** `/gsd:new-project`

**What it does:**
- Reads your design docs (blueprint, module breakdown, requirements)
- Asks clarifying questions about goals, constraints, team, timeline
- Creates `.planning/PROJECT.md` — goals, milestones, success criteria
- Creates `.planning/ROADMAP.md` — phased plan with gate criteria
- Creates `.planning/REQUIREMENTS.md` — traceable requirement list

**How to invoke:**
```
/gsd:new-project

> "Initialize a new project. The solution blueprint is at docs/design/blueprint.md
>  and module breakdown is at docs/design/module-breakdown.md."
```

**Auto mode** (skips interactive stops, runs research → requirements → roadmap end-to-end):
```
/gsd:new-project --auto @docs/design/blueprint.md
```

**Output:** `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`

---

### Step 0.3 — Configure GSD Settings

**Tool:** GSD
**Command:** `/gsd:settings`

**Settings to configure:**

| Setting | Options | Recommendation |
|---------|---------|----------------|
| Model profile | `quality` / `balanced` / `budget` | `balanced` for features, `quality` for security-critical phases |
| Verification agent | `true` / `false` | Always `true` |
| Code review agent | `true` / `false` | `true` for production projects |
| Git branching | `none` / `phase` / `milestone` | `phase` creates `gsd/phase-N-slug` branches automatically |
| Brave Search | set `BRAVE_API_KEY` env var | Enables web search in researcher agents |

**Persist defaults across all projects** (`~/.gsd/defaults.json`):
```json
{
  "profile": "balanced",
  "verification": true,
  "code_review": true,
  "branching": "phase"
}
```

---

### Step 0.4 — Map Existing Codebase (skip for new projects)

**Tool:** GSD
**Command:** `/gsd:map-codebase`

Run this only if starting from an existing codebase, not a blank repo.

**What it does:**
- Spawns parallel mapper agents across the repo
- Produces structured analysis in `.planning/codebase/` covering:
  - Tech stack and framework usage
  - Module architecture and boundaries
  - Code quality signals
  - Concerns and risks

---

### Step 0.5 — Validate Planning Directory Health

**Tool:** GSD
**Command:** `/gsd:health --repair`

**Always run after init** to catch setup issues before work begins.

**What it checks:**
- `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `config.json` present and valid
- Phase numbering consistent
- Frontmatter well-formed

**`--repair` flag** auto-fixes `config.json` and `STATE.md` with timestamped backups.

---

## 4. Phase Stages — The Inner Loop in Detail

Apply these steps to **every phase** in your roadmap. Replace phase-specific content with your project's goals and tasks.

---

### Step N.1 — Brainstorm

**Tool:** Superpowers
**Command:** `/superpowers:brainstorming`
**Invoke:** Before touching any code in this phase

**What it does:**
- Explores design decisions and surfaces ambiguities before implementation
- Helps you think through alternatives you might not have considered
- Produces a clear intent summary that feeds into the discussion step

**Focus your brainstorm on:**
- What is the core technical challenge of this phase?
- What are the 2-3 ways this could be built? Which is right for this project?
- What could go wrong? What are the dependencies?
- What decisions need to be made before planning?

**Example prompt:**
```
/superpowers:brainstorming

"I'm about to plan Phase 2: [your phase goal].
 Help me think through [key design decision] and [key design decision].
 Constraints: [list relevant constraints from CLAUDE.md]."
```

---

### Step N.2 — Gather Phase Context

**Tool:** GSD
**Command:** `/gsd:discuss-phase n`
**Invoke:** After brainstorm, before planning

**What it does:**
- Asks adaptive questions to capture your design decisions for this specific phase
- Writes `CONTEXT.md` into the phase directory
- This file flows into the researcher, planner, and plan checker — they honor your decisions

**Why this matters:** Without `CONTEXT.md`, `/gsd:plan-phase` warns you and makes assumptions.
The planner is smart but it doesn't know your preferences. `/gsd:discuss-phase` is how you tell it.

**What to capture:**
- Which modules/features are in scope vs. deferred to a later phase
- Non-obvious technology choices for this phase
- Integration constraints with already-built phases
- Any team decisions made outside of Claude (in meetings, design docs, etc.)

---

### Step N.3 — Surface Planning Assumptions

**Tool:** GSD
**Command:** `/gsd:list-phase-assumptions n`
**Invoke:** After `/gsd:discuss-phase`, before `/gsd:plan-phase`

**What it does:**
- Shows what GSD will assume about the implementation approach
- Lets you correct wrong assumptions before they become a plan
- Prevents silent wrong direction — cheaper to correct assumptions than to rewrite a plan

**What to look for:**
- Technology choices that differ from your intent
- Scope assumptions (includes too much or too little)
- Ordering assumptions (tasks planned in wrong sequence)
- Integration assumptions (connects to wrong module or wrong API)

If an assumption is wrong, correct it before proceeding:
```
"That assumption is wrong — we're using X not Y because [reason].
 Please update your assumptions and show me the list again."
```

---

### Step N.4 — Plan the Phase

**Tool:** GSD
**Command:** `/gsd:plan-phase n --skip-research`
**Invoke:** After assumptions are correct

**What it does:**
- Reads phase roadmap entry + your `CONTEXT.md`
- Researches implementation approach (web search if `BRAVE_API_KEY` set)
- Creates `PLAN.md` with atomic, ordered, dependency-aware tasks
- Runs **Nyquist validation** — blocks low-quality plans before execution
- Verifies all `REQUIREMENTS.md` entries for this phase appear in the plan

**What a good PLAN.md looks like:**
- Tasks are atomic (one file or one function per task, not "implement the whole module")
- Dependencies are explicit (task 3 requires task 1 and 2 to be done)
- Each task has clear acceptance criteria
- Wave grouping is visible (which tasks can run in parallel)

**If the plan is rejected by Nyquist:** Read the feedback, adjust your CONTEXT.md, and re-run `/gsd:plan-phase`.

---

### Step N.5 — Execute the Phase

**Tool:** GSD
**Command:** `/gsd:execute-phase`

**What it does:**
- Reads `PLAN.md` and identifies independent task groups (waves)
- Wave 1: runs tasks with no dependencies in parallel via subagents
- Wave 2: runs tasks dependent only on Wave 1, again in parallel
- Each subagent uses TDD internally (`superpowers:test-driven-development`)
- Updates `ROADMAP.md` and `REQUIREMENTS.md` traceability after completion

**Parallelism rules:**
- Tasks that write to different files: safe to parallelize
- Tasks that write to the same file: must be sequential
- Tasks where one depends on another's output: must be sequential

**If you want manual control over parallelism** (instead of letting GSD decide):
```
/superpowers:dispatching-parallel-agents

"Run these 3 independent tasks in parallel:
 Agent 1: [task description, files involved]
 Agent 2: [task description, files involved]
 Agent 3: [task description, files involved]"
```

**For non-trivial individual components**, apply TDD before implementing:
```
/superpowers:test-driven-development

"I'm implementing [component]. Write tests first, then implement to pass them."
```

---

### Step N.6 — UAT: Validate Intent

**Tool:** GSD
**Command:** `/gsd:verify-work`
**Invoke:** After execution, before automated verification

**What it does:**
- Conversational UAT — describes what was built and checks your intent is met
- Surfaces gaps between what was planned and what was actually implemented
- Creates UAT issues for gaps; you decide whether to fix now or log for later

**This is different from automated verification.** UAT answers:
*"Did we build the right thing?"*
Verification (Step N.7) answers: *"Did we build it correctly?"*

---

### Step N.7 — Verify: Gather Evidence

**Tool:** Superpowers
**Command:** `/superpowers:verification-before-completion`
**Invoke:** After UAT passes, before marking complete

**What it does:**
- Runs verification commands and collects actual output as evidence
- Requires real evidence before allowing any claim of "done"
- Blocks you from declaring a phase complete without proof

**Define your phase gate criteria** (what commands must pass):
```
/superpowers:verification-before-completion

"Phase N is complete when:
 1. [test command] passes with [expected output]
 2. [health check] returns [expected response]
 3. [integration test] demonstrates [expected behavior]

 Run each verification and show me the actual output."
```

Gate criteria should come from your `ROADMAP.md` phase entry. If they're not there, add them before planning.

---

### Step N.8 — Code Review

**Tool:** Superpowers
**Command:** `/superpowers:requesting-code-review`
**Invoke:** After verification passes

**What it does:**
- Reviews the code written in this phase against requirements, security standards, and quality
- Flags issues before they compound in later phases
- For security-sensitive phases, consider using `/dev-toolkit:security-scan` as well

**When receiving review feedback:**
```
/superpowers:receiving-code-review

"Here is the code review feedback: [paste feedback]
 Help me evaluate which items to fix now vs. log as tech debt."
```

---

### Step N.9 — Mark Phase Complete

**Tool:** GSD
**Command:** `/gsd:progress`

Shows current phase status and routes to the next action.
GSD marks the phase complete in `STATE.md` and `ROADMAP.md`, then prompts for the next phase.

---

## 5. Stage Final — Milestone Review & Close

Run these steps after all phases in a milestone are complete.

---

### Step F.1 — Audit Milestone Completion

**Tool:** GSD
**Command:** `/gsd:audit-milestone`

**What it does:**
- Reviews all phases against original `PROJECT.md` goals
- Cross-references: VERIFICATION.md + SUMMARY frontmatter + REQUIREMENTS.md traceability
- Detects orphaned requirements (in requirements list but absent from all verifications)
- **Blocks archival** until all requirements are confirmed complete

If gaps are found, don't skip them — close them before proceeding.

---

### Step F.2 — Full Code Review

**Tool:** Superpowers
**Command:** `/superpowers:requesting-code-review`

A milestone-level review across all implemented modules — more comprehensive than per-phase reviews.
Catches issues that only appear when the whole system is considered together.

---

### Step F.3 — Close Gaps (if found)

**Tool:** GSD
**Command:** `/gsd:plan-milestone-gaps`

If the audit reveals missing coverage, this creates new phases to close all identified gaps.
Also updates `REQUIREMENTS.md` traceability with new phase assignments.

After creating gap-closure phases, run them through the standard Phase Inner Loop (Steps N.1–N.9).

---

### Step F.4 — Complete Milestone

**Tool:** GSD
**Command:** `/gsd:complete-milestone`

Archives the completed milestone and prepares the project for the next version cycle.

---

### Step F.5 — Clean Up

**Tool:** GSD
**Command:** `/gsd:cleanup`

Archives accumulated phase directories from the completed milestone.
Keeps `.planning/` clean for the next milestone cycle.

---

## 6. Recurring Commands — Use Anytime

These are not tied to a phase step — invoke them whenever the situation arises.

| Situation | Tool | Command |
|-----------|------|---------|
| Something is broken or failing | Superpowers | `/superpowers:systematic-debugging` |
| About to implement any feature | Superpowers | `/superpowers:brainstorming` |
| Have a spec, need a written plan | Superpowers | `/superpowers:writing-plans` |
| Need isolated branch for risky work | Superpowers | `/superpowers:using-git-worktrees` |
| Received code review feedback | Superpowers | `/superpowers:receiving-code-review` |
| Implementation done, before commit | Superpowers | `/superpowers:verification-before-completion` |
| Want to check what's next | GSD | `/gsd:progress` |
| Resuming after any break | GSD | `/gsd:resume-work` |
| Validate features meet original intent | GSD | `/gsd:verify-work` |
| Need to capture decisions before planning | GSD | `/gsd:discuss-phase` |
| Want to see GSD's assumptions | GSD | `/gsd:list-phase-assumptions` |
| Urgent unplanned work appears | GSD | `/gsd:insert-phase` |
| Add new phase to end of roadmap | GSD | `/gsd:add-phase` |
| Remove a planned future phase | GSD | `/gsd:remove-phase` |
| Quick task with GSD guarantees | GSD | `/gsd:quick` |
| Quick task with full verification | GSD | `/gsd:quick --full` |
| Planning directory feels broken | GSD | `/gsd:health --repair` |
| After completing a milestone | GSD | `/gsd:cleanup` |
| Starting a new milestone | GSD | `/gsd:new-milestone` |
| Check project todos | GSD | `/gsd:check-todos` |
| Capture an idea as a todo | GSD | `/gsd:add-todo` |
| GSD needs updating | GSD | `/gsd:update` |

---

## 7. Full Command Reference Table

| Step | Description | Tool | Command |
|------|-------------|------|---------|
| 0.1 | Create context files | Manual | See `docs/guideline/project-context-guide.md` |
| 0.2 | Initialize project | GSD | `/gsd:new-project` |
| 0.3 | Configure settings | GSD | `/gsd:settings` |
| 0.4 | Map existing codebase | GSD | `/gsd:map-codebase` |
| 0.5 | Validate planning health | GSD | `/gsd:health --repair` |
| N.1 | Brainstorm phase | Superpowers | `/superpowers:brainstorming` |
| N.2 | Gather phase context | GSD | `/gsd:discuss-phase` |
| N.3 | Surface assumptions | GSD | `/gsd:list-phase-assumptions` |
| N.4 | Plan phase | GSD | `/gsd:plan-phase` |
| N.5a | Execute phase (GSD-managed) | GSD | `/gsd:execute-phase` |
| N.5b | Dispatch parallel agents (manual) | Superpowers | `/superpowers:dispatching-parallel-agents` |
| N.5c | TDD for component | Superpowers | `/superpowers:test-driven-development` |
| N.6 | UAT: validate intent | GSD | `/gsd:verify-work` |
| N.7 | Verify: gather evidence | Superpowers | `/superpowers:verification-before-completion` |
| N.8 | Code review | Superpowers | `/superpowers:requesting-code-review` |
| N.9 | Mark phase complete | GSD | `/gsd:progress` |
| F.1 | Audit milestone | GSD | `/gsd:audit-milestone` |
| F.2 | Full code review | Superpowers | `/superpowers:requesting-code-review` |
| F.3 | Plan gaps | GSD | `/gsd:plan-milestone-gaps` |
| F.4 | Complete milestone | GSD | `/gsd:complete-milestone` |
| F.5 | Cleanup directories | GSD | `/gsd:cleanup` |

---

## 8. Key Principles

1. **Context before code.**
   Create `CLAUDE.md` and `docs/dev-context.md` before running `/gsd:new-project`.
   Agents that start without context invent conventions and make wrong assumptions.

2. **Brainstorm before every phase.**
   `/superpowers:brainstorming` surfaces the design decisions you need to make before planning.
   Skipping it means planning with incomplete thinking.

3. **Discuss before planning.**
   `/gsd:discuss-phase` writes `CONTEXT.md`. Without it, the planner makes assumptions.
   Always run it before `/gsd:plan-phase`.

4. **Surface assumptions before committing to a plan.**
   `/gsd:list-phase-assumptions` is cheap. Rewriting a bad plan is expensive.
   Always run it between `/gsd:discuss-phase` and `/gsd:plan-phase`.

5. **Plan before executing.**
   `/gsd:plan-phase` produces a `PLAN.md` that GSD's Nyquist validation reviews.
   A rejected plan is a feature, not a bug — it catches problems before they become code.

6. **UAT before verify.**
   `/gsd:verify-work` (intent) comes before `/superpowers:verification-before-completion` (evidence).
   Building the wrong thing correctly is still wrong.

7. **Never claim done without evidence.**
   `/superpowers:verification-before-completion` requires actual command output.
   "It should work" is not evidence. Run the commands, show the results.

8. **Parallelize independent work.**
   Use `/superpowers:dispatching-parallel-agents` or `/gsd:execute-phase` (which does it automatically).
   Modules that write to different files are always safe to parallelize.

9. **Write tests first.**
   `/superpowers:test-driven-development` on every non-trivial component.
   Tests written after implementation always pass — they prove nothing.

10. **Resume with context.**
    After any break (end of day, context reset), run `/gsd:resume-work` before continuing.
    GSD reconstructs your full context from `.planning/` files.

11. **Keep planning directory healthy.**
    Run `/gsd:health` after any GSD update or if phase tracking feels inconsistent.

12. **Update `docs/dev-context.md` continuously.**
    Every new endpoint, URL, or gotcha discovered during work gets added immediately.
    Stale context is worse than no context — it confidently misleads.

---

## 9. Common Failure Modes and Fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Agent uses wrong URL or port | Skipped reading `docs/dev-context.md` | Add to AGENT INSTRUCTIONS in `CLAUDE.md`; add to Gotchas table |
| Plan includes things not in scope | No `CONTEXT.md` — planner made assumptions | Run `/gsd:discuss-phase` before planning |
| Plan direction is wrong | Assumptions not checked | Run `/gsd:list-phase-assumptions` and correct before planning |
| Phase declared done, but features are missing | Skipped UAT | Always run `/gsd:verify-work` before verification |
| Tests pass but behavior is wrong | TDD skipped — tests written after code | Use `/superpowers:test-driven-development` from the start |
| Security issue found after shipping | Code review skipped | Run `/superpowers:requesting-code-review` after every phase |
| Agent re-invents conventions each session | No `CLAUDE.md` | Create it; it's session-persistent context |
| Session starts without context | Skipped `/gsd:resume-work` | Always resume with `/gsd:resume-work` after a break |
| Planning directory is corrupted | GSD update or interrupted session | Run `/gsd:health --repair` |
| Milestone has orphaned requirements | Phases skipped requirements tracking | Run `/gsd:audit-milestone` — it finds and blocks these |

---

## 10. Adapting This Workflow to Different Project Types

### Web API (backend only)
- Typical phases: Skeleton + auth → Core domain + DB → Business logic + tests → Security hardening → Observability
- Emphasis: TDD on every endpoint, security scan before Phase Final, API contract tests

### Full-stack web app
- Typical phases: Infra + auth skeleton → Backend API → Frontend → Integration + E2E → Hardening
- Emphasis: Keep backend and frontend in separate parallel waves; API contract must be stable before frontend wave

### AI / Agent system
- Typical phases: Infra + LLM gateway → Agent orchestration + tools + memory → UI + streaming → Scheduling + channels → Security hardening
- Emphasis: Memory isolation tests are mandatory; credential containment verified at every phase; LLM aliases defined in `CLAUDE.md` before Phase 1

### CLI tool
- Typical phases: Core functionality → Input parsing + validation → Output formatting → Error handling → Tests + distribution
- Emphasis: Lighter infrastructure, heavier TDD, `/gsd:quick` often sufficient for small tasks

### Microservice
- Typical phases: Service skeleton + contract → Business logic → Integration with upstream/downstream → Testing + observability
- Emphasis: API contract defined and frozen early; consumer-driven contract tests; `/superpowers:dispatching-parallel-agents` for parallel service development

### When to use `/gsd:quick` instead of the full loop
Use `/gsd:quick` for:
- A single bug fix with clear scope
- A small, well-defined feature addition
- A configuration change
- A documentation update

Use the full Phase Inner Loop for:
- Any feature that touches more than 2 modules
- Any security-related work
- Any feature with user-facing behavior
- Anything that requires an architectural decision

---

## 11. New Project Checklist

Copy this for every new project:

```
## New Project Setup

### Before Any Code
- [ ] Architecture document written (or existing docs identified)
- [ ] CLAUDE.md created (follows docs/guideline/project-context-guide.md)
- [ ] docs/dev-context.md created
- [ ] .dev-secrets.example created
- [ ] .dev-secrets created (from example, gitignored)
- [ ] .gitignore created (.env and .dev-secrets blocked)

### GSD Initialization
- [ ] /gsd:new-project run — PROJECT.md, ROADMAP.md, REQUIREMENTS.md created
- [ ] /gsd:settings configured (profile, verification, branching)
- [ ] /gsd:health --repair run — planning directory validated
- [ ] /gsd:map-codebase run (skip if blank repo)

### Phase Gate Criteria Defined
- [ ] Every phase in ROADMAP.md has explicit gate criteria (what must pass before next phase)

### Per-Phase (repeat for each phase)
- [ ] /superpowers:brainstorming — design decisions explored
- [ ] /gsd:discuss-phase — CONTEXT.md written
- [ ] /gsd:list-phase-assumptions — assumptions verified
- [ ] /gsd:plan-phase — PLAN.md approved
- [ ] /gsd:execute-phase (or dispatching-parallel-agents) — code written
- [ ] /gsd:verify-work — intent confirmed (UAT)
- [ ] /superpowers:verification-before-completion — evidence gathered
- [ ] /superpowers:requesting-code-review — quality checked
- [ ] /gsd:progress — phase marked complete

### Milestone Close
- [ ] /gsd:audit-milestone — all requirements verified complete
- [ ] /superpowers:requesting-code-review — milestone-level review
- [ ] /gsd:plan-milestone-gaps (if gaps found)
- [ ] /gsd:complete-milestone
- [ ] /gsd:cleanup
```
