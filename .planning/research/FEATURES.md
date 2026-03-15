# Feature Research: Blitz AgentOS v1.4 Platform Enhancement & Infrastructure

**Domain:** Enterprise Agentic OS -- 9 enhancement topics for existing platform
**Researched:** 2026-03-15
**Confidence:** HIGH (most features are well-understood enterprise patterns with existing codebase to extend)

---

## Context: What Is Already Built (v1.0-v1.3)

This file covers **only new features for v1.4**. Everything below assumes the following is shipped and working:

- Dual auth (Keycloak SSO + local bcrypt), 3-gate security (JWT/RBAC/ACL), Next.js middleware route protection
- Master agent with sub-agents, 3-tier memory, visual workflow canvas, HITL
- Multi-channel (Telegram live, WhatsApp/Teams code-complete)
- Admin dashboard with AI wizard, OpenAPI-to-MCP bridge, external skill repos, full skill ecosystem
- Embedding sidecar (bge-m3 warm process), Keycloak runtime config, navigation rail, user preferences
- Grafana + Loki + Alloy observability, Cloudflare Tunnel, session hardening (silent refresh, HttpOnly cookies)

---

## Feature Landscape by Topic

### Topic 1: Keycloak SSO Hardening (#07)

**Existing:** Keycloak integration works, `fetchWithRetry` for startup timing, basic error handling. Keycloak is optional (local-auth fallback via admin Identity tab).

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Circuit breaker (closed/open/half-open states) | Prevents cascading failure when Keycloak is down; standard resilience pattern per Microsoft/AWS guidance | MEDIUM | Existing `security/jwt.py` |
| Graceful degradation to local auth | Users must not be locked out when SSO is temporarily unavailable | LOW | Existing dual-issuer JWT |
| Health categorization (healthy/degraded/unavailable) | Admins need to know SSO state at a glance, not just "up/down" | LOW | Existing health endpoint |
| Configurable failure thresholds | Different environments have different tolerance; hardcoded thresholds break in practice | LOW | Circuit breaker impl |
| Structured error diagnostics | "Keycloak connection failed" is useless; need specifics (DNS, cert, timeout, 5xx) | LOW | Existing structlog |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Admin Identity tab health widget | Real-time SSO health visible in admin UI without checking logs | LOW | Extends existing Identity tab |
| Auto-recovery with exponential backoff | Half-open state probes at increasing intervals; avoids thundering herd on recovery | LOW | Part of circuit breaker |
| JWKS cache with TTL and forced refresh | Reduces Keycloak dependency for JWT validation; cache survives brief outages | LOW | Existing JWKS fetch |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automatic Keycloak restart/recovery | "Self-healing" sounds good | AgentOS should not manage Keycloak lifecycle; separation of concerns | Report health, let ops restart Keycloak |
| Multiple Keycloak failover instances | HA sounds essential | Over-engineering for 100 users; Keycloak has its own HA patterns | Circuit breaker + local-auth fallback is sufficient |

---

### Topic 2: Admin Registry Edit UI (#06)

**Existing:** Registry detail pages for skills; create wizard with AI-assisted forms. No edit capability for agents/tools/MCP servers.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Edit forms for all artifact types (agents, tools, MCP servers) | Admins created entries; they need to modify them without SQL/API calls | MEDIUM | Existing registry tables + API routes |
| Field validation matching create wizard | Same validation rules on edit as create; inconsistency causes data corruption | LOW | Existing Pydantic schemas |
| Version increment on edit | Audit trail of changes; existing system tracks versions | LOW | Existing `version` columns |
| Confirmation dialog before destructive edits | Accidental changes to production registries can break running agents | LOW | Frontend-only |
| MCP server connection test button | "Is this MCP server reachable?" is the first question after registration | MEDIUM | Existing `MCPClient` |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Inline JSON editor with syntax highlighting | MCP server configs and tool schemas are JSON; raw textarea is painful | LOW | Monaco editor or CodeMirror |
| Diff view on save (before/after) | Shows admin exactly what changed before committing | MEDIUM | Frontend diff library |
| MCP tool discovery from connection test | After confirming connection, auto-populate available tools list | MEDIUM | Extends MCPClient.list_tools() |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Bulk edit across multiple entries | Efficiency for large registries | 100-user scale means small registries; bulk edit introduces complex merge/conflict UX | Single-entry edit is sufficient |
| Undo/redo history for edits | Familiar from text editors | Versioning already provides rollback; undo/redo adds state complexity | "Revert to previous version" button |

