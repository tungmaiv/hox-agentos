# Feature Research

**Domain:** Enterprise Agentic OS — v1.3 Production Readiness & Skill Platform
**Researched:** 2026-03-05
**Confidence:** HIGH for Next.js auth patterns and Agent Skills spec (official sources); MEDIUM for embedding sidecar and Keycloak runtime config; MEDIUM for navigation rail UX (established HCI pattern, no formal study)

---

## Context: What Is Already Built (v1.0–v1.2)

This file covers **only new features for v1.3**. Everything below assumes the following is shipped and working:

- Dual auth (Keycloak SSO + local bcrypt), 3-gate security (JWT/RBAC/ACL)
- Master agent with sub-agents, 3-tier memory, visual workflow canvas, HITL
- Multi-channel (Telegram live, WhatsApp/Teams code-complete)
- Admin dashboard with AI wizard, OpenAPI-to-MCP bridge, external skill repos
- agentskills.io-compliant export, SecurityScanner quarantine, PromptLoader
- Grafana + Loki + Alloy observability, Cloudflare Tunnel

---

## Feature Landscape: v1.3 New Features

### Five Feature Clusters

| Cluster | Feature Focus | Already Has Foundation |
|---------|--------------|----------------------|
| A | Session & auth hardening (Next.js middleware, cookie security) | Dual-issuer JWT, Keycloak SSO |
| B | Navigation redesign (rail), profile page, user preferences | /admin desk, Settings page (removed) |
| C | Performance + embedding sidecar service | bge-m3 in Celery workers (in-process) |
| D | Keycloak runtime configuration (admin-configurable) | Keycloak running, blitz-internal realm live |
| E | Skill platform: Agent Skills standard compliance, catalog, discovery, marketplace | agentskills.io export, SecurityScanner |

---

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or insecure.

#### Cluster A: Session & Auth Hardening

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Middleware route protection (middleware.ts) | Any Next.js 15 app with auth must gate protected routes at the edge. Without it, unauthenticated users can navigate to /admin, /chat, /canvas. CVE-2025-29927 (CVSS 9.1) exposed middleware-only reliance — fix requires defense-in-depth. | LOW | `middleware.ts` reads session cookie, redirects to /login if absent. JWT-verified at edge. Must also verify at Data Access Layer (server actions, route handlers). |
| HttpOnly session cookie (not localStorage) | CLAUDE.md mandates `JWT stored in memory only (not localStorage)` — XSS protection. Industry standard since ~2020. Any web app with sensitive data must use HttpOnly. | LOW | Cookie: `HttpOnly; Secure; SameSite=Lax`. Use `jose` for JWT signing/verification at edge. Replaces any in-memory client state as the persistence layer. |
| Session expiry + silent refresh | Users expect sessions to last a workday without forced re-login. Without refresh tokens, 1-hour JWT expiry constantly logs users out. | MEDIUM | Short-lived access token (1h) + HttpOnly refresh token cookie (7d). Background refresh when access token has < 5 min left. Works for both local bcrypt and Keycloak paths. |
| Logout (clear session) | Missing logout is a critical security gap and an obvious UX failure. `/api/auth/logout` that clears all cookies. | LOW | Server action clears `session` and `refresh_token` cookies. Keycloak path: also call Keycloak logout endpoint to invalidate refresh token server-side. |

#### Cluster B: Navigation & User Preferences

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Persistent navigation across routes | After adding /admin, /canvas, /chat, /settings, users need clear wayfinding. A top-level nav rail solves this. Without it, the app feels like a collection of disconnected pages. | LOW | Vertical icon rail (60–80px wide), always visible on desktop. Icons: Chat, Canvas, Admin, Profile. Supports 4–7 top-level destinations. Active-state highlight. |
| Profile page (/profile) | Users expect to see their account info, role, and manage session. Missing = no way to know who is logged in. | LOW | Displays: display name, email, role (from JWT claims), last login. Links to credential management. Logout button here. |
| LLM thinking mode toggle | Blitz AgentOS exposes `blitz/master` (complex reasoning) and `blitz/fast` (simple tasks). Users want control over when the agent "thinks deeply" vs responds quickly. ChatGPT, Claude, and Gemini all expose this. | MEDIUM | User preference stored in DB (`user_preferences` table). Toggle: Extended Thinking ON/OFF. When ON, adds thinking budget to LiteLLM calls for supported models. When OFF, uses fast path. Applied per-user at agent invocation. |
| Response style preference | Users differ: some want verbose explanations, others want bullet-point brevity. Explicit preference > implicit inference for enterprise. | MEDIUM | Preference: `response_style` in {detailed, concise, bullet_points}. Injected as instruction suffix in system prompt via PromptLoader. Persisted per-user. |

