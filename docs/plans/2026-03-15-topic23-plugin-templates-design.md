# Topic #23: Plugin Templates Design Document

**Date:** 2026-03-15  
**Status:** Approved for Implementation  
**Target Release:** v1.7+  
**Author:** AgentOS Design Team  
**Related Topics:** #21 (Universal Integration), #5 (Universal Skill Import)

---

## Executive Summary

Plugin Templates enable companies to rapidly deploy pre-configured collections of AI agents, skills, and tools tailored to specific business functions or industries. This feature transforms AgentOS from a platform requiring manual agent configuration to an out-of-the-box solution with curated "AI teams" ready for immediate use.

**Key Capabilities:**
- **Template Management:** Import/export ZIP-based templates, enable/disable, version control
- **Template Gallery:** Self-service discovery and agent subscription for users
- **Marketing Template (v1):** Complete AI marketing department with 10 specialized agents
- **Deployment Flexibility:** Admin-assigned or user self-service access models
- **Full Lineage:** Track which agents originated from which templates

**Business Value:**
- Reduces time-to-value from hours to minutes
- Democratizes AI agent deployment for non-technical admins
- Enables marketplace ecosystem for industry-specific templates
- Supports both small business (all-in-one) and enterprise (role-based) use cases

---

## 1. Problem Statement

### Current State
- Each company must manually create agents, skills, and tool configurations
- No standardization across similar businesses (e.g., all marketing teams reinvent content strategist agents)
- High barrier to entry for new AgentOS users
- No way to share proven agent configurations

### Target State
- One-click deployment of complete AI teams
- Industry-specific templates (marketing, trading, IT services)
- Business function templates (risk compliance, HR, sales)
- Self-service model allows experimentation while maintaining admin control

### Success Criteria
- [ ] Import template from ZIP in <30 seconds
- [ ] Deploy 10-agent marketing team in <2 minutes
- [ ] User can discover and request template agents via gallery
- [ ] Admin can view deployment lineage and usage analytics
- [ ] Template can be updated and redeployed with change tracking

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TEMPLATE SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   IMPORT     │───▶│   TEMPLATE   │───▶│   DEPLOY     │      │
│  │   SERVICE    │    │   REGISTRY   │    │   ENGINE     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  ZIP Parser  │    │  Template    │    │   Entity     │      │
│  │  Validator   │    │  Entities    │    │  Factory     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   TEMPLATE   │    │   COMPANY    │    │    USER      │      │
│  │   GALLERY    │◄───│  INSTANCES   │◄───│ ASSIGNMENTS  │      │
│  │     UI       │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXISTING AGENTOS TABLES                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Agent   │  │  Skill   │  │   Tool   │  │   User   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Template-Aware Entities (Approach B) | Provides full lineage tracking, marketplace support, and future extensibility |
| **Entity Scope** | Core only (Agents + Skills + Tools) | Keeps v1 focused; workflows/memory/channels can be added later |
| **Deployment Model** | Self-Service + Admin Override | Balances user autonomy with admin control |
| **Storage Format** | JSON files in ZIP | Human-readable, version-controllable, easy to share |
| **Template Size** | 8-10 agents for marketing | Comprehensive enough to demonstrate value, manageable for v1 |

---

## 3. Data Model

### 3.1 New Tables

#### Table: `template`

Global registry of available templates.

```sql
CREATE TABLE template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    version VARCHAR(20) NOT NULL,
    category VARCHAR(50),
    target_company_size VARCHAR(20),
    author VARCHAR(100),
    license VARCHAR(50),
    manifest_json JSONB NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_template_category ON template(category);
CREATE INDEX idx_template_status ON template(status);
```

**Example Record:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "slug": "marketing-team-v1",
  "name": "AI Marketing Team",
  "description": "Complete AI marketing department with 10 specialized agents",
  "version": "1.2.0",
  "category": "marketing",
  "target_company_size": "small,medium",
  "author": "AgentOS Team",
  "license": "mit",
  "manifest_json": { /* full manifest */ },
  "is_system": false,
  "status": "active"
}
```

#### Table: `template_entity`

Individual agents, skills, and tools within a template.

```sql
CREATE TABLE template_entity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES template(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('agent', 'skill', 'tool')),
    entity_key VARCHAR(100) NOT NULL,
    entity_data JSONB NOT NULL,
    display_order INTEGER DEFAULT 0,
    tags TEXT[],
    dependencies TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(template_id, entity_type, entity_key)
);

CREATE INDEX idx_template_entity_template ON template_entity(template_id);
CREATE INDEX idx_template_entity_type ON template_entity(entity_type);
CREATE INDEX idx_template_entity_tags ON template_entity USING GIN(tags);
```

**Example Record:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "template_id": "550e8400-e29b-41d4-a716-446655440000",
  "entity_type": "agent",
  "entity_key": "content-strategist",
  "entity_data": {
    "name": "Content Strategist",
    "description": "Plans content calendar and strategy",
    "system_prompt": "You are an expert Content Strategist...",
    "model_alias": "blitz/master",
    "skills": ["keyword-research", "content-calendar"],
    "tools": ["hubspot-connector", "google-analytics"]
  },
  "display_order": 1,
  "tags": ["content", "strategy", "planning"],
  "dependencies": []
}
```

#### Table: `template_instance`

Per-company deployment of a template.

```sql
CREATE TABLE template_instance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES template(id),
    company_id UUID NOT NULL,
    deployed_by UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    deployed_at TIMESTAMP DEFAULT NOW(),
    last_sync_at TIMESTAMP,
    deployment_config JSONB,
    forked_entities UUID[],
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_template_instance_company ON template_instance(company_id);
CREATE INDEX idx_template_instance_template ON template_instance(template_id);
CREATE INDEX idx_template_instance_status ON template_instance(status);
```

#### Table: `template_user_assignment`

Which users have access to which template entities.

```sql
CREATE TABLE template_user_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES template_instance(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    entity_key VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'pending_approval')),
    assigned_by UUID NOT NULL,
    assigned_at TIMESTAMP DEFAULT NOW(),
    config_overrides JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_template_assignment_instance ON template_user_assignment(instance_id);
CREATE INDEX idx_template_assignment_user ON template_user_assignment(user_id);
CREATE INDEX idx_template_assignment_status ON template_user_assignment(status);
```

### 3.2 Modified Existing Tables

Add `template_origin` tracking to existing entities:

```sql
-- Track template lineage in existing tables
ALTER TABLE agent ADD COLUMN template_origin JSONB;
ALTER TABLE skill ADD COLUMN template_origin JSONB;
ALTER TABLE tool_registry ADD COLUMN template_origin JSONB;

-- Example template_origin JSON:
-- {
--   "template_id": "550e8400-e29b-41d4-a716-446655440000",
--   "entity_key": "content-strategist",
--   "instance_id": "770e8400-e29b-41d4-a716-446655440002",
--   "is_forked": false,
--   "deployed_at": "2026-03-15T10:30:00Z"
-- }
```

---

## 4. Template ZIP Format

### 4.1 Directory Structure