---

### Topic 3: Scheduler UI & Management APIs (#15)

**Existing:** Celery + Redis, `workflow_triggers` table (cron/webhook), `workflow_runs` table. No management UI.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Global scheduler dashboard (list all jobs) | Admins need to see what is scheduled, by whom, and when | MEDIUM | Existing `workflow_triggers` |
| Visual cron expression builder | Cron syntax is error-prone; `0 9 * * 1-5` is not human-readable. Cronicle-style multi-selector is the proven pattern | MEDIUM | Frontend component |
| Execution history with status (success/fail/running) | "Did my 9am digest run? Did it succeed?" -- core operational question | MEDIUM | Existing `workflow_runs` |
| Manual trigger ("run now" button) | Testing scheduled jobs without waiting for the cron tick | LOW | Existing Celery task dispatch |
| Enable/disable toggle per job | Pause a job without deleting it; essential for debugging | LOW | `is_active` field on triggers |
| Timezone display on all timestamps | Cron in UTC but user thinks in local time; must show both | LOW | Frontend timezone conversion |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Next-run preview (show next 5 execution times) | Validates cron expression before saving; prevents "why didn't it run at 9am?" | LOW | `croniter` library in Python |
| Execution log viewer (live tail) | See job output in real time without SSH-ing into the server | MEDIUM | Stream from Celery task logs |
| Failure alerting configuration per job | Critical jobs need notifications on failure; non-critical don't | MEDIUM | Extends existing notification system |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Drag-and-drop job ordering/priority | Visual scheduling feels intuitive | Cron jobs don't have ordering; this confuses the mental model | Show next-run timeline instead |
| Calendar view of all scheduled jobs | Looks pretty in demos | Calendar becomes unreadable with overlapping jobs; list view is more practical | Sortable table with next-run column |
| Natural language cron input ("every weekday at 9am") | User-friendly | LLM parsing adds latency and ambiguity; visual builder is faster and deterministic | Visual multi-selector widget |

---

### Topic 4: Runtime Permission Approval HITL (#01)

**Existing:** 3-gate security (JWT -> RBAC -> Tool ACL), binary allow/deny in `tool_acl`, HITL in workflows. No temporal permissions or approval queues.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Permission request queue (pending approvals) | When agent needs a tool the user lacks access to, it must request, not silently fail. This is the standard HITL pattern per Microsoft, Permit.io, Oracle | MEDIUM | Existing `tool_acl` + new `permission_requests` table |
| Admin approval/deny UI | Queue is useless without a UI to process it | MEDIUM | Existing admin dashboard |
| Temporal ACL (time-limited permissions) | "Approve for 1 hour" is safer than permanent grants; standard enterprise IAM pattern | MEDIUM | `expires_at` column on `tool_acl` |
| Notification on approval/denial | Requesting user must know the outcome to continue their work | LOW | In-app notification (not email yet) |
| Audit trail for all permission decisions | Compliance requirement; who approved what, when, for how long | LOW | Existing audit logging |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-approve rules (tool X for role Y) | Reduces admin burden for routine requests; common in enterprise IAM (Permit.io pattern) | MEDIUM | New `auto_approve_rules` table |
| Agent-initiated permission escalation | Agent detects "access denied", automatically creates request and notifies user it's waiting | MEDIUM | Extends agent error handling in master_agent |
| Bulk approve/deny for batch requests | Admin processing efficiency when multiple users request same tool | LOW | UI convenience on approval queue |
| Permission request expiry | Stale requests auto-close after configurable period | LOW | Celery periodic task |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Self-approval by requesting user | Reduces friction | Defeats the purpose of approval gates; security anti-pattern | Auto-approve rules for low-risk tools instead |
| Cascading permissions (approve tool -> auto-approve all sub-tools) | Convenience | Hidden permission expansion; violates least-privilege principle | Explicit per-tool approval |
| Real-time chat-based approval flow | Feels natural in agent context | Mixes security decisions with casual chat; approval should be deliberate UI action | Dedicated approval UI with clear context |

---

### Topic 5: Multi-Agent Tab Architecture (#16)

