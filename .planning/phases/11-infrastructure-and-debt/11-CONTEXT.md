# Phase 11: Infrastructure and Debt - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Three workstreams: (1) Cloudflare Tunnel — webhooks route through an external CF Tunnel instead of ngrok; (2) Prompt externalization — all LLM instruction text moves to `backend/prompts/*.md` files editable without code changes; (3) Dead code removal — `classify_intent()` plus a full codebase sweep. Creating new agents, replacing routing architecture, and adding new channels are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Cloudflare Tunnel (INFRA-01, INFRA-02)
- Cloudflare Tunnel is **already running on an external machine at 172.16.155.118** — no `cloudflared` service needed in docker-compose.yml
- INFRA-01 and INFRA-02 are satisfied externally; the only action is documenting the tunnel URL in `docs/dev-context.md`
- No docker-compose changes for the tunnel

### Prompt externalization (INFRA-03, INFRA-04)
- Scope: **all LLM instruction text** — not just system prompts, but every string currently inlined in Python that gets passed to an LLM (agent instructions, classification prompts, tool guidance, etc.)
- Goal: a developer can edit any prompt behavior by editing a `.md` file — no Python change required
- File organization: Claude decides (flat vs subfolders — choose what makes sense given the number of prompts found)
- Variable substitution syntax: Claude decides (Jinja2 or f-string style — choose the simplest approach that covers all use cases found)
- Caching / hot-reload: Claude decides (optimize for dev experience — consider no-cache in dev mode, cached in production)
- `PromptLoader` lives in `backend/core/prompts.py`, exposes `load_prompt(name, **vars)` as specified in INFRA-04

### Dead code removal (DEBT-01 + broader)
- Remove `classify_intent()` from `backend/agents/subagents/router.py` — confirmed dead (no production callers, only tested in isolation)
- Remove its test file `backend/tests/agents/test_router.py` along with it
- Sweep scope: **entire codebase** — backend Python, frontend TypeScript/TSX, and infra/config files
- Uncertain cases (no clear caller but dynamically possible): add `# TODO: verify dead` comment, do not remove — flagged for a follow-up decision
- `_route_after_master` keyword routing: **do not remove** — still active; flag as future tech debt with a comment pointing to the deferred routing overhaul

### Claude's Discretion
- `backend/prompts/` directory structure and file naming convention
- Variable substitution syntax for `PromptLoader`
- Dev vs production caching behavior for `PromptLoader`
- Which specific files are flagged vs removed during the dead code sweep

</decisions>

<specifics>
## Specific Ideas

- The tunnel IP `172.16.155.118` must be documented in `docs/dev-context.md` so future agents know where webhooks are routed
- The user's vision: AgentOS as an enterprise AI automation platform (comparable to OpenClaw for personal agents) — this context informs why `classify_intent()` (fixed 3-label classifier) is the wrong architecture, not just dead code
- When sweeping for dead code, `_route_after_master` keyword routing should be **flagged with a comment** noting it needs replacement with the Agent-as-Tool pattern before the platform can scale to 10+ agents

</specifics>

<deferred>
## Deferred Ideas

- **Agent-as-Tool routing overhaul** — Replace `_route_after_master` keyword map with a dynamic agent registry where each registered agent/skill is exposed as a callable tool to the master LLM. This allows unlimited agents to be added without touching routing code, and enables multi-agent queries (e.g. "summarize my emails AND create a Jira ticket"). This is a prerequisite for scaling AgentOS to a full enterprise platform. Belongs in its own phase after Phase 11.

</deferred>

---

*Phase: 11-infrastructure-and-debt*
*Context gathered: 2026-03-02*