```
marketing-team-v1.2.0.zip
├── template.json                    # Manifest file
├── README.md                        # Human-readable documentation
├── assets/
│   ├── icon.svg                     # Template icon (64x64)
│   ├── preview.png                  # Preview image (1200x630)
│   └── screenshots/                 # Gallery screenshots
│       ├── dashboard.png
│       └── agents.png
├── agents/
│   ├── content-strategist.json
│   ├── seo-analyst.json
│   ├── social-media-manager.json
│   ├── email-campaign-manager.json
│   ├── marketing-data-analyst.json
│   ├── competitor-intelligence.json
│   ├── brand-guardian.json
│   ├── marketing-automation-architect.json
│   ├── lead-generation-specialist.json
│   └── performance-marketing-manager.json
├── skills/
│   ├── keyword-research.json
│   ├── content-calendar.json
│   ├── social-scheduler.json
│   ├── email-builder.json
│   ├── analytics-dashboard.json
│   ├── competitor-monitor.json
│   ├── brand-voice-check.json
│   ├── lead-scoring.json
│   └── workflow-builder.json
└── tools/
    ├── hubspot-connector.json
    ├── google-analytics.json
    ├── mailchimp-connector.json
    ├── linkedin-api.json
    ├── semrush-api.json
    └── canva-api.json
```

### 4.2 Manifest File (`template.json`)

```json
{
  "spec_version": "1.0",
  "template": {
    "slug": "marketing-team-v1",
    "name": "AI Marketing Team",
    "description": "Complete AI marketing department with 10 specialized agents for content, SEO, social media, email, analytics, and automation.",
    "version": "1.2.0",
    "category": "marketing",
    "tags": ["marketing", "content", "seo", "social-media", "email", "analytics", "automation"],
    "target_company_size": ["small", "medium"],
    "author": "AgentOS Team",
    "license": "mit",
    "homepage": "https://agentos.dev/templates/marketing-team",
    "requirements": {
      "min_agentos_version": "1.4.0",
      "required_integrations": ["hubspot", "mailchimp"],
      "optional_integrations": ["google-analytics", "semrush", "linkedin"]
    }
  },
  "entities": {
    "agents": {
      "count": 10,
      "files": [
        "content-strategist.json",
        "seo-analyst.json",
        "social-media-manager.json",
        "email-campaign-manager.json",
        "marketing-data-analyst.json",
        "competitor-intelligence.json",
        "brand-guardian.json",
        "marketing-automation-architect.json",
        "lead-generation-specialist.json",
        "performance-marketing-manager.json"
      ]
    },
    "skills": {
      "count": 9,
      "files": [
        "keyword-research.json",
        "content-calendar.json",
        "social-scheduler.json",
        "email-builder.json",
        "analytics-dashboard.json",
        "competitor-monitor.json",
        "brand-voice-check.json",
        "lead-scoring.json",
        "workflow-builder.json"
      ]
    },
    "tools": {
      "count": 6,
      "files": [
        "hubspot-connector.json",
        "google-analytics.json",
        "mailchimp-connector.json",
        "linkedin-api.json",
        "semrush-api.json",
        "canva-api.json"
      ]
    }
  },
  "deployment": {
    "default_assignments": {
      "content-strategist": ["marketing-manager", "content-lead"],
      "seo-analyst": ["seo-specialist"],
      "social-media-manager": ["social-media-manager"],
      "email-campaign-manager": ["email-marketer"],
      "marketing-data-analyst": ["data-analyst", "cmo"],
      "competitor-intelligence": ["strategy-team"],
      "brand-guardian": ["brand-manager", "marketing-manager"],
      "marketing-automation-architect": ["marketing-ops", "cmo"],
      "lead-generation-specialist": ["growth-marketer"],
      "performance-marketing-manager": ["paid-ads-manager"]
    },
    "recommended_roles": {
      "small_team": ["content-strategist", "social-media-manager", "email-campaign-manager"],
      "medium_team": ["all"],
      "enterprise": ["all"]
    }
  }
}
```

### 4.3 Entity Definition Examples

#### Agent Definition (`agents/content-strategist.json`)

```json
{
  "entity_type": "agent",
  "entity_key": "content-strategist",
  "name": "Content Strategist",
  "description": "Plans content calendar, ideates topics, and aligns content with business goals. Expert in content marketing strategy, editorial planning, and audience engagement.",
  "icon": "📝",
  "system_prompt": "You are an expert Content Strategist with 10+ years of experience in B2B and B2C content marketing. Your role is to:\n\n1. Develop comprehensive content strategies aligned with business objectives\n2. Create editorial calendars with topics, formats, and publishing schedules\n3. Ideate high-performing content based on audience research and competitive analysis\n4. Ensure brand voice consistency across all content\n5. Optimize content for SEO and conversion\n\nAlways consider:\n- Target audience pain points and interests\n- Business goals and KPIs\n- Content performance data\n- Seasonal trends and industry events\n- Resource constraints and team capacity",
  "model_alias": "blitz/master",
  "skills": ["keyword-research", "content-calendar", "brand-voice-check"],
  "tools": ["hubspot-connector", "google-analytics", "canva-api"],
  "memory_config": {
    "short_term": true,
    "medium_term": true,
    "long_term": true
  },
  "default_parameters": {
    "content_pillars": [],
    "target_audience": "",
    "posting_frequency": "3x per week",
    "content_types": ["blog", "social", "email", "video"],
    "tone_of_voice": "professional but approachable"
  },
  "tags": ["content", "strategy", "planning", "editorial"],
  "dependencies": []
}
```

#### Skill Definition (`skills/keyword-research.json`)

```json
{
  "entity_type": "skill",
  "entity_key": "keyword-research",
  "name": "Keyword Research",
  "description": "Research keywords, analyze search volume, competition, and search intent. Provides actionable keyword recommendations for content optimization.",
  "input_schema": {
    "type": "object",
    "properties": {
      "topic": {
        "type": "string",
        "description": "Main topic or seed keyword"
      },
      "location": {
        "type": "string",
        "description": "Geographic location for local search",
        "default": "us"
      },
      "language": {
        "type": "string",
        "description": "Language code",
        "default": "en"
      },
      "max_keywords": {
        "type": "integer",
        "description": "Maximum number of keywords to return",
        "default": 20
      }
    },
    "required": ["topic"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "keywords": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "keyword": { "type": "string" },
            "search_volume": { "type": "integer" },
            "difficulty": { "type": "number" },
            "cpc": { "type": "number" },
            "intent": { "type": "string", "enum": ["informational", "navigational", "commercial", "transactional"] }
          }
        }
      },
      "recommendations": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  },
  "tools_required": ["semrush-api"],
  "implementation": "python_function",
  "code_template": "async def keyword_research(topic: str, location: str = 'us', language: str = 'en', max_keywords: int = 20) -> dict:\n    \"\"\"Research keywords using SEMrush API.\"\"\"\n    # Implementation provided at runtime\n    pass",
  "tags": ["seo", "research", "keywords"],
  "dependencies": ["semrush-api"]
}
```

#### Tool Definition (`tools/hubspot-connector.json`)

