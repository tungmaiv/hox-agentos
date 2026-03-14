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
| 6 | Frontend Build Optimization (SWR) | 🟡 PENDING | High | v1.4 | Quick Fix |
| 7 | Keycloak SSO Hardening | 🟡 PENDING | High | v1.4 | 0.5 Phase |
| 8 | Analytics & Observability Dashboard | 🟡 PENDING | Medium | v1.4 | 1 Phase |
| 9 | Multi-Agent Orchestration | 🟡 PENDING | Low | v1.5 | 2 Phases |

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

## Pending Topics

### 2. WhatsApp Business API Integration

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

### 3. HashiCorp Vault Integration

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

### 4. Admin Console LLM Configuration

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

### 6. Frontend Build Optimization (SWR in Server Components)

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos (TECH-DEBT)  
**Priority:** High  
**Target:** v1.4  
**Type:** Bug Fix  

#### Brief Description
Fix SWR hooks causing prerender crashes on settings pages (`/settings/integrations`, `/settings/memory`). Error: SWR context undefined during static export.

#### Root Cause
SWR hooks destructure (`const { data } = useSWR(...)`) runs during static export where SWR context is undefined.

#### Current State
- `pnpm build` fails on affected pages
- Workaround: manual build skip

#### Target State
- Add `"use client"` directive to affected pages, OR
- Move SWR calls into client sub-components
- Clean build without errors

#### Estimated Effort
Quick Fix (1-2 hours)

---

### 7. Keycloak SSO Hardening

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

### 8. Analytics & Observability Dashboard

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

### 9. Multi-Agent Orchestration

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

### 10. CREDENTIAL_ENCRYPTION_KEY Production Setup

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Critical (Pre-production)  
**Target:** Before v1.4 production deploy  

**Description:** Add `CREDENTIAL_ENCRYPTION_KEY` to production `.env` before OAuth flows. Currently using dev key.

---

### 11. LLM Model Switch Back to qwen3.5:cloud

**Status:** 🟡 PENDING  
**Source:** STATE.md Pending Todos  
**Priority:** Low  
**Target:** When Ollama limit resets  

**Description:** Currently using `qwen2.5:7b` local due to weekly Ollama limit. Switch back to `qwen3.5:cloud` when reset.

---

## Topic Selection Guide

When starting next brainstorming session, consider:

### High Priority (v1.4 Must-Have)
1. ✅ Runtime Permission Approval (DONE)
2. Frontend Build Optimization (Quick win)
3. Keycloak SSO Hardening (Stability)
4. Admin Console LLM Configuration (Ops improvement)

### Medium Priority (v1.4 Should-Have)
5. WhatsApp Business API Integration (Channel expansion)
6. GitHub Repository Skill Sources (Developer experience)
7. Analytics & Observability Dashboard (Ops visibility)

### Low Priority (Post-v1.4)
8. HashiCorp Vault Integration (Enterprise feature)
9. Multi-Agent Orchestration (v1.5 vision)

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

**Next Recommended Topic:** Frontend Build Optimization (SWR) — Quick win, high impact, minimal effort

**Alternative:** Admin Console LLM Configuration — High ops value, medium effort

---

*This document is a living artifact. Update it continuously as brainstorming progresses.*
