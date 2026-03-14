# Runtime Permission Approval (HITL) - Design Document

**Status:** ✅ Approved for Implementation  
**Target:** v1.4  
**Priority:** High  
**Estimated Effort:** 1 Phase (5-6 Plans)  
**Author:** Architecture Team  
**Date:** 2026-03-14  

---

## Executive Summary

Transform Gate 3 (Tool ACL) from a binary deny mechanism into an **escalatable Human-in-the-Loop (HITL) permission approval system**. When a skill/workflow attempts to use a tool the user lacks permission for, execution pauses, notifies an admin, and resumes automatically upon approval—creating persistent ACL entries for future use.

**Key Innovation:** Unlike the existing manual HITL node, this system **automatically triggers** on permission denial, provides **rich context** for informed decisions, and creates **persistent permissions** (not one-time approvals).

---

## Current State vs Target State

### Current State (As-Is)

```
┌─────────────────────────────────────────────────────────────┐
│  CURRENT: Binary Permission Check                            │
├─────────────────────────────────────────────────────────────┤
│  Skill tries to use "channel.telegram.send"                 │
│  ↓                                                          │
│  Gate 2 (RBAC): Check role permissions                      │
│  ↓                                                          │
│  Gate 3 (ACL): check_tool_acl() returns False               │
│  ↓                                                          │
│  ❌ HARD DENY: Tool call fails with 403                     │
│  ↓                                                          │
│  Workflow dies, user stuck, no escalation path              │
└─────────────────────────────────────────────────────────────┘
```

**Problems:**
- No path for users to gain permission at runtime
- Workflows fail mid-execution due to permission gaps
- Admins must proactively grant permissions before need arises
- Poor UX: user must stop → contact admin → wait → restart

### Target State (To-Be)

```
┌─────────────────────────────────────────────────────────────┐
│  TARGET: Escalatable HITL Permission Approval                │
├─────────────────────────────────────────────────────────────┤
│  Skill tries to use "channel.telegram.send"                 │
│  ↓                                                          │
│  Gate 2 (RBAC): User lacks "channel:telegram"               │
│  ↓                                                          │
│  Gate 3 (ACL): No explicit allow → PermissionRequest created│
│  ↓                                                          │
│  ⚠️  PERMISSION PENDING: Execution paused (LangGraph)       │
│  ↓                                                          │
│  📬 Admin notified via UI (bell icon/badge)                 │
│  ↓                                                          │
│  👤 Admin reviews rich context → Approves/Rejects           │
│  ↓                                                          │
│  ✅ APPROVED:                                               │
│     • Create ToolAcl entry (with expiration)                │
│     • Resume execution automatically                        │
│     • Retry tool call successfully                          │
│  ❌ REJECTED:                                               │
│     • Create ToolAcl entry (allowed=False)                  │
│     • Execution fails with clear message                    │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Users can self-discover and request needed permissions
- Workflows don't fail—they pause and wait
- Admins make informed decisions with full context
- One approval grants persistent access (with expiration options)
- Auto-approve rules reduce admin burden for low-risk scenarios

---

## Detailed Design Decisions

### Decision 1: Permission Duration — Both Temporary AND Permanent

**Rationale:** Different use cases require different permission lifetimes. Session-only is safe for one-off tasks, while permanent is appropriate for core job functions.

**Implementation:**

```python
# Database Schema Extension
class ToolAcl:
    # Existing fields...
    allowed: bool
    
    # NEW FIELDS
    duration_type: Enum["session", "time_limited", "permanent"]
    expires_at: datetime | None  # NULL for permanent
    granted_at: datetime
    granted_by: UUID  # Admin who approved
    request_id: UUID  # Link to PermissionRequest

# Duration Types:
# - session: Expires when user logs out (session end)
# - time_limited: Expires at expires_at
# - permanent: Never expires (unless manually revoked)
```

**Default Behavior:**
- Default duration: **72 hours** (configurable in system config)
- Admin can choose at approval time: Session / 72h / Permanent / Custom

**Expiration Management:**
- Background Celery job runs daily to clean expired entries
- On tool use: Check `expires_at` before `allowed`, treat expired as denied
- Expired entries kept in DB for audit trail (soft delete)

---

### Decision 2: Who Can Approve — Permission-Based, Not Role-Based

**Problem Identified:** Current system uses role names (`it-admin`) which breaks in local-only auth mode (no Keycloak).

**Solution:** Use `system:admin` permission instead of role check.

**Rationale:**
- **Identity-agnostic:** Works whether auth is Keycloak, local, or LDAP
- **Flexible assignment:** Admin can grant `system:admin` to any role
- **Aligns with architecture:** Gate 2 RBAC already permission-based
- **Future-proof:** Easy to delegate to team leads without code changes

**Implementation:**

```python
# rbac.py — Add new permissions
DEFAULT_ROLE_PERMISSIONS = {
    "it-admin": {
        # ... existing permissions ...
        "system:admin",        # Can access admin dashboard
        "permission:approve",  # Can approve permission requests
        "permission:manage",   # Can manage auto-approve rules
    },
    "team-lead": {
        # ... existing permissions ...
        "permission:approve",  # Can approve for their team
    }
}

