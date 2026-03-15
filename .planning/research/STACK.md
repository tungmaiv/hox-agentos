# Stack Research: Blitz AgentOS

**Domain:** Enterprise on-premise agentic operating system
**Researched:** 2026-02-24 (v1.0-v1.2) | 2026-03-05 (v1.3) | Updated: 2026-03-15 (v1.4 additions)
**Confidence:** HIGH (core stack verified via official docs and PyPI/npm; v1.4 additions MEDIUM-HIGH)

---

## v1.4 Stack Additions (NEW -- Research Focus for This Document)

This section documents only the new libraries and patterns needed for v1.4 (Platform Enhancement & Infrastructure). The existing stack (LangGraph, FastAPI, Next.js 15, CopilotKit, PostgreSQL + pgvector, Redis, Celery, LiteLLM, Keycloak, infinity-emb, jose, shadcn/ui Sidebar) remains unchanged.

The 9 v1.4 features drive stack additions across 6 categories:
1. **Circuit breaker** (Keycloak SSO Hardening)
2. **Charting/dashboard** (Unified Dashboard)
3. **WebSocket** (Mission Control real-time feeds)
4. **Object storage** (Storage Service + Avatar upload)
5. **Email/IMAP/SMTP** (Email System & Notifications)
6. **Theme management** (User Experience Enhancement)
7. **Cron builder UI** (Scheduler UI)

---

### 1. Circuit Breaker for Keycloak SSO Hardening (#07)

**Decision:** Use `tenacity` (already installed) for retry logic + custom lightweight circuit breaker class -- do NOT add `pybreaker`.

**Rationale:** `tenacity` (>=9.1.4) is already in the backend dependency list and provides retry with exponential backoff, jitter, and retry-on-exception filtering. A circuit breaker is a small state machine (CLOSED/OPEN/HALF-OPEN) that can be implemented in ~60 lines of Python using `tenacity` as the retry engine underneath. Adding `pybreaker` introduces a new dependency for a pattern that only applies to one integration point (Keycloak JWKS/OIDC).

The circuit breaker wraps three Keycloak operations:
- JWKS key fetch (`/protocol/openid-connect/certs`)
- OIDC discovery (`/.well-known/openid-configuration`)
- Token introspection (if used)

When tripped (e.g., 5 consecutive failures in 60s), the circuit breaker returns cached JWKS keys and falls back to local-auth-only mode. This aligns with the spec's "Keycloak is OPTIONAL" principle.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `tenacity` | >=9.1.4 (already installed) | Retry with backoff for Keycloak HTTP calls | Already in stack; provides `retry`, `wait_exponential`, `stop_after_attempt`; composable with custom circuit breaker state |

**Implementation pattern (custom circuit breaker):**
```python
import time
from enum import Enum
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time: float = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN: allow one attempt

# Usage in jwt.py:
keycloak_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3),
       retry=retry_if_exception_type(httpx.HTTPError))
async def fetch_jwks_with_breaker(url: str) -> dict:
    if not keycloak_breaker.can_execute():
        raise KeycloakUnavailableError("Circuit open - using cached JWKS")
    try:
        result = await _fetch_jwks(url)
        keycloak_breaker.record_success()
        return result
    except Exception as e:
        keycloak_breaker.record_failure()
        raise
```

**What NOT to add:**
- `pybreaker` -- adds a dependency for a pattern used in exactly one place; custom implementation is simpler and more testable
- `circuitbreaker` (PyPI) -- same reasoning; the pattern is trivial to implement in-house
- `resilience4j` patterns -- Java ecosystem; Python equivalents are overkill at this scale

**Source confidence:** HIGH -- tenacity already in stack and verified; circuit breaker pattern is well-documented (Martin Fowler, Michael Nygard); pybreaker/circuitbreaker reviewed on PyPI and rejected for YAGNI.

---

### 2. Charting Library for Unified Dashboard (#08 + #14)

**Decision:** Use `recharts` (direct dependency) + custom chart wrapper components styled with Tailwind -- do NOT add `@tremor/react`.

**Rationale:** Both Tremor and shadcn/ui charts are built on Recharts underneath. Since the project already uses Tailwind CSS v4 and shadcn/ui design system, adding Tremor introduces 200KB+ gzipped bundle bloat and a parallel component library that conflicts with the existing design system. Using Recharts directly (~50KB) gives full control over chart styling via Tailwind, matches the existing shadcn/ui aesthetic, and avoids Tremor's opinionated color palette.