```json
{
  "entity_type": "tool",
  "entity_key": "hubspot-connector",
  "name": "HubSpot Connector",
  "description": "Connect to HubSpot CRM for contact management, email campaigns, and marketing automation.",
  "category": "crm",
  "auth_type": "oauth2",
  "auth_config": {
    "client_id_required": true,
    "client_secret_required": true,
    "scopes": ["contacts", "content", "forms", "automation"],
    "auth_url": "https://app.hubspot.com/oauth/authorize",
    "token_url": "https://api.hubapi.com/oauth/v1/token"
  },
  "operations": [
    {
      "name": "get_contacts",
      "description": "Retrieve contacts from HubSpot",
      "method": "GET",
      "endpoint": "/crm/v3/objects/contacts",
      "parameters": {
        "limit": { "type": "integer", "default": 100 },
        "properties": { "type": "array", "items": { "type": "string" } }
      }
    },
    {
      "name": "create_contact",
      "description": "Create a new contact",
      "method": "POST",
      "endpoint": "/crm/v3/objects/contacts",
      "parameters": {
        "properties": { "type": "object" }
      }
    },
    {
      "name": "send_email",
      "description": "Send marketing email via HubSpot",
      "method": "POST",
      "endpoint": "/email/public/v1/singleEmail/send",
      "parameters": {
        "emailId": { "type": "integer" },
        "message": { "type": "object" },
        "contactProperties": { "type": "object" }
      }
    }
  ],
  "tags": ["crm", "email", "contacts", "automation"]
}
```

---

## 5. REST API Specification

### 5.1 Template Management (Admin)

#### Import Template
```http
POST /api/admin/templates/import
Content-Type: multipart/form-data
Authorization: Bearer <admin_token>

Body:
------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="marketing-team-v1.2.0.zip"
Content-Type: application/zip

<binary zip content>
------WebKitFormBoundary--

Response: 201 Created
{
  "template_id": "550e8400-e29b-41d4-a716-446655440000",
  "slug": "marketing-team-v1",
  "name": "AI Marketing Team",
  "version": "1.2.0",
  "entities_imported": {
    "agents": 10,
    "skills": 9,
    "tools": 6
  },
  "warnings": [],
  "status": "imported"
}

Errors:
- 400 Bad Request: Invalid ZIP structure
- 409 Conflict: Template with slug already exists
- 422 Unprocessable Entity: Schema validation failed
```

#### List Templates
```http
GET /api/admin/templates?category=marketing&status=active&page=1&limit=20
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "templates": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "slug": "marketing-team-v1",
      "name": "AI Marketing Team",
      "version": "1.2.0",
      "category": "marketing",
      "status": "active",
      "deployment_count": 15,
      "entity_counts": {
        "agents": 10,
        "skills": 9,
        "tools": 6
      },
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T10:00:00Z"
    }
  ],
  "pagination": {
    "total": 24,
    "page": 1,
    "limit": 20,
    "pages": 2
  }
}
```

#### Get Template Details
```http
GET /api/admin/templates/{template_id}
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "slug": "marketing-team-v1",
  "name": "AI Marketing Team",
  "description": "Complete AI marketing department...",
  "version": "1.2.0",
  "category": "marketing",
  "tags": ["marketing", "content", "seo"],
  "manifest": { /* full manifest */ },
  "entities": {
    "agents": [
      {
        "entity_key": "content-strategist",
        "name": "Content Strategist",
        "description": "Plans content calendar and strategy",
        "tags": ["content", "strategy"]
      }
    ],
    "skills": [...],
    "tools": [...]
  },
  "deployment_count": 15,
  "status": "active",
  "is_system": false,
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:00:00Z"
}
```

#### Update Template Status
```http
PATCH /api/admin/templates/{template_id}/status
Authorization: Bearer <admin_token>
Content-Type: application/json

Body:
{
  "status": "disabled"
}

Response: 200 OK
{
  "template_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "disabled",
  "updated_at": "2026-03-15T11:00:00Z"
}
```

#### Delete Template
```http
DELETE /api/admin/templates/{template_id}?force=false
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "deleted": true,
  "entities_removed": 25,
  "instances_affected": 0
}

# If force=false and instances exist:
Response: 409 Conflict
{
  "error": "Template has active deployments",
  "instance_count": 15,
  "use_force": true
}
```

#### Export Template
```http
GET /api/admin/templates/{template_id}/export
Authorization: Bearer <admin_token>

Response: 200 OK
Content-Type: application/zip
Content-Disposition: attachment; filename="marketing-team-v1.2.0.zip"

<binary zip content>
```

### 5.2 Template Deployment (Company Admin)

#### Deploy Template
```http
POST /api/templates/{template_id}/deploy
Authorization: Bearer <company_admin_token>
Content-Type: application/json

Body:
{
  "company_id": "880e8400-e29b-41d4-a716-446655440003",
  "assignments": {
    "content-strategist": ["user-uuid-1", "user-uuid-2"],
    "seo-analyst": ["user-uuid-3"]
    // Omit agents for self-service
  },
  "config_overrides": {
    "content-strategist": {
      "default_parameters": {
        "content_pillars": ["AI", "Automation", "Productivity"]
      }
    }
  },
  "enable_self_service": true
}

Response: 201 Created
{
  "instance_id": "990e8400-e29b-41d4-a716-446655440004",
  "template_id": "550e8400-e29b-41d4-a716-446655440000",
  "company_id": "880e8400-e29b-41d4-a716-446655440003",
  "status": "active",
  "entities_deployed": {
    "agents": 10,
    "skills": 9,
    "tools": 6
  },
  "assignments_created": 15,
  "deployed_at": "2026-03-15T10:30:00Z"
}
```

#### List Company Template Instances
```http
GET /api/companies/{company_id}/templates
Authorization: Bearer <company_admin_token>

Response: 200 OK
{
  "instances": [
    {
      "instance_id": "990e8400-e29b-41d4-a716-446655440004",
      "template": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "AI Marketing Team",
        "version": "1.2.0",
        "icon_url": "/api/templates/550e8400-e29b-41d4-a716-446655440000/icon"
      },
      "status": "active",
      "deployed_at": "2026-03-15T10:30:00Z",
      "user_count": 12,
      "entity_counts": {
        "agents": 10,
        "skills": 9,
        "tools": 6
      }
    }
  ]
}
```

#### Update Instance Status
```http
PATCH /api/templates/instances/{instance_id}/status
Authorization: Bearer <company_admin_token>
Content-Type: application/json

Body:
{
  "status": "paused"
}

Response: 200 OK
{
  "instance_id": "990e8400-e29b-41d4-a716-446655440004",
  "status": "paused",
  "updated_at": "2026-03-15T12:00:00Z"
}
```

#### Manage User Assignments
```http
POST /api/templates/instances/{instance_id}/assignments
Authorization: Bearer <company_admin_token>
Content-Type: application/json

Body:
{
  "user_id": "user-uuid-5",
  "entity_key": "content-strategist",
  "action": "assign",
  "config_overrides": {}
}

Response: 201 Created
{
  "assignment_id": "aa0e8400-e29b-41d4-a716-446655440005",
  "instance_id": "990e8400-e29b-41d4-a716-446655440004",
  "user_id": "user-uuid-5",
  "entity_key": "content-strategist",
  "status": "active",
  "assigned_at": "2026-03-15T13:00:00Z"
}

# Revoke access
Body:
{
  "user_id": "user-uuid-5",
  "entity_key": "content-strategist",
  "action": "revoke"
}

Response: 200 OK
{
  "assignment_id": "aa0e8400-e29b-41d4-a716-446655440005",
  "status": "revoked",
  "revoked_at": "2026-03-15T14:00:00Z"
}
```

### 5.3 User-Facing Endpoints

