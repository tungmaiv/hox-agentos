# Phase 7: Hardening and Sandboxing - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Untrusted code executes safely in Docker sandbox containers with enforced resource limits, zero host access, and automatic cleanup. The full security perimeter is verified through automated penetration tests and PostgreSQL Row Level Security policies enforce user_id isolation as defense-in-depth. This phase does NOT add new agent capabilities — it hardens existing ones.

</domain>

<decisions>
## Implementation Decisions

### Sandbox invocation scope
- Sandbox executor is triggered by `sandbox_required: true` flag in the tool registry (`gateway/tool_registry.py`)
- Canvas "Code Execution" nodes always route through sandbox
- Agent-generated code does NOT auto-sandbox — agents use existing registered tools, not arbitrary eval
- Entry point: `sandbox/executor.py` receives code + language + timeout, spins container, returns structured result
- No interactive sessions — one-shot execution only

### Resource limits (fixed globally for MVP)
- CPU: 0.5 cores per container (hard limit via Docker `--cpus`)
- Memory: 256MB hard limit — container killed if exceeded
- Network: completely disabled (no outbound — sandboxed code cannot call external services)
- Timeout: 30 seconds default, configurable per canvas node up to 120s max
- Filesystem: read-only tmpfs only — zero host mounts, zero persistent state between runs

### Sandbox container lifecycle
- Container created fresh per execution request (no reuse)
- Destroyed immediately after execution completes OR on timeout
- Partial/leaked containers cleaned up by periodic background task
- No resource leaks: verify via Docker SDK `containers.list()` after each run in tests

### RLS implementation depth
- Tables receiving Row Level Security: `memory_facts`, `conversations`, `turns`, `credential_store`, `workflow_runs`, `workflow_run_results`
- Policy: `USING (user_id = current_setting('app.user_id')::uuid)` on SELECT/UPDATE/DELETE
- Service accounts (Celery workers, backend API) use `BYPASSRLS` PostgreSQL role — they MUST set `SET LOCAL app.user_id = '...'` before any query
- RLS is defense-in-depth: application-level `user_id` filtering in queries remains as primary control
- Admin superuser bypasses RLS by design (Postgres default)

### Security evidence format
- Automated pen tests live in `tests/security/` as standard pytest
- Tests verify cross-user isolation: authenticate as User A, attempt to read User B's memories/credentials → assert 403 or empty
- Credential scanner: `bandit` for Python secrets + `trufflehog` for git history — run on each CI commit
- All security tests run in the same `PYTHONPATH=. .venv/bin/pytest tests/security/` command
- Passing = zero cross-user data leaks, zero high-severity bandit findings
- No separate security dashboard for MVP

### Claude's Discretion
- Exact Docker image to use as sandbox base (Alpine or distroless)
- Specific seccomp/AppArmor profile to apply to containers
- Whether to use `cgroups` v1 or v2 for resource enforcement
- Error message format returned to agents on sandbox failure
- Exact bandit severity threshold for CI failure (high vs medium)

</decisions>

<specifics>
## Specific Ideas

- Sandbox must work for Python code execution at minimum (primary use case for canvas Code nodes)
- RLS should be applied via Alembic migration (not manual SQL) so it's tracked in version control
- Tests should run without Docker available in CI (mock Docker SDK calls in unit tests, integration tests require Docker)

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-hardening-and-sandboxing*
*Context gathered: 2026-03-01*
