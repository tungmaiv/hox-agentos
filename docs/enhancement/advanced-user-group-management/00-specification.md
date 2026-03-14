# Advanced User & Group Management with External Identity Integration

**Status:** ✅ Approved for Implementation  
**Topic:** #12 (New Topic)  
**Target:** v1.4  
**Priority:** High  
**Estimated Effort:** 1 Phase (6 plans)  
**Author:** Architecture Team  
**Date:** 2026-03-14  

---

## Executive Summary

Transform AgentOS user management into an enterprise-grade identity system with **direct group-based permissions** (replacing role indirection) and **seamless external identity provider integration** (Keycloak/AD/LDAP). 

**Core Innovation:** Clear separation between **Identity** (who you are, managed externally) and **Permissions** (what you can do, managed in AgentOS).

---

## Current State vs Target State

### Current State (As-Is)

**Permission Model (Overly Complex):**
```
User → [Direct Roles] → Permissions
     ↘ [Groups] → Roles → Permissions
```

**Problems:**
- Multiple paths to permissions (direct + via groups)
- Confusing: "Group has roles, roles have permissions"
- Hard to audit: "Why can Alice do X?" → Trace through multiple hops
- No external identity integration
- Groups only assignable at user creation time
- Can't edit user groups after creation
- No group detail view or member management

**Current UI Gaps:**
- ❌ Can't edit user groups after creation
- ❌ No inline "add user to group"
- ❌ Groups show only member count, not who
- ❌ No group detail page
- ❌ Permissions hidden behind roles
- ❌ No external IDP sync

### Target State (To-Be)

**Permission Model (Clean & Direct):**
```
External IDP (Keycloak/AD)
    ↓
Global Groups (read-only mirror)
    ↓ [Admin maps global → local]
Local Groups (permission-bearing)
    ↓
Permissions (tools, workflows)
    ↓
User Access
```

**Benefits:**
- **Single mental model:** "This group lets you do X"
- **Clear audit trail:** One hop (Group → Permissions)
- **IT-friendly:** Manage identities in existing systems
- **Flexible:** Map external groups to specific tool permissions
- **Auto-provisioning:** New hires automatically get access

**UI Improvements:**
- ✅ Edit user groups anytime via modal
- ✅ Group detail pages with tabs (Members, Permissions, Settings)
- ✅ Visual permission list (expanded, not hidden)
- ✅ External sync status indicators
- ✅ Permission source attribution

---

## Detailed Design Decisions

### Decision 1: Direct Group Permissions (No Role Indirection)

**Rationale:**
Roles add an unnecessary abstraction layer for AgentOS use case. Most enterprises want to say "Engineers can use these tools" not "Engineers have the 'employee' role which has these permissions."

**Implementation:**

```python
# OLD: Groups have roles
class LocalGroup:
    name: str
    roles: list[str]  # "employee", "manager"

# NEW: Groups have permissions directly
class LocalGroup:
    name: str
    permissions: list[str]  # "tool:email", "workflow:create"
```

**Migration Path:**
- Existing group roles → Convert to equivalent permissions
- Example: Group with role "employee" → Group with permissions ["chat", "tool:email", "tool:calendar"]

**UI Representation:**
```
Engineering Team (12 members, 8 permissions)
├─ Permissions:
│  ☑ chat
│  ☑ tool:email
│  ☑ tool:calendar
│  ☑ workflow:create
│  ☑ workflow:execute
│  ☐ workflow:approve
│  ☐ tool:admin
│  ☐ sandbox:execute
└─ Sources:
   • Manual assignments: 2 users
   • Keycloak mapping: 10 users
```

---

### Decision 2: Global vs Local Group Separation

**Concept:**

| Layer | Source | Editable | Purpose |
|-------|--------|----------|---------|
| **Global Groups** | Keycloak/AD/LDAP | ❌ Read-only | Identity mirror |
| **Local Groups** | AgentOS | ✅ Full control | Permission management |
| **Mappings** | Admin configured | ✅ Manageable | Bridge between layers |

**How It Works:**