**Existing:** Single CopilotKit instance (`blitz_master`), artifact wizard at `/admin/create`. CopilotKit v0.1.78 installed.

**IMPORTANT:** CopilotKit v1.50 (December 2025) added `useAgent` hook for multi-agent support. Current version 0.1.78 requires major upgrade to enable this feature. Verify compatibility before committing to this approach.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Tabbed chat interface (multiple conversations) | Users expect browser-tab-like experience; single chat is limiting | HIGH | CopilotKit `useAgent` hook (requires v1.50+), frontend state management |
| Independent agent state per tab | Switching tabs must not lose context or mix agent states | HIGH | Multiple agent sessions or CopilotKit instances |
| Tab persistence across page navigation | Opening a tab, navigating away, and returning should restore state | MEDIUM | Session storage or backend persistence |
| Specialized builder agents (tool_builder, mcp_builder) | Different artifact types need different expertise; one-size-fits-all agent is suboptimal | HIGH | New agent definitions, LangGraph graphs, tool ACL per agent |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Agent handoff between tabs | Master agent can delegate to specialized builder agent in a new tab | HIGH | Cross-agent communication protocol |
| Tab type indicators (chat vs builder vs workflow) | Visual distinction between conversation types helps navigation | LOW | Tab icon/color per agent type |
| Builder agent with artifact-specific tool access | tool_builder has code generation tools; mcp_builder has OpenAPI parsing tools | MEDIUM | Tool ACL per agent type |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Unlimited simultaneous tabs | "More is better" | Each tab holds a CopilotKit instance + LangGraph session; memory/resource explosion at 100 users | Cap at 5-8 tabs with clear "close oldest" UX |
| Cross-tab agent collaboration | Agents in different tabs working together | Massively complex state synchronization; v1.4 scope explosion | Sequential handoff (tab A produces artifact, tab B uses it) |
| Drag-and-drop tab reordering | Familiar from browsers | Engineering effort disproportionate to value | Fixed tab order by creation time |

---

### Topic 6: User Experience Enhancement (#13)

