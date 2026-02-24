# Pitfalls Research

**Domain:** Enterprise Agentic OS Platform (LangGraph + CopilotKit + React Flow + Keycloak + pgvector + LiteLLM + Multi-Channel)
**Researched:** 2026-02-24
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

## Sources

- [LangGraph GRAPH_RECURSION_LIMIT documentation](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT)
- [LangGraph token limit exceeded issue #3717](https://github.com/langchain-ai/langgraph/issues/3717)
- [CopilotKit overrides LangGraph recursion limits, issue #1717](https://github.com/CopilotKit/CopilotKit/issues/1717)
- [LangGraph Persistence and Checkpointing documentation](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Checkpoint Best Practices 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [OWASP LLM Top 10 Vulnerabilities 2025](https://deepstrike.io/blog/owasp-llm-top-10-vulnerabilities-2025)
- [LLM Security Risks 2026 - Sombra](https://sombrainc.com/blog/llm-security-risks-2026)
- [LLM Security Risks and Mitigation - USCS Institute](https://www.uscsinstitute.org/cybersecurity-insights/blog/what-are-llm-security-risks-and-mitigation-plan-for-2026)
- [pgvector production guide - Instaclustr 2026](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [pgvector for AI Memory in Production - Ivan Turkovic](https://www.ivanturkovic.com/2025/11/16/pgvector-for-ai-memory-in-production-applications/)
- [BAAI/bge-m3 Memory Requirements - HuggingFace](https://huggingface.co/BAAI/bge-m3/discussions/64)
- [BAAI/bge-m3 OOM on 8GB GPU - HuggingFace](https://huggingface.co/BAAI/bge-m3/discussions/2)
- [BAAI/bge-m3 Inference Speed Optimization - HuggingFace](https://huggingface.co/BAAI/bge-m3/discussions/9)
- [LiteLLM Budgets and Rate Limits documentation](https://docs.litellm.ai/docs/proxy/users)
- [LiteLLM Fallbacks documentation](https://docs.litellm.ai/docs/proxy/reliability)
- [LiteLLM Review 2026 - TrueFoundry](https://www.truefoundry.com/blog/a-detailed-litellm-review-features-pricing-pros-and-cons-2026)
- [MCP Specification November 2025](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Transport Future - Blog](http://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/)
- [MCP Enterprise Adoption Guide 2025](https://guptadeepak.com/the-complete-guide-to-model-context-protocol-mcp-enterprise-adoption-market-trends-and-implementation-strategies/)
- [CopilotKit Human-in-the-Loop documentation](https://docs.copilotkit.ai/human-in-the-loop)
- [CopilotKit + LangGraph.js HITL Integration Guide](https://chanmeng666.medium.com/copilotkit-langgraph-js-hitl-integration-guide-964468f1ed5c)
- [React Flow v12 Migration Guide](https://reactflow.dev/learn/troubleshooting/migrate-to-v12)
- [Ollama Docker Integration - Arsturn](https://www.arsturn.com/blog/integrating-ollama-with-docker-overcoming-common-challenges)
- [Ollama FAQ - Official](https://docs.ollama.com/faq)
- [Docker Networking Guide 2026](https://www.testleaf.com/blog/docker-networking-real-world-container-communication-2026/)
- [Celery Security Documentation](https://docs.celeryq.dev/en/stable/userguide/security.html)
- [Keycloak JWT Guide - Inteca](https://inteca.com/blog/identity-access-management/exploring-keycloak-jwt-a-comprehensive-guide/)
- [PostgresSaver row_factory requirement - LangGraph docs](https://fast.io/resources/langgraph-persistence/)

---
*Pitfalls research for: Blitz AgentOS -- Enterprise Agentic OS Platform*
*Researched: 2026-02-24*
