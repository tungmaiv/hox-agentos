# Roadmap: Blitz AgentOS

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3.1 (shipped 2026-02-26)
- ✅ **v1.1 Enterprise Platform** — Phases 4–10 (shipped 2026-03-02)
- 🚧 **v1.2 Developer Experience** — Phases 11–14 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–3.1) — SHIPPED 2026-02-26</summary>

- [x] **Phase 1: Identity and Infrastructure Skeleton** — 4/4 plans (completed 2026-02-24)
- [x] **Phase 2: Agent Core and Conversational Chat** — 5/5 plans (completed 2026-02-25)
- [x] **Phase 2.1: Tech Debt Cleanup** (INSERTED) — 1/1 plan (completed 2026-02-26)
- [x] **Phase 3: Sub-Agents, Memory, and Integrations** — 6/6 plans (completed 2026-02-26)
- [x] **Phase 3.1: Memory Read Path & MCP Hot-Registration** (INSERTED) — 1/1 plan (completed 2026-02-26)

Full phase details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Enterprise Platform (Phases 4–10) — SHIPPED 2026-03-02</summary>

- [x] **Phase 4: Canvas and Workflows** — 5/5 plans (completed 2026-02-27)
- [x] **Phase 4.1: Phase 4 Polish** (INSERTED) — 1/1 plan (completed 2026-02-27)
- [x] **Phase 5: Scheduler and Channels** — 6/6 plans (completed 2026-02-28)
- [x] **Phase 5.1: Workflow Execution Wiring** (INSERTED) — 1/1 plan (completed 2026-02-28)
- [x] **Phase 6: Extensibility Registries** — 8/8 plans (completed 2026-03-01)
- [x] **Phase 7: Hardening and Sandboxing** — 4/4 plans (completed 2026-03-01)
- [x] **Phase 8: Observability** — 4/4 plans (completed 2026-03-01)
- [x] **Phase 9: Tech Debt Code Fixes** (INSERTED) — 2/2 plans (completed 2026-03-01)
- [x] **Phase 10: Optional Tech Debt Closure** (INSERTED) — 2/2 plans (completed 2026-03-02)

Full phase details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 Developer Experience (In Progress)

**Milestone Goal:** Make AgentOS easier to extend, explore, and operate — unified admin desk, guided artifact creation, capabilities introspection, API-to-MCP generation, external skill repositories, local auth, and infrastructure hardening.

- [x] **Phase 11: Infrastructure and Debt** — Cloudflare Tunnel, prompt externalization, dead code removal (completed 2026-03-02)
- [ ] **Phase 12: Unified Admin Desk** — Consolidate /settings into /admin, guided artifact creation wizard
- [ ] **Phase 13: Local Auth** — Local user/group management with dual auth (local + Keycloak)
- [ ] **Phase 14: Ecosystem Capabilities** — Capabilities tool, API-to-MCP generation, external skill repositories

## Phase Details

### Phase 11: Infrastructure and Debt
**Goal**: The platform's infrastructure foundation is hardened and the codebase is clean — webhooks route through a stable tunnel, all LLM prompts are externalized and editable without code changes, and orphaned dead code is gone.
**Depends on**: Phase 10 (v1.2 start)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, DEBT-01
**Success Criteria** (what must be TRUE):
  1. Telegram, WhatsApp, and MS Teams webhooks receive live traffic through Cloudflare Tunnel without ngrok — verified by checking the tunnel dashboard and a test Telegram message end-to-end
  2. Cloudflare Tunnel starts automatically as part of `docker compose up` with only a token in `.env` required
  3. All LLM system prompts can be found and edited in `backend/prompts/*.md` files — no inline prompt strings remain in Python files
  4. `PromptLoader.load_prompt("name", **vars)` returns the correct rendered string with variable substitution, and repeated calls return the cached value without re-reading disk
  5. `classify_intent()` no longer exists in `router.py` — grep returns no results and all 586+ tests still pass
**Plans**: 2 plans

