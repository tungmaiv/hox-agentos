# Phase 8: Observability - Research

**Researched:** 2026-03-01
**Domain:** Prometheus + Grafana + Loki + Grafana Alloy + cAdvisor observability stack for Docker Compose
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Dashboard Layout
- **2 dashboards**: Ops Dashboard + Costs Dashboard (not 3 separate, not 1 unified)
- Ops Dashboard contains: system health panels + agent performance panels + embedded log panel
- Costs Dashboard contains: LLM spend breakdown + alert status
- 30-second auto-refresh on both dashboards

#### System Health Panels (Ops Dashboard)
- Both service uptime/error rates AND infrastructure metrics combined
- Service uptime: is each Docker service healthy? (backend, frontend, postgres, redis, keycloak, litellm, celery)
- Error rates: % of HTTP 5xx responses per service
- Infrastructure: CPU, memory, disk usage per container

#### Agent Performance Panels (Ops Dashboard)
- Latency per agent invocation (p50, p95)
- Success/failure rates per agent
- Token usage per invocation broken down by model alias
- All three combined in the Ops Dashboard

#### Log Search (Ops Dashboard)
- Embedded log table panel on the Ops Dashboard showing recent logs
- "View in Explore" link for full LogQL power queries in Grafana Explore
- Ops uses Grafana Explore (not a custom search UI) for deep dives

#### Loki Configuration
- **Labels indexed:** `service`, `level`, `user_id` — the three primary filter axes
- **Retention:** 90 days
- **Log sources via Alloy:**
  1. Structured JSON audit logs from `logs/blitz/` directory (structlog output)
  2. Docker container stdout for all services (catches startup errors, crashes, migrations)

#### Cost Tracking (Costs Dashboard)
- Breakdown: by model alias (`blitz/master`, `blitz/fast`, `blitz/coder`) AND by user
- Time aggregation: daily spend trend + monthly cumulative total
- Grafana alert rule fires when daily or monthly spend exceeds a configured threshold
- Alert notification: in-dashboard only (Grafana alert panel, no external Slack/email for MVP)
- **Data source:** LiteLLM Proxy spend API — LiteLLM's built-in `/spend` endpoints

#### Access Control
- Grafana is **ops/admin team only** — no general user access
- **Authentication:** Keycloak SSO via OIDC (same SSO as the main app)
- **Authorized roles:** users with either `admin` OR `ops` Keycloak role can log into Grafana
- Grafana exposed on **host port 3001** (accessible at `localhost:3001`)
- Protected by Keycloak SSO — not publicly accessible without login

### Claude's Discretion
- Exact Grafana dashboard panel layout and color scheme
- Specific Prometheus scrape intervals
- Alloy pipeline configuration details (log parsing rules, label extraction regex)
- Alert threshold default values (set reasonable defaults, configurable via env vars)
- Grafana role mapping (admin role → Grafana Admin, ops role → Grafana Viewer)
- Loki chunk/index store configuration

### Deferred Ideas (OUT OF SCOPE)
- **Admin UI settings page** — An in-app settings screen where admins can configure Grafana refresh rate and Loki retention days. Belongs in a future admin/settings phase.
- **External alert notifications** — Grafana alerts to Slack or email. In-dashboard alerts only for this phase; external channels are a future enhancement.
- **Per-user cost self-service** — Regular users seeing their own usage/cost panel. Currently ops-only.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBSV-01 | Grafana dashboards display system health, agent performance, and tool usage metrics | Prometheus + cAdvisor + prometheus-fastapi-instrumentator + custom prometheus-client metrics in backend provide all data; Grafana provisioning files deliver dashboards at startup |
| OBSV-02 | Loki aggregates structured JSON logs from all services via Alloy | Grafana Alloy v1 with loki.source.docker reads Docker container stdout; structlog writes JSON to stdout; Loki 3 stores with 90d retention |
| OBSV-03 | LiteLLM cost tracking dashboard shows spend per model, per user | LiteLLM callbacks=["prometheus"] exposes litellm_spend_metric, litellm_total_tokens_metric by model and user labels; Grafana Costs Dashboard queries these |
</phase_requirements>

---

## Summary

Phase 8 adds a complete observability stack to Blitz AgentOS using the Prometheus/Grafana/Loki/Alloy ecosystem — the de-facto standard for Docker Compose deployments at small-to-medium scale. The stack is well-established, all components are open-source, and the patterns are highly documented.

