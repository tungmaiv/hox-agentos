# Admin Registry Edit UI — Design Document

**Status:** ✅ Approved for Implementation  
**Topic:** #6 (Expanded from Frontend Build Optimization)  
**Target:** v1.4  
**Priority:** High  
**Estimated Effort:** 0.5-1 Phase  
**Author:** Architecture Team  
**Date:** 2026-03-14  

---

## Executive Summary

Create comprehensive detail and edit pages for all registry types (agents, tools, MCP servers, skills) with **form-based editing** instead of raw JSON. Include **test/preview functionality** for validation, consistent navigation patterns, and dual pagination placement.

**Key Principle:** No more JSON editing for registry configuration — provide intuitive forms with validation.

---

## Current State vs Target State

### Current State (As-Is)

| Registry Type | List View | Detail Page | Edit Capability |
|---------------|-----------|-------------|-----------------|
| **Skills** | ✅ Yes | ✅ Yes (basic) | ❌ JSON only, no forms |
| **Agents** | ✅ Yes | ❌ No | ❌ None |
| **Tools** | ✅ Yes | ❌ No | ❌ None |
| **MCP Servers** | ✅ Yes | ❌ No | ❌ None |

**Problems:**
- Skills detail shows raw JSON config (error-prone, not user-friendly)
- Agents, Tools, MCP servers have no detail pages at all
- No way to view or edit individual registry entries
- Inconsistent UX across registry types
- No way to test MCP server connectivity before saving
- Pagination only at bottom (inconvenient for long lists)

### Target State (To-Be)

| Registry Type | List View | Detail Page | Edit Capability | Test Function |
|---------------|-----------|-------------|-----------------|---------------|
| **Skills** | ✅ + Top Pagination | ✅ Enhanced | ✅ Form-based | ✅ Security rescan |
| **Agents** | ✅ + Top Pagination | ✅ NEW | ✅ Form-based | ⚠️ Future (agent test) |
| **Tools** | ✅ + Top Pagination | ✅ NEW | ✅ Form-based | ⚠️ Future (tool test) |
| **MCP Servers** | ✅ + Top Pagination | ✅ NEW | ✅ Form-based | ✅ Connection test |

**Benefits:**
- Consistent UX across all registry types
- Form-based editing reduces errors
- Test functionality prevents misconfiguration
- Better navigation with breadcrumbs and back links
- Improved list navigation with dual pagination

---

## Detailed Design Decisions

### Decision 1: Name/Slug is NOT Editable

**Rationale:**
- Name is used as identifier in URLs, configs, and references
- Changing name would break: workflows, skills, permission mappings
- Creates complexity with foreign key-like relationships
- Display name can be changed instead for user-facing labels

**Implementation:**
```typescript
// Name shown as read-only field
<div className="text-sm text-gray-500">
  <span className="font-medium">Name:</span> {entry.name}
  <span className="text-xs text-gray-400 ml-2">(cannot be changed)</span>
</div>

// Display name is editable
<input 
  value={formData.displayName} 
  onChange={...} 
  placeholder="User-friendly display name"
/>
```

---

### Decision 2: Field Priority — Phased Implementation

**Phase 1 (Core Fields) — All Registry Types:**
1. **Display Name** — User-friendly label
2. **Description** — What this registry entry does
3. **Status** — Active / Archived / Draft

**Phase 2 (Config Fields) — Type-Specific:**

**Agents:**
- System prompt / instructions
- Allowed tools (multi-select)
- Memory configuration (boolean + TTL)
- Max conversation length

**Tools:**
- Handler type (backend/mcp/openapi_proxy/sandbox) — read-only if affects infrastructure
- Required permissions (multi-select)
- Sandbox required (checkbox)
- MCP server reference (if handler=mcp)
- Input/output schema (JSON editor with validation)

**MCP Servers:**
- URL (with validation)
- Transport (http_sse / stdio)
- Authentication type (none/api_key/oauth)
- Auth credentials (encrypted, masked input)
- Health check endpoint
- Timeout configuration

**Skills:**
- Skill type (instructional/procedural) — read-only (determines structure)
- Instruction content (rich text/markdown editor)
- Procedure steps (visual step editor)
- Required tools (derived from procedure)

**Phase 3 (Advanced):**
- Metadata / tags
- Icon/image upload
- Documentation URL
- Version notes

---

### Decision 3: Test/Preview Functionality — YES

**MCP Server Test:**
```typescript
// Test button on MCP server detail/edit page
async function testMcpConnection() {
  const result = await fetch(`/api/admin/mcp-servers/${id}/test`, {
    method: "POST"
  });
  // Returns: { success: boolean, latency_ms: number, error?: string, tools_count?: number }
}
```

**UI Flow:**
1. User clicks "Test Connection" button
2. Backend attempts connection to MCP server URL
3. Result shown: ✅ Connected (45ms, 12 tools available) or ❌ Failed: Connection refused
4. User can save only after successful test (optional enforcement)

