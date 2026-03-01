# Phase 8: Observability — Design

**Date:** 2026-03-01
**Phase:** 08-observability
**Status:** Approved — ready for planning

---

## Goal

Add full-stack observability to Blitz AgentOS: real-time service health dashboards, structured log aggregation, LiteLLM cost tracking, and basic service-down alerting via Telegram. All dashboards are auto-provisioned at startup — no manual Grafana UI setup required.

Satisfies requirements: OBSV-01 (Grafana health dashboards), OBSV-02 (Loki log aggregation), OBSV-03 (LiteLLM cost tracking).

---

## Approach

Prometheus-centric stack: Prometheus scrapes metrics from cAdvisor, LiteLLM, and FastAPI. Grafana Alloy tails existing structlog JSON files and ships to Loki. Grafana uses Prometheus + Loki as data sources. Alert rules fire to Telegram via provisioned contact point.

---

## Section 1: Infrastructure Stack

Five new Docker Compose services on `blitz-net`:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `prometheus` | `prom/prometheus:v3` | 9090 (internal) | Scrapes and stores metrics |
| `grafana` | `grafana/grafana:11` | 3001 (external) | Dashboards + alerting UI |
| `loki` | `grafana/loki:3` | 3100 (internal) | Log aggregation store |
| `alloy` | `grafana/alloy:1` | — | Tails JSON log files → Loki |
| `cadvisor` | `gcr.io/cadvisor/cadvisor:latest` | 8080 (internal) | Docker container resource metrics |

**Persistence:** named volumes `prometheus_data`, `grafana_data`, `loki_data`.

**Config files:**
```
infra/
  prometheus/
    prometheus.yml          # scrape configs for cadvisor, litellm, backend
  grafana/
    provisioning/
      datasources/
        datasources.yml     # Prometheus + Loki data sources
      dashboards/
        dashboards.yml      # folder + file provider config
      alerting/
        contact_points.yml  # Telegram contact point
        alert_rules.yml     # service-down + high-error-rate rules
    dashboards/
      service-health.json
      api-health.json
      agent-activity.json
      litellm-costs.json
  loki/
    loki-config.yml         # filesystem storage, no auth (internal-only)
  alloy/
    config.alloy            # tail logs/blitz/*.json → push to Loki
```

Grafana is fully provisioned from these files on startup. No manual UI setup required after `just up`.

---

## Section 2: Metrics Collection

### Three Prometheus scrape targets

**1. cAdvisor** — Docker container CPU, memory, network, restarts per service. Zero code changes.

**2. LiteLLM** — Add `prometheus_metrics: true` to `infra/litellm/config.yaml`. Exposes `/metrics` with spend by user/model, token counts, request latency. Satisfies OBSV-03.

**3. FastAPI backend** — Add `prometheus-fastapi-instrumentator` to backend deps. 5-line addition to `main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```
Exposes `/metrics` with HTTP request rate, latency histograms, error rate by endpoint.

### Custom agent metrics

New file: `backend/core/metrics.py` — registers `prometheus_client` metrics at module level.

| Metric | Type | Labels | Instrumented in |
|--------|------|--------|-----------------|
| `blitz_tool_calls_total` | Counter | `tool`, `success` | `gateway/agui_middleware.py` |
| `blitz_tool_duration_seconds` | Histogram | `tool` | `gateway/agui_middleware.py` |
| `blitz_memory_ops_total` | Counter | `operation` | `memory/short_term.py`, `memory/long_term.py` |
| `blitz_memory_duration_seconds` | Histogram | `operation` | `memory/short_term.py`, `memory/long_term.py` |
| `blitz_llm_calls_total` | Counter | `model_alias` | `core/config.py` `get_llm()` wrapper |
| `blitz_llm_duration_seconds` | Histogram | `model_alias` | `core/config.py` `get_llm()` wrapper |

**Label cardinality rule:** All labels are low-cardinality (tool name, model alias, operation type). No `user_id` in metric labels — per-user spend stays in LiteLLM.

---

## Section 3: Dashboards (4 pre-provisioned)

All dashboards in `infra/grafana/dashboards/*.json`, folder `__Blitz`, auto-refresh 30s, default range 1h.

| Dashboard | Key panels |
|-----------|-----------|
| **Service Health** | Container up/down per service, CPU %, memory %, container restart count over time |
| **API Health** | Request rate (req/s), p50/p95/p99 latency by endpoint, 5xx error rate, active connections |
| **Agent Activity** | Tool call rate by tool name, tool p95 latency, memory op rate, LLM call rate by model alias, LLM p95 duration |
| **LiteLLM Costs** | Daily spend by model, spend by user (top 10), cumulative monthly spend, token usage by model |

---

## Section 4: Alerting

Two alert rules provisioned in `infra/grafana/provisioning/alerting/`:

| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| **Service Down** | Any monitored container not running for >1 min (backend, postgres, redis, litellm, keycloak, celery) | Critical | Telegram |
| **High Error Rate** | FastAPI 5xx rate >5% over 5-minute window | Warning | Telegram |

**Telegram contact point** uses `TELEGRAM_BOT_TOKEN` (existing) and a new `GRAFANA_ALERT_CHAT_ID` env var. Both are provisioned via `infra/grafana/provisioning/alerting/contact_points.yml` — no manual Grafana UI setup.

---

## Plan Breakdown

| Plan | Title | Scope |
|------|-------|-------|
| 08-01 | Infrastructure stack | docker-compose.yml additions + all infra config files (Prometheus, Loki, Alloy, Grafana provisioning skeleton) |
| 08-02 | LiteLLM + FastAPI metrics | `infra/litellm/config.yaml` prometheus flag + `prometheus-fastapi-instrumentator` in `main.py` |
| 08-03 | Custom agent metrics | `backend/core/metrics.py` + instrumentation in 5 backend files |
| 08-04 | Grafana dashboards | 4 dashboard JSON files in `infra/grafana/dashboards/` |
| 08-05 | Grafana alerting | Alert rules + Telegram contact point provisioning |

---

## Environment Variables Required

Add to `.env` (and `.dev-secrets.example`):
```
GRAFANA_ADMIN_PASSWORD=<password>
GRAFANA_ALERT_CHAT_ID=<telegram-chat-id-for-alerts>
```

`TELEGRAM_BOT_TOKEN` already exists in `.env` — reused for Grafana alerts.

---

## Constraints

- Grafana on port 3001 (pre-assigned in CLAUDE.md service port map)
- Prometheus, Loki, Alloy, cAdvisor are internal-only (no external ports except Grafana)
- No Kubernetes, no Grafana Cloud — fully on-premise Docker Compose
- All provisioning files are committed to git (no secrets in provisioning — secrets injected via env vars)
- `logs/blitz/` volume mount already exists in docker-compose.yml (shared between backend and alloy)

---

*Design approved: 2026-03-01*
*Approach: Prometheus + Grafana + Loki + Alloy + cAdvisor*
*Requirements covered: OBSV-01, OBSV-02, OBSV-03*
