---
created: 2026-03-15T06:51:58.504Z
title: "Implement Scheduler UI & Management APIs (Topic #15)"
area: ui
priority: high
target: v1.4-foundation
effort: 3 weeks
existing_code: "60% engine / 0% UI"
depends_on: []
design_doc: docs/enhancement/topics/15-scheduler-engine-ui/00-specification.md
files:
  - backend/scheduler/celery_app.py
  - backend/scheduler/tasks/cron_trigger.py
  - backend/core/models/workflow.py
  - backend/api/routes/workflows.py
---

## Problem

The scheduler backend engine is 60% implemented (Celery workers, beat scheduler, cron trigger task, WorkflowTrigger + WorkflowRun models, basic trigger CRUD API). However, there is ZERO scheduler management UI. Users must call REST APIs directly and write raw cron expressions. No visibility into schedule health, execution history, or queue status.

## What Exists (60% engine)

- Celery workers with beat scheduler (60s tick)
- Two queues: `embedding` (CPU-bound) and `default` (I/O-bound)
- `WorkflowTrigger` model (trigger_type, cron_expression, webhook_secret, is_active)
- `WorkflowRun` model (status tracking: pending → running → paused_hitl → completed | failed)
- Trigger CRUD API: `GET/POST/DELETE /api/workflows/{id}/triggers`
- Manual run: `POST /api/workflows/{id}/run`
- `croniter` library for cron expression parsing
- Cron trigger task fires every 60s, creates WorkflowRun records

## What's Needed (0% UI)

- **Global scheduler dashboard** — `/scheduler` page listing all scheduled jobs across workflows
- **Scheduler management APIs** — `GET /api/scheduler/jobs`, toggle enable/disable, run-now, queue status, cron validate/preview
- **Visual cron builder** — interactive UI with presets, time pickers, timezone selector (not raw cron strings)
- **Execution history view** — filterable list of WorkflowRun records with status, duration, error details
- **Queue monitoring** — visibility into Celery queue depth, worker status, active tasks
- **Notification/alerting** — configurable alerts for job failures
- **`scheduler_notifications` table** — new DB table for notification rules

## Solution

Follow specification at `docs/enhancement/topics/15-scheduler-engine-ui/00-specification.md`.