#### Cluster C: Performance & Embedding Sidecar

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Sub-second embedding response | Memory search (pgvector) is on the hot path for every agent invocation. Celery-worker embedding adds 500–3000ms queue latency. Users notice when the agent pauses. | MEDIUM | Separate FastAPI sidecar on port 8010 that loads bge-m3 once at startup. Backend calls `POST /embed` instead of dispatching to Celery. Keeps model warm in RAM permanently. |
| Embedding sidecar hot-model (bge-m3 stays loaded) | In current architecture, Celery workers load bge-m3 per-task (or keep it warm with concurrency=1). Sidecar keeps the model loaded in one process with a request queue. | MEDIUM | Sidecar exposes `/embed` (single text) and `/embed/batch` (list of texts). Returns `{"embedding": [...], "dim": 1024}`. Includes asyncio batching with 50ms accumulation window for efficiency. |
| Performance bottleneck visibility | Without timing instrumentation on the 7 critical paths (memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run), you cannot identify what to fix. | LOW | Add `duration_ms` to existing structlog entries for these paths. Grafana dashboards already exist — add panels for p50/p95 per operation. |

#### Cluster D: Keycloak Runtime Configuration

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Keycloak-optional boot (local-auth-first) | Current startup requires Keycloak to be reachable (JWKS fetch). If Keycloak is down, local-auth users cannot log in. Enterprises need the system to work when the identity provider is unavailable. | MEDIUM | Boot sequence: attempt Keycloak JWKS fetch; if it fails, enter local-auth-only mode. Log a warning. Resume Keycloak mode when JWKS becomes reachable again. Keycloak status shown in admin Health panel. |
| Keycloak connection config via admin UI | Admins currently configure Keycloak via `backend/.env` — requires SSH access and service restart. Admins expect to change OIDC provider settings through the web UI. | MEDIUM | Admin UI form: Keycloak URL, realm, client ID, client secret, CA cert path. Stored in `platform_config` DB table (encrypted sensitive fields). Backend reloads JWKS on save. No restart required — Keycloak config is runtime data, not build-time. |
| Keycloak connection test in admin UI | Before saving Keycloak config, admin should be able to verify it works. "Test Connection" button that calls the JWKS endpoint and validates reachability. | LOW | `POST /api/admin/keycloak/test-connection` — attempts JWKS fetch with provided config, returns `{reachable: bool, error?: string}`. |

#### Cluster E: Skill Platform

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Agent Skills spec compliance (SKILL.md format) | Blitz already exports agentskills.io-compatible packages, but the builder must also produce spec-valid SKILL.md with correct frontmatter (`name`, `description`, `license`, `metadata.version`, `compatibility`, `allowed-tools`). Without this, exported skills fail validation in other systems. | LOW | `name` field: max 64 chars, lowercase letters/numbers/hyphens, no consecutive hyphens, matches directory name. `description`: max 1024 chars, states what AND when to use. Use `skills-ref validate` CLI to check output. |
| Skill catalog (browsable list of local skills) | Users and admins need a searchable list of what skills are available in the platform. Currently skills are managed as records but not browsable as a catalog with filter/search/sort. | MEDIUM | `/admin/skills/catalog` page. Filter by: category, author, status (active/quarantine/disabled), compatibility. Search by name/description. Shows: name, description, version, install count, last updated. |
| Skill discovery from external registries | Beyond the existing "import from Git URL" flow, admins should be able to browse skills from known external registries (agentskills.io, GitHub repos, team-internal registry). | MEDIUM | Browse panel with paginated index fetched from configured registry URLs. Each entry shows: name, description, author, license, compatibility. One-click "Import" triggers existing SecurityScanner + quarantine flow. Registry URLs configurable in admin settings. |
| Skill dependency hardening | Skills that import Python packages or shell commands must declare dependencies explicitly. SecurityScanner should block skills with undeclared or high-risk dependencies. | MEDIUM | Skills with `scripts/` directory must include a `requirements.txt` or `dependencies.json`. Scanner checks declared vs used packages. Blocks skills importing `subprocess`, `os.system`, socket calls outside approved allowlist. |
| Skill marketplace / sharing | Users who create useful skills want to share them with teammates. Admins want to promote organization-internal skills to a curated catalog. | MEDIUM | Internal "Promoted Skills" section in catalog (admin-curated). Export remains agentskills.io-compliant zip. No auto-publish to external registries (deferred — explicitly out of scope). |