The dashboard needs 5 chart types: AreaChart (trends), BarChart (comparisons), LineChart (time series), PieChart (distribution), and ComposedChart (mixed). Recharts provides all of these out of the box.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `recharts` | ^2.15.x | Chart rendering for dashboard | Built on D3+React; 3700+ npm dependents; actively maintained (v3.8.0 available but v2.x is stable); AreaChart, BarChart, LineChart, PieChart, ComposedChart; responsive containers; animation support; ~50KB gzipped |

**Chart components needed:**

| Dashboard Section | Chart Type | Recharts Component |
|-------------------|------------|-------------------|
| Usage Analytics | Area chart (DAU/MAU trend) | `<AreaChart>` |
| Performance Metrics | Line chart (API latency P50/P95/P99) | `<LineChart>` |
| Cost Analytics | Bar chart (LLM spend per model) | `<BarChart>` |
| Agent Effectiveness | Pie chart (success/failure ratio) | `<PieChart>` |
| System Overview | Composed (multiple metrics) | `<ComposedChart>` |
| Activity Heatmap | Custom grid | Custom component (no Recharts) |

**Integration pattern:**
```tsx
// components/dashboard/charts/area-chart.tsx
"use client"
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface MetricChartProps {
  data: Array<{ date: string; value: number }>
  color?: string
}

export function MetricAreaChart({ data, color = "hsl(var(--primary))" }: MetricChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="date" className="text-muted-foreground" />
        <YAxis className="text-muted-foreground" />
        <Tooltip />
        <Area type="monotone" dataKey="value" stroke={color} fill={color} fillOpacity={0.1} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
```

**What NOT to add:**
- `@tremor/react` -- 200KB+ bundle; parallel design system conflicts with shadcn/ui; acquired by Vercel but last npm publish was Jan 2025 (maintenance uncertain)
- `visx` (@visx/visx) -- low-level D3 wrapper; requires writing much more code for the same charts
- `chart.js` / `react-chartjs-2` -- Canvas-based (not SVG); harder to theme with Tailwind; less React-native API
- `nivo` (@nivo/core) -- heavy bundle; designed for standalone dashboards, not embedded in existing apps
- `d3` directly -- too low-level; Recharts abstracts D3 with React components

**Source confidence:** MEDIUM-HIGH -- Recharts npm verified (v3.8.0 latest, v2.15.x stable line). Tremor bundle size comparison from shadcn/ui GitHub discussion #4133. Recharts used by shadcn/ui charts component internally.

---

### 3. WebSocket for Real-Time Dashboard Feeds (#14)

**Decision:** Use FastAPI's built-in WebSocket support (`fastapi.WebSocket`) + Redis pub/sub for cross-worker fan-out -- no additional library needed.

**Rationale:** FastAPI is built on ASGI (Starlette) and has native WebSocket support. The project already has Redis 7+ running as Celery broker. Using Redis pub/sub for WebSocket fan-out is the standard pattern for multi-worker deployments. No additional library is needed on the backend.

On the frontend, the native browser `WebSocket` API wrapped in a custom React hook provides reconnection logic without adding `socket.io-client` or other libraries.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| FastAPI WebSocket | built-in (0.115+) | WebSocket endpoint for dashboard | Native Starlette WebSocket; async handlers; already in stack |
| Redis pub/sub | built-in (redis 5.2.1) | Cross-worker message fan-out | Already installed; `redis.asyncio.PubSub` for async subscribe; enables multiple backend workers to broadcast to all connected dashboards |

**Backend pattern (WebSocket hub):**
```python
# api/routes/dashboard.py
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

class DashboardHub:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}  # user_id -> connections

    async def connect(self, ws: WebSocket, user_id: str) -> None:
        await ws.accept()
        self.connections.setdefault(user_id, set()).add(ws)

    async def disconnect(self, ws: WebSocket, user_id: str) -> None:
        self.connections.get(user_id, set()).discard(ws)

    async def broadcast(self, event: dict) -> None:
        """Send event to all connected dashboards."""
        for user_conns in self.connections.values():
            for ws in user_conns:
                try:
                    await ws.send_json(event)
                except Exception:
                    pass  # cleanup handled by disconnect

hub = DashboardHub()

@router.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    user = await authenticate_ws(ws)  # JWT from query param
    await hub.connect(ws, str(user.user_id))
    try:
        # Subscribe to Redis pub/sub for cross-worker events
        redis = Redis.from_url(settings.redis_url)
        pubsub = redis.pubsub()
        await pubsub.subscribe("dashboard:events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        await hub.disconnect(ws, str(user.user_id))
```