# Approval check in permission_request.py
async def can_approve_requests(user_context: UserContext, session: AsyncSession) -> bool:
    return await has_permission(user_context, "permission:approve", session)
```

**Frontend Check:**
```typescript
// Instead of: if (roles.includes("it-admin"))
// Use: if (hasPermission("permission:approve"))
```

---

### Decision 3: Full Context for Informed Decisions

**Rationale:** Admins need rich context to make informed approval decisions, especially when auto-approve rules don't apply.

**Context Provided:**

```json
{
  "request": {
    "id": "uuid",
    "requested_at": "2026-03-14T10:30:00Z",
    "status": "pending"
  },
  "requester": {
    "user_id": "uuid",
    "username": "john.doe",
    "email": "john@blitz.vn",
    "roles": ["employee", "sales-team"],
    "groups": ["apac-sales"],
    "trust_score": 85,
    "account_age_days": 120
  },
  "permission": {
    "tool_name": "channel.telegram.send",
    "tool_description": "Send messages via Telegram Bot API",
    "tool_category": "communication",
    "required_permission": "channel:telegram",
    "sensitivity": "medium",
    "sandbox_required": false
  },
  "trigger_context": {
    "source_type": "skill",  // skill | workflow | agent | chat
    "skill_id": "uuid",
    "skill_name": "Daily Sales Report",
    "skill_owner": "john.doe",
    "workflow_id": "uuid",
    "workflow_name": "Morning Digest",
    "conversation_id": "uuid",
    "message_preview": "User asked: 'Send this report to Telegram...'",
    "execution_history": [...]
  },
  "risk_assessment": {
    "tool_sensitivity": "medium",
    "user_trust_score": 85,
    "previous_denials": 2,
    "previous_approvals": 5,
    "auto_approve_eligible": false,
    "similar_requests_count": 3
  },
  "suggested_action": "approve_with_limit"  // ML-based suggestion (future)
}
```

**UI Components:**
- **Compact Card:** User, tool, time, quick approve/reject
- **Expandable Details:** Full JSON context, risk indicators
- **Similar Requests:** "3 other users requested this tool this week"
- **Trust Score Visualization:** Gauge showing user reliability

---

### Decision 4: Auto-Approve Rule Engine

**Rationale:** Reduce admin burden by automatically approving low-risk, routine permission requests based on configurable rules.

**Rule Structure:**

```yaml
# Example auto-approve rules
rules:
  - id: "rule-sales-telegram"
    name: "Sales team can use communication tools"
    enabled: true
    priority: 100
    conditions:
      all:
        - field: "user.roles"
          operator: "contains"
          value: "sales-team"
        - field: "tool.category"
          operator: "equals"
          value: "communication"
        - field: "tool.sensitivity"
          operator: "in"
          value: ["low", "medium"]
        - field: "user.trust_score"
          operator: "gte"
          value: 70
    action:
      type: "approve"
      duration: "permanent"
    
  - id: "rule-manager-reports"
    name: "Managers auto-approve reports"
    enabled: true
    priority: 90
    conditions:
      all:
        - field: "user.roles"
          operator: "contains"
          value: "manager"
        - field: "tool.name"
          operator: "starts_with"
          value: "reports."
    action:
      type: "approve"
      duration: "session"
    
  - id: "rule-high-sensitivity-manual"
    name: "High sensitivity always manual"
    enabled: true
    priority: 10  # Low priority = evaluated last
    conditions:
      all:
        - field: "tool.sensitivity"
          operator: "equals"
          value: "high"
    action:
      type: "require_approval"  # Always manual