The design was pre-decided in `docs/plans/2026-03-01-phase8-observability-design.md` which was approved on 2026-03-01. This document is the primary source of truth for implementation details. The research confirms all technical choices are sound and clarifies critical configuration specifics: LiteLLM Prometheus metrics are OSS (enabled with `callbacks: ["prometheus"]`), Grafana Keycloak OIDC uses `GF_AUTH_GENERIC_OAUTH_*` environment variables with a JMESPath role_attribute_path expression, and Alloy reads Docker container stdout via the Docker socket (NOT log files).

A critical discovery: structlog writes to stdout (`sys.stdout`) in `core/logging.py` — logs are NOT written to files. The `./logs:/app/logs` volume is empty in practice. Alloy must read Docker container stdout via `loki.source.docker` (Docker socket method), not file tailing. The design document correctly identifies this in the "Context for Implementer" section.

**Primary recommendation:** Implement the approved design from `docs/plans/2026-03-01-phase8-observability-design.md` exactly. Five new Docker Compose services (prometheus, grafana, loki, alloy, cadvisor) + backend Prometheus instrumentation + 2 provisioned Grafana dashboards + Keycloak OIDC SSO for Grafana.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Prometheus | `prom/prometheus:v3.2.1` | Metric collection and storage | Industry standard; time-series DB for metrics |
| Grafana | `grafana/grafana:11.4.0` | Dashboards and alerting UI | Market leader for observability dashboards |
| Loki | `grafana/loki:3.3.2` | Log aggregation store | Prometheus-native log store; label-indexed |
| Grafana Alloy | `grafana/alloy:v1.6.1` | Log collection agent | Successor to Promtail; supports Docker source |
| cAdvisor | `gcr.io/cadvisor/cadvisor:latest` | Docker container resource metrics | Zero-config; exposes /metrics for all containers |
| prometheus-fastapi-instrumentator | `7.1.0` | FastAPI HTTP metrics | Standard library for FastAPI Prometheus integration |
| prometheus-client | `>=0.20.0` | Custom Python metrics | Official Prometheus Python client; Counter/Histogram/Gauge |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LiteLLM `callbacks: ["prometheus"]` | built-in | LLM spend/token/latency metrics | Already in stack; enables /metrics on litellm:4000 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Grafana Alloy | Promtail | Alloy is Promtail's successor; more flexible HCL config |
| Grafana Alloy | Fluentd/Fluent Bit | Alloy integrates natively with Loki push API |
| prometheus-fastapi-instrumentator | starlette_exporter | Both work; instrumentator has more features |
| Loki filesystem storage | Loki object storage | Filesystem is simpler for Docker Compose MVP |

**Installation (backend Python deps):**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
uv add prometheus-fastapi-instrumentator>=7.1.0
uv add prometheus-client>=0.20.0
```

**No pip install — use `uv add` per project conventions.**

---

## Architecture Patterns

### Recommended Infra Structure
```
infra/
├── prometheus/
│   └── prometheus.yml          # scrape_configs for cadvisor, litellm, backend
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml # Prometheus + Loki data sources
│   │   ├── dashboards/
│   │   │   └── dashboards.yml  # folder + file provider config
│   │   └── alerting/
│   │       ├── contact_points.yml  # Telegram contact point
│   │       └── alert_rules.yml     # service-down + high-error-rate rules
│   └── dashboards/
│       ├── ops-dashboard.json       # System health + agent perf + logs
│       └── costs-dashboard.json     # LiteLLM spend by model + user
├── loki/
│   └── loki-config.yml         # filesystem storage, 90d retention, no auth
└── alloy/
    └── config.alloy            # loki.source.docker → loki:3100
```

### Pattern 1: Prometheus Service Discovery via Static Configs

**What:** Static scrape configs for all three metric producers.
**When to use:** Small deployments with fixed services.
**Example:**
```yaml
# Source: Prometheus docs - https://prometheus.io/docs/guides/cadvisor/
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "cadvisor"
    static_configs:
      - targets: ["cadvisor:8080"]

  - job_name: "litellm"
    static_configs:
      - targets: ["litellm:4000"]
    metrics_path: /metrics

  - job_name: "backend"
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: /metrics
```

### Pattern 2: prometheus-fastapi-instrumentator Integration

**What:** Single-line instrumentation that adds /metrics endpoint to FastAPI app.
**When to use:** Any FastAPI app needing HTTP metrics.

IMPORTANT: With uvicorn single-worker (not gunicorn multiprocessing), no PROMETHEUS_MULTIPROC_DIR is needed. Our backend runs as a single uvicorn process per Docker service.

```python
# Source: https://github.com/trallnag/prometheus-fastapi-instrumentator
# Add to main.py create_app() AFTER the app is created, BEFORE include_router calls
from prometheus_fastapi_instrumentator import Instrumentator

