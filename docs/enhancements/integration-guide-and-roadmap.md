# Blitz AgentOS Enhancement Integration Guide & Roadmap

## Executive Summary

This document integrates two major enhancement proposals for Blitz AgentOS:

1. **Unified Registry** - Consolidates agents, skills, tools, and MCP servers into a single, simplified management interface
2. **MCP Server Enhancement** - Adds support for public MCP servers via CLI installation and stdio transport

**Combined Impact**: A unified, extensible platform that can seamlessly integrate both internal tools and external AI capabilities through a consistent management interface.

---

## Part 1: Proposal Summaries

### 1.1 Unified Registry

**Goal**: Simplify entity management by consolidating 4 separate CRUD implementations into one unified system.

**Key Changes**:
- Single `registry_entries` table replaces agent_definitions, skill_definitions, tool_definitions, mcp_servers
- Simplified status flow: `draft` → `active` → `disabled`
- Latest version only (no complex versioning)
- Unified skill type (instructional + procedure merged)
- Full CRUD: Create, Read, Update, Delete, Clone, Test
- Strategy pattern for type-specific behaviors
- Admin menu consolidation: 13 tabs → 4 tabs

**Benefits**:
- ~60% code reduction
- Consistent UX across all entity types
- Faster development
- Easier maintenance

### 1.2 MCP Server Enhancement

**Goal**: Enable integration with public MCP servers (Context7, NotebookLM, etc.) that require CLI installation.

**Key Changes**:
- 3-tier architecture: Built-in | Public | OpenAPI Bridge
- Stdio transport support (subprocess communication)
- MCP Server Catalog (curated registry)
- One-click installation with env var configuration
- Installation manager for npm/pip packages
- Credential injection via template syntax

**Benefits**:
- Access to ecosystem of 100+ public MCP servers
- No manual CLI management
- Secure credential handling
- Categorized, rated server catalog

---

## Part 2: Integration Architecture

### 2.1 How Both Proposals Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED REGISTRY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Agents    │  │   Skills    │  │    Tools    │             │
│  │  (builtin)  │  │  (unified)  │  │  (multiple  │             │
│  │             │  │             │  │   types)    │             │
│  └─────────────┘  └─────────────┘  └──────┬──────┘             │
│                                            │                     │
│                             ┌──────────────┴──────────────┐     │
│                             │      MCP Servers            │     │
│                             │  ┌──────────────────────┐   │     │
│                             │  │  Built-in (Docker)   │   │     │
│                             │  │  - HTTP+SSE          │   │     │
│                             │  │  - Always-on         │   │     │
│                             │  └──────────────────────┘   │     │
│                             │  ┌──────────────────────┐   │     │
│                             │  │  Public (CLI)        │   │     │
│                             │  │  - Stdio transport   │   │     │
│                             │  │  - On-demand spawn   │   │     │
│                             │  └──────────────────────┘   │     │
│                             │  ┌──────────────────────┐   │     │
│                             │  │  OpenAPI Bridge      │   │     │
│                             │  │  - HTTP proxy        │   │     │
│                             │  │  - Auto-generated    │   │     │
│                             │  └──────────────────────┘   │     │
│                             └─────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP SERVER CATALOG                            │
├─────────────────────────────────────────────────────────────────┤
│  Curated registry of public MCP servers:                         │
│  • Context7 (Upstash)                                           │
│  • NotebookLM (Google)                                          │
│  • GitHub, Slack, Filesystem                                    │
│  • PostgreSQL, Fetch                                            │
│                                                                  │
│  One-click install → Auto-configuration → Tool discovery        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Integration Points

#### Point 1: Registry Entry for MCP Servers

In the unified registry, MCP servers are just another entry type:

```python
# Registry entry for a built-in MCP server
{
  "id": "uuid",
  "type": "mcp_server",
  "name": "crm",
  "display_name": "CRM Integration",
  "config": {
    "server_type": "builtin",
    "transport": "http",
    "url": "http://mcp-crm:8001",
    "auth_token": "{{credentials.crm.api_key}}"
  },
  "status": "active"
}

# Registry entry for a public MCP server
{
  "id": "uuid",
  "type": "mcp_server",
  "name": "context7",
  "display_name": "Context7 Vector Search",
  "config": {
    "server_type": "public",
    "transport": "stdio",
    "installation_source": "npm:@upstash/context7-mcp",
    "env_vars": {
      "UPSTASH_REDIS_REST_URL": "{{credentials.upstash.url}}",
      "UPSTASH_REDIS_REST_TOKEN": "{{credentials.upstash.token}}"
    }
  },
  "status": "active"
}
```

