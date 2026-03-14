# Brainstorming Master Index

## Quick Stats

- **Total Topics:** 24
- **✅ Completed:** 16 topics (with full design documents)
- **🔵 In-Progress:** 1 topic (design partial, needs completion)
- **🟡 Pending:** 2 topics (ready for brainstorming)
- **🟡 Future:** 3 topics (deferred to v1.6+)

---

## 🔄 SESSION HANDOVER

### Current Session: Ready to Start

**Session Date:** [TO BE FILLED]

**Previous Session: Session 10 (2026-03-17) ✅ COMPLETED - MOST RECENT**

**Topics Completed in Session 10:**
- Topic #22: MCP Server Creation Skill ✅
  - Natural language to MCP server generation
  - OpenAPI and GraphQL parser with auto-detection
  - AI semantic enrichment with external Markdown prompts
  - Interactive UI for tool refinement
  - Jinja2 templates for code generation
  - Dual output: downloadable code + runtime adapter
  - Three deployment modes: local, Docker, external
  - Builds on Topic #21 Universal Integration Framework

**Key Decisions in Session 10:**
- Hybrid approach: Structural parsing + LLM semantic enrichment
- External prompt files (Markdown) for maintainability and hot-reload
- Jinja2 templates for Python MCP server generation
- Support both MCP servers and CLI-Anything configuration
- Integration with Topic #21 IntegrationRegistry
- Three deployment modes for different use cases
- 10-week implementation plan (7 phases)

**Files Created in Session 10:**
- `docs/enhancement/topics/22-mcp-server-creation-skill/00-specification.md` (COMPREHENSIVE DESIGN - 12 SECTIONS, ~1800 lines)

---

### Session History Summary

**Recently Completed Topics:**
- Session 10: Topic #22 (MCP Server Creation Skill)
- Session 9: Topic #21 (Universal Integration)
- Session 8: Topic #20 (Projects/Spaces)
- Session 7: Topic #18 (Email System)

**Key Resolutions:**
- ✅ MCP vs CLI-Anything discussion RESOLVED in Topic #21
  - Hybrid architecture: MCP for custom tools, CLI-Anything for existing software
  - Saved context: `docs/enhancement/mcp-vs-cli-anything-evaluation.md`

**Files Created This Session:**
- `docs/enhancement/topics/20-projects-spaces/00-specification.md` (COMPREHENSIVE DESIGN - 9 SECTIONS)
- `docs/plans/2026-03-17-projects-spaces.md` (IMPLEMENTATION PLAN - 26 TASKS, 5 PHASES)

**Files Modified This Session:**
- `docs/enhancement/BRAINSTORMING-MASTER.md` (UPDATED)
- `docs/enhancement/BRAINSTORMING-INDEX.md` (UPDATED)

**Git Commits:**
- `91f929d`: docs: complete topic #20 design - Projects/Spaces
- `8d8ee95`: docs(20): add implementation plan for Projects/Spaces
- `06d846f`: docs(21): complete Universal Integration design
- `1de8a12`: docs(22): complete MCP Server Creation Skill design

---

### 📋 QUICK NAVIGATION

**For overview:** `docs/enhancement/BRAINSTORMING-MASTER.md`
- Quick stats, completed table, milestones, session handovers

**For search:** `docs/enhancement/BRAINSTORMING-INDEX.md`
- Searchable by status, milestone, topic number

**For detailed designs:** `docs/enhancement/topics/{topic-name}/`
- Individual topic folders with design documents

---

### 🚀 RECOMMENDED NEXT STEPS

**Option A: Continue Brainstorming**
1. **Topic #9:** Runtime Multi-Agent Orchestration — Complete detailed design
    - LangGraph Extension architecture already decided
    - Needs detailed design for multi-agent coordination

2. **Topic #22:** MCP Server Creation Skill — Medium priority
    - Natural language skill to auto-generate MCP servers
    - Builds on Universal Integration framework

3. **Topic #24:** Third-Party Apps UI — Medium priority
    - Dynamic UI generation using CopilotKit/AG-UI/A2UI

**Option B: Start Implementation Planning**
- Use `/gsd:plan-phase` to create implementation plans
- 15 topics ready for implementation (all completed designs):
  - v1.4: Topics #1, #4-8, #12-16 (11 topics)
  - v1.7+: Topics #18-21 (4 topics)
- Implementation plans created for Topics #19, #20

