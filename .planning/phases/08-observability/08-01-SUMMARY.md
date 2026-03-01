---
phase: 08-observability
plan: "01"
subsystem: infra
tags: [prometheus, grafana, loki, alloy, cadvisor, docker-compose, observability]

# Dependency graph
requires:
  - phase: 07-hardening-and-sandboxing
    provides: working backend service with security hardening complete
provides:
  - docker-compose services for prometheus, grafana, loki, alloy, cadvisor
  - prometheus.yml with 3 scrape targets (cadvisor, litellm, backend)
  - loki-config.yml with 90-day filesystem retention and tsdb v13 schema
  - alloy config.alloy with docker log collection pipeline
  - grafana provisioning datasources (blitz-prometheus, blitz-loki UIDs)
  - grafana provisioning dashboards (blitz-folder, /etc/grafana/dashboards path)
  - 3 named volumes: prometheus_data, grafana_data, loki_data
affects: [08-02, 08-03, 08-04, 08-05]

# Tech tracking
tech-stack:
  added:
    - prom/prometheus:v3.2.1
    - grafana/grafana:11.4.0
    - grafana/loki:3.3.2
    - grafana/alloy:v1.6.1
    - gcr.io/cadvisor/cadvisor:latest
  patterns:
    - Grafana OIDC using realm_roles JMESPath (flat list, not realm_access.roles)
    - cAdvisor with no host port binding to avoid conflict with Keycloak on blitz-net
    - Alloy uses loki.source.docker (not file tailing) because structlog writes to stdout
    - Grafana local admin login kept enabled (GF_AUTH_DISABLE_LOGIN_FORM=false) as fallback if Keycloak down
    - Datasource UIDs locked to blitz-prometheus and blitz-loki for dashboard panel references

key-files:
  created:
    - infra/prometheus/prometheus.yml
    - infra/loki/loki-config.yml
    - infra/alloy/config.alloy
    - infra/grafana/provisioning/datasources/datasources.yml
    - infra/grafana/provisioning/dashboards/dashboards.yml
    - infra/grafana/dashboards/ (empty dir for Plan 08-03 dashboard JSON files)
  modified:
    - docker-compose.yml

key-decisions:
  - "cAdvisor has no host port — Prometheus scrapes cadvisor:8080 on blitz-net only; no conflict with Keycloak which also uses 8080 (different DNS names)"
  - "GF_AUTH_DISABLE_LOGIN_FORM=false — keep local admin as fallback if Keycloak is down (prevent full lockout)"
  - "Grafana ROLE_ATTRIBUTE_PATH uses realm_roles[*] (flat list) not realm_access.roles — matches Keycloak realm config per STATE.md decision"
  - "Alloy reads Docker stdout via Docker socket (loki.source.docker) — structlog emits JSON to stdout, not log files"
  - "Datasource UIDs blitz-prometheus and blitz-loki are stable identifiers for dashboard JSON panel datasourceRef"
  - "Loki uses tsdb schema v13 with filesystem storage — appropriate for single-node MVP at 100-user scale"

patterns-established:
  - "Observability services on blitz-net only (no external ports except Grafana:3001)"
  - "Named volume per stateful service: prometheus_data, grafana_data, loki_data"
  - "Provisioning-first Grafana: datasources and dashboards auto-provisioned from ./infra/grafana/provisioning"

requirements-completed: [OBSV-01, OBSV-02, OBSV-03]

# Metrics
duration: 3min
completed: 2026-03-01
---

# Phase 8 Plan 01: Observability Infrastructure Stack Summary

**Five-service observability stack (Prometheus + Grafana + Loki + Alloy + cAdvisor) added to Docker Compose with all config files provisioned and Keycloak OIDC wired using flat realm_roles**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-01T11:30:20Z
- **Completed:** 2026-03-01T11:33:05Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Created 3 infrastructure config files: prometheus.yml (3 scrape targets), loki-config.yml (90d retention), config.alloy (docker log pipeline)
- Created 2 Grafana provisioning files: datasources (blitz-prometheus + blitz-loki UIDs), dashboards (blitz-folder provider)
- Added 5 new Docker Compose services and 3 named volumes to docker-compose.yml with correct network and security configuration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Prometheus, Loki, and Alloy config files** - `cfab4bd` (feat)
2. **Task 2: Create Grafana provisioning config files** - `9f80fde` (feat)
3. **Task 3: Add 5 new services and volumes to docker-compose.yml** - `6216db3` (feat)

## Files Created/Modified
- `infra/prometheus/prometheus.yml` - Scrape configs for cadvisor:8080, litellm:4000/metrics, backend:8000/metrics
- `infra/loki/loki-config.yml` - Filesystem storage, tsdb v13 schema, 90d retention with compactor enabled
- `infra/alloy/config.alloy` - Docker discovery pipeline filtering hox-agentos project, shipping to loki:3100
- `infra/grafana/provisioning/datasources/datasources.yml` - Prometheus (uid: blitz-prometheus, isDefault) + Loki (uid: blitz-loki)
- `infra/grafana/provisioning/dashboards/dashboards.yml` - File provider at /etc/grafana/dashboards, blitz-folder uid
- `docker-compose.yml` - Added prometheus, grafana (port 3001), loki, alloy, cadvisor services + 3 named volumes

## Decisions Made
- cAdvisor has no host port binding — Prometheus scrapes cadvisor:8080 on blitz-net; no conflict with Keycloak (different DNS names on same network)
- GF_AUTH_DISABLE_LOGIN_FORM=false — local admin kept as fallback if Keycloak is unavailable (prevents full lockout)
- ROLE_ATTRIBUTE_PATH uses realm_roles flat list (not realm_access.roles) — matches Keycloak realm configuration established in STATE.md
- Alloy uses loki.source.docker (not file tailing) — structlog outputs JSON to stdout, collected via Docker socket
- Datasource UIDs blitz-prometheus and blitz-loki are stable for dashboard panel datasourceRef in Plan 08-03

## Deviations from Plan

None - plan executed exactly as written.

Note: Files backend/core/metrics.py, backend/tests/test_metrics.py, and backend/pyproject.toml were pre-staged in the worktree from a prior partial session and were committed alongside the Task 3 docker-compose.yml changes. These files belong to Plan 08-02 scope but their early inclusion does not affect correctness — they are valid 08-02 work.

## Issues Encountered
- Pre-staged backend files (metrics.py, test_metrics.py) were included in the Task 3 commit due to prior incomplete session leaving them in the git index. Files are valid and correct — no rework needed.

## User Setup Required
None - no external service configuration required beyond what is already in docker-compose.yml environment variables.

## Next Phase Readiness
- Plan 08-02 (metrics instrumentation in backend code) can proceed — infra foundation is complete
- Plan 08-03 (Grafana dashboards JSON) can proceed — provisioning directory wired
- Run `just up` to start the full observability stack including the 5 new services
- Grafana available at http://localhost:3001 (admin/admin by default, or GRAFANA_ADMIN_PASSWORD env var)

---
*Phase: 08-observability*
*Completed: 2026-03-01*