**Frontend pattern (custom hook):**
```typescript
// hooks/use-dashboard-ws.ts
"use client"
import { useEffect, useRef, useState, useCallback } from 'react'

export function useDashboardWs(token: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const [events, setEvents] = useState<DashboardEvent[]>([])

  const connect = useCallback(() => {
    const ws = new WebSocket(`ws://localhost:8000/api/dashboard/ws?token=${token}`)
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data) as DashboardEvent
      setEvents(prev => [event, ...prev].slice(0, 100))
    }
    ws.onclose = () => setTimeout(connect, 3000) // reconnect
    wsRef.current = ws
  }, [token])

  useEffect(() => { connect(); return () => wsRef.current?.close() }, [connect])
  return events
}
```

**What NOT to add:**
- `socket.io` / `python-socketio` -- adds complexity over native WebSocket; Socket.IO protocol overhead not needed for server-push-only dashboard
- `channels` (Django Channels) -- Django ecosystem; not applicable to FastAPI
- `websockets` (PyPI) -- Starlette already provides WebSocket support; adding another library is redundant
- Server-Sent Events (SSE) for dashboard -- WebSocket is bidirectional (needed for user actions like filter changes); SSE is read-only

**Source confidence:** HIGH -- FastAPI WebSocket docs (official, fastapi.tiangolo.com/advanced/websockets/). Redis pub/sub pattern from multiple 2025 production references. Native browser WebSocket API is standard.

---

### 4. MinIO Object Storage for Storage Service (#19) + Avatar Upload (#13)

**Decision:** Add MinIO Docker service + `minio` Python SDK for backend + presigned URL pattern for frontend uploads.

**Rationale:** MinIO is the standard self-hosted S3-compatible object storage. It runs as a single Docker container, provides a web console at port 9001, and the Python SDK handles bucket creation, upload, download, and presigned URL generation. The same MinIO instance serves both the Storage Service (#19, file management) and User Experience Enhancement (#13, avatar uploads).

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `minio` (PyPI) | >=7.2.20 | Python SDK for MinIO/S3 operations | Official MinIO SDK; supports async via `minio.Minio` + `asyncio`; presigned URL generation; bucket policy management; Python 3.9+ |
| MinIO Server (Docker) | RELEASE.2025-09-06 (latest stable) | S3-compatible object storage | Single binary; Docker Compose native; web console at :9001; erasure coding optional; health endpoint for monitoring |

**Docker Compose service:**
```yaml
minio:
  image: minio/minio:RELEASE.2025-09-06T17-38-46Z
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  volumes:
    - minio_data:/data
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Web Console
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: unless-stopped

volumes:
  minio_data:
```

**Backend integration:**
```python
# core/storage.py
from minio import Minio
from core.config import settings

def get_storage_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,  # "minio:9000" inside Docker
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,  # Internal Docker network; TLS not needed
    )

# Presigned upload URL (frontend uploads directly to MinIO)
async def get_upload_url(bucket: str, object_name: str, expires: int = 3600) -> str:
    client = get_storage_client()
    return client.presigned_put_object(bucket, object_name, expires=timedelta(seconds=expires))

# Presigned download URL
async def get_download_url(bucket: str, object_name: str, expires: int = 3600) -> str:
    client = get_storage_client()
    return client.presigned_get_object(bucket, object_name, expires=timedelta(seconds=expires))
```

**Bucket structure:**
```
blitz-avatars/         # User avatar images (public-read policy)
  {user_id}/avatar.{ext}
blitz-files/           # User files (private, presigned URLs only)
  {user_id}/{folder_path}/{filename}
blitz-system/          # System files (email templates, exports)
  templates/
  exports/
