# Roadmap: Blitz AgentOS

## Milestones

- [x] **v1.0 MVP** - Phases 1-3.1 (shipped 2026-02-26)
- [x] **v1.1 Enterprise Platform** - Phases 4-10 (shipped 2026-03-02)
- [x] **v1.2 Developer Experience** - Phases 11-14 (shipped 2026-03-04)
- [x] **v1.3 Production Readiness & Skill Platform** - Phases 15-25 (shipped 2026-03-14)
- [ ] **v1.4 Platform Enhancement & Infrastructure** - Phases 26-35 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-3.1) - SHIPPED 2026-02-26</summary>

- [x] **Phase 1: Identity and Infrastructure Skeleton** - 4/4 plans (completed 2026-02-24)
- [x] **Phase 2: Agent Core and Conversational Chat** - 5/5 plans (completed 2026-02-25)
- [x] **Phase 2.1: Tech Debt Cleanup** (INSERTED) - 1/1 plan (completed 2026-02-26)
- [x] **Phase 3: Sub-Agents, Memory, and Integrations** - 6/6 plans (completed 2026-02-26)
- [x] **Phase 3.1: Memory Read Path & MCP Hot-Registration** (INSERTED) - 1/1 plan (completed 2026-02-26)

Full phase details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>v1.1 Enterprise Platform (Phases 4-10) - SHIPPED 2026-03-02</summary>

- [x] **Phase 4: Canvas and Workflows** - 5/5 plans (completed 2026-02-27)
- [x] **Phase 4.1: Phase 4 Polish** (INSERTED) - 1/1 plan (completed 2026-02-27)
- [x] **Phase 5: Scheduler and Channels** - 6/6 plans (completed 2026-02-28)
- [x] **Phase 5.1: Workflow Execution Wiring** (INSERTED) - 1/1 plan (completed 2026-02-28)
- [x] **Phase 6: Extensibility Registries** - 8/8 plans (completed 2026-03-01)
- [x] **Phase 7: Hardening and Sandboxing** - 4/4 plans (completed 2026-03-01)
- [x] **Phase 8: Observability** - 4/4 plans (completed 2026-03-01)
- [x] **Phase 9: Tech Debt Code Fixes** (INSERTED) - 2/2 plans (completed 2026-03-01)
- [x] **Phase 10: Optional Tech Debt Closure** (INSERTED) - 2/2 plans (completed 2026-03-02)

Full phase details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>v1.2 Developer Experience (Phases 11-14) - SHIPPED 2026-03-04</summary>

- [x] **Phase 11: Infrastructure & Debt** - 2/2 plans (completed 2026-03-02)
- [x] **Phase 12: Unified Admin Desk** - 2/2 plans (completed 2026-03-03)
- [x] **Phase 13: Local Auth** - 2/2 plans (completed 2026-03-03)
- [x] **Phase 14: Ecosystem Capabilities** - 5/5 plans (completed 2026-03-04)

Full phase details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>v1.3 Production Readiness & Skill Platform (Phases 15-25) - SHIPPED 2026-03-14</summary>

- [x] **Phase 15: Session & Auth Hardening** - 3/3 plans (completed 2026-03-05)
- [x] **Phase 16: Navigation & User Experience** - 3/3 plans (completed 2026-03-05)
- [x] **Phase 17: Performance & Embedding Sidecar** - 7/7 plans (completed 2026-03-05)
- [x] **Phase 18: Identity Configuration** - 3/3 plans (completed 2026-03-06)
- [x] **Phase 19: Skill Platform A - Standards** - 1/1 plans (completed 2026-03-07)
- [x] **Phase 20: Skill Platform B - Catalog** - 6/6 plans (completed 2026-03-08)
- [x] **Phase 21: Skill Platform C - Security** - 4/4 plans (completed 2026-03-08)
- [x] **Phase 22: Skill Platform D - Sharing** - 3/3 plans (completed 2026-03-08)
- [x] **Phase 23: Skill Platform E - Builder** - 4/4 plans (completed 2026-03-10)
- [x] **Phase 24: Unified Registry & MCP Platform** - 7/7 plans (completed 2026-03-12)
- [x] **Phase 25: Skill Builder Tool Resolver** - 6/6 plans (completed 2026-03-13)

Full phase details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

### v1.4 Platform Enhancement & Infrastructure

**Milestone Goal:** Harden production resilience, add admin management UIs for existing backend capabilities, introduce file storage and email notification infrastructure, and unify operational visibility into a single dashboard.

