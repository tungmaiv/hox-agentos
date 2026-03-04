# Stack Research: Blitz AgentOS

**Domain:** Enterprise on-premise agentic operating system
**Researched:** 2026-02-24 (v1.0–v1.2) | Updated: 2026-03-05 (v1.3 additions)
**Confidence:** HIGH (core stack verified via official docs and PyPI/npm; supporting libraries MEDIUM)

---

## v1.3 Stack Additions (NEW — Research Focus for This Document)

This section documents only the new libraries and patterns needed for v1.3. The existing stack (LangGraph, FastAPI, Next.js 15, CopilotKit, PostgreSQL + pgvector, Redis, Celery, LiteLLM, Keycloak) remains unchanged.

---

### 1. Next.js Middleware for Route Protection

**Decision:** Use `jose` + custom `middleware.ts` — do NOT add Auth.js v5 middleware.

**Rationale:** The project already uses NextAuth v5 (Auth.js) with a custom JWT strategy for dual-issuer tokens (local HS256 + Keycloak RS256). The existing `app/api/copilotkit/route.ts` proxy already injects JWT. What is missing is a `middleware.ts` that enforces authentication before any protected route renders.

**Critical security note:** CVE-2025-29927 (CVSS 9.1) disclosed March 2025 — middleware bypass via `x-middleware-subrequest` header — affects Next.js < 15.2.3. The project must be on Next.js 15.2.3+ before v1.3 ships. Defense-in-depth: always verify session at the data access layer (DAL), not only in middleware.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `jose` | ^5.x (npm) | JWT decode/verify in Edge Runtime | The only JWT library compatible with Next.js Edge Runtime; uses Web Crypto APIs; already recommended by official Next.js docs; `jwtVerify()` works for both HS256 (local tokens) and RS256 (Keycloak tokens) |
| `server-only` | latest (npm) | Mark session utilities as server-only | Prevents session code from leaking to client bundle; zero-cost guard |

**What NOT to add:**
- `jsonwebtoken` — cannot run in Edge Runtime (Node.js only)
- Auth.js middleware wrapper (`export { auth as middleware }`) — conflicts with the existing custom dual-issuer JWT dispatch; adds complexity without benefit
- Iron-session — stateful server sessions contradict the existing stateless JWT strategy

**Implementation pattern (middleware.ts):**
```typescript
// middleware.ts — cookie-only optimistic check, not full DB validation
import { jwtVerify } from 'jose'
import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_ROUTES = ['/login', '/api/auth', '/_next', '/favicon.ico']

export async function middleware(req: NextRequest) {
  const isPublic = PUBLIC_ROUTES.some(p => req.nextUrl.pathname.startsWith(p))
  if (isPublic) return NextResponse.next()

  const token = req.cookies.get('next-auth.session-token')?.value
    ?? req.cookies.get('__Secure-next-auth.session-token')?.value
  if (!token) return NextResponse.redirect(new URL('/login', req.url))

  try {
    // Optimistic check only — DAL verifySession() does full validation
    const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET)
    await jwtVerify(token, secret)
    return NextResponse.next()
  } catch {
    return NextResponse.redirect(new URL('/login', req.url))
  }
}

export const config = {
  matcher: ['/((?!api/auth|_next/static|_next/image|favicon.ico).*)'],
}
```

**Cookie security defaults (must be enforced):**
- `httpOnly: true` — blocks XSS access
- `secure: true` — HTTPS only in production
- `sameSite: 'lax'` — CSRF protection for same-site navigations
- `path: '/'` — available across entire app
- `maxAge` — 7 days (configurable, not indefinite)

**Installation:**
```bash
pnpm add jose server-only
```

**Source confidence:** HIGH — jose is the official Next.js authentication guide recommendation (nextjs.org/docs/app/guides/authentication, verified 2026-02-27). CVE-2025-29927 confirmed from Vercel postmortem (nextjs.org/blog/cve-2025-29927).

---

### 2. Embedding Sidecar Service

**Decision:** Deploy a separate FastAPI service using `infinity-emb` for configurable embedding model serving, accessible at `http://embedding:8003` from within Docker Compose.