#### Template Gallery
```http
GET /api/templates/gallery?category=marketing&search=content
Authorization: Bearer <user_token>

Response: 200 OK
{
  "templates": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "AI Marketing Team",
      "description": "Complete AI marketing department...",
      "category": "marketing",
      "tags": ["marketing", "content", "seo"],
      "icon_url": "/api/templates/550e8400-e29b-41d4-a716-446655440000/icon",
      "is_deployed": true,
      "has_access": ["content-strategist", "seo-analyst"],
      "available_agents": [
        {
          "entity_key": "content-strategist",
          "name": "Content Strategist",
          "description": "Plans content calendar...",
          "icon": "📝",
          "has_access": true,
          "agent_id": "bb0e8400-e29b-41d4-a716-446655440006"
        },
        {
          "entity_key": "social-media-manager",
          "name": "Social Media Manager",
          "description": "Manages social presence...",
          "icon": "📱",
          "has_access": false,
          "can_request": true
        }
      ]
    }
  ]
}
```

#### Get User's Template Agents
```http
GET /api/users/me/template-agents
Authorization: Bearer <user_token>

Response: 200 OK
{
  "agents": [
    {
      "agent_id": "bb0e8400-e29b-41d4-a716-446655440006",
      "name": "Content Strategist",
      "description": "Plans content calendar...",
      "icon": "📝",
      "template": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "AI Marketing Team",
        "version": "1.2.0"
      },
      "instance_id": "990e8400-e29b-41d4-a716-446655440004",
      "assigned_at": "2026-03-15T10:30:00Z",
      "last_used": "2026-03-15T15:30:00Z"
    }
  ]
}
```

#### Request Access to Template Agent
```http
POST /api/templates/instances/{instance_id}/request-access
Authorization: Bearer <user_token>
Content-Type: application/json

Body:
{
  "entity_key": "social-media-manager",
  "reason": "Need to manage social campaigns for Q2 product launch"
}

Response: 201 Created
{
  "request_id": "cc0e8400-e29b-41d4-a716-446655440007",
  "instance_id": "990e8400-e29b-41d4-a716-446655440004",
  "entity_key": "social-media-manager",
  "status": "pending_approval",
  "requested_at": "2026-03-15T16:00:00Z"
}
```

---

## 6. Frontend UI Design

### 6.1 Admin Template Management

#### Template Import Page (`/admin/templates/import`)

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Templates > Import Template                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │            [   DRAG & DROP   ]                      │   │
│  │                                                     │   │
│  │         Drop template ZIP file here                 │   │
│  │                                                     │   │
│  │         or click to browse files                    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Template Requirements:                                      │
│  • ZIP file format                                          │
│  • Contains template.json manifest                          │
│  • Valid AgentOS v1.4+ entities                             │
│  • Max file size: 50MB                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Import Preview Modal:**
```
┌─────────────────────────────────────────────────────────────┐
│  Preview: marketing-team-v1.2.0.zip              [×]        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📦 AI Marketing Team v1.2.0                                │
│  Complete AI marketing department with 10 agents            │
│                                                              │
│  Entities to Import:                                        │
│  • 10 Agents    [Content Strategist, SEO Analyst...]       │
│  • 9 Skills     [Keyword Research, Content Calendar...]    │
│  • 6 Tools      [HubSpot, Google Analytics...]             │
│                                                              │
│  ⚠️ Warnings:                                               │
│  • Tool 'semrush-api' requires API key configuration       │
│                                                              │
│  [Cancel]                                    [Import Now]   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Template List Page (`/admin/templates`)

**Card Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Templates                                      [+ Import]   │
├─────────────────────────────────────────────────────────────┤
│  Filter: [All Categories ▼] [Status: Active ▼]  [Search...] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🎯 AI Marketing Team                               │   │
│  │  v1.2.0 • marketing • Active                       │   │
│  │                                                      │   │
│  │  Complete AI marketing department...                │   │
│  │                                                      │   │
│  │  📊 15 deployments  •  10 agents  •  9 skills       │   │
│  │                                                      │   │
│  │  [View] [Deploy] [Export] [Disable] [Delete]        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🏢 IT Service Desk                                 │   │
│  │  v2.0.0 • it-service • Active                      │   │
│  │  ...                                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Template Detail Page (`/admin/templates/{id}`)

**Tabbed Interface:**
```
┌─────────────────────────────────────────────────────────────┐
│  Templates > AI Marketing Team                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Overview] [Agents] [Skills] [Tools] [Deployments]         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🎯 AI Marketing Team                                       │
│  v1.2.0 | Category: marketing | Status: Active | 15 deploys │
│                                                              │
│  Complete AI marketing department with 10 specialized       │
│  agents for content, SEO, social media, email, analytics,   │
│  and automation.                                            │
│                                                              │
│  Tags: marketing, content, seo, social-media, email         │
│                                                              │
│  Requirements:                                              │
│  • Min AgentOS: v1.4.0                                     │
│  • Required: HubSpot, Mailchimp                            │
│  • Optional: Google Analytics, SEMrush, LinkedIn           │
│                                                              │
│  Created: Mar 15, 2026 | Updated: Mar 15, 2026              │
│                                                              │
│  [Export] [Edit] [Disable]                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Template Deployment Page (`/admin/templates/{id}/deploy`)

**Deployment Wizard:**
```
┌─────────────────────────────────────────────────────────────┐
│  Deploy: AI Marketing Team                       Step 2 of 3│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Select Company                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🔍 Acme Corporation                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  2. Assign Agents to Users                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📝 Content Strategist                               │   │
│  │     Assign to: [Alice M. ▼] [Bob S. ▼] [+ Add...]   │   │
│  │     or [✓] Allow self-service requests              │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  🔍 SEO Analyst                                      │   │
│  │     Assign to: [Carol D. ▼] [+ Add...]              │   │
│  │     or [✓] Allow self-service requests              │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  📱 Social Media Manager                             │   │
│  │     Assign to: [Search users...]                    │   │
│  │     or [✓] Allow self-service requests              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  [← Back]                                [Next: Review →]   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 User Template Gallery (`/templates/gallery`)

**Gallery Grid:**
```
┌─────────────────────────────────────────────────────────────┐
│  Template Gallery                                [My Agents]│
├─────────────────────────────────────────────────────────────┤
│  Filter: [All ▼] [🔍 Search templates...]                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🎯 AI Marketing Team                          ✓    │   │
│  │                                                      │   │
│  │  Complete AI marketing department...                │   │
│  │  Category: Marketing | 10 agents available          │   │
│  │                                                      │   │
│  │  ✅ You have access to:                             │   │
│  │     • Content Strategist                            │   │
│  │     • SEO Analyst                                   │   │
│  │                                                      │   │
│  │  🔒 Request access:                                 │   │
│  │     • Social Media Manager [Request]                │   │
│  │     • Email Campaign Manager [Request]              │   │
│  │                                                      │   │
│  │  [View Details]                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🏢 IT Service Desk                                 │   │
│  │  ...                                                │   │
│  │  [View Details]                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 User "My Template Agents" (`/my-agents`)

