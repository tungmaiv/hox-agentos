---
created: 2026-03-15T06:51:58.504Z
title: "Implement Projects/Spaces (Topic #20)"
area: general
priority: high
target: v1.5-foundation
effort: 10 weeks
existing_code: 0%
depends_on: ["topic-19-storage-service"]
design_doc: docs/enhancement/topics/20-projects-spaces/00-specification.md
---

## Problem

No project/workspace concept exists. All organization is personal-only. No team collaboration, no shared resources, no project-scoped memory or workflows.

## What Exists (0%)

Zero code — specification only. pgvector exists (required for NotebookLM features).

## What's Needed

- **Unified Project Model** — single `projects` table with nullable `workspace_id` (personal or workspace-scoped)
- **Workspace management** — `workspaces`, `workspace_members` tables
- **Project permissions** — `project_permissions` table with granular view/edit/full access (Option B)
- **NotebookLM features:**
  - Notes (markdown, rich text)
  - File attachments (depends on Storage Service #19)
  - Chat with sources (pgvector semantic search)
  - AI-powered insights
- **Project-scoped memory and workflows** — memory isolation at project level
- **Team collaboration** — sharing, real-time presence
- **Opt-in public visibility** — owner marks project as public for workspace members
- **Personal→Workspace sharing** — personal projects can be shared (no copy, remains personal)
- **Archive/Restore** — complete freeze with ZIP backup format
- **Frontend pages** — `/projects`, `/workspaces` with full CRUD UI

## Solution

Follow specification at `docs/enhancement/topics/20-projects-spaces/00-specification.md`. Implementation plan at `docs/plans/2026-03-17-projects-spaces.md`.