```

**Frontend upload pattern (presigned URL):**
```typescript
// hooks/use-file-upload.ts
async function uploadFile(file: File, uploadUrl: string) {
  await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type },
  })
}
```

**What NOT to add:**
- `boto3` -- AWS SDK; heavyweight; MinIO's native Python SDK is simpler and purpose-built
- `aiobotocore` -- async S3 wrapper; unnecessary complexity when MinIO SDK handles presigned URLs
- Standalone file upload library -- presigned URLs let the browser upload directly to MinIO (no backend proxy needed)
- Azure Blob Storage / GCS SDK -- YAGNI; adapter pattern in code, but only MinIO implemented for MVP

**Source confidence:** HIGH -- MinIO Python SDK verified on PyPI (v7.2.20, Nov 2025). Docker image tag confirmed from GitHub releases. Presigned URL pattern is standard S3/MinIO.

---

### 5. Email IMAP/SMTP Libraries for Email System (#18)

**Decision:** Use `aiosmtplib` (SMTP) + `aioimaplib` (IMAP) for the email sidecar service, `google-auth-oauthlib` for Gmail OAuth, `msal` for Microsoft 365 OAuth.

**Rationale:** The email sidecar runs as a separate Python service (consistent with Telegram/WhatsApp sidecar pattern). It needs async IMAP for receiving email (IMAP IDLE) and async SMTP for sending. OAuth libraries are needed for Gmail and Microsoft 365 authentication without storing user passwords.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `aiosmtplib` | >=5.1.0 | Async SMTP client for sending email | asyncio-native; Python 3.10+; supports STARTTLS, AUTH; connection pooling; well-maintained |
| `aioimaplib` | >=2.0.1 | Async IMAP client for receiving email | asyncio-native; IMAP IDLE support (push notifications); 23/25 RFC 3501 commands implemented; XOAUTH2 authentication supported |
| `google-auth-oauthlib` | >=1.3.0 | Gmail OAuth 2.0 flow | Official Google library; InstalledAppFlow for OAuth consent; scope management for Gmail API access |
| `google-auth` | >=2.40.0 | Google credentials management | Required by google-auth-oauthlib; handles token refresh, caching |
| `msal` | >=1.34.0 | Microsoft 365 OAuth 2.0 flow | Official Microsoft Authentication Library; ConfidentialClientApplication for server OAuth; handles token acquisition and refresh |
| `jinja2` | >=3.1.0 | Email HTML templates | Standard Python templating; for system notification email templates; lightweight |

**Email sidecar dependencies (separate pyproject.toml):**
```toml
[project]
name = "email-sidecar"
dependencies = [
    "aiosmtplib>=5.1.0",
    "aioimaplib>=2.0.1",
    "google-auth-oauthlib>=1.3.0",
    "msal>=1.34.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.0",
    "jinja2>=3.1.0",
    "structlog>=25.1.0",
]
```

**IMAP IDLE pattern (push-based email receiving):**
```python
# channel-gateways/email/imap_listener.py
import aioimaplib

async def listen_for_new_emails(host: str, user: str, oauth_token: str):
    client = aioimaplib.IMAP4_SSL(host=host)
    await client.wait_hello_from_server()
    await client.xoauth2_login(user, oauth_token)
    await client.select("INBOX")

    while True:
        idle = await client.idle_start(timeout=300)
        msg = await client.idle_check(timeout=300)
        if msg:
            # Fetch new messages and forward to backend
            await process_new_messages(client)
        await client.idle_done()
```

**Notification service (backend -- no new deps):**
The NotificationService in the backend uses existing `httpx` to call channel sidecar `/send` endpoints. No additional library needed in the backend for notification routing.

**What NOT to add:**
- `imaplib` (stdlib) -- synchronous; blocks event loop
- `smtplib` (stdlib) -- synchronous; blocks event loop
- `django-allauth` -- Django ecosystem; not applicable
- `authlib` -- generic OAuth; google-auth-oauthlib and msal are the official libraries for their respective providers
- `sendgrid` / `mailgun` SDK -- SaaS email services; on-premise requirement means direct SMTP

**Source confidence:** HIGH -- aiosmtplib v5.1.0 verified on PyPI. aioimaplib v2.0.1 verified on PyPI. google-auth-oauthlib v1.3.0 and msal v1.34.0 verified on PyPI. All are official/well-maintained libraries.

---

### 6. Theme Management for User Experience Enhancement (#13)

**Decision:** Use `next-themes` for theme switching + Tailwind CSS v4 custom properties -- no other library needed.

**Rationale:** `next-themes` is the canonical dark mode solution for Next.js App Router. It provides system preference detection, zero-flash theme application (injects script before hydration), localStorage persistence, and works with Tailwind's `dark:` variant. The project already uses Tailwind CSS v4, so CSS custom properties for theme colors are native.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `next-themes` | ^0.4.x | Theme switching (light/dark/system) | 2 lines to set up; zero-flash; system preference detection; cookie persistence for SSR; works with Next.js 15 App Router; 5M+ weekly downloads |

**Integration with existing stack:**
```tsx
// components/theme-provider.tsx
"use client"
import { ThemeProvider as NextThemesProvider } from "next-themes"

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"       // Tailwind dark: variant
      defaultTheme="system"   // Follow OS preference
      enableSystem             // Detect OS dark mode
      disableTransitionOnChange // Prevent flash during switch
    >
      {children}
    </NextThemesProvider>
  )
}