- [x] **Phase 26: Keycloak SSO Hardening** - Production-grade SSO resilience with circuit breaker, health diagnostics, and graceful degradation (completed 2026-03-15)
- [ ] **Phase 27: Admin Registry Edit UI** - Form-based editing for all 4 registry types with MCP connection testing
- [ ] **Phase 28: Storage Service** - MinIO-backed file storage with per-user folders, sharing, and memory integration
- [ ] **Phase 29: User Experience Enhancement** - Dark theme, avatar upload, timezone management, and notification preferences
- [ ] **Phase 30: Scheduler Management** - Global scheduler dashboard with visual cron builder, execution history, and queue monitoring
- [ ] **Phase 31: Permission Approval HITL** - Runtime permission requests with admin approval, auto-approve rules, and temporal ACL
- [ ] **Phase 32: Multi-Agent Builder & Tech Debt** - Tabbed artifact builder with specialized agents and builder metadata fix
- [ ] **Phase 33: Email System & OAuth Integration** - Email sidecar with OAuth, bi-directional email channel, and notification routing
- [ ] **Phase 34: Dashboard & Mission Control** - Unified operations dashboard with real-time activity feed and system health
- [ ] **Phase 35: Analytics & Observability** - Usage, performance, cost, agent, and security analytics with materialized views

## Phase Details

### Phase 26: Keycloak SSO Hardening
**Goal**: SSO failures never cascade into user-facing outages; admins have full visibility into SSO health
**Depends on**: Nothing (foundation work, independent)
**Requirements**: KC-01, KC-02, KC-03, KC-04, KC-05, KC-06, KC-07
**Success Criteria** (what must be TRUE):
  1. Admin can view categorized SSO health status (certificate/config/unreachable/timeout) from the admin panel
  2. Admin can test Keycloak configuration (DNS, TLS, OIDC discovery, client auth) before saving changes
  3. When Keycloak is down, users see a friendly error and the SSO button hides; login falls back to local auth seamlessly
  4. Circuit breaker stops cascading SSO failures after 5 consecutive errors and auto-recovers after 60s
  5. Admin receives in-app notification when SSO transitions to unhealthy
**Plans**: 2 plans

Plans:
- [ ] 26-01-PLAN.md — Backend: circuit breaker, SSO health checker, admin notifications, API endpoints
- [ ] 26-02-PLAN.md — Frontend: health panel, login degradation, notification bell

### Phase 27: Admin Registry Edit UI
**Goal**: Admins can edit any registered artifact (agent, tool, MCP server, skill) through structured forms instead of raw JSON
**Depends on**: Nothing (independent admin UI work)
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05, REG-06
**Success Criteria** (what must be TRUE):
  1. Each of the 4 registry types has a detail page with consistent layout and form-based editing
  2. Type-specific config fields are editable (agent system prompt, tool handler, MCP URL/auth, skill instructions)
  3. Admin can test MCP server connection from the detail page and see success/failure result
  4. All list pages have dual pagination (top + bottom) and form validation shows inline Zod errors
**Plans**: TBD

Plans:
- [ ] 27-01: TBD
- [ ] 27-02: TBD

### Phase 28: Storage Service
**Goal**: Users have personal file storage with upload, download, sharing, and memory integration
**Depends on**: Nothing (new infrastructure, independent)
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04, STOR-05, STOR-06
**Success Criteria** (what must be TRUE):
  1. MinIO runs as a Docker Compose service with S3-compatible API accessible from backend
  2. User can upload files, organize them in virtual folders, and download via presigned URLs
  3. User can share files with other users at READ/WRITE/ADMIN permission levels
  4. User can add files to long-term memory; re-embedding triggers automatically on file update
  5. File manager UI supports grid/list view, folder tree, breadcrumb navigation, and search
**Plans**: TBD

Plans:
- [ ] 28-01: TBD
- [ ] 28-02: TBD
- [ ] 28-03: TBD

### Phase 29: User Experience Enhancement
**Goal**: Users can personalize their visual experience and time display; notification preferences are configurable
**Depends on**: Phase 28 (UX-04 avatar upload requires MinIO from STOR-01)
**Requirements**: UX-01, UX-02, UX-03, UX-04, UX-05, UX-06, UX-07
**Success Criteria** (what must be TRUE):
  1. User can switch between 3 built-in themes (Light, Dark, Navy Blue) with instant CSS variable switching
  2. User can pick from 6 curated color presets or enter custom hex with WCAG contrast validation; theme persists across sessions
  3. User can upload an avatar that is cropped/resized to 3 sizes and stored in MinIO
  4. User can set their timezone; all UI timestamps display in user timezone; admin can set system-wide default
  5. User can configure notification preferences per channel (email, in-app, Telegram) per event type
**Plans**: TBD

Plans:
- [ ] 29-01: TBD
- [ ] 29-02: TBD
- [ ] 29-03: TBD

