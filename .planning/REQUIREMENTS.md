# Requirements: Blitz AgentOS

**Defined:** 2026-03-15
**Core Value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.

## v1.4 Requirements

Requirements for v1.4 Platform Enhancement & Infrastructure. Each maps to roadmap phases.

### Keycloak SSO Hardening

- [ ] **KC-01**: Admin can view SSO health status with categorized diagnostics (certificate/config/unreachable/timeout)
- [ ] **KC-02**: Admin can test Keycloak configuration before saving (DNS, TLS, OIDC discovery, client auth)
- [ ] **KC-03**: Login page shows friendly error messages instead of "Server error — Configuration"
- [ ] **KC-04**: SSO failures gracefully fall back to local auth with helpful message
- [ ] **KC-05**: SSO button hides dynamically when Keycloak is unhealthy
- [ ] **KC-06**: Circuit breaker prevents cascade of failed SSO auth attempts (5 failures → open → 60s half-open)
- [ ] **KC-07**: Admin receives in-app notification when SSO goes down

### Admin Registry Edit UI

- [ ] **REG-01**: All 4 registry types (agents, tools, MCP servers, skills) have detail pages with consistent layout
- [ ] **REG-02**: All detail pages support form-based editing (not just JSON)
- [ ] **REG-03**: Type-specific config fields editable (agent: system prompt/tools; tool: handler/permissions; MCP: URL/auth; skill: instructions/procedure)
- [ ] **REG-04**: MCP servers have connection test functionality
- [ ] **REG-05**: All list pages have dual pagination (top + bottom)
- [ ] **REG-06**: Form validation shows inline errors with Zod schemas

### Scheduler UI & Management

- [ ] **SCHED-01**: Global scheduler dashboard at `/scheduler` lists all scheduled jobs with filtering
- [ ] **SCHED-02**: Admin can enable/disable scheduled jobs with one click
- [ ] **SCHED-03**: User can manually trigger "Run Now" on any scheduled job
- [ ] **SCHED-04**: Execution history page with drill-down details, status filtering, retry
- [ ] **SCHED-05**: Queue monitoring page shows Celery queue depth, worker status, auto-refresh
- [ ] **SCHED-06**: Per-workflow schedule tab manages triggers for specific workflows
- [ ] **SCHED-07**: Visual cron builder with presets, day toggles, timezone picker, and next-runs preview
- [ ] **SCHED-08**: Job failure notifications via in-app, Telegram, and email channels

### Runtime Permission Approval HITL

- [ ] **PERM-01**: Permission denial triggers HITL pause instead of hard 403 failure
- [ ] **PERM-02**: Admin sees pending permission requests via bell icon notification
- [ ] **PERM-03**: Admin can approve with duration options (session/72h/permanent/custom)
- [ ] **PERM-04**: Approval creates persistent ToolAcl entry and auto-resumes execution
- [ ] **PERM-05**: Auto-approve rule engine evaluates configurable conditions before creating request
- [ ] **PERM-06**: Admin UI for rule builder with visual conditions and test mode
- [ ] **PERM-07**: Configurable timeout with escalation path (24h → manager → it-admin → expire)

### Multi-Agent Tab Architecture

- [ ] **TABS-01**: Artifact builder supports tab-switching between skill, tool, and MCP builder agents
- [ ] **TABS-02**: Each tab runs isolated CopilotKit agent with clean context
- [ ] **TABS-03**: Database-backed dependency tracking between parent and child artifacts
- [ ] **TABS-04**: Dedicated tool_builder and mcp_builder agents with type-specific forms
- [ ] **TABS-05**: Parent skill tab shows dependency status and notifies on child completion

### User Experience Enhancement

- [ ] **UX-01**: 3 built-in themes work (Light, Dark, Navy Blue) with instant CSS variable switching
- [ ] **UX-02**: 6 curated color presets + custom hex input with WCAG contrast validation
- [ ] **UX-03**: Theme persists across sessions (localStorage + database sync)
- [ ] **UX-04**: Avatar upload with crop/resize generates 3 sizes (40px, 120px, 400px) stored in MinIO
- [ ] **UX-05**: User can set timezone with searchable dropdown; all UI timestamps display in user timezone
- [ ] **UX-06**: System-wide timezone configurable by admin; new users inherit admin default
- [ ] **UX-07**: Notification settings per channel (email, in-app, Telegram) per event type

### Dashboard & Mission Control

- [ ] **DASH-01**: Dashboard overview page shows system health metrics, alert banner, and real-time activity feed
- [ ] **DASH-02**: Activity feed updates in real-time via WebSocket/SSE
- [ ] **DASH-03**: Flow execution monitor lists workflow runs with step-by-step drill-down and retry
- [ ] **DASH-04**: Agents page shows all agents with status indicators and management actions
- [ ] **DASH-05**: Memory browser supports full-text and semantic (pgvector) search with content viewer

### Analytics & Observability

- [ ] **ANLYT-01**: Usage analytics page with DAU/MAU charts, feature adoption, session duration
- [ ] **ANLYT-02**: Performance analytics page with API latency percentiles, error rates, resource utilization
- [ ] **ANLYT-03**: Cost analytics page with LLM spend trends, model breakdown, budget tracking
- [ ] **ANLYT-04**: Agent effectiveness page with success rates, completion times, error patterns
- [ ] **ANLYT-05**: Security analytics page with login patterns, permission changes, anomaly detection
- [ ] **ANLYT-06**: PostgreSQL materialized views refreshed every 15 min via Celery for historical data

### Storage Service