**Option C: Plan v1.7+ Topics**
- Brainstorm additional v1.7+ features
- Review WhatsApp Business API requirements for v1.6+ planning

---

---

*Last Updated: 2026-03-17*

**Previous Session: Session 7 (2026-03-17) ✅ COMPLETED

**Topics Completed This Session:**
- Topic #18: Email System & Channel Notifications ✅

**Key Decisions:**
- Sidecar pattern for email adapter
- Hybrid authentication (OAuth + IMAP/SMTP)
- Centralized NotificationService for 8 notification types
- System-wide email settings (admin-enforced SMTP)
- UserCredential table for encrypted storage (AES-256-GCM)
- 7 implementation phases (foundation → sidecar → templates → linking → inbound → events → monitoring)

**Files Created This Session:**
- `docs/enhancement/topics/18-email-system-channel-notifications/00-specification.md` (COMPREHENSIVE DESIGN - 14 SECTIONS)
- `docs/enhancement/BRAINSTORMING-MASTER.md` (UPDATED)
- `docs/enhancement/BRAINSTORMING-INDEX.md` (UPDATED)
- `docs/enhancement/BRAINSTORMING-TRACKING-ARCHIVE.md` (ARCHIVED)

**Files Modified This Session:**
- `docs/enhancement/BRAINSTORMING-TRACKING.md` → `docs/enhancement/BRAINSTORMING-TRACKING-ARCHIVE.md` (moved)
- Removed 11 empty enhancement directories
- Moved 11 completed design docs to `topics/` folders
- Created 3 new index/overview files

**Git Commits:**
- `a7a4f10 refactor: shard BRAINSTORMING-TRACKING.md into topic folders`
- `c70e5ae refactor: remove empty enhancement directories`

**Structure Changes:**
- Sharded 2090-line tracking file → topic folders (94% line reduction)
- Created searchable INDEX.md (132 lines)
- Created overview-only MASTER.md (115 lines)
- Each topic now has its own folder with design doc

**Ready for New Session:**
- All context preserved in MASTER.md and INDEX.md
- Old tracking archived (no data loss)
- 11 completed design docs accessible in `topics/` folders
- System ready for next topic brainstorming

### 🆕 NEW SESSION: Ready to Start