**Rationale:** Currently, bge-m3 embedding runs inside Celery workers via FlagEmbedding. This couples the embedding model to the worker image, prevents model swapping without redeployment, and blocks CPU/GPU resource isolation. A dedicated sidecar service:
1. Allows changing the embedding model via env var (`INFINITY_MODEL_ID`) without code changes
2. Isolates memory pressure from Celery workers
3. Provides OpenAI-compatible `/v1/embeddings` endpoint — the backend switches from FlagEmbedding calls to HTTP calls, enabling future model changes (e.g., bge-m3 → bge-large-en) without touching Celery worker code

**Note:** bge-m3 `BAAI/bge-m3` is explicitly listed as a validated model in infinity-emb documentation.

| Library/Image | Version | Purpose | Why |
|---------|---------|---------|-----|
| `infinity-emb` (Docker image) | 0.0.77 (latest stable as of Aug 2025) | Embedding inference server | OpenAI-compatible REST API; supports bge-m3 natively; model selection via `INFINITY_MODEL_ID` env var; CPU/ONNX/GPU Docker variants; MIT license |
| `httpx` (Python) | already in stack | Backend calls to embedding sidecar | Already used for Keycloak JWKS; same pattern for embedding HTTP calls |

**Docker Compose service:**
```yaml
embedding:
  image: michaelf34/infinity:latest-cpu   # CPU-only; swap to :latest for GPU
  environment:
    INFINITY_MODEL_ID: "BAAI/bge-m3"
    INFINITY_PORT: "8003"
    INFINITY_BATCH_SIZE: "32"
    INFINITY_DEVICE: "cpu"               # or "cuda" for GPU host
  volumes:
    - embedding_cache:/app/.cache        # persist model weights
  ports:
    - "8003:8003"
  restart: unless-stopped
```

**Backend integration change:** Replace direct FlagEmbedding calls in Celery tasks with HTTP calls to the sidecar:
```python
# Before (in-process FlagEmbedding):
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
embeddings = model.encode(texts)['dense_vecs']

# After (HTTP sidecar):
import httpx
async with httpx.AsyncClient() as client:
    resp = await client.post(
        "http://embedding:8003/v1/embeddings",
        json={"input": texts, "model": "BAAI/bge-m3"}
    )
    embeddings = [item["embedding"] for item in resp.json()["data"]]
```

**What NOT to add:**
- A separate `sentence-transformers` HTTP server (reimplements what infinity-emb provides)
- Triton Inference Server — significant ops overhead; overkill for 100 users
- GPU requirement — infinity-emb CPU image works fine for 100 users; GPU is an optional upgrade

**Environment variable configuration (model swapping without code change):**
```bash
# Switch model at runtime by changing env var and restarting service:
INFINITY_MODEL_ID="BAAI/bge-large-en-v1.5"   # smaller, English-only
INFINITY_MODEL_ID="BAAI/bge-m3"               # default, multilingual
```

**Pitfall:** The embedding dimension in pgvector is locked at `vector(1024)` for bge-m3. Switching to a model with a different output dimension (e.g., bge-large at 1024, bge-base at 768) requires a full reindex. Validate output dimension before changing `INFINITY_MODEL_ID`.

**Source confidence:** HIGH — infinity-emb PyPI page (pypi.org/project/infinity-emb/, v0.0.77 verified Aug 2025). bge-m3 support confirmed from official GitHub README. Docker deployment pattern from michaelfeil/infinity GitHub.

**Installation:**
```bash
# No Python package install needed — infinity-emb runs as Docker service
# Backend only needs httpx (already installed) to call the sidecar
```

---

### 3. PostgreSQL Full-Text Search (tsvector) for Skill Catalog

**Decision:** Use native PostgreSQL `tsvector` with GIN index via raw Alembic migration SQL — no additional Python library needed.

**Rationale:** The skill catalog needs full-text search over skill `name`, `description`, and `tags` fields. PostgreSQL's native FTS is sufficient for 100 users and requires no additional infrastructure. SQLAlchemy 2.0 provides `func.to_tsvector()` and `func.plainto_tsquery()` in its `func` namespace for query construction.

**No new packages required.** The existing stack (SQLAlchemy 2.0, asyncpg, Alembic) handles this natively.