Plans:
- [ ] 11-01-PLAN.md — PromptLoader + externalize all LLM prompts to backend/prompts/*.md
- [ ] 11-02-PLAN.md — Cloudflare Tunnel docs + delete classify_intent dead code + annotate _route_after_master

### Phase 12: Unified Admin Desk
**Goal**: All artifact management is consolidated at `/admin` — there is one place for admins to operate, and every artifact type can be created through a guided wizard that validates input, prevents name conflicts, and starts from templates or existing clones.
**Depends on**: Phase 11
**Requirements**: ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06
**Success Criteria** (what must be TRUE):
  1. Admin can reach every admin function (agents, tools, skills, MCP servers, permissions, credentials) from `/admin` — `/settings` contains no admin-only controls
  2. User can open a creation wizard, select an artifact type, fill a form with inline field validation, preview the generated JSON, and submit — the artifact appears in the registry without a page reload
  3. User can pick from at least one starter template per artifact type when starting the creation wizard — the form pre-fills with the template's values
  4. User sees a live "name available" / "name taken" indicator while typing the artifact name in the creation form — no round-trip submit needed to detect conflicts
  5. User selects required permissions from a dropdown list (not a free-text field) when creating a tool or skill
  6. User can clone an existing artifact — the creation wizard opens pre-filled with the source artifact's values, ready to save under a new name
**Plans**: 2 plans

Plans:
- [ ] 12-01-PLAN.md — Config + Credentials tabs added to /admin; Admin section removed from /settings
- [ ] 12-02-PLAN.md — Hybrid form wizard at /admin/create with fill_form AI tool, templates, name check, clone support

### Phase 13: Local Auth
**Goal**: Admins can manage local users and groups entirely within AgentOS, and employees can sign in with a local username/password as an alternative to Keycloak SSO — with identical RBAC and Tool ACL behavior for both auth paths.
**Depends on**: Phase 11
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05
**Success Criteria** (what must be TRUE):
  1. Admin can create, edit, and delete a local user account from the admin panel — the account appears in the user list immediately
  2. Admin can create a local group, assign users to it, and assign roles to the group — role assignments take effect on next login without restart
  3. User can sign in via a local username/password form on the login page (separate from the Keycloak SSO button) and reach the main chat UI
  4. A locally-authenticated user's JWT carries the same `roles` and `user_id` claims as a Keycloak JWT — the RBAC permission check and Tool ACL check pass identically for both
  5. A local user with the `it-admin` role can access `/admin` and perform the same operations as a Keycloak-authenticated admin
**Plans**: TBD

### Phase 14: Ecosystem Capabilities
**Goal**: Agents and users can introspect what the platform can do, any OpenAPI-described service can be wired in as an MCP server in minutes, and external skill repositories can be browsed, imported, and exported in a standard format — turning AgentOS into an open, extensible ecosystem.
**Depends on**: Phase 12
**Requirements**: ECO-01, ECO-02, ECO-03, ECO-04, ECO-05, ECO-06
**Success Criteria** (what must be TRUE):
  1. User (or agent) can send "what can you do?" in chat and receive a structured list of all registered agents, tools, skills, and MCP servers with their descriptions — sourced live from the registries
  2. User can provide an app URL in chat or the admin panel, have AgentOS fetch its OpenAPI spec, select which endpoints to expose, and see a new MCP server appear in the registry — callable from chat immediately after
  3. Admin can add an external skill repository by URL from `/admin` and remove it — only registered repositories appear in the browse/search UI
  4. User can search and browse skills from registered external repositories inside the AgentOS UI and see name, description, and source repository for each result
  5. User can import a skill from an external repository — it enters `pending_review` status, an admin can approve it, and after approval the skill becomes available for use
  6. Admin can export any AgentOS skill definition as an agentskills.io-compliant manifest JSON file from the admin panel
**Plans**: TBD

## Progress

**Execution Order:** 1 → 2 → 2.1 → 3 → 3.1 → 4 → 4.1 → 5 → 5.1 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Identity & Skeleton | v1.0 | 4/4 | ✅ Complete | 2026-02-24 |
| 2. Agent Core & Chat | v1.0 | 5/5 | ✅ Complete | 2026-02-25 |
| 2.1. Tech Debt Cleanup | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 3. Sub-Agents & Memory | v1.0 | 6/6 | ✅ Complete | 2026-02-26 |
| 3.1. Memory Read + MCP Hot-Reg | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 4. Canvas & Workflows | v1.1 | 5/5 | ✅ Complete | 2026-02-27 |
| 4.1. Phase 4 Polish (INSERTED) | v1.1 | 1/1 | ✅ Complete | 2026-02-27 |
| 5. Scheduler & Channels | v1.1 | 6/6 | ✅ Complete | 2026-02-28 |
| 5.1. Workflow Execution Wiring (INSERTED) | v1.1 | 1/1 | ✅ Complete | 2026-02-28 |
| 6. Extensibility Registries | v1.1 | 8/8 | ✅ Complete | 2026-03-01 |
| 7. Hardening & Sandboxing | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 8. Observability | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 9. Tech Debt Code Fixes (INSERTED) | v1.1 | 2/2 | ✅ Complete | 2026-03-01 |
| 10. Optional Tech Debt Closure (INSERTED) | v1.1 | 2/2 | ✅ Complete | 2026-03-02 |
| 11. Infrastructure & Debt | 2/2 | Complete    | 2026-03-02 | - |
| 12. Unified Admin Desk | 1/2 | In Progress|  | - |
| 13. Local Auth | v1.2 | 0/TBD | Not started | - |
| 14. Ecosystem Capabilities | v1.2 | 0/TBD | Not started | - |
