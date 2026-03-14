# Brainstorming Tracking Document

**Project:** Blitz AgentOS  
**Milestone:** v1.4 Planning  
**Created:** 2026-03-14  
**Last Updated:** 2026-03-16  

---

## 🔄 SESSION HANDOVER

### Previous Session: 2026-03-17 (Session 7 - New Enhancement Topics Added) ✅ COMPLETED

**Total Topics Completed:** 11
- Topics #1, #4, #5, #6, #7, #8, #12, #13, #14, #15, #16 ✅
- Topic #9: Runtime Multi-Agent Orchestration (Architecture Decision Made) 🔵

**New Topics Added (v1.7+):** 7 topics
- #18: Email System & Channel Notifications
- #19: Storage Service
- #20: Projects/Spaces
- #21: Universal Integration
- #22: MCP Server Creation Skill
- #23: Plugin Templates
- #24: Third-Party Apps UI

**Key Decisions:**
- Option B selected for Multi-Agent (Extend LangGraph, not custom orchestrator)
- Topic #2 WhatsApp deferred to v1.6+
- Topic #17 Advanced Multi-Agent Orchestrator documented as future enhancement
- 7 new enhancement topics documented for v1.7+ roadmap

### 🆕 NEW SESSION: Ready to Start

**Current Status:**
- **11 Topics** ✅ COMPLETED with design docs
- **1 Topic** 🔵 IN-PROGRESS (Topic #9 - needs detailed design)
- **9 Topics** 🟡 PENDING (new v1.7+ topics ready for brainstorming)
- **3 Topics** 🟡 FUTURE (v1.6+)

**Recommended Order for Deep-Dive:**
1. Topic #19: Storage Service (High priority, foundational)
2. Topic #20: Projects/Spaces (High priority, organizational)
3. Topic #9: Runtime Multi-Agent Orchestration (Complete detailed design)
4. Topic #18: Email System (Medium priority)
5. Topic #21: Universal Integration (Medium priority)
6. Topic #22: MCP Server Creation Skill (Medium priority)
7. Topic #24: Third-Party Apps UI (Medium priority)
8. Topic #23: Plugin Templates (Low priority)

**Ready for Deep-Dive Brainstorming**

---

## 📋 CURRENT TOPIC STATUS

### Session 6 Completed Work:

**Topic #5: Universal Skill Import System (GitHub Repository Skill Sources Extended)** ✅
- Extended from simple GitHub import to Universal Adapter Pattern
- Comprehensive research of 7 skill repositories (VoltAgent, marketingskills, Claude Official, Everything Claude Code, Superpowers, GSD, etc.)
- Identified common patterns: SKILL.md, metadata.json, plugin.json structures
- Adapter architecture with GitHub, ZIP, and Index JSON adapters
- Skill-Tool Bundling: Private tools require mandatory sandbox execution
- References & Output Formats: Skills can declare external references and structured output schemas
- Security-First: Security scanning before import, private tools enforced in sandbox
- Full observability integration with Dashboard (#8) and Mission Control (#11)
- Extensible for v1.5 (GitLab, Bitbucket, Gitea) and v1.6 (full plugin ecosystem)
- **Design Doc:** `docs/plans/2026-03-14-universal-skill-import-design.md`

**Brainstorming Highlights:**
- Analyzed 7 different skill repository patterns from the ecosystem
- Discovered common manifest formats: .claude-plugin/plugin.json, SKILL.md, skills/ folders
- Designed extensible BaseSkillAdapter interface for future sources
- RawSkillBundle abstraction normalizes all sources to common format
- Security scanner with secrets detection, unsafe patterns, dependency scanning
- Import decision engine supporting immediate vs approval workflows
- Sandbox enforcement: All private tools MUST run in isolated containers
- References system for documentation, examples, API specs, related skills
- Output format specifications (markdown, JSON schema, templates)
- Full observability: metrics, logs, alerting for imports and sandbox executions

**Topic #16: Multi-Agent Tab Architecture (Artifact Creation)** ✅
- Added existing design document to tracking
- Creation-time multi-agent experience for artifact wizard
- Fixes context pollution and UI state bugs in skill/tool creation
- Enables parallel dependency creation in separate tabs
- Database-backed dependency tracking with status notifications
- **Design Doc:** `docs/enhancement/multi-agent-tab-architecture/00-specification.md`

**Topic #9: Runtime Multi-Agent Orchestration - Architecture Decision** 🔵
- Evaluated two approaches: Custom Orchestrator (Option A) vs Extend LangGraph (Option B)
- **DECISION: Option B (Extend LangGraph)** for v1.5
- Rationale: Leverages existing workflow infrastructure, visual canvas, faster implementation
- Option A (Custom Orchestrator) documented as future enhancement (Topic #17) for v1.6+
- Implementation phases: Rich agent node → Team templates → Shared memory → Agent spawning tool
- **Status:** Ready for detailed design documentation

**Architecture Decisions:**
- Adapter Pattern (not Strategy or Direct) for extensibility and testability
- RawSkillBundle as intermediate representation before normalization
- Security scan BEFORE parsing (fail fast for malicious content)
- Mandatory sandbox for private tools (enforced at validation and runtime)
- Configurable import policies per repository (immediate vs approval)
- Integration with existing AgentOS tables (SkillDefinition, ToolDefinition, etc.)
- Mission Control widgets for import queue and sandbox execution monitoring
- Analytics dashboard for import metrics, security scans, tool usage

---

### Previous Sessions Summary

**Session 5: 2026-03-16 (Late Evening)**  
- Topic #7: Keycloak SSO Hardening ✅

**Session Status:** ✅ COMPLETED  
**Total Topics Completed This Session:** 1  

**Topic #7: Keycloak SSO Hardening** ✅
- Comprehensive three-pillar hardening approach (Health + UX + Config Validation)
- Verified issue still exists in codebase (partial fix in Phase 24-01 insufficient)
- Error categorization: Certificate (40%) / Configuration (35%) / Unreachable (20%) / Timeout (5%)
- Health monitoring with 4-tier test suite (DNS → TLS → OIDC → Client)
- Graceful degradation to local auth when SSO fails
- Circuit breaker pattern (5 failures → 60s timeout → half-open)
- Pre-flight configuration validation with specific fix recommendations
- Admin dashboard with real-time health status
- **Key Principle:** Keycloak is OPTIONAL — system works perfectly with local auth only
- **Design Doc:** `docs/enhancement/keycloak-sso-hardening/00-specification.md`

---

### Previous Sessions Summary

**Session 4: 2026-03-16 (Evening)**  
- Topic #13: User Experience Enhancement ✅

**Session 3: 2026-03-16 (Afternoon)**  
- Topic #8: Analytics & Observability Dashboard ✅

**Session 2: 2026-03-16 (Afternoon)**  
- Topic #15: Scheduler Engine & UI ✅

**Session 1: 2026-03-16 (Morning)**  
- Topic #14: AgentOS Dashboard & Mission Control ✅

**Session: 2026-03-15**  
- Topic #13 added to pending list

**Session: 2026-03-14**  
- Topics #1, #4, #6 completed ✅

### 🎯 Key Decisions Made (All Sessions)

| Topic | Critical Decisions |
|-------|-------------------|
| **Dashboard (#14)** | Integrated approach in Next.js; Backend API aggregation; WebSocket for real-time; Leverages Phase 8 observability |
| **Scheduler (#15)** | Celery-centric approach (extend, don't replace); Dual UI (global + per-workflow); Full visual cron builder; Multi-channel alerting |
| **Analytics (#8)** | Dual-mode (Grafana + Embedded); Hybrid query strategy (materialized views + direct); 6 analytics categories; Tremor React for charts |
| **UX Enhancement (#13)** | CSS Variables theming (Tailwind v4); MinIO avatar storage; Dual timezone (system + user); 3 themes + color customization |
| **Keycloak Hardening (#7)** | Optional SSO with graceful degradation; Health monitoring with error categorization; Circuit breaker pattern; Pre-flight validation |
| **Skill Import (#5)** | Universal adapter pattern (BaseSkillAdapter); GitHub + ZIP + Index JSON support; Mandatory sandbox for private tools; Security-first validation; Extensible for v1.5/v1.6 |
| **Multi-Agent Tab (#16)** | Creation-time multi-agent experience; Tab-based context isolation; Database-backed dependency tracking; Parallel dependency creation; Separate CopilotKit instances per tab |
| **Multi-Agent Orchestration (#9)** | Option B selected: Extend LangGraph (not custom orchestrator); Leverages canvas builder and checkpointing; Rich agent nodes + team templates + shared memory; Option A (custom orchestrator) deferred to v1.6+ as Topic #17 |

### 🔄 Architecture Evolution

**New Patterns Introduced:**
- **BaseModule Framework:** Abstract class for all AgentOS modules
- **Module Sidecars:** Independent services in Docker Compose/K8s
- **Resilient Communication:** Circuit breaker + retry patterns
- **Dashboard Aggregation:** Unified API layer for multiple data sources
- **Scheduler Management:** Extend Celery with management API and UI
- **Hybrid Analytics Query:** Materialized views for history + Direct queries for real-time
- **Dual-Mode Visualization:** Grafana for ops + Embedded panels for users
- **SSO Hardening:** Graceful degradation; Health monitoring; Error categorization
- **Skill Adapter Pattern:** BaseSkillAdapter for universal import sources
- **Skill-Tool Bundling:** Private tools with mandatory sandbox execution
- **Security-First Import:** Scan before parsing; Validation at multiple layers
- **Import Decision Engine:** Configurable immediate vs approval workflows
- **RawSkillBundle:** Intermediate representation normalizing all skill sources
- **Sandbox Enforcement:** Private tool isolation at validation and runtime
- **Multi-Agent Tabs:** Creation-time agent spawning with context isolation; Database dependency tracking; Separate agent instances per tab

**Impact on Future Topics:**
- Security Scan Module can use same BaseModule pattern
- Analytics Module fits sidecar architecture
- All future modules follow consistent pattern
- Dashboard and Scheduler provide operational foundation
- Analytics patterns reusable for future reporting features
- SSO hardening patterns applicable to other external integrations
- Skill Import adapters establish pattern for GitLab/Bitbucket/Gitea (v1.5)
- Sandbox execution patterns reusable for all external code
- Security scanner can be extracted as standalone BaseModule

### 📊 Current Status

**Completed ✅ (11):**
- #1 Runtime Permission Approval (HITL)
- #4 Admin Console LLM Configuration
- #5 Universal Skill Import System (GitHub + ZIP + Adapters)
- #6 Admin Registry Edit UI
- #7 Keycloak SSO Hardening
- #8 Analytics & Observability Dashboard
- #12 Advanced User & Group Management
- #13 User Experience Enhancement
- #14 AgentOS Dashboard & Mission Control
- #15 Scheduler Engine & UI
- #16 Multi-Agent Tab Architecture (Artifact Creation)

**In-Progress 🔵 (1):**
- #9 Runtime Multi-Agent Orchestration (LangGraph Extension)

**Pending 🟡 (9):**
- #2 WhatsApp Business API Integration (Medium)
- #3 HashiCorp Vault Integration (Low)
- #18 Email System & Channel Notifications (Medium)
- #19 Storage Service (High) ⭐ **RECOMMENDED NEXT**
- #20 Projects/Spaces (High)
- #21 Universal Integration (Medium)
- #22 MCP Server Creation Skill (Medium)
- #23 Plugin Templates (Low)
- #24 Third-Party Apps UI (Medium)

### 🚀 Recommended Next Steps

**All Critical v1.4 Topics Completed! 🎉**

**For Next Session:**

**Option A: Continue Brainstorming (Remaining Topics)**
- Topic #9: Runtime Multi-Agent Orchestration (LangGraph Extension) ⭐ **RECOMMENDED NEXT**

**Option B: Start Implementation**
- Create PLAN.md files for any of the 11 completed topics
- Begin Phase 1 implementation of high-priority topics:
  - #7 Keycloak SSO Hardening (Critical stability fix)
  - #14 Dashboard & Mission Control (High user value)
  - #15 Scheduler Engine (Operational necessity)
  - #5 Universal Skill Import System (Developer experience)
- Review designs with stakeholders before coding

**Option C: Plan v1.5 Topics**
- #9 Runtime Multi-Agent Orchestration (LangGraph Extension)
- Brainstorm additional v1.5 features

**Option D: Plan v1.6+ Topics**
- #2 WhatsApp Business API Integration (Channel expansion)
- #3 HashiCorp Vault Integration (Enterprise feature)
- #17 Advanced Multi-Agent Orchestrator (Custom)

### 📁 Files Modified This Session (Session 6)

- `docs/plans/2026-03-14-universal-skill-import-design.md` (NEW)
- `docs/enhancement/BRAINSTORMING-TRACKING.md` (UPDATED)

### 📁 All Design Documents (11 Completed)

- `docs/enhancement/runtime-permission-approval/00-specification.md`
- `docs/enhancement/admin-console-llm-config/00-specification.md`
- `docs/enhancement/admin-registry-edit-ui/00-specification.md`
- `docs/enhancement/advanced-user-group-management/00-specification.md`
- `docs/enhancement/agentos-dashboard-mission-control/00-specification.md`
- `docs/enhancement/scheduler-engine-ui/00-specification.md`
- `docs/enhancement/analytics-observability-dashboard/00-specification.md`
- `docs/enhancement/user-experience-enhancement/00-specification.md`
- `docs/enhancement/keycloak-sso-hardening/00-specification.md`
- `docs/plans/2026-03-14-universal-skill-import-design.md`
- `docs/enhancement/multi-agent-tab-architecture/00-specification.md`

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
12. **Keycloak Hardening:** Optional SSO with graceful degradation; Health monitoring; Circuit breaker; Error categorization
13. **Skill Import:** Adapter pattern with BaseSkillAdapter interface; GitHub + ZIP + Index JSON; Mandatory sandbox for private tools; Security-first validation
14. **Skill-Tool Bundling:** Private tools require sandbox execution; Tool visibility controls access; References and output formats supported
15. **Multi-Agent Tabs:** Creation-time multi-agent experience; Separate CopilotKit instances per tab; Database-backed dependency tracking; Context isolation between artifact types

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
- Keycloak SSO hardening needs graceful error handling on login page
- Skill Import adapters need async HTTP client with circuit breaker (reuse BaseModule client)
- ToolDefinition table needs new columns for visibility, parent_skill_id, sandbox_required
- Sandbox execution service needs resource limits enforcement (CPU, memory, time)
- Import queue table needs periodic cleanup for old rejected entries
- Multi-Agent Tabs need database migration 031_agent_dependencies (already designed)
- Artifact builder needs refactoring to use new TabManager and separate agent instances

**Open Questions for Future:**
- WhatsApp Business verification timeline (for Topic #2)
- Module versioning and compatibility strategy
- Circuit breaker tuning parameters
- Dashboard 3D visualization performance optimization
- Scheduler holiday exclusion data source
- Multi-Agent Tabs: CopilotKit multi-instance performance at scale
- Multi-Agent Tabs: Max concurrent tabs limit (suggested: 5)
- GitLab/Bitbucket API rate limiting strategy (v1.5)
- Private tool marketplace with pricing (v1.6)
- Cross-skill tool sharing permissions model
- Runtime Multi-Agent Orchestration: Memory model (shared vs isolated)
- Runtime Multi-Agent Orchestration: Coordination patterns (hierarchical vs peer-to-peer)

---

## 🆕 MULTI-AGENT ORCHESTRATION - ARCHITECTURE DECISION

**Decision Date:** 2026-03-14  
**Status:** ✅ DECISION MADE  

### Context
During brainstorming of Topic #9 (Multi-Agent Orchestration), two architectural approaches were evaluated:

### Option A: Custom Orchestrator (Advanced)
**Approach:** Build separate orchestration layer with message bus, agent registry, and dynamic spawning

**Pros:**
- Maximum flexibility for any multi-agent pattern
- True dynamic runtime agent spawning
- Independent agent processes (fault isolation)
- Research-grade multi-agent capabilities

**Cons:**
- Duplicates effort (AgentOS already has LangGraph)
- No visual builder integration
- Complex integration with existing HITL/checkpointing
- 2-3 Phases implementation time
- Higher maintenance burden

**Target:** v1.6+ (Future enhancement)  
**Topic:** #17 Advanced Multi-Agent Orchestrator

### Option B: Extend LangGraph (Selected ✅)
**Approach:** Extend existing LangGraph workflow system with rich agent nodes and team templates

**Pros:**
- Leverages existing canvas and workflow infrastructure
- Visual builder already works
- HITL, checkpointing, persistence already solved
- Incremental implementation (1-2 Phases)
- Single orchestration model

**Cons:**
- Less flexible than custom orchestrator
- Constrained by graph topology
- Dynamic spawning requires subgraph complexity
- Shared state can get messy

**Target:** v1.5  
**Topic:** #9 Runtime Multi-Agent Orchestration (LangGraph Extension)

### Decision Rationale
1. **Existing Investment:** AgentOS already heavily uses LangGraph for workflows
2. **Visual Builder:** Canvas at `/workflows` is a key differentiator
3. **Timeline:** Option B ships faster (v1.5 vs v1.6+)
4. **80/20 Rule:** Option B provides 80% of multi-agent benefits with 20% of effort
5. **Migration Path:** Can implement Option A later if needed (not breaking change)

### Implementation Phases (Option B)
1. **Phase 1:** Rich agent node with dynamic agent discovery
2. **Phase 2:** Team template system with pre-built agent teams
3. **Phase 3:** Shared memory nodes for inter-agent communication
4. **Phase 4:** Agent spawning tool for dynamic sub-agent creation

### Future Revisit Criteria
Consider Option A (Custom Orchestrator) if:
- Multi-agent becomes PRIMARY differentiator for AgentOS
- Need cutting-edge research capabilities (consensus, negotiation, markets)
- Option B proves insufficient for customer use cases
- Team has bandwidth for major architectural investment

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
|---|---|---|-------|--------|--------|-------------|
| 1 | Runtime Permission Approval (HITL) | ✅ COMPLETED | High | v1.4 | 1 Phase |
| 2 | WhatsApp Business API Integration | 🟡 FUTURE | Medium | v1.6+ | 1 Phase |
| 3 | HashiCorp Vault Integration | 🟡 PENDING | Low | Post-MVP | 1 Phase |
| 4 | Admin Console LLM Configuration | ✅ COMPLETED | High | v1.4 | 0.5 Phase |
| 5 | Universal Skill Import System | ✅ COMPLETED | Medium | v1.4 | 1 Phase |
| 6 | Admin Registry Edit UI (expanded from SWR) | ✅ COMPLETED | High | v1.4 | 0.5-1 Phase |
| 7 | Keycloak SSO Hardening | ✅ COMPLETED | High | v1.4 | 0.5 Phase |
| 8 | Analytics & Observability Dashboard | ✅ COMPLETED | Medium | v1.4 | 1 Phase |
| 9 | Runtime Multi-Agent Orchestration (LangGraph Extension) | 🔵 IN-PROGRESS | Low | v1.5 | 1-2 Phases |
| 17 | Advanced Multi-Agent Orchestrator (Custom) | 🟡 FUTURE | Low | v1.6+ | 2-3 Phases |
| 12 | Advanced User & Group Management | ✅ COMPLETED | High | v1.4 | 1 Phase |
| 13 | User Experience Enhancement | ✅ COMPLETED | Medium | v1.4 | 1 Phase |
| 14 | AgentOS Dashboard & Mission Control | ✅ COMPLETED | High | v1.4 | 1.5 Phases |
| 15 | Scheduler Engine & UI | ✅ COMPLETED | High | v1.4 | 1 Phase |
| 16 | Multi-Agent Tab Architecture (Artifact Creation) | ✅ COMPLETED | High | v1.4 | 0.5 Phase |
| 18 | Email System & Channel Notifications | 🟡 PENDING | Medium | v1.7+ | 0.5 Phase |
| 19 | Storage Service | 🟡 PENDING | High | v1.7+ | 1 Phase |
| 20 | Projects/Spaces | 🟡 PENDING | High | v1.7+ | 1-2 Phases |
| 21 | Universal Integration | 🟡 PENDING | Medium | v1.7+ | 1-2 Phases |
| 22 | MCP Server Creation Skill | 🟡 PENDING | Medium | v1.7+ | 1 Phase |
| 23 | Plugin Templates | 🟡 PENDING | Low | v1.7+ | 0.5 Phase |
| 24 | Third-Party Apps UI | 🟡 PENDING | Medium | v1.7+ | 1-2 Phases |

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

### New Topics Added (v1.7+)

#### 18. Email System & Channel Notifications

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** Medium  
**Target:** v1.7+  
**Dependencies:** Channel gateway architecture (existing)

#### Brief Description
Transform email into a first-class channel alongside Telegram/WhatsApp. Enable system notifications to be sent via any configured channel (email, Telegram, in-app). Provide email settings management UI with SMTP/IMAP configuration support.

#### Current State
- Email is used for login/authentication only
- No email-based notifications
- No email channel adapter
- System notifications limited to in-app

#### Target State
- Email as channel adapter (like Telegram)
- System notifications routed via channel preferences
- Email settings UI (SMTP/IMAP configuration)
- Notification templates per channel
- User preference for notification channels

---

#### 19. Storage Service

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** High  
**Target:** v1.7+  
**Dependencies:** MinIO setup

#### Brief Description
Unified storage abstraction layer providing file upload/download capabilities. Serves avatars (Topic #13), workflow attachments, agent outputs, and document processing. S3-compatible API with MinIO backend.

#### Current State
- No centralized storage service
- Avatars planned for MinIO (Topic #13)
- File handling ad-hoc per feature

#### Target State
- StorageService abstraction layer
- MinIO integration (S3-compatible API)
- Upload/download endpoints with progress
- Storage quotas per user/project
- Access control and signed URLs
- Multiple storage backends (MinIO, S3, GCS)

---

#### 20. Projects/Spaces

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** High  
**Target:** v1.7+  
**Dependencies:** User/Group management (Topic #12)

#### Brief Description
Organizational workspaces for grouping agents, workflows, skills, and memory. Enables team collaboration with project-scoped resources and permissions.

#### Current State
- All resources are global/organization-wide
- No project-level isolation
- Limited collaboration features

#### Target State
- Project/Space creation and management
- Project-scoped agents and workflows
- Team membership and roles per project
- Resource isolation (agents can't access other projects)
- Project-level analytics and quotas
- Cross-project sharing (optional)

---

#### 21. Universal Integration

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** Medium  
**Target:** v1.7+  
**Dependencies:** MCP architecture, Plugin system foundation

#### Brief Description
Generic adapter framework for connecting external systems without custom code. Webhook-based integrations, REST API connector builder, and OAuth flow management.

#### Current State
- MCP servers for specific integrations
- Custom code required for new integrations
- No generic connector builder

#### Target State
- Visual integration builder
- Webhook receiver and processor
- REST API connector with authentication
- OAuth 2.0 flow management
- Integration marketplace/catalog
- Request/response transformation

---

#### 22. MCP Server Creation Skill

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** Medium  
**Target:** v1.7+  
**Dependencies:** MCP infrastructure (existing)

#### Brief Description
Natural language skill for creating new MCP servers. Users describe what they want to integrate with, and the skill auto-generates the MCP server scaffolding, tools, and deployment configuration.

#### Current State
- MCP servers created manually via code
- Requires understanding of MCP protocol
- No automated generation

#### Target State
- "Create MCP server" skill
- Natural language description → server code
- Auto-discovery of available APIs
- Tool binding and validation
- One-click deployment
- Server testing and health checks

---

#### 23. Plugin Templates

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** Low  
**Target:** v1.7+  
**Dependencies:** Plugin system foundation

#### Brief Description
Pre-built plugin templates for common patterns (Slack bot, GitHub webhook handler, database connector). Template marketplace with versioning and one-click generation.

#### Current State
- No plugin template system
- Each plugin created from scratch
- No template sharing

#### Target State
- Template gallery with categories
- One-click plugin generation from template
- Custom template creation and publishing
- Template versioning and updates
- Community template marketplace

---

#### 24. Third-Party Apps UI

**Status:** 🟡 PENDING  
**Source:** New enhancement request  
**Priority:** Medium  
**Target:** v1.7+  
**Dependencies:** CopilotKit, AG-UI, A2UI (existing)

#### Brief Description
Dynamic UI generation for third-party applications using CopilotKit, AG-UI, and A2UI. External apps can render rich interfaces within AgentOS chat/context.

#### Current State
- Static UI components
- No dynamic UI generation for external apps
- Limited app integration capabilities

#### Target State
- Apps can define UI components via schema
- CopilotKit renders app-specific UI
- AG-UI components for interactive elements
- A2UI envelopes for rich experiences
- App store/catalog for discovery
- Runtime UI composition

---

### 3. WhatsApp Business API Integration

**Status:** 🟡 FUTURE  
**Source:** STATE.md Pending Todos  
**Priority:** Medium  
**Target:** v1.6+  
**Dependencies:** Business verification (1-4 weeks), Resource prioritization  

#### Brief Description
Full WhatsApp Business API integration as a channel gateway. Currently Telegram is supported; WhatsApp requires Meta Business verification which takes 1-4 weeks.

#### Why Deferred to v1.6+
- Meta Business verification process is lengthy (1-4 weeks) and bureaucratic
- Complex message template requirements for business-initiated conversations
- Resource prioritization: Core platform features (v1.4/v1.5) take precedence
- Telegram channel already provides messaging capability
- Can be added later without breaking existing functionality

#### Open Questions
- Use Meta's Cloud API or On-Premises API?
- Handle message templates (required for business-initiated messages)?
- Support for interactive messages (buttons, lists)?
- Media message support (images, documents)?
- Business verification strategy and timeline?

#### Current State
- Channel gateway architecture exists
- Telegram adapter implemented
- No WhatsApp adapter
- Architecture ready for additional channel adapters

#### Target State (v1.6+)
- WhatsApp channel adapter in `channels/adapters/`
- Business verification process documented
- Message templates management UI
- Full feature parity with Telegram channel
- Compliance with Meta Business API policies

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

### 5. Universal Skill Import System (GitHub + ZIP + Adapters)

**Status:** ✅ COMPLETED  
**Completed Date:** 2026-03-14  
**Design Doc:** [docs/plans/2026-03-14-universal-skill-import-design.md](../plans/2026-03-14-universal-skill-import-design.md)  
**Priority:** Medium  
**Target:** v1.4  
**Dependencies:** None  

#### Brief Description
Universal skill import system with extensible adapter pattern. Supports GitHub repositories (single skill and skills/ folder structures), ZIP file uploads, and existing agentskills-index.json protocol. Skills can bundle private tools that run in mandatory sandboxes.

#### Key Decisions Made

| Decision | Current | Target | Rationale |
|----------|---------|--------|-----------|
| **Architecture** | Index JSON only | Adapter pattern (BaseSkillAdapter) | Extensible for GitLab/Bitbucket/Gitea (v1.5) |
| **Sources** | Manual only | GitHub + ZIP + Index JSON | Multiple import pathways |
| **Tool Bundling** | None | Private tools with sandbox | Self-contained skills with isolated execution |
| **Security** | Basic | Security-first validation | Scan before parsing, mandatory sandbox |
| **Import Flow** | Immediate | Configurable (immediate/approval) | Flexibility for different security postures |

#### Architecture Highlights

**Adapter Pattern:**
```
┌─────────────────────────────────────────────┐
│         SkillImportOrchestrator              │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ GitHub   │ │  ZIP     │ │ Index JSON   │ │
│  │ Adapter  │ │ Adapter  │ │ Adapter      │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
└─────────────────────────────────────────────┘
```

**RawSkillBundle Normalization:**
- All sources converge to common intermediate format
- Skill metadata, instruction markdown, procedure JSON
- Tools (0..N), references, output format schemas
- Security scan BEFORE normalization

**Skill-Tool Bundling:**
- Skills can include private tools
- Private tools MUST run in sandbox (enforced)
- Tool visibility: public | private | protected
- Parent skill reference for access control

**Security-First Validation:**
- Secrets detection (API keys, passwords, tokens)
- Unsafe patterns (eval, exec, shell=True)
- Dependency vulnerability scanning
- Policy violation checking

#### Supported Sources

**v1.4 (Current):**
- GitHub public repos (single skill or skills/ folder)
- ZIP file upload (full folder structure)
- agentskills-index.json URLs

**v1.5 (Future):**
- GitLab, Bitbucket, Gitea adapters
- Private repos (PAT/App auth)
- GitHub App with webhook auto-sync
- Monorepo support
- Version pinning (tags/branches)

**v1.6 (Future):**
- Full plugin system (commands + agents + skills)
- Plugin marketplace
- Auto-updates
- Dependency resolution

#### Database Schema Extensions

**New Tables:**
- `skill_references` - External references (docs, examples, APIs)
- `skill_output_formats` - Output format specifications
- `skill_import_queue` - Pending approval queue

**Extended Tables:**
- `tool_definitions` - Add visibility, parent_skill_id, sandbox_required

#### UI Integration

**Admin Console:**
- Import from GitHub (URL input, auto-discovery)
- Import from ZIP (drag-and-drop upload)
- Import queue management (approve/reject)
- Repository management (add/remove, policies)

**Mission Control:**
- Skill import queue widget
- Sandbox execution dashboard
- Tool usage analytics

**Analytics Dashboard:**
- Import volume and success rates
- Security scan statistics
- Sandbox resource usage
- Tool execution metrics

#### Success Criteria
- [ ] Import skills from GitHub repos (single skill and skills/ folder)
- [ ] Import skills from ZIP uploads
- [ ] Support agentskills-index.json protocol
- [ ] Private tools automatically run in sandbox
- [ ] Security scanning blocks malicious skills
- [ ] Import approval workflow functional
- [ ] Full observability in Dashboard and Mission Control
- [ ] Extensible adapter architecture for v1.5 sources

#### Estimated Effort
1 Phase (6 weeks)

---

### 6. Keycloak SSO Hardening

**Status:** ✅ COMPLETED  
**Source:** STATE.md Pending Todos (TECH-DEBT)  
**Priority:** High  
**Target:** v1.4  
**Type:** Bug Fix  
**Design Doc:** [docs/enhancement/keycloak-sso-hardening/00-specification.md](./keycloak-sso-hardening/00-specification.md)  

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

### Completed ✅ (11)
1. ✅ Runtime Permission Approval (HITL)
2. ✅ Admin Console LLM Configuration (Pluggable module architecture)
3. ✅ Admin Registry Edit UI
4. ✅ Advanced User & Group Management
5. ✅ Universal Skill Import System (GitHub + ZIP + Adapters)
6. ✅ Keycloak SSO Hardening (Critical stability fix)
7. ✅ Analytics & Observability Dashboard
8. ✅ User Experience Enhancement (UI Theme + User Profile)
9. ✅ AgentOS Dashboard & Mission Control
10. ✅ Scheduler Engine & UI
11. ✅ Multi-Agent Tab Architecture (Artifact Creation)

### High Priority (v1.4 Must-Have)
*All high priority topics completed*

### Medium Priority (v1.4 Should-Have)
*All v1.4 medium priority topics completed or reassigned*

### Low Priority (v1.5)
1. Runtime Multi-Agent Orchestration (LangGraph Extension) - Topic #9
    - Extend existing LangGraph workflow system
    - Rich agent nodes, team templates, shared memory
    - Leverages canvas builder and checkpointing

### Future / v1.6+
1. WhatsApp Business API Integration (Channel expansion)
    - Requires Meta Business verification (1-4 weeks lead time)
    - Complex message templates and compliance requirements
    - Deferred due to verification complexity and resource prioritization
2. HashiCorp Vault Integration (Enterprise feature)
3. Advanced Multi-Agent Orchestrator (Custom) - Option A
    - Research-grade multi-agent capabilities
    - Custom orchestrator with message bus
    - Dynamic runtime agent spawning
    - Maximum flexibility for complex patterns

### v1.7+ Topics (New Enhancement Topics)
4. **Email System & Channel Notifications** (#18)
    - Email as a first-class channel alongside Telegram/WhatsApp
    - System notifications via channel infrastructure
    - Email settings management UI
    - SMTP/IMAP configuration
    - Notification templates and preferences

5. **Storage Service** (#19)
    - Unified storage abstraction layer
    - MinIO integration (S3-compatible)
    - File upload/download capabilities
    - Storage quotas and access control
    - Support for documents, images, attachments

6. **Projects/Spaces** (#20)
    - Organizational workspaces for grouping resources
    - Project-scoped agents, workflows, and memory
    - Team collaboration within spaces
    - Resource isolation and permissions
    - Project-level analytics and quotas

7. **Universal Integration** (#21)
    - Generic adapter framework for external systems
    - Webhook-based integrations
    - REST API connector builder
    - OAuth flow management
    - Integration marketplace/catalog

8. **MCP Server Creation Skill** (#22)
    - Skill for creating new MCP servers via natural language
    - Auto-generate MCP server scaffolding
    - Tool discovery and binding
    - Server testing and validation
    - Deployment automation

9. **Plugin Templates** (#23)
    - Pre-built plugin templates for common patterns
    - Template marketplace
    - Custom template creation
    - Template versioning and updates
    - One-click plugin generation from templates

10. **Third-Party Apps UI** (#24)
    - Dynamic UI generation for external apps
    - CopilotKit integration for app interactions
    - AG-UI components for app interfaces
    - A2UI envelopes for rich app experiences
    - App store/catalog for 3rd party integrations
4. **Email System & Channel Notifications** (#18)
    - Email as a first-class channel alongside Telegram/WhatsApp
    - System notifications via channel infrastructure
    - Email settings management UI
    - SMTP/IMAP configuration
    - Notification templates and preferences

5. **Storage Service** (#19)
    - Unified storage abstraction layer
    - MinIO integration (S3-compatible)
    - File upload/download capabilities
    - Storage quotas and access control
    - Support for documents, images, attachments

6. **Projects/Spaces** (#20)
    - Organizational workspaces for grouping resources
    - Project-scoped agents, workflows, and memory
    - Team collaboration within spaces
    - Resource isolation and permissions
    - Project-level analytics and quotas

7. **Universal Integration** (#21)
    - Generic adapter framework for external systems
    - Webhook-based integrations
    - REST API connector builder
    - OAuth flow management
    - Integration marketplace/catalog

8. **MCP Server Creation Skill** (#22)
    - Skill for creating new MCP servers via natural language
    - Auto-generate MCP server scaffolding
    - Tool discovery and binding
    - Server testing and validation
    - Deployment automation

9. **Plugin Templates** (#23)
    - Pre-built plugin templates for common patterns
    - Template marketplace
    - Custom template creation
    - Template versioning and updates
    - One-click plugin generation from templates

10. **Third-Party Apps UI** (#24)
    - Dynamic UI generation for external apps
    - CopilotKit integration for app interactions
    - AG-UI components for app interfaces
    - A2UI envelopes for rich app experiences
    - App store/catalog for 3rd party integrations

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
- #2 WhatsApp Business API Integration (Medium) - Moved to v1.6+
- #5 GitHub Repository Skill Sources (Medium) - Now #5 Universal Skill Import ✅
- #9 HashiCorp Vault Integration (Low)
- #10 Multi-Agent Orchestration (Low) - Now #9 In Progress

---

**Next Recommended Topic:** Topic #9 Runtime Multi-Agent Orchestration — LangGraph Extension

**Alternatives:**
- Start implementation planning for completed topics (11 topics ready)
- Brainstorm additional v1.5 features
- Review WhatsApp Business API requirements for v1.6+ planning

---

## 🆕 NEW TOPIC ADDED (Multi-Agent Tab Architecture)

**Session Date:** 2026-03-14  
**Topic:** #16 Multi-Agent Tab Architecture  
**Status:** ✅ COMPLETED - Design document already exists

**Problem Statement:**
Artifact creation wizard (`/admin/create`) suffers from context pollution - skill creation conversations become cluttered with tool/MCP implementation details. UI state bugs when switching artifact types. No parallel creation of multiple dependencies.

**Solution:**
Multi-agent tab architecture that spawns separate agent instances in new UI tabs for tool/MCP creation:
- Context isolation between artifact types (skill vs tool vs MCP)
- Enables parallel dependency creation
- Database-backed dependency tracking
- Visual status indicators and seamless navigation

**Key Components:**
1. **TabManager** (`useAgentTabs` hook) - Manage multiple agent tabs
2. **Agent Dependencies** - Database table tracking parent-child relationships
3. **Separate CopilotKit Instances** - True context isolation per tab
4. **Tool/MCP Builder Agents** - Dedicated agents for artifact types
5. **Dependency Notifications** - Status updates between tabs

**Architecture:**
```
User creates skill requiring tools [email-fetch, slack-send]
         ↓
Skill Agent detects missing tools
         ↓
UI shows: "Tools needed: email-fetch, slack-send"
         ↓
User clicks "Create email-fetch tool"
         ↓
NEW TAB SPAWNS with Tool Builder Agent
  ┌─────────────────────────────────────┐
  │ Tool Form       │ Tool Agent Chat   │
  │ - handler_code  │ (isolated context)│
  └─────────────────────────────────────┘
         ↓
Tool created → Dependency service notifies parent → Status updated
```

**Benefits:**
- ✅ Fixes context pollution - each agent has clean slate
- ✅ Enables parallel work - multiple dependencies created simultaneously
- ✅ Clear navigation - Tabbed interface shows all active creations
- ✅ Status visibility - Visual indicators (✅ ⚠️ 🔄) on each tab
- ✅ Resume capability - Database tracking allows session recovery

**Effort:** 10-13 hours  
**Priority:** High (addresses critical UX issues)  
**Target:** v1.4  
**Rationale:** Fixes critical UX issues in artifact creation; enables efficient skill development workflow

**Design Doc:** [docs/enhancement/multi-agent-tab-architecture/00-specification.md](./multi-agent-tab-architecture/00-specification.md)

---

### 📁 Files Modified This Session (Session 6 - Skill Import Brainstorming)

- `docs/plans/2026-03-14-universal-skill-import-design.md` (NEW)
- `docs/enhancement/multi-agent-tab-architecture/00-specification.md` (MOVED to subfolder)
- `docs/enhancement/BRAINSTORMING-TRACKING.md` (UPDATED)

**Design Docs Moved:**
- `docs/enhancements/multi-agent-tab-architecture.md` → `docs/enhancement/multi-agent-tab-architecture/00-specification.md` (standardized structure)

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*

---

## 🆕 NEW TOPICS ADDED (Session 2026-03-17)

**7 New Enhancement Topics Added:**

| # | Topic | Priority | Target | Brief Description |
|---|-------|----------|--------|-------------------|
| 18 | Email System & Channel Notifications | Medium | v1.7+ | Email as first-class channel, system notifications via channels |
| 19 | Storage Service | High | v1.7+ | Unified storage abstraction with MinIO/S3 support |
| 20 | Projects/Spaces | High | v1.7+ | Organizational workspaces for team collaboration |
| 21 | Universal Integration | Medium | v1.7+ | Generic adapter framework for external systems |
| 22 | MCP Server Creation Skill | Medium | v1.7+ | Natural language skill to auto-generate MCP servers |
| 23 | Plugin Templates | Low | v1.7+ | Pre-built templates for common plugin patterns |
| 24 | Third-Party Apps UI | Medium | v1.7+ | Dynamic UI generation using CopilotKit/AG-UI/A2UI |

**Updated Statistics:**
- ✅ Completed: 11 topics
- 🔵 In-Progress: 1 topic (#9)
- 🟡 Pending: 9 topics (new v1.7+ topics)
- 🟡 Future: 3 topics (v1.6+)
- **Total Topics: 24**

**Recommended Next Topics (Priority Order):**
1. **Topic #19: Storage Service** (High priority, foundational for avatars, files)
2. **Topic #20: Projects/Spaces** (High priority, organizational structure)
3. **Topic #9: Runtime Multi-Agent Orchestration** (Complete detailed design)

**Ready for Deep-Dive Brainstorming:**
All 7 new topics are documented and ready for detailed design discussions. User can go through each topic to explore requirements, constraints, and architecture decisions.

---

