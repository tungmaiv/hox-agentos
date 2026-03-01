---
phase: 08-observability
plan: "01"
subsystem: infra
tags: [prometheus, grafana, loki, alloy, cadvisor, docker-compose, observability]

# Dependency graph
requires:
  - phase: 07-hardening-and-sandboxing
    provides: Fully hardened backend services to observe
provides:
  - Prometheus v3.2.1 scraping cadvisor:8080, litellm:4000/metrics, backend:8000/metrics on blitz-net
  - Grafana v11.4.0 at localhost:3001 with Keycloak OIDC + local admin fallback
  - Loki v3.3.2 with 90-day log retention using filesystem tsdb storage
  - Alloy v1.6.1 reading Docker container stdout via Docker socket and shipping to Loki
  - cAdvisor (latest) providing container resource metrics to Prometheus (no host port exposure)
  - 3 named volumes: prometheus_data, grafana_data, loki_data
  - Grafana datasources pre-provisioned with UIDs blitz-prometheus and blitz-loki
  - Grafana dashboard provider pointing at /etc/grafana/dashboards with blitz-folder UID
affects:
  - 08-02 (metrics instrumentation — depends on Prometheus datasource UID blitz-prometheus)
  - 08-03 (dashboards — depends on datasource UIDs and blitz-folder for alert rule placement)

# Tech tracking
tech-stack:
  added:
    - prom/prometheus:v3.2.1 (metrics collection)
    - grafana/grafana:11.4.0 (visualization + alerting)
    - grafana/loki:3.3.2 (log aggregation)
    - grafana/alloy:v1.6.1 (log shipping via Docker socket)
    - gcr.io/cadvisor/cadvisor:latest (container resource metrics)
  patterns:
    - All observability services on blitz-net only (no unnecessary host port exposure)
    - Grafana datasource UIDs are stable constants (blitz-prometheus, blitz-loki) referenced by dashboard JSON
    - Alloy uses loki.source.docker (not file tailing) because structlog writes to stdout
    - Grafana keeps GF_AUTH_DISABLE_LOGIN_FORM=false for local admin fallback when Keycloak is down
    - realm_roles JMESPath (not realm_access.roles) for Grafana OIDC role mapping

key-files:
  created:
    - infra/prometheus/prometheus.yml
    - infra/loki/loki-config.yml
    - infra/alloy/config.alloy
    - infra/grafana/provisioning/datasources/datasources.yml
    - infra/grafana/provisioning/dashboards/dashboards.yml
  modified:
    - docker-compose.yml (added 5 services + 3 volumes)

key-decisions:
  - "Alloy uses loki.source.docker (not file tailing) — structlog writes to stdout, not files"
  - "cAdvisor has no host port binding — Prometheus scrapes cadvisor:8080 on blitz-net; Keycloak also on 8080 but different DNS name, no collision"
  - "GF_AUTH_DISABLE_LOGIN_FORM=false — keep local admin fallback in case Keycloak is down"
  - "realm_roles JMESPath in ROLE_ATTRIBUTE_PATH — matches Keycloak realm_roles flat list, not realm_access.roles nested path"
  - "datasource UIDs blitz-prometheus and blitz-loki — stable constants dashboard JSON panels reference by UID"
  - "loki-config.yml compactor.delete_request_store=filesystem — required for Loki 3.3.x to start with retention_enabled"

patterns-established:
  - "Observability pattern: all 5 services communicate on blitz-net internally; only Grafana exposed to host on port 3001"
  - "Provisioning pattern: Grafana datasources and dashboard provider are file-provisioned (not UI-configured) for reproducibility"

requirements-completed: [OBSV-01, OBSV-02, OBSV-03]

# Metrics
duration: ~10min
completed: 2026-03-01
---

# Phase 08 Plan 01: Observability Infrastructure Stack Summary

**Prometheus + Grafana + Loki + Alloy + cAdvisor deployed as 5 Docker Compose services with file-provisioned datasources, 90-day log retention, and Keycloak OIDC auth with local admin fallback**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-01T12:00:00Z (estimated)
- **Completed:** 2026-03-01T12:18:55Z
- **Tasks:** 3
- **Files modified:** 7 (3 created in infra + 2 Grafana provisioning + docker-compose.yml update + loki fix)

## Accomplishments

- Created all 6 infra config files for the observability stack (prometheus.yml, loki-config.yml, config.alloy, datasources.yml, dashboards.yml)
- Added 5 new Docker Compose services (prometheus, grafana, loki, alloy, cadvisor) and 3 named volumes to docker-compose.yml
- Grafana pre-provisioned with Prometheus (uid: blitz-prometheus) and Loki (uid: blitz-loki) datasources and dashboard file provider
- Loki configured with 90-day retention using filesystem tsdb storage and compactor
- Alloy reads Docker container stdout via Docker socket with hox-agentos project filter (not file tailing)
- Fixed Loki startup issue by adding `delete_request_store: filesystem` required by Loki 3.3.x when retention_enabled

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Prometheus, Loki, and Alloy config files** - `0af347c` (feat)
2. **Task 2: Create Grafana provisioning config files** - `31709a9` (feat)
3. **Task 3: Add 5 new services and volumes to docker-compose.yml** - `f7c215c` (feat)