**Known Alembic gotcha:** Alembic autogenerate incorrectly detects "changes" on expression-based GIN indexes (using `to_tsvector()`). This is a known bug in Alembic 1.13.1+ / SQLAlchemy 2.0.25+. **Mitigation:** Create the GIN index via a manual Alembic migration using `op.execute()` with raw SQL rather than `op.create_index()` with `sa.text()`. Mark the migration as non-autogenerate with `include_symbol` configuration.

**Migration pattern (raw SQL, avoids Alembic false-positive drift detection):**
```python
# In Alembic migration file:
def upgrade():
    # Add tsvector computed column
    op.execute("""
        ALTER TABLE skills
        ADD COLUMN fts_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(name,'') || ' ' ||
                                   coalesce(description,'') || ' ' ||
                                   coalesce(tags,''))
        ) STORED
    """)
    # Create GIN index for fast FTS
    op.execute("""
        CREATE INDEX idx_skills_fts ON skills USING gin(fts_vector)
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_skills_fts")
    op.execute("ALTER TABLE skills DROP COLUMN IF EXISTS fts_vector")
```

**Query pattern (SQLAlchemy async):**
```python
from sqlalchemy import func, text

async def search_skills(query: str, session: AsyncSession) -> list[Skill]:
    result = await session.execute(
        select(Skill)
        .where(
            Skill.fts_vector.op("@@")(func.plainto_tsquery("english", query))
        )
        .order_by(
            func.ts_rank(Skill.fts_vector, func.plainto_tsquery("english", query)).desc()
        )
        .limit(50)
    )
    return result.scalars().all()
```

**What NOT to add:**
- `sqlalchemy-searchable` — adds triggers and complexity; overkill for a single table search
- Elasticsearch / OpenSearch — massively over-engineered for 100-user skill catalog
- `sqlalchemy-pg-fts` — alpha-quality PyPI package; native SQLAlchemy `func` namespace is sufficient
- Separate search microservice — YAGNI at this scale

**Alembic drift detection fix (add to `env.py`):**
```python
# Prevent Alembic from autogenerating changes for GIN expression indexes
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "index" and name in ("idx_skills_fts",):
        return False  # Skip autogenerate for manually managed indexes
    return True
```

**Source confidence:** MEDIUM — PostgreSQL tsvector docs (official, postgresql.org/docs/current). Alembic GIN index drift bug confirmed from GitHub Issue #1390. SQLAlchemy func namespace for FTS from official SQLAlchemy 2.0 PostgreSQL dialect docs. Async pattern inferred from existing codebase patterns (HIGH confidence for async itself).

---

### 4. Agent Skills Standard (agentskills.io) Compliance

**Decision:** Use `skills-ref` (Python CLI) for local validation only. No runtime dependency on any SDK. Skill compliance is enforced at export time via the existing skill export pipeline.

**What the standard requires (verified from agentskills.io/specification):**

A compliant skill is a directory with:
```
skill-name/
├── SKILL.md          # Required: YAML frontmatter + Markdown body
├── scripts/          # Optional: executable scripts
├── references/       # Optional: REFERENCE.md, domain-specific docs
└── assets/           # Optional: templates, images, data files
```

**Required SKILL.md frontmatter:**
```yaml
---
name: skill-name          # max 64 chars, lowercase + hyphens only, no leading/trailing hyphens
description: |            # max 1024 chars, non-empty, explains what AND when to use
  Extracts and summarizes email threads. Use when user asks for email digest
  or wants to review unread messages.
---
```

**Optional fields:** `license`, `compatibility`, `metadata` (arbitrary key-value), `allowed-tools` (experimental).

**Existing skill export (v1.2)** already produces a ZIP with `SKILL.md + procedure.json + schemas.json`. The v1.3 task is to ensure the existing `SKILL.md` format inside the ZIP is fully compliant with the agentskills.io specification (name constraints, description quality, optional fields populated).

| Tool | Version | Purpose | Production? |
|------|---------|---------|------------|
| `skills-ref` (PyPI) | 0.1.1 (Jan 2026) | CLI validation: `agentskills validate`, `agentskills to-prompt` | Alpha — dev/CI only |