#### Point 2: Unified Management Interface

The Registry tab in the admin panel shows all MCP servers with type indicators:

```
┌────────────────────────────────────────────┐
│ MCP Servers                    [+ Create]  │
├────────────────────────────────────────────┤
│ Name         Type      Status    Actions   │
├────────────────────────────────────────────┤
│ crm          Built-in   Active    ⚙️        │
│ context7     Public     Active    ⚙️ 🔄     │
│ github       Public     Error     ⚙️ 🔧    │
│ custom-api   OpenAPI    Active    ⚙️        │
└────────────────────────────────────────────┘
```

#### Point 3: Shared Tool Registry

Regardless of MCP server type, discovered tools go into the same tool registry:

```python
# From built-in HTTP server
tool: {
  "name": "crm.get_project_status",
  "handler_type": "mcp",
  "mcp_server_id": "...",
  "mcp_tool_name": "get_project_status"
}

# From public stdio server
tool: {
  "name": "context7.vector_search",
  "handler_type": "mcp",
  "mcp_server_id": "...",
  "mcp_tool_name": "vector_search"
}
```

#### Point 4: Catalog Integration

The MCP Catalog is accessible from within the Registry:

```
Registry → MCP Servers → [My Servers] [Catalog]
                          Tab         Tab
```

Clicking "Install from Catalog" creates a new registry entry with `server_type: "public"`.

### 2.3 Data Flow: Installing Context7

```
User clicks "Install" on Context7 card in Catalog
           │
           ▼
┌──────────────────────┐
│ 1. Show install      │
│    dialog with env   │
│    var inputs        │
└──────────────────────┘
           │
           ▼
User enters Upstash credentials
           │
           ▼
┌──────────────────────┐
│ 2. Create registry   │
│    entry:            │
│    type: mcp_server  │
│    config: {         │
│      server_type:    │
│        "public",     │
│      transport:      │
│        "stdio"       │
│    }                 │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ 3. Run installation  │
│    command:          │
│    npx -y            │
│    @upstash/         │
│    context7-mcp      │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ 4. Update status to  │
│    "installed"       │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ 5. Tool discovery    │
│    → Tool registry   │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ 6. Server available  │
│    for agent use     │
└──────────────────────┘
```

---

## Part 3: Unified Roadmap

### Phase 1: Foundation (Week 1)
**Goal**: Database schema and core models

**Tasks**:
- [ ] Create `registry_entries` table (Unified Registry)
- [ ] Add columns to `mcp_servers` table (MCP Enhancement)
- [ ] Create `mcp_server_catalog` table
- [ ] Create migration scripts for existing data
- [ ] Update SQLAlchemy models
- [ ] Create Pydantic config schemas for all types

**Dependencies**: None
**Risk**: Low
**Deliverable**: Database ready for new architecture

### Phase 2: Backend Core (Week 2-3)
**Goal**: Backend implementation for both proposals

**Unified Registry Tasks**:
- [ ] Implement RegistryService with CRUD operations
- [ ] Create type handlers (AgentHandler, SkillHandler, ToolHandler, McpServerHandler)
- [ ] Implement unified API routes (`/api/registry/*`)
- [ ] Add clone and test functionality
- [ ] Write unit tests for registry service

**MCP Enhancement Tasks**:
- [ ] Implement StdioMCPClient
- [ ] Create MCPClientFactory
- [ ] Implement MCPInstaller for npm/pip
- [ ] Add catalog API endpoints
- [ ] Write unit tests for stdio client

**Dependencies**: Phase 1
**Risk**: Medium (stdio client complexity)
**Deliverable**: Backend API ready for frontend integration

### Phase 3: Frontend - Registry (Week 4)
**Goal**: New unified admin interface

**Tasks**:
- [ ] Create new admin layout with 4 tabs (Registry, Access, System, Build)
- [ ] Build Registry sub-pages (Agents, Skills, Tools, MCP)
- [ ] Create generic registry list component
- [ ] Build create/edit dialogs with type-specific fields
- [ ] Implement clone and test UI
- [ ] Add search and filtering

**Dependencies**: Phase 2
**Risk**: Low
**Deliverable**: Working unified registry UI

