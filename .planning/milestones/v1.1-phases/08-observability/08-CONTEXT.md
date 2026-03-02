# Phase 8: Observability - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Operations team can monitor system health, agent performance, LLM costs, and troubleshoot issues through centralized Grafana dashboards and Loki log aggregation. This phase delivers the observability infrastructure (Grafana + Loki + Alloy) and dashboards. An admin UI for configuring these settings is a separate phase.

</domain>

<decisions>
## Implementation Decisions

### Dashboard Layout
- **2 dashboards**: Ops Dashboard + Costs Dashboard (not 3 separate, not 1 unified)
- Ops Dashboard contains: system health panels + agent performance panels + embedded log panel
- Costs Dashboard contains: LLM spend breakdown + alert status
- 30-second auto-refresh on both dashboards

### System Health Panels (Ops Dashboard)
- Both service uptime/error rates AND infrastructure metrics combined
- Service uptime: is each Docker service healthy? (backend, frontend, postgres, redis, keycloak, litellm, celery)
- Error rates: % of HTTP 5xx responses per service
- Infrastructure: CPU, memory, disk usage per container

### Agent Performance Panels (Ops Dashboard)
- Latency per agent invocation (p50, p95)
- Success/failure rates per agent
- Token usage per invocation broken down by model alias
- All three combined in the Ops Dashboard

### Log Search (Ops Dashboard)
- Embedded log table panel on the Ops Dashboard showing recent logs
- "View in Explore" link for full LogQL power queries in Grafana Explore
- Ops uses Grafana Explore (not a custom search UI) for deep dives

### Loki Configuration
- **Labels indexed:** `service`, `level`, `user_id` — the three primary filter axes
- **Retention:** 90 days
- **Log sources via Alloy:**
  1. Structured JSON audit logs from `logs/blitz/` directory (structlog output)
  2. Docker container stdout for all services (catches startup errors, crashes, migrations)

### Cost Tracking (Costs Dashboard)
- Breakdown: by model alias (`blitz/master`, `blitz/fast`, `blitz/coder`) AND by user
- Time aggregation: daily spend trend + monthly cumulative total
- Grafana alert rule fires when daily or monthly spend exceeds a configured threshold
- Alert notification: in-dashboard only (Grafana alert panel, no external Slack/email for MVP)
- **Data source:** LiteLLM Proxy spend API — LiteLLM's built-in `/spend` endpoints

### Access Control
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

</decisions>

<specifics>
## Specific Ideas

- Retention (90 days) and alert thresholds should be **env var configurable** at deploy time — not hardcoded in config files. Admin settings UI for these is deferred.
- `ops` Keycloak role: a new role to be created in the `blitz-internal` realm, distinct from full `admin` privileges. Ops users can monitor but don't have admin capabilities elsewhere.
- Grafana port 3001 is already noted in CLAUDE.md Section 3 Service Port Map as "Pre-production only" — this phase makes it a real, always-on service.

</specifics>

<deferred>
## Deferred Ideas

- **Admin UI settings page** — An in-app settings screen where admins can configure Grafana refresh rate and Loki retention days. Belongs in a future admin/settings phase.
- **External alert notifications** — Grafana alerts to Slack or email. In-dashboard alerts only for this phase; external channels are a future enhancement.
- **Per-user cost self-service** — Regular users seeing their own usage/cost panel. Currently ops-only.

</deferred>

---

*Phase: 08-observability*
*Context gathered: 2026-03-01*