// app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <SidebarProvider>{children}</SidebarProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

**CSS custom properties for multi-theme support (3 themes: light, dark, navy):**
```css
/* globals.css -- Tailwind v4 theming */
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  /* ... */
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --primary: 210 40% 98%;
}

[data-theme="navy"] {
  --background: 222 47% 11%;
  --foreground: 210 40% 98%;
  --primary: 217 91% 60%;
}
```

**What NOT to add:**
- CSS-in-JS solutions (styled-components, emotion) -- Tailwind v4 handles theming natively
- `theme-change` -- simple library superseded by next-themes
- Custom theme context provider -- next-themes handles all the edge cases (SSR, flash prevention, system detection)

**Source confidence:** HIGH -- next-themes GitHub (pacocoursey/next-themes, verified). shadcn/ui official dark mode guide uses next-themes. Multiple 2025-2026 Next.js 15 + Tailwind v4 tutorials confirm compatibility.

---

### 7. Cron Builder UI for Scheduler (#15)

**Decision:** Build a custom cron builder component using shadcn/ui form primitives (Select, Input, Tabs) + `cronstrue` for human-readable descriptions -- do NOT add a third-party cron builder.

**Rationale:** Existing React cron builder components are either outdated (`react-cron-builder`, 7 years old), Ant Design-dependent (`react-js-cron`), or too new/unproven (`@vpfaiz/cron-builder-ui`, <100 stars). A custom component built with the existing shadcn/ui design system (Select, RadioGroup, Tabs, Input) provides better UX consistency and avoids adding a component library with incompatible styles.

The backend already has `croniter` (>=6.0.0) for cron expression validation and next-run calculation. Adding `cronstrue` on the frontend provides human-readable cron descriptions ("Every Monday at 9:00 AM").

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `cronstrue` | ^2.x (npm) | Human-readable cron expression descriptions | Lightweight (no dependencies); "0 9 * * 1" -> "At 09:00, only on Monday"; i18n support; used by cron builder UIs to show preview text |

**Frontend pattern:**
```tsx
// components/scheduler/cron-builder.tsx
"use client"
import cronstrue from 'cronstrue'

function CronBuilder({ value, onChange }: { value: string; onChange: (cron: string) => void }) {
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple')

  // Simple mode: dropdowns for common patterns
  // Advanced mode: raw cron expression input

  const description = useMemo(() => {
    try { return cronstrue.toString(value) } catch { return 'Invalid expression' }
  }, [value])

  return (
    <div>
      <Tabs value={mode} onValueChange={v => setMode(v as 'simple' | 'advanced')}>
        <TabsList>
          <TabsTrigger value="simple">Simple</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>
        <TabsContent value="simple">
          {/* Frequency selector: Every N minutes/hours/days/weeks/months */}
          {/* Day-of-week checkboxes */}
          {/* Time picker */}
        </TabsContent>
        <TabsContent value="advanced">
          <Input value={value} onChange={e => onChange(e.target.value)} placeholder="* * * * *" />
        </TabsContent>
      </Tabs>
      <p className="text-sm text-muted-foreground mt-2">{description}</p>
    </div>
  )
}
```

**Backend validation (already in stack):**
```python
# croniter already installed (>=6.0.0)
from croniter import croniter

def validate_cron(expression: str) -> bool:
    return croniter.is_valid(expression)

def next_runs(expression: str, count: int = 5) -> list[datetime]:
    cron = croniter(expression)
    return [cron.get_next(datetime) for _ in range(count)]
```