### Phase 30: Scheduler Management
**Goal**: Admins and users can view, manage, and monitor all scheduled jobs from a dedicated UI
**Depends on**: Nothing (builds on existing Celery scheduler backend from v1.1)
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, SCHED-06, SCHED-07, SCHED-08
**Success Criteria** (what must be TRUE):
  1. Global scheduler dashboard lists all scheduled jobs with filtering; admin can enable/disable jobs with one click
  2. User can trigger "Run Now" on any scheduled job they own
  3. Execution history page shows past runs with status filtering, drill-down details, and retry capability
  4. Queue monitoring page shows Celery queue depth, worker status, and auto-refreshes
  5. Visual cron builder with presets, day toggles, timezone picker, and next-runs preview is usable for creating/editing schedules
**Plans**: TBD

Plans:
- [ ] 30-01: TBD
- [ ] 30-02: TBD
- [ ] 30-03: TBD

### Phase 31: Permission Approval HITL
**Goal**: Permission denials become approval requests instead of hard failures; admins can approve with temporal scope
**Depends on**: Nothing (extends existing RBAC/ACL infrastructure)
**Requirements**: PERM-01, PERM-02, PERM-03, PERM-04, PERM-05, PERM-06, PERM-07
**Success Criteria** (what must be TRUE):
  1. When a tool call is denied by ACL, execution pauses (HITL) instead of returning 403
  2. Admin sees pending permission requests via bell icon notification and can approve with duration (session/72h/permanent/custom)
  3. Approval creates a persistent ToolAcl entry and auto-resumes the paused execution
  4. Auto-approve rule engine evaluates configurable conditions before creating a request
  5. Configurable timeout with escalation path (24h default, then manager, then it-admin, then expire)
**Plans**: TBD

Plans:
- [ ] 31-01: TBD
- [ ] 31-02: TBD
- [ ] 31-03: TBD

### Phase 32: Multi-Agent Builder & Tech Debt
**Goal**: Artifact builder supports specialized agents per artifact type; builder metadata gaps from v1.3 are closed
**Depends on**: Phase 27 (registry edit UI provides foundation for artifact detail pages)
**Requirements**: TABS-01, TABS-02, TABS-03, TABS-04, TABS-05, CARRY-02
**Success Criteria** (what must be TRUE):
  1. Builder supports tab-switching between skill, tool, and MCP builder agents with isolated CopilotKit contexts
  2. Dedicated tool_builder and mcp_builder agents generate type-specific forms and artifacts
  3. Parent skill tab shows dependency status and notifies when child tool/MCP artifacts complete
  4. Builder fill_form correctly populates allowed_tools, category, and tags in artifact draft (v1.3 tech debt resolved)
**Plans**: TBD

Plans:
- [ ] 32-01: TBD
- [ ] 32-02: TBD

### Phase 33: Email System & OAuth Integration
**Goal**: Users can send/receive email through the agent; real OAuth replaces mock sub-agents; notifications route to preferred channels
**Depends on**: Phase 28 (email attachments may use storage service)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, CARRY-01
**Success Criteria** (what must be TRUE):
  1. Email sidecar service connects to Gmail and Microsoft 365 via OAuth 2.0 (IMAP/SMTP)
  2. User can send and receive emails through agent chat (bi-directional email channel)
  3. Real OAuth email/calendar integration replaces mock sub-agents with live Google/Microsoft data
  4. Centralized NotificationService routes notifications to user-preferred channels with 8 event types
  5. Admin can configure system SMTP settings and email templates; user can link email from profile page
**Plans**: TBD

Plans:
- [ ] 33-01: TBD
- [ ] 33-02: TBD
- [ ] 33-03: TBD

### Phase 34: Dashboard & Mission Control
**Goal**: Admins have a unified operations dashboard showing system health, activity, and management controls
**Depends on**: Phases 26-31 (dashboard surfaces data from scheduler, permissions, agents, workflows)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. Dashboard overview shows system health metrics, alert banner, and real-time activity feed via WebSocket/SSE
  2. Flow execution monitor lists workflow runs with step-by-step drill-down and retry capability
  3. Agents page shows all agents with status indicators and management actions
  4. Memory browser supports both full-text and semantic (pgvector) search with content viewer
**Plans**: TBD

Plans:
- [ ] 34-01: TBD
- [ ] 34-02: TBD
- [ ] 34-03: TBD