**skills-ref provides three CLI commands:**
- `agentskills validate ./my-skill` — checks SKILL.md frontmatter is valid
- `agentskills read-properties ./my-skill` — outputs metadata as JSON
- `agentskills to-prompt ./my-skills/` — generates `<available_skills>` XML for agent prompts

**v1.3 compliance changes needed in existing code:**
1. `backend/api/routes/skills.py` (export endpoint): ensure generated `SKILL.md` uses agentskills.io name constraints (lowercase, hyphens, ≤64 chars)
2. Add `skills-ref validate` to CI pipeline for skill export tests
3. Skill builder wizard in `/admin`: add `compatibility` and `metadata.author` fields to the creation form
4. `agentskills to-prompt` output format can be used to populate the `<available_skills>` context in the master agent's system prompt — **this is the key new capability**, enabling the agent to discover and activate skills dynamically

**What NOT to add:**
- `agent-skills-sdk` (PyPI) — third-party package unrelated to the official agentskills/agentskills repo
- Skills auto-publish to agentskills.io registry — explicitly out of scope for v1.3
- `pydantic-ai-skills` — experimental third-party package, not part of the standard
- Runtime dependency on `skills-ref` in the FastAPI backend — it's a dev/CI tool only

**Industry adoption context (informs why this matters):** Agent Skills was open-sourced by Anthropic in Dec 2025 and adopted by Claude Code, GitHub Copilot, VS Code, Cursor, OpenAI Codex, Gemini CLI, and 20+ other platforms within 3 months. Blitz's compliance enables skills to be loaded by any of these tools.

**Installation:**
```bash
# Dev dependency only — not in production backend
uv add --dev skills-ref
```

**Source confidence:** HIGH — agentskills.io/specification (official spec, fetched directly). PyPI skills-ref 0.1.1 (Jan 2026). Industry adoption from unite.ai and agentskills.io reports.

---

### 5. Navigation Rail Pattern in React/Next.js

**Decision:** Use shadcn/ui `Sidebar` component with `SidebarRail` — specifically the `icon` collapse variant. No additional navigation library needed.

**Rationale:** shadcn/ui is already in the project's design system (used in admin dashboard, wizard, and form components). The `Sidebar` component (added to shadcn/ui in late 2024) provides a composable navigation rail with collapse-to-icons behavior, keyboard shortcut (Ctrl+B / Cmd+B), and responsive mobile handling — all needed for the menu redesign.

**Key shadcn/ui Sidebar sub-components:**

| Component | Purpose |
|-----------|---------|
| `SidebarProvider` | Context: manages open/collapsed state (with localStorage persistence) |
| `Sidebar` | Main container with `collapsible="icon"` variant for rail mode |
| `SidebarRail` | Renders the persistent rail strip that toggles the sidebar |
| `SidebarHeader` | Sticky top section (logo, workspace picker) |
| `SidebarContent` | Scrollable middle area (nav items) |
| `SidebarFooter` | Sticky bottom section (user profile, settings link) |
| `SidebarMenu` / `SidebarMenuItem` | Nav item list structure |
| `SidebarMenuButton` | Clickable nav item with icon + label |
| `SidebarTrigger` | Toggle button (place in page header for accessibility) |

**Collapse variant to use:** `collapsible="icon"` — collapses to icon-only rail (material design navigation rail pattern), not off-canvas. This is the correct pattern for a persistent desktop sidebar that can compact to icon-only mode.

**Integration with Next.js App Router:**
```typescript
// app/layout.tsx — wrap root layout with SidebarProvider
import { SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SidebarProvider defaultOpen={true}>
          <AppSidebar />
          <main>{children}</main>
        </SidebarProvider>
      </body>
    </html>
  )
}
```

**Installation (shadcn CLI — already available in project):**
```bash
# Add Sidebar component via shadcn CLI
pnpx shadcn@latest add sidebar

# This installs: sidebar, button, separator, sheet, skeleton, tooltip
# (all peer dependencies of the Sidebar component)
```

**What NOT to add:**
- `react-pro-sidebar` — third-party library; duplicates what shadcn/ui Sidebar already provides; adds a dependency that conflicts with project's Tailwind/Radix design system
- MUI Drawer/Navigation — MUI is not in the project stack; mixing component libraries creates style conflicts
- Custom CSS navigation rail from scratch — shadcn/ui Sidebar covers the requirement with accessible Radix primitives
- `zustand` for sidebar state — `SidebarProvider` handles open/collapsed state internally with cookie persistence