**What NOT to add:**
- `react-js-cron` -- depends on Ant Design; adds antd as peer dependency (massive bundle; style conflicts)
- `react-cron-generator` -- last updated 2023; Quartz format focus (not needed for Celery/cron)
- `@vpfaiz/cron-builder-ui` -- too new (<100 npm downloads); not production-proven
- `react-cron-builder` -- 7 years old; unmaintained
- `cron-parser` (npm) -- `cronstrue` is for display only; backend `croniter` handles parsing/validation

**Source confidence:** MEDIUM -- cronstrue npm verified. Custom builder approach based on shadcn/ui form primitives is a design decision, not a library finding. croniter already in stack (verified from pyproject.toml).

---

### 8. No Additional Libraries Needed

The following v1.4 features require NO new stack additions:

**Admin Registry Edit UI (#06):**
- Uses existing shadcn/ui form components (Input, Select, Dialog, Tabs)
- MCP connection testing uses existing `httpx` to probe `/health` and `/sse` endpoints
- No new libraries

**Runtime Permission Approval HITL (#01):**
- Permission request queue uses existing PostgreSQL tables + FastAPI endpoints
- Temporal ACL uses existing `cachetools` for TTL-based permission caching
- Auto-approve rules stored in existing `platform_config` table
- UI uses existing shadcn/ui components
- No new libraries

**Multi-Agent Tab Architecture (#16):**
- Multiple CopilotKit instances reuse existing `@copilotkit/react-core`
- Tabbed UI uses existing shadcn/ui Tabs component
- Builder agents are new LangGraph graphs but use existing `langgraph` package
- No new libraries

---

## Version Compatibility Matrix (v1.4 Additions)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `recharts` ^2.15.x | React 19 + Next.js 15 | SSR-safe with `"use client"` directive; responsive containers |
| `next-themes` ^0.4.x | Next.js 15 App Router + Tailwind v4 | Must wrap `<html>` with `suppressHydrationWarning` |
| `cronstrue` ^2.x | Browser + Node.js | Pure JS; no framework dependency |
| `minio` >=7.2.20 | Python 3.12 + FastAPI | Sync SDK; use in FastAPI route handlers or wrap in `asyncio.to_thread()` |
| MinIO Server RELEASE.2025-09 | Docker Compose | Single container; S3-compatible API on :9000, console on :9001 |
| `aiosmtplib` >=5.1.0 | Python 3.10+ asyncio | Async SMTP; TLS/STARTTLS support |
| `aioimaplib` >=2.0.1 | Python 3.9+ asyncio | Async IMAP; IDLE + XOAUTH2 |
| `google-auth-oauthlib` >=1.3.0 | Python 3.7+ | Gmail OAuth flow |
| `msal` >=1.34.0 | Python 3.7+ | Microsoft 365 OAuth flow |
| `tenacity` >=9.1.4 | Already installed | Circuit breaker pattern uses existing dependency |
| `croniter` >=6.0.0 | Already installed | Backend cron validation |

---

## Installation Summary (v1.4 New Additions Only)

### Frontend
```bash
cd /home/tungmv/Projects/hox-agentos/frontend

# Dashboard charts
pnpm add recharts

# Theme management
pnpm add next-themes

# Cron expression display
pnpm add cronstrue

# Type definitions (if needed)
pnpm add -D @types/recharts
```

### Backend (main service)
```bash
cd /home/tungmv/Projects/hox-agentos/backend

# MinIO SDK for storage service
uv add minio

# No other additions -- tenacity, croniter, httpx, cachetools already installed
```

### Email Sidecar (new service)
```bash
# New pyproject.toml in channel-gateways/email/
uv add aiosmtplib aioimaplib google-auth-oauthlib msal fastapi uvicorn httpx jinja2 structlog
```

### Infrastructure (Docker Compose additions)
```yaml
# MinIO object storage (for Storage Service + Avatar upload)
minio:
  image: minio/minio:RELEASE.2025-09-06T17-38-46Z
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  volumes:
    - minio_data:/data
  ports:
    - "9000:9000"
    - "9001:9001"
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: unless-stopped

# Email sidecar (for Email System)
email-gateway:
  build: ./channel-gateways/email
  environment:
    EMAIL_SIDECAR_PORT: "8003"
    BACKEND_URL: "http://backend:8000"
  ports:
    - "8003:8003"
  depends_on:
    - backend
  restart: unless-stopped

volumes:
  minio_data:
```

---

## What NOT to Add (v1.4 Additions)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `@tremor/react` | 200KB+ bundle; parallel design system to shadcn/ui; uncertain maintenance since Vercel acquisition | `recharts` directly (~50KB) with Tailwind styling |
| `pybreaker` / `circuitbreaker` | New dependency for a pattern used in 1 place; 60-line custom impl is simpler | Custom circuit breaker class + existing `tenacity` |
| `socket.io` / `python-socketio` | Protocol overhead; Socket.IO features (rooms, namespaces) not needed for dashboard push | Native FastAPI WebSocket + Redis pub/sub |
| `boto3` / `aiobotocore` | AWS SDK heavyweight; MinIO has its own lighter SDK | `minio` Python SDK |
| `react-js-cron` | Ant Design dependency; style conflicts with shadcn/ui | Custom cron builder with shadcn/ui primitives + `cronstrue` |
| `react-cron-generator` | Outdated (2023); Quartz format focus | Custom component |
| `styled-components` / `emotion` | CSS-in-JS conflicts with Tailwind v4 theming | `next-themes` + CSS custom properties |
| `imaplib` / `smtplib` (stdlib) | Synchronous; blocks asyncio event loop | `aioimaplib` + `aiosmtplib` |
| `authlib` | Generic OAuth library; less maintained than official Google/Microsoft SDKs | `google-auth-oauthlib` + `msal` |
| `chart.js` / `react-chartjs-2` | Canvas-based (not SVG); harder to theme with Tailwind | `recharts` (SVG, React-native) |
| `zustand` for theme state | `next-themes` handles theme state internally | `next-themes` |

---

## Existing Stack (v1.0-v1.3) -- No Changes for v1.4

The following remain unchanged and require no re-research:

- **Agent Orchestration:** LangGraph 1.0.9, PydanticAI 1.63.0
- **Frontend:** Next.js 15.5+, CopilotKit 1.51.x, React Flow 12.10.x, jose ^5.x
- **Backend:** FastAPI 0.115+, SQLAlchemy 2.0.36, asyncpg, Alembic, structlog 25.1.0
- **Identity:** Keycloak 26+ (optional), dual-issuer JWT (local HS256 + Keycloak RS256)
- **Database:** PostgreSQL 16 + pgvector 0.8+, tsvector FTS
- **Infrastructure:** Docker Compose, Redis 7+, Celery 5+, LiteLLM Proxy
- **Embedding:** infinity-emb sidecar (bge-m3)
- **Observability:** Grafana + Loki + Alloy + Prometheus
- **Navigation:** shadcn/ui Sidebar (collapsible="icon")
- **MCP:** MCP Python SDK 1.26+

---

## Sources

### v1.4 New Research (2026-03-15)

- Recharts npm (v3.8.0/v2.15.x): https://www.npmjs.com/package/recharts
- Tremor vs shadcn/ui comparison: https://github.com/shadcn-ui/ui/discussions/4133
- next-themes GitHub: https://github.com/pacocoursey/next-themes
- shadcn/ui dark mode guide: https://ui.shadcn.com/docs/dark-mode/next
- MinIO Python SDK (v7.2.20): https://pypi.org/project/minio/
- MinIO Docker Compose: https://github.com/minio/minio/blob/master/docs/orchestration/docker-compose/docker-compose.yaml
- aiosmtplib (v5.1.0): https://pypi.org/project/aiosmtplib/
- aioimaplib (v2.0.1): https://pypi.org/project/aioimaplib/
- google-auth-oauthlib (v1.3.0): https://pypi.org/project/google-auth-oauthlib/
- MSAL Python (v1.34.0): https://pypi.org/project/msal/
- cronstrue npm: https://www.npmjs.com/package/cronstrue
- FastAPI WebSocket docs: https://fastapi.tiangolo.com/advanced/websockets/
- pybreaker PyPI (evaluated, rejected): https://pypi.org/project/pybreaker/
- tenacity PyPI (already installed): https://pypi.org/project/tenacity/

### Previous Research
- v1.3 additions (2026-03-05): jose, infinity-emb, tsvector, skills-ref, shadcn/ui Sidebar
- v1.0-v1.2 research (2026-02-24): LangGraph, CopilotKit, React Flow, FastAPI, Keycloak, pgvector, LiteLLM, MCP

---
*Stack research for: Blitz AgentOS -- Enterprise on-premise agentic operating system*
*Original research: 2026-02-24 | v1.3 additions: 2026-03-05 | v1.4 additions: 2026-03-15*