---

### Differentiators (Competitive Advantage)

Features that set v1.3 apart from the v1.2 baseline and from generic agent platforms.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Embedding sidecar with model hot-swap path | Single warm bge-m3 process eliminates Celery queue latency from memory search. Model swap (e.g., to `bge-large-en`) requires only sidecar container replace, no backend restart. | MEDIUM | Model config in sidecar env var `EMBED_MODEL`. Sidecar health endpoint `/health`. Backend falls back to Celery path if sidecar unreachable. Hot-swap: bring up new sidecar, drain, cut over — zero downtime. |
| Keycloak as optional, not required | System works without Keycloak (local-auth-first mode). Most enterprise agentic platforms require their identity provider to be online. This removes a critical single point of failure. | MEDIUM | `iss`-based JWT dispatch already works for dual-issuer. Change: make JWKS fetch async/non-blocking at startup. Add admin health panel showing Keycloak status. |
| Skills as first-class platform citizens (not just importable packages) | v1.2 treats skills as importable artifacts. v1.3 adds catalog, discovery, dependency enforcement, and promotion — making skills a managed platform resource like agents and tools. | HIGH | Brings Blitz closer to SkillsMP / agentskills.io catalog UX. For an enterprise, the ability to discover, vet, and promote internal skills is high-value governance. |
| User LLM preferences baked into system prompt | Most platforms expose model selection globally or per-workspace. Per-user LLM preferences (thinking depth, response style) that travel with the user across devices and sessions is uncommon. | MEDIUM | `user_preferences` table: `thinking_mode`, `response_style`, `preferred_model_alias`. Injected via PromptLoader into agent system prompt on each invocation. Persists across sessions. |
| Agent Skills `allowed-tools` enforcement | The spec's experimental `allowed-tools` field declares which tools a skill is pre-approved to use. Blitz can enforce this at Gate 3 (Tool ACL), creating skill-level sandboxing on top of user-level ACL. | HIGH | When activating a skill, intersect skill's `allowed-tools` with user's ACL. Deny tool calls not in the intersection. Log denials. First platform to enforce this spec field in production (most ignore it). |

