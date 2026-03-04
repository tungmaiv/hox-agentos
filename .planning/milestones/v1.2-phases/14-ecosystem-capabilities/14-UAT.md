---
status: complete
phase: 14-ecosystem-capabilities
source: 14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md, 14-04-SUMMARY.md, 14-05-SUMMARY.md
started: 2026-03-04T10:00:00Z
updated: 2026-03-04T10:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Capabilities Card via Chat
expected: In the chat, type "what can you do?" or "show me your capabilities". The agent responds with an A2UI CapabilitiesCard with four collapsible sections (Agents, Tools, Skills, MCP Servers), each showing a count badge. Sections are collapsed by default and expand on click to reveal items.
result: pass

### 2. OpenAPI Wizard — Parse Spec
expected: Go to Admin > MCP Servers page. Click "Connect OpenAPI" button. A wizard dialog opens. Paste an OpenAPI spec URL (e.g. https://petstore3.swagger.io/api/v3/openapi.json) and click Parse. The wizard shows a list of endpoints grouped by tag, with HTTP method badges (GET, POST, etc.).
result: pass

### 3. OpenAPI Wizard — Register Endpoints
expected: In the OpenAPI wizard (after parsing), select some endpoints via checkboxes. Click Next. Enter a server name, select auth type, provide API key if needed. Click Register. Success message appears. The registered tools should now show up in Admin > Tools page with handler_type "openapi_proxy".
result: pass

### 4. Skill Store Tab Exists
expected: In the admin panel sidebar/navigation, a "Skill Store" tab is visible. Clicking it opens a page with two sub-tabs: "Browse" and "Repositories".
result: pass

### 5. Skill Store — Add Repository
expected: On the Skill Store > Repositories tab, click the Add button. Enter a repository URL in the dialog. After confirming, the repository appears in the repositories table with its name, URL, and status.
result: pass

### 6. Skill Store — Browse Skills
expected: On the Skill Store > Browse tab, skills from all active repositories are shown in a 3-column card grid. Each card shows skill name and description. Typing in the search box filters cards in real-time (debounced ~300ms).
result: skipped
reason: No external skill repository available to populate browse results

### 7. Skill Store — Import Skill
expected: On the Browse tab, click Import on a skill card. A 2-step dialog appears: Step 1 confirms intent with a note about security scanning. After confirming, Step 2 shows the security scan result (score 0-100) and recommendation before allowing the dialog to close.
result: skipped
reason: No external skill repository available — requires browseable skills to test import

### 8. Skill Export — Download Zip
expected: Go to Admin > Skills page. Each skill row (table view) and card (card grid view) has an Export button. Clicking Export downloads a .zip file named "{name}-{version}.zip" containing a SKILL.md file with YAML frontmatter.
result: pass

## Summary

total: 8
passed: 6
issues: 0
pending: 0
skipped: 2

## Gaps

[none]
