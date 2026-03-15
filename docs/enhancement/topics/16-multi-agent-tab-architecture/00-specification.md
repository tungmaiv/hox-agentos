# Multi-Agent Tab Architecture for Artifact Creation

**Status:** Proposed  
**Phase:** Post-v1.3 Enhancement  
**Priority:** High (addresses critical UX and context pollution issues)  
**Estimated Effort:** 10-13 hours  

---

## 1. Executive Summary

### Problem Statement

The current artifact creation wizard (`/admin/create`) suffers from several critical issues:

1. **Context Pollution**: Skill creation conversations become cluttered with tool/MCP implementation details
2. **UI State Bugs**: Form state synchronization issues when switching artifact types (Bug 2: stale fields re-applied after form reset)
3. **No Parallel Creation**: Cannot work on multiple missing dependencies simultaneously
4. **Poor UX**: User must manually navigate away, loses context, hard to resume

### Solution Overview

Implement a **multi-agent tab architecture** that:
- Spawns separate agent instances in new UI tabs for tool/MCP creation
- Maintains clean context isolation between artifact types
- Enables parallel dependency creation
- Tracks cross-agent dependencies via database
- Provides visual status indicators and seamless navigation

---

## 2. Background & Current State

### Current Architecture (v1.3)

The artifact builder uses a **single CopilotKit co-agent** (`artifact_builder`) with a split-panel UI:

```
┌─────────────────────────────────────────────┐
│  Left Panel (45%)    │  Right Panel (55%)   │
│  - Structured Form   │  - CopilotChat       │
│  - Type selector     │  - artifact_builder  │
│  - Field inputs      │    co-agent          │
└─────────────────────────────────────────────┘
```

**Issues with Current Approach:**

1. **Single Conversation Thread**: All artifact types (skill, tool, MCP) share one chat context
2. **State Conflicts**: Form state updates can overwrite each other when switching types
3. **No Dependency Tracking**: When skill needs missing tools, no mechanism to coordinate creation
4. **Context Leakage**: Tool implementation details pollute skill intent discussion

### Known Bugs Driving This Change

#### Bug 1: artifact_type Stripped at Extraction
**File:** `backend/agents/artifact_builder.py:168`  
**Issue:** `_try_extract_fill_form_args()` filtered out `artifact_type` from text-format fill_form calls  
**Impact:** Type switch never detected, form stuck on wrong artifact type

#### Bug 2: Stale MCP Fields Re-applied After Form Reset
**File:** `frontend/src/components/admin/artifact-wizard.tsx:175-193`  
**Issue:** When AI switched `artifact_type`, form reset to `EMPTY_FORM`, but updates object still contained old MCP fields  
**Impact:** Old fields (`form_url`, `form_auth_token`) overwrote the reset

#### Bug 3: LLM Overrides Keyword Detection
**File:** `backend/agents/artifact_builder.py:576`  
**Issue:** After Bug 1 fix, LLM's `fill_form(artifact_type="skill")` overrode keyword-detected `"mcp_server"`  
**Impact:** Form jumped to Skill before MCP registration

---

## 3. Proposed Architecture

### 3.1 Multi-Tab Agent Model

```
User creates skill requiring tools [email-fetch, slack-send]
         ↓
Skill Agent detects missing tools
         ↓
UI shows: "Tools needed: email-fetch, slack-send"
         ↓
User clicks "Create email-fetch tool"
         ↓
┌──────────────────────────────────────────────────────────────┐
│ NEW TAB SPAWNS with Tool Builder Agent                       │
│   ┌─────────────────┐  ┌─────────────────┐                  │
│   │ Tool Form       │  │ Tool Agent Chat │                  │
│   │ - handler_code  │  │ (isolated from  │                  │
│   │ - input_schema  │  │  skill context) │                  │
│   │ - output_schema │  │                 │                  │
│   └─────────────────┘  └─────────────────┘                  │
│                                                              │
│   Pre-loaded context from parent skill:                      │
│   - Skill description                                        │
│   - Why this tool is needed                                  │
│   - Suggested tool configuration                             │
└──────────────────────────────────────────────────────────────┘
         ↓
User works in parallel tabs
         ↓
Tool created → Dependency service notifies parent → Status updated
         ↓
User returns to Skill tab, sees "✅ email-fetch ready", continues
```

### 3.2 System Components