```
┌──────────────────────────────────────────────────────────────┐
│ KEYCLOAK / ACTIVE DIRECTORY                                  │
│ Groups: /engineering, /engineering/backend, /sales          │
│ Users: alice (member of /engineering/backend)               │
└──────────────────────────────────────────────────────────────┘
                              ↓ Login + Sync
┌──────────────────────────────────────────────────────────────┐
│ AGENTOS GLOBAL GROUPS (Auto-created, read-only)             │
│ • keycloak:/engineering (source=keycloak, external_id=...)  │
│ • keycloak:/engineering/backend                             │
│ • keycloak:/sales                                           │
└──────────────────────────────────────────────────────────────┘
                              ↓ Admin Mapping
┌──────────────────────────────────────────────────────────────┐
│ AGENTOS LOCAL GROUPS (Permission-bearing)                   │
│ • "Engineering Team"                                        │
│   ├─ Mapped to: keycloak:/engineering                       │
│   ├─ Permissions: tool:email, workflow:create              │
│   └─ Members: alice (auto), bob (manual)                   │
│                                                              │
│ • "Backend Developers"                                      │
│   ├─ Mapped to: keycloak:/engineering/backend              │
│   ├─ Permissions: sandbox:execute, tool:admin              │
│   └─ Members: alice (auto)                                 │
└──────────────────────────────────────────────────────────────┘
                              ↓ Permission Resolution
┌──────────────────────────────────────────────────────────────┐
│ ALICE'S EFFECTIVE PERMISSIONS                               │
│ From "Engineering Team": tool:email, workflow:create       │
│ From "Backend Developers": sandbox:execute, tool:admin     │
│ ─────────────────────────────────────────────────────────  │
│ Total: 4 permissions                                        │
└──────────────────────────────────────────────────────────────┘
```

**Auto-Sync Behavior:**
- When Alice logs in, Keycloak sends groups: `["/engineering", "/engineering/backend"]`
- AgentOS creates Global Groups if not exist
- AgentOS finds Local Groups mapped to these Global Groups
- Alice automatically becomes member of "Engineering Team" and "Backend Developers"
- Alice gets all permissions from both groups

**Manual Override:**
- Admin can add Alice to additional Local Groups manually
- Admin can remove Alice from auto-mapped groups (creates exception)
- Changes in Keycloak reflected on next login

---

### Decision 3: Permission Visibility — Show All Expanded

**Rationale:**
Admins need to see exactly what access a group grants without clicking through layers.

**UI Implementation:**

```
┌─────────────────────────────────────────────────────────────┐
│ Engineering Team - Permissions                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Communication Tools                                         │
│ ☑ chat           - Access to chat interface                │
│ ☑ tool:email     - Send and receive emails                 │
│ ☑ tool:calendar  - View and manage calendars               │
│                                                             │
│ Workflow Tools                                              │
│ ☑ workflow:create  - Create new workflows                  │
│ ☑ workflow:execute - Run existing workflows                │
│ ☐ workflow:approve - Approve workflow executions           │
│                                                             │
│ Admin Tools                                                 │
│ ☐ tool:admin       - Administrative functions              │
│ ☐ sandbox:execute  - Execute code in sandbox               │
│                                                             │
│ [Save Changes]                                              │
└─────────────────────────────────────────────────────────────┘
```

**Categories:**
Permissions organized by category for easier management:
- **Communication:** chat, tool:email, tool:calendar
- **Workflows:** workflow:create, workflow:execute, workflow:approve
- **Admin:** tool:admin, sandbox:execute, registry:manage
- **Channels:** channel:telegram, channel:whatsapp, channel:teams

---

### Decision 4: UI Pattern — Modal for Group Assignment

**Rationale:**
Modal provides focused context without navigation. Better than inline for potentially long group lists.

**Modal Design:**

```
┌─────────────────────────────────────────────────────────────┐
│ Manage Groups: alice@corp.com              [X]             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Current Groups:                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ☑ Engineering Team (keycloak)               [Remove]   │ │
│ │ ☑ Backend Developers (keycloak)             [Remove]   │ │
│ │ ☑ Special Projects (manual)                 [Remove]   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Add to Group:                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Search: [____________________]                          │ │
│ │                                                         │ │
│ │ Available Groups:                                       │ │
│ │ ☐ Data Science Team                                    │ │
│ │ ☐ Marketing Team                                       │ │
│ │ ☐ Contractors                                          │ │
│ │ ☐ Executives                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                          [Save Changes]           │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Shows current groups with source (keycloak/manual)
- Search available groups
- Visual distinction for synced vs manual
- Remove button for current groups
- Checkbox for available groups

---

### Decision 5: Group Detail Page Navigation

**Rationale:**
Clicking group row navigates to detail page for full management.

**Page Structure:**

```
/admin/groups/{id}