def create_app() -> FastAPI:
    configure_logging(...)
    app = FastAPI(...)
    app.add_middleware(CORSMiddleware, ...)

    # Instrument BEFORE routes so /metrics is excluded from request tracking
    Instrumentator().instrument(app).expose(app)

    app.include_router(health.router)
    # ... rest of routers
    return app
```

This exposes `GET /metrics` (no auth) — accessible by Prometheus scraper on the internal blitz-net.

### Pattern 3: Custom prometheus-client Metrics

**What:** Module-level metric registry in `backend/core/metrics.py`.
**When to use:** When you need business-specific metrics beyond HTTP stats.

```python
# Source: https://prometheus.github.io/client_python/
# File: backend/core/metrics.py
from prometheus_client import Counter, Histogram

# Tool call metrics (instrumented in security/acl.py log_tool_call)
blitz_tool_calls_total = Counter(
    "blitz_tool_calls_total",
    "Total tool calls by tool name and success status",
    ["tool", "success"],
)
blitz_tool_duration_seconds = Histogram(
    "blitz_tool_duration_seconds",
    "Tool execution latency in seconds",
    ["tool"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# LLM call metrics (instrumented in core/config.py get_llm() wrapper)
blitz_llm_calls_total = Counter(
    "blitz_llm_calls_total",
    "Total LLM calls by model alias",
    ["model_alias"],
)
blitz_llm_duration_seconds = Histogram(
    "blitz_llm_duration_seconds",
    "LLM call latency in seconds",
    ["model_alias"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# Memory operation metrics (instrumented in memory/short_term.py, memory/long_term.py)
blitz_memory_ops_total = Counter(
    "blitz_memory_ops_total",
    "Total memory operations by type",
    ["operation"],  # read, write, search
)
```

**Label cardinality rule:** All labels must be LOW cardinality. NO `user_id` in metric labels — per-user data stays in LiteLLM's Prometheus metrics. Tool names, model aliases, and operation types are fine.

### Pattern 4: LiteLLM Prometheus Integration

**What:** Enable Prometheus metrics in LiteLLM config.yaml.
**When to use:** When you need LLM cost, token, and latency metrics.

```yaml
# Source: https://docs.litellm.ai/docs/proxy/prometheus
# Add to infra/litellm/config.yaml
litellm_settings:
  drop_params: true
  callbacks: ["prometheus"]   # ← ADD THIS LINE
```

This exposes `/metrics` on `litellm:4000` (internal only) with metrics including:
- `litellm_spend_metric` — spend per user, API key, team, model
- `litellm_total_tokens_metric` — tokens per model
- `litellm_request_total_latency_metric` — end-to-end latency
- `litellm_llm_api_latency_metric` — LLM-only latency

### Pattern 5: Grafana Alloy Docker Log Collection

**What:** Alloy reads Docker container stdout via Docker socket, ships to Loki.
**When to use:** All logs go to stdout (which structlog does in this project).

```alloy
// Source: https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.docker/
// File: infra/alloy/config.alloy

// Discover all containers from the hox-agentos compose project
discovery.docker "local_containers" {
  host = "unix:///var/run/docker.sock"
}

// Keep only hox-agentos project containers, add service label
discovery.relabel "blitz_containers" {
  targets = discovery.docker.local_containers.targets

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
    regex         = "hox-agentos"
    action        = "keep"
  }

  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }
}

// Read container stdout/stderr and ship to Loki
loki.source.docker "blitz_logs" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.blitz_containers.output
  forward_to = [loki.write.loki_server.receiver]
  labels     = { job = "blitz-agentos" }
}

loki.write "loki_server" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

### Pattern 6: Grafana Keycloak OIDC Configuration

**What:** Configure Grafana SSO via Keycloak using Generic OAuth.
**When to use:** When Grafana must use existing Keycloak realm for authentication.

The project uses a self-signed cert (`frontend/certs/keycloak-ca.crt`). Use `tls_skip_verify_insecure = true` for dev (the local Keycloak is internal-only, not public-facing — acceptable for MVP).

Keycloak realm uses a custom mapper that emits roles as flat `realm_roles` list (see STATE.md decisions). The JMESPath role_attribute_path must read from `realm_roles`, not `realm_access.roles`.

```yaml
# Source: https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/keycloak/
# Add to grafana service in docker-compose.yml environment section:
environment:
  GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
  GF_USERS_ALLOW_SIGN_UP: "false"
  GF_AUTH_GENERIC_OAUTH_ENABLED: "true"
  GF_AUTH_GENERIC_OAUTH_NAME: "Keycloak"
  GF_AUTH_GENERIC_OAUTH_ALLOW_SIGN_UP: "true"
  GF_AUTH_GENERIC_OAUTH_CLIENT_ID: "grafana"
  GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET: ${GRAFANA_OAUTH_CLIENT_SECRET}
  GF_AUTH_GENERIC_OAUTH_SCOPES: "openid email profile roles"
  GF_AUTH_GENERIC_OAUTH_AUTH_URL: "https://keycloak.blitz.local:7443/realms/blitz-internal/protocol/openid-connect/auth"
  GF_AUTH_GENERIC_OAUTH_TOKEN_URL: "https://keycloak.blitz.local:7443/realms/blitz-internal/protocol/openid-connect/token"
  GF_AUTH_GENERIC_OAUTH_API_URL: "https://keycloak.blitz.local:7443/realms/blitz-internal/protocol/openid-connect/userinfo"
  GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH: "contains(realm_roles[*], 'admin') && 'Admin' || contains(realm_roles[*], 'ops') && 'Viewer' || 'Viewer'"
  GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE: "true"
  GF_AUTH_DISABLE_LOGIN_FORM: "false"  # keep local admin login as fallback
```

**Note on role mapping:** The context decision says "admin role → Grafana Admin, ops role → Grafana Viewer." The JMESPath expression above maps `admin` → Admin, `ops` → Viewer. This blocks non-admin/non-ops users entirely via `auto_sign_up: false` logic — only mapped roles can access. If you want to block everyone else outright, also set `GF_AUTH_GENERIC_OAUTH_SKIP_ORG_ROLE_SYNC: "false"`.

**Alternative approach (no OIDC complexity for MVP):** If Keycloak OIDC proves difficult to configure with the self-signed cert, an alternative is Grafana local admin login only (single shared admin account for the ops team). This is simpler but less auditable. CONTEXT.md locks Keycloak SSO, so implement it — just be aware this is a potential complexity point.

### Pattern 7: Grafana Provisioning — Datasources and Dashboards

```yaml
# Source: https://grafana.com/docs/grafana/latest/administration/provisioning/
# infra/grafana/provisioning/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: blitz-prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    uid: blitz-loki
    access: proxy
    url: http://loki:3100
    editable: false
```

```yaml
# infra/grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: blitz-dashboards
    orgId: 1
    folder: __Blitz
    folderUid: blitz-folder
    type: file
    disableDeletion: true
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/dashboards
```

### Pattern 8: Grafana Alerting Provisioning (YAML)

```yaml
# Source: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/
# infra/grafana/provisioning/alerting/contact_points.yml
apiVersion: 1

contactPoints:
  - orgId: 1
    name: telegram-alerts
    receivers:
      - uid: telegram_receiver
        type: telegram
        settings:
          bottoken: ${TELEGRAM_BOT_TOKEN}
          chatid: ${GRAFANA_ALERT_CHAT_ID}
```

```yaml
# infra/grafana/provisioning/alerting/alert_rules.yml
apiVersion: 1

groups:
  - orgId: 1
    name: blitz-infra-alerts
    folder: __Blitz
    interval: 1m
    rules:
      - uid: service_down_alert
        title: Service Down
        condition: A
        for: 1m
        data:
          - refId: A
            datasourceUid: blitz-prometheus
            model:
              expr: up{job="cadvisor"} == 0
              type: range
        annotations:
          description: "Service {{ $labels.name }} is down"
        labels:
          severity: critical
```

### Pattern 9: Grafana Dashboard JSON Structure

Dashboard JSON files are large (hundreds of lines). The canonical way to create them:
1. Build the dashboard in the Grafana UI
2. Export as JSON (Dashboard settings → JSON Model)
3. Save to `infra/grafana/dashboards/ops-dashboard.json` and `costs-dashboard.json`

Alternatively, write the JSON directly with the required structure:
```json
{
  "title": "Blitz Ops Dashboard",
  "uid": "blitz-ops",
  "refresh": "30s",
  "time": {"from": "now-1h", "to": "now"},
  "panels": [...],
  "schemaVersion": 38
}
```

Key fields: `uid` (unique across Grafana), `refresh`, `schemaVersion` (use current Grafana version's schema).

### Anti-Patterns to Avoid

- **Grafana local login disabled entirely:** Don't set `GF_AUTH_DISABLE_LOGIN_FORM: "true"` — if Keycloak is down, you're locked out. Keep local admin as fallback.
- **user_id in Prometheus labels:** High cardinality. Never add user_id as a metric label. Use Loki for per-user log queries.
- **File tailing in Alloy for this project:** Structlog writes to stdout, NOT files. The `./logs:/app/logs` volume is empty. Use `loki.source.docker` (Docker socket), not `loki.source.file`.
- **LiteLLM `/spend` REST API as Grafana datasource:** The design calls for Prometheus metrics from LiteLLM, not direct REST API calls. Use `callbacks: ["prometheus"]` in litellm config — simpler, standard.
- **prometheus-fastapi-instrumentator multiprocess mode:** Only needed with gunicorn multiple workers. Single uvicorn process (our setup) does NOT need `PROMETHEUS_MULTIPROC_DIR`.
- **Hardcoding alert thresholds:** Alert thresholds should be env var configurable per CONTEXT.md specifics. Use Grafana dashboard variables or env-driven config.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP request metrics | Custom middleware tracking request counts | `prometheus-fastapi-instrumentator` | Handles label templating, latency histograms, error rate bucketing correctly |
| Container resource metrics | Docker stats polling script | `cAdvisor` Docker image | cAdvisor handles all container metrics including namespacing, zero config |
| Log shipping from containers | Custom log forwarder | Grafana Alloy `loki.source.docker` | Handles Docker socket, position tracking, restart-safe, filtering |
| Log storage | Elasticsearch or custom DB | `Loki` | Label-indexed log store; native Grafana integration; LogQL query language |
| Dashboard JSON generation | Custom Python script | Grafana JSON model export + provisioning | Standard JSON format; Grafana UI builder is the right tool |
| Alerting logic | Custom cron job | Grafana alert rules | Built-in evaluation, routing, dedup, silence |

**Key insight:** The entire observability stack is config-file work (YAML, JSON, Alloy HCL). Zero custom code for infrastructure layer. The only Python code is the `core/metrics.py` metric registration and 3-4 lines of instrumentation calls in existing modules.

---

## Common Pitfalls

### Pitfall 1: Structlog Writes to Stdout, Not Files
**What goes wrong:** Alloy configured to tail `logs/blitz/*.json` finds no logs. Dashboard shows no log data.
**Why it happens:** `core/logging.py` uses `logging.basicConfig(stream=sys.stdout)`. The `./logs:/app/logs` volume exists but `audit_log_path=logs/audit.jsonl` in config — the file IS written but only if `Path(audit_log_path).parent.mkdir()` succeeds. In practice, container stdout has all logs.
**How to avoid:** Use `loki.source.docker` (Docker socket approach) as primary log source. The Docker socket captures all stdout/stderr.
**Warning signs:** Loki shows zero streams in Grafana Explore.

### Pitfall 2: Keycloak Self-Signed Cert Breaks Grafana OAuth
**What goes wrong:** Grafana fails to authenticate users via Keycloak. Error in logs: "x509: certificate signed by unknown authority."
**Why it happens:** Grafana makes HTTPS calls to Keycloak token/userinfo endpoints. The self-signed cert is not trusted by the Grafana container's CA store.
**How to avoid:** Set `GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE: "true"` in the Grafana service environment. This is acceptable for internal-only Keycloak.
**Warning signs:** Grafana Keycloak login button works but returns error page.

### Pitfall 3: Keycloak Role Claims in Wrong JWT Field
**What goes wrong:** Grafana OIDC role mapping gives everyone Viewer role. `contains(realm_access.roles[*], 'admin')` returns false even for admins.
**Why it happens:** This Keycloak realm uses a custom scope mapper that puts roles in flat `realm_roles` field (not `realm_access.roles`). See STATE.md: "Roles in `realm_roles` not `realm_access.roles`."
**How to avoid:** Use `contains(realm_roles[*], 'admin') && 'Admin' || ...` in `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH`.
**Warning signs:** All Grafana users have Viewer role regardless of Keycloak role.

### Pitfall 4: LiteLLM Prometheus Not Enabled by Default
**What goes wrong:** `http://litellm:4000/metrics` returns 404. Prometheus scrape fails.
**Why it happens:** LiteLLM only exposes `/metrics` when `callbacks: ["prometheus"]` is set in `litellm_settings`. The current `config.yaml` only has `drop_params: true`.
**How to avoid:** Add `callbacks: ["prometheus"]` to `litellm_settings` in `infra/litellm/config.yaml`.
**Warning signs:** Prometheus target `litellm` shows DOWN in Prometheus targets UI.

### Pitfall 5: cAdvisor Port Conflict with Keycloak
**What goes wrong:** cAdvisor fails to start — port 8080 already in use.
**Why it happens:** Keycloak also runs on port 8080 externally. cAdvisor's default internal port is also 8080. If cAdvisor exposes port 8080 to the host, it conflicts.
**How to avoid:** Do NOT expose cAdvisor to the host. It only needs to be on `blitz-net` for Prometheus to scrape it internally. No `ports:` section for cAdvisor in docker-compose.yml.
**Warning signs:** cAdvisor container fails to start.

### Pitfall 6: Grafana Alert Rules Folder Must Exist
**What goes wrong:** Alert rule provisioning fails silently. No alerts appear in Grafana.
**Why it happens:** The `folder` field in alert_rules.yml must reference an existing Grafana folder. The `__Blitz` folder is created by the dashboard provisioning. If alert provisioning loads before dashboards, the folder doesn't exist yet.
**How to avoid:** Use the same `folder: __Blitz` and `folderUid: blitz-folder` in both dashboard provider and alert rules. Grafana handles this at startup — provisioning order is deterministic.
**Warning signs:** Grafana logs show "folder not found" on startup.

### Pitfall 7: Dashboard JSON `datasource.uid` Must Match Provisioned UIDs
**What goes wrong:** Dashboards show "Data source not found" for all panels.
**Why it happens:** Dashboard JSON panels reference datasource by uid. If `datasource.uid` in the JSON doesn't match the uid in `datasources.yml`, Grafana cannot resolve it.
**How to avoid:** Use consistent UIDs: `blitz-prometheus` and `blitz-loki` throughout. Set these UIDs in `datasources.yml` and reference them in all dashboard panel JSON.
**Warning signs:** Dashboard loads but all panels show "Data source blitz-prometheus not found."

### Pitfall 8: prometheus-fastapi-instrumentator Default /metrics Has No Auth
**What goes wrong:** Security concern — `/metrics` endpoint is publicly accessible.
**Why it happens:** The instrumentator exposes `/metrics` without authentication by default.
**How to avoid:** This is acceptable for this project — Prometheus scrapes from inside `blitz-net`. The `/metrics` endpoint is not reachable from the public internet (no external port). Document this explicitly.
**Warning signs:** None — this is an intentional design tradeoff for internal-only deployments.

---

## Code Examples

Verified patterns from official sources:

### Custom Metrics Registration (core/metrics.py)
```python
# Source: https://prometheus.github.io/client_python/
from prometheus_client import Counter, Histogram

blitz_tool_calls_total = Counter(
    "blitz_tool_calls_total",
    "Total tool calls by tool name and success status",
    ["tool", "success"],
)

blitz_tool_duration_seconds = Histogram(
    "blitz_tool_duration_seconds",
    "Tool execution latency in seconds",
    ["tool"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

blitz_llm_calls_total = Counter(
    "blitz_llm_calls_total",
    "Total LLM calls by model alias",
    ["model_alias"],
)

blitz_llm_duration_seconds = Histogram(
    "blitz_llm_duration_seconds",
    "LLM call duration in seconds",
    ["model_alias"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

blitz_memory_ops_total = Counter(
    "blitz_memory_ops_total",
    "Total memory operations by type",
    ["operation"],
)
```

### Instrumenting Tool Calls (security/acl.py)
```python
# Source: project patterns — existing log_tool_call function
# Add metric increment alongside existing structlog call
from core.metrics import blitz_tool_calls_total, blitz_tool_duration_seconds
import time

async def log_tool_call(user_id: str, tool: str, allowed: bool, elapsed: float) -> None:
    # Existing structlog call stays
    logger.info("tool_call", tool=tool, user_id=user_id, allowed=allowed, duration_ms=elapsed)
    # Add metric
    blitz_tool_calls_total.labels(tool=tool, success=str(allowed)).inc()
    blitz_tool_duration_seconds.labels(tool=tool).observe(elapsed / 1000.0)  # convert ms → s
```

### FastAPI Instrumentation (main.py)
```python
# Source: https://github.com/trallnag/prometheus-fastapi-instrumentator
from prometheus_fastapi_instrumentator import Instrumentator

def create_app() -> FastAPI:
    configure_logging(...)
    app = FastAPI(...)
    app.add_middleware(CORSMiddleware, ...)
    Instrumentator().instrument(app).expose(app)  # adds GET /metrics
    app.include_router(health.router)
    # ... remaining routers
    return app
```

### LogQL Query for JSON Log Parsing
```logql
# Source: https://grafana.com/docs/loki/latest/query/log_queries/
# Query logs from backend service, parse JSON, filter by level
{service="backend"} | json | level="ERROR"

# Query with user_id filter (extracted from JSON log line)
{service="backend"} | json | user_id="abc123"

# Count errors per service over time
count_over_time({job="blitz-agentos"} | json | level="ERROR" [5m])
```

### Loki Config with 90-Day Retention
```yaml
# Source: Official Loki documentation
# infra/loki/loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100
  log_level: warn

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 90d  # 90-day retention per CONTEXT.md

compactor:
  working_directory: /loki/compactor
  retention_enabled: true

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

analytics:
  reporting_enabled: false
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Promtail for log shipping | Grafana Alloy (successor) | 2024 | Alloy uses HCL config, supports more sources |
| Grafana 10 provisioning | Grafana 11 provisioning (same format) | 2024 | Alert provisioning YAML format unchanged |
| LiteLLM Prometheus (enterprise) | LiteLLM OSS Prometheus | Nov 2025 (v1.80.0) | `callbacks: ["prometheus"]` now free/open-source |
| prometheus-fastapi-instrumentator v6 | v7.1.0 | 2024 | Compatible with latest FastAPI; no API changes |

**Deprecated/outdated:**
- `Promtail`: Replaced by Grafana Alloy. Do not add Promtail to the stack.
- LiteLLM `prometheus_metrics: true` old flag: Current flag is `callbacks: ["prometheus"]` in `litellm_settings`. Verify this is current when implementing.

---

## Open Questions

1. **Grafana Client Registration in Keycloak**
   - What we know: Keycloak realm has `blitz-portal` and `blitz-backend` clients already. Grafana needs its own OIDC client registered.
   - What's unclear: Whether to create a `grafana` client in Keycloak manually before first run, or provision it via Keycloak realm JSON.
   - Recommendation: Create the `grafana` OIDC client manually in the Keycloak admin console as part of Plan 08-01 Task 1. Document the steps. Add `GRAFANA_OAUTH_CLIENT_SECRET` to `.env`.

2. **Alert Notifications In-Dashboard Only (context decision)**
   - What we know: CONTEXT.md says "in-dashboard only (Grafana alert panel, no external Slack/email for MVP)." But the design doc (`docs/plans/2026-03-01-phase8-observability-design.md`) includes Telegram alerts.
   - What's unclear: CONTEXT.md defers "external alert notifications" but the design doc has them. The design doc was the more recent document (same date).
   - Recommendation: The CONTEXT.md `deferred` section says "Grafana alerts to Slack or email" — Telegram is the channel used for user messages, not Slack/email. The design doc's Telegram alerting is NOT the same as external Slack/email. **Implement Telegram alert contact point as in the design doc.** This is consistent with the CONTEXT.md locked decision about "Grafana alert rule fires when daily or monthly spend exceeds a configured threshold" (which requires a contact point). Alert panel + Telegram contact point is the intended implementation.

3. **Dashboard JSON Generation Strategy**
   - What we know: Grafana dashboard JSON is complex (hundreds of lines per dashboard). The plan calls for 2 dashboards.
   - What's unclear: Whether to hand-write JSON or generate via Grafana UI.
   - Recommendation: Write the dashboard JSON directly (it can be done via reference to existing PromQL/LogQL queries). Hand-writing is faster than setting up a temporary Grafana, building in UI, and exporting. The plan document should include complete JSON.

4. **cAdvisor Port Collision Risk**
   - What we know: cAdvisor default listens on port 8080. Keycloak is also on 8080 externally (8180→8080 internal).
   - What's unclear: Whether cAdvisor internal port will conflict with Keycloak's internal service port on blitz-net.
   - Recommendation: Do NOT publish cAdvisor to any host port. On blitz-net, cAdvisor listens internally on 8080 and Keycloak listens internally on 8080 — but they are different containers with different DNS names (cadvisor:8080 vs keycloak:8080). No collision. Docker service names resolve to individual container IPs.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + pytest-asyncio 0.25.0 |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Estimated runtime | ~30-45 seconds (292 existing tests) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-01 | `GET /metrics` endpoint returns 200 with prometheus text format | unit/smoke | `PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py -x` | ❌ Wave 0 gap |
| OBSV-01 | Custom metric `blitz_tool_calls_total` increments on tool call | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py::test_tool_call_counter -x` | ❌ Wave 0 gap |
| OBSV-01 | `blitz_llm_calls_total` increments when `get_llm()` is used | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py::test_llm_call_counter -x` | ❌ Wave 0 gap |
| OBSV-02 | Loki config file is valid YAML with correct fields | manual | Review `infra/loki/loki-config.yml` manually | ❌ Wave 0 gap (infra config) |
| OBSV-02 | Alloy config.alloy references correct Loki URL and Docker socket | manual | Review `infra/alloy/config.alloy` manually | ❌ Wave 0 gap (infra config) |
| OBSV-03 | LiteLLM config.yaml has `callbacks: ["prometheus"]` | manual | Review `infra/litellm/config.yaml` manually | ❌ (to be added in plan) |

**Note on OBSV-02/OBSV-03:** These are infrastructure configuration requirements, not Python code requirements. They cannot be unit-tested with pytest. Verification is done by:
- `docker compose config --services` showing all 5 new services
- `curl http://localhost:4000/metrics` returning prometheus text from LiteLLM
- Grafana Explore showing log streams from Loki

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed Python task → run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green (must not drop below 292 tests) before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~30-45 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `backend/tests/test_metrics.py` — covers OBSV-01 metric registration and increment behavior
- [ ] `backend/core/metrics.py` — must exist before test_metrics.py can import it

**Infrastructure-only requirements (OBSV-02, OBSV-03):**
- No pytest tests needed — these are Docker Compose config files
- Verification: Docker Compose startup + HTTP smoke tests after `just up`

---

## Sources

### Primary (HIGH confidence)
- `docs/plans/2026-03-01-phase8-observability-design.md` — approved design doc (same date as research; authoritative)
- `docs/plans/2026-03-01-phase8-observability-plan.md` — detailed implementation plan with exact configs
- https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.docker/ — Alloy Docker log source
- https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/keycloak/ — Grafana Keycloak OIDC
- https://grafana.com/docs/grafana/latest/administration/provisioning/ — Grafana provisioning YAML format
- https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/ — Alert provisioning YAML
- https://docs.litellm.ai/docs/proxy/prometheus — LiteLLM Prometheus metrics config
- https://github.com/trallnag/prometheus-fastapi-instrumentator — version 7.1.0, FastAPI instrumentation
- https://prometheus.github.io/client_python/ — prometheus-client Python SDK

### Secondary (MEDIUM confidence)
- https://prometheus.io/docs/guides/cadvisor/ — cAdvisor Prometheus integration
- https://grafana.com/docs/loki/latest/query/log_queries/ — LogQL JSON parser
- Community forums: Grafana Keycloak TLS skip verify — `tls_skip_verify_insecure = true` works (ini or env var)

### Tertiary (LOW confidence)
- WebSearch: LiteLLM v1.80.0 Prometheus OSS release (Nov 2025) — confirmed but not directly verified against latest docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components are official Grafana stack; versions pinned in design doc
- Architecture: HIGH — design doc + plan doc provide complete implementation; research verifies key configs
- Pitfalls: HIGH — several pitfalls discovered from project-specific context (Keycloak self-signed cert, realm_roles field, structlog stdout)
- Keycloak OIDC: MEDIUM — role_attribute_path JMESPath for `realm_roles` field is project-specific; the generic Grafana docs use `realm_access.roles`

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (30 days — stable ecosystem)

---

## Key Implementation Notes for Planner

### Plan Breakdown (from approved design doc)

The design doc specifies these 5 plans:
1. **08-01: Infrastructure Stack** — docker-compose.yml additions (5 new services: prometheus, grafana, loki, alloy, cadvisor) + all infra config files
2. **08-02: LiteLLM + FastAPI Metrics** — litellm config.yaml prometheus flag + prometheus-fastapi-instrumentator in main.py
3. **08-03: Custom Agent Metrics** — backend/core/metrics.py + instrumentation in security/acl.py, memory/, core/config.py
4. **08-04: Grafana Dashboards** — 2 dashboard JSON files (ops-dashboard.json, costs-dashboard.json)
5. **08-05: Grafana Alerting + Keycloak SSO** — alert rules + Telegram contact point + Keycloak OIDC env vars

The CONTEXT.md notes "2 dashboards" (Ops + Costs) while the design doc lists 4 dashboard files (Service Health, API Health, Agent Activity, LiteLLM Costs). The planner should consolidate to 2 per CONTEXT.md locked decision: one Ops dashboard (combines service health + agent performance + embedded log panel) and one Costs dashboard (LiteLLM spend).

### Environment Variables Required (new)
```bash
GRAFANA_ADMIN_PASSWORD=   # Grafana admin UI local password
GRAFANA_ALERT_CHAT_ID=    # Telegram chat ID for Grafana service-down alerts
GRAFANA_OAUTH_CLIENT_SECRET=   # Keycloak 'grafana' client secret (create client first)
```
`TELEGRAM_BOT_TOKEN` already exists — reused for Grafana Telegram contact point.

### New Keycloak Setup Required
Before Plan 08-01 or as first task in 08-01: Create a `grafana` OIDC client in Keycloak blitz-internal realm with:
- Client ID: `grafana`
- Access Type: confidential
- Valid redirect URIs: `http://localhost:3001/*`
- Copy client secret → add to `.env` as `GRAFANA_OAUTH_CLIENT_SECRET`

Also create the `ops` Keycloak realm role (new role, not yet in the realm).