```
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND (Next.js)                      │
├──────────────────────────────────────────────────────────────┤
│  MultiAgentWizard                                            │
│  ├── TabManager (useAgentTabs hook)                          │
│  │   ├── Tab 1: Skill Agent (parent)                        │
│  │   │   └── CopilotKit(agent="artifact_builder")           │
│  │   ├── Tab 2: Tool Agent (child)                          │
│  │   │   └── CopilotKit(agent="tool_builder")               │
│  │   └── Tab 3: MCP Agent (child)                           │
│  │       └── CopilotKit(agent="mcp_builder")                │
│  └── DependencyNotifier (polling/backend events)             │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI + LangGraph)                   │
├──────────────────────────────────────────────────────────────┤
│  API Layer                                                   │
│  ├── POST /api/agent-dependencies                           │
│  ├── GET  /api/agent-dependencies/parent/{session_id}       │
│  ├── POST /api/agent-dependencies/{id}/child-started        │
│  └── POST /api/agent-dependencies/{id}/completed            │
│                                                              │
│  Agents (LangGraph)                                          │
│  ├── artifact_builder (skill creation)                      │
│  ├── tool_builder (tool creation)                           │
│  └── mcp_builder (MCP server creation)                      │
│                                                              │
│  Services                                                    │
│  └── AgentDependencyService                                  │
│      └── CRUD for dependency records                         │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL)                           │
├──────────────────────────────────────────────────────────────┤
│  agent_dependencies table                                    │
│  ├── id: UUID (PK)                                          │
│  ├── parent_session_id: string (indexed)                    │
│  ├── parent_agent_type: string                              │
│  ├── child_session_id: string (nullable, indexed)          │
│  ├── child_agent_type: string                               │
│  ├── dependency_name: string                                │
│  ├── dependency_type: enum(tool, mcp_server)               │
│  ├── status: enum(pending, in_progress, completed, failed) │
│  ├── context_payload: JSONB                                 │
│  ├── result_payload: JSONB                                  │
│  └── timestamps                                             │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate CopilotKit instances per tab** | True context isolation; no state leakage |

> **Implementation Note (from v1.4 pitfalls research):** CopilotKit v0.1.78 does NOT support
> multiple simultaneous provider instances on one page — `useCopilotChat` shares context through
> a single provider. Implementation must use **tab-switching with a single CopilotKit provider**
> (mount only the active tab's agent), not multiple parallel providers. See GitHub issue #1159.

| **Database-backed dependency tracking** | Survives page refresh; audit trail; cross-session recovery |
| **Explicit context passing** | Parent skill intent preserved when spawning child agents |
| **Tab-based UI** | Familiar UX (browser tabs); easy navigation; visual status |
| **Async notification (polling)** | Simple to implement; works with existing SSE/CopilotKit |
| **Parent cannot close with active children** | Prevents orphaned dependencies; forces completion |

---

## 4. Detailed Implementation

### 4.1 Database Schema

```sql
-- Migration: 031_agent_dependencies
CREATE TABLE agent_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id VARCHAR NOT NULL,
    parent_agent_type VARCHAR NOT NULL, -- skill, tool, mcp, agent
    child_session_id VARCHAR,
    child_agent_type VARCHAR NOT NULL, -- tool, mcp
    dependency_name VARCHAR NOT NULL,
    dependency_type VARCHAR NOT NULL, -- tool, mcp_server
    status VARCHAR NOT NULL DEFAULT 'pending', -- pending, in_progress, completed, failed
    context_payload JSONB,
    result_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agent_deps_parent ON agent_dependencies(parent_session_id, status);
CREATE INDEX idx_agent_deps_child ON agent_dependencies(child_session_id);
```

### 4.2 Backend API

#### Endpoints

```yaml
# POST /api/agent-dependencies
# Creates dependency record when skill detects missing tool/MCP
Request:
  parent_session_id: string
  parent_agent_type: string
  dependency_name: string
  dependency_type: string
  child_agent_type: string
  context_payload: object  # Skill context passed to child

Response: 201 Created
  id: UUID
  parent_session_id: string
  status: "pending"

---

# GET /api/agent-dependencies/parent/{session_id}
# Gets all pending dependencies for parent session
Response: 200 OK
  [
    {
      id: UUID
      dependency_name: string
      dependency_type: string
      status: string
      child_session_id: string|null
    }
  ]

---

# POST /api/agent-dependencies/{id}/child-started
# Called when child tab opens
Request:
  child_session_id: string

Response: 200 OK
  # Updated dependency with status="in_progress"

---

# POST /api/agent-dependencies/{id}/completed
# Called when child artifact created
Request:
  result_payload: object  # {tool_id: "...", tool_name: "..."}

Response: 200 OK
  # Updated dependency with status="completed"
```

### 4.3 Frontend Architecture

#### State Management

```typescript
// types/agent-tabs.ts
interface AgentTab {
  id: string;                    // Unique tab ID
  sessionId: string;             // CopilotKit session ID
  agentType: 'skill' | 'tool' | 'mcp' | 'agent';
  title: string;
  isActive: boolean;
  
