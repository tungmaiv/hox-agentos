---
status: complete
phase: 27-admin-registry-edit-ui
source: [27-01-SUMMARY.md, 27-02-SUMMARY.md, 27-03-SUMMARY.md]
started: 2026-03-15T13:10:00Z
updated: 2026-03-15T13:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Row-Click Navigation on Admin List Pages
expected: Clicking a row on any admin list page navigates to the detail page. Action buttons in the row do not trigger navigation.
result: pass

### 2. Dual Pagination on List Pages
expected: All 4 admin list pages (agents, tools, mcp-servers, skills) show pagination controls at both top and bottom of the list, with page selector, page size dropdown, and range text.
result: pass

### 3. Agent Detail Page — Form Editing
expected: Navigate to /admin/agents/{id}. See 3 tabs: Overview, Config, Permissions. Overview shows read-only ID/name and editable display name/description/status. Config tab shows system prompt textarea, model alias dropdown, routing keywords, and read-only handler info.
result: pass

### 4. Tool Detail Page — Conditional Fields
expected: Navigate to /admin/tools/{id}. See 3 tabs. On Config tab, changing handler type shows different fields: backend/sandbox shows handler module/function; MCP shows tool name/server ID. Switching to sandbox auto-checks sandbox_required.
result: pass

### 5. MCP Server Detail Page — Connection Test
expected: Navigate to /admin/mcp-servers/{id}. See Overview, Connection, Tools tabs. On Connection tab, click "Test Connection" — it should test using current (unsaved) form values and show an inline success/failure result card.
result: pass

### 6. Skill Detail Page — Form Editing with Markdown Preview
expected: Navigate to /admin/skills/{id}. See structured form fields (not raw JSON). Instruction field has a Preview toggle that renders the markdown content using react-markdown.
result: pass

### 7. Sticky Save Bar — Unsaved Changes
expected: On any detail page, modify a field. A sticky bar should appear at the bottom indicating unsaved changes with a Save button. Attempting to leave the page should trigger a beforeunload warning.
result: pass

### 8. Zod Validation on Blur
expected: On any detail page form, clear a required field and blur (click away). An inline validation error should appear for that field. The save button should be blocked until errors are resolved.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
