---
created: 2026-03-15T06:51:58.504Z
title: "Implement Unified Dashboard (Topics #08 + #14 Merged)"
area: ui
priority: high
target: v1.4-enhancement
effort: 6 weeks
existing_code: 0-15%
depends_on: []
design_doc:
  - docs/enhancement/topics/08-analytics-observability-dashboard/00-specification.md
  - docs/enhancement/topics/14-agentos-dashboard-mission-control/00-specification.md
---

## Problem

No user-facing operational dashboard or embedded analytics exist in the AgentOS UI. Phase 8 deployed Grafana/Prometheus/Loki infrastructure (port 3001) but this is for operations teams only — no embedded metrics for end users or non-technical admins.

Architecture decision confirmed: merge Topics #08 (Analytics) and #14 (Mission Control) into a unified dashboard at `/dashboard` with tab-based navigation.

## What Exists (0-15%)

- Grafana at port 3001 with Prometheus + Loki
- `prometheus-client` and `prometheus-fastapi-instrumentator` in backend dependencies
- No embedded analytics pages in AgentOS UI
- No dashboard frontend routes or API endpoints
- No Tremor React charts or charting library
- No materialized views for analytics

## What's Needed

- **Unified dashboard at `/dashboard`** — single entry point with tab-based navigation
- **Mission Control tab (#14):**
  - Real-time agent activity feed (WebSocket)
  - Live workflow execution monitoring
  - Active sessions and conversations
  - System status and alerts
- **Analytics tab (#08):**
  - Historical usage trends (DAU/MAU, feature adoption)
  - Performance metrics over time
  - User engagement statistics
  - Resource utilization charts
  - Cost analytics (LLM spending)
- **Shared infrastructure:**
  - Tremor React chart components
  - Metrics aggregation service
  - WebSocket real-time event system
  - Materialized views for performance
  - Role-based tab visibility (users see Mission Control, admins see all)
  - Deep-link to Grafana for technical metrics

## Solution

Follow specifications at both design docs. Implement as unified dashboard per confirmed architecture decision (ANALYSIS-REPORT.md Session 3).