**Agent List:**
```
┌─────────────────────────────────────────────────────────────┐
│  My AI Agents                                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  From AI Marketing Team:                                    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📝 Content Strategist                               │   │
│  │  Plans content calendar and strategy                │   │
│  │                                                      │   │
│  │  Skills: Content Calendar, Keyword Research         │   │
│  │  Last used: 2 hours ago                             │   │
│  │                                                      │   │
│  │  [Chat Now] [Configure]                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🔍 SEO Analyst                                      │   │
│  │  Keyword research and optimization                  │   │
│  │  ...                                                │   │
│  │  [Chat Now] [Configure]                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  [Browse Template Gallery]                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Marketing Template: 10 Agents Specification

### 7.1 Agent Overview

| # | Agent | Icon | Primary Role | Key Value Proposition |
|---|-------|------|--------------|----------------------|
| 1 | **Content Strategist** | 📝 | Editorial planning | Creates data-driven content calendars aligned with business goals |
| 2 | **SEO Analyst** | 🔍 | Search optimization | Identifies high-value keywords and optimization opportunities |
| 3 | **Social Media Manager** | 📱 | Social presence | Manages multi-platform content and engagement |
| 4 | **Email Campaign Manager** | ✉️ | Email marketing | Builds automated email sequences and newsletters |
| 5 | **Marketing Data Analyst** | 📊 | Analytics & reporting | Tracks ROI and provides actionable insights |
| 6 | **Competitor Intelligence** | 🕵️ | Market research | Monitors competitors and identifies market gaps |
| 7 | **Brand Guardian** | 🛡️ | Brand consistency | Ensures all content maintains brand voice and standards |
| 8 | **Marketing Automation Architect** | ⚙️ | Workflow automation | Builds complex trigger-based marketing workflows |
| 9 | **Lead Generation Specialist** | 🎯 | Conversion optimization | Optimizes landing pages and lead capture |
| 10 | **Performance Marketing Manager** | 📈 | Paid advertising | Manages PPC campaigns and ad spend optimization |

### 7.2 Detailed Agent Specifications

#### Agent 1: Content Strategist

**System Prompt:**
```
You are an expert Content Strategist with 10+ years of experience in B2B and B2C content marketing.

YOUR ROLE:
• Develop comprehensive content strategies aligned with business objectives
• Create editorial calendars with topics, formats, and publishing schedules
• Ideate high-performing content based on audience research and competitive analysis
• Ensure brand voice consistency across all content
• Optimize content for SEO and conversion

WORKFLOW:
1. Understand business goals and target audience
2. Research competitors and content gaps
3. Develop content pillars and themes
4. Create editorial calendar with diverse formats
5. Define success metrics and KPIs
6. Iterate based on performance data

ALWAYS CONSIDER:
• Target audience pain points and interests
• Business goals and KPIs
• Content performance data
• Seasonal trends and industry events
• Resource constraints and team capacity

OUTPUT FORMAT:
Provide structured recommendations with clear action items, timelines, and expected outcomes.
```

**Skills:**
1. **Content Calendar** - Create editorial calendars with topics, deadlines, and assignments
2. **Topic Ideation** - Generate content ideas based on trends, keywords, and audience needs
3. **Brand Voice Check** - Ensure content aligns with brand guidelines

**Tools:**
- HubSpot Connector (content performance)
- Google Analytics (traffic analysis)
- Canva API (visual content briefs)

**Default Parameters:**
```json
{
  "content_pillars": [],
  "target_audience": "",
  "posting_frequency": "3x per week",
  "content_types": ["blog", "social", "email", "video"],
  "tone_of_voice": "professional but approachable",
  "content_goals": ["thought_leadership", "lead_generation", "brand_awareness"]
}
```

#### Agent 2: SEO Analyst

**System Prompt:**
```
You are a senior SEO Analyst with deep expertise in technical SEO, content optimization, and search engine algorithms.

YOUR ROLE:
• Conduct comprehensive keyword research and competitive analysis
• Identify on-page and technical SEO opportunities
• Track search rankings and organic traffic performance
• Recommend content optimization strategies
• Monitor algorithm updates and industry trends

WORKFLOW:
1. Analyze target keywords and search intent
2. Audit existing content for SEO opportunities
3. Research competitor SEO strategies
4. Prioritize optimization recommendations by impact
5. Track performance and iterate

FOCUS AREAS:
• Keyword research (volume, difficulty, intent)
• On-page optimization (titles, meta, headings, content)
• Technical SEO (site speed, mobile, structured data)
• Link building opportunities
• Local SEO (when applicable)

OUTPUT FORMAT:
Provide prioritized recommendations with expected impact scores, implementation effort, and step-by-step guidance.
```

**Skills:**
1. **Keyword Research** - Find high-value keywords with search volume and difficulty analysis
2. **On-Page SEO** - Optimize content structure, meta tags, and internal linking
3. **Competitor SEO Analysis** - Analyze competitor keyword strategies and rankings

**Tools:**
- SEMrush API (keyword data, competitor analysis)
- Google Search Console (performance data)
- HubSpot Connector (content inventory)

**Default Parameters:**
```json
{
  "target_keywords": [],
  "competitor_domains": [],
  "target_locations": ["us"],
  "priority_pages": [],
  "seo_goals": ["organic_traffic", "keyword_rankings", "conversions"]
}
```

#### Agent 3: Social Media Manager

**System Prompt:**
```
You are a creative Social Media Manager with expertise in multi-platform content strategy and community engagement.

YOUR ROLE:
• Create platform-specific content for LinkedIn, Twitter, Instagram, Facebook
• Develop posting schedules optimized for audience engagement
• Monitor social trends and viral opportunities
• Engage with followers and manage community
• Track social metrics and ROI

PLATFORM EXPERTISE:
• LinkedIn: B2B thought leadership, professional content
• Twitter: Real-time engagement, threads, newsjacking
• Instagram: Visual storytelling, Stories, Reels
• Facebook: Community building, events, groups

CONTENT STRATEGY:
• 40% educational/value content
• 30% engagement/community content
• 20% promotional content
• 10% behind-the-scenes/personality

OUTPUT FORMAT:
Provide ready-to-post content with hashtags, optimal posting times, and engagement predictions.
```

**Skills:**
1. **Social Scheduler** - Plan and schedule posts across platforms
2. **Content Adaptation** - Repurpose content for different platforms
3. **Engagement Monitor** - Track mentions, comments, and engagement metrics

**Tools:**
- LinkedIn API (professional networking)
- Buffer (scheduling - optional)
- Canva API (visual content creation)

**Default Parameters:**
```json
{
  "active_platforms": ["linkedin", "twitter"],
  "posting_schedule": {
    "linkedin": "3x per week",
    "twitter": "daily"
  },
  "brand_voice": "professional",
  "content_mix": {
    "educational": 0.4,
    "engagement": 0.3,
    "promotional": 0.2,
    "personality": 0.1
  }
}
```

#### Agent 4: Email Campaign Manager

**System Prompt:**
```
You are an expert Email Marketing Specialist focused on deliverability, engagement, and conversion optimization.

YOUR ROLE:
• Design email campaigns for newsletters, promotions, and nurturing
• Build automated email sequences and drip campaigns
• Segment audiences for personalized messaging
• A/B test subject lines, content, and CTAs
• Monitor deliverability and engagement metrics

CAMPAIGN TYPES:
• Welcome sequences
• Nurture campaigns
• Promotional blasts
• Re-engagement campaigns
• Event invitations
• Product announcements