┌─────────────────────────────────────────────────────────────┐
│ ← Back to Groups                                             │
│                                                              │
│ Engineering Team                              [Edit] [Delete]│
│ 12 members • 8 permissions • Synced from Keycloak           │
│                                                              │
│ [Members (12)] [Permissions (8)] [Settings] ← Tabs          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ MEMBERS TAB                                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Search members... [________________]    [+ Add Member] │ │
│ │                                                         │ │
│ │ User            Email          Source      Joined      │ │
│ │ ─────────────────────────────────────────────────────  │ │
│ │ Alice Smith    alice@corp.com  Keycloak    Auto        │ │
│ │ Bob Jones      bob@corp.com    Keycloak    Auto        │ │
│ │ Charlie Doe    charlie@corp.com Manual     2024-03-14  │ │
│ │                                                         │ │
│ │ Showing 3 of 12 members        [1] [2] [3] ... [5]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ PERMISSIONS TAB                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                                                         │ │
│ │ Communication                                           │ │
│ │ ☑ chat                                                  │ │
│ │ ☑ tool:email                                            │ │
│ │ ☑ tool:calendar                                         │ │
│ │                                                         │ │
│ │ Workflows                                               │ │
│ │ ☑ workflow:create                                       │ │
│ │ ☑ workflow:execute                                      │ │
│ │ ☐ workflow:approve                                      │ │
│ │                                                         │ │
│ │ [Edit Permissions]                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ SETTINGS TAB                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Name: Engineering Team (cannot change)                 │ │
│ │ Description: Engineering department members            │ │
│ │                                                         │ │
│ │ External Mappings:                                      │ │
│ │ keycloak:/engineering ✓ Auto-sync enabled              │ │
│ │                                                         │ │
│ │ [Add Mapping] [Disable Sync]                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### Decision 6: External Identity Provider Integration

**Supported Providers (Phase 1):**
1. **Keycloak** (already integrated)
2. **Active Directory / LDAP** (future)

**Sync Strategy:**

**Option A: Real-time Sync (Recommended)**
- On every login, fetch fresh groups from IDP
- Update Global Groups
- Update Local Group memberships
- Pros: Always up-to-date
- Cons: Slightly slower login

**Option B: Periodic Sync**
- Background job syncs every 15 minutes
- Login uses cached groups
- Pros: Fast login
- Cons: Stale data possible

**Hybrid Approach:**
- Real-time on login (for immediate access)
- Background sync for bulk updates
- Configurable per provider

**Configuration:**

```yaml
# platform_config
identity_providers:
  keycloak:
    enabled: true
    sync_mode: "realtime"  # realtime | periodic | manual
    group_mappings:
      - global: "/engineering"
        local: "Engineering Team"
      - global: "/engineering/backend"
        local: "Backend Developers"
    auto_create_mappings: true  # Suggest new mappings
```

---

## Architecture

### Database Schema

#### New Tables

```sql
-- ============================================
-- GLOBAL GROUPS (External IDP mirror)
-- ============================================
CREATE TABLE global_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,  -- 'keycloak', 'ldap', 'ad'
    external_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(source, external_id)
);

CREATE INDEX idx_global_groups_source ON global_groups(source);
CREATE INDEX idx_global_groups_external ON global_groups(source, external_id);

-- ============================================
-- GROUP PERMISSIONS (Direct permission assignment)
-- ============================================
CREATE TABLE group_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES local_groups(id) ON DELETE CASCADE,
    permission VARCHAR(255) NOT NULL,
    granted_by UUID,  -- Admin user ID
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- Optional
    
    UNIQUE(group_id, permission)
);

CREATE INDEX idx_group_permissions_group ON group_permissions(group_id);
CREATE INDEX idx_group_permissions_perm ON group_permissions(permission);

-- ============================================
-- GLOBAL-TO-LOCAL GROUP MAPPINGS
-- ============================================
CREATE TABLE group_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_group_id UUID NOT NULL REFERENCES global_groups(id) ON DELETE CASCADE,
    local_group_id UUID NOT NULL REFERENCES local_groups(id) ON DELETE CASCADE,
    auto_sync BOOLEAN DEFAULT true,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(global_group_id, local_group_id)
);

CREATE INDEX idx_group_mappings_global ON group_mappings(global_group_id);
CREATE INDEX idx_group_mappings_local ON group_mappings(local_group_id);

-- ============================================
-- ENHANCED USER-GROUP MEMBERSHIP
-- ============================================
CREATE TABLE local_user_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES local_users(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES local_groups(id) ON DELETE CASCADE,
    source VARCHAR(50) DEFAULT 'manual',  -- 'manual', 'keycloak', 'ldap', 'ad'
    global_group_id UUID REFERENCES global_groups(id),
    is_exception BOOLEAN DEFAULT false,  -- Manually removed from auto-sync
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, group_id)
);

CREATE INDEX idx_local_user_groups_user ON local_user_groups(user_id);
CREATE INDEX idx_local_user_groups_group ON local_user_groups(group_id);
CREATE INDEX idx_local_user_groups_source ON local_user_groups(source);
```