**Shadcn/ui version note:** The `Sidebar` component requires shadcn/ui components to be installed (not a versioned npm package — shadcn/ui copies components into your project). The component was stable as of late 2024 and is the canonical sidebar solution documented at ui.shadcn.com/docs/components/radix/sidebar.

**Source confidence:** MEDIUM-HIGH — shadcn/ui official docs (ui.shadcn.com/docs/components/radix/sidebar). SidebarRail sub-component confirmed from same docs. Next.js App Router integration verified from build.

---

## Version Compatibility Matrix (v1.3 Additions)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `jose` ^5.x | Next.js 15.2.3+ Edge Runtime | jose uses Web Crypto API — Edge-compatible; verify Next.js is 15.2.3+ (CVE-2025-29927 fix) |
| `infinity-emb` 0.0.77 (Docker) | bge-m3 (`BAAI/bge-m3`) | bge-m3 supported but sparse vectors not available; dense-only mode works for pgvector |
| `infinity-emb` (CPU image) | Docker Compose host (no GPU) | Use `michaelf34/infinity:latest-cpu`; model loads in ~30s on first start |
| tsvector (PostgreSQL 16) | SQLAlchemy 2.0 + asyncpg | `func.to_tsvector()` works in async SQLAlchemy; GIN index created via raw SQL migration |
| `skills-ref` 0.1.1 | Python 3.9+ | Dev/CI only; Alpha status — not for production backend |
| shadcn/ui Sidebar | Next.js 15 App Router + Tailwind | Component copied into project (not npm); requires Tailwind CSS (already in stack) |

---

## Installation Summary (v1.3 New Additions Only)

### Frontend
```bash
# Middleware JWT verification
pnpm add jose server-only

# Navigation rail component
pnpx shadcn@latest add sidebar
# installs: sidebar, button, separator, sheet, skeleton, tooltip into components/ui/
```

### Backend
```bash
# Agent Skills validation (dev/CI only)
uv add --dev skills-ref

# No new production backend packages — tsvector uses existing SQLAlchemy/asyncpg,
# embedding sidecar is accessed via httpx (already installed)
```

### Infrastructure (Docker Compose additions)
```yaml
# New service: embedding sidecar
embedding:
  image: michaelf34/infinity:latest-cpu
  environment:
    INFINITY_MODEL_ID: "BAAI/bge-m3"
    INFINITY_PORT: "8003"
  volumes:
    - embedding_cache:/app/.cache
  ports:
    - "8003:8003"

volumes:
  embedding_cache:  # persist downloaded model weights
```

---

## What NOT to Add (v1.3 Additions)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `jsonwebtoken` in middleware.ts | Node.js only; fails in Edge Runtime | `jose` (Web Crypto compatible) |
| Auth.js middleware wrapper for route protection | Conflicts with existing custom dual-issuer JWT; adds hidden complexity | Custom `middleware.ts` with `jose` |
| `sqlalchemy-searchable` | Trigger-based abstraction; overkill for a single table | Native `func.to_tsvector()` + raw SQL migration |
| `Elasticsearch` / `MeiliSearch` | Separate infrastructure; overkill for 100-user skill catalog | PostgreSQL tsvector + GIN index |
| `react-pro-sidebar` or MUI Navigation | Adds dependency conflict with existing Tailwind/Radix design system | shadcn/ui `Sidebar` component |
| `agent-skills-sdk` (PyPI) | Third-party; not the official agentskills/agentskills reference impl | `skills-ref` for validation, custom export logic |
| `skills-ref` in production FastAPI | Alpha quality; not production-ready | Use only in CI pipeline and dev tooling |
| Triton Inference Server for embeddings | Massive ops overhead; requires Kubernetes; overkill | `infinity-emb` Docker sidecar |
| FlagEmbedding in production after sidecar ships | Tight coupling of model to worker; blocks model swapping | `infinity-emb` HTTP sidecar + `httpx` |

---

## Existing Stack (v1.0–v1.2) — No Changes for v1.3

The following are confirmed unchanged and require no re-research for v1.3:

### Agent Orchestration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| LangGraph | 1.0.9 | Agent graph orchestration, multi-agent workflows | v1.0 GA (stable); graph-based design maps directly to visual canvas workflows; built-in persistence, HITL, and checkpointing; adopted by Uber, LinkedIn, Klarna; pre-built patterns for Supervisor/Swarm architectures | HIGH |
| PydanticAI | 1.63.0 | Tool I/O validation, structured LLM output | Type-safe tool schemas with automatic LLM retry on validation failure; strict JSON schema enforcement for Anthropic/OpenAI; natural fit with FastAPI's Pydantic ecosystem | HIGH |
| langgraph-prebuilt | latest | Pre-built agent patterns (Supervisor, Swarm) | Reduces boilerplate for common multi-agent architectures; official LangChain package | MEDIUM |

### Frontend Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Next.js | 15.5+ (consider 16.x) | Frontend framework (App Router) | Server Components by default reduces client bundle; Turbopack stable for dev/build; typed routes in 15.5+; React 19 support; dominant framework for React apps | HIGH |
| CopilotKit | 1.51.x | AG-UI streaming, agent chat UI, CoAgents | The definitive AG-UI protocol implementation; adopted by Google, Microsoft, LangChain, AWS; real-time agent streaming with tool call visualization; `useCoAgent` for bidirectional state sync between frontend and backend StateGraph | HIGH |
| React Flow (@xyflow/react) | 12.10.x | Visual workflow canvas | Only production-grade React node-based editor; SSR support; `definition_json` stored natively as React Flow format (nodes/edges); workflow editor template with auto-layout available; v12 is stable with active maintenance | HIGH |

### Generative UI

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| A2UI (Google) | 0.8.x (Public Preview) | Declarative agent-driven UI specification | Open standard by Google; declarative JSON (not executable code) — security-safe for enterprise; flat component list is LLM-friendly for incremental generation; CopilotKit has first-class A2UI support | MEDIUM |
| CopilotKit Generative UI | 1.51.x | Runtime rendering of agent-generated components | Agents can render custom React components in chat; A2UI envelopes parsed in `A2UIMessageRenderer`; works with AG-UI protocol natively | HIGH |

### Backend Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| FastAPI | 0.115.13+ | REST API, WebSocket, async HTTP server | Async-first; native Pydantic v2 integration; automatic OpenAPI docs; dependency injection for security gates; streaming response support for AG-UI | HIGH |
| SQLAlchemy | 2.0.46 | Async ORM + raw SQL | Production-stable async support since 2.0; `async_session()` pattern; works with asyncpg for PostgreSQL | HIGH |
| asyncpg | latest | PostgreSQL async driver | Fastest Python PostgreSQL driver; native connection pooling; required by SQLAlchemy async | HIGH |
| Alembic | latest | Database migrations | Official SQLAlchemy migration tool; async support; required for schema evolution | HIGH |

### Identity & SSO

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Keycloak | 26.5.x | Identity provider, SSO, RBAC | Existing infrastructure (already running); v26.5 adds JWT Authorization Grants, FAPI 2.0, Organizations (multi-tenancy), Passkey support; CNCF project; OpenTelemetry integration for observability; fine-grained admin permissions v2 | HIGH |

### Database & Vector Search

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| PostgreSQL | 16+ (pgvector/pgvector:pg16 image) | Primary database + vector search | Single database for relational + vector data; `WHERE user_id = $1` enforces memory isolation in the same query as vector search; eliminates sync complexity of a separate vector DB | HIGH |
| pgvector | 0.8.x | Vector similarity search extension | v0.8 adds iterative index scans (prevents over-filtering), HNSW index improvements (9x faster queries reported on Aurora); `vector(1024)` for bge-m3 embeddings; supports cosine, L2, and inner product distance | HIGH |

### Embedding Model

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| bge-m3 (BAAI) | latest | Text embeddings (1024-dim) | Multilingual (100+ languages including Vietnamese); 8192 token input; dense + sparse + multi-vector retrieval; self-hosted via FlagEmbedding for on-premise compliance; top MTEB scores for multilingual | HIGH |
| FlagEmbedding | 1.3.5 | Python library for bge-m3 inference | Official BAAI library; `BGEM3FlagModel` class with fp16 support; handles all three retrieval modes. **NOTE for v1.3:** Replaced by infinity-emb HTTP sidecar — FlagEmbedding removed from worker code | HIGH |

