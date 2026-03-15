---
created: 2026-03-15T06:51:58.504Z
title: "Implement Third-Party Apps UI (Topic #24)"
area: ui
priority: medium
target: v1.6-architecture
effort: 10 weeks
existing_code: 0%
depends_on: ["topic-21-universal-integration"]
design_doc: docs/enhancement/topics/24-third-party-apps-ui/00-specification.md
---

## Problem

No dynamic form generation for third-party integrations. Users cannot interact with connected services through a visual UI — they must use chat commands or raw API calls. No A2UI-based form rendering for integration data.

## What Exists (0%)

- A2UI infrastructure exists (A2UIMessageRenderer in CopilotKit)
- Zero code for third-party apps UI — specification only

## What's Needed

- **Auto-generated forms** — when integrations connect, auto-generate A2UI forms from schema
- **`app_form` table** — form persistence with JSONB A2UI spec
- **12 A2UI component types:** text, select, table, chart, file, number, date, toggle, radio, checkbox, textarea, code
- **Form Generator Agent** — AI agent that creates A2UI form specs from integration schemas
- **Form Customizer Agent** — AI agent for chat-based form customization
- **"Chat with Apps" interface** — new left navigation entry
- **Interactive customization via natural language** — users chat to modify forms
- **Real-time preview** — live preview as users customize forms
- **Form execution** — forms execute via MCP/REST/CLI adapters (Topic #21)
- **Save and reuse** — customized forms saved for repeated use
- **Hybrid A2UI + useHumanInTheLoop** — CopilotKit integration for interactive customization

## Solution

Follow specification at `docs/enhancement/topics/24-third-party-apps-ui/00-specification.md`. Implementation plan at `docs/plans/2026-03-15-topic24-implementation-plan.md`.