### Phase 4: Frontend - MCP Catalog (Week 5)
**Goal**: MCP catalog browser and installation

**Tasks**:
- [ ] Build catalog browser with categories
- [ ] Create install dialog with env var inputs
- [ ] Implement installation progress tracking
- [ ] Add server type badges and status indicators
- [ ] Create server logs viewer
- [ ] Add credential template helper

**Dependencies**: Phase 3
**Risk**: Low
**Deliverable**: Full MCP management UI

### Phase 5: Integration & Migration (Week 6)
**Goal**: Connect everything and migrate data

**Tasks**:
- [ ] Populate MCP catalog with 8 initial servers
- [ ] Migrate existing agents/skills/tools to new registry
- [ ] Migrate existing MCP servers with new columns
- [ ] Test end-to-end flows:
  - Create agent → Register in unified registry
  - Install Context7 → Use in agent conversation
  - Clone skill → Modify → Activate
- [ ] Performance testing
- [ ] Security audit

**Dependencies**: Phase 4
**Risk**: Medium (migration complexity)
**Deliverable**: Production-ready system

### Phase 6: Documentation & Launch (Week 7)
**Goal**: Documentation and team onboarding

**Tasks**:
- [ ] Write admin user guide
- [ ] Document registry API
- [ ] Create MCP server development guide
- [ ] Record demo videos
- [ ] Train team on new interface
- [ ] Deploy to production
- [ ] Monitor for issues

**Dependencies**: Phase 5
**Risk**: Low
**Deliverable**: Launched and documented system

---

## Part 4: Implementation Priorities

### 4.1 Must-Have (MVP)

These are critical for the initial release:

1. **Unified Registry Database Schema**
   - Single table structure
   - Migration from old tables
   - Without this, nothing else works

2. **Basic Unified Registry UI**
   - List, create, edit for all types
   - Status management
   - Essential for daily operations

3. **Stdio Transport Support**
   - StdioMCPClient implementation
   - Process lifecycle management
   - Required for public MCP servers

4. **MCP Catalog with 3 Servers**
   - Context7 (most requested)
   - Filesystem (easy to test)
   - Fetch (useful immediately)
   - Prove the concept works

### 4.2 Should-Have (Post-MVP)

These add significant value but aren't blockers:

1. **Clone & Test Features**
   - Nice-to-have for development workflow
   - Can be added incrementally

2. **Full MCP Catalog (8 servers)**
   - Start with 3, add more over time
   - Community can suggest additions

3. **AI Builder Integration**
   - Merge AI Builder + Builder+
   - Can use existing builders during transition

4. **Advanced Env Var Templates**
   - Full credential store integration
   - Start with manual entry

### 4.3 Nice-to-Have (Future)

These can be added later based on usage:

1. **Auto-Installation Verification**
   - Checksums, signatures
   - Start with basic verification

2. **MCP Server Ratings/Reviews**
   - Community feedback
   - Start with curated list

3. **Custom Server Registry**
   - User-contributed servers
   - Start with official catalog

4. **WebSocket Transport**
   - Future transport option
   - Stdio and HTTP cover 99% of cases

---

## Part 5: Risk Mitigation

### Risk 1: Migration Data Loss
**Mitigation**:
- Create full database backup before migration
- Write idempotent migration scripts
- Test migration on staging data
- Keep old tables until verified (soft delete)

### Risk 2: Stdio Process Management Issues
**Mitigation**:
- Implement health checks and auto-restart
- Set resource limits (CPU, memory)
- Add timeout handling
- Log all subprocess activity
- Start with simple servers (filesystem, fetch)

### Risk 3: Security Concerns with Public MCPs
**Mitigation**:
- Run stdio servers in isolated subprocess
- Network policies to restrict outbound calls
- Audit logging for all MCP tool calls
- Admin approval required for new server types

### Risk 4: Frontend Rewrite Takes Too Long
**Mitigation**:
- Build incrementally (one entity type at a time)
- Keep old admin pages accessible during transition
- Use feature flags to toggle new UI
- Focus on Registry first, other tabs later

### Risk 5: Breaking Existing Workflows
**Mitigation**:
- Maintain backward compatibility for API routes
- Gradual rollout with opt-in
- Comprehensive testing with existing agents
- Quick rollback plan

---

## Part 6: Success Metrics