**Auto-fix (post-task):** `2498349` (fix: Loki delete_request_store and Grafana alerting mount for dev startup)

## Files Created/Modified

- `infra/prometheus/prometheus.yml` - Prometheus scrape config: cadvisor:8080, litellm:4000/metrics, backend:8000/metrics at 15s interval
- `infra/loki/loki-config.yml` - Loki config: filesystem storage, tsdb v13 schema, 90-day retention, compactor with delete_request_store=filesystem
- `infra/alloy/config.alloy` - Alloy pipeline: discovery.docker -> relabel (keep hox-agentos) -> loki.source.docker -> loki.write at loki:3100
- `infra/grafana/provisioning/datasources/datasources.yml` - Prometheus (uid: blitz-prometheus, isDefault) + Loki (uid: blitz-loki) datasources
- `infra/grafana/provisioning/dashboards/dashboards.yml` - File provider: /etc/grafana/dashboards, folder __Blitz, folderUid blitz-folder
- `docker-compose.yml` - Added prometheus, grafana, loki, alloy, cadvisor services + prometheus_data, grafana_data, loki_data volumes

## Decisions Made

- **Alloy uses loki.source.docker not file tailing** — structlog JSON is written to stdout (Docker captures it), not to files at /app/logs
- **cAdvisor has no host port binding** — Prometheus scrapes on blitz-net only; Keycloak also uses 8080 internally but on different DNS name (cadvisor:8080 vs keycloak:8080), no collision
- **GF_AUTH_DISABLE_LOGIN_FORM=false** — local admin account preserved as fallback if Keycloak is unavailable; prevents lockout
- **realm_roles JMESPath** — Grafana OIDC ROLE_ATTRIBUTE_PATH uses `realm_roles[*]` (flat list) not `realm_access.roles` per known JWT gotcha documented in STATE.md
- **datasource UIDs are stable constants** — blitz-prometheus and blitz-loki are the UIDs dashboard JSON panels reference; changing them breaks all panels
- **delete_request_store: filesystem** — required in Loki 3.3.x compactor config when retention_enabled=true; missing causes Loki to fail on startup

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Loki startup failure due to missing delete_request_store**
- **Found during:** Post-task verification (service startup testing)
- **Issue:** Loki 3.3.x requires `compactor.delete_request_store` to be set when `retention_enabled: true`; without it, Loki crashes on startup with a config validation error
- **Fix:** Added `delete_request_store: filesystem` to the `compactor` section in `infra/loki/loki-config.yml`
- **Files modified:** infra/loki/loki-config.yml
- **Verification:** Loki starts cleanly after fix
- **Committed in:** `2498349`

**2. [Rule 3 - Blocking] Grafana alerting volume mount removed for dev startup**
- **Found during:** Post-task verification
- **Issue:** `infra/grafana/provisioning/alerting/` directory does not exist yet (plan 08-03 creates it); Docker bind mount of non-existent directory causes Grafana container to fail with "no such file or directory"
- **Fix:** Removed the alerting volume mount from grafana service; added comment explaining it must be enabled in plan 08-03 once alerting dir is created
- **Files modified:** docker-compose.yml
- **Verification:** Grafana starts without the alerting mount
- **Committed in:** `2498349`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for services to start. No scope creep — loki-config.yml version-specific requirement and alerting mount belongs to plan 08-03.

## Issues Encountered

- Loki 3.3.x requires `delete_request_store` in compactor config when retention is enabled — this is a version-specific breaking change from Loki 3.x that the plan template did not include. Fixed by adding `delete_request_store: filesystem`.
- Grafana alerting provisioning directory referenced before it exists (plan 08-03 creates it) — removed the bind mount with a comment to re-enable in 08-03.

## User Setup Required

None - no external service configuration required beyond existing `.env` variables (GRAFANA_ADMIN_PASSWORD, GRAFANA_OAUTH_CLIENT_SECRET, GRAFANA_ALERT_CHAT_ID already templated).

## Next Phase Readiness

- All 5 observability services defined and verified ready to start with `just up` or `docker compose up`
- Grafana accessible at localhost:3001 with Prometheus and Loki datasources pre-provisioned
- Plan 08-02 (metrics instrumentation) can proceed — Prometheus is ready to scrape backend:8000/metrics
- Plan 08-03 (dashboards + alerting) can proceed — datasource UIDs and folder UID are stable

---
*Phase: 08-observability*
*Completed: 2026-03-01*