#### Modified Tables

```sql
-- Add sync tracking to local_groups
ALTER TABLE local_groups 
    ADD COLUMN IF NOT EXISTS external_sync_enabled BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS sync_source VARCHAR(50);

-- Note: local_group_roles table will be deprecated
-- Migration will copy role permissions to group_permissions
```

---

### API Endpoints

#### Global Groups (Read-Only)

```
GET    /api/admin/global-groups
       Query: source=keycloak&search=engineering
       Response: {
         "items": [{
           "id": "uuid",
           "source": "keycloak",
           "external_id": "/engineering",
           "name": "Engineering",
           "member_count": 45,
           "mappings": [{
             "local_group_id": "uuid",
             "local_group_name": "Engineering Team"
           }]
         }]
       }

GET    /api/admin/global-groups/{id}
GET    /api/admin/global-groups/{id}/members
```

#### Local Group Permissions

```
GET    /api/admin/local/groups/{id}/permissions
       Response: {
         "permissions": ["chat", "tool:email", "workflow:create"],
         "by_category": {
           "communication": ["chat", "tool:email"],
           "workflows": ["workflow:create"]
         }
       }

PUT    /api/admin/local/groups/{id}/permissions
       Body: {
         "permissions": ["chat", "tool:email", "workflow:create"]
       }
       Note: Replaces all permissions

POST   /api/admin/local/groups/{id}/permissions
       Body: { "permission": "tool:calendar" }

DELETE /api/admin/local/groups/{id}/permissions/{permission}
```

#### Group Member Management

```
GET    /api/admin/local/groups/{id}/members
       Query: source=manual&search=alice
       Response: {
         "items": [{
           "user_id": "uuid",
           "username": "alice",
           "email": "alice@corp.com",
           "source": "keycloak",
           "global_group_id": "uuid",
           "joined_at": "2024-03-14T10:00:00Z"
         }]
       }

POST   /api/admin/local/groups/{id}/members
       Body: { "user_id": "uuid", "source": "manual" }

DELETE /api/admin/local/groups/{id}/members/{user_id}
       Note: Creates exception if user was auto-synced
```

#### Group Mappings

```
POST   /api/admin/local/groups/{id}/mappings
       Body: { "global_group_id": "uuid", "auto_sync": true }

DELETE /api/admin/local/groups/{id}/mappings/{global_group_id}

PUT    /api/admin/local/groups/{id}/mappings/{global_group_id}
       Body: { "auto_sync": false }
```

#### User Group Management

```
GET    /api/admin/local/users/{id}/groups
       Response: {
         "groups": [{
           "id": "uuid",
           "name": "Engineering Team",
           "source": "keycloak",
           "permissions": ["chat", "tool:email"]
         }]
       }

PUT    /api/admin/local/users/{id}/groups
       Body: { "group_ids": ["uuid1", "uuid2"] }
       Note: Manual groups only, preserves auto-synced

POST   /api/admin/local/users/{id}/groups/{group_id}
       Body: { "source": "manual" }

DELETE /api/admin/local/users/{id}/groups/{group_id}
```

---

### Permission Resolution Logic

