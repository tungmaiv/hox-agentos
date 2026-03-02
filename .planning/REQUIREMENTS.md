# Requirements: Blitz AgentOS v1.2

**Defined:** 2026-03-02
**Core Value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.

## v1.2 Requirements

### Admin

- [ ] **ADMIN-01**: Admin can manage all artifacts (agents, tools, skills, MCP servers) from /admin only — admin features removed from /settings
- [ ] **ADMIN-02**: User can create an artifact using a guided creation wizard (choose type → fill form with inline validation → preview JSON → submit)
- [ ] **ADMIN-03**: User can pick from starter templates when creating a new artifact
- [ ] **ADMIN-04**: User sees live name availability check while typing artifact name in creation form
- [ ] **ADMIN-05**: User can select required permissions from a dropdown (not free-text input) when creating tools or skills
- [ ] **ADMIN-06**: User can clone an existing artifact to use as a starting point for a new version

### Auth

- [ ] **AUTH-01**: Admin can create, edit, and delete local user accounts (username/password)
- [ ] **AUTH-02**: Admin can create and manage local groups and assign users to groups
- [ ] **AUTH-03**: Admin can assign roles to local users and groups
- [ ] **AUTH-04**: User can sign in with local username/password credentials (parallel to Keycloak SSO login)
- [ ] **AUTH-05**: Local auth issues JWTs with same claims structure as Keycloak (roles, user_id) so RBAC and Tool ACL work identically for local and SSO users

### Ecosystem

- [ ] **ECO-01**: Agent or user can query `system.capabilities` tool to list all registered agents, tools, skills, and MCP servers with descriptions
- [ ] **ECO-02**: User can run `api-to-mcp` skill: provide an app URL, have AgentOS fetch the OpenAPI spec, select endpoints to expose, and generate + register an MCP server
- [ ] **ECO-03**: Admin can add and remove external skill/tool repositories by URL
- [ ] **ECO-04**: User can search and browse skills/tools from registered external repositories inside AgentOS
- [ ] **ECO-05**: User can import a skill or tool from an external repository into AgentOS (imported artifact enters security review flow before activation)
- [ ] **ECO-06**: AgentOS skill definitions can be exported in agentskills.io-compliant manifest format

### Infrastructure

- [x] **INFRA-01**: Webhook endpoints for Telegram, WhatsApp, and MS Teams are exposed via Cloudflare Tunnel (replacing ngrok)
- [x] **INFRA-02**: Cloudflare Tunnel runs as a Docker Compose service with tunnel token stored in .env
- [x] **INFRA-03**: All LLM system prompts are stored as .md files in backend/prompts/ — no inline prompt strings in Python files
- [x] **INFRA-04**: `PromptLoader` utility in backend/core/prompts.py provides `load_prompt(name, **vars)` with variable substitution and in-memory caching

### Tech Debt

- [x] **DEBT-01**: `classify_intent()` function in router.py is removed or properly wired — no orphaned dead code

## v1.3 Requirements (Deferred)

### Channels

- **CHAN-01**: WhatsApp Business live end-to-end (pending Meta Business API verification)
- **CHAN-02**: MS Teams live end-to-end (pending Azure Bot Service registration)

### Ecosystem (stretch)

- **ECO-07**: AgentOS skill can be published to external agentskills.io registry from /admin
- **ECO-08**: Skill/tool repository auto-sync via Celery scheduled task

## Out of Scope

| Feature | Reason |
|---------|--------|
| Kubernetes deployment | Docker Compose only for MVP; K8s is post-MVP |
| HashiCorp Vault | AES-256 DB encryption sufficient at ~100 user scale |
| Mobile native apps | Web-first; mobile apps post-MVP |
| SaaS/cloud hosting | Enterprise on-premise requirement |
| Real-time collaborative canvas editing | Single-user editing for MVP |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADMIN-01 | Phase 12 | Pending |
| ADMIN-02 | Phase 12 | Pending |
| ADMIN-03 | Phase 12 | Pending |
| ADMIN-04 | Phase 12 | Pending |
| ADMIN-05 | Phase 12 | Pending |
| ADMIN-06 | Phase 12 | Pending |
| AUTH-01 | Phase 13 | Pending |
| AUTH-02 | Phase 13 | Pending |
| AUTH-03 | Phase 13 | Pending |
| AUTH-04 | Phase 13 | Pending |
| AUTH-05 | Phase 13 | Pending |
| ECO-01 | Phase 14 | Pending |
| ECO-02 | Phase 14 | Pending |
| ECO-03 | Phase 14 | Pending |
| ECO-04 | Phase 14 | Pending |
| ECO-05 | Phase 14 | Pending |
| ECO-06 | Phase 14 | Pending |
| INFRA-01 | Phase 11 | Complete |
| INFRA-02 | Phase 11 | Complete |
| INFRA-03 | Phase 11 | Complete |
| INFRA-04 | Phase 11 | Complete |
| DEBT-01 | Phase 11 | Complete |

**Coverage:**
- v1.2 requirements: 22 total
- Mapped to phases: 22 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-02*
*Last updated: 2026-03-02 — traceability populated after roadmap creation*