**Current Status:**
- **12 Topics** ✅ COMPLETED with design documents
- **1 Topic** 🔵 IN-PROGRESS (Topic #9 - needs detailed design)
- **8 Topics** 🟡 PENDING
- **3 Topics** 🟡 FUTURE (v1.6+)

**Ready for New Topic Brainstorming**
All topics are documented and ready for detailed design discussions. User can go through each topic to explore requirements, constraints, and architecture decisions.

**Recommended Next Topics (Priority Order):**
1. **Topic #9:** Runtime Multi-Agent Orchestration — LangGraph Extension (Complete detailed design)
2. **Topic #19:** Storage Service — High priority, foundational
3. **Topic #20:** Projects/Spaces — High priority, organizational

**Alternative:**
- Start implementation planning for completed topics (12 topics ready)

---



## Quick Stats

- **Total Topics:** 24
- **✅ Completed:** 17 topics (with full design documents)
- **🔵 In-Progress:** 1 topic (design partial, needs completion)
- **🟡 Pending:** 1 topic (ready for brainstorming)
- **🟡 Future:** 3 topics (deferred to v1.6+)

---

## Completed Topics (Design Documents Ready)

| # | Topic | Design Doc | Target | Status |
|---|-------|-------------|---------|--------|
| 1 | Runtime Permission Approval (HITL) | [specification](./topics/01-runtime-permission-approval/00-specification.md) | v1.4 | ✅ Complete |
| 4 | Admin Console LLM Configuration | [specification](./topics/04-admin-console-llm-config/00-specification.md) | v1.4 | ✅ Complete |
| 5 | Universal Skill Import System | [specification](./topics/05-universal-skill-import/00-specification.md) | v1.4 | ✅ Complete |
| 6 | Admin Registry Edit UI | [specification](./topics/06-admin-registry-edit-ui/00-specification.md) | v1.4 | ✅ Complete |
| 7 | Keycloak SSO Hardening | [specification](./topics/07-keycloak-sso-hardening/00-specification.md) | v1.4 | ✅ Complete |
| 8 | Analytics & Observability Dashboard | [specification](./topics/08-analytics-observability-dashboard/00-specification.md) | v1.4 | ✅ Complete |
| 12 | Advanced User & Group Management | [specification](./topics/12-advanced-user-group-management/00-specification.md) | v1.4 | ✅ Complete |
| 13 | User Experience Enhancement | [specification](./topics/13-user-experience-enhancement/00-specification.md) | v1.4 | ✅ Complete |
| 14 | AgentOS Dashboard & Mission Control | [specification](./topics/14-agentos-dashboard-mission-control/00-specification.md) | v1.4 | ✅ Complete |
| 15 | Scheduler Engine & UI | [specification](./topics/15-scheduler-engine-ui/00-specification.md) | v1.4 | ✅ Complete |
| 16 | Multi-Agent Tab Architecture | [specification](./topics/16-multi-agent-tab-architecture/00-specification.md) | v1.4 | ✅ Complete |
| 18 | Email System & Channel Notifications | [specification](./topics/18-email-system-channel-notifications/00-specification.md) | v1.7+ | ✅ Complete |
| 19 | Storage Service | [specification](./topics/19-storage-service/00-specification.md) | v1.7+ | ✅ Complete |
| 20 | Projects/Spaces | [specification](./topics/20-projects-spaces/00-specification.md) | v1.7+ | ✅ Complete |
| 21 | Universal Integration | [specification](./topics/21-universal-integration/00-specification.md) | v1.7+ | ✅ Complete |
| 22 | MCP Server Creation Skill | [specification](./topics/22-mcp-server-creation-skill/00-specification.md) | v1.7+ | ✅ Complete |
| 23 | Plugin Templates | [specification](./topics/23-plugin-templates/00-specification.md) | v1.7+ | ✅ Complete |

---

## In-Progress Topics

| # | Topic | Design Doc | Target | Status |
|---|-------|-------------|---------|--------|
| 9 | Runtime Multi-Agent Orchestration (LangGraph Extension) | [specification](./topics/09-runtime-multi-agent-orchestration/00-specification.md) | v1.5 | 🔵 Architecture decision made, detailed design needed |

---

## Pending Topics (Ready for Brainstorming)

| # | Topic | Priority | Target | Description |
|---|-------|----------|---------|-------------|
| 24 | Third-Party Apps UI | Medium | v1.7+ | Dynamic UI generation using CopilotKit/AG-UI/A2UI |

---

## Future Topics (v1.6+)

| # | Topic | Priority | Target | Description |
|---|-------|----------|---------|-------------|
| 2 | WhatsApp Business API Integration | Medium | v1.6+ | Channel expansion (requires Meta verification) |
| 3 | HashiCorp Vault Integration | Low | Post-MVP | Enterprise secret management (replaces AES-256 DB) |
| 17 | Advanced Multi-Agent Orchestrator (Custom) | Low | v1.6+ | Research-grade multi-agent capabilities (custom orchestrator) |

---

## By Milestone

### v1.4 Topics (11 completed, 0 pending)
- 01, 04, 05, 06, 07, 08, 12, 13, 14, 15, 16

### v1.5 Topics (1 in-progress)
- 09: Runtime Multi-Agent Orchestration (LangGraph Extension) - Architecture decision made, needs detailed design

### v1.7+ Topics (6 completed, 1 pending)
- 18: Email System & Channel Notifications ✅ Complete
- 19: Storage Service ✅ Complete
- 20: Projects/Spaces ✅ Complete
- 21: Universal Integration ✅ Complete
- 22: MCP Server Creation Skill ✅ Complete
- 23: Plugin Templates ✅ Complete
- 24: Third-Party Apps UI

### v1.6+ Topics (0 completed, 3 pending)
- 02: WhatsApp Business API Integration
- 03: HashiCorp Vault Integration
- 17: Advanced Multi-Agent Orchestrator (Custom)

---

## Recent Sessions

### Session 10 (2026-03-17): MCP Server Creation Skill ✅
- **Topic #22:** MCP Server Creation Skill
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/22-mcp-server-creation-skill/00-specification.md)
- **Key Decisions:**
  - Hybrid approach: Structural parsing + LLM semantic enrichment
  - External prompt files (Markdown) for maintainability and hot-reload
  - Jinja2 templates for Python MCP server generation
  - Support both MCP servers and CLI-Anything configuration
  - Integration with Topic #21 IntegrationRegistry
  - Three deployment modes: local runtime, Docker container, external hosting
  - 10-week implementation plan (7 phases)