**Skill Security Rescan:**
- Already exists on skills page
- Add to skill detail page as "Re-scan" button
- Show scan progress and results inline

**Tool Test (Future):**
- Test tool with sample inputs
- Show output preview
- Validate input/output schema

**Agent Test (Future):**
- Quick chat interface to test agent
- Shows responses with current configuration

---

### Decision 4: Bulk Edit — NO

**Rationale:**
- Adds complexity to UI (checkboxes, selection state)
- Risk of accidental mass changes
- Most registry edits are individual and deliberate
- Can be added later if needed

**Alternative:**
- Provide quick status toggle on list view (already exists)
- Keep detailed editing to individual pages

---

### Decision 5: Dual Pagination (Top + Bottom)

**Rationale:**
- Users shouldn't have to scroll to bottom to navigate
- Long lists (50+ items) are hard to navigate
- Industry standard pattern

**Implementation:**
```typescript
// At top of list
<div className="flex items-center justify-between mb-4">
  <span className="text-sm text-gray-500">
    Showing {start}–{end} of {total}
  </span>
  <PaginationControls 
    page={page} 
    totalPages={totalPages} 
    onChange={setPage}
  />
</div>

// List content...

// At bottom of list (existing)
<div className="flex items-center justify-between mt-4 pt-3 border-t">
  <PageSizeSelector value={pageSize} onChange={setPageSize} />
  <PaginationControls 
    page={page} 
    totalPages={totalPages} 
    onChange={setPage}
  />
</div>
```

---

## Page Structure

### Detail Page Layout (All Registry Types)

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to [Registry Type]                                       │
│                                                                 │
│ [Display Name]                              [Edit] [Test]      │
│ [Name: registry_name] (immutable)                              │
│ [Status Badge]                                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [Overview] [Configuration] [Advanced] ← Tabs                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tab Content:                                                   │
│  • Overview: Read-only details or editable form                 │
│  • Configuration: Type-specific form fields                     │
│  • Advanced: Raw JSON (for power users)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Edit Mode

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to [Registry Type]                                       │
│                                                                 │
│ [Editing: Display Name]                    [Save] [Cancel]     │
│ Name: registry_name (cannot be changed)                        │
│ Status: [Active ▼]                                             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Form Fields:                                                    │
│                                                                 │
│ Display Name: [________________] *                             │
│ Description:  [________________]                               │
│                                                                 │
│ ── Configuration ──                                            │
│ Handler Type: [Backend ▼] (read-only)                          │
│ Required Permissions:                                          │
│   ☑ tool:email                                                 │
│   ☑ tool:calendar                                              │
│   ☐ tool:admin                                                 │
│                                                                 │
│ Sandbox Required: ☑                                            │
│                                                                 │
│ [Save Changes] [Cancel]                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### New Components

```
frontend/src/components/admin/registry/
├── RegistryDetailLayout.tsx      # Breadcrumb, header, tabs shell
├── RegistryEditForm.tsx          # Common fields (name, desc, status)
├── RegistryPagination.tsx        # Top/bottom pagination wrapper
├── TestConnectionButton.tsx      # Generic test button with status
│
├── agents/
│   └── AgentConfigForm.tsx       # Agent-specific fields
├── tools/
│   └── ToolConfigForm.tsx        # Tool-specific fields
├── mcp-servers/
│   ├── McpServerConfigForm.tsx   # MCP-specific fields
│   └── McpConnectionTester.tsx   # Connection test UI
└── skills/
    └── SkillConfigForm.tsx       # Skill-specific fields
```

### Component Details

**RegistryDetailLayout**
```typescript
interface RegistryDetailLayoutProps {
  type: "agent" | "tool" | "mcp_server" | "skill";
  entry: RegistryEntry;
  isEditing: boolean;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  activeTab: string;
  onTabChange: (tab: string) => void;
  children: React.ReactNode;
}
```

**TestConnectionButton**
```typescript
interface TestConnectionButtonProps {
  id: string;
  type: "mcp_server";  // Extendable to other types
  onTest?: (result: TestResult) => void;
  required?: boolean;  // If true, must pass before saving
}

interface TestResult {
  success: boolean;
  latencyMs?: number;
  toolsCount?: number;
  error?: string;
  timestamp: string;
}
```

---

## API Endpoints

### New Endpoints

```
GET    /api/admin/agents/{id}           # Get agent details
PUT    /api/admin/agents/{id}          # Update agent
POST   /api/admin/agents/{id}/test     # Test agent (future)

GET    /api/admin/tools/{id}            # Get tool details
PUT    /api/admin/tools/{id}           # Update tool
POST   /api/admin/tools/{id}/test      # Test tool (future)

GET    /api/admin/mcp-servers/{id}      # Get MCP server details
PUT    /api/admin/mcp-servers/{id}     # Update MCP server
POST   /api/admin/mcp-servers/{id}/test # Test MCP connection

# Skills endpoints already exist, enhance with:
PUT    /api/admin/skills/{id}          # Update skill (enhance)
```