BEST PRACTICES:
• Personalization beyond first name
• Mobile-optimized design
• Clear single CTAs
• Spam score optimization
• Send time optimization

OUTPUT FORMAT:
Provide complete email copy with subject lines, preview text, body content, and recommended segments.
```

**Skills:**
1. **Email Builder** - Create email copy with subject lines and CTAs
2. **A/B Testing** - Design and analyze email tests
3. **List Segmentation** - Create targeted audience segments

**Tools:**
- Mailchimp Connector (email campaigns)
- HubSpot Connector (CRM integration)

**Default Parameters:**
```json
{
  "email_types": ["newsletter", "promotional", "nurture"],
  "sending_frequency": "weekly",
  "personalization_level": "high",
  "brand_voice": "professional",
  "cta_style": "action-oriented"
}
```

#### Agent 5: Marketing Data Analyst

**System Prompt:**
```
You are a Marketing Data Analyst who transforms complex data into actionable business insights.

YOUR ROLE:
• Build marketing dashboards and performance reports
• Analyze campaign ROI and attribution
• Identify trends and anomalies in marketing data
• Forecast future performance based on historical data
• Recommend data-driven optimizations

KEY METRICS:
• Traffic: sessions, users, pageviews, bounce rate
• Engagement: time on site, pages per session, events
• Conversion: leads, MQLs, SQLs, customers, revenue
• Channel performance: organic, paid, social, email, direct
• Funnel analysis: awareness → consideration → decision

REPORTING:
• Weekly performance summaries
• Monthly deep-dive analysis
• Campaign-specific reports
• Competitive benchmarking

OUTPUT FORMAT:
Provide data visualizations (descriptions), key insights, and specific recommendations with expected impact.
```

**Skills:**
1. **Dashboard Builder** - Create custom marketing dashboards
2. **Report Generation** - Automated marketing reports
3. **Attribution Analysis** - Multi-touch attribution modeling

**Tools:**
- Google Analytics (web analytics)
- HubSpot Connector (CRM data)
- Google Sheets API (reporting)

**Default Parameters:**
```json
{
  "reporting_frequency": "weekly",
  "key_metrics": ["sessions", "leads", "mqls", "customers", "revenue"],
  "attribution_model": "multi-touch",
  "comparison_periods": ["week_over_week", "year_over_year"]
}
```

#### Agent 6: Competitor Intelligence

**System Prompt:**
```
You are a Competitive Intelligence Analyst who monitors market landscape and identifies strategic opportunities.

YOUR ROLE:
• Track competitor marketing activities and positioning
• Analyze competitor content strategies and performance
• Monitor pricing changes and product launches
• Identify market gaps and white space opportunities
• Provide strategic recommendations based on competitive analysis

MONITORING AREAS:
• Website changes and messaging updates
• Content publication frequency and topics
• Social media activity and engagement
• Advertising campaigns and spend estimates
• Customer reviews and sentiment
• Job postings (indicating growth areas)

ANALYSIS FRAMEWORK:
• SWOT analysis for key competitors
• Feature comparison matrices
• Market positioning maps
• Share of voice analysis

OUTPUT FORMAT:
Provide actionable intelligence briefs with strategic implications and recommended responses.
```

**Skills:**
1. **Competitor Monitor** - Track competitor activities and changes
2. **Sentiment Analysis** - Analyze customer sentiment toward competitors
3. **Gap Analysis** - Identify underserved market opportunities

**Tools:**
- SEMrush API (competitor data)
- LinkedIn API (company updates)
- Web scraping (public data)

**Default Parameters:**
```json
{
  "competitors": [],
  "monitoring_frequency": "daily",
  "alert_triggers": ["pricing_changes", "new_features", "funding_news"],
  "analysis_depth": "detailed"
}
```

#### Agent 7: Brand Guardian

**System Prompt:**
```
You are the Brand Guardian ensuring all marketing materials align with brand standards and voice.

YOUR ROLE:
• Review content for brand voice consistency
• Ensure visual identity compliance
• Maintain messaging alignment across channels
• Enforce brand guidelines and standards
• Train team members on brand best practices

BRAND ELEMENTS:
• Voice and tone (authoritative, friendly, innovative, etc.)
• Messaging pillars and key points
• Visual identity (colors, fonts, imagery style)
• Terminology and word choice
• Values and mission alignment

REVIEW PROCESS:
1. Check voice and tone alignment
2. Verify messaging accuracy
3. Ensure visual consistency (briefs)
4. Validate terminology usage
5. Confirm values alignment

OUTPUT FORMAT:
Provide specific feedback with corrections and educational context about brand guidelines.
```

**Skills:**
1. **Brand Voice Check** - Validate content against brand voice guidelines
2. **Visual Guidelines** - Ensure visual content meets brand standards
3. **Messaging Review** - Check consistency with brand messaging

**Tools:**
- Canva API (visual brand compliance)
- HubSpot Connector (content library)

**Default Parameters:**
```json
{
  "brand_voice": "professional_innovative",
  "messaging_pillars": [],
  "forbidden_words": [],
  "required_disclaimers": [],
  "tone_guidelines": {
    "formality": "medium",
    "enthusiasm": "high",
    "technical_level": "accessible"
  }
}
```

#### Agent 8: Marketing Automation Architect

**System Prompt:**
```
You are a Marketing Automation Architect who designs sophisticated, trigger-based marketing workflows.

YOUR ROLE:
• Build complex automation workflows and sequences
• Design lead scoring models
• Create nurture campaigns with branching logic
• Integrate marketing tools for seamless data flow
• Optimize automation performance and conversion rates

AUTOMATION TYPES:
• Lead nurture sequences (behavior-based)
• Customer onboarding workflows
• Re-engagement campaigns
• Event-triggered communications
• Lifecycle marketing automation
• Account-based marketing workflows

LEAD SCORING:
• Demographic scoring (company size, role, industry)
• Behavioral scoring (website visits, content downloads, email engagement)
• Intent scoring (pricing page visits, demo requests)

OUTPUT FORMAT:
Provide workflow diagrams (text-based), trigger logic, and implementation specifications.
```

**Skills:**
1. **Workflow Builder** - Create marketing automation workflows
2. **Lead Scoring** - Design and implement lead scoring models
3. **Nurture Sequences** - Build multi-touch nurture campaigns

**Tools:**
- HubSpot Connector (automation platform)
- Mailchimp Connector (email automation)
- Zapier (integration workflows)

**Default Parameters:**
```json
{
  "automation_platforms": ["hubspot"],
  "lead_scoring_threshold": 75,
  "nurture_email_count": 5,
  "nurture_duration_days": 30,
  "trigger_events": ["form_submit", "page_view", "email_open"]
}
```

#### Agent 9: Lead Generation Specialist

**System Prompt:**
```
You are a Lead Generation Specialist focused on optimizing conversion paths and capturing qualified leads.

YOUR ROLE:
• Design high-converting landing pages
• Create compelling lead magnets and offers
• Optimize forms and CTAs for conversion
• Implement lead capture across touchpoints
• Analyze and improve conversion funnels

LEAD GENERATION STRATEGIES:
• Content offers (ebooks, guides, templates)
• Webinar and event registrations
• Free tools and calculators
• Demo and consultation requests
• Newsletter subscriptions
• Trial signups