```

**Supported Operators:**
- `equals`, `not_equals`
- `contains`, `not_contains` (for arrays)
- `starts_with`, `ends_with`
- `matches_regex`
- `in`, `not_in`
- `gt`, `gte`, `lt`, `lte` (for numbers)
- `between` (for dates/numbers)

**Rule Evaluation:**
- Rules evaluated in priority order (highest first)
- First matching rule wins
- If no rule matches → require manual approval
- Rules can be tested in "dry run" mode (show what would happen without acting)

**Admin UI:**
- Visual rule builder (drag-and-drop conditions)
- Test against specific users
- Enable/disable rules
- View rule hit statistics

---

### Decision 5: Configurable Timeout with Escalation

**Rationale:** Permission requests shouldn't hang indefinitely. Configurable timeout with escalation ensures requests get attention.

**Timeout Configuration:**

```python
# platform_config table entries
PERMISSION_REQUEST_TIMEOUT_HOURS = 72  # Default
PERMISSION_REQUEST_TIMEOUT_ACTION = "expire_and_fail"  # Default
PERMISSION_REQUEST_ESCALATION_ENABLED = true

# Timeout Actions:
# - expire_and_fail: Request expires, execution fails
# - expire_and_retry: Request expires, retry with escalation
# - expire_and_fallback: Use fallback tool if configured
# - notify_and_extend: Notify admin, auto-extend 24h
```

**Escalation Path:**

```
T+0h:   Request created → Notify primary approver (permission:approve holder)
T+24h:  Still pending → Escalate to manager (if user has manager)
T+48h:  Still pending → Escalate to it-admin (system:admin holder)
T+72h:  Timeout reached → Execute timeout_action
```

**Per-Tool Override:**
```python
# Tools can define custom timeout behavior
class ToolDefinition:
    # Existing fields...
    
    # NEW FIELDS
    permission_timeout_hours: int | None  # Override default
    permission_timeout_action: str | None  # Override default
    escalation_contacts: list[UUID] | None  # Specific admins for this tool
```

**Notification Channels:**
- In-app bell icon (primary)
- Email notification (escalation)
- Optional: Slack/Teams DM for critical tools

---

## Architecture Overview

### New Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME PERMISSION APPROVAL                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Database   │    │   Backend    │    │   Frontend   │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │              │
│  ┌──────▼───────┐    ┌──────▼───────┐    ┌──────▼───────┐      │
│  │permission_   │    │security/     │    │Admin         │      │
│  │requests      │◄──►│permission_   │◄──►│Permission    │      │
│  │              │    │request.py    │    │Requests Page │      │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤      │
│  │auto_approve_ │    │security/     │    │Rule Builder  │      │
│  │rules         │◄──►│auto_approve. │◄──►│UI            │      │
│  │              │    │py            │    │              │      │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤      │
│  │tool_acl      │    │api/routes/   │    │Bell Icon     │      │
│  │(extended)    │◄──►│permission_   │◄──►│Notifications │      │
│  │              │    │requests.py   │    │              │      │
│  └──────────────┘    ├──────────────┤    └──────────────┘      │
│                      │scheduler/    │                          │
│                      │celery_tasks. │                          │
│                      │py            │                          │
│                      │(timeout/     │                          │
│                      │escalation)   │                          │
│                      └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Integration Points

**1. Gate 3 Enhancement (`security/acl.py`)**
```python
async def check_tool_acl_with_hitr(
    user_id: UUID,
    tool_name: str,
    session: AsyncSession,
    context: PermissionContext | None = None,
) -> PermissionResult:
    """
    Check tool ACL with HITL support.
    
    Returns:
        - ALLOWED: User has permission (existing or newly granted)
        - DENIED: Explicitly denied
        - PENDING: Request created, awaiting approval
    """
    # 1. Check existing ACL
    existing = await check_tool_acl(user_id, tool_name, session)
    if existing:
        return PermissionResult.ALLOWED
    
    # 2. Check for pending request
    pending = await get_pending_request(user_id, tool_name, session)
    if pending:
        return PermissionResult.PENDING
    
    # 3. Check auto-approve rules
    auto_result = await evaluate_auto_approve_rules(user_id, tool_name, context, session)
    if auto_result.action == "approve":
        await grant_permission(user_id, tool_name, auto_result.duration, session)
        return PermissionResult.ALLOWED
    
    # 4. Create permission request (HITL)
    request = await create_permission_request(user_id, tool_name, context, session)
    await notify_admins(request, session)
    return PermissionResult.PENDING
```

**2. Executor Integration (`skills/executor.py`)**
```python
async def execute_tool_step(...) -> StepResult:
    # ... existing code ...
    
    # Gate 3 with HITL
    result = await check_tool_acl_with_hitr(
        user_id, tool_name, session, 
        context=build_permission_context(state, step)
    )
    
    if result == PermissionResult.PENDING:
        # Pause execution using LangGraph interrupt
        return await pause_for_permission_request(request_id)
    
    if result == PermissionResult.DENIED:
        return StepResult.error("Permission denied for tool: {tool_name}")
    
    # Continue with tool execution...