**Existing:** Light theme only, basic profile page (v1.3), LLM preferences, navigation rail. No avatar upload, no timezone management.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Dark theme with system preference detection | Every modern web app supports dark mode; `next-themes` is the standard library (no flash, SSR-safe) | MEDIUM | `next-themes` + CSS variables + Tailwind `dark:` |
| Theme toggle in UI (not just system preference) | Users want explicit control over light/dark | LOW | `next-themes` built-in |
| Theme persistence across sessions | Theme must survive page reload and re-login | LOW | localStorage via `next-themes` (automatic) |
| Timezone display on all timestamps | Scheduled jobs, audit logs, execution history must show in user's timezone | MEDIUM | Backend stores UTC; frontend converts; `timezone` field in user profile |
| Avatar upload with preview | Profile feels incomplete without a photo; table stakes for user-facing platforms | MEDIUM | File upload + storage (MinIO or local filesystem) |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| No-flash theme loading (SSR-safe) | Avoids white flash on dark theme page load; polished UX signal | LOW | `next-themes` handles via script injection before hydration |
| Avatar in navigation rail and chat messages | Personalization across the UI, not just profile page | LOW | Render from profile data |
| Timezone-aware cron display | Scheduler shows "9:00 AM your time (01:00 UTC)" | LOW | Combines with Scheduler UI (#15) |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Custom accent colors / full theme customization | Personalization | Exponential testing matrix; two themes (light/dark) cover 99% of needs | Light + dark only |
| Animated theme transitions | Polished feel | CSS transition glitches across component libraries; `next-themes` docs recommend disabling transitions during switch | Instant swap |
| Profile background images / cover photos | Social media expectations | Enterprise tool, not social media; adds storage and rendering complexity | Avatar only |

---

### Topic 7: Unified Dashboard (#08+#14)

**Existing:** Admin hub at `/admin`, Grafana at `:3001`, Prometheus metrics, Loki logs. No user-facing operational dashboard or in-app analytics.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Mission Control: active agents, running workflows, pending approvals | "What is happening right now?" is the first question when opening the app. OpenClaw Mission Control, Splunk SOC dashboard set this expectation | HIGH | WebSocket or SSE for real-time; queries across multiple tables |
| Analytics: usage metrics (conversations, tool calls, tokens consumed) | "How much are we using this?" is the first management question | MEDIUM | Aggregation queries or materialized views |
| Real-time activity feed | Live updates without manual refresh; standard for operational dashboards | MEDIUM | WebSocket from FastAPI (built-in support) |
| Time-range selector (today/week/month/custom) | Analytics without time filtering is unusable | LOW | Frontend date picker + API query params |
| Role-based dashboard views | Admins see system-wide metrics; users see their own | MEDIUM | Existing RBAC |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tremor React charts (bar, line, area) | Production-quality charts with Tailwind integration; acquired by Vercel (Jan 2025), now fully free/OSS, 16K+ GitHub stars, 300K+ monthly downloads | MEDIUM | `@tremor/react` npm package |
| Quick actions from dashboard (run workflow, open chat) | Dashboard as command center, not just display | LOW | Links/buttons to existing pages |
| LLM cost tracking widget | Token spend visibility for budget management; data already exists in LiteLLM cost API | MEDIUM | Query LiteLLM `/spend/logs` endpoint |
| Deep-link to Grafana for technical metrics | Avoid duplicating Grafana's role; link to pre-built dashboards for deep dives | LOW | URL construction with time range params |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Custom dashboard builder (drag-and-drop widgets) | Flexibility | Massive engineering effort for 100 users; Grafana already does this | Fixed layout with role-based views |
| Embedded Grafana iframes | Reuse existing dashboards | CORS issues, auth token forwarding, iframe sizing problems, mixed-content security | Deep-link to Grafana in new tab |
| Real-time log streaming in dashboard | Convenient for debugging | Duplicates Grafana/Loki; log volume overwhelms browser | Link to Loki/Grafana for log exploration |
| Per-user customizable metric cards | Personalization | 100 users, each with custom dashboard state = maintenance burden | Standard dashboard with role-based sections |

---

### Topic 8: Storage Service (#19)

**Existing:** No file storage system. Files only exist as embeddings in pgvector. Avatar upload (Topic 6) and future file attachments need storage.

**IMPORTANT -- MinIO Status (Dec 2025):** MinIO Community Edition entered maintenance mode. No new features, no active PR review, admin UI features stripped from Community Edition. However, existing functionality remains fully operational and the S3 API implementation is complete. For 100 users on Docker Compose, MinIO's current feature set is more than sufficient. Implement a provider adapter pattern for future migration flexibility.

**Alternatives if MinIO deteriorates further:** Garage (Rust, AGPL, CNCF sandbox candidate), RustFS (Apache 2.0, 2.3x faster on small objects), SeaweedFS (Go, Apache 2.0). All S3-compatible.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| S3-compatible object storage deployment | Standard interface; all libraries and tools speak S3 | MEDIUM | Docker Compose service (MinIO) |
| File upload API (multipart) | Agents and users need to store files (avatars, attachments, exports) | MEDIUM | Backend routes + `boto3` / `aioboto3` client |
| File metadata in PostgreSQL | Track ownership, type, size, timestamps in DB; actual bytes in object store | MEDIUM | New `files` table |
| Per-user file isolation | Same principle as memory isolation; users must not access each other's files | LOW | `WHERE user_id = $1` on file queries (existing pattern) |
| Presigned URLs for downloads | Avoid proxying large files through backend; standard S3 pattern | LOW | S3 client presigned URL generation |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Provider adapter pattern (StorageProvider interface) | Switch storage backends (MinIO -> Garage -> AWS S3) without code changes; critical given MinIO uncertainty | MEDIUM | Abstract interface with MinIO implementation |
| File-memory linking | Associate uploaded files with memory facts for context retrieval | MEDIUM | `memory_file_links` join table |
| Automatic thumbnail generation for images | Better UX for avatar and image previews | LOW | PIL/Pillow in Celery worker |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full file manager UI (folders, tree view, drag-drop) | Familiar from Google Drive / Dropbox | v1.4 scope explosion; storage service is infrastructure, not a product feature | API-only + avatar upload UI; file manager deferred to Projects/Spaces (#20) |
| File versioning | "Never lose a version" | Object storage versioning adds complexity; at 100-user scale, simple overwrite is fine | Upload creates new file; keep previous via soft delete |
| File sharing with external users | Collaboration feature | On-premise, internal-only platform; no external access by design | Internal sharing only (per-user isolation + admin access) |

---

### Topic 9: Email System & Notifications (#18)

**Existing:** Email agent returns mock data. `channel_accounts` table exists. ChannelAdapter protocol in place. No email sidecar, no OAuth for Google/Microsoft.

**CRITICAL CONTEXT:** Google disabled Basic Authentication on March 14, 2025. Microsoft enforces OAuth-only by April 2026. IMAP with password auth is dead for major email providers. OAuth 2.0 with XOAUTH2 SASL is the only path forward.

#### Table Stakes

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Email sidecar service (IMAP/SMTP with OAuth) | Isolate email protocol handling from main backend; standard microservice pattern | HIGH | New Docker Compose service (port 8003) |
| OAuth 2.0 for Google (Gmail API or XOAUTH2 IMAP) | Only way to access Google email programmatically post-March 2025 | HIGH | Google Cloud Console OAuth client, consent screen setup |
| OAuth 2.0 for Microsoft (Graph API or XOAUTH2 IMAP) | Only way to access Microsoft email programmatically post-April 2026 | HIGH | Azure AD app registration |
| Email fetch, send, reply as agent tools | Core agent capability; email is the #1 enterprise communication channel | MEDIUM | Email sidecar + existing tool registry |
| Notification routing (in-app + email + channel) | System events (approval requests, job failures) need configurable delivery | MEDIUM | Router service choosing delivery channel per user preference |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| User preference for notification channels | "Approvals via email, job failures via Telegram" -- per-event-type routing | MEDIUM | `notification_preferences` table |
| Email thread summarization | Agent reads email thread and produces summary; core AI value prop | LOW | Existing LLM + prompt; just needs real email data |
| Unified inbox across Google + Microsoft | Single view regardless of email provider; reduces context-switching | HIGH | Normalization layer in email sidecar |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full email client in AgentOS | "Replace Gmail/Outlook" | Massive scope; email clients have decades of UX refinement; AgentOS is not an email client | Agent-assisted email: fetch, summarize, draft, send -- not browse/search/manage |
| Email push notifications via IMAP IDLE | Real-time email arrival | IMAP IDLE connections are fragile, consume resources, complicate deployment | Polling interval (every 5 min) is sufficient for 100 users |
| Custom SMTP relay for outbound | "Send from our domain" | SMTP relay setup, DKIM/SPF/DMARC configuration is ops burden | Send via provider API (Gmail API / Graph API) which handles deliverability |

---

## Cross-Topic Feature Dependencies

```
Storage Service (#19)
    |-- required by --> Avatar Upload (UX #13)
    |-- required by --> File Attachments (Email #18, future)
    |-- required by --> Skill ZIP Storage (future optimization)

Keycloak SSO Hardening (#07)
    |-- foundation for --> All auth-dependent features
    |-- no blockers (extends existing)

Admin Registry Edit UI (#06)
    |-- no blockers (extends existing registry)
    |-- enhances --> MCP connection testing

Scheduler UI (#15)
    |-- enhanced by --> Timezone management (UX #13) for display
    |-- no hard blockers

Permission Approval HITL (#01)
    |-- extends --> Existing 3-gate security
    |-- enhances --> Multi-Agent Tab (#16) -- builder agents can request tool access
    |-- feeds --> Unified Dashboard (#08+#14) -- pending approval count widget

Multi-Agent Tab Architecture (#16)
    |-- depends on --> CopilotKit upgrade to v1.50+ (useAgent hook)
    |-- enhanced by --> Permission Approval (#01) -- builder agents need specific tools

UX Enhancement (#13) -- Dark Theme
    |-- no blockers for theme / timezone
    |-- Avatar upload depends on --> Storage Service (#19) OR local filesystem workaround

Unified Dashboard (#08+#14)
    |-- depends on --> WebSocket infrastructure (new to codebase)
    |-- enhanced by --> Scheduler UI (#15) data (running jobs widget)
    |-- enhanced by --> Permission Approval (#01) data (pending count widget)

Email System (#18)
    |-- extends --> Existing ChannelAdapter pattern
    |-- requires --> External OAuth setup (Google Cloud Console, Azure AD) -- manual with approval delays
    |-- enhanced by --> Storage Service (#19) for attachments (future)
    |-- enhanced by --> Notification routing for system events
```

### Dependency Notes

- **Storage Service (#19) is a soft dependency for Avatar Upload (#13):** Avatar can use local filesystem initially, but MinIO is the proper solution. Build storage early if avatar is wanted, or accept local-fs as workaround.
- **Multi-Agent Tab (#16) requires CopilotKit v1.50+ upgrade:** Current version is 0.1.78. This is a major version jump. Compatibility with existing `LangGraphAGUIAgent`, venv patches, and `runtime.py` must be verified. HIGH RISK.
- **Email System (#18) requires external service registration:** Google Cloud Console and Azure AD app registration are manual processes with potential approval delays. Start registration early even if implementation comes later.
- **Unified Dashboard (#08+#14) needs WebSocket infrastructure:** FastAPI has built-in WebSocket support, but this is new to the codebase. Design endpoint structure and connection management.

---

## Priority Recommendation for v1.4

### Foundation Phase (build first -- low risk, high impact)

| Feature | User Value | Impl Cost | Priority | Rationale |
|---------|------------|-----------|----------|-----------|
| Keycloak SSO Hardening (#07) | HIGH | LOW | P1 | Production resilience; small scope, high impact; no dependencies |
| Admin Registry Edit UI (#06) | HIGH | LOW | P1 | Quick win; unblocks admin daily workflow; straightforward CRUD |
| Storage Service (#19) | MEDIUM | MEDIUM | P1 | Infrastructure dependency for avatar upload and future features |
| Scheduler UI (#15) | HIGH | MEDIUM | P1 | Backend exists, just needs UI; high visibility to users |

### Enhancement Phase (build second)

| Feature | User Value | Impl Cost | Priority | Rationale |
|---------|------------|-----------|----------|-----------|
| UX Enhancement (#13) | HIGH | MEDIUM | P1 | High user satisfaction per effort; dark theme is visible quality signal |
| Permission Approval HITL (#01) | HIGH | MEDIUM | P1 | Fills security capability gap; extends existing 3-gate system cleanly |
| Unified Dashboard (#08+#14) | HIGH | HIGH | P2 | Needs new WebSocket infrastructure + multiple data source integration |

### Infrastructure Phase (build third or carry to v1.5)

| Feature | User Value | Impl Cost | Priority | Rationale |
|---------|------------|-----------|----------|-----------|
| Multi-Agent Tab Architecture (#16) | MEDIUM | HIGH | P2 | CopilotKit major upgrade risk; highest complexity of all 9 topics |
| Email System & Notifications (#18) | HIGH | HIGH | P2 | External OAuth dependencies (registration delays); complex sidecar service |

---

## Sources

- [Circuit Breaker Pattern - Microsoft Azure](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [Circuit Breaker Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/circuit-breaker.html)
- [HITL for AI Agents - Permit.io](https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo)
- [HITL Architecture - Agent Patterns](https://www.agentpatterns.tech/en/architecture/human-in-the-loop-architecture)
- [Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [MinIO Maintenance Mode - InfoQ (Dec 2025)](https://www.infoq.com/news/2025/12/minio-s3-api-alternatives/)
- [MinIO Alternatives - DEV Community](https://dev.to/arash_ezazy_f69fb13acdd37/minio-alternatives-open-source-on-prem-real-world-credible-seaweedfs-garage-rustfs-and-ceph-36om)
- [next-themes - GitHub](https://github.com/pacocoursey/next-themes)
- [Tremor React Components](https://www.tremor.so/)
- [Vercel acquires Tremor (Jan 2025)](https://vercel.com/blog/vercel-acquires-tremor)
- [CopilotKit v1.50 Release](https://www.copilotkit.ai/blog/copilotkit-v1-50-release-announcement-whats-new-for-agentic-ui-builders)
- [Cronicle Scheduler](https://github.com/jhuckaby/Cronicle)
- [Microsoft OAuth for IMAP](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth)
- [Google OAuth IMAP (XOAUTH2)](https://developers.google.com/gmail/imap/xoauth2-protocol)
- [Google Basic Auth Sunset (March 2025)](https://support.google.com/a/answer/14114704)
- [Mission Control - Builderz Labs](https://github.com/builderz-labs/mission-control)
- [SSO Best Practices 2026 - Zluri](https://www.zluri.com/blog/sso-best-practices)

---
*Feature research for: Blitz AgentOS v1.4 Platform Enhancement & Infrastructure*
*Researched: 2026-03-15*