- [ ] **STOR-01**: MinIO deployed as Docker Compose service with S3-compatible API
- [ ] **STOR-02**: Per-user personal storage with virtual folder hierarchy (database-backed)
- [ ] **STOR-03**: File upload/download with presigned URLs, metadata storage, SHA-256 deduplication
- [ ] **STOR-04**: File sharing between users with READ/WRITE/ADMIN permissions
- [ ] **STOR-05**: Memory integration — add files to long-term memory with auto re-embedding on update
- [ ] **STOR-06**: File manager UI with grid/list view, folder tree, breadcrumb navigation, search

### Email System & Notifications

- [ ] **EMAIL-01**: Email sidecar service with IMAP/SMTP support and OAuth 2.0 for Gmail/Microsoft 365
- [ ] **EMAIL-02**: User can send and receive emails via agent chat (bi-directional email channel)
- [ ] **EMAIL-03**: Centralized NotificationService routes notifications to user-preferred channels
- [ ] **EMAIL-04**: 8 notification types with per-user, per-type channel preferences
- [ ] **EMAIL-05**: Admin configures system SMTP settings and email templates
- [ ] **EMAIL-06**: User email account management with "Link Email" from profile page

### Carried Forward

- [ ] **CARRY-01**: Real OAuth email/calendar integration replaces mock sub-agents with live Google/Microsoft OAuth
- [ ] **CARRY-02**: Builder fill_form populates allowed_tools, category, and tags in artifact draft

## Future Requirements

### v1.5+

- **CHAN-03**: WhatsApp Business live end-to-end (pending Meta Business API verification)
- **CHAN-04**: MS Teams live end-to-end (pending Azure Bot Service registration)

### v1.6+ Architecture

- **#20**: Projects & Spaces — workspace isolation, team collaboration
- **#09**: Multi-Agent Orchestration — runtime agent coordination
- **#12**: Advanced User & Group Management — LDAP sync, delegation
- **#05**: Universal Skill Import — Claude Code, Cursor, Windsurf format import
- **#04**: Admin Console LLM Config — full LLM model/provider management UI

### v1.7+ Architecture

- **#21**: Universal Integration Framework
- **#22**: MCP Server Creation Skill
- **#23**: Plugin Templates
- **#24**: Third-Party Apps UI

## Out of Scope

| Feature | Reason |
|---------|--------|
| SaaS/cloud hosting | Enterprise on-premise requirement |
| Kubernetes | Docker Compose only for MVP; K8s is post-MVP |
| HashiCorp Vault | AES-256 DB encryption sufficient at ~100 user scale |
| Separate vector database | pgvector in PostgreSQL is sufficient |
| Mobile native apps | Web-first; mobile apps are post-MVP |
| Real-time collaborative workflow editing | Single-user canvas for MVP |
| OAuth social login | Keycloak SSO + local auth is sufficient |
| 3D office visualization | Defer to post-v1.4 (nice-to-have in DASH spec) |
| Job dependency chains/DAGs | Scheduler v2 feature |
| ML-based permission suggestions | Permission HITL v2 feature |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| KC-01 | Pending | Pending |
| KC-02 | Pending | Pending |
| KC-03 | Pending | Pending |
| KC-04 | Pending | Pending |
| KC-05 | Pending | Pending |
| KC-06 | Pending | Pending |
| KC-07 | Pending | Pending |
| REG-01 | Pending | Pending |
| REG-02 | Pending | Pending |
| REG-03 | Pending | Pending |
| REG-04 | Pending | Pending |
| REG-05 | Pending | Pending |
| REG-06 | Pending | Pending |
| SCHED-01 | Pending | Pending |
| SCHED-02 | Pending | Pending |
| SCHED-03 | Pending | Pending |
| SCHED-04 | Pending | Pending |
| SCHED-05 | Pending | Pending |
| SCHED-06 | Pending | Pending |
| SCHED-07 | Pending | Pending |
| SCHED-08 | Pending | Pending |
| PERM-01 | Pending | Pending |
| PERM-02 | Pending | Pending |
| PERM-03 | Pending | Pending |
| PERM-04 | Pending | Pending |
| PERM-05 | Pending | Pending |
| PERM-06 | Pending | Pending |
| PERM-07 | Pending | Pending |
| TABS-01 | Pending | Pending |
| TABS-02 | Pending | Pending |
| TABS-03 | Pending | Pending |
| TABS-04 | Pending | Pending |
| TABS-05 | Pending | Pending |
| UX-01 | Pending | Pending |
| UX-02 | Pending | Pending |
| UX-03 | Pending | Pending |
| UX-04 | Pending | Pending |
| UX-05 | Pending | Pending |
| UX-06 | Pending | Pending |
| UX-07 | Pending | Pending |
| DASH-01 | Pending | Pending |
| DASH-02 | Pending | Pending |
| DASH-03 | Pending | Pending |
| DASH-04 | Pending | Pending |
| DASH-05 | Pending | Pending |
| ANLYT-01 | Pending | Pending |
| ANLYT-02 | Pending | Pending |
| ANLYT-03 | Pending | Pending |
| ANLYT-04 | Pending | Pending |
| ANLYT-05 | Pending | Pending |
| ANLYT-06 | Pending | Pending |
| STOR-01 | Pending | Pending |
| STOR-02 | Pending | Pending |
| STOR-03 | Pending | Pending |
| STOR-04 | Pending | Pending |
| STOR-05 | Pending | Pending |
| STOR-06 | Pending | Pending |
| EMAIL-01 | Pending | Pending |
| EMAIL-02 | Pending | Pending |
| EMAIL-03 | Pending | Pending |
| EMAIL-04 | Pending | Pending |
| EMAIL-05 | Pending | Pending |
| EMAIL-06 | Pending | Pending |
| CARRY-01 | Pending | Pending |
| CARRY-02 | Pending | Pending |

**Coverage:**
- v1.4 requirements: 63 total
- Mapped to phases: 0
- Unmapped: 63 ⚠️

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-15 after initial definition*
