---
phase: quick-7
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/components/admin/artifact-builder-client.tsx
autonomous: true
requirements: [IMPORT-URL-01]
must_haves:
  truths:
    - "Import from URL button/link is visible in the right panel at all times (not gated on is_complete)"
    - "Clicking it reveals a text input + Import button + Cancel link"
    - "Submitting a GitHub blob URL calls POST /api/admin/skills/import and on success populates securityReport + savedSkillId, revealing SecurityReportCard"
    - "Import errors show inline below the input"
    - "After successful import the import panel collapses"
  artifacts:
    - path: "frontend/src/components/admin/artifact-builder-client.tsx"
      provides: "Import URL panel state + handler + UI wired to /api/admin/skills/import"
  key_links:
    - from: "Import panel form submit"
      to: "/api/admin/skills/import (catch-all proxy → backend)"
      via: "fetch POST with JSON body { source_url }"
    - from: "import success response"
      to: "setSecurityReport + setSavedSkillId"
      via: "response.security_report + response.skill.id"
---

<objective>
Add an "Import from URL" panel to the Builder+ right panel that lets admins paste a GitHub SKILL.md blob URL and import it directly, bypassing the AI builder flow. On success the existing SecurityReportCard renders with Approve & Activate.

Purpose: Admins can import community SKILL.md files without using the conversational builder.
Output: Modified artifact-builder-client.tsx with import state, handler, and collapsible UI panel.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@frontend/src/components/admin/artifact-builder-client.tsx

<interfaces>
<!-- Catch-all admin proxy already handles POST /api/admin/skills/import -->
<!-- No new proxy file needed — the [...path]/route.ts proxies all /api/admin/* -->

Backend POST /api/admin/skills/import response shape:
```typescript
{
  skill: { id: string; name: string; status: string; /* ...other fields */ };
  security_report: SecurityReportData;  // same type already used by securityReport state
}
```

SecurityReportData is already imported from "./security-report-card".

Existing state already in BuilderInner (use/extend these):
  securityReport: SecurityReportData | null       → set from response.security_report
  savedSkillId: string | null                     → set from response.skill.id
  saveSuccess: boolean                            → check: SecurityReportCard only shows when !saveSuccess

Existing render guard already in place (lines 413-418):
  {securityReport && !saveSuccess && savedSkillId ? (
    <SecurityReportCard skillId={savedSkillId} report={securityReport} onApproved={() => setSaveSuccess(true)} />
  ) : ...}

Existing action buttons area (lines 460-468) — "Edit JSON" link pattern to follow:
  {builderState.is_complete && !showJsonEditor && !securityReport && (
    <button className="text-xs text-blue-600 hover:text-blue-800 underline">Edit JSON</button>
  )}

"Find Similar" block starts at line 471 — separated by border-t border-gray-100 pt-3.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add import URL state, handler, and panel UI to artifact-builder-client.tsx</name>
  <files>frontend/src/components/admin/artifact-builder-client.tsx</files>
  <action>
**Step 1 — Add 4 new state variables** after the `showJsonEditor` block (around line 83):

```typescript
// Import from URL panel state
const [showImport, setShowImport] = useState(false);
const [importUrl, setImportUrl] = useState("");
const [importing, setImporting] = useState(false);
const [importError, setImportError] = useState<string | null>(null);
```

**Step 2 — Add `handleImport` callback** after `handleToggleJsonEditor` (around line 332):

```typescript
const handleImport = useCallback(async () => {
  if (!importUrl.trim()) return;
  setImporting(true);
  setImportError(null);
  try {
    const res = await fetch("/api/admin/skills/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: importUrl.trim() }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      const msg = typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    const data = (await res.json()) as {
      skill: { id: string };
      security_report: SecurityReportData;
    };
    setSecurityReport(data.security_report);
    setSavedSkillId(data.skill.id);
    setShowImport(false);
    setImportUrl("");
  } catch (err) {
    setImportError(err instanceof Error ? err.message : "Import failed");
  } finally {
    setImporting(false);
  }
}, [importUrl]);
```

**Step 3 — Add "Import from URL" link** in the right panel body, after the "Edit JSON" button block (after line 468) and before the "Find Similar" block (line 470). Insert only when `!securityReport`:

```tsx
{/* Import from URL — always accessible, not gated on is_complete */}
{!securityReport && (
  <div>
    {!showImport ? (
      <button
        onClick={() => { setShowImport(true); setImportError(null); }}
        className="text-xs text-blue-600 hover:text-blue-800 underline"
      >
        Import from URL
      </button>
    ) : (
      <div className="space-y-2 border border-gray-200 rounded-md p-3 bg-gray-50">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-gray-700">Import SKILL.md from URL</span>
          <button
            onClick={() => { setShowImport(false); setImportUrl(""); setImportError(null); }}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>
        <input
          type="url"
          value={importUrl}
          onChange={(e) => setImportUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/blob/main/SKILL.md"
          className="w-full text-xs border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        {importError && (
          <p className="text-xs text-red-600">{importError}</p>
        )}
        <button
          onClick={handleImport}
          disabled={importing || !importUrl.trim()}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs font-medium disabled:opacity-50"
        >
          {importing ? "Importing..." : "Import"}
        </button>
      </div>
    )}
  </div>
)}
```

**Placement rule:** The import block goes between the "Edit JSON" button (line ~468) and the "Find Similar" section (line ~471 `{hasDraftNameAndDescription && !securityReport && (`). Both existing blocks are inside the `flex-1 overflow-auto p-4 space-y-4` div.

Note: The catch-all proxy at `/api/admin/[...path]/route.ts` already handles `POST /api/admin/skills/import` — no new proxy file is needed.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    - tsc --noEmit passes with no new errors
    - "Import from URL" link visible in right panel body (not gated on is_complete or securityReport)
    - Clicking reveals inline input + Import button + Cancel
    - Cancel hides the panel and clears the URL
    - On success: securityReport + savedSkillId are set, import panel collapses, SecurityReportCard renders
    - On API error: importError shown inline in red below the input
  </done>
</task>

</tasks>

<verification>
1. `pnpm exec tsc --noEmit` in frontend/ — no TypeScript errors
2. In the running app: open /admin/builder, confirm "Import from URL" link visible without needing to complete any AI conversation
3. Enter a GitHub blob URL, submit — verify SecurityReportCard appears with Approve & Activate button on success
</verification>

<success_criteria>
- TypeScript compiles cleanly
- Import panel state and handler integrated without breaking existing save/security-gate flow
- SecurityReportCard rendered after successful import (uses same securityReport + savedSkillId state path as the builder-save flow)
</success_criteria>

<output>
After completion, create `.planning/quick/7-add-import-url-panel-to-builder-right-pa/7-SUMMARY.md`
</output>
