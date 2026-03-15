# Domain Pitfalls

**Domain:** Platform Enhancement & Infrastructure (v1.4) — adding circuit breaker, MinIO storage, email OAuth, multi-CopilotKit, WebSocket dashboard, dark theme, scheduler UI, permission approval to existing AgentOS
**Researched:** 2026-03-15
**Confidence:** HIGH (verified against official docs, GitHub issues, project codebase, and known gotchas from v1.0-v1.3)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, security incidents, or block multiple features.

### Pitfall 1: Alembic Migration Branch Explosion from 9 Parallel Features

**What goes wrong:**
Nine features each add database tables or columns. If developed on parallel branches, each creates a migration with the same parent head (`617b296e937a`). Merging produces a multi-headed Alembic state. The project already has a history of this problem — migrations 002+003 branched, required merge `9754fd080ee2`, and later migrations 021 branched again (currently documented: "two active heads" before the recent merge). With 9 features in v1.4, the combinatorial merge problem becomes unmanageable.

**Why it happens:**
- Each feature branch runs `alembic revision --autogenerate` from the same head
- Parallel development means nobody coordinates migration numbering
- `alembic upgrade head` fails when there are multiple heads without a merge migration

**Consequences:**
- `just migrate` fails on any environment that doesn't have merge migrations
- Ordering-dependent migrations (e.g., `permission_requests` table references `tool_acl`) fail if applied out of order
- Test suite breaks because conftest.py creates tables from metadata, but migration chain is broken

**Prevention:**
1. Establish a strict migration creation sequence: assign migration number ranges per feature BEFORE development starts (e.g., 031-033 for Keycloak hardening, 034-035 for storage service, 036-037 for email)
2. Only ONE feature branch creates migrations at a time — others add ORM models but defer migration generation until their turn
3. Use a migration coordination document in `.planning/` that tracks: current head, who has the "migration lock", next available number
4. If parallel branches are unavoidable, create merge migrations immediately when merging to main — do not accumulate heads
5. Run `alembic heads` in CI to fail builds with multiple heads

**Detection:**
- `alembic heads` shows more than one revision
- `just migrate` fails with "Multiple heads" error
- Test suite passes locally but fails on CI (different migration order)

---

### Pitfall 2: WebSocket Authentication Bypass and Connection Leak

