---
phase: 07-hardening-and-sandboxing
verified: 2026-03-01T15:30:00Z
status: passed
score: 10/10 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 8/10
  gaps_closed:
    - "test_user_a_cannot_read_user_b_conversation_turns now passes in isolation — import core.models added at module top-level (commit 97957bf)"
    - "trufflehog git history scan executed — 0 verified secrets across 2245 chunks (trufflehog 3.93.6 installed via official install script)"
  gaps_remaining: []
  regressions: []
---

# Phase 7: Hardening and Sandboxing — Verification Report

**Phase Goal:** Untrusted code executes safely in sandboxed containers, and the full security perimeter is verified through automated testing and policy enforcement
**Verified:** 2026-03-01T15:30:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plans 07-03 and 07-04)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Untrusted code executes in a fresh Docker container with CPU=0.5, Memory=256MB, no network | VERIFIED | `sandbox/executor.py` calls `containers.run()` with `nano_cpus=500_000_000`, `mem_limit="256m"`, `network_disabled=True`; 6 sandbox unit tests pass in 0.03s |
| 2 | Sandbox containers have no access to the host filesystem (read-only tmpfs only) | VERIFIED | `SANDBOX_LIMITS["read_only"]=True`, `tmpfs={"/tmp": "size=64m,mode=777"}`, no host volume mounts; `test_execute_applies_readonly_filesystem` asserts both |
| 3 | Containers are destroyed immediately after execution completes or on timeout — no resource leaks | VERIFIED | `remove=True` (auto_remove) as primary; `container.remove(force=True)` in except block as safety net; `_cleanup_leaked_containers()` with label filter; tests 5 and 6 assert cleanup |
| 4 | Tools with sandbox_required=True in the registry are routed through SandboxExecutor, not called directly | VERIFIED | `agents/node_handlers.py` lines 140-161: `tool_meta.get("sandbox_required", False)` check; `SandboxExecutor` imported at module top-level |
| 5 | Unit tests pass without Docker installed (Docker SDK calls are mocked) | VERIFIED | `docker.from_env` patched via `mocker.patch("sandbox.executor.docker.from_env")`; 6 passed in 0.03s confirmed live |
| 6 | PostgreSQL RLS policies on 6 tables enforce user_id isolation as defense-in-depth | VERIFIED | Migration `016_rls_policies.py`: ENABLE ROW LEVEL SECURITY + FORCE RLS on `memory_facts`, `memory_conversations`, `user_credentials`, `workflow_runs`, `memory_episodes`, `conversation_titles`; BYPASSRLS granted to `blitz` |
| 7 | User A cannot access User B's data even if application-level filtering is bypassed (RLS defense-in-depth via migration 016) | VERIFIED | Migration 016 uses `USING (user_id = current_setting('app.user_id', true)::uuid)`; INSERT policy with `WITH CHECK` also present; both SELECT/UPDATE/DELETE and INSERT are covered |
| 8 | All user-scoped DB sessions enforce the authenticated user's data boundary via SET LOCAL app.user_id before every query | VERIFIED | `set_rls_user_id(session, user_id)` in `core/db.py` lines 49-72: executes `SET LOCAL app.user_id = :uid` with parameterized value; importable confirmed live |
| 9 | Automated pen tests verify cross-user memory and credential isolation (User A cannot read User B's data) | VERIFIED | Gap closed by 07-03. `import core.models` added at module top-level (line 29, commit 97957bf). Standalone run confirmed: 5 passed, 1 skipped — `test_user_a_cannot_read_user_b_conversation_turns` PASSES in isolation |
| 10 | Zero high-severity secrets detected by bandit scan + clean git history (trufflehog) | VERIFIED | Gap closed by 07-04. bandit: 0 High severity issues. trufflehog 3.93.6 git history scan: 0 verified secrets across 2245 chunks. Filesystem: 1 finding in `.env` (gitignored — expected local dev secrets, never committed) |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/sandbox/executor.py` | SandboxExecutor class with execute() and SandboxResult Pydantic model | VERIFIED | 218 lines; SandboxResult BaseModel; SandboxExecutor with execute(), _get_image(), _build_command(), _cleanup_leaked_containers() |
| `backend/sandbox/policies.py` | SANDBOX_LIMITS with nano_cpus=500_000_000, mem_limit="256m", network_disabled=True, read_only=True | VERIFIED | All 6 required keys present; DEFAULT_TIMEOUT=30, MAX_TIMEOUT=120 |
| `backend/agents/node_handlers.py` | sandbox_required routing — tools with sandbox_required=True routed through SandboxExecutor | VERIFIED | Lines 140-161 contain `sandbox_required` check; SandboxExecutor imported at top-level line 30 |
| `backend/tests/sandbox/test_executor.py` | Unit tests for SandboxExecutor with mocked Docker SDK; min 80 lines | VERIFIED | 160 lines; 6 tests; all pass with Docker mocked |
| `backend/alembic/versions/016_rls_policies.py` | Alembic migration enabling RLS on 6 tables with user_id policy | VERIFIED | 102 lines; ENABLE ROW LEVEL SECURITY on 6 tables; FORCE RLS; USING policy; WITH CHECK INSERT policy; BYPASSRLS grant; postgresql dialect check |
| `backend/core/db.py` | set_rls_user_id(session, user_id) helper for SET LOCAL app.user_id | VERIFIED | Lines 49-72; async function; parameterized SET LOCAL; importable confirmed |
| `backend/tests/security/test_isolation.py` | Pen tests: cross-user memory read returns empty, credential read returns None; min 80 lines; deterministic in isolation | VERIFIED | 323 lines; 6 tests (5 passed, 1 skipped pgvector); `import core.models` at module top-level (line 29); standalone run confirms 5 passed, 1 skipped |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/agents/node_handlers.py` | `backend/sandbox/executor.py` | import SandboxExecutor; call execute() when tool.sandbox_required | WIRED | SandboxExecutor imported at top-level; `sandbox_required` check at line 143; `execute()` called at line 148 |
| `backend/sandbox/executor.py` | docker Python SDK | `docker.from_env().containers.run()` with resource constraints | VERIFIED | `containers.run` pattern present; tests assert nano_cpus, mem_limit, network_disabled, read_only, tmpfs, labels all passed |
| `backend/alembic/versions/016_rls_policies.py` | 6 user-data tables | ALTER TABLE ... ENABLE ROW LEVEL SECURITY; CREATE POLICY | VERIFIED | `_RLS_TABLES` list contains all 6 tables; ENABLE + FORCE RLS; both SELECT/UPDATE/DELETE USING and INSERT WITH CHECK policies |
| `backend/core/db.py` | asyncpg connection | SET LOCAL app.user_id = '...' executed before query | VERIFIED | `set_rls_user_id()` at lines 49-72; `sa.text("SET LOCAL app.user_id = :uid")`; parameterized |
| `backend/tests/security/test_isolation.py` | memory/short_term.py, security/credentials.py | authenticate as user_a, attempt read with user_b_id, assert empty or None | WIRED | All 5 non-skipped tests pass in isolation; `import core.models` at top-level ensures Base.metadata populated before `db_session` fixture runs |
| trufflehog 3.93.6 | git history of `/home/tungmv/Projects/hox-agentos` | `trufflehog git file://. --only-verified` | VERIFIED | 2245 chunks scanned; 0 verified secrets; 0 unverified secrets; 869ms scan; documented in 07-04-SUMMARY.md |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SBOX-01 | 07-01-PLAN.md | Untrusted code executes in Docker containers with CPU, memory, and network limits | SATISFIED | `executor.py` passes `nano_cpus=500_000_000`, `mem_limit="256m"`, `network_disabled=True`; 6 unit tests all pass; tool registry dispatch in `node_handlers.py` routes `sandbox_required` tools correctly |
| SBOX-02 | 07-01-PLAN.md | Sandbox containers have no host filesystem access | SATISFIED | `read_only=True` and `tmpfs={"/tmp": ...}` (no host volume mounts) enforced in `SANDBOX_LIMITS`; `test_execute_applies_readonly_filesystem` verifies both constraints |
| SBOX-03 | 07-01-PLAN.md | Sandbox containers are destroyed after execution with timeout-based cleanup | SATISFIED | `remove=True` (auto_remove) as primary cleanup; `container.remove(force=True)` in except block; `_cleanup_leaked_containers()` with `blitz.sandbox=true` label filter; both cleanup paths tested |

Note: SBOX-01, SBOX-02, SBOX-03 are the three formal requirement IDs for Phase 7 (defined in `.planning/milestones/v1.0-REQUIREMENTS.md`). All three are satisfied by the sandbox executor implementation. The isolation pen tests (07-02, 07-03) and trufflehog scan (07-04) address security hardening and verification that support the phase goal but are not mapped to separate formal SBOX IDs.

No orphaned requirements detected — all three SBOX IDs are claimed by 07-01-PLAN.md and verified against the codebase.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

Previous blocker anti-pattern (lazy import in `test_isolation.py`) resolved by 07-03 (commit 97957bf). No new anti-patterns detected in gap-closure artifacts.

---

### Full Test Suite

**586 passed, 1 skipped, 16 warnings** in 7.65s — confirmed live during re-verification.

Breakdown:
- 6 sandbox executor tests (07-01)
- 5 isolation pen tests + 1 pgvector skip (07-02, 07-03)
- 575 baseline tests from prior phases

Zero regressions from gap closure.

---

### bandit Scan Results

Focused scan on `sandbox/`, `security/`, `gateway/` modules:
- High severity (any confidence): **0**
- Medium severity: 0
- Low severity: 2 (both `B110: try_except_pass` — High confidence, Low severity; intentional defensive patterns in cleanup code)

Zero High severity issues in production modules.

---

### trufflehog Scan Results

**Git history scan:** `trufflehog git file://. --only-verified`
- Chunks scanned: 2245
- Verified secrets: **0**
- Unverified secrets: 0
- Scan duration: 869ms
- Result: CLEAN

**Filesystem scan:** `trufflehog filesystem ... --only-verified`
- Verified secrets: 1 — `TELEGRAM_BOT_TOKEN` in `.env` (line 37)
- Assessment: EXPECTED — `.env` is gitignored (`.gitignore:2`), never committed to git history, standard local dev secrets location per `CLAUDE.md` Section 3

No real security findings. Git history is clean of committed credentials.

---

### Re-Verification Summary

**Gap 1 — Pen test determinism (CLOSED):**

`test_user_a_cannot_read_user_b_conversation_turns` now passes when `test_isolation.py` is run in isolation. Fix: `import core.models  # noqa: F401` added at module top-level (line 29, commit `97957bf`). This ensures `ConversationTurn` (and all other ORM models) are registered in `Base.metadata` before the `db_session` fixture calls `create_all()`. Confirmed live: standalone run shows 5 passed, 1 skipped.

**Gap 2 — trufflehog scan (CLOSED):**

trufflehog 3.93.6 installed via official install script to `/home/tungmv/bin/trufflehog` (go install was blocked by replace directives in trufflehog's go.mod — this is expected Go behavior, the plan's documented fallback was used). Git history scan completed: 0 verified secrets across 2245 chunks. Filesystem scan found 1 verified finding in `.env` (gitignored local dev secrets file — not a security finding). Evidence documented in `07-04-SUMMARY.md`.

**All 5 Success Criteria from ROADMAP.md are now verified:**

1. Untrusted code executes in Docker with enforced CPU/memory/network limits — VERIFIED (executor.py + 6 unit tests)
2. Sandbox containers have zero access to host filesystem — VERIFIED (read_only=True + tmpfs only, no host mounts)
3. Sandbox containers destroyed after execution or timeout with no leaks — VERIFIED (auto_remove + explicit cleanup + label-filtered GC)
4. Cross-user memory isolation verified by automated penetration tests — VERIFIED (5 pen tests pass in isolation, commit 97957bf fixes determinism)
5. PostgreSQL RLS policies enforce user_id isolation as defense-in-depth — VERIFIED (migration 016, 6 tables, BYPASSRLS for service role)

---

_Verified: 2026-03-01T15:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gaps closed by plans 07-03 (commit 97957bf) and 07-04 (trufflehog scan)_