- **Features:**
  - Natural language input to MCP server generation
  - OpenAPI 3.x and GraphQL introspection support
  - AI-powered semantic enrichment with LLM
  - Interactive UI for tool selection and refinement
  - Dual output: downloadable code package + immediate runtime adapter

### Session 11 (2026-03-15): Plugin Templates ✅
- **Topic #23:** Plugin Templates
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/23-plugin-templates/00-specification.md)
- **Key Decisions:**
  - Template-Aware Entities architecture with full lineage tracking
  - ZIP-based template format with JSON manifests
  - Self-Service + Admin Override deployment model
  - 10-agent comprehensive marketing template
  - Template Gallery for user discovery and subscription
- **Features:**
  - Import/export ZIP-based templates
  - 10 specialized marketing agents (Content Strategist, SEO Analyst, Social Media Manager, etc.)
  - Self-service template gallery for users
  - Admin deployment with user assignment
  - Template origin tracking for all entities
  - 10-week implementation plan (6 phases)

### Session 10 (2026-03-17): MCP Server Creation Skill ✅
- **Topic #22:** MCP Server Creation Skill
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/22-mcp-server-creation-skill/00-specification.md)
- **Key Decisions:**
  - Hybrid approach: Structural parsing + LLM semantic enrichment
  - External prompt files (Markdown) for maintainability and hot-reload
  - Jinja2 templates for Python MCP server generation
  - Support both MCP servers and CLI-Anything configuration
  - Integration with Topic #21 IntegrationRegistry
  - Three deployment modes for different use cases
  - 10-week implementation plan (7 phases)
- **Features:** Natural language input, OpenAPI/GraphQL parsers, AI enrichment, interactive UI

### Session 9 (2026-03-17): Universal Integration ✅
- **Topic #21:** Universal Integration
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/21-universal-integration/00-specification.md)
- **Key Decisions:**
  - Adapter Protocol: Abstract base class with Pydantic models
  - Unified Security: SecureAdapterWrapper applies RBAC + ACL to ALL adapters
  - CLI-Anything: Line-by-line streaming with `--stream-prefix` support
  - Webhook Security: HMAC-SHA256 primary, JWT optional
  - REST/OpenAPI: Hybrid architecture (BaseHTTPAdapter + OpenAPIAdapter + RESTAdapter)
  - Plugin SDK: Python entry points for third-party discovery
  - Modular design: Separate `integrations/` module from core AgentOS
- **Resolves:** Deferred MCP vs CLI-Anything discussion

### Session 8 (2026-03-17): Projects/Spaces ✅
- **Topic #20:** Projects/Spaces
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/20-projects-spaces/00-specification.md)
- **Key Decisions:**
  - Unified Project Model (Approach A): Single `projects` table with nullable `workspace_id`
  - NotebookLM features: Notes, files, markdown, chat with sources, AI insights
  - Granular permission model: view, edit, full (Option B)
  - Opt-in public visibility: Owner marks project as public for workspace members
  - Personal projects can be shared to workspaces (no copy, remains personal)
  - Archive: Complete freeze (no access except restore)
  - Backup/Restore: ZIP format, auto-rename on conflict

### Session 7 (2026-03-17): Email System ✅
- **Topic #18:** Email System & Channel Notifications
- **Status:** ✅ Completed
- **Design Doc:** [00-specification.md](./topics/18-email-system-channel-notifications/00-specification.md)
- **Key Decisions:** Sidecar pattern, hybrid auth, centralized notification routing, system SMTP enforced

### Session 6 (2026-03-14): Universal Skill Import + Multi-Agent Tab ✅
- **Topic #5:** Universal Skill Import System
- **Topic #16:** Multi-Agent Tab Architecture
- **Status:** Both ✅ Completed

---

## Quick Navigation

**For detailed design documents:** See [INDEX.md](./INDEX.md) - fully searchable topic index

**For planning/implementation:** See individual topic folders under `topics/`

**Next Recommended Topics (Priority Order):**
1. **Topic #9:** Runtime Multi-Agent Orchestration - Complete detailed design
2. **Topic #24:** Third-Party Apps UI - Medium priority, dynamic UI generation
3. **Topic #23:** Plugin Templates - Low priority, pre-built templates

**Implementation Ready:**
16 topics have complete designs and are ready for implementation:
- v1.4: Topics #1, #4-8, #12-16 (11 topics)
- v1.7+: Topics #18-22 (5 topics)

---

*Last Updated: 2026-03-17*
