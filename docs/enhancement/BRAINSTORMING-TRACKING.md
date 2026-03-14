# Brainstorming Tracking Document

**Project:** Blitz AgentOS  
**Milestone:** v1.4 Planning  
**Created:** 2026-03-14  
**Last Updated:** 2026-03-16  

---

## 🔄 SESSION HANDOVER

### Previous Session: 2026-03-14

**Session Status:** ✅ COMPLETED  
**Total Topics Completed:** 3  

**Topics:**
1. Runtime Permission Approval (HITL) ✅
2. Admin Registry Edit UI ✅  
3. Advanced User & Group Management ✅

---

### Session: 2026-03-15

**Session Status:** ✅ COMPLETED  
**Total Topics Completed This Session:** 1  

**Topic:** User Experience Enhancement (#13) — Added to pending

---

### Session 1: 2026-03-16 (Morning)

**Session Status:** ✅ COMPLETED  
**Total Topics Completed This Session:** 1  

**Topic #14: AgentOS Dashboard & Mission Control** ✅
- Comprehensive operational dashboard for agent visibility
- Real-time activity feed with WebSocket updates
- Flow execution monitor with step-by-step drill-down
- Agent management with optional 3D office visualization
- Memory browser with full-text and semantic search
- Analysis of 3 reference repositories (OpenClaw Dashboard variants)
- Deep integration with Phase 8 observability infrastructure
- **Design Doc:** `docs/enhancement/agentos-dashboard-mission-control/00-specification.md`

---

### Session 2: 2026-03-16 (Afternoon)

**Session Status:** ✅ COMPLETED - Ready for next session  
**Total Topics Completed This Session:** 1  

**Topic #15: Scheduler Engine & UI** ✅

---

### Session 3: 2026-03-16 (Evening)

**Session Status:** ✅ COMPLETED - Ready for next session  
**Total Topics Completed This Session:** 1  

**Topic #8: Analytics & Observability Dashboard** ✅
- Comprehensive analytics and observability system
- Dual-mode architecture: Grafana UI + Embedded Next.js panels
- Six analytics categories: Usage, Performance, Costs, Agents, Security, Overview
- Hybrid query strategy: Materialized views for history + Direct queries for real-time
- 6-week implementation timeline (1 Phase)
- Consistent with Topic #14 Dashboard architecture
- **Design Doc:** `docs/enhancement/analytics-observability-dashboard/00-specification.md`
- Comprehensive scheduler management interface
- Global scheduler view for operations (/scheduler)
- Per-workflow schedule tab for user management
- Full interactive cron builder with timezone and holiday support
- Real-time queue monitoring for Celery
- Multi-channel alerting (in-app, Telegram, email)
- Execution history with drill-down and retry capability
- Extends existing Celery infrastructure (no replacement)
- **Design Doc:** `docs/enhancement/scheduler-engine-ui/00-specification.md`

### 🎯 Key Decisions Made (Recent Sessions)

| Topic | Critical Decisions |
|-------|-------------------|
| **Dashboard** | Integrated approach in Next.js; Backend API aggregation; WebSocket for real-time; Leverages Phase 8 observability |
| **Scheduler** | Celery-centric approach (extend, don't replace); Dual UI (global + per-workflow); Full visual cron builder; Multi-channel alerting |
| **LLM Config** | Sidecar architecture with BaseModule; HTTP communication with circuit breaker; CLI execution + custom hooks; Zero-downtime module updates |
| **Architecture** | Generic module pattern reusable for Security Scanner, Analytics, and future features |
| **Scale Path** | Start with Docker Compose sidecars; migrate to Kubernetes Deployments with HPA |
| **Analytics** | Dual-mode (Grafana + Embedded); Hybrid query strategy (materialized views + direct); 6 analytics categories; Tremor React for charts |
| **UX Enhancement** | CSS Variables theming (Tailwind v4); MinIO avatar storage; Dual timezone (system + user); 3 themes + color customization |

### 🔄 Architecture Evolution

**New Patterns Introduced:**
- **BaseModule Framework:** Abstract class for all AgentOS modules
- **Module Sidecars:** Independent services in Docker Compose/K8s
- **Resilient Communication:** Circuit breaker + retry patterns
- **Dashboard Aggregation:** Unified API layer for multiple data sources
- **Scheduler Management:** Extend Celery with management API and UI
- **Hybrid Analytics Query:** Materialized views for history + Direct queries for real-time
- **Dual-Mode Visualization:** Grafana for ops + Embedded panels for users

**Impact on Future Topics:**
- Security Scan Module can use same BaseModule pattern
- Analytics Module fits sidecar architecture
- All future modules follow consistent pattern
- Dashboard and Scheduler provide operational foundation
- Analytics patterns reusable for future reporting features

### 📊 Current Status

**Completed ✅ (8):**
- #1 Runtime Permission Approval (HITL)
- #4 Admin Console LLM Configuration
- #6 Admin Registry Edit UI
- #8 Analytics & Observability Dashboard
- #12 Advanced User & Group Management
- #13 User Experience Enhancement
- #14 AgentOS Dashboard & Mission Control
- #15 Scheduler Engine & UI

**Pending 🟡 (4):**
- #2 WhatsApp Business API Integration (Medium)
- #5 GitHub Repository Skill Sources (Medium)
- #7 Keycloak SSO Hardening (High) ⭐ **RECOMMENDED NEXT**
- #9 HashiCorp Vault Integration (Low)
- #10 Multi-Agent Orchestration (Low)

### 🚀 Recommended Next Steps

**For Next Session:**

**Option A: Continue Brainstorming**
- Topic #7: Keycloak SSO Hardening (Critical stability fix) ⭐ **RECOMMENDED**
- Topic #5: GitHub Repository Skill Sources (Quick win)
- Topic #13: User Experience Enhancement (UI polish)

**Option B: Start Implementation**
- Create PLAN.md files for completed topics
- Begin Phase 1 implementation of any completed topic
- Review designs with stakeholders before coding

**Option C: Add New Topics**
- Brainstorm additional v1.4 features
- Refine existing designs based on feedback

### 📁 Files Modified This Session

- `docs/enhancement/agentos-dashboard-mission-control/00-specification.md` (NEW)
- `docs/enhancement/scheduler-engine-ui/00-specification.md` (NEW)
- `docs/enhancement/analytics-observability-dashboard/00-specification.md` (NEW)
- `docs/enhancement/user-experience-enhancement/00-specification.md` (NEW)
- `docs/enhancement/BRAINSTORMING-TRACKING.md` (UPDATED)
- `docs/enhancement/README.md` (UPDATED)

### ⚠️ Context to Preserve

**Architecture Decisions to Remember:**
1. **Permission Model:** Moving from role-based to direct group permissions
2. **External Identity:** Global Groups (read-only) map to Local Groups (permission-bearing)
3. **HITL:** Permission-based approval (`system:admin`) not role-based
4. **Registry UI:** Inline edit mode preferred over separate pages
5. **Module Architecture:** Sidecar pattern with BaseModule abstract class
6. **Module Communication:** HTTP with circuit breaker and retry patterns
7. **Scale Path:** Docker Compose → Swarm → Kubernetes for 100 to 5,000 users
8. **Dashboard:** Integrated in Next.js; API aggregation layer; WebSocket real-time updates
9. **Scheduler:** Extend existing Celery (don't replace); Dual UI (global + per-workflow); Full visual cron builder
10. **Analytics:** Dual-mode (Grafana UI + Embedded panels); Hybrid query (materialized views + direct); Tremor React charts
11. **UX Theming:** CSS Variables with Tailwind v4; MinIO for avatars; Dual timezone (system + user)

**Technical Debt Notes:**
- Old `local_group_roles` table to be deprecated in favor of `group_permissions`
- Migration strategy defined for User/Group topic
- SWR build issue superseded by comprehensive Admin Registry UI
- BaseModule framework to be built in Phase 1 of LLM Config implementation
- Security Scanner module can reuse BaseModule pattern once established
- Dashboard leverages Phase 8 observability (Prometheus, Loki, Grafana)
- Scheduler extends existing Celery infrastructure (no migration needed)
- Analytics materialized views need concurrent refresh monitoring
- Grafana dashboards need version control (JSON export/import)
- MinIO service needs to be added to docker-compose.yml for avatar storage
- Theme CSS variables need to be applied to all existing components

**Open Questions for Future:**
- Keycloak SSO error handling specifics (for Topic #7)
- WhatsApp Business verification timeline (for Topic #2)
- Module versioning and compatibility strategy
- Circuit breaker tuning parameters
- Dashboard 3D visualization performance optimization
- Scheduler holiday exclusion data source

---

*Next session: Continue with any pending topic or begin implementation planning.*

---

## Overview

This document tracks all brainstorming topics for v1.4 and beyond. Each topic moves through stages:

```
🟡 PENDING → 🔵 IN-PROGRESS → ✅ COMPLETED → 📋 PLANNED → 🚀 IMPLEMENTED
```

**Legend:**
- 🟡 **PENDING**: Topic identified, awaiting discussion
- 🔵 **IN-PROGRESS**: Currently being brainstormed
- ✅ **COMPLETED**: Brainstorming done, design document written
- 📋 **PLANNED**: Implementation planned (PLAN.md created)
- 🚀 **IMPLEMENTED**: Feature shipped

---

## Quick Status Summary

| # | Topic | Status | Priority | Target | Est. Effort |
|---|-------|--------|----------|--------|-------------|
| 1 | Runtime Permission Approval (HITL) | ✅ COMPLETED | High | v1.4 | 1 Phase |
| 2 | WhatsApp Business API Integration | 🟡 PENDING | Medium | v1.4 | 1 Phase |
| 3 | HashiCorp Vault Integration | 🟡 PENDING | Low | Post-MVP | 1 Phase |
| 4 | Admin Console LLM Configuration | ✅ COMPLETED | High | v1.4 | 0.5 Phase |
| 5 | GitHub Repository Skill Sources | 🟡 PENDING | Medium | v1.4 | 0.5 Phase |
| 6 | Admin Registry Edit UI (expanded from SWR) | ✅ COMPLETED | High | v1.4 | 0.5-1 Phase |
| 7 | Keycloak SSO Hardening | 🟡 PENDING | High | v1.4 | 0.5 Phase |
| 8 | Analytics & Observability Dashboard | ✅ COMPLETED | Medium | v1.4 | 1 Phase |
| 9 | Multi-Agent Orchestration | 🟡 PENDING | Low | v1.5 | 2 Phases |
| 12 | Advanced User & Group Management | ✅ COMPLETED | High | v1.4 | 1 Phase |
| 13 | User Experience Enhancement | ✅ COMPLETED | Medium | v1.4 | 1 Phase |
| 14 | AgentOS Dashboard & Mission Control | ✅ COMPLETED | High | v1.4 | 1.5 Phases |
| 15 | Scheduler Engine & UI | ✅ COMPLETED | High | v1.4 | 1 Phase |

---

## Completed Topics

### 8. Analytics & Observability Dashboard

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-16  
**Design Doc:** [docs/enhancement/analytics-observability-dashboard/00-specification.md](./analytics-observability-dashboard/00-specification.md)  

#### Problem Statement
No visibility into usage trends, performance metrics, costs, or security auditing. Ad-hoc database queries required for any analysis.

#### Target State (To-Be)
- Comprehensive analytics with 6 categories: Usage, Performance, Costs, Agents, Security, Overview
- Dual-mode architecture: Standalone Grafana (port 3001) + Embedded panels in Next.js
- Hybrid query strategy: Materialized views for history, direct queries for real-time
- Time-range filtering (24h, 7d, 30d, 90d, custom)
- Export capabilities (CSV/PDF)

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Architecture** | No analytics | Dual-mode (Grafana + Embedded) | Serves both ops teams and end users |
| **Query Strategy** | Direct queries only | Hybrid (matviews + direct) | Performance for history, freshness for recent |
| **Chart Library** | None | Tremor React | Pre-built analytics components, matches design system |
| **Data Sources** | Separate systems | Unified aggregation layer | Single API for all analytics |
| **Access Control** | Grafana only | JWT + RBAC in embedded views | Consistent with AgentOS security model |

#### Technical Approach
- PostgreSQL materialized views refreshed every 15 minutes (concurrently)
- Celery job for view refresh scheduling
- `AnalyticsService` class for data aggregation from Prometheus, Loki, PostgreSQL
- Grafana HTTP API for embedded panel data
- Tremor React components for charts
- Redis caching (30s TTL) for real-time queries

#### Analytics Categories

1. **Usage Analytics** - DAU/MAU, feature adoption, session duration, retention
2. **Performance Analytics** - API latency (p50/p95/p99), error rates, resource utilization
3. **Cost Analytics** - Token usage, spend by model/user, budget tracking
4. **Agent Effectiveness** - Success rates, completion times, error breakdowns
5. **Security & Audit** - Login patterns, permission changes, anomalies
6. **Overview** - Key metrics summary, trends, recent alerts

#### Success Criteria
- [ ] All 6 analytics pages accessible at `/admin/analytics/*`
- [ ] Overview page loads in < 3 seconds
- [ ] Materialized views refresh every 15 minutes
- [ ] Time range filtering works (24h, 7d, 30d, 90d, custom)
- [ ] Grafana accessible at port 3001
- [ ] Export to CSV works for all tables

#### Estimated Effort
1 Phase (6 weeks)

---

### 13. User Experience Enhancement (UI Theme + User Profile)

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-16  
**Design Doc:** [docs/enhancement/user-experience-enhancement/00-specification.md](./user-experience-enhancement/00-specification.md)  

#### Problem Statement
Single light theme with no customization; no user avatars; no personal profiles; UTC-only timestamps causing confusion for international users.

#### Target State (To-Be)
- 3 built-in themes (Light, Dark, Navy Blue) with smooth transitions
- Color customization: 6 curated presets + custom hex input
- Avatar upload with crop/resize, stored in MinIO
- Full user profile: display name, bio, preferences, notifications
- Dual-level timezone: System-wide (admin) + per-user

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Theming Approach** | Light only | 3 themes + custom colors | User personalization, accessibility |
| **Color System** | Fixed blue | CSS Variables (Tailwind v4) | Zero JS overhead, instant switching |
| **Avatar Storage** | None | MinIO (S3-compatible) | Scalable, aligns with storage system vision |
| **Timezone** | UTC only | System + User timezones | Global team support |
| **Customization** | None | Presets + Hex input | Balance ease-of-use with flexibility |

#### Technical Approach
- CSS Variables architecture using Tailwind v4's native support
- MinIO service in docker-compose for avatar storage
- Three avatar sizes generated: 40x40, 120x120, 400x400
- `date-fns-tz` for reliable timezone conversion
- localStorage for instant theme, database for persistence

#### Features

**Theme System:**
- Light, Dark, Navy Blue themes
- 6 curated color presets (Ocean Blue, Forest Green, Royal Purple, Sunset Orange, Ruby Red, Teal Wave)
- Custom hex color input with WCAG validation
- System preference detection
- Smooth 0.3s CSS transitions

**User Profile:**
- Avatar upload with crop/resize
- Display name (editable, separate from Keycloak)
- Bio/description (500 character limit)
- Contact preferences
- Profile visibility (Public/Organization/Private)

**Preferences:**
- Theme selection
- Color customization
- Timezone (searchable dropdown)
- Date format (MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD)

**Notifications:**
- Email toggles (weekly digest, failures, security)
- In-app toggles (features, mentions, completions)
- Channel toggles (Telegram, WhatsApp)

#### Success Criteria
- [ ] 3 themes work with smooth transitions
- [ ] Color customization with presets and hex input
- [ ] Avatar upload with crop/resize
- [ ] Display name and bio editable
- [ ] Timezone selection works
- [ ] Notification settings affect actual delivery
- [ ] Settings persist across sessions

#### Estimated Effort
1 Phase (6 weeks)

---

### 15. Scheduler Engine & UI

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-16  
**Design Doc:** [docs/enhancement/scheduler-engine-ui/00-specification.md](./scheduler-engine-ui/00-specification.md)  

#### Problem Statement
Existing Celery-based scheduling has no UI for visualization or management. Users cannot see scheduled jobs, monitor queue status, or configure schedules visually.

#### Target State (To-Be)
- Global scheduler view at /scheduler for operations
- Per-workflow schedule tab for user management
- Visual cron builder with timezone and holiday support
- Real-time queue monitoring for Celery
- Multi-channel alerting (in-app, Telegram, email)
- Execution history with filtering and drill-down

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Approach** | Celery only | Extend Celery with UI | Lower risk, leverages existing infrastructure |
| **Interface** | None | Dual UI (global + per-workflow) | Serves both ops and end users |
| **Cron Builder** | Text input | Visual interactive builder | User-friendly, reduces errors |
| **Monitoring** | CLI only | Real-time queue dashboard | Operational visibility |

#### Technical Approach
- Extend existing Celery infrastructure (no replacement)
- Backend API aggregation layer for job data
- Global scheduler view for operations team
- Per-workflow schedule tab integrated in workflow UI
- Interactive cron builder with live preview
- Redis Pub/Sub for real-time queue updates
- Multi-channel alert routing based on user preferences

#### Features

**Global Scheduler View:**
- All scheduled jobs list with filtering
- Job status indicators
- Enable/disable toggles
- Manual trigger ("Run Now")

**Per-Workflow Scheduling:**
- Schedule tab in workflow editor
- Cron expression builder
- Timezone selection
- Holiday exclusion rules

**Queue Monitoring:**
- Real-time Celery queue depth
- Worker status
- Task processing rates
- Failed task count

**Execution History:**
- Job run logs
- Success/failure status
- Duration tracking
- Retry functionality

#### Success Criteria
- [ ] Global scheduler view at /scheduler
- [ ] Per-workflow schedule tab functional
- [ ] Visual cron builder with preview
- [ ] Real-time queue monitoring
- [ ] Multi-channel alerting working
- [ ] Execution history with drill-down
- [ ] RBAC enforced throughout

#### Estimated Effort
1 Phase (5 weeks)

---

### 1. Runtime Permission Approval (HITL)

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-14  
**Design Doc:** [docs/enhancement/runtime-permission-approval/00-specification.md](./runtime-permission-approval/00-specification.md)  

#### Problem Statement
Currently, when a skill/workflow attempts to use a tool the user lacks permission for, the tool call fails immediately with a 403 error, causing workflows to die and leaving users stuck with no escalation path.

#### Current State (As-Is)
- Gate 3 (`check_tool_acl()`) returns binary True/False
- False = hard deny, execution fails
- User must stop workflow → contact admin → wait → restart
- No runtime path to gain permissions

#### Target State (To-Be)
- Gate 3 emits `PermissionPendingException` instead of hard deny
- Execution pauses using LangGraph interrupt
- Admin notified via UI (bell icon/badge) with rich context
- One-click approval creates persistent ACL entry with expiration
- Execution resumes automatically after approval

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Duration** | N/A (no runtime approval) | Session / Time-limited / Permanent | Different use cases need different lifetimes |
| **Approver** | Role-based (`it-admin`) | Permission-based (`system:admin`) | Works with local auth (no Keycloak dependency) |
| **Context** | None | Full context (user, tool, trigger, risk) | Informed decision-making |
| **Auto-approve** | No | Rule engine with conditions | Reduce admin burden |
| **Timeout** | N/A | Configurable, default 72h, escalation | Ensure requests get attention |

#### Technical Approach
- New tables: `permission_requests`, `auto_approve_rules`
- Extend `tool_acl` with expiration columns
- Celery jobs for timeout/escalation
- WebSocket/SSE for real-time notifications
- LangGraph interrupt integration

#### Success Criteria
- [ ] Permission denial triggers HITL pause
- [ ] Admin notification within 5 seconds
- [ ] One-click approval creates persistent ACL
- [ ] Auto-resume after approval
- [ ] Works in local auth mode

#### Estimated Effort
1 Phase (5-6 plans)

---

### 2. Admin Registry Edit UI (Topic #6 Expanded)

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-14  
**Design Doc:** [docs/enhancement/admin-registry-edit-ui/00-specification.md](./admin-registry-edit-ui/00-specification.md)  
**Original Topic:** Frontend Build Optimization (SWR) — Scope expanded to full Admin UI feature  

#### Problem Statement
Admin registry pages (agents, tools, MCP servers) lack detail pages and form-based editing. Skills page shows raw JSON only. No way to test MCP server connections before saving. Inconsistent UX across registry types.

#### Current State (As-Is)
- **Skills**: Detail page exists but shows JSON only, no form editing
- **Agents**: List view only, no detail page, no editing
- **Tools**: List view only, no detail page, no editing
- **MCP Servers**: List view only, no detail page, no editing
- **Pagination**: Only at bottom of lists

#### Target State (To-Be)
- **All registry types** have detail pages with consistent layout
- **Form-based editing** for all configuration (not JSON-only)
- **Name/slug is immutable** (display name editable)
- **Test functionality** for MCP servers (connection test)
- **Dual pagination** at top AND bottom of lists
- **Consistent navigation** with back links

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Name editable** | N/A | ❌ No (immutable) | Name is identifier, changing breaks references |
| **Display fields** | Raw JSON | ✅ Form fields | User-friendly, reduces errors |
| **Edit mode** | N/A | Inline toggle | Simple UX, no page navigation |
| **Test functionality** | None | MCP connection test | Prevent misconfiguration |
| **Bulk edit** | N/A | ❌ Not supported | Adds complexity, individual edits are safer |
| **Pagination** | Bottom only | Top + Bottom | Better UX for long lists |

#### Field Priority (Phased)

**Phase 1 (Core):**
- Display Name, Description, Status (all types)

**Phase 2 (Type-Specific):**
- **Agents**: System prompt, allowed tools, memory config
- **Tools**: Handler type, required permissions, sandbox flag
- **MCP Servers**: URL, transport, auth, health check
- **Skills**: Instructions/procedure, required tools

**Phase 3 (Advanced):**
- Metadata, icons, documentation links

#### Technical Approach
- Create `[id]/page.tsx` for agents, tools, mcp-servers
- Enhance existing skills detail page with forms
- Shared components: `RegistryDetailLayout`, `RegistryEditForm`
- Type-specific form components for config fields
- Backend test endpoint: `POST /api/admin/mcp-servers/{id}/test`

#### Success Criteria
- [ ] All 4 registry types have detail pages
- [ ] Form-based editing (not JSON-only)
- [ ] Name immutable, display name editable
- [ ] MCP server connection test functionality
- [ ] Pagination at top AND bottom
- [ ] Consistent back navigation
- [ ] Form validation with inline errors

#### Estimated Effort
0.5-1 Phase (5 plans)

---

### 12. Advanced User & Group Management with External Identity Integration

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-14  
**Design Doc:** [docs/enhancement/advanced-user-group-management/00-specification.md](./advanced-user-group-management/00-specification.md)  

#### Problem Statement
Current group management is limited: no inline user-to-group assignment, can't edit user groups after creation, groups only show member count (not who), no group detail pages, and no external identity provider integration for enterprise scenarios.

#### Current State (As-Is)
- **Permission Model:** Complex (User → Direct Roles OR User → Groups → Roles → Permissions)
- **Group Assignment:** Only at user creation time, cannot edit after
- **Group Visibility:** Shows only member count, not member list
- **No Detail Pages:** Groups are rows only, no drill-down
- **No External Sync:** Keycloak/AD groups not integrated
- **Permission Clarity:** Hidden behind role abstraction

#### Target State (To-Be)
- **Permission Model:** Clean (User → Local Groups → Permissions directly)
- **Group Assignment:** "Manage Groups" modal for anytime editing
- **Group Detail Pages:** /admin/groups/[id] with Members/Permissions/Settings tabs
- **External Integration:** Global Groups (Keycloak/AD) map to Local Groups
- **Permission Visibility:** Expanded checklist showing all granted permissions
- **Auto-Provisioning:** Users automatically get permissions based on external group membership

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Permission path** | Groups → Roles → Permissions | Groups → Permissions (direct) | Simpler, clearer audit trail |
| **External groups** | Not supported | Global Groups (read-only mirror) | IT manages identities externally |
| **Local groups** | Manual only | Permission-bearing with external mappings | AgentOS admin controls permissions |
| **Assignment UI** | Creation-time only | Modal dialog (Manage Groups) | Easier for large user bases |
| **Detail view** | None (count only) | Full page with tabs | Complete management capability |
| **Permission display** | Hidden in roles | Expanded checklist by category | Full visibility |

#### Architecture Highlights

**Three-Layer Design:**
```
External IDP (Keycloak/AD/LDAP)
    ↓
Global Groups (read-only, auto-sync)
    ↓ [Admin mapping]
Local Groups (permission-bearing)
    ↓
Permissions → User Access
```

**Key Features:**
- **Global Groups:** Mirror external IDP groups (keycloak:/engineering)
- **Local Groups:** AgentOS-managed with direct permissions
- **Mappings:** Link global to local (e.g., keycloak:/engineering → "Engineering Team")
- **Auto-Sync:** Users automatically join local groups based on external membership
- **Exceptions:** Manual add/remove overrides auto-sync

#### Database Changes
- New tables: `global_groups`, `group_permissions`, `group_mappings`
- Enhanced: `local_user_groups` with source tracking
- Migration: Convert `local_group_roles` → `group_permissions`

#### UI Components
- **ManageGroupsModal:** Add/remove users from groups
- **Group Detail Page:** Members tab, Permissions tab, Settings tab
- **PermissionChecklist:** Categorized permission management
- **SyncStatusIndicator:** Show external sync health

#### Implementation Phases
1. **Backend Foundation:** Database migration, new APIs, permission resolution
2. **Group Management UI:** Detail pages, permission management
3. **User Enhancement:** Manage Groups modal, user detail page
4. **Keycloak Integration:** Global group sync, auto-mapping

#### Success Criteria
- [ ] Groups have direct permissions (no role indirection)
- [ ] Group detail page with Members/Permissions/Settings tabs
- [ ] "Manage Groups" modal for user group assignment
- [ ] Keycloak groups sync as Global Groups
- [ ] Global-to-Local group mappings work
- [ ] Permission resolution includes all group permissions
- [ ] UI distinguishes manual vs synced group memberships
- [ ] Audit log tracks permission changes

#### Estimated Effort
1 Phase (6 plans)

---

### 4. Admin Console LLM Configuration with Pluggable Module Architecture

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-15  
**Design Doc:** [docs/enhancement/admin-console-llm-config/00-specification.md](./admin-console-llm-config/00-specification.md)  

#### Problem Statement
LiteLLM configuration requires editing YAML files and restarting containers. No runtime model management, no visibility into model health or costs, and no fallback chain configuration.

#### Current State (As-Is)
- **Configuration:** Edit `infra/litellm/config.yaml` manually
- **Apply Changes:** Restart LiteLLM container (downtime)
- **Testing:** Manual API calls to verify connectivity
- **Monitoring:** Check logs manually
- **Cost Tracking:** Not available
- **Fallbacks:** Static YAML only

#### Target State (To-Be)
- **Configuration:** Admin UI with forms and validation
- **Apply Changes:** Runtime via API (zero downtime)
- **Testing:** One-click connectivity test
- **Monitoring:** Real-time health dashboard
- **Cost Tracking:** Budget alerts and usage quotas
- **Fallbacks:** Visual chain builder with conditions

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Architecture** | Monolithic backend | Pluggable sidecar modules | Independent scaling and upgrades |
| **BaseModule** | None | Abstract class with CLI hooks | Reusable pattern for all modules |
| **Communication** | Direct function calls | HTTP with circuit breaker | Resilience and scalability |
| **Scale Path** | Docker Compose only | Compose → Swarm → K8s | Growth from 100 to 5,000 users |
| **Custom Logic** | None | Overrideable methods | Flexibility for complex operations |

#### Architecture Highlights

**Pluggable Module Pattern:**
```
┌─────────────────┐     ┌────────────────────────────────┐
│   Backend       │◀───▶│  Module Sidecars (scalable)    │
│  ┌───────────┐  │ HTTP│  ┌──────────────────────────┐  │
│  │BaseClient │  │     │  │  BaseModule (abstract)   │  │
│  │ - Circuit │  │     │  │  ┌──────────────────┐    │  │
│  │   breaker │  │     │  │  │ execute_cli()    │    │  │
│  │ - Retry   │  │     │  │  │ health_check()   │    │  │
│  └───────────┘  │     │  │  └──────────────────┘    │  │
└─────────────────┘     │  │  ┌──────────────────┐    │  │
                        │  │  │ Custom Methods   │    │  │
                        │  │  │ (overrideable)   │    │  │
                        │  │  └──────────────────┘    │  │
                        │  └──────────────────────────┘  │
                        └────────────────────────────────┘
```

**Key Features:**
- **BaseModule:** Abstract class with CLI execution + custom code hooks
- **Sidecar Pattern:** Each module is separate container/service
- **Horizontal Scaling:** Modules can have N replicas
- **Technology Diversity:** Different languages per module
- **Zero-Downtime Updates:** Restart modules independently

#### Module Commands

**LiteLLM Config Module (7 commands):**
1. `add_model` - Add new LLM with validation
2. `remove_model` - Remove existing model
3. `list_models` - List all configured models
4. `test_model` - Test connectivity
5. `update_model` - Update configuration
6. `get_model_health` - Health status
7. `get_metrics` - Usage metrics

#### UI Components

- **Models Page:** CRUD operations, search, filter, pagination
- **Fallbacks Page:** Visual chain builder with drag-and-drop
- **Health Page:** Real-time monitoring with latency charts
- **Costs Page:** Budget tracking, quotas, usage alerts

#### Database Schema

- `module_metadata` - Registered modules with health status
- `llm_usage_stats` - Aggregated daily usage per model
- `fallback_chains` - Fallback chain configurations
- `model_quotas` - Quota settings per model

#### Implementation Phases

1. **Base Framework:** BaseModule, client, registry, resilience patterns
2. **LiteLLM Module:** Sidecar service with 7 commands
3. **Backend Integration:** API routes, discovery, permissions
4. **Frontend Models:** Model CRUD with forms
5. **Frontend Advanced:** Fallbacks, health, costs
6. **Testing & Docs:** E2E tests, documentation, admin guide

#### Success Criteria

- [ ] Add model via UI in <5 seconds
- [ ] Zero downtime for configuration changes
- [ ] One-click model connectivity test
- [ ] Real-time health dashboard
- [ ] Budget alerts at 80%/90%/100%
- [ ] Module restart doesn't affect backend
- [ ] Works with Docker Compose (MVP)
- [ ] Migration path to Kubernetes documented

#### Estimated Effort
2-3 weeks (7 phases)

---

## Pending Topics

### 3. WhatsApp Business API Integration

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Medium  
**Target:** v1.4  
**Dependencies:** Business verification (1-4 weeks)  

#### Brief Description
Full WhatsApp Business API integration as a channel gateway. Currently Telegram is supported; WhatsApp requires Meta Business verification which takes 1-4 weeks.

#### Open Questions
- Use Meta's Cloud API or On-Premises API?
- Handle message templates (required for business-initiated messages)?
- Support for interactive messages (buttons, lists)?
- Media message support (images, documents)?

#### Current State
- Channel gateway architecture exists
- Telegram adapter implemented
- No WhatsApp adapter

#### Target State
- WhatsApp channel adapter in `channels/adapters/`
- Business verification process documented
- Message templates management UI
- Full feature parity with Telegram channel

---

### 4. HashiCorp Vault Integration

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos + Architecture discussions  
**Priority:** Low  
**Target:** Post-MVP  
**Dependencies:** Enterprise security requirements  

#### Brief Description
Replace AES-256 encrypted DB storage with HashiCorp Vault for enterprise-grade secret management. Currently credentials stored in PostgreSQL with AES-256 encryption.

#### Open Questions
- Vault deployment model (integrated container vs external)?
- Migration path for existing credentials?
- Support for Vault's dynamic secrets (database credentials)?
- Kubernetes integration (post-MVP)?

#### Current State
- Credentials in PostgreSQL with AES-256 encryption
- Encryption key in environment variable
- No external secret management

#### Target State
- Vault as optional secret backend
- Same interface, pluggable provider
- Support for dynamic database credentials
- Audit logging integration

---

### 5. Admin Console LLM Configuration

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** High  
**Target:** v1.4  
**Dependencies:** None  

#### Brief Description
Make LLM model and provider configurable via admin UI instead of editing `infra/litellm/config.yaml`. Currently requires file edit + container restart.

#### Open Questions
- Support for multiple providers simultaneously?
- Model fallback configuration UI?
- Cost tracking per model?
- A/B testing different models?

#### Current State
- LiteLLM config in YAML file
- Requires container restart to apply
- No runtime configuration

#### Target State
- Admin UI page for LLM configuration
- Runtime model addition/removal
- Fallback chain configuration
- Model health/status dashboard

---

### 5. GitHub Repository Skill Sources

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Medium  
**Target:** v1.4  
**Dependencies:** None  

#### Brief Description
Allow importing skills directly from GitHub repositories. Currently only `agentskills-index.json` protocol is supported.

#### Open Questions
- Support for private repositories (GitHub App vs PAT)?
- Auto-sync on repository updates (webhooks)?
- Version pinning (tags/branches)?
- Monorepo support (multiple skills in one repo)?

#### Current State
- Skill Store supports index.json URLs only
- Manual ZIP upload
- No GitHub integration

#### Target State
- GitHub repo URL input in Add Repository dialog
- Automatic skill file detection
- Tree/file listing for skill selection
- Fork-based workflow support

---

### 6. Keycloak SSO Hardening

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos (TECH-DEBT)  
**Priority:** High  
**Target:** v1.4  
**Type:** Bug Fix  

#### Brief Description
Fix Keycloak SSO login returning "Server error — Configuration" (`/api/auth/error?error=Configuration`). Next-auth Keycloak provider fails during OIDC discovery or token exchange.

#### Possible Causes
1. `KEYCLOAK_ISSUER` URL unreachable from Next.js server (self-signed cert/DNS)
2. `KEYCLOAK_CLIENT_ID` or `KEYCLOAK_CLIENT_SECRET` mismatch with Keycloak realm
3. Keycloak service not running or realm not configured
4. Issuer URL mismatch (HTTP vs HTTPS)

#### Current State
- SSO login fails with generic error
- Local auth works fine

#### Target State
- Reliable SSO login flow
- Better error messages for configuration issues
- Automatic retry/fallback

---

### 7. Analytics & Observability Dashboard

**Status:** 🟡 PENDING  
**Source:** Architecture discussions  
**Priority:** Medium  
**Target:** v1.4  
**Dependencies:** Grafana/Loki setup (Phase 6 foundation)  

#### Brief Description
Comprehensive analytics dashboard showing system usage, performance metrics, audit trails, and agent effectiveness. Builds on Phase 6 observability foundation.

#### Open Questions
- Real-time vs batch analytics?
- User-level vs system-level metrics?
- Data retention policies?
- Export capabilities (PDF reports)?

#### Current State
- Audit logs in JSON files (Loki-compatible)
- Prometheus metrics exposed
- No visualization layer

#### Target State
- Grafana dashboards (embedded or standalone)
- Usage analytics: active users, popular skills, tool usage
- Performance: latency percentiles, error rates
- Agent effectiveness: completion rates, user satisfaction
- Audit trail visualization

---

### 8. Multi-Agent Orchestration

**Status:** 🟡 PENDING  
**Source:** Architecture vision  
**Priority:** Low  
**Target:** v1.5  
**Dependencies:** Stable single-agent platform  

#### Brief Description
Enable agents to spawn sub-agents and coordinate complex workflows. Currently single-agent execution; multi-agent requires manual workflow composition.

#### Open Questions
- Parent-child agent relationships?
- Shared memory vs isolated memory?
- Conflict resolution between agents?
- Hierarchical vs flat coordination?
- Agent marketplace/discovery?

#### Current State
- Single agent execution
- Workflow canvas for manual composition
- No dynamic agent spawning

#### Target State
- Agent can spawn sub-agents via tool call
- Hierarchical state management
- Inter-agent communication protocol
- Dynamic workflow generation
- Agent supervisor pattern

---

### 13. User Experience Enhancement (UI Theme + User Profile)

**Status:** 🟡 PENDING  
**Source:** User feedback / Product vision  
**Priority:** Medium  
**Target:** v1.4  
**Dependencies:** None  
**Estimated Effort:** 1 Phase (0.5 Theme + 0.5 Profile)

#### Brief Description
Comprehensive user experience improvements combining UI theme system with full user profile management. Transforms AgentOS from a functional but utilitarian interface into a polished, personalized user experience.

**Two Components:**
1. **UI Theme System** - Dark/light mode, color palettes, design system foundation
2. **Full User Profile** - Avatar, bio, preferences, notification settings

#### Open Questions
- Theme persistence: localStorage vs database vs both?
- Avatar storage: local filesystem vs S3-compatible vs database?
- Theme scope: global only or per-workspace/per-chat?
- Default theme: follow system preference or fixed default?
- User profile fields: minimal vs comprehensive?
- Profile visibility: public (to org) vs private?

#### Current State
- Single light theme (default)
- No user profile page (only basic info in settings)
- No avatar support
- No theme switching
- User preferences not persisted

#### Target State
- **Theme System:**
  - Dark/Light mode toggle with system detection
  - Color palette customization (primary, secondary, accent)
  - Component consistency across all pages
  - Theme persistence across sessions
  - Smooth transitions between themes
  
- **User Profile:**
  - Dedicated profile page (`/profile` or `/settings/profile`)
  - Avatar upload with crop/resize
  - Display name (editable, separate from Keycloak username)
  - Bio/Description field
  - Contact preferences
  - Notification settings (email, in-app, channels)
  - User-specific settings (language, timezone, theme preference)
  - Profile visibility controls

#### Success Criteria
- [ ] Toggle between dark/light modes
- [ ] Theme follows system preference by default
- [ ] Theme persists across browser sessions
- [ ] All components respect theme settings
- [ ] Smooth theme transitions (no flash)
- [ ] User can upload avatar
- [ ] User can edit display name
- [ ] User can write bio/description
- [ ] User can manage notification preferences
- [ ] User settings persist to database
- [ ] Profile page accessible from user menu

---

## Additional Topics (From STATE.md)

### 9. CREDENTIAL_ENCRYPTION_KEY Production Setup

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Critical (Pre-production)  
**Target:** Before v1.4 production deploy  

**Description:** Add `CREDENTIAL_ENCRYPTION_KEY` to production `.env` before OAuth flows. Currently using dev key.

---

### 10. LLM Model Switch Back to qwen3.5:cloud

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Low  
**Target:** When Ollama limit resets  

**Description:** Currently using `qwen2.5:7b` local due to weekly Ollama limit. Switch back to `qwen3.5:cloud` when reset.

---

## Topic Selection Guide

When starting next brainstorming session, consider:

### Completed ✅
1. ✅ Runtime Permission Approval (HITL)
2. ✅ Admin Registry Edit UI
3. ✅ Advanced User & Group Management
4. ✅ Admin Console LLM Configuration (Pluggable module architecture)
5. ✅ Analytics & Observability Dashboard
6. ✅ User Experience Enhancement (UI Theme + User Profile)

### High Priority (v1.4 Must-Have)
5. Keycloak SSO Hardening (Stability) ⭐ **NEXT RECOMMENDED**

### Medium Priority (v1.4 Should-Have)
6. WhatsApp Business API Integration (Channel expansion)
7. GitHub Repository Skill Sources (Developer experience)

### Low Priority (Post-v1.4)
10. HashiCorp Vault Integration (Enterprise feature)
11. Multi-Agent Orchestration (v1.5 vision)

---

## Brainstorming Process

For each topic:

1. **Move to IN-PROGRESS** — Update status
2. **Clarify scope** — Current vs target state
3. **Ask questions** — One at a time, gather requirements
4. **Propose approaches** — 2-3 options with trade-offs
5. **Make decisions** — Document current → target with rationale
6. **Write design doc** — Save to `docs/enhancement/<topic>/`
7. **Mark COMPLETED** — Update this tracking doc
8. **Select next topic** — Continue or stop for approval

---

## Document Maintenance

- Update status immediately when topic changes state
- Add new topics as they arise
- Archive completed topics to separate section if list grows
- Link to design docs for completed topics

---

## 📝 SESSION SUMMARY (2026-03-16) — Analytics Dashboard

**Topics Completed:** Analytics & Observability Dashboard (#8)

**Brainstorming Highlights:**
- Defined dual-mode architecture (Grafana + Embedded panels)
- Selected hybrid query strategy (materialized views + direct queries)
- Identified 6 analytics categories covering all operational needs
- Chose Tremor React for chart components
- Designed 6-page analytics hub structure
- Ensured consistency with Topic #14 Dashboard architecture

**Architecture Decisions:**
- Grafana HTTP API + Custom Components (not iframe embedding)
- Hybrid approach: Materialized views for history, direct queries for real-time
- PostgreSQL materialized views with concurrent refresh
- Redis caching layer for performance
- Tremor React chart library for professional defaults

**Completed Topics Now: 7**
- #1, #4, #6, #8, #12, #14, #15

**Remaining Pending: 5**
- #7 Keycloak SSO Hardening (Critical - Recommended Next)
- #2, #5, #13 (Medium priority)
- #9, #10 (Low priority)

---

**Next Recommended Topic:** Keycloak SSO Hardening — Critical stability fix

**Alternatives:**
- GitHub Repository Skill Sources — Developer experience improvement
- Start implementation planning for completed topics

---

## 🆕 NEW TOPIC ADDED

**Session Date:** 2026-03-15  
**Topic:** #13 User Experience Enhancement  
**Status:** 🟡 PENDING - Awaiting brainstorming

**Components:**
1. UI Theme System (Dark/Light mode, color palettes, design system)
2. Full User Profile (Avatar, bio, preferences, notification settings)

**Effort:** 1 Phase (0.5 + 0.5)  
**Priority:** Medium  
**Rationale:** Improves user satisfaction, product polish, competitive differentiation

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*

---

## 🆕 NEW TOPIC ADDED (Dashboard & Mission Control)

**Session Date:** 2026-03-16  
**Topic:** #14 AgentOS Dashboard & Mission Control  
**Status:** ✅ COMPLETED - Design document written

**Components:**
1. **Overview Page** — System health + Activity feed
2. **Flow Execution Monitor** — Workflow runs with step-by-step drill-down
3. **Agents Page** — Agent management + optional 3D office visualization
4. **Memory Browser** — Memory search and exploration

**Key Innovations:**
- Unified operational interface for admins and users
- Real-time WebSocket updates
- Deep integration with Phase 8 observability
- Inspired by OpenClaw Dashboard (mudrii, tugcantopaloglu, tenacitOS)

**Effort:** 1.5 Phases (6 weeks)  
**Priority:** High  
**Target:** v1.4  
**Rationale:** Essential operational visibility; complements existing Grafana dashboards with user-friendly interface

**Design Doc:** [docs/enhancement/agentos-dashboard-mission-control/00-specification.md](./agentos-dashboard-mission-control/00-specification.md)

---

## 📝 SESSION SUMMARY (2026-03-16)

**Topics Completed:** AgentOS Dashboard & Mission Control (#14)

**Brainstorming Highlights:**
- Analyzed 3 reference repositories (mudrii, tugcantopaloglu, tenacitOS)
- Selected integrated approach (same Next.js app)
- Defined 4-page structure: Overview, Flows, Agents, Memory
- Leverages existing Phase 8 observability (Prometheus, Loki)
- Real-time updates via WebSocket
- Optional 3D office visualization

**Architecture Decisions:**
- Backend API aggregation layer
- WebSocket + Redis Pub/Sub for real-time
- Lazy-loaded 3D visualization
- RBAC-enforced throughout

**Next Topics:**
- #7 Keycloak SSO Hardening (Critical)
- #15 Scheduler Management UI (Future)

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*


---

## 🆕 NEW TOPIC ADDED (Scheduler Engine & UI)

**Session Date:** 2026-03-16  
**Topic:** #15 Scheduler Engine & UI  
**Status:** ✅ COMPLETED - Design document written

**Components:**
1. **Global Scheduler View** (/scheduler) — Operations dashboard for all jobs
2. **Per-Workflow Schedule Tab** — Integrated workflow scheduling
3. **Visual Cron Builder** — Interactive builder with timezone, preview
4. **Execution History** — Job runs with filtering and drill-down
5. **Queue Monitoring** — Real-time Celery queue status
6. **Multi-Channel Alerting** — In-app, Telegram, email notifications

**Key Innovations:**
- Extends existing Celery infrastructure (no replacement)
- Dual UI: Global view for ops + per-workflow for users
- Full interactive cron builder (not just text)
- Real-time queue monitoring
- Comprehensive alerting system

**Effort:** 1 Phase (5 weeks)  
**Priority:** High  
**Target:** v1.4  
**Rationale:** Essential operational capability; complements Dashboard with scheduling management

**Design Doc:** [docs/enhancement/scheduler-engine-ui/00-specification.md](./scheduler-engine-ui/00-specification.md)

---

## 📝 SESSION SUMMARY (2026-03-16) — Scheduler

**Topics Completed:** Scheduler Engine & UI (#15)

**Brainstorming Highlights:**
- Investigated existing Celery scheduler infrastructure
- Identified gaps: No UI, no visual builder, no queue monitoring
- Selected Celery-centric approach (extends existing)
- Defined 5-page structure: Global Jobs, History, Queue, Per-Workflow, Cron Builder
- Full interactive cron builder with timezone and holiday support
- Multi-channel alerting architecture

**Architecture Decisions:**
- Extend Celery (no replacement) — lower risk
- Backend API aggregation layer
- Global + per-workflow dual interface
- Real-time queue status
- RBAC-enforced throughout

---

### Session 4: 2026-03-16 (Evening)

**Session Status:** ✅ COMPLETED - Ready for next session  
**Total Topics Completed This Session:** 1  

**Topic #13: User Experience Enhancement (UI Theme + User Profile)** ✅
- Comprehensive UX transformation with dual-component system
- 3 Built-in themes: Light, Dark, Navy Blue
- Color customization: 6 curated presets + custom hex input
- Full user profile: Avatar (MinIO), bio, preferences, notifications
- Dual-level timezone: System-wide (admin) + per-user
- CSS Variables architecture (Tailwind v4 native)
- Avatar storage via MinIO (S3-compatible)
- 6-week implementation timeline (1 Phase)
- Consistent with all other v1.4 topics
- **Design Doc:** `docs/enhancement/user-experience-enhancement/00-specification.md`

**Brainstorming Highlights:**
- Analyzed existing Tailwind v4 CSS variable foundation
- Selected CSS Variables approach over next-themes (better performance, Tailwind v4 native)
- Defined complete color system with 17 CSS variables per theme
- Architected dual-level timezone management (system + user)
- Integrated MinIO for avatar storage (aligns with broader storage system vision)
- Designed 4-tab profile structure (Profile, Preferences, Notifications, Security)

**Architecture Decisions:**
- CSS Variables strategy for zero-JS-overhead theming
- MinIO (S3-compatible) for scalable avatar storage
- 6 curated color presets + custom hex input
- localStorage for instant theme, database for persistence
- 3 avatar sizes generated (40px, 120px, 400px)
- date-fns-tz for reliable timezone handling

**Completed Topics Now: 8**
- #1, #4, #6, #8, #12, #13, #14, #15

**Remaining Pending: 4**
- #7 Keycloak SSO Hardening (Critical - Recommended Next)
- #2, #5 (Medium priority)

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*