### Technical Metrics
- [ ] All 258 existing tests pass
- [ ] New registry service has 80%+ test coverage
- [ ] MCP stdio client has 70%+ test coverage
- [ ] Frontend build time < 30 seconds
- [ ] API response time < 200ms (p95)

### User Experience Metrics
- [ ] Create new skill: < 2 minutes
- [ ] Install public MCP server: < 3 minutes
- [ ] Find entity in registry: < 10 seconds
- [ ] Admin menu navigation: < 3 clicks to any destination

### Business Metrics
- [ ] 3+ public MCP servers installed in first week
- [ ] 80% of team using unified registry within 2 weeks
- [ ] Zero data loss incidents
- [ ] < 5 critical bugs in first month

---

## Part 7: Decision Log

### Decision 1: Implement Both Proposals Together vs Separately
**Decision**: Together in unified roadmap
**Rationale**: 
- MCP servers are just another registry entry type
- Both require similar database changes
- Frontend admin rewrite benefits both
- Reduces overall migration pain

### Decision 2: Keep Old Tables During Transition
**Decision**: Yes, with soft delete
**Rationale**:
- Safety net in case of migration issues
- Allows rollback if needed
- Can verify data integrity
- Drop old tables in Phase 7 (cleanup)

### Decision 3: Support All 3 MCP Types from Day 1
**Decision**: Yes, but prioritize public servers
**Rationale**:
- Built-in already works (HTTP)
- Public servers are the new capability
- OpenAPI bridge can use existing code
- Shows full vision of unified platform

### Decision 4: Pre-populate Catalog vs Empty
**Decision**: Pre-populate with 8 servers
**Rationale**:
- Immediate value for users
- Demonstrates capability
- Curated list ensures quality
- Can add more based on feedback

---

## Part 8: Quick Reference

### 8.1 File Locations

**New Files to Create**:
```
backend/core/models/registry_entry.py
backend/core/schemas/registry_configs.py
backend/registry/
  ├── service.py
  └── handlers/
      ├── agent_handler.py
      ├── skill_handler.py
      ├── tool_handler.py
      └── mcp_server_handler.py
backend/mcp/
  ├── types.py
  ├── client_factory.py
  ├── stdio_client.py
  └── installer.py
backend/core/models/mcp_server_catalog.py

frontend/app/(authenticated)/admin/
  ├── registry/
  ├── access/
  ├── system/
  └── build/
frontend/components/mcp/
frontend/lib/registry-types.ts
frontend/lib/mcp-types.ts
```

**Modified Files**:
```
backend/core/models/mcp_server.py (add columns)
backend/api/routes/ (new registry routes)
frontend/app/(authenticated)/admin/layout.tsx
```

### 8.2 Key Technologies

- **Database**: PostgreSQL + JSONB for flexible configs
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Frontend**: Next.js + React + TypeScript
- **Process Management**: asyncio subprocess
- **Transport**: HTTP+SSE, stdio, (future: WebSocket)

### 8.3 Testing Strategy

1. **Unit Tests**: All handlers, services, clients
2. **Integration Tests**: API endpoints, database migrations
3. **E2E Tests**: User flows (create, install, use)
4. **Performance Tests**: Registry with 1000+ entries
5. **Security Tests**: Permission checks, credential handling

---

## Part 4: Skill Import Adapter Framework Integration

### 4.1 Overview

The Adapter Framework enables importing skills from multiple sources through a unified interface:
- **AgentSkills repositories** (existing)
- **Claude Code marketplace** (new)
- **ZIP file uploads** (existing)
- **Future**: VS Code marketplace, Hugging Face, GitHub repos, etc.

### 4.2 Integration with Unified Registry

The adapter framework integrates seamlessly with the Unified Registry:

```
User requests import 
    ↓
Adapter auto-detects source type
    ↓
Fetches & normalizes to common format
    ↓
Security scan
    ↓
Creates registry entry (skill type)
    ↓
Stores assets (templates, scripts, refs)
```

### 4.3 Implementation Phases

#### Phase 3.5: Adapter Framework (Week 3-4)
**Parallel with Phase 3 (Frontend)**

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Create base adapter interface | `base.py` with SkillAdapter ABC |
| 3-4 | Implement SkillRepoAdapter | Refactor from existing code |
| 5-6 | Implement ZIP adapter | Direct ZIP upload support |
| 7-8 | Create UnifiedImportService | Single API for all imports |
| 9-10 | Refactor existing imports | All use adapter pattern |