### LLM Gateway

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| LiteLLM Proxy | 1.81.x | Unified LLM gateway, routing, fallback | OpenAI-compatible API for 100+ providers; 8ms P95 latency at 1k RPS; cost tracking + guardrails + load balancing; model aliases (`blitz/master`, `blitz/fast`, etc.) route to different backends transparently; JWT auth built-in; Docker-deployable with `-stable` tag | HIGH |

### MCP Integration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| MCP Python SDK | 1.26.x | MCP server/client implementation | Official Anthropic SDK; supports Streamable HTTP transport (recommended) and legacy SSE; FastMCP helper for rapid server creation | HIGH |

### Task Queue & Scheduler

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Celery | 5.6.2 | Task queue, scheduled jobs, background workers | Battle-tested for Python async workloads; Redis as broker (already in stack); cron-style scheduling via Celery Beat; runs as job owner's UserContext (not service account); sufficient for 100-user scale | HIGH |
| Redis | 7.x (or 8.x) | Cache, message broker, Celery backend | Fast, simple, proven as Celery broker; pub/sub for real-time notifications; session cache | HIGH |

### Observability & Logging

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| structlog | 25.5.0 | Structured JSON logging | Production-proven since 2013; JSON output is Loki-compatible; asyncio context variable support; type hints; audit logger pattern via `get_audit_logger()` | HIGH |
| Grafana | latest | Dashboards, alerting | De facto standard for observability dashboards; Loki integration for log queries | HIGH |
| Loki | latest | Log aggregation | Lightweight log aggregation that indexes labels (not full text); pairs with structlog JSON output; much simpler than ELK at 100-user scale | MEDIUM |
| Alloy (Grafana) | latest | Telemetry collector | Replaces Promtail; collects logs, metrics, traces; ships to Loki/Prometheus | MEDIUM |

---

## Sources

### v1.3 New Research (2026-03-05)

- Next.js authentication guide (official, fetched 2026-02-27): https://nextjs.org/docs/app/guides/authentication
- CVE-2025-29927 Vercel postmortem: https://nextjs.org/blog/cve-2025-29927
- Auth.js v5 protecting routes: https://authjs.dev/getting-started/session-management/protecting
- jose npm: https://www.npmjs.com/package/jose
- infinity-emb PyPI (v0.0.77, Aug 2025): https://pypi.org/project/infinity-emb/
- michaelfeil/infinity GitHub (bge-m3 support confirmed): https://github.com/michaelfeil/infinity
- agentskills.io specification (fetched directly): https://agentskills.io/specification
- skills-ref PyPI (v0.1.1, Jan 2026): https://pypi.org/project/skills-ref/
- shadcn/ui Sidebar docs: https://ui.shadcn.com/docs/components/radix/sidebar
- Alembic GIN index drift bug: https://github.com/sqlalchemy/alembic/issues/1390
- PostgreSQL tsvector docs: https://www.postgresql.org/docs/current/datatype-textsearch.html
- SQLAlchemy 2.0 PostgreSQL dialect: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html

### v1.0–v1.2 Research (2026-02-24 — see git history for full source list)

- LangGraph 1.0 announcement: https://blog.langchain.com/langchain-langgraph-1dot0/
- CopilotKit npm (v1.51.x): https://www.npmjs.com/package/@copilotkit/react-core
- React Flow v12 release: https://xyflow.com/blog/react-flow-12-release
- FastAPI release notes: https://fastapi.tiangolo.com/release-notes/
- Keycloak 26.5 releases: https://www.keycloak.org/2026/02/keycloak-2653-released
- pgvector 0.8.0 announcement: https://www.postgresql.org/about/news/pgvector-080-released-2952/
- LiteLLM docs: https://docs.litellm.ai/
- MCP spec transports (Streamable HTTP): https://modelcontextprotocol.io/specification/2025-03-26/basic/transports

---
*Stack research for: Blitz AgentOS — Enterprise on-premise agentic operating system*
*Original research: 2026-02-24 | v1.3 additions: 2026-03-05*