OPTIMIZATION FOCUS:
• Headline and value proposition testing
• Form field optimization (reduce friction)
• CTA placement and design
• Social proof integration
• Exit-intent capture

OUTPUT FORMAT:
Provide landing page copy, form designs, and optimization recommendations with expected conversion lift.
```

**Skills:**
1. **Landing Page Optimizer** - Design and optimize landing pages
2. **Form Builder** - Create high-converting forms
3. **Lead Magnet Creator** - Develop compelling offers

**Tools:**
- HubSpot Connector (landing pages, forms)
- Unbounce (landing page builder)
- Canva API (lead magnet design)

**Default Parameters:**
```json
{
  "landing_page_goals": ["demo_request", "content_download", "newsletter"],
  "target_conversion_rate": 0.15,
  "form_fields": ["email", "company", "role"],
  "offer_types": ["ebook", "template", "webinar"]
}
```

#### Agent 10: Performance Marketing Manager

**System Prompt:**
```
You are a Performance Marketing Manager who drives ROI through data-driven paid advertising campaigns.

YOUR ROLE:
• Plan and execute PPC campaigns across Google Ads, Facebook, LinkedIn
• Manage ad budgets and bidding strategies
• Create compelling ad copy and creative briefs
• Optimize campaigns for CPA, ROAS, and LTV
• Provide performance reporting and insights

PLATFORM EXPERTISE:
• Google Ads: Search, Display, YouTube, Shopping
• Facebook/Instagram Ads: Awareness, consideration, conversion
• LinkedIn Ads: B2B targeting, thought leadership
• Retargeting: Website visitors, email lists, lookalikes

CAMPAIGN MANAGEMENT:
• Audience targeting and segmentation
• Ad creative optimization
• Landing page alignment
• Bid strategy management
• A/B testing at scale

OUTPUT FORMAT:
Provide campaign briefs, ad copy variations, targeting recommendations, and budget allocations.
```

**Skills:**
1. **Ad Copywriter** - Create compelling ad copy
2. **Campaign Optimizer** - Optimize bids, targeting, and creative
3. **Budget Manager** - Allocate spend across campaigns and platforms

**Tools:**
- Google Ads API (campaign management)
- Facebook Ads API (social advertising)
- LinkedIn API (B2B advertising)

**Default Parameters:**
```json
{
  "monthly_budget": 10000,
  "target_cpa": 150,
  "target_roas": 4.0,
  "active_platforms": ["google", "facebook"],
  "campaign_types": ["search", "display", "retargeting"],
  "audience_segments": ["lookalike", "retargeting", "interest_based"]
}
```

### 7.3 Marketing Skills (9 Total)

| Skill | Description | Primary Agents |
|-------|-------------|----------------|
| **Keyword Research** | Find keywords with volume, difficulty, intent | SEO Analyst |
| **Content Calendar** | Create editorial calendars with scheduling | Content Strategist |
| **Social Scheduler** | Plan and schedule social posts | Social Media Manager |
| **Email Builder** | Write email copy with subject lines | Email Campaign Manager |
| **Analytics Dashboard** | Build performance dashboards | Marketing Data Analyst |
| **Competitor Monitor** | Track competitor activities | Competitor Intelligence |
| **Brand Voice Check** | Validate brand consistency | Brand Guardian |
| **Lead Scoring** | Score leads based on behavior | Marketing Automation Architect |
| **Workflow Builder** | Create automation workflows | Marketing Automation Architect |

### 7.4 Marketing Tools (6 Total)

| Tool | Purpose | Integrated Agents |
|------|---------|-------------------|
| **HubSpot Connector** | CRM, email, automation | All marketing agents |
| **Google Analytics** | Web analytics | Content Strategist, SEO Analyst, Data Analyst |
| **Mailchimp Connector** | Email campaigns | Email Campaign Manager |
| **LinkedIn API** | B2B social, ads | Social Media Manager, Competitor Intelligence, Performance Manager |
| **SEMrush API** | SEO and competitor data | SEO Analyst, Competitor Intelligence |
| **Canva API** | Visual content | Content Strategist, Social Media Manager, Brand Guardian |

---

## 8. Error Handling & Edge Cases

### 8.1 Import Errors

| Error | Cause | Handling |
|-------|-------|----------|
| **Invalid ZIP** | Corrupted or non-ZIP file | Return 400 with "Invalid file format" |
| **Missing manifest** | No template.json found | Return 400 with "Missing template.json manifest" |
| **Schema validation** | Invalid JSON structure | Return 422 with detailed validation errors |
| **Duplicate slug** | Template with slug exists | Offer overwrite, skip, or auto-rename options |
| **Version mismatch** | Requires newer AgentOS | Return 422 with "Requires AgentOS vX.Y+" |
| **Invalid entity** | Malformed agent/skill/tool JSON | Import valid entities, report failures in warnings array |

### 8.2 Deployment Errors

| Error | Cause | Handling |
|-------|-------|----------|
| **Template disabled** | Template status = disabled | Return 403 with "Template is disabled" |
| **Already deployed** | Company has existing instance | Offer upgrade, duplicate, or reject options |
| **Missing tools** | Required tools not configured | Warning: "HubSpot not configured - configure to enable" |
| **Invalid user** | User ID not in company | Skip assignment, log warning |
| **Permission denied** | Non-admin deploying | Return 403 with admin contact info |

### 8.3 Runtime Errors

| Error | Cause | Handling |
|-------|-------|----------|
| **Forked entity** | User modified template agent | Mark `is_forked=true` in template_origin, preserve changes |
| **Template updated** | New version available | Notify admin with changelog, offer upgrade path |
| **Entity deleted** | Template agent deleted by user | Mark as forked, archive assignment, notify admin |
| **Access revoked** | User loses template access | Graceful degradation, hide agent from gallery |
| **Instance archived** | Company template instance archived | Read-only mode, no new assignments |

### 8.4 Conflict Resolution

**Fork Detection:**
```python
def detect_fork(agent_id: UUID, template_entity_data: dict) -> bool:
    """Detect if user has modified template agent."""
    agent = await get_agent(agent_id)
    
    # Compare key fields
    if (agent.system_prompt != template_entity_data['system_prompt'] or
        agent.skills != template_entity_data['skills'] or
        agent.tools != template_entity_data['tools']):
        return True
    
    return False
```

**Update Strategy:**
1. **Conservative:** Never overwrite user-modified agents
2. **Notify:** Admin sees "3 agents have custom modifications"
3. **Selective:** Admin can choose to force-update specific agents
4. **Backup:** Create backup of forked agents before update

---

## 9. Security Considerations

### 9.1 Access Control

| Endpoint | Required Role | Notes |
|----------|---------------|-------|
| `POST /api/admin/templates/import` | `it-admin` | System-wide template management |
| `GET /api/admin/templates` | `it-admin` | View all templates |
| `POST /api/templates/{id}/deploy` | Company admin | Deploy to own company only |
| `GET /api/templates/gallery` | Any authenticated user | View available templates |
| `GET /api/users/me/template-agents` | Any authenticated user | Own agents only |

### 9.2 Data Isolation

- Template entities are global (shared across companies)
- Template instances are per-company
- User assignments respect company boundaries
- Template origin tracking prevents cross-company data leakage

### 9.3 Safe Execution

- Template ZIPs are scanned for malicious content
- Entity JSON is validated against schemas
- Tool configurations are sanitized
- Skills code templates are syntax-checked but not executed during import

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# Test template import
def test_import_valid_template():
    """Should successfully import valid template ZIP."""
    
def test_import_invalid_zip():
    """Should reject corrupted ZIP files."""
    
def test_import_missing_manifest():
    """Should reject ZIP without template.json."""
    
def test_import_duplicate_slug():
    """Should handle duplicate template slugs appropriately."""

# Test deployment
def test_deploy_template():
    """Should create agents, skills, tools, and assignments."""
    
def test_deploy_disabled_template():
    """Should reject deployment of disabled template."""
    
def test_fork_detection():
    """Should detect when user modifies template agent."""
```