  // Child-specific fields
  parentTabId?: string;
  dependencyId?: string;
  initialContext?: Record<string, unknown>;
  
  // Status tracking
  status: 'idle' | 'working' | 'completed' | 'error';
}

// hooks/use-agent-tabs.ts
function useAgentTabs() {
  const [tabs, setTabs] = useState<AgentTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  
  // Actions
  const createParentTab = (agentType, title) => {...}
  const spawnChildTab = (parentTabId, agentType, depName, depId, context) => {...}
  const switchTab = (tabId) => {...}
  const closeTab = (tabId) => {...}  // Prevents closing parent with children
  const updateTabStatus = (tabId, status) => {...}
  
  return { tabs, activeTabId, createParentTab, spawnChildTab, ... };
}
```

#### Component Hierarchy

```tsx
// MultiAgentWizard (main container)
<MultiAgentWizard>
  <MultiAgentTabs 
    tabs={tabs} 
    activeTabId={activeTabId}
    onSwitchTab={...}
    onCloseTab={...}
  />
  
  {tabs.map(tab => (
    tab.isActive && (
      <CopilotKit 
        key={tab.sessionId}  // Forces new instance per tab
        runtimeUrl="/api/copilotkit"
        agent={getAgentName(tab.agentType)}
      >
        <SplitPanelLayout>
          <ArtifactWizardForm />
          <CopilotChat 
            initial={tab.parentTabId 
              ? `Creating ${tab.agentType}. Parent context: ${JSON.stringify(tab.initialContext)}`
              : "I can create agents, tools, skills, and MCP servers..."
            }
          />
        </SplitPanelLayout>
      </CopilotKit>
    )
  ))}
</MultiAgentWizard>
```

### 4.4 Agent-Specific Behavior

#### Skill Builder Agent Changes

Add new phase to `backend/prompts/artifact_builder_skill.md`:

```markdown
### Phase 4b — Detect Missing Dependencies

When designing a procedural skill:
1. Analyze each step's tool requirements
2. Query system.capabilities for available tools
3. If tool/MCP doesn't exist:
   - Add to artifact_draft.missing_dependencies
   - Suggest configuration
   - Set artifact_draft.requires_dependencies = true

### Phase 6 — Preview (Updated)

If missing_dependencies exist:
```
⚠️ This skill requires {N} dependencies:

1. Tool: email-fetch
   [Create Tool] ← Spawns tool builder in new tab

2. MCP: slack-integration
   [Create MCP] ← Spawns MCP builder in new tab

Options:
- Create dependencies first
- Save as Draft
- Modify to remove dependencies
```
```

#### New Tool Builder Agent

```python
# backend/agents/tool_builder.py
"""Dedicated agent for tool creation."""

@tool
def update_tool_form(
    name: str | None = None,
    handler_code: str | None = None,
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    required_permissions: list[str] | None = None,
) -> str:
    """Update tool creation form fields."""
    ...

