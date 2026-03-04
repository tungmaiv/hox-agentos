# Pitfalls Research

**Domain:** Enterprise Agentic OS Platform (LangGraph + CopilotKit + React Flow + Keycloak + pgvector + LiteLLM + Multi-Channel)
**Researched:** 2026-02-24 (v1.0 original) | Updated: 2026-03-05 (v1.3 additions)
**Confidence:** HIGH (verified across official docs, GitHub issues, and multiple independent sources)

---

## Critical Pitfalls

These mistakes cause rewrites, security incidents, or fundamental architecture failures. Address them in the phase where they first become relevant.

### Pitfall 1: LangGraph Agent Infinite Loops and Context Explosion

**What goes wrong:**
Agents enter infinite recursion between the agent node and tool nodes, bouncing back and forth without termination. Simultaneously, conversation state grows unboundedly -- messages, tool results, and retrieved documents accumulate in `BlitzState.messages` until the LLM context window is exceeded. A real production issue documented on GitHub showed 142,800 tokens against a 128,000 token limit because the full conversation history plus retrieved documents were passed to the LLM without trimming.

**Why it happens:**
- Missing or incorrect `should_continue` conditional edges in the StateGraph
- No `recursion_limit` set in LangGraph config (default is 25, which may be too high for some flows)
- Sub-agents calling tools that return large payloads (e.g., full email bodies, CRM dumps) that get appended to state
- The master agent re-invokes itself or a sub-agent without making progress toward completion
- Tool errors causing the agent to retry the same tool call indefinitely