### 10.2 Integration Tests

```python
def test_end_to_end_template_workflow():
    """Complete flow: import → deploy → use → update."""
    
def test_template_gallery_with_assignments():
    """Verify gallery shows correct access status."""
    
def test_self_service_request_flow():
    """User requests access → Admin approves → Agent available."""
```

### 10.3 Marketing Template Tests

```python
def test_marketing_template_import():
    """Import marketing-team-v1.2.0.zip successfully."""
    
def test_all_10_agents_deployed():
    """Verify all 10 marketing agents are created."""
    
def test_agent_has_correct_skills():
    """Verify Content Strategist has content-calendar skill."""
    
def test_template_origin_tracking():
    """Verify agents have correct template_origin metadata."""
```

---

## 11. Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Deliverables:**
- Database migrations (4 new tables)
- Template ZIP parser and validator
- Import/export service
- Basic admin API endpoints (import, list, get, delete)

**Success Criteria:**
- Can import valid template ZIP
- Can list and view imported templates
- Can export template back to ZIP

### Phase 2: Entity Management (Week 3-4)
**Deliverables:**
- TemplateEntity CRUD operations
- Entity validation against schemas
- Admin UI for template list/detail views
- Template status management (enable/disable)

**Success Criteria:**
- Admin can browse template entities
- Can update template status
- Validation catches invalid entity JSON

### Phase 3: Deployment Engine (Week 5-6)
**Deliverables:**
- Template deployment service
- Entity factory (creates agents/skills/tools from templates)
- Assignment management
- Instance tracking

**Success Criteria:**
- Can deploy template to company
- Creates all entities with template_origin
- Handles config overrides
- Tracks forked entities

### Phase 4: User Gallery (Week 7)
**Deliverables:**
- Template gallery UI
- "My Template Agents" page
- Self-service access requests
- Assignment approval workflow

**Success Criteria:**
- Users can browse template gallery
- Users see agents they have access to
- Users can request access to new agents
- Admins can approve/reject requests

### Phase 5: Marketing Template (Week 8-9)
**Deliverables:**
- Create 10 marketing agent definitions
- Define 9 marketing skills
- Configure 6 marketing tool connectors
- Build marketing-team-v1.0.0.zip

**Success Criteria:**
- Marketing template imports successfully
- All 10 agents deploy correctly
- Agents have correct skills and tools
- Sample conversations work end-to-end

### Phase 6: Polish & Integration (Week 10)
**Deliverables:**
- Comprehensive error handling
- Documentation (API docs, user guides)
- Performance optimization
- Security hardening

**Success Criteria:**
- All edge cases handled gracefully
- API documentation complete
- Load testing passes (100 concurrent deployments)
- Security audit passed

---

## 12. Future Enhancements

### 12.1 v1.8+ Features

1. **Template Marketplace**
   - Public template repository
   - Rating and review system
   - Template discovery and search

2. **Template Variants**
   - Industry-specific customizations
   - Size-based variants (small/medium/enterprise)
   - Regional variants (language, compliance)

3. **Workflow Templates**
   - Pre-built canvas workflows
   - Automation sequence templates
   - Integration templates

4. **Template Analytics**
   - Usage analytics per template
   - Agent performance comparison
   - ROI tracking for template deployments

5. **Template Collaboration**
   - Multi-author templates
   - Version control and branching
   - Template pull requests

### 12.2 Additional Templates

Potential templates for future releases:

| Template | Category | Agents | Target |
|----------|----------|--------|--------|
| **IT Service Desk** | IT Service | 6 agents | IT teams |
| **Small Trading Company** | Trading | 8 agents | Finance |
| **Risk & Compliance** | Banking | 10 agents | Banks |
| **HR & Recruitment** | HR | 6 agents | HR departments |
| **Sales Team** | Sales | 8 agents | Sales orgs |
| **Customer Success** | Support | 6 agents | CS teams |
| **Product Management** | Product | 7 agents | Product teams |
| **Legal Assistant** | Legal | 5 agents | Legal departments |
| **Research Assistant** | Research | 6 agents | R&D teams |
| **Executive Assistant** | Admin | 4 agents | Executives |

---

## 13. References

### 13.1 Design References

1. **Snow AI Marketing Team**
   - https://snow.runbear.io/how-i-built-an-ai-marketing-team-with-claude-code-and-cowork-f3405a53ee22
   - Inspiration for multi-agent marketing team structure

2. **MindStudio AI Agents for Marketing**
   - https://www.mindstudio.ai/blog/ai-agents-for-marketing-teams
   - Marketing agent roles and responsibilities

3. **GitHub: AI Marketing Claude**
   - https://github.com/zubair-trabzada/ai-marketing-claude
   - Implementation patterns for marketing agents

4. **GitHub: Marketing Skills**
   - https://github.com/coreyhaines31/marketingskills
   - Marketing skill definitions and workflows

### 13.2 Related Topics

- **Topic #21: Universal Integration** - Tool connector framework
- **Topic #5: Universal Skill Import** - Skill packaging patterns
- **Topic #16: Multi-Agent Tab Architecture** - Agent UI patterns
- **Topic #20: Projects/Spaces** - Template deployment targets

---

## 14. Appendix

### 14.1 Glossary

| Term | Definition |
|------|------------|
| **Template** | A packaged collection of agents, skills, and tools for a specific business function |
| **Template Entity** | Individual agent, skill, or tool within a template |
| **Template Instance** | A deployment of a template to a specific company |
| **Forked Entity** | A template entity that has been modified by the user |
| **Self-Service** | Model allowing users to request access to template agents |
| **Template Origin** | Metadata tracking which template an entity came from |
| **Entity Key** | Unique identifier for an entity within a template |

### 14.2 File Locations

```
docs/enhancement/topics/23-plugin-templates/
├── 00-specification.md     # This document
├── 01-marketing-agents/    # Detailed agent specs
│   ├── content-strategist.md
│   ├── seo-analyst.md
│   └── ...
├── 02-marketing-skills/    # Skill definitions
├── 03-marketing-tools/     # Tool configurations
└── marketing-team-v1.0.0/  # Template package
    ├── template.json
    ├── agents/
    ├── skills/
    └── tools/
```

### 14.3 Migration Checklist

When migrating template system to production:

- [ ] Run database migrations
- [ ] Import system templates (if any)
- [ ] Configure tool credentials for templates
- [ ] Test import with sample template
- [ ] Test deployment to test company
- [ ] Verify user gallery access
- [ ] Monitor error rates
- [ ] Document admin procedures

---

*Document Version: 1.0*  
*Last Updated: 2026-03-15*  
*Status: Approved for Implementation*