```

**3. LangGraph Interrupt Integration**
```python
async def pause_for_permission_request(request_id: UUID) -> StepResult:
    """Pause graph execution and wait for admin approval."""
    from langgraph.types import interrupt
    
    result = interrupt({
        "type": "permission_request",
        "request_id": str(request_id),
        "message": "Waiting for permission approval..."
    })
    
    # Execution resumes here after approval
    if result.get("approved"):
        return StepResult.retry()  # Retry the tool call
    else:
        return StepResult.error("Permission request rejected")
```

---

## API Endpoints

### Admin Endpoints

```
GET    /api/admin/permission-requests          # List pending requests
GET    /api/admin/permission-requests/{id}     # Get request details
POST   /api/admin/permission-requests/{id}/approve  # Approve request
POST   /api/admin/permission-requests/{id}/reject   # Reject request
GET    /api/admin/permission-requests/stats    # Request statistics

GET    /api/admin/auto-approve-rules           # List rules
POST   /api/admin/auto-approve-rules           # Create rule
GET    /api/admin/auto-approve-rules/{id}      # Get rule
PUT    /api/admin/auto-approve-rules/{id}      # Update rule
DELETE /api/admin/auto-approve-rules/{id}      # Delete rule
POST   /api/admin/auto-approve-rules/{id}/test # Test rule

GET    /api/admin/permission-requests/notifications  # SSE stream
```

### User Endpoints

```
GET    /api/permission-requests                # My requests
GET    /api/permission-requests/{id}/status    # Check request status
```

### Internal Endpoints

```
POST   /api/internal/permission-requests/{id}/resume  # Resume after approval
```

---

## Database Schema

### New Tables

```sql
-- Permission requests queue
CREATE TABLE permission_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,  -- No FK (Keycloak users)
    tool_name VARCHAR(255) NOT NULL,
    requester_context JSONB NOT NULL,  -- Full context
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, approved, rejected, expired
    
    -- Timing
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,  -- Request timeout
    
    -- Resolution
    resolved_by UUID,
    resolution_notes TEXT,
    duration_type VARCHAR(50),  -- session, time_limited, permanent
    granted_duration_hours INTEGER,  -- NULL for permanent/session
    
    -- Escalation tracking
    escalation_level INTEGER DEFAULT 0,
    last_escalation_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_perm_req_user ON permission_requests(user_id);
CREATE INDEX idx_perm_req_status ON permission_requests(status);
CREATE INDEX idx_perm_req_tool ON permission_requests(tool_name);
CREATE INDEX idx_perm_req_expires ON permission_requests(expires_at) WHERE status = 'pending';

-- Auto-approve rules
CREATE TABLE auto_approve_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,
    
    -- Conditions (stored as JSON for flexibility)
    conditions JSONB NOT NULL,
    
    -- Action
    action_type VARCHAR(50) NOT NULL,  -- approve, require_approval
    action_duration VARCHAR(50),  -- session, time_limited, permanent
    action_duration_hours INTEGER,
    
    -- Metadata
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMP WITH TIME ZONE,
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_auto_rule_enabled ON auto_approve_rules(enabled);
CREATE INDEX idx_auto_rule_priority ON auto_approve_rules(priority);
```

### Extended Tables

```sql
-- Extend tool_acl with expiration and provenance
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS duration_type VARCHAR(50);
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS granted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS granted_by UUID;
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS request_id UUID REFERENCES permission_requests(id);
ALTER TABLE tool_acl ADD COLUMN IF NOT EXISTS is_auto_approved BOOLEAN DEFAULT false;
```

---

## UI/UX Design

### Admin Permission Requests Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Permission Requests                                [⚙️ Rules]  │
├─────────────────────────────────────────────────────────────────┤
│  [Pending ▼] [All Tools ▼] [Search...                 ]        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 👤 john.doe                    ⏱️ 2 hours ago              │  │
│  │                                                           │  │
│  │ 🛠️ channel.telegram.send                                  │  │
│  │    "Send messages via Telegram Bot API"                   │  │
│  │                                                           │  │
│  │ 📋 Context: Daily Sales Report skill (owned by john.doe)  │  │
│  │    💬 "User asked: 'Send this report to Telegram...'"     │  │
│  │                                                           │  │
│  │ 🏷️ User: employee, sales-team | Trust: 85 | Prev denials: 2│  │
│  │                                                           │  │
│  │ [✅ Approve ▼] [❌ Reject] [🔍 Details]                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 👤 jane.smith                  ⏱️ 5 minutes ago            │  │
│  │ 🛠️ reports.sales.monthly                                  │  │
│  │ 📋 Context: Manager requesting reports tool               │  │
│  │ 🏷️ User: manager | Trust: 92 | Auto-approve eligible ✓    │  │
│  │                                                           │  │
│  │ [✅ Auto-Approve] [🔍 Details]                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Approval Dropdown

```
[✅ Approve ▼]
  ├── 🕐 This session only
  ├── 🕐 72 hours (default)
  ├── 📅 7 days
  ├── 📅 30 days
  ├── ♾️  Permanent
  └── ⚙️  Custom...