```python
async def resolve_user_permissions(
    user_id: UUID,
    session: AsyncSession
) -> set[str]:
    """
    Resolve all permissions for a user from:
    1. Direct user permissions (rare)
    2. Local group permissions (primary)
    """
    permissions = set()
    
    # 1. Direct user permissions (for edge cases)
    direct_perms = await session.execute(
        select(user_permissions.c.permission)
        .where(user_permissions.c.user_id == user_id)
    )
    permissions.update([r[0] for r in direct_perms])
    
    # 2. Get user's groups
    user_groups = await session.execute(
        select(local_user_groups.c.group_id)
        .where(
            and_(
                local_user_groups.c.user_id == user_id,
                local_user_groups.c.is_exception == false()
            )
        )
    )
    group_ids = [r[0] for r in user_groups]
    
    # 3. Get permissions from all groups
    if group_ids:
        group_perms = await session.execute(
            select(group_permissions.c.permission)
            .where(group_permissions.c.group_id.in_(group_ids))
        )
        permissions.update([r[0] for r in group_perms])
    
    return permissions


async def sync_user_groups_from_keycloak(
    user_id: UUID,
    keycloak_groups: list[str],
    session: AsyncSession
) -> None:
    """
    Sync user's group memberships from Keycloak on login.
    """
    for group_path in keycloak_groups:
        # 1. Find or create global group
        global_group = await session.execute(
            select(GlobalGroup)
            .where(
                and_(
                    GlobalGroup.source == "keycloak",
                    GlobalGroup.external_id == group_path
                )
            )
        )
        global_group = global_group.scalar_one_or_none()
        
        if not global_group:
            # Auto-create global group
            global_group = GlobalGroup(
                source="keycloak",
                external_id=group_path,
                name=group_path.split("/")[-1]
            )
            session.add(global_group)
            await session.flush()
        
        # 2. Find mappings to local groups
        mappings = await session.execute(
            select(GroupMapping)
            .where(GroupMapping.global_group_id == global_group.id)
        )
        
        for mapping in mappings.scalars():
            if not mapping.auto_sync:
                continue
            
            # 3. Add user to local group (if not exception)
            existing = await session.execute(
                select(LocalUserGroup)
                .where(
                    and_(
                        LocalUserGroup.user_id == user_id,
                        LocalUserGroup.group_id == mapping.local_group_id
                    )
                )
            )
            
            if not existing.scalar_one_or_none():
                membership = LocalUserGroup(
                    user_id=user_id,
                    group_id=mapping.local_group_id,
                    source="keycloak",
                    global_group_id=global_group.id,
                    is_exception=False
                )
                session.add(membership)
```

---

## Frontend Components

### New Components

```
frontend/src/components/admin/user-management/
├── ManageGroupsModal.tsx         # Group assignment modal
├── PermissionChecklist.tsx       # Expandable permission list
├── GroupMemberList.tsx           # Member table with sources
├── GlobalGroupBadge.tsx          # Shows external source
├── PermissionCategory.tsx        # Grouped permission section
├── SyncStatusIndicator.tsx       # Shows sync health
└── GroupMappingEditor.tsx        # Map global → local

frontend/src/app/(authenticated)/admin/
├── groups/
│   └── [id]/
│       └── page.tsx              # Group detail page
├── users/
│   └── [id]/
│       └── page.tsx              # User detail page (enhanced)
```

### Component Details

**ManageGroupsModal.tsx**
```typescript
interface ManageGroupsModalProps {
  userId: string;
  username: string;
  currentGroups: UserGroup[];
  availableGroups: LocalGroup[];
  onSave: (groupIds: string[]) => void;
  onClose: () => void;
}

interface UserGroup {
  id: string;
  name: string;
  source: "manual" | "keycloak" | "ldap";
  permissions: string[];
  canRemove: boolean;
}
```

**PermissionChecklist.tsx**
```typescript
interface PermissionChecklistProps {
  permissions: Permission[];
  selected: string[];
  onChange: (selected: string[]) => void;
  categories?: PermissionCategory[];
  readonly?: boolean;
}

interface Permission {
  id: string;
  name: string;
  description: string;
  category: string;
}
```

---

## Implementation Phases

### Phase 1: Backend Foundation (2 plans)

**Plan 1: Database Migration**
- Create new tables: `global_groups`, `group_permissions`, `group_mappings`
- Migrate existing `local_group_roles` → `group_permissions`
- Add columns to `local_groups` and `local_user_groups`
- Backward compatibility layer

**Plan 2: Backend APIs**
- Global groups CRUD (read-only for external)
- Group permissions endpoints
- Group member management
- Permission resolution update
- Keycloak sync integration