### Test Endpoint Response

```typescript
// POST /api/admin/mcp-servers/{id}/test
interface McpTestResponse {
  success: boolean;
  latency_ms: number;
  tools_available: number;
  tools_list?: string[];
  error?: string;
  error_code?: "connection_refused" | "timeout" | "auth_failed" | "invalid_response";
  timestamp: string;
}
```

---

## Implementation Plan

### Phase 1: Foundation (2 plans)

**Plan 1: Shared Components**
- Create `RegistryDetailLayout` component
- Create `RegistryPagination` (dual pagination)
- Create `RegistryEditForm` (common fields)
- Update existing list pages to add top pagination

**Plan 2: MCP Server Detail + Test**
- Create `/admin/mcp-servers/[id]/page.tsx`
- Implement MCP-specific config form
- Add connection test functionality
- Backend endpoint: `POST /api/admin/mcp-servers/{id}/test`

### Phase 2: Agents & Tools (2 plans)

**Plan 3: Agent Detail Page**
- Create `/admin/agents/[id]/page.tsx`
- Agent-specific form fields (system prompt, allowed tools)
- Link from agent list to detail pages

**Plan 4: Tool Detail Page**
- Create `/admin/tools/[id]/page.tsx`
- Tool-specific form fields (handler type, permissions)
- Link from tool list to detail pages

### Phase 3: Enhanced Skills (1 plan)

**Plan 5: Skills Edit Enhancement**
- Enhance existing `/admin/skills/[id]/page.tsx`
- Replace JSON-only config with form fields
- Add form-based editing for skill type-specific fields
- Keep JSON tab for advanced users

---

## UI/UX Specifications

### Navigation Patterns

**Breadcrumb Pattern:**
```
← Back to Tools                    (simple back link)
-or-
Admin / Tools / email_fetch        (breadcrumb)
```

**Decision:** Use simple back link for consistency with existing UI

**List to Detail Navigation:**
- List items clickable (whole row or explicit "View" link)
- Card view: Click card to open detail
- List view: Click name or "View" action

### Form Validation

**Client-Side:**
```typescript
const FormSchema = z.object({
  displayName: z.string().min(1, "Display name is required").max(100),
  description: z.string().max(500).optional(),
  status: z.enum(["active", "archived", "draft"]),
  // Type-specific fields...
});
```

**Error Display:**
- Inline under each field
- Red border on invalid fields
- Summary at top for submit errors

### Loading States

- **Page load:** Skeleton screens matching content layout
- **Save:** Loading spinner on Save button, disable form
- **Test:** Progress indicator, disable Test button during test

### Success/Error Feedback

- **Save success:** Toast notification, stay on page with updated data
- **Save error:** Inline error display, scroll to first error
- **Test success:** Inline success message with metrics
- **Test failure:** Inline error with troubleshooting hint

---

## Success Criteria

- [ ] All 4 registry types have detail pages with consistent layout
- [ ] All detail pages support form-based editing (not just JSON)
- [ ] Name/slug is displayed but not editable
- [ ] Display name, description, status editable on all types
- [ ] Type-specific config fields editable with appropriate inputs
- [ ] MCP servers have connection test functionality
- [ ] All list pages have pagination at top AND bottom
- [ ] Consistent "Back to [List]" navigation on all detail pages
- [ ] Form validation shows inline errors
- [ ] Changes persist to backend and reflect immediately
- [ ] Responsive design works on mobile devices

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complex form state management | Medium | Use single form state object, Zod for validation |
| MCP test endpoint security | High | Gate with `tool:admin` permission, rate limit |
| Breaking existing skills page | Medium | Keep JSON tab as fallback, gradual migration |
| Too many form fields overwhelming | Medium | Group into tabs, progressive disclosure |
| Backend validation mismatches | Medium | Share Zod schemas between frontend/backend |

---

## Future Enhancements

1. **Rich Text Editor** — For skill instructions and agent prompts
2. **Schema Builder** — Visual editor for tool input/output schemas
3. **Version History** — Show/edit previous versions of registry entries
4. **Clone/Duplicate** — Copy existing registry as template
5. **Import/Export** — JSON import/export for registry entries
6. **Tool Test Console** — Interactive tool testing with custom inputs
7. **Agent Playground** — Full chat interface to test agents

---

## Notes

- Keep existing skills detail page JSON view as "Advanced" tab
- Ensure all forms work with keyboard navigation (accessibility)
- Consider adding "Discard changes?" confirmation if user navigates away with unsaved edits
- Mobile: Stack form fields vertically, tabs become dropdown on small screens

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-14  
**Status:** Ready for Implementation Planning