# Nodes: gather_requirements → design_handler → generate_code → validate_tool
```

---

## 5. Migration Path

### Phase 1: Backend Infrastructure (2-3 hours)
1. Database migration (031_agent_dependencies)
2. AgentDependency model
3. AgentDependencyService
4. API endpoints
5. Unit tests

### Phase 2: Frontend Tabs (2-3 hours)
1. Type definitions
2. useAgentTabs hook
3. MultiAgentTabs component
4. MultiAgentWizard container
5. Integration with existing form components

### Phase 3: Agent Refactoring (3-4 hours)
1. Tool builder agent
2. MCP builder agent
3. Update skill builder prompts
4. Context passing implementation

### Phase 4: Testing & Polish (2 hours)
1. Integration tests
2. E2E tests with Cypress
3. Bug fixes
4. Documentation

### Backward Compatibility
- Existing single-tab mode still works
- Opt-in via feature flag or URL param
- Database changes additive (no breaking changes)

---

## 6. Benefits

### Immediate Fixes
- ✅ **Fixes Bug 2**: Context isolation prevents stale field issues
- ✅ **Fixes context pollution**: Each agent has clean slate
- ✅ **Enables parallel work**: Multiple dependencies created simultaneously

### UX Improvements
- ✅ **Clear navigation**: Tabbed interface shows all active creations
- ✅ **Status visibility**: Visual indicators (✅ ⚠️ 🔄) on each tab
- ✅ **Context preservation**: Parent skill intent passed to children
- ✅ **Resume capability**: Database tracking allows session recovery

### Technical Benefits
- ✅ **Scalability**: Easy to add new agent types
- ✅ **Testability**: Isolated agents easier to test
- ✅ **Maintainability**: Clear separation of concerns
- ✅ **Observability**: Dependency tracking provides audit trail

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CopilotKit multi-instance performance | Medium | Medium | Lazy-load inactive tabs; limit max tabs (5) |
| Database polling overhead | Low | Low | Use 5s polling; add SSE in future |
| User confusion with tabs | Medium | Medium | Clear labeling; onboarding tooltip |
| Lost parent context | Low | High | Database persistence; session recovery |
| Complex state synchronization | Medium | Medium | Well-tested hook; clear state boundaries |

---

## 8. Success Criteria

- [ ] User can create skill with 2+ missing tools in parallel
- [ ] Tool creation context doesn't leak into skill conversation
- [ ] Visual indicators show completion status on tabs
- [ ] Parent skill notified when child dependencies complete
- [ ] No regression in single-tab artifact creation
- [ ] All existing tests pass
- [ ] New integration tests cover multi-agent flow

---

## 9. Files Created/Modified

### New Files
```
backend/alembic/versions/031_agent_dependencies.py
backend/core/models/agent_dependency.py
backend/services/agent_dependency_service.py
backend/api/routes/agent_dependencies.py
backend/agents/tool_builder.py
backend/agents/state/tool_builder_types.py
backend/agents/tool_builder_prompts.py
backend/tests/test_agent_dependencies.py
backend/tests/services/test_agent_dependency_service.py
backend/tests/api/test_agent_dependencies.py
frontend/src/types/agent-tabs.ts
frontend/src/hooks/use-agent-tabs.ts
frontend/src/components/admin/multi-agent-tabs.tsx
frontend/src/components/admin/multi-agent-wizard.tsx
backend/prompts/tool_builder.md
backend/prompts/mcp_builder.md
```

### Modified Files
```
backend/main.py (register new routes)
backend/prompts/artifact_builder_skill.md (add Phase 4b)
frontend/src/app/(authenticated)/admin/create/page.tsx (use MultiAgentWizard)
```

---

## 10. Appendix

### A. Database Migration Example

See Task 1 in implementation plan for complete migration code.

### B. API Sequence Diagram

```
┌─────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ Frontend│     │Backend API   │     │Agent Service │     │Database  │
└────┬────┘     └──────┬───────┘     └──────┬───────┘     └────┬─────┘
     │                 │                    │                   │
     │ 1. Skill detects missing tools       │                   │
     │─────────────────────────────────────>│                   │
     │                 │ 2. Create deps     │                   │
     │                 │───────────────────────────────────────>│
     │                 │                 │ 3. Return dep IDs     │
     │                 │<───────────────────────────────────────│
     │ 4. Dep IDs      │                    │                   │
     │<─────────────────────────────────────│                   │
     │                 │                    │                   │
     │ 5. User clicks "Create Tool"         │                   │
     │─────────────────────────────────────>│                   │
     │                 │ 6. Mark child started                   │
     │                 │───────────────────────────────────────>│
     │                 │                    │                   │
     │ 7. New tab spawns with Tool Agent    │                   │
     │══════════════════════════════════════════════════════════│
     │                 │                    │                   │
     │ 8. Tool created  │                    │                   │
     │─────────────────────────────────────>│                   │
     │                 │ 9. Mark completed  │                   │
     │                 │───────────────────────────────────────>│
     │                 │                    │                   │
     │ 10. Notify parent tab                │                   │
     │<─────────────────────────────────────│                   │
```

### C. Frontend State Flow

```
1. User starts skill creation
   → createParentTab('skill', 'New Skill')
   → Tab: {id: 'tab-1', agentType: 'skill', isActive: true}

2. Skill detects missing tools
   → POST /api/agent-dependencies (tool: email-fetch)
   → Response: {id: 'dep-123', status: 'pending'}

3. User clicks "Create email-fetch"
   → spawnChildTab('tab-1', 'tool', 'email-fetch', 'dep-123', context)
   → POST /api/agent-dependencies/dep-123/child-started
   → New Tab: {id: 'tab-2', parentTabId: 'tab-1', isActive: true}
   → Previous tab marked isActive: false

4. User creates tool
   → updateTabStatus('tab-2', 'completed')
   → POST /api/agent-dependencies/dep-123/completed
   → Parent tab polls and sees completed status

5. User returns to skill tab
   → switchTab('tab-1')
   → Skill agent sees tool is now available
```

---

## 11. Related Documents

- Implementation Plan: `~/.local/share/opencode/plans/2025-03-13-multi-agent-tab-architecture-phase2.md`
- Current Artifact Builder: `backend/agents/artifact_builder.py`
- Skill Builder Prompts: `backend/prompts/artifact_builder_skill.md`
- Existing Form Component: `frontend/src/components/admin/artifact-wizard.tsx`

---

**Document Version:** 1.0  
**Last Updated:** 2025-03-13  
**Author:** Blitz AgentOS Development Team  