### Phase 35: Analytics & Observability
**Goal**: Operational and business metrics are visualized with historical trends and anomaly detection
**Depends on**: Phase 34 (shares dashboard infrastructure and navigation)
**Requirements**: ANLYT-01, ANLYT-02, ANLYT-03, ANLYT-04, ANLYT-05, ANLYT-06
**Success Criteria** (what must be TRUE):
  1. Usage analytics page shows DAU/MAU charts, feature adoption, and session duration
  2. Performance analytics page shows API latency percentiles, error rates, and resource utilization
  3. Cost analytics page shows LLM spend trends with model breakdown and budget tracking
  4. Agent effectiveness and security analytics pages show success rates, error patterns, login anomalies
  5. PostgreSQL materialized views refresh every 15 min via Celery for historical data aggregation
**Plans**: TBD

Plans:
- [ ] 35-01: TBD
- [ ] 35-02: TBD
- [ ] 35-03: TBD

## Progress

**Execution Order:** 26 -> 27 -> 28 -> 29 -> 30 -> 31 -> 32 -> 33 -> 34 -> 35

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Identity & Skeleton | v1.0 | 4/4 | Complete | 2026-02-24 |
| 2. Agent Core & Chat | v1.0 | 5/5 | Complete | 2026-02-25 |
| 2.1. Tech Debt Cleanup | v1.0 | 1/1 | Complete | 2026-02-26 |
| 3. Sub-Agents & Memory | v1.0 | 6/6 | Complete | 2026-02-26 |
| 3.1. Memory Read + MCP Hot-Reg | v1.0 | 1/1 | Complete | 2026-02-26 |
| 4. Canvas & Workflows | v1.1 | 5/5 | Complete | 2026-02-27 |
| 4.1. Phase 4 Polish | v1.1 | 1/1 | Complete | 2026-02-27 |
| 5. Scheduler & Channels | v1.1 | 6/6 | Complete | 2026-02-28 |
| 5.1. Workflow Execution Wiring | v1.1 | 1/1 | Complete | 2026-02-28 |
| 6. Extensibility Registries | v1.1 | 8/8 | Complete | 2026-03-01 |
| 7. Hardening & Sandboxing | v1.1 | 4/4 | Complete | 2026-03-01 |
| 8. Observability | v1.1 | 4/4 | Complete | 2026-03-01 |
| 9. Tech Debt Code Fixes | v1.1 | 2/2 | Complete | 2026-03-01 |
| 10. Optional Tech Debt Closure | v1.1 | 2/2 | Complete | 2026-03-02 |
| 11. Infrastructure & Debt | v1.2 | 2/2 | Complete | 2026-03-02 |
| 12. Unified Admin Desk | v1.2 | 2/2 | Complete | 2026-03-03 |
| 13. Local Auth | v1.2 | 2/2 | Complete | 2026-03-03 |
| 14. Ecosystem Capabilities | v1.2 | 5/5 | Complete | 2026-03-04 |
| 15. Session & Auth Hardening | v1.3 | 3/3 | Complete | 2026-03-05 |
| 16. Navigation & UX | v1.3 | 3/3 | Complete | 2026-03-05 |
| 17. Performance & Embedding Sidecar | v1.3 | 7/7 | Complete | 2026-03-05 |
| 18. Identity Configuration | v1.3 | 3/3 | Complete | 2026-03-06 |
| 19. Skill Platform A - Standards | v1.3 | 1/1 | Complete | 2026-03-07 |
| 20. Skill Platform B - Catalog | v1.3 | 6/6 | Complete | 2026-03-08 |
| 21. Skill Platform C - Security | v1.3 | 4/4 | Complete | 2026-03-08 |
| 22. Skill Platform D - Sharing | v1.3 | 3/3 | Complete | 2026-03-08 |
| 23. Skill Platform E - Builder | v1.3 | 4/4 | Complete | 2026-03-10 |
| 24. Unified Registry & MCP Platform | v1.3 | 7/7 | Complete | 2026-03-12 |
| 25. Skill Builder Tool Resolver | v1.3 | 6/6 | Complete | 2026-03-13 |
| 26. Keycloak SSO Hardening | 2/2 | Complete   | 2026-03-15 | - |
| 27. Admin Registry Edit UI | v1.4 | 0/TBD | Not started | - |
| 28. Storage Service | v1.4 | 0/TBD | Not started | - |
| 29. User Experience Enhancement | v1.4 | 0/TBD | Not started | - |
| 30. Scheduler Management | v1.4 | 0/TBD | Not started | - |
| 31. Permission Approval HITL | v1.4 | 0/TBD | Not started | - |
| 32. Multi-Agent Builder & Tech Debt | v1.4 | 0/TBD | Not started | - |
| 33. Email System & OAuth Integration | v1.4 | 0/TBD | Not started | - |
| 34. Dashboard & Mission Control | v1.4 | 0/TBD | Not started | - |
| 35. Analytics & Observability | v1.4 | 0/TBD | Not started | - |
