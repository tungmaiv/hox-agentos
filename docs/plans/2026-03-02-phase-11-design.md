# Phase 11 Design: Infrastructure and Debt

**Date:** 2026-03-02
**Phase:** 11 (v1.2 Developer Experience — first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, DEBT-01
**Depends on:** Phase 10 (v1.1 complete)

---

## Goal

Harden the platform's infrastructure and clean up the codebase before the v1.2 feature phases:
1. Replace ngrok with a stable Cloudflare Tunnel for webhook exposure (Telegram, WhatsApp, Teams)
2. Externalize all inline LLM system prompts to editable `.md` files with a `PromptLoader` utility
3. Delete `classify_intent()` — orphaned dead code never called from production

---

## Success Criteria

1. Telegram, WhatsApp, and MS Teams webhooks receive live traffic through the Cloudflare Tunnel on the remote LXC — verified by a test Telegram message end-to-end
2. Running `docker compose up` is the only local step needed; no manual ngrok command required
3. All 7 LLM system prompts can be found and edited in `backend/prompts/*.md` — no inline prompt strings remain in Python files
4. `PromptLoader.load_prompt("name", **vars)` returns the rendered string with variable substitution; repeated calls return the cached value without re-reading disk
5. `classify_intent()` no longer exists — grep returns no results in non-test code, and all 586+ tests still pass (test file deleted too)

---

## Architecture

### Work Stream 1: Cloudflare Tunnel

**Infrastructure topology:**

```
Telegram / WhatsApp / Teams platforms
          ↓ HTTPS
   Cloudflare (your domain)
          ↓
  cloudflared on remote LXC
       172.16.155.118
          ↓ Tailscale
  Local workstation tailscale0
       100.68.144.118
          ↓
  Docker channel gateways
    :9001  telegram-gateway
    :9002  whatsapp-gateway
    :9003  teams-gateway
```

The `cloudflared` daemon on the LXC is already installed and connected to Cloudflare. Phase 11 adds three ingress rules to the existing tunnel config, pointing each subdomain to the corresponding workstation port via Tailscale.

**LXC cloudflared config** (`/etc/cloudflared/config.yml` or equivalent):

```yaml
tunnel: <tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json

ingress:
  - hostname: telegram.yourdomain.com
    service: http://100.68.144.118:9001
  - hostname: whatsapp.yourdomain.com
    service: http://100.68.144.118:9002
  - hostname: teams.yourdomain.com
    service: http://100.68.144.118:9003
  - service: http_status:404
```

**DNS records** (Cloudflare dashboard — one-time): CNAME each subdomain to `<tunnel-id>.cfargotunnel.com`.

**Local changes (docker-compose.yml):** Add missing `WHATSAPP_WEBHOOK_URL` and `TEAMS_WEBHOOK_URL` env vars to their gateway services (currently only `telegram-gateway` has `TELEGRAM_WEBHOOK_URL`).

**Environment variables** (`.env.example` updated):
```
TELEGRAM_WEBHOOK_URL=https://telegram.yourdomain.com/webhook
WHATSAPP_WEBHOOK_URL=https://whatsapp.yourdomain.com/webhook
TEAMS_WEBHOOK_URL=https://teams.yourdomain.com/webhook
```

Note: WhatsApp and Teams webhook URLs are registered in their respective external dashboards (Meta Business, Azure Bot Service). The env vars document the stable Cloudflare URLs for that registration step.

**INFRA-02 satisfaction:** The LXC tunnel is always-on. Running `docker compose up` starts the channel gateways which are immediately reachable through the tunnel — no manual ngrok step needed.

---

### Work Stream 2: Prompt Externalization

**New directory:** `backend/prompts/`

**7 prompt files to create:**

| File | Source location | Notes |
|------|----------------|-------|
| `master-agent.md` | `agents/master_agent.py:188` `_DEFAULT_SYSTEM_PROMPT` | No variables |
| `artifact-gather-type.md` | `agents/artifact_builder_prompts.py:11` `_GATHER_TYPE_PROMPT` | No variables |
| `artifact-agent.md` | `agents/artifact_builder_prompts.py:25` `_AGENT_PROMPT` | No variables |
| `artifact-tool.md` | `agents/artifact_builder_prompts.py:46` `_TOOL_PROMPT` | No variables |
| `artifact-skill.md` | `agents/artifact_builder_prompts.py:75` `_SKILL_PROMPT` | No variables |
| `artifact-mcp-server.md` | `agents/artifact_builder_prompts.py:103` `_MCP_SERVER_PROMPT` | No variables |
| `memory-summarizer.md` | `scheduler/tasks/embedding.py:166` inline prompt | Uses `{transcript}` variable |

**`backend/core/prompts.py` — PromptLoader:**

```python
_cache: dict[str, str] = {}

def load_prompt(name: str, **vars: str) -> str:
    if name not in _cache:
        path = Path(__file__).parent.parent / "prompts" / f"{name}.md"
        _cache[name] = path.read_text(encoding="utf-8")
    template = _cache[name]
    return template.format_map(vars) if vars else template
```

- Module-level `_cache` dict — populated on first call, survives process lifetime
- `str.format_map(vars)` for `{variable}` substitution — zero new dependencies
- `path.read_text()` fails loudly on missing file — no silent fallback

**Files modified:**
- `agents/master_agent.py` — replace `_DEFAULT_SYSTEM_PROMPT` constant with `load_prompt("master-agent")`
- `agents/artifact_builder_prompts.py` — replace all 5 `_*_PROMPT` constants with `load_prompt(...)` calls; the module's public functions (`get_gather_type_prompt`, `get_system_prompt`) remain as the stable API
- `scheduler/tasks/embedding.py` — replace inline `prompt = (...)` with `load_prompt("memory-summarizer", transcript=transcript)`

**Not touched:**
- `alembic/versions/015_seed_builtin_skills.py` — "You are" strings are skill *content* seeded into the DB, not module-level LLM prompts
- `agents/node_handlers.py:98` — `"Please provide a summary."` is a one-line fallback message
- `skills/validator.py` — `_MAX_PROMPT_SIZE` is a byte-size constant

**Tests:** Unit tests for `PromptLoader` covering: cache hit (file read once on two calls), variable substitution, missing file raises `FileNotFoundError`.

---

### Work Stream 3: Dead Code Removal

**Files to delete:**

| File | Reason |
|------|--------|
| `backend/agents/subagents/router.py` | Contains only `classify_intent()` — never imported by production code |
| `backend/tests/agents/test_router.py` | Tests only `classify_intent()` — becomes unreachable after deletion |

**Verification:** `grep -rn "classify_intent\|from agents.subagents.router"` in `backend/` (excluding `.venv`) returns zero results. Full test suite runs with 580+ passing (net: −6 test count from deleted test file, no regressions).

---

## Plan Breakdown

Three plans, all independent — 11-02 and 11-03 can execute in parallel:

### Plan 11-01: Cloudflare Tunnel wiring
- Document LXC ingress config in `docs/dev-context.md` (config snippet + DNS setup steps)
- Add `WHATSAPP_WEBHOOK_URL` and `TEAMS_WEBHOOK_URL` to `docker-compose.yml` gateway services
- Update `.env.example` with CF domain placeholders for all three webhook URLs
- Remove all ngrok references from `docs/`, `.planning/`, and code comments
- Update `docs/dev-context.md` tunnel architecture section

### Plan 11-02: PromptLoader + prompt file extraction
- Create `backend/prompts/` directory with 7 `.md` files (content copied verbatim from source)
- Create `backend/core/prompts.py` with `load_prompt()` and module-level cache
- Refactor `master_agent.py`, `artifact_builder_prompts.py`, `embedding.py` to use `load_prompt()`
- Add unit tests for `PromptLoader` in `tests/core/test_prompts.py`
- Verify full test suite still passes

### Plan 11-03: Dead code removal
- Delete `backend/agents/subagents/router.py`
- Delete `backend/tests/agents/test_router.py`
- Verify grep returns no `classify_intent` references in production code
- Verify full test suite passes (count drops by ~6, no regressions)

---

## Key Decisions

- **No `cloudflared` Docker service locally** — LXC tunnel is always-on; docker compose up alone is sufficient
- **Tailscale as the transport** — LXC reaches workstation at `100.68.144.118` (stable Tailscale IP)
- **`str.format_map()` not Jinja2** — current prompts only need simple `{variable}` substitution; zero new dependencies
- **Module-level dict cache** — simpler than `functools.lru_cache` for this use case; prompt files are small and immutable at runtime
- **Delete entire router.py + test file** — the module has no other purpose; partial deletion leaves confusing empty shells
- **`artifact_builder_prompts.py` public API preserved** — `get_gather_type_prompt()` and `get_system_prompt()` remain as the stable interface; only the internals change to use `load_prompt()`

---

*Design approved: 2026-03-02*
