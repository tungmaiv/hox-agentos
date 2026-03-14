# Brainstorming Tracking Document

**Project:** Blitz AgentOS  
**Milestone:** v1.4 Planning  
**Created:** 2026-03-14  
**Last Updated:** 2026-03-14  

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
| 4 | Admin Console LLM Configuration | 🟡 PENDING | High | v1.4 | 0.5 Phase |
| 5 | GitHub Repository Skill Sources | 🟡 PENDING | Medium | v1.4 | 0.5 Phase |
| 6 | Admin Registry Edit UI (expanded from SWR) | ✅ COMPLETED | High | v1.4 | 0.5-1 Phase |
| 7 | Keycloak SSO Hardening | 🟡 PENDING | High | v1.4 | 0.5 Phase |
| 8 | Analytics & Observability Dashboard | 🟡 PENDING | Medium | v1.4 | 1 Phase |
| 9 | Multi-Agent Orchestration | 🟡 PENDING | Low | v1.5 | 2 Phases |
| 12 | Advanced User & Group Management | ✅ COMPLETED | High | v1.4 | 1 Phase |

---

## Completed Topics

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

### High Priority (v1.4 Must-Have)
4. Keycloak SSO Hardening (Stability)
5. Admin Console LLM Configuration (Ops improvement)

### Medium Priority (v1.4 Should-Have)
6. WhatsApp Business API Integration (Channel expansion)
7. GitHub Repository Skill Sources (Developer experience)
8. Analytics & Observability Dashboard (Ops visibility)

### Low Priority (Post-v1.4)
9. HashiCorp Vault Integration (Enterprise feature)
10. Multi-Agent Orchestration (v1.5 vision)

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

**Next Recommended Topic:** Keycloak SSO Hardening — Critical stability fix

**Alternative:** Admin Console LLM Configuration — High ops value, medium effort

**Quick Win:** GitHub Repository Skill Sources — Developer experience improvement

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*