---

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-publish skills to agentskills.io public registry | "Why not publish our skills to the ecosystem?" | Skills may contain proprietary business logic, internal API patterns, or PII-adjacent workflows. Auto-publish violates data-stays-on-premise requirement. Also: public registry requires policy review per skill. | Keep agentskills.io-compliant **export** (already built). Admin decides what to share. No auto-publish — explicitly Out of Scope in v1.3. |
| JWT stored in localStorage as well as cookie | "We need to access the token from client-side JavaScript for the CopilotKit calls" | localStorage is vulnerable to XSS. CLAUDE.md mandates HttpOnly cookie. The CopilotKit `/api/copilotkit` route proxy already injects the JWT server-side — client-side code never needs the raw token. | Server-side Next.js route handlers read the HttpOnly cookie and inject the JWT into backend calls. Client never touches the token. |
| Keycloak as sole auth (remove local bcrypt) | "Why maintain two auth paths?" | Local auth is the fallback when Keycloak is down. ~100 users means even 1 hour of Keycloak downtime affects the whole company. Removing local auth creates a hard dependency on an external system. | Keep dual-issuer. Keycloak is primary; local bcrypt is fallback/emergency. The `iss`-based dispatch is already working — no maintenance burden. |
| Real-time skill install notifications ("someone published a skill") | "Like npm notifications — alert users when new skills are available" | For ~100 users with a curated internal catalog, push notifications for skill updates are operational noise. Admins promote skills; users discover on demand via catalog. | Polling catalog refresh (5-min TTL). Skill version badge in catalog shows when a newer version is available. No push notifications. |
| Skill ratings and reviews (star system) | "Users should rate skills like an app store" | At 100 users, a 5-star system provides statistically meaningless signal. A skill with 3 ratings means nothing. Over-engineered for scale. | Simple usage count (number of activations) shown in catalog. Admins add a "Recommended" badge to promote quality skills. |
| Multi-model embedding (switch per-user or per-request) | "Some users want English embeddings, others Vietnamese" | bge-m3 is multilingual (handles Vietnamese + English natively — that's why it was chosen). Multiple embedding models means multiple vector dimensions, breaking the `vector(1024)` constraint and requiring separate columns/indexes. Full reindex on change = downtime. | Single bge-m3 sidecar. Dimension locked at 1024. Multilingual is bge-m3's core strength — no per-user model needed. |

---

## Feature Dependencies

```
[Session & Auth Hardening (Cluster A)]
    |-- builds-on --> [Existing dual-issuer JWT dispatch]
    |-- builds-on --> [Keycloak SSO + local bcrypt (v1.0)]
    |-- enables --> [Keycloak runtime config (Cluster D)] (needs session to protect admin UI)
    |-- enables --> [User preferences (Cluster B)] (needs user_id from session)

[Navigation Rail (Cluster B)]
    |-- builds-on --> [Existing /admin, /canvas, /chat pages]
    |-- requires --> [Profile page] (nav item needs destination)
    |-- enhances --> [User preferences] (accessible from profile)

[User Preferences (Cluster B)]
    |-- requires --> [Auth session] (preferences keyed by user_id from JWT)
    |-- requires --> [PromptLoader] (already built — injects preferences into system prompt)
    |-- enhances --> [Master agent] (thinking mode changes blitz/master behavior)

[Embedding Sidecar (Cluster C)]
    |-- replaces --> [Celery embedding task] (same bge-m3 model, different invocation path)
    |-- requires --> [existing pgvector memory tables] (sidecar output feeds same vectors)
    |-- backwards-compatible-with --> [Celery fallback] (if sidecar unreachable)

[Keycloak Runtime Config (Cluster D)]
    |-- builds-on --> [Admin dashboard at /admin (v1.2)]
    |-- builds-on --> [Keycloak-optional boot] (prerequisite — if Keycloak can be optional, config can be loaded from DB)
    |-- requires --> [platform_config DB table] (new migration)

[Skill Catalog + Discovery (Cluster E)]
    |-- builds-on --> [External skill repository management (v1.2)]
    |-- builds-on --> [SecurityScanner quarantine (v1.2)]
    |-- builds-on --> [agentskills.io export (v1.2)]
    |-- requires --> [skill_registry table] (already exists — add catalog metadata columns)
    |-- enhances --> [Skill dependency hardening] (catalog shows dependency scan results)

[Agent Skills spec compliance]
    |-- builds-on --> [agentskills.io export (v1.2)]
    |-- verifies-with --> [skills-ref CLI] (Anthropic's reference validator)
    |-- enables --> [allowed-tools enforcement] (spec field → Gate 3 intersection)

[allowed-tools enforcement]
    |-- requires --> [Agent Skills spec compliance] (field must be present in SKILL.md)
    |-- requires --> [Gate 3 Tool ACL] (already built — add skill context to ACL check)
    |-- conflicts --> [Skills without allowed-tools field] (treated as unrestricted — backward compatible)
```

### Dependency Notes

- **Auth hardening (Cluster A) is prerequisite for everything else in v1.3.** Profile, preferences, and Keycloak config all need a reliable session. Build first.
- **Navigation rail (Cluster B) is cosmetic but enables UX for B, C, D, E features.** Profile page is where preferences live; admin desk is where skill catalog and Keycloak config live.
- **Embedding sidecar (Cluster C) is architecturally independent.** Can be built and shipped in parallel with any other cluster. Backend falls back gracefully if sidecar is absent.
- **Keycloak runtime config (Cluster D) depends on the admin desk being stable.** Build after auth hardening confirms the admin session is secure.
- **Skill platform (Cluster E) is additive to the existing v1.2 skill import/export.** No existing functionality is broken. Catalog, discovery, and enforcement are layered on top.

---

## MVP Definition for v1.3

### Launch With (v1.3 required features)

Minimum set for v1.3 to be called "Production Readiness & Skill Platform."

- [ ] **middleware.ts route protection** — Gate all /chat, /admin, /canvas, /canvas/*, /profile routes. Redirect to /login if no valid session cookie. Defense-in-depth: verify at Data Access Layer as well.
- [ ] **HttpOnly session cookie** — Replace any localStorage JWT storage. Set `Secure; SameSite=Lax; HttpOnly`. Silent refresh via `/api/auth/refresh`.
- [ ] **Logout endpoint + UI button** — `POST /api/auth/logout` clears cookies. Button in nav rail profile icon dropdown and profile page.
- [ ] **Navigation rail** — Vertical icon rail with Chat, Canvas, Admin, Profile destinations. Replaces current ad-hoc nav links.
- [ ] **Profile page (/profile)** — Shows user info (name, email, role), logout button, link to credential management.
- [ ] **User preferences (thinking mode + response style)** — DB table, API endpoints, UI in profile page. Injected into agent system prompt via PromptLoader.
- [ ] **Embedding sidecar service** — FastAPI service on port 8010, loads bge-m3 at startup, exposes `/embed` and `/embed/batch`. Backend `memory/embeddings.py` calls sidecar first, Celery fallback if unreachable.
- [ ] **Performance instrumentation (7 paths)** — Add `duration_ms` to structlog for: memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run.
- [ ] **Keycloak-optional boot** — Backend starts without Keycloak being reachable. Local-auth continues working. Keycloak health shown in /admin Health panel.
- [ ] **Agent Skills SKILL.md spec compliance** — Validate exported zips against agentskills.io spec. Run `skills-ref validate` as part of export CI check. Fix any frontmatter violations.
- [ ] **Skill catalog UI** — `/admin/skills/catalog` with filter (category, status), search (name/description), and skill detail view.
- [ ] **Skill discovery from external registries** — Admin-configured registry URLs, paginated browse, one-click import into existing SecurityScanner flow.
- [ ] **Skill dependency hardening** — Scripts directory requires declared dependencies. SecurityScanner blocks undeclared subprocess/socket usage.

### Add After Validation (v1.3.x — stretch goals)

- [ ] **Keycloak runtime config via admin UI** — Add after Keycloak-optional boot is confirmed stable. Store in `platform_config` table (encrypted). Test-connection button.
- [ ] **allowed-tools enforcement** — Add after SKILL.md spec compliance is verified. Gate 3 intersection of skill `allowed-tools` with user ACL.
- [ ] **Skill marketplace (internal promotion)** — Admin "Promoted Skills" badge in catalog. After catalog is used and admins have a feel for which skills to surface.

### Future Consideration (v1.4+)

- [ ] **Skill auto-sync from registries** — Celery periodic task to refresh remote index. Out of scope for v1.3; manual sync is sufficient.
- [ ] **Agent Skills `allowed-tools` for MCP tools** — Extend to MCP tool names (not just backend tools). After MCP governance patterns solidify.
- [ ] **Skill rating/feedback** — Usage counts in v1.3; stars/reviews deferred until user base grows.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| middleware.ts route protection | HIGH | LOW | P1 |
| HttpOnly session cookie + silent refresh | HIGH | LOW | P1 |
| Logout endpoint + UI | HIGH | LOW | P1 |
| Navigation rail | HIGH | LOW | P1 |
| Profile page (/profile) | MEDIUM | LOW | P1 |
| User preferences (thinking mode, response style) | MEDIUM | MEDIUM | P1 |
| Embedding sidecar (bge-m3 warm process) | HIGH | MEDIUM | P1 |
| Performance instrumentation (7 paths) | MEDIUM | LOW | P1 |
| Keycloak-optional boot | HIGH | MEDIUM | P1 |
| Agent Skills SKILL.md spec compliance | MEDIUM | LOW | P1 |
| Skill catalog UI (filter/search) | MEDIUM | MEDIUM | P1 |
| Skill discovery from external registries | MEDIUM | MEDIUM | P1 |
| Skill dependency hardening | HIGH | MEDIUM | P1 |
| Keycloak admin UI runtime config | MEDIUM | MEDIUM | P2 |
| allowed-tools enforcement (skill sandboxing) | HIGH | HIGH | P2 |
| Skill marketplace (internal promotion) | LOW | LOW | P2 |
| Performance bottleneck fixes (7 identified) | HIGH | HIGH | P2 |

**Priority key:**
- P1: Required for v1.3 to ship — production readiness and skill platform goals met
- P2: Should have — adds significant value, implement after P1 is stable
- P3: Nice to have — deferred to v1.3.x or v1.4

---

## Research Notes Per Feature Area

### 1. Next.js Middleware Route Protection Patterns (Cluster A)

**Confidence: HIGH** — Official Next.js docs + CVE disclosure confirm patterns.

The standard v1.3 pattern for Next.js 15 App Router:

1. `middleware.ts` at project root — reads `session` cookie, does lightweight JWT signature check (using `jose` which runs in Edge Runtime), redirects to `/login` if invalid. This is a "fast bouncer," not the only security layer.

2. **CVE-2025-29927 (CVSS 9.1)** — middleware bypass in Next.js < 15.2.3 via `x-middleware-subrequest` header manipulation. Mitigation: upgrade to 15.2.3+ AND add Data Access Layer verification.

3. **Data Access Layer (DAL) pattern** — `lib/dal.ts` with `'server-only'` import and React `cache()` memoization. `verifySession()` called in every Server Component, Server Action, and Route Handler that touches sensitive data. This is the real security gate; middleware is optimization.

4. **Token storage**: Access token in `session` HttpOnly cookie (1h TTL). Refresh token in `refresh_token` HttpOnly cookie (7d TTL). Never localStorage.

5. **Silent refresh**: Route handler `/api/auth/refresh` checks refresh token cookie validity, issues new access token cookie. Called automatically when access token is < 5 min from expiry.

The dual-issuer JWT dispatch already in `backend/security/jwt.py` is compatible — middleware only needs to verify the cookie exists and has a valid signature (not decode the full payload).

**Implementation note:** Next.js `middleware.ts` runs in the Edge Runtime — only `jose` (not `jsonwebtoken`) works there because `jsonwebtoken` uses Node.js crypto APIs not available in Edge.

**Source confidence:** [Next.js Auth Guide 2026 (WorkOS)](https://workos.com/blog/nextjs-app-router-authentication-guide-2026) — HIGH; [CVE-2025-29927 disclosure](https://dev.to/nidal_tahir_cde5660ddbe04/how-i-built-a-secure-scalable-auth-system-in-nextjs-15-with-jwt-edge-middleware-and-drizzle-47ji) — MEDIUM (CVE confirmed real).

---

### 2. Embedding Sidecar Architecture (Cluster C)

**Confidence: MEDIUM** — Pattern is established (Azure sidecar tutorials, BentoML docs), bge-m3 specific sidecar confirmed by open-source reference (`puppetm4st3r/baai_m3_simple_server`).

Standard pattern: separate FastAPI process dedicated to model serving.

Key components discovered:
- **`AIModel` class** wraps `BGEM3FlagModel` — loaded once at startup, stays in RAM.
- **`RequestProcessor` class** — asyncio-based batch aggregation with semaphore-based concurrency limiter. Groups requests within a 50ms window before calling the model. Maximizes GPU/CPU efficiency.
- **API**: `POST /embeddings/` (returns dense vector) and `POST /rerank/` (returns reranking scores). Both async.
- **Timeout middleware** — 504 if embedding takes > N seconds. Protects backend from hanging on sidecar failures.

**Model hot-swap** (for future use): done at the container level — spin up new sidecar container with `EMBED_MODEL=new-model`, health-check it, update backend `EMBED_SIDECAR_URL` env var (or use service discovery), drain old container. Zero-downtime because backend falls back to Celery during transition.

For Blitz specifically: sidecar does NOT need GPU because bge-m3 at 100-user scale runs comfortably on CPU (1024-dim, ~70ms per embedding on modern CPU). GPU is optional.

**Warning:** `transformers<5.0` pin must be maintained in the sidecar (same constraint as Celery workers). `FlagEmbedding 1.3.x` breaks on `transformers 5.0+`.

**Source confidence:** [puppetm4st3r/baai_m3_simple_server (GitHub)](https://github.com/puppetm4st3r/baai_m3_simple_server) — MEDIUM (open-source reference, not official docs); [Azure sidecar pattern](https://learn.microsoft.com/en-us/azure/app-service/tutorial-sidecar-local-small-language-model) — MEDIUM.

---

### 3. Agent Skills Ecosystem (Cluster E)

**Confidence: HIGH** — Official agentskills.io spec fetched directly; Anthropic-authored specification.

**Specification facts (authoritative):**
- A skill = directory with `SKILL.md` at minimum. Optional: `scripts/`, `references/`, `assets/`.
- `SKILL.md` = YAML frontmatter + Markdown body.
- Required frontmatter: `name` (max 64 chars, lowercase alphanumeric + hyphens, no consecutive hyphens, matches directory name) and `description` (max 1024 chars, states what AND when to use).
- Optional frontmatter: `license`, `compatibility` (max 500 chars, environment requirements), `metadata` (key-value map for `author`, `version`, etc.), `allowed-tools` (experimental — space-delimited list of pre-approved tools).
- Progressive disclosure: metadata (~100 tokens) loaded at startup for all skills; full body loaded only when skill is activated.
- Integration: agent scans directories for SKILL.md files; injects metadata as XML into system prompt; activates skill by loading full body when task matches.
- Validation: `skills-ref validate ./my-skill` CLI from `github.com/agentskills/agentskills`.

**Ecosystem facts:**
- Standard published by Anthropic in December 2025; adopted by OpenAI, Gemini CLI, VS Code, Cursor, Junie, GitHub Copilot, and 25+ other agent products.
- 280,000+ skills publicly available (March 2026); SkillsMP at 66,541+ skills (January 2026).
- Discovery challenge: power-law distribution — handful of publishers (Microsoft, Vercel) dominate installs; most small publishers have near-zero adoption.
- Enterprise pattern: private internal registry for org-specific skills; curated catalog with admin promotion.

**Catalog/discovery patterns for enterprise:**
- Index-based discovery: registry hosts a JSON index file with skill name, description, author, version, compatibility per entry. Clients fetch the index, display in browse UI, pull individual skills on demand.
- Trust mechanisms: SecurityScanner is the Blitz equivalent of "verified publisher." Skills pass scanner → enter catalog. Skills fail → quarantine.
- Catalog UX: search (name/description), filter (category/status/author), sort (install count/date), detail view (SKILL.md rendered), one-click import.

**`allowed-tools` enforcement:** The spec defines this as experimental. Blitz's Gate 3 Tool ACL is the natural enforcement point — intersect skill's declared `allowed-tools` with user's ACL entries. If tool not in intersection: deny + audit log. This is an opportunity for Blitz to be the first platform to enforce this in production.

**Source confidence:** [agentskills.io/specification](https://agentskills.io/specification) — HIGH (official); [agentskills.io/integrate-skills](https://agentskills.io/integrate-skills) — HIGH (official); [PulseMCP post on OpenAI adoption](https://www.pulsemcp.com/posts/openai-agent-skills-anthropic-donates-mcp-gpt-5-2-image-1-5) — MEDIUM.

---

### 4. Navigation Rail UX (Cluster B)

**Confidence: MEDIUM** — Established HCI pattern; specific research for AI chat-first apps extrapolated from general SaaS patterns.

Key facts:
- Navigation rail = vertical column (typically 60–80px wide) with icon-only or icon+label items. Distinct from sidebar (wider, 200–300px, has text lists). Rail is appropriate for 600dp–1240dp screen widths; sidebar for wider.
- Supports 4–7 top-level destinations. More than 7 = overwhelming.
- Active item: filled icon + color highlight or background pill.
- Chat-first AI apps (ChatGPT, Claude, Gemini) use a combined pattern: narrow icon rail for top-level sections + wider conversation history sidebar for the chat section. The two are not mutually exclusive.
- 2026 trend: "context-aware menus" where sidebar/rail adapts to current route (shows conversation list in /chat, shows canvas tools in /canvas, shows admin tools in /admin).

For Blitz specifically:
- Rail items: Chat (message icon), Canvas (workflow icon), Admin (cog — admin role only, hidden for regular users), Profile (avatar/initials).
- In /chat route: rail + conversation history sidebar (already exists as part of CopilotKit chat).
- In /admin route: rail + admin tabs (already exists).
- Profile/logout accessible via profile icon in rail (dropdown or separate route).

**Source confidence:** [uinkits.com navigation rail guide](https://www.uinkits.com/blog-post/what-is-a-navigation-rail-and-how-to-use-it-in-ui-ux-design) — MEDIUM; [groovyweb AI UX trends 2026](https://www.groovyweb.co/blog/ui-ux-design-trends-ai-apps-2026) — LOW (marketing content, directionally correct).

---

### 5. Keycloak Runtime Configuration (Cluster D)

**Confidence: MEDIUM** — Official Keycloak docs confirm architecture; specific runtime-vs-build-time distinction confirmed.

Key facts:
- Keycloak distinguishes **build options** (require `kc.sh build` + restart: cache, DB vendor, feature flags) from **configuration options** (changeable via CLI or env vars without rebuild, but typically still require restart of the Keycloak process itself).
- **Admin REST API**: Fully supports runtime CRUD on realms, clients, identity providers, and mappers. `PUT /admin/realms/{realm}` updates realm settings immediately without Keycloak restart. `POST /admin/realms/{realm}/identity-provider/instances` creates identity provider at runtime.
- Keycloak's Admin REST API is the correct mechanism for "Keycloak configuration from the Blitz admin UI." Blitz's backend calls the Keycloak Admin REST API to update realm/client settings; the Keycloak server applies them immediately.
- **Limitation**: Some Keycloak settings (like switching DB vendor, enabling FIPS) are build-time and cannot be changed via Admin REST API. These are irrelevant to Blitz's use case (connecting Blitz to an existing Keycloak instance, not configuring Keycloak itself).

**What Blitz's "Keycloak runtime config" actually means:**
Not configuring Keycloak internals — instead: configuring **which Keycloak instance Blitz connects to** (URL, realm, client ID, client secret) at runtime via the admin UI, stored in the `platform_config` DB table, loaded dynamically by the backend without restart.

This is simpler than it sounds: it's a settings record in PostgreSQL that the `security/jwt.py` JWKS fetcher reads at request time instead of at startup from `.env`. The main complexity is encrypting the client secret and providing a "test connection" button.

**Source confidence:** [Keycloak all-config docs](https://www.keycloak.org/server/all-config) — HIGH (official); [Keycloak Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html) — HIGH (official); [Keycloak forum on OIDC client config](https://forum.keycloak.org/t/setting-the-oidc-clients-secret-using-the-admin-rest-api/28896/3) — MEDIUM.

---

## Competitor / Reference Feature Analysis

| Feature | ChatGPT / Claude / Gemini | Dify / n8n (enterprise) | Blitz v1.3 Approach |
|---------|--------------------------|------------------------|---------------------|
| Session management | HttpOnly cookie, silent refresh, logout | Varies by deployment | HttpOnly dual-issuer cookie; silent refresh; server-side proxy injects JWT |
| Navigation | Narrow icon rail + conversation sidebar | Horizontal tabs or left sidebar | Icon rail (4 items) + section-specific sidebars |
| LLM thinking mode | Claude: Extended Thinking toggle; Gemini: Deep Research | No user-level toggle | Per-user `thinking_mode` preference in DB, injected into system prompt |
| Embedding service | Cloud APIs (no local model) | Cloud or pluggable | bge-m3 sidecar; always local, never cloud; warm model in RAM |
| Identity provider config | SaaS — not configurable | Admin-configured in platform UI | Keycloak URL/realm/client via admin UI; stored encrypted in DB; no restart required |
| Skill catalog | Claude Code Skills Marketplace; SkillsMP | No built-in skill catalog | Internal catalog at /admin/skills/catalog with search/filter; external registry discovery |
| Skill security | Trust based on publisher reputation | No security scan | SecurityScanner (AST + dependency scan) + quarantine; `allowed-tools` enforcement (unique) |

---

## Sources

- [agentskills.io Specification (Official)](https://agentskills.io/specification) — HIGH confidence. Authoritative Agent Skills format spec.
- [agentskills.io Integrate Skills (Official)](https://agentskills.io/integrate-skills) — HIGH confidence. Integration pattern for agent platforms.
- [Next.js App Router Auth Guide 2026 (WorkOS)](https://workos.com/blog/nextjs-app-router-authentication-guide-2026) — MEDIUM-HIGH confidence. Covers middleware + DAL pattern.
- [CVE-2025-29927 Next.js Middleware Bypass](https://dev.to/nidal_tahir_cde5660ddbe04/how-i-built-a-secure-scalable-auth-system-in-nextjs-15-with-jwt-edge-middleware-and-drizzle-47ji) — MEDIUM confidence. CVE real, implementation details extrapolated.
- [Keycloak All-Config Reference (Official)](https://www.keycloak.org/server/all-config) — HIGH confidence. Build vs runtime config distinction.
- [Keycloak Admin REST API (Official)](https://www.keycloak.org/docs-api/latest/rest-api/index.html) — HIGH confidence. Realm/client/IDP management endpoints.
- [puppetm4st3r/baai_m3_simple_server (GitHub)](https://github.com/puppetm4st3r/baai_m3_simple_server) — MEDIUM confidence. Reference implementation for bge-m3 FastAPI sidecar.
- [Navigation Rail UX (uinkits.com)](https://www.uinkits.com/blog-post/what-is-a-navigation-rail-and-how-to-use-it-in-ui-ux-design) — MEDIUM confidence. HCI design pattern reference.
- [Agent Skills Ecosystem Scale Analysis (arXiv 2603.02176)](https://arxiv.org/html/2603.02176) — MEDIUM confidence. Ecosystem scale data and discovery challenges.
- [PulseMCP: OpenAI Adopts Agent Skills (2026)](https://www.pulsemcp.com/posts/openai-agent-skills-anthropic-donates-mcp-gpt-5-2-image-1-5) — MEDIUM confidence. Adoption timeline and ecosystem facts.
- [SkillsMP Marketplace Guide (SmartScope)](https://smartscope.blog/en/blog/skillsmp-marketplace-guide/) — LOW-MEDIUM confidence. Marketplace scale and discovery patterns.
- [AI UX Design Trends 2026 (Groovyweb)](https://www.groovyweb.co/blog/blog/ui-ux-design-trends-ai-apps-2026) — LOW confidence. Marketing content, directionally useful for nav patterns.

---
*Feature research for: Blitz AgentOS v1.3 Production Readiness & Skill Platform*
*Researched: 2026-03-05*