```

### Rule Builder UI

```
┌─────────────────────────────────────────────────────────────────┐
│  Auto-Approve Rules                               [+ New Rule]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Rule: Sales team can use communication tools                   │
│  Priority: 100 | Status: ✅ Enabled | Hits: 42                  │
│                                                                  │
│  IF:                                                             │
│    [user.roles] [contains] [sales-team]                        │
│    AND [tool.category] [equals] [communication]                │
│    AND [tool.sensitivity] [in] [low, medium]                   │
│    AND [user.trust_score] [>=] [70]                            │
│  THEN:                                                           │
│    [Approve] for [Permanent]                                   │
│                                                                  │
│  [Edit] [Test] [Disable] [Delete]                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Bell Icon Notifications

```
┌──────────┐
│  🔔 3   │  ← Shows pending count
└────┬─────┘
     │
     ▼
┌──────────────────────────────┐
│ Permission Requests          │
├──────────────────────────────┤
│ • john.doe → telegram.send   │
│ • jane.smith → reports.sales │
│ • mike.jones → email.send    │
│                              │
│ [View All →]                 │
└──────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (2 plans)

**Plan 1: Database & Models**
- Create `permission_requests` table
- Create `auto_approve_rules` table
- Extend `tool_acl` table
- SQLAlchemy models and migrations

**Plan 2: Backend Core**
- `security/permission_request.py` - Request lifecycle
- `security/auto_approve.py` - Rule engine
- API routes for listing/approving/rejecting
- Unit tests

### Phase 2: Integration (2 plans)

**Plan 3: Gate 3 Integration**
- Extend `check_tool_acl()` with HITL support
- LangGraph interrupt integration
- Executor modifications
- Error handling and retry logic

**Plan 4: Real-time & Notifications**
- WebSocket/SSE for live updates
- Bell icon badge API
- Email notifications for escalation
- Celery tasks for timeout/escalation

### Phase 3: UI & Rules (2 plans)

**Plan 5: Admin UI**
- Permission requests page
- Request detail view
- Approve/reject flows
- Bell icon integration

**Plan 6: Rule Builder**
- Rule list UI
- Visual rule builder
- Test mode
- Rule statistics

---

## Success Criteria

- [ ] Permission denial triggers HITL pause (not hard failure)
- [ ] Admin sees notification within 5 seconds of request
- [ ] One-click approval creates persistent ACL entry
- [ ] Execution resumes automatically after approval
- [ ] Auto-approve rules process requests within 1 second
- [ ] Timeout behavior is configurable and reliable
- [ ] Audit log captures: request → approval → usage
- [ ] Works for both canvas workflows and conversational skills
- [ ] 100% backward compatible (existing ACL behavior unchanged)
- [ ] Works in both Keycloak and local-only auth modes

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Admin overwhelmed with requests | High | Auto-approve rules + bulk approval + delegation |
| Request timeouts cause UX issues | Medium | Configurable timeouts + fallback behaviors |
| Rule engine performance | Medium | Cache compiled rules + priority ordering |
| Security: Approval bypass | Critical | Multiple enforcement points + audit logging |
| State management complexity | Medium | LangGraph checkpointer + idempotent operations |

---

## Future Enhancements

1. **ML-Based Suggestions**: Predict approval likelihood based on historical patterns
2. **Bulk Operations**: Approve multiple similar requests at once
3. **Time-Based Rules**: "Auto-approve during business hours only"
4. **Delegation Chains**: "If manager doesn't respond in 24h, escalate to director"
5. **Just-in-Time Permissions**: "Approve for next 5 uses only"
6. **Usage Analytics**: Dashboard showing permission request trends

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-14  
**Status:** Ready for Implementation Planning
