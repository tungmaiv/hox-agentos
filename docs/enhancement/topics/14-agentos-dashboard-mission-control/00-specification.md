# AgentOS Dashboard & Mission Control

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4  
**Estimated Effort:** 1.5 Phases (6 weeks)  
**Last Updated:** 2026-03-15

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Reference Analysis](#reference-analysis)
4. [Architecture](#architecture)
5. [Page Structure & Features](#page-structure--features)
6. [Data Flow & Integration](#data-flow--integration)
7. [Implementation Phases](#implementation-phases)
8. [Success Criteria](#success-criteria)
9. [Risks and Mitigations](#risks-and-mitigations)
10. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This enhancement introduces a comprehensive **AgentOS Dashboard & Mission Control** — a unified operational interface that provides real-time visibility into agent activities, workflow executions, system health, and memory management. Drawing inspiration from OpenClaw Dashboard implementations (mudrii, tugcantopaloglu, tenacitOS), this design creates an integrated experience within the existing AgentOS Next.js frontend.

### Key Innovation: Unified Operational Interface

Unlike standalone monitoring tools, this dashboard seamlessly integrates with AgentOS's existing chat, workflow canvas, and admin interfaces. It leverages the existing Phase 8 observability infrastructure (Prometheus, Grafana, Loki) while providing a user-friendly, real-time operational view.

**Target Users:** Both IT administrators (operations monitoring) and end users (agent visibility)

**Core Capabilities:**
- Real-time activity feed of agent actions and workflow executions
- Flow execution monitor with step-by-step drill-down
- Agent management with optional 3D office visualization
- Memory browser with full-text and semantic search
- Deep integration with existing observability stack

---

## Problem Statement

### Current State (As-Is)

| Aspect | Current Reality | Pain Point |
|--------|----------------|------------|
| **Agent Visibility** | Check individual agent logs | No unified view of all agent activities |
| **Workflow Monitoring** | Query database or check logs | No visual execution tracking |
| **System Health** | Grafana dashboards (Phase 8) | Technical, not user-friendly |
| **Memory Exploration** | SQL queries or raw files | No searchable interface |
| **Real-time Updates** | Manual refresh | No live activity stream |
| **Error Investigation** | Dig through logs | No execution step visualization |

### Target State (To-Be)

| Aspect | Target Experience | Benefit |
|--------|------------------|---------|
| **Agent Visibility** | Activity feed + agent status | Complete operational picture |
| **Workflow Monitoring** | Visual execution timeline | Instant failure diagnosis |
| **System Health** | User-friendly dashboard | Accessible to non-technical users |
| **Memory Exploration** | Searchable browser | Quick information retrieval |
| **Real-time Updates** | Live WebSocket stream | Immediate awareness |
| **Error Investigation** | Step-by-step drill-down | Faster troubleshooting |

---

## Reference Analysis

### Repository 1: mudrii/openclaw-dashboard

**Approach:** Zero-dependency, single-file dashboard (Go/Python)

**Key Features Analyzed:**
- 12 dashboard panels covering metrics, costs, cron jobs, sessions, sub-agents
- AI Chat for natural language queries about system state
- 6 built-in themes with glass morphism UI
- Real-time auto-refresh with countdown timer
- Gateway runtime observability via healthz/readyz probes
- Cost tracking with per-model breakdown
- Agent hierarchy tree visualization
- System metrics (CPU, RAM, disk) with configurable thresholds

**Relevance to AgentOS:**
- Activity feed concept applicable to AgentOS
- Cost tracking already covered by Phase 8 Grafana
- Agent hierarchy useful for multi-agent workflows
- Real-time refresh pattern suitable for AgentOS

### Repository 2: tugcantopaloglu/openclaw-dashboard

**Approach:** Secure Node.js dashboard with authentication

**Key Features Analyzed:**
- Username/Password + TOTP MFA authentication
- Activity heatmap and streak tracking
- Memory file browser (MEMORY.md, HEARTBEAT.md)
- File manager with security hardening
- Live feed of agent messages via Server-Sent Events
- Security dashboard (UFW, fail2ban, SSH logs)
- Docker management UI
- Notification center with audit log
- Config editor with JSON validation
- Keyboard shortcuts for navigation
- Browser notifications for alerts

**Relevance to AgentOS:**
- Memory browser pattern directly applicable
- Live feed concept for real-time updates
- Security dashboard ideas for admin features
- Notification center pattern for alerts

### Repository 3: carlosazaustre/tenacitOS (Mission Control)

**Approach:** Next.js 15 + React 19 modern stack

**Key Features Analyzed:**
- 3D Office visualization with React Three Fiber (one desk per agent)
- Visual cron manager with weekly timeline
- Activity feed with heatmaps
- Global search across memory and workspace files
- Real-time notification center
- Terminal for safe status commands
- Cost tracking from SQLite
- System monitor (CPU, RAM, Disk, Network)
- Agent dashboard with session tracking

**Relevance to AgentOS:**
- 3D office visualization as optional feature
- Visual cron manager pattern for scheduler UI
- Activity feed with heatmaps
- Global search architecture

### Synthesis: What AgentOS Needs

From the references, the highest-value features for AgentOS are:

1. **Activity Feed** — Real-time visibility into agent actions (all three)
2. **Flow Execution Monitor** — Step-by-step workflow tracking (all three)
3. **Memory Browser** — Searchable memory exploration (tugcan, tenacitOS)
4. **3D Office** — Visual agent presence (tenacitOS — optional)
5. **System Health** — Already covered by Phase 8 Grafana (complement, not replace)

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AgentOS Frontend (Next.js)                         │
│                                                                              │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │   /chat     │  │ /workflows   │  │  /admin/*   │  │ /dashboard/*    │   │
│   │   (existing)│  │  (existing)  │  │  (existing) │  │   (NEW)         │   │
│   └─────────────┘  └──────────────┘  └─────────────┘  └────────┬────────┘   │
│                                                                 │            │
│   ┌─────────────────────────────────────────────────────────────┘            │
│   │  Dashboard Pages:                                                         │
│   │  • /dashboard/overview    — System health + Activity feed                │
│   │  • /dashboard/flows       — Workflow execution monitor                   │
│   │  • /dashboard/agents      — Agent management + 3D office (optional)      │
│   │  • /dashboard/memory      — Memory browser/search                        │
│   └──────────────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend API (FastAPI)                              │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐ │
│   │  Dashboard API Router (/api/dashboard/*)                               │ │
│   │  • GET /overview      — Aggregated metrics                             │ │
│   │  • GET /activity      — Activity feed (SSE)                            │ │
│   │  • GET /flows         — Workflow executions                            │ │
│   │  • GET /flows/{id}    — Execution details                              │ │
│   │  • GET /memory/search — Memory search                                  │ │
│   │  • WS /stream         — Real-time updates                              │ │
│   └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│   │   Metrics    │  │    State     │  │    Logs      │  │   Scheduler     │ │
│   │   Service    │  │   Service    │  │   Service    │  │   Service       │ │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
│          │                 │                 │                   │          │
└──────────┼─────────────────┼─────────────────┼───────────────────┼──────────┘
           │                 │                 │                   │
           ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Sources                                     │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Prometheus  │  │  PostgreSQL  │  │    Loki      │  │  Celery/Redis   │  │
│  │  (metrics)   │  │   (state)    │  │   (logs)     │  │  (scheduler)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐                                          │
│  │   LiteLLM    │  │  pgvector    │                                          │
│  │   (costs)    │  │  (memory)    │                                          │
│  └──────────────┘  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Integration Pattern** | Integrated into existing Next.js app | Shared auth, navigation, components; consistent UX |
| **API Layer** | Backend aggregation | Single source of truth, RBAC control, caching opportunity |
| **Real-time Updates** | WebSocket + SSE | WebSocket for push notifications, SSE for streams |
| **3D Visualization** | Optional lazy-load | Keeps initial bundle small; feature can be disabled |
| **Data Sources** | Multiple (Prometheus, PG, Loki) | Leverages existing Phase 8 infrastructure |
| **Authentication** | Existing JWT + RBAC | Reuses current security gates |

### Integration with Phase 8 Observability

The dashboard complements (not replaces) the existing Grafana dashboards:

- **Grafana (Port 3001):** Technical metrics, infrastructure monitoring, alerting
- **AgentOS Dashboard:** User-friendly operational view, agent activities, workflow tracking

Data flow from Phase 8:
- Prometheus metrics → Dashboard API → Frontend metric cards
- Loki logs → Dashboard API → Activity feed
- Both sources remain available in Grafana for deep-dive analysis

---

## Page Structure & Features

### Navigation Structure

```
/dashboard
├── /overview              # System health + Activity feed (landing page)
├── /flows                 # Workflow execution monitor
├── /agents                # Agent management + 3D office (optional)
└── /memory                # Memory browser/search
```

### Page 1: Overview (`/dashboard/overview`)

**Purpose:** At-a-glance system health and recent activity

**Layout Components:**
- **Alert Banner:** Critical issues requiring attention (failed workflows, high resource usage)
- **Metric Cards:** Key numbers (active flows, active agents, today's cost, system health)
- **Activity Feed:** Real-time stream of agent/workflow actions with timestamps
- **Controls:** Live/pause toggle, time range filter

**Activity Event Types:**
- Workflow started/completed/failed
- Agent invoked tool
- Tool call success/failure
- System alerts (high memory, service down)

### Page 2: Flow Execution Monitor (`/dashboard/flows`)

**Purpose:** Monitor workflow runs and drill into execution details

**Layout Components:**
- **Workflow Selector:** Dropdown to filter by workflow
- **Execution Table:** List of runs with columns (Run ID, Started, Duration, Status, Cost, Actions)
- **Status Filtering:** Tabs for All/Success/Failed/Running
- **Detail Panel:** Step-by-step execution breakdown

**Execution Detail View:**
- Visual timeline of steps (1 → 2 → 3 → ...)
- Step status indicators (success/warning/error)
- Duration per step
- Error details with context
- Action buttons: Retry, View Logs, Debug

**Features:**
- Retry failed workflows from specific step
- View execution logs inline
- Export execution history

### Page 3: Agents (`/dashboard/agents`)

**Purpose:** Agent management and optional 3D visualization

**Layout Components:**
- **View Toggle:** List View / 3D Office
- **Agent List:** Table with columns (Agent, Status, Last Active, Workflows, Cost)
- **Agent Detail Panel:** Configuration, recent activity, metrics

**List View Features:**
- Sortable columns
- Status indicators (Live/Idle/Offline)
- Quick actions (Start/Stop/Configure)
- Activity sparkline

**3D Office View (Optional):**
- React Three Fiber canvas
- One "desk" per agent
- Visual presence indicators (green = active, yellow = idle, gray = offline)
- Click to open agent details
- Lazy-loaded to minimize bundle size

### Page 4: Memory Browser (`/dashboard/memory`)

**Purpose:** Explore and search agent memory

**Layout Components:**
- **Search Bar:** Full-text search with filters
- **Memory Tree:** Hierarchical navigation (User Facts, Preferences, History, Workflows)
- **Content Viewer:** Rich text display of memory content
- **Similar Memories:** Semantic similarity suggestions

**Search Capabilities:**
- Full-text search across all memory
- Filter by agent, memory type, date range
- Semantic search using pgvector embeddings
- Results ranked by relevance

**Memory Management:**
- View memory content
- Edit memory (with audit logging)
- Delete memory
- View memory source/context

---

## Data Flow & Integration

### Data Sources

| Data Type | Source | Access Method | Use Case |
|-----------|--------|---------------|----------|
| **System Metrics** | Prometheus | HTTP API (port 9090) | CPU, memory, request rates |
| **Logs** | Loki | HTTP API (port 3100) | Activity feed, error details |
| **Workflow State** | PostgreSQL | SQLAlchemy ORM | Execution history, step status |
| **Memory** | PostgreSQL (pgvector) | SQLAlchemy ORM | Memory search, retrieval |
| **Costs** | LiteLLM | HTTP API / DB | Token usage, spend |
| **Scheduler** | Redis + Celery | Celery Inspect API | Job status, queue depth |
| **Real-time Events** | WebSocket | Custom protocol | Live updates |

### Real-Time Event Architecture

```
Event Sources (Workflow Engine, Agent Runtime, System Monitor)
                    │
                    ▼
            Redis Pub/Sub
         (Channel: events:user:{id})
                    │
                    ▼
         Backend WebSocket Manager
                    │
                    ▼
            Frontend Dashboard
         (React Context + State)
```

**Event Types:**
- `workflow.started` — Workflow execution began
- `workflow.completed` — Workflow finished successfully
- `workflow.failed` — Workflow failed with error
- `agent.invoked` — Agent was triggered
- `tool.called` — Tool was invoked
- `alert.triggered` — System alert fired

### API Design Principles

1. **Aggregation:** Single API call returns data from multiple sources
2. **Caching:** Expensive queries cached with short TTL
3. **Pagination:** List endpoints support pagination
4. **Filtering:** Query parameters for status, date range, etc.
5. **Permissions:** All endpoints enforce RBAC (user sees only their data)

---

## Implementation Phases

### Phase 1: Foundation & API Layer (Week 1)

**Goal:** Establish backend API structure and data aggregation layer

**Scope:**
- Create dashboard API router structure
- Implement data aggregation service for Prometheus/Loki/PostgreSQL
- Create database models for dashboard-specific data
- Build basic API endpoints (overview, activity feed)
- Set up WebSocket infrastructure for real-time updates
- Implement event bus (Redis Pub/Sub) for real-time events
- Add authentication/authorization to dashboard routes

**Deliverables:**
- Backend API routes functional
- Data aggregation layer working
- WebSocket endpoint accepting connections
- Basic overview endpoint returning aggregated data

**Dependencies:** Phase 8 observability (Prometheus/Loki) must be in place

---

### Phase 2: Overview Page & Activity Feed (Week 2)

**Goal:** Build the dashboard landing page with activity feed

**Scope:**
- Create dashboard layout shell (navigation, header)
- Build overview page components (metric cards, alert banner)
- Implement activity feed component
- Create WebSocket client connection in frontend
- Build activity event types and display formats
- Add time range filtering
- Implement live/pause toggle for real-time updates

**Deliverables:**
- Overview page accessible at `/dashboard/overview`
- Activity feed showing real-time events
- Metric cards displaying system stats
- Alert banner for critical issues

**Dependencies:** Phase 1 API endpoints

---

### Phase 3: Flow Execution Monitor (Week 3)

**Goal:** Build workflow execution monitoring with drill-down

**Scope:**
- Create workflow execution list view
- Build execution detail panel with step visualization
- Implement status filtering (success/failed/running)
- Create step-by-step execution timeline
- Add error details display
- Build retry functionality UI
- Implement execution logs viewer

**Deliverables:**
- Flows page at `/dashboard/flows`
- Workflow execution list with filtering
- Execution detail view with steps
- Error visualization and retry actions

**Dependencies:** Workflow execution data in PostgreSQL

---

### Phase 4: Agents Page & 3D Office (Week 4)

**Goal:** Build agent management and optional 3D visualization

**Scope:**
- Create agent list view with status indicators
- Build agent detail panel
- Implement agent actions (start/stop/configure)
- Add agent activity history
- Create 3D office visualization (lazy-loaded)
- Build 3D agent presence indicators
- Add view toggle (list/3D)

**Deliverables:**
- Agents page at `/dashboard/agents`
- Agent list with management actions
- Optional 3D office visualization
- Agent activity tracking

**Dependencies:** Agent runtime data from backend

---

### Phase 5: Memory Browser (Week 5)

**Goal:** Build memory exploration and search interface

**Scope:**
- Create memory tree navigation component
- Build memory content viewer
- Implement full-text search interface
- Create semantic search integration
- Add memory editing capabilities
- Build similar memories suggestions
- Implement memory organization UI

**Deliverables:**
- Memory page at `/dashboard/memory`
- Tree browser for memory organization
- Search interface with results
- Memory content viewer/editor

**Dependencies:** pgvector for semantic search

---

### Phase 6: Integration & Polish (Week 6)

**Goal:** Integration testing, performance optimization, documentation

**Scope:**
- End-to-end testing of all dashboard features
- Performance optimization (query caching, lazy loading)
- Mobile responsiveness testing
- Add keyboard shortcuts
- Create user documentation
- Add dashboard onboarding/tour
- Final security review

**Deliverables:**
- Fully functional dashboard
- Performance benchmarks met
- User documentation
- Production-ready code

**Dependencies:** All previous phases complete

---

## Success Criteria

### Functional Requirements

- [ ] Dashboard accessible at `/dashboard/*` routes
- [ ] Overview page shows system health and activity feed
- [ ] Activity feed updates in real-time via WebSocket
- [ ] Flow execution monitor lists all workflow runs
- [ ] Execution drill-down shows step-by-step progress
- [ ] Error details visible with retry option
- [ ] Agents page lists all agents with status
- [ ] Optional 3D office visualization loads on demand
- [ ] Memory browser supports full-text search
- [ ] Semantic search works with pgvector
- [ ] All features respect RBAC (users see only their data)

### Performance Requirements

- [ ] Dashboard loads in <3 seconds
- [ ] Activity feed updates within 1 second of events
- [ ] Search returns results in <2 seconds
- [ ] 3D visualization loads asynchronously (no blocking)
- [ ] Supports 100 concurrent users (AgentOS scale)
- [ ] Mobile responsive (usable on tablet/phone)

### Security Requirements

- [ ] All endpoints require authentication
- [ ] RBAC enforced (admin vs user views)
- [ ] WebSocket connections validated
- [ ] No sensitive data exposed in frontend
- [ ] Audit logging for dashboard actions
- [ ] Rate limiting on search endpoints

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Phase 8 not ready** | Low | High | Dashboard has graceful degradation; shows "observability not configured" message |
| **WebSocket scaling** | Medium | Medium | For ~100 users, single WebSocket server sufficient; can add Redis adapter later |
| **3D visualization bundle size** | Medium | Low | Lazy-load Three.js; only load when 3D view selected |
| **Complex data aggregation** | Medium | Medium | Implement caching layer; cache expensive queries for 30s |
| **User confusion (Grafana vs Dashboard)** | Medium | Low | Clear documentation; Grafana for ops, Dashboard for daily use |
| **Memory search performance** | Medium | Medium | Use pgvector indexes; paginate results; add search filters |

---

## Future Enhancements

### Post-v1.4 (Topic #15: Scheduler Management)

**Scope:** Visual cron/scheduler management UI

**Features:**
- Visual cron timeline (weekly view)
- Enable/disable scheduled jobs
- Manual trigger ("run now")
- Job execution history
- Edit job schedules
- Schedule workflow canvas visually

**Effort:** 0.5-1 Phase

### v1.5 Enhancements

1. **Advanced Analytics**
   - Cost prediction based on usage patterns
   - Agent performance analytics
   - Workflow optimization suggestions

2. **Collaborative Features**
   - Share dashboard views
   - Team activity feed
   - Annotated memory sharing

3. **Mobile App**
   - React Native companion app
   - Push notifications
   - Quick actions

4. **Custom Dashboards**
   - User-configurable widgets
   - Save custom layouts
   - Export dashboard as PDF

---

## Related Documents

- [Phase 8 Observability Design](../plans/2026-03-01-phase8-observability-design.md)
- [Admin Console LLM Config](admin-console-llm-config/00-specification.md)
- [User Experience Enhancement](BRAINSTORMING-TRACKING.md#13-user-experience-enhancement)

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