### Phase 2: Group Management UI (2 plans)

**Plan 3: Group Detail Page**
- Create `/admin/groups/[id]/page.tsx`
- Members tab with search and pagination
- Permissions tab with categorized checklist
- Settings tab with mappings
- Add "View" links from groups list

**Plan 4: Permission Management**
- PermissionChecklist component
- Category organization
- Save/validation logic
- Permission preview

### Phase 3: User Management Enhancement (2 plans)

**Plan 5: User Group Modal**
- ManageGroupsModal component
- Current vs available groups
- Source indicators (keycloak/manual)
- Search and filter
- Save changes

**Plan 6: Keycloak Integration**
- Global group sync on login
- Auto-mapping suggestions
- Sync status dashboard
- Exception handling (manual removals)

---

## Migration Strategy

### Step 1: Database Migration (Zero Downtime)

```sql
-- Create new tables alongside existing
CREATE TABLE group_permissions (...);

-- Copy existing data
INSERT INTO group_permissions (group_id, permission, granted_at)
SELECT 
    g.id as group_id,
    rp.permission,
    NOW() as granted_at
FROM local_groups g
JOIN local_group_roles lgr ON g.id = lgr.group_id
JOIN role_permissions rp ON lgr.role = rp.role;

-- Add triggers to keep in sync during transition
```

### Step 2: Dual-Read Period

```python
# Backend reads from both old and new
def get_group_permissions(group_id: UUID) -> list[str]:
    # Try new table first
    new_perms = db.query(group_permissions).filter(...).all()
    if new_perms:
        return [p.permission for p in new_perms]
    
    # Fallback to old (during transition)
    return get_permissions_via_roles(group_id)
```

### Step 3: Frontend Cutover

- Deploy new UI
- Feature flag: `USE_NEW_GROUP_MANAGEMENT`
- Gradual rollout to admins

### Step 4: Cleanup

- Remove old role-based group permissions
- Drop `local_group_roles` table
- Remove backward compatibility code

---

## Success Criteria

- [ ] Groups have permissions assigned directly (not through roles)
- [ ] Group detail page accessible from groups list
- [ ] Members tab shows all members with source attribution
- [ ] Permissions tab shows categorized permission checklist
- [ ] Settings tab shows external mappings
- [ ] User "Manage Groups" modal allows add/remove
- [ ] Keycloak groups sync automatically on login
- [ ] Global groups created automatically from Keycloak
- [ ] Admin can map global groups to local groups
- [ ] Permission resolution includes all group permissions
- [ ] UI shows clear distinction: manual vs synced groups
- [ ] Backward compatibility maintained during migration
- [ ] Audit log tracks all permission changes

---

## Enterprise Readiness Checklist

| Feature | Status | Notes |
|---------|--------|-------|
| **Identity Integration** | ✅ | Keycloak/AD sync |
| **Permission Audit** | ✅ | Who granted what, when |
| **Permission Expiration** | ✅ | Time-limited access |
| **Group Hierarchy** | ⚠️ Future | Nested groups |
| **Bulk Operations** | ⚠️ Future | Mass user updates |
| **Group Templates** | ⚠️ Future | Create from template |
| **Self-Service** | ⚠️ Future | User requests access |
| **Access Reviews** | ⚠️ Future | Periodic certification |

---

## Future Enhancements

1. **Group Hierarchy**
   - Parent/child group relationships
   - Permission inheritance
   - Visual org chart

2. **Attribute-Based Access Control (ABAC)**
   - Rules like: "If user.department = 'Engineering' AND time < 18:00"
   - Dynamic permission calculation

3. **Access Requests**
   - Users request group membership
   - Approval workflow
   - Time-limited access grants

4. **Access Reviews**
   - Quarterly access certification
   - Managers review team access
   - Auto-removal for unused permissions

5. **Advanced Sync**
   - LDAP/Active Directory support
   - SCIM provisioning
   - Real-time webhooks

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-14 | Initial design |

---

**Next Steps:**
1. Review and approve design
2. Create implementation plans (PLAN.md files)
3. Schedule database migration window
4. Begin Phase 1 development

**Questions or concerns?** Document should be reviewed by:
- Backend team (API design)
- Frontend team (UI components)
- Security team (permission model)
- DevOps (migration strategy)
