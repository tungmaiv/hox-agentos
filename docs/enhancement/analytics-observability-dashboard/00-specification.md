# Analytics & Observability Dashboard

**Status:** ✅ Design Complete  
**Priority:** Medium  
**Target:** v1.4  
**Estimated Effort:** 1 Phase (6 weeks)  
**Last Updated:** 2026-03-16

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Architecture](#architecture)
4. [Data Sources & Integration](#data-sources--integration)
5. [Page Structure & Features](#page-structure--features)
6. [Implementation Phases](#implementation-phases)
7. [Success Criteria](#success-criteria)
8. [Risks and Mitigations](#risks-and-mitigations)
9. [Consistency with Topic #14](#consistency-with-topic-14)
10. [Related Documents](#related-documents)

---

## Executive Summary

This enhancement introduces a comprehensive **Analytics & Observability Dashboard** that provides historical trends, performance metrics, cost analysis, and security auditing capabilities. It complements Topic #14 (Dashboard & Mission Control) by focusing on **analytics and insights** rather than real-time operations.

### Key Innovation: Dual-Mode Analytics

Topic #8 provides **two complementary interfaces**:

1. **Standalone Grafana UI** (Port 3001) - Full-featured dashboards for operations teams
2. **Embedded Panels** in Next.js - Integrated analytics views for daily use

Both interfaces share the same data sources but serve different user needs and contexts.

### Scope Coverage

This system covers **six analytics categories**:
- **Usage Analytics** - User engagement, DAU/MAU, feature adoption
- **Performance Analytics** - System metrics, API latency, resource utilization
- **Cost Analytics** - LLM spending, token usage, budget tracking
- **Agent Effectiveness** - Success rates, completion times, error patterns
- **Security & Audit** - Login patterns, permission changes, anomalies
- **Overview** - High-level summary and key metrics

### Target Users

- **IT Operations**: Deep-dive analysis via Grafana
- **System Administrators**: Security auditing and compliance
- **Management**: Cost tracking and ROI metrics
- **End Users**: Personal usage statistics (embedded views)

---

## Problem Statement

### Current State (As-Is)

| Aspect | Current Reality | Pain Point |
|--------|----------------|------------|
| **Usage Tracking** | No visibility into user engagement | Cannot measure adoption or identify power users |
| **Performance Monitoring** | Grafana exists but technical only | Non-technical users cannot interpret metrics |
| **Cost Visibility** | Check LiteLLM logs manually | No centralized cost tracking or budgeting |
| **Historical Trends** | Query databases directly | Time-consuming, requires SQL knowledge |
| **Security Auditing** | Parse raw logs | No structured audit trail viewer |
| **Report Generation** | Manual data collection | Cannot generate usage reports for stakeholders |

### Target State (To-Be)

| Aspect | Target Experience | Benefit |
|--------|------------------|---------|
| **Usage Tracking** | Visual dashboards with trends | Data-driven feature decisions |
| **Performance Monitoring** | User-friendly charts and alerts | Proactive issue identification |
| **Cost Visibility** | Automated cost tracking with budgets | Financial control and forecasting |
| **Historical Trends** | Time-range filtering with instant results | Quick historical analysis |
| **Security Auditing** | Structured audit trail with filtering | Compliance and security monitoring |
| **Report Generation** | One-click export to CSV/PDF | Easy stakeholder reporting |

### Relationship to Topic #14

Topic #14 (Dashboard & Mission Control) and Topic #8 serve complementary purposes:

| | Topic #14 | Topic #8 |
|---|---|---|
| **Focus** | Real-time operations | Historical trends & analysis |
| **Data Freshness** | Live (seconds) | Near real-time (5-15 minutes) |
| **Primary Use** | Daily monitoring, troubleshooting | Reporting, planning, optimization |
| **Users** | End users + admins | Ops teams + management |
| **UI Style** | Activity feeds, execution lists | Charts, graphs, trends |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ANALYTICS & OBSERVABILITY                   │
│                         DASHBOARD SYSTEM                         │
├─────────────────────────────┬───────────────────────────────────┤
│   STANDALONE GRAFANA UI     │      EMBEDDED NEXT.JS PANELS      │
│   (Port 3001)               │      (/admin/analytics/*)         │
├─────────────────────────────┼───────────────────────────────────┤
│ • Full-featured dashboards  │ • Integrated with AgentOS UI      │
│ • Custom alerting rules     │ • Simplified views for users      │
│ • Ad-hoc queries            │ • Matches design system           │
│ • Technical deep-dive       │ • JWT authentication              │
└─────────────────────────────┴───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED DATA SOURCES                           │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  PROMETHEUS     │     LOKI        │      POSTGRESQL             │
│  (metrics)      │    (logs)       │   (state + matviews)        │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Hybrid Query Strategy (Approach 3)

```
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI ANALYTICS API                       │
├───────────────────────────────┬─────────────────────────────────┤
│   REAL-TIME QUERIES           │   HISTORICAL AGGREGATES         │
│   (< 1 hour old)              │   (materialized views)          │
├───────────────────────────────┼─────────────────────────────────┤
│ • Direct Prometheus/Loki      │ • PostgreSQL materialized views │
│ • Fast for recent data        │ • Pre-computed for performance  │
│ • Live system status          │ • Trends, comparisons, reports  │
└───────────────────────────────┴─────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYTICS SERVICE LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Prometheus  │  │     Loki     │  │  PostgreSQL Matviews │   │
│  │   Client     │  │   Client     │  │      Manager         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Grafana HTTP API + Custom Components (Approach B)**
- ✅ Consistent with Topic #14's backend aggregation pattern
- ✅ Matches AgentOS design system (no embedded iframe styling issues)
- ✅ Full JWT + RBAC control through existing security gates
- ✅ Can mix Grafana data with AgentOS-specific data
- ✅ Backend caching reduces load on data sources

**Hybrid Query Strategy (Approach 3)**
- ✅ Best of both worlds: fast historical queries + fresh real-time data
- ✅ Materialized views are perfect for ~100 user scale
- ✅ PostgreSQL 16 has excellent concurrent refresh support
- ✅ Consistent with Topic #14's hybrid real-time patterns

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Integration Pattern** | Grafana API + Custom Components | Design system consistency, full RBAC control |
| **Query Strategy** | Hybrid (Materialized Views + Direct) | Performance for history, freshness for recent |
| **Chart Library** | Tremor React | Pre-built analytics components, professional defaults |
| **Data Sources** | Prometheus, Loki, PostgreSQL | Leverages existing Phase 8 infrastructure |
| **Authentication** | Existing JWT + RBAC | Reuses current security gates |
| **Caching** | Redis, 30s TTL | Reduces load, improves response times |

---

## Data Sources & Integration

### Data Source Mapping

| Data Category | Source | Access Method | Use Cases |
|---------------|--------|---------------|-----------|
| **System Metrics** | Prometheus (port 9090) | HTTP API | CPU, memory, request rates, latency percentiles |
| **Application Logs** | Loki (port 3100) | HTTP API | Error tracking, audit trails, access patterns |
| **Workflow State** | PostgreSQL | SQLAlchemy ORM | Execution counts, duration trends, success rates |
| **User Activity** | PostgreSQL | SQLAlchemy ORM + Matviews | DAU/MAU, feature adoption, engagement |
| **Cost Data** | LiteLLM DB | HTTP API / Direct SQL | Token usage, spend per model, budget tracking |
| **Security Events** | PostgreSQL + Loki | SQLAlchemy + Loki API | Login patterns, permission changes, anomalies |

### Materialized Views (Historical Aggregates)

Refreshed every 15 minutes via Celery job with `REFRESH CONCURRENTLY`:

```sql
-- Hourly user activity
CREATE MATERIALIZED VIEW analytics_hourly_user_activity AS
SELECT 
    date_trunc('hour', created_at) as hour_timestamp,
    COUNT(DISTINCT user_id) as active_users_count,
    COUNT(*) as session_count
FROM user_sessions
GROUP BY date_trunc('hour', created_at);

-- Daily workflow metrics
CREATE MATERIALIZED VIEW analytics_daily_workflows AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_runs,
    COUNT(*) FILTER (WHERE status = 'success') as success_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failure_count,
    AVG(duration_ms) as avg_duration_ms,
    SUM(cost) as total_cost
FROM workflow_runs
GROUP BY DATE(created_at);

-- Hourly tool usage
CREATE MATERIALIZED VIEW analytics_hourly_tool_usage AS
SELECT 
    date_trunc('hour', created_at) as hour_timestamp,
    tool_name,
    COUNT(*) as call_count,
    COUNT(*) FILTER (WHERE success = true) as success_count,
    AVG(latency_ms) as avg_latency_ms
FROM tool_calls
GROUP BY date_trunc('hour', created_at), tool_name;

-- Daily cost breakdown
CREATE MATERIALIZED VIEW analytics_daily_costs AS
SELECT 
    DATE(created_at) as date,
    model_name,
    SUM(input_tokens) as input_tokens,
    SUM(output_tokens) as output_tokens,
    SUM(cost) as total_cost
FROM llm_usage
GROUP BY DATE(created_at), model_name;

-- Daily security events
CREATE MATERIALIZED VIEW analytics_daily_security AS
SELECT 
    DATE(created_at) as date,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT user_id) as unique_users
FROM audit_log
WHERE event_type IN ('login', 'logout', 'permission_change', 'failed_auth')
GROUP BY DATE(created_at), event_type;
```

### Grafana Integration

**Standalone Grafana (Port 3001):**
- Full dashboard suite with pre-configured panels
- Data sources: Prometheus, Loki, PostgreSQL
- Role-based access control (Viewer/Editor/Admin)
- Custom alerting rules and notifications
- Dashboard JSON export/import for version control

**Embedded Panels (Next.js):**
- Backend queries Grafana HTTP API for specific panel data
- Custom React components render charts using Tremor
- Same underlying data, different presentation
- JWT authentication passed through existing auth layer

---

## Page Structure & Features

### Navigation Structure

```
/admin/analytics (Analytics Hub - Landing Page)
├── /overview          # High-level summary cards + key metrics
├── /usage             # User engagement, DAU/MAU, feature adoption
├── /performance       # System performance, API latency, resources
├── /costs             # LLM spending, token usage, budgets
├── /agents            # Agent effectiveness, success rates
├── /security          # Audit trails, security events, access patterns
└── /grafana           # Link to standalone Grafana UI
```

### Page 1: Overview (`/admin/analytics/overview`)

**Purpose:** At-a-glance analytics summary

**Components:**
- **Time Range Selector** (Last 24h, 7d, 30d, 90d, Custom)
- **Key Metric Cards** (4-6 cards):
  - Active Users (today vs yesterday)
  - Total Workflow Runs
  - Success Rate %
  - Current System Health
  - Today's Cost
  - API Request Volume
- **Trend Sparklines** (mini charts showing 7-day trend)
- **Recent Alerts** (critical events requiring attention)

### Page 2: Usage Analytics (`/admin/analytics/usage`)

**Purpose:** User engagement and adoption metrics

**Components:**
- **User Activity Chart** (line chart: daily active users over time)
- **Feature Adoption** (bar chart: most used skills/workflows)
- **Session Duration** (histogram: session length distribution)
- **Retention Metrics** (cohort analysis table)
- **Top Users** (table: most active users with activity counts)

### Page 3: Performance (`/admin/analytics/performance`)

**Purpose:** System health and performance monitoring

**Components:**
- **API Latency Percentiles** (line chart: p50, p95, p99 over time)
- **Error Rate Trend** (line chart: error percentage over time)
- **Resource Utilization** (gauges: CPU, Memory, Disk usage)
- **Slowest Endpoints** (table: latency rankings with percentiles)
- **Request Volume** (area chart: requests per minute)

### Page 4: Costs (`/admin/analytics/costs`)

**Purpose:** Financial visibility and budget management

**Components:**
- **Cost Trend** (line chart: daily spend over time)
- **Cost by Model** (donut chart: spending breakdown by LLM model)
- **Cost by User** (table: sortable user spend rankings)
- **Budget Status** (progress bars with 80%/90%/100% thresholds)
- **Token Usage** (stacked area: input vs output tokens)
- **Cost Forecast** (projection based on current usage)

### Page 5: Agent Effectiveness (`/admin/analytics/agents`)

**Purpose:** Agent quality and performance metrics

**Components:**
- **Success Rate by Agent** (bar chart: completion rates)
- **Completion Time Trends** (line chart: average duration)
- **Error Breakdown** (table: errors by type and frequency)
- **Agent Utilization** (heatmap: activity by hour/day)
- **Tool Usage by Agent** (stacked bar: which tools each agent uses)

### Page 6: Security (`/admin/analytics/security`)

**Purpose:** Security auditing and compliance

**Components:**
- **Login Activity** (timeline: successful/failed logins)
- **Failed Authentication** (count + trend line)
- **Permission Changes** (audit log table with filtering)
- **Anomaly Detection** (flagged suspicious activity)
- **Access Patterns** (heatmap: activity by time of day)

### Design System Consistency

| Element | Topic #14 Pattern | Topic #8 Implementation |
|---------|-------------------|-------------------------|
| **Layout** | Dashboard shell with sidebar | Reuse same shell, add Analytics section |
| **Cards** | Metric cards on overview | Same component, analytics data |
| **Tables** | Execution list with filtering | Same table component, analytics data |
| **Charts** | Not used in #14 | New: Tremor React components |
| **Time Filters** | Live/pause toggle | Date range picker (24h/7d/30d/90d) |
| **Colors** | Status indicators | Same pattern for thresholds |
| **Loading States** | Skeleton loaders | Same pattern |

---

## Implementation Phases

### Phase 1: Foundation & Data Layer (Week 1)

**Backend:**
- Create analytics materialized views in PostgreSQL
- Set up Celery job for view refresh (15-minute interval, `CONCURRENTLY`)
- Create `AnalyticsService` class for data aggregation
- Implement Prometheus/Loki HTTP API clients
- Set up Grafana HTTP API client with authentication

**Infrastructure:**
- Verify Grafana data sources configuration
- Create initial Grafana dashboards (export as JSON)
- Set up materialized view refresh monitoring

**Deliverables:**
- Materialized views created and refreshing
- Analytics API endpoints returning test data
- Grafana accessible with basic dashboards

---

### Phase 2: Backend API & Overview Page (Week 2)

**Backend:**
- Implement `/api/analytics/overview` endpoint
- Implement time-range filtering parameters
- Add Redis caching layer (30s TTL for real-time data)
- Add RBAC enforcement (admin-only access)

**Frontend:**
- Create Analytics layout shell (sidebar navigation)
- Build Overview page with metric cards
- Implement time range selector component
- Add Tremor React chart components

**Deliverables:**
- Overview page functional at `/admin/analytics/overview`
- Key metrics visible with real data
- Time filtering works

---

### Phase 3: Usage & Performance Pages (Week 3)

**Backend:**
- `/api/analytics/usage` - user activity metrics
- `/api/analytics/performance` - system performance data
- Implement drill-down endpoints (user detail, endpoint detail)

**Frontend:**
- Usage page with DAU/MAU charts
- Feature adoption visualizations
- Performance page with latency percentiles
- Resource utilization gauges

**Deliverables:**
- Usage analytics page complete
- Performance monitoring page complete
- Both pages populated with real data

---

### Phase 4: Costs & Agent Analytics (Week 4)

**Backend:**
- `/api/analytics/costs` - cost aggregation from LiteLLM
- `/api/analytics/agents` - agent effectiveness metrics
- Budget alert integration

**Frontend:**
- Cost trends and breakdowns
- Model comparison charts
- Agent success rate visualizations
- Budget status indicators with thresholds

**Deliverables:**
- Cost analytics page complete
- Agent effectiveness page complete
- Budget tracking functional

---

### Phase 5: Security & Grafana Integration (Week 5)

**Backend:**
- `/api/analytics/security` - audit log aggregation
- Basic anomaly detection rules
- Grafana API endpoints for embedded panels

**Frontend:**
- Security events page
- Audit trail viewer with filtering
- Link to standalone Grafana UI
- Grafana embedded panel component

**Deliverables:**
- Security analytics page complete
- Grafana integration working
- Standalone Grafana linked from UI

---

### Phase 6: Polish & Testing (Week 6)

**Tasks:**
- End-to-end testing of all analytics flows
- Performance optimization (query tuning, caching)
- Mobile responsiveness testing
- Export functionality (CSV/PDF)
- Documentation (user guide, admin guide)
- Grafana dashboard fine-tuning

**Deliverables:**
- Production-ready analytics suite
- User and admin documentation
- Performance benchmarks met

---

## Success Criteria

### Functional Requirements

- [ ] All 6 analytics pages accessible at `/admin/analytics/*`
- [ ] Overview page loads in < 3 seconds
- [ ] Materialized views refresh every 15 minutes automatically
- [ ] Time range filtering works (24h, 7d, 30d, 90d, custom)
- [ ] Grafana accessible at port 3001 with pre-configured dashboards
- [ ] Embedded panels display correctly in Next.js UI
- [ ] All data respects RBAC (users see only their permitted data)
- [ ] Export to CSV works for all tables

### Performance Requirements

- [ ] API responses < 2 seconds for historical data
- [ ] Real-time queries < 500ms
- [ ] Dashboard supports 100 concurrent users
- [ ] Materialized view refresh doesn't impact production performance
- [ ] Mobile responsive (usable on tablet)

### Data Requirements

- [ ] 6 categories covered: Usage, Performance, Costs, Agents, Security, Overview
- [ ] Historical data available for 90 days minimum
- [ ] Real-time data accurate within 1 minute
- [ ] Cost calculations match LiteLLM data (within 1% tolerance)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Materialized view refresh locks tables** | Medium | High | Use `CONCURRENTLY` refresh; schedule during low-traffic hours |
| **Prometheus retention too short** | Low | Medium | Verify 15-day retention minimum; document data retention limits |
| **Grafana licensing (enterprise features)** | Low | Low | Use Grafana OSS (free); all features available in open source |
| **Query performance on large datasets** | Medium | Medium | Add indexes; implement pagination; cache aggressively |
| **Topic #14 dependency** | Medium | High | Can develop in parallel; uses same observability foundation |
| **Data accuracy issues** | Medium | High | Implement validation checks; compare with source systems |
| **User confusion (two UIs)** | Medium | Low | Clear navigation labels; documentation explaining when to use each |

---

## Consistency with Topic #14

### Pattern Reuse

| Topic #14 Feature | Topic #8 Equivalent |
|-------------------|---------------------|
| Overview page with metric cards | Overview page with analytics cards |
| Activity feed | Audit trail with filtering |
| Flow execution list | Workflow success rate analytics |
| Agent list with status | Agent effectiveness metrics |
| Real-time WebSocket | Near-real-time (acceptable for analytics) |
| Time range filters | Same pattern, different ranges |
| Backend aggregation | Same pattern, different data sources |

### Key Integration Points

1. **Shared Observability Infrastructure** - Both use Prometheus, Loki, Grafana from Phase 8
2. **Consistent API Pattern** - Backend aggregation layer in FastAPI
3. **Same Design System** - shadcn/ui components, Tremor for charts
4. **Unified Navigation** - Analytics section added to existing admin shell
5. **RBAC Consistency** - Same JWT + permission checks

### Data Flow Consistency

```
Topic #14 (Dashboard)          Topic #8 (Analytics)
         │                              │
         ▼                              ▼
┌─────────────────┐            ┌─────────────────┐
│ Real-time data  │            │ Historical data │
│ (WebSocket)     │            │ (API queries)   │
└─────────────────┘            └─────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        ▼
              ┌─────────────────┐
              │  PostgreSQL     │
              │  Prometheus     │
              │  Loki           │
              └─────────────────┘
```

---

## Related Documents

- [Topic #14: Dashboard & Mission Control](../agentos-dashboard-mission-control/00-specification.md) - Complementary real-time dashboard
- [Phase 8 Observability Design](../../plans/2026-03-01-phase8-observability-design.md) - Foundation infrastructure
- [Brainstorming Tracking](../BRAINSTORMING-TRACKING.md) - Project context and status

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
