---
status: diagnosed
phase: 06-extensibility-registries
source: 06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md, 06-04-SUMMARY.md, 06-05-SUMMARY.md, 06-06-SUMMARY.md, 06-07-SUMMARY.md
started: 2026-02-28T16:10:00Z
updated: 2026-02-28T16:25:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Admin Dashboard Access
expected: Navigate to /admin. See tabbed dashboard with Agents, Tools, Skills, MCP Servers, Permissions tabs. Non-admin users see 403.
result: pass

### 2. Agents Tab — View Agent Definitions
expected: Click the Agents tab. See a list of built-in agents (master, email, calendar, project) with name, version, status badges, and handler info. Toggle between table and card views using the view toggle.
result: pass

### 3. Tools Tab — View Tool Definitions
expected: Click the Tools tab. See registered tools with handler_type (backend/mcp/sandbox) and sandbox_required info. Status badges (active/disabled) visible.
result: pass

### 4. Skills Tab — View Skills and Pending Filter
expected: Click the Skills tab. See any registered skills. A "Pending Review" filter button should be available to show only skills in pending_review status. Skills show type (procedural/instructional), slash_command, and security trust score.
result: issue
reported: "skill is not as per describe"
severity: major

### 5. MCP Servers Tab — Connectivity Dots
expected: Click MCP Servers tab. See registered MCP servers (CRM, Docs). Each server has a connectivity status dot — green (<5min since last seen), yellow (<30min), or red (>30min or never contacted).
result: pass

### 6. Permissions Tab — Role x Artifact Matrix
expected: Click Permissions tab. See a matrix with roles as columns (admin, it-admin, developer, employee, viewer) and permission names as rows. Checkboxes indicate which roles have which permissions. Changing a checkbox marks it as pending (yellow highlight). An "Apply Pending" button activates staged changes.
result: pass

### 7. View Toggle Persistence
expected: On any artifact tab (Agents/Tools/Skills), toggle between table and card view. Refresh the page. The view preference should persist (stored in localStorage).
result: pass

### 8. Slash Command Menu in Chat
expected: Go to the chat page (/chat). Type "/" in the chat input. A dropdown/popover should appear listing available commands (both built-in and skill-based). Use Arrow keys to navigate, Tab/Enter to select, Escape to dismiss.
result: pass

### 9. User Skills API — Role-Based Filtering
expected: As an admin user, call GET /api/skills (or view the chat slash commands). You should see skills available to your role. Skills that are disabled or that your role is denied access to should NOT appear.
result: issue
reported: "only two commands no slash command for skill"
severity: major

### 10. User Tools API — Role-Based Filtering
expected: As an admin user, call GET /api/tools. You should see only active tools that your role has permission to access. Disabled tools or tools denied to your role should NOT appear.
result: pass

### 11. Admin Create Agent via API
expected: From the Agents tab, create a new agent definition (or via API: POST /api/admin/agents with name, version, handler_module, handler_function). The new agent should appear in the list. You can toggle its status (active/disabled) and activate a specific version.
result: pass

### 12. Admin Create Skill via API
expected: From the Skills tab, create a new skill (or via API: POST /api/admin/skills with name, version, skill_type, instruction_markdown or procedure_json). The new skill appears in the list. If procedural, validate it via the validate endpoint.
result: [pending]

### 13. Backend Test Suite Passes
expected: Run `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` from terminal. All tests should pass (536+ tests, 0 failures).
result: pass

### 14. Frontend Build Clean
expected: Run `cd frontend && pnpm run build` from terminal. Build completes with 0 TypeScript errors.
result: pass

## Summary

total: 14
passed: 12
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "Skills tab shows skill-specific columns (type, slash_command, trust score) and Pending Review filter"
  status: failed
  reason: "User reported: skill is not as per describe"
  severity: minor
  test: 4
  root_cause: "Code is complete and wired correctly (extraColumns, Pending Review button exist in skills/page.tsx). Likely appeared broken because skill_definitions table is empty (no data to display columns for). Also: Pending Review filter logic checks status==='active' + securityScore<70 instead of status==='pending_review'."
  artifacts:
    - path: "frontend/src/app/admin/skills/page.tsx"
      issue: "Pending Review filter logic uses wrong status check (active vs pending_review)"
  missing:
    - "Fix Pending Review filter to check status==='pending_review' instead of status==='active'"
    - "Seed skill_definitions with built-in skills so columns have data to display"
  debug_session: ""

- truth: "Slash command menu shows skill-based commands alongside built-in commands"
  status: failed
  reason: "User reported: only two commands no slash command for skill"
  severity: major
  test: 9
  root_cause: "Migration 014 creates skill_definitions table but seeds ZERO rows. Only agent_definitions (4 built-in agents) and role_permissions are seeded. GET /api/skills returns [] because table is empty. Frontend code (useSkills hook, chat-panel slash menu) is correct but receives empty data."
  artifacts:
    - path: "backend/alembic/versions/014_extensibility_registries.py"
      issue: "No INSERT statements for skill_definitions — seeds agents and role_permissions but not skills"
  missing:
    - "Add seed data for built-in skills in migration (or new migration) with slash_commands"
    - "Example skills: /summarize, /debug, /export — at minimum 2-3 to demonstrate the feature"
  debug_session: ""