**What goes wrong:**
The Unified Dashboard (#08+#14) introduces WebSocket for real-time activity feeds. FastAPI's `Depends()` dependency injection does NOT work with WebSocket endpoints the same way as HTTP. The browser WebSocket API cannot send custom headers after the initial handshake. JWT tokens passed as query parameters end up in server logs, proxy logs, and browser history.

**Why it happens:**
- Developers copy the existing `get_current_user()` HTTP dependency and apply it to WebSocket endpoints — it fails silently or throws cryptic errors
- `OAuth2PasswordBearer` looks at the `Request` object, which doesn't exist in WebSocket context
- After the initial handshake, there's no mechanism to re-authenticate — a revoked JWT remains valid for the WebSocket lifetime
- Long-lived WebSocket connections (dashboard left open) outlive JWT expiry without re-validation

**Consequences:**
- Unauthenticated users can receive real-time system metrics (information disclosure)
- Revoked users maintain active WebSocket connections after being disabled
- Memory leak from abandoned WebSocket connections that never close
- Server resource exhaustion from unauthenticated connection attempts

**Prevention:**
1. Create a dedicated `get_ws_current_user()` dependency that extracts JWT from the WebSocket query parameter during handshake ONLY, validates it, then stores `user_id` on the connection state
2. Implement a periodic heartbeat (every 60s) that re-validates the JWT — disconnect if expired or revoked
3. Never log the query parameter containing the JWT — strip it from access logs
4. Set a maximum WebSocket connection duration (e.g., 4 hours) with graceful reconnection
5. Track active WebSocket connections per user in Redis — enforce a per-user connection limit (e.g., 5)
6. Use a short-lived WebSocket ticket pattern: REST call to get a single-use ticket, connect with ticket, ticket expires after first use

**Detection:**
- WebSocket connections surviving beyond JWT expiry time
- WebSocket endpoint accessible without any token
- Server memory growing linearly with time (connection leak)

---

### Pitfall 3: MinIO Docker Image Unavailability and Credential Initialization Race

**What goes wrong:**
MinIO ceased publishing official Docker images to Docker Hub and Quay for the Community Edition on October 23, 2025. Using `minio/minio:latest` will pull a stale, potentially vulnerable image. Additionally, fresh MinIO containers started via Docker Compose against empty volumes ignore `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` environment variables under certain race conditions.

**Why it happens:**
- MinIO shifted to a source-only distribution model for Community Edition
- The Docker Hub `minio/minio:latest` tag is frozen at October 2025 and contains unpatched CVEs (CVE-2025-62506)
- Volume permissions: the MinIO process runs as a specific UID inside the container, and if the host directory doesn't match, MinIO crashes silently
- On first startup with an empty volume, credential environment variables may be ignored if the container restarts before initialization completes

**Consequences:**
- Security vulnerability from unpatched Docker images
- Avatar uploads (UX Enhancement #13) and file storage (#19) silently fail
- `docker compose up` works, but MinIO returns 403 on all operations because default credentials weren't applied
- Data loss if volumes aren't properly mounted (in-container storage vanishes on restart)

**Prevention:**
1. Use a pinned, maintained MinIO image: `quay.io/minio/minio:RELEASE.2025-01-10T21-58-47Z` or build from source via a multi-stage Dockerfile
2. Add MinIO healthcheck in `docker-compose.yml`: `curl -f http://localhost:9000/minio/health/live`
3. Create a MinIO init script that runs after healthcheck passes: creates the default bucket, sets bucket policy
4. Mount a named Docker volume (not a bind mount) for data persistence — same pattern as `postgres_data`
5. Pin `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `.env` — never use defaults
6. Add MinIO to the `depends_on` chain for backend service with `condition: service_healthy`

**Detection:**
- `docker compose logs minio` shows permission errors or credential warnings
- Backend returns 500 on avatar upload with `S3Error` in logs
- MinIO console (port 9001) shows empty bucket list after restart

---

### Pitfall 4: CopilotKit Multi-Instance Context Bleeding

**What goes wrong:**
Multi-Agent Tab Architecture (#16) requires multiple CopilotKit instances on the same page (one per builder tab). CopilotKit's `useCopilotChat` hook has documented issues with its `id` option — message states leak between instances using different IDs. Components using different IDs should have separate message states, but in practice they share underlying React context.

**Why it happens:**
- CopilotKit v1.51.4 uses a single `CopilotKitProvider` context at the tree root — all `useCopilotChat` hooks share this context
- The `id` parameter on `useCopilotChat` was designed for route-based isolation, not simultaneous multi-instance isolation
- The AG-UI protocol routes all messages through a single `POST /api/copilotkit` endpoint — there's no per-tab routing
- Thread IDs may collide if multiple tabs create conversations simultaneously

**Consequences:**
- Skill builder conversation pollutes tool builder conversation (the exact bug #16 is meant to fix)
- Agent state from one tab overwrites another tab's state mid-stream
- Memory saving uses wrong `conversation_id`, corrupting user memory
- "Message bleed" — user sees responses from wrong agent in wrong tab

**Prevention:**
1. Do NOT use multiple `CopilotKitProvider` instances — CopilotKit is not designed for this. Instead, use a single provider with a tab-switching mechanism that swaps the active `agentId` and `threadId`
2. Each builder tab gets a unique `threadId` stored in React state — switching tabs updates the provider's thread
3. If true parallel agents are needed, use iframes with separate CopilotKit contexts (heavy but isolated)
4. Alternatively, implement a custom AG-UI client that routes requests per tab without CopilotKit's shared context
5. Test with console logging on `useCopilotChat` to verify message isolation before building full UI
6. Consider a "one active builder at a time" UX constraint — simpler and avoids the multi-instance problem entirely

**Detection:**
- Open two builder tabs, type in one — messages appear in the other
- Agent responds to the wrong artifact type
- `threadId` in backend logs doesn't match the active tab's expected thread

---

### Pitfall 5: OAuth Email Token Refresh Failure and Google's Post-2025 Restrictions

**What goes wrong:**
Email System (#18) requires OAuth for Gmail and Microsoft 365. As of March 14, 2025, Google completely disabled app passwords and basic authentication for IMAP/SMTP. OAuth tokens expire (Google: 1 hour, Microsoft: varies), and refresh tokens can be revoked by the user or admin at any time. A failed refresh means the email channel silently stops receiving/sending with no notification to the user.

**Why it happens:**
- OAuth refresh tokens have limited lifetime and can be revoked unilaterally by the provider
- Google requires re-consent if certain scopes change or if the app hasn't been used in 6 months
- Microsoft enforces Conditional Access policies that can invalidate tokens based on location/device
- The Celery background task for token refresh runs on a schedule — if it fails, the next email operation discovers the stale token at runtime
- AES-256 encrypted tokens in `user_credentials` table don't carry "last refreshed" metadata

**Consequences:**
- User's email integration silently stops working — no emails fetched, no notifications sent
- Agent tries to send email, gets 401, returns error to user mid-conversation
- Stale encrypted tokens accumulate in the database (dead credentials)
- If refresh fails during a workflow execution, the entire workflow fails at the email step

**Prevention:**
1. Add `last_refreshed_at` and `expires_at` columns to `user_credentials` — proactively refresh tokens before expiry (e.g., 5 minutes before)
2. Celery periodic task (every 15 minutes) attempts refresh for all email credentials expiring within 30 minutes
3. On refresh failure: update credential status to `expired`, notify user via in-app notification AND their preferred channel
4. Email agent checks credential freshness before attempting send/fetch — return structured error "Your email connection has expired, please re-authenticate" instead of crashing
5. Store the OAuth provider's error response (scope_changed, consent_required, account_disabled) to give actionable re-auth instructions
6. For Google: request `offline` access type and `prompt=consent` on first auth to get a long-lived refresh token

**Detection:**
- `user_credentials` rows where `expires_at < NOW()` with no recent refresh
- Email agent returning 401 errors in audit logs
- Users reporting "email stopped working" after weeks of inactivity

---

## Moderate Pitfalls

These cause significant debugging time or partial feature breakage, but are recoverable.

### Pitfall 6: Dark Theme FOUC (Flash of Unstyled Content) on SSR

**What goes wrong:**
Next.js server-renders HTML with the default (light) theme because the server doesn't know the user's preference (stored in localStorage or cookies). On hydration, the client applies the dark theme, causing a visible flash from light to dark. This happens on every page navigation and full reload.

**Why it happens:**
- `localStorage` and `window.matchMedia('(prefers-color-scheme: dark)')` are not available during SSR
- Next.js App Router renders Server Components first — CSS variables resolve to light-mode defaults
- React hydration happens after the initial paint — there's a visible gap

**Prevention:**
1. Use `next-themes` library — it injects a blocking `<script>` in `<head>` that reads localStorage before any content renders
2. If building custom: add an inline `<script>` in `app/layout.tsx` (via `dangerouslySetInnerHTML`) that sets `document.documentElement.dataset.theme` before React loads
3. Store theme preference in a cookie (not just localStorage) so the server can read it during SSR via `cookies()` API
4. Use CSS `color-scheme: dark` on `<html>` element to hint the browser before styles load
5. Test with `Slow 3G` network throttling in DevTools — FOUC is most visible on slow connections

**Detection:**
- White flash on page load when user has dark mode enabled
- `prefers-color-scheme: dark` users see light mode for 100-500ms on first load
- Screenshots in Playwright tests show wrong theme

---

### Pitfall 7: Circuit Breaker State Persistence Across Backend Restarts

**What goes wrong:**
Keycloak SSO Hardening (#07) adds a circuit breaker for Keycloak connectivity. If the circuit breaker state is stored in-process (Python module-level variable), it resets on every backend container restart or Uvicorn worker reload. This means: Keycloak goes down, circuit opens, backend restarts (e.g., deploy), circuit resets to closed, backend immediately hammers dead Keycloak with requests, all requests timeout (30s each), system appears frozen.

**Why it happens:**
- Python `circuitbreaker` and `pybreaker` libraries store state in memory by default
- Docker Compose restart recreates the container — all in-memory state lost
- Uvicorn with `--reload` (dev mode) restarts workers on file changes
- Multiple Uvicorn workers (if concurrency > 1) each have independent circuit breaker state

**Prevention:**
1. Store circuit breaker state in Redis: `circuit:keycloak:state` = `closed|open|half_open`, `circuit:keycloak:failure_count`, `circuit:keycloak:last_failure_at`
2. On startup, read circuit state from Redis — if `open` and within timeout window, stay open
3. Use a single `async` circuit breaker implementation (not thread-based) compatible with FastAPI's event loop
4. Set reasonable thresholds: 3 failures to open, 60s recovery timeout, 1 probe request in half-open state
5. Log all circuit state transitions to audit log — admins need to see when Keycloak was unreachable

**Detection:**
- After backend restart during Keycloak outage, all requests hang for 30s (circuit didn't stay open)
- Keycloak health dashboard shows "healthy" but circuit is still open (stale state)

---

### Pitfall 8: Temporal ACL Entries Never Expire (Permission Approval #01)

**What goes wrong:**
Runtime Permission Approval creates `ToolAcl` entries with an `expires_at` field. But the existing `check_tool_acl()` function (140 lines in `security/acl.py`) doesn't check expiration — it only checks `allowed: bool`. Approved temporal permissions persist forever in practice, violating the principle of least privilege.

**Why it happens:**
- Original `tool_acl` table has no `expires_at` column — it must be added
- Existing `check_tool_acl()` query is `SELECT ... WHERE role = $1 AND tool_name = $2 AND allowed = true` — no time filter
- Background cleanup tasks for expired entries are easy to forget
- Auto-approve rules may create entries without expiration by default

**Consequences:**
- Users retain elevated permissions indefinitely after a one-time approval
- Security audit shows users with permissions they shouldn't have
- Admin can't tell which permissions were granted temporarily vs permanently

**Prevention:**
1. Add `expires_at TIMESTAMP NULL` and `granted_by UUID` and `grant_type VARCHAR` (permanent/temporal/auto) to `tool_acl` table
2. Modify `check_tool_acl()` query: `WHERE ... AND (expires_at IS NULL OR expires_at > NOW())`
3. Add Celery periodic task (hourly) to hard-delete expired ACL entries and log removals
4. Default temporal grants to 24 hours — admin can extend during approval
5. Admin UI shows grant type and expiration in permission matrix

**Detection:**
- `SELECT * FROM tool_acl WHERE expires_at < NOW()` returns rows (expired but still active)
- User can access tool weeks after "temporary" approval

---

### Pitfall 9: Tremor Charts Break Server Components and Inflate Bundle

**What goes wrong:**
The Unified Dashboard (#08+#14) uses Tremor for charts. All Tremor chart components (`BarChart`, `LineChart`, `AreaChart`, `DonutChart`) require client-side rendering (`"use client"`). Developers place chart components in pages that are Server Components by default, causing build errors or hydration mismatches. Additionally, Tremor's full bundle is large (~200KB gzipped) and importing it in multiple dashboard pages bloats the client bundle.

**Why it happens:**
- Next.js App Router defaults to Server Components — forgetting `"use client"` causes cryptic errors
- Tremor components internally use `useRef`, `useState`, `useEffect` — incompatible with RSC
- Importing `@tremor/react` at the top level pulls in all chart types even if only one is used

**Prevention:**
1. Create a `components/dashboard/charts/` directory with explicit `"use client"` wrappers for each chart type
2. Use `next/dynamic` with `ssr: false` for chart components to prevent SSR attempts: `const BarChart = dynamic(() => import('./bar-chart'), { ssr: false })`
3. Import specific chart components: `import { BarChart } from '@tremor/react'` — tree shaking works with named imports
4. Wrap Tremor charts in `<Suspense fallback={<ChartSkeleton />}>` for loading states
5. If Tailwind prose classes are used in the same page, wrap charts with `className="not-prose"` to prevent style interference

**Detection:**
- Build error: "useState is not allowed in Server Components"
- Hydration mismatch warnings in browser console
- Bundle analyzer shows @tremor/react in multiple chunks

---

### Pitfall 10: Scheduler UI Misalignment with Existing Celery Architecture

**What goes wrong:**
Scheduler UI (#15) assumes REST APIs for job management (`GET /api/scheduler/jobs`, `POST /api/scheduler/jobs/{id}/run-now`). But the existing scheduler uses Celery Beat + `workflow_triggers` table — there are NO scheduler REST endpoints (documented in `dev-context.md` gotchas). Building a UI against non-existent APIs means the entire backend must be built first, and the UI design may not match what's actually possible with Celery.

**Why it happens:**
- Design spec (#15) describes a rich scheduler API, but v1.3 has zero scheduler HTTP routes
- Celery Beat reads from a database schedule — it doesn't expose a management API
- "Run Now" requires triggering a Celery task programmatically, not just creating a database row
- Queue monitoring (depth, worker count) requires Celery's `inspect` API, which is synchronous and blocking

**Consequences:**
- Frontend built against mock APIs that don't match eventual backend behavior
- Celery's `inspect` API blocks the event loop when called from async FastAPI handlers
- "Run Now" implementation is more complex than expected — must find the workflow, create a WorkflowRun, submit to Celery, and track status
- Queue depth monitoring requires `celery -A scheduler.celery_app inspect active` which spawns a subprocess

**Prevention:**
1. Build backend APIs FIRST, then UI — never build UI against assumed API shapes
2. For Celery inspect: run in a thread pool executor (`asyncio.to_thread()`) to avoid blocking the event loop
3. For "Run Now": reuse the existing `POST /api/workflows/{id}/run` endpoint — don't duplicate execution logic
4. Store job metadata (last_run, next_run, run_count, last_status) in `workflow_triggers` table — don't query Celery for historical data
5. Use Celery's `flower` monitoring or Redis-backed metrics instead of synchronous inspect calls

**Detection:**
- Frontend shows "0 workers" because inspect call timed out
- "Run Now" button creates a WorkflowRun but doesn't actually execute (Celery task not submitted)
- Schedule changes in UI don't take effect until Celery Beat restarts

---

### Pitfall 11: Docker Compose Port Exhaustion with MinIO + Email Sidecar

**What goes wrong:**
v1.4 adds MinIO (ports 9000 + 9001 for console) and email sidecar to an already port-heavy Docker Compose setup. The existing `docker-compose.yml` already uses ports 3000, 3001, 4000, 5432, 6379, 7997, 8000, 8001, 8002, 8003, 8180, 7443, 9001, 9002, 9003. Adding MinIO on 9000 conflicts with nothing, but MinIO console on 9001 conflicts with the Telegram gateway (currently port 9001).

**Why it happens:**
- Port assignments are scattered across docker-compose.yml — no central registry
- MinIO default ports (9000 API, 9001 console) are common and likely to conflict
- Developers don't check existing port allocations before adding services

**Consequences:**
- `docker compose up` fails with "port already in use" — Telegram gateway and MinIO console fight for 9001
- Debugging port conflicts is time-consuming — error messages don't specify which service owns the port

**Prevention:**
1. Reassign MinIO to non-conflicting ports: API on 9100, Console on 9101 (or only expose API, not console)
2. Maintain a port allocation table in `docs/dev-context.md` — update it when adding any service
3. For email sidecar: use a port in the 9200+ range (e.g., 9200 for IMAP listener)
4. Consider NOT exposing MinIO ports to the host — backend accesses it via Docker network (`minio:9000`), no host exposure needed
5. Updated port map should be the FIRST thing committed when adding a new Docker service

**Detection:**
- `just up` fails with `bind: address already in use`
- Telegram webhook stops working after adding MinIO (port hijacked)

---

### Pitfall 12: WebSocket Scaling Conflicts with Uvicorn Single-Worker

**What goes wrong:**
The dashboard WebSocket requires the backend to maintain persistent connections. The current backend runs Uvicorn with a single worker (`uvicorn main:app --host 0.0.0.0 --port 8000` — no `--workers` flag). A single worker means WebSocket connections share the event loop with HTTP request processing. If 20 users open the dashboard (20 WebSocket connections) and a workflow triggers a complex agent call, the event loop saturates and WebSocket messages queue up, making the dashboard appear frozen.

**Why it happens:**
- WebSocket connections are persistent — each consumes event loop attention even when idle
- Agent calls (LLM inference) can take 5-30 seconds — during this time, WebSocket heartbeats may miss their window
- No worker isolation: HTTP API and WebSocket share the same Uvicorn process

**Prevention:**
1. Keep WebSocket on a SEPARATE FastAPI app/mount or use a lightweight WebSocket-only service
2. If keeping in the same process: use `asyncio.create_task()` for all WebSocket message broadcasting — never block the main event loop waiting for broadcasts
3. Use Redis Pub/Sub for WebSocket message distribution — backend publishes events to Redis, a dedicated WebSocket handler subscribes and pushes to clients
4. Set WebSocket ping/pong interval to 30s with 10s timeout — detect dead connections early
5. Limit concurrent WebSocket connections to 50 total (more than enough for 100 users, most won't have dashboard open)

**Detection:**
- Dashboard "freezes" when agent is processing a request
- WebSocket connections disconnect with 1006 (abnormal closure) during high load
- Backend health check starts timing out when many dashboards are open

---

## Minor Pitfalls

These cause confusion or minor bugs, but are quick to fix.

### Pitfall 13: Dark Theme CSS Variables Conflict with Existing Tailwind Classes

**What goes wrong:**
The existing codebase uses hardcoded Tailwind color classes (`bg-white`, `text-gray-900`, `border-gray-200`) throughout 18,959 LOC of TypeScript. Adding CSS variables for theming requires replacing ALL hardcoded color references with variable-based classes (`bg-background`, `text-foreground`). Missing even one `bg-white` class means that component stays white in dark mode.

**Prevention:**
1. Do a comprehensive grep for all hardcoded color classes BEFORE starting: `grep -r "bg-white\|bg-gray\|text-gray\|border-gray" --include="*.tsx" --include="*.ts" | wc -l`
2. Create a migration script or Tailwind plugin that maps old colors to CSS variables
3. Start with layout components (nav rail, sidebar, page backgrounds) — they're most visible
4. Use Tailwind's `dark:` variant as a fallback for components not yet migrated
5. Add a Playwright visual regression test that screenshots key pages in both themes

---

### Pitfall 14: Permission Request Queue Flooding from Automated Workflows

**What goes wrong:**
Runtime Permission Approval (#01) pauses execution on permission denial. If a scheduled workflow runs hourly and hits a permission wall every time, it creates 24 permission requests per day per workflow. Admin's approval queue fills with duplicate requests for the same user+tool combination.

**Prevention:**
1. Deduplicate: if a pending `PermissionRequest` already exists for the same `user_id + tool_name`, don't create another — attach the new execution to the existing request
2. Add `request_count` column to track how many times this permission was requested
3. Auto-reject duplicate requests from the same workflow within a cooldown window (1 hour)
4. Show "already requested" status in workflow execution logs instead of pausing again

---

### Pitfall 15: MCP Connection Test Timeout Blocks Admin UI

**What goes wrong:**
Admin Registry Edit UI (#06) adds "Test Connection" for MCP servers. MCP servers use HTTP+SSE — the test sends a request to the `/sse` endpoint. If the MCP server is down or the URL is wrong, the HTTP request hangs for the default timeout (30s+ for httpx). The admin UI freezes with a spinner for 30 seconds before showing an error.

**Prevention:**
1. Set a strict 5-second timeout on MCP connection tests: `httpx.AsyncClient(timeout=5.0)`
2. Run the test in a background task, return immediately with a `test_id`, poll for result
3. Show a progress indicator with a "Cancel" button
4. Cache test results for 60 seconds — don't re-test the same server within a minute

---

### Pitfall 16: Avatar Upload Without Size/Type Validation

**What goes wrong:**
User Experience Enhancement (#13) adds avatar upload to MinIO. Without validation, users upload 50MB PNGs, SVG files with embedded scripts (XSS), or non-image files renamed to .jpg. The frontend renders these without sanitization.

**Prevention:**
1. Backend validation: max 2MB, allowed MIME types `image/jpeg`, `image/png`, `image/webp` only (NO SVG)
2. Validate MIME type by reading file magic bytes — not just the extension
3. Re-encode uploaded images server-side (resize to 256x256, convert to WebP) to strip EXIF data and embedded payloads
4. Serve avatars with `Content-Security-Policy: default-src 'none'` header
5. Store in MinIO with a content-addressed path: `avatars/{user_id}/{sha256}.webp`

---

### Pitfall 17: Cron Builder Timezone Mismatch with Celery Beat

**What goes wrong:**
Scheduler UI (#15) includes a visual cron builder with timezone support. Users set "every day at 9:00 AM Hanoi time" (UTC+7). But Celery Beat stores cron expressions in UTC by default. If the timezone conversion is wrong or missing, the job runs at 9:00 AM UTC (4:00 PM Hanoi time).

**Prevention:**
1. Store timezone alongside cron expression in `workflow_triggers` table
2. Convert to UTC at storage time, but display in user's timezone in the UI
3. Show "Next 5 runs" preview in the user's timezone before saving
4. Use `croniter` library for next-run calculation — it handles timezone-aware datetimes correctly
5. Test across DST boundaries (though Vietnam doesn't observe DST, future users may)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Keycloak SSO Hardening (#07) | Circuit breaker resets on container restart (Pitfall 7) | Store state in Redis; read on startup |
| Keycloak SSO Hardening (#07) | Circuit breaker too aggressive — opens on 1 timeout, blocks all SSO | Set threshold to 3+ failures; always allow local auth fallback |
| Admin Registry Edit UI (#06) | MCP test timeout freezes UI (Pitfall 15) | 5-second timeout; background task pattern |
| Admin Registry Edit UI (#06) | Edit form breaks unified `registry_entries` table — updates overwrite config JSON fields | Use JSON merge patch, not full replacement; validate schema before save |
| Scheduler UI (#15) | UI built before backend APIs exist (Pitfall 10) | Backend-first; reuse existing workflow run endpoints |
| Scheduler UI (#15) | Cron timezone mismatch (Pitfall 17) | Store timezone; preview next runs in user TZ |
| Permission Approval (#01) | Temporal ACL entries never expire (Pitfall 8) | Add expires_at to query; hourly cleanup task |
| Permission Approval (#01) | Queue flooding from scheduled workflows (Pitfall 14) | Deduplicate pending requests per user+tool |
| Multi-Agent Tab (#16) | CopilotKit context bleeding between tabs (Pitfall 4) | Single provider with tab-switching, not multiple providers |
| Multi-Agent Tab (#16) | Multiple AG-UI streams compete for the same SSE connection | Ensure only one active stream per browser tab |
| UX Enhancement (#13) | Dark theme FOUC (Pitfall 6) | Use next-themes or blocking script in head |
| UX Enhancement (#13) | Avatar upload XSS via SVG (Pitfall 16) | Reject SVG; re-encode to WebP server-side |
| UX Enhancement (#13) | Avatar requires MinIO but MinIO is a separate feature (#19) | Either: make #13 depend on #19, or store avatars in PostgreSQL bytea (temporary) |
| Unified Dashboard (#08+#14) | WebSocket auth bypass (Pitfall 2) | Dedicated WS auth; periodic JWT re-validation |
| Unified Dashboard (#08+#14) | WebSocket blocks event loop (Pitfall 12) | Redis Pub/Sub for broadcasting; separate from HTTP |
| Unified Dashboard (#08+#14) | Tremor breaks SSR (Pitfall 9) | Dynamic import with ssr: false |
| Storage Service (#19) | MinIO image unavailable or credentials race (Pitfall 3) | Pin image version; named volume; init script |
| Storage Service (#19) | MinIO port conflicts with Telegram gateway (Pitfall 11) | Reassign to 9100/9101; update port map |
| Email System (#18) | OAuth token refresh failure (Pitfall 5) | Proactive refresh; expiry monitoring; user notification |
| Email System (#18) | Google requires OAuth-only (no app passwords) since March 2025 | Implement full OAuth 2.0 flow; no IMAP password fallback for Gmail |
| Email System (#18) | IMAP IDLE long polling blocks Celery worker threads | Run IMAP listener in a dedicated asyncio service, not in Celery |

---

## Integration Pitfalls (Cross-Feature)

### Cross-Feature 1: Feature Dependency Ordering

Several v1.4 features have hidden dependencies:

```
Storage Service (#19) ← UX Enhancement (#13) needs MinIO for avatars
Email System (#18) ← Unified Dashboard (#08) wants email notifications for alerts
Permission Approval (#01) ← Multi-Agent Tab (#16) needs permission escalation for builder agents
Scheduler UI (#15) ← Unified Dashboard (#14) displays scheduled job status
```

**Mitigation:** Build in dependency order: Storage (#19) before UX (#13), Scheduler API before Dashboard (#14). Or use feature flags to degrade gracefully when dependencies aren't ready.

### Cross-Feature 2: Database Migration Coordination

Nine features = potentially 15+ new tables/columns. The current migration chain is linear (head: `617b296e937a`). If features are developed in parallel branches, expect migration conflicts.

**Mitigation:** Assign migration number ranges upfront. Features that only add columns to existing tables should use `op.add_column()` — these are inherently safe to reorder. Features that create new tables with foreign keys must be ordered by dependency.

### Cross-Feature 3: Docker Compose Complexity Explosion

Current `docker-compose.yml` has 17 services. Adding MinIO (+1), email sidecar (+1), and possibly a WebSocket gateway (+1) brings it to 20. `just up` startup time increases. Memory consumption increases. Developer machines with <16GB RAM will struggle.

**Mitigation:** Create a `docker-compose.override.yml` for optional services (MinIO, email sidecar) that developers enable only when working on those features. Core services remain in the base file. Document minimum RAM requirement (16GB recommended, 8GB minimum without MinIO/email).

---

## Sources

- [MinIO Docker Hub deprecation (Oct 2025)](https://github.com/minio/minio/issues/21502)
- [MinIO credential initialization race](https://github.com/minio/minio/discussions/21406)
- [CopilotKit useCopilotChat ID isolation issue](https://github.com/CopilotKit/CopilotKit/issues/1159)
- [FastAPI WebSocket JWT authentication](https://dev.to/hamurda/how-i-solved-websocket-authentication-in-fastapi-and-why-depends-wasnt-enough-1b68)
- [FastAPI WebSocket Depends() incompatibility](https://github.com/fastapi/fastapi/issues/2587)
- [Circuit breaker pattern in FastAPI](https://blog.stackademic.com/system-design-1-implementing-the-circuit-breaker-pattern-in-fastapi-e96e8864f342)
- [Next.js dark mode FOUC prevention](https://notanumber.in/blog/fixing-react-dark-mode-flickering)
- [next-themes library](https://github.com/pacocoursey/next-themes)
- [Google OAuth enforcement (March 2025)](https://support.google.com/a/answer/14114704)
- [Alembic migration conflicts in multi-developer environments](https://github.com/sqlalchemy/alembic/discussions/1543)
- [Tremor Next.js installation guide](https://www.tremor.so/docs/getting-started/installation/next)
