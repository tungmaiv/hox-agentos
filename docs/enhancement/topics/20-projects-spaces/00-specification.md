# Projects & Spaces - Design Specification

**Topic:** #20 - Projects/Spaces
**Status:** 🟡 PENDING → ✅ DESIGNED
**Target Version:** v1.7+
**Date:** 2026-03-17
**Priority:** High

---

## Executive Summary

Projects & Spaces provides organizational workspaces and NotebookLM-like personal projects for team collaboration. Users can create personal projects with notes, files, markdown documents, chat with sources, and AI-generated insights. Workspaces serve as team containers for organizing shared projects with granular permissions.

**Key Features:**
- Personal projects with NotebookLM-like features (notes, files, markdown, chat with sources)
- Organized sections/folders for project content
- AI-generated insights with source citations
- Semantic search across project sources (pgvector)
- Workspaces for team collaboration
- Granular permission model (view, edit, full)
- Personal projects can be shared to workspaces
- Public visibility toggle for workspace projects
- Archive, backup, and restore functionality

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Architecture Approach](#2-architecture-approach)
3. [Database Schema](#3-database-schema)
4. [API Design](#4-api-design)
5. [Data Flow & Architecture](#5-data-flow--architecture)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Testing Strategy](#7-testing-strategy)
8. [Implementation Phases](#8-implementation-phases)
9. [Open Questions & Future Work](#9-open-questions--future-work)

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Users can create personal projects | High |
| FR2 | Personal projects contain notes, files, markdown | High |
| FR3 | Projects have organized sections/folders | High |
| FR4 | Chat with project sources (Q&A) | High |
| FR5 | AI-generated insights (summary, analysis, relationships) | High |
| FR6 | Source citations in AI responses | High |
| FR7 | Semantic search across project sources | High |
| FR8 | Workspaces for team collaboration | High |
| FR9 | Workspace admins can create projects within workspace | High |
| FR10 | Workspace admins can add members (users/groups) | High |
| FR11 | Granular project permissions (view, edit, full) | High |
| FR12 | Personal projects can be shared to workspaces | High |
| FR13 | Public visibility toggle for workspace projects | Medium |
| FR14 | Archive projects/workspaces | Medium |
| FR15 | Backup projects (ZIP export) | Medium |
| FR16 | Restore from backup | Medium |

### 1.2 NotebookLM Features

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| NR1 | Multi-source notes | Text notes, file uploads, markdown import | High |
| NR2 | AI summaries | LLM-generated summaries of sources | High |
| NR3 | Q&A with documents | Chat with sources, semantic search | High |
| NR4 | Source citations | AI responses cite source IDs | High |
| NR5 | Organized sections | Hierarchical folder structure | Medium |
| NR6 | Cross-note relationships | Future: keyword citation graph | Low |

**Note:** NotebookLM features available at PROJECT level only. Workspaces are containers of projects.

### 1.3 Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR1 | Permissions checked on every request | Critical |
| NFR2 | Embedding generation async (Celery) | High |
| NFR3 | Semantic search < 500ms | Medium |
| NFR4 | Backup/restore for large projects (>1GB) | Medium |
| NFR5 | Audit logging for all permission changes | High |

---

## 2. Architecture Approach

### 2.1 Selected Approach: Unified Project Model (Approach A)

**Decision:** Single `projects` table with optional `workspace_id`.

**Rationale:**
- Personal projects have `workspace_id = NULL`
- Workspace projects reference a workspace
- Sharing personal projects to workspaces via `project_permissions`
- Simple, unified schema - same structure for all project types
- Natural sharing model without duplication
- Extensible for future features (cross-note keyword graph)

**Alternative Approaches Considered:**

| Approach | Pros | Cons | Decision |
|----------|------|-------|----------|
| **A: Unified Model** | Single schema, clean sharing, extensible | Nullable workspace_id queries | ✅ SELECTED |
| B: Separate Tables | Clear separation, no nulls | Schema duplication, complex sync | ❌ Rejected |
| C: Workspace-Centric | No nulls, all projects unified | Confuses "personal" concept, violates mental model | ❌ Rejected |

---

## 3. Database Schema

### 3.1 Core Tables

#### Workspaces

```sql
CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  created_by UUID NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_workspaces_created_by ON workspaces(created_by);
CREATE INDEX idx_workspaces_status ON workspaces(status);
```

#### Workspace Members

```sql
CREATE TABLE workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  grantee_type TEXT NOT NULL CHECK (grantee_type IN ('user', 'group')),
  grantee_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
  added_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, grantee_type, grantee_id)
);
CREATE INDEX idx_workspace_members_workspace ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_grantee ON workspace_members(grantee_type, grantee_id);
```

#### Projects

```sql
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(id),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  description TEXT,
  is_public BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_workspace ON projects(workspace_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_public ON projects(is_public) WHERE is_public = TRUE;
```

**Key Design Decisions:**
- `workspace_id NULL` = personal project
- `workspace_id NOT NULL` = workspace project
- `is_public` only meaningful for workspace projects
- Personal projects cannot be public (must share to workspace)

#### Project Permissions (Granular Model)

```sql
CREATE TABLE project_permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  grantee_type TEXT NOT NULL CHECK (grantee_type IN ('user', 'group', 'workspace')),
  grantee_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('view', 'edit', 'full')),
  granted_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, grantee_type, grantee_id)
);
CREATE INDEX idx_project_permissions_project ON project_permissions(project_id);
CREATE INDEX idx_project_permissions_grantee ON project_permissions(grantee_type, grantee_id);
```

**Role Hierarchy:**
- `view` = Read-only access (view notes, chat)
- `edit` = Can add/edit notes, manage sources
- `full` = Owner-level access (can manage members, re-share, delete)

### 3.2 NotebookLM Features

#### Project Sections (Organized Folders)

```sql
CREATE TABLE project_sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES project_sections(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  order_index INT NOT NULL DEFAULT 0,
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_project_sections_project ON project_sections(project_id);
CREATE INDEX idx_project_sections_parent ON project_sections(parent_id);
```

**Hierarchy:** `parent_id` enables nested folders/sessions.

#### Project Sources (Notes, Files, Markdown)

```sql
CREATE TABLE project_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  section_id UUID REFERENCES project_sections(id) ON DELETE SET NULL,
  type TEXT NOT NULL CHECK (type IN ('note', 'file', 'markdown', 'chat_result')),
  title TEXT NOT NULL,
  content TEXT,
  file_path TEXT,
  file_size BIGINT,
  file_mime_type TEXT,
  embedding vector(1024),
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_project_sources_project ON project_sources(project_id);
CREATE INDEX idx_project_sources_section ON project_sources(section_id);
CREATE INDEX idx_project_sources_vec ON project_sources
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Key Design Decisions:**
- Single table for all source types (note, file, markdown, chat_result)
- `embedding` column for semantic search (pgvector, bge-m3, 1024-dim)
- `file_path` references Storage Service (Topic #19)
- Embedding generation async via Celery task

#### Project Chats (Q&A with Sources)

```sql
CREATE TABLE project_chats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  sources_cited JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_project_chats_project ON project_chats(project_id, created_at DESC);
CREATE INDEX idx_project_chats_user ON project_chats(user_id);
```

**`sources_cited` Format:**
```json
[ "source-uuid-1", "source-uuid-2" ]
```

#### Project AI Insights

```sql
CREATE TABLE project_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_id UUID REFERENCES project_sources(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('summary', 'analysis', 'relationship', 'citation_graph')),
  content TEXT NOT NULL,
  metadata JSONB,
  generated_by TEXT NOT NULL DEFAULT 'ai',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_project_insights_project ON project_insights(project_id);
CREATE INDEX idx_project_insights_source ON project_insights(source_id);
```

**Insight Types:**
- `summary` = AI-generated summary of source
- `analysis` = Deep analysis, key points
- `relationship` = Cross-source relationships
- `citation_graph` = Future: keyword citation graph

### 3.3 Backup & Restore

#### Project Backups

```sql
CREATE TABLE project_backups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  backup_path TEXT NOT NULL,
  size_bytes BIGINT,
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_project_backups_project ON project_backups(project_id);
```

**Backup Format (ZIP):**
```
backup.zip
├── project.json           { metadata, sections, chats, insights }
├── sources/
│   ├── note-001.json
│   ├── file-001.pdf
│   └── markdown-001.md
└── files/
    └── uploaded-files/
```

---

## 4. API Design

### 4.1 Workspaces API

**`GET /api/workspaces`** - List accessible workspaces
- Permission: Authenticated user
- Returns: Personal workspaces (created_by=user) + memberships

**`POST /api/workspaces`** - Create workspace
- Request: `{ name, description }`
- Permission: Authenticated user

**`GET /api/workspaces/{workspace_id}`** - Get workspace details
- Permission: Workspace member

**`PUT /api/workspaces/{workspace_id}`** - Rename workspace
- Request: `{ name }`
- Permission: Workspace admin

**`DELETE /api/workspaces/{workspace_id}`** - Archive workspace
- Permission: Workspace admin
- Effect: `status = 'archived'`

**`POST /api/workspaces/{workspace_id}/members`** - Add member
- Request: `{ grantee_type ('user'|'group'), grantee_id, role ('admin'|'member') }`
- Permission: Workspace admin

**`DELETE /api/workspaces/{workspace_id}/members/{member_id}`** - Remove member
- Permission: Workspace admin

### 4.2 Projects API

**`GET /api/projects`** - List projects
- Query: `workspace_id` (optional)
- Returns: Personal + Workspace + Shared projects
- Permission: Authenticated user

**`POST /api/projects`** - Create project
- Request: `{ name, description, workspace_id (optional) }`
- Validation: If `workspace_id`, user must be workspace admin
- Permission: Authenticated user

**`GET /api/projects/{project_id}`** - Get project details
- Permission: Owner OR (workspace project AND (is_public OR permission exists))

**`PUT /api/projects/{project_id}`** - Update project
- Permission: Owner OR (permission.role IN ('edit', 'full'))

**`DELETE /api/projects/{project_id}`** - Archive project
- Permission: Owner OR workspace admin OR permission.role='full'
- Effect: `status = 'archived'`

**`POST /api/projects/{project_id}/public`** - Toggle public visibility
- Request: `{ is_public: boolean }`
- Permission: Owner OR workspace admin
- Validation: `workspace_id` must NOT be NULL

### 4.3 Project Permissions API

**`POST /api/projects/{project_id}/permissions`** - Grant permission
- Request: `{ grantee_type ('user'|'group'|'workspace'), grantee_id, role ('view'|'edit'|'full') }`
- Permission: Owner OR permission.role='full'

**`DELETE /api/projects/{project_id}/permissions/{permission_id}`** - Revoke permission
- Permission: Owner OR permission.role='full'

**`GET /api/projects/{project_id}/permissions`** - List permissions
- Permission: Owner OR workspace admin OR permission.role='full'

### 4.4 Project Sections API

**`GET /api/projects/{project_id}/sections`** - List sections (tree)
- Permission: Project view access
- Returns: Hierarchical tree structure

**`POST /api/projects/{project_id}/sections`** - Create section
- Request: `{ name, parent_id (optional), order_index }`
- Permission: Project edit access

**`PUT /api/sections/{section_id}`** - Update section
- Request: `{ name, parent_id, order_index }`
- Permission: Project edit access

**`DELETE /api/sections/{section_id}`** - Delete section
- Permission: Project edit access
- Effect: Cascades to sources

### 4.5 Project Sources API

**`GET /api/projects/{project_id}/sources`** - List sources
- Query: `section_id` (optional), `type` (optional), `q` (search query)
- Permission: Project view access
- If `q`: Semantic search via pgvector

**`POST /api/projects/{project_id}/sources`** - Create source
- Request (note): `{ type: 'note', section_id, title, content }`
- Request (markdown): `{ type: 'markdown', section_id, title, content }`
- Request (file): `{ type: 'file', section_id, file_id, title }`
- Permission: Project edit access
- Side effect: Triggers Celery embedding task

**`PUT /api/sources/{source_id}`** - Update source
- Request: `{ title, content, section_id }`
- Permission: Project edit access
- Side effect: Re-generates embedding

**`DELETE /api/sources/{source_id}`** - Delete source
- Permission: Project edit access

**`POST /api/sources/{source_id}/insights`** - Generate AI insight
- Request: `{ type ('summary'|'analysis'|'relationship') }`
- Permission: Project edit access
- Side effect: Async Celery task calls LLM

### 4.6 Project Chats API

**`GET /api/projects/{project_id}/chats`** - List chat history
- Permission: Project view access

**`POST /api/projects/{project_id}/chats`** - Send message (RAG)
- Request: `{ role: 'user', content }`
- Permission: Project view access
- Processing:
  1. Store user message
  2. Semantic search over `project_sources`
  3. Call LLM with sources context
  4. Parse citations from LLM response
  5. Store assistant message with `sources_cited`
- Returns: Assistant message with citations

**`DELETE /api/projects/{project_id}/chats`** - Clear chat history
- Permission: Project edit access

### 4.7 Project Insights API

**`GET /api/projects/{project_id}/insights`** - List insights
- Query: `source_id` (optional), `type` (optional)
- Permission: Project view access

**`GET /api/insights/{insight_id}`** - Get insight details
- Permission: Project view access

**`DELETE /api/insights/{insight_id}`** - Delete insight
- Permission: Project edit access

### 4.8 Backup / Archive / Restore API

**`POST /api/projects/{project_id}/backup`** - Create backup
- Permission: Owner (personal) OR workspace admin (workspace)
- Processing: Async Celery task
  1. Export project data to JSON
  2. Download files from Storage Service
  3. Package into ZIP
  4. Upload to Storage Service
  5. Create `project_backups` record
- Returns: Backup object with status ('pending'|'complete'|'failed')

**`GET /api/projects/{project_id}/backups`** - List backups
- Permission: Owner OR workspace admin

**`DELETE /api/projects/{project_id}/backups/{backup_id}`** - Delete backup
- Permission: Owner OR workspace admin

**`POST /api/projects/{project_id}/restore`** - Restore from backup
- Request: `{ backup_id, new_name (optional) }`
- Permission: Owner OR workspace admin
- Processing: Async Celery task
  1. Download ZIP from Storage Service
  2. Extract and parse JSON
  3. Auto-rename on name conflict
  4. Create new project
  5. Restore data + files
  6. Generate embeddings
- Returns: Restored project object

### 4.9 Left Navigation Integration

**`GET /api/user/context`** - Get navigation context
- Permission: Authenticated user
- Returns:
  ```json
  {
    "my_projects": {
      "total": 12,
      "recent": [/* 5 most recent */]
    },
    "workspaces": [
      {
        "id": "...",
        "name": "Marketing Team",
        "role": "admin",
        "project_count": 8,
        "public_projects": 5,
        "shared_projects": 3
      }
    ]
  }
  ```

---

## 5. Data Flow & Architecture

### 5.1 Directory Structure

```
backend/
├── api/
│   └── routes/
│       ├── workspaces.py
│       ├── projects.py
│       ├── project_sections.py
│       ├── project_sources.py
│       ├── project_chats.py
│       ├── project_insights.py
│       └── backups.py
├── core/
│   └── schemas/
│       ├── workspace.py
│       ├── project.py
│       ├── project_permission.py
│       └── backup.py
├── services/
│   ├── project_service.py
│   ├── permission_service.py
│   ├── embedding_service.py
│   └── backup_service.py
├── scheduler/
│   └── tasks.py
└── memory/
    └── long_term.py

frontend/
├── src/
│   ├── app/
│   │   ├── projects/
│   │   ├── workspaces/
│   │   └── project/
│   │       ├── [id]/
│   │       │   ├── sources/
│   │       │   ├── chat/
│   │       │   └── insights/
│   │       └── settings/
│   ├── components/
│   │   ├── project/
│   │   └── workspace/
│   └── hooks/
│       ├── use-projects.ts
│       ├── use-workspaces.ts
│       └── use-project-chat.ts
```

### 5.2 Key Data Flows

#### Flow 1: Create Source + Embedding

```
POST /api/projects/{id}/sources
  ↓
project_sources.py → project_service.create_source()
  1. Validate edit permission
  2. Insert source (embedding = NULL)
  3. Trigger Celery: embed_source(source_id)
  ↓
Celery worker (async)
  1. Fetch source content
  2. Generate embedding via EmbeddingService.embed([content])
  3. Update project_sources.embedding
```

#### Flow 2: Chat with Sources (RAG)

```
POST /api/projects/{id}/chats
  ↓
project_chats.py → project_service.chat_with_sources()
  1. Store user message
  2. Semantic search over project_sources:
     ```sql
     SELECT id, title, content
     FROM project_sources
     WHERE project_id = $1
       AND embedding IS NOT NULL
     ORDER BY embedding <-> $query_embedding
     LIMIT 5
     ```
  3. Construct prompt: "Context: {sources} Question: {query}"
  4. Call LLM (blitz/master)
  5. Parse citations from response
  6. Store assistant message with sources_cited JSONB
  ↓
Frontend renders chat bubble with source links
```

#### Flow 3: Share Personal Project to Workspace

```
POST /api/projects/{id}/permissions
  Request: { grantee_type: 'workspace', grantee_id, role: 'view' }
  ↓
permission_service.grant_permission()
  1. Validate user has 'full' or owner
  2. Check target workspace exists
  3. Insert project_permissions
  ↓
Workspace members see project in GET /api/projects?workspace_id={id}
```

**Key:** `workspace_id` remains NULL (still personal project). Workspace members gain access via permissions.

#### Flow 4: Backup Project

```
POST /api/projects/{id}/backup
  ↓
backup_service.create_backup()
  ↓
Celery task: backup_project(backup_id)
  1. Fetch project data
  2. Download files from Storage Service
  3. Package into ZIP
  4. Upload ZIP to Storage Service
  5. Update project_backups.status = 'complete'
```

#### Flow 5: Restore Project

```
POST /api/projects/{id}/restore
  Request: { backup_id, new_name (optional) }
  ↓
backup_service.restore_project()
  ↓
Celery task: restore_project(project_id, backup_id, new_name)
  1. Download ZIP from Storage Service
  2. Extract and parse project.json
  3. Auto-rename on conflict
  4. Create new project (new UUID)
  5. Restore sections, sources, chats, insights
  6. Upload files to Storage Service
  7. Generate embeddings
  8. Update project_backups.restored_project_id
```

### 5.3 Permission Model Architecture

```python
# services/permission_service.py

class PermissionService:
    @staticmethod
    async def check_project_access(
        user_id: UUID,
        project_id: UUID,
        required_role: str = 'view'
    ) -> bool:
        project = await get_project(project_id)

        # Owner check
        if project.owner_id == user_id:
            return True

        # Workspace project: check public OR permission
        if project.workspace_id is not None:
            if project.is_public:
                return True
            workspace_member = await get_workspace_member(project.workspace_id, user_id)
            if workspace_member:
                return await _has_permission_role(project_id, user_id, required_role)

        # Personal project shared to user (or workspace user is in)
        return await _has_permission_role(project_id, user_id, required_role)

    @staticmethod
    def _role_sufficient(have: str, need: str) -> bool:
        role_hierarchy = {'view': 1, 'edit': 2, 'full': 3}
        return role_hierarchy.get(have, 0) >= role_hierarchy.get(need, 0)
```

---

## 6. Error Handling Strategy

### 6.1 Error Categories

#### Permission Errors (403)

```python
HTTPException(
    status_code=403,
    detail={
        "code": "PERMISSION_DENIED",
        "message": "You do not have permission to access this project",
        "project_id": str(project_id)
    }
)
```

#### Not Found Errors (404)

```python
HTTPException(
    status_code=404,
    detail={
        "code": "WORKSPACE_NOT_FOUND",
        "message": "Workspace not found",
        "workspace_id": str(workspace_id)
    }
)
```

#### Validation Errors (422)

```python
HTTPException(
    status_code=422,
    detail={
        "code": "VALIDATION_ERROR",
        "message": "Invalid request data",
        "errors": pydantic_errors
    }
)
```

#### Quota Errors (507)

```python
HTTPException(
    status_code=507,
    detail={
        "code": "QUOTA_EXCEEDED",
        "message": "Storage quota exceeded. Cannot create backup.",
        "limit_mb": limit,
        "current_mb": current
    }
)
```

### 6.2 Error Codes Reference

| Code | Status | Description | User Action |
|------|--------|-------------|-------------|
| `PERMISSION_DENIED` | 403 | Insufficient permissions | Contact owner |
| `WORKSPACE_NOT_FOUND` | 404 | Workspace does not exist | Check ID |
| `PROJECT_NOT_FOUND` | 404 | Project does not exist | Check ID |
| `INVALID_WORKSPACE` | 400 | Workspace validation failed | Verify exists |
| `NOT_WORKSPACE_ADMIN` | 403 | User not workspace admin | Contact admin |
| `VALIDATION_ERROR` | 422 | Invalid request data | Fix input |
| `QUOTA_EXCEEDED` | 507 | Storage quota exceeded | Contact admin |
| `BACKUP_FAILED` | 500 | Backup creation failed | Try later |
| `RESTORE_FAILED` | 500 | Restore operation failed | Check backup |
| `PGVECTOR_MISSING` | 500 | pgvector not installed | Contact admin |

### 6.3 Logging Strategy

All errors logged via structlog:

```python
logger.warning(
    "project_access_denied",
    project_id=str(project_id),
    user_id=str(user_id),
    required_role='edit'
)
```

**Never log:** Credentials, access tokens, sensitive user data

---

## 7. Testing Strategy

### 7.1 Backend Testing

**Unit Tests:**
- Permission service (100% coverage - critical security gate)
- Project service (95% coverage)
- Backup service (85% coverage)

**Integration Tests:**
- API routes (90% coverage)
- Celery tasks (85% coverage)
- RAG chat flow with mocked LLM

**Test Structure:**
```
backend/tests/
├── api/
│   ├── test_workspaces.py
│   ├── test_projects.py
│   ├── test_project_sources.py
│   ├── test_project_chats.py
│   └── test_backups.py
├── services/
│   ├── test_permission_service.py
│   ├── test_project_service.py
│   └── test_backup_service.py
└── scheduler/
    └── test_tasks.py
```

### 7.2 Frontend E2E Testing

**Scenarios:**
1. Create personal project
2. Create workspace project (admin vs member)
3. Share personal project to workspace
4. Create note and chat with sources
5. Semantic search across sources
6. Generate AI insights
7. Backup and restore project

**Test Structure:**
```
frontend/e2e/tests/
├── project-creation.spec.ts
├── project-sharing.spec.ts
├── workspace-management.spec.ts
├── source-management.spec.ts
├── chat-with-sources.spec.ts
└── backup-restore.spec.ts
```

### 7.3 Coverage Targets

| Layer | Target | Notes |
|-------|---------|-------|
| Permission Service | 100% | Critical security gate |
| Project Service | 95% | Business logic |
| API Routes | 90% | Edge cases, error paths |
| Celery Tasks | 85% | Retry logic, failures |
| E2E Scenarios | 80% | Critical journeys |

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Backend:**
- Database schema (migrations)
- Workspaces API (CRUD, members)
- Projects API (CRUD, permissions)
- Permission service

**Frontend:**
- Workspace list page
- Project list page
- Left navigation integration

**Deliverable:** Basic workspace/project management

### Phase 2: NotebookLM Core (Week 3-4)

**Backend:**
- Project sources API (notes, files, markdown)
- Project sections API (hierarchical folders)
- Embedding generation (Celery)
- Semantic search (pgvector)

**Frontend:**
- Source grid view
- Note editor (markdown)
- File upload (Storage Service integration)
- Section/folder tree

**Deliverable:** NotebookLM-like source management

### Phase 3: Chat & Insights (Week 5-6)

**Backend:**
- Project chats API (RAG)
- Project insights API
- LLM integration (blitz/master)
- Source citation parsing

**Frontend:**
- Chat panel with sources
- AI insight cards
- Source citation display
- Search bar (semantic + text)

**Deliverable:** Q&A with sources + AI insights

### Phase 4: Advanced Features (Week 7-8)

**Backend:**
- Public visibility toggle
- Archive functionality
- Backup/restore (ZIP)
- Celery task monitoring

**Frontend:**
- Project settings page
- Backup management UI
- Public/private badges
- Archive view

**Deliverable:** Backup/restore + archive

### Phase 5: Polish & Hardening (Week 9-10)

**Testing:**
- Unit tests (95%+ coverage)
- E2E tests (80%+ coverage)
- Load testing (large projects)

**Frontend:**
- UX refinements
- Error handling
- Loading states

**Deliverable:** Production-ready release

---

## 9. Open Questions & Future Work

### 9.1 Future Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Cross-note keyword graph | Maintain graph for all keyword citations | Low (v1.8+) |
| Real-time collaboration | Multi-user editing of notes | Medium (v1.8+) |
| Project templates | Pre-built project structures (e.g., meeting notes) | Low (v1.9+) |
| Version history | Track source changes, restore versions | Medium (v1.9+) |
| Export formats | PDF, Markdown, HTML export | Low (v1.9+) |
| Advanced search | Boolean operators, date ranges, filters | Low (v1.9+) |

### 9.2 Open Questions

1. **Storage quota:** Per-workspace or per-user limits?
2. **Backup retention:** How long to keep backups? Auto-delete old backups?
3. **Large file handling:** Streaming uploads for files > 100MB?
4. **LLM rate limiting:** Per-project or per-user limits?

---

## Appendix: Key Design Decisions

### ADR-001: Unified Project Model (Approach A)

**Decision:** Single `projects` table with nullable `workspace_id`.

**Rationale:**
- Simplifies schema (no duplication)
- Natural sharing model (add workspace to permissions)
- Personal projects remain personal even when shared
- Extensible for future features

**Consequence:**
- Permission checks need `workspace_id IS NULL OR workspace_id = $w` logic
- Personal projects cannot be public (must share to workspace)

### ADR-002: pgvector for Semantic Search

**Decision:** Use pgvector extension in PostgreSQL for semantic search.

**Rationale:**
- Matches AgentOS memory subsystem architecture
- No separate vector database needed
- Single database simplifies operations
- bge-m3 embedding (1024-dim) already in use

**Consequence:**
- All sources require embedding generation (async Celery)
- Search performance depends on PostgreSQL tuning

### ADR-003: Celery for Async Operations

**Decision:** Use Celery for embedding generation, insights, backups, restores.

**Rationale:**
- Avoids blocking API requests
- Large projects may take significant time
- Retries on failure (exponential backoff)
- Matches existing AgentOS scheduler architecture

**Consequence:**
- Requires task queue (Redis) and worker monitoring
- Frontend needs polling or SSE for task status

### ADR-004: Granular Permission Model (Option B)

**Decision:** 3-tier permission model (view, edit, full).

**Rationale:**
- Fine-grained control for team collaboration
- Hierarchy simplifies role checks
- Explicit re-sharing control (full role only)

**Consequence:**
- More complex permission checks
- Requires UI for role selection when sharing

---

**Document Status:** ✅ COMPLETE - Ready for Implementation Planning
**Next Step:** Invoke `writing-plans` skill to create detailed implementation plan
**Implementation Target:** v1.7+