#### Phase 4.5: Claude Marketplace Support (Week 6)
**Parallel with Phase 4 (MCP Catalog)**

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Implement ClaudeMarketAdapter | GitHub ZIP download |
| 3-4 | Add multi-command support | Command extraction from `commands/` |
| 5-6 | Asset storage system | Templates, references, scripts |
| 7-10 | Testing | Import visual-explainer + 3 others |

### 4.4 Files to Create

```
backend/skills/adapters/
  ├── __init__.py              # Package + adapter registration
  ├── base.py                  # Base classes and interfaces
  ├── registry.py              # AdapterRegistry
  ├── skill_repo_adapter.py    # AgentSkills format
  ├── claude_market_adapter.py # Claude marketplace
  ├── zip_adapter.py           # ZIP file uploads
  └── import_service.py        # UnifiedImportService

frontend/components/skills/
  ├── import-source-selector.tsx  # Choose import source
  ├── claude-market-browser.tsx   # Browse Claude marketplace
  └── import-preview-dialog.tsx   # Preview before import
```

### 4.5 API Endpoints

```python
# New unified endpoints
POST /api/skills/import              # Auto-detect source
POST /api/skills/import/claude       # Claude marketplace
POST /api/skills/import/zip          # ZIP upload
POST /api/skills/import/repo         # Skill repository

GET  /api/skills/preview             # Preview before import
GET  /api/skills/catalog/claude      # List Claude marketplace skills
GET  /api/skills/catalog/{repo_id}   # List repo skills
```

### 4.6 User Flow: Import from Claude Marketplace

```
Admin → Registry → Skills → Import Skill
    ↓
Select "Claude Marketplace" tab
    ↓
Enter GitHub URL or browse catalog
    ↓
Preview skill (name, description, commands)
    ↓
Click Import
    ↓
Adapter downloads ZIP, extracts, normalizes
    ↓
Security scan runs
    ↓
Skill created with status "pending_review"
    ↓
Available for activation after review
```

### 4.7 Updated Success Criteria

Add to existing checklist:
- [ ] Can import from Claude marketplace (visual-explainer works)
- [ ] Can import skills with multiple commands
- [ ] Can preview skills before import
- [ ] Auto-detection works for all source types
- [ ] All existing imports work via adapters (no regression)
- [ ] Asset storage handles templates and scripts

### 4.8 Benefits

| Before | After |
|--------|-------|
| Hardcoded to AgentSkills only | Supports unlimited sources |
| Can't import Claude skills | One-click Claude marketplace import |
| Adding sources = core changes | Add adapter = instant support |
| No preview capability | Preview before import |
| Duplicate import code | Single unified service |

---

## Part 9: Next Steps

### Immediate Actions (This Week)
1. ✅ Review this integration guide
2. ✅ Approve roadmap timeline
3. ✅ Set up feature branch
4. ✅ Assign Phase 1 tasks
5. ✅ Schedule daily standups

### Week 1 Goals
- [ ] Database schema created
- [ ] Models implemented
- [ ] Migration scripts tested

### Communication Plan
- **Daily**: Standup (15 min)
- **Weekly**: Demo to stakeholders
- **Bi-weekly**: Architecture review
- **Milestone**: Team celebration at Phase 6

---

## Appendix A: Glossary

- **Registry**: Unified management system for all entity types
- **Entry**: Single item in registry (agent, skill, tool, or MCP server)
- **MCP**: Model Context Protocol - standard for AI tool integration
- **Stdio**: Standard input/output - communication via subprocess pipes
- **Catalog**: Curated list of installable public MCP servers
- **Handler**: Strategy pattern implementation for type-specific logic
- **Transport**: Communication method (HTTP, stdio, WebSocket)

## Appendix B: References

1. [Unified Registry Proposal](./unified-registry-proposal.md)
2. [MCP Server Enhancement Proposal](./mcp-server-enhancement-proposal.md)
3. [Skill Import Adapter Framework](./skill-import-adapter-framework.md)
4. [MCP Specification](https://modelcontextprotocol.io/specification)
5. [Public MCP Servers Directory](https://github.com/modelcontextprotocol/servers)
6. [Claude Code Skills](https://github.com/nicobailon/visual-explainer)

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-XX  
**Status**: Ready for Implementation  
**Owner**: Engineering Team
