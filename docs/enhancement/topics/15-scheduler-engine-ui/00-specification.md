# Scheduler Engine & UI

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4  
**Estimated Effort:** 1 Phase (5 weeks)  
**Last Updated:** 2026-03-16

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Existing Infrastructure](#existing-infrastructure)
4. [Architecture](#architecture)
5. [Page Structure & Features](#page-structure--features)
6. [Database Schema](#database-schema)
7. [Implementation Phases](#implementation-phases)
8. [Success Criteria](#success-criteria)
9. [Risks and Mitigations](#risks-and-mitigations)
10. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This enhancement introduces a comprehensive **Scheduler Engine & UI** for AgentOS, transforming the existing Celery-based background task system into a fully manageable, visible, and interactive scheduling platform. While AgentOS already has Celery workers and cron triggers for workflows, there is currently no user interface to visualize, manage, or monitor scheduled jobs.

### Key Innovation: Unified Scheduling Management

The design provides **two complementary interfaces**:
1. **Global Scheduler View** — Operations dashboard for administrators to monitor all scheduled jobs, queue health, and system-wide execution history
2. **Per-Workflow Schedule Tab** — Integrated workflow scheduling for users to configure when and how their workflows run

**Core Capabilities:**
- Visual job management (enable/disable, run now, delete)
- Full execution history with drill-down details
- Interactive cron builder with timezone support and holiday exclusion
- Real-time queue monitoring (Celery queue depth, worker status)
- Multi-channel alerting (in-app, Telegram, email) for job failures
- Step-by-step execution visibility (integrates with Flow Execution Monitor)

---

## Problem Statement

### Current State (As-Is)

AgentOS has a working scheduler infrastructure but lacks visibility and management capabilities:

| Aspect | Current Reality | Pain Point |
|--------|----------------|------------|
| **Job Visibility** | Query database or check logs | No unified view of scheduled jobs |
| **Job Control** | API calls or database updates | No UI to enable/disable jobs |
| **Cron Creation** | Raw cron expression in API | Error-prone, no validation or preview |
| **Execution History** | `WorkflowRun` table exists | No UI to view or filter runs |
| **Failure Handling** | Check logs manually | No alerts when jobs fail |
| **Queue Monitoring** | Check Celery via CLI | No visibility into queue health |
| **Manual Trigger** | No capability | Cannot run scheduled job on demand |

### Target State (To-Be)

| Aspect | Target Experience | Benefit |
|--------|------------------|---------|
| **Job Visibility** | Global scheduler dashboard | Complete operational picture |
| **Job Control** | One-click enable/disable/run | Instant control |
| **Cron Creation** | Visual builder with preview | Intuitive, error-proof |
| **Execution History** | Filterable history with details | Easy troubleshooting |
| **Failure Handling** | Automatic alerts via preferred channel | Immediate awareness |
| **Queue Monitoring** | Real-time queue status | Proactive capacity management |
| **Manual Trigger** | "Run Now" button on any job | Flexibility for ad-hoc execution |

---

## Existing Infrastructure

### Current Scheduler Implementation

AgentOS already has a solid Celery-based foundation:

**Celery Application (`backend/scheduler/celery_app.py`):**
- Redis broker and backend
- Two queues: `embedding` (CPU-bound) and `default` (I/O-bound)
- Beat schedule running every 60 seconds
- Tasks: embedding, workflow execution, cron triggers, skill updates

**Database Models (`backend/core/models/workflow.py`):**
- `WorkflowTrigger` — Stores cron and webhook triggers
- `WorkflowRun` — Records execution history
- Fields: `trigger_type`, `cron_expression`, `is_active`, `webhook_secret`

**API Endpoints (`backend/api/routes/workflows.py`):**
- `GET /api/workflows/{id}/triggers` — List triggers
- `POST /api/workflows/{id}/triggers` — Create trigger
- `DELETE /api/workflows/{id}/triggers/{trigger_id}` — Delete trigger

**Cron Trigger Task (`backend/scheduler/tasks/cron_trigger.py`):**
- Runs every 60 seconds via Celery Beat
- Checks all active cron triggers
- Creates `WorkflowRun` and enqueues execution
- Security: Jobs run as trigger owner (not service account)

### What's Missing

While the backend infrastructure is solid, the following are completely absent:

1. **No Scheduler Management API** — No endpoints for job control, history, or queue status
2. **No Scheduler UI** — No frontend interface for any scheduling operations
3. **No Visual Cron Builder** — Users must write raw cron expressions
4. **No Execution Visibility** — No UI to view `WorkflowRun` records
5. **No Queue Monitoring** — No visibility into Celery queue depth or worker status
6. **No Alerting** — No notifications for failed jobs
7. **No Manual Trigger** — Cannot run scheduled jobs on demand

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AgentOS Frontend (Next.js)                           │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │   /scheduler     │  │ /workflows/{id}  │  │   Cron Builder Modal     │   │
│  │   (Global View)  │  │   /schedule      │  │   (Interactive)          │   │
│  │                  │  │   (Per-Workflow) │  │                          │   │
│  │  • Job List      │  │                  │  │  • Visual time picker    │   │
│  │  • Queue Status  │  │  • Triggers      │  │  • Timezone selector     │   │
│  │  • History       │  │  • Schedule Tab  │  │  • Holiday exclusion     │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Backend API (FastAPI)                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  Scheduler Router (/api/scheduler/*)                                   │ │
│  │  • GET    /jobs                — List scheduled jobs                   │ │
│  │  • POST   /jobs/{id}/toggle    — Enable/disable job                    │ │
│  │  • POST   /jobs/{id}/run-now   — Manual trigger                        │ │
│  │  • GET    /jobs/{id}/history   — Execution history                     │ │
│  │  • POST   /jobs/{id}/retry     — Retry failed job                      │ │
│  │  • DELETE /jobs/{id}           — Delete trigger                        │ │
│  │  • GET    /queue/status        — Queue depth, worker status            │ │
│  │  • POST   /cron/validate       — Validate cron expression              │ │
│  │  • POST   /cron/preview        — Preview next N runs                   │ │
│  │  • GET    /notifications/settings — Alert preferences                  │ │
│  │  • PUT    /notifications/settings — Update alert preferences           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Celery Infrastructure (Existing)                        │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐  │
│  │ Celery Beat  │───▶│  Redis       │◀───│  Celery Worker               │  │
│  │ (scheduler)  │    │  (broker)    │    │  (executor)                  │  │
│  │              │    │              │    │                              │  │
│  │ Checks every│    │              │    │  • workflow_execution        │  │
│  │ 60 seconds  │    │              │    │  • embedding                 │  │
│  │ for due jobs│    │              │    │  • check_skill_updates       │  │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Sources                                     │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  PostgreSQL      │  │  Redis           │  │  Notification Service    │   │
│  │                  │  │                  │  │                          │   │
│  │ • workflow_triggers│  │ • Celery queues  │  │ • In-app notifications   │   │
│  │ • workflow_runs  │  │ • Task metadata  │  │ • Channel notifications  │   │
│  │ • scheduler_notifications│            │  │   (Telegram/email)       │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Scheduler Core** | Extend existing Celery Beat | Already running, proven, low risk |
| **API Layer** | New FastAPI router | Clean separation, RBAC control |
| **Frontend** | Integrated in Next.js | Shared auth, components, navigation |
| **UI Locations** | Global + Per-workflow | Ops view + user view |
| **Cron Builder** | Full interactive | Visual time picker, timezone, preview |
| **Execution Visibility** | Full details | Step-by-step execution, logs, errors |
| **Alerting** | Multi-channel | Dashboard + in-app + channel notifications |

### Key Principles

1. **Leverage Existing Infrastructure** — Build on top of Celery, don't replace it
2. **Backward Compatible** — Existing cron triggers continue to work unchanged
3. **Security First** — All endpoints enforce RBAC; users see only their jobs
4. **Admin vs User Views** — Different permissions and capabilities
5. **Real-time Where Needed** — Queue status updates automatically
6. **Graceful Degradation** — Works even if Celery is temporarily unavailable

---

## Page Structure & Features

### Route Structure

```
/scheduler                      # Global scheduler view (admin/ops)
├── /jobs                       # All scheduled jobs list
├── /history                    # Execution history
└── /queue                      # Queue monitoring

/workflows/{id}
├── /canvas                     # Existing workflow canvas
├── /runs                       # Existing execution runs
└── /schedule                   # NEW: Schedule management tab
    ├── /triggers               # List/edit triggers
    └── /cron-builder           # Interactive cron builder
```

### Page 1: Global Scheduler (`/scheduler`)

**Purpose:** Operations view of all scheduled jobs across the system

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Scheduler Management                                [+ New Schedule]│
├─────────────────────────────────────────────────────────────────────┤
│  [Jobs] [History] [Queue]                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Filters: Workflow: [All ▼] Status: [All ▼] Owner: [All ▼] [🔍]    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Job Name        │ Workflow    │ Schedule    │ Status │ Actions│  │
│  │──────────────────────────────────────────────────────────────│  │
│  │ Daily Report    │ wf_daily    │ 0 8 * * 1-5 │ 🟢 On  │ ▶️ ⏸️ 🗑️│  │
│  │ Weekly Sync     │ wf_weekly   │ 0 9 * * 1   │ 🟢 On  │ ▶️ ⏸️ 🗑️│  │
│  │ Backup Job      │ wf_backup   │ 0 2 * * *   │ 🔴 Off │ ▶️ ⏸️ 🗑️│  │
│  │ Data Cleanup    │ wf_cleanup  │ 0 0 1 * *   │ 🟢 On  │ ▶️ ⏸️ 🗑️│  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Queue Status: 3 pending │ 2 running │ 0 failed │ Workers: 4/4     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- List all scheduled jobs with filtering (workflow, status, owner)
- Toggle enable/disable individual jobs
- Manual "Run Now" for immediate execution
- Delete trigger with confirmation
- Quick view of queue status
- Pagination for large job lists

**Permissions:**
- Admin: See all jobs across all users
- User: See only their own jobs

---

### Page 2: Execution History (`/scheduler/history`)

**Purpose:** View all job executions with filtering and drill-down

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Execution History                                    [Filter ▼]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Run ID      │ Job           │ Started │ Duration │ Status    │  │
│  │──────────────────────────────────────────────────────────────│  │
│  │ run_abc123  │ Daily Report  │ 08:00   │ 45s      │ ✅ Success │  │
│  │ run_def456  │ Weekly Sync   │ 09:00   │ 2m 15s   │ ✅ Success │  │
│  │ run_ghi789  │ Backup Job    │ 02:00   │ —        │ 🟡 Running │  │
│  │ run_jkl012  │ Data Cleanup  │ 00:00   │ 5m 30s   │ 🔴 Failed  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Details: run_jkl012                                                │
│  ─────────────────────────────────────────────────────────────────  │
│  Error: Database connection timeout after 5 minutes                 │
│  Step: 3/7 (Data archival)                                          │
│  [🔁 Retry] [📋 View Logs] [🐛 Debug]                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- List all executions with key info (ID, job name, start time, duration, status)
- Filter by date range, status (success/failed/running), workflow
- Drill-down to execution details
- Retry failed jobs with one click
- View full execution logs
- Link to Flow Execution Monitor for step-by-step view

---

### Page 3: Queue Monitoring (`/scheduler/queue`)

**Purpose:** Monitor Celery queue health and worker status

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Queue Monitoring                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ Pending      │ │ Running      │ │ Failed       │ │ Workers  │  │
│  │     3        │ │     2        │ │     0        │ │   4/4    │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Queue Breakdown:                                             │  │
│  │ • default: 2 pending, 1 running                              │  │
│  │ • embedding: 1 pending, 1 running                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Worker Status:                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Worker 1 │ Online │ Last Task: Daily Report │ 45s ago        │  │
│  │ Worker 2 │ Online │ Last Task: Weekly Sync  │ 2m ago         │  │
│  │ Worker 3 │ Online │ Idle                     │ —              │  │
│  │ Worker 4 │ Online │ Idle                     │ —              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  [🔄 Refresh]  Auto-refresh: [☑]                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Real-time queue depth by queue (default, embedding)
- Running tasks count
- Failed tasks count
- Worker status (online/offline/idle)
- Last activity per worker
- Auto-refresh toggle

---

### Page 4: Per-Workflow Schedule (`/workflows/{id}/schedule`)

**Purpose:** Manage schedules for a specific workflow

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Workflow: Daily Report                              [Save Changes] │
├─────────────────────────────────────────────────────────────────────┤
│  [Canvas] [Runs] [Settings] [Schedule] ← active                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Active Triggers:                                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 🕐 Cron: 0 8 * * 1-5 (Every weekday at 8:00 AM)             │  │
│  │    Status: 🟢 Active  [⏸️ Disable] [▶️ Run Now] [🗑️ Delete]  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 🔗 Webhook: https://api.agentos.io/webhooks/abc123          │  │
│  │    Status: 🟢 Active  [⏸️ Disable] [🗑️ Delete]              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  [+ Add Schedule]                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- List all triggers for this workflow
- Enable/disable individual triggers
- "Run Now" for immediate execution
- Delete triggers with confirmation
- Add new schedule (opens cron builder)
- View webhook URL for webhook triggers

---

### Page 5: Cron Builder (Modal/Full Page)

**Purpose:** Interactive visual cron builder with advanced options

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Schedule Builder                                     [Cancel] [Save]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Quick Presets:                                              │  │
│  │  [Hourly] [Daily] [Weekly] [Monthly] [Custom]                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Time Selection:                                             │  │
│  │  Hour: [08 ▼]  Minute: [00 ▼]  AM/PM [AM ▼]                 │  │
│  │                                                              │  │
│  │  Days of Week:                                               │  │
│  │  [☑ Mon] [☑ Tue] [☑ Wed] [☑ Thu] [☑ Fri] [☐ Sat] [☐ Sun]   │  │
│  │                                                              │  │
│  │  Timezone: [America/New_York ▼]                             │  │
│  │                                                              │  │
│  │  Options:                                                    │  │
│  │  [☐ Skip holidays] [☐ Skip weekends]                        │  │
│  │                                                              │  │
│  │  Description: [Daily morning report...]                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Preview: "Runs every weekday at 8:00 AM EST"                      │
│                                                                     │
│  Next 5 runs:                                                       │
│  • Today at 8:00 AM                                                │
│  • Tomorrow at 8:00 AM                                             │
│  • Wed at 8:00 AM                                                  │
│  • Thu at 8:00 AM                                                  │
│  • Fri at 8:00 AM                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Quick presets (Hourly, Daily, Weekly, Monthly, Custom)
- Visual time selection (hour, minute, AM/PM)
- Days of week toggles
- Timezone picker with search
- Holiday exclusion option
- Weekend exclusion option
- Optional description field
- Natural language preview
- Next N runs preview
- Real-time validation

**Advanced Tab (Optional Future):**
- Day of month selection
- Month selection
- Year selection
- Raw cron expression edit (for power users)

---

## Database Schema

### Schema Extensions

```sql
-- Extend existing workflow_triggers table with scheduling metadata
ALTER TABLE workflow_triggers 
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC',
ADD COLUMN IF NOT EXISTS skip_holidays BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS skip_weekends BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS notification_settings JSONB DEFAULT '{
  "on_success": false,
  "on_failure": true,
  "channels": ["in_app"]
}'::jsonb,
ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS run_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS failure_count INTEGER DEFAULT 0;

-- New table for notification preferences
CREATE TABLE IF NOT EXISTS scheduler_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    trigger_id UUID REFERENCES workflow_triggers(id) ON DELETE CASCADE,
    notification_type VARCHAR(20) NOT NULL CHECK (notification_type IN ('in_app', 'telegram', 'email')),
    on_success BOOLEAN DEFAULT FALSE,
    on_failure BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, trigger_id, notification_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scheduler_notifications_user_id ON scheduler_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduler_notifications_trigger_id ON scheduler_notifications(trigger_id);
CREATE INDEX IF NOT EXISTS idx_workflow_triggers_next_run ON workflow_triggers(next_run_at) WHERE is_active = TRUE;

-- Extend workflow_runs with scheduler metadata
ALTER TABLE workflow_runs 
ADD COLUMN IF NOT EXISTS triggered_by VARCHAR(50) DEFAULT 'manual' CHECK (triggered_by IN ('cron', 'webhook', 'manual', 'retry')),
ADD COLUMN IF NOT EXISTS retry_of UUID REFERENCES workflow_runs(id),
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS notification_sent BOOLEAN DEFAULT FALSE;

-- Table for holiday exclusions (optional future feature)
CREATE TABLE IF NOT EXISTS scheduler_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    name VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) DEFAULT 'US',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_scheduler_holidays_date ON scheduler_holidays(date);
```

### Data Model Relationships

```
workflow_triggers
├── id (PK)
├── workflow_id (FK → workflows.id)
├── owner_user_id
├── trigger_type (cron | webhook)
├── cron_expression
├── timezone (NEW)
├── skip_holidays (NEW)
├── skip_weekends (NEW)
├── description (NEW)
├── notification_settings (NEW)
├── is_active
└── ... (existing fields)

scheduler_notifications (NEW)
├── id (PK)
├── user_id
├── trigger_id (FK → workflow_triggers.id)
├── notification_type (in_app | telegram | email)
├── on_success
└── on_failure

workflow_runs
├── id (PK)
├── workflow_id (FK)
├── trigger_type
├── triggered_by (NEW: cron | webhook | manual | retry)
├── retry_of (FK → workflow_runs.id, NEW)
├── retry_count (NEW)
├── status
└── ... (existing fields)
```

---

## Implementation Phases

### Phase 1: Backend API Foundation (Week 1)

**Goal:** Create scheduler API router and basic endpoints

**Scope:**
- Create `/api/scheduler` FastAPI router
- Implement `GET /api/scheduler/jobs` — List all scheduled jobs
  - Support filtering: workflow_id, status (active/inactive), owner_id
  - Pagination support
  - Return job metadata: name, schedule, status, last run, next run
- Implement `POST /api/scheduler/jobs/{id}/toggle` — Enable/disable job
  - Update `is_active` flag in database
  - Return updated job status
- Implement `POST /api/scheduler/jobs/{id}/run-now` — Manual trigger
  - Create `WorkflowRun` record
  - Enqueue `execute_workflow_task`
  - Return run ID for tracking
- Implement `GET /api/scheduler/jobs/{id}/history` — Execution history
  - Query `workflow_runs` table
  - Support filtering by status, date range
  - Pagination
- Implement `POST /api/scheduler/jobs/{id}/retry` — Retry failed job
  - Create new `WorkflowRun` with `retry_of` reference
  - Optionally allow parameter override
- Implement `GET /api/scheduler/queue/status` — Queue status
  - Query Celery for queue depths
  - Get worker status
  - Return real-time metrics
- Implement `POST /api/scheduler/cron/validate` — Validate cron
  - Parse and validate cron expression
  - Return validation result and error message
- Implement `POST /api/scheduler/cron/preview` — Preview next runs
  - Calculate next N occurrences
  - Return list of datetime strings
- Implement notification settings endpoints
  - `GET /api/scheduler/notifications/settings`
  - `PUT /api/scheduler/notifications/settings`
- Add comprehensive RBAC checks
  - Users see only their own jobs
  - Admins can see all jobs
- Write unit tests for all endpoints

**Deliverables:**
- All API endpoints functional
- Unit tests passing (>80% coverage)
- API documentation updated

**Dependencies:** None (extends existing infrastructure)

---

### Phase 2: Global Scheduler UI (Week 2)

**Goal:** Build global scheduler view for operations

**Scope:**
- Create `/scheduler` page layout shell
  - Header with navigation tabs (Jobs, History, Queue)
  - Sidebar or top navigation
- Build Jobs tab (`/scheduler/jobs`)
  - Job list component with columns: Name, Workflow, Schedule, Status, Actions
  - Filter components (Workflow dropdown, Status dropdown, Owner dropdown for admins)
  - Search box
  - Enable/disable toggle buttons
  - "Run Now" buttons
  - Delete buttons with confirmation modal
  - Pagination
- Build History tab (`/scheduler/history`)
  - Execution list component
  - Status filters (Success, Failed, Running)
  - Date range picker
  - Drill-down to execution details
  - Retry button for failed jobs
  - Link to Flow Execution Monitor
- Build Queue tab (`/scheduler/queue`)
  - Metric cards: Pending, Running, Failed, Workers
  - Queue breakdown by queue name
  - Worker status table
  - Auto-refresh toggle
- Connect all components to backend API
- Add loading states and error handling
- Responsive design for mobile

**Deliverables:**
- Global scheduler accessible at `/scheduler`
- All three tabs functional
- Responsive design
- Error handling complete

**Dependencies:** Phase 1 API endpoints

---

### Phase 3: Per-Workflow Schedule Tab (Week 3)

**Goal:** Add schedule management to workflow detail page

**Scope:**
- Add "Schedule" tab to workflow detail page (`/workflows/{id}/schedule`)
  - Integrate with existing workflow navigation
- Build trigger list component
  - Show cron triggers with human-readable description
  - Show webhook triggers with URL (masked)
  - Status indicators (active/inactive)
  - Action buttons: Enable/Disable, Run Now, Delete
- Build "Add Schedule" flow
  - Button opens cron builder modal
  - Save creates new trigger
- Build delete confirmation modal
- Show empty state when no triggers
- Link to global scheduler for advanced management
- Update existing trigger API calls to use new endpoints

**Deliverables:**
- Schedule tab visible on workflow detail
- Can create, edit, delete triggers
- Can run triggers manually
- Smooth user experience

**Dependencies:** Phase 1 API, Phase 2 components

---

### Phase 4: Cron Builder (Week 4)

**Goal:** Build interactive visual cron builder

**Scope:**
- Create cron builder modal component
- Build preset buttons (Hourly, Daily, Weekly, Monthly, Custom)
- Build time selection UI
  - Hour dropdown (1-12 or 0-23 based on 12/24h preference)
  - Minute dropdown (00, 15, 30, 45, or 0-59)
  - AM/PM toggle (if 12h format)
- Build days of week toggles
  - Checkboxes for Mon-Sun
  - "Weekdays" shortcut button
  - "Weekends" shortcut button
  - "All" shortcut button
- Build timezone selector
  - Searchable dropdown
  - Group by region
  - Show current selection
- Build options section
  - Skip holidays checkbox
  - Skip weekends checkbox
  - Description text field
- Build preview section
  - Natural language description
  - Next 5 runs list
  - Raw cron expression (read-only or editable for power users)
- Implement validation
  - Real-time cron validation
  - Error messages for invalid combinations
- Connect to save endpoint
- Handle save success/error states

**Deliverables:**
- Visual cron builder functional
- Can create schedules via UI
- Validation and preview working
- All preset options functional

**Dependencies:** Phase 1 cron endpoints

---

### Phase 5: Notifications & Polish (Week 5)

**Goal:** Add alerting and finalize

**Scope:**
- Build notification settings UI
  - Per-trigger notification preferences
  - Channel selection (in-app, Telegram, email)
  - Success/failure toggles
  - Global defaults vs per-job settings
- Implement in-app notifications
  - Toast notifications for job failures
  - Notification bell in header
  - Notification history page
- Implement channel notifications
  - Telegram bot integration for job alerts
  - Email notifications (optional)
- Add keyboard shortcuts
  - `r` for refresh
  - `n` for new schedule
  - `?` for help
- Mobile responsiveness pass
  - Test on tablet and phone
  - Adjust layouts for small screens
- Performance optimization
  - Query optimization
  - Caching for expensive operations
  - Lazy loading for history
- Write user documentation
  - How to create schedules
  - How to monitor jobs
  - How to troubleshoot failures
- Final security review
  - RBAC enforcement
  - Input validation
  - SQL injection prevention
- End-to-end testing
  - Happy path tests
  - Error scenario tests
  - Performance tests

**Deliverables:**
- Notifications working (in-app + channels)
- Mobile responsive
- Documentation complete
- All tests passing
- Production ready

**Dependencies:** All previous phases

---

## Success Criteria

### Functional Requirements

- [ ] Global scheduler accessible at `/scheduler`
- [ ] Can view all scheduled jobs with filtering
- [ ] Can enable/disable jobs with one click
- [ ] Can run jobs manually ("Run Now")
- [ ] Can delete jobs with confirmation
- [ ] Can view execution history with filtering
- [ ] Can retry failed jobs
- [ ] Can view queue status in real-time
- [ ] Per-workflow schedule tab accessible
- [ ] Can create cron triggers via visual builder
- [ ] Can create webhook triggers
- [ ] Cron builder validates expressions
- [ ] Cron builder shows preview of next runs
- [ ] Notifications sent on job failure
- [ ] All features respect RBAC

### Performance Requirements

- [ ] Scheduler page loads in <2 seconds
- [ ] Job list supports 100+ jobs with pagination
- [ ] History page supports filtering 1000+ runs
- [ ] Queue status updates every 5 seconds
- [ ] Cron preview calculates in <1 second
- [ ] Mobile responsive (usable on phone/tablet)

### Security Requirements

- [ ] Users see only their own jobs
- [ ] Admins can see all jobs
- [ ] All endpoints require authentication
- [ ] Input validation on all fields
- [ ] SQL injection prevention
- [ ] Audit logging for job changes

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Celery complexity** | Medium | Medium | Leverage existing Celery expertise; thorough testing |
| **Cron expression edge cases** | Medium | Low | Extensive validation library; clear error messages |
| **Timezone handling bugs** | Medium | Medium | Use established libraries (zoneinfo); test with multiple zones |
| **Holiday calculation** | Low | Medium | Use external holiday API or manual entry; optional feature |
| **Notification delivery failures** | Medium | Low | Queue notifications; retry logic; fallback to in-app |
| **Performance with many jobs** | Low | Medium | Pagination; indexing; caching |
| **Mobile UX complexity** | Medium | Low | Responsive design; simplify mobile views |

---

## Future Enhancements

### v1.5 (Post-v1.4)

1. **Job Dependencies**
   - Job chains (Job A runs, then Job B)
   - Conditional execution (run Job B only if Job A succeeds)
   - Job DAGs (directed acyclic graphs)

2. **Advanced Scheduling**
   - Business days only (skip weekends + holidays)
   - Complex recurrence (e.g., "first Monday of month")
   - Timezone-aware scheduling for global teams
   - Daylight saving time handling

3. **Enhanced Monitoring**
   - Job performance trends
   - SLA monitoring (alerts if job runs too long)
   - Resource usage per job
   - Custom metrics

4. **Scheduler API**
   - Public API for external scheduling
   - Webhook callbacks on job completion
   - Integration with external calendars

### v2.0 (Long-term)

1. **Distributed Scheduling**
   - Multi-region scheduler support
   - Geographic job routing
   - Disaster recovery

2. **AI-Powered Scheduling**
   - Optimal schedule recommendations
   - Load balancing suggestions
   - Failure prediction

3. **Compliance Features**
   - Audit trails for all scheduler changes
   - Compliance reporting
   - Data retention policies

---

## Related Documents

- [Phase 4 Workflows Design](../plans/2026-02-28-phase-4-workflows-design.md)
- [Phase 8 Observability Design](../plans/2026-03-01-phase8-observability-design.md)
- [AgentOS Dashboard & Mission Control](agentos-dashboard-mission-control/00-specification.md) — Execution monitoring integration
- [Celery Documentation](https://docs.celeryq.dev/) — For advanced configuration

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
