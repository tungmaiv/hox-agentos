# Phase 24: Unified Registry, MCP Platform Enhancement & Skill Import Adapters - Research

**Researched:** 2026-03-12
**Domain:** Registry consolidation, MCP stdio transport, skill import adapters, security scanning service, admin UI restructure, LLM hot-reload
**Confidence:** HIGH (all major findings verified against codebase + official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Registry migration strategy (24-02):**
- Drop old tables: After migrating all data to `registry_entries`, the old tables (`agent_definitions`, `skill_definitions`, `tool_definitions`, `mcp_servers`) are dropped in the same Alembic migration. Clean break — no views, no aliases, no dual sources.
- Data migration in Alembic: A single migration file (028) does the full cycle atomically: CREATE `registry_entries` → INSERT from each old table with type mapping → DROP old tables. No separate data scripts.
- Single skill type, no versioning: Merge instructional + procedural skill types into one. Latest version is the only version — editing overwrites in place. No activate/deactivate workflow. Status is simply: `active` / `draft` / `archived`.
- Replace all API routes: Old scattered routes (`/api/admin/skills/*`, `/api/admin/tools/*`, `/api/gateway/registry/*`, `/api/mcp/*`) are removed entirely. New unified routes at `/api/registry/*` become the only API surface. Frontend updated to use new routes.

**Admin UI tab structure (24-06):**
- 4-tab layout:
  - **Registry** — nav hub; each entity type (Agents / Skills / Tools / MCP Servers) has its own dedicated page, accessible from the Registry tab as a nav menu or dashboard with counts.
  - **Access** — Users, Permissions, Credentials.
  - **System** — Config, Identity (SSO), LLM model/provider settings, Memory management.
  - **Build** — Artifact Builder, Skill Store.
- Registry tab is a nav hub (not a unified list): clicking a type navigates to its dedicated page. Keeps each type's specific CRUD UI intact without cramming into one grid.
- Memory page moves to System tab (infrastructure concern, not user management).
- Identity/Credentials stay in Access tab.

**Security scan service availability (24-05):**
- Fallback to in-process scanner: When the Docker security scan service is unavailable (down, timeout, crash), the backend falls back to the existing `SecurityScanner` in `backend/skills/security_scanner.py`. Skill save proceeds with lightweight scan. Log a warning with `scan_engine='fallback'`.
- Admin-triggered retroactive scan: No automatic re-scanning of existing active skills. Add an admin action (button in System tab or skill list) that triggers a batch re-scan on demand.
- ScanResults tab in admin skill detail: Full pip-audit and bandit output surfaces as a new "Scan Results" tab. `SecurityReportCard` stays in the builder panel for quick-save feedback.
- Scan runs on every write: New saves, imports, forks — all trigger a scan. Docker service first, fallback to in-process if unavailable.

**Tech debt scope and priority (24-01):**
- CREDENTIAL_ENCRYPTION_KEY is back in scope: Add `CREDENTIAL_ENCRYPTION_KEY` to `backend/.env` and `core/config.py` validation. Required before any OAuth flows go live. No retroactive migration of existing credential rows — encryption applies to new writes only.
- Priority order (if capacity is limited):
  1. SWR/Server Component build fix — unblocks `pnpm build` and CI
  2. CREDENTIAL_ENCRYPTION_KEY — needed before OAuth
  3. Keycloak SSO "Server error — Configuration" — affects SSO login reliability
  4. Page load performance — 5-minute sign-in issue after Phase 18 changes
- Page load fix depth: Fix ALL 5 hypotheses:
  1. Aggressive caching for `get_keycloak_config()` DB reads (pre-warm on startup)
  2. `auth.ts` startup fetch — add readiness probe before fetching `/api/internal/keycloak/provider-config`
  3. NextAuth SSR waterfall — reduce per-page session resolution round-trips
  4. Cold-start retries — add backoff/timeout so LiteLLM/Keycloak not-ready doesn't cascade
  5. JWKS pre-warm — fetch JWKS at app startup, not on first auth request

### Claude's Discretion

- Exact column mapping from old tables to `registry_entries` (field naming, JSONB structure for type-specific config)
- Migration 028 numbering — confirm no conflicts with any migrations added since Phase 23
- Which of the 4 Registry tab entity pages reuses existing admin page components vs needs new ones
- `scan_engine` field name in scan result storage (`'full'` vs `'docker'` vs `'fallback'`)
- Retry/timeout policy for Docker scan service HTTP client (suggested: 10s timeout, 1 retry)

### Deferred Ideas (OUT OF SCOPE)

- HashiCorp Vault for secret management — explicitly post-MVP per CLAUDE.md; confirmed deferred.
- Stack initialization wizard — pending todo from 2026-03-05; separate phase.
- Ngrok → Cloudflare Tunnel — pending todo from 2026-03-02; separate phase.
- Proactive similar skills auto-surface — was deferred from Phase 23; still deferred.
- Skill composition — explicitly deferred to v1.4+.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| 24-01-DEBT | Fix SWR/Server Component build failure, CREDENTIAL_ENCRYPTION_KEY validation, Keycloak SSO error, page load performance (5 hypotheses) | Auth.ts startup fetch pattern confirmed; `credential_encryption_key` field exists in config.py (line 45) but not validated; settings/integrations page is already a redirect (not SWR issue); SWR not installed in package.json |
| 24-02-REG | Create `registry_entries` table, migrate agents/skills/tools/mcp_servers atomically in migration 028, implement strategy-pattern handlers, expose `/api/registry/*` routes | Two Alembic heads exist (027 and 83f730920f5a from 020) — 028 must first merge both heads, then create registry_entries. Existing ORM models and route patterns documented. |
| 24-03-MCP | StdioMCPClient using `mcp` SDK `stdio_client` + `StdioServerParameters`, MCPInstaller (npm/pip subprocess), MCP catalog (Context7, Fetch, Filesystem pre-seeded), OpenAPI-to-MCP bridge | MCP SDK API confirmed from official docs: `from mcp import ClientSession, StdioServerParameters; from mcp.client.stdio import stdio_client`. AsyncExitStack pattern required for lifecycle management. |
| 24-04-SKL | Base adapter interface, SkillRepoAdapter refactor, ClaudeMarketAdapter, GitHubAdapter, UnifiedImportService with security gate | Existing `SkillImporter` in `backend/skills/importer.py` handles AgentSkills format. Adapter refactor wraps this. `NormalizedSkill` dataclass design from proposal is the canonical format. |
| 24-05-SEC | `infra/security-scanner/` Docker service (pip-audit, bandit, detect-secrets), `SecurityScanClient` in backend, replace WeightedSecurityScanner on writes, RBAC permissions | Specification confirmed from 00-specification.md. Service on port 8003. Existing `SecurityScanner` in `backend/skills/security_scanner.py` stays as fallback only. |
| 24-06-UI | 4-tab admin layout, registry CRUD UI, LLM model/provider configurable in admin console via LiteLLM `/model/new` + `/model/update` + `/model/delete` API | LiteLLM model management API confirmed: `/model/new`, `/model/update`, `/model/delete` endpoints exist. No container restart needed. Existing admin layout has 13 tabs (needs restructure to 4). |
</phase_requirements>

---

## Summary

Phase 24 is a large structural refactoring across 6 plans. The core theme is consolidation: one registry table, one import interface, one security scanner service, four admin tabs, and one way to configure LLMs. All 6 plans have detailed design documents in `docs/enhancements/` that are authoritative for implementation details.

The most critical discovery for planning is the **Alembic migration head split**: migration 027 (`skill_repo_index`) branches from 026, while migration `83f730920f5a` (`platform_config`) branches from 020. These are currently two separate heads. Migration 028 for `registry_entries` must first generate a merge migration to resolve the two heads, then proceed with the registry table creation and data migration. This is a mandatory Wave 0 task.

The **LiteLLM admin API** (`/model/new`, `/model/update`, `/model/delete`) supports hot-reload model configuration without container restart — this is the correct approach for 24-06 LLM config UI. The existing `infra/litellm/config.yaml` is the source of truth for initial config; admin console changes go to LiteLLM's DB storage via API.

**Primary recommendation:** Implement in strict wave order within each plan. 24-02 (registry) is the dependency for 24-03, 24-04, and 24-06. 24-01 (tech debt) can run in parallel with 24-02 as it is independent. 24-05 (security scanner) can start building the Docker service in parallel with 24-04.

---

## Standard Stack

### Core (All Existing in Project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | Backend API framework | Project standard (CLAUDE.md) |
| SQLAlchemy | 2.0+ async | ORM for registry_entries | Existing pattern throughout codebase |
| Alembic | Latest | Schema migrations | Existing migration chain 001-027+83f730 |
| Pydantic v2 | 2.12.5 | Schema validation for registry types | Project standard |
| structlog | Latest | Audit logging for scanner decisions | Project standard — get_audit_logger() |
| httpx | Latest | SecurityScanClient HTTP calls to Docker service | Existing MCPClient pattern |
| Next.js | 15+ | Frontend admin UI | Project standard |

### New Dependencies for Phase 24

| Library | Where | Purpose | When to Use |
|---------|-------|---------|-------------|
| `mcp` (Python SDK) | `backend/` | `StdioServerParameters`, `stdio_client`, `ClientSession` | 24-03 StdioMCPClient only |
| `pip-audit` | `infra/security-scanner/` | Dependency vulnerability scanning | Security scanner Docker service |
| `bandit` | `infra/security-scanner/` | Python SAST | Security scanner Docker service |
| `detect-secrets` | `infra/security-scanner/` | Secret/credential detection | Security scanner Docker service |
| `tenacity` | `backend/` | Retry logic for SecurityScanClient | 24-05 HTTP client retry |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp` Python SDK for stdio | Custom subprocess + JSON-RPC | SDK handles asyncio lifecycle, error handling; never hand-roll |
| LiteLLM `/model/new` API | Editing config.yaml + container restart | API requires no restart; config.yaml only applies on boot |
| Standalone Docker scanner service | In-process pip-audit via subprocess | Isolation prevents scanner crash from killing backend; independent scaling |

**Backend installation (security-scanner service):**
```bash
# infra/security-scanner/pyproject.toml
pip-audit bandit detect-secrets fastapi uvicorn sqlalchemy asyncpg structlog pydantic-settings
```

**Backend (mcp SDK for stdio):**
```bash
cd backend && uv add mcp
```

**Backend (retry for SecurityScanClient):**
```bash
cd backend && uv add tenacity
```

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
backend/
├── api/routes/
│   └── registry.py            # Replaces admin_skills/admin_tools/admin_agents/mcp_servers.py
├── registry/
│   ├── __init__.py
│   ├── models.py              # RegistryEntry ORM model
│   ├── handlers/
│   │   ├── base.py            # RegistryHandler ABC
│   │   ├── agent_handler.py
│   │   ├── skill_handler.py
│   │   ├── tool_handler.py
│   │   └── mcp_handler.py
│   └── service.py             # UnifiedRegistryService
├── mcp/
│   ├── client.py              # Existing HTTP+SSE MCPClient (unchanged)
│   ├── stdio_client.py        # New StdioMCPClient (wraps mcp SDK)
│   ├── installer.py           # MCPInstaller (npm/pip subprocess)
│   └── registry.py            # Existing MCPRegistry (removed after 24-02)
├── skills/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            # SkillAdapter ABC + NormalizedSkill
│   │   ├── registry.py        # AdapterRegistry
│   │   ├── skill_repo.py      # Refactored from SkillImporter
│   │   ├── claude_market.py   # ClaudeMarketAdapter
│   │   └── github.py          # GitHubAdapter
│   └── import_service.py      # UnifiedImportService
├── security/
│   └── scan_client.py         # SecurityScanClient (HTTP to Docker service)

infra/
└── security-scanner/          # New Docker service
    ├── Dockerfile
    ├── pyproject.toml
    ├── main.py
    ├── scanners/
    │   ├── dependency_scanner.py
    │   ├── secret_scanner.py
    │   └── code_scanner.py
    └── policies/
        └── default-policies.yaml

frontend/src/app/(authenticated)/admin/
├── layout.tsx                 # Restructured: 4 top-level tabs
├── page.tsx                   # Registry hub with entity counts
├── agents/                    # Existing pages, minimal changes
├── skills/
│   └── [id]/                  # Add "Scan Results" tab to detail view
├── tools/
├── mcp-servers/
│   ├── page.tsx               # Enhanced with install button + catalog
│   └── catalog/page.tsx       # MCP server catalog browse
├── system/
│   ├── config/page.tsx        # Moved from /admin/config
│   ├── identity/page.tsx      # Moved from /admin/identity
│   ├── llm/page.tsx           # NEW: LLM model/provider config
│   └── memory/page.tsx        # Moved from /admin/memory
├── access/
│   ├── users/page.tsx         # Moved from /admin/users
│   ├── permissions/page.tsx   # Moved from /admin/permissions
│   └── credentials/page.tsx   # Moved from /admin/credentials
└── build/
    ├── create/page.tsx        # Moved from /admin/create
    ├── builder/page.tsx       # Moved from /admin/builder
    └── skill-store/page.tsx   # Moved from /admin/skill-store
```

### Pattern 1: Strategy Pattern for Registry Handlers

**What:** Type-specific handler classes share common interface; `UnifiedRegistryService` dispatches to the right handler based on `entry.type`.
**When to use:** Whenever code must branch on entity type.

```python
# Source: docs/enhancements/unified-registry-proposal.md
from abc import ABC, abstractmethod
from uuid import UUID
from core.models.registry import RegistryEntry

class RegistryHandler(ABC):
    """Base handler for type-specific registry logic."""

    @abstractmethod
    async def on_create(self, entry: RegistryEntry, session: AsyncSession) -> None:
        """Called after registry_entries INSERT."""
        pass

    @abstractmethod
    async def on_delete(self, entry: RegistryEntry, session: AsyncSession) -> None:
        """Called before registry_entries DELETE."""
        pass

    @abstractmethod
    async def validate_config(self, config: dict) -> None:
        """Validate type-specific config JSONB before write."""
        pass

class UnifiedRegistryService:
    _handlers: dict[str, RegistryHandler] = {
        "agent": AgentHandler(),
        "skill": SkillHandler(),
        "tool": ToolHandler(),
        "mcp_server": McpHandler(),
    }

    def _get_handler(self, entry_type: str) -> RegistryHandler:
        if entry_type not in self._handlers:
            raise ValueError(f"Unknown registry type: {entry_type}")
        return self._handlers[entry_type]
```

### Pattern 2: StdioMCPClient (wraps mcp Python SDK)

**What:** Spawns CLI-installed MCP servers as subprocesses using asyncio; communicates via stdin/stdout.
**When to use:** For `server_type='public'` entries in the registry with `transport='stdio'`.

```python
# Source: Official MCP docs https://modelcontextprotocol.io/docs/develop/build-client
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class StdioMCPClient:
    """Subprocess-based MCP client for stdio transport servers."""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        self._params = StdioServerParameters(command=command, args=args, env=env)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession, None]:
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[dict]:
        async with self.session() as s:
            response = await s.list_tools()
            return [t.model_dump() for t in response.tools]

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        async with self.session() as s:
            result = await s.call_tool(tool_name, arguments)
            return result.model_dump()
```

**Critical:** Each `session()` spawns a new subprocess. For high-frequency calls, consider a persistent subprocess pool. For ~100 users, on-demand spawning is acceptable.

### Pattern 3: Adapter Pattern for Skill Import

**What:** All import sources implement `SkillAdapter` ABC; `UnifiedImportService` detects source type and delegates.
**When to use:** Any skill import path — direct URL, GitHub, ZIP, Claude Market.

```python
# Source: docs/enhancements/skill-import-adapter-framework.md
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class NormalizedSkill:
    name: str
    description: str
    version: str
    instruction_markdown: Optional[str] = None
    procedure_json: Optional[List[dict]] = None
    allowed_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str = "direct_url"

class SkillAdapter(ABC):
    @abstractmethod
    async def can_handle(self, source: str, **kwargs) -> bool: ...

    @abstractmethod
    async def validate_source(self, source: str, **kwargs) -> dict: ...

    @abstractmethod
    async def fetch_and_normalize(self, source: str, **kwargs) -> NormalizedSkill: ...

    @abstractmethod
    async def get_skill_list(self, source: str, **kwargs) -> List[dict]: ...
```

### Pattern 4: SecurityScanClient with Fallback

**What:** HTTP client calling Docker security scanner service; falls back to in-process `SecurityScanner` on unavailability.
**When to use:** Every skill write (save, import, fork).

```python
# Source: docs/enhancements/security-scan-module/00-specification.md
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger(__name__)

class SecurityScanClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base_url = base_url  # e.g. http://security-scanner:8003

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=5))
    async def scan_skill(self, skill_data: dict) -> dict:
        """Returns scan result dict with status, findings, scan_engine='docker'."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/sse",
                json={"jsonrpc": "2.0", "method": "tools/call",
                      "params": {"name": "scan_code",
                                 "arguments": {"source_code": skill_data.get("scripts", "")}},
                      "id": 1}
            )
            response.raise_for_status()
            return {**response.json().get("result", {}), "scan_engine": "docker"}

async def scan_skill_with_fallback(
    skill_data: dict,
    client: SecurityScanClient,
) -> dict:
    """Try Docker scanner, fall back to in-process SecurityScanner."""
    try:
        return await client.scan_skill(skill_data)
    except (httpx.TimeoutException, httpx.ConnectError, Exception) as e:
        logger.warning("security_scan_fallback", reason=str(e), scan_engine="fallback")
        from skills.security_scanner import SecurityScanner
        report = await SecurityScanner().scan(skill_data)
        return {"scan_engine": "fallback", "score": report.score,
                "recommendation": report.recommendation, "findings": []}
```

### Pattern 5: LiteLLM Model Config via API

**What:** Admin saves LLM config → backend calls LiteLLM `/model/new` (add), `/model/update` (change), `/model/delete` (remove) via HTTP.
**When to use:** Admin console LLM model/provider config changes in 24-06.

```python
# Source: LiteLLM docs https://docs.litellm.ai/docs/proxy/model_management
# Confirmed: /model/new, /model/update, /model/delete endpoints exist (as of 2025-03)
import httpx
from core.config import settings

async def add_llm_model(model_name: str, provider_model: str, api_base: str | None) -> None:
    """Add or update model in LiteLLM proxy without restart."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"{settings.litellm_url}/model/new",
            json={
                "model_name": model_name,
                "litellm_params": {
                    "model": provider_model,
                    "api_base": api_base,
                }
            },
            headers={"Authorization": f"Bearer {settings.litellm_master_key}"}
        )
```

**Important limitation:** LiteLLM `/model/new` stores models in DB (if configured), not in `config.yaml`. On restart, it loads from `config.yaml` first, then DB models. The admin console changes persist in LiteLLM's DB, not in the file. This is acceptable for MVP — document it in admin UI.

### Pattern 6: Migration Merge + Registry (Migration 028)

**What:** Two independent Alembic heads (027 and 83f730920f5a) must be merged before 028 can create the registry table.
**Critical discovery:** `027_skill_repo_index.py` branches from `026`. `83f730920f5a_add_platform_config.py` branches from `020`. These are currently TWO separate heads. Migration 028 for `registry_entries` requires a merge migration first.

```bash
# Step 1: Create merge migration (Wave 0 of 24-02)
cd backend
.venv/bin/alembic merge 027 83f730920f5a -m "028_merge_027_and_platform_config"

# Step 2: Create registry_entries migration
.venv/bin/alembic revision -m "029_registry_entries_unified"
# (or number it 028 if merge is numbered differently — check heads after step 1)
```

**Actual migration numbering:** The merge migration will get an auto-generated hex ID (like `83f730920f5a`). Wave 0 must verify the correct head ID after merge before writing the data migration.

### Anti-Patterns to Avoid

- **Updating config.yaml for LLM changes:** Use LiteLLM API endpoints — config.yaml changes require container restart.
- **Spawning a new stdio subprocess per tool call in hot path:** Acceptable for 100 users; keep a note to add pooling if call frequency increases.
- **Running pip-audit/bandit in-process inside FastAPI:** Always run in the security-scanner Docker service subprocess. Never execute pip-audit inside the backend process.
- **Registering new registry routes in both old and new routers:** Remove old routes entirely; dual-registration causes 500s from conflicting schema types.
- **Creating migration 028 before merging two heads:** Will fail with "Target database is not up to date" unless both heads are merged first.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| stdio subprocess MCP client | Custom asyncio subprocess + JSON-RPC parser | `mcp` Python SDK `stdio_client` + `StdioServerParameters` | MCP SDK handles process lifecycle, stream multiplexing, error recovery |
| Python dependency vulnerability scanning | Custom PyPI advisory DB checker | `pip-audit` subprocess call | pip-audit uses OSV + PyPI advisory DB, handles edge cases, maintained by PyPA |
| Python SAST | Custom AST walker | `bandit` subprocess call | 47 built-in checks, CWE mapping, maintained by PyCQA |
| Secret detection in code | Regex patterns | `detect-secrets` subprocess call | Covers 30+ secret types, handles entropy analysis, maintained by Yelp |
| LiteLLM config management | File editing + container restart | LiteLLM `/model/new` API | No restart needed, API documented and maintained |
| Retry logic for HTTP clients | Custom sleep loops | `tenacity` | Exponential backoff, retry predicates, jitter — prevents thundering herd |

**Key insight:** All security scanning tools (`pip-audit`, `bandit`, `detect-secrets`) are Python command-line tools designed to be called via subprocess. They do not have stable Python import APIs — always invoke them as subprocesses in the security-scanner service.

---

## Common Pitfalls

### Pitfall 1: Alembic Two-Head Problem
**What goes wrong:** Running `alembic upgrade head` when two heads exist will refuse to upgrade (ambiguous target).
**Why it happens:** Migration `83f730920f5a` (`platform_config`, added in Phase 18) branches from `020`, while migrations 021-027 form a separate chain. They were never merged.
**How to avoid:** Wave 0 of 24-02 must create a merge migration (`alembic merge 027 83f730920f5a`) before any registry table migration. Verify with `alembic heads` after merge shows exactly one head.
**Warning signs:** `alembic heads` shows two lines instead of one.

### Pitfall 2: Gateway Runtime Not Updated After Registry Migration
**What goes wrong:** `backend/gateway/runtime.py` calls `tool_registry.get_tools_for_user()` which reads from the now-dropped `tool_definitions` table → 500 on every agent call.
**Why it happens:** `tool_registry.py` is independent of the new registry and won't auto-migrate.
**How to avoid:** 24-02 must update `gateway/runtime.py` to call `UnifiedRegistryService.get_tools_for_user()` instead. This is a mandatory task in 24-02.
**Warning signs:** `GET /api/agents/chat` returns 500 after registry migration runs.

### Pitfall 3: StdioMCPClient Subprocess Hanging
**What goes wrong:** `stdio_client()` hangs if the spawned subprocess exits prematurely or blocks on stdin.
**Why it happens:** asyncio event loop blocks waiting for subprocess to respond; MCP SDK issue #671.
**How to avoid:** Always set a timeout on `call_tool` calls. Wrap `StdioMCPClient.session()` in `asyncio.wait_for()`. Log process exit codes.
**Warning signs:** Agent calls to public MCP tools never return; Celery worker heartbeat times out.

### Pitfall 4: Old Admin Routes Returning 404 After Removal
**What goes wrong:** Frontend pages still calling `/api/admin/skills/*`, `/api/admin/tools/*`, `/api/mcp/*` get 404 after routes are removed.
**Why it happens:** Frontend and backend updated in separate deployments.
**How to avoid:** In 24-02, update all frontend fetch calls to `/api/registry/*` in the same plan. Do not remove backend routes until frontend is updated.
**Warning signs:** Admin pages show "Failed to load" after backend deploy.

### Pitfall 5: LiteLLM Model Persistence After Restart
**What goes wrong:** Admin adds model via console → works → container restart → model gone.
**Why it happens:** `/model/new` stores in LiteLLM's in-memory state; only persistent if LiteLLM's own DB is configured.
**How to avoid:** In 24-06 admin UI, add a visible note: "Model changes apply immediately but require manual config.yaml update for persistence across restarts." Document this in the LLM config page UI.
**Warning signs:** Admin complains models disappeared after `just rebuild litellm`.

### Pitfall 6: Security Scanner Blocking Skill Save
**What goes wrong:** Security scanner Docker service is slow (>10s) → user clicks Save in builder → request times out → skill not saved.
**Why it happens:** Scan is synchronous in the skill save endpoint.
**How to avoid:** Set `SecurityScanClient` timeout to 10s with 1 retry (max 20s total). Fallback to in-process scanner immediately on timeout. The skill is always saved; scan result is advisory, not blocking (except for hard veto from in-process scanner).
**Warning signs:** Builder save button spins indefinitely.

### Pitfall 7: JSONB Column Variant Missing in Tests
**What goes wrong:** `registry_entries.config` using `JSONB()` directly fails in SQLite-based tests.
**Why it happens:** SQLite doesn't support JSONB type natively.
**How to avoid:** Use established pattern: `JSON().with_variant(JSONB(), 'postgresql')` on all JSONB columns in the `RegistryEntry` ORM model (consistent with Phase 16 decision).
**Warning signs:** `test_registry_models.py` fails with `CompileError: Unknown type 'JSONB'`.

---

## Code Examples

Verified patterns from official sources and codebase:

### MCP SDK: stdio_client lifecycle (official docs)

```python
# Source: https://modelcontextprotocol.io/docs/develop/build-client
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# For npx-installed servers (e.g. Context7):
server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@upstash/context7-mcp@latest"],
    env={"UPSTASH_REDIS_REST_URL": "...", "UPSTASH_REDIS_REST_TOKEN": "..."}
)

# For pip-installed servers (e.g. mcp-server-fetch):
server_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_server_fetch"],
    env=None
)

async with AsyncExitStack() as stack:
    transport = await stack.enter_async_context(stdio_client(server_params))
    read, write = transport
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    tools = await session.list_tools()
```

### Registry Entry ORM Model

```python
# Source: docs/enhancements/unified-registry-proposal.md + existing ORM patterns
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from core.db import Base

class RegistryEntry(Base):
    __tablename__ = "registry_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(20), nullable=False)  # agent|skill|tool|mcp_server
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    config = Column(
        JSON().with_variant(JSONB(), "postgresql"),  # SQLite compat for tests
        nullable=False, default=dict
    )
    status = Column(String(20), nullable=False, default="draft")  # draft|active|archived
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("type", "name", name="uq_registry_type_name"),
    )
```

### Migration 028: Merge + Create registry_entries

```python
# Wave 0: run this first
# cd backend && .venv/bin/alembic merge 027 83f730920f5a -m "028_merge_heads"
# Then create the registry migration:
# .venv/bin/alembic revision -m "029_registry_entries"  (or check head name after merge)

# In the registry migration's upgrade():
def upgrade() -> None:
    op.create_table(
        "registry_entries",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("description", sa.Text()),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("owner_id", UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("type", "name", name="uq_registry_type_name"),
    )
    # Data migration INSERTs from agent_definitions, skill_definitions, etc.
    # ... (see unified-registry-proposal.md for full SQL)
    # DROP old tables at end:
    op.drop_table("agent_definitions")
    op.drop_table("skill_definitions")
    op.drop_table("tool_definitions")
    op.drop_table("mcp_servers")
```

### Admin UI 4-Tab Layout (Next.js)

```typescript
// frontend/src/app/(authenticated)/admin/layout.tsx
// Source: existing layout.tsx pattern + CONTEXT.md decision
const ADMIN_TABS = [
  { label: "Registry",  href: "/admin" },         // Hub page with entity counts
  { label: "Access",    href: "/admin/access" },  // Users, Permissions, Credentials
  { label: "System",    href: "/admin/system" },  // Config, Identity, LLM, Memory
  { label: "Build",     href: "/admin/build" },   // AI Builder, Skill Store
] as const;
// Each tab page renders sub-navigation for its child pages.
// The Registry tab links to /admin/agents, /admin/skills, /admin/tools, /admin/mcp-servers
```

### CREDENTIAL_ENCRYPTION_KEY Validation Fix

```python
# Source: backend/core/config.py (existing field at line 45)
# Current: credential_encryption_key: str = ""  — no validation
# Fix: add validator
from pydantic import model_validator

@model_validator(mode="after")
def validate_encryption_key(self) -> "Settings":
    key = self.credential_encryption_key
    if key and len(bytes.fromhex(key)) != 32:
        raise ValueError("CREDENTIAL_ENCRYPTION_KEY must be a 64-char hex string (32 bytes AES-256)")
    return self
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Multiple entity tables (agent_definitions, skill_definitions, etc.) | Single `registry_entries` table with type + config JSONB | Phase 24 | Unified CRUD; type-specific behavior in handlers |
| HTTP+SSE only for MCP | HTTP+SSE (Tier 1) + stdio (Tier 2) + OpenAPI bridge (Tier 3) | Phase 24 | Enables Context7, Fetch, Filesystem public servers |
| Single SkillImporter (AgentSkills format only) | Adapter pattern with 4 adapters (SkillRepo, Claude Market, GitHub, ZIP) | Phase 24 | New skill sources without core code changes |
| In-process WeightedSecurityScanner | Standalone Docker service + SecurityScanClient with fallback | Phase 24 | Isolation, independent scaling, pip-audit/bandit/detect-secrets |
| 13-tab flat admin layout | 4-tab grouped layout (Registry/Access/System/Build) | Phase 24 | Cleaner navigation; entity pages remain dedicated |
| LLM config via config.yaml only | LLM config via admin console → LiteLLM API | Phase 24 | No container restart needed for model changes |

**Deprecated/outdated after Phase 24:**
- `backend/gateway/tool_registry.py`: Superseded by UnifiedRegistryService strategy handlers. Remove after 24-02.
- `backend/mcp/registry.py`: MCPRegistry superseded. Merge into mcp_handler.py strategy handler.
- `backend/api/routes/admin_skills.py`, `admin_tools.py`, `admin_agents.py`, `mcp_servers.py`: All replaced by `registry.py`.
- `backend/core/models/agent_definition.py`, `skill_definition.py`, `tool_definition.py`, `mcp_server.py`: All dropped after migration.

---

## Open Questions

1. **Migration numbering after merge**
   - What we know: Two heads exist (027 and 83f730920f5a). Merge creates a new hex ID migration.
   - What's unclear: The exact revision ID of the merge migration (determined at runtime by Alembic).
   - Recommendation: 24-02 Wave 0 task runs `alembic merge`, captures the resulting revision ID, then writes the registry_entries migration referencing that ID as `down_revision`.

2. **MCP catalog pre-seed timing**
   - What we know: 3 servers (Context7, Fetch, Filesystem) should be pre-seeded in `mcp_server_catalog` table.
   - What's unclear: Whether the catalog table is in the main `registry_entries` (as `type='mcp_server'` with `status='catalog'`) or a separate `mcp_server_catalog` table.
   - Recommendation: Use a separate `mcp_server_catalog` table as the proposal describes. Pre-seed via data migration or fixture in 24-03.

3. **LiteLLM model persistence**
   - What we know: `/model/new` stores in LiteLLM's state; may not persist across restarts without LiteLLM DB configured.
   - What's unclear: Whether Blitz's LiteLLM instance has DB configured (the config.yaml uses file-only config).
   - Recommendation: In 24-06, implement admin LLM config by (a) calling LiteLLM API for immediate effect AND (b) updating `platform_config` table with the model list so backend can reconstruct config on LiteLLM restart. Add a "sync to LiteLLM" action.

4. **Security scanner secscan_results table ownership**
   - What we know: The scanner service has its own `alembic/` directory per the spec.
   - What's unclear: Whether `secscan_results` lives in the same PostgreSQL DB as the main app or a separate schema.
   - Recommendation: Use the shared PostgreSQL DB (same `DATABASE_URL`) but prefix tables with `secscan_` for isolation. Keep the scanner's alembic separate but pointing to the same DB. This is consistent with the spec (port 5432 shared).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend), tsc --noEmit (frontend) |
| Config file | `backend/` — no pytest.ini; conftest.py at root |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q -x --ignore=tests/mcp` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Current baseline | 879 tests collected |
| Frontend check | `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| 24-01-BUILD | `pnpm build` succeeds with no prerender errors | build | `cd frontend && pnpm exec tsc --noEmit` | ✅ (tsc) |
| 24-01-CRED | `CREDENTIAL_ENCRYPTION_KEY` validation rejects invalid keys | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_config.py -x` | ✅ exists |
| 24-01-PERF | auth.ts startup fetch has retry/backoff | integration (manual) | Manual: check Keycloak not started → backend boots gracefully | manual-only |
| 24-02-SCHEMA | `registry_entries` table created, old tables dropped | integration | `PYTHONPATH=. .venv/bin/pytest tests/test_registry_models.py -x` | ❌ Wave 0 |
| 24-02-CRUD | `/api/registry/` CRUD endpoints return correct status codes | integration | `PYTHONPATH=. .venv/bin/pytest tests/api/test_registry_routes.py -x` | ❌ Wave 0 |
| 24-02-GATEWAY | Agent tool calls work via unified registry after migration | integration | `PYTHONPATH=. .venv/bin/pytest tests/test_runtime.py -x` | ✅ exists |
| 24-03-STDIO | `StdioMCPClient.list_tools()` connects to a stdio server | unit (mock) | `PYTHONPATH=. .venv/bin/pytest tests/mcp/test_stdio_client.py -x` | ❌ Wave 0 |
| 24-03-INSTALL | `MCPInstaller.install()` invokes correct npm/pip command | unit (mock subprocess) | `PYTHONPATH=. .venv/bin/pytest tests/mcp/test_installer.py -x` | ❌ Wave 0 |
| 24-04-ADAPTER | `SkillRepoAdapter.fetch_and_normalize()` returns NormalizedSkill | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py -x` | ✅ exists (needs update) |
| 24-04-GITHUB | `GitHubAdapter.get_skill_list()` fetches repo file tree | unit (mock httpx) | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_github_adapter.py -x` | ❌ Wave 0 |
| 24-05-SCAN | `SecurityScanClient.scan_skill()` calls scanner service | unit (mock httpx) | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scan_client.py -x` | ❌ Wave 0 |
| 24-05-FALLBACK | Fallback to in-process scanner when Docker service unavailable | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scan_client.py::test_fallback -x` | ❌ Wave 0 |
| 24-05-DOCKER | Security scanner Docker service responds to `/health` | smoke (manual) | `curl http://localhost:8003/health` | manual (docker service) |
| 24-06-LLM | LLM config POST calls LiteLLM `/model/new` | unit (mock httpx) | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_llm_config.py -x` | ❌ Wave 0 |
| 24-06-TABS | Admin layout renders 4 tabs | build (tsc) | `cd frontend && pnpm exec tsc --noEmit` | ✅ (after layout update) |

### Sampling Rate

- **Per task commit:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q -x --ignore=tests/mcp -k "not slow"`
- **Per wave merge:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Phase gate:** Full backend suite green + `pnpm exec tsc --noEmit` passes before `/gsd:verify-work`

### Wave 0 Gaps (test stubs to create before implementation)

- [ ] `tests/test_registry_models.py` — replace existing test (currently tests old ORM models); covers 24-02 schema
- [ ] `tests/api/test_registry_routes.py` — CRUD endpoints for `/api/registry/*`; covers 24-02-CRUD
- [ ] `tests/mcp/test_stdio_client.py` — mock subprocess, covers 24-03-STDIO
- [ ] `tests/mcp/test_installer.py` — mock subprocess for npm/pip install, covers 24-03-INSTALL
- [ ] `tests/skills/test_github_adapter.py` — mock httpx for GitHub API, covers 24-04-GITHUB
- [ ] `tests/test_security_scan_client.py` — mock httpx + fallback logic, covers 24-05-SCAN and 24-05-FALLBACK
- [ ] `tests/api/test_admin_llm_config.py` — mock httpx to LiteLLM, covers 24-06-LLM
- [ ] Migration: run `alembic merge 027 83f730920f5a -m "028_merge_heads"` — required before any registry migration

---

## Sources

### Primary (HIGH confidence)

- Codebase direct inspection — `backend/alembic/versions/` (migration chain), `backend/core/config.py` (settings), `backend/gateway/tool_registry.py`, `backend/mcp/client.py`, `backend/skills/importer.py`, `backend/skills/security_scanner.py`, `frontend/src/app/(authenticated)/admin/layout.tsx` (13 tabs), `infra/litellm/config.yaml`
- `docs/enhancements/unified-registry-proposal.md` — full schema, migration SQL, strategy pattern design
- `docs/enhancements/mcp-server-enhancement-proposal.md` — StdioMCPClient design, MCPInstaller, catalog seeding SQL
- `docs/enhancements/skill-import-adapter-framework.md` — SkillAdapter ABC, NormalizedSkill, AdapterRegistry
- `docs/enhancements/security-scan-module/00-specification.md` — scanner service architecture, API spec, Docker config, SecurityScanClient retry pattern
- `https://modelcontextprotocol.io/docs/develop/build-client` — StdioServerParameters + stdio_client API (verified)
- `.planning/phases/24-unified-registry-mcp-platform-enhancement-skill-import-adapters/24-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- LiteLLM docs `https://docs.litellm.ai/docs/proxy/model_management` — `/model/new`, `/model/update`, `/model/delete` endpoints exist and documented (verified, marked BETA)
- WebSearch: LiteLLM model management without restart — confirmed `/model/new` adds models dynamically; model persistence across restarts requires LiteLLM DB config (limitation documented)
- WebSearch: MCP Python SDK stdio transport — confirmed `StdioServerParameters(command, args, env)` + `stdio_client()` pattern; asyncio subprocess hang issues in SDK issue #671

### Tertiary (LOW confidence)

- LiteLLM `/config/update` hot-reload: WebSearch found a GitHub issue (#12148) noting this endpoint cannot update all settings without restart. Recommend using `/model/new` API instead of `/config/update` for model changes. (Unverified against current LiteLLM version.)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in codebase or official docs
- Architecture: HIGH — strategy pattern, adapter pattern, migration approach all verified against existing code structure
- Pitfalls: HIGH — Alembic two-head issue confirmed by direct inspection; gateway coupling confirmed by code review; JSONB pattern confirmed from Phase 16 decision
- LiteLLM hot-reload: MEDIUM — API endpoints confirmed but persistence behavior needs validation against running instance

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable libraries, 30-day window)