**How to avoid:**
1. Set `recursion_limit` explicitly in every `graph.invoke()` call (15-30 for conversations, 30-50 for complex workflows)
2. Implement a `trim_messages()` function in state reducers that caps `BlitzState.messages` at a token budget (e.g., keep last 4000 tokens of conversation, summarize the rest)
3. Add a `step_count` field to `BlitzState` and a guard node that terminates after N steps with a graceful "I need more information" response
4. Truncate tool outputs before appending to state -- tool functions should return summaries, not raw data dumps
5. Use LangGraph's built-in `messages` annotation with `add_messages` reducer, which handles deduplication
6. For CopilotKit integration specifically: CopilotKit can override LangGraph recursion limits (GitHub issue #1717) -- explicitly set limits in both the LangGraph config AND the CopilotKit runtime config

**Warning signs:**
- Agent responses take longer and longer over a conversation session
- Backend memory usage climbs steadily during conversations
- LiteLLM logs show increasing token counts per request
- `GraphRecursionError` exceptions in logs

**Phase to address:** Phase 2 (Agents, Tools & Memory) -- this must be built into the master agent and sub-agent patterns from day one.

---

### Pitfall 2: Credential Leakage to LLMs via Tool Descriptions, Error Messages, or State

**What goes wrong:**
Credentials (OAuth tokens, API keys, passwords) leak into the LLM context through multiple vectors: (a) tool error messages that include stack traces containing decrypted credentials, (b) tool descriptions or system prompts that mention credential formats, (c) debug logging that serializes the full state including credential fields, (d) LLM-generated code that references `.env` variables or config files. A ServiceNow incident demonstrated that multi-agent privilege escalation can occur where a low-privilege agent tricks a higher-privilege agent into performing credentialed actions.

**Why it happens:**
- Python exception tracebacks include local variable values -- if a credential is in scope when an exception fires, it appears in the traceback
- Tool functions receive credentials as parameters rather than resolving them internally
- Developers add credential fields to Pydantic tool input/output schemas during debugging and forget to remove them
- Agent state (`BlitzState`) is serialized to the LangGraph checkpoint in PostgreSQL -- if credentials end up in state, they persist in the database
- Error messages from external APIs (Gmail, O365) sometimes include the bearer token in the error response

**How to avoid:**
1. Enforce the architecture invariant: tools resolve credentials internally via `user_id` from `UserContext`, never from parameters
2. Create a `SafeException` wrapper that strips local variables from tracebacks before they reach the agent
3. Add a `RedactionProcessor` to structlog that regex-matches and masks patterns like `Bearer ey...`, `sk-...`, `xoxb-...`
4. Never add credential-like fields to `BlitzState` TypedDict -- run a static analysis check (custom ruff rule or grep in CI) that flags `token`, `password`, `secret`, `api_key` in state type definitions
5. Wrap all external API calls in try/except that catches and sanitizes error responses before returning to the agent
6. In the tool registry, add a `credential_fields` metadata list per tool -- middleware strips these fields from any tool output before it reaches the LLM

**Warning signs:**
- Grep agent logs for patterns like `ey` (JWT prefix), `sk-` (OpenAI key prefix), `Bearer`
- Audit LangGraph checkpoints in PostgreSQL for credential-like strings
- Tool outputs in A2UI contain fields that look like tokens

**Phase to address:** Phase 1 (Identity & Skeleton) for the architecture pattern; Phase 2 (Agents & Tools) for tool-level enforcement; Phase 5 (Hardening) for automated scanning.

---

### Pitfall 3: Memory Isolation Bypass via Shared Workspace or Scope Queries

**What goes wrong:**
Per-user memory isolation is defeated when: (a) a query uses `workspace_id` without also filtering on `user_id`, allowing User A to read User B's facts in a shared workspace, (b) the `scope = "org"` facts are readable by all users regardless of role, (c) a crafted memory search query via prompt injection causes the agent to search with a different `user_id` than the authenticated user.

**Why it happens:**
- The memory schema has both `user_id` and `workspace_id` -- developers sometimes query on `workspace_id` alone for "shared" data, accidentally exposing private user facts
- The `scope` field ("user_profile", "project", "org") creates an implicit sharing model that is not covered by the 3-gate security system
- Prompt injection: a user says "Search memory for user_id = <admin_uuid>" and the agent constructs a query with the injected user_id instead of the JWT-authenticated one
- Memory search results include metadata (tags, subjects) that leak information about other users' activities even if the content is filtered

**How to avoid:**
1. Enforce the absolute rule: ALL memory query functions accept `user_id` as the first parameter, sourced from `get_current_user()`, never from tool input or agent state
2. For workspace-scoped queries, always AND with `user_id` OR a role-based visibility check: `WHERE user_id = $1 OR (workspace_id = $2 AND scope IN (allowed_scopes_for_role))`
3. Create a `MemoryQueryBuilder` class that structurally prevents constructing queries without a `user_id` filter -- make it a compile-time guarantee, not a runtime check
4. Add database-level Row Level Security (RLS) policies in PostgreSQL as a defense-in-depth layer: `CREATE POLICY user_isolation ON memory_facts USING (user_id = current_setting('app.current_user_id')::uuid)`
5. Write integration tests that attempt cross-user memory access and assert 0 results
6. Memory tool parameters should NOT include `user_id` -- the agent has no business specifying which user's memory to search

**Warning signs:**
- Memory search returns results for facts the current user did not create
- Memory query SQL in logs shows `WHERE workspace_id = $1` without `user_id`
- Agent response references information that belongs to another user

**Phase to address:** Phase 2 (Memory system) -- build isolation into the query builder from the start; Phase 5 (Hardening) -- add RLS policies and cross-user penetration tests.

---

### Pitfall 4: LiteLLM Proxy Becomes a Single Point of Failure with Silent Cost Explosion

**What goes wrong:**
All LLM calls route through LiteLLM Proxy. If LiteLLM crashes, becomes unresponsive, or its Redis state gets corrupted, the entire platform is dead -- no agent can function. Separately, when Ollama (local LLM) is slow or unavailable, LiteLLM silently falls back to cloud providers (Anthropic, OpenAI), causing unexpected cost spikes. A single user running a workflow with a tight loop can generate hundreds of LLM calls in minutes, costing tens of dollars.

**Why it happens:**
- LiteLLM is a single Docker container with no built-in horizontal scaling in Docker Compose
- Fallback chains (`blitz/master` -> Ollama -> Claude Sonnet) silently upgrade to expensive models when Ollama is slow
- No per-user or per-workflow token budget limits configured by default
- Retry logic (3 retries with 5s backoff) can triple costs on expensive models if the first attempt times out but actually succeeds on the provider side
- No health check distinguishes between "Ollama is slow" and "Ollama is down" -- slow responses trigger fallback to cloud

**How to avoid:**
1. Configure LiteLLM budget limits per model alias: `max_budget: 10.0` per day for `blitz/master`, with alerts at 80% threshold
2. Set per-user token budgets using LiteLLM's budget/rate limit tiers feature
3. Add a dedicated health check for Ollama that distinguishes slow from down: if Ollama responds within 30s, wait for it rather than falling back to cloud
4. Set `timeout` per model in LiteLLM config (e.g., 60s for local Ollama, 30s for cloud) -- do not use the same timeout for cheap and expensive models
5. Add a `max_tokens` cap to every `get_llm()` call to prevent runaway token generation
6. Monitor LiteLLM's `/spend/logs` endpoint and build a Grafana dashboard tracking daily spend per model
7. Add a circuit breaker: if cloud fallback triggers more than N times in M minutes, halt and alert rather than continuing to spend
8. Run LiteLLM with a restart policy (`restart: unless-stopped`) and health check in docker-compose

**Warning signs:**
- LiteLLM logs show frequent fallback events from Ollama to cloud models
- Monthly cloud LLM costs exceed budget by 2-3x
- Agent responses become slow (Ollama latency) then suddenly fast (cloud fallback) in an inconsistent pattern
- Celery workers queue up because all LLM calls are blocking on a single LiteLLM instance

**Phase to address:** Phase 1 (Skeleton) for health checks and restart policies; Phase 2 (Agents) for token budgets in agent code; Phase 6 (Observability) for cost dashboards.

---

### Pitfall 5: Canvas Workflow Schema Becomes Unmigrable Due to Missing Versioning Discipline

**What goes wrong:**
The `definition_json` schema for React Flow canvas workflows evolves during development. Developers add new node types, change `data` field structures, or modify edge semantics without bumping `schema_version`. After a few iterations, existing saved workflows cannot be compiled by `compile_workflow_to_stategraph()` because the code expects the new schema but the database contains old-format definitions. Since there is no migration script, the only option is to manually re-create every workflow.

**Why it happens:**
- Schema changes feel "minor" -- adding an optional field, renaming a property -- so developers skip the version bump
- No automated validation exists to check that `definition_json` in the database matches the current schema version
- React Flow's save/restore pattern just serializes whatever the current component state is, with no schema enforcement
- Testing only uses freshly created workflows, never loading saved workflows from previous schema versions

**How to avoid:**
1. Add a Pydantic model for `WorkflowDefinition` that validates `schema_version` on every load from the database
2. Create a `workflow_migrations/` directory with numbered migration scripts (similar to Alembic but for JSON): `001_add_mcp_node_type.py`, `002_rename_hitl_prompt.py`
3. `compile_workflow_to_stategraph()` must first call `migrate_definition(definition_json)` which applies all pending migrations up to the current version
4. Add a CI check that fails if any code references `definition_json` fields not present in the current Pydantic schema
5. Include a "load old workflow" integration test for every schema version that ever existed
6. The canvas frontend should display a warning banner when loading a workflow with an older `schema_version` and offer to migrate it

**Warning signs:**
- `compile_workflow_to_stategraph()` throws `KeyError` or `ValidationError` on saved workflows
- Users report "my workflow stopped working after the update"
- Database has `definition_json` records with different structures but the same `schema_version`

**Phase to address:** Phase 3 (Canvas & Workflows) -- establish the migration framework before any workflow is saved to the database.

---

### Pitfall 6: MCP SSE Transport Fragility and Tool Discovery Overhead

**What goes wrong:**
MCP server connections over HTTP+SSE are long-lived and stateful. When an MCP server container restarts (due to a crash, OOM, or Docker Compose rebuild), the SSE connection drops silently. The MCP client in the backend does not reconnect automatically and continues to fail until the backend itself is restarted. Additionally, every MCP tool call requires a full initialization handshake (including tool discovery), adding 200-500ms of overhead per call.

**Why it happens:**
- The MCP Python SDK's `sse_client` context manager opens a connection per call but does not pool or cache connections
- The MCP spec (as of November 2025) requires a full handshake for tool discovery -- there is no lightweight ping or capability check
- SSE connections through Docker's internal network can be silently dropped by Docker's proxy without triggering a TCP reset
- No retry logic exists in the basic `MCPClient` implementation shown in the architecture doc
- The MCP spec is actively evolving (Streamable HTTP replaces SSE, Server Cards for discovery) -- today's implementation may need rewriting for the June 2026 spec

**How to avoid:**
1. Implement connection pooling in `MCPClient`: maintain a persistent session per MCP server, with automatic reconnect on connection failure
2. Cache the tool list from `session.initialize()` with a TTL (e.g., 5 minutes) -- do not re-discover tools on every call
3. Add health checks for MCP server containers in docker-compose (`healthcheck: curl -f http://localhost:8001/health`)
4. Implement retry with exponential backoff in `MCPClient.call_tool()` (3 retries, 1s/2s/4s)
5. Design `MCPClient` with an abstraction layer that can swap transport (SSE -> Streamable HTTP) without changing tool registry or agent code
6. Monitor MCP call latency and failure rate -- if a server is consistently slow, circuit-break rather than blocking the agent
7. Consider pre-warming MCP connections on backend startup rather than lazily on first tool call

**Warning signs:**
- MCP tool calls intermittently fail with connection errors after infrastructure changes
- Agent responses involving MCP tools are 500ms+ slower than equivalent backend tools
- MCP tool list becomes stale (new tools added to server but not visible to agents)

**Phase to address:** Phase 2 (Tools -- when MCP tools are first integrated); Phase 5 (Hardening -- connection resilience and health checks).

---

### Pitfall 7: bge-m3 Embedding Service Blocks FastAPI Event Loop or OOMs Celery Workers

**What goes wrong:**
The bge-m3 model (`BAAI/bge-m3`) requires approximately 1.06 GB of GPU memory (float16) or 2+ GB of CPU RAM for inference. If embedding is called synchronously inside a FastAPI request handler, it blocks the async event loop for 500ms-2s per batch, making the entire API unresponsive. If run in Celery workers without memory limits, multiple concurrent embedding tasks can OOM the worker host. Additionally, `use_fp16=True` on CPU-only deployments causes silent failures or crashes.

**Why it happens:**
- FlagEmbedding's `FlagModel.encode()` is a synchronous, CPU/GPU-bound operation -- calling it in an `async def` endpoint blocks the event loop
- The architecture correctly specifies running embeddings in Celery workers, but developers may shortcut this for "just one embedding" during development and leave it in production
- `FlagModel` loads the full model into memory on first use (lazy loading via class variable) -- if multiple Celery workers each load their own copy, RAM usage multiplies
- Default batch_size=256 with max_length=512 requires ~9 GB VRAM; production documents may exceed 512 tokens, silently truncating content

**How to avoid:**
1. Never call `EmbeddingService.embed()` from a FastAPI request handler -- always dispatch to Celery
2. Configure Celery workers with `--concurrency=1` for embedding tasks (model is not thread-safe) and use a dedicated queue (`-Q embeddings`)
3. Set `use_fp16=False` explicitly when running on CPU; only enable fp16 on GPU
4. Use a singleton pattern for `FlagModel` within each worker process (already in the architecture) but also set `--max-memory-per-child` on Celery workers to force periodic restart if memory leaks
5. Set `max_length=512` explicitly (or 256 for short-text use cases) and log a warning if input exceeds the limit
6. Implement batch size limits: process at most 12 texts per batch on CPU, 32 on GPU
7. Pre-load the model on Celery worker startup (`worker_init` signal) rather than lazy-loading on first task

**Warning signs:**
- FastAPI health check starts timing out during periods with many new facts being created
- Celery workers show steadily increasing RSS memory
- Embedding tasks take 10x longer than expected (fp16 on CPU fallback path)
- Memory facts are saved with `NULL` embeddings because the Celery task silently failed

**Phase to address:** Phase 2 (Memory system) -- configure Celery worker isolation from the start; Phase 5 (Hardening) -- memory limits and monitoring.

---

## v1.3-Specific Pitfalls

The following pitfalls are specific to adding v1.3 features (session management, nav redesign, embedding sidecar, Keycloak runtime config, Agent Skills compliance) to the existing v1.2 system. Confidence: HIGH for code-verified items, MEDIUM for ecosystem-pattern items.

---

### Pitfall 8: Next.js Middleware Infinite Redirect Loop on Authenticated Routes

**What goes wrong:**
`middleware.ts` is configured with a broad matcher pattern (e.g., `/((?!api|_next/static|_next/image|favicon.ico).*)`) and redirect logic that says "if authenticated, go to /dashboard." When an authenticated user requests `/dashboard`, the middleware fires again, sees the user is authenticated, and redirects to `/dashboard` again — infinite loop. Browser shows "ERR_TOO_MANY_REDIRECTS."

Current system: no `middleware.ts` exists. Every page does its own auth check in component code. When `middleware.ts` is added, the existing per-page redirects will interact with middleware redirects unless both are coordinated.

**Why it happens:**
The redirect logic is written from the wrong perspective. Instead of asking "who should NOT be here?" (unauthenticated users on protected pages), it asks "where should this user GO?" — which fires on every request including the destination.

**How to avoid:**
Use `NextResponse.next()` for already-authorized users — never redirect an authenticated user further. Middleware should only redirect unauthenticated users away from protected routes.

```typescript
// CORRECT: middleware.ts
export function middleware(request: NextRequest) {
  const token = request.cookies.get('auth-token')?.value
  const isProtected = !request.nextUrl.pathname.startsWith('/login')

  if (!token && isProtected) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
  return NextResponse.next()  // Always pass through — never redirect authenticated users
}
```

Matcher must explicitly exclude static files and API routes:
```typescript
export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon\\.ico|login).*)'],
}
```

After middleware handles auth, remove per-page auth redirect logic from existing pages to prevent two-layer redirect conflicts.

**Warning signs:**
- Browser shows "ERR_TOO_MANY_REDIRECTS" on any route
- Middleware logs firing more than once per request for the same URL
- `/login` becomes inaccessible (loop catches it too if matcher not properly scoped)
- Next.js internal `x-middleware-subrequest` depth counter reaches 5

**Phase to address:** Session & Auth Hardening (first phase of v1.3). Must be stable before navigation overhaul.

---

### Pitfall 9: CVE-2025-29927 — Middleware Auth Bypass via `x-middleware-subrequest` Header

**What goes wrong:**
Any Next.js version before 15.2.3 allows complete bypass of `middleware.ts` by sending the `x-middleware-subrequest` header. An attacker skips auth entirely by adding `x-middleware-subrequest: middleware` to any request. This is a known critical vulnerability actively exploited as of March 2025.

**Why it happens:**
Next.js uses `x-middleware-subrequest` internally to prevent infinite loops (see Pitfall 8). The header was designed for internal use but was never validated against external input before version 15.2.3. The same mechanism that prevents loops enables bypass.

Adding `middleware.ts` to the project without upgrading to 15.2.3+ ships a known critical vulnerability.

**How to avoid:**
1. Confirm current Next.js version and upgrade to ≥ 15.2.3 before writing any `middleware.ts`
2. At the reverse-proxy layer (Nginx), strip the header before it reaches Next.js: `proxy_set_header x-middleware-subrequest ""`
3. Treat middleware as UX convenience only — the backend's 3-gate security (JWT → RBAC → Tool ACL) is the actual enforcement layer

**Warning signs:**
- `next --version` reports < 15.2.3
- No reverse proxy header stripping in docker-compose nginx config
- Security scanner flags CVE-2025-29927 in frontend deps

**Phase to address:** Session & Auth Hardening. Version upgrade must happen before any `middleware.ts` is written.

---

### Pitfall 10: Keycloak Made Optional — Boot-Time Validation Breaks Local-Auth-Only Mode

**What goes wrong:**
`core/config.py` declares `keycloak_url: str` as a required field with no default. When Keycloak is made optional (for local-auth-first boot), pydantic-settings validation fails at startup if `KEYCLOAK_URL` is not set — even if the admin configured local-auth-only mode. The backend refuses to start before any feature flags can be checked.

Additionally, `keycloak_client.py` calls `settings.keycloak_url` to construct URLs. If `keycloak_url` is empty, URL construction produces malformed strings like `"/realms/blitz-internal/protocol/openid-connect/certs"` that pass validation but fail at runtime.

The Celery workflow execution path calls `fetch_user_realm_roles()` for every scheduled run. For local users, this hits the Keycloak Admin API with a `user_id` that doesn't exist in Keycloak — returning 404 and failing every local user's scheduled workflow.

**Why it happens:**
The system was designed with Keycloak as a hard dependency. The dual-issuer dispatcher in `jwt.py` already handles local tokens correctly — the authentication runtime is already optional. The bootup validation and service calls are the broken parts that must be surgically updated.

**How to avoid:**
- Change `keycloak_url: str` to `keycloak_url: str = ""` with a `@field_validator` that validates non-empty only when `keycloak_enabled: bool = True`
- Wrap all Keycloak service calls in guards: `if not settings.keycloak_enabled: ...`
- The JWKS fetch in `_validate_keycloak_token` must short-circuit if Keycloak is disabled
- In `workflow_execution.py`: if owner is a local user, skip the Keycloak Admin API call and use `owner_roles_json` snapshot directly
- Add health check endpoint that reports Keycloak status separately from overall app health
- Add `KEYCLOAK_ENABLED=false` test to CI that starts backend without `KEYCLOAK_URL` and asserts HTTP 200 on `/health`

**Warning signs:**
- `pydantic_settings.ValidationError: keycloak_url field required` at startup when removing `KEYCLOAK_URL`
- `settings.keycloak_jwks_url` is empty string after removing `KEYCLOAK_URL`
- Celery logs show `httpx.HTTPStatusError: 404` for local user UUIDs during workflow execution
- `httpx.ConnectError` in Celery worker logs for local-user workflows

**Phase to address:** Keycloak Runtime Config phase. This must be tackled atomically — half-done optional Keycloak causes auth regressions for all users.

---

### Pitfall 11: Embedding Sidecar Migration — bge-m3 Loaded in Both FastAPI Process AND Sidecar

**What goes wrong:**
`master_agent.py` currently calls `BGE_M3Provider().embed()` directly in `_load_memory_node`. When the embedding sidecar is added as a new Docker service, developers add the sidecar but forget to remove the in-process call. Result: bge-m3 is loaded in three processes simultaneously — FastAPI uvicorn, Celery embedding worker, and the new sidecar — consuming ~4GB RAM total. The bug is invisible until memory profiling or until Docker host OOM-kills a process.

The in-process call uses `run_in_executor` (non-blocking) so it still "works" — no test catches the dual-load unless memory is explicitly profiled.

**Why it happens:**
The sidecar is added as a new service without removing the old in-process embedding. Both paths produce valid 1024-dim vectors. No existing test asserts "BGE_M3Provider is NOT imported in agents/."

**How to avoid:**
- The migration commit must include both: adding the sidecar service AND removing `from memory.embeddings import BGE_M3Provider` from `master_agent.py`
- Replace the in-process embed call in `_load_memory_node` with an HTTP call to the sidecar endpoint
- Add a test that asserts `BGE_M3Provider` is NOT imported from any file under `backend/agents/`
- The sidecar must expose a health endpoint; docker-compose `depends_on: condition: service_healthy` ensures backend waits for sidecar
- Celery embedding tasks (`scheduler/tasks/embedding.py`) must also be migrated to the sidecar HTTP call — or kept as-is if the sidecar handles only synchronous query-time embedding

**Warning signs:**
- `bge_m3_model_loaded` log line appears in both backend uvicorn logs AND embedding-sidecar logs
- `backend` Docker container memory grows by 1.3GB after sidecar deployment
- `pgrep -f FlagModel` shows more than one process with the model loaded

**Phase to address:** Performance & Embedding Sidecar phase. Extraction must be atomic — add sidecar and remove in-process call in the same commit.

---

### Pitfall 12: PostgreSQL tsvector Full-Text Search — Language Config Mismatch Silently Disables Index

**What goes wrong:**
A GIN index is created with `to_tsvector('english', content)` but queries use `to_tsvector(content)` (no explicit language, uses `default_text_search_config`). PostgreSQL does NOT use the GIN index for the implicit-language query — it falls back to sequential scan. Search "works" but is O(n) instead of O(log n).

For this project specifically: the platform has Vietnamese content (bge-m3 is multilingual). The `english` dictionary does not stem Vietnamese. Using `'simple'` (no stemming, just lowercasing) is correct for mixed Vietnamese/English content. Using `'english'` on Vietnamese produces poor search quality.

**Why it happens:**
Developers copy the standard PostgreSQL FTS pattern without realizing the language argument must be explicit and identical in both the index definition and the query. Vietnamese has no built-in PostgreSQL text search configuration — there is no `'vietnamese'` option.

**How to avoid:**
- Always use explicit language in both index AND query: `to_tsvector('simple', content) @@ plainto_tsquery('simple', query)`
- Create index: `CREATE INDEX idx_skills_fts ON skills USING GIN (to_tsvector('simple', name || ' ' || description))`
- Backfill existing rows when adding a tsvector column: `UPDATE skills SET tsv = to_tsvector('simple', name || ' ' || description)`
- Alembic autogenerate does NOT capture GIN expression indexes — write them as explicit `op.execute()` in migrations
- Verify index usage with `EXPLAIN ANALYZE` — must show "Bitmap Index Scan on idx_skills_fts", not "Seq Scan"

**Warning signs:**
- `EXPLAIN ANALYZE` shows "Seq Scan" on the skill search query
- Search works but is slower than expected
- Search for Vietnamese words returns 0 results when using `'english'` dictionary

**Phase to address:** Performance & Embedding Sidecar phase, or whichever phase adds FTS to the skill catalog. Validate with `EXPLAIN ANALYZE` before shipping.

---

### Pitfall 13: LangGraph Graph Topology Change Breaks HITL-Interrupted Checkpoints

**What goes wrong:**
Existing canvas workflows have persisted checkpoints in PostgreSQL (via `AsyncPostgresSaver`). LangGraph supports adding new nodes for completed threads, but does NOT support renaming or removing nodes for threads currently interrupted at a HITL approval node. If a workflow is paused at HITL when the deployment adds a `security_review` node, it becomes impossible to resume — the checkpointed "next node" no longer matches the new topology.

LangGraph raises `ValueError: Node X not found in graph` when trying to resume an interrupted thread whose checkpointed next-node no longer exists.

**Why it happens:**
LangGraph's checkpoint stores the "next node to execute" alongside state. For HITL-interrupted threads, the next-node is the node after the interrupt. If that node name is removed or the insertion point changes, the checkpoint becomes invalid.

Note: CVE-2025-64439 affects `langgraph-checkpoint` < 3.0 via `JsonPlusSerializer` RCE. This project is already at `langgraph-checkpoint-postgres>=3.0.4` (confirmed in pyproject.toml) — verify before any checkpoint-touching changes.

**How to avoid:**
- Before adding new nodes: drain all `status='pending_hitl'` workflow runs. Mark them as failed or let users re-trigger
- Add new nodes as optional branches from existing nodes rather than inserting between existing nodes
- Never rename or remove existing node names from master_agent or canvas workflow graphs
- Add a pre-deployment check: query `workflow_runs` for `status='pending_hitl'` rows; block deploy if found
- After deploying new graph topology, add a cleanup job that marks old-topology interrupted runs as `status='stale'`

**Warning signs:**
- `ValueError: Node X not found in graph` in Celery logs after deployment
- HITL workflow runs permanently stuck in `pending_hitl` status
- `workflow_runs` rows with `status='pending_hitl'` older than the deployment timestamp

**Phase to address:** Skill & Security Builder phase (when `security_review` node is added). Pre-deployment HITL drain is a required deployment step.

---

### Pitfall 14: Navigation Overhaul — Root Layout Wraps Login Page and API Routes

**What goes wrong:**
When the navigation rail is added to `app/layout.tsx`, all routes inherit it — including `/login` (shows nav rail before authentication) and `/api/copilotkit` (API routes get HTML wrapping). The current `app/layout.tsx` only wraps `SessionProvider` and auth toasts, so there is no precedent for this issue yet.

Additionally, hardcoded paths in existing A2UI cards that reference `/settings` break when the settings page moves to `/admin` or a renamed route during the navigation redesign.

**Why it happens:**
Next.js App Router root layout is universal — it applies to everything under `app/`, including API routes. Developers add the nav component to `app/layout.tsx` for simplicity, not realizing the scope.

**How to avoid:**
- Create `app/(protected)/layout.tsx` route group containing the nav rail. Move all authenticated pages under `(protected)/`. `/login` and `/api/` stay at root
- Route groups (`(protected)/`) are transparent to URLs — `/dashboard` stays `/dashboard` regardless of physical location under `(protected)/dashboard/page.tsx`
- Audit all A2UI cards and channel message formatters for hardcoded route strings before restructuring
- Add a smoke test: `curl /api/copilotkit` must return JSON, not HTML with nav components
- Keep `app/layout.tsx` minimal — only providers that must wrap everything

**Warning signs:**
- Login page shows nav rail or user avatar before authentication
- `/api/copilotkit` returns HTML instead of JSON
- Admin URLs like `/admin#skills` show 404 after restructure
- Console errors: hooks called in Server Components inside the layout

**Phase to address:** Navigation & UX Overhaul phase. Must be done AFTER middleware.ts is stable — middleware determines auth state used by the nav rail.

---

### Pitfall 15: agentskills.io Compliance — `name` Field Constraints Silently Produce Non-Compliant Exports

**What goes wrong:**
The agentskills.io specification (verified from agentskills.io/specification) requires:
- `name`: max 64 chars, lowercase alphanumeric and hyphens only (`a-z`, `0-9`, `-`), no consecutive hyphens, must match parent directory name
- `description`: max 1024 chars, non-empty, must describe both what the skill does AND when to use it

Existing skills in the DB were created before these constraints were enforced. Names like `"Email Fetch v2"`, `"CRM_Lookup"`, or `"Morning-Digest-Workflow"` (uppercase, underscores, or spaces) fail the spec. The export silently produces a non-compliant zip. Consumers using `skills-ref validate` reject the import.

Additionally: the zip directory structure must be `<name>/SKILL.md`, not a flat zip. The `name` field in SKILL.md frontmatter must match the enclosing directory name exactly.

**Why it happens:**
The export was implemented in v1.2 before the agentskills.io spec's naming constraints were finalized. No validation was added at skill creation time.

**How to avoid:**
- Add `normalize_skill_name(name: str) -> str` that slugifies names: lowercase, replace spaces/underscores with hyphens, remove invalid chars, truncate to 64 chars
- Add name validation to the skill creation wizard (reject at input time, not export time)
- Zip structure must be `<normalized-name>/SKILL.md`, not flat
- Run `skills-ref validate ./skill-directory` in CI on exported zips
- Truncate description to 1024 chars with a warning log if truncation occurs

**Warning signs:**
- Exported skill zips fail `skills-ref validate`
- Skill names in DB contain spaces, uppercase, or underscores
- `name` field in SKILL.md doesn't match the enclosing directory name in the zip

**Phase to address:** Skill Platform Compliance phase. Add validation at the DB model level so the catalog stays spec-compliant from creation.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skipping IVFFlat index tuning (`lists=100` hardcoded) | Faster setup, works at small scale | At 10K+ facts, recall drops significantly because `lists=100` is wrong for small datasets (should be `sqrt(n)`) | MVP only -- revisit when facts table reaches 1000 rows |
| Using `sse_client` context manager per MCP call instead of pooling | Simpler code, no connection state to manage | 200-500ms overhead per MCP tool call, SSE reconnection storms under load | MVP only -- pool before Phase 4 |
| Storing full conversation history in `BlitzState.messages` | Complete context for the agent | Token budget overflow, checkpoint bloat in PostgreSQL, slow state serialization | Never -- implement trimming from Phase 2 |
| Embedding dimension `vector(1024)` hardcoded in schema | Matches bge-m3 exactly | Changing embedding model requires full reindex + schema migration + downtime | Acceptable -- bge-m3 is a good choice for multilingual |
| Single LiteLLM container with no redundancy | Simpler deployment | Single point of failure for all LLM calls | MVP only -- add health checks and restart policies in Phase 1, consider replication in Phase 6 |
| No TTL on LangGraph checkpoints | All workflow states preserved forever | PostgreSQL checkpoint table grows unboundedly, slows down queries | MVP only -- add TTL-based cleanup in Phase 5 |
| AES-256 encryption keys in environment variables | No need for HashiCorp Vault | Key rotation requires redeploying all containers, key visible in `docker inspect` | MVP only -- documented as acceptable in architecture |
| Per-page auth checks without middleware.ts (current state) | Simple, no middleware | Every page must duplicate redirect logic; unauthenticated API calls return HTML | Never post-v1.3 — replace with middleware.ts |
| bge-m3 loaded in FastAPI process via `_load_memory_node` (current state) | No network hop for query-time embedding | 1.3GB+ RAM consumed in uvicorn; model load on cold start blocks first request for 10-15s | Never post-v1.3 — move to sidecar |
| `owner_roles_json` snapshot for Keycloak roles | Works offline | Stale if user's roles change between schedule and execution | Acceptable for local users and when Keycloak is unavailable |
| Keycloak as hard boot dependency (current state) | Simple config validation | Prevents local-auth-only deployments; 503 on all requests if Keycloak restarts | Never post-v1.3 — make optional |
| Skills catalog search via ILIKE (current state) | No index maintenance | O(n) scan; acceptable at 100 skills, poor at 1000+ | Acceptable until skill catalog exceeds ~500 rows |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Keycloak JWT | Caching JWKS keys indefinitely -- when Keycloak rotates keys, JWT validation breaks for all users until backend restart | Implement JWKS cache with a TTL (5-10 minutes) and a fallback: on validation failure with cached key, fetch fresh JWKS once before rejecting |
| Keycloak JWT | Hardcoding the Keycloak realm URL without handling Keycloak restart/migration | Use the OIDC discovery endpoint (`/.well-known/openid-configuration`) to dynamically resolve JWKS URI |
| Ollama (host) | Using `http://ollama:11434` in LiteLLM config (Docker service name) | Ollama runs on the host, not in Docker -- use `http://host.docker.internal:11434` and add `extra_hosts: ["host.docker.internal:host-gateway"]` to LiteLLM service on Linux |
| Ollama (host) | Not setting `OLLAMA_HOST=0.0.0.0` on the host machine | Default Ollama binds to `127.0.0.1` -- containers cannot reach it even with `host.docker.internal` unless Ollama binds to all interfaces |
| LiteLLM config | Using `api_base: http://ollama:11434` in LiteLLM config YAML | LiteLLM runs inside Docker, Ollama on the host -- use `http://host.docker.internal:11434` as `api_base` |
| Telegram webhook | Setting webhook URL to `http://localhost:8000/channels/telegram/webhook` | Telegram servers need a public HTTPS URL; use ngrok for dev, reverse proxy for production |
| WhatsApp Business API | Trying to use WhatsApp Cloud API without a verified business account | Business verification takes 1-4 weeks; start the process in Phase 1, implement the adapter in Phase 4 |
| MS Teams Bot Framework | Registering the bot in Azure AD but not configuring the messaging endpoint | The Bot Framework requires a publicly reachable HTTPS endpoint registered in the Azure portal |
| React Flow v12 | Importing from `react-flow-renderer` (v10 package name) | v12 uses `@xyflow/react` -- the package name changed and old imports will not resolve |
| PostgresSaver | Creating Postgres connection without `autocommit=True` and `row_factory=dict_row` | PostgresSaver requires `autocommit=True` for `.setup()` to commit checkpoint tables, and `dict_row` factory because it accesses rows by key name |
| CopilotKit + LangGraph | Using LangGraph tools for HITL approval nodes | ToolMessage format incompatibility between LangGraph and CopilotKit causes ZodError -- use dedicated graph interrupt nodes instead of tools for HITL |
| Next.js middleware + NextAuth | Middleware reads session using `getToken()` — requires same `NEXTAUTH_SECRET` as the NextAuth handler | Use `getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })` in middleware; ensure env var is consistent across all contexts |
| Next.js middleware + App Router API routes | Root `middleware.ts` matcher catches `/api/copilotkit` — middleware runs on every backend API call | Explicitly exclude `/api/` from middleware matcher pattern |
| agentskills.io spec + existing skill names | Skill names with uppercase, spaces, or underscores exported verbatim | Normalize to spec format (lowercase, hyphens only) before export; validate with `skills-ref validate` |
| LangGraph checkpoint + graph topology change | Deploying a new node while HITL threads are interrupted | Drain HITL-interrupted runs before deployment; use feature flags for new nodes |
| bge-m3 sidecar + Celery workers | Celery workers still import `BGE_M3Provider` directly after sidecar migration | Celery embedding tasks must also be refactored to call sidecar HTTP endpoint, not in-process model |
| PostgreSQL tsvector + Alembic autogenerate | `CREATE INDEX USING GIN (to_tsvector(...))` not captured by Alembic autogenerate | Write GIN index as explicit `op.execute()` in the migration |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| IVFFlat index with `lists=100` on a table with < 1000 rows | Recall drops below 80% because IVFFlat needs `lists ~= sqrt(n)` and 100 is far too many for small tables | Start with `lists=10` or use HNSW index instead; reindex when fact count grows significantly | Below 1000 rows (paradoxically, too FEW rows for the index config) |
| Full `memory_search()` on every agent turn | Agent latency increases 200-500ms per turn as fact table grows | Only run `memory_search()` when the master agent explicitly decides it needs context -- do not inject it in every prompt assembly | 5000+ facts per user |
| Embedding every conversation turn immediately | Celery queue backs up, embeddings lag behind conversations | Only embed facts and episode summaries, not raw conversation turns; batch embedding tasks | 50+ concurrent conversations |
| Serializing full `BlitzState` to LangGraph checkpoint on every step | Checkpoint write latency grows from 5ms to 500ms as state accumulates tool outputs | Use `jsonb` compression, strip large tool outputs from state before checkpointing, set checkpoint TTL | States with 50+ messages or tool outputs |
| A single Celery worker handling both embedding tasks and scheduled workflow jobs | Embedding tasks (CPU-bound, 1-2s each) starve scheduled workflows | Use separate Celery queues: `celery -Q embeddings` and `celery -Q workflows` with dedicated workers | 10+ concurrent embedding tasks |
| Loading FlagModel in every Celery task | Model load takes 5-10s, happens on every new worker process | Pre-load model in `worker_init` signal, use `--concurrency=1` for embedding workers | Any scale -- this is always slow |
| bge-m3 loaded in uvicorn process (current state) | Cold start time 10-15s for first request; 1.3GB RAM per uvicorn worker | Extract to embedding sidecar | Breaks at first cold start; worsens with multiple uvicorn workers (`--workers N`) |
| ILIKE search on skills catalog (current state) | `/admin/skills?search=email` is slow | Add GIN index on tsvector column | Breaks at ~500 rows in skills table |
| HNSW index bloat after memory fact deletions | pgvector cosine_distance queries slow down over weeks | `REINDEX CONCURRENTLY idx_memory_facts_embedding` weekly | Degrades gradually; noticeable at ~10K memory facts per user |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Passing `user_id` as a tool input parameter instead of extracting from JWT | Agents can be prompt-injected to impersonate other users, accessing their memory, credentials, and tool results | `user_id` must ONLY come from `get_current_user()` dependency, never from request body, query params, or tool input schema |
| Logging the full MCP tool call payload including user credentials resolved internally | Audit logs contain decrypted OAuth tokens for external services | `get_audit_logger()` must NEVER log fields matching credential patterns; add a structlog processor that redacts `access_token`, `refresh_token`, `password`, `secret` |
| Celery scheduled jobs running as a privileged service account | A scheduled workflow has access to ALL users' tools and memory, not just the job owner's | Celery worker must reconstruct the job owner's `UserContext` from the stored `user_id` and apply the same 3-gate security as interactive requests |
| Channel webhook endpoints accepting unauthenticated requests | Attacker can spoof Telegram/WhatsApp/Teams messages to impersonate users | Each channel adapter must verify platform-specific signatures (Telegram: compare token hash; WhatsApp: verify `X-Hub-Signature-256`; Teams: Bot Framework JWT) |
| Storing AES-256 encryption key in the same database as encrypted credentials | A database breach exposes both the encrypted data and the key to decrypt it | Store the encryption key in an environment variable or file mount separate from the database volume; rotate periodically |
| LLM prompt containing system instructions about credential handling | Attacker can extract system prompt via prompt injection, learning the credential access pattern | System prompts should describe WHAT tools do, not HOW credentials are resolved; credential resolution is an implementation detail invisible to the LLM |
| Embedding inversion attacks on pgvector data | Attacker with database read access can reconstruct original text from embedding vectors | Restrict database access with RLS; embeddings of sensitive facts should use the same user isolation as the text content |
| Treating Next.js middleware as the auth gate | CVE-2025-29927 allows complete bypass via `x-middleware-subrequest` header | Middleware is UX only — backend 3-gate security is authoritative; upgrade Next.js to ≥15.2.3 |
| Skipping `x-middleware-subrequest` header stripping at reverse proxy | Any attacker who knows the header bypasses middleware entirely | Add `proxy_set_header x-middleware-subrequest ""` to Nginx/Caddy config |
| Trusting agentskills.io imported skill names without sanitization | Skill names with path traversal could write files outside the skill directory | Validate skill names against spec regex; use `pathlib.Path.resolve()` to verify destination is within allowed skill root |
| SecurityScanner runs only on import, not on locally-built skills | Malicious prompt injections added via admin builder after import bypass scanner | Run SecurityScanner on both imported skills AND locally built skills before activation |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing raw LLM streaming tokens during multi-tool workflows | Users see partial JSON, tool call syntax, or thinking tokens that are confusing | Buffer tool call results and show a progress indicator ("Fetching your emails...") via A2UI Progress widget; only stream the final natural language response |
| HITL approval node blocks workflow indefinitely with no timeout | User forgets to approve, workflow hangs forever, scheduled outputs never arrive | Set a default timeout on HITL nodes (e.g., 24 hours) with configurable auto-approve or auto-reject; notify user via channel when approval is pending |
| Canvas workflow builder shows no validation errors until runtime | User builds a workflow with disconnected nodes or missing config, saves it, and only discovers the error when the scheduled job fails | Validate the workflow graph client-side: check for disconnected nodes, missing required fields, cycles without exit conditions; show validation errors inline |
| Agent says "I'll check your calendar" but takes 8 seconds (Ollama latency) | User thinks the system is frozen | Show typing indicator immediately; if response takes > 3s, send an interim "Working on it..." message; for external channels (Telegram), use platform-specific typing actions |
| Error messages expose internal details ("PostgresSaver connection refused") | Users see infrastructure errors they cannot act on | Catch infrastructure errors at the API boundary and return user-friendly messages ("Something went wrong, please try again"); log details server-side |
| Multi-channel users lose conversation context when switching platforms | User asks about project status on Telegram, switches to web -- agent does not remember | Use `conversation_id` from `channel_sessions` to maintain continuity; when a new session starts on a different channel, the agent should load the user's recent episodes from memory |
| Nav rail added but no back-navigation state | Users in admin wizard lose progress when clicking nav rail items | Implement route guard in nav rail items: "You have unsaved changes — leave?" confirmation dialog |
| Profile page added without preference persistence | User sets "dark mode" preference, refreshes, preference is gone | Persist user preferences to DB (`user_preferences` table or `system_config` keyed by user_id); not just localStorage |
| Keycloak optional but login page shows SSO button when Keycloak is disabled | Confusing UI; users try SSO and get error | Read `keycloak_enabled` from backend `/api/auth/providers` endpoint on login page load; render only available options |
| Embedding sidecar cold start delays first memory search | User sends first message, waits 10-15s, response feels broken | Pre-warm sidecar via health check at Docker Compose startup; show "memory loading..." state in chat |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **JWT Validation:** Often missing JWKS key rotation handling -- verify that token validation still works after Keycloak rotates keys (simulate by clearing JWKS cache and rotating keys)
- [ ] **Tool ACL:** Often missing denial audit logging -- verify that every ACL denial produces a structured log entry with user_id, tool_name, and user_roles
- [ ] **Memory Search:** Often missing the `user_id` filter on workspace-scoped queries -- verify with a cross-user test: User A creates a fact in a shared workspace, User B should NOT see it in memory_search results (unless explicitly shared)
- [ ] **Canvas Workflow Save:** Often missing schema_version validation -- verify that loading a workflow with `schema_version: "0.9"` (nonexistent) returns a clear error, not a crash
- [ ] **Channel Identity Mapping:** Often missing the "unlinked user" path -- verify that a Telegram message from an unknown chat_id results in a pairing request, not an unhandled exception
- [ ] **Scheduled Jobs:** Often missing error notification -- verify that when a scheduled workflow fails, the job owner receives a notification on their preferred channel
- [ ] **Embedding Pipeline:** Often missing the NULL embedding case -- verify that facts with `embedding IS NULL` (failed embedding) are excluded from vector search results but still queryable by metadata
- [ ] **Docker Sandbox:** Often missing the timeout-based container cleanup -- verify that a sandbox container running past its timeout is force-killed and removed, not left dangling
- [ ] **LiteLLM Fallback:** Often missing cost attribution -- verify that when a request falls back from Ollama to Claude, the cost is logged and attributed to the correct user/workflow
- [ ] **A2UI Rendering:** Often missing error boundary -- verify that malformed A2UI JSONL (e.g., invalid JSON) does not crash the entire chat panel, but shows a graceful fallback
- [ ] **Next.js middleware (v1.3):** Verify it runs in `middleware.ts` (not `_middleware.ts`); check matcher excludes `/api/`, `/_next/`, `/login`
- [ ] **CVE-2025-29927 (v1.3):** Run `next --version` — must be ≥ 15.2.3. Add to CI/CD version gate
- [ ] **Keycloak optional (v1.3):** Test backend startup with `KEYCLOAK_URL` removed from `.env` — must start in local-auth-only mode without any validation errors
- [ ] **Embedding sidecar (v1.3):** Verify `bge_m3_model_loaded` does NOT appear in backend uvicorn logs after sidecar extraction
- [ ] **tsvector index (v1.3):** Run `EXPLAIN ANALYZE` on skill search query — must show "Bitmap Index Scan", not "Seq Scan"
- [ ] **agentskills.io compliance (v1.3):** Run `skills-ref validate` on at least 3 exported skill zips — must pass all checks
- [ ] **HITL drain before topology change (v1.3):** Check `workflow_runs` for `status='pending_hitl'` rows before deploying LangGraph graph changes
- [ ] **Navigation rail exclusions (v1.3):** Visit `/login` — must NOT show nav components. `curl /api/copilotkit` — must return JSON, not HTML
- [ ] **Local user + Keycloak workflow (v1.3):** Create workflow as local user, schedule it, run it — must complete without Keycloak errors in Celery logs
- [ ] **SecurityScanner on builder output (v1.3):** Create skill via admin builder with prompt injection attempt — verify SecurityScanner runs and quarantines it

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Agent infinite loop consumed cloud LLM budget | LOW | Identify the runaway workflow from LiteLLM spend logs, kill the LangGraph thread, add recursion limit, refund is unlikely from providers -- focus on prevention |
| Credential leaked to LLM context/logs | HIGH | Rotate all affected credentials immediately, audit LangGraph checkpoints for credential strings, purge affected checkpoint records, review and redact audit logs, notify security team |
| Memory isolation breach | HIGH | Identify affected queries from audit logs, determine exposure scope, notify affected users if required by policy, add RLS policies, write cross-user integration tests |
| Canvas workflows broken by schema change | MEDIUM | Write a migration script for the old schema, apply to all affected `definition_json` records, bump `schema_version`, test all migrated workflows |
| LiteLLM cost explosion from uncontrolled fallback | MEDIUM | Review LiteLLM logs to identify the triggering condition, set budget caps, add circuit breaker, consider prepaid credits or billing alerts on cloud providers |
| bge-m3 OOM killed Celery workers | LOW | Restart workers with `--max-memory-per-child` limit, reduce batch size, check if fp16 is enabled on CPU (disable it), re-queue failed embedding tasks |
| MCP server connection lost silently | LOW | Restart the MCP server container, backend will reconnect on next call if retry logic is implemented; if not, restart backend too |
| HITL workflow stuck indefinitely | LOW | Query LangGraph checkpoints for workflows with `hitl_pending=True` older than the timeout, programmatically approve/reject them, notify the user |
| Checkpoint table bloat in PostgreSQL | MEDIUM | Run `DELETE FROM checkpoints WHERE created_at < now() - interval '30 days'`; add a periodic Celery task to clean up; consider partitioning the checkpoints table by date |
| Middleware infinite redirect loop (v1.3) | LOW | Fix matcher to exclude destination route; use `NextResponse.next()` for authenticated users; remove per-page redirect logic |
| CVE-2025-29927 middleware bypass (v1.3) | LOW | `pnpm add next@latest`; add reverse proxy header stripping; redeploy |
| Keycloak optional boot failure (v1.3) | MEDIUM | Change `keycloak_url: str = ""` with conditional validator; redeploy; no data migration needed |
| bge-m3 dual-load in FastAPI + sidecar (v1.3) | LOW | Remove `BGE_M3Provider` import from `master_agent.py`; update `_load_memory_node` to HTTP sidecar call; restart |
| tsvector wrong language index (v1.3) | LOW | `DROP INDEX idx_skills_fts; CREATE INDEX ... USING GIN (to_tsvector('simple', ...)); UPDATE skills SET tsv = ...` |
| HITL checkpoint corruption after topology change (v1.3) | HIGH | Identify affected thread_ids in checkpoint tables; mark `workflow_runs` as failed; users must re-trigger workflows manually |
| agentskills.io non-compliant export (v1.3) | LOW | Add name normalizer function; re-export affected skills; no DB migration needed |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Agent infinite loops / context explosion | Phase 2 | Run a 50-turn conversation test; assert token count per request stays below context window limit; assert no `GraphRecursionError` |
| Credential leakage to LLMs | Phase 1 (pattern) + Phase 2 (enforcement) + Phase 5 (scanning) | Grep all LangGraph checkpoints and logs for credential patterns after running a full tool suite test |
| Memory isolation bypass | Phase 2 (query builder) + Phase 5 (RLS + pen test) | Cross-user integration test: User A's facts must be invisible to User B's memory_search |
| LiteLLM single point of failure / cost explosion | Phase 1 (health check) + Phase 2 (budgets) + Phase 6 (monitoring) | Kill LiteLLM container; verify backend returns graceful error within 5s; check cost dashboard after running 100 agent conversations |
| Canvas schema migration | Phase 3 | Save a workflow, modify the schema, load the workflow -- migration should apply automatically and silently |
| MCP SSE transport fragility | Phase 2 (retry logic) + Phase 5 (health checks) | Kill MCP server container; verify next tool call reconnects and succeeds within retry window |
| bge-m3 blocking/OOM | Phase 2 (Celery isolation) + Phase 5 (memory limits) | Run 50 concurrent embedding tasks; assert no FastAPI health check failures; assert Celery worker RSS stays below limit |
| Keycloak JWKS rotation | Phase 1 | Simulate key rotation: clear JWKS cache, verify next request fetches new keys and succeeds |
| Channel identity mapping gaps | Phase 4 | Send a Telegram message from an unlinked account; verify pairing request is created, no crash |
| HITL deadlock / timeout | Phase 3 (timeout) + Phase 4 (notification) | Create a HITL workflow, do NOT approve within timeout; verify auto-action fires and user is notified |
| Checkpoint table growth | Phase 5 | After running 1000 workflow steps, verify checkpoint cleanup task runs and table size is bounded |
| Docker sandbox resource leak | Phase 5 | Run a sandbox tool that exceeds its timeout; verify container is killed and removed within 10s |
| Next.js middleware redirect loop (v1.3) | v1.3 Session & Auth Hardening | Automated test: visit /dashboard authenticated, assert no redirect chain > 1 hop |
| CVE-2025-29927 bypass (v1.3) | v1.3 Session & Auth Hardening | CI version gate: `next --version` ≥ 15.2.3; nginx header stripping in docker-compose |
| Keycloak optional boot failure (v1.3) | v1.3 Keycloak Runtime Config | Integration test: start backend with `KEYCLOAK_URL=""`, assert 200 on `/health` |
| bge-m3 dual-load after sidecar (v1.3) | v1.3 Performance & Embedding Sidecar | Log assertion: `bge_m3_model_loaded` absent from backend logs after sidecar active |
| tsvector language mismatch (v1.3) | v1.3 Performance & Embedding Sidecar | `EXPLAIN ANALYZE` on skills search query in CI |
| LangGraph topology + HITL checkpoints (v1.3) | v1.3 Skill & Security Builder | Pre-deployment checklist; drain HITL runs; E2E test for interrupted workflow after topology change |
| Navigation on login/API routes (v1.3) | v1.3 Navigation & UX Overhaul | Smoke test: `curl /api/copilotkit` returns JSON; Playwright: /login has no nav rail |
| agentskills.io compliance (v1.3) | v1.3 Skill Platform Compliance | `skills-ref validate` in CI on sample export |
| Local user + Keycloak workflow failure (v1.3) | v1.3 Keycloak Runtime Config | Test: schedule workflow as local user, assert Celery completes without 404 errors |
| SecurityScanner gap on builder output (v1.3) | v1.3 Skill & Security Builder | Unit test: builder pipeline includes SecurityScanner step before activation |

---

## Sources

- [LangGraph GRAPH_RECURSION_LIMIT documentation](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT)
- [LangGraph token limit exceeded issue #3717](https://github.com/langchain-ai/langgraph/issues/3717)
- [CopilotKit overrides LangGraph recursion limits, issue #1717](https://github.com/CopilotKit/CopilotKit/issues/1717)
- [LangGraph Persistence and Checkpointing documentation](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Checkpoint Best Practices 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [OWASP LLM Top 10 Vulnerabilities 2025](https://deepstrike.io/blog/owasp-llm-top-10-vulnerabilities-2025)
- [pgvector production guide - Instaclustr 2026](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [BAAI/bge-m3 Memory Requirements - HuggingFace](https://huggingface.co/BAAI/bge-m3/discussions/64)
- [LiteLLM Budgets and Rate Limits documentation](https://docs.litellm.ai/docs/proxy/users)
- [MCP Specification November 2025](https://modelcontextprotocol.io/specification/2025-11-25)
- [React Flow v12 Migration Guide](https://reactflow.dev/learn/troubleshooting/migrate-to-v12)
- [CVE-2025-29927 Technical Analysis — ProjectDiscovery](https://projectdiscovery.io/blog/nextjs-middleware-authorization-bypass) — HIGH confidence
- [Vercel Postmortem on Next.js Middleware Bypass](https://vercel.com/blog/postmortem-on-next-js-middleware-bypass) — HIGH confidence
- [Next.js Middleware Redirect Causes Infinite Loop — GitHub Issue #62547](https://github.com/vercel/next.js/issues/62547) — HIGH confidence
- [CVE-2025-64439 — LangGraph JsonPlusSerializer RCE](https://github.com/advisories/GHSA-wwqv-p2pp-99h5) — HIGH confidence
- [agentskills.io/specification](https://agentskills.io/specification) — HIGH confidence (fetched directly)
- [Optimizing Full Text Search with PostgreSQL tsvector — Thoughtbot](https://thoughtbot.com/blog/optimizing-full-text-search-with-postgres-tsvector-columns-and-triggers) — MEDIUM confidence
- [PostgreSQL tsvector documentation](https://www.postgresql.org/docs/current/textsearch-tables.html) — HIGH confidence
- [Auth Migration Hell — Security Boulevard](https://securityboulevard.com/2025/09/auth-migration-hell-why-your-next-identity-project-might-keep-you-up-at-night/) — MEDIUM confidence
- Code inspection: `backend/security/jwt.py`, `backend/core/config.py`, `backend/agents/master_agent.py`, `backend/security/keycloak_client.py`, `backend/memory/embeddings.py` — HIGH confidence (direct source)

---
*Pitfalls research for: Blitz AgentOS -- Enterprise Agentic OS Platform (v1.0 original + v1.3 additions)*
*Researched: 2026-02-24 | Updated: 2026-03-05*
