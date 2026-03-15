---
created: 2026-03-15T06:51:58.504Z
title: "Implement Plugin Templates (Topic #23)"
area: general
priority: low
target: v1.6-architecture
effort: 6 weeks
existing_code: 0%
depends_on: ["topic-21-universal-integration"]
design_doc: docs/enhancement/topics/23-plugin-templates/00-specification.md
---

## Problem

Only workflow templates exist (`workflow_templates` table). No agent, skill, or tool templates. No template marketplace or gallery for users to discover and subscribe to pre-built agent packs.

## What Exists (0%)

- `workflow_templates` table (basic, for workflows only)
- Zero code for general template system — specification only

## What's Needed

- **Template data model:**
  - `template` table — ZIP-based template packages with JSON manifests
  - `template_entity` table — individual entities within a template (agents, skills, tools)
  - `template_instance` table — deployed instances with lineage tracking
  - `template_user_assignment` table — user subscriptions to template agents
- **Template management:** import/export ZIP, enable/disable/delete
- **Template gallery:** self-service discovery, preview, and agent subscription
- **Marketing Template v1:** 10 specialized agents:
  - Content Strategist, SEO Analyst, Social Media Manager, Email Marketer, Analytics Reporter, Brand Voice Guardian, Competitor Intelligence, Campaign Manager, Content Calendar, Performance Optimizer
- **REST API:** admin management, deployment, user gallery endpoints
- **Frontend UI:** import, list, detail, deploy, gallery, my-agents pages
- **Template-Aware Entities** — full lineage tracking (which agents came from which templates)
- **Self-Service + Admin Override** deployment model

## Solution

Follow specification at `docs/enhancement/topics/23-plugin-templates/00-specification.md`. Implementation plan at `docs/plans/2026-03-15-topic23-plugin-templates-plan.md`.
